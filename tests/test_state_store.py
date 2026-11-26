import json

import pytest

from core import clock
from core.state_store import StateStore


@pytest.fixture
def store(tmp_path):
    fake = clock.FakeClock(10_000.0)
    clock.set_provider(fake)
    s = StateStore(tmp_path / "state.json", debounce=2.0)
    s.registreer("body", {"bloos": 0.0})
    yield s, tmp_path / "state.json", fake
    clock.reset()


def test_roundtrip(store):
    s, pad, _ = store
    with s.muteer("body") as d:
        d["bloos"] = 0.4
    s.flush(True)
    assert json.loads(pad.read_text(encoding="utf-8"))["namespaces"]["body"]["data"]["bloos"] == 0.4


def test_debounce_weigert_snel_tweede_write(store):
    s, pad, fake = store
    with s.muteer("body") as d:
        d["bloos"] = 0.1
    eerste = pad.stat().st_mtime_ns
    fake.advance(0.5)
    with s.muteer("body") as d:
        d["bloos"] = 0.2
    assert pad.stat().st_mtime_ns == eerste
    fake.advance(2.0)
    with s.muteer("body") as d:
        d["bloos"] = 0.3
    assert json.loads(pad.read_text(encoding="utf-8"))["namespaces"]["body"]["data"]["bloos"] == 0.3


def test_force_negeert_debounce(store):
    s, pad, _ = store
    with s.muteer("body") as d:
        d["bloos"] = 0.9
    s.flush(True)
    assert "0.9" in pad.read_text(encoding="utf-8")


def test_defaults_gevuld(tmp_path):
    s = StateStore(tmp_path / "s.json")
    s.registreer("x", {"a": 1, "b": {"c": 2}})
    assert s.get("x") == {"a": 1, "b": {"c": 2}}


def test_migratie_loopt_vanaf_opgeslagen_versie(tmp_path):
    pad = tmp_path / "s.json"
    pad.write_text(json.dumps({"schema_version": 1, "namespaces": {
        "x": {"_versie": 1, "data": {"oud": 1}}}}), encoding="utf-8")

    s = StateStore(pad)
    s.registreer("x", {}, migraties=[(1, lambda d: {**d, "nieuw": d["oud"] * 2})])
    assert s.get("x") == {"oud": 1, "nieuw": 2}


def test_toekomstige_versie_weigert(tmp_path):
    pad = tmp_path / "s.json"
    pad.write_text(json.dumps({"schema_version": 99, "namespaces": {}}), encoding="utf-8")
    with pytest.raises(ValueError):
        StateStore(pad)


def test_snapshot_is_een_kopie(store):
    s, _, _ = store
    snap = s.snapshot()
    snap["body"]["data"]["bloos"] = 1.0
    assert s.get("body")["bloos"] == 0.0