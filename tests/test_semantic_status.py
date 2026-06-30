# tests/test_semantic_status.py
import json
from core.event_bus import EventBus
from modules import memory, semantic

def test_semantic_status(setup_semantic_module):
    bus, mem, sem, concepts_file, concepts_log = setup_semantic_module

    bus.publish("teach_concept", {"word": "pizza", "meaning": "food"})
    with open(concepts_log, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f]
    # Eerste teach → updated i.p.v. new
    assert any(l["status"] == "updated" and l["word"] == "pizza" and l["action"] == "teach" for l in lines)

    bus.publish("teach_concept", {"word": "pizza", "meaning": "snack"})
    with open(concepts_log, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f]
    # Tweede teach → ook updated
    assert any(l["status"] == "updated" and l["word"] == "pizza" and l["action"] == "teach" for l in lines)
