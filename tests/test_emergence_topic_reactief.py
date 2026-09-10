"""
Tests voor punt 15: gespreks-contextuele proactiviteit in Layer 7.

Test tegen de ECHTE emergence_engine.py (met de 4 zoek/vervang-blokken
al toegepast), niet een nagebouwde kopie -- zelfde aanpak als
test_memory_archief_search.py voor memory.py.

Isolatie: get_project_root() gemonkeypatcht zodat _feedback_path/
_cooldown_path in tmp_path terechtkomen (vaste werkwijze, zie
nova_state.md) -- MemoryModule-stijl I/O in __init__ (hier: 2 JSON-
laadpogingen) vereist dit.
"""

import sys
import time
import pytest

sys.path.insert(0, ".")

import modules.paths as paths_module


class NepEventBus:
    """
    "*" gedraagt zich als wildcard-voor-alles (zelfde patroon als
    memory.py's event_bus.subscribe("*", self.on_event) -- ELKE
    publish() roept ook de "*"-subscribers aan, naast eventuele exacte
    event_type-matches. Zonder dit zou _on_elk_event() (dat op "*"
    subscribet) nooit iets ontvangen in deze nep-bus, ook al werkt het
    prima tegen de echte EventBus.
    """
    def __init__(self):
        self.modules = {}
        self._subscribers = {}
        self.gepubliceerd = []

    def subscribe(self, event_type, handler):
        self._subscribers.setdefault(event_type, []).append(handler)

    def publish(self, event_type, data):
        self.gepubliceerd.append((event_type, data))
        for handler in self._subscribers.get(event_type, []):
            handler(data, event_type=event_type)
        for handler in self._subscribers.get("*", []):
            handler(data, event_type=event_type)


class NepPatternMatcher:
    """Simuleert get_pattern() met vaste, controleerbare data."""

    MIN_OBSERVATIES_VOOR_ANOMALIE = 10

    def __init__(self, patterns=None):
        self._patterns = patterns or {}

    def get_pattern(self, event_type):
        return self._patterns.get(event_type)

    def get_all_patterns(self):
        return self._patterns


class NepContextManager:
    def __init__(self, mag_onderbreken=True):
        self._mag_onderbreken = mag_onderbreken

    def can_interrupt(self):
        return self._mag_onderbreken


def _sterk_pattern(total=20, confidence=0.9, uur=14):
    return {"total": total, "confidence": confidence, "most_common_hour": uur}


@pytest.fixture
def engine(tmp_path, monkeypatch):
    """
    Bouwt een echte EmergenceEngine, met get_project_root()
    gemonkeypatcht zodat alle state-bestanden (feedback + cooldown)
    in tmp_path terechtkomen -- volledige isolatie, geen aanraking
    van echte data/-bestanden.
    """
    monkeypatch.setattr(paths_module, "get_project_root", lambda f: tmp_path)

    # emergence_engine.py doet "from modules.paths import get_project_root"
    # -- die naam moet OOK in emergence_engine's eigen module-namespace
    # gepatcht worden, monkeypatchen van paths_module alleen is niet genoeg
    # omdat de import al bij module-load gebeurd is.
    import modules.experimental.emergence_engine as ee_module
    monkeypatch.setattr(ee_module, "get_project_root", lambda f: tmp_path)

    from modules.experimental.emergence_engine import EmergenceEngine

    bus = NepEventBus()

    def _maak(pattern_matcher=None, context_manager=None):
        layers = {}
        if pattern_matcher is not None:
            layers["pattern_matcher"] = pattern_matcher
        if context_manager is not None:
            layers["context_manager"] = context_manager
        return EmergenceEngine(event_bus=bus, layers=layers)

    yield bus, _maak


class TestCheckTopicSterkte:
    """Directe tests van _check_topic_sterkte(), los van gates/events."""

    def test_geen_pattern_matcher_geeft_none(self, engine):
        bus, maak = engine
        eng = maak()
        assert eng._check_topic_sterkte("python") is None

    def test_onbekend_topic_geeft_none(self, engine):
        bus, maak = engine
        pm = NepPatternMatcher({})
        eng = maak(pattern_matcher=pm)
        assert eng._check_topic_sterkte("python") is None

    def test_te_weinig_observaties_geeft_none(self, engine):
        bus, maak = engine
        pm = NepPatternMatcher({
            "topic_detected:python": _sterk_pattern(total=5)  # < 10
        })
        eng = maak(pattern_matcher=pm)
        assert eng._check_topic_sterkte("python") is None

    def test_geen_most_common_hour_geeft_none(self, engine):
        bus, maak = engine
        pm = NepPatternMatcher({
            "topic_detected:python": {"total": 20, "confidence": 0.9, "most_common_hour": None}
        })
        eng = maak(pattern_matcher=pm)
        assert eng._check_topic_sterkte("python") is None

    def test_sterk_genoeg_geeft_tijdspatroon_insight(self, engine):
        bus, maak = engine
        pm = NepPatternMatcher({
            "topic_detected:python": _sterk_pattern(total=20, confidence=0.9, uur=14)
        })
        eng = maak(pattern_matcher=pm)
        insight = eng._check_topic_sterkte("python")
        assert insight is not None
        assert insight["type"] == "tijdspatroon"
        assert insight["event_type"] == "topic_detected:python"
        assert insight["confidence"] == 0.9
        assert insight["uur"] == 14


class TestCooldown:
    """Tests van _op_cooldown()/_zet_cooldown()/_cooldown_sleutel()."""

    def test_nog_nooit_gemeld_is_niet_op_cooldown(self, engine):
        bus, maak = engine
        eng = maak()
        insight = {"type": "tijdspatroon", "event_type": "topic_detected:python", "confidence": 0.9}
        assert eng._op_cooldown(insight) is False

    def test_net_gemeld_is_op_cooldown(self, engine):
        bus, maak = engine
        eng = maak()
        insight = {"type": "tijdspatroon", "event_type": "topic_detected:python", "confidence": 0.9}
        eng._zet_cooldown(insight)
        assert eng._op_cooldown(insight) is True

    def test_verlopen_cooldown_is_niet_meer_op_cooldown(self, engine):
        bus, maak = engine
        eng = maak()
        insight = {"type": "tijdspatroon", "event_type": "topic_detected:python", "confidence": 0.9}
        eng.EMERGENCE_TOPIC_COOLDOWN_MINUTEN = 15
        # Simuleer "16 minuten geleden gemeld"
        sleutel = eng._cooldown_sleutel(insight)
        eng._laatst_gemeld[sleutel] = time.time() - (16 * 60)
        assert eng._op_cooldown(insight) is False

    def test_ander_topic_zelfde_type_niet_geblokkeerd(self, engine):
        """Kernpunt van 'losser dan per uur': topic A op cooldown mag
        topic B niet blokkeren."""
        bus, maak = engine
        eng = maak()
        insight_a = {"type": "tijdspatroon", "event_type": "topic_detected:python", "confidence": 0.9}
        insight_b = {"type": "tijdspatroon", "event_type": "topic_detected:schaken", "confidence": 0.9}
        eng._zet_cooldown(insight_a)
        assert eng._op_cooldown(insight_a) is True
        assert eng._op_cooldown(insight_b) is False

    def test_cooldown_state_persisteert_naar_schijf(self, engine, tmp_path):
        bus, maak = engine
        eng = maak()
        insight = {"type": "tijdspatroon", "event_type": "topic_detected:python", "confidence": 0.9}
        eng._zet_cooldown(insight)

        assert eng._cooldown_path.exists()

    def test_kennisdichtheid_gebruikt_insight_type_als_sleutel(self, engine):
        bus, maak = engine
        eng = maak()
        insight = {"type": "kennisdichtheid", "confidence": 10}
        sleutel = eng._cooldown_sleutel(insight)
        assert sleutel == "kennisdichtheid"


class TestOnElkEvent:
    """Integratietest: het volledige gerichte pad via _on_elk_event()."""

    def test_negeert_niet_topic_detected_events(self, engine):
        bus, maak = engine
        pm = NepPatternMatcher({
            "topic_detected:python": _sterk_pattern()
        })
        eng = maak(pattern_matcher=pm, context_manager=NepContextManager())
        bus.publish("chat_message", {"text": "iets"})

        layer4_calls = [e for e in bus.gepubliceerd if e[0] == "layer4_response"]
        assert layer4_calls == []

    def test_zwak_topic_publiceert_niets(self, engine):
        bus, maak = engine
        pm = NepPatternMatcher({
            "topic_detected:python": _sterk_pattern(total=2)  # te weinig
        })
        eng = maak(pattern_matcher=pm, context_manager=NepContextManager())
        bus.publish("topic_detected:python", {"bron": "detect"})

        layer4_calls = [e for e in bus.gepubliceerd if e[0] == "layer4_response"]
        assert layer4_calls == []

    def test_sterk_topic_mag_onderbreken_publiceert_layer4_response(self, engine):
        bus, maak = engine
        pm = NepPatternMatcher({
            "topic_detected:python": _sterk_pattern(total=20, confidence=0.95, uur=14)
        })
        eng = maak(pattern_matcher=pm, context_manager=NepContextManager(mag_onderbreken=True))
        bus.publish("topic_detected:python", {"bron": "detect"})

        layer4_calls = [e for e in bus.gepubliceerd if e[0] == "layer4_response"]
        assert len(layer4_calls) == 1
        assert "text" in layer4_calls[0][1]

    def test_mag_niet_onderbreken_blokkeert(self, engine):
        bus, maak = engine
        pm = NepPatternMatcher({
            "topic_detected:python": _sterk_pattern(total=20, confidence=0.95)
        })
        eng = maak(pattern_matcher=pm, context_manager=NepContextManager(mag_onderbreken=False))
        bus.publish("topic_detected:python", {"bron": "detect"})

        layer4_calls = [e for e in bus.gepubliceerd if e[0] == "layer4_response"]
        assert layer4_calls == []

    def test_ontbrekende_context_manager_blokkeert_niet(self, engine):
        """Fail-open, zelfde principe als _mag_nu_spreken()'s eigen docstring."""
        bus, maak = engine
        pm = NepPatternMatcher({
            "topic_detected:python": _sterk_pattern(total=20, confidence=0.95)
        })
        eng = maak(pattern_matcher=pm)  # geen context_manager
        bus.publish("topic_detected:python", {"bron": "detect"})

        layer4_calls = [e for e in bus.gepubliceerd if e[0] == "layer4_response"]
        assert len(layer4_calls) == 1

    def test_tweede_bericht_zelfde_topic_binnen_cooldown_wordt_stil(self, engine):
        """Kernscenario van punt 15's cooldown-vereiste."""
        bus, maak = engine
        pm = NepPatternMatcher({
            "topic_detected:python": _sterk_pattern(total=20, confidence=0.95)
        })
        eng = maak(pattern_matcher=pm, context_manager=NepContextManager())

        bus.publish("topic_detected:python", {"bron": "detect"})
        bus.publish("topic_detected:python", {"bron": "detect"})  # meteen erna

        layer4_calls = [e for e in bus.gepubliceerd if e[0] == "layer4_response"]
        assert len(layer4_calls) == 1  # niet 2

    def test_ander_topic_meteen_erna_wordt_niet_geblokkeerd(self, engine):
        """Kernscenario van Kevin's 'losser dan per uur'-wens: 2
        verschillende onderwerpen binnen 1 gesprek moeten allebei
        gewoon door kunnen."""
        bus, maak = engine
        pm = NepPatternMatcher({
            "topic_detected:python": _sterk_pattern(total=20, confidence=0.95),
            "topic_detected:schaken": _sterk_pattern(total=20, confidence=0.95),
        })
        eng = maak(pattern_matcher=pm, context_manager=NepContextManager())

        bus.publish("topic_detected:python", {"bron": "detect"})
        bus.publish("topic_detected:schaken", {"bron": "detect"})

        layer4_calls = [e for e in bus.gepubliceerd if e[0] == "layer4_response"]
        assert len(layer4_calls) == 2

    def test_geen_pattern_matcher_crasht_niet(self, engine):
        bus, maak = engine
        eng = maak(context_manager=NepContextManager())
        # Mag geen exceptie geven, gewoon stil blijven
        bus.publish("topic_detected:python", {"bron": "detect"})

        layer4_calls = [e for e in bus.gepubliceerd if e[0] == "layer4_response"]
        assert layer4_calls == []


class TestReflectGebruiktZelfdeCooldown:
    """
    Bevestigt dat de bestaande periodieke reflect()-klok nu OOK de
    gedeelde cooldown respecteert -- kernpunt van Kevin's antwoord op
    'moet dit ook de periodieke klok blokkeren? Ja.'
    """

    def test_reflect_zet_cooldown_en_tweede_aanroep_herhaalt_niet(self, engine):
        bus, maak = engine
        pm = NepPatternMatcher({
            "topic_detected:python": _sterk_pattern(total=20, confidence=0.95, uur=14)
        })
        eng = maak(pattern_matcher=pm, context_manager=NepContextManager())

        eng.reflect()
        eerste_aantal = len([e for e in bus.gepubliceerd if e[0] == "layer4_response"])

        eng.reflect()
        tweede_aantal = len([e for e in bus.gepubliceerd if e[0] == "layer4_response"])

        # 2e reflect()-ronde mag NIET opnieuw hetzelfde tijdspatroon-
        # insight publiceren zolang de cooldown nog loopt.
        assert tweede_aantal == eerste_aantal

    def test_on_elk_event_zet_cooldown_die_reflect_ook_respecteert(self, engine):
        """Kruistest: het GERICHTE pad meldt iets, en de PERIODIEKE
        klok mag dat exacte onderwerp daarna niet nog eens melden."""
        bus, maak = engine
        pm = NepPatternMatcher({
            "topic_detected:python": _sterk_pattern(total=20, confidence=0.95, uur=14)
        })
        eng = maak(pattern_matcher=pm, context_manager=NepContextManager())

        # Gericht pad meldt het eerst
        bus.publish("topic_detected:python", {"bron": "detect"})
        na_gericht_pad = len([e for e in bus.gepubliceerd if e[0] == "layer4_response"])
        assert na_gericht_pad == 1

        # Periodieke klok draait meteen erna -- zelfde topic is de
        # sterkste kandidaat, maar staat al op cooldown
        eng.reflect()
        na_periodieke_klok = len([e for e in bus.gepubliceerd if e[0] == "layer4_response"])

        assert na_periodieke_klok == na_gericht_pad  # geen extra melding