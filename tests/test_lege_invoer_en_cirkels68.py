# tests/test_lege_invoer_en_cirkels68.py
"""
Punt 68 (5 november 2026).

(a) Een lege invoer (alleen Enter, of enkel spaties) wordt genegeerd: geen
    fallback, geen antwoord, geen raw_user_message-event.
(b) Een is_a- of part_of-cirkel wordt door ÉÉN woord gemeld, het alfabetisch
    eerste woord van de cirkel -- niet meer vanuit elk woord van de cirkel.

Alles draait op een tijdelijke concepts.json (tmp_path); je echte data wordt
nooit aangeraakt.
"""
from pathlib import Path

import pytest

from core.intent_router import IntentRouter
from core.semantic import ConceptStore, SenseEngine, RelationEngine, ReasoningEngine
from modules.knowledge.contradiction_checker import ContradictionChecker


# ---------------------------------------------------------------- (a) lege invoer
class DummyEventBus:
    def __init__(self):
        self.modules = {}
        self.gepubliceerd = []

    def subscribe(self, *args, **kwargs):
        pass

    def publish(self, event_type, data=None):
        self.gepubliceerd.append((event_type, data))

    def namen(self):
        return [t for t, _ in self.gepubliceerd]


@pytest.fixture
def router():
    bus = DummyEventBus()
    return IntentRouter(bus), bus


@pytest.mark.parametrize("data", [
    {"text": ""},
    {"text": "   "},
    {"text": "\t\n"},
    {"text": None},
    {},
    None,
])
def test_lege_invoer_geeft_geen_enkele_reactie(router, data):
    r, bus = router
    r.route(data, "chat_message")
    assert bus.gepubliceerd == []


def test_gewone_invoer_loopt_nog_steeds_door_de_router(router):
    r, bus = router
    r.route({"text": "hallo"}, "chat_message")
    assert "raw_user_message" in bus.namen()


def test_lege_invoer_laat_een_open_vraag_staan(router):
    class OpenVraag:
        def __init__(self):
            self.aangeroepen = False

        def is_open(self):
            self.aangeroepen = True
            return True

    r, bus = router
    vraag = OpenVraag()
    bus.modules["pending_question"] = vraag
    r.route({"text": ""}, "chat_message")
    assert vraag.aangeroepen is False      # de pending-logica wordt niet eens bereikt


def test_hoofdlus_in_main_slaat_lege_invoer_over():
    bron = (Path(__file__).resolve().parent.parent / "main.py").read_text(encoding="utf-8")
    assert "if not user_input.strip():\n            continue" in bron
    # en de check staat VOOR het publiceren van het bericht
    assert bron.index("if not user_input.strip():") < bron.index('bus.publish("chat_message"')


# ---------------------------------------------------------------- (b) cirkels
@pytest.fixture
def delen(tmp_path):
    store = ConceptStore(
        concepts_file=str(tmp_path / "concepts.json"),
        log_file=str(tmp_path / "concepts.jsonl"),
    )
    se = SenseEngine(store)
    re_ = RelationEngine(store, se)
    rs = ReasoningEngine(store, re_)
    return store, se, re_, rs


def _woorden(se, *woorden):
    for w in woorden:
        se.add_sense(w, f"definitie van {w}", source="user")


def _cirkels(rs, store, soort):
    """Alle cirkel-meldingen van een soort, over alle woorden heen."""
    gevonden = []
    for w in store.concepts.keys():
        gevonden += [c for c in rs.find_contradictions(w) if c["type"] == soort]
    return gevonden


@pytest.mark.parametrize("relatie, soort", [("is_a", "is_a_cirkel"), ("part_of", "part_of_cirkel")])
def test_tweewoord_cirkel_wordt_een_keer_gemeld(delen, relatie, soort):
    store, se, re_, rs = delen
    _woorden(se, "hond", "dier")
    re_.add_relation("hond", relatie, "dier")
    re_.add_relation("dier", relatie, "hond")
    gevonden = _cirkels(rs, store, soort)
    assert len(gevonden) == 1
    assert gevonden[0]["word"] == "dier"          # alfabetisch eerste


@pytest.mark.parametrize("relatie, soort", [("is_a", "is_a_cirkel"), ("part_of", "part_of_cirkel")])
def test_driewoord_cirkel_wordt_een_keer_gemeld(delen, relatie, soort):
    store, se, re_, rs = delen
    _woorden(se, "a", "b", "c")
    re_.add_relation("a", relatie, "b")
    re_.add_relation("b", relatie, "c")
    re_.add_relation("c", relatie, "a")
    gevonden = _cirkels(rs, store, soort)
    assert len(gevonden) == 1
    assert gevonden[0]["word"] == "a"


def test_woord_buiten_de_cirkel_meldt_hem_niet(delen):
    store, se, re_, rs = delen
    _woorden(se, "a", "b", "staart")
    re_.add_relation("a", "is_a", "b")
    re_.add_relation("b", "is_a", "a")
    re_.add_relation("staart", "is_a", "a")      # hangt eraan, zit niet in de cirkel
    namen = [c["word"] for c in _cirkels(rs, store, "is_a_cirkel")]
    assert namen == ["a"]


def test_twee_aparte_cirkels_geven_twee_meldingen(delen):
    store, se, re_, rs = delen
    _woorden(se, "a", "b", "x", "y")
    re_.add_relation("a", "is_a", "b")
    re_.add_relation("b", "is_a", "a")
    re_.add_relation("x", "is_a", "y")
    re_.add_relation("y", "is_a", "x")
    namen = sorted(c["word"] for c in _cirkels(rs, store, "is_a_cirkel"))
    assert namen == ["a", "x"]


def test_een_woord_dat_zichzelf_is_blijft_gemeld(delen):
    store, se, re_, rs = delen
    _woorden(se, "hond")
    re_.add_relation("hond", "is_a", "hond")
    assert [c["word"] for c in _cirkels(rs, store, "is_a_cirkel")] == ["hond"]


def test_checker_geeft_een_melding_met_een_weerleg_voorstel(delen, tmp_path):
    store, se, re_, rs = delen
    _woorden(se, "hond", "dier")
    re_.add_relation("hond", "is_a", "dier")
    re_.add_relation("dier", "is_a", "hond")

    class Semantic:
        pass

    sem = Semantic()
    sem.store = store
    sem.find_contradictions = rs.find_contradictions

    bus = DummyEventBus()
    checker = ContradictionChecker(bus, sem)
    checker.state_pad = tmp_path / "contradiction_state.json"
    checker._al_gemelde_conflicten = set()
    checker.check_contradictions()

    berichten = [d["text"] for t, d in bus.gepubliceerd if t == "layer4_response"]
    assert len(berichten) == 1
    assert berichten[0].count("weerleg:") == 1