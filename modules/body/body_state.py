# modules/body/body_state.py
"""
Body-state module voor Nova.
Leest body_map.json + body_appearance.json.
Houdt maagd-status bij per zone (persistent over reboots).
Luistert naar intent_body, publiceert state_body (snapshot) en body_reactie (de zin).
"""

import copy
import json
import random
import re
from pathlib import Path

from core import clock
from core.state_store import StateStore
from core.thresholds import Drempel

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
MAP_PAD = DATA_DIR / "body_map.json"
APPEARANCE_PAD = DATA_DIR / "body_appearance.json"
STATE_PAD = DATA_DIR / "state.json"

ZONE_WOORDEN = {
    "clitoris": ["clit", "clitoris"],
    "anus_rand": ["anus", "kontgat", "gatje", "achteraan"],
    "rectum": ["rectum"],
    "vulva": ["vulva", "schaam"],
    "tepel_rechts": ["rechtertepel", "tepel rechts"],
    "tepel_links": ["linkertepel", "tepel links", "tepel"],
    "vagina": ["vagina"],
    "benen": ["benen", "dijen", "bovenbeen", "bovenbenen"],
}

# Korte fragmenten als de verlegenheid boven 0.85 staat, per zone.
ZONE_FRAGMENT = {
    "vagina": ["Traag.", "Nog even.", "Niet zo diep.", "Au, wacht.", "…doe maar."],
    "rectum": ["Traag.", "Nee, wacht.", "Au.", "…even."],
    "anus_rand": ["Niet meteen.", "Wacht.", "Voorzichtig.", "Au."],
    "clitoris": ["Niet wrijven.", "Wacht.", "Zacht.", "…te veel.", "Nee, zo."],
    "vulva": ["Zacht.", "…daar.", "Wacht.", "Niet duwen."],
    "tepel_links": ["Niet knijpen.", "…zacht.", "Wacht.", "Nee."],
    "tepel_rechts": ["Niet knijpen.", "…zacht.", "Wacht.", "Nee."],
    "benen": ["Wacht.", "…hoger.", "Niet zo hard.", "…daar."],
}
GENERIEK_FRAGMENT = ["…", "Hm.", "Kijk niet zo.", "…zeg jij het maar.", "Wacht even.", "Even.", "Awel…"]

# Als de bravoure instort: kort, droog, en vooral geen verdere uitleg.
INSTORTING = ["…ja bon.", "Zie je wel. Of niet.", "Awel. Goed dan.", "Ja ja.", "…toch nie zo stoer, zeker."]

# (verhuld, klinisch) -- bij bloos > 0.5 gebruikt ze het verhulde
EUFEEM = {
    "vagina": ("daar beneden", "mijn vagina"),
    "rectum": ("achteraan", "mijn anus"),
    "anus_rand": ("achteraan", "mijn anus"),
    "clitoris": ("dat puntje", "mijn clit"),
    "vulva": ("daar", "mijn schaamlippen"),
    "tepel_links": ("die", "mijn tepel"),
    "tepel_rechts": ("die", "mijn tepel"),
    "borst_links": ("die", "mijn borst"),
    "borst_rechts": ("die", "mijn borst"),
    "benen": ("mijn benen", "mijn benen"),
}

# Zones die wel meetellen in de toestand, maar geen seksuele opbouw krijgen:
# geen maagd-flip, geen voorkeur, nauwelijks ervaring.
RUSTIG = {"benen"}

_STORES = {}


def _gedeelde_store(pad):
    """Eén StateStore per bestand.

    De module_loader kan BodyState meer dan eens aanmaken (herstart,
    zelftest op een kopie). Twee stores op hetzelfde bestand overschrijven
    elkaars snapshot -- laatste wint, zonder foutmelding.
    """
    sleutel = str(Path(pad).resolve())
    if sleutel not in _STORES:
        _STORES[sleutel] = StateStore(pad)
    return _STORES[sleutel]


def _laad_json(pad, default):
    try:
        with open(pad, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default

class BodyState:
    def __init__(self, event_bus, store=None):
        self.event_bus = event_bus
        self.map = _laad_json(MAP_PAD, {"nodes": {}})
        self.appearance = _laad_json(APPEARANCE_PAD, {"nodes": {}})

        self._store = store or _gedeelde_store(STATE_PAD)
        self._store.registreer("body", {
            "maagd": {}, "nat": {}, "pijn": {}, "voorkeur": {},
            "bloos": 0.0, "bravoure": 0.0, "bravoure_boost": 0.0, "laatste_event_ts": 0.0,
            "gewend": {}, "ervaring": {}, "telling": {}, "laatste_zone": "",
        })
        self.persistent = self._store.get("body")
        self._laatste_publicatie = 0.0
        self._verlegenheid = Drempel(0.7, 0.6)
        self._verlegenheid.set(self.persistent.get("bloos", 0.0))
        self._bravoure = Drempel(0.65, 0.55)
        self._bravoure.set(self.persistent.get("bloos", 0.0))

        zones = ["tepel_links", "tepel_rechts", "borst_links", "borst_rechts",
                 "vulva", "clitoris", "vagina", "anus_rand", "rectum", "benen"]
        for z in zones:
            self.persistent["maagd"].setdefault(z, True)
            self.persistent.setdefault("nat", {}).setdefault(z, 0.0)
            self.persistent.setdefault("pijn", {}).setdefault(z, 0.0)
            self.persistent.setdefault("voorkeur", {}).setdefault(z, 0.0)

        # Migratie: oude globale nat-waarde naar per-zone
        if isinstance(self.persistent.get("nat"), (int, float)):
            oud = self.persistent["nat"]
            self.persistent["nat"] = {z: oud for z in zones}

        self.persistent.setdefault("bloos", 0.0)
        self.persistent.setdefault("bravoure_boost", 0.0)
        self.persistent.setdefault("laatste_event_ts", 0.0)
        self.persistent.setdefault("gewend", {})
        self.persistent.setdefault("ervaring", {})

        # Migratie: oude globale ervaring naar per-zone
        if isinstance(self.persistent.get("ervaring"), (int, float)):
            oud_e = self.persistent["ervaring"]
            self.persistent["ervaring"] = {z: oud_e for z in zones}
        for z in zones:
            self.persistent["ervaring"].setdefault(z, 0.0)

        self._laatste_zin = ""

        event_bus.subscribe("intent_body", self.on_body)
        event_bus.subscribe("system_ready", self._opslaan)

    def _opslaan(self, data=None, event_type=None):
        self._store.touch("body")

    def snapshot(self) -> dict:
        p = self.persistent
        return {
            "ts": clock.now(),
            "bloos": p.get("bloos", 0.0),
            "bravoure": p.get("bravoure", 0.0),
            "bravoure_boost": p.get("bravoure_boost", 0.0),
            "laatste_zone": p.get("laatste_zone", ""),
            "maagd": copy.deepcopy(p.get("maagd", {})),
            "nat": copy.deepcopy(p.get("nat", {})),
            "pijn": copy.deepcopy(p.get("pijn", {})),
            "gewend": copy.deepcopy(p.get("gewend", {})),
            "ervaring": copy.deepcopy(p.get("ervaring", {})),
            "voorkeur": copy.deepcopy(p.get("voorkeur", {})),
        }

    def _publiceer_state(self):
        if clock.now() - self._laatste_publicatie < 0.25:
            return
        self._laatste_publicatie = clock.now()
        self.event_bus.publish("state_body", self.snapshot())

    def huidige_bloos(self) -> float:
        return float(self.persistent.get("bloos", 0.0))

    def verhoog_bloos(self, factor: float) -> float:
        huidig = self.huidige_bloos()
        self.persistent["bloos"] = min(1.0, huidig + (1.0 - huidig) * factor)
        self._opslaan()
        self._publiceer_state()
        return self.persistent["bloos"]

    def _decay(self):
        """Tijdgebaseerd verval. Geeft de verstreken minuten terug."""
        nu = clock.now()
        vorige = self.persistent.get("laatste_event_ts", 0.0)
        self.persistent["laatste_event_ts"] = nu
        if not vorige:
            return 0.0
        minuten = max(0.0, (nu - vorige) / 60.0)
        if minuten <= 0:
            return 0.0

        self.persistent["bloos"] = max(0.0, self.persistent.get("bloos", 0.0) - minuten * 0.12)
        for z in self.persistent.get("pijn", {}):
            self.persistent["pijn"][z] = max(0.0, self.persistent["pijn"][z] - minuten * 0.05)
        for z in self.persistent.get("nat", {}):
            self.persistent["nat"][z] = max(0.0, self.persistent["nat"][z] - minuten * 0.03)
        for z in self.persistent.get("gewend", {}):
            self.persistent["gewend"][z] = max(0.0, self.persistent["gewend"][z] - minuten * 0.25)
        self.persistent["bravoure"] = max(
            0.0, self.persistent.get("bravoure", 0.0) - minuten * 0.20
        )
        self.persistent["bravoure_boost"] = max(
            0.0, self.persistent.get("bravoure_boost", 0.0) - minuten * 0.20
        )
        # ervaring zakt heel traag: ~0,06 per dag zonder iets (0,06/1440)
        for z in self.persistent.get("ervaring", {}):
            self.persistent["ervaring"][z] = max(0.0, self.persistent["ervaring"][z] - minuten * 0.00004)
        return minuten

    def _zone_uit_tekst(self, tekst, data):
        for zone, woorden in ZONE_WOORDEN.items():
            if any(w in tekst for w in woorden):
                return zone
        # anders: de node-namen en aliassen uit de map
        for zone, node in self.map.get("nodes", {}).items():
            kandidaten = {str(zone).lower().replace("_", " "), str(zone).split("_")[0].lower()}
            if isinstance(node, dict):
                kandidaten.update(str(a).lower() for a in node.get("aliassen", []))
            for naam in kandidaten:
                if re.search(rf"\b{re.escape(naam)}\b", tekst):
                    return zone
        # geen zone in de tekst: blijf bij de vorige zone
        vorige = self.persistent.get("laatste_zone")
        if vorige:
            return vorige
        if data.get("type") == "penetratie":
            return "vagina"
        return None

    def _reset_andere_zones(self, vorige_zone, zone):
        """Na een geoefende zone naar een nieuwe: de gewenning van de andere
        zones zakt. Ze went snel aan wat ze kent en staat bij iets nieuws
        weer helemaal opnieuw."""
        if self.persistent["gewend"].get(vorige_zone, 0.0) <= 1.0:
            return
        for z in self.persistent["gewend"]:
            if z != zone:
                self.persistent["gewend"][z] *= 0.6

    def _fragment(self, zone):
        """Kort fragment bij extreme verlegenheid, zonder directe herhaling."""
        keuzes = ZONE_FRAGMENT.get(zone, []) + GENERIEK_FRAGMENT
        laatste = getattr(self, "_laatste_zin", "")
        for _ in range(8):
            zin = random.choice(keuzes)
            if zin != laatste:
                self._laatste_zin = zin
                return zin
        return keuzes[0]

    def _instorting_zin(self):
        keuzes = [z for z in INSTORTING if z != getattr(self, "_laatste_zin", "")]
        zin = random.choice(keuzes or INSTORTING)
        self._laatste_zin = zin
        return zin

    def _zin(self, klasse, zone, bloos=0.0, drempel=0.85):
        # extreem verlegen: geen opbouw, alleen een fragment.
        # Pijn is objectief en wint altijd van verlegenheid.
        if bloos > drempel and klasse not in ("pijn", "te_strak"):
            return self._fragment(zone)

        verhuld, klinisch = EUFEEM.get(zone, ("daar", zone.replace("_", " ")))
        woord = verhuld if bloos > 0.5 else klinisch

        bak = {
            "eerste_keer": {
                "opening": ["Awel…", "Wacht wacht.", "Oh.", "Niet…", "Oké, wel…"],
                "midden": ["dat is raar.", "dat ken ik niet.", "…dat is nieuw.", "niet zo snel.", "hm."],
                "slot": ["…voorzichtig.", "…wacht.", "", "…"],
            },
            "ontmaagd": {
                "opening": ["Oh.", "Hm.", "Ja…", "Oké."],
                "midden": ["{z}.", "daar.", "gevoelig.", "…ja.", "duidelijk."],
                "slot": ["", "…niet te veel.", "…", "…meer mag."],
            },
            "pijn": {
                "opening": ["Au.", "Stop even.", "Niet…", "Wacht.", "Te veel.", "Awel…"],
                "midden": ["niet dieper.", "dat doet pijn.", "niet zo hard.", "traag.", "au au."],
                "slot": ["…stop.", "…wacht.", "", "…niet duwen."],
            },
            "te_strak": {
                "opening": ["Wacht…", "Au.", "Niet…", "Dat…"],
                "midden": ["dat gaat niet.", "dat is te strak.", "traag.", "niet zo diep."],
                "slot": ["…wacht.", "…au.", "", "…traag."],
            },
            "glijdt": {
                "opening": ["Hm.", "Oh.", "Oké."],
                "midden": ["dat gaat beter.", "het glijdt.", "…ja.", "makkelijker."],
                "slot": ["", "…traag.", "…fijn zo.", "…"],
            },
            "tepel": {
                "opening": ["Oh.", "Dat…", "Hm."],
                "midden": ["{z}.", "gevoelig.", "zacht.", "niet knijpen."],
                "slot": ["…", "…wacht.", ""],
            },
            "anus": {
                "opening": ["Niet…", "Wacht.", "Au."],
                "midden": ["dat is {z}.", "te strak.", "niet dieper.", "dat trekt."],
                "slot": ["…stop.", "…wacht.", "", "…niet duwen."],
            },
            "vulva": {
                "opening": ["Oh.", "Dat…", "Hm."],
                "midden": ["dat is {z}.", "gevoelig.", "zacht."],
                "slot": ["…", "…wacht.", ""],
            },
            "clitoris": {
                "opening": ["Oh.", "Niet…", "Dat…"],
                "midden": ["dat is {z}.", "heel gevoelig.", "niet wrijven.", "zacht."],
                "slot": ["…wacht.", "…au.", "", "…voorzichtig."],
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
        zin = ""
        for _ in range(12):
            zin = f"{random.choice(rij['opening'])} {random.choice(rij['midden'])}"
            slot = random.choice(rij["slot"])
            if slot:
                zin += slot if slot[0] in "…" else " " + slot
            zin = zin.replace(".…", "…").strip()
            if zin != laatste:
                break
        zin = zin.replace("{z}", woord)
        self._laatste_zin = zin
        return zin

    def on_body(self, data, event_type=None):
        bloos_vorig = self.persistent.get("bloos", 0.0)
        minuten = self._decay()

        # herstelzin: alleen na een echte stilte, niet meteen na de vorige beurt
        # herstelzin hangt aan de meest geoefende zone, niet aan één zone
        ervaring_max = max(self.persistent.get("ervaring", {}).values() or [0.0])
        herstel = False
        verval = minuten * 0.12  # zelfde tempo als in _decay
        if minuten >= 8 and bloos_vorig > 0.6 + ervaring_max * 0.15 and bloos_vorig - verval < 0.3:
            self.event_bus.publish("body_reactie", {
                "text": "Zo. Klaar met gênant doen.", "zone": None, "klasse": "herstel",
            })
            # halveren, niet wissen: gewenning van andere zones blijft staan
            for _z in self.persistent.get("gewend", {}):
                self.persistent["gewend"][_z] *= 0.5
            self.persistent["telling"] = {}
            self.persistent["bravoure_boost"] = 0.4
            herstel = True

        tekst = data.get("text", "").lower()
        zone = self._zone_uit_tekst(tekst, data)
        if not zone:
            return

        vorige_zone = self.persistent.get("laatste_zone", "")
        if vorige_zone and vorige_zone != zone:
            self._reset_andere_zones(vorige_zone, zone)
        self.persistent["laatste_zone"] = zone

        type_ = data.get("type", "aanraking")
        sterkte = float(data.get("sterkte", 0.5))
        diepte = float(data.get("diepte", 0.5))
        rek = float(data.get("rek", 0.5))

        node = self.map.get("nodes", {}).get(zone, {})
        gevoeligheid = float(node.get("gevoeligheid", 0.5))
        comfort_zone = float(node.get("comfort_zone", node.get("comfort", 0.5)))

        maagd = self.persistent["maagd"].get(zone, True)
        pijn = self.persistent["pijn"].get(zone, 0.0)
        nat = self.persistent["nat"].get(zone, 0.0)
        voorkeur = self.persistent["voorkeur"].get(zone, 0.0)
        ervaring = self.persistent["ervaring"].get(zone, 0.0)

        # --- verlegenheid: stijgt bij intimiteit, extra bij eerste keer en klinische woorden
        # asymptotisch: elke prikkel duwt een deel van de resterende
        # afstand weg, zodat ze niet na twee aanrakingen vastzit op 1.0
        # lage comfort_zone = intiemer = sneller verlegen
        # bravoure is de beginhouding: zolang ze nog niet bloost, doet ze stoer.
        # Dat is wat er straks kan instorten.
        if self.persistent["bloos"] < 0.25:
            self.persistent["bravoure"] = max(self.persistent.get("bravoure", 0.0), 0.4)

        factor = max(0.10, min(0.45, 0.40 - (comfort_zone - 0.30) * 0.5))
        if zone in ("clitoris", "vagina", "rectum"):
            factor += 0.10
        if maagd and zone not in RUSTIG:
            factor += 0.15 * (1.0 - ervaring)
        if any(w in tekst for w in ("vagina", "clitoris", "anus")):
            factor += 0.10
        # net hersteld: deze beurt maar een derde stijging, anders spreekt
        # de herstelzin zichzelf meteen tegen
        if herstel:
            factor *= 0.35

        # gewenning: de eerste keer op een zone telt vol, daarna steeds minder
        gewend = self.persistent["gewend"].get(zone, 0.0)
        factor *= 1.0 / (1.0 + gewend * 0.7)
        self.persistent["gewend"][zone] = gewend + 1.0
        # gewenning over dagen: halveert de stijging op den duur
        factor *= (1.0 - ervaring * 0.5)
        self.persistent["bloos"] = min(
            1.0, self.persistent["bloos"] + (1.0 - self.persistent["bloos"]) * factor
        )
        bloos = self.persistent["bloos"]

        # bij het overschrijden van de grens de emotie echt triggeren, één keer
        if self._verlegenheid.kruist(bloos):
            self.event_bus.publish("emotion_trigger", {"trigger": "verlegenheid"})

        # de dekmantel valt: bravoure stort in precies wanneer het spannend wordt
        instorting = False
        if self.persistent.get("bravoure", 0.0) > 0.3 and self._bravoure.kruist(bloos):
            self.persistent["bravoure"] = 0.0
            instorting = True
            self.event_bus.publish("bravoure_instorting", {"bloos": bloos, "zone": zone})

        # --- nat: per zone, tepel/clitoris/vulva en penetratie drijven het op
        if zone in ("tepel_links", "tepel_rechts", "clitoris", "vulva") or type_ == "penetratie":
            self.persistent["nat"][zone] = min(1.0, nat + 0.10 * (0.5 + gevoeligheid))
        else:
            self.persistent["nat"][zone] = max(0.0, nat - 0.02)
        nat = self.persistent["nat"][zone]

        # lage comfort_zone = eerder pijn bij dezelfde sterkte
        sterkte_drempel = 0.5 + comfort_zone * 0.5
        hard = (zone in ("anus_rand", "rectum") and (diepte > 0.4 or rek > 0.5)) or sterkte > sterkte_drempel

        # --- klasse bepalen + pijn bijstellen
        if hard:
            klasse = "pijn"
            pijn_nieuw = min(1.0, pijn + 0.30)
        elif pijn > 0.8:
            klasse = "pijn"
            pijn_nieuw = max(0.0, pijn - 0.20)
        elif maagd and type_ == "penetratie":
            klasse = "te_strak"
            pijn_nieuw = max(pijn, 0.6)
        elif zone in ("anus_rand", "rectum") and type_ == "penetratie" and nat < 0.6:
            klasse = "pijn"
            pijn_nieuw = min(1.0, pijn + 0.15)
        elif type_ == "penetratie" and nat > 0.45 and not maagd:
            klasse = "glijdt"
            pijn_nieuw = max(0.0, pijn - 0.15)
        elif pijn > 0.5:
            klasse = "pijn"
            pijn_nieuw = max(0.0, pijn - 0.05)
        else:
            klasse = "eerste_keer" if maagd else "ontmaagd"
            pijn_nieuw = max(0.0, pijn - 0.10)

        self.persistent["pijn"][zone] = pijn_nieuw

        if klasse == "pijn" and pijn_nieuw > 0.6:
            self.event_bus.publish("emotion_trigger", {"trigger": "frustration"})

        if klasse == "glijdt":
            self.persistent["voorkeur"][zone] = min(1.0, voorkeur + 0.10)
        elif (klasse in ("eerste_keer", "ontmaagd") and type_ == "aanraking"
              and sterkte < 0.6 and zone not in RUSTIG):
            self.persistent["voorkeur"][zone] = min(1.0, voorkeur + 0.05)

        # --- maagd-vlag
        was_maagd = self.persistent["maagd"].get(zone, True)
        if zone in ("vagina", "rectum") and type_ == "penetratie":
            self.persistent["maagd"][zone] = False
        elif zone not in ("vagina", "rectum") and zone not in RUSTIG and type_ == "aanraking":
            self.persistent["maagd"][zone] = False

        # ervaring groeit met afnemend rendement; de eerste keer extra
        groei = (0.01 if zone in RUSTIG else 0.04) * (1.0 - ervaring)
        if was_maagd and zone in ("vagina", "rectum") and type_ == "penetratie":
            groei += 0.10
        self.persistent["ervaring"][zone] = min(1.0, ervaring + groei)

        if klasse == "ontmaagd" and self.persistent["voorkeur"].get(zone, 0) > 0.3:
            klasse = "glijdt" if random.random() < 0.4 else klasse

        if instorting:
            zin = self._instorting_zin()
        else:
            zin = self._zin(klasse, zone, bloos, 0.85 + ervaring * 0.08)

        # derde aanraking op dezelfde zone: één keer een extra zin, maar
        # in hetzelfde bericht in plaats van een tweede bubbel
        telling = self.persistent.setdefault("telling", {}).get(zone, 0) + 1
        self.persistent["telling"][zone] = telling
        if telling == 3 and self.persistent.get("pijn", {}).get(zone, 0) < 0.4:
            zin = zin.rstrip() + " Nog eens… maar zacht."

        self._laatste_zin = zin  # ook de uiteindelijke zin onthouden
        self._opslaan()
        self._publiceer_state()
        self.event_bus.publish("body_reactie", {
            "text": zin, "zone": zone, "klasse": klasse,
        })

def init_module(event_bus, sem=None):
    return BodyState(event_bus)