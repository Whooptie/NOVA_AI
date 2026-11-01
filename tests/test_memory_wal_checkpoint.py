# tests/test_memory_wal_checkpoint.py
# Punt 32: na vacuum_db() moet het -wal bestand weer leeg zijn.

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.memory import MemoryModule


class DummyEventBus:
    def __init__(self):
        self.gepubliceerd = []

    def subscribe(self, event_type, handler):
        pass

    def publish(self, event_type, data=None):
        self.gepubliceerd.append((event_type, data))


@pytest.fixture
def memory(tmp_path):
    # MemoryModule doet I/O in __init__() (map + databank), dus altijd een
    # eigen save_path in tmp_path meegeven: de echte data/ blijft onaangeroerd.
    mem = MemoryModule(DummyEventBus(), save_path=tmp_path / "interactions.jsonl")
    yield mem
    mem.stop_maintenance()
    mem._on_shutdown()


def _vul(mem, aantal=2000):
    for i in range(aantal):
        mem.on_event({"text": f"testbericht {i} " + "x" * 200}, "chat_message")
    mem._flush_buffer()


def _wal_grootte(mem):
    wal = Path(str(mem.db_path) + "-wal")
    return wal.stat().st_size if wal.exists() else 0


def test_vacuum_maakt_wal_bestand_leeg(memory):
    _vul(memory)
    memory.vacuum_db()
    assert _wal_grootte(memory) == 0


def test_vacuum_laat_data_intact(memory):
    _vul(memory, aantal=300)
    memory.vacuum_db()
    aantal = memory.conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
    assert aantal == 300


def test_vacuum_zonder_verbinding_crasht_niet(memory):
    memory.conn.close()
    memory.conn = None
    memory.vacuum_db()  # mag niets doen, geen exception
    memory._afgesloten = True  # fixture-opruiming overslaan