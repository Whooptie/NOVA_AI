# core/interruption_tracker.py

"""
Activity-Aware Interaction: Interruption Tracker

Leert per activiteit een confidence-score op: hoe vaak stond Kevin
toe dat Nova hem onderbrak tijdens deze activiteit, versus hoe vaak
weigerde hij? Dit is PURE STATISTIEK, zelfde familie als Layer 1 (PMI)
en Layer 2 (frequentie/confidence) -- geen ML, geen interpretatie van
TOON of motivatie. Nova mag weten DAT een patroon bestaat, nooit WAAROM
(zie interruption_learning_roadmap.md, sectie "Eerlijkheid").

Dit bestand houdt zelf GEEN tijd bij van "welke activiteit loopt nu"
-- dat is de taak van session_watcher.py (huidig-moment-state). Dit
bestand beantwoordt uitsluitend: "hoe vaak was storen bij activiteit
X in het VERLEDEN oké?"

Bewust plat JSON-bestand (interruption_patterns.json), zelfde
filosofie als word_associations.json en patterns_layer2.json -- geen
SQLite nodig, dit groeit traag en simpel.
"""

import json
from pathlib import Path
from datetime import datetime


class InterruptionTracker:
    """
    Houdt per activiteit bij: hoeveel keer werd storen toegestaan,
    hoeveel keer geweigerd, en de daaruit berekende confidence-score.
    """

    # Vanaf hoeveel observaties vinden we een confidence-score
    # betrouwbaar genoeg om erop te vertrouwen? Met te weinig data
    # zou zelfs 1x "ja" al confidence 1.0 geven, wat niks zegt.
    MIN_OBSERVATIES = 5

    def __init__(self, event_bus=None):
        self.event_bus = event_bus

        # structuur per activiteit:
        # {
        #   "totaal_pogingen": int,
        #   "aantal_toegestaan": int,
        #   "confidence": float,
        #   "laatst_bijgewerkt": str (ISO-tijdstip)
        # }
        self.patterns = {}

        # Portable pad, zelfde principe als memory.py/pattern_matcher.py:
        # nooit hardcoded Windows-pad, altijd relatief t.o.v. dit bestand.
        self.save_path = Path(__file__).resolve().parent.parent / "data" / "interruption_patterns.json"

        self.load_from_disk()

        # Houdt bij of er iets veranderd is sinds de laatste save --
        # zelfde patroon als pattern_matcher.py's self._dirty, om niet
        # nodeloos vaak naar schijf te schrijven.
        self._dirty = False

    # ------------------------------------------------------------------
    # Feedback registreren
    # ------------------------------------------------------------------

    def record_feedback(self, activiteit, toegestaan, tijd_sinds_start=None):
        """
        Registreert één interruption-poging voor een activiteit.

        activiteit: naam van de activiteit (bv. "coderen") -- exact
        dezelfde string als gebruikt in activity_started:<naam>.
        toegestaan: True/False -- mocht Nova storen of niet?
        tijd_sinds_start: optioneel, hoeveel minuten sinds de
        activiteit begon (nog niet gebruikt voor iets anders dan
        loggen in deze eerste versie -- zie roadmap's "optioneel
        verfijnder" idee voor toekomstig gebruik per tijdsvenster).
        """
        if activiteit not in self.patterns:
            self.patterns[activiteit] = {
                "totaal_pogingen": 0,
                "aantal_toegestaan": 0,
                "confidence": None,
                "laatst_bijgewerkt": None
            }

        entry = self.patterns[activiteit]
        entry["totaal_pogingen"] += 1
        if toegestaan:
            entry["aantal_toegestaan"] += 1

        entry["confidence"] = round(
            entry["aantal_toegestaan"] / entry["totaal_pogingen"], 4
        )
        entry["laatst_bijgewerkt"] = datetime.now().isoformat()

        self._dirty = True
        self.save_to_disk()

        if self.event_bus is not None:
            try:
                self.event_bus.publish("interruption_pattern_updated", {
                    "activiteit": activiteit,
                    "confidence": entry["confidence"],
                    "totaal_pogingen": entry["totaal_pogingen"]
                })
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Opvragen
    # ------------------------------------------------------------------

    def get_confidence(self, activiteit):
        """
        Geeft de confidence-score terug (0.0-1.0), of None als er nog
        te weinig observaties zijn (zie has_enough_data()).
        """
        entry = self.patterns.get(activiteit)
        if entry is None:
            return None
        if not self.has_enough_data(activiteit):
            return None
        return entry["confidence"]

    def get_pattern(self, activiteit):
        """Geeft de volledige, ruwe data terug voor een activiteit."""
        return self.patterns.get(activiteit)

    def has_enough_data(self, activiteit, min_observaties=None):
        """
        Zijn er genoeg observaties om de confidence-score te
        vertrouwen? min_observaties override mogelijk, anders wordt
        de klasse-constante MIN_OBSERVATIES gebruikt.
        """
        drempel = min_observaties if min_observaties is not None else self.MIN_OBSERVATIES
        entry = self.patterns.get(activiteit)
        if entry is None:
            return False
        return entry["totaal_pogingen"] >= drempel

    def get_stats(self):
        """Kort overzicht, zelfde stijl als pattern_matcher.py's get_stats()."""
        return {
            "aantal_activiteiten": len(self.patterns),
            "totaal_observaties": sum(
                p["totaal_pogingen"] for p in self.patterns.values()
            )
        }

    # ------------------------------------------------------------------
    # Opslag
    # ------------------------------------------------------------------

    def load_from_disk(self):
        """
        Leest interruption_patterns.json in (indien aanwezig). Als het
        bestand nog niet bestaat (allereerste keer), blijft
        self.patterns gewoon leeg -- geen crash, verwacht gedrag.
        """
        if not self.save_path.exists():
            return

        try:
            with open(self.save_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[INTERRUPTION_TRACKER] Kon interruption_patterns.json niet lezen, start leeg: {e}")
            return

        self.patterns = data.get("interruption_patterns", {})

        print(
            f"[INTERRUPTION_TRACKER] {len(self.patterns)} activiteit(en) "
            f"hersteld uit interruption_patterns.json."
        )

    def save_to_disk(self):
        """Slaat de huidige patronen op als JSON."""
        self.save_path.parent.mkdir(parents=True, exist_ok=True)

        output = {
            "interruption_patterns": self.patterns
        }

        with open(self.save_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        self._dirty = False

    def shutdown(self):
        """
        Netjes afsluiten (zelfde conventie als pattern_matcher.py) --
        forceert een laatste save als er nog niet-opgeslagen wijzigingen
        zijn. In deze versie slaan we al bij ELKE record_feedback()
        meteen op (geen write-buffer/timer zoals pattern_matcher.py's
        Fase 5), dus dit is vooral een veiligheidsnet.
        """
        if self._dirty:
            self.save_to_disk()


def init_module(event_bus, semantic_module=None):
    """
    Standaard module_loader-conventie: init_module(event_bus, sem).
    'semantic_module' wordt hier niet gebruikt, net als bij
    pattern_matcher.py/word_associations_learner.py.

    LET OP: dit bestand staat in core/, dus wordt NIET automatisch
    gescand door de dynamische pkgutil-scan in module_loader.py (zie
    pending_question.py voor exact dezelfde situatie) -- moet
    handmatig toegevoegd worden aan module_loader.py.
    """
    instance = InterruptionTracker(event_bus)
    if event_bus is not None:
        event_bus.publish("module_loaded", {"name": "interruption_tracker"})
    return instance