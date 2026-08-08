# test_tombstone.py
#
# Echte pytest-test voor punt 26 van nova_state.md: bevestigt dat
# status == "rejected" (het tombstone-mechanisme in semantic.py)
# intact blijft -- zowel in de REASONING-laag (is_a_chained,
# part_of_chained, get_relations) als bij een POGING TOT RE-ASSERTIE
# (opnieuw dezelfde sense/relatie toevoegen na een weerlegging).
#
# Isolatie: ConceptStore accepteert een concepts_file-pad, dus elke
# test bouwt zijn eigen ConceptStore op binnen pytest's tmp_path --
# NOOIT de echte data/concepts.json. SemanticConceptsModule zelf wordt
# hier bewust NIET gebruikt, want die maakt altijd een ConceptStore()
# met het standaardpad (dus je echte data) en vereist een EventBus.
# SenseEngine/RelationEngine/ReasoningEngine rechtstreeks aanspreken
# geeft dezelfde functionaliteit, volledig geïsoleerd.
#
# Uitvoeren: pytest tests/test_tombstone.py -v

import pytest

from core.semantic import ConceptStore, SenseEngine, RelationEngine, ReasoningEngine


@pytest.fixture
def engines(tmp_path):
    """Bouwt een volledig geïsoleerde Store+Sense+Relation+Reasoning-
    combinatie op, met concepts.json in een tijdelijke map."""
    store = ConceptStore(
        concepts_file=str(tmp_path / "concepts.json"),
        log_file=str(tmp_path / "concepts.jsonl"),
    )
    sense_engine = SenseEngine(store)
    relation_engine = RelationEngine(store, sense_engine)
    reasoning_engine = ReasoningEngine(store, relation_engine)
    return store, sense_engine, relation_engine, reasoning_engine


# ─────────────────────────────────────────────────────────────
# Scenario 1: het exacte scenario uit nova_changelog.md/punt 26 --
# gitaar part_of orkest (via gitaar part_of orkest), weerleggen,
# en bevestigen dat part_of_chained() daarna False geeft.
# ─────────────────────────────────────────────────────────────

def test_part_of_chained_voor_weerlegging_is_true(engines):
    """Vóór het weerleggen hoort de keten gewoon te kloppen."""
    store, sense_engine, relation_engine, reasoning_engine = engines

    sense_engine.add_sense("snaar", "onderdeel van een instrument", source="user")
    sense_engine.add_sense("gitaar", "snaarinstrument", source="user")
    relation_engine.add_relation("snaar", "part_of", "gitaar")
    relation_engine.add_relation("gitaar", "part_of", "orkest")

    gevonden, pad = reasoning_engine.part_of_chained("snaar", "orkest")
    assert gevonden is True
    assert pad == ["snaar", "gitaar", "orkest"]


def test_part_of_chained_na_weerlegging_is_false(engines):
    """
    HET KERNSCENARIO: nadat de tussenschakel (gitaar part_of orkest)
    weerlegd is, hoort part_of_chained("snaar", "orkest") False te
    geven -- een afgewezen feit mag niet blijven meetellen in
    redeneringen, ook al blijft de relatie zelf zichtbaar in
    concepts.json (transparantie, geen stille verwijdering).
    """
    store, sense_engine, relation_engine, reasoning_engine = engines

    sense_engine.add_sense("snaar", "onderdeel van een instrument", source="user")
    sense_engine.add_sense("gitaar", "snaarinstrument", source="user")
    relation_engine.add_relation("snaar", "part_of", "gitaar")
    relation_engine.add_relation("gitaar", "part_of", "orkest")

    # Bevestig eerst dat de keten klopt (zelfde als test hierboven,
    # herhaald zodat deze test op zichzelf leesbaar blijft)
    gevonden_voor, _ = reasoning_engine.part_of_chained("snaar", "orkest")
    assert gevonden_voor is True

    # Weerleg de tussenschakel: gitaar is GEEN onderdeel van orkest
    gitaar_sense = sense_engine.get_senses("gitaar")[0]
    resultaat = relation_engine.reject_relation(
        "gitaar", gitaar_sense["sense_id"], "part_of", "orkest",
        reason="een gitaar is geen orkest-onderdeel, dat was fout"
    )
    assert resultaat is not None, "reject_relation() vond de relatie niet"
    assert resultaat["status"] == "rejected"

    gevonden_na, _ = reasoning_engine.part_of_chained("snaar", "orkest")
    assert gevonden_na is False, (
        "FOUT: part_of_chained() vindt nog steeds een pad via een "
        "afgewezen relatie -- het tombstone-mechanisme wordt niet "
        "gerespecteerd door de reasoning-laag."
    )


def test_rejected_relatie_blijft_zichtbaar_in_concepts_json(engines):
    """
    Transparantie-eis: een rejected relatie moet blijven BESTAAN in
    concepts.json (niet fysiek verdwijnen) -- enkel de reasoning-laag
    negeert 'm. get_senses()/export_concept() horen alles te tonen.
    """
    store, sense_engine, relation_engine, reasoning_engine = engines

    sense_engine.add_sense("gitaar", "snaarinstrument", source="user")
    relation_engine.add_relation("gitaar", "part_of", "orkest")

    gitaar_sense = sense_engine.get_senses("gitaar")[0]
    relation_engine.reject_relation("gitaar", gitaar_sense["sense_id"], "part_of", "orkest")

    concept = store.export_concept("gitaar")
    relaties = concept["senses"][0]["relations"]
    assert len(relaties) == 1, "De relatie had moeten blijven bestaan, niet verdwijnen."
    assert relaties[0]["status"] == "rejected"


# ─────────────────────────────────────────────────────────────
# Scenario 2: get_relations() zelf -- de centrale doorvoerpijp
# waar bijna alle andere queries doorheen lopen (is_a, synoniemen,
# antoniemen, ...). Eén test hier dekt indirect een brede laag.
# ─────────────────────────────────────────────────────────────

def test_get_relations_negeert_rejected_relatie(engines):
    store, sense_engine, relation_engine, reasoning_engine = engines

    sense_engine.add_sense("hond", "huisdier", source="user")
    relation_engine.add_relation("hond", "is_a", "dier")
    relation_engine.add_relation("hond", "is_a", "meubel")  # de fout uit het changelog-scenario

    # Vóór weerlegging: beide relaties tellen mee
    assert set(relation_engine.get_relations("hond", "is_a")) == {"dier", "meubel"}

    hond_sense = sense_engine.get_senses("hond")[0]
    relation_engine.reject_relation("hond", hond_sense["sense_id"], "is_a", "meubel")

    # Na weerlegging: enkel nog 'dier', 'meubel' blijft zichtbaar in
    # concepts.json maar telt niet meer mee in get_relations()
    assert relation_engine.get_relations("hond", "is_a") == ["dier"]


def test_get_relations_negeert_alles_onder_rejected_sense(engines):
    """
    Als de SENSE zelf rejected is, tellen ALLE relaties eronder niet
    meer mee, ongeacht hun eigen status (zie get_relations()-
    docstring/commentaar in de broncode).
    """
    store, sense_engine, relation_engine, reasoning_engine = engines

    sense_engine.add_sense("bank", "meubelstuk om op te zitten", source="user")
    relation_engine.add_relation("bank", "is_a", "meubel")

    bank_sense = sense_engine.get_senses("bank")[0]
    sense_engine.reject_sense("bank", bank_sense["sense_id"], reason="verkeerde sense-splitsing")

    assert relation_engine.get_relations("bank", "is_a") == []


# ─────────────────────────────────────────────────────────────
# Scenario 3: het OPENSTAANDE ONDERZOEKSPUNT uit punt 26 zelf --
# "of de dedup-loop in add_sense() intentioneel toestaat dat een
# rejected definitie overleeft bij re-assertie (matcht op tekst
# zonder rejected-rijen te filteren)". Dit was nog niet bevestigd,
# enkel als vraag genoteerd -- deze test legt het GEDRAG vast zoals
# het nu is, zodat een toekomstige wijziging bewust gebeurt.
# ─────────────────────────────────────────────────────────────

def test_add_sense_dedup_NEGEERT_rejected_status_BEKENDE_BEVINDING(engines):
    """
    BEVINDING (beantwoordt de open vraag uit punt 26): add_sense()'s
    deduplicatie-check (regel 188-209 van semantic.py) vergelijkt
    ENKEL op `definition`-tekst, zonder te filteren op status. Een
    rejected sense met exact dezelfde definitie-tekst komt daardoor
    STILZWIJGEND terug tot leven zodra add_sense() opnieuw met die
    tekst wordt aangeroepen (bv. via een nieuwe Wikipedia/auto-
    extract-match) -- de status wordt teruggezet naar "confirmed"
    (bij source="user") of blijft op zijn minst niet "rejected".

    Dit is op dit moment BEVESTIGD GEDRAG, geen giswerk meer. Het is
    aan Kevin om te beslissen of dit een bug is die gefixt moet
    worden (dedup zou rejected-rijen moeten overslaan en een NIEUWE
    sense moeten aanmaken i.p.v. de oude te doen herleven) of bewust
    gedrag blijft. Deze test legt vast WAT er nu gebeurt, zodat een
    toekomstige fix hier bewust tegenaan botst i.p.v. onopgemerkt te
    passeren.
    """
    store, sense_engine, relation_engine, reasoning_engine = engines

    sense = sense_engine.add_sense("verzonnenwoord", "een compleet verzonnen definitie", source="user")
    sense_id = sense["sense_id"]

    sense_engine.reject_sense("verzonnenwoord", sense_id, reason="test: dit was verzonnen")

    concept = store.export_concept("verzonnenwoord")
    assert concept["senses"][0]["status"] == "rejected"

    # Re-assertie: exact dezelfde definitie-tekst opnieuw aanbieden,
    # zoals een nieuwe Wikipedia-match of hernieuwde chat-input zou
    # kunnen doen.
    opnieuw = sense_engine.add_sense(
        "verzonnenwoord", "een compleet verzonnen definitie", source="user"
    )

    # BEVINDING: dit matcht de bestaande (rejected) sense via de
    # dedup-tak, en source="user" zet status terug naar "confirmed".
    assert opnieuw["sense_id"] == sense_id, (
        "Verwacht: dedup matcht dezelfde sense_id (bevestigt dat het "
        "de rejected rij hergebruikt i.p.v. een nieuwe aan te maken)."
    )
    assert opnieuw["status"] == "confirmed", (
        "BEVESTIGD: een rejected sense komt stilzwijgend terug als "
        "'confirmed' zodra dezelfde definitie-tekst opnieuw met "
        "source='user' wordt aangeboden. Dit is de kern van de open "
        "vraag in punt 26 -- nu een vastgelegd feit i.p.v. een "
        "vermoeden."
    )