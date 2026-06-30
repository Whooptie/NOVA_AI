# tests/test_semantic.py
from core.event_bus import EventBus
from modules import memory, semantic

def test_semantic_concepts(tmp_path):
    # Setup: EventBus + MemoryModule
    storage_file = tmp_path / "interactions.jsonl"
    bus = EventBus()
    mem = memory.MemoryModule(bus, buffer_size=10, storage_file=str(storage_file))

    # Laad SemanticConceptsModule
    semantic.SemanticConceptsModule(bus, mem)

    # Publiceer een paar chat_messages
    bus.publish("chat_message", {"sender": "Kevin", "text": "Hallo Nova"})
    bus.publish("chat_message", {"sender": "Nova", "text": "Hallo Kevin!"})

    # Haal buffer op
    buffer = mem.get_recent_events()

    # Filter semantic_update events
    updates = [e for e in buffer if e["event_type"] == "semantic_update"]
    assert len(updates) >= 1

    # Controleer inhoud van laatste semantic_update
    concepts = updates[-1]["data"]["concepts"]
    assert concepts["hallo"]["senses"][0]["definition"] == "greeting"
    assert concepts["nova"]["senses"][0]["definition"] == "self"
    assert concepts["kevin"]["senses"][0]["definition"] == "user"