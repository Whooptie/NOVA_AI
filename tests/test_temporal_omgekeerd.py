# tests/test_temporal_omgekeerd.py -- Semantic Fase 9.3 (omgekeerde vragen)
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.semantic import ConceptStore, SenseEngine, SemanticConceptsModule
from core.intent_router import IntentRouter
from modules.knowledge import temporal_semantics as ts


class FakeBus:
    def __init__(self):
        self.gepubliceerd = []
        self.handlers = {}
        self.modules = {}

    def subscribe(self, naam, handler):
        self.handlers.setdefault(naam, []).append(handler)

    def publish(self, naam, data=None):
        self.gepubliceerd.append((naam, data))
        for h in self.handlers.get(naam, []):
            h(data)

    def events(self, naam):
        return [d for n, d in self.gepubliceerd if n == naam]


@pytest.fixture
def engine(tmp_path):
    store = ConceptStore(str(tmp_path / "c.json"), str(tmp_path / "log.jsonl"))
    return SenseEngine(store)


@pytest.fixture
def opstelling(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    bus = FakeBus()
    sem = SemanticConceptsModule(bus)
    sem.store = ConceptStore(str(tmp_path / "c.json"), str(tmp_path / "log.jsonl"))
    sem.sense_engine = SenseEngine(sem.store)
    router = IntentRouter(bus, semantic_module=sem)
    ts.init_module(bus, sem)
    return bus, sem, router


def vul(sem):
    for woord, jaar in [("vliegtuig", 1903), ("python", 1991), ("internet", 1983),
                        ("piano", 1700), ("machine learning", 1959)]:
        sem.set_ontstaan(woord, jaar)


def zeg(router, bus, tekst):
    bus.gepubliceerd.clear()
    router.route({"text": tekst})
    antw = bus.events("layer4_response") + bus.events("chat_response")
    return antw[-1]["text"] if antw else None


# ---------- SenseEngine.get_all_ontstaan ----------
def test_get_all_ontstaan_gesorteerd(engine):
    engine.set_ontstaan("python", 1991)
    engine.set_ontstaan("piano", 1700)
    engine.set_ontstaan("internet", 1983)
    assert engine.get_all_ontstaan() == [
        {"word": "piano", "jaar": 1700},
        {"word": "internet", "jaar": 1983},
        {"word": "python", "jaar": 1991},
    ]


def test_get_all_ontstaan_zelfde_jaar_op_woord(engine):
    engine.set_ontstaan("b", 1990)
    engine.set_ontstaan("a", 1990)
    assert [r["word"] for r in engine.get_all_ontstaan()] == ["a", "b"]


def test_get_all_ontstaan_negeert_afgewezen_en_woorden_zonder_jaar(engine):
    s = engine.add_sense("slang", "een dier")
    engine.set_ontstaan("slang", 1000)
    s["status"] = "rejected"
    engine.add_sense("hond", "een dier")
    assert engine.get_all_ontstaan() == []


def test_get_all_ontstaan_leeg(engine):
    assert engine.get_all_ontstaan() == []


# ---------- detect_temporal_omgekeerd ----------
@pytest.mark.parametrize("zin,vorm,van,tot,jaar", [
    ("wat bestond er in 1990", "bestond", None, 1990, 1990),
    ("wat bestond er al in 1990?", "bestond", None, 1990, 1990),
    ("wat ontstond er in 1991", "exact", 1991, 1991, 1991),
    ("wat ontstond er tussen 1950 en 1960", "tussen", 1950, 1960, 1950),
    ("wat ontstond er voor 1900", "voor", None, 1899, 1900),
    ("wat ontstond er na 1990", "na", 1991, None, 1990),
])
def test_omgekeerd_herkend(opstelling, zin, vorm, van, tot, jaar):
    bus, sem, router = opstelling
    bus.gepubliceerd.clear()
    assert router.detect_temporal(zin) is True
    assert bus.events("intent_temporal_omgekeerd") == [
        {"vorm": vorm, "van": van, "tot": tot, "jaar": jaar}]


@pytest.mark.parametrize("zin", [
    "wat ontstond er in 3000",
    "wat bestond er in 0",
    "wat ontstond er tussen 1960 en 1950",
    "wat ontstond er in",
    "wat ontstond er vandaag",
    "wat bestond er gisteren",
])
def test_omgekeerd_geen_match(opstelling, zin):
    bus, sem, router = opstelling
    bus.gepubliceerd.clear()
    router.detect_temporal(zin)
    assert not bus.events("intent_temporal_omgekeerd")


# ---------- eind-tot-eind via route() ----------
def test_route_bestond(opstelling):
    bus, sem, router = opstelling
    vul(sem)
    antw = zeg(router, bus, "wat bestond er in 1960")
    assert antw == ("Dit bestond al in 1960 (voor zover ik weet):\n"
                    "- piano (1700)\n- vliegtuig (1903)\n- machine learning (1959)")


def test_route_exact(opstelling):
    bus, sem, router = opstelling
    vul(sem)
    assert zeg(router, bus, "wat ontstond er in 1991") == \
        "Dit ontstond in 1991 (voor zover ik weet):\n- python (1991)"


def test_route_tussen(opstelling):
    bus, sem, router = opstelling
    vul(sem)
    antw = zeg(router, bus, "wat ontstond er tussen 1950 en 1990")
    assert "machine learning (1959)" in antw and "internet (1983)" in antw
    assert "python" not in antw and "vliegtuig" not in antw


def test_route_voor_en_na(opstelling):
    bus, sem, router = opstelling
    vul(sem)
    voor = zeg(router, bus, "wat ontstond er voor 1903")
    assert "piano (1700)" in voor and "vliegtuig" not in voor
    na = zeg(router, bus, "wat ontstond er na 1983")
    assert "python (1991)" in na and "internet" not in na


def test_route_leeg_met_uitleg_over_kennis(opstelling):
    bus, sem, router = opstelling
    vul(sem)
    antw = zeg(router, bus, "wat ontstond er in 1800")
    assert "geen woord" in antw and "5 woorden" in antw


def test_route_zonder_enige_data(opstelling):
    bus, sem, router = opstelling
    antw = zeg(router, bus, "wat bestond er in 1990")
    assert "geen enkel woord" in antw


def test_route_beperkt_lange_lijst(opstelling):
    bus, sem, router = opstelling
    for i in range(25):
        sem.set_ontstaan(f"woord{i:02d}", 1900 + i)
    antw = zeg(router, bus, "wat bestond er in 2000")
    assert antw.count("\n- ") == 21
    assert "nog 5 meer" in antw


def test_vorige_fases_blijven_werken(opstelling):
    bus, sem, router = opstelling
    assert "Genoteerd" in zeg(router, bus, "python bestaat sinds 1991")
    assert zeg(router, bus, "wanneer ontstond python") == "Python bestaat sinds 1991."
    assert "Genoteerd" in zeg(router, bus, "python was van 1991 tot 2005 een niche")
    assert zeg(router, bus, "wat was python in 2003") == "In 2003 was Python een niche."