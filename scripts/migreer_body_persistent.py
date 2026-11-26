"""Eenmalig: data/body_persistent.json naar de state store.

Kopieert, verplaatst niet: body_state.py leest tot fase 0.4 nog uit het
origineel. Dat blijft dus staan, met een .bak ernaast.
"""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.state_store import StateStore  # noqa: E402

TOEGESTAAN = {
    "maagd", "nat", "pijn", "voorkeur", "bloos", "bravoure_boost",
    "laatste_event_ts", "gewend", "ervaring", "telling", "laatste_zone",
}


def main(bron=None, doel=None) -> int:
    bron = Path(bron or ROOT / "data" / "body_persistent.json")
    doel = Path(doel or ROOT / "data" / "state.json")

    if not bron.exists():
        print(f"geen bronbestand: {bron}")
        return 1

    with open(bron, "r", encoding="utf-8") as f:
        oud = json.load(f)

    onbekend = set(oud) - TOEGESTAAN
    if onbekend:
        print(f"onbekende sleutels overgeslagen: {sorted(onbekend)}")
    schoon = {k: v for k, v in oud.items() if k in TOEGESTAAN}

    store = StateStore(doel)
    store.registreer("body", {})
    with store.muteer("body") as data:
        data.update(schoon)
    store.flush(True)

    shutil.copy2(bron, bron.with_name(bron.name + ".bak"))
    print(f"{len(schoon)} sleutels gemigreerd, origineel bewaard als .bak")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())