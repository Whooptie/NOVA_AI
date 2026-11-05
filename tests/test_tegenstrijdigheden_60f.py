# test_tegenstrijdigheden_60f.py
#
# Regressietests voor punt 60f (3 november 2026): find_contradictions()
# kent nu een expliciet "type" per conflict en drie extra controles:
#   is_a_cirkel, geerfde_categorie (botsing via voorouders) en
#   synoniem_antoniem. contradiction_checker.py gebruikt dat type voor de
#   melding, de weerleg-suggestie en de spam-preventie-sleutel.
#
# Isolatie: ConceptStore in pytest's tmp_path en de checker met een
# tmp_path-state, nooit de echte data/ bestanden.
# Uitvoeren: pytest tests/test_tegenstrijdigheden_60f.py -v

import pytest

from core.semantic import ConceptStore, SenseEngine, RelationEngine, ReasoningEngine
from modules.knowledge.contradiction_checker import ContradictionChecker


@pytest.fixture
def delen(tmp_path):
    store = ConceptStore(
        concepts_file=str(tmp_path / "concepts.json"),
        log_file=str(tmp_path / "concepts.jsonl"),
    )
    sense_engine = SenseEngine(store)
    relation_engine = RelationEngine(store, sense_engine)
    reasoning = ReasoningEngine(store, relation_engine)
    return sense_engine, relation_engine, reasoning


def _woorden(sense_engine, *woorden):
    for w in woorden:
        sense_engine.add_sense(w, f"definitie van {w}", source="user")


def _types(conflicten):
    return [c["type"] for c in conflicten]


@pytest.fixture
def checker(tmp_path):
    class DummyEventBus:
        modules = {}

        def subscribe(self, *a, **k):
            pass

        def publish(self, *a, **k):
            pass

    c = ContradictionChecker(DummyEventBus(), semantic_module=None)
    c.project_root = tmp_path
    c.state_pad = tmp_path / "contradiction_state.json"
    return c


# --- type-veld op de oude conflicten ---------------------------------------

def test_categorie_conflict_heeft_type(delen):
    s, r, rs = delen
    _woorden(s, "hond", "dier", "meubel")
    r.add_relation("hond", "is_a", "dier")
    r.add_relation("hond", "is_a", "meubel")
    assert _types(rs.find_contradictions("hond")) == ["categorie"]


def test_part_of_cirkel_heeft_type(delen):
    s, r, rs = delen
    _woorden(s, "snaar", "gitaar")
    r.add_relation("snaar", "part_of", "gitaar")
    r.add_relation("gitaar", "part_of", "snaar")
    # Punt 68b: de cirkel wordt door het alfabetisch eerste woord gemeld.
    assert _types(rs.find_contradictions("gitaar")) == ["part_of_cirkel"]


# --- is_a-cirkels -----------------------------------------------------------

def test_is_a_cirkel_wordt_gevonden(delen):
    s, r, rs = delen
    _woorden(s, "hond", "dier")
    r.add_relation("hond", "is_a", "dier")
    r.add_relation("dier", "is_a", "hond")
    # Punt 68b: de cirkel wordt door het alfabetisch eerste woord gemeld ("dier").
    conflicten = rs.find_contradictions("dier")
    assert _types(conflicten) == ["is_a_cirkel"]
    assert sorted(conflicten[0]["conflict"]) == ["dier", "hond"]
    assert "dier → hond → dier" in conflicten[0]["reason"]
    assert rs.find_contradictions("hond") == []


def test_is_a_cirkel_via_langere_keten(delen):
    s, r, rs = delen
    _woorden(s, "a", "b", "c")
    r.add_relation("a", "is_a", "b")
    r.add_relation("b", "is_a", "c")
    r.add_relation("c", "is_a", "a")
    assert "is_a_cirkel" in _types(rs.find_contradictions("a"))


def test_gewone_is_a_keten_is_geen_cirkel(delen):
    s, r, rs = delen
    _woorden(s, "hond", "zoogdier", "dier")
    r.add_relation("hond", "is_a", "zoogdier")
    r.add_relation("zoogdier", "is_a", "dier")
    assert rs.find_contradictions("hond") == []


def test_is_a_cirkel_verdwijnt_na_weerleggen(delen):
    s, r, rs = delen
    _woorden(s, "hond", "dier")
    r.add_relation("hond", "is_a", "dier")
    r.add_relation("dier", "is_a", "hond")
    sense_id = s.get_senses("dier")[0]["sense_id"]
    r.reject_relation("dier", sense_id, "is_a", "hond")
    assert rs.find_contradictions("hond") == []


# --- botsing via voorouders -------------------------------------------------

def test_geerfde_botsing_wordt_gevonden(delen):
    s, r, rs = delen
    _woorden(s, "puppy", "hond", "dier", "plant")
    r.add_relation("puppy", "is_a", "hond")
    r.add_relation("hond", "is_a", "dier")
    r.add_relation("puppy", "is_a", "plant")
    conflicten = rs.find_contradictions("puppy")
    assert _types(conflicten) == ["geerfde_categorie"]
    c = conflicten[0]
    assert set(c["conflict"]) == {"dier", "plant"}
    # de DIRECTE relaties die weerlegd kunnen worden
    assert c["via"] == {"dier": "hond", "plant": "plant"} or c["via"] == {"plant": "plant", "dier": "hond"}


def test_directe_botsing_wordt_niet_dubbel_gemeld(delen):
    s, r, rs = delen
    _woorden(s, "hond", "dier", "meubel")
    r.add_relation("hond", "is_a", "dier")
    r.add_relation("hond", "is_a", "meubel")
    assert _types(rs.find_contradictions("hond")) == ["categorie"]


def test_geen_vals_alarm_binnen_een_keten(delen):
    s, r, rs = delen
    _woorden(s, "hond", "huisdier", "dier")
    r.add_relation("hond", "is_a", "dier")
    r.add_relation("hond", "is_a", "huisdier")
    r.add_relation("huisdier", "is_a", "dier")
    assert rs.find_contradictions("hond") == []


def test_dierklassen_via_voorouders(delen):
    s, r, rs = delen
    _woorden(s, "x", "y", "z", "vogel", "reptiel")
    r.add_relation("x", "is_a", "y")
    r.add_relation("y", "is_a", "vogel")
    r.add_relation("x", "is_a", "z")
    r.add_relation("z", "is_a", "reptiel")
    conflicten = rs.find_contradictions("x")
    assert _types(conflicten) == ["geerfde_categorie"]
    assert set(conflicten[0]["via"].values()) == {"y", "z"}


# --- synoniem en antoniem ---------------------------------------------------

def test_synoniem_en_antoniem_tegelijk(delen):
    s, r, rs = delen
    _woorden(s, "groot", "klein")
    r.add_relation("groot", "synonym", "klein")
    r.add_relation("groot", "antonym", "klein")
    conflicten = rs.find_contradictions("groot")
    assert _types(conflicten) == ["synoniem_antoniem"]
    assert conflicten[0]["conflict"] == ["klein"]


def test_synoniem_antoniem_wordt_maar_een_keer_gemeld(delen):
    s, r, rs = delen
    _woorden(s, "groot", "klein")
    for woord, ander in (("groot", "klein"), ("klein", "groot")):
        r.add_relation(woord, "synonym", ander)
        r.add_relation(woord, "antonym", ander)
    totaal = rs.find_contradictions("groot") + rs.find_contradictions("klein")
    assert _types(totaal) == ["synoniem_antoniem"]


def test_enkel_antoniem_is_geen_conflict(delen):
    s, r, rs = delen
    _woorden(s, "groot", "klein")
    r.add_relation("groot", "antonym", "klein")
    assert rs.find_contradictions("groot") == []


# --- contradiction_checker: melding, suggestie en sleutel -------------------

def test_melding_is_a_cirkel(checker):
    c = {"word": "hond", "type": "is_a_cirkel", "conflict": ["dier", "hond"]}
    kernzin, suggestie = checker._bouw_melding_regel(c)
    assert "andersom" in kernzin
    assert suggestie == "'weerleg: hond is_a dier'"


def test_melding_is_a_cirkel_zelfrelatie(checker):
    c = {"word": "hond", "type": "is_a_cirkel", "conflict": ["hond", "hond"]}
    kernzin, suggestie = checker._bouw_melding_regel(c)
    assert "zichzelf" in kernzin
    assert suggestie == "'weerleg: hond is_a hond'"


def test_melding_geerfde_categorie_noemt_de_directe_relaties(checker):
    c = {"word": "puppy", "type": "geerfde_categorie",
         "conflict": ["dier", "plant"], "via": {"dier": "hond", "plant": "plant"}}
    kernzin, suggestie = checker._bouw_melding_regel(c)
    assert "'dier' en 'plant'" in kernzin
    assert "'weerleg: puppy is_a hond'" in suggestie
    assert "'weerleg: puppy is_a plant'" in suggestie


def test_melding_synoniem_antoniem(checker):
    c = {"word": "groot", "type": "synoniem_antoniem", "conflict": ["klein"]}
    kernzin, suggestie = checker._bouw_melding_regel(c)
    assert "weerleg: groot synonym klein" in suggestie
    assert "weerleg: groot antonym klein" in suggestie


def test_oude_sleutels_blijven_gelijk(checker):
    zonder_type = {"word": "hond", "conflict": ["meubel", "dier"]}
    met_type = {"word": "hond", "type": "categorie", "conflict": ["meubel", "dier"]}
    assert checker._conflict_sleutel(zonder_type) == "hond::dier|meubel"
    assert checker._conflict_sleutel(met_type) == "hond::dier|meubel"
    part_of = {"word": "snaar", "type": "part_of_cirkel", "conflict": ["gitaar", "snaar"]}
    assert checker._conflict_sleutel(part_of) == "snaar::gitaar|snaar"


def test_is_a_en_part_of_cirkel_hebben_verschillende_sleutels(checker):
    is_a = {"word": "snaar", "type": "is_a_cirkel", "conflict": ["gitaar", "snaar"]}
    part_of = {"word": "snaar", "type": "part_of_cirkel", "conflict": ["gitaar", "snaar"]}
    assert checker._conflict_sleutel(is_a) != checker._conflict_sleutel(part_of)


def test_is_a_cirkel_wordt_niet_als_part_of_herkend(checker):
    c = {"word": "hond", "type": "is_a_cirkel", "conflict": ["dier", "hond"]}
    assert checker._is_part_of_cirkel(c) is False