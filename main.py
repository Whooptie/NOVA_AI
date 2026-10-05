# main.py

import os
import sys
import signal
import ctypes
import time
import threading
import traceback
from datetime import datetime

# ---------------------------------------------------------------
# ANSI-kleurcodes activeren in het Windows-console-venster
# ---------------------------------------------------------------
# Waarom nodig? Sinds de /reboot-fix start Nova soms op in een
# gloednieuw Windows-console-venster (via subprocess.Popen met
# CREATE_NEW_CONSOLE in reboot_manager.py). Zo'n nieuw venster heeft
# niet altijd gegarandeerd "VT100/ANSI-verwerking" aanstaan — de
# instelling die ervoor zorgt dat codes zoals \033[92m ("maak tekst
# groen") ook echt als kleur getoond worden, in plaats van als
# letterlijke tekst zoals "←[92m".
#
# Dit blokje zet die instelling expliciet AAN bij het opstarten,
# ongeacht wat de standaardinstelling van dat venster toevallig is.
# Op Linux/Mac doet dit niets (daar staat het altijd al aan),
# vandaar de check "if os.name == 'nt'" (nt = Windows).
if os.name == "nt":
    ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
    STD_OUTPUT_HANDLE = -11

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
    mode = ctypes.c_uint32()

    if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        kernel32.SetConsoleMode(
            handle,
            mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING
        )

from core.event_bus import EventBus
from core.module_loader import ModuleLoader

# ANSI kleurcodes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
RESET = "\033[0m"

# Hoe snel Nova "typt" — tijd in seconden tussen elke letter.
# Kleiner getal = sneller. Pas dit gerust aan naar smaak.
TYPEWRITER_SNELHEID = 0.02

# Tijdstempel ([HH:MM]) voor elke "Nova:"- en "Jij:"-regel (30 sept
# 2026). Handig om te zien WANNEER een proactief bericht kwam. Zet op
# False om ze weer uit te zetten.
TOON_TIJDSTEMPELS = True

def tijdstempel():
    """Geeft bv. '[20:15] ' terug (in cyaan), of '' als het uit staat."""
    if not TOON_TIJDSTEMPELS:
        return ""
    return f"{CYAN}[{datetime.now():%H:%M}]{RESET} "

# Bug #30-fix (typewriter/threading race condition, 8 aug 2026):
# print_nova_typewriter() wordt aangeroepen vanuit on_chat_response(),
# en on_chat_response() kan door ELKE thread getriggerd worden — de
# hoofdthread (na Kevin's eigen input) ÉN de achtergrondthread
# (session_watcher/emergence_engine/weather.py via achtergrond_loop()).
# Zonder bescherming kunnen twee threads dus TEGELIJK letter-voor-letter
# naar dezelfde stdout schrijven, wat de tekens door elkaar hustelt bij
# lange antwoorden. Deze lock zorgt dat een tweede aanroep gewoon netjes
# wacht tot de eerste volledig klaar is, in plaats van ertussendoor te
# printen. wachten_op_input blijft apart bestaan — dat beschermt enkel
# het opnieuw tekenen van de "Jij: "-prompt NA het printen, niet het
# printen zelf.
_typewriter_lock = threading.Lock()

def print_nova_typewriter(tekst):
    """
    Print Nova's antwoord met een typewriter-effect: 'Nova: ' verschijnt
    direct in 1 blok, en de rest van de zin komt daarna letter per letter.
    Thread-safe via _typewriter_lock — zie uitleg hierboven bij Bug #30.
    """
    with _typewriter_lock:
        # "Nova: " blijft in 1 keer verschijnen — geen vertraging hier
        print(f"{tijdstempel()}{MAGENTA}Nova: {RESET}", end="", flush=True)

        # De rest van de tekst letter per letter
        for letter in tekst:
            print(f"{MAGENTA}{letter}{RESET}", end="", flush=True)
            time.sleep(TYPEWRITER_SNELHEID)

        print()  # nieuwe regel op het einde, anders plakt de volgende prompt eraan vast

def maak_invoer_veilig(tekst):
    """
    Bug #36-fix (24 september 2026): maakt getypte tekst veilig voor de
    rest van Nova, VOORDAT ze de EventBus op gaat.

    Het probleem: als er bij het typen een kapotte byte in de terminal
    terechtkomt (bv. een half doorgekomen 'é', of een verdwaalde
    toetsaanslag), geeft Python die door als een "surrogaat"-teken
    (zoals \\udcc3) -- een plaatshouder voor "hier stond een byte die
    ik niet snapte". Zo'n teken ziet er onschuldig uit, maar crasht
    later op elke plek die de tekst echt naar bytes omzet: een
    Wikipedia-URL opbouwen, opslaan in JSON/SQLite, en afhankelijk van
    de terminal zelfs gewoon printen.

    Werkwijze, in twee stappen:
      1. Probeer de oorspronkelijke bytes terug te winnen
         (errors="surrogateescape" doet precies het omgekeerde van wat
         Python bij het inlezen deed). Kwamen ALLE bytes van een teken
         wel door (bv. beide helften van een 'é'), dan krijg je zo het
         juiste teken gewoon terug.
      2. Bytes die ook samen geen geldig teken vormen (een losse,
         halve helft), worden weggelaten (errors="ignore").

    Gewone tekst (ook met é/ë/ç) komt hier 100% ongewijzigd door.
    """
    if not isinstance(tekst, str):
        return tekst
    try:
        ruwe_bytes = tekst.encode("utf-8", errors="surrogateescape")
    except UnicodeEncodeError:
        # Een surrogaat dat NIET van het inlezen komt (zeldzaam) --
        # dan kunnen we de bytes niet terugwinnen, gewoon weglaten.
        ruwe_bytes = tekst.encode("utf-8", errors="ignore")
    return ruwe_bytes.decode("utf-8", errors="ignore")

# Houdt bij of de hoofdthread op dit moment op input() staat te wachten.
# Nodig om te weten of we na een proactief bericht de "Jij: "-prompt
# opnieuw moeten tekenen (enkel relevant als we ECHT aan het wachten
# zijn — niet wanneer Nova toch al een normaal antwoord aan het geven is).
wachten_op_input = False

# Afwezigheid (3 oktober 2026): referentie naar
# modules/context/afwezigheid.py, ingevuld in main() na het laden van
# de modules. on_chat_response() hieronder vraagt deze module of een
# proactief bericht bewaard moet worden omdat Kevin's laptop
# vergrendeld is. None = module niet geladen -> alles gewoon tonen.
_afwezigheid_module = None

def on_chat_response(data, event_type=None):
    """
    Rechtstreekse subscriber op 'chat_response' — print onmiddellijk,
    ongeacht welke thread (hoofdthread via input(), of de achtergrond-
    thread via een proactieve module zoals session_watcher) dit event
    publiceert. Dit is nodig omdat de oude polling-aanpak (via
    mem.get_recent_events() in de hoofdlus) enkel afgaat NADAT Kevin
    zelf een bericht typt — een proactief bericht van de achtergrond-
    thread zou anders onzichtbaar in de memory-buffer blijven liggen
    tot de volgende keer dat Kevin toevallig iets intypt.
    """

    # Afwezigheid (3 oktober 2026): is Kevin weg (laptop vergrendeld)
    # en komt dit bericht NIET van de hoofdthread (= het is proactief,
    # geen antwoord op iets wat Kevin net typte)? Dan bewaart
    # afwezigheid.py het tot hij terug is, in plaats van het tegen een
    # lege stoel te zeggen. Bij een fout: gewoon tonen, nooit een
    # bericht kwijtraken.
    if _afwezigheid_module is not None:
        try:
            is_hoofdthread = threading.current_thread() is threading.main_thread()
            if _afwezigheid_module.onderschep_bericht(data, is_hoofdthread):
                return
        except Exception as e:
            print(f"[AFWEZIGHEID] Fout bij onderscheppen, bericht wordt gewoon getoond: {e}")

    msg = data.get("text") or data.get("msg") or ""

    # instant=True (bv. help.py) betekent: lang, opgemaakt overzicht,
    # geen gesproken zin — toon in 1 keer, geen typewriter-effect.
    if data.get("instant"):
        print(f"{tijdstempel()}{MAGENTA}Nova: {msg}{RESET}")
    else:
        print_nova_typewriter(msg)

    # Als de hoofdthread op dit moment op input() staat te wachten,
    # betekent dit dat DIT bericht proactief kwam (van de achtergrond-
    # thread) — de "Jij: "-prompt is dan al geprint maar raakt nu
    # visueel "begraven" onder Nova's bericht. We tekenen hem opnieuw
    # zodat het weer duidelijk is waar Kevin kan typen.
    if wachten_op_input:
        print(f"{GREEN}Jij: {RESET}", end="", flush=True)

# Layer 5, Fase 4: hoeveel keer van de 60-seconden-loop moet er
# verstrijken vóór de webcam gecheckt wordt? De webcam is trager en
# zwaarder dan de andere sensors (het lampje flikkert bovendien elke
# keer mee, zie het gesprek met Kevin op 16 juli 2026), dus dit draait
# NIET elke minuut zoals activity/focus, maar veel spaarzamer.
#
# LET OP VOOR LATER AANPASSEN: dit is gewoon 1 getal. Waarde = hoeveel
# minuten er tussen elke webcam-check zitten (5 = elke 5 minuten,
# 15 = elke 15 minuten, 1 = elke minuut).
PRESENCE_CHECK_INTERVAL_MINUTEN = 5

# Hoe vaak Nova zelf het weer checkt voor een proactieve waarschuwing
# (onweer/sneeuw/extreem/mist/hagel/harde wind) — zie weather.py's
# check_proactieve_waarschuwing(). Net als bij PRESENCE hierboven: gewoon
# 1 getal, hoeveel minuten tussen elke check (30 = elke 30 minuten).
WEATHER_CHECK_INTERVAL_MINUTEN = 1

# Hoe vaak Layer 7 (emergence_engine.py) reflecteert op verzamelde
# inzichten (woordverband/tijdspatroon/kennisdichtheid/personality_
# drift). In tegenstelling tot PRESENCE/WEATHER hierboven is dit GEEN
# zware/externe operatie (geen webcam, geen API-call) — puur lokale
# Python-berekening op data die toch al in het geheugen zit. Daarom
# een kortere interval dan bij die twee: 10 minuten, zodat een sterk
# insight niet te lang blijft "liggen" voor het ooit hardop gezegd
# wordt. reflect() bevat zelf al de confidence-gate (LAYER4_DREMPELS)
# en timing-gate (_mag_nu_spreken()) — een kortere interval verhoogt
# dus geen spam-risico, enkel hoe snel een insight ontdekt wordt.
EMERGENCE_CHECK_INTERVAL_MINUTEN = 10

# Fase 5 (periodieke hertraining intent_classifier, 28 juli 2026):
# hoe vaak wordt het ML-model van de Intent Classifier opnieuw
# getraind op training_data.json + de ondertussen verzamelde
# gecorrigeerde_voorbeelden.jsonl (Fase 4's "nee ik bedoelde X").
# Kevin's keuze: elke 4 uur, wat de nacht vanzelf ook meepikt zolang
# Nova 24/7 blijft draaien -- geen apart, vast nachtelijk tijdstip
# nodig. 240 minuten = 4 uur (zelfde eenheid als de andere
# CHECK_INTERVAL_MINUTEN-constantes hierboven).
INTENT_CLASSIFIER_RETRAIN_INTERVAL_MINUTEN = 240

# Punt 2 (find_contradictions() een aanroeper geven, 6 augustus 2026):
# hoe vaak contradiction_checker.py over de VOLLEDIGE kennisgraaf loopt
# op zoek naar botsende is_a-relaties (bv. 'hond' zowel 'dier' als
# 'meubel'). Zelfde soort lichte, pure Python-berekening als
# emergence_engine.reflect() hierboven (geen webcam, geen externe
# API) -- vandaar een vergelijkbare interval. Eigen spam-preventie zit
# al IN de module zelf (data/contradiction_state.json, onthoudt welke
# conflicten al gemeld zijn), dus een kortere interval verhoogt geen
# spam-risico, enkel hoe snel een nieuw conflict ontdekt wordt.
CONTRADICTION_CHECK_INTERVAL_MINUTEN = 15

# Punt 7 (topic_events_roadmap.md Fase 5, 13 augustus 2026): hoe vaak
# topic_suggestions.py checkt of er een geschikt moment is om een
# tijdstip-gebaseerde topic-suggestie te doen (bv. "wil je een potje
# schaken?"). Zelfde soort lichte, pure Python-berekening als
# emergence_engine.reflect() en contradiction_checker hierboven (geen
# webcam, geen externe API) -- vandaar een vergelijkbare interval.
# Eigen spam-preventie zit al IN de module zelf (data/
# topic_suggestion_state.json, onthoudt per topic het laatst
# voorgestelde uur/dag), dus een kortere interval verhoogt geen
# spam-risico, enkel hoe snel een geschikt moment ontdekt wordt.
TOPIC_SUGGESTIONS_CHECK_INTERVAL_MINUTEN = 10


def sluit_modules_netjes_af(loaded_modules):
    """
    Bug #47-vervolg (5 okt 2026): sluit ELKE geladen module met een
    shutdown()-methode netjes af, en memory als allerlaatste.

    Automatisch voor elke module: wie een shutdown()-methode heeft, wordt
    meegenomen -- ook toekomstige modules, zonder dat deze functie
    aangepast hoeft te worden. Zelfde aanpak als reboot_manager.py bij
    /reboot (sinds 5 juli 2026 bewezen veilig).

    Eén module die faalt, houdt de rest NIET tegen (elke aanroep zit in
    een eigen try/except) -- bij afsluiten is "zoveel mogelijk opslaan"
    belangrijker dan stoppen bij de eerste fout.

    Memory komt bewust als LAATSTE: zo kan elke andere module tijdens
    zijn eigen afsluiten nog events sturen die memory opvangt.
    """
    for naam, module in list(loaded_modules.items()):
        if naam == "memory" or module is None:
            continue
        shutdown = getattr(module, "shutdown", None)
        if not callable(shutdown):
            continue
        try:
            shutdown()
        except Exception as e:
            print(f"[Afsluiten] Fout bij {naam}.shutdown(): {e}")

    memory = loaded_modules.get("memory")
    afsluiten_memory = getattr(memory, "_on_shutdown", None)
    if callable(afsluiten_memory):
        try:
            afsluiten_memory()
        except Exception as e:
            print(f"[Afsluiten] Fout bij memory._on_shutdown(): {e}")


def installeer_stopsignaal(loader):
    """
    Bug #47-vervolg (5 okt 2026): wat doet Nova als Docker/Unraid de
    container stopt (server afsluiten, "Stop" in Unraid)?

    Docker stuurt dan een SIGTERM. Tot nu toe ving enkel memory.py dat op
    (en sinds bug #47 stopt die Nova daarna ook echt) -- maar de andere
    modules (pattern_matcher, chess_engine, interruption_tracker, ...)
    kregen geen kans om hun laatste stand op te slaan, in tegenstelling
    tot bij "exit" of "/reboot".

    Deze functie registreert een eigen SIGTERM-afhandeling die eerst
    sluit_modules_netjes_af() doet en daarna Nova stopt. Ze VERVANGT de
    afhandeling van memory.py (een programma kan per signaal maar één
    afhandeling hebben) -- memory wordt in sluit_modules_netjes_af() wel
    nog steeds netjes afgesloten, als laatste.

    MOET aangeroepen worden NA loader.discover_and_load(): memory.py
    registreert zijn eigen afhandeling tijdens het laden, en de laatste
    registratie wint.

    Python voert een signaal-afhandeling altijd uit in de HOOFDTHREAD,
    ook als die op input() staat te wachten -- sys.exit(0) stopt Nova
    daardoor meteen.
    """
    def _bij_stopsignaal(signum, frame):
        print(f"{YELLOW}[Afsluiten] Stopsignaal ontvangen (bv. container gestopt) — modules worden netjes afgesloten...{RESET}")
        sluit_modules_netjes_af(loader.loaded_modules)
        sys.exit(0)

    try:
        signal.signal(signal.SIGTERM, _bij_stopsignaal)
    except (ValueError, OSError, AttributeError) as e:
        # ValueError: niet vanuit de hoofdthread aangeroepen;
        # AttributeError/OSError: platform zonder SIGTERM. Dan blijft
        # memory.py's eigen afhandeling gewoon actief.
        print(f"[Afsluiten] Kon geen stopsignaal-afhandeling registreren: {e}")


def achtergrond_loop(loader):
    """
    Draait continu op de achtergrond, los van de input()-lus in main().
    Checkt elke 60 seconden of er een proactieve melding nodig is
    (session_watcher), en detecteert elke 60 seconden ook de huidige
    activiteit + focus (Layer 5, Fase 2-3). De webcam-aanwezigheids-
    check (Fase 4) gebeurt spaarzamer, elke
    PRESENCE_CHECK_INTERVAL_MINUTEN minuten, niet elke minuut.
    """
    aantal_loops = 0

    while True:
        time.sleep(60)
        aantal_loops += 1

        watcher = loader.loaded_modules.get("session_watcher")
        if watcher:
            try:
                watcher.check_pauze()
            except Exception as e:
                print(f"[Achtergrondthread] Fout in check_pauze(): {e}")

            # Activity-Aware Interaction (22 juli 2026): checkt of de
            # actieve activiteit al lang genoeg loopt om Nova's "mag
            # ik storen?"-vraag te triggeren.
            try:
                watcher.check_activity_interruption()
            except Exception as e:
                print(f"[Achtergrondthread] Fout in check_activity_interruption(): {e}")

        # Layer 5, Fase 2: activiteit periodiek detecteren, zodat
        # Layer 2 (pattern_matcher.py) dit als event_type kan meetellen
        # en context_manager.py altijd een vers "duration_minutes" heeft
        # klaarstaan, ook als er ondertussen niemand "context" typt.
        activity_detector = loader.loaded_modules.get("activity_detector")
        if activity_detector:
            try:
                activity_detector.detect_activity()
            except Exception as e:
                print(f"[Achtergrondthread] Fout in detect_activity(): {e}")

        # Layer 5, Fase 3: focus ook periodiek detecteren — dit is
        # BELANGRIJK om op een moment te meten waarop Kevin NIET zelf
        # net een commando aan het typen is (typen telt zelf als
        # input, en zou de meting dus altijd "actief" tonen). Deze
        # achtergrondmeting geeft daarom een eerlijker beeld dan enkel
        # via het "context"/"focus debug"-commando.
        focus_detector = loader.loaded_modules.get("focus_detector")
        if focus_detector:
            try:
                focus_detector.get_focus_info()
            except Exception as e:
                print(f"[Achtergrondthread] Fout in get_focus_info(): {e}")

        # Layer 5, Fase 4: webcam-aanwezigheid, ENKEL elke
        # PRESENCE_CHECK_INTERVAL_MINUTEN minuten (spaarzamer dan de
        # rest — zie uitleg bij de constante hierboven). We roepen
        # HIER context_manager.update_presence_info() aan (niet
        # presence_detector rechtstreeks) — die methode roept
        # presence_detector zelf aan EN onthoudt het resultaat, zodat
        # get_current() (dat wel elke minuut draait) de webcam niet
        # zelf hoeft te openen.
        if aantal_loops % PRESENCE_CHECK_INTERVAL_MINUTEN == 0:
            context_manager_voor_presence = loader.loaded_modules.get("context_manager")
            if context_manager_voor_presence:
                try:
                    context_manager_voor_presence.update_presence_info()
                except Exception as e:
                    print(f"[Achtergrondthread] Fout in update_presence_info(): {e}")

        # Layer 5: ook de volledige context (incl. should_interrupt-
        # beslissing) periodiek laten berekenen en loggen, zodat
        # context_log.jsonl een eerlijke, ongestoorde geschiedenis
        # bijhoudt — niet enkel momenten waarop Kevin zelf "context"
        # typte (wat de focus-meting zou vervuilen, want typen is zelf
        # input).
        context_manager = loader.loaded_modules.get("context_manager")
        if context_manager:
            try:
                context_manager.get_current()
            except Exception as e:
                print(f"[Achtergrondthread] Fout in context_manager.get_current(): {e}")

        # Proactieve weerwaarschuwing — ENKEL elke
        # WEATHER_CHECK_INTERVAL_MINUTEN minuten (zelfde soort spaarzame
        # aanpak als PRESENCE hierboven, geen externe API elke minuut
        # aanroepen). Meldt zelf max. 1x per dag per stad (zie
        # weather.py's _al_gemeld_vandaag()), dus geen risico op spam
        # ook al draait deze check regelmatig door.
        if aantal_loops % WEATHER_CHECK_INTERVAL_MINUTEN == 0:
            weather = loader.loaded_modules.get("weather")
            if weather:
                try:
                    weather.check_proactieve_waarschuwing()
                except Exception as e:
                    print(f"[Achtergrondthread] Fout in check_proactieve_waarschuwing(): {e}")

        # Layer 7 — periodiek reflecteren op verzamelde inzichten
        # (woordverband/tijdspatroon/kennisdichtheid/personality_drift).
        # emergence_engine.reflect() bevat zelf al de confidence-gate
        # (LAYER4_DREMPELS) en de timing-gate (_mag_nu_spreken(), vraagt
        # context_manager.can_interrupt()) — deze aanroep hier zorgt
        # enkel dat reflect() OOIT vanzelf gebeurt (voorheen enkel via
        # een handmatig debug-commando bereikbaar), niet dat de gates
        # zelf veranderen. Geen risico op spam: dezelfde gates die
        # eerder al "stil bleven" bij een ongeschikt moment gelden
        # hier evengoed.
        if aantal_loops % EMERGENCE_CHECK_INTERVAL_MINUTEN == 0:
            emergence = loader.loaded_modules.get("emergence_engine")
            if emergence:
                try:
                    emergence.reflect()
                except Exception as e:
                    print(f"[Achtergrondthread] Fout in emergence.reflect(): {e}")

        # Fase 5 (periodieke hertraining Intent Classifier, 28 juli
        # 2026): traint het ML-model opnieuw op training_data.json +
        # gecorrigeerde_voorbeelden.jsonl samen. Zelfde
        # aantal_loops-modulo-patroon als emergence_engine hierboven.
        # Duurt in de praktijk 1-2 seconden (zie opstart-logs) -- geen
        # noemenswaardige impact op de rest van de achtergrondthread.
        if aantal_loops % INTENT_CLASSIFIER_RETRAIN_INTERVAL_MINUTEN == 0:
            intent_classifier = loader.loaded_modules.get("intent_classifier")
            if intent_classifier:
                try:
                    intent_classifier.retrain_vanuit_bestanden()
                except Exception as e:
                    print(f"[Achtergrondthread] Fout in intent_classifier.retrain_vanuit_bestanden(): {e}")

        # Punt 2 (find_contradictions() een aanroeper geven, 6 augustus
        # 2026): periodiek de volledige kennisgraaf checken op botsende
        # is_a-relaties. Eigen spam-preventie zit in de module zelf
        # (onthoudt welke conflicten al gemeld zijn), dus deze aanroep
        # zorgt enkel dat de check OOIT vanzelf gebeurt -- net als bij
        # emergence_engine hierboven, geen extra risico op spam.
        if aantal_loops % CONTRADICTION_CHECK_INTERVAL_MINUTEN == 0:
            contradiction_checker = loader.loaded_modules.get("contradiction_checker")
            if contradiction_checker:
                try:
                    contradiction_checker.check_contradictions()
                except Exception as e:
                    print(f"[Achtergrondthread] Fout in contradiction_checker.check_contradictions(): {e}")

        # Punt 7 (topic_events_roadmap.md Fase 5, 13 augustus 2026):
        # periodiek checken of er een geschikt moment is voor een
        # tijdstip-gebaseerde topic-suggestie. Eigen spam-preventie zit
        # in de module zelf -- net als bij emergence_engine/
        # contradiction_checker hierboven, geen extra risico op spam.
        if aantal_loops % TOPIC_SUGGESTIONS_CHECK_INTERVAL_MINUTEN == 0:
            topic_suggestions = loader.loaded_modules.get("topic_suggestions")
            if topic_suggestions:
                try:
                    topic_suggestions.check_suggesties()
                except Exception as e:
                    print(f"[Achtergrondthread] Fout in topic_suggestions.check_suggesties(): {e}")

def main():
    global wachten_op_input, _afwezigheid_module
    bus = EventBus()

    # Modules laden
    loader = ModuleLoader(bus)
    loader.discover_and_load()

    # Afwezigheid (3 oktober 2026): zie on_chat_response().
    _afwezigheid_module = loader.loaded_modules.get("afwezigheid")

    # Bug #47-vervolg (5 okt 2026): bij een stop van buitenaf (Docker/
    # Unraid) alle modules netjes laten afsluiten. Bewust NA
    # discover_and_load(), zie installeer_stopsignaal().
    installeer_stopsignaal(loader)

    # Rechtstreeks abonneren op chat_response, zodat berichten
    # ONMIDDELLIJK geprint worden, ook als ze van de achtergrondthread
    # komen (proactieve meldingen), niet pas nadat Kevin zelf typt.
    bus.subscribe("chat_response", on_chat_response)

    # Achtergrondthread starten — laat Nova proactief kunnen spreken
    # terwijl de hoofdthread op input() wacht (bv. pauze-meldingen).
    # daemon=True zorgt dat deze thread automatisch stopt zodra Nova stopt.
    bg_thread = threading.Thread(target=achtergrond_loop, args=(loader,), daemon=True)
    bg_thread.start()

    # Tijdzone automatisch activeren
    zone = loader.event_bus.modules.get("zone")
    if zone:
        zone.enable_auto_timezone()

    # Boot banner
    print(MAGENTA + r"""
    ███╗   ██╗ ██████╗ ██╗   ██╗ █████╗ 
    ████╗  ██║██╔═══██╗██║   ██║██╔══██╗
    ██╔██╗ ██║██║   ██║██║   ██║███████║
    ██║╚██╗██║██║   ██║██║   ██║██╔══██║
    ██║ ╚████║╚██████╔╝╚██████╔╝██║  ██║
    ╚═╝  ╚═══╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═╝
    """ + RESET)

    print(CYAN + "        N O V A   S Y S T E M   B O O T" + RESET)
    print(CYAN + "───────────────────────────────────────────────" + RESET)

    # Module status
    for name, instance in sorted(loader.loaded_modules.items()):
        load_time = getattr(instance, "__load_time_ms__", None)

        if instance is None:
            print(f"{RED}[ FAIL ]{RESET} {name:<15}")
        else:
            if load_time is not None:
                print(f"{GREEN}[ OK ]{RESET}   {name:<15} ({load_time} ms)")
            else:
                print(f"{GREEN}[ OK ]{RESET}   {name:<15}")

    print(CYAN + "───────────────────────────────────────────────" + RESET)
    print(GREEN + " SYSTEM READY — Awaiting input..." + RESET + "\n")

    print("Nova is gestart. Typ een bericht (of 'exit' om te stoppen).")
    print("Gebruik 'teach <woord> <betekenis>' om Nova iets expliciet te leren.")

    

    global wachten_op_input

    while True:
        printed = set()
        wachten_op_input = True
        user_input = input(f"{GREEN}Jij: {RESET}")
        wachten_op_input = False

        # Bug #36-fix (24 september 2026): kapotte tekens (surrogaten,
        # bv. een half doorgekomen toetsaanslag) meteen hier weghalen,
        # VOORDAT een module de tekst ooit te zien krijgt. Zie de uitleg
        # bij maak_invoer_veilig() bovenaan dit bestand.
        user_input = maak_invoer_veilig(user_input)

        # Tijdstempel bij Kevin's eigen regel (30 sept 2026): de "Jij: "-
        # prompt verscheen al toen Nova klaar was met antwoorden -- dat
        # kan lang voor het typen zijn. Daarom herschrijven we de regel
        # pas NA Enter, met de echte verzendtijd:
        #   \033[A  = cursor 1 regel omhoog (naar de regel die je typte)
        #   \r      = naar het begin van die regel
        #   \033[K  = die regel leegmaken
        # Bewust NA maak_invoer_veilig(): kapotte tekens zouden het
        # printen anders kunnen laten crashen (Bug #36).
        # Beperking: is je bericht langer dan de breedte van de
        # terminal (loopt het over 2 regels), dan wordt enkel de
        # onderste regel herschreven -- puur cosmetisch.
        if TOON_TIJDSTEMPELS:
            print(f"\033[A\r\033[K{tijdstempel()}{GREEN}Jij: {RESET}{user_input}")

        # "exit" staat bewust BUITEN het vangnet hieronder: als het
        # afsluiten zelf ooit een fout zou geven, moet Nova toch stoppen,
        # niet stilletjes verder draaien.
        if user_input.lower() == "exit":
            # Chess-engine (Stockfish) netjes afsluiten, anders blijft het proces hangen
            chess_module = loader.loaded_modules.get("chess_engine")
            if chess_module and hasattr(chess_module, "shutdown"):
                print(f"{CYAN}Stockfish wordt afgesloten...{RESET}")
                chess_module.shutdown()

            # Presence-detector (MediaPipe) netjes afsluiten
            presence_module = loader.loaded_modules.get("presence_detector")
            if presence_module and hasattr(presence_module, "shutdown"):
                presence_module.shutdown()

            # Pattern Matcher (Layer 2) netjes afsluiten — sinds de
            # overstap naar tijdgebaseerd opslaan (18 juli 2026) kan er
            # tussen de laatste save-timer-tick en nu nog niet-
            # opgeslagen data in het geheugen zitten. shutdown() dwingt
            # één laatste, definitieve save af, zodat "exit" niet stil
            # de laatste minuten aan patronen laat verdwijnen.
            pattern_module = loader.loaded_modules.get("pattern_matcher")
            if pattern_module and hasattr(pattern_module, "shutdown"):
                pattern_module.shutdown()

            # Interruption Tracker (Activity-Aware Interaction) netjes
            # afsluiten — veiligheidsnet, ook al slaat record_feedback()
            # zelf al meteen op bij elke aanroep.
            interruption_module = loader.loaded_modules.get("interruption_tracker")
            if interruption_module and hasattr(interruption_module, "shutdown"):
                interruption_module.shutdown()
            break

        # Bug #36-fix (24 september 2026): vangnet rond de verwerking van
        # elk bericht. Voorheen kon EEN fout diep in eender welke module
        # (via bus.publish) de hele hoofdloop -- en dus heel Nova --
        # laten crashen. Nu wordt de fout getoond (met volledige
        # traceback, zodat hij niet verborgen raakt) en wacht Nova
        # gewoon op het volgende bericht. Zelfde patroon als de
        # try/except-blokken in achtergrond_loop() hierboven.
        # except Exception vangt GEEN Ctrl+C (KeyboardInterrupt) --
        # handmatig stoppen blijft dus gewoon werken.
        try:
            # Debug-/testcommando's (Layer 0/2/5/6/7, Activity-Aware
            # Interaction) zijn verhuisd naar modules/debug/debug_commands.py
            # om main.py overzichtelijk te houden. Zie 'help debug' voor
            # het volledige overzicht van beschikbare commando's.
            debug_module = loader.loaded_modules.get("debug_commands")
            if debug_module and debug_module.is_debug_command(user_input):
                bus.publish("debug_command", {"text": user_input})
                continue

            # Teach-flow wordt nu volledig afgehandeld door IntentRouter
            bus.publish("chat_message", {"sender": "Kevin", "text": user_input})

            # Memory events ophalen
            mem = loader.loaded_modules.get("memory")
            if mem:
                for e in mem.get_recent_events():
                    key = (e["event_type"], str(e["data"]))

                    # Chat mag NOOIT gededupliceerd worden
                    if e["event_type"] != "chat_response":
                        if key in printed:
                            continue
                        printed.add(key)

                    etype = e["event_type"]
                    data = e["data"]

                    # Semantic updates
                    if etype == "semantic_update":
                        meaning = data.get("meaning") or data.get("definition") or "onbekend"
                        status = data.get("status", "")
                        word = data.get("word", "")
                        if status == "new":
                            print(f"Nova leerde een nieuw woord: {word} → {meaning}")
                        elif status == "updated":
                            print(f"Nova herkende {word} nu als {meaning}")
                        elif status == "duplicate":
                            print(f"Nova wist dit al: {word} betekent {meaning}")
                        elif status == "auto":
                            print(f"Nova herkende automatisch {word} als {meaning}")

                    # Pattern updates
                    elif etype == "pattern_update":
                        counts = data["event_counts"]
                        words = data["word_counts"]
                        print("Nova zag patronen:")
                        print("  Events:", counts)
                        print("  Top woorden:", words)

                    # Chat responses worden nu NIET meer hier geprint —
                    # dat gebeurt via de rechtstreekse on_chat_response()
                    # subscriber hierboven (nodig voor proactieve berichten
                    # van de achtergrondthread). We slaan dit event-type
                    # hier gewoon over om dubbel printen te voorkomen.
                    elif etype == "chat_response":
                        pass

                    # Timezone ready
                    elif etype == "time_zone_ready":
                        offset = data["offset_minutes"]
                        dst = data["dst_active"]
                        print(f"TimeZoneModule geladen → offset: {offset} min, DST actief: {dst}")

        except Exception as e:
            print(f"{RED}[Hoofdloop] Onverwachte fout bij het verwerken van je bericht: {e}{RESET}")
            traceback.print_exc()
            print(f"{RED}[Hoofdloop] Nova draait gewoon verder.{RESET}")


if __name__ == "__main__":
    main()