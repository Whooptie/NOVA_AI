# tools/kennisgaten_overzicht.py
"""
Toont wat Nova niet wist (data/kennisgaten.jsonl, punt 72a), meest gevraagd
bovenaan, per soort. Verandert niets.

Gebruik (in de map van Nova):
    python tools/kennisgaten_overzicht.py            # alles
    python tools/kennisgaten_overzicht.py oorzaken   # enkel een soort
    python tools/kennisgaten_overzicht.py --pad ander_bestand.jsonl
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

STANDAARD = Path(__file__).resolve().parent.parent / "data" / "kennisgaten.jsonl"


def lees(pad):
    regels = []
    if not Path(pad).exists():
        return regels
    with open(pad, "r", encoding="utf-8") as f:
        for r in f:
            r = r.strip()
            if not r:
                continue
            try:
                regels.append(json.loads(r))
            except Exception:
                continue  # een kapotte regel mag de rest niet blokkeren
    return regels


def overzicht(regels, soort=None):
    per_soort = defaultdict(Counter)
    for r in regels:
        if soort and r.get("soort") != soort:
            continue
        per_soort[r.get("soort", "?")][r.get("woord", "?")] += 1
    return per_soort


def main(argv=None):
    p = argparse.ArgumentParser(description="Overzicht van Nova's kennisgaten")
    p.add_argument("soort", nargs="?", help="bv. oorzaken, gevolgen, synoniemen, woord")
    p.add_argument("--pad", default=str(STANDAARD))
    a = p.parse_args(argv)

    regels = lees(a.pad)
    if not regels:
        print("Nog geen kennisgaten gelogd. Praat wat met Nova en kijk later opnieuw.")
        return 0
    per_soort = overzicht(regels, a.soort)
    if not per_soort:
        print(f"Geen kennisgaten van het soort '{a.soort}'.")
        return 0
    print(f"{len(regels)} kennisgaten in totaal.\n")
    for soort, teller in sorted(per_soort.items(), key=lambda kv: -sum(kv[1].values())):
        print(f"== {soort} ({sum(teller.values())}) ==")
        for woord, n in teller.most_common():
            print(f"  {n}x  {woord}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())