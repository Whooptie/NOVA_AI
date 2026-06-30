import json
from core.event_bus import EventBus
from modules import memory, semantic

def test_semantic_timestamp(setup_semantic_module):
    bus, mem, sem, concepts_file, concepts_log = setup_semantic_module

    bus.publish("teach_concept", {"word": "pizza", "meaning": "food"})
    with open(concepts_log, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f]

    assert all("timestamp" in entry for entry in lines)
    assert all("T" in entry["timestamp"] for entry in lines)