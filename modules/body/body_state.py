# modules/body/body_state.py
"""
Body-state module voor Nova.
Leest body_map.json + body_appearance.json.
Houdt maagd-status bij per zone (persistent over reboots).
Luistert naar intent_body en geeft een zin terug via layer4_response.
"""

import json
import random
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
MAP_PAD = DATA_DIR / "body_map.json"
APPEARANCE_PAD = DATA_DIR / "body_appearance.json"
STATE_PAD = DATA_DIR / "body_persistent.json"  # maagd + voorkeur, blijft over reboot

def _laad_json(pad, default):
    try:
        with open(pad, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default

def _schrijf_json(pad, data):
    pad.parent.mkdir(parents=True, exist_ok=True)
    with open(pad, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class BodyState:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.map = _laad_json(MAP_PAD, {"nodes": {}})
        self.appearance = _laad_json(APPEARANCE_PAD, {"nodes": {}})
        self.persistent = _laad_json(STATE_PAD, {"maagd": {}, "voorkeur": {}})

        # Init maagd-vlaggen als ze nog niet bestaan
        zones = ["tepel_links", "tepel_rechts", "borst_links", "borst_rechts",
                 "vulva", "clitoris", "vagina", "anus_rand", "rectum"]
        for z in zones:
            self.persistent["maagd"].setdefault(z, True)

        self.persistent.setdefault("nat", 0.0)
        self._laatste_zin = ""

        event_bus.subscribe("intent_body", self.on_body)
        event_bus.subscribe("system_ready", self._opslaan)  # save bij shutdown-achtige momenten

    def _opslaan(self, data=None, event_type=None):
        _schrijf_json(STATE_PAD, self.persistent)

    def _zin(self, klasse, zone):
        bak = {
            "eerste_keer": {
                "opening": ["Oh…", "Wacht…", "Hmm…", "Niet zo…", "Voorzichtig…"],
                "midden": ["dat is nieuw.", "niet zo snel.", "wacht even.", "dat ken ik niet.", "langzaam."],
                "slot": ["…voorzichtig.", "…niet duwen.", "…", "…wacht.", "…"]
            },
            "ontmaagd": {
                "opening": ["Ik voel het.", "Dat is…", "Hmm.", "Oké…", "Ja…"],
                "midden": ["gevoelig.", "zacht, maar ik voel het.", "daar.", "duidelijk.", "fijn, maar intens."],
                "slot": ["", "…niet te veel.", "…", "…meer mag.", "…"]
            },
            "pijn": {
                "opening": ["Au…", "Niet…", "Stop.", "Wacht…", "Te veel."],
                "midden": ["niet dieper.", "dat doet pijn.", "niet zo hard.", "langzaam.", "dat is te veel."],
                "slot": ["…stop.", "…wacht.", "…", "…niet duwen.", "…"]
            },
            "te_strak": {
                "opening": ["Wacht…", "Au…", "Niet…", "Voorzichtig…", "Dat…"],
                "midden": ["dat is te strak.", "dat gaat niet zomaar.", "ik ben nog niet open.", "dat trekt te veel.", "niet zo diep."],
                "slot": ["…langzaam.", "…wacht.", "…", "…niet duwen.", "…"]
            },
            "glijdt": {
                "opening": ["Hmm…", "Oh…", "Ja…", "Dat…", "Oké…"],
                "midden": ["het glijdt.", "dat gaat makkelijker.", "ik voel het glijden.", "niet meer zo strak.", "het beweegt."],
                "slot": ["", "…langzaam.", "…", "…fijn zo.", "…"]
            },
            "tepel": {
                "opening": ["Oh…", "Dat…", "Hmm…", "Voorzichtig…", "Ja…"],
                "midden": ["dat is gevoelig.", "mijn tepel.", "niet zo hard.", "dat prikkelt.", "zacht."],
                "slot": ["…", "…wacht.", "", "…niet knijpen.", "…"]
            },
            "anus": {
                "opening": ["Niet…", "Wacht…", "Au…", "Voorzichtig…", "Dat…"],
                "midden": ["niet dieper.", "dat is te strak.", "mijn kont.", "niet zo hard.", "dat trekt."],
                "slot": ["…stop.", "…wacht.", "…", "…niet duwen.", "…"]
            },
            "vulva": {
                "opening": ["Oh…", "Dat…", "Hmm…", "Voorzichtig…", "Ja…"],
                "midden": ["mijn schaamlippen.", "dat is gevoelig.", "zacht.", "niet zo hard.", "daar."],
                "slot": ["…", "…wacht.", "", "…voorzichtig.", "…"]
            },
            "clitoris": {
                "opening": ["Oh…", "Niet…", "Hmm…", "Voorzichtig…", "Dat…"],
                "midden": ["mijn clit.", "dat is heel gevoelig.", "niet zo hard.", "dat prikkelt.", "zacht."],
                "slot": ["…wacht.", "…niet wrijven.", "…", "…voorzichtig.", "…"]
            },
        }
        # zone-specifiek overschrijft als het past
        if zone in ("tepel_links", "tepel_rechts") and klasse in ("eerste_keer", "ontmaagd"):
            klasse = "tepel"
        elif zone in ("anus_rand", "rectum") and klasse in ("pijn", "te_strak"):
            klasse = "anus"
        elif zone == "vulva" and klasse in ("eerste_keer", "ontmaagd"):
            klasse = "vulva"
        elif zone == "clitoris" and klasse in ("eerste_keer", "ontmaagd"):
            klasse = "clitoris"

        rij = bak.get(klasse, bak["ontmaagd"])
        laatste = getattr(self, "_laatste_zin", "")
        for _ in range(5):
            zin = (random.choice(rij["opening"]) + " " + random.choice(rij["midden"]) + random.choice(rij["slot"])).strip()
            if zin != laatste:
                break
        self._laatste_zin = zin
        return zin

    def on_body(self, data, event_type=None):
        tekst = data.get("text", "").lower()
        if "tepel" in tekst:
            zone = "tepel_links"
        elif any(w in tekst for w in ["clit", "clitoris"]):
            zone = "clitoris"
        elif any(w in tekst for w in ["anus", "kontgat", "gatje"]):
            zone = "anus_rand"
        elif any(w in tekst for w in ["vulva", "schaam"]):
            zone = "vulva"
        else:
            zone = "vagina" if data.get("type") == "penetratie" else None

        type_ = data.get("type", "aanraking")
        sterkte = float(data.get("sterkte", 0.5))
        diepte = float(data.get("diepte", 0.5))
        rek = float(data.get("rek", 0.5))

        if not zone:
            return

        if zone in ("tepel_links", "clitoris") and type_ == "aanraking":
            self.persistent["nat"] = min(1.0, self.persistent.get("nat", 0) + 0.08)
        else:
            self.persistent["nat"] = max(0.0, self.persistent.get("nat", 0) - 0.02)

        maagd = self.persistent["maagd"].get(zone, True)
        pijn_vorige = self.persistent.get("pijn", {}).get(zone, 0)
        nat = self.persistent.get("nat", 0)
        voorkeur = self.persistent.setdefault("voorkeur", {}).get(zone, 0)

        if pijn_vorige > 0.8:
            self.event_bus.publish("layer4_response", {"text": "Stop. Niet meer."})
            return

        if (zone in ("anus_rand", "rectum") and (diepte > 0.4 or rek > 0.5)) or sterkte > 0.8:
            klasse = "pijn"
            self.persistent.setdefault("pijn", {})[zone] = min(1.0, pijn_vorige + 0.3)
        elif maagd and type_ == "penetratie":
            klasse = "te_strak"
            self.persistent.setdefault("pijn", {})[zone] = 0.6
        elif zone in ("anus_rand", "rectum") and type_ == "penetratie" and nat < 0.6:
            klasse = "pijn"
            self.persistent.setdefault("pijn", {})[zone] = min(1.0, pijn_vorige + 0.2)
        elif type_ == "penetratie" and nat > 0.45 and not maagd:
            klasse = "glijdt"
            self.persistent.setdefault("pijn", {})[zone] = max(0, pijn_vorige - 0.1)
            self.persistent["voorkeur"][zone] = min(1.0, voorkeur + 0.1)
        elif pijn_vorige > 0.5:
            klasse = "pijn"
        else:
            klasse = "eerste_keer" if maagd else "ontmaagd"
            self.persistent.setdefault("pijn", {})[zone] = max(0, pijn_vorige - 0.1)
            if type_ == "aanraking" and sterkte < 0.6:
                self.persistent["voorkeur"][zone] = min(1.0, voorkeur + 0.05)

        if zone in ("vagina", "rectum") and type_ == "penetratie":
            self.persistent["maagd"][zone] = False
        elif zone not in ("vagina", "rectum") and type_ == "aanraking":
            self.persistent["maagd"][zone] = False

        # voorkeur maakt "ontmaagd" iets vaker fijn
        if klasse == "ontmaagd" and self.persistent["voorkeur"].get(zone, 0) > 0.3:
            klasse = "glijdt" if random.random() < 0.4 else klasse

        zin = self._zin(klasse, zone)
        self._opslaan()
        self.event_bus.publish("layer4_response", {"text": zin})

        telling = self.persistent.setdefault("telling", {}).get(zone, 0) + 1
        self.persistent["telling"][zone] = telling
        if telling == 3 and self.persistent.get("pijn", {}).get(zone, 0) < 0.4:
            self.event_bus.publish("layer4_response", {"text": "Nog eens… maar zacht."})

def init_module(event_bus, sem=None):
    return BodyState(event_bus)