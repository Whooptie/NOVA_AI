# modules/knowledge/contradiction_checker.py
"""
Contradiction Checker — de ontbrekende aanroeper voor
semantic.py's find_contradictions() (punt 2, 6 augustus 2026).

find_contradictions() bestond al langer en werkt (checkt of een woord
via is_a-relaties tegelijk tot 2+ onderling onmogelijke categorieën
behoort, bv. tegelijk "dier" en "meubel") -- maar werd nergens
aangeroepen. Deze module is dat ontbrekende stuk: een periodieke
achtergrondcheck (zelfde patroon als weather.py/emergence_engine.py
in main.py's achtergrond_loop()) die zelf over de kennisgraaf loopt,
gevonden tegenstrijdigheden verzamelt, en Kevin er proactief over
aanspreekt via layer4_response -- met een concreet 'weerleg:'-voorstel
per conflict, zodat hij het meteen kan oplossen (zie punt 1,
verwijderpad).

Puur symbolisch: geen ML, geen generatie -- roept enkel bestaande,
al-geteste reasoning-code aan en formatteert het resultaat.
"""

import json
from datetime import datetime

from modules.paths import get_project_root


class ContradictionChecker:

    STATE_BESTAND = "data/contradiction_state.json"

    def __init__(self, event_bus, semantic_module=None):
        self.event_bus = event_bus
        self.semantic = semantic_module
        self.project_root = get_project_root(__file__)
        self.state_pad = self.project_root / self.STATE_BESTAND
        # Spam-preventie: onthoudt WELKE conflicten al eens gemeld
        # zijn (zodat een al-gemeld, nog niet opgelost conflict niet
        # elke cyclus opnieuw verschijnt). Sleutel is een stabiele
        # string per conflict (woord + gesorteerde conflict-lijst),
        # zodat dezelfde botsing altijd dezelfde sleutel geeft
        # ongeacht de volgorde waarin de is_a-relaties zijn opgeslagen.
        self._al_gemelde_conflicten = self._laad_state()

        print("[ContradictionChecker] module geladen")

    # ------------------------------------------------------------------
    def _laad_state(self):
        if self.state_pad.exists():
            try:
                with open(self.state_pad, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return set(data.get("al_gemeld", []))
            except (json.JSONDecodeError, OSError):
                return set()
        return set()

    def _sla_state_op(self):
        self.state_pad.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.state_pad, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "al_gemeld": sorted(self._al_gemelde_conflicten),
                        "laatst_bijgewerkt": datetime.utcnow().isoformat(),
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except OSError:
            pass

    def _conflict_sleutel(self, contradiction: dict) -> str:
        """
        Bouwt een stabiele, herhaalbare sleutel voor een gevonden
        conflict, zodat dezelfde botsing (ongeacht volgorde van de
        conflict-lijst) altijd dezelfde sleutel oplevert.
        """
        woord = contradiction.get("word", "")
        conflict = sorted(contradiction.get("conflict", []))
        return f"{woord}::{'|'.join(conflict)}"

    # ------------------------------------------------------------------
    def alle_contradicties_nu(self) -> list[dict]:
        """
        Geeft ALLE huidige conflicten terug, ongeacht of ze al eerder
        gemeld zijn -- wijzigt de spam-preventie-state NIET. Puur
        bedoeld voor het 'contradicties' debug-commando, zodat Kevin
        altijd een eerlijk, volledig antwoord krijgt i.p.v. "niets
        nieuws" als een conflict al eerder gemeld was maar nog niet
        opgelost is.
        """
        if not self.semantic:
            return []

        resultaat = []
        for woord in self.semantic.store.concepts.keys():
            try:
                gevonden = self.semantic.find_contradictions(woord)
            except Exception:
                continue
            resultaat.extend(gevonden)
        return resultaat

    # ------------------------------------------------------------------
    # Kernmethode -- wordt aangeroepen vanuit main.py's achtergrond_loop(),
    # zelfde patroon als weather.check_proactieve_waarschuwing() en
    # emergence.reflect().
    # ------------------------------------------------------------------
    def check_contradictions(self):
        """
        Loopt over ALLE concepten in concepts.json (goedkoop -- pure
        in-memory dict-lookups, geen I/O, geen externe aanroepen per
        concept) en roept find_contradictions() per woord aan.

        Nieuwe (nog niet eerder gemelde) conflicten worden verzameld
        en in EEN samenvattend bericht gemeld via layer4_response, met
        een concreet 'weerleg:'-voorstel per conflict. Conflicten die
        al eerder gemeld zijn worden overgeslagen (spam-preventie) --
        ze verschijnen pas opnieuw als ze ooit via _vergeet_opgeloste_
        conflicten() als opgelost herkend en verwijderd zijn uit de
        state, en zich daarna weer zouden voordoen.
        """
        if not self.semantic:
            return

        alle_woorden = list(self.semantic.store.concepts.keys())

        nieuwe_conflicten = []
        actuele_sleutels = set()

        for woord in alle_woorden:
            try:
                gevonden = self.semantic.find_contradictions(woord)
            except Exception as e:
                print(f"[ContradictionChecker] Fout bij find_contradictions('{woord}'): {e}")
                continue

            for c in gevonden:
                sleutel = self._conflict_sleutel(c)
                actuele_sleutels.add(sleutel)
                if sleutel not in self._al_gemelde_conflicten:
                    nieuwe_conflicten.append(c)

        # Opgeloste conflicten (bv. via 'weerleg:') uit de gemelde-set
        # halen, zodat een HERHAALDE, andere botsing op hetzelfde woord
        # later weer als nieuw zou tellen -- voorkomt dat de state
        # blijft aangroeien met conflicten die al lang niet meer
        # bestaan.
        self._al_gemelde_conflicten &= actuele_sleutels

        if not nieuwe_conflicten:
            self._sla_state_op()
            return

        for c in nieuwe_conflicten:
            self._al_gemelde_conflicten.add(self._conflict_sleutel(c))
        self._sla_state_op()

        tekst = self._bouw_melding(nieuwe_conflicten)
        self.event_bus.publish("layer4_response", {"text": tekst})

    # ------------------------------------------------------------------
    def _bouw_melding(self, conflicten: list) -> str:
        """
        Bouwt EEN samenvattend bericht voor alle nieuw gevonden
        conflicten tegelijk (i.p.v. apart per conflict) -- Kevin's
        voorkeur (6 augustus 2026), rustiger dan meerdere losse
        meldingen na elkaar.
        """
        if len(conflicten) == 1:
            c = conflicten[0]
            woord = c["word"]
            a, b = c["conflict"][0], c["conflict"][1]
            return (
                f"Ik zag een tegenstrijdigheid in wat ik weet: "
                f"'{woord}' staat bij mij zowel als '{a}' als '{b}' genoteerd, "
                f"en dat kan niet allebei kloppen. "
                f"Wil je dat ik een van de twee weerleg? "
                f"Typ bv. 'weerleg: {woord} is_a {a}' of 'weerleg: {woord} is_a {b}'."
            )

        regels = [
            f"Ik zag {len(conflicten)} tegenstrijdigheden in wat ik weet:"
        ]
        for i, c in enumerate(conflicten, start=1):
            woord = c["word"]
            a, b = c["conflict"][0], c["conflict"][1]
            regels.append(
                f"  {i}. '{woord}' staat zowel als '{a}' als '{b}' genoteerd "
                f"(bv. 'weerleg: {woord} is_a {a}' om er een van te weerleggen)"
            )
        regels.append("Wil je dat ik dit voor je oplos, of los je het liever zelf op met 'weerleg: ...'?")
        return "\n".join(regels)


def init_module(event_bus, semantic_module=None):
    checker = ContradictionChecker(event_bus, semantic_module)
    event_bus.publish("module_loaded", {"name": "contradiction_checker"})
    return checker