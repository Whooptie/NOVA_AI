# tests/test_response_engine_kort.py
"""
Tests voor core/response_engine.py (Layer 4): timing-hint en
response_style, plus het eerlijke "weet ik niet"-gedrag en de
onderbrekingsbeslissing.

Belangrijkste bewijs: bij response_style == "kort" mag GEEN enkel
antwoord een timing-hint krijgen, ook het is_a_fallback-antwoord niet
(dat deed dat vroeger wel, zie nova_changelog.md).

Isolatie: ResponseEngine doet geen bestands-I/O in __init__, dus
tmp_path is hier niet nodig. Alle lagen zijn kleine neptoestellen
(Fake-klassen), geen echte concepts.json of patterns_layer2.json.
"""

import pytest

from core.response_engine import ResponseEngine

# Layer 2 kiest uit 3 timing_hint-varianten en Layer 4 kiest zelf
# willekeurig tussen sjablonen, dus elke test draait meerdere keren
# om alle varianten te raken.
HERHALINGEN = 30
UUR = 14


class FakeSemantic:
    """Minimale Layer 3: vaste definitie en/of is_a-ouders."""

    def __init__(self, definitie=None, ouders=None):
        self.definitie = definitie
        self.ouders = ouders or []

    def get_meaning(self, word, context_words=None):
        return self.definitie

    def get_relations(self, word, relation_type=None):
        return list(self.ouders)

    def detect_sense(self, word, context_words):
        return None


class FakePatternMatcher:
    """Minimale Layer 2: patroon is actief en piekt rond UUR."""

    def __init__(self, actief=True):
        self.actief = actief

    def is_pattern_active(self, event_type):
        return self.actief

    def get_pattern(self, event_type):
        return {"most_common_hour": UUR}


class FakeTracker:
    """Minimale interruption_tracker met een vaste confidence."""

    def __init__(self, genoeg_data=True, confidence=None):
        self.genoeg_data = genoeg_data
        self.confidence = confidence

    def has_enough_data(self, activiteit, min_observaties=None, tijd_sinds_start=None):
        return self.genoeg_data

    def get_confidence(self, activiteit, tijd_sinds_start=None):
        return self.confidence


@pytest.fixture
def maak_engine():
    class DummyEventBus:
        def __init__(self):
            self.gepubliceerd = []

        def publish(self, event_type, data=None):
            self.gepubliceerd.append((event_type, data))

    def _maak(semantic=None, pattern_matcher=None, tracker=None):
        layers = {}
        if semantic is not None:
            layers["semantic"] = semantic
        if pattern_matcher is not None:
            layers["pattern_matcher"] = pattern_matcher
        if tracker is not None:
            layers["interruption_tracker"] = tracker
        return ResponseEngine(DummyEventBus(), layers=layers)

    return _maak


# ---------------------------------------------------------------
# Timing-hint en response_style
# ---------------------------------------------------------------

def test_is_a_fallback_normaal_heeft_timing_hint(maak_engine):
    engine = maak_engine(FakeSemantic(ouders=["dier"]), FakePatternMatcher())
    for _ in range(HERHALINGEN):
        resultaat = engine.generate("hond", response_style="normaal")
        assert resultaat["confidence"] == 0.6
        assert f"{UUR}u" in resultaat["text"]


def test_is_a_fallback_kort_heeft_geen_timing_hint(maak_engine):
    engine = maak_engine(FakeSemantic(ouders=["dier"]), FakePatternMatcher())
    for _ in range(HERHALINGEN):
        resultaat = engine.generate("hond", response_style="kort")
        assert resultaat["confidence"] == 0.6
        assert f"{UUR}u" not in resultaat["text"]


def test_definitie_normaal_heeft_timing_hint(maak_engine):
    engine = maak_engine(FakeSemantic(definitie="een huisdier"), FakePatternMatcher())
    for _ in range(HERHALINGEN):
        resultaat = engine.generate("hond", response_style="normaal")
        assert resultaat["confidence"] == 0.9
        assert "een huisdier" in resultaat["text"]
        assert f"{UUR}u" in resultaat["text"]


def test_definitie_kort_heeft_geen_timing_hint(maak_engine):
    engine = maak_engine(FakeSemantic(definitie="een huisdier"), FakePatternMatcher())
    for _ in range(HERHALINGEN):
        resultaat = engine.generate("hond", response_style="kort")
        assert resultaat["confidence"] == 0.9
        assert "een huisdier" in resultaat["text"]
        assert f"{UUR}u" not in resultaat["text"]


def test_onbekend_krijgt_nooit_een_timing_hint(maak_engine):
    engine = maak_engine(FakeSemantic(), FakePatternMatcher())
    for stijl in ("normaal", "kort", "uitgebreid"):
        for _ in range(HERHALINGEN):
            resultaat = engine.generate("blablabla", response_style=stijl)
            assert resultaat["confidence"] == 0.2
            assert resultaat["sources"] == []
            assert f"{UUR}u" not in resultaat["text"]


# ---------------------------------------------------------------
# Ontbrekende lagen: nooit crashen, eerlijk antwoorden
# ---------------------------------------------------------------

def test_zonder_enige_laag_antwoordt_nova_eerlijk_onbekend():
    engine = ResponseEngine(None, layers={})
    resultaat = engine.generate("hond")
    assert resultaat["confidence"] == 0.2
    assert resultaat["sources"] == []


def test_lege_entity_vraagt_waarover():
    engine = ResponseEngine(None, layers={})
    resultaat = engine.generate("   ")
    assert resultaat["text"] == "Waarover wil je meer weten?"
    assert resultaat["confidence"] == 0.0


# ---------------------------------------------------------------
# Onderbrekingsbeslissing (Activity-Aware Interaction)
# ---------------------------------------------------------------

def test_zonder_tracker_vraagt_nova_eerst(maak_engine):
    engine = maak_engine()
    beslissing = engine.beslis_interruption_gedrag("coderen", tijd_sinds_start=15.0)
    assert beslissing["actie"] == "vraag_eerst"
    assert beslissing["tekst"] in engine.templates["interruption_vraag"]
    assert beslissing["confidence"] is None


def test_te_weinig_data_vraagt_nova_eerst(maak_engine):
    engine = maak_engine(tracker=FakeTracker(genoeg_data=False, confidence=0.95))
    beslissing = engine.beslis_interruption_gedrag("coderen", tijd_sinds_start=15.0)
    assert beslissing["actie"] == "vraag_eerst"


def test_hoge_confidence_gaat_gewoon_door(maak_engine):
    engine = maak_engine(tracker=FakeTracker(confidence=0.9))
    beslissing = engine.beslis_interruption_gedrag("coderen", tijd_sinds_start=15.0)
    assert beslissing["actie"] == "ga_gewoon_door"
    assert beslissing["tekst"] in engine.templates["interruption_ga_door"]
    assert beslissing["confidence"] == 0.9


def test_lage_confidence_blijft_stil(maak_engine):
    engine = maak_engine(tracker=FakeTracker(confidence=0.1))
    beslissing = engine.beslis_interruption_gedrag("gamen", tijd_sinds_start=15.0)
    assert beslissing["actie"] == "blijf_stil"
    assert beslissing["tekst"] is None
    assert beslissing["confidence"] == 0.1


def test_middenzone_vraagt_nova_eerst(maak_engine):
    engine = maak_engine(tracker=FakeTracker(confidence=0.5))
    beslissing = engine.beslis_interruption_gedrag("lezen", tijd_sinds_start=15.0)
    assert beslissing["actie"] == "vraag_eerst"
    assert beslissing["confidence"] == 0.5