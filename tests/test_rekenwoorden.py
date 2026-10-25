# tests/test_rekenwoorden.py
#
# Bug #31 + het kleine deel van punt 10 (25 oktober 2026):
# core/rekenwoorden.py (puur symbolisch) en de koppeling in
# IntentRouter.detect_math().
#
# Uitvoeren: pytest tests/test_rekenwoorden.py -v

import pytest

from core.rekenwoorden import vertaal_rekenzin, getalwoord_naar_int


# ---------- getalwoorden ----------
@pytest.mark.parametrize("woord,verwacht", [
    ("nul", 0), ("een", 1), ("één", 1), ("negen", 9), ("tien", 10),
    ("elf", 11), ("negentien", 19), ("twintig", 20),
    ("eenentwintig", 21), ("tweeëntwintig", 22), ("vierentwintig", 24),
    ("negenennegentig", 99), ("honderd", 100), ("honderdvijf", 105),
    ("driehonderd", 300), ("negenhonderdnegenennegentig", 999),
    ("duizend", 1000), ("tweeduizend", 2000),
    ("tweeduizendvijfhonderd", 2500),
])
def test_getalwoord_naar_int(woord, verwacht):
    assert getalwoord_naar_int(woord) == verwacht


@pytest.mark.parametrize("woord", ["", "blaat", "nulhonderd", "drievijf", "twintigen", "hond"])
def test_geen_getalwoord_geeft_none(woord):
    assert getalwoord_naar_int(woord) is None


# ---------- vertaling ----------
@pytest.mark.parametrize("zin,verwacht", [
    ("wat is drie plus vijf", "3 + 5"),
    ("Wat is drie plus vijf?", "3 + 5"),
    ("hoeveel is twintig gedeeld door vier", "20 / 4"),
    ("wat is zeven maal zes", "7 * 6"),
    ("wat is dertien keer dertien", "13 * 13"),
    ("wat is tweeëntwintig min zeven", "22 - 7"),
    ("wat is tien minus drie", "10 - 3"),
    ("wat is een plus twee", "1 + 2"),
    ("wat is honderdvijf plus tweeduizend vijfhonderd", "105 + 2500"),
    ("wat is 3 plus 5", "3 + 5"),
    ("wat is 2,5 maal 4", "2.5 * 4"),
    ("wat is 2 tot de macht 10", "2 ^ 10"),
    ("wat is vijf min drie maal twee", "5 - 3 * 2"),
    ("drie keer vijf", "3 * 5"),                 # zonder inleiding, met woordoperatie
    # inleiding met symbolen: voorheen "Er ging iets mis: Ongeldige expressie"
    ("wat is 3+5", "3 + 5"),
    ("hoeveel is 3 + 5", "3 + 5"),
    ("bereken 3+5", "3 + 5"),
    ("wat is 9/11", "9 / 11"),
    ("wat is 7*6", "7 * 6"),
    ("wat is 3 x 4", "3 * 4"),
    ("reken uit 2^10", "2 ^ 10"),
])
def test_vertaal_rekenzin(zin, verwacht):
    assert vertaal_rekenzin(zin) == verwacht


@pytest.mark.parametrize("zin", [
    "",
    "3+5",                                    # kale symbolen: bestaand pad
    "10/2",
    "wat is een hond",
    "wat is x plus 3",                        # onbekende term
    "wat is drie plus",                       # onvolledig
    "wat is plus drie",
    "wat is drie plus vijf honden",           # extra woorden: niet raden
    "ik heb drie keer gebeld",
    "wat is er gebeurd op 9/11",              # datumvraag blijft datumvraag
    "gebeurtenissen op 9/11",
    "ik wil twee plus een gratis",
    "wat is twee komma vijf plus een",        # niet ondersteund
    "wat is (3+5)*2",                         # haakjes: niet ondersteund
    "wat is drie vijf plus twee",
])
def test_geen_rekenzin_geeft_none(zin):
    assert vertaal_rekenzin(zin) is None


def test_geen_string_geeft_none():
    assert vertaal_rekenzin(None) is None
    assert vertaal_rekenzin(42) is None


# ---------- koppeling in de router ----------
pytest.importorskip("sympy")

from modules.math.math import MathModule
from core.intent_router import IntentRouter


class FakeBus:
    def __init__(self):
        self.subs = {}
        self.events = []
        self.modules = {}

    def subscribe(self, naam, fn):
        self.subs.setdefault(naam, []).append(fn)

    def publish(self, naam, data=None):
        self.events.append((naam, data))
        for fn in self.subs.get(naam, []):
            fn(data or {}, naam)

    def antwoorden(self):
        return [d["text"] for n, d in self.events if n == "layer4_response"]

    def namen(self):
        return [n for n, _ in self.events]


@pytest.fixture
def bus():
    b = FakeBus()
    MathModule(b)
    return b


@pytest.fixture
def router(bus):
    return IntentRouter(bus)


@pytest.mark.parametrize("zin,verwacht", [
    ("wat is drie plus vijf", "8"),
    ("hoeveel is twintig gedeeld door vier", "5"),
    ("wat is zeven maal zes", "42"),
    ("wat is tweeëntwintig min zeven", "15"),
    ("wat is 3+5", "8"),
    ("bereken 3+5", "8"),
    ("wat is 2 tot de macht 10", "1024"),
])
def test_router_rekent_rekenzinnen_uit(bus, router, zin, verwacht):
    router.route({"text": zin})
    assert "intent_definition" not in bus.namen(), "BUG #31: de zin ging naar de Wikipedia-route"
    assert "intent_fallback" not in bus.namen()
    assert len(bus.antwoorden()) == 1
    assert verwacht in bus.antwoorden()[0]


def test_router_geeft_schone_expressie_door(bus, router):
    router.route({"text": "wat is drie plus vijf"})
    math_events = [d for n, d in bus.events if n == "intent_math"]
    assert math_events == [{"expr": "3 + 5"}]


@pytest.mark.parametrize("zin", ["wat is een hond", "wat is python", "wat is liefde"])
def test_gewone_definitievragen_blijven_definitievragen(bus, router, zin):
    router.route({"text": zin})
    assert "intent_math" not in bus.namen()


def test_datumvraag_9_11_blijft_een_datumvraag(bus, router):
    router.route({"text": "wat is er gebeurd op 9/11"})
    assert "intent_on_this_day_query" in bus.namen()
    assert "intent_math" not in bus.namen()


def test_deling_door_nul_geeft_nette_melding(bus, router):
    router.route({"text": "wat is vijf gedeeld door nul"})
    assert "nul" in bus.antwoorden()[0].lower()