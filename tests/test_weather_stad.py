# Tests voor het herkennen van de stad in weer- en regenvragen
# (18 oktober 2026): "in de stad" is geen stad.
import pytest

from modules.weather import rain
from modules.weather.rain import RainModule, vind_stad
from modules.weather.weather import WeatherModule


class NepBus:
    def publish(self, *args, **kwargs):
        pass

    def subscribe(self, *args, **kwargs):
        pass


@pytest.mark.parametrize("zin, verwacht", [
    ("gaat het regenen in gent", "gent"),
    ("Gaat het regenen in Gent?", "gent"),
    ("wat is het weer in brugge vandaag", "brugge"),
    ("gaat het regenen", "Aartrijke"),
    ("moet ik een paraplu meenemen in de stad", "Aartrijke"),
    ("wordt het droog in de middag", "Aartrijke"),
    ("wat is het weer in het weekend", "Aartrijke"),
    ("blijft het droog in de middag in gent", "gent"),
    ("regent het in", "Aartrijke"),
    ("", "Aartrijke"),
])
def test_vind_stad(zin, verwacht):
    assert vind_stad(zin, "Aartrijke") == verwacht


@pytest.mark.parametrize("zin, verwacht", [
    ("gaat het regenen in gent", "gent"),
    ("moet ik een paraplu meenemen in de stad", "Aartrijke"),
])
def test_rain_module_extract_city(zin, verwacht):
    assert RainModule(NepBus()).extract_city(zin) == verwacht


@pytest.mark.parametrize("zin, verwacht", [
    ("wat is het weer in gent", "gent"),
    ("hoe is het weer in de stad", "Aartrijke"),
    ("hoe is het weer in het weekend", "Aartrijke"),
    ("wat is het weer", "Aartrijke"),
])
def test_weather_module_extract_city(zin, verwacht):
    w = WeatherModule(NepBus(), api_key=None)
    assert w.extract_city(zin) == verwacht


def test_lidwoorden_staan_in_de_geen_stad_lijst():
    assert {"de", "het", "een"} <= rain.GEEN_STAD_WOORDEN