# test_randgeval_fase5.py
#
# Los testscript (NIET onderdeel van Nova zelf, net als
# test_forceer_anomalieen.py uit Fase 1) — bevestigt het exacte
# randgeval waarvoor Fase 5 gebouwd werd: wat gebeurt er als "coding"
# EN "gebruikelijk moment" TEGELIJK waar zijn?
#
# Met de OUDE (Fase 1-4) "eerste match wint"-volgorde zou dit ALTIJD
# should_interrupt=False geven, met een reden die het gebruikelijke
# moment NOOIT vermeldt (de coding-regel greep in en stopte daar).
#
# Met de NIEUWE (Fase 5) score-logica moeten BEIDE signalen in de
# reden-tekst verschijnen, en bepaalt de OPGETELDE score het resultaat.
#
# Gebruik: plaats dit bestand in de hoofdmap van Nova_AI (naast
# main.py) en draai het met:
#
#   python test_randgeval_fase5.py
#
# Vereist geen draaiende Nova, geen webcam, geen EventBus — roept
# ContextManager rechtstreeks aan met event_bus=None en lege layers,
# want _bepaal_interrupt() heeft enkel de doorgegeven parameters nodig,
# geen echte sensoren.

from modules.context.context_manager import ContextManager


def toon_resultaat(titel, should_interrupt, reden):
    print(f"\n--- {titel} ---")
    print(f"should_interrupt: {should_interrupt}")
    print(f"reden: {reden}")


def main():
    cmgr = ContextManager(event_bus=None, layers={})

    # ------------------------------------------------------------
    # HET RANDGEVAL: coding (storingsgevoelig, actieve focus, ruim
    # over de drempel) EN een gebruikelijk moment TEGELIJK.
    # ------------------------------------------------------------
    should_interrupt, reden = cmgr._bepaal_interrupt(
        is_gebruikelijk_moment=True,       # Layer 2: dit is een gebruikelijk chat-moment
        anomalieen_vandaag=[],             # geen anomalieën, willen dit signaal puur zien
        activiteit_label="coding",         # storingsgevoelige activiteit
        activiteit_duur_minuten=20,        # ruim over CODING_ONDERBREEK_DREMPEL_MINUTEN
        focus_niveau="actief",             # Kevin is er ook echt nog mee bezig
        is_alleen=False,                   # iemand aanwezig, harde stopregel triggert niet
    )
    toon_resultaat(
        "RANDGEVAL: coding (20 min, focus actief) + gebruikelijk moment",
        should_interrupt,
        reden,
    )

    # Verwacht (met de huidige standaardgewichten uit context_manager.py):
    #   SCORE_STORINGSGEVOELIGE_ACTIVITEIT_ACTIEF = -3
    #   SCORE_GEBRUIKELIJK_MOMENT = +2
    #   totaal = -1  ->  should_interrupt = False (want -1 < INTERRUPT_SCORE_DREMPEL=0)
    #
    # HET BELANGRIJKSTE OM TE CONTROLEREN: staat "gebruikelijk moment
    # volgens Layer 2: +2" WEL in de reden-tekst hierboven? Dat is het
    # bewijs dat Fase 5 dit signaal nu WEL meeweegt, i.p.v. het
    # onvermeld te laten zoals de oude volgorde deed.
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
    print("\n✅ Randgeval bevestigd: BEIDE signalen staan samen in de reden, "
          "en de opgetelde score (niet de 'eerste match') bepaalt het resultaat.")

    # ------------------------------------------------------------
    # Ter vergelijking: HETZELFDE gebruikelijke moment, maar ZONDER
    # coding — laat zien dat het gebruikelijke moment op zichzelf wél
    # tot should_interrupt=True zou leiden. Dit bewijst dat coding het
    # NIET stilzwijgend "overschrijft" zoals vroeger, maar er
    # daadwerkelijk tegenop weegt (2 punten voor, 3 punten tegen).
    # ------------------------------------------------------------
    should_interrupt_zonder_coding, reden_zonder_coding = cmgr._bepaal_interrupt(
        is_gebruikelijk_moment=True,
        anomalieen_vandaag=[],
        activiteit_label="unknown",
        activiteit_duur_minuten=0,
        focus_niveau="onbekend",
        is_alleen=False,
    )
    toon_resultaat(
        "TER VERGELIJKING: zelfde gebruikelijk moment, GEEN coding",
        should_interrupt_zonder_coding,
        reden_zonder_coding,
    )
    assert should_interrupt_zonder_coding is True, (
        "FOUT: zonder coding zou het gebruikelijke moment (+2) alleen "
        "moeten volstaan om should_interrupt=True te geven."
    )
    print("\n✅ Vergelijking bevestigd: zonder coding weegt hetzelfde "
          "gebruikelijke moment wél door naar should_interrupt=True — "
          "het verschil met hierboven toont dat coding ECHT meeweegt "
          "in een score, niet enkel een aan/uit-blokkade is.")

    print("\nAlle asserts geslaagd — Fase 5's score-combinatie werkt zoals bedoeld.")


if __name__ == "__main__":
    main()