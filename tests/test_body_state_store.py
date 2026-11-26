import copy

import pytest

from core import clock
from core.state_store import StateStore
from modules.body.body_state import BodyState


class NepBus:
    def __init__(self):
        self.events = []

    def subscribe(self, naam, fn):
        pass

    def publish(self, naam, data=None):
        self.events.append((naam, data))

    def van(self, naam):
        return [d for n, d in self.events if n == naam]


@pytest.fixture
def opzet(tmp_path):
    fake = clock.FakeClock(50_000.0)
    clock.set_provider(fake)
    store = StateStore(tmp_path / "state.json")
    bus = NepBus()
    yield BodyState(bus, store=store), bus, store, fake
    clock.reset()


def test_state_wordt_gepubliceerd(opzet):
    bs, bus, _, _ = opzet
    bs.on_body({"text": "tepel", "type": "aanraking"})
    assert bus.van("state_body")
    assert bus.van("state_body")[0]["bloos"] > 0


def test_publicatie_gedebounced(opzet):
    bs, bus, _, _ = opzet
    bs.on_body({"text": "tepel", "type": "aanraking"})
    bs.on_body({"text": "tepel", "type": "aanraking"})
    assert len(bus.van("state_body")) == 1


def test_na_debounce_weer_een_publicatie(opzet):
    bs, bus, _, fake = opzet
    bs.on_body({"text": "tepel", "type": "aanraking"})
    fake.advance(1.0)
    bs.on_body({"text": "vulva", "type": "aanraking"})
    assert len(bus.van("state_body")) == 2


def test_body_reactie_niet_layer4(opzet):
    bs, bus, _, _ = opzet
    bs.on_body({"text": "clitoris", "type": "aanraking"})
    assert bus.van("body_reactie")
    assert not bus.van("layer4_response")


def test_snapshot_is_kopie(opzet):
    bs, _, _, _ = opzet
    snap = bs.snapshot()
    snap["nat"]["vulva"] = 9.0
    assert bs.persistent["nat"]["vulva"] != 9.0


def test_state_overleeft_herstart(tmp_path):
    store = StateStore(tmp_path / "state.json")
    bus = NepBus()
    bs = BodyState(bus, store=store)
    bs.on_body({"text": "tepel", "type": "aanraking"})
    store.flush(True)

    bs2 = BodyState(NepBus(), store=StateStore(tmp_path / "state.json"))
    assert bs2.persistent["bloos"] > 0