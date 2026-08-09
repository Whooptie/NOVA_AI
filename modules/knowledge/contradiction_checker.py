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
    def _is_part_of_cirkel(self, c: dict) -> bool:
        """
        Onderscheidt een part_of-cirkelconflict (idee #3 uit
        reasoning_engine_ideeen_roadmap.md, 8 augustus 2026) van een
        gewoon is_a-conflict, puur op basis van de vorm van 'conflict':
        bij een part_of-cirkel komt 'word' zelf altijd terug voor in
        zijn eigen conflict-lijst (zie find_contradictions() in
        semantic.py, sectie 2 -- conflict is daar altijd [doel, word]).
        Bij een is_a-conflict staat 'word' zelf NOOIT in conflict
        (dat zijn enkel de botsende ouder-categorieën).
        """
        return c.get("word") in c.get("conflict", [])

    def _weerleg_type_voor(self, c: dict) -> str:
        """Geeft 'part_of' of 'is_a' terug, voor de juiste weerleg:-suggestie."""
        return "part_of" if self._is_part_of_cirkel(c) else "is_a"

    def _bouw_melding_regel(self, c: dict) -> tuple[str, str]:
        """
        Bouwt de kernzin + de weerleg-suggestie voor 1 conflict, met
        de juiste formulering en het juiste relatietype al naargelang
        het een is_a-conflict of een part_of-cirkel is. Geeft
        (kernzin, weerleg_suggestie) terug, telkens ZONDER leidende
        opsommingstekens -- dat voegt de aanroeper toe.
        """
        woord = c["word"]
        rel_type = self._weerleg_type_voor(c)

        if self._is_part_of_cirkel(c):
            doel = c["conflict"][0]
            kernzin = f"'{woord}' zit zowel in '{doel}' als (via een omweg) andersom"
            suggestie = f"'weerleg: {woord} {rel_type} {doel}'"
        else:
            a, b = c["conflict"][0], c["conflict"][1]
            kernzin = f"'{woord}' staat bij mij zowel als '{a}' als '{b}' genoteerd"
            suggestie = f"'weerleg: {woord} {rel_type} {a}' of 'weerleg: {woord} {rel_type} {b}'"

        return kernzin, suggestie

    def _bouw_melding(self, conflicten: list) -> str:
        """
        Bouwt EEN samenvattend bericht voor alle nieuw gevonden
        conflicten tegelijk (i.p.v. apart per conflict) -- Kevin's
        voorkeur (6 augustus 2026), rustiger dan meerdere losse
        meldingen na elkaar.

        Sinds idee #3 (8 augustus 2026): onderscheidt is_a-conflicten
        van part_of-cirkels via _bouw_melding_regel(), zodat de
        weerleg:-suggestie altijd het JUISTE relatietype gebruikt --
        voorheen stond hier altijd hardcoded 'is_a', ook bij een
        part_of-cirkel, wat een niet-werkende suggestie opleverde.
        """
        if len(conflicten) == 1:
            c = conflicten[0]
            kernzin, suggestie = self._bouw_melding_regel(c)
            return (
                f"Ik zag een tegenstrijdigheid in wat ik weet: "
                f"{kernzin}, en dat kan niet allebei kloppen. "
                f"Wil je dat ik dit weerleg? Typ bv. {suggestie}."
            )

        regels = [
            f"Ik zag {len(conflicten)} tegenstrijdigheden in wat ik weet:"
        ]
        for i, c in enumerate(conflicten, start=1):
            kernzin, suggestie = self._bouw_melding_regel(c)
            regels.append(f"  {i}. {kernzin} (bv. {suggestie} om dit te weerleggen)")
        regels.append("Wil je dat ik dit voor je oplos, of los je het liever zelf op met 'weerleg: ...'?")
        return "\n".join(regels)


def init_module(event_bus, semantic_module=None):
    checker = ContradictionChecker(event_bus, semantic_module)
    event_bus.publish("module_loaded", {"name": "contradiction_checker"})
    return checker