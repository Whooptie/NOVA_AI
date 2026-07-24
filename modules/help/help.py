# modules/help/help.py

from modules.help.topics import algemeen, schaken, debug

C_RESET = "\033[0m"
C_GREEN = "\033[92m"
C_CYAN = "\033[96m"

def dbg(label):
    print(f"{C_CYAN}[HELP]{C_RESET} {label}")


class HelpModule:
    def __init__(self, event_bus):
        self.event_bus = event_bus

        event_bus.subscribe("intent_help", self.handle_help)
        dbg(f"{C_GREEN}HelpModule geladen{C_RESET}")

    def handle_help(self, data, event_type=None):
        topic = data.get("topic", "").strip().lower()

        if topic == "schaken":
            chess_module = self.event_bus.get_module("chess_engine")
            tekst = schaken.get_help(chess_module)
        elif topic == "debug":
            tekst = debug.get_help()
        else:
            tekst = algemeen.get_help()

        # instant=True: dit is een lang, opgemaakt overzicht (meerdere
        # regels, emoji-kopjes), geen gesproken zin. Typewriter-effect
        # zou hier alleen maar onnodig lang duren, dus we tonen dit
        # in één keer i.p.v. letter per letter.
        self.event_bus.publish("chat_response", {"text": tekst, "instant": True})


def init_module(event_bus, semantic_module=None):
    instance = HelpModule(event_bus)
    event_bus.publish("module_loaded", {"name": "help"})
    return instance