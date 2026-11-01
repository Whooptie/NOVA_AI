# scripts/terugblik_status.py
#
# Toont wat de datum-terugblik (modules/knowledge/datum_terugblik.py) NU zou
# vinden, zonder dat Nova iets zegt en zonder iets te wijzigen. Leest
# data/interactions.db ALLEEN-LEZEN, dus je kan dit veilig draaien terwijl
# Nova draait.
#
# Gebruik (vanuit de projectmap, bv. /app in de container):
#   python scripts/terugblik_status.py
#   python scripts/terugblik_status.py --datum 2026-12-15    (simuleer een andere dag)
#
# In Docker op battleserver:
#   docker exec nova-ai python scripts/terugblik_status.py

import argparse
import sys
from datetime import date, datetime, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from modules.knowledge import datum_terugblik as dt  # noqa: E402


def main():
    ouder = argparse.ArgumentParser(description="Toon wat de datum-terugblik zou vinden.")
    ouder.add_argument("--datum", help="simuleer deze dag (JJJJ-MM-DD), standaard vandaag")
    args = ouder.parse_args()

    nu_datum = date.fromisoformat(args.datum) if args.datum else dt._nu().date()
    db = ROOT / "data" / "interactions.db"
    if not db.exists():
        print(f"Database niet gevonden: {db}")
        return 1

    ondergrens = datetime.combine(nu_datum, time(23, 59)).timestamp() - dt.LOOKBACK_DAGEN * 86400
    rijen = dt.lees_rijen_uit_db(db, ROOT / "data" / "archive", ondergrens)
    rijen = [r for r in rijen if dt._naar_dt(r[0]).date() <= nu_datum]
    print(f"{len(rijen)} berichten ingelezen.\n")
    print(dt.formatteer_status(dt.vind_terugblik(rijen, nu_datum), nu_datum))
    return 0


if __name__ == "__main__":
    sys.exit(main())