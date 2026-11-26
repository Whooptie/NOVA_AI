import time

from core import clock


def test_standaard_is_echte_klok():
    assert abs(clock.now() - time.time()) < 2


def test_fake_clock_volgt_geen_echte_tijd():
    fake = clock.FakeClock(1000.0)
    clock.set_provider(fake)
    try:
        assert clock.now() == 1000.0
        fake.advance(30)
        assert clock.now() == 1030.0
    finally:
        clock.reset()
    assert abs(clock.now() - time.time()) < 2