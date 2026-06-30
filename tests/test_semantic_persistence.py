# tests/test_semantic_persistence.py
import json
from core.event_bus import EventBus
from modules import memory, semantic

def test_semantic_persistence(tmp_path):
    # Setup: EventBus + MemoryModule
    storage_file = tmp_path / "interactions.jsonl"
    concepts_file = tmp_path / "concepts.json"
    bus = EventBus()
    mem = memory.MemoryModule(bus, buffer_size=10, storage_file=str(storage_file))

    # Laad SemanticConceptsModule met custom concepts_file
    sem = semantic.SemanticConceptsModule(bus, mem, concepts_file=str(concepts_file))

    # Leer Nova een nieuw concept
    bus.publish("teach_concept", {"word": "pizza", "meaning": "food"})

    # ✅ Check dat het bestand is aangemaakt
    assert concepts_file.exists()

    # ✅ Check dat 'pizza' in het bestand staat
    with open(concepts_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["pizza"]["senses"][0]["definition"] == "food"

    # Herlaad module om te zien of ze het onthoudt
    sem2 = semantic.SemanticConceptsModule(bus, mem, concepts_file=str(concepts_file))
    assert sem2.concepts["pizza"]["senses"][0]["definition"] == "food"