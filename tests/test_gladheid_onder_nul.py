"""Tests voor punt 48: gladheid ook ONDER 0 graden (rain.py en weather.py)."""
from datetime import datetime, timedelta

import pytest

from modules.weather import rain
from modules.weather.rain import Weerpunt, is_glad, analyseer_gevaar
from modules.weather.weather import WeatherModule


NU = datetime(2026, 12, 10, 12, 0)


class FakeBus:
    def subscribe(self, *a, **k):
        pass

    def publish(self, *a, **k):
        pass


def punt(temp, neerslag=0.5):
    return Weerpunt(NU, NU + timedelta(minutes=15), temp, neerslag, 3.0, 5.0)


@pytest.mark.parametrize("temp", [-10, -3.5, -0.1, 0, 1, 2])
def test_is_glad_met_neerslag(temp):
    assert is_glad(punt(temp)) is True


@pytest.mark.parametrize("temp", [2.1, 5, 15])
def test_is_niet_glad_boven_twee_graden(temp):
    assert is_glad(punt(temp)) is False


def test_droge_vorst_is_niet_glad():
    assert is_glad(punt(-5, neerslag=0.0)) is False


def test_ontbrekende_waarden_zijn_niet_glad():
    assert is_glad(punt(None)) is False
    assert is_glad(punt(-2, neerslag=None)) is False


def test_analyseer_gevaar_vindt_gladheid_bij_vorst():
    punten = [
        Weerpunt(NU + timedelta(minutes=15 * i), NU + timedelta(minutes=15 * (i + 1)),
                 -3.0, 0.4 if i >= 2 else 0.0, 2.0, 4.0)
        for i in range(8)
    ]
    info = analyseer_gevaar(punten, NU)
    assert info["gladheid"] is not None
    assert info["gladheid"]["begin_min"] == 30
    assert info["gladheid"]["temp"] == -3.0


@pytest.fixture
def weer():
    return WeatherModule(FakeBus(), "geen-sleutel")


@pytest.mark.parametrize("temp", [-8, -1, 0, 2])
def test_weerwaarschuwing_gladheid_ook_onder_nul(weer, temp):
    zin = weer.weerwaarschuwing("Rain", temperatuur=temp, heeft_neerslag=True)
    assert zin is not None and "gladheid" in zin


def test_weerwaarschuwing_geen_gladheid_zonder_neerslag(weer):
    zin = weer.weerwaarschuwing("Clear", temperatuur=-5, heeft_neerslag=False)
    assert zin is None or "gladheid" not in zin


def test_weerwaarschuwing_geen_gladheid_boven_twee(weer):
    zin = weer.weerwaarschuwing("Rain", temperatuur=4, heeft_neerslag=True)
    assert zin is None or "gladheid" not in zin


def test_weather_en_rain_gebruiken_dezelfde_grenzen(weer, monkeypatch):
    # Verschuif de grens in rain.py: weather.py moet meebewegen.
    monkeypatch.setattr(rain, "GLADHEID_MAX_C", 5)
    zin = weer.weerwaarschuwing("Rain", temperatuur=4, heeft_neerslag=True)
    assert zin is not None and "gladheid" in zin