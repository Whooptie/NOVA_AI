"""
Tests voor embedding_specialist.py.

We testen GEDRAG (cache, rejected negeren, veilig falen, labels) met een
nepmodel -- niet de exacte scores van een echt ML-model. Daardoor draaien
deze tests overal, ook zonder sentence-transformers of internet.
"""

import numpy as np
import pytest

from modules.knowledge.embedding_specialist import (
    EmbeddingSpecialist, concept_tekst, init_module,
)


class NepModel:
    """Maakt van elke tekst een vector op basis van een paar kernwoorden."""
    KERN = ["hond", "kat", "auto"]

    def __init__(self):
        self.aantal_teksten = 0

    def encode(self, teksten):
        self.aantal_teksten += len(teksten)
        return np.array([[1.0 if k in t.lower() else 0.0 for k in self.KERN] + [0.1]
                         for t in teksten])


def sense(definitie, status="confirmed"):
    return {"definition": definitie, "status": status, "relations": []}


@pytest.fixture
def concepten():
    return {
        "hond": {"senses": [sense("een hond is een huisdier")]},
        "puppy": {"senses": [sense("een jonge hond")]},
        "kat": {"senses": [sense("een kat is een huisdier")]},
        "auto": {"senses": [sense("een auto heeft vier wielen")]},
        "leeg": {"senses": []},
    }


def maak(concepten, tmp_path, model=None):
    return EmbeddingSpecialist(
        model=model or NepModel(), concepten=concepten,
        cache_pad=tmp_path / "cache.npz", models_map=tmp_path / "models",
    )


def test_concept_tekst_negeert_rejected_en_lege():
    c = {"senses": [sense("goed"), sense("fout", status="rejected")]}
    assert concept_tekst("x", c) == "x: goed"
    assert concept_tekst("x", {"senses": [sense("fout", "rejected")]}) is None
    assert concept_tekst("x", None) is None


def test_find_similar_rangschikt_en_labelt(concepten, tmp_path):
    s = maak(concepten, tmp_path)
    res = s.find_similar("hond", top_k=3)
    assert res[0]["woord"] == "puppy"
    assert all(r["bron"] == "embedding" for r in res)
    assert all("model" in r for r in res)
    assert "hond" not in [r["woord"] for r in res]   # nooit zichzelf
    assert "leeg" not in [r["woord"] for r in res]   # zonder definitie


def test_onbekend_woord_geeft_lege_lijst(concepten, tmp_path):
    assert maak(concepten, tmp_path).find_similar("bestaatniet") == []


def test_cache_wordt_hergebruikt(concepten, tmp_path):
    m1 = NepModel()
    maak(concepten, tmp_path, m1).find_similar("hond")
    assert m1.aantal_teksten == 4            # vier concepten met definitie

    m2 = NepModel()                          # nieuwe instantie, zelfde cache
    maak(concepten, tmp_path, m2).find_similar("hond")
    assert m2.aantal_teksten == 0            # niets opnieuw berekend


def test_gewijzigde_definitie_wordt_opnieuw_berekend(concepten, tmp_path):
    m1 = NepModel()
    maak(concepten, tmp_path, m1).find_similar("hond")
    concepten["kat"]["senses"][0]["definition"] = "een kat jaagt op muizen"
    m2 = NepModel()
    maak(concepten, tmp_path, m2).find_similar("hond")
    assert m2.aantal_teksten == 1            # alleen 'kat'


def test_kapotte_cache_crasht_niet(concepten, tmp_path):
    (tmp_path / "cache.npz").write_bytes(b"geen echte npz")
    assert maak(concepten, tmp_path).find_similar("hond")


def test_model_faalt_dan_module_uit(concepten, tmp_path):
    class Kapot:
        def encode(self, teksten):
            raise RuntimeError("boem")
    s = maak(concepten, tmp_path, Kapot())
    assert s.find_similar("hond") == []
    assert s.reden_uit and "encode" in s.reden_uit
    assert s.is_beschikbaar() is False


def test_zonder_sentence_transformers_veilig_uit(concepten, tmp_path, monkeypatch):
    import importlib.util
    echt = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util, "find_spec",
        lambda naam, *a, **k: None if naam == "sentence_transformers" else echt(naam, *a, **k),
    )
    s = EmbeddingSpecialist(concepten=concepten, cache_pad=tmp_path / "c.npz")
    assert s.reden_uit and "sentence-transformers" in s.reden_uit
    assert s.find_similar("hond") == []
    assert s.similarity("a", "b") is None


def test_similarity_tussen_teksten(concepten, tmp_path):
    s = maak(concepten, tmp_path)
    assert s.similarity("hond", "hond") == pytest.approx(1.0)
    assert s.similarity("hond", "auto") < s.similarity("hond", "hond")


def test_init_module(concepten):
    class Bus:
        def __init__(self):
            self.geregistreerd = {}
        def register_module(self, naam, inst):
            self.geregistreerd[naam] = inst

    bus = Bus()
    inst = init_module(bus, None)
    assert bus.geregistreerd["embedding_specialist"] is inst


def test_find_all_pairs_unieke_gesorteerde_paren(concepten, tmp_path):
    s = maak(concepten, tmp_path)
    paren = s.find_all_pairs(min_score=0.5)
    sleutels = [(p["woord_a"], p["woord_b"]) for p in paren]
    assert len(sleutels) == len(set(sleutels))               # elk paar 1x
    assert all(a < b for a, b in sleutels)                   # alfabetisch
    scores = [p["score"] for p in paren]
    assert scores == sorted(scores, reverse=True)
    assert ("hond", "puppy") in sleutels
    assert all(p["bron"] == "embedding" for p in paren)
    assert not any("leeg" in k for k in sleutels)            # zonder definitie


def test_find_all_pairs_module_uit(concepten, tmp_path):
    class Kapot:
        def encode(self, teksten):
            raise RuntimeError("boem")
    assert maak(concepten, tmp_path, Kapot()).find_all_pairs() == []