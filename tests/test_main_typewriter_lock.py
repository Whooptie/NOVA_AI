# tests/test_main_typewriter_lock.py
"""
Tests voor Bug #30-fix: typewriter-effect + achtergrondthread race condition.

WAAROM DEZE TESTS BESTAAN
--------------------------
main.py's print_nova_typewriter() print Nova's antwoord letter per letter
naar stdout. Deze functie wordt aangeroepen vanuit on_chat_response(), en
on_chat_response() kan door VERSCHILLENDE threads getriggerd worden: de
hoofdthread (na Kevin's eigen input) én de achtergrondthread
(session_watcher/emergence_engine/weather.py via achtergrond_loop()).

Zonder bescherming kunnen twee threads dus TEGELIJK letter-voor-letter naar
dezelfde stdout schrijven, waardoor de tekens door elkaar hustelen bij lange
antwoorden (bevestigd 5 augustus 2026 tijdens het testen van math_uitleg.py).

De fix: een threading.Lock() (_typewriter_lock) rond de hele typewriter-print,
zodat een tweede aanroep netjes wacht tot de eerste klaar is.

BELANGRIJKE KANTTEKENING
--------------------------
Een race condition die afhangt van timing (time.sleep) is notoir lastig
100% betrouwbaar te testen — soms "wint" de juiste volgorde toevallig, ook
zonder lock. Daarom testen we NIET door te gokken of de bug zich toevallig
voordoet, maar door:
  1. De lock zelf van buitenaf al vast te houden en te bewijzen dat de
     functie dan ECHT blokkeert (test_typewriter_wacht_als_lock_al_bezet_is)
     — dit is de betrouwbare, deterministische manier om te bewijzen dat de
     functie de lock ook echt gebruikt.
  2. Een gecontroleerde simulatie met twee threads die elk hun eigen tekst
     printen, met een kunstmatige vertraging die groot genoeg is om een
     eventuele race condition zichtbaar te maken.

VOORWAARDE OM TE DRAAIEN
--------------------------
Dit testbestand verwacht dat het NAAST de map core/ staat (dus in de
Nova_AI-hoofdmap, in een tests/-submap), want main.py doet zelf
`from core.event_bus import EventBus` en `from core.module_loader import
ModuleLoader`. Draai vanuit de project-root met:

    pytest tests/test_main_typewriter_lock.py -v
"""

import io
import sys
import threading
import time

import pytest


# ---------------------------------------------------------------
# main.py importeren
# ---------------------------------------------------------------
# main.py voert bij het inladen meteen wat Windows-console-setup-code uit
# (enkel actief als os.name == "nt", dus onschadelijk op andere platforms)
# en importeert daarna core.event_bus / core.module_loader. Die moeten dus
# gewoon vindbaar zijn zoals in de echte Nova-projectstructuur.
import main


# ---------------------------------------------------------------
# Test 1 — bestaat de lock, en is het echt een threading.Lock?
# ---------------------------------------------------------------
def test_lock_bestaat_en_is_threading_lock():
    """
    Sanity-check: _typewriter_lock moet bestaan in main.py en van het
    juiste type zijn. Dit voorkomt dat iemand per ongeluk een gewone
    boolean-vlag gebruikt die er in code hetzelfde uitziet, maar geen
    echte thread-blokkering biedt.
    """
    assert hasattr(main, "_typewriter_lock"), (
        "main.py mist '_typewriter_lock' — de Bug #30-fix "
        "(lock rond print_nova_typewriter) lijkt nog niet toegepast."
    )

    # threading.Lock() geeft een object van het interne type
    # '_thread.lock' terug, dus we checken op de aanwezigheid van de
    # verwachte lock-methodes (acquire/release) in plaats van op een
    # exacte klasse-naam — dat is de robuuste manier om dit te checken.
    assert hasattr(main._typewriter_lock, "acquire")
    assert hasattr(main._typewriter_lock, "release")


# ---------------------------------------------------------------
# Test 2 — gebruikt print_nova_typewriter() de lock ook echt?
# ---------------------------------------------------------------
def test_typewriter_wacht_als_lock_al_bezet_is():
    """
    Bewijst dat print_nova_typewriter() de lock ook daadwerkelijk
    vastpakt vóór het printen, door de lock zelf al bezet te houden
    (alsof een andere thread al aan het typen is) en te controleren
    dat de functie dan blijft wachten in plaats van meteen te printen.

    Dit is deterministisch (geen timing-gok nodig): zolang wij de lock
    vasthouden, MOET een correcte implementatie geblokkeerd blijven.
    """
    # We houden de lock zelf vast, alsof "de hoofdthread" al bezig is.
    main._typewriter_lock.acquire()

    resultaat = {"klaar": False}

    def loop_in_andere_thread():
        # Dit moet blokkeren zolang wij de lock hierboven vasthouden.
        main.print_nova_typewriter("test")
        resultaat["klaar"] = True

    # Stdout omleiden zodat de test geen rommel op het scherm print.
    oude_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        t = threading.Thread(target=loop_in_andere_thread, daemon=True)
        t.start()

        # Geef de thread een korte kans om te starten en (fout gedrag)
        # meteen te printen — als de lock NIET gebruikt wordt, is
        # 'klaar' hier waarschijnlijk al True.
        time.sleep(0.3)
        assert resultaat["klaar"] is False, (
            "print_nova_typewriter() liep door terwijl de lock al "
            "bezet was — de functie gebruikt _typewriter_lock niet "
            "(of niet correct) rond het printen."
        )

        # Nu geven we de lock vrij — de wachtende thread moet nu
        # binnen redelijke tijd wél klaar komen.
        main._typewriter_lock.release()
        t.join(timeout=5)

        assert resultaat["klaar"] is True, (
            "print_nova_typewriter() kwam niet klaar nadat de lock "
            "werd vrijgegeven — mogelijk een deadlock in de fix."
        )
    finally:
        sys.stdout = oude_stdout
        # Veiligheidsnet: als de test halverwege faalt, lock zeker
        # weer vrijgeven zodat andere tests er niet door vastlopen.
        if main._typewriter_lock.locked():
            main._typewriter_lock.release()


# ---------------------------------------------------------------
# Test 3 — geen gehusselde tekens bij twee gelijktijdige aanroepen
# ---------------------------------------------------------------
def test_geen_gehusselde_tekens_bij_gelijktijdige_aanroepen():
    """
    Simuleert het exacte scenario van Bug #30: twee threads roepen
    print_nova_typewriter() zo goed als gelijktijdig aan met elk hun
    eigen, onderscheidbare tekst. Zonder werkende lock zou de output
    om-en-om gemengd kunnen raken (het bug-symptoom: "tekens door
    elkaar gehusseld"). Met de lock moet elke tekst volledig na
    elkaar in de output staan, nooit dooreengeweven.

    We verlagen TYPEWRITER_SNELHEID tijdelijk niet — de standaard
    0.02s per letter is al ruim genoeg om een eventuele race
    (zonder lock) betrouwbaar zichtbaar te maken over een tekst van
    een paar tientallen tekens.
    """
    tekst_a = "AAAAAAAAAAAAAAAAAAAA"
    tekst_b = "BBBBBBBBBBBBBBBBBBBB"

    oude_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()
    try:
        t1 = threading.Thread(target=main.print_nova_typewriter, args=(tekst_a,))
        t2 = threading.Thread(target=main.print_nova_typewriter, args=(tekst_b,))

        # Zo gelijktijdig mogelijk starten, om de race condition
        # zoveel mogelijk kans te geven zich te tonen als de lock
        # niet zou werken.
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        output = buffer.getvalue()

        # De ANSI-kleurcodes (MAGENTA/RESET) rond elke letter maken de
        # ruwe output rommelig om op te lezen — we filteren ze eruit
        # zodat we enkel de letters zelf overhouden, in de volgorde
        # waarin ze geprint zijn.
        kale_output = (
            output.replace(main.MAGENTA, "").replace(main.RESET, "")
        )

        # Kern van de test: elke tekst moet als AANEENGESLOTEN blok
        # in de output staan. Als de twee typewriter-aanroepen door
        # elkaar liepen, zou "AAAA...BBBB...AAAA" (afgewisseld)
        # ontstaan in plaats van twee nette, gescheiden blokken.
        assert tekst_a in kale_output, (
            f"Tekst A kwam niet als aaneengesloten blok voor in de "
            f"output — mogelijk door elkaar gehusseld met tekst B.\n"
            f"Ruwe output: {kale_output!r}"
        )
        assert tekst_b in kale_output, (
            f"Tekst B kwam niet als aaneengesloten blok voor in de "
            f"output — mogelijk door elkaar gehusseld met tekst A.\n"
            f"Ruwe output: {kale_output!r}"
        )
    finally:
        sys.stdout = oude_stdout
        if main._typewriter_lock.locked():
            main._typewriter_lock.release()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))