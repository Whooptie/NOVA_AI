# tests/test_keuze_in_woorden73.py
"""
Tests voor punt 73 (6 november 2026): een antwoord in woorden op de keuzevraag
"welke betekenis bedoel je?" ("ik bedoel het schaakstuk").

Eerlijk over wat dit is: woordzoeken in de aangeboden definities, geen begrip van betekenis.
Past precies één betekenis, dan kiest Nova die. Passen er meer, dan vraagt ze één keer opnieuw.
Past er geen enkele (of is het een vraag of een lange zin), dan vervalt de vraag zoals voorheen.
"""
import pytest

import core.semantic as semantic_mod
from core.event_bus import EventBus
from core.intent_router import IntentRouter
from core.semantic import ConceptStore, SemanticConceptsModule

GEBOUW = "een hoog gebouw of bouwwerk, bijvoorbeeld een kerktoren"
SCHAAK = "een schaakstuk dat in rechte lijnen over het bord beweegt"
GELD = "een financieel instituut waar je geld kunt bewaren"
MEUBEL = "een zitmeubel voor meerdere personen"
BANK_MEUBEL_GELD = "een zitmeubel in een financieel gebouw"


@pytest.fixture
def omgeving(tmp_path, monkeypatch):
    echte_klasse = ConceptStore
    concepts = str(tmp_path / "data" / "concepts.json")
    log = str(tmp_path / "logs" / "concepts.jsonl")
    monkeypatch.setattr(semantic_mod, "ConceptStore", lambda: echte_klasse(concepts, log))
    bus = EventBus()
    sem = SemanticConceptsModule(bus)
    antwoorden = []
    bus.subscribe("layer4_response", lambda d, *a, **k: antwoorden.append(d.get("text", "")))
    bus.subscribe("chat_response", lambda d, *a, **k: antwoorden.append(d.get("text", "")))
    return sem, bus, antwoorden


def _toren(sem):
    sem.sense_engine.add_sense("toren", GEBOUW, source="user", confidence=1.0)
    sem.sense_engine.add_sense("toren", SCHAAK, source="user", confidence=0.5)


def _start(sem, woord="toren"):
    assert sem.start_definitie_keuze(woord, ["wat", "is", "een", woord])
    assert sem.pending_definitie_keuze is not None


# ---------------------------------------------------------------------------
# handle_definitie_keuze: antwoord in woorden
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("antwoord", [
    "ik bedoel het schaakstuk", "het schaakstuk", "Ik bedoelde het schaakstuk.",
    "schaakstuk", "gewoon het schaakstuk natuurlijk",
])
def test_woordantwoord_kiest_de_juiste_betekenis(omgeving, antwoord):
    sem, bus, antwoorden = omgeving
    _toren(sem)
    _start(sem)
    antwoorden.clear()
    assert sem.handle_definitie_keuze(antwoord) is True
    assert sem.pending_definitie_keuze is None
    assert antwoorden == [f"toren betekent: {SCHAAK}"]


def test_woordantwoord_kiest_de_eerste_betekenis(omgeving):
    sem, bus, antwoorden = omgeving
    _toren(sem)
    _start(sem)
    antwoorden.clear()
    assert sem.handle_definitie_keuze("ik bedoel het gebouw") is True
    assert antwoorden == [f"toren betekent: {GEBOUW}"]


def test_nummer_en_rangtelwoord_werken_nog(omgeving):
    sem, bus, antwoorden = omgeving
    _toren(sem)
    _start(sem)
    antwoorden.clear()
    assert sem.handle_definitie_keuze("2") is True
    assert antwoorden == [f"toren betekent: {SCHAAK}"]
    _start(sem)
    antwoorden.clear()
    assert sem.handle_definitie_keuze("de eerste") is True
    assert antwoorden == [f"toren betekent: {GEBOUW}"]


def test_meerdere_treffers_vraagt_een_keer_opnieuw(omgeving):
    sem, bus, antwoorden = omgeving
    sem.sense_engine.add_sense("bank", BANK_MEUBEL_GELD, source="user", confidence=1.0)
    sem.sense_engine.add_sense("bank", GELD, source="user", confidence=0.5)
    sem.sense_engine.add_sense("bank", MEUBEL, source="user", confidence=0.4)
    _start(sem, "bank")
    antwoorden.clear()
    # "financieel" staat in definitie 1 en 2, "instituut" in 2: dit past op meerdere betekenissen.
    assert sem.handle_definitie_keuze("die van het financieel instituut gebouw") is True
    assert "Kies een nummer tussen 1 en 3" in antwoorden[0]
    assert sem.pending_definitie_keuze is not None
    # Tweede keer weer onduidelijk: de vraag vervalt en de zin gaat door de routing.
    assert sem.handle_definitie_keuze("die van het financieel instituut gebouw") is False
    assert sem.pending_definitie_keuze is None


def test_geen_treffer_laat_de_vraag_vervallen(omgeving):
    sem, bus, antwoorden = omgeving
    _toren(sem)
    _start(sem)
    antwoorden.clear()
    assert sem.handle_definitie_keuze("ik hou van koffie") is False
    assert sem.pending_definitie_keuze is None
    assert antwoorden == []


@pytest.mark.parametrize("zin", [
    "wat is een schaakstuk",            # vraag
    "is het schaakstuk een paard?",     # vraag
    "waar staat het schaakstuk",        # vraagwoord
    "ik denk dat ik gisteren op de markt een mooi gebouw heb gezien bij mijn tante",  # te lang
])
def test_vraag_of_lange_zin_is_geen_keuze(omgeving, zin):
    sem, bus, antwoorden = omgeving
    _toren(sem)
    _start(sem)
    antwoorden.clear()
    assert sem.handle_definitie_keuze(zin) is False
    assert sem.pending_definitie_keuze is None


def test_nummer_buiten_bereik_blijft_zoals_het_was(omgeving):
    sem, bus, antwoorden = omgeving
    _toren(sem)
    _start(sem)
    antwoorden.clear()
    assert sem.handle_definitie_keuze("9") is True
    assert antwoorden == ["Kies een nummer tussen 1 en 2."]
    assert sem.pending_definitie_keuze is not None


# ---------------------------------------------------------------------------
# Door de hele router
# ---------------------------------------------------------------------------
def test_router_woordantwoord_na_keuzevraag(omgeving):
    sem, bus, antwoorden = omgeving
    _toren(sem)
    bus.modules = getattr(bus, "modules", {})
    bus.modules["semantic"] = sem
    from modules.chat.chat import ChatModule
    ChatModule(bus, semantic_module=sem)
    router = IntentRouter(bus, semantic_module=sem)
    router.route({"text": "wat is een toren"}, "chat_message")
    assert sem.pending_definitie_keuze is not None
    antwoorden.clear()
    router.route({"text": "ik bedoel het schaakstuk"}, "chat_message")
    assert any(a == f"toren betekent: {SCHAAK}" for a in antwoorden)
    assert sem.pending_definitie_keuze is None