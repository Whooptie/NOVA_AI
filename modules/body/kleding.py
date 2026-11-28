# modules/body/kleding.py
"""Kledingstaat: wat ze draagt, in welke laag, en wat dat met een aanraking doet.

Dit is het enige stuk van haar lichaam dat in een scène echt kan veranderen.
Zonder deze module ziet de derde keer er identiek uit als de eerste, want er
is niets dat kan verschuiven.

Drie dingen die de module bewaakt:

- **Volgorde.** Er gaat niets uit voordat de laag erboven weg is. Een handeling
  die dat breekt wordt geweigerd, met een zin, en zonder automatische correctie.
- **Demping.** Stof zit tussen de hand en de huid. `demping(zone)` geeft hoeveel
  er nog tussen zit, en `drempel_bonus(zone)` verhoogt de prikkeldrempel
  zolang er iets over die plek zit. `comfort_zone` wordt nooit geraakt.
- **Koud.** Gaat er iets uit terwijl het koud is, dan wordt ze koud. Koud is
  een reden om dichterbij te komen, niet een status.

De toestand staat in de state store en overleeft een reboot. Standaardstanden
gelden alleen als de namespace nog niet bestaat.
"""

import copy
import json
from pathlib import Path

from core import clock
from core.state_store import StateStore
from core.thresholds import Drempel
from modules.body import bekeken as bekeken_module
from modules.body.kleding_tekst import kies

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
STATE_PAD = DATA_DIR / "state.json"
DATA_PAD = DATA_DIR / "kleding.json"

STATEN = ("aan", "los", "verschoven", "uit")
ACTIES = ("aan", "los", "verschoven", "uit")

DREMPEL_KOUD = 0.6
DREMPEL_KOUD_LAAG = 0.4
KOUD_PER_UIT = 0.25
KOUD_PER_MINUUT = 0.03
WARMTE_GRENS = 18.0
VERSCHOVEN_DEMPING = 0.5
DREMPEL_BONUS = 0.15

_STORES = {}


def _gedeelde_store(pad):
    sleutel = str(Path(pad).resolve())
    if sleutel not in _STORES:
        _STORES[sleutel] = StateStore(pad)
    return _STORES[sleutel]


def _valideer(data):
    """Faalt luid bij een kapot bestand in plaats van stil te doen alsof."""
    items = data.get("items") or {}
    if not items:
        raise ValueError("kleding.json: geen items")

    for naam, info in items.items():
        if not isinstance(info.get("laag"), int):
            raise ValueError(f"kleding.json: item {naam} heeft geen laag")
        if "demping" not in info:
            raise ValueError(f"kleding.json: item {naam} heeft geen demping")

    for zone, lijst in (data.get("zones") or {}).items():
        for item in lijst:
            if item not in items:
                raise ValueError(f"kleding.json: zone {zone} verwijst naar onbekend item {item}")

    for stand in ("wakker", "slapen"):
        for item, staat in (data.get("start") or {}).get(stand, {}).items():
            if item not in items:
                raise ValueError(f"kleding.json: start.{stand} kent item {item} niet")
            if staat not in STATEN:
                raise ValueError(f"kleding.json: start.{stand}.{item} is geen geldige staat")

    return data


def _laad_data(pad=DATA_PAD):
    with open(pad, encoding="utf-8") as bestand:
        return _valideer(json.load(bestand))


class Kleding:
    def __init__(self, event_bus, store=None, data=None):
        self.event_bus = event_bus
        self._store = store or _gedeelde_store(STATE_PAD)
        self._data = data or _laad_data()
        self._items = self._data["items"]
        self._zones = self._data.get("zones") or {}
        self._regels = self._data.get("regels") or {}

        standaard = dict(self._data["start"]["wakker"])
        self._store.registreer(
            "kleding", {"items": standaard, "koud": 0.0, "laatste_ts": 0.0}
        )
        self._state = self._store.get("kleding")
        if not self._state.get("items"):
            self._state["items"] = standaard
        if not self._state.get("laatste_ts"):
            self._state["laatste_ts"] = clock.now()

        self._drempel = Drempel(DREMPEL_KOUD, DREMPEL_KOUD_LAAG)
        self._drempel.set(self._verval_koud(len_ts=False))

        event_bus.subscribe("intent_kleding", self.on_intent)
        event_bus.subscribe("intent_slaap", self.on_slaap)

    # ---------------- state ----------------
    def staat(self, item: str) -> str:
        return self._state["items"].get(item, "uit")

    def snapshot(self) -> dict:
        return copy.deepcopy(self._state)

    def is_naakt(self) -> bool:
        return all(self.staat(item) == "uit" for item in self._items)

    def _zet(self, item: str, staat: str) -> None:
        self._state["items"][item] = staat

    def _verval_koud(self, len_ts: bool = True) -> float:
        nu = clock.now()
        vorige = float(self._state.get("laatste_ts", 0.0))
        koud = float(self._state.get("koud", 0.0))

        if vorige and nu > vorige:
            koud = max(0.0, koud - (nu - vorige) / 60.0 * KOUD_PER_MINUUT)
            self._state["koud"] = koud
        if len_ts:
            self._state["laatste_ts"] = nu
        return koud

    def koud(self) -> float:
        return self._verval_koud()

    # ---------------- afgeleid ----------------
    def demping(self, zone: str) -> float:
        """Hoeveel stof er nog tussen een hand en deze plek zit."""
        best = 0.0
        for item in self._zones.get(zone, ()):
            staat = self.staat(item)
            eigen = float(self._items[item]["demping"])
            if staat == "aan":
                best = max(best, eigen)
            elif staat == "verschoven":
                best = max(best, eigen * VERSCHOVEN_DEMPING)
            elif staat == "los" and not self._regels.get("los_zet_demping_op_nul", True):
                best = max(best, eigen)
        return best

    def drempel_bonus(self, zone: str) -> float:
        """Extra prikkeldrempel zolang er iets over die plek zit."""
        return DREMPEL_BONUS if self.demping(zone) > 0 else 0.0

    def _bedekt(self, zone: str) -> list:
        return [i for i in self._zones.get(zone, ()) if self.staat(i) != "uit"]

    def _hoger_aan(self, item: str) -> list:
        """Stukken die boven dit stuk hangen en nog niet uit zijn."""
        eigen_laag = self._items[item]["laag"]
        blokkerend = set()
        for zone, items in self._zones.items():
            if item not in items:
                continue
            for ander in items:
                if ander == item or self.staat(ander) == "uit":
                    continue
                if self._items[ander]["laag"] < eigen_laag:
                    blokkerend.add(ander)
        return sorted(blokkerend)

    def _zone_van(self, item: str):
        for zone, items in self._zones.items():
            if item in items:
                return zone
        return None

    def _temperatuur(self):
        try:
            return float(self._store.get("gesteldheid").get("temperatuur"))
        except Exception:
            return None

    # ---------------- gedrag ----------------
    def on_intent(self, data=None, event_type=None):
        data = data or {}
        item = data.get("item")
        actie = data.get("actie")

        if item not in self._items or actie not in ACTIES:
            return None
        if actie == "los" and item != "short":
            actie = "verschoven"

        huidig = self.staat(item)
        if huidig == actie:
            return None

        if actie == "aan":
            return self._naar_aan(item)
        if huidig == "uit":
            return None

        hoger = self._hoger_aan(item)
        if hoger and self._regels.get("volgorde_breken", "weiger") == "weiger":
            return self._publiceer(kies("weiger", hoger[0]), self._zone_van(item))

        return self._naar(item, actie)

    def _naar_aan(self, item: str):
        groep = self._items[item].get("groep")
        if groep:
            for ander, info in self._items.items():
                if ander != item and info.get("groep") == groep and self.staat(ander) != "uit":
                    self._zet(ander, "uit")
        self._zet(item, "aan")
        return self._publiceer(kies("aan", item), self._zone_van(item))

    def _naar(self, item: str, actie: str):
        self._zet(item, actie)

        tekst = kies(actie, item)
        if actie == "uit" and self._wordt_koud(item):
            tekst = f"{tekst} {kies('koud')}".strip()

        if actie in ("los", "uit"):
            self._bekeken_bonus()

        return self._publiceer(tekst, self._zone_van(item))

    def _wordt_koud(self, item: str) -> bool:
        temperatuur = self._temperatuur()
        if temperatuur is None or temperatuur >= WARMTE_GRENS:
            return False

        self._state["koud"] = min(1.0, self._verval_koud() + KOUD_PER_UIT)
        return self._drempel.kruist(self._state["koud"])

    def _bekeken_bonus(self) -> None:
        bonus = float(self._regels.get("bekeken_bonus", 0.0))
        if not bonus:
            return
        bekeken = getattr(self.event_bus, "modules", {}).get("bekeken")
        if bekeken is None or not bekeken.is_actief():
            return
        bekeken.verhoog(bonus / bekeken_module.STIJGING)

    # ---------------- slapen ----------------
    def on_slaap(self, data=None, event_type=None):
        return self.naar_bed()

    def naar_bed(self) -> dict:
        for item, staat in self._data["start"]["slapen"].items():
            self._zet(item, staat)
        self._meld()
        return dict(self._state["items"])

    def wakker_worden(self) -> dict:
        for item, staat in self._data["start"]["wakker"].items():
            self._zet(item, staat)
        self._meld()
        return dict(self._state["items"])

    # ---------------- uitgang ----------------
    def _meld(self) -> None:
        self._store.touch("kleding")
        self.event_bus.publish("kleding_changed", {"items": dict(self._state["items"])})

    def _publiceer(self, tekst, zone):
        if tekst:
            self.event_bus.publish(
                "body_reactie", {"text": tekst, "zone": zone, "bron": "kleding"}
            )
        self._meld()
        return tekst or None


def init_module(event_bus, sem=None):
    return Kleding(event_bus)