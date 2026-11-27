# modules/body/bekeken.py
"""Bekeken-as: zelfbewustzijn bij observatie, los van aanraking.

Adolescent zelfbewustzijn ("denkbeeldig publiek"): ze wordt hyperbewust van
bekeken worden, ook als er niets aangeraakt wordt. Stijgt bij observatie,
zakt met de tijd. Boven de drempel worden antwoorden kort en stijgt bloos
licht mee.

Los van body_state: eigen as, eigen decay. body_state leest hier niets van,
bekeken publiceert alleen.
"""

from pathlib import Path

from core import clock
from core.state_store import StateStore
from core.thresholds import Drempel

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
STATE_PAD = DATA_DIR / "state.json"

TRIGGER_EVENTS = ("intent_uiterlijk", "bekeken_trigger")

DREMPEL_HOOG = 0.45
DREMPEL_LAAG = 0.35
STIJGING = 0.15
DAAL_PER_MINUUT = 0.035

_STORES = {}


def _gedeelde_store(pad):
    sleutel = str(Path(pad).resolve())
    if sleutel not in _STORES:
        _STORES[sleutel] = StateStore(pad)
    return _STORES[sleutel]


class Bekeken:
    def __init__(self, event_bus, store=None):
        self.event_bus = event_bus
        self._store = store or _gedeelde_store(STATE_PAD)
        self._store.registreer("bekeken", {"waarde": 0.0, "laatste_ts": 0.0})
        self._state = self._store.get("bekeken")

        self._drempel = Drempel(DREMPEL_HOOG, DREMPEL_LAAG)
        self._drempel.set(self._verval(len_ts=False))

        for naam in TRIGGER_EVENTS:
            event_bus.subscribe(naam, self.on_trigger)

    # ---------------- state ----------------
    def _verval(self, len_ts: bool = True) -> float:
        nu = clock.now()
        vorige = self._state.get("laatste_ts", 0.0)
        waarde = float(self._state.get("waarde", 0.0))

        if vorige and nu > vorige:
            nieuw = max(0.0, waarde - (nu - vorige) / 60.0 * DAAL_PER_MINUUT)
            if nieuw != waarde:
                self._state["waarde"] = nieuw
                self._store.touch("bekeken")
            waarde = nieuw
        if len_ts:
            self._state["laatste_ts"] = nu
        return waarde

    def waarde(self) -> float:
        return self._verval()

    def is_actief(self) -> bool:
        # Via de Drempel, zodat de band echt geldt: aan vanaf
        # DREMPEL_HOOG, pas weer uit onder DREMPEL_LAAG.
        self._drempel.kruist(self._verval())
        return self._drempel.actief

    # ---------------- gedrag ----------------
    def on_trigger(self, data=None, event_type=None):
        self.verhoog()

    def verhoog(self, factor: float = 1.0) -> float:
        huidig = self._verval()

        # Eerst herwapenen op de vervallen waarde. Anders blijft de drempel
        # hangen wanneer de volgende trigger meteen weer boven komt.
        if self._drempel.kruist(huidig):
            self.event_bus.publish("bekeken_changed", {"waarde": huidig, "actief": True})

        self._state["waarde"] = min(1.0, huidig + STIJGING * factor)
        waarde = self._state["waarde"]

        if self._drempel.kruist(waarde):
            self.event_bus.publish("bekeken_changed", {"waarde": waarde, "actief": True})

        self._store.touch("bekeken")
        return waarde

        
    def on_trigger(self, data=None, event_type=None):
        self.verhoog()

def init_module(event_bus, sem=None):
    return Bekeken(event_bus)