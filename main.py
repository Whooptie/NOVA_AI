# main.py
import os
import sys
import ctypes

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

def main():
    bus = EventBus()

    # Modules laden
    loader = ModuleLoader(bus)
    loader.discover_and_load()

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

    

    while True:
        printed = set()
        user_input = input(f"{GREEN}Jij: {RESET}")

        # Tijdelijk test-commando voor Fase 4 (mag je later weer verwijderen)
        if user_input.lower() == "onderhoud":
            mem = loader.loaded_modules.get("memory")
            if mem:
                print(f"{CYAN}Onderhoudsronde wordt gestart...{RESET}")
                mem.run_maintenance()
            else:
                print(f"{RED}Memory-module niet gevonden.{RESET}")
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

                # Chat responses (uniform: altijd 'text')
                elif etype == "chat_response":
                    msg = data.get("text") or data.get("msg") or ""
                    print(f"{MAGENTA}Nova: {msg}{RESET}")

                # Time engine
                elif etype == "time_response":
                    print(f"{MAGENTA}Nova: {data.get('msg')}{RESET}")

                # Weather
                elif etype == "weather_response":
                    print(f"{MAGENTA}Nova: {data.get('msg')}{RESET}")

                # Date
                elif etype == "date_response":
                    print(f"{MAGENTA}Nova: {data.get('msg')}{RESET}")
                
                # Math
                elif etype == "math_response":
                    print(f"{MAGENTA}Nova: {data.get('msg')}{RESET}")

                # Timezone ready
                elif etype == "time_zone_ready":
                    offset = data["offset_minutes"]
                    dst = data["dst_active"]
                    print(f"TimeZoneModule geladen → offset: {offset} min, DST actief: {dst}")


if __name__ == "__main__":
    main()

