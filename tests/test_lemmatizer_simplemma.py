# tests/test_lemmatizer_simplemma.py
"""
Lemmatizer-herziening (3 oktober 2026, bug #32): simplemma + beschermings-
regels in word_associations_learner.py's lemmatize_nl().

Tests die de echte simplemma-data nodig hebben, worden overgeslagen als
simplemma niet geïnstalleerd is (pytest.importorskip). De terugval- en
beschermingstests werken altijd.

Isolatie: save_path naar tmp_path, geen event_bus.
"""
import pytest

from modules.learning import word_associations_learner as wa_module
from modules.learning.word_associations_learner import WordAssociationsLearner


class NepStore:
    def __init__(self, concepten):
        self.concepts = {c: {} for c in concepten}


class NepSemantic:
    def __init__(self, concepten):
        self.store = NepStore(concepten)

    def detect_sense(self, woord, context):
        return None


@pytest.fixture
def learner(tmp_path):
    return WordAssociationsLearner(event_bus=None, save_path=tmp_path / "wa.json")


# ---------------------------------------------------------------
# Met simplemma (echte data)
# ---------------------------------------------------------------
@pytest.mark.parametrize("woord, verwacht", [
    ("morgen", "morgen"),
    ("keuken", "keuken"),
    ("gisteren", "gisteren"),
    ("liefde", "liefde"),
    ("module", "module"),
    ("schaken", "schaken"),
    ("huizen", "huis"),
    ("kinderen", "kind"),
])
def test_bug32_fragmenten_zijn_weg(learner, woord, verwacht):
    pytest.importorskip("simplemma")
    assert learner.lemmatize_nl(woord) == verwacht


@pytest.mark.parametrize("woord", ["loop", "liep", "lopen"])
def test_loop_liep_lopen_komen_samen(learner, woord):
    pytest.importorskip("simplemma")
    assert learner.lemmatize_nl(woord) == "lopen"


@pytest.mark.parametrize("woord", ["vraag", "vragen"])
def test_vraag_vragen_komen_samen(learner, woord):
    pytest.importorskip("simplemma")
    assert learner.lemmatize_nl(woord) == "vragen"


def test_liggend_streepje_wordt_weggehaald(learner):
    pytest.importorskip("simplemma")
    assert "_" not in learner.lemmatize_nl("opgebouwd")


# ---------------------------------------------------------------
# Bescherming (werkt met of zonder simplemma)
# ---------------------------------------------------------------
@pytest.mark.parametrize("woord", ["nova", "data", "beter"])
def test_beschermde_woorden_blijven_ongewijzigd(learner, woord):
    assert learner.lemmatize_nl(woord) == woord


def test_bestaand_concept_blijft_ongewijzigd(learner):
    learner.semantic = NepSemantic(["kat", "fiets"])
    assert learner.lemmatize_nl("kat") == "kat"
    assert learner.lemmatize_nl("fiets") == "fiets"


def test_onregelmatig_werkwoord_gaat_voor_alles(learner):
    learner.semantic = NepSemantic(["liep"])
    assert learner.lemmatize_nl("liep") == "lopen"


def test_zonder_semantic_geen_crash(learner):
    learner.semantic = None
    assert isinstance(learner.lemmatize_nl("hond"), str)


# ---------------------------------------------------------------
# Terugval op de oude regels
# ---------------------------------------------------------------
def test_terugval_zonder_simplemma(learner):
    learner.gebruik_simplemma = False
    assert learner.lemmatize_nl("honden") == "hond"
    assert learner.lemmatize_nl("boekje") == "boek"
    assert learner.lemmatize_nl("snelle") == "snel"


def test_terugval_als_simplemma_crasht(learner, monkeypatch):
    class KapotteSimplemma:
        @staticmethod
        def lemmatize(woord, lang):
            raise RuntimeError("kapot")

    monkeypatch.setattr(wa_module, "simplemma", KapotteSimplemma())
    learner.gebruik_simplemma = True
    assert learner.lemmatize_nl("honden") == "hond"


# ---------------------------------------------------------------
# Stopwoorden
# ---------------------------------------------------------------
def test_nieuwe_stopwoorden_worden_gefilterd(learner):
    woorden = learner.filter_stopwords(
        learner.tokenize("hey hoeveel oké teach wiki onthoud pff koffie")
    )
    assert woorden == ["koffie"]


# ---------------------------------------------------------------
# Integratie: learn_from() slaat op onder de conceptnaam
# ---------------------------------------------------------------
def test_learn_from_bewaart_concept_onder_eigen_naam(learner):
    learner.semantic = NepSemantic(["kat"])
    learner.learn_from({
        "event_type": "chat_message",
        "data": {"text": "mijn kat slaapt de hele dag op de zetel"},
        "timestamp": 1,
    })
    assert "kat" in learner.word_stats