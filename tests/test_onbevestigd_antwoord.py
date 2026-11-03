# test_onbevestigd_antwoord.py
#
# Regressietests voor punt 60c (3 november 2026): een "Ja"-antwoord van
# explain_is_a / explain_part_of / explain_causes zegt het erbij als (een
# deel van) het bewijs nog niet door Kevin is bevestigd. Antwoorden waarin
# alles bevestigd is blijven letterlijk hetzelfde.
#
# Isolatie: ConceptStore in pytest's tmp_path, nooit de echte
# data/concepts.json.
# Uitvoeren: pytest tests/test_onbevestigd_antwoord.py -v

import pytest

from core.semantic import ConceptStore, SenseEngine, RelationEngine, ReasoningEngine


@pytest.fixture
def delen(tmp_path):
    store = ConceptStore(
        concepts_file=str(tmp_path / "concepts.json"),
        log_file=str(tmp_path / "concepts.jsonl"),
    )
    sense_engine = SenseEngine(store)
    relation_engine = RelationEngine(store, sense_engine)
    reasoning = ReasoningEngine(store, relation_engine)
    for woord in ("hond", "zoogdier", "dier", "wiel", "auto", "regen", "modder", "groei"):
        sense_engine.add_sense(woord, f"definitie van {woord}", source="user")
    return store, relation_engine, reasoning


def _sense_id(store, woord):
    return store.get_concept(woord)["senses"][0]["sense_id"]


# --- is_a -------------------------------------------------------------------

def test_bevestigde_relatie_geeft_ongewijzigd_antwoord(delen):
    store, rel, reasoning = delen
    rel.add_relation("hond", "is_a", "dier", source="user", confidence=1.0)
    assert reasoning.explain_is_a("hond", "dier") == "Ja, een hond is een dier."


def test_onbevestigde_directe_relatie_krijgt_let_op(delen):
    store, rel, reasoning = delen
    rel.add_relation("hond", "is_a", "dier", source="auto_extract", confidence=0.9)
    antwoord = reasoning.explain_is_a("hond", "dier")
    assert antwoord.startswith("Ja, een hond is een dier.")
    assert "Let op: dat heb je nog niet bevestigd" in antwoord
    assert "een automatische afleiding uit een definitie" in antwoord


def test_wikipedia_als_bron_wordt_genoemd(delen):
    store, rel, reasoning = delen
    rel.add_relation("hond", "is_a", "dier", source="wikipedia", confidence=0.9)
    assert "Wikipedia" in reasoning.explain_is_a("hond", "dier")


def test_keten_met_een_onbevestigde_schakel(delen):
    store, rel, reasoning = delen
    rel.add_relation("hond", "is_a", "zoogdier", source="user")
    rel.add_relation("zoogdier", "is_a", "dier", source="wikipedia", confidence=0.9)
    antwoord = reasoning.explain_is_a("hond", "dier")
    assert "want: hond → zoogdier → dier." in antwoord
    assert "één schakel heb je nog niet bevestigd: zoogdier → dier (Wikipedia)" in antwoord
    assert "hond → zoogdier (" not in antwoord


def test_keten_met_twee_onbevestigde_schakels(delen):
    store, rel, reasoning = delen
    rel.add_relation("hond", "is_a", "zoogdier", source="auto_extract", confidence=0.9)
    rel.add_relation("zoogdier", "is_a", "dier", source="wikipedia", confidence=0.9)
    antwoord = reasoning.explain_is_a("hond", "dier")
    assert "2 schakels heb je nog niet bevestigd" in antwoord


def test_keten_volledig_bevestigd_blijft_ongewijzigd(delen):
    store, rel, reasoning = delen
    rel.add_relation("hond", "is_a", "zoogdier", source="user")
    rel.add_relation("zoogdier", "is_a", "dier", source="user")
    assert reasoning.explain_is_a("hond", "dier") == "Ja, een hond is een dier, want: hond → zoogdier → dier."


def test_na_bevestigen_verdwijnt_de_opmerking(delen):
    store, rel, reasoning = delen
    rel.add_relation("hond", "is_a", "dier", source="auto_extract", confidence=0.9)
    assert "Let op" in reasoning.explain_is_a("hond", "dier")
    assert rel.confirm_relation("hond", _sense_id(store, "hond"), "is_a", "dier")
    assert reasoning.explain_is_a("hond", "dier") == "Ja, een hond is een dier."


def test_negatief_antwoord_blijft_ongewijzigd(delen):
    store, rel, reasoning = delen
    rel.add_relation("hond", "is_a", "dier", source="auto_extract", confidence=0.9)
    assert "Let op" not in reasoning.explain_is_a("hond", "meubel")


# --- part_of ----------------------------------------------------------------

def test_part_of_onbevestigd(delen):
    store, rel, reasoning = delen
    rel.add_relation("wiel", "part_of", "auto", source="wikipedia", confidence=0.9)
    antwoord = reasoning.explain_part_of("wiel", "auto")
    assert antwoord.startswith("Ja, een wiel is onderdeel van auto.")
    assert "Let op: dat heb je nog niet bevestigd (Wikipedia)" in antwoord


def test_part_of_bevestigd_ongewijzigd(delen):
    store, rel, reasoning = delen
    rel.add_relation("wiel", "part_of", "auto", source="user")
    assert reasoning.explain_part_of("wiel", "auto") == "Ja, een wiel is onderdeel van auto."


# --- causes -----------------------------------------------------------------

def test_causes_direct_onbevestigd(delen):
    store, rel, reasoning = delen
    rel.add_relation("regen", "causes", "modder", source="auto", confidence=0.5)
    antwoord = reasoning.explain_causes("regen", "modder")
    assert antwoord.startswith("Ja, regen veroorzaakt modder.")
    assert "automatische gok" in antwoord


def test_causes_keten_onbevestigd(delen):
    store, rel, reasoning = delen
    rel.add_relation("regen", "causes", "modder", source="user")
    rel.add_relation("modder", "causes", "groei", source="wikipedia", confidence=0.9)
    antwoord = reasoning.explain_causes("regen", "groei")
    assert antwoord.startswith("Waarschijnlijk wel: regen leidt tot groei, via: regen → modder → groei.")
    assert "modder → groei (Wikipedia)" in antwoord


def test_causes_bevestigd_ongewijzigd(delen):
    store, rel, reasoning = delen
    rel.add_relation("regen", "causes", "modder", source="user")
    assert reasoning.explain_causes("regen", "modder") == "Ja, regen veroorzaakt modder."