# tests/conftest.py
import pytest
from core.event_bus import EventBus
from modules import memory, semantic

@pytest.fixture
def setup_semantic_module(tmp_path):
    """Maak een schone SemanticConceptsModule met tijdelijke bestanden."""
    storage_file = tmp_path / "interactions.jsonl"
    concepts_file = tmp_path / "concepts.json"
    concepts_log = tmp_path / "concepts.jsonl"

    bus = EventBus()
    mem = memory.MemoryModule(bus, buffer_size=10, storage_file=str(storage_file))
    sem = semantic.SemanticConceptsModule(
        bus, mem,
        concepts_file=str(concepts_file),
        concepts_log=str(concepts_log)
    )
    return bus, mem, sem, concepts_file, concepts_log
