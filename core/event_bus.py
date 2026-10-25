# core/event_bus.py
#
# Bug #46 (25 oktober 2026): publish() riep een handler een tweede keer aan als
# de eerste aanroep een TypeError gaf. Een echte fout IN een handler liet die
# daardoor half dubbel draaien en gaf een misleidende foutmelding.
#
# Nu: bij het eerste gebruik kijken we met inspect.signature() hoeveel
# argumenten de handler aanneemt (1 of 2) en roepen we hem EEN keer aan met het
# juiste aantal. Een fout in een handler wordt gelogd (bestand + geheugen) en
# stopt de andere handlers niet.
import inspect
import os
import traceback
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Any

# logs/handler_fouten.log naast de map "core" (in Docker: /app/logs/)
_LOGBESTAND = Path(__file__).resolve().parent.parent / "logs" / "handler_fouten.log"
_MAX_LOG_BYTES = 1_000_000


class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self.modules: Dict[str, Any] = {}
        self._aantal_args: Dict[Any, int] = {}   # cache: handler -> 1 of 2
        self.fouten = deque(maxlen=50)           # laatste 50 handler-fouten (voor Nova)
        self.fout_teller = 0                     # telt ALLE fouten ooit (deque vergeet oude)

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

    def _bepaal_aantal_args(self, handler):
        """2 = handler(data, event_type), 1 = handler(data)."""
        try:
            params = inspect.signature(handler).parameters.values()
        except (ValueError, TypeError):
            return 2                              # onbekend: oude voorkeur
        positioneel = 0
        for p in params:
            if p.kind == p.VAR_POSITIONAL:
                return 2                          # *args: past altijd
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD):
                positioneel += 1
        return 2 if positioneel >= 2 else 1

    def _roep_aan(self, handler, data, event_type):
        try:
            aantal = self._aantal_args.get(handler)
            if aantal is None:
                aantal = self._bepaal_aantal_args(handler)
                self._aantal_args[handler] = aantal
        except TypeError:                         # handler niet hashbaar: geen cache
            aantal = self._bepaal_aantal_args(handler)
        try:
            if aantal == 2:
                handler(data, event_type)
            else:
                handler(data)
        except Exception as e:
            self._log_fout(handler, event_type, e)

    def _log_fout(self, handler, event_type, fout):
        naam = getattr(handler, "__qualname__", None) or repr(handler)
        tijd = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.fout_teller += 1
        self.fouten.append({
            "tijd": tijd, "event": event_type, "handler": naam,
            "fout": f"{type(fout).__name__}: {fout}",
        })
        print(f"[EVENTBUS] Fout in handler {naam} bij '{event_type}': "
              f"{type(fout).__name__}: {fout}")
        # volledige traceback ook in de console (stderr), zoals voorheen
        traceback.print_exception(type(fout), fout, fout.__traceback__)
        try:
            _LOGBESTAND.parent.mkdir(parents=True, exist_ok=True)
            # Roteren: boven 1 MB wordt het oude log "handler_fouten.log.1"
            if _LOGBESTAND.exists() and _LOGBESTAND.stat().st_size > _MAX_LOG_BYTES:
                os.replace(_LOGBESTAND, _LOGBESTAND.with_name(_LOGBESTAND.name + ".1"))
            with open(_LOGBESTAND, "a", encoding="utf-8") as f:
                f.write(f"[{tijd}] event='{event_type}' handler={naam}\n")
                f.write("".join(traceback.format_exception(
                    type(fout), fout, fout.__traceback__)))
                f.write("\n")
        except Exception:
            pass                                  # loggen mag nooit zelf crashen

    def publish(self, event_type, data):
        # 1. Specifieke handlers (kopie van de lijst: handlers mogen zich
        #    tijdens het publiceren (af)melden)
        for handler in list(self._subscribers.get(event_type, [])):
            self._roep_aan(handler, data, event_type)

        # 2. Wildcard handlers
        for handler in list(self._subscribers.get("*", [])):
            self._roep_aan(handler, data, event_type)