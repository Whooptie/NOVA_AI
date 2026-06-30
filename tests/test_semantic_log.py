import json
from core.event_bus import EventBus
from modules import memory, semantic

def test_semantic_log(setup_semantic_module):
    bus, mem, sem, concepts_file, concepts_log = setup_semantic_module

    bus.publish("chat_message", {"sender": "Kevin", "text": "Pizza is lekker"})
    bus.publish("chat_message", {"sender": "Kevin", "text": "Ik hou van pizza"})
    bus.publish("chat_message", {"sender": "Kevin", "text": "Pizza met kaas"})

    with open(concepts_log, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f]
    assert any(l["action"] == "auto" for l in lines)

    bus.publish("teach_concept", {"word": "pizza", "meaning": "food"})
    with open(concepts_log, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f]
    assert any(l["action"] == "teach" and l["word"] == "pizza" for l in lines)

