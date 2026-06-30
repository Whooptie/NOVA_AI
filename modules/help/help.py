# modules/help/help.py

from modules.help.topics import algemeen, schaken

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
        else:
            tekst = algemeen.get_help()

        self.event_bus.publish("chat_response", {"text": tekst})


def init_module(event_bus, semantic_module=None):
    instance = HelpModule(event_bus)
    event_bus.publish("module_loaded", {"name": "help"})
    return instance