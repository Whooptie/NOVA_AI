# tests/test_intent_router_kleding.py
"""Kledingdetectie in de router.

De detector wordt los aangeroepen op een kaal router-object, zonder de
rest van de router op te bouwen. Zo raakt deze file geen andere
detectors en kan hij ook niets anders blokkeren.
"""

import pytest

from core.intent_router import IntentRouter


class NepBus:
    def __init__(self):
        self.events = []
        self.modules = {}

    def subscribe(self, naam, fn):
        pass

    def publish(self, naam, data=None):
        self.events.append((naam, data))

    def van(self, naam):
        return [d for n, d in self.events if n == naam]


@pytest.fixture
def router():
    r = IntentRouter.__new__(IntentRouter)
    r.event_bus = NepBus()
    r._emit_topic = lambda *a, **kw: None
    return r


def test_short_uit(router):
    assert router.detect_kleding("trek mijn short uit") is True
    assert router.event_bus.van("intent_kleding")[0] == {"item": "short", "actie": "uit"}


def test_shortje_is_short(router):
    router.detect_kleding("shortje uit")
    assert router.event_bus.van("intent_kleding")[0]["item"] == "short"


def test_hoodie_omhoog(router):
    router.detect_kleding("hoodie omhoog")
    assert router.event_bus.van("intent_kleding")[0] == {"item": "hoodie", "actie": "verschoven"}


def test_topje_terug_aan(router):
    router.detect_kleding("doe je topje terug aan")
    assert router.event_bus.van("intent_kleding")[0] == {"item": "topje", "actie": "aan"}


def test_knoop_is_los(router):
    router.detect_kleding("knoop mijn short open")
    assert router.event_bus.van("intent_kleding")[0]["actie"] == "los"


def test_tshirt_is_shirt(router):
    router.detect_kleding("t-shirt uit")
    assert router.event_bus.van("intent_kleding")[0]["item"] == "shirt"


# ---------------- wat kleding moet laten liggen ----------------
def test_vraagvorm_blijft_bij_uiterlijk(router):
    assert router.detect_kleding("wat draag je") is False
    assert not router.event_bus.van("intent_kleding")


def test_hoe_zit_je_short_blijft_weg(router):
    assert router.detect_kleding("hoe zit je short") is False


def test_aanraking_blijft_bij_body(router):
    assert router.detect_kleding("raak mijn short aan") is False
    assert not router.event_bus.van("intent_kleding")


def test_aanraking_met_hoodie_blijft_bij_body(router):
    assert router.detect_kleding("steek je hand onder mijn hoodie") is False


def test_stuk_zonder_handeling(router):
    assert router.detect_kleding("mijn short") is False


def test_handeling_zonder_stuk(router):
    assert router.detect_kleding("trek het uit") is False


# ---------------- plaatsing in de tabel ----------------
def test_kleding_staat_direct_voor_body():
    r = IntentRouter.__new__(IntentRouter)
    onderwerpen = [naam for naam, _ in r._build_intent_tabel_deel1()]
    assert "kleding" in onderwerpen
    assert onderwerpen.index("kleding") == onderwerpen.index("body") - 1