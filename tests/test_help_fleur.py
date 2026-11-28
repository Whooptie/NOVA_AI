"""Tests voor 'help fleur'. Schrijft niets op schijf buiten tmp_path.

De belangrijkste test: elk voorbeeldcommando in de help wordt echt door de
cyclus-module herkend. Zo kan de help nooit iets beloven dat niet werkt.
"""

from datetime import date, datetime

import pytest

from core.intent_router import IntentRouter
from modules.help.help import HelpModule
from modules.help.topics import algemeen, fleur
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

    def get_module(self, naam):
        return self.modules.get(naam)

    def antwoord(self):
        return [d["text"] for n, d in self.gepubliceerd if n == "chat_response"][-1]


class NepSemantic:
    pending_reactivation = None

    def get_senses(self, woord):
        return []

    def _detect_relation(self, text):
        return False


def _vraag(tekst):
    bus = NepBus()
    HelpModule(bus)
    IntentRouter(bus, semantic_module=NepSemantic()).route({"text": tekst})
    return bus.antwoord()


@pytest.mark.parametrize("zin", ["help fleur", "help cyclus", "help maandstonden"])
def test_help_fleur_en_aliassen(zin):
    assert _vraag(zin) == fleur.get_help()


def test_algemene_help_verwijst_ernaar():
    assert "help fleur" in algemeen.get_help()


def test_help_bevat_kop_en_veiligheidsuitleg():
    tekst = fleur.get_help()
    assert "MAANDSTONDEN EN CYCLUS" in tekst
    assert "geen meting en geen" in tekst and "anticonceptie" in tekst
    assert "data/cyclus.json" in tekst


def test_elk_commando_staat_in_de_tekst():
    tekst = fleur.get_help()
    for commando in fleur.alle_commandos():
        assert commando in tekst


@pytest.mark.parametrize("commando", fleur.alle_commandos("cyclus"))
def test_elk_voorbeeldcommando_wordt_door_cyclus_herkend(commando, tmp_path):
    bus = NepBus()
    module = c.CyclusModule(bus, pad=str(tmp_path / "cyclus.json"),
                            klok=lambda: datetime(2026, 11, 28, 9, 0), start_loop=False)
    module.registreer_start(date(2026, 10, 1))
    module.registreer_start(date(2026, 10, 29))
    assert module.verwerk_zin(commando) is True, f"niet herkend: {commando!r}"


def test_nieuwe_sectie_verschijnt_automatisch(monkeypatch):
    extra = {"kop": "🎂 VERJAARDAG", "module": None,
             "commando's": [("fleur verjaart op 3 mei", "onthoudt de datum")]}
    monkeypatch.setattr(fleur, "SECTIES", fleur.SECTIES + [extra])
    tekst = fleur.get_help()
    assert "VERJAARDAG" in tekst and "fleur verjaart op 3 mei" in tekst
    assert "MAANDSTONDEN EN CYCLUS" in tekst