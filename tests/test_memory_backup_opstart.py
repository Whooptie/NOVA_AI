# test_memory_backup_opstart.py
#
# Test voor _seconden_tot_eerste_onderhoud(): na een herstart moet de eerste
# onderhoudsronde (en dus de back-up) rekening houden met hoe oud de
# nieuwste back-up is, in plaats van altijd 6 uur te wachten.
#
# Uitvoeren: pytest tests/test_memory_backup_opstart.py -v

import os
import time

import pytest

from core.memory import MemoryModule


class DummyEventBus:
    def subscribe(self, *args, **kwargs):
        pass

    def publish(self, *args, **kwargs):
        pass


@pytest.fixture
def memory(tmp_path):
    mm = MemoryModule(DummyEventBus(), save_path=str(tmp_path / "interactions.jsonl"))
    yield mm
    mm._on_shutdown()


def _maak_backup(memory, uren_oud):
    memory.backup_dir.mkdir(parents=True, exist_ok=True)
    pad = memory.backup_dir / f"interactions_test_{uren_oud}.db"
    pad.write_bytes(b"x")
    tijd = time.time() - uren_oud * 3600
    os.utime(pad, (tijd, tijd))
    return pad


INTERVAL = 6 * 3600


def test_geen_backups_volle_interval(memory):
    assert memory._seconden_tot_eerste_onderhoud() == INTERVAL


def test_verse_backup_wacht_de_rest(memory):
    _maak_backup(memory, 2)
    wacht = memory._seconden_tot_eerste_onderhoud()
    assert 4 * 3600 - 60 < wacht <= 4 * 3600


def test_oude_backup_snelle_ronde(memory):
    _maak_backup(memory, 10.6)
    assert memory._seconden_tot_eerste_onderhoud() == memory.onderhoud_opstart_wacht_seconden


def test_net_te_oud_ook_snel(memory):
    _maak_backup(memory, 6.5)
    assert memory._seconden_tot_eerste_onderhoud() == memory.onderhoud_opstart_wacht_seconden


def test_backup_van_net_nu_wacht_niet_langer_dan_interval(memory):
    _maak_backup(memory, 0)
    assert memory._seconden_tot_eerste_onderhoud() <= INTERVAL


def test_nieuwste_backup_telt(memory):
    _maak_backup(memory, 12)
    _maak_backup(memory, 1)
    wacht = memory._seconden_tot_eerste_onderhoud()
    assert 5 * 3600 - 60 < wacht <= 5 * 3600


def test_toekomstige_mtime_geeft_hoogstens_interval(memory):
    pad = _maak_backup(memory, 0)
    toekomst = time.time() + 3600
    os.utime(pad, (toekomst, toekomst))
    assert memory._seconden_tot_eerste_onderhoud() <= INTERVAL


def test_fout_bij_lezen_valt_terug_op_interval(memory, monkeypatch):
    _maak_backup(memory, 10)

    def stuk(*a, **k):
        raise OSError("kapot")

    monkeypatch.setattr(type(memory.backup_dir), "glob", stuk, raising=False)
    assert memory._seconden_tot_eerste_onderhoud() == INTERVAL


def test_start_maintenance_gebruikt_berekende_wachttijd(memory):
    _maak_backup(memory, 10)
    memory.stop_maintenance()
    memory.start_maintenance()
    assert memory.maintenance_timer.interval == memory.onderhoud_opstart_wacht_seconden


def test_volgende_rondes_wachten_het_volle_interval(memory):
    _maak_backup(memory, 10)
    memory.stop_maintenance()
    memory.start_maintenance(eerste=False)
    assert memory.maintenance_timer.interval == INTERVAL