# test_fase3.py
"""
Los testscript voor Fase 3 van Layer 1 (Word Associations Learner).

Test of calculate_pmi() zinvolle sterkte-scores geeft: woorden die
STEEDS samen voorkomen (python + snel) moeten een hogere score krijgen
dan woorden die maar TOEVALLIG 1 keer samen opdoken.
"""

import time
from modules.learning.word_associations_learner import WordAssociationsLearner


class NepEventBus:
    def __init__(self):
        self.subscribers = {}

    def subscribe(self, event_type, callback):
        self.subscribers.setdefault(event_type, []).append(callback)

    def publish(self, event_type, data):
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
    print("FASE 3 TEST — Word Associations Learner (PMI)")
    print("=" * 60)

    bus = NepEventBus()
    leerder = WordAssociationsLearner(event_bus=bus)

    # "python" en "snel" komen HERHAALDELIJK samen voor -> sterke band
    for _ in range(8):
        stuur_interactie(bus, "Python is heel snel", "Ja, Python is snel!")

    # "kaas" komt vaak VOOR (hoge eigen frequentie), maar bijna nooit
    # samen met "snel" -> zwakke band ondanks dat het woord vaak voorkomt
    stuur_interactie(bus, "Ik at snel wat kaas", "Kaas is lekker.")
    for _ in range(7):
        stuur_interactie(bus, "Ik hou van kaas op brood", "Kaas is heerlijk, ja.")

    # Wat neutrale ruis
    stuur_interactie(bus, "Het weer is mooi vandaag", "Fijn dat de zon schijnt.")
    stuur_interactie(bus, "Ik ga morgen fietsen", "Veel plezier met fietsen!")

    snapshot = leerder.get_debug_snapshot()
    python_assoc = snapshot["associations"].get("python", {})
    snel_assoc = snapshot["associations"].get("snel", {})

    print("\n--- Associaties van 'python' (met PMI-score) ---")
    for woord, info in sorted(
        python_assoc.items(), key=lambda x: x[1].get("pmi", 0), reverse=True
    ):
        print(f"  python <-> {woord!r:12} "
              f"co_occurrence={info['co_occurrence']:<3} "
              f"pmi={info.get('pmi', 0):.3f}")

    print("\n--- Associaties van 'snel' (met PMI-score) ---")
    for woord, info in sorted(
        snel_assoc.items(), key=lambda x: x[1].get("pmi", 0), reverse=True
    ):
        print(f"  snel <-> {woord!r:12} "
              f"co_occurrence={info['co_occurrence']:<3} "
              f"pmi={info.get('pmi', 0):.3f}")

    print("\n" + "=" * 60)
    print("Verwacht:")
    print("- 'snel' <-> 'python' heeft een HOGE pmi-score (sterk verband,")
    print("  komen 8x samen voor)")
    print("- 'snel' <-> 'kaas' heeft een LAGE pmi-score (komen maar 1x")
    print("  toevallig samen voor)")
    print("- Alle scores liggen tussen 0.0 en 1.0")
    print("=" * 60)