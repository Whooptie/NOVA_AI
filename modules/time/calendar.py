# modules/time/calendar.py

# ============================================================
# CalendarModule
# ------------------------------------------------------------
# Beantwoordt kalendervragen: welke dag, welke datum, welke
# maand, welk jaar, welke week -- en een algemeen overzicht
# ("wat is het vandaag") dat alles in één zin samenvat.
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
# ============================================================

from datetime import date, datetime

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
        # dat mee als "type" in data. Geen tekst-checks meer hier.
        vraag_type = data.get("type", "algemeen")

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


def init_module(event_bus):
    mod = CalendarModule(event_bus)
    event_bus.publish("module_loaded", {"name": "calendar"})
    return mod