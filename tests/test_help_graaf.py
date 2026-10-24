"""Tests voor 'help graaf' (Semantic Fase 13)."""

from core.intent_router import IntentRouter
from modules.help.help import HelpModule
from modules.help.topics import algemeen, graaf, semantic


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
        return None

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


def test_help_graaf_geeft_graaf_overzicht():
    assert _vraag("help graaf") == graaf.get_help()


def test_alias_kennisgraaf():
    assert _vraag("help kennisgraaf") == graaf.get_help()


def test_help_graaf_noemt_alle_commandos():
    tekst = graaf.get_help()
    for commando in ("toon graaf van", "toon de hele kennisgraaf", "hoe zijn", "graaf statistieken"):
        assert commando in tekst


def test_algemene_help_en_semantic_verwijzen_ernaar():
    assert "help graaf" in algemeen.get_help()
    assert "help graaf" in semantic.get_help()


def test_help_semantic_blijft_werken():
    assert _vraag("help semantic") == semantic.get_help()
    assert _vraag("help kennis") == semantic.get_help()