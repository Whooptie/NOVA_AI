# modules/time/time.py
from datetime import datetime

class TimeModule:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.zone = event_bus.get_module("zone")  # optioneel

        # Elke intent_time_query = tijdvraag
        event_bus.subscribe("intent_time_query", self.on_time_intent)

    def now(self):
        if self.zone:
            return self.zone.now_local()
        return datetime.now()

    def on_time_intent(self, data, event_type=None):
        # Geen tekst-checks meer: IntentRouter heeft al beslist
        self.answer_time()

    def answer_time(self):
        now = self.now()
        msg = now.strftime("Het is nu %H:%M.")
        self.event_bus.publish("layer4_response", {"text": msg})


def init_module(event_bus):
    mod = TimeModule(event_bus)
    event_bus.publish("module_loaded", {"name": "time"})
    return mod
