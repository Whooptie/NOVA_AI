# tests/test_main_achtergrond_en_response.py
"""
Tests voor main.py's on_chat_response() en achtergrond_loop().

Dit testbestand staat los van test_main_typewriter_lock.py — andere
verantwoordelijkheid (algemeen gedrag i.p.v. specifiek de thread-lock-fix
van Bug #30), aparte file blijft overzichtelijker.

GEDEKTE GEDRAGINGEN
--------------------
Groep A — on_chat_response():
  1. instant=True print in 1 keer, GEEN typewriter-effect.
  2. instant afwezig/False gebruikt WEL print_nova_typewriter().
  3. wachten_op_input=True -> de "Jij: "-prompt wordt na het bericht
     opnieuw getekend (het "verse prompt"-mechanisme, zie nova_state.md).
  4. wachten_op_input=False -> de prompt wordt NIET opnieuw getekend
     (anders zou een normaal antwoord een dubbele "Jij: "-prompt geven).

Groep B — achtergrond_loop()'s foutafscherming:
  5. Als een module een exception gooit (bv. session_watcher.check_pauze()),
     crasht de achtergrondthread niet -- de andere modules in diezelfde
     iteratie worden nog steeds aangeroepen.
  6. De fout wordt zichtbaar geprint ("[Achtergrondthread] Fout in ..."),
     niet stil geslikt.

Groep C -- de "aantal_loops % INTERVAL == 0"-gates:
  7. Bij een aantal_loops-waarde die deelbaar is door de interval, wordt
     de bijbehorende check WEL aangeroepen.
  8. Bij een waarde die NIET deelbaar is, wordt de check NIET aangeroepen.
  9. Twee verschillende gates (presence/weather) werken onafhankelijk van
     elkaar -- niet toevallig gekoppeld aan dezelfde teller.

BELANGRIJKE TECHNISCHE NOOT over achtergrond_loop()
-----------------------------------------------------
achtergrond_loop() is een "while True"-lus met time.sleep(60) er middenin
-- die draait normaal voor altijd. Om 'm testbaar te maken zonder echt
60 seconden te wachten (of voor altijd te blijven draaien), mocken we
time.sleep() zodat de EERSTE aanroep meteen een eigen StopLus-uitzondering
gooit. Dat stopt de while-lus gecontroleerd na precies 1 iteratie, zodat
we exact kunnen nakijken wat er in die ene iteratie gebeurde.

VOORWAARDE OM TE DRAAIEN
--------------------------
Net als test_main_typewriter_lock.py moet dit bestand in tests/ staan,
naast de core/-map (main.py doet zelf 'from core.event_bus import
EventBus' bij het importeren). Draai vanuit de project-root:

    pytest tests/test_main_achtergrond_en_response.py -v
"""

import io
import sys
from unittest.mock import MagicMock, patch

import pytest

import main


# =================================================================
# Groep A — on_chat_response()
# =================================================================

def test_instant_bericht_print_in_1_keer_geen_typewriter():
    """
    instant=True (bv. help.py's overzicht) moet in 1 keer geprint worden
    via een gewone print(), NIET via print_nova_typewriter(). Anders zou
    een lang, opgemaakt overzicht ook letter-voor-letter "getypt" worden,
    wat voor zo'n tekst niet de bedoeling is (zie de docstring-uitleg in
    main.py zelf bij on_chat_response()).
    """
    oude_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        with patch.object(main, "print_nova_typewriter") as mock_typewriter:
            main.on_chat_response({"text": "een lang overzicht", "instant": True})
            mock_typewriter.assert_not_called()
    finally:
        sys.stdout = oude_stdout


def test_normaal_bericht_gebruikt_wel_typewriter():
    """
    Een gewoon bericht (instant afwezig of False) moet WEL via
    print_nova_typewriter() lopen -- dat is het standaardgedrag voor
    Nova's gesproken antwoorden.
    """
    oude_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        with patch.object(main, "print_nova_typewriter") as mock_typewriter:
            main.on_chat_response({"text": "hallo Kevin"})
            mock_typewriter.assert_called_once_with("hallo Kevin")
    finally:
        sys.stdout = oude_stdout


def test_prompt_wordt_opnieuw_getekend_als_wachten_op_input_true():
    """
    Als de hoofdthread op input() staat te wachten (wachten_op_input=True)
    op het moment dat een bericht binnenkomt, betekent dit dat het bericht
    PROACTIEF kwam (van de achtergrondthread) -- de "Jij: "-prompt moet
    dan opnieuw getekend worden zodat die niet visueel "begraven" blijft
    onder Nova's nieuwe tekst.
    """
    oude_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()
    oude_waarde = main.wachten_op_input
    try:
        main.wachten_op_input = True
        with patch.object(main, "print_nova_typewriter"):
            main.on_chat_response({"text": "proactief bericht"})
        output = buffer.getvalue()
        assert "Jij:" in output, (
            "De 'Jij: '-prompt werd niet opnieuw getekend terwijl "
            "wachten_op_input=True was -- het 'verse prompt'-mechanisme "
            "lijkt niet (meer) te werken."
        )
    finally:
        sys.stdout = oude_stdout
        main.wachten_op_input = oude_waarde


def test_prompt_wordt_niet_opnieuw_getekend_als_wachten_op_input_false():
    """
    Omgekeerd geval: als het bericht een NORMAAL antwoord is op Kevin's
    eigen typen (wachten_op_input=False, want de hoofdthread zit dan al
    niet meer in input()), mag de prompt NIET nog eens extra getekend
    worden -- anders krijg je een dubbele "Jij: "-regel.
    """
    oude_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()
    oude_waarde = main.wachten_op_input
    try:
        main.wachten_op_input = False
        with patch.object(main, "print_nova_typewriter"):
            main.on_chat_response({"text": "normaal antwoord"})
        output = buffer.getvalue()
        assert "Jij:" not in output, (
            "De 'Jij: '-prompt werd TOCH opnieuw getekend terwijl "
            "wachten_op_input=False was -- dit zou een dubbele prompt "
            "geven bij een gewoon antwoord."
        )
    finally:
        sys.stdout = oude_stdout
        main.wachten_op_input = oude_waarde


# =================================================================
# Groep B — achtergrond_loop()'s foutafscherming
# =================================================================

class _StopLus(Exception):
    """Eigen uitzondering om de 'while True' in achtergrond_loop() na
    precies 1 iteratie gecontroleerd te stoppen (zie moduledocstring)."""
    pass


def _maak_loader_met_modules(modules_dict):
    """
    Bouwt een neppe 'loader' na met enkel wat achtergrond_loop() nodig
    heeft: .loaded_modules.get(naam) moet de juiste nep-module (of None)
    teruggeven, precies zoals de echte ModuleLoader dat doet.

    We gebruiken hier een ECHTE dict (geen MagicMock) voor
    loaded_modules, want een dict se eigen .get()-methode is read-only
    en kan niet zomaar overschreven worden -- een gewone dict met de
    juiste inhoud erin geeft exact hetzelfde .get(naam)-gedrag als de
    echte ModuleLoader, zonder die beperking.
    """
    loader = MagicMock()
    loader.loaded_modules = dict(modules_dict)
    return loader


def test_exception_in_1_module_stopt_de_andere_modules_niet():
    """
    Kern van de Bug-preventie: als session_watcher.check_pauze() een
    exception gooit, moet achtergrond_loop() dat opvangen (de try/except
    per module-aanroep in main.py) EN gewoon doorgaan met de volgende
    modules in dezelfde iteratie (activity_detector, focus_detector, ...).
    Zonder deze afscherming zou 1 kapotte module de HELE achtergrondthread
    (en dus alle proactieve features) laten crashen.
    """
    kapotte_watcher = MagicMock()
    kapotte_watcher.check_pauze.side_effect = RuntimeError("kunstmatige testfout")
    kapotte_watcher.check_activity_interruption = MagicMock()

    activity_detector = MagicMock()
    focus_detector = MagicMock()

    loader = _maak_loader_met_modules({
        "session_watcher": kapotte_watcher,
        "activity_detector": activity_detector,
        "focus_detector": focus_detector,
    })

    # time.sleep(60) staat HELEMAAL BOVENAAN de while-lus, vóór enige
    # module-aanroep. We moeten die eerste aanroep dus gewoon laten
    # doorgaan (niet meteen stoppen), en pas bij de TWEEDE sleep-aanroep
    # (= na 1 volledige iteratie) stoppen -- anders krijgt geen enkele
    # module ooit de kans om aangeroepen te worden.
    aanroep_teller = {"n": 0}

    def sleep_side_effect(*args, **kwargs):
        aanroep_teller["n"] += 1
        if aanroep_teller["n"] > 1:
            raise _StopLus

    oude_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        with patch("main.time.sleep", side_effect=sleep_side_effect):
            with pytest.raises(_StopLus):
                main.achtergrond_loop(loader)
    finally:
        sys.stdout = oude_stdout

    # check_pauze() faalde, maar de VOLGENDE aanroepen in diezelfde
    # iteratie moeten toch gebeurd zijn -- dat bewijst dat de try/except
    # rond elke module-aanroep werkt zoals bedoeld.
    kapotte_watcher.check_activity_interruption.assert_called_once()
    activity_detector.detect_activity.assert_called_once()
    focus_detector.get_focus_info.assert_called_once()


def test_foutmelding_wordt_zichtbaar_geprint():
    """
    Een fout in een module mag niet STIL verdwijnen -- die moet zichtbaar
    geprint worden zodat Kevin het merkt in de console/logs, ook al
    crasht de rest van het programma niet.
    """
    kapotte_watcher = MagicMock()
    kapotte_watcher.check_pauze.side_effect = RuntimeError("kunstmatige testfout")

    loader = _maak_loader_met_modules({"session_watcher": kapotte_watcher})

    # Zelfde reden als bij de vorige test: de eerste sleep(60)-aanroep
    # moet gewoon doorgaan, anders komt check_pauze() nooit aan bod.
    aanroep_teller = {"n": 0}

    def sleep_side_effect(*args, **kwargs):
        aanroep_teller["n"] += 1
        if aanroep_teller["n"] > 1:
            raise _StopLus

    oude_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()
    try:
        with patch("main.time.sleep", side_effect=sleep_side_effect):
            with pytest.raises(_StopLus):
                main.achtergrond_loop(loader)
    finally:
        sys.stdout = oude_stdout

    output = buffer.getvalue()
    assert "Fout in check_pauze" in output, (
        "De exception uit check_pauze() werd niet zichtbaar geprint -- "
        "een fout in een achtergrondmodule zou nu stil verdwijnen."
    )


# =================================================================
# Groep C — de "aantal_loops % INTERVAL == 0"-gates
# =================================================================

def _draai_1_iteratie_en_geef_loader_terug(modules_dict, aantal_loops_start):
    """
    Helper: draait achtergrond_loop() voor exact 1 iteratie, gestart
    vanaf een gekozen aantal_loops-waarde, en geeft de gebruikte
    nep-modules terug zodat de test kan nakijken wat wel/niet is
    aangeroepen.

    We simuleren "aantal_loops_start" door time.sleep() een teller te
    laten bijhouden: pas bij de (aantal_loops_start + 1)e aanroep van
    sleep() gooien we _StopLus, zodat aantal_loops binnen de functie
    exact op aantal_loops_start uitkomt op het moment dat de interval-
    gates gecheckt worden. (achtergrond_loop() telt aantal_loops +=1
    NA elke sleep(60), dus 1 sleep-aanroep laten doorgaan = 1 iteratie
    met aantal_loops == 1.)
    """
    loader = _maak_loader_met_modules(modules_dict)

    aanroep_teller = {"n": 0}

    def sleep_side_effect(*args, **kwargs):
        aanroep_teller["n"] += 1
        if aanroep_teller["n"] > aantal_loops_start:
            raise _StopLus

    with patch("main.time.sleep", side_effect=sleep_side_effect):
        with pytest.raises(_StopLus):
            main.achtergrond_loop(loader)

    return loader


def test_presence_gate_triggert_wel_bij_deelbare_loop_waarde():
    """
    PRESENCE_CHECK_INTERVAL_MINUTEN staat in main.py op 5. Bij
    aantal_loops == 5 (5 % 5 == 0) moet context_manager.update_
    presence_info() dus WEL aangeroepen worden.
    """
    context_manager = MagicMock()
    modules = {"context_manager": context_manager}

    _draai_1_iteratie_en_geef_loader_terug(
        modules, aantal_loops_start=main.PRESENCE_CHECK_INTERVAL_MINUTEN
    )

    context_manager.update_presence_info.assert_called_once()


def test_presence_gate_triggert_niet_bij_niet_deelbare_loop_waarde():
    """
    Omgekeerd: bij een aantal_loops-waarde die NIET deelbaar is door
    PRESENCE_CHECK_INTERVAL_MINUTEN (bv. interval - 1), mag update_
    presence_info() niet aangeroepen worden.
    """
    context_manager = MagicMock()
    modules = {"context_manager": context_manager}

    niet_deelbare_waarde = max(main.PRESENCE_CHECK_INTERVAL_MINUTEN - 1, 1)
    # Veiligheidscheck: als de interval toevallig 1 is, is elke waarde
    # deelbaar -- dan slaan we deze specifieke test bewust over, want
    # dan is er geen "niet-deelbare" waarde om te testen.
    if main.PRESENCE_CHECK_INTERVAL_MINUTEN <= 1:
        pytest.skip(
            "PRESENCE_CHECK_INTERVAL_MINUTEN is 1 of minder -- elke "
            "waarde is dan deelbaar, geen niet-deelbaar geval te testen."
        )

    _draai_1_iteratie_en_geef_loader_terug(
        modules, aantal_loops_start=niet_deelbare_waarde
    )

    context_manager.update_presence_info.assert_not_called()


def test_weather_gate_werkt_onafhankelijk_van_presence_gate():
    """
    Bewijst dat de gates NIET toevallig aan dezelfde teller vastzitten:
    bij een aantal_loops-waarde die WEL deelbaar is door WEATHER_
    CHECK_INTERVAL_MINUTEN maar NIET door PRESENCE_CHECK_INTERVAL_MINUTEN
    (voor zover die twee verschillend zijn), moet enkel de weather-check
    triggeren, niet de presence-check.

    Als beide constantes toevallig gelijk staan in main.py, heeft deze
    specifieke test geen onderscheidend vermogen meer -- dan slaan we
    'm over in plaats van een vals resultaat te riskeren.
    """
    if main.WEATHER_CHECK_INTERVAL_MINUTEN == main.PRESENCE_CHECK_INTERVAL_MINUTEN:
        pytest.skip(
            "WEATHER_CHECK_INTERVAL_MINUTEN == PRESENCE_CHECK_INTERVAL_"
            "MINUTEN in main.py -- deze test kan de twee gates dan niet "
            "los van elkaar aantonen."
        )

    # Zoek de kleinste aantal_loops-waarde die WEL deelbaar is door
    # WEATHER_CHECK_INTERVAL_MINUTEN maar NIET door PRESENCE_CHECK_
    # INTERVAL_MINUTEN, zodat de twee gates hier gegarandeerd
    # uiteenlopen.
    waarde = None
    for kandidaat in range(
        main.WEATHER_CHECK_INTERVAL_MINUTEN,
        main.WEATHER_CHECK_INTERVAL_MINUTEN * (main.PRESENCE_CHECK_INTERVAL_MINUTEN + 1) + 1,
        main.WEATHER_CHECK_INTERVAL_MINUTEN,
    ):
        if kandidaat % main.PRESENCE_CHECK_INTERVAL_MINUTEN != 0:
            waarde = kandidaat
            break

    if waarde is None:
        pytest.skip(
            "Geen aantal_loops-waarde gevonden binnen een redelijk "
            "bereik die weather wel en presence niet triggert."
        )

    weather = MagicMock()
    context_manager = MagicMock()
    modules = {"weather": weather, "context_manager": context_manager}

    _draai_1_iteratie_en_geef_loader_terug(modules, aantal_loops_start=waarde)

    weather.check_proactieve_waarschuwing.assert_called_once()
    context_manager.update_presence_info.assert_not_called()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))