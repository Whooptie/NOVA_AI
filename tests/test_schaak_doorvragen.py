# tests/test_schaak_doorvragen.py
"""
Punt 79 (10 november 2026): doorvragen over schaakzetten.

Getest worden de zuivere functies in modules/chess/chess_uitleg.py (feiten uit python-chess)
en de hele weg router -> chess_engine met een NEPMOTOR. Er wordt dus nooit een echte
Stockfish gestart (een niet-afgesloten engine laat pytest aan het einde hangen).
"""
import pytest

chess = pytest.importorskip("chess")
import chess.engine

import core.semantic as semantic_mod
from core.event_bus import EventBus
from core.intent_router import IntentRouter
from core.last_context import init_module as init_last_context
from core.semantic import ConceptStore, SemanticConceptsModule
from modules.chat.chat import ChatModule
from modules.chess import chess_engine as chess_mod
from modules.chess import chess_uitleg as u


# ---------------------------------------------------------------- zuivere functies
def test_feiten_slaan_met_veld_en_stuk():
    bord = chess.Board("4k3/8/8/4p3/8/8/8/3QK3 w - - 0 1")
    bord.push_uci("d1d4")
    zin = u.zin_over_zet(u.feiten_van_zet(bord_voor=chess.Board("4k3/8/8/4p3/3p4/8/8/3QK3 w - - 0 1"),
                                          zet=chess.Move.from_uci("d1d4"), door_nova=True))
    assert "pion" in zin and "d4" in zin


def test_gevaar_stuk_kan_geslagen_worden_en_staat_niet_gedekt():
    voor = chess.Board("4k3/8/8/4p3/8/8/8/3QK3 w - - 0 1")
    zet = chess.Move.from_uci("d1d4")
    na = voor.copy()
    na.push(zet)
    zinnen = u.gevaren_na_zet(na, zet, chess.Move.from_uci("e5d4"))
    tekst = " ".join(zinnen)
    assert "dame" in tekst and "d4" in tekst and "geslagen" in tekst


def test_geen_feit_geeft_lege_uitleg():
    voor = chess.Board()
    zet = chess.Move.from_uci("a2a3")
    assert u.zin_over_zet(u.feiten_van_zet(voor, zet, door_nova=False)) in ("", None)


def test_mogelijke_zetten_per_stuk():
    bord = chess.Board()
    alles = u.mogelijke_zetten_tekst(bord)
    paard = u.mogelijke_zetten_tekst(bord, chess.KNIGHT)
    assert "e4" in alles
    assert "f3" in paard and "e4" not in paard


@pytest.mark.parametrize("cp,woord", [(0, "gelijk"), (500, "veel beter")])
def test_beoordeel_stand(cp, woord):
    assert woord in u.beoordeel_stand(cp).lower()


@pytest.mark.parametrize("zin,soort", [
    ("wat was de beste zet", "beste_zet_vorige"),
    ("wat is de beste zet nu", "beste_zet_nu"),
    ("waarom speelde je dat", "waarom_nova"),
    ("welke zetten kan ik doen", "mogelijke_zetten"),
    ("welke zetten kan mijn paard doen", "mogelijke_zetten"),
    ("wie staat er beter", "stand"),
])
def test_herken_doorvraag(zin, soort):
    herkend = u.herken_doorvraag(zin, True, False)
    assert herkend and herkend[0] == soort


def test_herken_doorvraag_stuk():
    assert u.herken_doorvraag("welke zetten kan mijn paard doen", True, False)[1]["stuk"] == chess.KNIGHT


def test_zonder_partij_wordt_niets_herkend():
    assert u.herken_doorvraag("wie staat er beter", False, False) is None


def test_terug_zonder_cursor_wordt_ook_herkend():
    # Nova vraagt dan zelf over welke zet het gaat (geen algemene fallback).
    assert u.herken_doorvraag("en daarvoor", True, False)[0] == "terug"
    assert u.herken_doorvraag("en daarvoor", False, False) is None


def test_terug_met_cursor():
    assert u.herken_doorvraag("en daarvoor", True, True)[0] == "terug"
    assert u.herken_doorvraag("en mijn zet", True, True)[0] == "mijn_zet"
    assert u.herken_doorvraag("en jouw zet", True, True)[0] == "jouw_zet"


# ---------------------------------------------------------------- nepmotor
FEN_START = "4k3/8/8/4p3/8/8/8/3QK3 w - - 0 1"


class NepMotor:
    """Antwoordt volgens een script: fen -> (centipawns vanuit wit, eerste zet van de pv)."""

    def __init__(self, script, nova_zet):
        self.script = script
        self.nova_zet = nova_zet

    def analyse(self, bord, limiet):
        cp, pv = self.script.get(bord.fen(), (0, None))
        return {
            "score": chess.engine.PovScore(chess.engine.Cp(cp), chess.WHITE),
            "pv": [chess.Move.from_uci(pv)] if pv else [],
        }

    def play(self, bord, limiet):
        class R:
            pass
        r = R()
        r.move = chess.Move.from_uci(self.nova_zet)
        return r

    def configure(self, opties):
        pass

    def quit(self):
        pass


@pytest.fixture
def omgeving(tmp_path, monkeypatch):
    echte_klasse = ConceptStore
    monkeypatch.setattr(semantic_mod, "ConceptStore",
                        lambda: echte_klasse(str(tmp_path / "data" / "concepts.json"),
                                             str(tmp_path / "logs" / "concepts.jsonl")))
    monkeypatch.setattr(chess_mod, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(chess_mod.ChessModule, "_start_inactivity_watcher", lambda self: None)

    bus = EventBus()
    sem = SemanticConceptsModule(bus)
    sem.sense_engine.add_sense("zet", "een verplaatsing van een stuk", source="user", confidence=1.0)
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

    def start(script, nova_zet, fen=FEN_START):
        motor = NepMotor(script, nova_zet)

        def ensure(self):
            self.engine = motor
            return True
        monkeypatch.setattr(chess_mod.ChessModule, "ensure_engine", ensure)
        router.route({"text": "nieuwe partij"}, "chat_message")
        schaak.board = chess.Board(fen)
        teksten.clear()

    def zeg(zin):
        teksten.clear()
        router.route({"text": zin}, "chat_message")
        return " ".join(teksten)

    yield start, zeg, schaak, last_ctx
    schaak.engine = None   # nepmotor: niets af te sluiten


def _blunder_script():
    voor = chess.Board(FEN_START)
    na = voor.copy()
    na.push_uci("d1d4")
    return {voor.fen(): (900, "d1d2"), na.fen(): (-100, "e5d4")}


# ---------------------------------------------------------------- integratie
def test_na_een_zet_geeft_wat_is_dat_geen_definitie_meer(omgeving):
    start, zeg, _, _ = omgeving
    start(_blunder_script(), "e5d4")
    zeg("d1d4")
    assert "Waar heb je het over" in zeg("wat is dat")


def test_beste_zet_van_de_vorige(omgeving):
    start, zeg, _, _ = omgeving
    start(_blunder_script(), "e5d4")
    zeg("d1d4")
    antwoord = zeg("wat was de beste zet")
    assert "gespeeld" in antwoord and "d2" in antwoord


def test_waarom_blunder_geeft_concrete_reden(omgeving):
    start, zeg, _, _ = omgeving
    start(_blunder_script(), "e5d4")
    zeg("d1d4")
    antwoord = zeg("waarom was dat een blunder")
    assert "geslagen" in antwoord and "dame" in antwoord


def test_waarom_speelde_je_dat(omgeving):
    start, zeg, _, _ = omgeving
    start(_blunder_script(), "e5d4")
    zeg("d1d4")
    antwoord = zeg("waarom speelde je dat")
    assert "Ik speelde" in antwoord and "dame" in antwoord


def test_welke_zetten_kan_ik_doen(omgeving):
    start, zeg, _, _ = omgeving
    start({}, "e5d4")
    assert "d1" in zeg("welke zetten kan ik doen") or "d2" in zeg("welke zetten kan ik doen")


def test_wie_staat_er_beter(omgeving):
    start, zeg, _, _ = omgeving
    start({chess.Board(FEN_START).fen(): (900, None)}, "e5d4")
    assert "beter" in zeg("wie staat er beter").lower()


def test_terug_door_de_zetten(omgeving):
    start, zeg, _, _ = omgeving
    start(_blunder_script(), "e5d4")
    zeg("d1d4")
    zeg("waarom speelde je dat")                 # cursor staat op Nova's zet
    assert "Jij speelde" in zeg("en daarvoor")
    assert "eerste zet" in zeg("en daarvoor")
    assert "Ik speelde" in zeg("en jouw zet")


def test_terug_zonder_cursor_vraagt_over_welke_zet(omgeving):
    start, zeg, _, _ = omgeving
    start({}, "e5d4")
    zeg("d1d4")
    antwoord = zeg("en daarvoor")
    assert "Over welke zet gaat het" in antwoord
    assert "moeite" not in antwoord