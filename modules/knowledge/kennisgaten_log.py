# modules/knowledge/kennisgaten_log.py
"""
Kennisgaten-logboek (punt 72a, 4 november 2026).

PROBLEEM
    Als Nova een vraag wel begrijpt maar het antwoord niet weet ("Ik ken geen
    oorzaken van 'modder'"), blijft daar nergens een spoor van. Zinnen die ze
    NIET begrijpt worden al gelogd (data/unmatched_intents.jsonl), maar deze
    kennisgaten niet. Zonder die lijst weten we niet welke woorden Kevin echt
    vraagt en dus welke kennis in concepts.json het eerst moet komen.

WAT DEZE MODULE DOET
    Luistert (zonder iets te veranderen) naar twee dingen:
      - "raw_user_message": wat Kevin zelf typt (vlak voor de routing);
      - "layer4_response" en "chat_response": wat Nova antwoordt.
    Past het antwoord bij een "ik weet het niet"-zin (zie _PATRONEN), dan komt er
    EEN regel bij in data/kennisgaten.jsonl:
      {"tijd": "...", "vraag": "wat veroorzaakt modder", "soort": "oorzaken",
       "woord": "modder", "antwoord": "Ik ken geen oorzaken van 'modder'."}
    Per bericht van Kevin hoogstens een regel (hetzelfde antwoord komt langs
    twee events: layer4_response en daarna chat_response).

    Overzicht bekijken (meest gevraagd bovenaan):
        python tools/kennisgaten_overzicht.py

VEILIGHEID
    - Verandert nooit een antwoord, stuurt zelf geen berichten.
    - Elke fout (schijf vol, kapot bestand) wordt ingeslikt: loggen mag Nova
      nooit laten haperen.
    - Alleen tekst die Kevin zelf typte, niet wat modules onderling versturen.
    - Puur symbolisch: regex op Nova's eigen antwoordzinnen, geen ML.

AUTO-ONTDEKKING
    Staat in modules/knowledge/, dus module_loader.py vindt en start deze module
    zelf via init_module(event_bus, sem). Geen wijziging in module_loader nodig.
"""

import json
import re
from datetime import datetime
from pathlib import Path

# (soort, patroon). Het eerste patroon dat past wint. Groep "woord" is het
# woord waar het over ging.
_PATRONEN = [
    ("synoniemen",
     re.compile(r"ik ken geen synoniemen van '(?P<woord>[^']+)'", re.I)),
    ("tegendeel",
     re.compile(r"ik ken geen tegendeel van '(?P<woord>[^']+)'", re.I)),
    ("oorzaken",
     re.compile(r"ik ken geen oorzaken van '(?P<woord>[^']+)'", re.I)),
    ("gevolgen",
     re.compile(r"ik ken geen gevolgen van '(?P<woord>[^']+)'", re.I)),
    ("eigenschappen",
     re.compile(r"ik ken geen eigenschappen van '(?P<woord>[^']+)'", re.I)),
    ("onderdelen",
     re.compile(r"ik ken geen onderdelen van (?P<woord>[^\s.]+)", re.I)),
    ("relatie",
     re.compile(r"ik ken de relatie '(?P<woord>[^']+)' niet", re.I)),
    ("woord",
     re.compile(r"ik ken '(?P<woord>[^']+)' (?:nog )?niet", re.I)),
    ("wikipedia",
     re.compile(r"ik kon '(?P<woord>[^']+)' niet vinden op wikipedia", re.I)),
]

BESTANDSNAAM = "kennisgaten.jsonl"


def herken_kennisgat(antwoord):
    """
    Geeft (soort, woord) als dit antwoord een 'ik weet het niet' over een woord
    is, anders None. Pure functie, zodat ze los te testen is.
    """
    if not isinstance(antwoord, str) or not antwoord:
        return None
    for soort, patroon in _PATRONEN:
        m = patroon.search(antwoord)
        if m:
            return soort, m.group("woord").strip()
    return None


class KennisgatenLog:
    def __init__(self, event_bus, data_dir=None):
        self.event_bus = event_bus
        if data_dir is None:
            project_root = Path(__file__).resolve().parent.parent.parent
            data_dir = project_root / "data"
        self._pad = Path(data_dir) / BESTANDSNAAM

        self._laatste_vraag = None
        self._al_gelogd = False  # per bericht van Kevin hoogstens een regel

        event_bus.subscribe("raw_user_message", self.on_raw_user_message)
        event_bus.subscribe("layer4_response", self.on_antwoord)
        event_bus.subscribe("chat_response", self.on_antwoord)

    def on_raw_user_message(self, data, event_type=None):
        try:
            self._laatste_vraag = (data or {}).get("text") or None
            self._al_gelogd = False
        except Exception:
            pass

    def on_antwoord(self, data, event_type=None):
        try:
            if self._laatste_vraag is None or self._al_gelogd:
                return
            antwoord = (data or {}).get("text")
            gevonden = herken_kennisgat(antwoord)
            if gevonden is None:
                return
            soort, woord = gevonden
            regel = {
                "tijd": datetime.now().isoformat(timespec="seconds"),
                "vraag": self._laatste_vraag,
                "soort": soort,
                "woord": woord,
                "antwoord": antwoord,
            }
            self._pad.parent.mkdir(parents=True, exist_ok=True)
            with open(self._pad, "a", encoding="utf-8") as f:
                f.write(json.dumps(regel, ensure_ascii=False) + "\n")
            self._al_gelogd = True
        except Exception:
            # Loggen mag Nova nooit laten haperen.
            pass


def init_module(event_bus, sem=None):
    return KennisgatenLog(event_bus)