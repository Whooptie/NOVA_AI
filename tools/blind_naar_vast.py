#!/usr/bin/env python3
# tools/blind_naar_vast.py
"""
Verhuist ALLE cases uit de blinde taalset naar de vaste taalset (punt 62a).

Waarom: blinde zinnen zijn "verbrand" zodra je ze gezien en daarop patronen
gebouwd hebt. Ze horen dan in de vaste set (regressie), en de blinde set
begint weer leeg voor een verse batch.

Wat het doet
- Elke blinde case krijgt een nieuw id in de vaste set: taal-t<niveau>-<nr>,
  doorgenummerd na het hoogste bestaande nummer van dat niveau.
- Cases waarvan de vraag al in de vaste set staat worden niet dubbel gezet;
  ze worden gewoon uit de blinde set gehaald.
- De blinde set blijft daarna leeg (met zijn uitleg) staan.

GEBRUIK (vanuit de projectmap, bv. /app)
    python tools/blind_naar_vast.py            # toont enkel wat er zou gebeuren
    python tools/blind_naar_vast.py --schrijf  # voert de verhuizing echt uit
"""

import argparse
import json
import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAST_PAD = os.path.join(PROJECT_ROOT, "tests", "benchmark", "benchmark_taalbegrip.json")
BLIND_PAD = os.path.join(PROJECT_ROOT, "tests", "benchmark", "benchmark_taalbegrip_blind.json")


def _lees(pad):
    with open(pad, encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("cases", [])   # lege set zonder "cases"-sleutel mag
    return data


def _schrijf(pad, data):
    with open(pad, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _sleutel(case):
    """Dezelfde vraag na een andere eerdere beurt is een andere case (punt 62d)."""
    voor = " >> ".join(v.strip().lower() for v in case.get("voorvragen", []))
    vraag = case["vraag"].strip().lower()
    return f"{voor} >> {vraag}" if voor else vraag


def plan_verhuizing(vast, blind):
    """Berekent de verhuizing zonder iets te schrijven.

    Geeft (nieuwe_vaste_cases, overgeslagen_vragen):
    nieuwe_vaste_cases = lijst (oud_id, nieuwe_case), overgeslagen = vragen die al vast waren.
    """
    bestaande_vragen = {_sleutel(c) for c in vast["cases"]}
    hoogste = {}
    for c in vast["cases"]:
        m = re.match(r"taal-t(\d+)-(\d+)$", c["id"])
        if m:
            niveau, nr = int(m.group(1)), int(m.group(2))
            hoogste[niveau] = max(hoogste.get(niveau, 0), nr)

    nieuw, overgeslagen = [], []
    for c in blind["cases"]:
        vraag = _sleutel(c)
        if vraag in bestaande_vragen:
            overgeslagen.append(c["vraag"])
            continue
        niveau = int(c.get("taalniveau", 0))
        hoogste[niveau] = hoogste.get(niveau, 0) + 1
        kopie = dict(c)
        kopie["id"] = f"taal-t{niveau}-{hoogste[niveau]:02d}"
        nieuw.append((c["id"], kopie))
        bestaande_vragen.add(vraag)
    return nieuw, overgeslagen


def main(argv=None, vast_pad=VAST_PAD, blind_pad=BLIND_PAD):
    ap = argparse.ArgumentParser(description="Verhuis alle blinde taalcases naar de vaste set.")
    ap.add_argument("--schrijf", action="store_true", help="voer de verhuizing echt uit")
    args = ap.parse_args(argv)

    vast, blind = _lees(vast_pad), _lees(blind_pad)
    nieuw, overgeslagen = plan_verhuizing(vast, blind)

    print(f"Blinde set: {len(blind['cases'])} cases. Vaste set nu: {len(vast['cases'])} cases.")
    for oud, case in nieuw:
        print(f"  {oud} -> {case['id']}: {case['vraag']}")
    for vraag in overgeslagen:
        print(f"  (al in vaste set, wordt niet dubbel gezet): {vraag}")

    if not args.schrijf:
        print("\nNiets geschreven (voeg --schrijf toe om echt te verhuizen).")
        return 0

    vast["cases"].extend(case for _, case in nieuw)
    blind["cases"] = []
    _schrijf(vast_pad, vast)
    _schrijf(blind_pad, blind)
    print(f"\nKlaar: vaste set heeft nu {len(vast['cases'])} cases, de blinde set is leeg.")
    print("Vraag nu een verse batch aan Grok en voeg die toe met tools/maak_blind_cases.py --schrijf.")
    return 0


if __name__ == "__main__":
    sys.exit(main())