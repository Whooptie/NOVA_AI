"""Test de HELE keten: echte IntentRouter + echte CyclusModule op een nep-bus.

Zo zie je dat zinnen over Fleur's maandstonden niet door een andere stap van
de router (datum, kennis, context-resolver) worden weggekaapt, en dat gewone
zinnen ongemoeid blijven. Schrijft alleen in tmp_path.
Uitvoeren: pytest tests/test_cyclus_router.py -v
"""

from datetime import date, datetime

import pytest

from core.intent_router import IntentRouter
from modules.time import cyclus as c


class NepBus:
    def __init__(self):
        self.gepubliceerd, self.modules, self.abonnees = [], {}, {}

    def subscribe(self, naam, functie):
        self.abonnees.setdefault(naam, []).append(functie)

    def publish(self, naam, data=None):
        self.gepubliceerd.append((naam, data or {}))
        for f in self.abonnees.get(naam, []):
            f(data or {})

    def register_module(self, naam, instantie):
        self.modules[naam] = instantie

    def antwoorden(self):
        return [d["text"] for n, d in self.gepubliceerd if n == "layer4_response"]


@pytest.fixture
def opstelling(tmp_path):
    bus = NepBus()
    module = c.CyclusModule(bus, pad=str(tmp_path / "cyclus.json"),
                            klok=lambda: datetime(2026, 11, 28, 9, 0), start_loop=False)
    bus.register_module("cyclus", module)
    router = IntentRouter(bus)
    return router, bus, module


def vraag(opstelling, tekst):
    router, bus, _ = opstelling
    bus.gepubliceerd.clear()
    router.route({"text": tekst})
    return bus.antwoorden()


def test_start_via_router(opstelling):
    antwoorden = vraag(opstelling, "Fleur is gisteren ongesteld geworden")
    assert len(antwoorden) == 1 and "Genoteerd" in antwoorden[0]
    assert opstelling[2].starts() == [date(2026, 11, 27)]


@pytest.mark.parametrize("zin", [
    "wanneer is ze weer ongesteld",
    "wanneer is fleur weer ongesteld?",
    "in welke fase zit fleur?",
    "is ze vruchtbaar?",
    "ze is nog niet ongesteld",
    "cyclus overzicht",
])
def test_zinnen_worden_door_cyclus_beantwoord(opstelling, zin):
    opstelling[2].registreer_start(date(2026, 11, 14))
    antwoorden = vraag(opstelling, zin)
    assert len(antwoorden) == 1
    assert any(w in antwoorden[0] for w in ("Fleur", "cyclus", "Cyclus"))


def test_zonder_module_valt_de_router_gewoon_door(tmp_path):
    bus = NepBus()
    router = IntentRouter(bus)
    bus.gepubliceerd.clear()
    router.route({"text": "wanneer is ze weer ongesteld"})
    assert not any("Fleur" in t for t in bus.antwoorden())


def test_gewone_zinnen_blijven_ongemoeid(opstelling):
    router, bus, module = opstelling
    bus.gepubliceerd.clear()
    router.route({"text": "wat is ongesteld"})
    assert not any("Fleur" in t for t in bus.antwoorden())
    assert module.status["perioden"] == []


def test_kapotte_module_laat_router_niet_crashen(opstelling):
    router, bus, module = opstelling

    def stuk(_tekst):
        raise RuntimeError("boem")

    module.verwerk_zin = stuk
    router.route({"text": "fleur is ongesteld geworden"})      # mag niet crashen
    assert module.status["perioden"] == []


def test_geen_topic_voor_gezondheidsinfo(opstelling):
    vraag(opstelling, "fleur is ongesteld geworden")
    topics = [n for n, _ in opstelling[1].gepubliceerd if n.startswith("topic_detected")]
    assert not any("cyclus" in t for t in topics)