# test_bugs_47_48_49.py
#
# Regressietests voor drie bugs uit nova_state.md (24 oktober 2026):
#   #47  weerleg-omweg via de "unknown"-placeholder (upgrade_unknown_sense)
#   #48  Wikipedia-refresh: weerleggingen/bevestigingen blijven, audit-entry
#   #49  valse bevestiging in RelationFlowEngine.handle_confirm()
#
# Isolatie: alles in pytest's tmp_path, nooit de echte data/concepts.json.
# Uitvoeren: pytest tests/test_bugs_47_48_49.py -v

import pytest

from core.semantic import (
    ConceptStore, SenseEngine, RelationEngine, TeachEngine, RelationFlowEngine,
)
from modules.knowledge.wikipedia_teacher import WikipediaTeacher


class FakeBus:
    def __init__(self):
        self.berichten = []

    def subscribe(self, *a, **k):
        pass

    def publish(self, naam, data=None):
        if naam == "chat_response":
            self.berichten.append(data["text"])


class SemanticStub:
    """Minimale vervanger voor SemanticConceptsModule: genoeg voor
    WikipediaTeacher._teach_word(), zonder EventBus of echte data."""
    def __init__(self, store, sense_engine):
        self.store = store
        self.sense_engine = sense_engine

    def export_concept(self, word):
        return self.store.export_concept(word)


@pytest.fixture
def delen(tmp_path):
    store = ConceptStore(
        concepts_file=str(tmp_path / "concepts.json"),
        log_file=str(tmp_path / "concepts.jsonl"),
    )
    sense_engine = SenseEngine(store)
    relation_engine = RelationEngine(store, sense_engine)
    teach_engine = TeachEngine(store, sense_engine)
    return store, sense_engine, relation_engine, teach_engine


def maak_weerlegde_sense_met_placeholder(sense_engine, woord="werk", tekst="arbeid die je doet",
                                         bron="user"):
    """Eerst een echte sense die Kevin weerlegt, DAARNA een unknown-
    placeholder (zoals auto_learn die aanmaakt)."""
    echte = sense_engine.add_sense(woord, tekst, source=bron)
    sense_engine.reject_sense(woord, echte["sense_id"], reason="test")
    placeholder = sense_engine.add_sense(woord, "unknown", source="auto", confidence=0.1)
    assert placeholder["definition"] == "unknown"
    return echte, placeholder


# ─────────────────────────────────────────────────────────────
# Bug #47
# ─────────────────────────────────────────────────────────────

def test_47_upgrade_unknown_sense_blokkeert_weerlegde_definitie(delen):
    store, sense_engine, _, _ = delen
    echte, placeholder = maak_weerlegde_sense_met_placeholder(sense_engine)

    resultaat = sense_engine.upgrade_unknown_sense("werk", "arbeid die je doet", source="user")

    assert isinstance(resultaat, dict) and resultaat.get("blocked") == "rejected"
    assert resultaat["sense"]["sense_id"] == echte["sense_id"]
    concept = store.export_concept("werk")
    placeholder_na = next(s for s in concept["senses"] if s["sense_id"] == placeholder["sense_id"])
    assert placeholder_na["definition"] == "unknown", "De placeholder mag niet zijn ingevuld."
    assert placeholder_na.get("status") != "confirmed"


def test_47_teach_geeft_blocked_door_en_vult_placeholder_niet(delen):
    store, sense_engine, _, teach_engine = delen
    echte, placeholder = maak_weerlegde_sense_met_placeholder(sense_engine)

    resultaat = teach_engine.teach("werk", "arbeid die je doet", source="user")

    assert isinstance(resultaat, dict) and resultaat.get("blocked") == "rejected"
    concept = store.export_concept("werk")
    assert not any(
        s.get("status") == "confirmed" and s.get("definition") == "arbeid die je doet"
        for s in concept["senses"]
    ), "REGRESSIE: de weerlegde definitie kwam terug als confirmed."


def test_47_andere_definitie_upgradet_placeholder_nog_gewoon(delen):
    """Controle: de fix blokkeert enkel dezelfde tekst, niet alles."""
    store, sense_engine, _, teach_engine = delen
    maak_weerlegde_sense_met_placeholder(sense_engine)

    resultaat = teach_engine.teach("werk", "een kunstwerk of product", source="user")

    assert resultaat.get("blocked") is None
    assert resultaat["definition"] == "een kunstwerk of product"
    assert resultaat["status"] == "confirmed"


def test_47_zonder_weerlegging_upgradet_placeholder_gewoon(delen):
    store, sense_engine, _, teach_engine = delen
    sense_engine.add_sense("boom", "unknown", source="auto", confidence=0.1)

    resultaat = teach_engine.teach("boom", "een grote plant met een stam", source="user")

    assert resultaat["definition"] == "een grote plant met een stam"
    assert resultaat["status"] == "confirmed"


def test_47_wikipedia_pad_meldt_en_slaat_niet_op(delen):
    store, sense_engine, _, _ = delen
    # Bron "auto": bij bron "user" of "wikipedia" grijpen in _teach_word()
    # eerder al andere guards in (een ander pad); met "auto" bereikt de
    # aanroep echt de upgrade-stap waar bug #47 zat.
    maak_weerlegde_sense_met_placeholder(sense_engine, bron="auto")
    teacher = WikipediaTeacher(FakeBus(), SemanticStub(store, sense_engine))

    bericht = teacher._teach_word("werk", "arbeid die je doet", [])

    assert "eerder al afgewezen" in bericht
    concept = store.export_concept("werk")
    assert not any(s.get("source") == "wikipedia" for s in concept["senses"])
    assert any(s["definition"] == "unknown" for s in concept["senses"])


# ─────────────────────────────────────────────────────────────
# Bug #49
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def flow(delen):
    store, sense_engine, relation_engine, _ = delen
    bus = FakeBus()
    engine = RelationFlowEngine(store, sense_engine, relation_engine, bus)
    sense = sense_engine.add_sense("hond", "huisdier", source="user")
    return engine, bus, relation_engine, sense, store


def vraag_ja(engine, sense, doel="dier"):
    engine.pending_relation = {
        "subject": "hond", "object": doel, "relation_type": "is_a",
        "subject_sense_id": sense["sense_id"], "object_sense_id": None,
        "state": "confirm",
    }
    engine.handle_confirm("ja")


def test_49_nieuwe_relatie_wordt_onthouden(flow):
    engine, bus, relation_engine, sense, _ = flow
    vraag_ja(engine, sense)
    assert bus.berichten[-1].startswith("Oké, ik onthoud")
    assert relation_engine.get_relations("hond", "is_a") == ["dier"]
    assert engine.pending_relation is None


def test_49_bestaande_relatie_geeft_eerlijke_melding(flow):
    engine, bus, relation_engine, sense, _ = flow
    relation_engine.add_relation("hond", "is_a", "dier", sense_id=sense["sense_id"])

    vraag_ja(engine, sense)

    assert "Oké, ik onthoud" not in bus.berichten[-1]
    assert "wist ik al" in bus.berichten[-1]
    assert relation_engine.get_relations("hond", "is_a") == ["dier"]
    assert engine.pending_relation is None


def test_49_weerlegde_relatie_wordt_eerlijk_gemeld_en_blijft_weerlegd(flow):
    engine, bus, relation_engine, sense, store = flow
    relation_engine.add_relation("hond", "is_a", "meubel", sense_id=sense["sense_id"])
    relation_engine.reject_relation("hond", sense["sense_id"], "is_a", "meubel")

    vraag_ja(engine, sense, doel="meubel")

    assert "Oké, ik onthoud" not in bus.berichten[-1]
    assert "afgewezen" in bus.berichten[-1]
    rel = store.export_concept("hond")["senses"][0]["relations"][0]
    assert rel["status"] == "rejected"


def test_49_onbekende_sense_geeft_mislukt_melding(flow):
    engine, bus, relation_engine, sense, _ = flow
    engine.pending_relation = {
        "subject": "hond", "object": "dier", "relation_type": "is_a",
        "subject_sense_id": "hond#99", "object_sense_id": None, "state": "confirm",
    }
    engine.handle_confirm("ja")
    assert "Oké, ik onthoud" not in bus.berichten[-1]
    assert "lukte niet" in bus.berichten[-1]


# ─────────────────────────────────────────────────────────────
# Bug #48
# ─────────────────────────────────────────────────────────────

def maak_wikipedia_sense(sense_engine, relation_engine, status="unverified"):
    sense = sense_engine.add_sense(
        "gitaar", "oude tekst over een gitaar", source="wikipedia", confidence=0.8
    )
    if status == "confirmed":
        sense["status"] = "confirmed"
    relation_engine.add_relation("gitaar", "is_a", "instrument", sense_id=sense["sense_id"],
                                 source="wikipedia", confidence=0.8)
    relation_engine.add_relation("gitaar", "is_a", "wapen", sense_id=sense["sense_id"],
                                 source="wikipedia", confidence=0.8)
    relation_engine.reject_relation("gitaar", sense["sense_id"], "is_a", "wapen")
    relation_engine.add_relation("gitaar", "part_of", "band", sense_id=sense["sense_id"],
                                 source="user", confidence=1.0)
    return sense


def nieuwe_relatie(doel, soort="is_a"):
    return {"type": soort, "target": doel, "confidence": 0.8,
            "source": "wikipedia", "status": "unverified"}


def test_48_refresh_behoudt_weerlegde_en_bevestigde_relaties(delen):
    store, sense_engine, relation_engine, _ = delen
    maak_wikipedia_sense(sense_engine, relation_engine)
    teacher = WikipediaTeacher(FakeBus(), SemanticStub(store, sense_engine))

    bericht = teacher._teach_word(
        "gitaar", "nieuwe tekst over een gitaar",
        [nieuwe_relatie("wapen"), nieuwe_relatie("instrument"), nieuwe_relatie("snaarinstrument")],
    )

    assert bericht.startswith("Wikipedia-definitie van 'gitaar' bijgewerkt")
    sense = store.export_concept("gitaar")["senses"][0]
    assert sense["definition"] == "nieuwe tekst over een gitaar"
    per_doel = {(r["type"], r["target"]): r for r in sense["relations"]}
    assert per_doel[("is_a", "wapen")]["status"] == "rejected", "weerlegde relatie moet weerlegd blijven"
    assert per_doel[("part_of", "band")]["status"] == "confirmed", "bevestigde relatie moet blijven"
    assert ("is_a", "snaarinstrument") in per_doel, "nieuwe relatie hoort erbij"
    assert len(sense["relations"]) == 4, "geen dubbele relaties"


def test_48_refresh_schrijft_audit_entry(delen):
    store, sense_engine, relation_engine, _ = delen
    maak_wikipedia_sense(sense_engine, relation_engine)
    teacher = WikipediaTeacher(FakeBus(), SemanticStub(store, sense_engine))

    teacher._teach_word("gitaar", "nieuwe tekst over een gitaar", [nieuwe_relatie("snaarinstrument")])

    log = store.export_concept("gitaar")["audit_log"]
    refresh = [e for e in log if e.get("event_type") == "wikipedia_refresh"]
    assert len(refresh) == 1
    assert refresh[0]["old_value"] == "oude tekst over een gitaar"
    assert refresh[0]["new_value"] == "nieuwe tekst over een gitaar"
    assert refresh[0]["nieuwe_relaties"] == ["is_a: snaarinstrument"]
    assert refresh[0]["source"] == "wikipedia"


def test_48_bevestigde_sense_blijft_onaangeroerd_en_geen_audit(delen):
    store, sense_engine, relation_engine, _ = delen
    maak_wikipedia_sense(sense_engine, relation_engine, status="confirmed")
    teacher = WikipediaTeacher(FakeBus(), SemanticStub(store, sense_engine))

    bericht = teacher._teach_word("gitaar", "nieuwe tekst over een gitaar", [nieuwe_relatie("x")])

    assert "bevestigd" in bericht
    concept = store.export_concept("gitaar")
    assert concept["senses"][0]["definition"] == "oude tekst over een gitaar"
    assert concept["senses"][0]["status"] == "confirmed"
    assert not any(e.get("event_type") == "wikipedia_refresh" for e in concept["audit_log"])


def test_48_weerlegde_wikipedia_sense_wordt_niet_aangeraakt(delen):
    store, sense_engine, relation_engine, _ = delen
    sense = maak_wikipedia_sense(sense_engine, relation_engine)
    sense_engine.reject_sense("gitaar", sense["sense_id"], reason="test")
    teacher = WikipediaTeacher(FakeBus(), SemanticStub(store, sense_engine))

    bericht = teacher._teach_word("gitaar", "nieuwe tekst over een gitaar", [])

    assert "afgewezen" in bericht
    concept = store.export_concept("gitaar")
    assert concept["senses"][0]["definition"] == "oude tekst over een gitaar"
    assert not any(e.get("event_type") == "wikipedia_refresh" for e in concept["audit_log"])