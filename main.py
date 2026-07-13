# main.py

import os
import sys
import ctypes
import time
import threading

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
TYPEWRITER_SNELHEID = 0.04

def print_nova_typewriter(tekst):
    """
    Print Nova's antwoord met een typewriter-effect: 'Nova: ' verschijnt
    direct in 1 blok, en de rest van de zin komt daarna letter per letter.
    """
    # "Nova: " blijft in 1 keer verschijnen — geen vertraging hier
    print(f"{MAGENTA}Nova: {RESET}", end="", flush=True)

    # De rest van de tekst letter per letter
    for letter in tekst:
        print(f"{MAGENTA}{letter}{RESET}", end="", flush=True)
        time.sleep(TYPEWRITER_SNELHEID)

    print()  # nieuwe regel op het einde, anders plakt de volgende prompt eraan vast

# Houdt bij of de hoofdthread op dit moment op input() staat te wachten.
# Nodig om te weten of we na een proactief bericht de "Jij: "-prompt
# opnieuw moeten tekenen (enkel relevant als we ECHT aan het wachten
# zijn — niet wanneer Nova toch al een normaal antwoord aan het geven is).
wachten_op_input = False

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
    msg = data.get("text") or data.get("msg") or ""

    # instant=True (bv. help.py) betekent: lang, opgemaakt overzicht,
    # geen gesproken zin — toon in 1 keer, geen typewriter-effect.
    if data.get("instant"):
        print(f"{MAGENTA}Nova: {msg}{RESET}")
    else:
        print_nova_typewriter(msg)

    # Als de hoofdthread op dit moment op input() staat te wachten,
    # betekent dit dat DIT bericht proactief kwam (van de achtergrond-
    # thread) — de "Jij: "-prompt is dan al geprint maar raakt nu
    # visueel "begraven" onder Nova's bericht. We tekenen hem opnieuw
    # zodat het weer duidelijk is waar Kevin kan typen.
    if wachten_op_input:
        print(f"{GREEN}Jij: {RESET}", end="", flush=True)

def achtergrond_loop(loader):
    """
    Draait continu op de achtergrond, los van de input()-lus in main().
    Checkt elke 60 seconden of er een proactieve melding nodig is
    (voorlopig enkel de pauze-check van session_watcher).
    """
    while True:
        time.sleep(60)

        watcher = loader.loaded_modules.get("session_watcher")
        if watcher:
            try:
                watcher.check_pauze()
            except Exception as e:
                print(f"[Achtergrondthread] Fout in check_pauze(): {e}")

def main():
    global wachten_op_input
    bus = EventBus()

    # Modules laden
    loader = ModuleLoader(bus)
    loader.discover_and_load()

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

        # Tijdelijk test-commando voor Fase 4 (mag je later weer verwijderen)
        if user_input.lower() == "onderhoud":
            mem = loader.loaded_modules.get("memory")
            if mem:
                print(f"{CYAN}Onderhoudsronde wordt gestart...{RESET}")
                mem.run_maintenance()
            else:
                print(f"{RED}Memory-module niet gevonden.{RESET}")
            continue
        
        # Tijdelijk test-commando voor Layer 5 Fase 1 (mag je later weer verwijderen)
        if user_input.lower() == "context":
            ctx_mgr = loader.loaded_modules.get("context_manager")
            if not ctx_mgr:
                print(f"{RED}context_manager-module niet gevonden.{RESET}")
                continue
            print(f"{CYAN}{ctx_mgr.get_context_summary()}{RESET}")
            continue

        # Tijdelijk test-commando: geschiedenis van Layer 5-beslissingen
        # (mag je later weer verwijderen). Gebruik: "context geschiedenis"
        # of "context geschiedenis 20" voor een ander aantal regels.
        if user_input.lower().startswith("context geschiedenis"):
            ctx_mgr = loader.loaded_modules.get("context_manager")
            if not ctx_mgr:
                print(f"{RED}context_manager-module niet gevonden.{RESET}")
                continue

            delen = user_input.split()
            aantal = 10
            if len(delen) >= 3 and delen[2].isdigit():
                aantal = int(delen[2])

            regels = ctx_mgr.get_recent_log(aantal=aantal)
            if not regels:
                print(f"{CYAN}Nog geen geschiedenis beschikbaar.{RESET}")
                continue

            print(f"{CYAN}--- Laatste {len(regels)} Layer 5-beslissing(en) ---{RESET}")
            for regel in regels:
                tijd = regel.get("time", "?")
                should_interrupt = regel.get("should_interrupt")
                reden = regel.get("reden", "?")
                print(f"  {tijd} — mag onderbreken: {should_interrupt} — reden: {reden}")
            continue

        # Tijdelijk test-commando voor Layer 2 Fase 3-4 (mag je later weer verwijderen)
        if user_input.lower().startswith("patronen"):
            pm = loader.loaded_modules.get("pattern_matcher")
            if not pm:
                print(f"{RED}pattern_matcher-module niet gevonden.{RESET}")
                continue

            delen = user_input.split()
            if len(delen) < 2:
                # Geen event_type opgegeven: toon algemene stats
                print(f"{CYAN}Layer 2 stats: {pm.get_stats()}{RESET}")
                continue

            event_type = delen[1]

            print(f"{CYAN}--- Patroon voor '{event_type}' ---{RESET}")
            print("Ruwe data:", pm.get_pattern(event_type))
            print("Is nu actief?:", pm.is_pattern_active(event_type))
            print("Volgende verwachte moment:", pm.predict_next_occurrence(event_type))
            print("Anomalieën (laatste 7 dagen):", pm.get_anomalies(days=7))
            continue
            
        if user_input.lower() == "exit":
            # Chess-engine (Stockfish) netjes afsluiten, anders blijft het proces hangen
            chess_module = loader.loaded_modules.get("chess_engine")
            if chess_module and hasattr(chess_module, "shutdown"):
                print(f"{CYAN}Stockfish wordt afgesloten...{RESET}")
                chess_module.shutdown()
            break

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


if __name__ == "__main__":
    main()

