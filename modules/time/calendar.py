# modules/time/calendar.py

# ============================================================
# CalendarModule
# ------------------------------------------------------------
# Beantwoordt kalendervragen:
# 1) Basiskalender: welke dag, welke datum, welke maand, welk
#    jaar, welke week -- en een algemeen overzicht ("wat is het
#    vandaag") dat alles in één zin samenvat.
# 2) Datumrekenen (date_calendar_roadmap.md, Onderdeel 1):
#    "hoeveel dagen tot X", "welke dag van de week is X",
#    "wat is de datum over N dagen/weken".
#
# Zelfde patroon als modules/time/time.py:
# - luistert op één intent-event (intent_calendar_query)
# - gebruikt zone.py voor de lokale datum, indien beschikbaar
# - antwoordt via layer4_response (spreektalige tekst, gaat
#   door de tone-pipeline)
#
# BEWUST GEEN locale.setlocale() of strftime("%A")/strftime("%B")
# voor Nederlandse namen: dat hangt af van welke locales in de
# Docker-container geïnstalleerd zijn en kan dus op de ene
# machine werken en op de andere stil breken (Engelse namen
# teruggeven zonder foutmelding). In plaats daarvan: eigen,
# vaste vertaaltabellen. Puur symbolisch, geen enkele externe
# dependency nodig -- dit is 100% Python's ingebouwde datetime,
# net als time.py.
#
# BEWUST NOG GEEN feestdag-namen ("kerst", "pasen", ...) als
# datum-invoer -- dat is inhoudelijk feestdagen-kennis
# (date_calendar_roadmap.md, Onderdeel 2), nog niet gebouwd.
# calendar.py herkent hier enkel EXPLICIETE datums.
#
# Eigen, kleine dag-offset-herkenning ("morgen"/"overmorgen"/
# weekdagnamen) -- bewust NIET hergebruikt vanuit weather.py's
# extract_day_offset(), op uitdrukkelijk verzoek (geen wijziging
# aan weather.py). Dit betekent dat dezelfde 7 weekdagnamen nu
# op meerdere plekken in Nova voorkomen (weather.py's WEEKDAGEN-
# dict + zijn eigen weekdag_namen-lijst in dag_label(), en hier
# DAGNAMEN) -- bekende, bewust geaccepteerde duplicatie, geen
# gedeelde bron. Zie nova_changelog.md voor de volledige
# afweging.
# ============================================================

import re
from datetime import date, datetime, timedelta

DAGNAMEN = {
    0: "maandag",
    1: "dinsdag",
    2: "woensdag",
    3: "donderdag",
    4: "vrijdag",
    5: "zaterdag",
    6: "zondag",
}

MAANDNAMEN = {
    1: "januari",
    2: "februari",
    3: "maart",
    4: "april",
    5: "mei",
    6: "juni",
    7: "juli",
    8: "augustus",
    9: "september",
    10: "oktober",
    11: "november",
    12: "december",
}

# Omgekeerde lookup (naam -> nummer) voor het parsen van "15 augustus"
MAAND_NAAR_NUMMER = {naam: nummer for nummer, naam in MAANDNAMEN.items()}

# Omgekeerde lookup (naam -> nummer) voor het parsen van weekdagnamen,
# bv. "hoeveel dagen tot maandag" -- nodig om "maandag" als dag-offset
# te herkennen in _parse_datum().
DAGNAAM_NAAR_NUMMER = {naam: nummer for nummer, naam in DAGNAMEN.items()}


class CalendarModule:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.zone = event_bus.get_module("zone")  # optioneel, zelfde als time.py

        event_bus.subscribe("intent_calendar_query", self.on_calendar_intent)

    # --------------------------------------------------------
    # Lokale datum ophalen (zelfde aanpak als time.py's now())
    # --------------------------------------------------------
    def today(self):
        if self.zone:
            return self.zone.now_local().date()
        return datetime.now().date()

    # --------------------------------------------------------
    # Event-handler
    # --------------------------------------------------------
    def on_calendar_intent(self, data, event_type=None):
        # IntentRouter heeft al beslist welk type vraag dit is
        # (zie detect_calendar() in intent_router.py) en stuurt
        # dat mee als "type" in data. Geen tekst-checks meer hier,
        # BEHALVE voor de drie datumreken-types hieronder, die de
        # ruwe tekst nog nodig hebben om de genoemde datum eruit
        # te halen (intent_router.py detecteert enkel DAT het een
        # datumrekenvraag is, niet WELKE datum precies bedoeld is
        # -- dat blijft hier, dicht bij de rekenlogica zelf).
        vraag_type = data.get("type", "algemeen")
        text = data.get("text", "")

        if vraag_type == "dag":
            self.antwoord_dag()
        elif vraag_type == "datum":
            self.antwoord_datum()
        elif vraag_type == "maand":
            self.antwoord_maand()
        elif vraag_type == "jaar":
            self.antwoord_jaar()
        elif vraag_type == "week":
            self.antwoord_week()
        elif vraag_type == "dagen_tot":
            self.antwoord_dagen_tot(text)
        elif vraag_type == "dag_van_de_week":
            self.antwoord_dag_van_de_week(text)
        elif vraag_type == "datum_plus":
            self.antwoord_datum_plus(text)
        else:
            self.antwoord_algemeen()

    # --------------------------------------------------------
    # Gerichte antwoorden -- elk kort en specifiek (optie B)
    # --------------------------------------------------------
    def antwoord_dag(self):
        vandaag = self.today()
        dagnaam = DAGNAMEN[vandaag.weekday()]
        msg = f"Het is vandaag {dagnaam}."
        self.event_bus.publish("layer4_response", {"text": msg})

    def antwoord_datum(self):
        vandaag = self.today()
        maandnaam = MAANDNAMEN[vandaag.month]
        msg = f"Vandaag is het {vandaag.day} {maandnaam} {vandaag.year}."
        self.event_bus.publish("layer4_response", {"text": msg})

    def antwoord_maand(self):
        vandaag = self.today()
        maandnaam = MAANDNAMEN[vandaag.month]
        msg = f"We zitten in {maandnaam}."
        self.event_bus.publish("layer4_response", {"text": msg})

    def antwoord_jaar(self):
        vandaag = self.today()
        msg = f"Het is {vandaag.year}."
        self.event_bus.publish("layer4_response", {"text": msg})

    def antwoord_week(self):
        vandaag = self.today()
        _, weeknummer, _ = vandaag.isocalendar()
        msg = f"Het is week {weeknummer}."
        self.event_bus.publish("layer4_response", {"text": msg})

    # --------------------------------------------------------
    # Algemeen overzicht -- alles in één zin
    # --------------------------------------------------------
    def antwoord_algemeen(self):
        vandaag = self.today()
        dagnaam = DAGNAMEN[vandaag.weekday()]
        maandnaam = MAANDNAMEN[vandaag.month]
        _, weeknummer, _ = vandaag.isocalendar()
        msg = (
            f"Het is vandaag {dagnaam} {vandaag.day} {maandnaam} "
            f"{vandaag.year}, week {weeknummer}."
        )
        self.event_bus.publish("layer4_response", {"text": msg})

    # ==========================================================
    # DATUMREKENEN (date_calendar_roadmap.md, Onderdeel 1)
    # ==========================================================

    # --------------------------------------------------------
    # Tekst -> datum. Probeert, in volgorde, een aantal vaste,
    # ondubbelzinnige patronen. Geeft None terug als niets matcht
    # of als de gevonden datum ongeldig is (bv. 31 april) --
    # NOOIT een gok, NOOIT een crash.
    #
    # Herkende vormen:
    #   1) "morgen" / "overmorgen" / "vandaag"
    #   2) een weekdagnaam ("maandag", ...) -- eerstvolgende
    #      gelegenheid, zelfde regel als weather.py's
    #      extract_day_offset(): een genoemde dag is nooit
    #      vandaag, zelfs niet als vandaag toevallig die dag is
    #   3) "over N dagen" / "over N weken"
    #   4) cijfernotatie: "15/08", "15-08", "15/08/2027",
    #      "15-08-2027"
    #   5) dag + maandnaam: "15 augustus", "15 augustus 2027"
    #
    # Voor 4) en 5) zonder expliciet jaartal: als die datum dit
    # jaar al voorbij is, wordt automatisch naar volgend jaar
    # gesprongen (bevestigd met Kevin) -- "vandaag zelf" telt
    # NIET als "al voorbij", blijft dit jaar.
    # --------------------------------------------------------
    def _parse_datum(self, text):
        t = text.lower().strip()
        vandaag = self.today()

        # 1) morgen / overmorgen / vandaag
        if "overmorgen" in t:
            return vandaag + timedelta(days=2)
        if "morgen" in t:
            return vandaag + timedelta(days=1)
        if "vandaag" in t:
            return vandaag

        # 2) weekdagnaam -- eerstvolgende gelegenheid
        for naam, weekday_nr in DAGNAAM_NAAR_NUMMER.items():
            if naam in t:
                offset = (weekday_nr - vandaag.weekday()) % 7
                if offset == 0:
                    offset = 7  # vandaag toevallig die dag = volgende week bedoeld
                return vandaag + timedelta(days=offset)

        # 3) "over N dagen" / "over N weken"
        m = re.search(r"\bover\s+(\d+)\s+(dag|dagen|week|weken)\b", t)
        if m:
            aantal = int(m.group(1))
            eenheid = m.group(2)
            if eenheid in ("week", "weken"):
                aantal *= 7
            return vandaag + timedelta(days=aantal)

        # 4) cijfernotatie: 15/08, 15-08, 15/08/2027, 15-08-2027
        m = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}))?\b", t)
        if m:
            return self._bouw_datum_met_jaarsprong(
                dag=int(m.group(1)),
                maand=int(m.group(2)),
                jaar_str=m.group(3),
                vandaag=vandaag,
            )

        # 5) dag + maandnaam: "15 augustus", "15 augustus 2027"
        maandnamen_patroon = "|".join(MAAND_NAAR_NUMMER.keys())
        m = re.search(
            r"\b(\d{1,2})\s+(" + maandnamen_patroon + r")(?:\s+(\d{4}))?\b", t
        )
        if m:
            return self._bouw_datum_met_jaarsprong(
                dag=int(m.group(1)),
                maand=MAAND_NAAR_NUMMER[m.group(2)],
                jaar_str=m.group(3),
                vandaag=vandaag,
            )

        return None

    def _bouw_datum_met_jaarsprong(self, dag, maand, jaar_str, vandaag):
        """Bouwt een date() uit dag/maand (+ optioneel jaar). Zonder
        expliciet jaar: probeert eerst het huidige jaar, springt naar
        volgend jaar als die datum al voorbij is. Geeft None terug bij
        een ongeldige datum (bv. 31 april, 29 februari in een niet-
        schrikkeljaar) -- nooit een gok, nooit een crash."""
        if jaar_str:
            try:
                return date(int(jaar_str), maand, dag)
            except ValueError:
                return None

        jaar = vandaag.year
        try:
            kandidaat = date(jaar, maand, dag)
        except ValueError:
            return None
        if kandidaat < vandaag:
            jaar += 1
            try:
                return date(jaar, maand, dag)
            except ValueError:
                # Zeldzaam randgeval: bv. 29 februari, geldig dit jaar
                # (schrikkeljaar) maar niet meer volgend jaar. Dan geen
                # gok naar een ander jaar -- gewoon None, nette
                # tegenvraag in antwoord_*() hieronder.
                return None
        return kandidaat

    # --------------------------------------------------------
    # Nette "dat snap ik niet"-boodschap, hergebruikt door alle
    # drie de datumreken-antwoorden hieronder bij een onherkende
    # of ongeldige datum.
    # --------------------------------------------------------
    def _geen_datum_herkend(self):
        msg = (
            "Welke datum bedoel je precies? Ik versta bijvoorbeeld "
            "'15 augustus', '15/08/2027' of 'over 10 dagen'."
        )
        self.event_bus.publish("layer4_response", {"text": msg})

    # --------------------------------------------------------
    # "Hoeveel dagen tot X?"
    # --------------------------------------------------------
    def dagen_tot(self, datum):
        """Puur rekenkundig, geen tekst-parsing. Geeft een int terug
        (kan negatief zijn als datum in het verleden ligt, 0 als datum
        vandaag is)."""
        return (datum - self.today()).days

    def antwoord_dagen_tot(self, text):
        datum = self._parse_datum(text)
        if datum is None:
            self._geen_datum_herkend()
            return

        aantal = self.dagen_tot(datum)
        maandnaam = MAANDNAMEN[datum.month]

        if aantal == 0:
            msg = f"Dat is vandaag, {datum.day} {maandnaam} {datum.year}!"
        elif aantal == 1:
            msg = f"Dat is morgen, {datum.day} {maandnaam} {datum.year}."
        elif aantal > 1:
            msg = (
                f"Nog {aantal} dagen tot {datum.day} {maandnaam} "
                f"{datum.year}."
            )
        else:
            # Datum ligt in het verleden -- kan enkel als een
            # expliciet jaartal is meegegeven (bv. "15/08/2020"),
            # want zonder jaartal springt _bouw_datum_met_jaarsprong()
            # zelf al automatisch naar volgend jaar.
            msg = (
                f"{datum.day} {maandnaam} {datum.year} was {abs(aantal)} "
                f"dagen geleden."
            )
        self.event_bus.publish("layer4_response", {"text": msg})

    # --------------------------------------------------------
    # "Welke dag van de week is X?"
    # --------------------------------------------------------
    def dag_van_de_week(self, datum):
        """Puur rekenkundig, geen tekst-parsing."""
        return DAGNAMEN[datum.weekday()]

    def antwoord_dag_van_de_week(self, text):
        datum = self._parse_datum(text)
        if datum is None:
            self._geen_datum_herkend()
            return

        dagnaam = self.dag_van_de_week(datum)
        maandnaam = MAANDNAMEN[datum.month]
        msg = f"{datum.day} {maandnaam} {datum.year} is een {dagnaam}."
        self.event_bus.publish("layer4_response", {"text": msg})

    # --------------------------------------------------------
    # "Wat is de datum over N dagen/weken?"
    # --------------------------------------------------------
    def datum_plus(self, n_dagen):
        """Puur rekenkundig, geen tekst-parsing."""
        return self.today() + timedelta(days=n_dagen)

    def antwoord_datum_plus(self, text):
        t = text.lower().strip()
        m = re.search(r"\bover\s+(\d+)\s+(dag|dagen|week|weken)\b", t)
        if not m:
            self._geen_datum_herkend()
            return

        aantal = int(m.group(1))
        eenheid = m.group(2)
        if eenheid in ("week", "weken"):
            aantal *= 7

        datum = self.datum_plus(aantal)
        dagnaam = DAGNAMEN[datum.weekday()]
        maandnaam = MAANDNAMEN[datum.month]
        msg = (
            f"Dat is {dagnaam} {datum.day} {maandnaam} {datum.year}."
        )
        self.event_bus.publish("layer4_response", {"text": msg})


def init_module(event_bus):
    mod = CalendarModule(event_bus)
    event_bus.publish("module_loaded", {"name": "calendar"})
    return mod