# tests/test_uncertainty_keten.py -- Semantic Fase 10.3: zekerheid van een keten (zwakste schakel)
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

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


class FakeRE:
    MAX_DEPTH = 5


class FakeSem:
    def __init__(self, store):
        self.store = store
        self.reasoning_engine = FakeRE()

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


def rel(t, tg, conf, status, src):
    return {"type": t, "target": tg, "confidence": conf, "status": status, "source": src}


def concept(naam, *relaties):
    return {"senses": [{"sense_id": naam + "#1", "status": "confirmed", "relations": list(relaties)}]}


def maak(concepten):
    bus = FakeBus()
    store = FakeStore(concepten)
    sem = FakeSem(store)
    Uncertainty(bus, sem)
    return bus, sem, store


def vraag(bus, t, s, tg):
    bus.publish("intent_uncertainty_query", {"relation_type": t, "source": s, "target": tg})


@pytest.fixture
def puppy():
    return maak({
        "puppy": concept("puppy", rel("is_a", "hond", 0.9, "unverified", "auto_extract")),
        "hond": concept("hond", rel("is_a", "dier", 1.0, "confirmed", "user")),
        "dier": concept("dier"),
    })


# ---------- basis ----------
def test_keten_met_onbevestigde_schakel(puppy):
    bus, *_ = puppy
    vraag(bus, "is_a", "puppy", "dier")
    t = bus.teksten()[-1]
    assert "waarschijnlijk" in t and "zeker van" not in t
    assert "puppy -> hond -> dier" in t
    assert "zwakste schakel" in t
    assert "puppy is een hond" in t and "automatische afleiding" in t
    assert "zekerheid 0.90" in t
    assert "Wil je die schakel bevestigen?" in t


def test_keten_vraagt_naar_de_zwakste_schakel_en_niet_naar_de_keten(puppy):
    bus, *_ = puppy
    vraag(bus, "is_a", "puppy", "dier")
    pq = bus.modules["pending_question"]
    assert pq.type == "bevestig_relatie"


def test_ja_bevestigt_de_schakel_en_geeft_ketenupdate(puppy):
    bus, sem, store = puppy
    vraag(bus, "is_a", "puppy", "dier")
    bus.publish("pending_question:answered", {"vraag_type": "bevestig_relatie", "signaal": "bevestiging"})
    t = bus.teksten()[-1]
    assert "Bevestigd: puppy is een hond" in t
    assert "Alle schakels van de keten zijn nu bevestigd" in t
    assert "nu zeker" in t
    r = store.concepts["puppy"]["senses"][0]["relations"][0]
    assert r["status"] == "confirmed"
    vraag(bus, "is_a", "puppy", "dier")
    t = bus.teksten()[-1]
    assert "zeker van" in t and "Alle schakels heb jij zelf bevestigd" in t
    assert "Typ" not in t


def test_nee_laat_staan(puppy):
    bus, sem, store = puppy
    vraag(bus, "is_a", "puppy", "dier")
    bus.publish("pending_question:answered", {"vraag_type": "bevestig_relatie", "signaal": "ontkenning"})
    assert "weerleg: puppy is_a hond" in bus.teksten()[-1]
    assert store.concepts["puppy"]["senses"][0]["relations"][0]["status"] == "unverified"


def test_keten_volledig_bevestigd_is_zeker():
    bus, *_ = maak({
        "a": concept("a", rel("is_a", "b", 1.0, "confirmed", "user")),
        "b": concept("b", rel("is_a", "c", 1.0, "confirmed", "user")),
    })
    vraag(bus, "is_a", "a", "c")
    t = bus.teksten()[-1]
    assert "Ik ben er zeker van" in t and "Alle schakels heb jij zelf bevestigd" in t
    assert "Typ" not in t
    assert not bus.modules["pending_question"].open


# ---------- zwakste schakel en keuze van de keten ----------
def test_zwakste_schakel_is_de_laagste_onbevestigde():
    bus, *_ = maak({
        "a": concept("a", rel("is_a", "b", 0.9, "unverified", "auto_extract")),
        "b": concept("b", rel("is_a", "c", 0.8, "unverified", "wikipedia")),
        "c": concept("c", rel("is_a", "d", 1.0, "confirmed", "user")),
    })
    vraag(bus, "is_a", "a", "d")
    t = bus.teksten()[-1]
    assert "zekerheid 0.80" in t
    assert "De zwakste onbevestigde schakel is b is een c" in t
    # de vraag gaat over precies die schakel
    bus.publish("pending_question:answered", {"vraag_type": "bevestig_relatie", "signaal": "bevestiging"})
    t = bus.teksten()[-1]
    assert "Bevestigd: b is een c" in t
    assert "Zwakste onbevestigde schakel nu: a is een b" in t
    assert "zekerheid 0.90" in t


def test_kiest_de_zekerste_keten_niet_de_eerste():
    bus, *_ = maak({
        "a": concept("a",
                     rel("is_a", "b", 0.5, "unverified", "auto"),
                     rel("is_a", "c", 0.8, "unverified", "wikipedia")),
        "b": concept("b", rel("is_a", "d", 0.5, "unverified", "auto")),
        "c": concept("c", rel("is_a", "d", 0.9, "unverified", "auto_extract")),
    })
    vraag(bus, "is_a", "a", "d")
    t = bus.teksten()[-1]
    assert "a -> c -> d" in t and "zekerheid 0.80" in t


def test_bij_gelijke_score_wint_de_kortste():
    bus, *_ = maak({
        "a": concept("a",
                     rel("is_a", "x", 0.8, "unverified", "wikipedia"),
                     rel("is_a", "y", 0.8, "unverified", "wikipedia")),
        "x": concept("x", rel("is_a", "d", 0.8, "unverified", "wikipedia")),
        "y": concept("y", rel("is_a", "z", 0.8, "unverified", "wikipedia")),
        "z": concept("z", rel("is_a", "d", 0.8, "unverified", "wikipedia")),
    })
    vraag(bus, "is_a", "a", "d")
    assert "a -> x -> d" in bus.teksten()[-1]


def test_twijfelachtig_onder_de_drempel():
    bus, *_ = maak({
        "a": concept("a", rel("is_a", "b", 0.3, "unverified", "auto")),
        "b": concept("b", rel("is_a", "c", 0.9, "unverified", "wikipedia")),
    })
    vraag(bus, "is_a", "a", "c")
    t = bus.teksten()[-1]
    assert "twijfelachtig" in t and "zekerheid 0.30" in t


# ---------- randgevallen ----------
def test_cirkel_hangt_niet():
    bus, *_ = maak({
        "a": concept("a", rel("is_a", "b", 0.8, "unverified", "wikipedia")),
        "b": concept("b",
                     rel("is_a", "a", 0.8, "unverified", "wikipedia"),
                     rel("is_a", "c", 0.8, "unverified", "wikipedia")),
    })
    vraag(bus, "is_a", "a", "c")
    assert "a -> b -> c" in bus.teksten()[-1]


def test_afgewezen_schakel_telt_niet_mee():
    bus, *_ = maak({
        "a": concept("a", rel("is_a", "b", 0.9, "rejected", "auto_extract")),
        "b": concept("b", rel("is_a", "c", 1.0, "confirmed", "user")),
    })
    vraag(bus, "is_a", "a", "c")
    assert "weet ik niet" in bus.teksten()[-1]


def test_direct_afgewezen_gaat_voor_een_keten():
    bus, *_ = maak({
        "a": concept("a",
                     rel("is_a", "c", 0.9, "rejected", "auto_extract"),
                     rel("is_a", "b", 1.0, "confirmed", "user")),
        "b": concept("b", rel("is_a", "c", 1.0, "confirmed", "user")),
    })
    vraag(bus, "is_a", "a", "c")
    assert "afgewezen" in bus.teksten()[-1]


def test_diepte_wordt_gerespecteerd():
    ketens = {}
    namen = ["a", "b", "c", "d", "e", "f", "g"]
    for n, m in zip(namen, namen[1:]):
        ketens[n] = concept(n, rel("is_a", m, 1.0, "confirmed", "user"))
    ketens["g"] = concept("g")
    bus, *_ = maak(ketens)
    vraag(bus, "is_a", "a", "f")      # 5 schakels: net toegestaan
    assert "a -> b -> c -> d -> e -> f" in bus.teksten()[-1]
    vraag(bus, "is_a", "a", "g")      # 6 schakels: te diep
    assert "weet ik niet" in bus.teksten()[-1]


def test_open_pending_dan_geen_vraag_maar_wel_antwoord(puppy):
    bus, *_ = puppy
    bus.modules["pending_question"].open = True
    vraag(bus, "is_a", "puppy", "dier")
    t = bus.teksten()[-1]
    assert "puppy -> hond -> dier" in t and "Typ" not in t


def test_part_of_keten():
    bus, *_ = maak({
        "bout": concept("bout", rel("part_of", "wiel", 0.8, "unverified", "wikipedia")),
        "wiel": concept("wiel", rel("part_of", "auto", 1.0, "confirmed", "user")),
    })
    vraag(bus, "part_of", "bout", "auto")
    t = bus.teksten()[-1]
    assert "'bout' onderdeel is van 'auto'" in t and "bout -> wiel -> auto" in t
    assert "'bout' is onderdeel van 'wiel'" in t


def test_causes_keten():
    bus, *_ = maak({
        "roken": concept("roken", rel("causes", "longschade", 0.8, "unverified", "wikipedia")),
        "longschade": concept("longschade", rel("causes", "kanker", 0.9, "unverified", "auto_extract")),
    })
    vraag(bus, "causes", "roken", "kanker")
    t = bus.teksten()[-1]
    assert "'roken' tot 'kanker' leidt" in t and "roken veroorzaakt longschade" in t


def test_waarom_bij_een_keten(puppy):
    bus, *_ = puppy
    bus.publish("intent_uncertainty_why", {"relation_type": "is_a", "source": "puppy", "target": "dier"})
    t = bus.teksten()[-1]
    assert "zwakste schakel" in t and "puppy -> hond -> dier" in t


def test_andere_relatietypes_vormen_geen_keten():
    bus, *_ = maak({
        "a": concept("a", rel("is_a", "b", 1.0, "confirmed", "user")),
        "b": concept("b", rel("part_of", "c", 1.0, "confirmed", "user")),
    })
    vraag(bus, "is_a", "a", "c")
    assert "weet ik niet" in bus.teksten()[-1]