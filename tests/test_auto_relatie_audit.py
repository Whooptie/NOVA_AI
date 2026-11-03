# test_auto_relatie_audit.py
#
# Regressietests voor punt 60a (3 november 2026): relaties van automatische
# bronnen (auto_extract, wikipedia) lopen via ConceptStore.add_auto_relation()
# en laten voortaan een audit-regel achter, zoals RelationEngine.add_relation().
#
# Isolatie: alles in pytest's tmp_path, nooit de echte data/concepts.json.
# Uitvoeren: pytest tests/test_auto_relatie_audit.py -v

import pytest

from core.semantic import ConceptStore, SenseEngine, RelationEngine, TeachEngine


@pytest.fixture
def delen(tmp_path):
    store = ConceptStore(
        concepts_file=str(tmp_path / "concepts.json"),
        log_file=str(tmp_path / "concepts.jsonl"),
    )
    sense_engine = SenseEngine(store)
    relation_engine = RelationEngine(store, sense_engine)
    teach = TeachEngine(store, sense_engine)
    return store, sense_engine, relation_engine, teach


def _eerste_sense(store, woord):
    return store.get_concept(woord)["senses"][0]


def _relation_add_regels(store, woord):
    return [e for e in store.get_concept(woord).get("audit_log", [])
            if e.get("event_type") == "relation_add"]


def test_add_auto_relation_voegt_toe_en_schrijft_audit(delen):
    store, sense_engine, _, _ = delen
    sense_engine.add_sense("hond", "een huisdier", source="user")
    sense = _eerste_sense(store, "hond")
    rel = {"type": "is_a", "target": "dier", "confidence": 0.9,
           "source": "wikipedia", "status": "unverified", "created_at": "x"}

    assert store.add_auto_relation("hond", sense, rel) is True

    assert any(r["target"] == "dier" for r in sense["relations"])
    regels = _relation_add_regels(store, "hond")
    assert len(regels) == 1
    assert regels[0]["source"] == "wikipedia"
    assert regels[0]["relation"]["target"] == "dier"
    assert regels[0]["sense_id"] == sense["sense_id"]


def test_dubbel_doelwoord_wordt_overgeslagen_zonder_tweede_audit(delen):
    store, sense_engine, _, _ = delen
    sense_engine.add_sense("hond", "een huisdier", source="user")
    sense = _eerste_sense(store, "hond")
    rel = {"type": "is_a", "target": "dier", "source": "wikipedia",
           "status": "unverified"}

    assert store.add_auto_relation("hond", sense, dict(rel)) is True
    assert store.add_auto_relation("hond", sense, dict(rel)) is False

    assert len([r for r in sense["relations"] if r["target"] == "dier"]) == 1
    assert len(_relation_add_regels(store, "hond")) == 1


def test_afgewezen_doelwoord_komt_niet_terug(delen):
    store, sense_engine, relation_engine, _ = delen
    sense_engine.add_sense("hond", "een huisdier", source="user")
    relation_engine.add_relation("hond", "is_a", "meubel")
    sense = _eerste_sense(store, "hond")
    relation_engine.reject_relation("hond", sense["sense_id"], "is_a", "meubel")
    aantal_voor = len(_relation_add_regels(store, "hond"))

    rel = {"type": "is_a", "target": "meubel", "source": "wikipedia",
           "status": "unverified"}
    assert store.add_auto_relation("hond", sense, rel) is False

    assert len(_relation_add_regels(store, "hond")) == aantal_voor
    meubel = [r for r in sense["relations"] if r["target"] == "meubel"]
    assert len(meubel) == 1 and meubel[0]["status"] == "rejected"


def test_relatie_zonder_doelwoord_wordt_geweigerd(delen):
    store, sense_engine, _, _ = delen
    sense_engine.add_sense("hond", "een huisdier", source="user")
    sense = _eerste_sense(store, "hond")
    assert store.add_auto_relation("hond", sense, {"type": "is_a"}) is False
    assert _relation_add_regels(store, "hond") == []


def test_auto_extract_is_a_schrijft_nu_een_audit_regel(delen):
    store, sense_engine, _, teach = delen
    teach.teach("zeilboot", "Een zeilboot is een vaartuig dat wordt voortgestuwd door de wind.")

    sense = _eerste_sense(store, "zeilboot")
    auto = [r for r in sense["relations"] if r.get("source") == "auto_extract"]
    assert auto and auto[0]["target"] == "vaartuig"
    assert auto[0]["status"] == "unverified"

    regels = [e for e in _relation_add_regels(store, "zeilboot")
              if e["source"] == "auto_extract"]
    assert len(regels) == 1
    assert regels[0]["relation"]["target"] == "vaartuig"