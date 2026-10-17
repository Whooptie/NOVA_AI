# tests/test_emergence_kennis_labels.py -- Layer 7-label voor Knowledge Extraction (Fase 11.2)
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


def test_label_kennis_extractie():
    assert maak_engine()._onderwerp_label("topic_detected:kennis_extractie") == "kennis uit Wikipedia halen"


def test_bestaande_labels_ongewijzigd():
    e = maak_engine()
    assert e._onderwerp_label("topic_detected:zekerheid") == "hoe zeker dingen zijn"
    assert e._onderwerp_label("topic_detected:chess") == "schaken"