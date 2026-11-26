"""Enige schrijver van persistente state.

Eén bestand, namespaces per module, schema_version, migraties, atomaire
write en debounce. Geen module schrijft nog zelf JSON.
"""

import atexit
import contextlib
import copy
import json
import os
import threading
from pathlib import Path

from core import clock

SCHEMA_VERSION = 1
DEBOUNCE_S = 2.0


class StateStore:
    def __init__(self, pad, debounce: float = DEBOUNCE_S) -> None:
        self._pad = Path(pad)
        self._lock = threading.RLock()
        self._debounce = float(debounce)
        self._laatste_schrijf = 0.0
        self._dirty = False
        self._data = self._laad()
        atexit.register(self.flush, True)

    # ---------------- laden ----------------
    def _laad(self) -> dict:
        try:
            with open(self._pad, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return {"schema_version": SCHEMA_VERSION, "namespaces": {}}

        versie = int(data.get("schema_version", 0))
        if versie > SCHEMA_VERSION:
            raise ValueError(
                f"state-bestand is versie {versie}, code kent {SCHEMA_VERSION}"
            )
        data["schema_version"] = SCHEMA_VERSION
        data.setdefault("namespaces", {})
        return data

    # ---------------- namespaces ----------------
    def registreer(self, ns: str, defaults: dict, migraties=()) -> None:
        """Registreer een namespace.

        migraties: reeks (van_versie, functie(data) -> data). Wordt enkel
        toegepast als de opgeslagen versie exact overeenkomt met van_versie.
        """
        with self._lock:
            ruw = self._data["namespaces"].setdefault(ns, {})
            versie = int(ruw.get("_versie", 1))
            data = dict(ruw.get("data", {}))

            for van, fn in sorted(migraties):
                if versie == van:
                    data = fn(data)
                    versie = van + 1

            for sleutel, waarde in defaults.items():
                data.setdefault(sleutel, copy.deepcopy(waarde))

            self._data["namespaces"][ns] = {"_versie": versie, "data": data}
            self._markeer()

    def get(self, ns: str) -> dict:
        with self._lock:
            return self._data["namespaces"][ns]["data"]

    @contextlib.contextmanager
    def muteer(self, ns: str):
        with self._lock:
            data = self.get(ns)
            yield data
            self._markeer()

    def snapshot(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._data["namespaces"])

    def touch(self, ns: str) -> None:
        """Markeer gewijzigd zonder de dict via muteer() te openen."""
        with self._lock:
            self._markeer()

    # ---------------- schrijven ----------------
    def _markeer(self) -> None:
        self._dirty = True
        self.flush()

    def flush(self, force: bool = False) -> None:
        with self._lock:
            if not force and not self._dirty:
                return
            if not force and clock.now() - self._laatste_schrijf < self._debounce:
                return

            tmp = self._pad.with_name(self._pad.name + ".tmp")
            self._pad.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self._pad)

            self._laatste_schrijf = clock.now()
            self._dirty = False