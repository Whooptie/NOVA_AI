#!/usr/bin/env python3
# tools/maak_blind_cases.py
"""
Zet je eigen zinnen om naar blinde taalbenchmark-cases (punt 61/62).

Je schrijft een gewoon tekstbestand, een zin per regel, in dit vaste formaat:

    type | vraag | verwachte woorden (gescheiden door komma's)

Voorbeelden:

    definitie | kun je me vertellen wat een hond is | wolf, dier, huisdier
    relatie   | klopt het dat een kat een zoogdier is | ja
    oorzaak   | waardoor ontstaat modder | regen
    gevolg    | wat komt er van regen | modder
    synoniem  | welk woord betekent hetzelfde als zus | zuster
    onbekend  | is een glorbix een vis

Types: definitie, relatie, oorzaak, gevolg, synoniem, onbekend.
- Bij 'onbekend' (taalniveau 5) laat je de woorden weg: Nova hoort dan
  eerlijk te zeggen dat ze het niet weet, en mag NOOIT "ja" of "nee" antwoorden.
- De verwachte woorden komen uit WAT WAAR IS (jouw kennis / concepts.json),
  NIET uit wat Nova nu toevallig antwoordt.
- Lege regels en regels die met # beginnen worden overgeslagen.

GEBRUIK (vanuit de projectmap, bv. /app)
    python tools/maak_blind_cases.py blind_nieuw.txt            # controleert enkel (droog)
    python tools/maak_blind_cases.py blind_nieuw.txt --schrijf  # voegt toe aan de blinde set

Het script voegt NIETS toe als een regel een fout heeft, of als een vraag al
in de vaste of de blinde set staat.
"""

import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAST_PAD = os.path.join(PROJECT_ROOT, "tests", "benchmark", "benchmark_taalbegrip.json")
BLIND_PAD = os.path.join(PROJECT_ROOT, "tests", "benchmark", "benchmark_taalbegrip_blind.json")

TYPES = {
    "definitie": ("intent_definition", "definitie"),
    "relatie": ("intent_relation_check", "relatie"),
    "oorzaak": ("intent_causes", "oorzaak"),
    "gevolg": ("intent_effects", "gevolg"),
    "synoniem": ("intent_synonym", "synoniem"),
}
ONBEKEND_WOORDEN = ["ken", "onbekend", "weet", "idee"]
ONBEKEND_VERBODEN = ["ja", "nee"]


def lees_regels(pad):
    """Geeft (cases, fouten). Case = dict zonder id; fouten = lijst teksten."""
    cases, fouten = [], []
    with open(pad, encoding="utf-8") as f:
        for nummer, regel in enumerate(f, start=1):
            regel = regel.strip()
            if not regel or regel.startswith("#"):
                continue
            delen = [d.strip() for d in regel.split("|")]
            if len(delen) < 2:
                fouten.append(f"regel {nummer}: gebruik 'type | vraag | woorden' ({regel!r})")
                continue
            soort, vraag = delen[0].lower(), delen[1]
            woorden = [w.strip().lower() for w in delen[2].split(",") if w.strip()] if len(delen) > 2 else []
            if not vraag:
                fouten.append(f"regel {nummer}: de vraag is leeg")
                continue
            if soort == "onbekend":
                cases.append({
                    "taalniveau": 5, "dimensie": "onzekerheid", "categorie": "onbekend",
                    "vraag": vraag, "moet_bevatten_een_van": ONBEKEND_WOORDEN,
                    "mag_niet_bevatten": ONBEKEND_VERBODEN,
                })
            elif soort in TYPES:
                if not woorden:
                    fouten.append(f"regel {nummer}: geef minstens één verwacht woord (bv. 'ja' of 'wolf, dier')")
                    continue
                event, categorie = TYPES[soort]
                cases.append({
                    "taalniveau": 2, "dimensie": "intentie", "categorie": categorie,
                    "vraag": vraag, "moet_event": [event], "moet_bevatten_een_van": woorden,
                })
            else:
                fouten.append(f"regel {nummer}: onbekend type {soort!r} (kies uit "
                              f"{', '.join(list(TYPES) + ['onbekend'])})")
    return cases, fouten


def _laad(pad):
    with open(pad, encoding="utf-8") as f:
        return json.load(f)


def voeg_toe(cases, vast_pad=VAST_PAD, blind_pad=BLIND_PAD, schrijf=False):
    """Controleert dubbels, geeft id's, schrijft optioneel. Geeft (toegevoegd, fouten)."""
    vast, blind = _laad(vast_pad), _laad(blind_pad)
    bestaand = {c["vraag"].strip().lower() for c in vast["cases"] + blind["cases"]}
    fouten, nieuw = [], []
    volgnummer = {}
    for c in blind["cases"]:
        deel = c["id"].rsplit("-", 1)
        if len(deel) == 2 and deel[1].isdigit():
            sleutel = deel[0]
            volgnummer[sleutel] = max(volgnummer.get(sleutel, 0), int(deel[1]))
    for c in cases:
        sleutel_vraag = c["vraag"].strip().lower()
        if sleutel_vraag in bestaand:
            fouten.append(f"staat al in de vaste of blinde set: {c['vraag']!r}")
            continue
        bestaand.add(sleutel_vraag)
        sleutel = f"blind-t{c['taalniveau']}"
        volgnummer[sleutel] = volgnummer.get(sleutel, 0) + 1
        c = dict(c)
        c["id"] = f"{sleutel}-{volgnummer[sleutel]:02d}"
        nieuw.append(c)
    if fouten:
        return [], fouten
    if schrijf and nieuw:
        blind["cases"] = blind["cases"] + nieuw
        with open(blind_pad, "w", encoding="utf-8") as f:
            json.dump(blind, f, ensure_ascii=False, indent=1)
    return nieuw, []


def main(argv=None):
    ap = argparse.ArgumentParser(description="Eigen zinnen omzetten naar blinde taalcases")
    ap.add_argument("bestand", help="tekstbestand met 'type | vraag | woorden' per regel")
    ap.add_argument("--schrijf", action="store_true", help="voeg echt toe aan de blinde set")
    args = ap.parse_args(argv)

    if not os.path.exists(args.bestand):
        print(f"Bestand niet gevonden: {args.bestand}")
        return 1
    cases, fouten = lees_regels(args.bestand)
    if fouten:
        print("Niets toegevoegd, los dit eerst op:")
        for f in fouten:
            print(f"  - {f}")
        return 1
    nieuw, fouten = voeg_toe(cases, schrijf=args.schrijf)
    if fouten:
        print("Niets toegevoegd, los dit eerst op:")
        for f in fouten:
            print(f"  - {f}")
        return 1
    for c in nieuw:
        print(f"  {c['id']}: T{c['taalniveau']} {c['vraag']}")
    if args.schrijf:
        print(f"\n{len(nieuw)} cases toegevoegd aan {os.path.relpath(BLIND_PAD, PROJECT_ROOT)}.")
    else:
        print(f"\n{len(nieuw)} cases zijn in orde. Niets geschreven (voeg --schrijf toe om echt toe te voegen).")
    return 0


if __name__ == "__main__":
    sys.exit(main())