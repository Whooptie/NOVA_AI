# modules/chat/brugs_filter.py
#
# Brugse stijl-laag: zet Nova's (al afgewerkte) antwoordtekst om naar een
# lichte West-Vlaamse/Brugse kleur ("da's nie waar" i.p.v. "dat is niet waar").
#
# Puur symbolisch: woordvervanging via een JSON-woordenlijst
# (identity/expression/brugs_regels.json) + af en toe een brutale opener
# of slotwoord via random.choice. Geen ML, geen generatie. Het is GEEN
# echt dialect: het blijft losse woordkleur.
#
# De filter kent de inhoud niet en verandert nooit wat Nova WEET, enkel
# hoe het klinkt. Hij blijft daarom van tekst tussen aanhalingstekens
# ("..." of '...'), `code`, {plaatshouders}, URL's en getallen af.
#
# Aan/uit: standaard UIT. Debug-commando's "brugs aan" / "brugs uit" /
# "brugs status" (modules/debug/debug_commands.py). De stand wordt bewaard
# in data/brugs_modus.json en overleeft een /reboot.
#
# Auto-discovery: net als de andere modules heeft dit bestand een
# init_module(); het registreert zichzelf als event_bus.modules["brugs_filter"],
# waar expression_injector.py hem vandaan haalt. Ontbreekt of faalt hij,
# dan blijft de tekst gewoon ongewijzigd.

import json
import os
import random
import re

_BASIS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_BASIS, "..", ".."))
REGELS_PAD = os.path.join(_ROOT, "identity", "expression", "brugs_regels.json")
STATE_PAD = os.path.join(_ROOT, "data", "brugs_modus.json")
SJABLONEN_PAD = os.path.join(_ROOT, "identity", "expression", "brugs_sjablonen.json")

# Stukken tekst die NOOIT aangepast worden. Een enkel aanhalingsteken telt
# enkel als begin/einde van een citaat als het niet middenin een woord staat
# (zo blijft een apostrof zoals in "da's" buiten schot).
_BESCHERMD = re.compile(
    r"(\"[^\"\n]*\""
    r"|(?<!\w)'[^'\n]+'(?!\w)"
    r"|`[^`\n]*`"
    r"|\{[^}\n]*\}"
    r"|⟦[^⟧\n]*⟧"
    r"|https?://\S+"
    r"|www\.\S+)"
)


class BrugsFilter:
    def __init__(self, event_bus=None, bewaar=True, regels_pad=None, state_pad=None,
                 sjablonen_pad=None):
        self.event_bus = event_bus
        self.bewaar = bewaar
        self.regels_pad = regels_pad or REGELS_PAD
        self.state_pad = state_pad or STATE_PAD
        self.sjablonen_pad = sjablonen_pad or SJABLONEN_PAD
        self.regels = self._laad_regels()
        self.sjablonen = self._laad_sjablonen()
        self.aan = self._laad_modus()
        self._patroon = self._bouw_patroon()

    # ---------------------------------------------------------
    # Laden / opslaan
    # ---------------------------------------------------------
    def _laad_regels(self) -> dict:
        try:
            with open(self.regels_pad, "r", encoding="utf-8") as f:
                regels = json.load(f)
            if isinstance(regels, dict):
                return regels
        except Exception:
            pass
        return {}

    def _laad_sjablonen(self) -> dict:
        try:
            with open(self.sjablonen_pad, "r", encoding="utf-8") as f:
                sjablonen = json.load(f)
            if isinstance(sjablonen, dict):
                return sjablonen
        except Exception:
            pass
        return {}

    def varianten(self, sjabloon_naam: str):
        """
        Brutale Brugse varianten van een vast sjabloon (identity/expression/
        brugs_sjablonen.json), of None als de modus UIT staat of er voor dit
        sjabloon geen varianten zijn. De aanroeper valt dan gewoon terug op
        zijn eigen gewone zinnen.
        """
        if not self.aan:
            return None
        lijst = self.sjablonen.get(sjabloon_naam)
        if isinstance(lijst, list) and lijst and all(isinstance(z, str) for z in lijst):
            return list(lijst)
        return None

    def kies(self, gewone_varianten, sjabloon_naam: str):
        """
        Centrale keuze: de Brugse varianten onder dezelfde naam als de modus
        aan staat en ze bestaan, anders de meegegeven gewone lijst.

        Geeft altijd een (lijst, naam)-tuple terug. Bij Brugs komt er "_brugs"
        achter de naam, zodat de leerstatistieken van gewoon en Brugs apart
        blijven (zie variant_kiezer.kies_variant). De gewone lijst wordt hier
        enkel doorgegeven; deze klasse kent de inhoud van de sjablonen niet.
        """
        try:
            brugse = self.varianten(sjabloon_naam)
        except Exception:
            brugse = None
        if brugse:
            return brugse, sjabloon_naam + "_brugs"
        return gewone_varianten, sjabloon_naam

    def onderdelen(self, sjabloon_naam: str):
        """
        Voor sjablonen die uit losse delen bestaan (opening/midden/afsluiting):
        een dict {"opening": [...], "midden": [...], "afsluiting": [...]}, of None
        als de modus UIT staat of er geen (volledige) Brugse versie is.
        """
        if not self.aan:
            return None
        delen = self.sjablonen.get(sjabloon_naam)
        if not isinstance(delen, dict) or not delen:
            return None
        for lijst in delen.values():
            if not (isinstance(lijst, list) and lijst and all(isinstance(z, str) for z in lijst)):
                return None
        return {k: list(v) for k, v in delen.items()}

    def _laad_modus(self) -> bool:
        if not self.bewaar:
            return False
        try:
            with open(self.state_pad, "r", encoding="utf-8") as f:
                return bool(json.load(f).get("aan", False))
        except Exception:
            return False

    def zet_modus(self, aan: bool) -> None:
        self.aan = bool(aan)
        if not self.bewaar:
            return
        try:
            os.makedirs(os.path.dirname(self.state_pad), exist_ok=True)
            with open(self.state_pad, "w", encoding="utf-8") as f:
                json.dump({"aan": self.aan}, f)
        except Exception:
            pass  # best effort: de stand in het geheugen blijft gewoon gelden

    def _bouw_patroon(self):
        woorden = self.regels.get("woorden") or {}
        if not woorden:
            return None
        # Langste eerst, zodat een lang woord niet door een korter deel wordt weggevangen.
        sleutels = sorted(woorden.keys(), key=len, reverse=True)
        return re.compile(r"\b(" + "|".join(re.escape(k) for k in sleutels) + r")\b",
                          re.IGNORECASE)

    # ---------------------------------------------------------
    # Woordvervanging
    # ---------------------------------------------------------
    def _vervang_woord(self, match) -> str:
        woorden = self.regels.get("woorden") or {}
        origineel = match.group(0)
        nieuw = woorden.get(origineel.lower())
        if nieuw is None:
            return origineel
        if origineel.isupper() and len(origineel) > 1:
            return nieuw.upper()
        if origineel[0].isupper():
            return nieuw[0].upper() + nieuw[1:]
        return nieuw

    def _vervang_woorden(self, tekst: str) -> str:
        if self._patroon is None:
            return tekst
        delen = _BESCHERMD.split(tekst)
        # re.split met 1 capture-groep: oneven indexen zijn de beschermde stukken
        for i in range(0, len(delen), 2):
            delen[i] = self._patroon.sub(self._vervang_woord, delen[i])
        return "".join(delen)

    # ---------------------------------------------------------
    # Opener / slotwoord (brutale tussenwerpsels)
    # ---------------------------------------------------------
    def _voeg_opener_toe(self, tekst: str) -> str:
        openers = self.regels.get("openers") or []
        kans = float(self.regels.get("opener_kans", 0.0))
        max_len = int(self.regels.get("opener_max_tekenlengte", 140))
        if not openers or len(tekst) > max_len or "\n" in tekst:
            return tekst
        if random.random() >= kans:
            return tekst
        if not tekst or not tekst[0].isalpha():
            return tekst  # begint met een citaat, gebaar (*...*), emoji, cijfer
        opener = random.choice(openers)
        if tekst.lower().startswith(opener.lower().rstrip(",")):
            return tekst
        eerste_woord = re.split(r"\W", tekst, maxsplit=1)[0]
        namen = self.regels.get("namen_niet_kleinmaken") or []
        if eerste_woord in namen or eerste_woord.isupper():
            rest = tekst
        else:
            rest = tekst[0].lower() + tekst[1:]
        return f"{opener} {rest}"

    def _voeg_slot_toe(self, tekst: str) -> str:
        sloten = self.regels.get("slotwoorden") or []
        kans = float(self.regels.get("slot_kans", 0.0))
        max_len = int(self.regels.get("slot_max_tekenlengte", 80))
        if not sloten or len(tekst) > max_len or "\n" in tekst:
            return tekst
        # Enkel bij één korte zin die op een gewone punt eindigt.
        if not tekst.endswith(".") or tekst.endswith("..") or tekst[:-1].count(".") > 0:
            return tekst
        if random.random() >= kans:
            return tekst
        return tekst[:-1] + random.choice(sloten)

    # ---------------------------------------------------------
    # Publieke ingang
    # ---------------------------------------------------------
    def pas_toe(self, tekst: str, response_style: str = "normaal") -> str:
        """Geeft de Brugse versie van `tekst`; bij UIT of een fout de originele tekst."""
        if not self.aan or not tekst or not isinstance(tekst, str):
            return tekst
        try:
            nieuw = self._vervang_woorden(tekst)
            # Bij "kort" (Kevin is met iets anders bezig) enkel woordkleur, geen extra zinnen.
            if response_style != "kort":
                nieuw = self._voeg_opener_toe(nieuw)
                nieuw = self._voeg_slot_toe(nieuw)
            return nieuw
        except Exception:
            return tekst


def init_module(event_bus, semantic_module=None):
    instance = BrugsFilter(event_bus)
    if hasattr(event_bus, "register_module"):
        event_bus.register_module("brugs_filter", instance)
    event_bus.publish("module_loaded", {"name": "brugs_filter"})
    return instance