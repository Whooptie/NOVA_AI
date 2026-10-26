# tests/test_intent_router_synoniem_zinsvormen.py
"""
Pytest-suite voor extra zinsvormen bij synoniemen (26 oktober 2026).

Aanleiding: de Nova-benchmark liet zien dat "wat is een ander woord voor zus"
en "wat is het synoniem van X" niet als synoniemvraag werden herkend (ze vielen
door naar intent_definition met het hele zinsdeel als woord).

Uitvoeren: pytest tests/test_intent_router_synoniem_zinsvormen.py -v
"""

import pytest

from core.intent_router import IntentRouter


class DummyEventBus:
    def __init__(self):
        self.modules = {}
        self.gepubliceerd = []

    def subscribe(self, *args, **kwargs):
        pass

    def publish(self, event_type, data=None):
        self.gepubliceerd.append((event_type, data))

    def events(self, naam):
        return [d for t, d in self.gepubliceerd if t == naam]


@pytest.fixture
def router():
    bus = DummyEventBus()
    return IntentRouter(bus), bus


class TestSynoniemZinsvormen:
    @pytest.mark.parametrize("zin,woord", [
        # bestaande vormen blijven werken (regressie)
        ("wat is een synoniem van zus", "zus"),
        ("wat zijn synoniemen van auto", "auto"),
        ("synoniemen van huis", "huis"),
        # nieuwe vormen
        ("wat is het synoniem van zus", "zus"),
        ("wat is een ander woord voor zus", "zus"),
        ("ander woord voor zus", "zus"),
        ("wat is een ander woord voor kunstmatige intelligentie", "kunstmatige intelligentie"),
        ("wat is een ander woord voor zus?", "zus"),
    ])
    def test_synoniem_zinsvormen(self, router, zin, woord):
        r, bus = router
        assert r.detect_definition(zin) is True
        assert bus.events("intent_synonym") == [{"word": woord}]
        assert bus.events("intent_definition") == []

    def test_gewone_definitievraag_blijft_definitie(self, router):
        """Regressie: 'wat is een ander ...' zonder 'woord voor' blijft een definitie."""
        r, bus = router
        r.detect_definition("wat is een anker")
        assert bus.events("intent_synonym") == []
        assert bus.events("intent_definition") != []

    @pytest.mark.parametrize("zin", [
        "wat is een ander woord voor tijd",
        "wat is het synoniem van tijd",
    ])
    def test_geen_klokvraag_bij_synoniem_van_tijd(self, router, zin):
        """Zoals 'waartoe leidt tijd': kennisvraag, geen vraag naar de klok."""
        r, bus = router
        assert r.detect_time(zin) is False