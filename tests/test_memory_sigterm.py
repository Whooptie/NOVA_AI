# tests/test_memory_sigterm.py
"""
Tests voor Bug #47 (5 oktober 2026): memory.py bij SIGTERM.

Het probleem: wanneer Docker/Unraid de container stopt (bv. de server
valt uit of wordt afgesloten), krijgt Nova een SIGTERM. memory.py's
_on_signal() sloot dan wel de databank, maar liet Nova gewoon verder
draaien -- met rode "Memory SQLite flush error: 'NoneType' object has
no attribute 'executemany'"-regels tot Docker haar ~10 seconden later
hard afschoot.

Drie lagen getest:
1. _flush_buffer() met een gesloten databank: stil overslaan, geen fout.
2. _on_shutdown() mag veilig twee keer lopen (signal + atexit).
3. Een ECHT apart Python-proces dat op input() wacht, terwijl een
   achtergrondthread events blijft sturen, krijgt een echte SIGTERM:
   het moet snel en zonder flush-fouten stoppen.

Alles met tmp_path: nooit de echte data/-map.
"""

import os
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from core.memory import MemoryModule


class DummyEventBus:
    def __init__(self):
        self.subscribers = {}

    def subscribe(self, event_type, callback):
        self.subscribers.setdefault(event_type, []).append(callback)

    def publish(self, event_type, data):
        for callback in self.subscribers.get(event_type, []):
            callback(data, event_type=event_type)
        for callback in self.subscribers.get("*", []):
            callback(data, event_type=event_type)


@pytest.fixture
def memory(tmp_path):
    # __init__ doet I/O (maakt de databank aan) -> save_path naar tmp_path.
    # Het registreert ook een SIGTERM-handler en een atexit-hook: die
    # zetten we na de test weer terug, zodat andere tests er geen last van
    # hebben.
    oude_handler = signal.getsignal(signal.SIGTERM)
    mem = MemoryModule(DummyEventBus(), save_path=tmp_path / "interactions.jsonl")
    yield mem
    mem.stop_maintenance()
    mem._on_shutdown()
    signal.signal(signal.SIGTERM, oude_handler)


class TestFlushNaAfsluiten:

    def test_flush_met_gesloten_databank_geeft_geen_fout(self, memory, capsys):
        memory._on_shutdown()
        capsys.readouterr()
        memory.write_buffer.append({"timestamp": time.time(), "event_type": "x", "data": {}})
        memory._flush_buffer()
        assert "flush error" not in capsys.readouterr().out

    def test_events_na_afsluiten_geven_geen_fout(self, memory, capsys):
        memory._on_shutdown()
        capsys.readouterr()
        memory.last_flush = 0  # forceer een flush-poging bij elk event
        for i in range(5):
            memory.on_event({"i": i}, event_type="test_event")
        assert "flush error" not in capsys.readouterr().out

    def test_events_na_afsluiten_staan_nog_in_jsonl(self, memory):
        memory._on_shutdown()
        memory.on_event({"tekst": "laatste woorden"}, event_type="test_event")
        inhoud = memory.save_path.read_text(encoding="utf-8")
        assert "laatste woorden" in inhoud

    def test_gewone_flush_werkt_nog(self, memory):
        memory.on_event({"tekst": "hallo"}, event_type="test_event")
        memory._flush_buffer()
        aantal = memory.conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
        assert aantal >= 1


class TestShutdownTweeKeer:

    def test_tweede_keer_doet_niets(self, memory, capsys):
        memory._on_shutdown()
        memory._on_shutdown()
        assert capsys.readouterr().out.count("netjes afgesloten") == 1

    def test_databank_is_dicht_na_shutdown(self, memory):
        memory._on_shutdown()
        assert memory.conn is None


class TestOnSignal:

    def test_on_signal_stopt_het_programma(self, memory):
        with pytest.raises(SystemExit) as info:
            memory._on_signal(signal.SIGTERM, None)
        assert info.value.code == 0
        assert memory.conn is None


# ─────────────────────────────────────────────────────────────
# Echte procestest: precies wat Docker doet bij het stoppen
# ─────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SCRIPT = textwrap.dedent("""
    import sys, threading, time
    sys.path.insert(0, {root!r})
    from core.memory import MemoryModule

    class Bus:
        def __init__(self):
            self.subs = {{}}
        def subscribe(self, t, cb):
            self.subs.setdefault(t, []).append(cb)
        def publish(self, t, d):
            for cb in self.subs.get(t, []) + self.subs.get("*", []):
                cb(d, event_type=t)

    bus = Bus()
    mem = MemoryModule(bus, save_path={pad!r})
    mem.buffer_max_seconds = 0  # elk event meteen proberen weg te schrijven

    # Zoals Nova's achtergrondthread: blijft events sturen
    def achtergrond():
        while True:
            bus.publish("context:updated", {{"t": time.time()}})
            time.sleep(0.1)
    threading.Thread(target=achtergrond, daemon=True).start()

    print("TEST_PROCES_GESTART", flush=True)
    input()   # zoals main.py: wachten op Kevin
""")


@pytest.mark.skipif(not hasattr(signal, "SIGTERM") or os.name == "nt",
                    reason="SIGTERM-procestest enkel op Linux (zoals de Docker-container)")
def test_echte_sigterm_stopt_proces_snel_en_zonder_fouten(tmp_path):
    script = SCRIPT.format(root=str(PROJECT_ROOT), pad=str(tmp_path / "interactions.jsonl"))
    proces = subprocess.Popen(
        [sys.executable, "-c", script],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        # Wachten tot het testproces klaar is met opstarten.
        for regel in proces.stdout:
            if regel.strip() == "TEST_PROCES_GESTART":
                break
        time.sleep(0.5)  # wat events laten binnenkomen
        proces.send_signal(signal.SIGTERM)
        uitvoer, _ = proces.communicate(timeout=5)
    finally:
        if proces.poll() is None:
            proces.kill()

    assert proces.returncode == 0
    assert "flush error" not in uitvoer
    assert uitvoer.count("netjes afgesloten") == 1