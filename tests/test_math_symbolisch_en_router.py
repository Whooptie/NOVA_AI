# tests/test_math_symbolisch_en_router.py
# Dekt twee bugfixes:
#   BUG 1: differentiate() crashte ("argument of type 'Symbol' is not iterable")
#   BUG 2: dubbel antwoord bij de "functienaam-keyword"-tak van detect_math()
import pytest

pytest.importorskip("sympy")

from modules.math.math import MathModule
from core.intent_router import IntentRouter


class FakeBus:
    """Minimale EventBus: onthoudt subscribers en alle gepubliceerde events."""
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


def vraag(bus, expr):
    bus.publish("intent_math", {"expr": expr})
    return bus.antwoorden()[-1]


# ---------- BUG 1: differentiate ----------
def test_differentiate_zonder_variabele(bus):
    antw = vraag(bus, "differentiate(x^3 + 2x)")
    assert "iets mis" not in antw
    assert "3x^2" in antw and "2" in antw


def test_differentiate_met_variabele_x(bus):
    antw = vraag(bus, "differentiate(x^3 + 2x, x)")
    assert "iets mis" not in antw
    assert "3x^2" in antw


def test_differentiate_andere_variabele_wordt_niet_stil_genegeerd(bus):
    antw = vraag(bus, "differentiate(x^3, y)")
    assert "3x^2" not in antw
    assert "x" in antw  # foutmelding noemt de ondersteunde variabele


@pytest.mark.parametrize("expr", [
    "solve_sym(x^2 - 4)",
    "factor_sym(x^2 - 4)",
    "integrate_sym(2x)",
    "simplify_sym(x + x)",
    "expand_sym((x+1)^2)",
])
def test_andere_symbolische_commandos_blijven_werken(bus, expr):
    assert "iets mis" not in vraag(bus, expr)


# ---------- BUG 2: één antwoord bij functienaam-keyword ----------
@pytest.mark.parametrize("zin", [
    "binary_search([1,3,5,7,9], 7)",
    "det([[1,2],[3,4]])",
])
def test_keyword_aanroep_geeft_precies_een_antwoord_en_geen_fallback(bus, router, zin):
    router.route({"text": zin})
    assert len(bus.antwoorden()) == 1
    assert "intent_fallback" not in bus.namen()


def test_binary_search_uitkomst(bus, router):
    router.route({"text": "binary_search([1,3,5,7,9], 7)"})
    assert "3" in bus.antwoorden()[0]


# ---------- Negatieve tests: gewone zinnen niet inslikken ----------
@pytest.mark.parametrize("zin", [
    "wat is de log van mijn dag",
    "ik heb een unit nodig",
    "ik wil dit afronden met round",
])
def test_kaal_keyword_in_gewone_zin_is_geen_rekenvraag(router, bus, zin):
    assert router.detect_math(zin) is not True
    assert "intent_math" not in bus.namen()