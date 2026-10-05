# tests/test_main_stopsignaal.py
"""
Tests voor het vervolg op bug #47 (5 oktober 2026): main.py sluit bij een
stopsignaal van buitenaf (SIGTERM: Docker/Unraid stopt de container) ALLE
modules netjes af, niet enkel memory.py.

Twee lagen getest:
1. sluit_modules_netjes_af() rechtstreeks, met nep-modules.
2. Een ECHT apart Python-proces dat main.py's installeer_stopsignaal()
   gebruikt, met de ECHTE memory.py, op input() wacht en een echte
   SIGTERM krijgt -- precies wat Docker doet.

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

import main


class NepModule:
    def __init__(self, naam, logboek, faalt=False):
        self.naam = naam
        self.logboek = logboek
        self.faalt = faalt

    def shutdown(self):
        self.logboek.append(self.naam)
        if self.faalt:
            raise RuntimeError("kapot")


class NepMemory:
    def __init__(self, logboek):
        self.logboek = logboek

    def _on_shutdown(self):
        self.logboek.append("memory")


class ZonderShutdown:
    pass


class TestSluitModulesNetjesAf:

    def test_alle_modules_met_shutdown_worden_afgesloten(self):
        logboek = []
        modules = {
            "pattern_matcher": NepModule("pattern_matcher", logboek),
            "chess_engine": NepModule("chess_engine", logboek),
            "interruption_tracker": NepModule("interruption_tracker", logboek),
        }
        main.sluit_modules_netjes_af(modules)
        assert sorted(logboek) == ["chess_engine", "interruption_tracker", "pattern_matcher"]

    def test_memory_komt_als_allerlaatste(self):
        logboek = []
        modules = {
            "memory": NepMemory(logboek),          # bewust als EERSTE in de dict
            "pattern_matcher": NepModule("pattern_matcher", logboek),
            "chess_engine": NepModule("chess_engine", logboek),
        }
        main.sluit_modules_netjes_af(modules)
        assert logboek[-1] == "memory"
        assert logboek.count("memory") == 1

    def test_een_fout_houdt_de_rest_niet_tegen(self, capsys):
        logboek = []
        modules = {
            "kapotte_module": NepModule("kapotte_module", logboek, faalt=True),
            "pattern_matcher": NepModule("pattern_matcher", logboek),
            "memory": NepMemory(logboek),
        }
        main.sluit_modules_netjes_af(modules)
        assert "pattern_matcher" in logboek
        assert logboek[-1] == "memory"
        assert "kapotte_module.shutdown()" in capsys.readouterr().out

    def test_modules_zonder_shutdown_of_none_worden_overgeslagen(self):
        logboek = []
        modules = {
            "help": ZonderShutdown(),
            "leeg": None,
            "pattern_matcher": NepModule("pattern_matcher", logboek),
        }
        main.sluit_modules_netjes_af(modules)
        assert logboek == ["pattern_matcher"]

    def test_zonder_memory_geen_crash(self):
        logboek = []
        main.sluit_modules_netjes_af({"x": NepModule("x", logboek)})
        assert logboek == ["x"]

    def test_lege_lijst_geen_crash(self):
        main.sluit_modules_netjes_af({})


class TestInstalleerStopsignaal:

    def test_handler_sluit_af_en_stopt(self):
        logboek = []

        class Loader:
            loaded_modules = {
                "pattern_matcher": NepModule("pattern_matcher", logboek),
                "memory": NepMemory(logboek),
            }

        oude_handler = signal.getsignal(signal.SIGTERM)
        try:
            main.installeer_stopsignaal(Loader())
            handler = signal.getsignal(signal.SIGTERM)
            assert callable(handler) and handler is not oude_handler
            with pytest.raises(SystemExit) as info:
                handler(signal.SIGTERM, None)
            assert info.value.code == 0
            assert logboek == ["pattern_matcher", "memory"]
        finally:
            signal.signal(signal.SIGTERM, oude_handler)


# ─────────────────────────────────────────────────────────────
# Echte procestest: precies wat Docker doet bij het stoppen
# ─────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SCRIPT = textwrap.dedent("""
    import os, sys, threading, time
    sys.path.insert(0, {root!r})
    os.chdir({root!r})
    import main
    from core.memory import MemoryModule

    class Bus:
        def __init__(self):
            self.subs = {{}}
        def subscribe(self, t, cb):
            self.subs.setdefault(t, []).append(cb)
        def publish(self, t, d):
            for cb in self.subs.get(t, []) + self.subs.get("*", []):
                cb(d, event_type=t)

    class PatternMatcherNep:
        # Schrijft bij shutdown een bestand weg, zoals pattern_matcher
        # zijn laatste stand opslaat.
        def shutdown(self):
            with open({opslag!r}, "w") as f:
                f.write("opgeslagen")

    bus = Bus()
    # Memory EERST laden: registreert zijn eigen SIGTERM-afhandeling,
    # die main.installeer_stopsignaal() daarna moet vervangen.
    mem = MemoryModule(bus, save_path={pad!r})
    mem.buffer_max_seconds = 0

    class Loader:
        loaded_modules = {{"memory": mem, "pattern_matcher": PatternMatcherNep()}}

    main.installeer_stopsignaal(Loader())

    def achtergrond():
        while True:
            bus.publish("context:updated", {{"t": time.time()}})
            time.sleep(0.1)
    threading.Thread(target=achtergrond, daemon=True).start()

    print("TEST_PROCES_GESTART", flush=True)
    input()
""")


@pytest.mark.skipif(os.name == "nt", reason="SIGTERM-procestest enkel op Linux (zoals de Docker-container)")
def test_echte_sigterm_sluit_alle_modules_af(tmp_path):
    opslag = tmp_path / "pattern_opgeslagen.txt"
    script = SCRIPT.format(
        root=str(PROJECT_ROOT),
        pad=str(tmp_path / "interactions.jsonl"),
        opslag=str(opslag),
    )
    proces = subprocess.Popen(
        [sys.executable, "-c", script],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        for regel in proces.stdout:
            if regel.strip() == "TEST_PROCES_GESTART":
                break
        time.sleep(0.5)
        proces.send_signal(signal.SIGTERM)
        uitvoer, _ = proces.communicate(timeout=5)
    finally:
        if proces.poll() is None:
            proces.kill()

    assert proces.returncode == 0
    assert opslag.read_text() == "opgeslagen"       # andere module netjes afgesloten
    assert uitvoer.count("Memory: netjes afgesloten.") == 1  # memory precies één keer
    assert "flush error" not in uitvoer
    assert "Stopsignaal ontvangen" in uitvoer