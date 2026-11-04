"""Tests voor punt 62d: vervolgvragen op de laatste kennisvraag."""
import pytest

from core import context_resolver as cr
from core.last_context import LastContext
from core import intent_router as ir


# ---------------------------------------------------------------- herken_vraag
@pytest.mark.parametrize("zin,verwacht", [
    ("wat is een hond", ("wat is {x}", "een hond", "np")),
    ("Wat is een hond?", ("wat is {x}", "een hond", "np")),
    ("is een zebra een dier", ("is {x} een dier", "een zebra", "np")),
    ("wat veroorzaakt regen", ("wat veroorzaakt {x}", "regen", "kaal")),
    ("wat zijn de gevolgen van regen", ("wat zijn de gevolgen van {x}", "regen", "kaal")),
    ("wat is een synoniem van groot", ("wat is een synoniem van {x}", "groot", "kaal")),
])
def test_herken_vraag(zin, verwacht):
    assert cr.herken_vraag(zin) == verwacht


@pytest.mark.parametrize("zin", [
    "wat is dat", "is dat een dier", "hallo", "en een kat?", "wat is het",
    "hoe laat is het", "wat is de zin van het leven in een grote stad",
])
def test_herken_vraag_negatief(zin):
    assert cr.herken_vraag(zin) is None


# ---------------------------------------------------------------- los_op
KADER_DEF = ("wat is {x}", "een hond", "np")
KADER_REL = ("is {x} een dier", "een zebra", "np")
KADER_GEVOLG = ("wat zijn de gevolgen van {x}", "regen", "kaal")


@pytest.mark.parametrize("tekst,kader,verwacht,regel", [
    ("en een kat?", KADER_DEF, "wat is een kat", "ellips"),
    ("en dan een kat", KADER_DEF, "wat is een kat", "ellips"),
    ("en een kat?", KADER_REL, "is een kat een dier", "ellips"),
    ("en brand?", KADER_GEVOLG, "wat zijn de gevolgen van brand", "ellips"),
    ("en een brand?", KADER_GEVOLG, "wat zijn de gevolgen van brand", "ellips"),
    ("is dat een dier", KADER_DEF, "is een hond een dier", "relatie_verwijzing"),
    ("is dat dan ook een zoogdier", KADER_DEF, "is een hond een zoogdier", "relatie_verwijzing"),
    ("wat is het gevolg ervan", ("wat is {x}", "regen", "kaal"),
     "wat zijn de gevolgen van regen", "gevolg_verwijzing"),
    ("wat is de oorzaak ervan", ("wat is {x}", "een brand", "np"),
     "wat veroorzaakt brand", "oorzaak_verwijzing"),
])
def test_los_op_positief(tekst, kader, verwacht, regel):
    assert cr.los_op(tekst, *kader) == (verwacht, regel)


@pytest.mark.parametrize("tekst", [
    "en dat?", "en hoe?", "en", "hallo nova", "wat is een kat", "is dat",
    "en wat eten die", "is dat een", "wat is een tijger",
])
def test_los_op_laat_rest_ongemoeid(tekst):
    assert cr.los_op(tekst, *KADER_DEF) is None


def test_los_op_zonder_kader():
    assert cr.los_op("en een kat?", "", "", "np") is None


def test_relatie_verwijzing_niet_na_gevolgvraag():
    # Na "gevolgen van regen" (soort kaal) is "is dat een dier" niet zinvol.
    assert cr.los_op("is dat een dier", *KADER_GEVOLG) is None


# ---------------------------------------------------------------- LastContext
def test_lastcontext_vraag_onthouden_en_verlopen():
    lc = LastContext()
    assert lc.get_vraag() is None
    lc.set_vraag(*KADER_DEF)
    assert lc.get_vraag() == KADER_DEF
    lc._laatste_update -= LastContext.VERVAL_SECONDEN + 1
    assert lc.get_vraag() is None


def test_lastcontext_vraag_leeg_negeren_en_clear():
    lc = LastContext()
    lc.set_vraag("", "x", "np")
    assert lc.get_vraag() is None
    lc.set_vraag(*KADER_DEF)
    lc.clear()
    assert lc.get_vraag() is None


# ---------------------------------------------------------------- router
class _Bus:
    def __init__(self):
        self.events = []
        self.modules = {}

    def publish(self, naam, data=None, *a, **k):
        self.events.append((naam, data))

    def subscribe(self, *a, **k):
        pass


def _router(met_context=True):
    bus = _Bus()
    lc = LastContext(bus)
    if met_context:
        bus.modules["last_context"] = lc
    return ir.IntentRouter(bus), lc


def test_router_vervolgvraag_herschrijft():
    r, lc = _router()
    assert r._verwerk_vervolgvraag("wat is een hond") == "wat is een hond"
    assert lc.get_vraag() == KADER_DEF
    assert r._verwerk_vervolgvraag("en een kat?") == "wat is een kat"
    assert any(n == "context_resolved" for n, _ in r.event_bus.events)


def test_router_keten_en_een_kat_en_een_bank():
    r, lc = _router()
    r._verwerk_vervolgvraag("is een zebra een dier")
    assert r._verwerk_vervolgvraag("en een kat?") == "is een kat een dier"
    assert r._verwerk_vervolgvraag("en een bank?") == "is een bank een dier"


def test_router_zonder_kader_verandert_niets():
    r, _ = _router()
    assert r._verwerk_vervolgvraag("en een kat?") == "en een kat?"


def test_router_zonder_last_context_module():
    r, _ = _router(met_context=False)
    assert r._verwerk_vervolgvraag("en een kat?") == "en een kat?"


def test_router_verlopen_kader_verandert_niets():
    r, lc = _router()
    r._verwerk_vervolgvraag("wat is een hond")
    lc._laatste_update -= LastContext.VERVAL_SECONDEN + 1
    assert r._verwerk_vervolgvraag("en een kat?") == "en een kat?"