# tests/test_main_ochtend.py
"""
Tests voor de ochtendsamenvatting-aansluiting in main.py (18 oktober 2026):

  - de "aantal_loops % OCHTEND_CHECK_INTERVAL_MINUTEN == 0"-gate in
    achtergrond_loop()
  - _layer5_laat_spreken_toe(): vraagt aan Layer 5 (context_manager.
    can_interrupt()) of Nova nu spontaan mag spreken

Risico-afweging: dit is de schakel tussen "er is een weerbericht" en "Nova
zegt het hardop". Zit de gate verkeerd, dan komt het bericht nooit; zit
_layer5_laat_spreken_toe() verkeerd (bv. een tuple die altijd 'waar' is),
dan spreekt Nova tegen een lege kamer. Beide zijn stille fouten.

Zelfde aanpak als test_main_achtergrond_en_response.py: time.sleep() wordt
vervangen zodat de oneindige lus na een vast aantal rondes stopt.

Uitvoeren (vanuit de projectroot):

    pytest tests/test_main_ochtend.py -v
"""

import io
import sys
from unittest.mock import MagicMock, patch

import pytest

import main


class _StopLus(Exception):
    """Stopt de 'while True' in achtergrond_loop() gecontroleerd."""


def _draai_lus(modules_dict, aantal_rondes):
    """Draait achtergrond_loop() precies 'aantal_rondes' rondes (aantal_loops
    loopt dus van 1 tot en met aantal_rondes). Geeft alles terug wat er
    geprint werd."""
    loader = MagicMock()
    loader.loaded_modules = dict(modules_dict)

    teller = {"n": 0}

    def sleep_side_effect(*args, **kwargs):
        teller["n"] += 1
        if teller["n"] > aantal_rondes:
            raise _StopLus

    oude_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()
    try:
        with patch("main.time.sleep", side_effect=sleep_side_effect):
            with pytest.raises(_StopLus):
                main.achtergrond_loop(loader)
    finally:
        sys.stdout = oude_stdout
    return loader, buffer.getvalue()


def _loader_met(modules):
    loader = MagicMock()
    loader.loaded_modules = dict(modules)
    return loader


# =================================================================
# De gate in achtergrond_loop()
# =================================================================

def test_ochtend_interval_is_een_positief_getal():
    assert isinstance(main.OCHTEND_CHECK_INTERVAL_MINUTEN, int)
    assert main.OCHTEND_CHECK_INTERVAL_MINUTEN >= 1


def test_ochtend_gate_triggert_bij_deelbare_loop_waarde():
    weather = MagicMock()
    _draai_lus({"weather": weather}, aantal_rondes=main.OCHTEND_CHECK_INTERVAL_MINUTEN)
    weather.check_ochtend_samenvatting.assert_called_once()


def test_ochtend_gate_triggert_niet_bij_niet_deelbare_loop_waarde():
    if main.OCHTEND_CHECK_INTERVAL_MINUTEN <= 1:
        pytest.skip("Interval is 1: elke waarde is deelbaar.")
    weather = MagicMock()
    _draai_lus({"weather": weather}, aantal_rondes=main.OCHTEND_CHECK_INTERVAL_MINUTEN - 1)
    weather.check_ochtend_samenvatting.assert_not_called()


def test_ochtend_gate_triggert_elke_interval_opnieuw():
    weather = MagicMock()
    _draai_lus({"weather": weather}, aantal_rondes=main.OCHTEND_CHECK_INTERVAL_MINUTEN * 3)
    assert weather.check_ochtend_samenvatting.call_count == 3


def test_ochtend_gate_doet_niets_zonder_weather_module():
    # Geen weather geladen: geen crash, geen foutmelding.
    _, uitvoer = _draai_lus({}, aantal_rondes=main.OCHTEND_CHECK_INTERVAL_MINUTEN)
    assert "Fout" not in uitvoer


def test_ochtend_gate_is_onafhankelijk_van_de_bestaande_weerwaarschuwing():
    # Dezelfde 'weather'-module, twee verschillende aanroepen: de ochtendcheck
    # mag de 30-minutencheck niet vervangen en omgekeerd.
    weather = MagicMock()
    ronde = main.WEATHER_CHECK_INTERVAL_MINUTEN
    _draai_lus({"weather": weather}, aantal_rondes=ronde)
    assert weather.check_proactieve_waarschuwing.call_count == 1
    assert weather.check_ochtend_samenvatting.call_count == ronde // main.OCHTEND_CHECK_INTERVAL_MINUTEN


def test_ochtend_geeft_een_mag_spreken_functie_mee():
    weather = MagicMock()
    _draai_lus({"weather": weather}, aantal_rondes=main.OCHTEND_CHECK_INTERVAL_MINUTEN)
    kwargs = weather.check_ochtend_samenvatting.call_args.kwargs
    assert callable(kwargs["mag_spreken"])


def test_ochtend_vraagt_layer5_niet_zelf_maar_laat_het_aan_weather():
    # main.py geeft enkel een functie mee; Layer 5 wordt pas gevraagd als
    # weather.py die functie aanroept (dus alleen als de rest klopt).
    weather = MagicMock()
    context_manager = MagicMock()
    _draai_lus({"weather": weather, "context_manager": context_manager},
               aantal_rondes=main.OCHTEND_CHECK_INTERVAL_MINUTEN)
    context_manager.can_interrupt.assert_not_called()


def test_ochtend_mag_spreken_functie_vraagt_de_echte_layer5():
    weather = MagicMock()
    context_manager = MagicMock()
    context_manager.can_interrupt.return_value = False
    _draai_lus({"weather": weather, "context_manager": context_manager},
               aantal_rondes=main.OCHTEND_CHECK_INTERVAL_MINUTEN)
    mag_spreken = weather.check_ochtend_samenvatting.call_args.kwargs["mag_spreken"]
    assert mag_spreken() is False
    context_manager.can_interrupt.assert_called_once()


def test_fout_in_ochtend_stopt_de_rest_niet_en_wordt_geprint():
    kapot = MagicMock()
    kapot.check_ochtend_samenvatting.side_effect = RuntimeError("kunstmatige testfout")
    emergence = MagicMock()
    # Een waarde waarop zowel de ochtendcheck als emergence aan de beurt zijn.
    rondes = main.OCHTEND_CHECK_INTERVAL_MINUTEN * main.EMERGENCE_CHECK_INTERVAL_MINUTEN

    _, uitvoer = _draai_lus({"weather": kapot, "emergence_engine": emergence}, aantal_rondes=rondes)

    assert "Fout in weather.check_ochtend_samenvatting" in uitvoer
    assert emergence.reflect.call_count == rondes // main.EMERGENCE_CHECK_INTERVAL_MINUTEN
    # De fout in ronde 5 mag ronde 10 niet tegenhouden: de lus ging gewoon door.
    assert kapot.check_ochtend_samenvatting.call_count == rondes // main.OCHTEND_CHECK_INTERVAL_MINUTEN


# =================================================================
# _layer5_laat_spreken_toe()
# =================================================================

def test_toelaten_zonder_context_manager_mag_gewoon():
    # Layer 5 ontbreken mag Nova nooit stiller maken dan voorheen.
    assert main._layer5_laat_spreken_toe(_loader_met({})) is True


def test_toelaten_layer5_zegt_ja():
    cm = MagicMock()
    cm.can_interrupt.return_value = True
    assert main._layer5_laat_spreken_toe(_loader_met({"context_manager": cm})) is True


def test_toelaten_layer5_zegt_nee():
    cm = MagicMock()
    cm.can_interrupt.return_value = False
    assert main._layer5_laat_spreken_toe(_loader_met({"context_manager": cm})) is False


@pytest.mark.parametrize("antwoord,verwacht", [
    ((True, "alles ok"), True),
    ((False, "niemand aanwezig volgens webcam"), False),   # gevulde tuple is anders altijd 'waar'
    ((), False),
])
def test_toelaten_tuple_antwoord_telt_het_eerste_deel(antwoord, verwacht):
    cm = MagicMock()
    cm.can_interrupt.return_value = antwoord
    assert main._layer5_laat_spreken_toe(_loader_met({"context_manager": cm})) is verwacht


@pytest.mark.parametrize("antwoord,verwacht", [(1, True), (0, False), (None, False)])
def test_toelaten_geeft_altijd_een_echte_bool(antwoord, verwacht):
    cm = MagicMock()
    cm.can_interrupt.return_value = antwoord
    assert main._layer5_laat_spreken_toe(_loader_met({"context_manager": cm})) is verwacht


def test_toelaten_fout_in_layer5_betekent_nee_en_wordt_geprint(capsys):
    cm = MagicMock()
    cm.can_interrupt.side_effect = RuntimeError("kunstmatige testfout")
    assert main._layer5_laat_spreken_toe(_loader_met({"context_manager": cm})) is False
    assert "Fout in context_manager.can_interrupt" in capsys.readouterr().out