#tools/meet_embeddings.py

"""
meet_embeddings.py -- meetscript voor Fase 12, stap 1.

Draai dit vanuit de project-root (de map met main.py):

    python tools/meet_embeddings.py
    python tools/meet_embeddings.py --woorden hond fiets computer
    python tools/meet_embeddings.py --modellen paraphrase-multilingual-MiniLM-L12-v2 \
        paraphrase-multilingual-mpnet-base-v2 intfloat/multilingual-e5-small

Het script pakt NIETS in Nova aan. Het leest data/concepts.json (alleen
lezen) en print per model:
  1. de dichtstbijzijnde buren voor een paar woorden (kijk zelf: zinnig?)
  2. een meetgetal: hoeveel van jouw BEVESTIGDE relaties (is_a, related_to,
     part_of, ...) staan in de top-10 buren? Hoger = het model denkt
     meer zoals jij.
De vectoren van dit script komen in een eigen cache (data/embeddings_meting_*.npz),
dus Nova's eigen cache blijft ongemoeid.
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.knowledge.embedding_specialist import EmbeddingSpecialist  # noqa: E402

STANDAARD_MODELLEN = ["paraphrase-multilingual-MiniLM-L12-v2"]
STANDAARD_WOORDEN = ["hond", "fiets", "computer", "planeet", "huiskat"]
RELATIETYPES = {"is_a", "related_to", "part_of", "has_part", "used_for", "synonym"}


def bevestigde_doelen(concept):
    doelen = set()
    for s in concept.get("senses", []):
        if s.get("status") == "rejected":
            continue
        for r in s.get("relations", []):
            if r.get("status") == "confirmed" and r.get("type") in RELATIETYPES:
                doelen.add(r.get("target"))
    return doelen


def meet_model(naam, concepten, woorden, models_map, top_k_hit=10):
    veilig = naam.replace("/", "_")
    s = EmbeddingSpecialist(
        model_naam=naam, concepten=concepten, models_map=models_map,
        cache_pad=ROOT / "data" / f"embeddings_meting_{veilig}.npz",
    )
    print("\n" + "=" * 70)
    print(f"MODEL: {naam}")
    print("=" * 70)
    t0 = time.time()
    if not s.is_beschikbaar():
        print(f"  Niet beschikbaar: {s.reden_uit}")
        return
    s.concept_vectoren()
    print(f"  Laden + vectoren: {time.time() - t0:.1f} s")

    for w in woorden:
        res = s.find_similar(w, top_k=5)
        if not res:
            print(f"\n  {w}: (onbekend of zonder definitie)")
            continue
        print(f"\n  {w}:")
        for r in res:
            print(f"     {r['score']:.3f}  {r['woord']}")

    treffers = totaal = 0
    for w, c in concepten.items():
        doelen = {d for d in bevestigde_doelen(c) if d in concepten}
        if not doelen:
            continue
        buren = {r["woord"] for r in s.find_similar(w, top_k=top_k_hit)}
        treffers += len(doelen & buren)
        totaal += len(doelen)
    if totaal:
        print(f"\n  MEETGETAL: {treffers}/{totaal} bevestigde relaties staan in de "
              f"top-{top_k_hit} ({100 * treffers / totaal:.1f}%)")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--concepten", default=str(ROOT / "data" / "concepts.json"))
    p.add_argument("--modellen", nargs="+", default=STANDAARD_MODELLEN)
    p.add_argument("--woorden", nargs="+", default=None)
    p.add_argument("--models-map", default=str(ROOT / "data" / "models"))
    a = p.parse_args()

    with open(a.concepten, encoding="utf-8") as f:
        concepten = json.load(f)
    woorden = a.woorden or [w for w in STANDAARD_WOORDEN if w in concepten]
    if len(woorden) < 5:
        woorden += random.Random(1).sample(sorted(concepten), 5 - len(woorden))
    for m in a.modellen:
        meet_model(m, concepten, woorden, a.models_map)


if __name__ == "__main__":
    main()