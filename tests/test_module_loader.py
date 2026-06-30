from core.event_bus import EventBus
from core.module_loader import ModuleLoader

def test_module_loader():
    bus = EventBus()
    loader = ModuleLoader(bus)
    loader.discover_and_load()

    # Controleer of modules geladen zijn
    assert isinstance(loader.loaded_modules, dict)
