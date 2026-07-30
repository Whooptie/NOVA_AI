# core/logger.py
#
# LoggerModule — logt ENKEL fouten en waarschuwingen naar logs/nova.log
# (niet meer elk event, dat doet memory.py met interactions.jsonl al).
# Heeft rotatie zodat het bestand nooit ongelimiteerd kan groeien.

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

class LoggerModule:
    def __init__(self, event_bus):
        Path("logs").mkdir(exist_ok=True)

        # RotatingFileHandler: roteert automatisch bij 5 MB,
        # houdt max 3 oude versies bij (nova.log.1, .2, .3)
        handler = RotatingFileHandler(
            "logs/nova.log",
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8"
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )

        self.logger = logging.getLogger("nova")
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(handler)

        # Event-types die we altijd als ECHTE fout behandelen (ERROR),
        # ook al heet het event zelf niet "error"
        self.explicit_error_events = {
            "memory_write_failed",
        }

        # Event-types die we als waarschuwing behandelen (WARNING) —
        # minder ernstig dan een error, maar toch het melden waard
        self.explicit_warning_events = set()

        def log_event(data, event_type=None):
            if event_type is None:
                return

            naam = event_type.lower()
            is_error = (
                "error" in naam
                or event_type in self.explicit_error_events
            )
            is_warning = (
                "fail" in naam
                or event_type in self.explicit_warning_events
            )

            if is_error:
                self.logger.error(f"Event: {event_type} | Data: {data}")
            elif is_warning:
                self.logger.warning(f"Event: {event_type} | Data: {data}")

        event_bus.subscribe("*", log_event)
        self.logger.info("Logger-module gestart — logt fouten/waarschuwingen (en opstart als info).")


def init_module(event_bus):
    logger = LoggerModule(event_bus)
    event_bus.publish("module_loaded", {"name": "logger"})
    return logger