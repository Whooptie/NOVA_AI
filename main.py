# main.py
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

