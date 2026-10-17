# tests/test_kennis_detectie.py -- Semantic Fase 11.2: router-detectie voor
# "extraheer X" en "neem N over" / "laat N vallen"
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.intent_router import IntentRouter


class RouterBus:
    def __init__(self):
        self.ev = []

    def publish(self, e, d=None):
        self.ev.append((e, d))

    def subscribe(self, *a, **k):
        pass


@pytest.fixture
def router():
    r = IntentRouter.__new__(IntentRouter)
    r.event_bus = RouterBus()
    r.topics = []
    r._emit_topic = lambda *a, **k: r.topics.append((a, k))
    return r


def events(r):
    return list(r.event_bus.ev)


# ---------- extraheer ----------
@pytest.mark.parametrize("zin, woord", [
    ("extraheer fiets", "fiets"),
    ("Extraheer fiets!", "fiets"),
    ("extraheer de fiets", "fiets"),
    ("extraheer kennis over gitaar", "gitaar"),
    ("extraheer uit wikipedia over machine learning", "machine learning"),
    ("haal kennis uit wikipedia over hond", "hond"),
    ("haal kennis van het water", "water"),
    ("extraheer regen (neerslag)", "regen (neerslag)"),
    ("Extraheer Regen (Neerslag)!", "regen (neerslag)"),
    ("extraheer de bank (meubel)", "bank (meubel)"),
    ("haal kennis over wiel (voertuig)", "wiel (voertuig)"),
])
def test_extractie_positief(router, zin, woord):
    assert router.detect_kennis_extractie(zin) is True
    assert events(router)[-1] == ("intent_kennis_extract", {"word": woord})
    assert router.topics and router.topics[-1][0][0] == "kennis_extractie"


@pytest.mark.parametrize("zin", [
    "extraheer",
    "extraheer ",
    "wat is extraheer",
    "kun je fiets extraheren",
    "extraheer een twee drie vier vijf",
    "extraheer jij",
    "extraheer regen (neerslag",
    "extraheer regen ()",
    "extraheer (neerslag)",
    "haal kennis",
    "wat weet je over fiets",
])
def test_extractie_negatief(router, zin):
    assert router.detect_kennis_extractie(zin) is False
    assert events(router) == []


# ---------- neem / laat vallen ----------
@pytest.mark.parametrize("zin, actie, nr, alles", [
    ("neem 2 over", "neem", 2, False),
    ("Neem 12 over", "neem", 12, False),
    ("neem alles over", "neem", None, True),
    ("laat 3 vallen", "laat_vallen", 3, False),
    ("laat alles vallen", "laat_vallen", None, True),
])
def test_keuze_positief(router, zin, actie, nr, alles):
    assert router.detect_kennis_keuze(zin) is True
    assert events(router)[-1] == ("intent_kennis_keuze",
                                  {"actie": actie, "nummer": nr, "alles": alles})


@pytest.mark.parametrize("zin", [
    "neem 2",
    "neem over",
    "neem 123 over",
    "laat 2 los",
    "laat vallen",
    "bevestig 2",           # is van Fase 10.2
    "wijs af 2",            # is van Fase 10.2
    "ik neem 2 over",
])
def test_keuze_negatief(router, zin):
    assert router.detect_kennis_keuze(zin) is False
    assert events(router) == []


def test_botst_niet_met_onzekerheidscommandos(router):
    assert router.detect_kennis_keuze("bevestig 3") is False
    assert router.detect_uncertainty_keuze("neem 3 over") is False