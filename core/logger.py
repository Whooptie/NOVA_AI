# core/logger.py
import logging
from pathlib import Path

class LoggerModule:
    def __init__(self, event_bus):
        Path("logs").mkdir(exist_ok=True)

        logging.basicConfig(
            filename="logs/nova.log",
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
        )

        def log_event(data, event_type=None):
            logging.info(f"Event: {event_type} | Data: {data}")

        event_bus.subscribe("*", log_event)
        logging.info("Logger-module succesvol geladen en luistert naar alle events.")

def init_module(event_bus):
    logger = LoggerModule(event_bus)
    event_bus.publish("module_loaded", {"name": "logger"})
    return logger