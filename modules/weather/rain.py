# modules/weather/rain.py
"""
Regenradar-module — beantwoordt vragen als "gaat het regenen?" en
"wanneer stopt het met regenen?", en zegt er bij hoe lang het nog duurt
("over ongeveer 25 minuten").

Hoe het werkt (puur symbolisch, geen ML/LLM):
1. Haalt de neerslagverwachting voor de komende ~2 uur op bij Buienradar
   (per 5 minuten). Lukt dat niet, dan valt ze terug op Open-Meteo
   (per 15 minuten, grover).
2. Zet elk tijdsblok om naar mm regen per uur en vergelijkt dat met een drempel.
3. Zoekt in die reeks "wanneer begint de regen" of "wanneer stopt de regen".
4. Giet het resultaat in vaste Nederlandse zinsjablonen.

Eerlijke beperkingen:
- Het is een SCHATTING van een regenradar. De eerste 30 minuten zijn het
  betrouwbaarst, daarna wordt het onzekerder. Vandaar "ongeveer".
- Het Buienradar-adres is onofficieel: het kan ooit veranderen of wegvallen.
  Daarom is Open-Meteo de reserve.
- Verder dan ~2 uur kijkt deze module niet.

Event: luistert naar "intent_rain" (de IntentRouter doet de detectie) en
antwoordt via "layer4_response", net als weather.py.
"""

import os
import requests
from collections import namedtuple
from datetime import datetime, timedelta
from dotenv import load_dotenv

try:
    from zoneinfo import ZoneInfo
except ImportError:  # heel oude Python-versies
    ZoneInfo = None

load_dotenv()

# -----------------------------------------------------
# Instellingen (hier kan je zelf aan draaien)
# -----------------------------------------------------
# Vanaf hoeveel mm/u we het "regen" noemen. 0.1 = de lichtste Buienradar-waarde.
REGEN_DREMPEL_MM_U = 0.1

# Een droog stuk telt pas als "het is gestopt" als het minstens zo lang duurt
# (anders zou 1 droog blokje tussen de regen al "gestopt" zijn).
MIN_DROOG_MINUTEN = 10

# Grenzen voor de woorden bij de intensiteit (mm per uur).
MOTREGEN_GRENS_MM_U = 0.5   # eronder: lichte motregen
LICHT_GRENS_MM_U = 2.5      # eronder: lichte regen
MATIG_GRENS_MM_U = 7.6      # eronder: matige regen, daarboven zware regen

# --- Proactieve melding ("over 15 minuten begint het te regenen") ---
PROACTIEF_VOORUIT_MINUTEN = 20   # melden als de regen binnen zoveel minuten begint
PROACTIEF_MIN_MM_U = 0.5         # alleen echte regen, geen motregen-spoortjes
PROACTIEF_MIN_TUSSENTIJD_MIN = 60  # nooit vaker dan 1 melding per uur
PROACTIEF_STIL_VAN_UUR = 23      # 's nachts geen spontane meldingen
PROACTIEF_STIL_TOT_UUR = 7

BUIENRADAR_URL = (
    "https://gpsgadget.buienradar.nl/data/raintext?lat={lat:.2f}&lon={lon:.2f}"
)
OPEN_METEO_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={lat:.4f}&longitude={lon:.4f}"
    "&minutely_15=precipitation&forecast_minutely_15=12"
    "&timezone=Europe%2FBrussels"
)

# Steden waarvan we de coördinaten al kennen (spaart een opzoeking).
BEKENDE_LOCATIES = {
    "aartrijke": (51.1192, 3.0903),
}

# Woorden die aangeven dat Kevin wil weten WANNEER HET STOPT.
STOP_WOORDEN = (
    "stopt", "stoppen", "ophouden", "houdt op", "weer droog",
    "voorbij", "afgelopen", "klaar met", "gedaan", "klaart",
)

# Eén tijdsblok uit de radar: wanneer het begint, wanneer het eindigt,
# en hoeveel mm regen per uur er in dat blok valt.
Slot = namedtuple("Slot", ["start", "einde", "mm_u"])


# -----------------------------------------------------
# Tijd
# -----------------------------------------------------
def nu_lokaal():
    """Huidige Belgische tijd, zonder tijdzone-info (zodat we gewoon kunnen
    vergelijken met de tijden uit de radar). Een container staat vaak op UTC,
    daarom rekenen we hier expliciet met Europe/Brussels. Lukt dat niet
    (bv. Windows zonder tzdata-pakket), dan vallen we terug op de
    computertijd."""
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo("Europe/Brussels")).replace(tzinfo=None)
        except Exception:
            pass
    return datetime.now()


# -----------------------------------------------------
# Data inlezen
# -----------------------------------------------------
def waarde_naar_mm_u(waarde):
    """Buienradar geeft een getal 0-255. 0 = droog. Anders geldt:
    mm/u = 10 ** ((waarde - 109) / 32)."""
    if waarde <= 0:
        return 0.0
    return 10 ** ((waarde - 109) / 32)


def parse_buienradar(tekst, nu):
    """Zet de Buienradar-tekst ('077|13:00' per regel) om in een lijst Slots.
    Het datum-deel ontbreekt in de tekst; we leiden het af uit 'nu' en
    houden rekening met het over middernacht gaan."""
    slots = []
    vorige_start = None

    for regel in tekst.splitlines():
        regel = regel.strip()
        if "|" not in regel:
            continue

        waarde_txt, tijd_txt = regel.split("|", 1)
        try:
            waarde = int(waarde_txt)
            uur_txt, minuut_txt = tijd_txt.strip().split(":")
            start = nu.replace(
                hour=int(uur_txt), minute=int(minuut_txt), second=0, microsecond=0
            )
        except ValueError:
            continue

        if vorige_start is None:
            # Eerste blok ligt vlak bij 'nu'. Staat het ver in het verleden,
            # dan bedoelt de radar 'na middernacht' (morgen).
            if start < nu - timedelta(hours=12):
                start += timedelta(days=1)
        elif start < vorige_start:
            start += timedelta(days=1)  # over middernacht heen

        vorige_start = start
        slots.append(Slot(start, start + timedelta(minutes=5), waarde_naar_mm_u(waarde)))

    return slots


def parse_open_meteo(data):
    """Zet het Open-Meteo-antwoord (per kwartier, mm per kwartier) om in
    Slots. Een kwartier-bedrag keer 4 = mm per uur."""
    try:
        tijden = data["minutely_15"]["time"]
        neerslag = data["minutely_15"]["precipitation"]
    except (KeyError, TypeError):
        return []

    slots = []
    for tijd_txt, mm in zip(tijden, neerslag):
        if mm is None:
            continue
        try:
            start = datetime.fromisoformat(tijd_txt)
        except ValueError:
            continue
        slots.append(Slot(start, start + timedelta(minutes=15), mm * 4))
    return slots


# -----------------------------------------------------
# Analyse: wanneer begint / stopt de regen?
# -----------------------------------------------------
def analyseer(slots, nu, drempel=REGEN_DREMPEL_MM_U, min_droog=MIN_DROOG_MINUTEN):
    """Zoekt in de reeks wanneer de regen begint of stopt.

    Geeft een dict terug (of None als er geen bruikbare blokken zijn):
      regent_nu   : True/False
      intensiteit : mm/u (piek van de huidige/eerstvolgende regenreeks)
      begin_min   : minuten tot de regen begint (enkel als het nu droog is)
      stop_min    : minuten tot de regen stopt (enkel als het nu regent)
      daarna_min  : minuten tot er na het stoppen weer regen komt (of None)
      horizon_min : hoe ver de data vooruit kijkt, in minuten
    """
    slots = [s for s in slots if s.einde > nu]  # blokken in het verleden weg
    if not slots:
        return None

    def regent(slot):
        return slot.mm_u >= drempel

    def minuten_tot(tijdstip):
        return max(0, int(round((tijdstip - nu).total_seconds() / 60)))

    huidig = slots[0]
    stap = max(1, int(round((huidig.einde - huidig.start).total_seconds() / 60)))

    analyse = {
        "regent_nu": regent(huidig),
        "intensiteit": huidig.mm_u,
        "begin_min": None,
        "stop_min": None,
        "daarna_min": None,
        "horizon_min": minuten_tot(slots[-1].einde),
    }

    if analyse["regent_nu"]:
        piek = 0.0
        stop_idx = None
        i = 0
        while i < len(slots):
            if regent(slots[i]):
                piek = max(piek, slots[i].mm_u)
                i += 1
                continue

            # Droog blok: hoe lang blijft het droog?
            j = i
            while j < len(slots) and not regent(slots[j]):
                j += 1

            # Telt als "gestopt" als het droge stuk lang genoeg is of tot het
            # einde van de data loopt. Een kort droog blokje tussen de regen
            # negeren we (regent daarna gewoon verder).
            if j == len(slots) or (j - i) * stap >= min_droog:
                stop_idx = i
                break
            i = j

        analyse["intensiteit"] = piek

        if stop_idx is not None:
            analyse["stop_min"] = minuten_tot(slots[stop_idx].start)
            for k in range(stop_idx, len(slots)):
                if regent(slots[k]):
                    analyse["daarna_min"] = minuten_tot(slots[k].start)
                    break
    else:
        for k in range(1, len(slots)):
            if regent(slots[k]):
                analyse["begin_min"] = minuten_tot(slots[k].start)
                piek = 0.0
                m = k
                while m < len(slots) and regent(slots[m]):
                    piek = max(piek, slots[m].mm_u)
                    m += 1
                analyse["intensiteit"] = piek
                break

    return analyse


# -----------------------------------------------------
# Zinnen (vaste Nederlandse sjablonen)
# -----------------------------------------------------
def duur_tekst(minuten):
    """34 -> '35 minuten', 80 -> '1 uur en 20 minuten', 120 -> '2 uur'.
    Vanaf 10 minuten ronden we af op 5, want nauwkeuriger is de radar niet."""
    if minuten >= 10:
        totaal = int(round(minuten / 5.0)) * 5
    else:
        totaal = int(minuten)

    uren, rest = divmod(totaal, 60)
    if uren == 0:
        return "1 minuut" if totaal == 1 else f"{totaal} minuten"
    if rest == 0:
        return f"{uren} uur"
    return f"{uren} uur en {rest} minuten"


def minuten_tekst(minuten):
    """'zo meteen' of 'over ongeveer 35 minuten'."""
    if minuten <= 2:
        return "zo meteen"
    return f"over ongeveer {duur_tekst(minuten)}"


def horizon_tekst(minuten):
    """Hoe ver de radar vooruit kijkt, op een natuurlijke manier:
    124 -> '2 uur', 169 -> '3 uur', 45 -> '45 minuten'. Vanaf een uur
    ronden we af op een half uur (nauwkeuriger hoeft dat niet)."""
    if minuten < 60:
        return duur_tekst(minuten)
    return duur_tekst(int(round(minuten / 30.0)) * 30)


def intensiteit_tekst(mm_u):
    if mm_u < MOTREGEN_GRENS_MM_U:
        return "lichte motregen"
    if mm_u < LICHT_GRENS_MM_U:
        return "lichte regen"
    if mm_u < MATIG_GRENS_MM_U:
        return "matige regen"
    return "zware regen"


def _daarna_zin(analyse):
    if analyse["daarna_min"] is not None:
        return f" Maar {minuten_tekst(analyse['daarna_min'])} begint het opnieuw te regenen."
    return (
        f" Daarna blijft het droog, zover ik de komende "
        f"{horizon_tekst(analyse['horizon_min'])} kan zien."
    )


def formuleer_begin(analyse):
    """Antwoord op: 'gaat het regenen?'"""
    soort = intensiteit_tekst(analyse["intensiteit"])
    horizon = horizon_tekst(analyse["horizon_min"])

    if analyse["regent_nu"]:
        if analyse["stop_min"] is None:
            return (
                f"Het regent nu al ({soort}) en dat blijft zo tot minstens "
                f"{horizon}. Verder kijk ik niet."
            )
        return (
            f"Het regent nu al ({soort}). "
            f"Het stopt {minuten_tekst(analyse['stop_min'])} met regenen."
            + _daarna_zin(analyse)
        )

    if analyse["begin_min"] is None:
        return f"Het blijft droog: de komende {horizon} zie ik geen regen aankomen."

    return (
        f"Het is nu droog. "
        f"Het begint {minuten_tekst(analyse['begin_min'])} te regenen ({soort})."
    )


def formuleer_stop(analyse):
    """Antwoord op: 'wanneer stopt het met regenen?'"""
    horizon = horizon_tekst(analyse["horizon_min"])

    if not analyse["regent_nu"]:
        if analyse["begin_min"] is not None:
            soort = intensiteit_tekst(analyse["intensiteit"])
            return (
                f"Het regent nu niet. Wel begint het "
                f"{minuten_tekst(analyse['begin_min'])} te regenen ({soort})."
            )
        return f"Het regent nu niet, en de komende {horizon} blijft het droog."

    if analyse["stop_min"] is None:
        return (
            f"Het blijft regenen tot minstens {horizon}. "
            f"Verder kijk ik niet."
        )

    return (
        f"Het stopt {minuten_tekst(analyse['stop_min'])} met regenen."
        + _daarna_zin(analyse)
    )


def beslis_proactief(analyse, nu, staat):
    """
    Beslist of Nova spontaan een melding moet doen. Geeft (zin of None, staat).
    'staat' is een dict met 'gemeld' (bool) en 'laatste' (datetime of None).

    Regels (alles in één plek, zodat het goed te testen is):
    - Stil 's nachts.
    - Regent het nu al: nooit melden, en de volgende bui mag weer gemeld worden.
    - Droog en de komende 2 uur geen regen: alles resetten.
    - Droog, regen binnen PROACTIEF_VOORUIT_MINUTEN, krachtig genoeg,
      nog niet gemeld en minstens een uur sinds de vorige melding: melden.
    - Blijft de voorspelling schommelen (18 -> 25 -> 18 min), dan wordt er
      NIET opnieuw gemeld: 'gemeld' wordt pas gewist als de regen er is
      geweest of volledig uit de voorspelling verdwenen is.
    """
    staat = dict(staat)
    if analyse is None:
        return None, staat

    if analyse["regent_nu"]:
        staat["gemeld"] = False
        return None, staat

    if analyse["begin_min"] is None:
        staat["gemeld"] = False
        return None, staat

    if nu.hour >= PROACTIEF_STIL_VAN_UUR or nu.hour < PROACTIEF_STIL_TOT_UUR:
        return None, staat
    if staat.get("gemeld"):
        return None, staat
    if analyse["begin_min"] > PROACTIEF_VOORUIT_MINUTEN:
        return None, staat
    if analyse["intensiteit"] < PROACTIEF_MIN_MM_U:
        return None, staat
    laatste = staat.get("laatste")
    if laatste is not None and (nu - laatste) < timedelta(minutes=PROACTIEF_MIN_TUSSENTIJD_MIN):
        return None, staat

    staat["gemeld"] = True
    staat["laatste"] = nu
    soort = intensiteit_tekst(analyse["intensiteit"])
    zin = f"Let op: het begint {minuten_tekst(analyse['begin_min'])} te regenen ({soort})."
    return zin, staat


def bepaal_vraagtype(text):
    """'stop' als Kevin wil weten wanneer het ophoudt, anders 'begin'."""
    t = text.lower()
    for woord in STOP_WOORDEN:
        if woord in t:
            return "stop"
    # "wanneer houdt het / de regen op": 'houdt' en 'op' staan los van elkaar
    if "houdt" in t and " op" in t:
        return "stop"
    return "begin"


# -----------------------------------------------------
# De module zelf
# -----------------------------------------------------
class RainModule:
    def __init__(self, event_bus, api_key=None, default_city="Aartrijke", default_country="BE"):
        self.event_bus = event_bus
        self.api_key = api_key
        self.default_city = default_city
        self.default_country = default_country
        self._coord_cache = {}
        self._proactief_staat = {"gemeld": False, "laatste": None}

        # Luistert enkel naar intent_rain (IntentRouter doet detectie)
        event_bus.subscribe("intent_rain", self.on_rain)

    # Tekst -> stad ("gaat het regenen in Gent" -> "gent")
    def extract_city(self, text):
        text = text.lower()
        if " in " not in text:
            return self.default_city
        city = text.split(" in ", 1)[1].strip()
        if not city:
            return self.default_city
        return city.split()[0].strip(".,!?;:")

    # Stad -> (lat, lon)
    def get_coordinates(self, city):
        sleutel = city.lower()
        if sleutel in BEKENDE_LOCATIES:
            return BEKENDE_LOCATIES[sleutel]
        if sleutel in self._coord_cache:
            return self._coord_cache[sleutel]
        if not self.api_key:
            return None

        url = (
            f"https://api.openweathermap.org/data/2.5/weather?"
            f"q={city},{self.default_country}&appid={self.api_key}"
        )
        try:
            data = requests.get(url, timeout=4).json()
            coords = (data["coord"]["lat"], data["coord"]["lon"])
        except Exception:
            return None

        self._coord_cache[sleutel] = coords
        return coords

    # (lat, lon) -> (slots, is_grove_bron)
    def haal_slots(self, lat, lon, nu):
        try:
            r = requests.get(BUIENRADAR_URL.format(lat=lat, lon=lon), timeout=5)
            if r.status_code == 200:
                slots = parse_buienradar(r.text, nu)
                if slots:
                    return slots, False
        except Exception:
            pass

        try:
            r = requests.get(OPEN_METEO_URL.format(lat=lat, lon=lon), timeout=5)
            if r.status_code == 200:
                slots = parse_open_meteo(r.json())
                if slots:
                    return slots, True
        except Exception:
            pass

        return [], False

    def maak_antwoord(self, city, vraagtype, nu=None):
        nu = nu or nu_lokaal()

        coords = self.get_coordinates(city)
        if coords is None:
            return f"Ik weet niet waar {city.title()} ligt, dus ik kan daar de regenradar niet bekijken."

        slots, grof = self.haal_slots(coords[0], coords[1], nu)
        if not slots:
            return "Ik kon de regenradar nu niet bereiken."

        analyse = analyseer(slots, nu)
        if analyse is None:
            return "De regenradar gaf me geen bruikbare gegevens."

        if vraagtype == "stop":
            zin = formuleer_stop(analyse)
        else:
            zin = formuleer_begin(analyse)

        if city.lower() != self.default_city.lower():
            zin = f"In {city.title()}: {zin}"
        if grof:
            zin += " (Let op: dit is een grovere schatting per kwartier.)"
        return zin

    def check_proactief(self, nu=None):
        """
        Wordt door main.py's achtergrond_loop() om de paar minuten
        aangeroepen. Kijkt enkel naar de standaardstad. Doet niets (en
        crasht nooit) als de radar niet bereikbaar is.
        Geeft de gepubliceerde zin terug, of None.
        """
        try:
            nu = nu or nu_lokaal()
            coords = self.get_coordinates(self.default_city)
            if coords is None:
                return None
            slots, _grof = self.haal_slots(coords[0], coords[1], nu)
            if not slots:
                return None
            analyse = analyseer(slots, nu)
            zin, self._proactief_staat = beslis_proactief(
                analyse, nu, self._proactief_staat
            )
            if zin:
                self.event_bus.publish("layer4_response", {"text": zin})
            return zin
        except Exception as e:
            print(f"[rain] proactieve check mislukt: {e}")
            return None

    def on_rain(self, data, event_type=None):
        text = (data.get("text") or "").lower()
        city = self.extract_city(text)
        vraagtype = bepaal_vraagtype(text)
        antwoord = self.maak_antwoord(city, vraagtype)
        self.event_bus.publish("layer4_response", {"text": antwoord})


def init_module(event_bus):
    API_KEY = os.getenv("OPENWEATHER_API_KEY")
    instance = RainModule(event_bus, API_KEY)
    event_bus.publish("module_loaded", {"name": "rain"})
    return instance