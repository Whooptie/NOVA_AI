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
import re
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

# --- Soort neerslag (sneeuw) en onweer ---
# WMO-weercodes, zoals Open-Meteo ze per kwartier teruggeeft.
SNEEUW_CODES = (71, 73, 75, 77, 85, 86)
ONWEER_CODES = (95, 96, 99)
ONWEER_VOORUIT_MINUTEN = 45     # onweer melden als het binnen zoveel minuten kan komen
ONWEER_WOORDEN = ("onweer", "onweert", "onweren")

# Aparte aanvraag voor het SOORT neerslag en onweer, zodat een fout hier de
# gewone regencheck (OPEN_METEO_URL hieronder) nooit kan breken.
OPEN_METEO_TYPE_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={lat:.4f}&longitude={lon:.4f}"
    "&minutely_15=rain,snowfall,weather_code"
    "&forecast_minutely_15=12&timezone=Europe%2FBrussels"
)

# --- Gladheid en harde wind vooruit ("kans op gladheid over ongeveer 1 uur") ---
# Zelfde venster en drempels als weather.py's weerwaarschuwing(), zodat
# "nu" en "straks" op dezelfde manier meten.
GLADHEID_MIN_C = 0              # gladheid: 0 tot 2 graden SAMEN met neerslag
GLADHEID_MAX_C = 2
WIND_DREMPEL_MS = 15            # gemiddelde wind in m/s (zoals weather.py)
VLAAG_DREMPEL_MS = 20           # windstoten in m/s (= 72 km/u)
GEVAAR_VOORUIT_MINUTEN = 120    # spontaan melden als het binnen zoveel minuten begint

# Aparte aanvraag (net als OPEN_METEO_TYPE_URL): een fout hier breekt de
# gewone regencheck nooit. Alle vier de velden zijn op 18 oktober 2026
# door Kevin getest en werken per kwartier.
OPEN_METEO_GEVAAR_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={lat:.4f}&longitude={lon:.4f}"
    "&minutely_15=temperature_2m,precipitation,wind_speed_10m,wind_gusts_10m"
    "&forecast_minutely_15=12&wind_speed_unit=ms&timezone=Europe%2FBrussels"
)

GROVE_BRON_NOOT = " (Let op: dit is een grovere schatting per kwartier.)"

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

# Woorden die NA "in" geen stad zijn: "in de stad", "in het weekend",
# "in de middag". Zonder deze lijst zou Nova "de" voor een stad aanzien en
# antwoorden "Ik weet niet waar De ligt".
GEEN_STAD_WOORDEN = frozenset({
    "de", "het", "een", "deze", "dit", "die", "dat", "mijn", "jouw", "uw",
    "onze", "ons", "komende", "volgende", "vorige", "vanavond", "vanmiddag",
    "vanochtend", "vannacht", "vandaag", "morgen", "overmorgen", "plaats",
})


def vind_stad(text, standaard):
    """Het woord na " in " dat een stad kan zijn, anders 'standaard'.
    'gaat het regenen in Gent' -> 'gent'; 'in de stad' -> standaard.
    Kijkt naar elke " in " in de zin (de eerste kan 'in de middag' zijn)."""
    text = text.lower()
    delen = text.split(" in ")[1:]
    for deel in delen:
        woorden = deel.strip().split()
        if not woorden:
            continue
        kandidaat = woorden[0].strip(".,!?;:")
        if kandidaat and kandidaat not in GEEN_STAD_WOORDEN:
            return kandidaat
    return standaard


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


# -----------------------------------------------------
# Soort neerslag: regen, sneeuw of natte sneeuw
# -----------------------------------------------------
Kwartier = namedtuple("Kwartier", ["start", "einde", "regen", "sneeuw", "code"])


def parse_typeinfo(data):
    """Zet het Open-Meteo-antwoord (rain, snowfall, weather_code per kwartier)
    om in Kwartier-objecten. Ontbrekende velden worden None; rommel geeft []."""
    try:
        blok = data["minutely_15"]
        tijden = blok["time"]
    except (KeyError, TypeError):
        return []
    if not isinstance(blok, dict) or not isinstance(tijden, list):
        return []

    def lijst(naam):
        waarden = blok.get(naam)
        return waarden if isinstance(waarden, list) else []

    regen, sneeuw, codes = lijst("rain"), lijst("snowfall"), lijst("weather_code")

    def pak(waarden, i):
        return waarden[i] if i < len(waarden) else None

    kwartieren = []
    for i, tijd_txt in enumerate(tijden):
        try:
            start = datetime.fromisoformat(tijd_txt)
        except (ValueError, TypeError):
            continue
        kwartieren.append(Kwartier(
            start, start + timedelta(minutes=15),
            pak(regen, i), pak(sneeuw, i), pak(codes, i),
        ))
    return kwartieren


def _kwartier_op(typeinfo, tijdstip):
    for k in typeinfo:
        if k.start <= tijdstip < k.einde:
            return k
    return None


def bepaal_soort(typeinfo, nu, analyse):
    """'regen', 'sneeuw' of 'natte sneeuw' voor het moment waar de zin over gaat:
    nu (als het regent) of het begin van de bui. Geen gegevens = 'regen'."""
    if not typeinfo or analyse is None:
        return "regen"
    if analyse["regent_nu"]:
        moment = nu
    elif analyse["begin_min"] is not None:
        moment = nu + timedelta(minutes=analyse["begin_min"])
    else:
        return "regen"

    k = _kwartier_op(typeinfo, moment)
    if k is None:
        return "regen"
    sneeuw = (k.sneeuw or 0) > 0 or k.code in SNEEUW_CODES
    regen = (k.regen or 0) > 0
    if sneeuw and regen:
        return "natte sneeuw"
    if sneeuw:
        return "sneeuw"
    return "regen"


def pas_soort_toe(zin, soort):
    """Vervangt de regen-woorden in een zin door sneeuw-woorden.
    'regen' laat de zin ongemoeid."""
    if soort == "regen":
        return zin
    if soort == "natte sneeuw":
        zin = re.sub(
            r"\((?:lichte motregen|lichte regen|matige regen|zware regen)\)",
            "(natte sneeuw)", zin,
        )
    else:
        zin = zin.replace("lichte motregen", "lichte regen")
    for oud, nieuw in (("regenen", "sneeuwen"), ("regent", "sneeuwt"), ("regen", "sneeuw")):
        zin = re.sub(rf"\b{oud}\b", nieuw, zin)
    return zin


# -----------------------------------------------------
# Onweer (verwachting van een weermodel, GEEN bliksemradar)
# -----------------------------------------------------
ONWEER_EERLIJK = (
    " Let op: onweer is moeilijk te voorspellen. "
    "Dit is een verwachting van een weermodel, geen bliksemradar."
)


def analyseer_onweer(typeinfo, nu):
    """Zoekt onweerscodes in de komende kwartieren.
    Geeft None zonder gegevens, anders een dict:
      nu          : True als er nu kans op onweer is
      begin_min   : minuten tot het (eerstvolgende) onweer, of None
      einde_min   : minuten tot dat onweer voorbij is (None = tot het einde van de data)
      horizon_min : hoe ver de data vooruit kijkt"""
    kw = sorted((k for k in typeinfo if k.einde > nu), key=lambda k: k.start)
    if not kw:
        return None

    def onweer(k):
        return k.code in ONWEER_CODES

    def minuten_tot(tijdstip):
        return max(0, int(round((tijdstip - nu).total_seconds() / 60)))

    info = {
        "nu": False,
        "begin_min": None,
        "einde_min": None,
        "horizon_min": minuten_tot(kw[-1].einde),
    }
    i = 0
    while i < len(kw) and not onweer(kw[i]):
        i += 1
    if i == len(kw):
        return info

    info["begin_min"] = minuten_tot(kw[i].start) if kw[i].start > nu else 0
    info["nu"] = info["begin_min"] == 0
    j = i
    while j < len(kw) and onweer(kw[j]):
        j += 1
    info["einde_min"] = None if j == len(kw) else minuten_tot(kw[j].start)
    return info


def formuleer_onweer(info):
    """Antwoord op: 'gaat het onweren?' / 'wanneer stopt het onweer?'"""
    if info["nu"]:
        if info["einde_min"] is None:
            zin = (
                f"Er is nu kans op onweer, en dat blijft zo tot minstens "
                f"{horizon_tekst(info['horizon_min'])}."
            )
        else:
            zin = (
                f"Er is nu kans op onweer. Volgens de verwachting is het "
                f"{minuten_tekst(info['einde_min'])} voorbij."
            )
    elif info["begin_min"] is not None:
        zin = f"Er is kans op onweer {minuten_tekst(info['begin_min'])}."
    else:
        zin = (
            f"De komende {horizon_tekst(info['horizon_min'])} zie ik "
            f"geen onweer in de verwachting."
        )
    return zin + ONWEER_EERLIJK


def beslis_onweer(info, nu, staat):
    """Beslist of Nova spontaan onweer meldt. Geeft (zin of None, staat).
    Zelfde opzet als beslis_proactief(): 'staat' = {'gemeld', 'laatste'}.
    - Is er al onweer, dan meldt weather.py dat (huidig weer): hier niets.
    - Geen onweer in de hele verwachting: 'gemeld' wordt gewist.
    - Onweer binnen ONWEER_VOORUIT_MINUTEN, nog niet gemeld, niet 's nachts en
      minstens een uur na de vorige melding: melden."""
    staat = dict(staat)
    if info is None:
        return None, staat
    if info["nu"]:
        return None, staat
    if info["begin_min"] is None:
        staat["gemeld"] = False
        return None, staat

    if nu.hour >= PROACTIEF_STIL_VAN_UUR or nu.hour < PROACTIEF_STIL_TOT_UUR:
        return None, staat
    if staat.get("gemeld"):
        return None, staat
    if info["begin_min"] > ONWEER_VOORUIT_MINUTEN:
        return None, staat
    laatste = staat.get("laatste")
    if laatste is not None and (nu - laatste) < timedelta(minutes=PROACTIEF_MIN_TUSSENTIJD_MIN):
        return None, staat

    staat["gemeld"] = True
    staat["laatste"] = nu
    zin = f"Let op: er is kans op onweer {minuten_tekst(info['begin_min'])}." + ONWEER_EERLIJK
    return zin, staat


def beslis_proactief(analyse, nu, staat, neerslag_soort="regen"):
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
    return pas_soort_toe(zin, neerslag_soort), staat


def bepaal_vraagtype(text):
    """'stop' als Kevin wil weten wanneer het ophoudt, anders 'begin'."""
    t = text.lower()
    # Onweer heeft een eigen antwoord (geen radar, maar een weermodel)
    if any(w in t for w in ONWEER_WOORDEN):
        return "onweer"
    for woord in STOP_WOORDEN:
        if woord in t:
            return "stop"
    # "wanneer houdt het / de regen op": 'houdt' en 'op' staan los van elkaar
    if "houdt" in t and " op" in t:
        return "stop"
    return "begin"


# -----------------------------------------------------
# Korte radarzin voor in "wat is het weer"
# -----------------------------------------------------
def _hoofdletter(zin):
    return zin[:1].upper() + zin[1:]


def formuleer_kort(analyse, soort="regen"):
    """Eén korte radarzin voor in het weerbericht, bv.
    'Over ongeveer 20 minuten begint het te regenen (lichte regen).'
    Geeft None als er niets te melden valt (het is droog en blijft droog):
    het weerbericht hoeft niet elke keer 'het blijft droog' te zeggen."""
    if analyse is None:
        return None

    if analyse["regent_nu"]:
        if analyse["stop_min"] is None:
            zin = (
                f"De regen houdt voorlopig aan, minstens de komende "
                f"{horizon_tekst(analyse['horizon_min'])}."
            )
        else:
            zin = f"De regen stopt {minuten_tekst(analyse['stop_min'])}."
            if analyse["daarna_min"] is not None:
                zin += (
                    f" Maar {minuten_tekst(analyse['daarna_min'])} "
                    f"begint het opnieuw te regenen."
                )
    elif analyse["begin_min"] is not None:
        zin = (
            f"{_hoofdletter(minuten_tekst(analyse['begin_min']))} begint het te "
            f"regenen ({intensiteit_tekst(analyse['intensiteit'])})."
        )
    else:
        return None

    return pas_soort_toe(zin, soort)


# -----------------------------------------------------
# Gladheid en harde wind in de komende uren
# -----------------------------------------------------
# Eén kwartier uit het weermodel. 'neerslag' = mm in dat kwartier,
# 'wind' = gemiddelde wind (m/s), 'vlagen' = windstoten (m/s).
Weerpunt = namedtuple("Weerpunt", ["start", "einde", "temp", "neerslag", "wind", "vlagen"])


def parse_gevaar(data):
    """Zet het Open-Meteo-antwoord (temperature_2m, precipitation,
    wind_speed_10m, wind_gusts_10m per kwartier) om in Weerpunt-objecten.
    Ontbrekende velden worden None; rommel geeft []."""
    try:
        blok = data["minutely_15"]
        tijden = blok["time"]
    except (KeyError, TypeError):
        return []
    if not isinstance(blok, dict) or not isinstance(tijden, list):
        return []

    def lijst(naam):
        waarden = blok.get(naam)
        return waarden if isinstance(waarden, list) else []

    temps, neerslag = lijst("temperature_2m"), lijst("precipitation")
    winden, vlagen = lijst("wind_speed_10m"), lijst("wind_gusts_10m")

    def pak(waarden, i):
        return waarden[i] if i < len(waarden) else None

    punten = []
    for i, tijd_txt in enumerate(tijden):
        try:
            start = datetime.fromisoformat(tijd_txt)
        except (ValueError, TypeError):
            continue
        punten.append(Weerpunt(
            start, start + timedelta(minutes=15),
            pak(temps, i), pak(neerslag, i), pak(winden, i), pak(vlagen, i),
        ))
    return punten


def is_glad(punt):
    """Gladheid: 0-2 graden SAMEN met neerslag (droge kou geeft geen glad
    wegdek). Neerslag per kwartier x 4 = mm per uur, zelfde drempel als de radar."""
    if punt.temp is None or punt.neerslag is None:
        return False
    return (
        GLADHEID_MIN_C <= punt.temp <= GLADHEID_MAX_C
        and punt.neerslag * 4 >= REGEN_DREMPEL_MM_U
    )


def is_harde_wind(punt):
    """Harde wind: gemiddelde wind OF windstoten boven de drempel."""
    return (
        (punt.wind is not None and punt.wind >= WIND_DREMPEL_MS)
        or (punt.vlagen is not None and punt.vlagen >= VLAAG_DREMPEL_MS)
    )


def _zoek_reeks(punten, test):
    """Eerste aaneengesloten reeks punten waarvoor test() klopt.
    Geeft (eerste_index, index_na_de_reeks) of None."""
    i = 0
    while i < len(punten) and not test(punten[i]):
        i += 1
    if i == len(punten):
        return None
    j = i
    while j < len(punten) and test(punten[j]):
        j += 1
    return i, j


def analyseer_gevaar(punten, nu):
    """Zoekt gladheid en harde wind in de komende kwartieren.
    Geeft None zonder gegevens, anders een dict:
      horizon_min : hoe ver de data vooruit kijkt
      gladheid    : None, of {'nu', 'begin_min', 'einde_min', 'temp'}
      wind        : None, of {'nu', 'begin_min', 'einde_min', 'wind', 'vlagen'}
    'nu' = het gebeurt al; 'einde_min' None = tot het einde van de data."""
    kw = sorted((p for p in punten if p.einde > nu), key=lambda p: p.start)
    if not kw:
        return None

    def minuten_tot(tijdstip):
        return max(0, int(round((tijdstip - nu).total_seconds() / 60)))

    info = {"horizon_min": minuten_tot(kw[-1].einde), "gladheid": None, "wind": None}

    for naam, test in (("gladheid", is_glad), ("wind", is_harde_wind)):
        reeks = _zoek_reeks(kw, test)
        if reeks is None:
            continue
        i, j = reeks
        deel = kw[i:j]
        item = {
            "nu": kw[i].start <= nu,
            "begin_min": minuten_tot(kw[i].start),
            "einde_min": None if j == len(kw) else minuten_tot(kw[j].start),
        }
        if naam == "gladheid":
            temps = [p.temp for p in deel if p.temp is not None]
            item["temp"] = min(temps) if temps else None
        else:
            winden = [p.wind for p in deel if p.wind is not None]
            vlagen = [p.vlagen for p in deel if p.vlagen is not None]
            item["wind"] = max(winden) if winden else None
            item["vlagen"] = max(vlagen) if vlagen else None
        info[naam] = item

    return info


def gevaar_fragment(naam, item):
    """Een zinsdeel zonder hoofdletter en punt, bv.
    'kans op gladheid over ongeveer 1 uur (rond 1°C met neerslag)'.
    Zo kan de aanroeper er 'Let op: ...' of 'Straks: ...' voor zetten."""
    if item.get("nu"):
        # Het gebeurt al. "nog ongeveer 45 minuten" als het einde in zicht is.
        wanneer = "nu"
        if item.get("einde_min") is not None:
            wanneer += f", nog ongeveer {duur_tekst(item['einde_min'])}"
    else:
        wanneer = minuten_tekst(item["begin_min"])

    if naam == "gladheid":
        tekst = f"kans op gladheid {wanneer}"
        if item.get("temp") is not None:
            tekst += f" (rond {int(round(item['temp']))}°C met neerslag)"
        return tekst

    delen = []
    if item.get("wind") is not None and item["wind"] >= WIND_DREMPEL_MS:
        delen.append(f"wind tot {int(round(item['wind']))} m/s")
    if item.get("vlagen") is not None and item["vlagen"] >= VLAAG_DREMPEL_MS:
        delen.append(f"windstoten tot {int(round(item['vlagen']))} m/s")
    tekst = f"kans op harde wind {wanneer}"
    if delen:
        tekst += " (" + " en ".join(delen) + ")"
    return tekst


def beslis_gevaar(info, nu, staat):
    """Beslist of Nova spontaan gladheid of harde wind meldt.
    Geeft (lijst zinnen, staat). 'staat' = {'gladheid': {...}, 'wind': {...}},
    elk met 'gemeld' (bool) en 'laatste' (datetime of None).
    Zelfde regels als bij onweer:
    - Gebeurt het al, dan meldt weather.py dat (huidig weer): hier niets.
    - Staat het niet (meer) in de verwachting: 'gemeld' wordt gewist.
    - Binnen GEVAAR_VOORUIT_MINUTEN, nog niet gemeld, niet 's nachts en
      minstens een uur na de vorige melding van dit soort: melden."""
    staat = {naam: dict(staat.get(naam) or {}) for naam in ("gladheid", "wind")}
    if info is None:
        return [], staat

    stil = nu.hour >= PROACTIEF_STIL_VAN_UUR or nu.hour < PROACTIEF_STIL_TOT_UUR
    zinnen = []

    for naam in ("gladheid", "wind"):
        item = info.get(naam)
        deel = staat[naam]

        if item is None:
            deel["gemeld"] = False
            continue
        if item["nu"]:
            continue
        if stil or deel.get("gemeld"):
            continue
        if item["begin_min"] > GEVAAR_VOORUIT_MINUTEN:
            continue
        laatste = deel.get("laatste")
        if laatste is not None and (nu - laatste) < timedelta(minutes=PROACTIEF_MIN_TUSSENTIJD_MIN):
            continue

        deel["gemeld"] = True
        deel["laatste"] = nu
        zinnen.append(f"Let op: {gevaar_fragment(naam, item)}.")

    return zinnen, staat


def haal_gevaar(lat, lon):
    """Weerpunten (temperatuur, neerslag, wind) per kwartier uit Open-Meteo.
    Geeft [] bij elke fout."""
    try:
        r = requests.get(OPEN_METEO_GEVAAR_URL.format(lat=lat, lon=lon), timeout=5)
        if r.status_code == 200:
            return parse_gevaar(r.json())
    except Exception:
        pass
    return []


def weer_vooruit_zin(lat, lon, nu=None, inclusief_nu=False):
    """Voor weather.py ('wat is het weer'): de korte radarzin plus
    'Straks: kans op gladheid/harde wind ...' als dat eraan komt.
    Geeft None als er niets te melden is. Gaat er iets mis (bron weg,
    rare data), dan óók None: het gewone weerbericht blijft altijd werken.

    inclusief_nu=False (standaard): gladheid/wind die er AL is wordt niet
    genoemd, want 'wat is het weer' meldt het huidige weer zelf al.
    inclusief_nu=True: wel, als 'Let op: kans op gladheid nu, ...'. Dat is
    voor de ochtendsamenvatting, die het huidige weer niet apart ophaalt."""
    nu = nu or nu_lokaal()
    delen = []

    try:
        slots, grof = RainModule.haal_slots(lat, lon, nu)
        if slots:
            analyse = analyseer(slots, nu)
            soort = "regen"
            if analyse is not None and (analyse["regent_nu"] or analyse["begin_min"] is not None):
                soort = bepaal_soort(RainModule.haal_typeinfo(lat, lon), nu, analyse)
            zin = formuleer_kort(analyse, soort)
            if zin:
                delen.append(zin + (GROVE_BRON_NOOT if grof else ""))
    except Exception:
        pass

    try:
        info = analyseer_gevaar(haal_gevaar(lat, lon), nu)
        if info:
            for naam in ("gladheid", "wind"):
                item = info.get(naam)
                if not item:
                    continue
                if item["nu"]:
                    if inclusief_nu:
                        delen.append(f"Let op: {gevaar_fragment(naam, item)}.")
                else:
                    delen.append(f"Straks: {gevaar_fragment(naam, item)}.")
    except Exception:
        pass

    return " ".join(delen) if delen else None


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
        self._onweer_staat = {"gemeld": False, "laatste": None}
        self._gevaar_staat = {
            "gladheid": {"gemeld": False, "laatste": None},
            "wind": {"gemeld": False, "laatste": None},
        }

        # Luistert enkel naar intent_rain (IntentRouter doet detectie)
        event_bus.subscribe("intent_rain", self.on_rain)

    # Tekst -> stad ("gaat het regenen in Gent" -> "gent")
    def extract_city(self, text):
        return vind_stad(text, self.default_city)

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
    # staticmethod: heeft geen 'self' nodig, zodat weer_vooruit_zin() hem ook
    # kan gebruiken zonder een RainModule-object. self.haal_slots(...)
    # werkt precies zoals voorheen.
    @staticmethod
    def haal_slots(lat, lon, nu):
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

    @staticmethod
    def haal_typeinfo(lat, lon):
        """Soort neerslag (regen/sneeuw) en onweerscode per kwartier, uit
        Open-Meteo. Aparte aanvraag: een fout hier breekt de gewone
        regencheck nooit. Geeft [] bij elke fout."""
        try:
            r = requests.get(OPEN_METEO_TYPE_URL.format(lat=lat, lon=lon), timeout=5)
            if r.status_code == 200:
                return parse_typeinfo(r.json())
        except Exception:
            pass
        return []

    def maak_antwoord(self, city, vraagtype, nu=None, woord="regen"):
        nu = nu or nu_lokaal()

        coords = self.get_coordinates(city)
        if coords is None:
            return f"Ik weet niet waar {city.title()} ligt, dus ik kan daar de regenradar niet bekijken."

        if vraagtype == "onweer":
            info = analyseer_onweer(self.haal_typeinfo(coords[0], coords[1]), nu)
            if info is None:
                return "Ik kon de onweersgegevens nu niet bereiken."
            zin = formuleer_onweer(info)
            if city.lower() != self.default_city.lower():
                zin = f"In {city.title()}: {zin}"
            return zin

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

        # Regen of sneeuw? Valt er (straks) iets, dan bepaalt het weermodel
        # het soort. Valt er niets, dan gebruiken we het woord uit de vraag
        # ("gaat het sneeuwen?" -> "Het sneeuwt nu niet ...").
        if analyse["regent_nu"] or analyse["begin_min"] is not None:
            soort = bepaal_soort(self.haal_typeinfo(coords[0], coords[1]), nu, analyse)
        else:
            soort = woord
        zin = pas_soort_toe(zin, soort)

        if city.lower() != self.default_city.lower():
            zin = f"In {city.title()}: {zin}"
        if grof:
            zin += " (Let op: dit is een grovere schatting per kwartier.)"
        return zin

    def check_proactief(self, nu=None):
        """
        Wordt door main.py's achtergrond_loop() om de paar minuten
        aangeroepen. Kijkt enkel naar de standaardstad. Twee onafhankelijke
        controles: (1) regen/sneeuw die binnenkort begint, (2) kans op
        onweer. Doet niets (en crasht nooit) als een bron niet bereikbaar is.
        Geeft de gepubliceerde zin(nen) terug, of None.
        """
        try:
            nu = nu or nu_lokaal()
            coords = self.get_coordinates(self.default_city)
            if coords is None:
                return None
            typeinfo = self.haal_typeinfo(coords[0], coords[1])
            meldingen = []

            # 1. Regen of sneeuw (radar)
            slots, _grof = self.haal_slots(coords[0], coords[1], nu)
            if slots:
                analyse = analyseer(slots, nu)
                soort = bepaal_soort(typeinfo, nu, analyse)
                zin, self._proactief_staat = beslis_proactief(
                    analyse, nu, self._proactief_staat, soort
                )
                if zin:
                    meldingen.append(zin)

            # 2. Onweer (weermodel)
            info = analyseer_onweer(typeinfo, nu)
            zin, self._onweer_staat = beslis_onweer(info, nu, self._onweer_staat)
            if zin:
                meldingen.append(zin)

            # 3. Gladheid en harde wind (weermodel, komende 3 uur). Eigen
            # foutafscherming: een probleem hier mag de meldingen hierboven
            # niet tegenhouden.
            try:
                info_gevaar = analyseer_gevaar(haal_gevaar(coords[0], coords[1]), nu)
                zinnen, self._gevaar_staat = beslis_gevaar(info_gevaar, nu, self._gevaar_staat)
                meldingen.extend(zinnen)
            except Exception as e:
                print(f"[rain] gladheid/wind-check mislukt: {e}")

            for zin in meldingen:
                self.event_bus.publish("layer4_response", {"text": zin})
            return " ".join(meldingen) if meldingen else None
        except Exception as e:
            print(f"[rain] proactieve check mislukt: {e}")
            return None

    def on_rain(self, data, event_type=None):
        text = (data.get("text") or "").lower()
        city = self.extract_city(text)
        vraagtype = bepaal_vraagtype(text)
        woord = "sneeuw" if "sneeuw" in text else "regen"
        antwoord = self.maak_antwoord(city, vraagtype, woord=woord)
        self.event_bus.publish("layer4_response", {"text": antwoord})


def init_module(event_bus):
    API_KEY = os.getenv("OPENWEATHER_API_KEY")
    instance = RainModule(event_bus, API_KEY)
    event_bus.publish("module_loaded", {"name": "rain"})
    return instance