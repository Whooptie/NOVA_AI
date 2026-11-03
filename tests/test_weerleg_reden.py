# test_weerleg_reden.py
#
# Regressietests voor punt 60b (3 november 2026): 'weerleg ... reden: ...'
# geeft de reden door aan reject_concept / reject_sense / reject_relation,
# waar ze in het audit_log terechtkomt. Zonder 'reden:' blijft alles
# werken zoals voorheen.
#
# Isolatie: ConceptStore in pytest's tmp_path, nooit de echte
# data/concepts.json. De router praat met een kleine stub die de echte
# engines aanroept (zelfde namen als SemanticConceptsModule).
#
# Uitvoeren: pytest tests/test_weerleg_reden.py -v

import pytest

from core.semantic import ConceptStore, SenseEngine, RelationEngine
from core.intent_router import IntentRouter


class NepEventBus:
    def __init__(self):
        self.modules = {}
        self.gepubliceerd = []

    def subscribe(self, *a, **k):
        pass

    def publish(self, naam, data=None):
        self.gepubliceerd.append((naam, data))

    def antwoorden(self):
        return [d.get("text", "") for n, d in self.gepubliceerd if n == "chat_response"]


class SemanticStub:
    """Dezelfde methodenamen als SemanticConceptsModule, op echte engines."""

    def __init__(self, store, sense_engine, relation_engine):
        self.store = store
        self.sense_engine = sense_engine
        self.relation_engine = relation_engine

    def get_senses(self, woord):
        return self.sense_engine.get_senses(woord)

    def reject_sense(self, woord, sense_id, reason=""):
        return self.sense_engine.reject_sense(woord, sense_id, reason)

    def reject_concept(self, woord, reason=""):
        return self.sense_engine.reject_concept(woord, reason)

    def reject_relation(self, woord, sense_id, rel_type, target, reason=""):
        return self.relation_engine.reject_relation(woord, sense_id, rel_type, target, reason)


@pytest.fixture
def opstelling(tmp_path):
    store = ConceptStore(
        concepts_file=str(tmp_path / "concepts.json"),
        log_file=str(tmp_path / "concepts.jsonl"),
    )
    sense_engine = SenseEngine(store)
    relation_engine = RelationEngine(store, sense_engine)
    sense_engine.add_sense("hond", "een huisdier", source="user")
    relation_engine.add_relation("hond", "is_a", "meubel")
    bus = NepEventBus()
    router = IntentRouter(bus, semantic_module=SemanticStub(store, sense_engine, relation_engine))
    return store, router, bus


def _audit_tekst(store, woord):
    return str(store.get_concept(woord).get("audit_log", []))


# --- de hulpmethode zelf ---------------------------------------------------

def test_splits_reden_zonder_reden():
    assert IntentRouter._splits_reden("hond is_a meubel") == ("hond is_a meubel", "")


def test_splits_reden_met_reden():
    assert IntentRouter._splits_reden("hond is_a meubel reden: een hond is geen meubel") == \
        ("hond is_a meubel", "een hond is geen meubel")


def test_splits_reden_hoofdletters_en_spaties():
    assert IntentRouter._splits_reden("python 2 REDEN :  verkeerde slang") == ("python 2", "verkeerde slang")


# --- relatie ----------------------------------------------------------------

def test_weerleg_relatie_met_reden_bewaart_reden(opstelling):
    store, router, bus = opstelling
    assert router.handle_weerleg("weerleg: hond is_a meubel reden: een hond is geen meubelstuk") is True
    sense = store.get_concept("hond")["senses"][0]
    rel = [r for r in sense["relations"] if r["target"] == "meubel"][0]
    assert rel["status"] == "rejected"
    assert "een hond is geen meubelstuk" in _audit_tekst(store, "hond")
    assert any("Reden bewaard" in t for t in bus.antwoorden())


def test_weerleg_relatie_zonder_reden_werkt_als_voorheen(opstelling):
    store, router, bus = opstelling
    router.handle_weerleg("weerleg: hond is_a meubel")
    sense = store.get_concept("hond")["senses"][0]
    assert [r for r in sense["relations"] if r["target"] == "meubel"][0]["status"] == "rejected"
    assert not any("Reden bewaard" in t for t in bus.antwoorden())


# --- betekenis --------------------------------------------------------------

def test_weerleg_betekenis_met_reden(opstelling):
    store, router, bus = opstelling
    router.handle_weerleg("weerleg betekenis: hond 1 reden: onjuiste definitie")
    assert store.get_concept("hond")["senses"][0]["status"] == "rejected"
    assert "onjuiste definitie" in _audit_tekst(store, "hond")


def test_weerleg_betekenis_zonder_reden(opstelling):
    store, router, bus = opstelling
    router.handle_weerleg("weerleg betekenis: hond 1")
    assert store.get_concept("hond")["senses"][0]["status"] == "rejected"


# --- concept ----------------------------------------------------------------

def test_weerleg_concept_met_reden(opstelling):
    store, router, bus = opstelling
    router.handle_weerleg("weerleg concept: hond reden: verzonnen testwoord")
    assert store.get_concept("hond")["senses"][0]["status"] == "rejected"
    assert "verzonnen testwoord" in _audit_tekst(store, "hond")
    assert not any(t.startswith("Gebruik:") for t in bus.antwoorden())


def test_weerleg_concept_zonder_reden(opstelling):
    store, router, bus = opstelling
    router.handle_weerleg("weerleg concept: hond")
    assert store.get_concept("hond")["senses"][0]["status"] == "rejected"