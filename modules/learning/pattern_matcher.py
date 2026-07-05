# modules/learning/pattern_matcher.py

"""
Layer 2: Pattern Matcher

Detecteert gedragspatronen in Nova's interacties: op welk uur en welke
dag komt een bepaald event (bv. "coffee:mentioned") meestal voor, en
hoe zeker is dat patroon?

Dit is 100% symbolisch: enkel tellen en rekenen op timestamps.
Geen ML, geen taalverwerking.

Fase 1: Event grouping (per uur, per dag, per event_type)
Fase 2: Pattern detection (frequentie + confidence-score)
Fase 3 (later): Anomaly detection
Fase 4 (later): Query & predictie
Fase 5 (later): Volledige integratie met Layer 5/7
"""

from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path


# Nederlandse dagnamen, index volgens datetime.weekday() (0 = maandag)
# LET OP: we gebruiken bewust NIET dt.strftime("%A"), want dat geeft op
# Windows Engelse dagnamen terug (bekende bug, ook al opgelost in
# weather.py op dezelfde manier).
DAGEN_NL = [
    "maandag", "dinsdag", "woensdag", "donderdag",
    "vrijdag", "zaterdag", "zondag"
]


class PatternMatcher:
    """
    Layer 2: Pattern Matcher

    Houdt van élk event_type bij op welk uur en welke dag het meestal
    voorkomt, en berekent hoe betrouwbaar (confidence) dat patroon is.
    """

    def __init__(self, event_bus=None, semantic_module=None):
        self.event_bus = event_bus
        # Nog niet gebruikt in Fase 1-2, maar we houden de parameter
        # aan zodat module_loader.py (die altijd init_module(event_bus, sem)
        # aanroept) niet crasht. Zelfde conventie als word_associations_learner.py.
        self.semantic = semantic_module

        # patterns structuur, per event_type:
        # {
        #   "hours": {0: aantal, 1: aantal, ...},   # int -> int
        #   "days": {"maandag": aantal, ...},        # str -> int
        #   "total": aantal
        # }
        self.patterns = {}

        # Portable pad, zelfde principe als memory.py: nooit hardcoded
        # Windows-pad, altijd relatief t.o.v. dit bestand.
        self.save_path = Path(__file__).resolve().parent.parent.parent / "data" / "patterns_layer2.json"

        if self.event_bus is not None:
            self.event_bus.subscribe("memory:interaction_added", self.detect_from)

    # ------------------------------------------------------------------
    # FASE 1: Event grouping
    # ------------------------------------------------------------------

    def detect_from(self, interaction, event_type=None):
        """
        Wordt aangeroepen bij élke 'memory:interaction_added'-event.

        LET OP: memory.py publiceert élk event opnieuw met een aparte
        'event_type'-parameter (niet als los veld in de dict) — dezelfde
        structuur die we ook al bij word_associations_learner.py
        tegenkwamen. We gebruiken hier dus de 'event_type'-parameter,
        niet interaction.get("event_type").
        """

        if event_type is None:
            return

        timestamp = interaction.get("timestamp")
        if timestamp is None:
            return

        dt = datetime.fromtimestamp(timestamp)
        hour = dt.hour
        day_name = DAGEN_NL[dt.weekday()]

        # Nieuw event_type? Structuur aanmaken.
        if event_type not in self.patterns:
            self.patterns[event_type] = {
                "hours": defaultdict(int),
                "days": defaultdict(int),
                "total": 0
            }

        self.patterns[event_type]["hours"][hour] += 1
        self.patterns[event_type]["days"][day_name] += 1
        self.patterns[event_type]["total"] += 1

        # Na elke nieuwe observatie meteen de statistieken herberekenen
        # (Fase 2). Bij grote hoeveelheden events kan dit later
        # geoptimaliseerd worden (bv. enkel elke N events), maar voor nu
        # houden we het simpel en altijd up-to-date.
        self._update_pattern_stats(event_type)

    # ------------------------------------------------------------------
    # FASE 2: Pattern detection (frequentie + confidence)
    # ------------------------------------------------------------------

    def _update_pattern_stats(self, event_type):
        """
        Berekent voor één event_type:
        - most_common_hour: het uur waarop dit event het vaakst voorkomt
        - confidence: hoe vaak het exact op dat uur is (0.0 - 1.0)
        - day_frequency: per dag, hoe vaak dit event relatief voorkomt
        """

        data = self.patterns[event_type]
        total = data["total"]

        if total == 0:
            return

        # Meest voorkomende uur
        hours = data["hours"]
        most_common_hour = max(hours, key=hours.get)
        occurrences_at_hour = hours[most_common_hour]

        # Confidence: hoe groot is het aandeel van dat ene uur t.o.v. alle
        # keren dat dit event ooit voorkwam?
        confidence = occurrences_at_hour / total

        self.patterns[event_type]["most_common_hour"] = most_common_hour
        self.patterns[event_type]["confidence"] = round(confidence, 3)

        # Dagfrequentie: voor elke dag, hoeveel aandeel heeft die dag in
        # het totaal aantal observaties?
        days = data["days"]
        total_days_observed = sum(days.values())

        day_frequency = {}
        for dag in DAGEN_NL:
            aantal_op_die_dag = days.get(dag, 0)
            if total_days_observed > 0:
                # Aandeel van deze dag t.o.v. alle observaties, genormaliseerd
                # zodat een dag die "elke keer" voorkomt naar 1.0 neigt.
                verwacht_per_dag = total_days_observed / 7
                freq = aantal_op_die_dag / verwacht_per_dag if verwacht_per_dag > 0 else 0
                day_frequency[dag] = round(min(1.0, freq), 3)
            else:
                day_frequency[dag] = 0.0

        self.patterns[event_type]["day_frequency"] = day_frequency

    # ------------------------------------------------------------------
    # Query-functies (basis, meer volgt in Fase 4)
    # ------------------------------------------------------------------

    def get_pattern(self, event_type):
        """Geeft alle patroongegevens terug voor een bepaald event_type."""
        return self.patterns.get(event_type)

    def get_all_patterns(self):
        """Geeft alle gedetecteerde patronen terug (voor alle event_types)."""
        return self.patterns

    def get_stats(self):
        """Kort overzicht: hoeveel event_types worden er bijgehouden en met hoeveel observaties totaal."""
        return {
            "aantal_event_types": len(self.patterns),
            "totaal_observaties": sum(p["total"] for p in self.patterns.values())
        }

    # ------------------------------------------------------------------
    # Opslag (volledige persistente opslag volgt in Fase 5, dit is een
    # eenvoudige eerste versie zodat je nu al iets op schijf kan zien)
    # ------------------------------------------------------------------

    def save_to_disk(self):
        """Slaat de huidige patronen op als JSON, zodat je ze kan inspecteren."""
        self.save_path.parent.mkdir(parents=True, exist_ok=True)

        # defaultdict kan niet direct naar JSON, dus zetten we alles om
        # naar gewone dicts voor het opslaan.
        serializable = {}
        for event_type, data in self.patterns.items():
            serializable[event_type] = {
                "hours": dict(data["hours"]),
                "days": dict(data["days"]),
                "total": data["total"],
                "most_common_hour": data.get("most_common_hour"),
                "confidence": data.get("confidence"),
                "day_frequency": data.get("day_frequency", {})
            }

        with open(self.save_path, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2, ensure_ascii=False)


def init_module(event_bus, semantic_module=None):
    """
    Wordt aangeroepen door module_loader.py bij het opstarten van Nova.

    Let op: module_loader.py roept dynamische modules altijd aan als
    init_module(event_bus, sem) — waarbij "sem" de semantic-module
    (Layer 3) is. Daarom accepteert deze functie een
    "semantic_module"-parameter, net zoals word_associations_learner.py
    dat ook al doet. We gebruiken semantic_module hier momenteel nog
    niet.

    LET OP: dit is Fase 1-2 van 5. Er wordt nog NIETS automatisch
    opgeslagen naar schijf bij elk event — dat komt pas in Fase 5.
    Herstart je Nova, dan is alles wat tot dan toe geleerd is, weer weg.
    Dat is verwacht gedrag voor deze fase. Je kan wel manueel
    save_to_disk() aanroepen om tussentijds te kijken wat er verzameld is.
    """
    instance = PatternMatcher(event_bus, semantic_module=semantic_module)
    if event_bus is not None:
        event_bus.publish("module_loaded", {"name": "pattern_matcher"})
    return instance