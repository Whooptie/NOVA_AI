# test_fase5.py
#
# Echte pytest-test voor Fase 5 van Layer 1 (Word Associations Learner):
# persistentie -- save_to_disk(), load_from_disk(), en events op de
# EventBus bij het bijwerken van associaties.
#
# Het origineel gebruikte al bewust een apart testbestand
# (test_word_associations.json, niet je echte data/) en ruimde dat zelf
# op met .unlink(). Deze versie gaat een stap verder: via pytest's
# 'tmp_path'-fixture staat het testbestand in een map die pytest zelf
# aanmaakt en na afloop AUTOMATISCH verwijdert -- ook als de test
# halverwege faalt, blijft er dus nooit een bestand achter (dat kon bij
# de oude .unlink()-aanpak wel gebeuren als een assert ervoor crashte).
#
# Uitvoeren: pytest tests/test_fase5.py -v

import time
import json

import pytest

from modules.learning.word_associations_learner import WordAssociationsLearner


class NepEventBus:
    def __init__(self):
        self.subscribers = {}
        self.ontvangen_events = []  # Alles bijhouden wat gepubliceerd werd

    def subscribe(self, event_type, callback):
        self.subscribers.setdefault(event_type, []).append(callback)

    def publish(self, event_type, data):
        if event_type == "word_association:updated":
            self.ontvangen_events.append(data)
        for callback in self.subscribers.get(event_type, []):
            callback(data)


def stuur_interactie(bus, user_input, nova_response=None):
    """Zie toelichting in test_fase2.py: event_type moet 'chat_message'
    zijn en de tekst moet in data['text'] staan, anders breekt
    learn_from() meteen af zonder iets te leren."""
    bus.publish("memory:interaction_added", {
        "timestamp": time.time(),
        "event_type": "chat_message",
        "data": {"text": user_input},
    })


@pytest.fixture
def test_pad(tmp_path):
    """Tijdelijk pad voor het associaties-bestand, binnen pytest's
    eigen tmp_path -- verdwijnt automatisch na de test."""
    return tmp_path / "test_word_associations.json"


def test_opslaan_maakt_bestand_aan(test_pad):
    """Na een paar interacties hoort save_to_disk() het bestand aan te maken."""
    bus = NepEventBus()
    leerder = WordAssociationsLearner(event_bus=bus, save_path=str(test_pad))

    stuur_interactie(bus, "Python is heel snel", "Ja, Python is snel!")
    stuur_interactie(bus, "Python is ook elegant", "Klopt, heel elegant.")

    assert test_pad.exists(), "Bestand werd niet aangemaakt na leren."

    with open(test_pad) as f:
        inhoud = json.load(f)
    assert inhoud["metadata"]["total_words"] > 0


def test_herladen_geeft_zelfde_associaties_terug(test_pad):
    """
    Een NIEUWE instantie (alsof Nova herstart is) die hetzelfde pad
    inleest, hoort de eerder geleerde associaties terug te vinden.
    """
    bus1 = NepEventBus()
    leerder1 = WordAssociationsLearner(event_bus=bus1, save_path=str(test_pad))
    stuur_interactie(bus1, "Python is heel snel", "Ja, Python is snel!")
    stuur_interactie(bus1, "Python is ook elegant", "Klopt, heel elegant.")

    bus2 = NepEventBus()
    leerder2 = WordAssociationsLearner(event_bus=bus2, save_path=str(test_pad))
    associaties_na_herladen = leerder2.get_associations("python")

    assert associaties_na_herladen, (
        "Geen associaties teruggevonden na herladen -- persistentie werkt niet."
    )


def test_events_worden_gepubliceerd_bij_leren(test_pad):
    """Bij het leren van nieuwe associaties hoort er minstens 1
    'word_association:updated'-event gepubliceerd te worden."""
    bus = NepEventBus()
    leerder = WordAssociationsLearner(event_bus=bus, save_path=str(test_pad))

    stuur_interactie(bus, "Python is heel snel", "Ja, Python is snel!")
    stuur_interactie(bus, "Python is ook elegant", "Klopt, heel elegant.")

    assert len(bus.ontvangen_events) > 0, (
        "Er werden geen 'word_association:updated'-events gepubliceerd."
    )