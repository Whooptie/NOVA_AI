# tests/test_reasoning_engine_ideeen.py
"""
Pytest-suite voor de 6 ideeën uit reasoning_engine_ideeen_roadmap.md,
gebouwd en live getest op 8 augustus 2026:

1. get_all_parts             -- spiegelbeeld van get_all_subtypes
2. related_to_chained        -- keten-redenering voor related_to (BFS,
                                 kortste pad; MAX_DEPTH_RELATED = 4)
3. find_contradictions        -- uitgebreid met part_of-cirkeldetectie
   + contradiction_checker.py -- _bouw_melding_regel() toont het juiste
                                 relatietype (part_of vs is_a) in de
                                 weerleg:-suggestie
4. get_all_parts_with_property -- multi-hop combinatie (parts x property)
5. explain_is_a/explain_part_of/explain_related_to -- "waarom niet"-
   uitleg bij een negatief antwoord (_geen_bewijs_met_alternatief)
6. compare_concepts            -- vergelijking tussen 2 concepten

Isolatie: elke test bouwt zijn eigen ConceptStore op een tmp_path-
bestand, geen enkele test raakt de echte data/concepts.json aan.
ConceptStore accepteert concepts_file/log_file als parameter, dus geen
monkeypatch nodig voor die klasse. SenseEngine/RelationEngine/
ReasoningEngine doen geen I/O in __init__(), dus die kunnen gewoon
rechtstreeks aangemaakt worden.

ContradictionChecker.__init__() roept wel get_project_root(__file__)
aan (bepaalt project_root/state_pad buiten onze controle om) -- daar
wordt na het aanmaken van de instantie project_root/state_pad met
monkeypatch/direct overschrijven naar een tmp_path gestuurd, zodat ook
die klasse nooit de echte data/contradiction_state.json aanraakt.
"""

import json

import pytest

from core.semantic import (
    ConceptStore,
    SenseEngine,
    RelationEngine,
    ReasoningEngine,
)
from modules.knowledge.contradiction_checker import ContradictionChecker


# ---------------------------------------------------------------------
# Gedeelde fixtures
# ---------------------------------------------------------------------

@pytest.fixture
def store(tmp_path):
    """Lege ConceptStore, volledig geïsoleerd op tmp_path."""
    concepts_file = tmp_path / "concepts.json"
    log_file = tmp_path / "concepts.jsonl"
    return ConceptStore(concepts_file=str(concepts_file), log_file=str(log_file))


@pytest.fixture
def engines(store):
    """
    (sense_engine, relation_engine, reasoning_engine) op dezelfde,
    geïsoleerde store -- de standaard combinatie die elke test nodig
    heeft om concepten/relaties op te bouwen en te bevragen.
    """
    sense_engine = SenseEngine(store)
    relation_engine = RelationEngine(store, sense_engine)
    reasoning_engine = ReasoningEngine(store, relation_engine)
    return sense_engine, relation_engine, reasoning_engine


def _voeg_concept_toe(sense_engine, woord, definitie="testdefinitie"):
    """Kleine hulpfunctie: legt snel een concept + 1 sense aan."""
    sense_engine.add_sense(woord, definitie, source="user")


def _voeg_relatie_toe(relation_engine, sense_engine, woord, rel_type, target):
    """
    Kleine hulpfunctie: zorgt dat 'woord' bestaat (met minstens 1
    sense) en voegt dan de relatie toe aan de EERSTE sense.
    """
    senses = sense_engine.get_senses(woord)
    if not senses:
        _voeg_concept_toe(sense_engine, woord)
        senses = sense_engine.get_senses(woord)
    sense_id = senses[0]["sense_id"]
    relation_engine.add_relation(woord, rel_type, target, sense_id=sense_id)


# ---------------------------------------------------------------------
# Idee #1: get_all_parts
# ---------------------------------------------------------------------

class TestGetAllParts:
    def test_directe_parts(self, engines):
        sense_engine, relation_engine, reasoning_engine = engines
        _voeg_relatie_toe(relation_engine, sense_engine, "wiel", "part_of", "fiets")
        _voeg_relatie_toe(relation_engine, sense_engine, "zadel", "part_of", "fiets")

        resultaat = reasoning_engine.get_all_parts("fiets")

        assert set(resultaat) == {"wiel", "zadel"}

    def test_keten_van_parts(self, engines):
        """snaar -> gitaar -> orkest: get_all_parts(orkest) moet beide vinden."""
        sense_engine, relation_engine, reasoning_engine = engines
        _voeg_relatie_toe(relation_engine, sense_engine, "snaar", "part_of", "gitaar")
        _voeg_relatie_toe(relation_engine, sense_engine, "gitaar", "part_of", "orkest")

        resultaat = reasoning_engine.get_all_parts("orkest")

        assert set(resultaat) == {"snaar", "gitaar"}

    def test_geen_parts_geeft_lege_lijst(self, engines):
        sense_engine, relation_engine, reasoning_engine = engines
        _voeg_concept_toe(sense_engine, "hond")

        resultaat = reasoning_engine.get_all_parts("hond")

        assert resultaat == []

    def test_onbekend_woord_geeft_lege_lijst_geen_crash(self, engines):
        _, _, reasoning_engine = engines
        resultaat = reasoning_engine.get_all_parts("bestaat_niet")
        assert resultaat == []


# ---------------------------------------------------------------------
# Idee #2: related_to_chained (BFS, kortste pad, MAX_DEPTH_RELATED=4)
# ---------------------------------------------------------------------

class TestRelatedToChained:
    def test_directe_relatie(self, engines):
        sense_engine, relation_engine, reasoning_engine = engines
        _voeg_relatie_toe(relation_engine, sense_engine, "snaar", "related_to", "muziek")

        gevonden, pad = reasoning_engine.related_to_chained("snaar", "muziek")

        assert gevonden is True
        assert pad == ["snaar", "muziek"]

    def test_keten_via_tussenstap(self, engines):
        sense_engine, relation_engine, reasoning_engine = engines
        _voeg_relatie_toe(relation_engine, sense_engine, "potlood", "related_to", "boek")
        _voeg_relatie_toe(relation_engine, sense_engine, "boek", "related_to", "taal")

        gevonden, pad = reasoning_engine.related_to_chained("potlood", "taal")

        assert gevonden is True
        assert pad == ["potlood", "boek", "taal"]

    def test_kiest_kortste_pad_bij_meerdere_routes(self, engines):
        """
        Regressietest voor de BFS-fix (8 augustus 2026): als zowel een
        DIRECT pad als een langere omweg bestaan, moet het korte pad
        teruggegeven worden. Dit faalde met de oorspronkelijke
        depth-first implementatie als de omweg toevallig eerst in de
        relatielijst stond.
        """
        sense_engine, relation_engine, reasoning_engine = engines
        # Omweg EERST toevoegen, zodat een depth-first zoektocht die
        # als eerste zou tegenkomen (en dus fout zou aflopen).
        _voeg_relatie_toe(relation_engine, sense_engine, "snaar", "related_to", "trilling")
        _voeg_relatie_toe(relation_engine, sense_engine, "trilling", "related_to", "geluid")
        _voeg_relatie_toe(relation_engine, sense_engine, "geluid", "related_to", "muziek")
        # Nu pas het DIRECTE pad toevoegen.
        _voeg_relatie_toe(relation_engine, sense_engine, "snaar", "related_to", "muziek")

        gevonden, pad = reasoning_engine.related_to_chained("snaar", "muziek")

        assert gevonden is True
        assert pad == ["snaar", "muziek"], (
            f"Verwacht het KORTSTE pad ['snaar', 'muziek'], kreeg {pad}"
        )

    def test_respecteert_max_depth_related(self, engines):
        """
        MAX_DEPTH_RELATED = 4: een keten van 5 stappen mag niet
        gevonden worden.
        """
        sense_engine, relation_engine, reasoning_engine = engines
        keten = ["a", "b", "c", "d", "e", "f"]  # a->b->c->d->e->f = 5 stappen
        for bron, doel in zip(keten, keten[1:]):
            _voeg_relatie_toe(relation_engine, sense_engine, bron, "related_to", doel)

        gevonden, pad = reasoning_engine.related_to_chained("a", "f")

        assert gevonden is False
        assert pad == []

    def test_binnen_max_depth_related_wel_gevonden(self, engines):
        """4 stappen (de grens zelf) moet nog wel lukken."""
        sense_engine, relation_engine, reasoning_engine = engines
        keten = ["a", "b", "c", "d", "e"]  # a->b->c->d->e = 4 stappen
        for bron, doel in zip(keten, keten[1:]):
            _voeg_relatie_toe(relation_engine, sense_engine, bron, "related_to", doel)

        gevonden, pad = reasoning_engine.related_to_chained("a", "e")

        assert gevonden is True
        assert pad == ["a", "b", "c", "d", "e"]

    def test_geen_verband_geeft_false(self, engines):
        sense_engine, relation_engine, reasoning_engine = engines
        _voeg_concept_toe(sense_engine, "ei")
        _voeg_concept_toe(sense_engine, "server")

        gevonden, pad = reasoning_engine.related_to_chained("ei", "server")

        assert gevonden is False
        assert pad == []


# ---------------------------------------------------------------------
# Idee #5: "waarom niet"-uitleg bij een negatief antwoord
# ---------------------------------------------------------------------

class TestWaaromNietUitleg:
    def test_is_a_met_alternatief(self, engines):
        sense_engine, relation_engine, reasoning_engine = engines
        _voeg_relatie_toe(relation_engine, sense_engine, "hond", "is_a", "wolf")

        tekst = reasoning_engine.explain_is_a("hond", "meubel")

        assert "kan niet bewijzen" in tekst
        assert "wolf" in tekst, "Verwacht dat het alternatief (wolf) genoemd wordt"

    def test_is_a_zonder_alternatief_blijft_kaal(self, engines):
        sense_engine, relation_engine, reasoning_engine = engines
        _voeg_concept_toe(sense_engine, "xylofoon")

        tekst = reasoning_engine.explain_is_a("xylofoon", "dier")

        assert "kan niet bewijzen" in tekst
        assert "maar ik weet wel" not in tekst

    def test_part_of_met_alternatief(self, engines):
        sense_engine, relation_engine, reasoning_engine = engines
        _voeg_relatie_toe(relation_engine, sense_engine, "snaar", "part_of", "gitaar")

        tekst = reasoning_engine.explain_part_of("snaar", "huis")

        assert "gitaar" in tekst

    def test_related_to_met_alternatief(self, engines):
        sense_engine, relation_engine, reasoning_engine = engines
        _voeg_relatie_toe(relation_engine, sense_engine, "ei", "related_to", "kip")

        tekst = reasoning_engine.explain_related_to("ei", "server")

        assert "kip" in tekst

    def test_toont_enkel_eerste_alternatief_niet_alle(self, engines):
        """
        Kevin's expliciete keuze (8 augustus 2026): bij meerdere
        bekende is_a-relaties enkel de EERSTE/dichtstbijzijnde tonen,
        geen volledige opsomming.
        """
        sense_engine, relation_engine, reasoning_engine = engines
        _voeg_relatie_toe(relation_engine, sense_engine, "hond", "is_a", "wolf")
        _voeg_relatie_toe(relation_engine, sense_engine, "hond", "is_a", "zoogdier")
        _voeg_relatie_toe(relation_engine, sense_engine, "hond", "is_a", "huisdier")

        tekst = reasoning_engine.explain_is_a("hond", "meubel")

        # Enkel de eerste (wolf) hoort in de tekst te staan, niet
        # per se de andere twee -- geen opsomming.
        gevonden_alternatieven = sum(
            1 for w in ("wolf", "zoogdier", "huisdier") if w in tekst
        )
        assert gevonden_alternatieven == 1, (
            f"Verwacht precies 1 alternatief in de tekst, kreeg er {gevonden_alternatieven}: {tekst!r}"
        )


# ---------------------------------------------------------------------
# Idee #3: find_contradictions -- part_of-cirkeldetectie
# ---------------------------------------------------------------------

class TestPartOfContradictie:
    def test_geen_cirkel_geeft_geen_conflict(self, engines):
        sense_engine, relation_engine, reasoning_engine = engines
        _voeg_relatie_toe(relation_engine, sense_engine, "snaar", "part_of", "gitaar")

        conflicten = reasoning_engine.find_contradictions("snaar")

        assert conflicten == []

    def test_directe_cirkel_wordt_gevonden(self, engines):
        """snaar part_of gitaar, EN gitaar part_of snaar -- cirkel."""
        sense_engine, relation_engine, reasoning_engine = engines
        _voeg_relatie_toe(relation_engine, sense_engine, "snaar", "part_of", "gitaar")
        _voeg_relatie_toe(relation_engine, sense_engine, "gitaar", "part_of", "snaar")

        conflicten = reasoning_engine.find_contradictions("snaar")

        assert len(conflicten) == 1
        c = conflicten[0]
        assert c["word"] == "snaar"
        assert set(c["conflict"]) == {"gitaar", "snaar"}

    def test_indirecte_cirkel_via_keten_wordt_gevonden(self, engines):
        """a part_of b part_of c part_of a -- cirkel via 2 tussenstappen."""
        sense_engine, relation_engine, reasoning_engine = engines
        _voeg_relatie_toe(relation_engine, sense_engine, "a", "part_of", "b")
        _voeg_relatie_toe(relation_engine, sense_engine, "b", "part_of", "c")
        _voeg_relatie_toe(relation_engine, sense_engine, "c", "part_of", "a")

        conflicten = reasoning_engine.find_contradictions("a")

        assert len(conflicten) >= 1
        assert any("a" in c["conflict"] for c in conflicten)

    def test_bestaande_is_a_contradictie_blijft_werken(self, engines):
        """
        Regressietest: de OORSPRONKELIJKE is_a-contradictiecheck mag
        niet stukgegaan zijn door de part_of-uitbreiding.
        """
        sense_engine, relation_engine, reasoning_engine = engines
        _voeg_relatie_toe(relation_engine, sense_engine, "hond", "is_a", "dier")
        _voeg_relatie_toe(relation_engine, sense_engine, "hond", "is_a", "meubel")

        conflicten = reasoning_engine.find_contradictions("hond")

        assert len(conflicten) == 1
        assert set(conflicten[0]["conflict"]) == {"dier", "meubel"}

    def test_reject_relation_lost_cirkel_op(self, engines):
        """
        Een geweerlegde (rejected) part_of-relatie mag niet meer
        meetellen in de cirkeldetectie -- consistent met hoe
        get_relations() rejected relaties al overal negeert.
        """
        sense_engine, relation_engine, reasoning_engine = engines
        senses_snaar = sense_engine.get_senses("snaar") if sense_engine.get_senses("snaar") else None
        _voeg_relatie_toe(relation_engine, sense_engine, "snaar", "part_of", "gitaar")
        _voeg_relatie_toe(relation_engine, sense_engine, "gitaar", "part_of", "snaar")

        # Bevestig eerst dat de cirkel er is.
        assert len(reasoning_engine.find_contradictions("snaar")) == 1

        # Weerleg de foute relatie (gitaar part_of snaar).
        sense_id = sense_engine.get_senses("gitaar")[0]["sense_id"]
        relation_engine.reject_relation("gitaar", sense_id, "part_of", "snaar")

        conflicten_na_weerleg = reasoning_engine.find_contradictions("snaar")
        assert conflicten_na_weerleg == []


class TestContradictionCheckerMelding:
    """
    Test _bouw_melding_regel() (contradiction_checker.py): moet het
    JUISTE relatietype (part_of vs is_a) in de weerleg:-suggestie
    tonen. Regressietest voor de bug waarbij een part_of-cirkel altijd
    een (niet-werkende) 'weerleg: ... is_a ...'-suggestie kreeg.

    Gebruikt hetzelfde DummyEventBus-patroon als
    test_contradiction_checker.py, voor consistentie met de rest van
    de testsuite.
    """

    @pytest.fixture
    def checker(self, tmp_path):
        class DummyEventBus:
            def subscribe(self, *args, **kwargs):
                pass

            def publish(self, *args, **kwargs):
                pass

        checker = ContradictionChecker(DummyEventBus(), semantic_module=None)
        # project_root/state_pad hangen af van get_project_root(), wat
        # buiten onze controle ligt -- direct overschrijven naar
        # tmp_path zodat deze test nooit de echte
        # data/contradiction_state.json aanraakt of leest. Zelfde
        # aanpak als test_contradiction_checker.py's maak_checker-
        # fixture.
        checker.project_root = tmp_path
        checker.state_pad = tmp_path / "contradiction_state.json"
        return checker

    def test_part_of_cirkel_geeft_part_of_suggestie(self, checker):
        conflict = {"word": "snaar", "conflict": ["gitaar", "snaar"]}

        kernzin, suggestie = checker._bouw_melding_regel(conflict)

        assert "part_of" in suggestie
        assert "is_a" not in suggestie

    def test_is_a_conflict_geeft_is_a_suggestie(self, checker):
        conflict = {"word": "hond", "conflict": ["dier", "meubel"]}

        kernzin, suggestie = checker._bouw_melding_regel(conflict)

        assert "is_a" in suggestie
        assert "part_of" not in suggestie

    def test_is_part_of_cirkel_onderscheid(self, checker):
        part_of_conflict = {"word": "snaar", "conflict": ["gitaar", "snaar"]}
        is_a_conflict = {"word": "hond", "conflict": ["dier", "meubel"]}

        assert checker._is_part_of_cirkel(part_of_conflict) is True
        assert checker._is_part_of_cirkel(is_a_conflict) is False

    def test_bouw_melding_1_conflict_bevat_juiste_suggestie(self, checker):
        conflicten = [{"word": "snaar", "conflict": ["gitaar", "snaar"]}]

        tekst = checker._bouw_melding(conflicten)

        assert "weerleg: snaar part_of gitaar" in tekst

    def test_bouw_melding_meerdere_conflicten_gemengd(self, checker):
        """Mix van is_a- en part_of-conflicten in 1 melding."""
        conflicten = [
            {"word": "hond", "conflict": ["dier", "meubel"]},
            {"word": "snaar", "conflict": ["gitaar", "snaar"]},
        ]

        tekst = checker._bouw_melding(conflicten)

        assert "weerleg: hond is_a" in tekst
        assert "weerleg: snaar part_of gitaar" in tekst


# ---------------------------------------------------------------------
# Idee #6: compare_concepts
# ---------------------------------------------------------------------

class TestCompareConcepts:
    def test_gedeelde_is_a(self, engines):
        sense_engine, relation_engine, reasoning_engine = engines
        _voeg_relatie_toe(relation_engine, sense_engine, "hond", "is_a", "zoogdier")
        _voeg_relatie_toe(relation_engine, sense_engine, "kat", "is_a", "zoogdier")

        resultaat = reasoning_engine.compare_concepts("hond", "kat")

        assert "zoogdier" in resultaat["per_type"]["is_a"]["gedeeld"]

    def test_enkel_bij_een_van_beide(self, engines):
        sense_engine, relation_engine, reasoning_engine = engines
        _voeg_relatie_toe(relation_engine, sense_engine, "hond", "is_a", "wolf")
        _voeg_concept_toe(sense_engine, "huiskat")
        _voeg_relatie_toe(relation_engine, sense_engine, "huiskat", "is_a", "kat")

        resultaat = reasoning_engine.compare_concepts("hond", "huiskat")

        assert "wolf" in resultaat["per_type"]["is_a"]["enkel_a"]
        assert "kat" in resultaat["per_type"]["is_a"]["enkel_b"]
        assert resultaat["per_type"]["is_a"]["gedeeld"] == []

    def test_leeg_relatietype_wordt_weggelaten(self, engines):
        """
        Als BEIDE concepten niets hebben voor een relatietype, mag dat
        type niet in per_type verschijnen (voorkomt lege secties bij
        de huidige, nog dunne data -- Kevin's keuze 8 augustus 2026).
        """
        sense_engine, relation_engine, reasoning_engine = engines
        _voeg_concept_toe(sense_engine, "auto")
        _voeg_concept_toe(sense_engine, "fiets")
        _voeg_relatie_toe(relation_engine, sense_engine, "fiets", "is_a", "voertuig")

        resultaat = reasoning_engine.compare_concepts("auto", "fiets")

        # is_a mag er zijn (fiets heeft het), maar bv. "part_of" of
        # "causes" (waar geen van beide iets voor heeft) NIET.
        assert "part_of" not in resultaat["per_type"]
        assert "causes" not in resultaat["per_type"]

    def test_beide_leeg_geeft_lege_per_type(self, engines):
        sense_engine, relation_engine, reasoning_engine = engines
        _voeg_concept_toe(sense_engine, "auto")
        _voeg_concept_toe(sense_engine, "wolk")

        resultaat = reasoning_engine.compare_concepts("auto", "wolk")

        assert resultaat["per_type"] == {}


# ---------------------------------------------------------------------
# Idee #4: get_all_parts_with_property (multi-hop combinatie)
# ---------------------------------------------------------------------

class TestGetAllPartsWithProperty:
    def test_combinatie_vindt_juiste_onderdeel(self, engines):
        sense_engine, relation_engine, reasoning_engine = engines
        _voeg_relatie_toe(relation_engine, sense_engine, "mes", "part_of", "keuken")
        _voeg_relatie_toe(relation_engine, sense_engine, "pan", "part_of", "keuken")
        _voeg_relatie_toe(relation_engine, sense_engine, "mes", "property_of", "scherp")

        resultaat = reasoning_engine.get_all_parts_with_property("keuken", "scherp")

        assert resultaat == ["mes"]

    def test_geen_match_geeft_lege_lijst(self, engines):
        sense_engine, relation_engine, reasoning_engine = engines
        _voeg_relatie_toe(relation_engine, sense_engine, "mes", "part_of", "keuken")
        _voeg_relatie_toe(relation_engine, sense_engine, "mes", "property_of", "scherp")

        resultaat = reasoning_engine.get_all_parts_with_property("keuken", "zwaar")

        assert resultaat == []

    def test_werkt_ook_via_part_of_keten(self, engines):
        """
        get_all_parts_with_property moet ook onderdelen vinden die
        via een KETEN (niet enkel direct) part_of zijn, aangezien het
        intern get_all_parts() hergebruikt.
        """
        sense_engine, relation_engine, reasoning_engine = engines
        _voeg_relatie_toe(relation_engine, sense_engine, "oog", "part_of", "hoofd")
        _voeg_relatie_toe(relation_engine, sense_engine, "hoofd", "part_of", "lichaam")
        _voeg_relatie_toe(relation_engine, sense_engine, "oog", "property_of", "rond")

        resultaat = reasoning_engine.get_all_parts_with_property("lichaam", "rond")

        assert resultaat == ["oog"]

    def test_hoofdletterongevoelig_op_property_waarde(self, engines):
        sense_engine, relation_engine, reasoning_engine = engines
        _voeg_relatie_toe(relation_engine, sense_engine, "mes", "part_of", "keuken")
        _voeg_relatie_toe(relation_engine, sense_engine, "mes", "property_of", "scherp")

        resultaat = reasoning_engine.get_all_parts_with_property("keuken", "SCHERP")

        assert resultaat == ["mes"]