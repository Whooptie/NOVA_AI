# test_pattern_matcher.py
#
# Echte pytest-test voor modules/learning/pattern_matcher.py (Layer 2):
# event grouping (Fase 1), pattern detection/confidence (Fase 2),
# anomaliedetectie -- ongewone timing (Fase 3, Deel A), en
# is_pattern_active() (Fase 4).
#
# BEWUST NIET GETEST: _check_missing_events() (Fase 3, Deel B) en de
# achtergrondtimers zelf (start_missing_event_checks/start_save_timer)
# -- die zijn tijdgebonden (draaien elk uur/5 minuten) en zouden een
# test onnodig traag of flaky maken. is_pattern_active() wordt wel
# getest, maar enkel op een manier die met het ECHTE huidige moment
# werkt (zie hieronder), niet met hardgecodeerde uren -- de functie
# zelf gebruikt intern datetime.now(), dus een test met een vast uur
# zou de volgende keer dat je pytest draait zomaar kunnen falen.
#
# Isolatie: save_path is een vast pad (net als bij
# contradiction_checker.py), geen constructor-parameter. Elke fixture
# overschrijft self.save_path EXPLICIET naar tmp_path na constructie,
# vóór er iets gelezen/geschreven wordt. shutdown() wordt in de
# teardown aangeroepen om beide achtergrondtimers netjes te stoppen.
#
# Uitvoeren: pytest tests/test_pattern_matcher.py -v

import time
from datetime import datetime, timedelta

import pytest

from modules.learning.pattern_matcher import PatternMatcher, DAGEN_NL


class DummyEventBus:
    def subscribe(self, *args, **kwargs):
        pass

    def publish(self, *args, **kwargs):
        pass


@pytest.fixture
def matcher(tmp_path, monkeypatch):
    """Bouwt een geïsoleerde PatternMatcher op.

    BELANGRIJK (correctie t.o.v. eerdere versie): save_path wordt in
    __init__() zelf berekend EN load_from_disk() wordt ook binnen
    __init__() aangeroepen -- dus save_path na constructie overschrijven
    komt te laat, __init__() heeft dan al je ECHTE data/patterns_layer2
    .json ingelezen. In plaats daarvan patchen we PatternMatcher.__init__
    zelf tijdelijk, zodat save_path AL naar tmp_path wijst voordat
    load_from_disk() ooit draait.
    """
    tijdelijk_pad = tmp_path / "patterns_layer2.json"
    origineel_init = PatternMatcher.__init__

    def gepatchte_init(self, event_bus=None, semantic_module=None):
        self.event_bus = event_bus
        self.semantic = semantic_module
        self.patterns = {}
        self.anomalies = []
        self.max_anomalies = 200
        self._laatst_gecheckte_uur_per_type = {}
        self.save_path = tijdelijk_pad  # HIER al gezet, vóór load_from_disk()
        self.load_from_disk()
        self.missing_event_check_interval_seconds = 3600
        self.missing_event_timer = None
        self._dirty = False
        self.save_timer = None
        if self.event_bus is not None:
            self.event_bus.subscribe("memory:interaction_added", self.detect_from)
        self.start_missing_event_checks()
        self.start_save_timer()

    monkeypatch.setattr(PatternMatcher, "__init__", gepatchte_init)

    pm = PatternMatcher(event_bus=None, semantic_module=None)

    yield pm

    # Teardown: stopt beide achtergrondtimers en schrijft een laatste
    # keer weg, zodat er geen levende thread blijft hangen na de test.
    pm.shutdown()


def _stuur_event(matcher, event_type, dt: datetime):
    """Simuleert 1 'memory:interaction_added'-event op een specifiek
    tijdstip, door detect_from() rechtstreeks aan te roepen (zoals
    memory.py dat via de EventBus zou doen)."""
    matcher.detect_from({
        "event_type": event_type,
        "timestamp": dt.timestamp(),
    })


# ─────────────────────────────────────────────────────────────
# Fase 1: event grouping -- welke event_types tellen mee
# ─────────────────────────────────────────────────────────────

def test_relevante_event_type_wordt_geteld(matcher):
    """chat_message zit in RELEVANTE_EVENT_TYPES en hoort geteld te worden."""
    dt = datetime(2026, 8, 10, 14, 0)  # maandag 14u
    _stuur_event(matcher, "chat_message", dt)

    pattern = matcher.get_pattern("chat_message")
    assert pattern is not None
    assert pattern["total"] == 1
    assert pattern["hours"][14] == 1
    assert pattern["days"]["maandag"] == 1


def test_irrelevant_event_type_wordt_genegeerd(matcher):
    """Interne pipeline-events (bv. 'pipeline_response') horen NIET
    meegeteld te worden -- staan niet in RELEVANTE_EVENT_TYPES en
    matchen geen topic_detected:/activity_started:-voorvoegsel."""
    dt = datetime(2026, 8, 10, 14, 0)
    _stuur_event(matcher, "pipeline_response", dt)

    assert matcher.get_pattern("pipeline_response") is None
    assert matcher.get_stats()["aantal_event_types"] == 0


def test_topic_detected_voorvoegsel_wordt_generiek_meegeteld(matcher):
    """topic_detected:<naam> is geen vaste string, maar hoort via het
    voorvoegsel toch meegeteld te worden, ongeacht welk onderwerp."""
    dt = datetime(2026, 8, 10, 14, 0)
    _stuur_event(matcher, "topic_detected:chess", dt)
    _stuur_event(matcher, "topic_detected:weer", dt)

    assert matcher.get_pattern("topic_detected:chess")["total"] == 1
    assert matcher.get_pattern("topic_detected:weer")["total"] == 1


def test_niet_dict_interactie_wordt_genegeerd_zonder_crash(matcher):
    """detect_from() hoort defensief om te gaan met een niet-dict
    interactie -- geen crash, gewoon negeren."""
    matcher.detect_from("dit is geen dict", event_type="memory:interaction_added")
    assert matcher.get_stats()["aantal_event_types"] == 0


def test_ontbrekende_timestamp_wordt_genegeerd(matcher):
    matcher.detect_from({"event_type": "chat_message"})  # geen timestamp
    assert matcher.get_pattern("chat_message") is None


# ─────────────────────────────────────────────────────────────
# Fase 2: pattern detection -- most_common_hour, confidence, day_frequency
# ─────────────────────────────────────────────────────────────

def test_most_common_hour_en_confidence(matcher):
    """Bij 8x om 9u en 2x om 15u hoort most_common_hour 9 te zijn,
    met confidence 0.8 (8 van de 10 observaties)."""
    for _ in range(8):
        _stuur_event(matcher, "chat_message", datetime(2026, 8, 10, 9, 0))
    for _ in range(2):
        _stuur_event(matcher, "chat_message", datetime(2026, 8, 10, 15, 0))

    pattern = matcher.get_pattern("chat_message")
    assert pattern["most_common_hour"] == 9
    assert pattern["confidence"] == pytest.approx(0.8, abs=0.001)


def test_day_frequency_hoge_score_voor_elke_keer_dezelfde_dag(matcher):
    """Als een event ALTIJD op maandag voorkomt, hoort day_frequency
    voor maandag rond 1.0 te liggen (genormaliseerd, zie
    _update_pattern_stats())."""
    for _ in range(5):
        _stuur_event(matcher, "chat_message", datetime(2026, 8, 10, 9, 0))  # maandag

    pattern = matcher.get_pattern("chat_message")
    assert pattern["day_frequency"]["maandag"] == pytest.approx(1.0, abs=0.01)
    assert pattern["day_frequency"]["dinsdag"] == 0.0


# ─────────────────────────────────────────────────────────────
# Fase 3, Deel A: anomaliedetectie -- ongewone timing
# ─────────────────────────────────────────────────────────────

def _bouw_sterk_patroon(matcher, event_type="chat_message", uur=9, dag_datum=None):
    """Helper: bouwt een sterk, betrouwbaar patroon op (>= MIN_OBSERVATIES_
    VOOR_ANOMALIE observaties, allemaal op hetzelfde uur), zodat
    _check_ongewone_timing() ook echt gaat vergelijken i.p.v. vroeg te
    stoppen wegens te weinig data."""
    basis_datum = dag_datum or datetime(2026, 8, 10)  # maandag
    for _ in range(matcher.MIN_OBSERVATIES_VOOR_ANOMALIE + 2):
        _stuur_event(matcher, event_type, basis_datum.replace(hour=uur))


def test_geen_anomalie_bij_te_weinig_observaties(matcher):
    """Met minder observaties dan MIN_OBSERVATIES_VOOR_ANOMALIE hoort
    een sterk afwijkend uur NIET als anomalie gelogd te worden --
    er is simpelweg nog geen betrouwbaar patroon om tegen te vergelijken."""
    for _ in range(3):  # ruim onder de drempel van 10
        _stuur_event(matcher, "chat_message", datetime(2026, 8, 10, 9, 0))

    # Sterk afwijkend uur (9u -> 23u, verschil > 4)
    _stuur_event(matcher, "chat_message", datetime(2026, 8, 11, 23, 0))

    assert matcher.get_anomalies() == []


def test_anomalie_bij_sterk_afwijkend_uur_na_betrouwbaar_patroon(matcher):
    """Zodra het patroon sterk genoeg is (genoeg observaties, hoge
    confidence) EN het huidige moment > 4 uur afwijkt van het
    gebruikelijke uur, hoort dit als 'ongewone_timing'-anomalie
    gelogd te worden."""
    _bouw_sterk_patroon(matcher, uur=9)  # patroon: altijd om 9u

    # Nu een observatie op 23u -- verschil met 9u is 10 (of 24-10=14,
    # dus min(10,14)=10), ruim boven de drempel van 4.
    _stuur_event(matcher, "chat_message", datetime(2026, 8, 11, 23, 0))

    anomalieen = matcher.get_anomalies()
    assert len(anomalieen) == 1
    assert anomalieen[0]["type"] == "ongewone_timing"
    assert anomalieen[0]["event_type"] == "chat_message"


def test_geen_anomalie_bij_klein_tijdsverschil(matcher):
    """Een afwijking van pakweg 2 uur (onder de drempel van >4) hoort
    NIET als anomalie gelogd te worden."""
    _bouw_sterk_patroon(matcher, uur=9)

    _stuur_event(matcher, "chat_message", datetime(2026, 8, 11, 11, 0))  # 2u verschil

    assert matcher.get_anomalies() == []


def test_middernacht_verschil_wordt_correct_over_de_grens_berekend(matcher):
    """
    Het uurverschil hoort 'rond middernacht' correct berekend te
    worden: 23u vs 1u is maar 2 uur verschil, niet 22u (zie
    _check_ongewone_timing()'s min(abs(...), 24-abs(...))-berekening).
    """
    _bouw_sterk_patroon(matcher, uur=23)  # patroon: altijd om 23u

    # 1u is maar 2 uur van 23u verwijderd (over middernacht heen) --
    # ONDER de drempel van 4, dus GEEN anomalie verwacht.
    _stuur_event(matcher, "chat_message", datetime(2026, 8, 11, 1, 0))

    assert matcher.get_anomalies() == [], (
        "23u en 1u liggen maar 2 uur uit elkaar over middernacht heen -- "
        "dit had NIET als anomalie gelogd mogen worden."
    )


def test_anomalieen_lijst_heeft_een_maximum(matcher):
    """De anomalieën-lijst mag niet onbeperkt groeien -- max_anomalies
    als bovengrens, meest recente eerst."""
    _bouw_sterk_patroon(matcher, uur=9)

    # Ruim meer afwijkende observaties dan max_anomalies produceren
    oorspronkelijk_max = matcher.max_anomalies
    matcher.max_anomalies = 3  # klein zetten zodat de test snel blijft

    for i in range(5):
        _stuur_event(matcher, "chat_message", datetime(2026, 8, 11 + i, 23, 0))

    assert len(matcher.anomalies) == 3


# ─────────────────────────────────────────────────────────────
# Fase 4: is_pattern_active()
# ─────────────────────────────────────────────────────────────

def test_is_pattern_active_true_op_het_juiste_moment(matcher):
    """
    is_pattern_active() gebruikt INTERN datetime.now() -- deze test
    bouwt daarom een patroon op basis van het ECHTE huidige uur/dag,
    i.p.v. een vast uur te hardcoden (dat zou de test flaky maken,
    afhankelijk van wanneer je pytest toevallig draait).
    """
    nu = datetime.now()
    huidig_uur = nu.hour
    huidige_dag_index = nu.weekday()

    # Bouw >= MIN_OBSERVATIES_VOOR_ANOMALIE observaties op, allemaal op
    # het HUIDIGE uur, op data die op dezelfde weekdag vallen als vandaag.
    for i in range(matcher.MIN_OBSERVATIES_VOOR_ANOMALIE + 2):
        # Ga steeds 7 dagen terug (dezelfde weekdag), zodat day_frequency
        # voor de huidige dag hoog genoeg wordt (>0.5).
        moment = nu - timedelta(days=7 * i)
        moment = moment.replace(hour=huidig_uur, minute=0, second=0, microsecond=0)
        _stuur_event(matcher, "chat_message", moment)

    assert matcher.is_pattern_active("chat_message") is True


def test_is_pattern_active_false_voor_onbekend_event_type(matcher):
    assert matcher.is_pattern_active("nooit_gezien_event") is False


def test_is_pattern_active_false_bij_te_weinig_observaties(matcher):
    _stuur_event(matcher, "chat_message", datetime.now())
    assert matcher.is_pattern_active("chat_message") is False


# ─────────────────────────────────────────────────────────────
# Fase 5: opslaan/herladen
# ─────────────────────────────────────────────────────────────

def test_save_en_load_behouden_patroon_data(matcher, tmp_path, monkeypatch):
    """Na save_to_disk() + een NIEUWE PatternMatcher-instantie met
    hetzelfde save_path, hoort het patroon correct hersteld te worden
    -- inclusief hours/days terug als defaultdict(int) en integer-
    sleutels voor uren (zie load_from_disk()'s expliciete herstel-
    logica).

    LET OP: gebruikt dezelfde monkeypatch-aanpak als de 'matcher'-
    fixture -- __init__() roept load_from_disk() intern aan, dus
    save_path moet AL correct staan vóór constructie, niet erna."""
    for _ in range(5):
        _stuur_event(matcher, "chat_message", datetime(2026, 8, 10, 9, 0))
    matcher.save_to_disk()

    origineel_init = PatternMatcher.__init__

    def gepatchte_init(self, event_bus=None, semantic_module=None):
        self.event_bus = event_bus
        self.semantic = semantic_module
        self.patterns = {}
        self.anomalies = []
        self.max_anomalies = 200
        self._laatst_gecheckte_uur_per_type = {}
        self.save_path = matcher.save_path  # zelfde tijdelijke bestand
        self.load_from_disk()
        self.missing_event_check_interval_seconds = 3600
        self.missing_event_timer = None
        self._dirty = False
        self.save_timer = None
        self.start_missing_event_checks()
        self.start_save_timer()

    monkeypatch.setattr(PatternMatcher, "__init__", gepatchte_init)
    nieuwe_matcher = PatternMatcher(event_bus=None, semantic_module=None)

    try:
        pattern = nieuwe_matcher.get_pattern("chat_message")
        assert pattern is not None
        assert pattern["total"] == 5
        assert pattern["hours"][9] == 5  # integer-sleutel, niet string "9"
        assert pattern["days"]["maandag"] == 5
    finally:
        nieuwe_matcher.shutdown()


def test_get_stats_bevat_verwachte_velden(matcher):
    _stuur_event(matcher, "chat_message", datetime(2026, 8, 10, 9, 0))
    _bouw_sterk_patroon(matcher, uur=9)
    _stuur_event(matcher, "chat_message", datetime(2026, 8, 11, 23, 0))  # triggert anomalie

    stats = matcher.get_stats()
    assert stats["aantal_event_types"] == 1
    assert stats["totaal_observaties"] > 0
    assert stats["aantal_anomalieen"] == 1