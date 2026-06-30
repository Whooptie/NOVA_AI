from core.event_bus import EventBus
from core.module_loader import ModuleLoader
import os

def test_logger_module():
    bus = EventBus()
    loader = ModuleLoader(bus)
    loader.discover_and_load()

    # Controleer of logbestand is aangemaakt
    assert os.path.exists("logs/nova.log")
