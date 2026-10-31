# tests/test_calendar_morgen_en_feestdag_jaar.py
#
# Regressietests voor twee fouten die niveau 3 van de benchmark vond:
#   1) "welke dag is het morgen" antwoordde "Het is vandaag ..."
#   2) "wanneer is pasen in 2028" negeerde het jaartal en gaf 2027
#
# "Vandaag" wordt vastgezet op zaterdag 31 oktober 2026, zodat de
# tests elke dag dezelfde uitkomst geven.

from datetime import date

from modules.time.calendar import CalendarModule
from modules.time.holidays import HolidaysModule

VANDAAG = date(2026, 10, 31)  # zaterdag


class NepBus:
    """Minimale nep-EventBus: onthoudt alles wat gepubliceerd wordt."""

    def __init__(self):
        self.gepubliceerd = []

    def get_module(self, naam):
        return None

    def subscribe(self, event, handler):
        pass

    def publish(self, event, data=None):
        self.gepubliceerd.append((event, data))

    def laatste_tekst(self):
        assert self.gepubliceerd, "er is niets gepubliceerd"
        return self.gepubliceerd[-1][1]["text"]


def maak_calendar():
    bus = NepBus()
    mod = CalendarModule(bus)
    mod.today = lambda: VANDAAG
    return mod, bus


def maak_holidays():
    bus = NepBus()
    mod = HolidaysModule(bus)
    mod.today = lambda: VANDAAG
    return mod, bus


# ---------------- calendar: dag-vragen ----------------

def test_vandaag_zonder_tekst_blijft_werken():
    mod, bus = maak_calendar()
    mod.antwoord_dag()
    assert bus.laatste_tekst() == "Het is vandaag zaterdag."


def test_vandaag_met_gewone_tekst():
    mod, bus = maak_calendar()
    mod.on_calendar_intent({"type": "dag", "text": "welke dag is het"})
    assert bus.laatste_tekst() == "Het is vandaag zaterdag."


def test_morgen():
    mod, bus = maak_calendar()
    mod.on_calendar_intent({"type": "dag", "text": "welke dag is het morgen"})
    assert bus.laatste_tekst() == "Morgen is het zondag."


def test_overmorgen():
    mod, bus = maak_calendar()
    mod.on_calendar_intent({"type": "dag", "text": "welke dag is het overmorgen"})
    assert bus.laatste_tekst() == "Overmorgen is het maandag."


def test_gisteren():
    mod, bus = maak_calendar()
    mod.on_calendar_intent({"type": "dag", "text": "welke dag was het gisteren"})
    assert bus.laatste_tekst() == "Gisteren was het vrijdag."


def test_eergisteren():
    mod, bus = maak_calendar()
    mod.on_calendar_intent({"type": "dag", "text": "welke dag was het eergisteren"})
    assert bus.laatste_tekst() == "Eergisteren was het donderdag."


def test_goedemorgen_telt_niet_als_morgen():
    mod, bus = maak_calendar()
    mod.on_calendar_intent({"type": "dag", "text": "goedemorgen welke dag is het"})
    assert bus.laatste_tekst() == "Het is vandaag zaterdag."


# ---------------- holidays: jaartal in de vraag ----------------

def test_pasen_met_expliciet_jaar_2028():
    mod, bus = maak_holidays()
    mod.antwoord_wanneer_is("wanneer is pasen in 2028")
    tekst = bus.laatste_tekst()
    assert "2028" in tekst
    assert "16 april" in tekst
    assert "dit jaar" not in tekst


def test_kerstmis_met_expliciet_jaar_2028():
    mod, bus = maak_holidays()
    mod.antwoord_wanneer_is("wanneer is kerstmis in 2028")
    tekst = bus.laatste_tekst()
    assert "25 december" in tekst
    assert "maandag" in tekst  # 25 dec 2028 is een maandag


def test_pasen_2027_zegt_niet_dit_jaar():
    mod, bus = maak_holidays()
    mod.antwoord_wanneer_is("wanneer is pasen in 2027")
    tekst = bus.laatste_tekst()
    assert "28 maart" in tekst
    assert "dit jaar" not in tekst


def test_zonder_jaar_blijft_dit_jaar_als_het_nog_komt():
    mod, bus = maak_holidays()
    mod.antwoord_wanneer_is("wanneer is kerstmis")
    assert "dit jaar" in bus.laatste_tekst()
    assert "25 december 2026" in bus.laatste_tekst()


def test_zonder_jaar_springt_naar_volgend_jaar_met_juiste_woorden():
    mod, bus = maak_holidays()
    mod.antwoord_wanneer_is("wanneer is pasen")  # Pasen 2026 is al voorbij
    tekst = bus.laatste_tekst()
    assert "volgend jaar" in tekst
    assert "2027" in tekst


def test_jaar_voor_1583_wordt_geweigerd():
    mod, bus = maak_holidays()
    mod.antwoord_wanneer_is("wanneer is pasen in 1500")
    assert "1583" in bus.laatste_tekst()