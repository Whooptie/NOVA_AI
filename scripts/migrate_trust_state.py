# scripts/migrate_trust_state.py
#
# Eenmalig migratiescript (punt 3, "Trust state", 6 augustus 2026).
#
# WAT DIT DOET:
# Voegt een "status"-veld toe aan elke bestaande sense en elke bestaande
# relatie in concepts.json, afgeleid uit het al bestaande "source"-veld:
#   source == "user"  -> status = "confirmed"
#   source == alles anders (auto, auto_extract, wikipedia, ...)
#                     -> status = "unverified"
#
# WAT DIT NOOIT DOET:
# - Een bestaande "status" overschrijven (enkel toevoegen als hij ontbreekt)
# - Enig ander veld wijzigen (definition, confidence, relations, audit_log,
#   metadata blijven exact zoals ze waren)
# - Concepten/senses/relaties verwijderen of toevoegen
#
# VEILIGHEID:
# 1. Draait STANDAARD in dry-run modus -- schrijft niets weg, toont enkel
#    een samenvatting + een leesbaar diff-verslag.
# 2. Pas met --apply wordt er echt geschreven, en dan ALTIJD pas nadat
#    er eerst een timestamped backup is weggeschreven.
# 3. Na het schrijven wordt het resultaat opnieuw ingelezen en gevalideerd
#    (zelfde aantal concepten/senses/relaties als ervoor) -- bij een
#    afwijking stopt het script met een foutmelding, zonder de backup
#    te verwijderen.
# 4. Idempotent: een tweede keer draaien verandert niets meer.
#
# BELANGRIJK: zet Nova stil (geen actieve daemon-run) terwijl je dit met
# --apply draait, anders kunnen Nova's eigen schrijfacties en dit script
# elkaar overschrijven.
#
# GEBRUIK:
#   python scripts/migrate_trust_state.py                # dry-run (veilig, altijd eerst dit)
#   python scripts/migrate_trust_state.py --apply         # echt uitvoeren
#   python scripts/migrate_trust_state.py --apply --file pad/naar/concepts.json

import json
import os
import sys
import argparse
import copy
from datetime import datetime


def bepaal_status(source: str) -> str:
    return "confirmed" if source == "user" else "unverified"


def migreer(data: dict) -> tuple[dict, list[dict]]:
    """
    Geeft (nieuwe_data, wijzigingen) terug.
    wijzigingen is een lijst van dicts, één per aangepaste sense/relatie,
    bedoeld voor het leesbare diff-verslag.
    """
    nieuwe_data = copy.deepcopy(data)
    wijzigingen = []

    for word, concept in nieuwe_data.items():
        for sense in concept.get("senses", []):
            if "status" not in sense:
                source = sense.get("source", "?")
                status = bepaal_status(source)
                sense["status"] = status
                wijzigingen.append({
                    "type": "sense",
                    "woord": word,
                    "sense_id": sense.get("sense_id"),
                    "definition_preview": (sense.get("definition") or "")[:60],
                    "source": source,
                    "nieuwe_status": status,
                })

            for rel in sense.get("relations", []):
                if "status" not in rel:
                    source = rel.get("source", "?")
                    status = bepaal_status(source)
                    rel["status"] = status
                    wijzigingen.append({
                        "type": "relatie",
                        "woord": word,
                        "sense_id": sense.get("sense_id"),
                        "relatie": f"{rel.get('type')} -> {rel.get('target')}",
                        "source": source,
                        "nieuwe_status": status,
                    })

    return nieuwe_data, wijzigingen


def tel_stats(data: dict) -> dict:
    aantal_concepten = len(data)
    aantal_senses = 0
    aantal_relaties = 0
    for concept in data.values():
        senses = concept.get("senses", [])
        aantal_senses += len(senses)
        for s in senses:
            aantal_relaties += len(s.get("relations", []))
    return {
        "concepten": aantal_concepten,
        "senses": aantal_senses,
        "relaties": aantal_relaties,
    }


def print_samenvatting(wijzigingen: list[dict]) -> None:
    senses_gewijzigd = [w for w in wijzigingen if w["type"] == "sense"]
    rels_gewijzigd = [w for w in wijzigingen if w["type"] == "relatie"]

    def tel_status(lijst):
        confirmed = sum(1 for w in lijst if w["nieuwe_status"] == "confirmed")
        unverified = sum(1 for w in lijst if w["nieuwe_status"] == "unverified")
        return confirmed, unverified

    sc, su = tel_status(senses_gewijzigd)
    rc, ru = tel_status(rels_gewijzigd)

    print("=" * 60)
    print("SAMENVATTING")
    print("=" * 60)
    print(f"Senses die een status krijgen:    {len(senses_gewijzigd)}")
    print(f"  -> confirmed (source=user):     {sc}")
    print(f"  -> unverified (andere source):  {su}")
    print()
    print(f"Relaties die een status krijgen:  {len(rels_gewijzigd)}")
    print(f"  -> confirmed (source=user):     {rc}")
    print(f"  -> unverified (andere source):  {ru}")
    print("=" * 60)


def schrijf_diff_verslag(wijzigingen: list[dict], pad: str) -> None:
    with open(pad, "w", encoding="utf-8") as f:
        f.write("Trust state migratie -- diff-verslag\n")
        f.write(f"Gegenereerd op: {datetime.now().isoformat()}\n")
        f.write("=" * 70 + "\n\n")

        senses = [w for w in wijzigingen if w["type"] == "sense"]
        rels = [w for w in wijzigingen if w["type"] == "relatie"]

        f.write(f"SENSES ({len(senses)} totaal)\n")
        f.write("-" * 70 + "\n")
        for w in senses:
            f.write(
                f"[{w['nieuwe_status']:10}] {w['woord']} ({w['sense_id']}) "
                f"source={w['source']:12} \"{w['definition_preview']}\"\n"
            )

        f.write("\n")
        f.write(f"RELATIES ({len(rels)} totaal)\n")
        f.write("-" * 70 + "\n")
        for w in rels:
            f.write(
                f"[{w['nieuwe_status']:10}] {w['woord']} ({w['sense_id']}) "
                f"{w['relatie']:30} source={w['source']}\n"
            )

    print(f"\nVolledig diff-verslag weggeschreven naar: {pad}")


def main():
    parser = argparse.ArgumentParser(
        description="Migreert concepts.json naar trust state (status-veld)."
    )
    parser.add_argument(
        "--file", default=os.path.join("data", "concepts.json"),
        help="Pad naar concepts.json (default: data/concepts.json)"
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Schrijft de wijziging echt weg. Zonder deze vlag: enkel dry-run."
    )
    args = parser.parse_args()

    pad = args.file
    if not os.path.exists(pad):
        print(f"FOUT: bestand niet gevonden: {pad}")
        sys.exit(1)

    with open(pad, "r", encoding="utf-8") as f:
        oude_data = json.load(f)

    oude_stats = tel_stats(oude_data)
    nieuwe_data, wijzigingen = migreer(oude_data)
    nieuwe_stats = tel_stats(nieuwe_data)

    print(f"Bestand: {pad}")
    print(f"Concepten voor migratie:  {oude_stats['concepten']}")
    print(f"Senses voor migratie:     {oude_stats['senses']}")
    print(f"Relaties voor migratie:   {oude_stats['relaties']}")
    print()

    if not wijzigingen:
        print("Niets te migreren -- alle senses/relaties hebben al een status-veld.")
        return

    print_samenvatting(wijzigingen)

    diff_pad = pad + f".trust_state_diff_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    schrijf_diff_verslag(wijzigingen, diff_pad)

    if not args.apply:
        print()
        print(">> DRY RUN -- er is NIETS weggeschreven naar concepts.json.")
        print(">> Lees het diff-verslag na, en draai daarna opnieuw met --apply om echt te migreren.")
        return

    # --- Vanaf hier: echt toepassen ---

    # 1. Backup wegschrijven, VOOR er iets overschreven wordt
    backup_pad = pad + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    with open(backup_pad, "w", encoding="utf-8") as f:
        json.dump(oude_data, f, indent=2, ensure_ascii=False)
    print(f"\nBackup weggeschreven naar: {backup_pad}")

    # 2. Nieuwe data wegschrijven
    with open(pad, "w", encoding="utf-8") as f:
        json.dump(nieuwe_data, f, indent=2, ensure_ascii=False)
    print(f"Nieuwe versie weggeschreven naar: {pad}")

    # 3. Valideren: opnieuw inlezen en structuur vergelijken
    with open(pad, "r", encoding="utf-8") as f:
        gecontroleerde_data = json.load(f)
    gecontroleerde_stats = tel_stats(gecontroleerde_data)

    structuur_klopt = (
        gecontroleerde_stats["concepten"] == oude_stats["concepten"]
        and gecontroleerde_stats["senses"] == oude_stats["senses"]
        and gecontroleerde_stats["relaties"] == oude_stats["relaties"]
    )

    if not structuur_klopt:
        print()
        print("FOUT: validatie na schrijven mislukt -- aantallen komen niet overeen!")
        print(f"  Voor migratie:  {oude_stats}")
        print(f"  Na migratie:    {gecontroleerde_stats}")
        print(f"  De backup staat nog veilig in: {backup_pad}")
        print("  Herstel handmatig door de backup terug te kopiëren naar concepts.json.")
        sys.exit(1)

    # Extra check: telt elke sense/relatie nu een status?
    alle_hebben_status = True
    for concept in gecontroleerde_data.values():
        for s in concept.get("senses", []):
            if "status" not in s:
                alle_hebben_status = False
            for r in s.get("relations", []):
                if "status" not in r:
                    alle_hebben_status = False

    print()
    print("VALIDATIE GESLAAGD:")
    print(f"  Concepten: {gecontroleerde_stats['concepten']} (ongewijzigd)")
    print(f"  Senses: {gecontroleerde_stats['senses']} (ongewijzigd)")
    print(f"  Relaties: {gecontroleerde_stats['relaties']} (ongewijzigd)")
    print(f"  Alle senses/relaties hebben nu een status-veld: {alle_hebben_status}")
    print()
    print("Migratie voltooid. De backup blijft staan als extra veiligheid:")
    print(f"  {backup_pad}")


if __name__ == "__main__":
    main()