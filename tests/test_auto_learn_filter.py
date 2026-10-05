# tests/test_auto_learn_filter.py
"""
Auto-learn-filter (5 oktober 2026): welke woorden uit een fallback-zin
als "unknown"-concept in concepts.json mogen belanden, plus de gedeelde
stopwoordenlijst (core/nl_stopwoorden.py).

Isolatie: ResponsePipeline wordt aangemaakt ZONDER __init__ (die maakt
PersonalityEngine/EmotionEngine aan, die echte bestanden lezen). Enkel
.semantic wordt gezet, met een nep-semantic die bijhoudt wat er
geleerd wordt. Geen echte concepts.json wordt aangeraakt.
"""
import pytest

from core.nl_stopwoorden import STOPWOORDEN
from modules.chat import response_pipeline as rp_module
from modules.chat.response_pipeline import ResponsePipeline
from modules.learning.word_associations_learner import WordAssociationsLearner


class NepSenseEngine:
    WERKWOORDEN = {"lopen", "spelen"}

    def detect_pos(self, woord):
        return "verb" if woord in self.WERKWOORDEN else "noun"


class NepStore:
    def __init__(self, bekend=()):
        self.bekend = set(bekend)

    def has_concept(self, woord):
        return woord in self.bekend


class NepSemantic:
    def __init__(self, bekend=()):
        self.sense_engine = NepSenseEngine()
        self.store = NepStore(bekend)
        self.geleerd = []

    def auto_learn(self, woord):
        self.geleerd.append(woord)


def _pipeline(bekend=()):
    rp = object.__new__(ResponsePipeline)
    rp.semantic = NepSemantic(bekend)
    return rp


def test_functiewoorden_groeten_en_commandos_worden_niet_geleerd():
    rp = _pipeline()
    rp._auto_learn_from_sentence("wat hoe over hey hoeveel debug oké alweer omdat")
    assert rp.semantic.geleerd == []


def test_typfouten_worden_niet_geleerd():
    pytest.importorskip("simplemma")
    rp = _pipeline()
    rp._auto_learn_from_sentence("hyey emercence")
    assert rp.semantic.geleerd == []


def test_echt_naamwoord_wordt_wel_geleerd():
    rp = _pipeline()
    rp._auto_learn_from_sentence("mijn paraplu is stuk")
    assert "paraplu" in rp.semantic.geleerd
    assert "mijn" not in rp.semantic.geleerd


def test_bestandsnaam_en_koppelteken_nooit_letterlijk():
    rp = _pipeline()
    rp._auto_learn_from_sentence("type data\\layer0_gebruikt.jsonl, op mijn 21-jarige leeftijd")
    assert "data\\layer0_gebruikt.jsonl" not in rp.semantic.geleerd
    assert "21-jarige" not in rp.semantic.geleerd
    assert all(w.isalpha() for w in rp.semantic.geleerd)


def test_bestaand_concept_wordt_niet_opnieuw_geleerd():
    rp = _pipeline(bekend={"paraplu"})
    rp._auto_learn_from_sentence("mijn paraplu")
    assert rp.semantic.geleerd == []


def test_werkwoord_volgens_detect_pos_wordt_niet_geleerd():
    rp = _pipeline()
    rp._auto_learn_from_sentence("lopen spelen")
    assert rp.semantic.geleerd == []


def test_dubbel_woord_wordt_een_keer_geleerd():
    rp = _pipeline()
    rp._auto_learn_from_sentence("paraplu paraplu paraplu")
    assert rp.semantic.geleerd == ["paraplu"]


def test_zonder_simplemma_valt_enkel_de_woordenboekcontrole_weg(monkeypatch):
    monkeypatch.setattr(rp_module, "simplemma", None)
    rp = _pipeline()
    rp._auto_learn_from_sentence("hyey wat")
    assert rp.semantic.geleerd == ["hyey"]


def test_geen_semantic_geen_crash():
    rp = object.__new__(ResponsePipeline)
    rp.semantic = None
    rp._auto_learn_from_sentence("mijn paraplu")


def test_layer1_gebruikt_de_gedeelde_lijst(tmp_path):
    learner = WordAssociationsLearner(event_bus=None, save_path=tmp_path / "wa.json")
    assert STOPWOORDEN <= learner.stopwords


def test_beter_staat_niet_in_de_gedeelde_lijst():
    # "beter" is in Layer 1 een beschermd woord en moet daar meetellen;
    # het mag dus enkel in de auto-learn-extra-lijst staan.
    assert "beter" not in STOPWOORDEN
    assert "beter" in rp_module.AUTO_LEARN_EXTRA_STOPWOORDEN


# ---------------------------------------------------------------
# semantic.py -- de gedeelde lijst als centrale poort
# ---------------------------------------------------------------
def _tijdelijke_store(tmp_path):
    from core.semantic import ConceptStore
    return ConceptStore(
        concepts_file=str(tmp_path / "concepts.json"),
        log_file=str(tmp_path / "concepts.jsonl"),
    )


def test_detect_pos_ziet_stopwoord_als_functiewoord(tmp_path):
    from core.semantic import SenseEngine
    sense_engine = SenseEngine(_tijdelijke_store(tmp_path))
    assert sense_engine.detect_pos("hoeveel") == "function"
    assert sense_engine.detect_pos("teach") == "function"
    assert sense_engine.detect_pos("paraplu") == "noun"


def test_auto_learn_weigert_stopwoord_voor_elke_aanroeper(tmp_path):
    from core.semantic import SenseEngine, TeachEngine
    store = _tijdelijke_store(tmp_path)
    teach_engine = TeachEngine(store, SenseEngine(store))
    resultaat = teach_engine.auto_learn("teach")
    assert resultaat.get("geweigerd") is True
    assert not store.has_concept("teach")


def test_relation_parser_ziet_gedeeld_stopwoord_als_ruis():
    from core.semantic import RelationParser
    parser = RelationParser()
    assert parser.is_ruiswoord("hoeveel")
    assert parser.is_ruiswoord("wat")
    assert not parser.is_ruiswoord("paraplu")