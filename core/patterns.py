# core/patterns.py

import time
import re

class PatternsModule:
    def __init__(self, event_bus):
        self.event_bus = event_bus

        self.word_counts = {}
        self.event_counts = {}

        self.stopwords = {
            "de","het","een","en","of","maar","want","dus","is","ben","zijn",
            "hoe","wat","wie","waar","waarom","wanneer","welke","dat","dit",
            "die","als","dan","er","hier","daar","nu","straks","vandaag",
            "morgen","gisteren","weer","tijd","dag","datum"
        }

        self.last_update = 0
        self.update_interval = 5

        event_bus.subscribe("chat_message", self.on_chat)

    def on_chat(self, data, event_type=None):
        text = (data.get("text") or "").lower().strip()

        self.event_counts[event_type] = self.event_counts.get(event_type, 0) + 1

        words = re.findall(r"\w+", text)
        changed = False

        for w in words:
            if w in self.stopwords:
                continue
            old = self.word_counts.get(w, 0)
            self.word_counts[w] = old + 1
            if old == 0:
                changed = True

        if not changed:
            return

        now = time.time()
        if now - self.last_update < self.update_interval:
            return

        self.last_update = now

        self.event_bus.publish("pattern_update", {
            "word_counts": dict(sorted(self.word_counts.items(), key=lambda x: -x[1])[:10]),
            "event_counts": dict(self.event_counts)
        })


def init_module(event_bus):
    instance = PatternsModule(event_bus)
    event_bus.publish("module_loaded", {"name": "patterns"})
    return instance
