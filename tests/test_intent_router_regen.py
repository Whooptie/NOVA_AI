# tests/test_intent_router_regen.py
"""
pytest-tests voor IntentRouter.detect_rain() (regenvragen -> intent_rain).

Risico-afweging: detect_rain() staat in de intent-tabel VOOR detect_weather()
en kijkt naar losse woorden zoals "regen" en "weer". Een fout hier merk je
niet meteen: Nova beantwoordt dan ofwel een gewone zin als regenvraag, of
"wanneer is het weer droog" belandt bij de verkeerde module. Daarom testen
we zowel wat WEL als wat NIET als regenvraag telt.
"""

import pytest

from core.intent_router import IntentRouter


class DummyEventBus:
    def __init__(self):
        self.gepubliceerd = []
        self.modules = {}

    def subscribe(self, *args, **kwargs):
        pass

    def publish(self, event, data=None):
        self.gepubliceerd.append((event, data))


@pytest.fixture
def bus():
    return DummyEventBus()


@pytest.fixture
def router(bus):
    return IntentRouter(bus)


@pytest.mark.parametrize(
    "tekst",
    [
        "gaat het regenen",
        "Gaat het regenen?",
        "regent het",
        "regent het in gent",
        "wanneer stopt het met regenen",
        "wanneer stopt de regen",
        "wanneer houdt het op met regenen",
        "wanneer houdt de regen op",
        "wanneer is het weer droog",
        "wanneer klaart het op",
        "hoe lang blijft het nog regenen",
        "blijft het droog vandaag",
        "komt er een bui aan",
        "gaat het weer regenen",
    ],
)
def test_regenvraag_gaat_naar_intent_rain(router, bus, tekst):
    assert router.detect_rain(tekst) is True
    assert bus.gepubliceerd == [("intent_rain", {"text": tekst})]


@pytest.mark.parametrize(
    "tekst",
    ["gaat het morgen regenen", "regent het overmorgen?", "gaat het zaterdag regenen"],
)
def test_regenvraag_met_dagwoord_gaat_naar_de_weermodule(router, bus, tekst):
    # De radar kijkt maar ~2 uur vooruit; een dag-voorspelling is voor weather.py.
    assert router.detect_rain(tekst) is True
    assert bus.gepubliceerd == [("intent_weather", {"text": tekst})]


@pytest.mark.parametrize(
    "tekst",
    [
        "wat is het weer",
        "wat is het weer morgen",
        "is het droog",
        "wat is regen",
        "leg uit hoe regen ontstaat",
        "regen is water",
        "onthoud regen is nat",
        "hou je van regen?",
        "ik vind regen leuk",
        "hallo",
        "",
    ],
)
def test_geen_regenvraag(router, bus, tekst):
    assert router.detect_rain(tekst) is False
    assert bus.gepubliceerd == []


def test_rain_staat_in_de_intent_tabel_voor_weather(router):
    namen = [naam for naam, _ in router._intent_tabel_deel1]
    assert "rain" in namen
    assert namen.index("rain") < namen.index("weather")