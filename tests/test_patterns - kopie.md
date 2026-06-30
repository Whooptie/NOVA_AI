from core.event_bus import EventBus
from modules import memory, patterns

def test_pattern_recognition(tmp_path):
    storage_file = tmp_path / "interactions.jsonl"
    bus = EventBus()
    mem = memory.MemoryModule(bus, buffer_size=10, storage_file=str(storage_file))

    patterns.PatternRecognitionModule(bus, mem)

    bus.publish("chat_message", {"sender": "Kevin", "text": "Hallo Nova"})
    bus.publish("chat_message", {"sender": "Nova", "text": "Hallo Kevin!"})
    bus.publish("system_event", {"msg": "Test klaar"})
    bus.publish("chat_message", {"sender": "Kevin", "text": "Hallo opnieuw Nova"})

    buffer = mem.get_recent_events()

    # ✅ Filter alleen originele events
    originals = [e for e in buffer if e["event_type"] != "pattern_update"]
    assert len(originals) == 4

    # ✅ Check dat er pattern_update events zijn
    updates = [e for e in buffer if e["event_type"] == "pattern_update"]
    assert len(updates) >= 1

    # Controleer inhoud van een pattern_update
    data = updates[-1]["data"]
    assert "chat_message" in data["event_counts"]
    assert "hallo" in data["word_counts"]

