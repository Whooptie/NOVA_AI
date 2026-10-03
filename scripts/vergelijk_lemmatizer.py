# scripts/vergelijk_lemmatizer.py
"""
Vergelijkt de huidige lemmatize_nl() (Layer 1, word_associations_learner.py)
met simplemma, op (1) een vaste lijst lastige woorden en (2) alle echte
woorden uit Kevins twijfel- en onherkende zinnen.

Puur een meting: wijzigt GEEN enkel bestand. Leest enkel:
  - identity/personality/uncertain_signals.jsonl
  - modules/preferences/sentiment_uncertain.jsonl
  - data/unmatched_intents.jsonl

Draaien vanuit de project-root in de container:
  python scripts/vergelijk_lemmatizer.py
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import simplemma
except ImportError:
    print("simplemma is niet geïnstalleerd. Eerst: pip install simplemma")
    sys.exit(1)

from modules.learning.word_associations_learner import WordAssociationsLearner


LASTIGE_WOORDEN = [
    # woorden die op -en/-e eindigen maar geen meervoud/bijvoeglijke vorm zijn
    "morgen", "keuken", "regen", "teken", "gisteren", "liefde", "module", "frame",
    # werkwoorden (infinitief)
    "koken", "schaken", "spelen", "lopen", "vragen",
    # echte meervouden
    "honden", "katten", "huizen", "wolken", "dagen", "mensen", "kinderen", "eieren",
    # verkleinwoorden en bijvoeglijke vormen
    "boekje", "kopje", "snelle", "mooie",
    # onregelmatige werkwoordsvormen
    "liep", "gaven", "dronk", "was", "ging",
]

BRONNEN = [
    PROJECT_ROOT / "identity" / "personality" / "uncertain_signals.jsonl",
    PROJECT_ROOT / "modules" / "preferences" / "sentiment_uncertain.jsonl",
    PROJECT_ROOT / "data" / "unmatched_intents.jsonl",
]


def nieuw(woord):
    return simplemma.lemmatize(woord, lang="nl").lower()


def verzamel_echte_woorden(learner):
    woorden = set()
    for pad in BRONNEN:
        if not pad.exists():
            print(f"(bestand niet gevonden, overgeslagen: {pad.relative_to(PROJECT_ROOT)})")
            continue
        with open(pad, "r", encoding="utf-8") as f:
            for regel in f:
                try:
                    item = json.loads(regel)
                except json.JSONDecodeError:
                    continue
                tekst = item.get("text") or item.get("tekst") or ""
                tokens = learner.filter_stopwords(learner.tokenize(tekst))
                woorden.update(tokens)
    return sorted(woorden)


def main():
    # Zonder event_bus: leest enkel word_associations.json in, schrijft niets.
    learner = WordAssociationsLearner(event_bus=None)

    print("=" * 60)
    print("1. Lastige woorden")
    print("=" * 60)
    print(f"{'woord':<14}{'huidig':<14}{'simplemma':<14}")
    for woord in LASTIGE_WOORDEN:
        oud = learner.lemmatize_nl(woord)
        nw = nieuw(woord)
        markering = "" if oud == nw else "  <-- verschil"
        print(f"{woord:<14}{oud:<14}{nw:<14}{markering}")

    print()
    print("=" * 60)
    print("2. Echte woorden uit je eigen zinnen")
    print("=" * 60)
    echte = verzamel_echte_woorden(learner)
    verschillen = [(w, learner.lemmatize_nl(w), nieuw(w)) for w in echte]
    verschillen = [v for v in verschillen if v[1] != v[2]]

    print(f"Unieke woorden: {len(echte)}")
    print(f"Met een verschil: {len(verschillen)}")
    print()
    print(f"{'woord':<18}{'huidig':<18}{'simplemma':<18}")
    for woord, oud, nw in verschillen[:80]:
        print(f"{woord:<18}{oud:<18}{nw:<18}")
    if len(verschillen) > 80:
        print(f"... en nog {len(verschillen) - 80} meer.")


if __name__ == "__main__":
    main()