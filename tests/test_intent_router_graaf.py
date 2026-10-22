"""Tests voor Semantic Fase 13.3: de graaf-commando's in intent_router.py (stap 2K)."""

import pytest

from core.intent_router import IntentRouter


class NepBus:
    def __init__(self):
        self.gepubliceerd = []
        self.modules = {}

    def subscribe(self, naam, functie):
        pass

    def publish(self, naam, data=None):
        self.gepubliceerd.append((naam, data or {}))

    def events(self, naam):
        return [d for n, d in self.gepubliceerd if n == naam]


class NepSemantic:
    """Kent een paar concepten; pending_reactivation bestaat (route() leest dat)."""
    pending_reactivation = None

    def __init__(self, bekend=("fiets", "auto", "zwart gat", "zintuig")):
        self.bekend = set(bekend)

    def get_senses(self, woord):
        return [object()] if woord in self.bekend else []

    def _detect_relation(self, text):       # zou de RelationParser voorstellen
        self.laatste_relatie_tekst = text
        return False


@pytest.fixture
def router():
    bus = NepBus()
    return IntentRouter(bus, semantic_module=NepSemantic()), bus


def _route(router_bus, tekst):
    router, bus = router_bus
    bus.gepubliceerd.clear()
    router.route({"text": tekst})
    return bus


@pytest.mark.parametrize("tekst,woord,diepte", [
    ("toon graaf van fiets", "fiets", 1),
    ("Toon de graaf van fiets", "fiets", 1),
    ("toon graaf van fiets diepte 2", "fiets", 2),
    ("toon graaf van fiets met diepte 3", "fiets", 3),
    ("laat de graaf van fiets zien", "fiets", 1),
    ("toon me de kennisgraaf van de fiets", "fiets", 1),
    ("graaf van fiets", "fiets", 1),
    ("visualiseer fiets", "fiets", 1),
    ("toon graaf van zwart gat", "zwart gat", 1),
    ("toon graaf van zwart gat diepte 2", "zwart gat", 2),
    ("toon graaf van zintuigen", "zintuig", 1),          # meervoud -> enkelvoud
])
def test_toon_graaf(router, tekst, woord, diepte):
    bus = _route(router, tekst)
    assert bus.events("intent_graph_show") == [{"word": woord, "diepte": diepte}]
    assert bus.events("topic_detected:graaf_toon")


@pytest.mark.parametrize("tekst,a,b", [
    ("hoe zijn fiets en auto verbonden", "fiets", "auto"),
    ("hoe zijn fiets en auto met elkaar verbonden?", "fiets", "auto"),
    ("hoe hangen fiets en auto samen", "fiets", "auto"),
    ("pad tussen fiets en auto", "fiets", "auto"),
    ("toon het pad van fiets naar auto", "fiets", "auto"),
    ("zoek de verbinding tussen fiets en zwart gat", "fiets", "zwart gat"),
    ("hoe zijn zwart gat en fiets verbonden", "zwart gat", "fiets"),
])
def test_pad(router, tekst, a, b):
    bus = _route(router, tekst)
    assert bus.events("intent_graph_path") == [{"word_a": a, "word_b": b}]
    assert bus.events("topic_detected:graaf_pad")


def test_pad_wordt_niet_als_is_a_uitspraak_gelezen(router):
    """Het hele punt van stap 2K: 'zijn' mag nooit bij de RelationParser (stap 9) terechtkomen."""
    r, bus = router
    _route(router, "hoe zijn fiets en auto verbonden")
    assert not hasattr(r.semantic, "laatste_relatie_tekst")


@pytest.mark.parametrize("tekst", [
    "graaf statistieken", "toon graaf statistieken", "kennisgraaf statistieken",
    "statistieken van de graaf", "hoe groot is je kennisgraaf", "hoe dicht is je graaf",
])
def test_statistieken(router, tekst):
    bus = _route(router, tekst)
    assert bus.events("intent_graph_stats") == [{}]
    assert bus.events("topic_detected:graaf_stats")


@pytest.mark.parametrize("tekst", [
    "toon graaf van het",           # stopwoord als onderwerp
    "hoe zijn het en dat verbonden",
    "wat is een graaf",
    "toon het weer",
    "hoe zijn jullie",
])
def test_geen_graaf_commando(router, tekst):
    bus = _route(router, tekst)
    assert not bus.events("intent_graph_show")
    assert not bus.events("intent_graph_path")
    assert not bus.events("intent_graph_stats")


@pytest.mark.parametrize("tekst", [
    "wat is een fiets", "hoe zeker ben je dat een fiets een voertuig is",
    "zoek gelijkenissen voor fiets", "extraheer fiets", "help",
])
def test_bestaande_commandos_blijven_werken(router, tekst):
    bus = _route(router, tekst)
    assert not bus.events("intent_graph_show") and not bus.events("intent_graph_path")