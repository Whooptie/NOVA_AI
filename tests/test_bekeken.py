import pytest

from core import clock
from core.state_store import StateStore
from modules.body.bekeken import Bekeken


class NepBus:
    def __init__(self):
        self.subs = {}
        self.events = []

    def subscribe(self, naam, fn):
        self.subs[naam] = fn

    def publish(self, naam, data=None):
        self.events.append((naam, data))

    def van(self, naam):
        return [d for n, d in self.events if n == naam]


@pytest.fixture
def b(tmp_path):
    fake = clock.FakeClock(10_000.0)
    clock.set_provider(fake)
    yield Bekeken(NepBus(), store=StateStore(tmp_path / "s.json")), fake
    clock.reset()


def test_stijgt_bij_trigger(b):
    bk, _ = b
    assert bk.verhoog() > 0.0


def test_zakt_met_de_tijd(b):
    bk, fake = b
    bk.verhoog()
    bk.verhoog()
    hoog = bk.waarde()
    fake.advance(600)
    assert bk.waarde() < hoog


def test_actief_pas_boven_de_drempel(b):
    bk, _ = b
    assert bk.is_actief() is False
    for _ in range(4):
        bk.verhoog()
    assert bk.is_actief() is True


def test_na_decay_weer_inactief(b):
    bk, fake = b
    for _ in range(4):
        bk.verhoog()
    fake.advance(600)
    assert bk.is_actief() is False


def test_publiceert_een_keer(b):
    bk, _ = b
    for _ in range(4):
        bk.verhoog()
    assert len(bk.event_bus.van("bekeken_changed")) == 1


def test_herwapent_onder_de_onderdrempel(b):
    bk, fake = b
    for _ in range(4):
        bk.verhoog()
    fake.advance(600)
    bk.verhoog()  # herwapent, blijft onder de drempel
    bk.verhoog()  # tweede duwt hem er weer over
    assert len(bk.event_bus.van("bekeken_changed")) == 2


def test_subscribet_op_de_trigger(b):
    bk, _ = b
    assert "intent_uiterlijk" in bk.event_bus.subs


def test_trigger_event_verhoogt(b):
    bk, _ = b
    bk.event_bus.subs["intent_uiterlijk"]({"deel": "haar"})
    assert bk.waarde() > 0.0