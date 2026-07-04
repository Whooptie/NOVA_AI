# test_fase5.py
"""
Los testscript voor Fase 5 van Layer 1 (Word Associations Learner).

Test:
1. Of save_to_disk() een JSON-bestand aanmaakt op de juiste plek.
2. Of load_from_disk() (via een NIEUWE instantie) de data terugleest.
3. Of publish_update() events publiceert op de EventBus.

We gebruiken hier een tijdelijke testmap (niet je echte data/ map),
zodat dit script je echte Nova-data niet overschrijft.
"""

import time
import json
import shutil
from pathlib import Path
from modules.learning.word_associations_learner import WordAssociationsLearner


class NepEventBus:
    def __init__(self):
        self.subscribers = {}
        self.ontvangen_events = []  # Voor deze test: alles bijhouden wat gepubliceerd werd

    def subscribe(self, event_type, callback):
        self.subscribers.setdefault(event_type, []).append(callback)

    def publish(self, event_type, data):
        if event_type == "word_association:updated":
            self.ontvangen_events.append(data)
        for callback in self.subscribers.get(event_type, []):
            callback(data)


def stuur_interactie(bus, user_input, nova_response):
    bus.publish("memory:interaction_added", {
        "timestamp": time.time(),
        "event_type": "user:chat",
        "data": {"user_input": user_input, "nova_response": nova_response}
    })


if __name__ == "__main__":
    print("=" * 60)
    print("FASE 5 TEST — Word Associations Learner (persistentie)")
    print("=" * 60)

    # Tijdelijke testmap, NIET je echte data/ map
    test_pad = Path("test_word_associations.json")
    if test_pad.exists():
        test_pad.unlink()

    bus1 = NepEventBus()
    leerder1 = WordAssociationsLearner(
        event_bus=bus1,
        config={"save_path": str(test_pad)}
    )

    print(f"\n1. Opslaan testen...")
    stuur_interactie(bus1, "Python is heel snel", "Ja, Python is snel!")
    stuur_interactie(bus1, "Python is ook elegant", "Klopt, heel elegant.")

    if test_pad.exists():
        print(f"   OK: {test_pad} bestaat na leren.")
        with open(test_pad) as f:
            inhoud = json.load(f)
        print(f"   Bestand bevat {inhoud['metadata']['total_words']} woorden.")
    else:
        print("   PROBLEEM: bestand werd niet aangemaakt!")

    print(f"\n2. Herladen testen (nieuwe instantie, zelfde bestand)...")
    bus2 = NepEventBus()
    leerder2 = WordAssociationsLearner(
        event_bus=bus2,
        config={"save_path": str(test_pad)}
    )
    associaties_na_herladen = leerder2.get_associations("python")
    if associaties_na_herladen:
        print(f"   OK: 'python' associaties teruggevonden na herladen:")
        print(f"   {associaties_na_herladen}")
    else:
        print("   PROBLEEM: geen associaties teruggevonden na herladen!")

    print(f"\n3. Events op de EventBus testen...")
    print(f"   Aantal 'word_association:updated' events ontvangen: "
          f"{len(bus1.ontvangen_events)}")
    if bus1.ontvangen_events:
        voorbeeld = bus1.ontvangen_events[0]
        print(f"   Voorbeeld event: {voorbeeld}")
    else:
        print("   PROBLEEM: er werden geen events gepubliceerd!")

    # Opruimen
    if test_pad.exists():
        test_pad.unlink()

    print("\n" + "=" * 60)
    print("Verwacht:")
    print("- Stap 1: bestand bestaat, bevat woorden")
    print("- Stap 2: na een NIEUWE instantie (alsof Nova herstart is)")
    print("  zijn de associaties van 'python' er nog steeds")
    print("- Stap 3: er zijn events gepubliceerd op de EventBus")
    print("=" * 60)