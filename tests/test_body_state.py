import json
import time

import pytest

@pytest.fixture(autouse=True)
def _lege_store_cache():
    from modules.body import body_state
    body_state._STORES.clear()
    yield
    body_state._STORES.clear()

from modules.body import body_state as bs


class FakeBus:
    def __init__(self):
        self.events = []

    def subscribe(self, *_a, **_k):
        pass

    def publish(self, event, data=None):
        self.events.append((event, data))


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setattr(bs, "STATE_PAD", tmp_path / "state.json")
    monkeypatch.setattr(bs, "MAP_PAD", tmp_path / "map.json")
    monkeypatch.setattr(bs, "APPEARANCE_PAD", tmp_path / "app.json")
    (tmp_path / "map.json").write_text(json.dumps({"nodes": {
        "vagina": {"gevoeligheid": 0.8, "comfort_zone": 0.4},
        "clitoris": {"gevoeligheid": 0.95, "comfort_zone": 0.35},
        "tepel_links": {"gevoeligheid": 0.9, "comfort_zone": 0.45},
    }}), encoding="utf-8")
    (tmp_path / "app.json").write_text("{}", encoding="utf-8")
    bus = FakeBus()
    return bs.BodyState(bus), bus


def _penetratie():
    return {"text": "erin", "type": "penetratie", "sterkte": 0.5, "diepte": 0.8, "rek": 0.4}


def test_pijn_softlock_breekt(state):
    s, _ = state
    s.persistent["pijn"]["vagina"] = 0.9
    for _ in range(4):
        s.on_body(_penetratie())
    assert s.persistent["pijn"]["vagina"] < 0.6


def test_nat_is_per_zone(state):
    s, _ = state
    s.on_body({"text": "tepel", "type": "aanraking", "sterkte": 0.4})
    assert s.persistent["nat"]["tepel_links"] > 0
    assert s.persistent["nat"]["vagina"] == 0


def test_nat_zakt_met_tijd(state):
    s, _ = state
    s.persistent["nat"]["clitoris"] = 1.0
    s.persistent["laatste_event_ts"] = time.time() - 600
    s.on_body({"text": "tepel", "type": "aanraking", "sterkte": 0.4})
    assert s.persistent["nat"]["clitoris"] < 1.0


def test_bloos_stijgt_en_zakt(state):
    s, _ = state
    s.on_body({"text": "clitoris", "type": "aanraking", "sterkte": 0.4})
    hoog = s.persistent["bloos"]
    assert hoog > 0.3
    s.persistent["laatste_event_ts"] = time.time() - 1800
    s.on_body({"text": "tepel", "type": "aanraking", "sterkte": 0.4})
    assert s.persistent["bloos"] < hoog


def test_herstelzin_na_piek(state):
    s, bus = state
    s.persistent["bloos"] = 0.9
    s.persistent["laatste_event_ts"] = time.time() - 3600
    s.on_body({"text": "tepel", "type": "aanraking", "sterkte": 0.4})
    teksten = [d["text"] for e, d in bus.events if e == "body_reactie"]
    assert "Zo. Klaar met gênant doen." in teksten


def test_maagd_flip(state):
    s, _ = state
    assert s.persistent["maagd"]["vagina"] is True
    s.on_body(_penetratie())
    assert s.persistent["maagd"]["vagina"] is False


def test_geen_dubbele_zin(state):
    s, bus = state
    for _ in range(12):
        s.persistent["bloos"] = 0.0
        s.on_body({"text": "tepel", "type": "aanraking", "sterkte": 0.4})
    zinnen = [d["text"] for e, d in bus.events if e == "body_reactie"]
    for a, b in zip(zinnen, zinnen[1:]):
        assert a != b


def test_fragmenten_herhalen_niet(state):
    s, bus = state
    for _ in range(10):
        s.persistent["bloos"] = 0.95
        s.on_body({"text": "clitoris", "type": "aanraking", "sterkte": 0.4})
    zinnen = [d["text"] for e, d in bus.events if e == "body_reactie"]
    for a, b in zip(zinnen, zinnen[1:]):
        assert a != b


def test_verlegenheid_triggert_maar_een_keer(state):
    s, bus = state
    s.persistent["bloos"] = 0.6
    s.on_body({"text": "tepel", "type": "aanraking", "sterkte": 0.4})
    s.on_body({"text": "tepel", "type": "aanraking", "sterkte": 0.4})
    triggers = [d for e, d in bus.events
                if e == "emotion_trigger" and d.get("trigger") == "verlegenheid"]
    assert len(triggers) == 1


def test_bekeken_verhoogt_bloos(state):
    s, _ = state
    begin = s.huidige_bloos()
    s.on_bekeken({"actief": True})
    assert s.huidige_bloos() > begin


def test_bekeken_inactief_doet_niets(state):
    s, _ = state
    s.persistent["bloos"] = 0.5
    s.on_bekeken({"actief": False})
    assert s.huidige_bloos() == 0.5