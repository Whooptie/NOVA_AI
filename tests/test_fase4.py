# test_fase4.py
"""
Los testscript voor Fase 4 van Layer 1 (Word Associations Learner).

Test de query-functies: get_associations, find_related, word_distance,
get_word_sentiment, get_stats.
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
    print("FASE 4 TEST — Word Associations Learner (queries)")
    print("=" * 60)

    bus = NepEventBus()
    leerder = WordAssociationsLearner(event_bus=bus)

    for _ in range(6):
        stuur_interactie(bus, "Python is heel snel en elegant", "Ja, Python is top!")
    for _ in range(4):
        stuur_interactie(bus, "Java is traag en saai", "Dat hoor ik vaker over Java.")
    for _ in range(5):
        stuur_interactie(bus, "Ik hou van kaas op brood", "Kaas is heerlijk, ja.")

    print("\n--- get_associations('python') ---")
    print(leerder.get_associations("python"))

    print("\n--- find_related('python', top_k=3) ---")
    print(leerder.find_related("python", top_k=3))

    print("\n--- word_distance('python', 'elegant') (direct) ---")
    print(leerder.word_distance("python", "elegant"))

    print("\n--- word_distance('python', 'saai') (waarschijnlijk indirect/0) ---")
    print(leerder.word_distance("python", "saai"))

    print("\n--- get_word_sentiment('snel') (bekend positief woord) ---")
    print(leerder.get_word_sentiment("snel"))

    print("\n--- get_word_sentiment('traag') (bekend negatief woord) ---")
    print(leerder.get_word_sentiment("traag"))

    print("\n--- get_word_sentiment('python') (onbekend, afgeleid) ---")
    print(leerder.get_word_sentiment("python"))

    print("\n--- get_stats() ---")
    stats = leerder.get_stats()
    print(f"total_words: {stats['total_words']}")
    print(f"total_associations: {stats['total_associations']}")
    print("strongest_associations (top 5):")
    for w1, w2, score in stats["strongest_associations"][:5]:
        print(f"  {w1} <-> {w2}: {score:.3f}")

    print("\n" + "=" * 60)
    print("Verwacht:")
    print("- get_associations('python') geeft een dict met o.a. 'snel',")
    print("  'elegant', gesorteerd van hoog naar laag")
    print("- get_word_sentiment('snel') -> hoge 'positive' score (0.9)")
    print("- get_word_sentiment('traag') -> hoge 'negative' score (0.9)")
    print("- get_word_sentiment('python') -> positief-leunend, want")
    print("  geassocieerd met 'snel'/'elegant'")
    print("=" * 60)