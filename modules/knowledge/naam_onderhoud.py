"""
naam_onderhoud.py — proactieve "nieuwe naam gedetecteerd"-melding
(roadmap punt 12, Layer 7 whitelist-onderhoud).

Wat doet dit?
  Nova telt in Layer 2 (pattern_matcher) alle events. Soms duikt daar een
  NIEUWE naam op (bv. activity_started:gamen, of topic_detected:weer2) die
  niet in de whitelist / vertaallijst van de EmergenceEngine staat. Zo'n naam
  blijft dan stil. Deze module meldt dat een keer aan Kevin, zodat hij hem
  kan toevoegen.

Bewust GEEN insight-type van emergence_engine.reflect(): dit is een
systeem-onderhoudsbericht. 100% symbolisch: tellen, if/else en vaste zinnen.
Geen ML, geen generatie.
"""

import json
import os
import tempfile
import threading
import time
from typing import Dict, List, Optional

from modules.paths import get_project_root

# Hoe vaak moet een nieuwe naam gezien zijn voor we hem melden?
MIN_OBSERVATIES_VOOR_NIEUWE_NAAM_MELDING = 4
CONTROLE_INTERVAL_SECONDEN = 30 * 60      # elke 30 minuten
EERSTE_CONTROLE_NA_SECONDEN = 180         # 3 minuten na opstarten
MAX_NAMEN_PER_BERICHT = 12


class NaamOnderhoud:
    def __init__(self, event_bus, state_pad: Optional[str] = None,
                 start_thread: bool = True):
        self.event_bus = event_bus
        if state_pad is None:
            root = get_project_root(__file__)
            state_pad = str(root / "data" / "naam_onderhoud_state.json")
        self.state_pad = state_pad
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._fout_gemeld = False
        self._thread = None
        # {event_type: {"reden": str, "gemeld_op": float}}
        self.gemeld: Dict[str, Dict] = self._laad_state()

        if start_thread:
            self._thread = threading.Thread(
                target=self._loop, name="NaamOnderhoud", daemon=True)
            self._thread.start()

    # ── state ─────────────────────────────────────────
    def _laad_state(self) -> Dict[str, Dict]:
        try:
            with open(self.state_pad, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data.get("gemeld", {})
        except (OSError, ValueError):
            pass
        return {}

    def _bewaar_state(self) -> None:
        # Atomisch schrijven: eerst tijdelijk bestand, dan vervangen.
        map_ = os.path.dirname(self.state_pad) or "."
        os.makedirs(map_, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=map_, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump({"gemeld": self.gemeld}, f, ensure_ascii=False,
                          indent=2)
            os.replace(tmp, self.state_pad)
        except OSError:
            try:
                os.remove(tmp)
            except OSError:
                pass

    # ── modules ophalen (lazy) ────────────────────────
    def _module(self, naam: str):
        modules = getattr(self.event_bus, "modules", None) or {}
        return modules.get(naam)

    # ── kern ──────────────────────────────────────────
    def vind_nieuwe_namen(self) -> List[Dict]:
        """Geeft [{event_type, naam, reden, total}] van nog niet gemelde namen."""
        pm = self._module("pattern_matcher")
        em = self._module("emergence_engine")
        if pm is None or em is None:
            return []
        try:
            patronen = pm.get_all_patterns() or {}
        except Exception:
            return []

        resultaat = []
        for event_type, info in patronen.items():
            if event_type in self.gemeld:
                continue
            total = (info or {}).get("total", 0)
            if total < MIN_OBSERVATIES_VOOR_NIEUWE_NAAM_MELDING:
                continue
            try:
                reden = em.beoordeel_naam(event_type)
            except Exception as e:
                if not self._fout_gemeld:
                    self._fout_gemeld = True
                    print(f"[NAAM_ONDERHOUD] beoordeel_naam mislukt "
                          f"(emergence_engine aangepast?): {e}")
                reden = None
            if reden is None:
                continue
            resultaat.append({
                "event_type": event_type,
                "naam": event_type.split(":", 1)[1],
                "reden": reden,
                "total": total,
            })
        resultaat.sort(key=lambda r: (-r["total"], r["event_type"]))
        return resultaat

    def _mag_nu_spreken(self) -> bool:
        cm = self._module("context_manager")
        if cm is None:
            return True  # fail-open
        try:
            return bool(cm.can_interrupt())
        except Exception:
            return True

    def _formuleer(self, namen: List[Dict]) -> str:
        act = [n for n in namen if n["reden"] == "activiteit_whitelist"]
        top = [n for n in namen if n["reden"] == "topic_vertaling"]
        delen = ["Onderhoudsmelding: ik zag nieuwe namen die ik nog niet kan gebruiken."]
        if act:
            lijst = ", ".join(f"{n['naam']} ({n['total']}x)" for n in act)
            delen.append(
                f"Activiteiten die nog niet in INSIGHT_WAARDIGE_ACTIVITEITEN "
                f"staan: {lijst}.")
        if top:
            lijst = ", ".join(f"{n['naam']} ({n['total']}x)" for n in top)
            delen.append(
                f"Onderwerpen zonder vertaling in _topic_naam_labels: {lijst}.")
        delen.append("Wil je ze toevoegen of bewust uitsluiten?")
        return " ".join(delen)

    def check_nieuwe_namen(self) -> Optional[str]:
        """Eén controleronde. Geeft de verstuurde tekst terug, of None."""
        with self._lock:
            nieuw = self.vind_nieuwe_namen()
            print(f"[NAAM_ONDERHOUD] controle: {len(nieuw)} nieuwe naam/namen.")
            if not nieuw:
                return None
            if not self._mag_nu_spreken():
                print("[NAAM_ONDERHOUD] nu niet storen (context_manager) "
                      "-> volgende ronde opnieuw.")
                return None  # niet gemarkeerd -> volgende ronde opnieuw
            batch = nieuw[:MAX_NAMEN_PER_BERICHT]
            tekst = self._formuleer(batch)
            self.event_bus.publish("chat_response", {"text": tekst})
            nu = time.time()
            for n in batch:
                self.gemeld[n["event_type"]] = {
                    "reden": n["reden"], "gemeld_op": nu}
            self._bewaar_state()
            return tekst

    def status_nu(self) -> Dict:
        return {
            "drempel": MIN_OBSERVATIES_VOOR_NIEUWE_NAAM_MELDING,
            "al_gemeld": sorted(self.gemeld.keys()),
            "wachtend": [n["event_type"] for n in self.vind_nieuwe_namen()],
        }

    # ── thread ────────────────────────────────────────
    def _loop(self):
        if self._stop.wait(EERSTE_CONTROLE_NA_SECONDEN):
            return
        while not self._stop.is_set():
            try:
                self.check_nieuwe_namen()
            except Exception:
                pass
            if self._stop.wait(CONTROLE_INTERVAL_SECONDEN):
                return

    def shutdown(self):
        self._stop.set()


def init_module(event_bus, sem=None):
    instance = NaamOnderhoud(event_bus)
    event_bus.modules["naam_onderhoud"] = instance
    return instance