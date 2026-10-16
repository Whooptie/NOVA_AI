"""
spacy_verkenning.py -- Semantic Fase 11, stap 0

Doel: kijken wat spaCy (het Nederlandse model nl_core_news_sm) met onze
voorbeeldzinnen doet. Dit script wijzigt NIETS aan Nova en schrijft
geen bestanden. Het print enkel info naar het scherm.

Draaien (op battleserver):
    docker exec nova-ai python scripts/spacy_verkenning.py
"""

import sys
import time

MODEL_NAAM = "nl_core_news_sm"

VOORBEELDZINNEN = [
    # 1. De simpelste is_a-zin
    "Een hond is een zoogdier.",
    # 2. Bijvoeglijk naamwoord tussen 'een' en het echte doel (bekend gat)
    "Een narwal is een arctische walvis die in de Noordpoolzee leeft.",
    # 3. Tussenzin die de regex in de war brengt
    "Een hond, ook wel huisdier genoemd, is een zoogdier.",
    # 4. Eigennaam als onderwerp
    "Python is een programmeertaal die wordt gebruikt voor data science.",
    # 5. Opsomming (voor part_of, later)
    "Een fiets bestaat uit een frame, twee wielen en een stuur.",
    # 6 en 7. Hetzelfde woord, twee woordsoorten
    "Ik kom morgen naar Brugge.",
    "De morgen is mooi.",
    # 8. Voorbehoud: mag NIET zomaar als feit opgeslagen worden
    "Een hond is niet altijd een huisdier.",
    # 9. Verwijswoord als onderwerp: onbruikbaar zonder de vorige zin
    "Het is een dier dat blaft.",
]


def main():
    # --- Stap A: is spaCy geinstalleerd? ---
    try:
        import spacy
    except ImportError:
        print("spaCy is NIET geinstalleerd.")
        print("Installeer eerst met:  docker exec nova-ai pip install spacy")
        sys.exit(1)

    print(f"spaCy-versie: {spacy.__version__}")

    # --- Stap B: is het Nederlandse model aanwezig? ---
    start = time.time()
    try:
        nlp = spacy.load(MODEL_NAAM)
    except OSError:
        print(f"Model '{MODEL_NAAM}' is NIET gevonden.")
        print(f"Download het met:  docker exec nova-ai python -m spacy download {MODEL_NAAM}")
        sys.exit(1)
    laadtijd = time.time() - start

    meta = nlp.meta
    print(f"Model: {meta.get('name')} versie {meta.get('version')}")
    print(f"LICENTIE: {meta.get('license')}")
    print(f"Laadtijd: {laadtijd:.2f} seconden")
    print(f"Onderdelen in het model: {nlp.pipe_names}")

    # --- Stap C: welke labels kent het model? ---
    labels = meta.get("labels", {})
    for onderdeel, lijst in labels.items():
        print(f"\nLabels van '{onderdeel}' ({len(lijst)} stuks):")
        print("  " + ", ".join(lijst))

    # --- Stap D: onze voorbeeldzinnen ontleden ---
    print("\n" + "=" * 70)
    print("ZINNEN ONTLEDEN")
    print("=" * 70)

    for nummer, zin in enumerate(VOORBEELDZINNEN, start=1):
        doc = nlp(zin)
        print(f"\n--- Zin {nummer}: {zin}")
        print(f"{'woord':<16}{'lemma':<16}{'woordsoort':<8}{'rol':<12}{'hoort bij':<14}")
        for token in doc:
            print(
                f"{token.text:<16}{token.lemma_:<16}{token.pos_:<8}"
                f"{token.dep_:<12}{token.head.text:<14}"
            )
        if doc.ents:
            namen = ", ".join(f"{e.text} ({e.label_})" for e in doc.ents)
            print(f"Herkende namen (NER): {namen}")
        else:
            print("Herkende namen (NER): geen")


if __name__ == "__main__":
    main()