# tests/test_temporal_periodes.py -- Semantic Fase 9.2 (periodes en tijdlijn)
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


def zeg(router, bus, tekst):
    """Geeft het (laatste) antwoord: layer4_response of chat_response."""
    bus.gepubliceerd.clear()
    router.route({"text": tekst})
    antw = bus.events("layer4_response") + bus.events("chat_response")
    return antw[-1]["text"] if antw else None


# ---------- SenseEngine ----------
def test_periode_toevoegen_en_ophalen(engine):
    r = engine.add_periode("python", 1991, 2005, "niche")
    assert r["ok"] and r["periode"]["label"] == "niche"
    assert engine.get_periodes("python")[0]["van"] == 1991


def test_periodes_gesorteerd(engine):
    engine.add_periode("python", 2010, None, "dominant")
    engine.add_periode("python", 1991, 2005, "niche")
    assert [p["van"] for p in engine.get_periodes("python")] == [1991, 2010]


def test_get_periode_in_randen_inclusief(engine):
    engine.add_periode("python", 1991, 2005, "niche")
    assert engine.get_periode_in("python", 1991)["label"] == "niche"
    assert engine.get_periode_in("python", 2005)["label"] == "niche"
    assert engine.get_periode_in("python", 2006) is None
    assert engine.get_periode_in("python", 1990) is None


def test_open_periode_loopt_tot_nu(engine):
    engine.add_periode("python", 2010, None, "dominant")
    assert engine.get_periode_in("python", 2026)["label"] == "dominant"


def test_overlap_wordt_geweigerd(engine):
    engine.add_periode("python", 1991, 2005, "niche")
    r = engine.add_periode("python", 2003, 2010, "groeiend")
    assert r["conflict"]["label"] == "niche"
    assert len(engine.get_periodes("python")) == 1


def test_aangrenzend_zonder_overlap_mag(engine):
    engine.add_periode("python", 1991, 2005, "niche")
    assert engine.add_periode("python", 2006, 2009, "groeiend")["ok"]


def test_open_periode_botst_met_latere_periode(engine):
    engine.add_periode("python", 2010, None, "dominant")
    assert "conflict" in engine.add_periode("python", 2025, None, "verdwijnend")


def test_zelfde_periode_opnieuw_is_bestaat(engine):
    engine.add_periode("python", 1991, 2005, "niche")
    assert engine.add_periode("python", 1991, 2005, "Niche").get("bestaat")
    assert len(engine.get_periodes("python")) == 1


def test_open_periode_afsluiten(engine):
    engine.add_periode("python", 2010, None, "dominant")
    r = engine.add_periode("python", 2010, 2024, "dominant")
    assert r["gesloten"] and r["periode"]["tot"] == 2024
    assert len(engine.get_periodes("python")) == 1
    log = engine.store.get_concept("python")["audit_log"]
    assert any(e["event_type"] == "periode_closed" for e in log)


def test_periode_voor_ontstaan_geweigerd(engine):
    engine.set_ontstaan("python", 1991)
    r = engine.add_periode("python", 1980, 1990, "niche")
    assert r == {"voor_ontstaan": 1991}


def test_ongeldige_invoer(engine):
    assert "fout" in engine.add_periode("python", 2005, 1991, "niche")
    assert "fout" in engine.add_periode("python", 1991, 2005, "  ")


def test_periodes_en_ontstaan_op_dezelfde_sense(engine):
    engine.add_sense("python", "een programmeertaal")
    engine.set_ontstaan("python", 1991)
    engine.add_periode("python", 1991, 2005, "niche")
    senses = engine.get_senses("python")
    assert len(senses) == 1
    assert senses[0]["ontstaan"]["jaar"] == 1991 and senses[0]["periodes"]


def test_clear_periodes_laat_ontstaan_staan(engine):
    engine.set_ontstaan("python", 1991)
    engine.add_periode("python", 1991, 2005, "niche")
    assert engine.clear_periodes("python") == 1
    assert engine.get_periodes("python") == []
    assert engine.get_ontstaan("python")["jaar"] == 1991
    log = engine.store.get_concept("python")["audit_log"]
    assert any(e["event_type"] == "periodes_cleared" for e in log)


def test_clear_zonder_periodes(engine):
    assert engine.clear_periodes("nietbestaand") == 0


def test_afgewezen_sense_telt_niet_mee(engine):
    s = engine.add_sense("python", "een slang")
    engine.add_periode("python", 1991, 2005, "niche")
    s["status"] = "rejected"
    assert engine.get_periodes("python") == []


def test_persistentie(tmp_path):
    pad, log = str(tmp_path / "c.json"), str(tmp_path / "l.jsonl")
    SenseEngine(ConceptStore(pad, log)).add_periode("python", 1991, 2005, "niche")
    assert SenseEngine(ConceptStore(pad, log)).get_periode_in("python", 2000)["label"] == "niche"


# ---------- detect_temporal_periode ----------
@pytest.mark.parametrize("zin,woord,van,tot,label", [
    ("python was van 1991 tot 2005 een niche", "python", 1991, 2005, "een niche"),
    ("Python was tussen 1991 en 2005 niche", "python", 1991, 2005, "niche"),
    ("python is van 2010 tot nu dominant", "python", 2010, None, "dominant"),
    ("python is sinds 2010 dominant", "python", 2010, None, "dominant"),
    ("het zwart gat was van 1971 tot 1990 erg onbekend", "zwart gat", 1971, 1990, "erg onbekend"),
])
def test_periode_leerzinnen(opstelling, zin, woord, van, tot, label):
    bus, sem, router = opstelling
    bus.gepubliceerd.clear()
    assert router.detect_temporal(zin) is True
    assert bus.events("intent_temporal_periode_leer") == [
        {"word": woord, "van": van, "tot": tot, "label": label}]


@pytest.mark.parametrize("zin,event,data", [
    ("wat was python in 2003", "intent_temporal_periode_query", {"word": "python", "jaar": 2003}),
    ("wat was de computer in 1985?", "intent_temporal_periode_query", {"word": "computer", "jaar": 1985}),
    ("tijdlijn van python", "intent_temporal_tijdlijn", {"word": "python"}),
    ("geef me de tijdlijn van python", "intent_temporal_tijdlijn", {"word": "python"}),
    ("wis de periodes van python", "intent_temporal_periodes_wis", {"word": "python"}),
    ("verwijder de tijdlijn van python", "intent_temporal_periodes_wis", {"word": "python"}),
])
def test_periode_vragen_en_wissen(opstelling, zin, event, data):
    bus, sem, router = opstelling
    bus.gepubliceerd.clear()
    assert router.detect_temporal(zin) is True
    assert bus.events(event) == [data]


@pytest.mark.parametrize("zin", [
    "ik was van 1991 tot 2005 gelukkig",
    "python was van 2005 tot 1991 niche",
    "python was van 1991 tot 3000 niche",
    "python was van 1991 tot 2005",
    "python was van 1991 tot 2005 een heel erg lange omschrijving",
    "python is sinds 2010",
    "wat was ik in 2003",
    "wat was python in 3000",
    "wat was het weer gisteren",
    "dat was van 1991 tot 2005 niche",
])
def test_periode_geen_match(opstelling, zin):
    bus, sem, router = opstelling
    bus.gepubliceerd.clear()
    router.detect_temporal(zin)
    assert not bus.events("intent_temporal_periode_leer")
    assert not bus.events("intent_temporal_periode_query")


# ---------- eind-tot-eind via route() ----------
def test_route_leren_en_vragen(opstelling):
    bus, sem, router = opstelling
    assert zeg(router, bus, "python was van 1991 tot 2005 een niche") == \
        "Genoteerd: Python was van 1991 tot 2005 een niche."
    assert zeg(router, bus, "wat was python in 2003") == "In 2003 was Python een niche."


def test_route_open_periode_zin(opstelling):
    bus, sem, router = opstelling
    assert zeg(router, bus, "python is sinds 2010 dominant") == "Genoteerd: Python is sinds 2010 dominant."


def test_route_voor_ontstaan(opstelling):
    bus, sem, router = opstelling
    zeg(router, bus, "python bestaat sinds 1991")
    assert "nog niet" in zeg(router, bus, "wat was python in 1980")
    assert "1991" in zeg(router, bus, "wat was python in 1980")


def test_route_gat_in_de_tijdlijn(opstelling):
    bus, sem, router = opstelling
    zeg(router, bus, "python bestaat sinds 1991")
    zeg(router, bus, "python was van 1991 tot 2005 een niche")
    antw = zeg(router, bus, "wat was python in 2007")
    assert "weet niet" in antw and "1991" in antw


def test_route_onbekend_woord(opstelling):
    bus, sem, router = opstelling
    assert "weet niet" in zeg(router, bus, "wat was xyzwoord in 2003")


def test_route_conflict_met_uitweg(opstelling):
    bus, sem, router = opstelling
    zeg(router, bus, "python was van 1991 tot 2005 een niche")
    antw = zeg(router, bus, "python was van 2003 tot 2010 groeiend")
    assert "botst" in antw and "wis de periodes van python" in antw
    assert len(sem.get_periodes("python")) == 1


def test_route_voor_ontstaan_leren_geweigerd(opstelling):
    bus, sem, router = opstelling
    zeg(router, bus, "python bestaat sinds 1991")
    assert "kan niet" in zeg(router, bus, "python was van 1980 tot 1990 niche")


def test_route_afsluiten_open_periode(opstelling):
    bus, sem, router = opstelling
    zeg(router, bus, "python is sinds 2010 dominant")
    antw = zeg(router, bus, "python was van 2010 tot 2024 dominant")
    assert antw.startswith("Afgesloten")


def test_route_tijdlijn(opstelling):
    bus, sem, router = opstelling
    zeg(router, bus, "python bestaat sinds 1991")
    zeg(router, bus, "python was van 1991 tot 2005 een niche")
    zeg(router, bus, "python is sinds 2010 dominant")
    assert zeg(router, bus, "tijdlijn van python") == (
        "Tijdlijn van Python:\n- 1991: ontstaan\n- 1991-2005: een niche\n- sinds 2010: dominant")


def test_route_tijdlijn_leeg(opstelling):
    bus, sem, router = opstelling
    assert "nog geen tijdlijn" in zeg(router, bus, "tijdlijn van xyzwoord")


def test_route_wissen(opstelling):
    bus, sem, router = opstelling
    zeg(router, bus, "python bestaat sinds 1991")
    zeg(router, bus, "python was van 1991 tot 2005 een niche")
    assert "Gewist: 1 periode" in zeg(router, bus, "wis de periodes van python")
    assert "weet niet" in zeg(router, bus, "wat was python in 2000")
    assert "1991" in zeg(router, bus, "wanneer ontstond python")
    assert "geen periodes" in zeg(router, bus, "wis de periodes van python")


def test_ontstaan_9_1_blijft_werken(opstelling):
    bus, sem, router = opstelling
    assert "Genoteerd" in zeg(router, bus, "python bestaat sinds 1991")
    assert zeg(router, bus, "wanneer ontstond python") == "Python bestaat sinds 1991."