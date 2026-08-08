# test_reasoning.py
#
# Echte pytest-test voor het resterende deel van de ReasoningEngine en
# RelationEngine in semantic.py, als aanvulling op test_tombstone.py
# (die zich beperkte tot part_of_chained() en de tombstone/status-
# filtering zelf). Dit bestand dekt:
#
#   - find_contradictions() -- de contradictiedetectie ZELF, i.p.v.
#     enkel de aanroeper (zie test_contradiction_checker.py, dat een
#     nep-semantic gebruikte en dus deze functie nooit echt aanriep)
#   - ReasoningEngine.is_a_chained(), causes_chained()
#   - RelationEngine.is_a() en de eenvoudige get_*()-shortcuts
#     (get_synonyms, get_antonyms, get_causes, get_instances,
#     get_properties, get_all_relations)
#
# Achtergrond (6-8 aug 2026): find_contradictions() bestond al langer
# en werkte, maar had geen enkele aanroeper -- pas met
# contradiction_checker.py kreeg de functie voor het eerst een
# gebruiker. Dit bestand test de functie ZELF rechtstreeks, zodat een
# toekomstige wijziging aan de contradictie-logica altijd meteen
# zichtbaar wordt, ongeacht of er op dat moment een aanroeper bestaat.
#
# Isolatie: zelfde patroon als test_tombstone.py -- ConceptStore met
# concepts_file in tmp_path, SenseEngine/RelationEngine/ReasoningEngine
# rechtstreeks aangesproken (geen SemanticConceptsModule/EventBus
# nodig, en geen risico op de echte data/concepts.json).
#
# Uitvoeren: pytest tests/test_reasoning.py -v

import pytest

from core.semantic import ConceptStore, SenseEngine, RelationEngine, ReasoningEngine


@pytest.fixture
def engines(tmp_path):
    store = ConceptStore(
        concepts_file=str(tmp_path / "concepts.json"),
        log_file=str(tmp_path / "concepts.jsonl"),
    )
    sense_engine = SenseEngine(store)
    relation_engine = RelationEngine(store, sense_engine)
    reasoning_engine = ReasoningEngine(store, relation_engine)
    return store, sense_engine, relation_engine, reasoning_engine


# ─────────────────────────────────────────────────────────────
# find_contradictions() -- de detectielogica zelf
# ─────────────────────────────────────────────────────────────

def test_find_contradictions_detecteert_conflict_binnen_groep(engines):
    """'hond' met zowel is_a 'dier' als is_a 'meubel' -- allebei in
    dezelfde INCOMPATIBLE_GROUP (dier/plant/meubel/...) -- hoort als
    conflict herkend te worden."""
    store, sense_engine, relation_engine, reasoning_engine = engines

    sense_engine.add_sense("hond", "huisdier", source="user")
    relation_engine.add_relation("hond", "is_a", "dier")
    relation_engine.add_relation("hond", "is_a", "meubel")

    conflicten = reasoning_engine.find_contradictions("hond")

    assert len(conflicten) == 1
    assert conflicten[0]["word"] == "hond"
    assert set(conflicten[0]["conflict"]) == {"dier", "meubel"}


def test_find_contradictions_geen_conflict_over_verschillende_groepen(engines):
    """'hond' is_a 'dier' EN is_a 'levend' -- 'dier' en 'levend' zitten
    in VERSCHILLENDE INCOMPATIBLE_GROUPS, dus dit is GEEN conflict
    (een dier is immers gewoon ook levend, dat is geen tegenstrijdigheid)."""
    store, sense_engine, relation_engine, reasoning_engine = engines

    sense_engine.add_sense("hond", "huisdier", source="user")
    relation_engine.add_relation("hond", "is_a", "dier")
    relation_engine.add_relation("hond", "is_a", "levend")

    conflicten = reasoning_engine.find_contradictions("hond")
    assert conflicten == []


def test_find_contradictions_geen_conflict_bij_1_categorie(engines):
    """Slechts 1 is_a-relatie binnen een groep is per definitie geen
    conflict -- er is niets om mee te botsen."""
    store, sense_engine, relation_engine, reasoning_engine = engines

    sense_engine.add_sense("hond", "huisdier", source="user")
    relation_engine.add_relation("hond", "is_a", "dier")

    assert reasoning_engine.find_contradictions("hond") == []


def test_find_contradictions_negeert_rejected_relatie(engines):
    """
    Bevestigt hetzelfde tombstone-gedrag als test_tombstone.py, maar
    nu specifiek voor find_contradictions() zelf: een weerlegde is_a-
    relatie mag geen conflict meer triggeren, want find_contradictions()
    gebruikt get_relations() (dat rejected al filtert) om de parents
    op te halen.
    """
    store, sense_engine, relation_engine, reasoning_engine = engines

    sense_engine.add_sense("hond", "huisdier", source="user")
    relation_engine.add_relation("hond", "is_a", "dier")
    relation_engine.add_relation("hond", "is_a", "meubel")

    # Bevestig eerst dat het conflict er is
    assert len(reasoning_engine.find_contradictions("hond")) == 1

    # Weerleg de foute relatie
    hond_sense = sense_engine.get_senses("hond")[0]
    relation_engine.reject_relation("hond", hond_sense["sense_id"], "is_a", "meubel")

    conflicten = reasoning_engine.find_contradictions("hond")
    assert conflicten == [], (
        "Een weerlegde is_a-relatie triggerde nog steeds een conflict -- "
        "find_contradictions() respecteert de tombstone niet correct."
    )


def test_find_contradictions_drie_categorieen_tegelijk(engines):
    """Bij 3 conflicterende categorieën tegelijk (dier + meubel +
    voertuig) hoort 'conflict' alle drie te bevatten, niet slechts 2."""
    store, sense_engine, relation_engine, reasoning_engine = engines

    sense_engine.add_sense("ding", "onduidelijk object", source="user")
    relation_engine.add_relation("ding", "is_a", "dier")
    relation_engine.add_relation("ding", "is_a", "meubel")
    relation_engine.add_relation("ding", "is_a", "voertuig")

    conflicten = reasoning_engine.find_contradictions("ding")
    assert len(conflicten) == 1
    assert set(conflicten[0]["conflict"]) == {"dier", "meubel", "voertuig"}


def test_find_contradictions_meerdere_groepen_apart_gemeld(engines):
    """Als een woord conflicten heeft in TWEE verschillende
    INCOMPATIBLE_GROUPS tegelijk (bv. dier+meubel EN levend+niet-levend),
    hoort elke groep als APART conflict-item in de resultatenlijst te staan."""
    store, sense_engine, relation_engine, reasoning_engine = engines

    sense_engine.add_sense("ding", "onduidelijk object", source="user")
    relation_engine.add_relation("ding", "is_a", "dier")
    relation_engine.add_relation("ding", "is_a", "meubel")
    relation_engine.add_relation("ding", "is_a", "levend")
    relation_engine.add_relation("ding", "is_a", "niet-levend")

    conflicten = reasoning_engine.find_contradictions("ding")
    assert len(conflicten) == 2

    alle_conflict_sets = [set(c["conflict"]) for c in conflicten]
    assert {"dier", "meubel"} in alle_conflict_sets
    assert {"levend", "niet-levend"} in alle_conflict_sets


# ─────────────────────────────────────────────────────────────
# is_a() (RelationEngine) -- eenvoudige directe check
# ─────────────────────────────────────────────────────────────

def test_is_a_true_bij_directe_relatie(engines):
    store, sense_engine, relation_engine, reasoning_engine = engines
    sense_engine.add_sense("hond", "huisdier", source="user")
    relation_engine.add_relation("hond", "is_a", "dier")

    assert relation_engine.is_a("hond", "dier") is True


def test_is_a_false_zonder_relatie(engines):
    store, sense_engine, relation_engine, reasoning_engine = engines
    sense_engine.add_sense("hond", "huisdier", source="user")

    assert relation_engine.is_a("hond", "plant") is False


def test_is_a_negeert_hoofdletters_en_spaties(engines):
    """is_a() doet .lower().strip() op beide argumenten."""
    store, sense_engine, relation_engine, reasoning_engine = engines
    sense_engine.add_sense("hond", "huisdier", source="user")
    relation_engine.add_relation("hond", "is_a", "dier")

    assert relation_engine.is_a("  Hond ", " DIER") is True


def test_is_a_false_bij_rejected_relatie(engines):
    store, sense_engine, relation_engine, reasoning_engine = engines
    sense_engine.add_sense("hond", "huisdier", source="user")
    relation_engine.add_relation("hond", "is_a", "meubel")

    hond_sense = sense_engine.get_senses("hond")[0]
    relation_engine.reject_relation("hond", hond_sense["sense_id"], "is_a", "meubel")

    assert relation_engine.is_a("hond", "meubel") is False


# ─────────────────────────────────────────────────────────────
# is_a_chained() -- niet gedekt door test_tombstone.py (die testte
# enkel part_of_chained). Zelfde ketenlogica, andere relatie-type.
# ─────────────────────────────────────────────────────────────

def test_is_a_chained_via_tussenstap(engines):
    """hond -> dier -> levend_wezen: is_a_chained('hond','levend_wezen')
    hoort True te zijn via de tussenstap 'dier'."""
    store, sense_engine, relation_engine, reasoning_engine = engines

    sense_engine.add_sense("hond", "huisdier", source="user")
    sense_engine.add_sense("dier", "levend wezen met zintuigen", source="user")
    relation_engine.add_relation("hond", "is_a", "dier")
    relation_engine.add_relation("dier", "is_a", "levend_wezen")

    gevonden, pad = reasoning_engine.is_a_chained("hond", "levend_wezen")
    assert gevonden is True
    assert pad == ["hond", "dier", "levend_wezen"]


def test_is_a_chained_zelfde_woord_is_altijd_true(engines):
    """is_a_chained('hond','hond') hoort triviaal True te zijn."""
    store, sense_engine, relation_engine, reasoning_engine = engines
    gevonden, pad = reasoning_engine.is_a_chained("hond", "hond")
    assert gevonden is True
    assert pad == ["hond"]


def test_is_a_chained_false_zonder_pad(engines):
    store, sense_engine, relation_engine, reasoning_engine = engines
    sense_engine.add_sense("hond", "huisdier", source="user")
    relation_engine.add_relation("hond", "is_a", "dier")

    gevonden, pad = reasoning_engine.is_a_chained("hond", "plant")
    assert gevonden is False
    assert pad == []


def test_is_a_chained_stopt_bij_cirkel(engines):
    """Een cirkelvormige is_a-relatie (a is_a b, b is_a a) mag
    is_a_chained() niet in een oneindige lus laten hangen -- de
    _visited-set moet dit voorkomen."""
    store, sense_engine, relation_engine, reasoning_engine = engines

    sense_engine.add_sense("a", "concept a", source="user")
    sense_engine.add_sense("b", "concept b", source="user")
    relation_engine.add_relation("a", "is_a", "b")
    relation_engine.add_relation("b", "is_a", "a")

    # Mag niet crashen/hangen, en 'c' bestaat nergens in de cirkel
    gevonden, pad = reasoning_engine.is_a_chained("a", "c")
    assert gevonden is False


def test_is_a_chained_respecteert_rejected_tussenstap(engines):
    """Als de TUSSENSTAP van een keten weerlegd is, hoort de keten
    niet langer te kloppen -- zelfde soort scenario als
    test_part_of_chained_na_weerlegging_is_false in test_tombstone.py,
    nu voor is_a_chained()."""
    store, sense_engine, relation_engine, reasoning_engine = engines

    sense_engine.add_sense("hond", "huisdier", source="user")
    sense_engine.add_sense("dier", "levend wezen", source="user")
    relation_engine.add_relation("hond", "is_a", "dier")
    relation_engine.add_relation("dier", "is_a", "levend_wezen")

    gevonden_voor, _ = reasoning_engine.is_a_chained("hond", "levend_wezen")
    assert gevonden_voor is True

    dier_sense = sense_engine.get_senses("dier")[0]
    relation_engine.reject_relation("dier", dier_sense["sense_id"], "is_a", "levend_wezen")

    gevonden_na, _ = reasoning_engine.is_a_chained("hond", "levend_wezen")
    assert gevonden_na is False


# ─────────────────────────────────────────────────────────────
# causes_chained() -- zelfde structuur als is_a_chained(), andere relatie
# ─────────────────────────────────────────────────────────────

def test_causes_chained_via_tussenstap(engines):
    """regen -> modder -> uitglijden: causes_chained('regen','uitglijden')
    hoort True te zijn via de tussenstap 'modder'."""
    store, sense_engine, relation_engine, reasoning_engine = engines

    sense_engine.add_sense("regen", "neerslag", source="user")
    sense_engine.add_sense("modder", "natte grond", source="user")
    relation_engine.add_relation("regen", "causes", "modder")
    relation_engine.add_relation("modder", "causes", "uitglijden")

    gevonden, pad = reasoning_engine.causes_chained("regen", "uitglijden")
    assert gevonden is True
    assert pad == ["regen", "modder", "uitglijden"]


def test_causes_chained_false_zonder_pad(engines):
    store, sense_engine, relation_engine, reasoning_engine = engines
    sense_engine.add_sense("regen", "neerslag", source="user")
    relation_engine.add_relation("regen", "causes", "modder")

    gevonden, pad = reasoning_engine.causes_chained("regen", "zonneschijn")
    assert gevonden is False
    assert pad == []


# ─────────────────────────────────────────────────────────────
# RelationEngine's eenvoudige get_*()-shortcuts
# ─────────────────────────────────────────────────────────────

def test_get_synonyms(engines):
    store, sense_engine, relation_engine, reasoning_engine = engines
    sense_engine.add_sense("blij", "gevoel van vreugde", source="user")
    relation_engine.add_relation("blij", "synonym", "vrolijk")
    relation_engine.add_relation("blij", "synonym", "gelukkig")

    assert set(relation_engine.get_synonyms("blij")) == {"vrolijk", "gelukkig"}


def test_get_antonyms(engines):
    store, sense_engine, relation_engine, reasoning_engine = engines
    sense_engine.add_sense("blij", "gevoel van vreugde", source="user")
    relation_engine.add_relation("blij", "antonym", "verdrietig")

    assert relation_engine.get_antonyms("blij") == ["verdrietig"]


def test_get_causes(engines):
    store, sense_engine, relation_engine, reasoning_engine = engines
    sense_engine.add_sense("regen", "neerslag", source="user")
    relation_engine.add_relation("regen", "causes", "modder")

    assert relation_engine.get_causes("regen") == ["modder"]


def test_get_instances(engines):
    store, sense_engine, relation_engine, reasoning_engine = engines
    sense_engine.add_sense("hond", "huisdier", source="user")
    relation_engine.add_relation("hond", "instance_of", "zoogdier")

    assert relation_engine.get_instances("hond") == ["zoogdier"]


def test_get_properties(engines):
    store, sense_engine, relation_engine, reasoning_engine = engines
    sense_engine.add_sense("vuur", "verbrandingsproces", source="user")
    relation_engine.add_relation("vuur", "property_of", "heet")

    assert relation_engine.get_properties("vuur") == ["heet"]


def test_get_all_relations_groepeert_per_type(engines):
    """get_all_relations() hoort alle relatietypes van een woord te
    groeperen in een dict, {relatietype: [targets]}."""
    store, sense_engine, relation_engine, reasoning_engine = engines
    sense_engine.add_sense("hond", "huisdier", source="user")
    relation_engine.add_relation("hond", "is_a", "dier")
    relation_engine.add_relation("hond", "synonym", "viervoeter")

    alle = relation_engine.get_all_relations("hond")
    assert alle["is_a"] == ["dier"]
    assert alle["synonym"] == ["viervoeter"]


def test_get_all_relations_negeert_rejected(engines):
    """get_all_relations() hoort rejected relaties EN rejected senses
    te negeren (zie de expliciete filter in de broncode, regel 828-832)."""
    store, sense_engine, relation_engine, reasoning_engine = engines
    sense_engine.add_sense("hond", "huisdier", source="user")
    relation_engine.add_relation("hond", "is_a", "dier")
    relation_engine.add_relation("hond", "is_a", "meubel")

    hond_sense = sense_engine.get_senses("hond")[0]
    relation_engine.reject_relation("hond", hond_sense["sense_id"], "is_a", "meubel")

    alle = relation_engine.get_all_relations("hond")
    assert alle["is_a"] == ["dier"]


def test_get_all_relations_leeg_dict_voor_onbekend_woord(engines):
    store, sense_engine, relation_engine, reasoning_engine = engines
    assert relation_engine.get_all_relations("nooitgezien") == {}