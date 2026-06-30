# tests/test_semantic_learning.py
from core.event_bus import EventBus
from modules import memory, semantic

def test_semantic_learning(setup_semantic_module):
    bus, mem, sem, concepts_file, concepts_log = setup_semantic_module

    bus.publish("chat_message", {"sender": "Kevin", "text": "Pizza is lekker"})
    bus.publish("chat_message", {"sender": "Kevin", "text": "Ik hou van pizza"})
    bus.publish("chat_message", {"sender": "Kevin", "text": "Pizza met kaas"})

    buffer = mem.get_recent_events()
    updates = [e for e in buffer if e["event_type"] == "semantic_update"]

    concepts = updates[-1]["data"]["concepts"]
    assert concepts["pizza"]["senses"][0]["definition"] == "unknown"

    bus.publish("teach_concept", {"word": "pizza", "meaning": "food"})
    buffer = mem.get_recent_events()
    updates = [e for e in buffer if e["event_type"] == "semantic_update"]
    concepts = updates[-1]["data"]["concepts"]
    assert concepts["pizza"]["senses"][0]["definition"] == "food"