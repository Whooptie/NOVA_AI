import os
from core.event_bus import EventBus
from modules import memory

def test_memory_buffer_and_storage(tmp_path):
    storage_file = tmp_path / "interactions.jsonl"
    bus = EventBus()
    mem = memory.MemoryModule(bus, buffer_size=3, storage_file=str(storage_file))

    bus.publish("chat_message", {"sender": "Kevin", "text": "Hallo Nova"})
    bus.publish("chat_message", {"sender": "Nova", "text": "Hallo Kevin!"})
    bus.publish("system_event", {"msg": "Test klaar"})
    bus.publish("chat_message", {"sender": "Kevin", "text": "Nog eentje"})

    # ✅ Buffer check (max 3 events, oudste eruit)
    buffer = mem.get_recent_events()
    assert len(buffer) == 3
    assert buffer[0]["data"]["sender"] == "Nova"   # "Hallo Kevin!"
    assert buffer[1]["data"]["msg"] == "Test klaar"
    assert buffer[2]["data"]["text"] == "Nog eentje"

    # ✅ Bestand check (alle 4 events moeten er staan)
    assert storage_file.exists()
    lines = storage_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4
    assert '"Hallo Nova"' in lines[0]
    assert '"Hallo Kevin!"' in lines[1]
    assert '"Test klaar"' in lines[2]
    assert '"Nog eentje"' in lines[3]
