# test_afwijzing_op_betekenis.py
#
# Regressietests voor punt 60d (3 november 2026): een afgewezen (rejected)
# definitie komt ook niet terug als ze enkel anders getypt is
# (hoofdletters, leestekens, lidwoorden) of een spelfout bevat. Bewust
# GEEN losse tekstovereenkomst: een definitie met een ander kernwoord
# ("lange" tegenover "korte" slagtanden) moet gewoon toegevoegd kunnen
# worden.
#
# Isolatie: ConceptStore in pytest's tmp_path, nooit de echte
# data/concepts.json.
# Uitvoeren: pytest tests/test_afwijzing_op_betekenis.py -v

import pytest

from core.semantic import ConceptStore, SenseEngine, definitie_gelijkenis


@pytest.fixture
def sense_engine(tmp_path):
    store = ConceptStore(
        concepts_file=str(tmp_path / "concepts.json"),
        log_file=str(tmp_path / "concepts.jsonl"),
    )
    return SenseEngine(store)


def _weerlegde_sense(sense_engine, woord, tekst):
    sense = sense_engine.add_sense(woord, tekst, source="user")
    assert sense_engine.reject_sense(woord, sense["sense_id"])
    return sense


# --- de vergelijking zelf ---------------------------------------------------

@pytest.mark.parametrize("a,b,verwacht", [
    ("een huisdier", "een huisdier", "exact"),
    ("een huisdier", "Een huisdier.", "genormaliseerd"),
    ("een huisdier", "huisdier", "genormaliseerd"),
    ("Een hoog, smal gebouw", "een hoog smal gebouw", "genormaliseerd"),
    ("een huisdier dat blaft", "een huisdeir dat blaft", "spelfout"),
])
def test_zelfde_betekenis_wordt_herkend(a, b, verwacht):
    assert definitie_gelijkenis(a, b) == verwacht


@pytest.mark.parametrize("a,b", [
    # tegenstellingen scoren met difflib hoog, maar zijn andere betekenissen
    ("een zeezoogdier met lange slagtanden", "een zeezoogdier met korte slagtanden"),
    ("een dier met vier poten", "een dier met twee poten"),
    ("een vrucht die rood is", "een vrucht die groen is"),
    ("een boom met bladeren", "een boom zonder bladeren"),
    # extra woord = andere (uitgebreidere) definitie
    ("een zeezoogdier met lange slagtanden", "een zeezoogdier met lange slagtanden en snorharen"),
    # totaal andere betekenis
    ("een hoog, smal gebouw", "een schaakstuk dat recht beweegt"),
    # leeg
    ("", "een huisdier"),
])
def test_andere_betekenis_wordt_niet_gelijkgesteld(a, b):
    assert definitie_gelijkenis(a, b) is None


# --- add_sense --------------------------------------------------------------

def test_exact_zelfde_tekst_blijft_geblokkeerd(sense_engine):
    _weerlegde_sense(sense_engine, "walrus", "een huisdier")
    resultaat = sense_engine.add_sense("walrus", "een huisdier", source="user")
    assert resultaat["blocked"] == "rejected"


def test_andere_schrijfwijze_wordt_geblokkeerd(sense_engine):
    oud = _weerlegde_sense(sense_engine, "walrus", "een huisdier")
    resultaat = sense_engine.add_sense("walrus", "Een huisdier.", source="user")
    assert resultaat["blocked"] == "rejected"
    assert resultaat["match"] == "genormaliseerd"
    assert resultaat["sense"]["sense_id"] == oud["sense_id"]


def test_spelfout_wordt_geblokkeerd_ook_voor_automatische_bron(sense_engine):
    _weerlegde_sense(sense_engine, "hond", "een huisdier dat blaft")
    resultaat = sense_engine.add_sense("hond", "een huisdeir dat blaft", source="wikipedia")
    assert resultaat["blocked"] == "rejected"
    assert resultaat["attempted_source"] == "wikipedia"


def test_geblokkeerde_sense_is_niet_aangepast_of_toegevoegd(sense_engine):
    _weerlegde_sense(sense_engine, "hond", "een huisdier")
    sense_engine.add_sense("hond", "een huisdier!", source="user")
    senses = sense_engine.store.get_concept("hond")["senses"]
    assert len(senses) == 1
    assert senses[0]["status"] == "rejected"
    assert senses[0]["definition"] == "een huisdier"


def test_nieuwe_definitie_met_ander_kernwoord_mag_wel(sense_engine):
    _weerlegde_sense(sense_engine, "walrus", "een zeezoogdier met korte slagtanden")
    resultaat = sense_engine.add_sense("walrus", "een zeezoogdier met lange slagtanden", source="user")
    assert "blocked" not in resultaat
    assert resultaat["status"] == "confirmed"


def test_niet_afgewezen_sense_wordt_niet_geblokkeerd(sense_engine):
    sense_engine.add_sense("hond", "een huisdier", source="user")
    resultaat = sense_engine.add_sense("hond", "Een huisdier.", source="user")
    assert "blocked" not in resultaat          # gewone dedup/nieuwe sense, geen afwijzing


def test_unknown_placeholder_telt_niet_als_afgewezen(sense_engine):
    sense_engine.add_sense("hond", "unknown", source="auto", confidence=0.1)
    resultaat = sense_engine.add_sense("hond", "een huisdier", source="user")
    assert "blocked" not in resultaat


# --- upgrade_unknown_sense (bug #47-pad) ---------------------------------

def test_placeholder_upgrade_met_andere_schrijfwijze_wordt_geblokkeerd(sense_engine):
    _weerlegde_sense(sense_engine, "werk", "arbeid die je doet")
    # placeholder erbij, zoals auto_learn dat doet bij een meervoud
    sense_engine.add_sense("werk", "unknown", source="auto", confidence=0.1)
    resultaat = sense_engine.upgrade_unknown_sense("werk", "Arbeid die je doet.", source="user")
    assert resultaat["blocked"] == "rejected"
    assert resultaat["match"] == "genormaliseerd"