# tests/test_uncertainty_lijst.py -- Semantic Fase 10.2: onzekerheidslijst, keuzes en "waarom"
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.intent_router import IntentRouter
from modules.knowledge.uncertainty import Uncertainty


# ---------- nepdelen ----------
class FakeStore:
    def __init__(self, concepts):
        self.concepts = concepts

    def get_concept(self, w):
        return self.concepts.get(w)


class FakePQ:
    def __init__(self):
        self.open = False
        self.type = None

    def set(self, t, verval_seconden=60):
        self.open = True
        self.type = t

    def is_open(self):
        return self.open

    def clear(self):
        self.open = False


class FakeBus:
    def __init__(self):
        self.subs = {}
        self.out = []
        self.modules = {"pending_question": FakePQ()}

    def subscribe(self, e, f):
        self.subs.setdefault(e, []).append(f)

    def publish(self, e, d=None):
        self.out.append((e, d))
        for f in self.subs.get(e, []):
            f(d, e)

    def teksten(self):
        return [d["text"] for e, d in self.out if e in ("layer4_response", "chat_response")]


class FakeSem:
    def __init__(self, store):
        self.store = store

    def _vind(self, w, sid, t, tg):
        for s in self.store.get_concept(w)["senses"]:
            if s["sense_id"] == sid:
                for r in s["relations"]:
                    if r["type"] == t and r["target"] == tg:
                        return r
        return None

    def confirm_relation(self, w, sid, t, tg):
        r = self._vind(w, sid, t, tg)
        if r:
            r["status"] = "confirmed"
            r["confidence"] = 1.0
            r["source"] = "user"
        return r

    def reject_relation(self, w, sid, t, tg, reason=""):
        r = self._vind(w, sid, t, tg)
        if r:
            r["status"] = "rejected"
        return r


def rel(t, tg, conf, status, src):
    return {"type": t, "target": tg, "confidence": conf, "status": status, "source": src}


@pytest.fixture
def opzet():
    concepten = {
        "hond": {"senses": [{"sense_id": "hond#1", "status": "confirmed", "relations": [
            rel("is_a", "dier", 0.9, "confirmed", "user"),
            rel("is_a", "wolf", 0.8, "unverified", "wikipedia"),
            rel("is_a", "kat", 0.9, "rejected", "auto_extract")]}]},
        "fiets": {"senses": [{"sense_id": "fiets#1", "status": "confirmed", "relations": [
            rel("is_a", "voertuig", 0.8, "unverified", "wikipedia")]}]},
        "pitvrucht": {"senses": [{"sense_id": "pitvrucht#1", "status": "confirmed", "relations": [
            rel("is_a", "vrucht", 0.9, "unverified", "auto_extract"),
            rel("related_to", "boom", 0.3, "unverified", "auto")]}]},
        "wiel": {"senses": [{"sense_id": "wiel#1", "status": "confirmed", "relations": [
            rel("part_of", "auto", 1.0, "confirmed", "user")]}]},
        "leeg": {"senses": []},
    }
    bus = FakeBus()
    store = FakeStore(concepten)
    sem = FakeSem(store)
    Uncertainty(bus, sem)
    return bus, sem, store


def lijst(bus, woord=None):
    bus.publish("intent_uncertainty_list", {"word": woord})


def keuze(bus, actie, nummer):
    bus.publish("intent_uncertainty_keuze", {"actie": actie, "nummer": nummer})


# ---------- lijst ----------
def test_lijst_alles_onzekerste_eerst(opzet):
    bus, *_ = opzet
    lijst(bus)
    t = bus.teksten()[-1]
    regels = [r for r in t.split("\n") if r[:1].isdigit()]
    assert len(regels) == 3
    # laagste confidence eerst, bij gelijke confidence alfabetisch op woord
    assert "fiets is een voertuig" in regels[0]
    assert "hond is een wolf" in regels[1]
    assert "pitvrucht is een vrucht" in regels[2]
    # niet bevestigd en niet afgewezen, geen related_to, geen confirmed
    tekst_regels = "\n".join(regels)
    assert "is een kat" not in tekst_regels      # afgewezen
    assert "is een dier" not in tekst_regels     # bevestigd
    assert "boom" not in tekst_regels            # related_to hoort er niet bij
    assert "onderdeel" not in tekst_regels       # bevestigd part_of
    assert "3 onbevestigd" in t and "bevestig 3" in t


def test_lijst_per_woord(opzet):
    bus, *_ = opzet
    lijst(bus, "hond")
    t = bus.teksten()[-1]
    assert "over hond" in t and "hond is een wolf" in t and "fiets" not in t


def test_lijst_woord_zonder_onzekere_relaties(opzet):
    bus, *_ = opzet
    lijst(bus, "wiel")
    assert "geen onbevestigde relaties over wiel" in bus.teksten()[-1]


def test_lijst_onbekend_woord(opzet):
    bus, *_ = opzet
    lijst(bus, "xyz")
    assert "nog niets" in bus.teksten()[-1]


def test_lijst_maximaal_tien(opzet):
    bus, sem, store = opzet
    store.concepts["veel"] = {"senses": [{"sense_id": "v#1", "status": "confirmed", "relations": [
        rel("is_a", f"d{n}", 0.5, "unverified", "auto") for n in range(15)]}]}
    lijst(bus)
    t = bus.teksten()[-1]
    assert t.count("\n10. ") == 1 and "\n11. " not in t and "nog 8 meer" in t


# ---------- keuze ----------
def test_bevestig_nummer(opzet):
    bus, sem, store = opzet
    lijst(bus, "fiets")
    keuze(bus, "bevestig", 1)
    assert "Bevestigd" in bus.teksten()[-1]
    r = store.concepts["fiets"]["senses"][0]["relations"][0]
    assert r["status"] == "confirmed" and r["confidence"] == 1.0
    keuze(bus, "bevestig", 1)
    assert "al behandeld" in bus.teksten()[-1]


def test_wijs_af_nummer(opzet):
    bus, sem, store = opzet
    lijst(bus, "hond")
    keuze(bus, "wijs_af", 1)
    assert "Afgewezen" in bus.teksten()[-1]
    assert store.concepts["hond"]["senses"][0]["relations"][1]["status"] == "rejected"


def test_keuze_zonder_lijst(opzet):
    bus, *_ = opzet
    keuze(bus, "bevestig", 1)
    assert "Vraag eerst" in bus.teksten()[-1]


def test_keuze_buiten_bereik(opzet):
    bus, *_ = opzet
    lijst(bus, "hond")
    keuze(bus, "bevestig", 7)
    assert "staat niet in de lijst" in bus.teksten()[-1]


def test_lijst_verlopen(opzet, monkeypatch):
    bus, *_ = opzet
    lijst(bus, "hond")
    import modules.knowledge.uncertainty as u
    echte = u.time.time
    monkeypatch.setattr(u.time, "time", lambda: echte() + 601)
    keuze(bus, "bevestig", 1)
    assert "Vraag eerst" in bus.teksten()[-1]


def test_nummers_verschuiven_niet(opzet):
    bus, sem, store = opzet
    lijst(bus)
    keuze(bus, "bevestig", 1)
    keuze(bus, "bevestig", 2)
    assert bus.teksten()[-1].startswith("Bevestigd")
    keuze(bus, "bevestig", 1)
    assert "al behandeld" in bus.teksten()[-1]


# ---------- waarom ----------
def waarom(bus, t, s, tg):
    bus.publish("intent_uncertainty_why", {"relation_type": t, "source": s, "target": tg})


def test_waarom_onbevestigd(opzet):
    bus, *_ = opzet
    waarom(bus, "is_a", "hond", "wolf")
    t = bus.teksten()[-1]
    assert "niet helemaal zeker" in t and "Wikipedia" in t and "0.80" in t
    assert "geen gemeten kans" in t and "Typ 'ja'" in t
    assert bus.modules["pending_question"].type == "bevestig_relatie"


def test_waarom_bevestigd(opzet):
    bus, *_ = opzet
    waarom(bus, "part_of", "wiel", "auto")
    t = bus.teksten()[-1]
    assert "jij dit zelf hebt bevestigd" in t and "Typ" not in t


def test_waarom_bevestigd_met_oorspronkelijke_bron(opzet):
    bus, sem, store = opzet
    store.concepts["fiets"]["senses"][0]["relations"][0].update(
        {"status": "confirmed", "source": "user", "confidence": 1.0,
         "oorspronkelijke_bron": "wikipedia"})
    waarom(bus, "is_a", "fiets", "voertuig")
    assert "Oorspronkelijk kwam het van Wikipedia" in bus.teksten()[-1]


def test_waarom_afgewezen_en_onbekend(opzet):
    bus, *_ = opzet
    waarom(bus, "is_a", "hond", "kat")
    assert "afgewezen" in bus.teksten()[-1]
    waarom(bus, "is_a", "xyz", "abc")
    assert "weet ik niet" in bus.teksten()[-1]


def test_waarom_ja_bevestigt(opzet):
    bus, sem, store = opzet
    waarom(bus, "is_a", "fiets", "voertuig")
    bus.publish("pending_question:answered", {"vraag_type": "bevestig_relatie", "signaal": "bevestiging"})
    assert store.concepts["fiets"]["senses"][0]["relations"][0]["status"] == "confirmed"


# ---------- router ----------
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
    r._emit_topic = lambda *a, **k: None
    return r


def events(r):
    return [(e, d) for e, d in r.event_bus.ev]


@pytest.mark.parametrize("zin, woord", [
    ("wat weet je niet zeker?", None),
    ("Wat weet je niet zeker over hond", "hond"),
    ("welke dingen weet je niet zeker", None),
    ("wat is er onzeker over de fiets?", "fiets"),
    ("toon me onzekere kennis", None),
])
def test_router_lijst(router, zin, woord):
    assert router.detect_uncertainty_lijst(zin) is True
    assert events(router)[-1] == ("intent_uncertainty_list", {"word": woord})


@pytest.mark.parametrize("zin", ["wat weet je", "wat is een hond", "hoe laat is het", "wat weet je niet zeker over jij"])
def test_router_lijst_negatief(router, zin):
    assert router.detect_uncertainty_lijst(zin) is False


@pytest.mark.parametrize("zin, actie, nr", [
    ("bevestig 3", "bevestig", 3),
    ("Bevestig nummer 12", "bevestig", 12),
    ("wijs af 2", "wijs_af", 2),
])
def test_router_keuze(router, zin, actie, nr):
    assert router.detect_uncertainty_keuze(zin) is True
    assert events(router)[-1] == ("intent_uncertainty_keuze", {"actie": actie, "nummer": nr})


@pytest.mark.parametrize("zin", ["bevestig", "bevestig dit", "bevestig 123", "weerleg: hond is_a wolf"])
def test_router_keuze_negatief(router, zin):
    assert router.detect_uncertainty_keuze(zin) is False


def test_router_waarom(router):
    assert router.detect_uncertainty("waarom ben je er niet zeker van dat een hond een wolf is?") is True
    assert events(router)[-1] == ("intent_uncertainty_why",
                                  {"relation_type": "is_a", "source": "hond", "target": "wolf"})


def test_router_hoe_zeker_blijft_query(router):
    assert router.detect_uncertainty("hoe zeker ben je dat een hond een wolf is") is True
    assert events(router)[-1][0] == "intent_uncertainty_query"