from core.event_bus import EventBus
from core.module_loader import ModuleLoader

def test_hello_module(capsys):
    bus = EventBus()
    loader = ModuleLoader(bus)
    loader.discover_and_load()

    # Controleer of de Hello-module een event print
    captured = capsys.readouterr()
    assert "Hallo vanuit Nova!" in captured.out
