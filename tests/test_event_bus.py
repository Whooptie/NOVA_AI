from core.event_bus import EventBus

def test_event_bus():
    bus = EventBus()
    results = []

    def handler(data):
        results.append(data)

    bus.subscribe("test_event", handler)
    bus.publish("test_event", {"msg": "Hello Nova"})

    assert results == [{"msg": "Hello Nova"}]
