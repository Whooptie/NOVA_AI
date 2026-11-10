# tests/test_schaak_last_context17.py
"""
Punt 17 (10 november 2026): de schaakmodule onthoudt het gespreksonderwerp.

Voorheen riep geen enkel schaakcommando last_context.set_concept() aan, dus "wat is dat" na
"bord" gaf "Waar heb je het over?". Nu zet:
- het bord tonen      -> onderwerp "schaakbord"
- een nieuwe partij   -> onderwerp "schaken"
- een zet             -> wist het onderwerp (punt 79: daar komen de doorvragen voor in de plaats)

Eerlijke beperking: "wat is dat" geeft daarna de woordenboekdefinitie van "schaakbord" of
"schaken", niet een uitleg over jouw lopende partij.

Draait zonder Stockfish en zonder je echte data: PROJECT_ROOT wijst naar tmp_path.
Stockfish wordt ook NIET gestart als hij op je machine wel staat (ensure_engine geeft False):
een gestarte engine die niemand afsluit laat pytest aan het einde blijven hangen.
"""
import pytest

pytest.importorskip("chess")

import core.semantic as semantic_mod
from core.event_bus import EventBus
from core.intent_router import IntentRouter
from core.last_context import init_module as init_last_context
from core.semantic import ConceptStore, SemanticConceptsModule
from modules.chat.chat import ChatModule
from modules.chess import chess_engine as chess_mod


@pytest.fixture
def omgeving(tmp_path, monkeypatch):
    echte_klasse = ConceptStore
    concepts = str(tmp_path / "data" / "concepts.json")
    log = str(tmp_path / "logs" / "concepts.jsonl")
    monkeypatch.setattr(semantic_mod, "ConceptStore", lambda: echte_klasse(concepts, log))
    monkeypatch.setattr(chess_mod, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(chess_mod.ChessModule, "_start_inactivity_watcher", lambda self: None)
    monkeypatch.setattr(chess_mod.ChessModule, "ensure_engine", lambda self: False)

    bus = EventBus()
    sem = SemanticConceptsModule(bus)
    sem.sense_engine.add_sense("schaakbord", "een bord met 64 velden om op te schaken",
                               source="user", confidence=1.0)
    sem.sense_engine.add_sense("schaken", "een bordspel voor twee spelers",
                               source="user", confidence=1.0)
    bus.modules["semantic"] = sem
    last_ctx = init_last_context(bus)
    bus.register_module("last_context", last_ctx)
    ChatModule(bus, semantic_module=sem)
    schaak = chess_mod.ChessModule(bus)
    bus.register_module("chess_engine", schaak)
    router = IntentRouter(bus, semantic_module=sem)
    teksten = []
    bus.subscribe("layer4_response", lambda d, *a, **k: teksten.append(d.get("text", "")))
    bus.subscribe("chat_response", lambda d, *a, **k: teksten.append(d.get("text", "")))
    yield bus, router, last_ctx, teksten
    schaak.shutdown()          # sluit een eventuele engine netjes af


def _zeg(router, teksten, zin):
    teksten.clear()
    router.route({"text": zin}, "chat_message")
    return " ".join(teksten)


def test_bord_tonen_onthoudt_schaakbord(omgeving):
    _, router, last_ctx, teksten = omgeving
    _zeg(router, teksten, "bord")
    assert last_ctx.get_concept() == "schaakbord"


def test_nieuwe_partij_onthoudt_schaken(omgeving):
    _, router, last_ctx, teksten = omgeving
    _zeg(router, teksten, "nieuwe partij")
    assert last_ctx.get_concept() == "schaken"


def test_na_een_zet_geeft_wat_is_dat_geen_definitie(omgeving):
    # Punt 79: een zet WIST het onderwerp. "wat is dat" geeft dan geen woordenboekdefinitie
    # van "schaken" meer; de doorvragen ("waarom speelde je dat") nemen die rol over.
    _, router, last_ctx, teksten = omgeving
    _zeg(router, teksten, "nieuwe partij")
    _zeg(router, teksten, "e2e4")
    assert last_ctx.get_concept() is None
    assert "Waar heb je het over" in _zeg(router, teksten, "wat is dat")


def test_wat_is_dat_na_bord_geeft_de_definitie_en_geen_tegenvraag(omgeving):
    _, router, _, teksten = omgeving
    _zeg(router, teksten, "bord")
    antwoord = _zeg(router, teksten, "wat is dat")
    assert "Waar heb je het over" not in antwoord
    assert "64 velden" in antwoord


def test_wat_is_dat_na_nieuwe_partij_gaat_over_schaken(omgeving):
    _, router, _, teksten = omgeving
    _zeg(router, teksten, "nieuwe partij")
    antwoord = _zeg(router, teksten, "wat is dat")
    assert "Waar heb je het over" not in antwoord
    assert "bordspel" in antwoord


def test_zonder_schaakcommando_blijft_de_tegenvraag_bestaan(omgeving):
    _, router, _, teksten = omgeving
    assert "Waar heb je het over" in _zeg(router, teksten, "wat is dat")


def test_een_ander_onderwerp_na_het_bord_wint(omgeving):
    _, router, last_ctx, teksten = omgeving
    _zeg(router, teksten, "bord")
    _zeg(router, teksten, "wat is schaken")
    assert last_ctx.get_concept() == "schaken"