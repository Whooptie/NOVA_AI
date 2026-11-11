# tests/test_snelle_activiteit29.py
"""
Punt 29 (11 november 2026): de activiteit (vergrendeld/ontgrendeld) wordt elke
ACTIVITEIT_SNEL_INTERVAL_SECONDEN seconden bekeken in een eigen lus, los van de
60-secondenlus. Zo komt "welkom terug" niet meer tot een minuut te laat.

De tests slapen niet echt: slaap en blijf_draaien zijn injecteerbaar.
"""
from unittest.mock import MagicMock

import main


def _loader(detector):
    loader = MagicMock()
    loader.loaded_modules = {"activity_detector": detector} if detector is not None else {}
    return loader


def _lus(loader, aantal_rondes):
    """Draait de snelle lus voor precies aantal_rondes metingen. De lus slaapt er een keer
    meer (de laatste slaap wordt gevolgd door het stopsignaal, zonder meting)."""
    slaaptijden = []
    rondes = {"n": 0}

    def slaap(seconden):
        slaaptijden.append(seconden)
        rondes["n"] += 1

    main.snelle_activiteit_loop(loader, slaap=slaap, blijf_draaien=lambda: rondes["n"] < aantal_rondes + 1)
    return slaaptijden


def test_interval_is_kort_maar_niet_korter_dan_de_client_stuurt():
    assert 1 <= main.ACTIVITEIT_SNEL_INTERVAL_SECONDEN <= 15


def test_detect_activity_wordt_elke_ronde_aangeroepen():
    detector = MagicMock()
    slaaptijden = _lus(_loader(detector), 3)
    assert detector.detect_activity.call_count == 3
    assert slaaptijden == [main.ACTIVITEIT_SNEL_INTERVAL_SECONDEN] * 4


def test_een_fout_stopt_de_lus_niet(capsys):
    detector = MagicMock()
    detector.detect_activity.side_effect = [RuntimeError("kapot"), None, None]
    _lus(_loader(detector), 3)
    assert detector.detect_activity.call_count == 3
    assert "Fout in detect_activity()" in capsys.readouterr().out


def test_zonder_detector_gebeurt_er_niets():
    _lus(_loader(None), 2)          # geen crash


def test_module_wordt_elke_ronde_opnieuw_opgezocht():
    # De detector kan pas na het opstarten geladen zijn.
    loader = _loader(None)
    detector = MagicMock()
    rondes = {"n": 0}

    def slaap(_):
        rondes["n"] += 1
        if rondes["n"] == 2:
            loader.loaded_modules["activity_detector"] = detector

    main.snelle_activiteit_loop(loader, slaap=slaap, blijf_draaien=lambda: rondes["n"] < 4)
    assert detector.detect_activity.call_count == 2
    