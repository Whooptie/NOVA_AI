"""Tests voor ronde 2 van punt 62d: meer manieren om een vervolgvraag te stellen.

De voorbeelden zijn bewust NIET de zinnen uit de blinde batch van Grok: ze volgen
dezelfde families met eigen woorden, zodat de regels algemeen blijven.
"""
import pytest

from core import context_resolver as cr
from core.last_context import LastContext
from core import intent_router as ir

DEF = ("wat is {x}", "een hond", "np")
GEVOLG = ("wat zijn de gevolgen van {x}", "regen", "kaal")


# ---- familie 2: andere inleidingen voor een nieuw onderwerp ----
@pytest.mark.parametrize("tekst,verwacht", [
    ("hoe zit dat met een paard", "wat is een paard"),
    ("hoe zit het dan met een paard", "wat is een paard"),
    ("hoe is het met een paard", "wat is een paard"),
    ("wat dacht je van een konijn", "wat is een konijn"),
    ("en wat denk je van een konijn", "wat is een konijn"),
    ("idem voor een vis", "wat is een vis"),
    ("idem met een vis", "wat is een vis"),
    ("hetzelfde voor een vis", "wat is een vis"),
    ("ok en een krant", "wat is een krant"),
    ("oke, en een krant", "wat is een krant"),
    ("nou dan een tafel", "wat is een tafel"),
    ("ook voor een tafel", "wat is een tafel"),
])
def test_ellips_inleidingen(tekst, verwacht):
    assert cr.los_op(tekst, *DEF) == (verwacht, "ellips")


def test_ellips_in_gevolgvraag_geeft_kaal_onderwerp():
    assert cr.los_op("idem voor brand", *GEVOLG) == ("wat zijn de gevolgen van brand", "ellips")


# ---- familie 1: oorzaak/gevolg met een verwijswoord ----
@pytest.mark.parametrize("tekst,verwacht,regel", [
    ("waardoor ontstaat dat", "wat veroorzaakt regen", "oorzaak_verwijzing"),
    ("waardoor komt dat", "wat veroorzaakt regen", "oorzaak_verwijzing"),
    ("en waardoor is dat", "wat veroorzaakt regen", "oorzaak_verwijzing"),
    ("wat zorgt hiervoor", "wat veroorzaakt regen", "oorzaak_verwijzing"),
    ("wat zorgt ervoor", "wat veroorzaakt regen", "oorzaak_verwijzing"),
    ("hoe ontstaat dit", "wat veroorzaakt regen", "oorzaak_verwijzing"),
    ("wat veroorzaakt dat", "wat veroorzaakt regen", "oorzaak_verwijzing"),
    ("wat gebeurt er daardoor", "wat zijn de gevolgen van regen", "gevolg_verwijzing"),
    ("en wat komt er dan", "wat zijn de gevolgen van regen", "gevolg_verwijzing"),
    ("wat volgt er daarop", "wat zijn de gevolgen van regen", "gevolg_verwijzing"),
    ("wat komt er van", "wat zijn de gevolgen van regen", "gevolg_verwijzing"),
    ("wat heeft dat voor gevolgen", "wat zijn de gevolgen van regen", "gevolg_verwijzing"),
    ("wat is het resultaat ervan", "wat zijn de gevolgen van regen", "gevolg_verwijzing"),
])
def test_oorzaak_en_gevolg_verwijzingen(tekst, verwacht, regel):
    assert cr.los_op(tekst, *GEVOLG) == (verwacht, regel)


# ---- familie 4: synoniem en afgebroken zinnen ----
@pytest.mark.parametrize("tekst", [
    "wat is een ander woord voor",
    "wat is een ander woord ervoor",
    "en wat is een ander woord daarvoor",
    "welk woord betekent hetzelfde",
    "welk woord heeft dezelfde betekenis",
    "wat is een synoniem",
])
def test_synoniem_verwijzingen(tekst):
    assert cr.los_op(tekst, *DEF) == ("wat is een synoniem van hond", "synoniem_verwijzing")


# ---- grenzen: dit mag NIET herschreven worden ----
@pytest.mark.parametrize("tekst", [
    "en nu?", "ok dan", "dan toch", "en misschien", "ja en", "idem", "nou en",
    "wat is een ander woord voor huis",   # volledige vraag: de normalizer/router doet dit
    "waardoor ontstaat modder",           # volledige vraag
    "is dat waar",                        # geen lidwoord + geen begrip
    "is dat leuk",
])
def test_grenzen_blijven_ongewijzigd(tekst):
    assert cr.los_op(tekst, *DEF) is None


def test_is_verwijzing_zonder_onderwerp():
    for zin in ["waardoor ontstaat dat", "wat is een ander woord voor", "wat komt er van",
                "ok wat zorgt ervoor", "welk woord betekent hetzelfde"]:
        assert cr.is_verwijzing_zonder_onderwerp(zin), zin
    for zin in ["waardoor ontstaat modder", "wat is een hond", "en een kat?", "is dat een dier"]:
        assert not cr.is_verwijzing_zonder_onderwerp(zin), zin


# ---- router: eerlijk terugvragen zonder onthouden vraag (punt 74) ----
class _Bus:
    def __init__(self):
        self.events = []
        self.modules = {}

    def publish(self, naam, data=None, *a, **k):
        self.events.append((naam, data))

    def subscribe(self, *a, **k):
        pass


def _router():
    bus = _Bus()
    bus.modules["last_context"] = LastContext(bus)
    return ir.IntentRouter(bus)


def test_router_verwijzing_zonder_kader_vraagt_terug():
    r = _router()
    assert r._verwerk_vervolgvraag("wat is een ander woord voor") is None
    antwoorden = [d["text"] for n, d in r.event_bus.events if n == "chat_response"]
    assert len(antwoorden) == 1 and antwoorden[0].startswith("Waar heb je het over")


def test_router_vervolg_met_kader_wordt_opgelost():
    r = _router()
    r._verwerk_vervolgvraag("wat is een hond")
    assert r._verwerk_vervolgvraag("wat is een ander woord voor") == "wat is een synoniem van hond"
    assert r._verwerk_vervolgvraag("idem voor een kat") == "wat is een synoniem van kat"


def test_router_volledige_vraag_zonder_kader_blijft_gewoon():
    r = _router()
    assert r._verwerk_vervolgvraag("waardoor ontstaat modder") == "waardoor ontstaat modder"


# ---- punt 74: een vraag is nooit een leerzin ----
@pytest.mark.parametrize("zin,is_vraag", [
    ("en wat is een ander woord ervoor", True),
    ("wat is een hond", True),
    ("waarom is een zebra een dier", True),
    ("hoe heet dat", True),
    ("een hond is een dier?", True),
    ("een hond is een dier", False),
    ("een kat is een zoogdier", False),
])
def test_vraagzin_wordt_nooit_geleerd(zin, is_vraag):
    from core.semantic import SemanticConceptsModule as M
    # _is_vraagzin gebruikt alleen een klassenpatroon; de klasse zelf volstaat als 'self'.
    assert M._is_vraagzin(M, zin) is is_vraag