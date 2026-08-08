# test_hard_delete_en_atomic_save.py
#
# Echte pytest-test voor de laatste twee onderdelen van semantic.py die
# nog niet gedekt waren door test_tombstone.py / test_reasoning.py:
#
#   Deel 1 -- hard_delete_sense() / hard_delete_relation(): de guard
#   die vereist dat iets EERST via reject_*() afgewezen moet zijn
#   vóórdat het fysiek verwijderd mag worden (tombstone-voor-hard-
#   delete-principe).
#
#   Deel 2 -- ConceptStore.save()'s atomaire schrijflogica: schrijft
#   naar een tijdelijk bestand en wisselt dat pas om met os.replace(),
#   zodat een crash tijdens het schrijven het bestaande concepts.json
#   nooit halverwege leeg/kapot achterlaat. Gebaseerd op hetzelfde idee
#   als het bestaande, handmatige scripts/test_atomic_save.py, maar nu
#   als een echte, geïsoleerde pytest-test met tmp_path.
#
# Isolatie: zelfde patroon als test_tombstone.py/test_reasoning.py --
# ConceptStore met concepts_file/log_file in tmp_path.
#
# Uitvoeren: pytest tests/test_hard_delete_en_atomic_save.py -v

import glob
import json
import os

import pytest

from core.semantic import ConceptStore, SenseEngine, RelationEngine


@pytest.fixture
def engines(tmp_path):
    store = ConceptStore(
        concepts_file=str(tmp_path / "concepts.json"),
        log_file=str(tmp_path / "concepts.jsonl"),
    )
    sense_engine = SenseEngine(store)
    relation_engine = RelationEngine(store, sense_engine)
    return store, sense_engine, relation_engine


# ─────────────────────────────────────────────────────────────
# Deel 1a: hard_delete_sense() -- de guard
# ─────────────────────────────────────────────────────────────

def test_hard_delete_sense_weigert_zonder_voorafgaande_reject(engines):
    """
    KERN VAN DE GUARD: een sense die nog NIET via reject_sense() is
    afgewezen, mag hard_delete_sense() niet fysiek verwijderen -- dit
    is het tombstone-voor-hard-delete-principe.
    """
    store, sense_engine, relation_engine = engines

    sense = sense_engine.add_sense("verzonnenwoord", "een definitie", source="user")
    sense_id = sense["sense_id"]

    resultaat = sense_engine.hard_delete_sense("verzonnenwoord", sense_id)

    assert resultaat is False, (
        "hard_delete_sense() verwijderde een sense die nog nooit "
        "afgewezen was -- de guard werkt niet."
    )
    # De sense hoort nog gewoon te bestaan, ongewijzigd.
    concept = store.export_concept("verzonnenwoord")
    assert len(concept["senses"]) == 1
    assert concept["senses"][0]["status"] != "rejected"


def test_hard_delete_sense_werkt_na_voorafgaande_reject(engines):
    """Na EERST reject_sense() aan te roepen, hoort hard_delete_sense()
    de sense wél fysiek te mogen verwijderen."""
    store, sense_engine, relation_engine = engines

    sense = sense_engine.add_sense("verzonnenwoord", "een definitie", source="user")
    sense_id = sense["sense_id"]

    sense_engine.reject_sense("verzonnenwoord", sense_id, reason="test")
    resultaat = sense_engine.hard_delete_sense("verzonnenwoord", sense_id)

    assert resultaat is True
    concept = store.export_concept("verzonnenwoord")
    assert len(concept["senses"]) == 0, (
        "De sense had fysiek verwijderd moeten zijn na reject + hard_delete."
    )


def test_hard_delete_sense_laat_audit_spoor_achter(engines):
    """Ook na fysieke verwijdering hoort er een audit-log-entry op
    CONCEPT-niveau te blijven staan (de sense zelf bestaat niet meer
    om naar te verwijzen, dus het spoor moet op het concept zelf)."""
    store, sense_engine, relation_engine = engines

    sense = sense_engine.add_sense("verzonnenwoord", "een definitie", source="user")
    sense_id = sense["sense_id"]
    sense_engine.reject_sense("verzonnenwoord", sense_id, reason="test")
    sense_engine.hard_delete_sense("verzonnenwoord", sense_id)

    concept = store.export_concept("verzonnenwoord")
    audit_events = [a["event_type"] for a in concept.get("audit_log", [])]
    assert "sense_hard_deleted" in audit_events


def test_hard_delete_sense_false_voor_onbekend_woord(engines):
    store, sense_engine, relation_engine = engines
    assert sense_engine.hard_delete_sense("nooitgezien", "sense_1") is False


def test_hard_delete_sense_false_voor_onbekende_sense_id(engines):
    store, sense_engine, relation_engine = engines
    sense_engine.add_sense("hond", "huisdier", source="user")
    assert sense_engine.hard_delete_sense("hond", "niet-bestaande-sense-id") is False


# ─────────────────────────────────────────────────────────────
# Deel 1b: hard_delete_relation() -- zelfde guard, andere laag
# ─────────────────────────────────────────────────────────────

def test_hard_delete_relation_weigert_zonder_voorafgaande_reject(engines):
    store, sense_engine, relation_engine = engines

    sense_engine.add_sense("hond", "huisdier", source="user")
    relation_engine.add_relation("hond", "is_a", "meubel")
    hond_sense = sense_engine.get_senses("hond")[0]

    resultaat = relation_engine.hard_delete_relation(
        "hond", hond_sense["sense_id"], "is_a", "meubel"
    )

    assert resultaat is False, (
        "hard_delete_relation() verwijderde een relatie die nog nooit "
        "afgewezen was -- de guard werkt niet."
    )
    concept = store.export_concept("hond")
    relaties = concept["senses"][0]["relations"]
    assert len(relaties) == 1  # nog steeds aanwezig


def test_hard_delete_relation_werkt_na_voorafgaande_reject(engines):
    store, sense_engine, relation_engine = engines

    sense_engine.add_sense("hond", "huisdier", source="user")
    relation_engine.add_relation("hond", "is_a", "meubel")
    hond_sense = sense_engine.get_senses("hond")[0]

    relation_engine.reject_relation("hond", hond_sense["sense_id"], "is_a", "meubel")
    resultaat = relation_engine.hard_delete_relation(
        "hond", hond_sense["sense_id"], "is_a", "meubel"
    )

    assert resultaat is True
    concept = store.export_concept("hond")
    relaties = concept["senses"][0]["relations"]
    assert len(relaties) == 0, (
        "De relatie had fysiek verwijderd moeten zijn na reject + hard_delete."
    )


def test_hard_delete_relation_raakt_andere_relaties_niet_aan(engines):
    """Als een sense MEERDERE relaties heeft, mag hard_delete_relation()
    enkel de specifiek opgegeven relatie verwijderen, niet de rest."""
    store, sense_engine, relation_engine = engines

    sense_engine.add_sense("hond", "huisdier", source="user")
    relation_engine.add_relation("hond", "is_a", "dier")
    relation_engine.add_relation("hond", "is_a", "meubel")
    hond_sense = sense_engine.get_senses("hond")[0]

    relation_engine.reject_relation("hond", hond_sense["sense_id"], "is_a", "meubel")
    relation_engine.hard_delete_relation("hond", hond_sense["sense_id"], "is_a", "meubel")

    assert relation_engine.get_relations("hond", "is_a") == ["dier"], (
        "hard_delete_relation() raakte een relatie aan die niet was "
        "opgegeven om verwijderd te worden."
    )


def test_hard_delete_relation_false_voor_onbekende_sense(engines):
    store, sense_engine, relation_engine = engines
    assert relation_engine.hard_delete_relation(
        "nooitgezien", "sense_1", "is_a", "iets"
    ) is False


# ─────────────────────────────────────────────────────────────
# Deel 2: ConceptStore.save() -- atomaire schrijflogica
# ─────────────────────────────────────────────────────────────

def test_save_schrijft_correcte_inhoud(tmp_path):
    """Basisgeval: save() hoort de huidige self.concepts-inhoud
    correct als JSON weg te schrijven naar concepts_file."""
    concepts_file = tmp_path / "concepts.json"
    store = ConceptStore(concepts_file=str(concepts_file), log_file=str(tmp_path / "log.jsonl"))

    store.concepts["testwoord"] = {"senses": [], "metadata": {}}
    store.save()

    assert concepts_file.exists()
    with open(concepts_file, "r", encoding="utf-8") as f:
        inhoud = json.load(f)
    assert "testwoord" in inhoud


def test_save_laat_geen_tijdelijk_bestand_achter_bij_succes(tmp_path):
    """Na een succesvolle save() hoort er GEEN .tmp<pid>-bestand meer
    te bestaan -- os.replace() ruimt dat impliciet op door het bestand
    te hernoemen naar de definitieve naam."""
    concepts_file = tmp_path / "concepts.json"
    store = ConceptStore(concepts_file=str(concepts_file), log_file=str(tmp_path / "log.jsonl"))

    store.concepts["testwoord"] = {"senses": [], "metadata": {}}
    store.save()

    tmp_bestanden = glob.glob(str(tmp_path / "concepts.json.tmp*"))
    assert tmp_bestanden == [], (
        f"Er bleef een tijdelijk bestand achter na een succesvolle save(): {tmp_bestanden}"
    )


def test_save_meerdere_keren_overschrijft_correct(tmp_path):
    """Meerdere save()-aanroepen na elkaar horen elke keer de LAATSTE
    stand van self.concepts weg te schrijven, niet te blijven
    toevoegen aan het oude bestand."""
    concepts_file = tmp_path / "concepts.json"
    store = ConceptStore(concepts_file=str(concepts_file), log_file=str(tmp_path / "log.jsonl"))

    store.concepts["woord_1"] = {"senses": [], "metadata": {}}
    store.save()

    store.concepts["woord_2"] = {"senses": [], "metadata": {}}
    store.save()

    with open(concepts_file, "r", encoding="utf-8") as f:
        inhoud = json.load(f)
    assert "woord_1" in inhoud
    assert "woord_2" in inhoud


def test_save_faalt_netjes_bij_schrijffout_en_ruimt_tmp_bestand_op(tmp_path, monkeypatch):
    """
    Als het schrijven naar het tijdelijke bestand faalt (bv. schijf
    vol, of een andere OSError), hoort save() de exception door te
    geven (niet stil te slikken) EN het eventueel al aangemaakte
    tijdelijke bestand op te ruimen -- geen verweesd .tmp<pid>-bestand
    achterlaten.
    """
    concepts_file = tmp_path / "concepts.json"
    store = ConceptStore(concepts_file=str(concepts_file), log_file=str(tmp_path / "log.jsonl"))
    store.concepts["testwoord"] = {"senses": [], "metadata": {}}

    origineel_replace = os.replace

    def kapotte_replace(*args, **kwargs):
        raise OSError("kunstmatige testfout: schijf vol")

    monkeypatch.setattr(os, "replace", kapotte_replace)

    with pytest.raises(OSError):
        store.save()

    # Geen concepts.json aangemaakt (de replace faalde, dus het
    # bestand bestond hiervoor ook nog niet)
    assert not concepts_file.exists()

    # Geen verweesd tijdelijk bestand
    tmp_bestanden = glob.glob(str(tmp_path / "concepts.json.tmp*"))
    assert tmp_bestanden == [], (
        f"Er bleef een tijdelijk bestand achter na een gefaalde save(): {tmp_bestanden}"
    )


def test_save_laat_oud_bestand_intact_bij_gefaalde_write(tmp_path, monkeypatch):
    """
    KERN VAN DE ATOMICITEIT: als er al een geldig concepts.json bestaat,
    en een VOLGENDE save() faalt tijdens het schrijven, moet het oude,
    intacte bestand blijven staan -- niet half overschreven of leeg
    raken. Dit is exact het scenario dat de fix (6 augustus 2026)
    moest oplossen.
    """
    concepts_file = tmp_path / "concepts.json"
    store = ConceptStore(concepts_file=str(concepts_file), log_file=str(tmp_path / "log.jsonl"))

    # Eerste, succesvolle save -- dit is het "oude, intacte bestand"
    store.concepts["oorspronkelijk_woord"] = {"senses": [], "metadata": {}}
    store.save()

    with open(concepts_file, "r", encoding="utf-8") as f:
        inhoud_voor_crash = json.load(f)

    # Tweede save() faalt kunstmatig tijdens de replace-stap
    store.concepts["nieuw_woord_dat_nooit_aankomt"] = {"senses": [], "metadata": {}}

    def kapotte_replace(*args, **kwargs):
        raise OSError("kunstmatige testfout tijdens 2e save")

    monkeypatch.setattr(os, "replace", kapotte_replace)
    with pytest.raises(OSError):
        store.save()

    # Het bestand op schijf hoort NOG STEEDS de EERSTE, succesvolle
    # inhoud te hebben -- niet leeg, niet half geschreven, niet de
    # (nooit voltooide) tweede versie.
    with open(concepts_file, "r", encoding="utf-8") as f:
        inhoud_na_crash = json.load(f)

    assert inhoud_na_crash == inhoud_voor_crash, (
        "Het bestaande concepts.json werd aangetast door een gefaalde "
        "save()-poging -- de atomaire write-garantie werkt niet."
    )
    assert "nieuw_woord_dat_nooit_aankomt" not in inhoud_na_crash