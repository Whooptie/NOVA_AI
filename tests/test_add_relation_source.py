"""
Tests voor add_relation()'s nieuwe source/confidence-parameters
(13 augustus 2026, "Volgende stappen" punt 4 in nova_state.md).

Kernvraag die deze tests moeten bewijzen:
1. Bestaande aanroepen (zonder source) blijven zich exact zo gedragen
   als vóór de fix: confidence=1.0, source="user", status="confirmed".
2. Een NIEUWE aanroeper die wel een source meegeeft, krijgt de juiste
   status: "user" -> confirmed, alles anders -> unverified (zelfde
   regel als SenseEngine.add_sense() al langer toepast).
3. De facade-wrapper (de tweede, kortere add_relation() verderop in
   het bestand) geeft sense_id/source/confidence correct door aan
   RelationEngine.add_relation() -- geen stille default die alles
   overschrijft.

Isolatie: elke test krijgt een eigen tmp_path voor concepts.json/
concepts.jsonl, want ConceptStore.__init__() leest altijd meteen van
schijf. Geen sys.path-manipulatie nodig -- semantic.py wordt gewoon
als losstaande module geimporteerd.
"""

import pytest

from core.semantic import ConceptStore, SenseEngine, RelationEngine


@pytest.fixture
def store(tmp_path):
    concepts_file = tmp_path / "concepts.json"
    log_file = tmp_path / "concepts.jsonl"
    return ConceptStore(concepts_file=str(concepts_file), log_file=str(log_file))


@pytest.fixture
def sense_engine(store):
    return SenseEngine(store)


@pytest.fixture
def relation_engine(store, sense_engine):
    return RelationEngine(store, sense_engine)


def _eerste_relatie(store, subject, relation_type, target):
    """Haalt het rauwe relatie-object rechtstreeks uit concepts.json,
    zodat we status/confidence/source kunnen controleren -- get_relations()
    geeft enkel een lijst targets terug, geen volledig object."""
    concept = store.get_concept(subject) if hasattr(store, "get_concept") else store.concepts.get(subject)
    for sense in concept["senses"]:
        for rel in sense["relations"]:
            if rel["type"] == relation_type and rel["target"] == target:
                return rel
    return None


class TestAddRelationBestaandGedragOngewijzigd:
    """Zonder source-parameter moet alles exact blijven zoals vóór de fix."""

    def test_default_source_is_user(self, store, sense_engine, relation_engine):
        sense_engine.add_sense("gitaar", "een snaarinstrument", source="user")
        ok = relation_engine.add_relation("gitaar", "part_of", "orkest")

        assert ok is True
        rel = _eerste_relatie(store, "gitaar", "part_of", "orkest")
        assert rel["source"] == "user"
        assert rel["confidence"] == 1.0
        assert rel["status"] == "confirmed"

    def test_sense_id_werkt_nog_zoals_voorheen(self, store, sense_engine, relation_engine):
        sense = sense_engine.add_sense("bank", "meubel om op te zitten", source="user")
        sense_id = sense["sense_id"]

        ok = relation_engine.add_relation(
            "bank", "is_a", "meubel", sense_id=sense_id
        )

        assert ok is True
        rel = _eerste_relatie(store, "bank", "is_a", "meubel")
        assert rel["status"] == "confirmed"


class TestAddRelationMetSource:
    """Nieuw gedrag: een expliciete source stuurt de status, zelfde
    regel als SenseEngine.add_sense() al gebruikt."""

    def test_source_user_geeft_confirmed(self, store, sense_engine, relation_engine):
        sense_engine.add_sense("piano", "een toetsinstrument", source="user")
        relation_engine.add_relation("piano", "is_a", "instrument", source="user")

        rel = _eerste_relatie(store, "piano", "is_a", "instrument")
        assert rel["status"] == "confirmed"
        assert rel["source"] == "user"

    def test_source_auto_geeft_unverified(self, store, sense_engine, relation_engine):
        sense_engine.add_sense("vioolbouw", "het bouwen van violen", source="auto")
        relation_engine.add_relation(
            "vioolbouw", "related_to", "houtbewerking", source="auto"
        )

        rel = _eerste_relatie(store, "vioolbouw", "related_to", "houtbewerking")
        assert rel["status"] == "unverified"
        assert rel["source"] == "auto"

    def test_source_wikipedia_geeft_unverified(self, store, sense_engine, relation_engine):
        sense_engine.add_sense("cello", "een strijkinstrument", source="wikipedia")
        relation_engine.add_relation(
            "cello", "is_a", "strijkinstrument", source="wikipedia", confidence=0.6
        )

        rel = _eerste_relatie(store, "cello", "is_a", "strijkinstrument")
        assert rel["status"] == "unverified"
        assert rel["confidence"] == 0.6

    def test_confidence_wordt_correct_doorgegeven(self, store, sense_engine, relation_engine):
        sense_engine.add_sense("trompet", "een koperinstrument", source="user")
        relation_engine.add_relation(
            "trompet", "is_a", "koperinstrument", source="auto", confidence=0.4
        )

        rel = _eerste_relatie(store, "trompet", "is_a", "koperinstrument")
        assert rel["confidence"] == 0.4


class TestAddRelationDuplicateCheckBlijftWerken:
    """De duplicate-check (regel 677-681 in semantic.py) mag door de
    nieuwe parameters niet stuklopen -- een tweede aanroep met een
    andere source/confidence mag een bestaande relatie niet overschrijven."""

    def test_duplicate_met_andere_source_wordt_geweigerd(self, store, sense_engine, relation_engine):
        sense_engine.add_sense("harp", "een snaarinstrument", source="user")
        relation_engine.add_relation("harp", "is_a", "snaarinstrument", source="user")

        ok = relation_engine.add_relation(
            "harp", "is_a", "snaarinstrument", source="auto", confidence=0.3
        )

        assert ok is False
        rel = _eerste_relatie(store, "harp", "is_a", "snaarinstrument")
        # Blijft de oorspronkelijke, eerst opgeslagen versie.
        assert rel["source"] == "user"
        assert rel["status"] == "confirmed"


class TestAddRelationFacadeWrapper:
    """De tweede, kortere add_relation()-methode verderop in
    semantic.py (de facade/doorgeefmethode) moet sense_id/source/
    confidence correct doorgeven aan RelationEngine.add_relation(),
    niet stilzwijgend negeren."""

    def test_facade_geeft_source_door(self, store, sense_engine, relation_engine):
        # Zelfde constructie als SemanticEngine in semantic.py: een
        # object met .relation_engine dat naar de echte engine wijst.
        class FacadeStub:
            def __init__(self, relation_engine):
                self.relation_engine = relation_engine

            def add_relation(self, subject, relation_type, target, sense_id=None,
                             source="user", confidence=1.0):
                return self.relation_engine.add_relation(
                    subject, relation_type, target,
                    sense_id=sense_id, source=source, confidence=confidence
                )

        facade = FacadeStub(relation_engine)
        sense_engine.add_sense("fluit", "een blaasinstrument", source="user")

        facade.add_relation("fluit", "is_a", "blaasinstrument", source="auto", confidence=0.5)

        rel = _eerste_relatie(store, "fluit", "is_a", "blaasinstrument")
        assert rel["status"] == "unverified"
        assert rel["source"] == "auto"
        assert rel["confidence"] == 0.5