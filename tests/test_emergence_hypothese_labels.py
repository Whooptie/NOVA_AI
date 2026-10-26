# tests/test_emergence_hypothese_labels.py -- Layer 7-labels voor idee 3 + 4
import pytest

from modules.experimental.emergence_engine import EmergenceEngine


@pytest.fixture
def engine(monkeypatch):
    # De constructor leest feedback- en cooldown-bestanden uit data/; in de
    # test laten we die leeg zodat er nooit echte bestanden aangeraakt worden.
    monkeypatch.setattr(EmergenceEngine, "_load_feedback", lambda self: {})
    monkeypatch.setattr(EmergenceEngine, "_laad_cooldown_state", lambda self: {})
    return EmergenceEngine(event_bus=None, layers={})


def test_hypothese_label(engine):
    assert engine._onderwerp_label("topic_detected:hypothese") == "wat-als-vragen"


def test_terugblik_label(engine):
    assert engine._onderwerp_label("topic_detected:terugblik") == "terugblikken op eerdere vragen"


def test_bestaande_labels_ongewijzigd(engine):
    assert engine._onderwerp_label("topic_detected:chess") == "schaken"
    assert engine._onderwerp_label("topic_detected:zekerheid") == "hoe zeker dingen zijn"
    assert engine._onderwerp_label("topic_detected:onbekend_ding") == "onbekend_ding"