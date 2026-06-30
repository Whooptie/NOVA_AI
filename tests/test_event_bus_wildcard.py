from core.event_bus import EventBus

def test_event_bus_wildcard(capsys):
    bus = EventBus()
    results = []

    def wildcard_handler(event):
        results.append(event)

    # Abonneer op alle events
    bus.subscribe("*", wildcard_handler)

    # Publiceer een paar events
    bus.publish("greet", {"msg": "Hallo Nova"})
    bus.publish("memory_update", {"key": "test", "value": 42})

    # Controleer dat beide events zijn opgevangen
    assert len(results) == 2
    assert results[0]["event_type"] == "greet"
    assert results[0]["data"] == {"msg": "Hallo Nova"}
    assert results[1]["event_type"] == "memory_update"
    assert results[1]["data"] == {"key": "test", "value": 42}

    # Controleer dat er ook output is gelogd
    captured = capsys.readouterr()
    # Dit checkt dat er iets naar stdout/stderr is gegaan (optioneel)
    assert captured.out == ""  # geen directe print, alleen logging
