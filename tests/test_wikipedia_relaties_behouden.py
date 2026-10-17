# tests/test_wikipedia_relaties_behouden.py -- een herhaalde "wiki X" mag
# bestaande relaties (bevestigd of opgeslagen via "neem N over") niet wissen
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.knowledge.wikipedia_teacher import WikipediaTeacher


class FakeStore:
    def __init__(self, concept):
        self.concept = concept
        self.saves = 0

    def get_concept(self, word):
        return self.concept

    def save(self):
        self.saves += 1


class FakeSemantic:
    def __init__(self, concept):
        self.store = FakeStore(concept)
        self._concept = concept

    def export_concept(self, word):
        return self._concept


class FakeBus:
    def __init__(self):
        self.modules = {}

    def subscribe(self, e, f):
        pass

    def publish(self, e, d=None):
        pass


def maak(relaties, status="unverified", examples=None):
    concept = {
        "metadata": {},
        "senses": [{
            "sense_id": "hond#1",
            "definition": "oud",
            "source": "wikipedia",
            "status": status,
            "relations": relaties,
            "examples": list(examples or []),
        }],
    }
    t = WikipediaTeacher(FakeBus(), FakeSemantic(concept))
    return t, concept["senses"][0]


def rel(typ, doel, status="confirmed"):
    return {"type": typ, "target": doel, "status": status, "source": "user"}


def test_bestaande_relaties_blijven_staan():
    t, sense = maak([rel("is_a", "zoogdier")])
    nieuw = [{"type": "is_a", "target": "gedomesticeerde", "confidence": 0.8}]
    res = t._teach_word("hond", "nieuwe tekst", nieuw)
    assert "bijgewerkt" in res
    doelen = [r["target"] for r in sense["relations"]]
    assert "zoogdier" in doelen
    assert "gedomesticeerde" in doelen
    assert sense["definition"] == "nieuwe tekst"


def test_geen_dubbele_relatie():
    t, sense = maak([rel("is_a", "Zoogdier")])
    nieuw = [{"type": "is_a", "target": "zoogdier", "confidence": 0.8}]
    t._teach_word("hond", "nieuwe tekst", nieuw)
    assert len(sense["relations"]) == 1
    assert sense["relations"][0]["status"] == "confirmed"


def test_zonder_nieuwe_relaties_blijft_alles():
    t, sense = maak([rel("is_a", "zoogdier")])
    t._teach_word("hond", "nieuwe tekst", [])
    assert len(sense["relations"]) == 1


def test_bevestigde_wikipedia_sense_blijft_onaangeroerd():
    t, sense = maak([rel("has_part", "snaar")], status="confirmed")
    sense["confidence"] = 1.0
    res = t._teach_word("gitaar", "nieuwe tekst", [{"type": "is_a", "target": "x"}])
    assert "bevestigd" in res and "bijgewerkt" not in res
    assert sense["definition"] == "oud"
    assert sense["status"] == "confirmed"
    assert sense["confidence"] == 1.0
    assert len(sense["relations"]) == 1


def test_eigen_voorbeeldzinnen_blijven_staan():
    t, sense = maak([], examples=["De hond blafte naar de postbode."])
    t._teach_word("hond", "nieuwe tekst", [], examples=["Wikipedia-zin.", "De hond blafte naar de postbode."])
    assert sense["examples"] == ["De hond blafte naar de postbode.", "Wikipedia-zin."]