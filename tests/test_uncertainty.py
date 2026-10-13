import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from modules.knowledge.uncertainty import Uncertainty


class FakeStore:
    def __init__(self, concepts):
        self.concepts = concepts
        self.saved = 0
    def get_concept(self, w):
        return self.concepts.get(w)
    def save(self):
        self.saved += 1


class FakePQ:
    def __init__(self): self.open = False; self.type = None
    def set(self, t, verval_seconden=60): self.open = True; self.type = t
    def is_open(self): return self.open
    def clear(self): self.open = False


class FakeBus:
    def __init__(self):
        self.subs = {}; self.out = []; self.modules = {"pending_question": FakePQ()}
    def subscribe(self, e, f): self.subs.setdefault(e, []).append(f)
    def publish(self, e, d=None):
        self.out.append((e, d))
        for f in self.subs.get(e, []): f(d, e)
    def teksten(self):
        return [d["text"] for e, d in self.out if e == "layer4_response"]


class FakeRE:
    def is_a_chained(self, a, b):
        return (True, [a, "hond", b]) if (a, b) == ("puppy", "dier") else (False, [])


class FakeSem:
    def __init__(self, store):
        self.store = store
        self.reasoning_engine = FakeRE()
    def confirm_relation(self, w, sid, t, tg):
        for s in self.store.get_concept(w)["senses"]:
            if s["sense_id"] == sid:
                for r in s["relations"]:
                    if r["type"] == t and r["target"] == tg:
                        r["status"] = "confirmed"; r["confidence"] = 1.0; r["source"] = "user"
                        return r
        return None


def rel(t, tg, conf, status, src):
    return {"type": t, "target": tg, "confidence": conf, "status": status, "source": src}


@pytest.fixture
def opzet():
    concepten = {
        "hond": {"senses": [{"sense_id": "s1", "status": "confirmed", "relations": [
            rel("is_a", "dier", 0.9, "unverified", "auto_extract"),
            rel("is_a", "kat", 0.9, "rejected", "auto_extract")]}]},
        "wiel": {"senses": [{"sense_id": "s1", "status": "confirmed", "relations": [
            rel("part_of", "auto", 1.0, "confirmed", "user")]}]},
        "puppy": {"senses": []},
    }
    bus = FakeBus(); store = FakeStore(concepten); sem = FakeSem(store)
    Uncertainty(bus, sem)
    return bus, sem, store


def vraag(bus, t, s, tg):
    bus.publish("intent_uncertainty_query", {"relation_type": t, "source": s, "target": tg})


def test_unverified_nooit_zeker_en_vraagt_bevestiging(opzet):
    bus, sem, store = opzet
    vraag(bus, "is_a", "hond", "dier")
    t = bus.teksten()[-1]
    assert "waarschijnlijk" in t and "zeker van" not in t
    assert "0.90" in t and "automatische afleiding" in t
    assert "Typ 'ja'" in t
    assert bus.modules["pending_question"].type == "bevestig_relatie"


def test_ja_bevestigt(opzet):
    bus, sem, store = opzet
    vraag(bus, "is_a", "hond", "dier")
    bus.publish("pending_question:answered", {"vraag_type": "bevestig_relatie", "signaal": "bevestiging"})
    assert "Bevestigd" in bus.teksten()[-1]
    r = store.concepts["hond"]["senses"][0]["relations"][0]
    assert r["status"] == "confirmed" and r["confidence"] == 1.0
    vraag(bus, "is_a", "hond", "dier")
    assert "Ik ben er zeker van" in bus.teksten()[-1]


def test_nee_laat_staan(opzet):
    bus, sem, store = opzet
    vraag(bus, "is_a", "hond", "dier")
    bus.publish("pending_question:answered", {"vraag_type": "bevestig_relatie", "signaal": "ontkenning"})
    assert "weerleg: hond is_a dier" in bus.teksten()[-1]
    assert store.concepts["hond"]["senses"][0]["relations"][0]["status"] == "unverified"


def test_andere_vraag_type_genegeerd(opzet):
    bus, sem, store = opzet
    vraag(bus, "is_a", "hond", "dier")
    n = len(bus.teksten())
    bus.publish("pending_question:answered", {"vraag_type": "iets_anders", "signaal": "bevestiging"})
    assert len(bus.teksten()) == n


def test_confirmed_geen_vraag(opzet):
    bus, *_ = opzet
    vraag(bus, "part_of", "wiel", "auto")
    t = bus.teksten()[-1]
    assert "zeker" in t and "zelf bevestigd" in t and "Typ" not in t
    assert not bus.modules["pending_question"].open


def test_keten(opzet):
    bus, *_ = opzet
    vraag(bus, "is_a", "puppy", "dier")
    assert "keten" in bus.teksten()[-1]


def test_afgewezen(opzet):
    bus, *_ = opzet
    vraag(bus, "is_a", "hond", "kat")
    assert "afgewezen" in bus.teksten()[-1]


def test_onbekend(opzet):
    bus, *_ = opzet
    vraag(bus, "is_a", "xyz", "abc")
    assert "weet ik niet" in bus.teksten()[-1]


def test_geen_vraag_als_pending_al_open(opzet):
    bus, *_ = opzet
    bus.modules["pending_question"].open = True
    vraag(bus, "is_a", "hond", "dier")
    assert "Typ" not in bus.teksten()[-1]


# ---------- meervoud en aanhalingstekens (10.1, vervolg) ----------
class FakeTeach:
    MAP = {"honden": "hond", "dieren": "dier", "wielen": "wiel", "auto's": "auto"}
    def _normalize_plural_if_noun(self, w, pos):
        return self.MAP.get(w, w)


def test_meervoud_wordt_enkelvoud(opzet):
    bus, sem, store = opzet
    sem.teach_engine = FakeTeach()
    vraag(bus, "is_a", "honden", "dieren")
    t = bus.teksten()[-1]
    assert "een hond een dier is" in t and "waarschijnlijk" in t


def test_meervoud_zonder_teach_engine_valt_terug(opzet):
    bus, *_ = opzet
    vraag(bus, "is_a", "honden", "dieren")
    assert "weet ik niet" in bus.teksten()[-1]


def test_part_of_met_aanhalingstekens(opzet):
    bus, *_ = opzet
    vraag(bus, "part_of", "wiel", "auto")
    assert "'wiel' onderdeel is van 'auto'" in bus.teksten()[-1]


def test_bevestigen_via_meervoud_werkt_op_enkelvoud(opzet):
    bus, sem, store = opzet
    sem.teach_engine = FakeTeach()
    vraag(bus, "is_a", "honden", "dieren")
    bus.publish("pending_question:answered", {"vraag_type": "bevestig_relatie", "signaal": "bevestiging"})
    assert store.concepts["hond"]["senses"][0]["relations"][0]["status"] == "confirmed"