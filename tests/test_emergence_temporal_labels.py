# tests/test_emergence_temporal_labels.py -- Layer 7-labels voor Temporal Semantics (Fase 9.1/9.2)
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.experimental.emergence_engine import EmergenceEngine


class FakeBus:
    def __init__(self):
        self.modules = {}

    def subscribe(self, *a, **k):
        pass

    def publish(self, *a, **k):
        pass


def maak_engine():
    return EmergenceEngine(event_bus=FakeBus(), layers={})


def test_label_ontstaan():
    assert maak_engine()._onderwerp_label("topic_detected:ontstaan") == "wanneer dingen ontstonden"


def test_label_tijdlijn():
    assert maak_engine()._onderwerp_label("topic_detected:tijdlijn") == "tijdlijnen van dingen"


def test_bestaande_labels_ongewijzigd():
    e = maak_engine()
    assert e._onderwerp_label("topic_detected:chess") == "schaken"
    assert e._onderwerp_label("topic_detected:causes_check") == "oorzaak-en-gevolg-vragen"
    assert e._onderwerp_label("topic_detected:oorzaken_regen") == "oorzaken van regen"