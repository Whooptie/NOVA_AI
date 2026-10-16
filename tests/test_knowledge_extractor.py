"""Tests voor Semantic Fase 11.1 (knowledge_extractor)."""
import json
from pathlib import Path

import pytest

spacy = pytest.importorskip("spacy")
try:
    spacy.load("nl_core_news_sm", disable=["ner"])
except OSError:
    pytest.skip("model nl_core_news_sm ontbreekt", allow_module_level=True)

from modules.knowledge.knowledge_extractor import (
    KnowledgeExtractor, verwijder_haakjes, init_module)

REGELS = Path(__file__).resolve().parents[1] / "data" / "extractie_regels.json"


@pytest.fixture(scope="module")
def ex():
    return KnowledgeExtractor(regels_pad=REGELS)


def feiten(ex, tekst, zoek=None):
    return {(f["onderwerp"], f["relatie"], f["doel"])
            for f in ex.extract_from_text(tekst, zoek)}


def test_is_a_enkel(ex):
    assert ("gitaar", "is_a", "snaarinstrument") in feiten(
        ex, "Een gitaar is een snaarinstrument.", "gitaar")


def test_is_a_meerdere_doelen(ex):
    f = feiten(ex, "Een gitaar is een snaarinstrument en een muziekinstrument.", "gitaar")
    assert ("gitaar", "is_a", "snaarinstrument") in f
    assert ("gitaar", "is_a", "muziekinstrument") in f


def test_soort_vaartuig(ex):
    assert ("zeilboot", "is_a", "vaartuig") in feiten(
        ex, "Een zeilboot is een soort vaartuig.", "zeilboot")


def test_has_part(ex):
    f = feiten(ex, "Een fiets bestaat uit een frame, twee wielen en een stuur.", "fiets")
    assert {("fiets", "has_part", d) for d in ("frame", "wielen", "stuur")} <= f


def test_water_zuurstofatoom_niet(ex):
    t = "Water is een verbinding van twee waterstofatomen en een zuurstofatoom."
    assert ("water", "is_a", "zuurstofatoom") not in feiten(ex, t, "water")


def test_hond_de_eerste_zin(ex):
    t = "De hond is de gedomesticeerde ondersoort van de wolf."
    assert ("hond", "is_a", "ondersoort") in feiten(ex, t, "hond")


def test_de_niet_in_tweede_zin(ex):
    t = "Een hond is een dier. De hond is de beste vriend van de mens."
    f = feiten(ex, t, "hond")
    assert ("hond", "is_a", "dier") in f
    assert ("hond", "is_a", "vriend") not in f


def test_voorbehoud_meestal(ex):
    assert feiten(ex, "Een kat is meestal een huisdier.", "kat") == set()


def test_ontkenning(ex):
    assert feiten(ex, "Een hond is niet altijd een huisdier.", "hond") == set()


def test_voorbehoud_in_bijzin_mag(ex):
    t = "Een fiets is een voertuig dat doorgaans met spierkracht wordt aangedreven."
    assert ("fiets", "is_a", "voertuig") in feiten(ex, t, "fiets")


def test_voornaamwoord_onderwerp(ex):
    assert feiten(ex, "Het is een dier dat blaft.") == set()


def test_verleden_tijd(ex):
    assert feiten(ex, "De hond was het eerste dier dat werd gedomesticeerd.", "hond") == set()


def test_in_opkomst(ex):
    t = "In het begin van de 21e eeuw is de elektrische fiets in opkomst."
    assert feiten(ex, t, "fiets") == set()


def test_voorbeeld_vaag(ex):
    assert feiten(ex, "Een geleidehond is een voorbeeld van een assistentiehond.", "geleidehond") == set()


def test_onderwerp_gelijk_aan_doel(ex):
    assert feiten(ex, "Een hond is een hond.", "hond") == set()


def test_onderwerp_moet_zoekwoord_bevatten(ex):
    assert feiten(ex, "Een gitaar is een snaarinstrument.", "piano") == set()


def test_haakjes():
    assert verwijder_haakjes("De hond (Canis (lupus)) is een dier.") == "De hond is een dier."


def test_haakjes_in_zin(ex):
    t = "Een gitaar (van het Grieks kithara) is een snaarinstrument."
    assert ("gitaar", "is_a", "snaarinstrument") in feiten(ex, t, "gitaar")


def test_doorverwijspagina(ex):
    assert feiten(ex, "Mercurius kan verwijzen naar: een planeet is een hemellichaam.") == set()


def test_leeg(ex):
    assert ex.extract_from_text("", "x") == []
    assert ex.extract_from_text("   ", "x") == []


def test_geen_duplicaten(ex):
    t = "Een gitaar is een snaarinstrument. Een gitaar is een snaarinstrument."
    assert len(ex.extract_from_text(t, "gitaar")) == 1


def test_regels_ontbreken(tmp_path):
    e = KnowledgeExtractor(regels_pad=tmp_path / "bestaat_niet.json")
    assert not e.is_beschikbaar()
    assert e.extract_from_text("Een gitaar is een snaarinstrument.", "gitaar") == []


def test_regels_corrupt(tmp_path):
    p = tmp_path / "kapot.json"
    p.write_text("{ dit is geen json", encoding="utf-8")
    e = KnowledgeExtractor(regels_pad=p)
    assert not e.is_beschikbaar()
    assert e.extract_from_text("Een gitaar is een snaarinstrument.", "gitaar") == []


def test_regels_sleutel_mist(tmp_path):
    p = tmp_path / "onvolledig.json"
    p.write_text(json.dumps({"voorbehoud": []}), encoding="utf-8")
    e = KnowledgeExtractor(regels_pad=p)
    assert not e.is_beschikbaar()


def test_init_module():
    class Bus:
        def __init__(self): self.geregistreerd = {}
        def register_module(self, naam, inst): self.geregistreerd[naam] = inst
    bus = Bus()
    inst = init_module(bus)
    assert bus.geregistreerd["knowledge_extractor"] is inst