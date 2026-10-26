# tests/test_help_hypothese_terugblik.py
# Elke zin die de help noemt, moet Nova ook echt herkennen (anders belooft de help iets
# dat niet werkt).
import re

import pytest

from core.intent_router import IntentRouter
from modules.help.topics import algemeen, semantic


class DummyEventBus:
    def __init__(self):
        self.modules = {}
        self.handlers = {}
        self.gepubliceerd = []

    def register_module(self, naam, instance):
        self.modules[naam] = instance

    def subscribe(self, event_type, handler):
        self.handlers.setdefault(event_type, []).append(handler)

    def publish(self, event_type, data=None):
        self.gepubliceerd.append((event_type, data))


class Aannames:
    def heeft_aannames(self):
        return True


@pytest.fixture
def router():
    bus = DummyEventBus()
    bus.register_module("hypothese", Aannames())
    bus.register_module("case_herinnering", object())
    return IntentRouter(bus, semantic_module=None), bus


HYPOTHESE_ZINNEN = [
    "stel dat een hond een meubel is",
    "veronderstel dat een hond een meubel is",
    "neem aan dat een hond een meubel is",
    "stel dat een wiel een onderdeel van een boom is",
    "stel dat regen droogte veroorzaakt",
    "stel dat regen tot droogte leidt",
    "wat zou dat betekenen",
    "welke aannames heb ik",
    "wis de aannames",
    "laat de aannames vallen",
    "terug naar de feiten",
]
TERUGBLIK_ZINNEN = [
    "heb ik dit al eens gevraagd",
    "vroeg ik dit al eens",
    "wanneer vroeg ik dat laatst",
    "stop met terugblikken",
    "blik weer terug",
]


@pytest.mark.parametrize("zin", HYPOTHESE_ZINNEN)
def test_help_hypothese_zinnen_werken(router, zin):
    r, bus = router
    assert r.detect_hypothese(zin) is True


@pytest.mark.parametrize("zin", TERUGBLIK_ZINNEN)
def test_help_terugblik_zinnen_werken(router, zin):
    r, bus = router
    assert r.detect_case_herinnering(zin) is True


def test_help_semantic_noemt_alle_zinnen():
    tekst = semantic.get_help()
    for zin in HYPOTHESE_ZINNEN + TERUGBLIK_ZINNEN:
        if zin == "wat zou dat betekenen" or zin in ("neem aan dat een hond een meubel is",
                                                     "veronderstel dat een hond een meubel is",
                                                     "stel dat regen tot droogte leidt",
                                                     "vroeg ik dit al eens",
                                                     "laat de aannames vallen",
                                                     "terug naar de feiten"):
            continue  # staan als "ook: ..." bij een andere regel
        assert zin in tekst, zin
    assert "WAT ALS" in tekst and "TERUGBLIKKEN" in tekst


def test_help_algemeen_noemt_de_nieuwe_commandos():
    tekst = algemeen.get_help()
    assert "stel dat een hond een meubel is" in tekst
    assert "heb ik dit al eens gevraagd" in tekst
    assert "topic_detected:hypothese" in tekst and "topic_detected:terugblik" in tekst


def test_help_blijft_netjes():
    # geen lege get_help, geen verdwenen oude secties
    assert "KENNISGRAAF" in semantic.get_help()
    assert "ANDERE HELP" in semantic.get_help()
    assert "HELP" in algemeen.get_help()