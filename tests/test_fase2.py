# test_fase2.py
"""
Los testscript voor Fase 2 van Layer 1 (Word Associations Learner).

Dit bestand test learn_from(): of woordfrequenties en co-occurrences
correct opgeteld worden na een paar nep-interacties.

Er wordt GEEN echte event_bus.py gebruikt — we simuleren een minimale
nep-EventBus, enkel genoeg om subscribe()/publish() na te bootsen.
Dit is puur voor testdoeleinden; in de echte Nova gebruikt
module_loader.py de echte event_bus.py.

Hoe te gebruiken:
1. Zet dit bestand in dezelfde map als word_associations_learner.py.
2. Run: python test_fase2.py
3. Bekijk de output in je terminal.
"""

import time
from modules.learning.word_associations_learner import WordAssociationsLearner


class NepEventBus:
    """Minimale stand-in voor event_bus.py, enkel voor dit testscript."""

    def __init__(self):
        self.subscribers = {}

    def subscribe(self, event_type, callback):
        self.subscribers.setdefault(event_type, []).append(callback)

    def publish(self, event_type, data):
        for callback in self.subscribers.get(event_type, []):
            callback(data)


def stuur_interactie(bus, user_input, nova_response):
    """Simuleert wat memory.py zou publiceren na een echt gesprek."""
    bus.publish("memory:interaction_added", {
        "timestamp": time.time(),
        "event_type": "user:chat",
        "data": {
            "user_input": user_input,
            "nova_response": nova_response,
        }
    })


if __name__ == "__main__":
    print("=" * 60)
    print("FASE 2 TEST — Word Associations Learner (co-occurrence)")
    print("=" * 60)

    bus = NepEventBus()
    leerder = WordAssociationsLearner(event_bus=bus)

    # Een reeks nep-gesprekken, zoals de voorbeelden uit de roadmap
    stuur_interactie(bus, "Python is mijn favoriet", "Leuk! Waarom vind je dat?")
    stuur_interactie(bus, "Python is snel", "Klopt, Python kan zeker snel zijn.")
    stuur_interactie(bus, "Ik hou van snelle talen", "Snelheid is inderdaad fijn.")
    stuur_interactie(bus, "Java is traag", "Dat hoor ik vaker over Java.")
    stuur_interactie(bus, "Rust is ook snel", "Rust staat inderdaad bekend als snel.")

    snapshot = leerder.get_debug_snapshot()

    print(f"\nAantal unieke woorden geleerd: {snapshot['aantal_woorden']}")
    print(f"Aantal woorden met minstens 1 associatie: "
          f"{snapshot['aantal_woorden_met_associaties']}")

    print("\n--- Woordfrequenties (word_stats) ---")
    for woord, stats in sorted(
        snapshot["word_stats"].items(),
        key=lambda x: x[1]["frequency"],
        reverse=True
    ):
        print(f"  {woord!r:15} frequentie={stats['frequency']}")

    print("\n--- Associaties van 'python' ---")
    python_assoc = snapshot["associations"].get("python", {})
    if python_assoc:
        for woord, info in python_assoc.items():
            print(f"  python <-> {woord!r:15} co_occurrence={info['co_occurrence']}")
    else:
        print("  (geen associaties gevonden voor 'python' — dat zou een probleem zijn!)")

    print("\n--- Associaties van 'snel' ---")
    snel_assoc = snapshot["associations"].get("snel", {})
    if snel_assoc:
        for woord, info in snel_assoc.items():
            print(f"  snel <-> {woord!r:15} co_occurrence={info['co_occurrence']}")
    else:
        print("  (geen associaties gevonden voor 'snel' — dat zou een probleem zijn!)")

    print("\n" + "=" * 60)
    print("Verwacht (ruwweg):")
    print("- 'python' heeft co-occurrence met 'favoriet' en 'snel'")
    print("- 'snel' heeft co-occurrence met 'python', 'rust', 'hou', 'taal'")
    print("- Woorden die vaker voorkomen (bv. 'python', 'snel') hebben")
    print("  een hogere frequentie dan woorden die maar 1x voorkomen")
    print("=" * 60)
