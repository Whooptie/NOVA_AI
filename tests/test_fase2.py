# test_fase2.py
#
# Echte pytest-test voor Fase 2 van Layer 1 (Word Associations Learner):
# learn_from() -- of woordfrequenties en co-occurrences correct
# opgeteld worden na een paar nep-interacties.
#
# Gebruikt een minimale NepEventBus (geen echte core/event_bus.py nodig)
# -- exact dezelfde aanpak als het origineel, nu binnen een fixture.
#
# Uitvoeren: pytest tests/test_fase2.py -v

import time

import pytest

from modules.learning.word_associations_learner import WordAssociationsLearner


class NepEventBus:
    """Minimale stand-in voor event_bus.py, enkel voor deze test."""

    def __init__(self):
        self.subscribers = {}

    def subscribe(self, event_type, callback):
        self.subscribers.setdefault(event_type, []).append(callback)

    def publish(self, event_type, data):
        for callback in self.subscribers.get(event_type, []):
            callback(data)


def stuur_interactie(bus, user_input, nova_response=None):
    """Simuleert wat memory.py zou publiceren na een echt gesprek.

    BELANGRIJK (gecorrigeerd t.o.v. eerdere versie): learn_from() in
    word_associations_learner.py verwerkt ENKEL interacties met
    event_type == "chat_message" en leest de tekst uit data["text"]
    (zie learn_from(), regel 293 en 296 in het echte bestand) -- niet
    "user:chat"/"user_input" zoals deze test eerder simuleerde. Met
    de oude, foute structuur werd learn_from() altijd meteen
    afgebroken op de event_type-check, en leerde er dus NOOIT iets
    van deze testinteracties (dat bleef verborgen zolang de test ook
    per ongeluk uit de echte word_associations.json las).

    Nova's eigen antwoord (nova_response) wordt bewust NIET als apart
    event gesimuleerd: memory.py's echte "chat_message"-event bevat
    enkel Kevin's tekst, en learn_from() leert bewust niet van Nova's
    eigen, door Kevin geschreven sjablonen (zie de toelichting in
    learn_from() zelf). nova_response blijft als parameter staan voor
    leesbaarheid van de testscenario's, maar wordt niet gebruikt.
    """
    bus.publish("memory:interaction_added", {
        "timestamp": time.time(),
        "event_type": "chat_message",
        "data": {"text": user_input},
    })


@pytest.fixture
def leerder_met_gesprekken(tmp_path):
    """Bouwt een WordAssociationsLearner op en voedt hem dezelfde
    reeks nep-gesprekken als het originele script.

    BELANGRIJK: save_path=tmp_path/... wordt hier bewust altijd
    meegegeven, ook al testen we in dit bestand geen persistentie.
    Reden: __init__() roept zelf altijd load_from_disk() aan (zie
    word_associations_learner.py), en zonder save_path pakt dat
    automatisch je ECHTE data/word_associations.json erbij -- waardoor
    deze test stiekem met jouw eigen, groeiende chatgeschiedenis zou
    mengen in plaats van een schone, voorspelbare test-staat te hebben.
    """
    bus = NepEventBus()
    leerder = WordAssociationsLearner(
        event_bus=bus,
        save_path=str(tmp_path / "test_word_associations.json"),
    )

    stuur_interactie(bus, "Python is mijn favoriet", "Leuk! Waarom vind je dat?")
    stuur_interactie(bus, "Python is snel", "Klopt, Python kan zeker snel zijn.")
    stuur_interactie(bus, "Ik hou van snelle talen", "Snelheid is inderdaad fijn.")
    stuur_interactie(bus, "Java is traag", "Dat hoor ik vaker over Java.")
    stuur_interactie(bus, "Rust is ook snel", "Rust staat inderdaad bekend als snel.")

    return leerder


def test_python_heeft_associaties(leerder_met_gesprekken):
    """'python' hoort een co-occurrence te hebben met 'snel'."""
    snapshot = leerder_met_gesprekken.get_debug_snapshot()
    python_assoc = snapshot["associations"].get("python", {})

    assert python_assoc, "Geen associaties gevonden voor 'python' — dat zou een probleem zijn."
    assert "snel" in python_assoc


def test_snel_heeft_associaties(leerder_met_gesprekken):
    """'snel' hoort een co-occurrence te hebben met 'python'."""
    snapshot = leerder_met_gesprekken.get_debug_snapshot()
    snel_assoc = snapshot["associations"].get("snel", {})

    assert snel_assoc, "Geen associaties gevonden voor 'snel' — dat zou een probleem zijn."
    assert "python" in snel_assoc


def test_veelvoorkomende_woorden_hebben_hogere_frequentie(leerder_met_gesprekken):
    """
    Woorden die vaker voorkomen ('python', 'snel' -- elk 2x) horen een
    hogere frequentie te hebben dan woorden die maar 1x voorkomen
    (bv. 'favoriet').
    """
    snapshot = leerder_met_gesprekken.get_debug_snapshot()
    stats = snapshot["word_stats"]

    assert stats["python"]["frequency"] >= stats["favoriet"]["frequency"]
    assert stats["snel"]["frequency"] >= stats["favoriet"]["frequency"]