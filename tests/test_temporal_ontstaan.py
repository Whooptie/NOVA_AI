# tests/test_temporal_ontstaan.py -- Semantic Fase 9.1 (ontstaansjaar)
import os
import sys
from datetime import datetime

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


def zeg(router, bus, tekst):
    bus.gepubliceerd.clear()
    router.route({"text": tekst})
    antw = bus.events("layer4_response")
    return antw[-1]["text"] if antw else None


# ---------- SenseEngine ----------
def test_set_en_get_ontstaan(engine):
    engine.add_sense("python", "een programmeertaal")
    r = engine.set_ontstaan("python", 1991)
    assert r == {"jaar": 1991, "oud": None}
    assert engine.get_ontstaan("python")["jaar"] == 1991


def test_ontstaan_zonder_bestaande_sense_maakt_unknown_sense(engine):
    engine.set_ontstaan("rad", 3500)
    assert engine.get_ontstaan("rad")["jaar"] == 3500
    assert engine.get_senses("rad")[0]["definition"] == "unknown"


def test_overschrijven_geeft_oude_waarde_en_audit(engine):
    engine.set_ontstaan("python", 1990)
    r = engine.set_ontstaan("python", 1991)
    assert r["oud"] == 1990
    log = engine.store.get_concept("python")["audit_log"]
    assert any(e["event_type"] == "ontstaan_set" and e["new_value"] == 1991 for e in log)


def test_onbekend_woord_geeft_none(engine):
    assert engine.get_ontstaan("bestaatniet") is None


def test_afgewezen_sense_telt_niet_mee(engine):
    s = engine.add_sense("python", "een slang")
    engine.set_ontstaan("python", 1991)
    s["status"] = "rejected"
    assert engine.get_ontstaan("python") is None


def test_persistentie(tmp_path):
    pad, log = str(tmp_path / "c.json"), str(tmp_path / "l.jsonl")
    SenseEngine(ConceptStore(pad, log)).set_ontstaan("python", 1991)
    assert SenseEngine(ConceptStore(pad, log)).get_ontstaan("python")["jaar"] == 1991


# ---------- detect_temporal ----------
@pytest.mark.parametrize("zin,woord,jaar", [
    ("python bestaat sinds 1991", "python", 1991),
    ("Python bestaat al sinds 1991", "python", 1991),
    ("machine learning ontstond in 1959", "machine learning", 1959),
    ("het zwart gat is ontstaan in 1971", "zwart gat", 1971),
])
def test_leerzinnen_herkend(opstelling, zin, woord, jaar):
    bus, sem, router = opstelling
    bus.gepubliceerd.clear()
    assert router.detect_temporal(zin) is True
    assert bus.events("intent_temporal_leer") == [{"word": woord, "jaar": jaar}]


@pytest.mark.parametrize("zin,woord,vorm", [
    ("wanneer ontstond python", "python", "wanneer"),
    ("wanneer is python ontstaan?", "python", "wanneer"),
    ("sinds wanneer bestaat de computer", "computer", "wanneer"),
    ("hoe lang bestaat python al", "python", "hoelang"),
    ("hoelang bestaat python al?", "python", "hoelang"),
])
def test_vragen_herkend(opstelling, zin, woord, vorm):
    bus, sem, router = opstelling
    bus.gepubliceerd.clear()
    assert router.detect_temporal(zin) is True
    assert bus.events("intent_temporal_query") == [{"word": woord, "vorm": vorm}]


@pytest.mark.parametrize("zin", [
    "ik bestaat sinds 1991",
    "wanneer is kerst",
    "wanneer is python geboren",
    "hoeveel dagen tot kerst",
    "python bestaat sinds 3000",
    "python bestaat sinds 0",
    "wat is python",
    "een heel lang onderwerp met veel woorden bestaat sinds 1991",
    "dat bestaat sinds 1991",
])
def test_geen_match(opstelling, zin):
    bus, sem, router = opstelling
    bus.gepubliceerd.clear()
    assert router.detect_temporal(zin) is False
    assert not bus.events("intent_temporal_leer")
    assert not bus.events("intent_temporal_query")


def test_topic_en_last_context_concept(opstelling):
    bus, sem, router = opstelling
    bus.gepubliceerd.clear()
    router.detect_temporal("python bestaat sinds 1991")
    assert any(n == "topic_detected:ontstaan" for n, _ in bus.gepubliceerd)


# ---------- eind-tot-eind via route() ----------
def test_route_leren_en_vragen(opstelling):
    bus, sem, router = opstelling
    assert "Genoteerd" in zeg(router, bus, "python bestaat sinds 1991")
    assert zeg(router, bus, "wanneer ontstond python") == "Python bestaat sinds 1991."


def test_route_hoelang(opstelling):
    bus, sem, router = opstelling
    zeg(router, bus, "python bestaat sinds 1991")
    verwacht = datetime.now().year - 1991
    assert f"al {verwacht} jaar" in zeg(router, bus, "hoe lang bestaat python al")


def test_route_onbekend_woord_legt_uit_hoe_te_leren(opstelling):
    bus, sem, router = opstelling
    antw = zeg(router, bus, "wanneer ontstond xyzwoord")
    assert "weet nog niet" in antw and "bestaat sinds" in antw


def test_route_aanpassen_meldt_oude_waarde(opstelling):
    bus, sem, router = opstelling
    zeg(router, bus, "python bestaat sinds 1990")
    assert "1990" in zeg(router, bus, "python bestaat sinds 1991")


def test_route_zelfde_jaar_opnieuw(opstelling):
    bus, sem, router = opstelling
    zeg(router, bus, "python bestaat sinds 1991")
    assert "al" in zeg(router, bus, "python bestaat sinds 1991")


def test_kerst_blijft_naar_holidays_gaan(opstelling):
    bus, sem, router = opstelling
    bus.gepubliceerd.clear()
    router.route({"text": "wanneer is kerst"})
    assert not bus.events("intent_temporal_query")