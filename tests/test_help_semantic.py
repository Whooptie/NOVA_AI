# tests/test_help_semantic.py -- "help semantic": eigen help-overzicht voor alles rond Nova's kennis
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from modules.help.help import HelpModule
from modules.help.topics import algemeen, debug, math, semantic


class FakeBus:
    def __init__(self):
        self.out = []

    def subscribe(self, *a, **k):
        pass

    def publish(self, e, d=None):
        self.out.append((e, d))

    def get_module(self, naam):
        return None


def vraag_help(topic):
    bus = FakeBus()
    HelpModule(bus).handle_help({"topic": topic})
    antwoorden = [d for e, d in bus.out if e == "chat_response"]
    assert len(antwoorden) == 1
    return antwoorden[0]


@pytest.mark.parametrize("topic", ["semantic", "semantiek", "kennis", "kennisbank", "SEMANTIC"])
def test_help_semantic_aliassen(topic):
    antwoord = vraag_help(topic)
    assert antwoord["text"] == semantic.get_help()
    assert antwoord["instant"] is True


@pytest.mark.parametrize("commando", [
    # leren/opvragen en redeneren
    "wat is een zwart gat", "teach fotosynthese", "hond is een dier", "vergelijk hond met huiskat",
    # oorzaak/gevolg (Fase 8)
    "wat veroorzaakt regen", "wat zijn de gevolgen van regen", "leidt regen tot modder",
    # tijd (Fase 9)
    "python bestaat sinds 1991", "wanneer ontstond python", "tijdlijn van python",
    "wis de periodes van python", "wat bestond er in 1960",
    # zekerheid (Fase 10)
    "hoe zeker ben je dat een hond een dier is", "waarom ben je er niet zeker van dat",
    "wat weet je niet zeker", "bevestig 3", "wijs af 3",
    # weerleggen
    "weerleg: hond is_a meubel", "verwijder definitief: hond is_a meubel",
])
def test_help_semantic_bevat_alle_fases(commando):
    assert commando in semantic.get_help()


def test_help_algemeen_verwijst_naar_semantic():
    tekst = vraag_help("")["text"]
    assert tekst == algemeen.get_help()
    assert "help semantic" in tekst


def test_algemene_help_is_korter_geworden():
    # de lange semantic-blokken staan nu in help semantic, niet meer in help
    tekst = algemeen.get_help()
    assert "welke soorten dier ken je" not in tekst
    assert "verwijder definitief concept" not in tekst


def test_andere_topics_ongewijzigd():
    assert vraag_help("debug")["text"] == debug.get_help()
    assert vraag_help("wiskunde")["text"] == math.get_help()
    assert vraag_help("onbekend onderwerp")["text"] == algemeen.get_help()