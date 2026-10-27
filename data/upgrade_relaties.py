#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
upgrade_relaties.py  --  maakt vage 'related_to'-relaties in concepts.json preciezer.

Voorbeeld: 'schop related_to graven' wordt 'schop used_for graven'.

Het script doet twee dingen:
  1. UPGRADEN: de lijst WIJZIGINGEN hieronder verandert het veld "type" van bestaande relaties
     (bij part_of/has_part ook de omgekeerde kant).
  2. OPRUIMEN: een 'related_to' wordt verwijderd als dezelfde twee woorden al een preciezere
     relatie hebben (bijv. 'computer related_to toetsenbord' terwijl 'computer has_part toetsenbord'
     al bestaat). Overbodige dubbelen verdwijnen dus; er gaat geen kennis verloren.
     Met --geen-opruiming sla je deze stap over.
Er worden geen woorden of betekenissen verwijderd of toegevoegd.

GEBRUIK (Nova eerst stoppen!):
    python3 upgrade_relaties.py                 -> PROEFRUN: laat alleen zien wat er zou veranderen
    python3 upgrade_relaties.py --toepassen     -> maakt een back-up en past de wijzigingen echt toe
    python3 upgrade_relaties.py --bestand pad/naar/concepts.json   -> ander bestand gebruiken
    python3 upgrade_relaties.py --geen-opruiming                   -> alleen upgraden, niet opruimen
"""
import argparse
import json
import os
import shutil
import sys
from datetime import datetime

# ---------------------------------------------------------------------------
# DE LIJST MET WIJZIGINGEN
# (woord, oud_type, doelwoord, nieuw_type)
# Leesvoorbeeld: ("doorn", "related_to", "roos", "part_of")  =  "een doorn is een onderdeel van een roos"
# ---------------------------------------------------------------------------
WIJZIGINGEN = [
    # X is een soort Y
    ("huisdier",    "related_to", "dier",          "is_a"),
    ("limiet",      "related_to", "grens",         "is_a"),
    ("storm",       "related_to", "wind",          "is_a"),
    ("emotie",      "related_to", "gevoel",        "is_a"),
    ("oceaan",      "related_to", "zee",           "is_a"),
    ("haan",        "related_to", "kip",           "is_a"),
    ("vleugel",     "related_to", "piano",         "is_a"),   # de piano-betekenis van vleugel
    ("document",    "related_to", "bestand",       "is_a"),
    ("zoekmachine", "related_to", "website",       "is_a"),
    ("email",       "related_to", "bericht",       "is_a"),
    ("elektriciteit", "related_to", "energie",     "is_a"),
    ("warmte",      "related_to", "energie",       "is_a"),
    # X is een onderdeel van Y / Y heeft X
    ("zaad",        "related_to", "plant",         "part_of"),
    ("computer",    "related_to", "hardware",      "has_part"),
    ("computer",    "related_to", "software",      "has_part"),
    ("computer",    "related_to", "besturingssysteem", "has_part"),
    ("computer",    "related_to", "chip",          "has_part"),
    ("bos",         "related_to", "boom",          "has_part"),
    # waarvoor gebruik je X?
    ("kabel",       "related_to", "elektriciteit", "used_for"),
    ("zwangerschapstest", "related_to", "zwangerschap", "used_for"),
]

# Bij deze types hoort een omgekeerde relatie aan de andere kant.
SPIEGEL = {"part_of": "has_part", "has_part": "part_of"}


def levende_senses(concept):
    """Alleen betekenissen die niet zijn afgekeurd (rejected)."""
    return [s for s in concept.get("senses", []) if s.get("status") != "rejected"]


def zoek_relatie(data, woord, rel_type, doel):
    """Zoekt een niet-afgekeurde relatie. Geeft (sense, relatie) of (None, None)."""
    concept = data.get(woord)
    if not concept:
        return None, None
    for sense in levende_senses(concept):
        for rel in sense.get("relations", []):
            if (rel.get("type") == rel_type and rel.get("target") == doel
                    and rel.get("status") != "rejected"):
                return sense, rel
    return None, None


def bestaat_al(data, woord, rel_type, doel):
    return zoek_relatie(data, woord, rel_type, doel)[1] is not None


def pas_toe(data):
    """Voert alle wijzigingen uit in 'data' (in het geheugen). Geeft een rapport terug."""
    rapport = []
    aantal = 0
    for woord, oud, doel, nieuw in WIJZIGINGEN:
        tekst = f"{woord} {oud} {doel}  ->  {nieuw}"
        if woord not in data:
            rapport.append(("OVERGESLAGEN", tekst, f"woord '{woord}' bestaat niet in het bestand"))
            continue
        sense, rel = zoek_relatie(data, woord, oud, doel)
        if rel is None:
            rapport.append(("OVERGESLAGEN", tekst, "deze relatie staat er niet (meer) in"))
            continue
        if bestaat_al(data, woord, nieuw, doel):
            rapport.append(("OVERGESLAGEN", tekst, f"'{woord} {nieuw} {doel}' bestaat al"))
            continue
        rel["type"] = nieuw
        aantal += 1
        rapport.append(("GEWIJZIGD", tekst, ""))
        # omgekeerde kant bijwerken (alleen part_of <-> has_part)
        spiegel = SPIEGEL.get(nieuw)
        if spiegel:
            s2, r2 = zoek_relatie(data, doel, "related_to", woord)
            if r2 is not None and not bestaat_al(data, doel, spiegel, woord):
                r2["type"] = spiegel
                aantal += 1
                rapport.append(("GEWIJZIGD", f"{doel} related_to {woord}  ->  {spiegel}", "(omgekeerde kant)"))
    return rapport, aantal


def opruimen(data):
    """Verwijdert 'related_to' als dezelfde twee woorden al een preciezere relatie hebben.
    Geeft (rapport, aantal) terug."""
    rapport = []
    aantal = 0
    for woord, concept in data.items():
        for sense in levende_senses(concept):
            nieuwe_lijst = []
            for rel in sense.get("relations", []):
                if rel.get("type") != "related_to" or rel.get("status") == "rejected":
                    nieuwe_lijst.append(rel)
                    continue
                doel = rel.get("target")
                reden = None
                # a) in dezelfde betekenis bestaat al een preciezere relatie naar hetzelfde woord
                for r2 in sense.get("relations", []):
                    if (r2 is not rel and r2.get("target") == doel and r2.get("status") != "rejected"
                            and r2.get("type") != "related_to"):
                        reden = f"{woord} {r2['type']} {doel}"
                        break
                # b) het doelwoord heeft zelf al een preciezere relatie terug naar dit woord
                if reden is None and doel in data:
                    for s2 in levende_senses(data[doel]):
                        for r2 in s2.get("relations", []):
                            if (r2.get("target") == woord and r2.get("status") != "rejected"
                                    and r2.get("type") != "related_to"):
                                reden = f"{doel} {r2['type']} {woord}"
                                break
                        if reden:
                            break
                if reden:
                    rapport.append(("VERWIJDERD", f"{woord} related_to {doel}", f"(want: {reden})"))
                    aantal += 1
                else:
                    nieuwe_lijst.append(rel)
            sense["relations"] = nieuwe_lijst
    return rapport, aantal


def main():
    ap = argparse.ArgumentParser(description="Maak related_to-relaties in concepts.json preciezer.")
    ap.add_argument("--bestand", default=os.path.join("data", "concepts.json"),
                    help="pad naar concepts.json (standaard: data/concepts.json)")
    ap.add_argument("--geen-opruiming", action="store_true",
                    help="alleen de lijst WIJZIGINGEN uitvoeren, geen dubbele related_to verwijderen")
    ap.add_argument("--toepassen", action="store_true",
                    help="schrijf de wijzigingen echt weg (zonder deze optie is het een proefrun)")
    args = ap.parse_args()

    if not os.path.exists(args.bestand):
        print(f"FOUT: bestand niet gevonden: {args.bestand}")
        print("Tip: start dit script vanuit de map waar de map 'data' in staat (bijv. /app).")
        sys.exit(1)

    with open(args.bestand, encoding="utf-8") as f:
        data = json.load(f)

    print("=== DEEL 1: relaties preciezer maken ===")
    rapport, aantal = pas_toe(data)
    for status, tekst, opm in rapport:
        print(f"  [{status:12}] {tekst} {opm}")
    overgeslagen = sum(1 for r in rapport if r[0] == "OVERGESLAGEN")
    print(f"\nDeel 1: {aantal} relaties gewijzigd, {overgeslagen} overgeslagen.")

    verwijderd = 0
    if not args.geen_opruiming:
        print("\n=== DEEL 2: overbodige dubbele related_to opruimen ===")
        rapport2, verwijderd = opruimen(data)
        for status, tekst, opm in rapport2:
            print(f"  [{status:12}] {tekst} {opm}")
        print(f"\nDeel 2: {verwijderd} overbodige relaties verwijderd.")
    aantal += verwijderd
    print(f"\nTOTAAL: {aantal} wijzigingen.")

    if not args.toepassen:
        print("\nDit was een PROEFRUN: er is niets opgeslagen.")
        print("Klopt het rapport? Draai dan opnieuw met:  python3 upgrade_relaties.py --toepassen")
        return
    if aantal == 0:
        print("Niets te wijzigen, bestand blijft ongemoeid.")
        return

    # 1) back-up maken
    stempel = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = f"{args.bestand}.backup_{stempel}"
    shutil.copy2(args.bestand, backup)
    print(f"\nBack-up gemaakt: {backup}")

    # 2) veilig wegschrijven: eerst naar een tijdelijk bestand, dan pas vervangen
    tmp = args.bestand + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(tmp, encoding="utf-8") as f:   # controle: is het geldige JSON?
        json.load(f)
    os.replace(tmp, args.bestand)
    print(f"Klaar! {args.bestand} is bijgewerkt. Start Nova nu opnieuw.")
    print(f"Iets mis? Zet de back-up terug:  cp {backup} {args.bestand}")


if __name__ == "__main__":
    main()