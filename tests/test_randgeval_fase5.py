# test_randgeval_fase5.py
#
# Echte pytest-test die het exacte randgeval bevestigt waarvoor Fase 5
# gebouwd werd: wat gebeurt er als "coding" EN "gebruikelijk moment"
# TEGELIJK waar zijn?
#
# Met de OUDE (Fase 1-4) "eerste match wint"-volgorde zou dit ALTIJD
# should_interrupt=False geven, met een reden die het gebruikelijke
# moment NOOIT vermeldt (de coding-regel greep in en stopte daar).
#
# Met de NIEUWE (Fase 5) score-logica moeten BEIDE signalen in de
# reden-tekst verschijnen, en bepaalt de OPGETELDE score het resultaat.
#
# Vereist geen draaiende Nova, geen webcam, geen EventBus -- roept
# ContextManager rechtstreeks aan met event_bus=None en lege layers,
# want _bepaal_interrupt() heeft enkel de doorgegeven parameters nodig,
# geen echte sensoren. Geen bestanden, geen netwerk -- puur logica.
#
# Uitvoeren: pytest tests/test_randgeval_fase5.py -v

import pytest

from modules.context.context_manager import ContextManager


@pytest.fixture
def cmgr():
    return ContextManager(event_bus=None, layers={})


def test_coding_en_gebruikelijk_moment_samen(cmgr):
    """
    HET RANDGEVAL: coding (storingsgevoelig, actieve focus, ruim over
    de drempel) EN een gebruikelijk moment TEGELIJK.

    Verwacht (met de huidige standaardgewichten uit context_manager.py):
        SCORE_STORINGSGEVOELIGE_ACTIVITEIT_ACTIEF = -3
        SCORE_GEBRUIKELIJK_MOMENT               = +2
        totaal = -1  ->  should_interrupt = False (want -1 < INTERRUPT_SCORE_DREMPEL=0)

    HET BELANGRIJKSTE OM TE CONTROLEREN: staat "gebruikelijk moment
    volgens Layer 2: +2" WEL in de reden-tekst? Dat is het bewijs dat
    Fase 5 dit signaal nu WEL meeweegt, i.p.v. het onvermeld te laten
    zoals de oude "eerste match wint"-logica deed.
    """
    should_interrupt, reden = cmgr._bepaal_interrupt(
        is_gebruikelijk_moment=True,       # Layer 2: dit is een gebruikelijk chat-moment
        anomalieen_vandaag=[],             # geen anomalieën, willen dit signaal puur zien
        activiteit_label="coding",         # storingsgevoelige activiteit
        activiteit_duur_minuten=20,        # ruim over CODING_ONDERBREEK_DREMPEL_MINUTEN
        focus_niveau="actief",             # Kevin is er ook echt nog mee bezig
        is_alleen=False,                   # iemand aanwezig, harde stopregel triggert niet
    )

    assert "gebruikelijk moment volgens Layer 2: +2" in reden, (
        "FOUT: het gebruikelijke moment wordt niet vermeld in de reden — "
        "dat zou betekenen dat de oude 'eerste match wint'-logica "
        "terug is, en Fase 5's score-combinatie niet werkt."
    )
    assert "coding" in reden and "-3" in reden, (
        "FOUT: de coding-score wordt niet vermeld in de reden."
    )
    assert should_interrupt is False, (
        "FOUT: bij score -1 (onder de drempel van 0) zou "
        "should_interrupt False moeten zijn."
    )


def test_gebruikelijk_moment_alleen_zonder_coding(cmgr):
    """
    TER VERGELIJKING: hetzelfde gebruikelijke moment, maar ZONDER
    coding -- laat zien dat het gebruikelijke moment op zichzelf wél
    tot should_interrupt=True leidt. Dit bewijst dat coding het NIET
    stilzwijgend "overschrijft" zoals vroeger, maar er daadwerkelijk
    tegenop weegt (2 punten voor, 3 punten tegen in de vorige test).
    """
    should_interrupt, reden = cmgr._bepaal_interrupt(
        is_gebruikelijk_moment=True,
        anomalieen_vandaag=[],
        activiteit_label="unknown",
        activiteit_duur_minuten=0,
        focus_niveau="onbekend",
        is_alleen=False,
    )

    assert should_interrupt is True, (
        "FOUT: zonder coding zou het gebruikelijke moment (+2) alleen "
        "moeten volstaan om should_interrupt=True te geven."
    )