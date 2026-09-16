# test_calendar.py
#
# Echte pytest-test voor de nieuwe kalendermodule (modules/time/calendar.py):
# dag, datum, maand, jaar, week -- en het algemene overzicht.
#
# Zelfde conventies als de rest van de test-suite:
# - Echte package-import (from modules.time.calendar import ...), geen
#   importlib/spec_from_file_location-omweg, zelfde patroon als
#   test_fase1.py's "from modules.learning.word_associations_learner
#   import WordAssociationsLearner".
# - DummyEventBus als lokale class (publish/subscribe/get_module).
# - Geen I/O in CalendarModule.__init__() -> geen monkeypatch nodig
#   (zelfde conclusie als bij IntentRouter/ChatModule). Een DummyZone
#   met een vaste, injecteerbare datum volstaat om onafhankelijk van
#   de werkelijke "vandaag" te testen (zelfde principe als
#   test_last_context.py's NepKlok-helper).
#
# Uitvoeren: pytest tests/test_calendar.py -v

from datetime import date, datetime

import pytest

from modules.time.calendar import CalendarModule, init_module, DAGNAMEN, MAANDNAMEN


# ------------------------------------------------------------
# Test-dubbels
# ------------------------------------------------------------
class DummyEventBus:
    """Nep-EventBus: publish/subscribe/get_module, geen echte pub/sub-logica nodig."""

    def __init__(self, zone=None):
        self.gepubliceerd = []          # lijst van (event_type, data)-tuples
        self.subscripties = {}          # event_type -> handler
        self._zone = zone
        self.modules = {}

    def get_module(self, naam):
        if naam == "zone":
            return self._zone
        return self.modules.get(naam)

    def subscribe(self, event_type, handler):
        self.subscripties[event_type] = handler

    def publish(self, event_type, data):
        self.gepubliceerd.append((event_type, data))

    # Hulpmethode voor de tests: laatste layer4_response-tekst
    def laatste_tekst(self):
        for event_type, data in reversed(self.gepubliceerd):
            if event_type == "layer4_response":
                return data["text"]
        return None


class DummyZone:
    """Nep-zone-module: levert een VASTE, injecteerbare datum terug,
    zodat tests nooit afhangen van de werkelijke 'vandaag'."""

    def __init__(self, vaste_datetime):
        self._vaste_datetime = vaste_datetime

    def now_local(self):
        return self._vaste_datetime


# ------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------
@pytest.fixture
def woensdag_16_sept_2026():
    """Woensdag 16 september 2026, week 38 -- vaste referentiedatum."""
    return datetime(2026, 9, 16, 14, 30, 0)


@pytest.fixture
def bus_met_zone(woensdag_16_sept_2026):
    """EventBus MET een zone-module (normale situatie)."""
    zone = DummyZone(woensdag_16_sept_2026)
    return DummyEventBus(zone=zone)


@pytest.fixture
def bus_zonder_zone():
    """EventBus ZONDER zone-module (fallback-pad, get_module('zone') geeft None)."""
    return DummyEventBus(zone=None)


# ============================================================
# 1. Basis: module laden en registratie
# ============================================================
class TestInitModule:
    def test_init_module_geeft_calendarmodule_instantie(self, bus_met_zone):
        mod = init_module(bus_met_zone)
        assert isinstance(mod, CalendarModule)

    def test_init_module_publiceert_module_loaded(self, bus_met_zone):
        init_module(bus_met_zone)
        assert ("module_loaded", {"name": "calendar"}) in bus_met_zone.gepubliceerd

    def test_init_module_abonneert_op_intent_calendar_query(self, bus_met_zone):
        init_module(bus_met_zone)
        assert "intent_calendar_query" in bus_met_zone.subscripties

    def test_geen_io_in_init_geen_bestanden_aangeraakt(self, bus_zonder_zone, tmp_path, monkeypatch):
        # Regressie-achtige garantie: __init__() doet geen file-I/O,
        # dus werken in een lege tmp_path als cwd mag nooit een
        # FileNotFoundError of vergelijkbaars opleveren.
        monkeypatch.chdir(tmp_path)
        mod = CalendarModule(bus_zonder_zone)
        assert mod is not None


# ============================================================
# 2. today() -- zone-koppeling en fallback
# ============================================================
class TestToday:
    def test_today_gebruikt_zone_now_local_indien_beschikbaar(
        self, bus_met_zone, woensdag_16_sept_2026
    ):
        mod = CalendarModule(bus_met_zone)
        assert mod.today() == woensdag_16_sept_2026.date()

    def test_today_valt_terug_op_datetime_now_zonder_zone(self, bus_zonder_zone):
        mod = CalendarModule(bus_zonder_zone)
        # Geen zone beschikbaar -> valt terug op de ECHTE datetime.now().
        # We testen enkel dat het geen crash geeft en een date-object
        # teruggeeft dat overeenkomt met vandaag volgens het systeem
        # (geen vaste datum injecteerbaar in dit pad, dat is precies
        # het punt van de fallback).
        vandaag = mod.today()
        assert vandaag == datetime.now().date()

    def test_get_module_zone_wordt_bij_init_opgevraagd(self, bus_met_zone):
        # Zelfde patroon als time.py: self.zone wordt EENMALIG
        # opgevraagd in __init__(), niet telkens opnieuw.
        mod = CalendarModule(bus_met_zone)
        assert mod.zone is bus_met_zone._zone


# ============================================================
# 3. Elk gericht antwoord-type -- kort en specifiek (optie B)
# ============================================================
class TestGerichteAntwoorden:
    def test_antwoord_dag(self, bus_met_zone):
        mod = CalendarModule(bus_met_zone)
        mod.on_calendar_intent({"text": "welke dag is het", "type": "dag"})
        assert bus_met_zone.laatste_tekst() == "Het is vandaag woensdag."

    def test_antwoord_datum(self, bus_met_zone):
        mod = CalendarModule(bus_met_zone)
        mod.on_calendar_intent({"text": "wat is de datum", "type": "datum"})
        assert bus_met_zone.laatste_tekst() == "Vandaag is het 16 september 2026."

    def test_antwoord_maand(self, bus_met_zone):
        mod = CalendarModule(bus_met_zone)
        mod.on_calendar_intent({"text": "welke maand is het", "type": "maand"})
        assert bus_met_zone.laatste_tekst() == "We zitten in september."

    def test_antwoord_jaar(self, bus_met_zone):
        mod = CalendarModule(bus_met_zone)
        mod.on_calendar_intent({"text": "welk jaar is het", "type": "jaar"})
        assert bus_met_zone.laatste_tekst() == "Het is 2026."

    def test_antwoord_week(self, bus_met_zone):
        mod = CalendarModule(bus_met_zone)
        mod.on_calendar_intent({"text": "welke week is het", "type": "week"})
        assert bus_met_zone.laatste_tekst() == "Het is week 38."

    def test_antwoord_algemeen_bevat_alles(self, bus_met_zone):
        mod = CalendarModule(bus_met_zone)
        mod.on_calendar_intent({"text": "wat is het vandaag", "type": "algemeen"})
        tekst = bus_met_zone.laatste_tekst()
        assert "woensdag" in tekst
        assert "16" in tekst
        assert "september" in tekst
        assert "2026" in tekst
        assert "week 38" in tekst

    def test_onbekend_type_valt_terug_op_algemeen(self, bus_met_zone):
        # data.get("type", "algemeen") + de else-tak in
        # on_calendar_intent(): een type dat niet expliciet
        # gekend is, geeft nooit een crash, maar het volledige
        # overzicht.
        mod = CalendarModule(bus_met_zone)
        mod.on_calendar_intent({"text": "iets vreemds", "type": "onbekend_type_xyz"})
        tekst = bus_met_zone.laatste_tekst()
        assert "woensdag" in tekst and "week 38" in tekst

    def test_ontbrekend_type_valt_terug_op_algemeen(self, bus_met_zone):
        # Geen "type"-sleutel in data (zou in theorie niet mogen
        # voorkomen als intent_router.py altijd type meestuurt,
        # maar de .get()-default moet dit toch netjes opvangen).
        mod = CalendarModule(bus_met_zone)
        mod.on_calendar_intent({"text": "iets"})
        tekst = bus_met_zone.laatste_tekst()
        assert "woensdag" in tekst and "week 38" in tekst

    def test_elk_gericht_antwoord_publiceert_via_layer4_response(self, bus_met_zone):
        # Kernvereiste uit nova_state.md: calendar.py moet, net als
        # weather/time/math, via layer4_response gaan (tone-pipeline),
        # nooit rechtstreeks chat_response.
        mod = CalendarModule(bus_met_zone)
        for vraag_type in ["dag", "datum", "maand", "jaar", "week", "algemeen"]:
            bus_met_zone.gepubliceerd.clear()
            mod.on_calendar_intent({"text": "x", "type": vraag_type})
            event_types = [e for e, _ in bus_met_zone.gepubliceerd]
            assert event_types == ["layer4_response"], (
                f"type={vraag_type} publiceerde {event_types}, verwacht enkel layer4_response"
            )


# ============================================================
# 4. Directe methode-aanroepen (los van het event-pad)
# ============================================================
class TestDirecteMethodeAanroepen:
    """Dezelfde antwoord_*()-methodes, maar rechtstreeks aangeroepen
    i.p.v. via on_calendar_intent() -- bevestigt dat de methodes zelf
    correct zijn, onafhankelijk van de event-routing."""

    def test_antwoord_dag_rechtstreeks(self, bus_met_zone):
        mod = CalendarModule(bus_met_zone)
        mod.antwoord_dag()
        assert bus_met_zone.laatste_tekst() == "Het is vandaag woensdag."

    def test_antwoord_week_rechtstreeks(self, bus_met_zone):
        mod = CalendarModule(bus_met_zone)
        mod.antwoord_week()
        assert bus_met_zone.laatste_tekst() == "Het is week 38."


# ============================================================
# 5. Andere datums -- dekt randgevallen (jaarwisseling, weeknummer-
#    grenzen, enkelvoudige/dubbele cijfers)
# ============================================================
class TestAndereData:
    @pytest.mark.parametrize(
        "jaar, maand, dag, verwachte_dagnaam, verwacht_weeknummer",
        [
            (2026, 1, 1, "donderdag", 1),      # jaarwisseling: 1 jan 2026 is week 1
            (2025, 12, 31, "woensdag", 1),      # 31 dec 2025 valt al in ISO-week 1 van 2026
            (2026, 12, 31, "donderdag", 53),    # jaareinde met een 53e ISO-week
            (2026, 2, 1, "zondag", 5),          # weekend-datum
        ],
    )
    def test_verschillende_datums_dag_en_week(
        self, jaar, maand, dag, verwachte_dagnaam, verwacht_weeknummer
    ):
        zone = DummyZone(datetime(jaar, maand, dag, 9, 0, 0))
        bus = DummyEventBus(zone=zone)
        mod = CalendarModule(bus)

        mod.antwoord_dag()
        assert bus.laatste_tekst() == f"Het is vandaag {verwachte_dagnaam}."

        bus.gepubliceerd.clear()
        mod.antwoord_week()
        assert bus.laatste_tekst() == f"Het is week {verwacht_weeknummer}."

    def test_datum_enkelvoudig_dagcijfer_geen_leidende_nul(self):
        # 3 maart moet "3 maart", niet "03 maart" geven -- de f-string
        # gebruikt vandaag.day (een int), dus geen leidende nul.
        zone = DummyZone(datetime(2026, 3, 3, 8, 0, 0))
        bus = DummyEventBus(zone=zone)
        mod = CalendarModule(bus)
        mod.antwoord_datum()
        assert bus.laatste_tekst() == "Vandaag is het 3 maart 2026."

    def test_alle_12_maandnamen_correct(self):
        for maandnummer in range(1, 13):
            zone = DummyZone(datetime(2026, maandnummer, 15, 8, 0, 0))
            bus = DummyEventBus(zone=zone)
            mod = CalendarModule(bus)
            mod.antwoord_maand()
            verwacht = f"We zitten in {MAANDNAMEN[maandnummer]}."
            assert bus.laatste_tekst() == verwacht

    def test_alle_7_dagnamen_correct(self):
        # 5 t/m 11 januari 2026 = maandag t/m zondag, één volledige week
        for i, dagnummer in enumerate(range(5, 12)):
            zone = DummyZone(datetime(2026, 1, dagnummer, 8, 0, 0))
            bus = DummyEventBus(zone=zone)
            mod = CalendarModule(bus)
            mod.antwoord_dag()
            verwacht = f"Het is vandaag {DAGNAMEN[i]}."
            assert bus.laatste_tekst() == verwacht


# ============================================================
# 6. Consistentie tussen DAGNAMEN/MAANDNAMEN en Python's eigen
#    weekday()/month-nummering (voorkomt een off-by-one-bug)
# ============================================================
class TestVertaaltabellenConsistentie:
    def test_dagnamen_heeft_alle_7_sleutels_0_tot_6(self):
        assert set(DAGNAMEN.keys()) == set(range(7))

    def test_maandnamen_heeft_alle_12_sleutels_1_tot_12(self):
        assert set(MAANDNAMEN.keys()) == set(range(1, 13))

    def test_weekday_0_is_daadwerkelijk_maandag(self):
        # Sanity-check op Python's eigen gedrag: 5 januari 2026 is een
        # maandag (extern geverifieerd), .weekday() moet dus 0 geven.
        assert date(2026, 1, 5).weekday() == 0
        assert DAGNAMEN[0] == "maandag"