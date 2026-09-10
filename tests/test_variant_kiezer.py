# tests/test_variant_kiezer.py
"""
Tests voor de gedeelde variant-kies-functie
(modules/response_learning/variant_kiezer.py), gebruikt door
response_pipeline.py en conversation_engine.py voor Response Variant
Learning.
"""

import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.response_learning.variant_kiezer import kies_variant


class FakeEventBus:
    def __init__(self):
        self.published = []

    def publish(self, event_type, data):
        self.published.append((event_type, data))


class FakeGewichtenLogger:
    """Simuleert variant_feedback_logger.get_gewichten()."""

    def __init__(self, gewichten_per_sjabloon):
        self.gewichten_per_sjabloon = gewichten_per_sjabloon

    def get_gewichten(self, sjabloon_naam, aantal_varianten):
        return self.gewichten_per_sjabloon.get(sjabloon_naam)


class KapotteGewichtenLogger:
    def get_gewichten(self, sjabloon_naam, aantal_varianten):
        raise RuntimeError("simuleer een fout")


def test_zonder_logger_gelijke_kansen(tmp_path):
    bus = FakeEventBus()
    teller = Counter()
    for _ in range(500):
        tekst = kies_variant(["a", "b", "c"], "sjabloon", bus, variant_feedback_logger=None)
        teller[tekst] += 1

    assert set(teller.keys()) == {"a", "b", "c"}
    # Geen enkele variant zou extreem moeten domineren zonder gewichten
    assert max(teller.values()) < 250


def test_event_wordt_altijd_gepubliceerd(tmp_path):
    bus = FakeEventBus()
    kies_variant(["enige"], "sjabloon_x", bus, entity="python", response_style="kort")

    assert len(bus.published) == 1
    event_type, data = bus.published[0]
    assert event_type == "variant_gekozen"
    assert data["sjabloon_naam"] == "sjabloon_x"
    assert data["entity"] == "python"
    assert data["response_style"] == "kort"
    assert data["gekozen_variant_index"] == 0
    assert data["variant_tekst"] == "enige"


def test_gewogen_keuze_favoriseert_hoog_gewicht():
    bus = FakeEventBus()
    logger = FakeGewichtenLogger({"sjabloon": [10.0, 0.05, 0.05]})

    teller = Counter()
    for _ in range(300):
        tekst = kies_variant(["x", "y", "z"], "sjabloon", bus, variant_feedback_logger=logger)
        teller[tekst] += 1

    assert teller["x"] > teller["y"]
    assert teller["x"] > teller["z"]


def test_fout_in_logger_valt_terug_op_gelijke_kansen():
    """Een fout in get_gewichten() mag nooit crashen -- valt terug op random."""
    bus = FakeEventBus()
    logger = KapotteGewichtenLogger()

    # Mag niet raisen
    tekst = kies_variant(["a", "b"], "sjabloon", bus, variant_feedback_logger=logger)
    assert tekst in ["a", "b"]


def test_uitsluiten_indices_wordt_nooit_gekozen():
    bus = FakeEventBus()
    for _ in range(200):
        tekst = kies_variant(
            ["a", "b", "c", "d"], "sjabloon", bus,
            variant_feedback_logger=None,
            uitsluiten_indices=[1],
        )
        assert tekst != "b"

    for _, data in bus.published:
        assert data["gekozen_variant_index"] != 1


def test_uitsluiten_indices_behoudt_index_stabiliteit():
    """
    De volledige lijst blijft behouden (niet gefilterd) -- de
    gelogde gekozen_variant_index moet altijd corresponderen met de
    juiste positie in de ORIGINELE, volledige lijst.
    """
    bus = FakeEventBus()
    varianten = ["x0", "x1", "x2", "x3"]
    for _ in range(50):
        kies_variant(varianten, "sjabloon", bus, uitsluiten_indices=[0, 2])

    for _, data in bus.published:
        idx = data["gekozen_variant_index"]
        assert varianten[idx] == data["variant_tekst"]
        assert idx not in (0, 2)


def test_uitsluiten_wint_van_hoog_gewicht():
    """Een uitgesloten index mag NOOIT gekozen worden, zelfs met het hoogste gewicht."""
    bus = FakeEventBus()
    logger = FakeGewichtenLogger({"sjabloon": [0.1, 10.0, 0.1]})  # index 1 favoriet

    for _ in range(200):
        tekst = kies_variant(
            ["a", "b", "c"], "sjabloon", bus,
            variant_feedback_logger=logger,
            uitsluiten_indices=[1],
        )
        assert tekst != "b"


def test_geen_event_bus_crasht_niet():
    tekst = kies_variant(["a", "b"], "sjabloon", event_bus=None)
    assert tekst in ["a", "b"]


def test_lege_uitsluiten_indices_lijst_gedraagt_zich_normaal():
    """Een lege lijst (in plaats van None) mag het gedrag niet veranderen."""
    bus = FakeEventBus()
    teller = Counter()
    for _ in range(200):
        tekst = kies_variant(["a", "b"], "sjabloon", bus, uitsluiten_indices=[])
        teller[tekst] += 1
    assert set(teller.keys()) == {"a", "b"}