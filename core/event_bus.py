# core/event_bus.py
from typing import Callable, Dict, List, Any

class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self.modules: Dict[str, Any] = {}

    # -----------------------------
    # Module-registratie
    # -----------------------------
    def register_module(self, name, instance):
        self.modules[name] = instance

    def get_module(self, name):
        return self.modules.get(name)

    # -----------------------------
    # Event-systeem
    # -----------------------------
    def subscribe(self, event_type, handler):
        # voorkom dubbele subscriptions
        handlers = self._subscribers.setdefault(event_type, [])
        if handler not in handlers:
            handlers.append(handler)

    def publish(self, event_type, data):
        # 1. Specifieke handlers
        for handler in self._subscribers.get(event_type, []):
            try:
                handler(data, event_type)
            except TypeError:
                handler(data)

        # 2. Wildcard handlers
        for handler in self._subscribers.get("*", []):
            try:
                handler(data, event_type)
            except TypeError:
                handler(data)
