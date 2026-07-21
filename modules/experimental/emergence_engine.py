# modules/experimental/emergence_engine.py
"""
Layer 7: Emergence Engine
=========================

FASE 1a: Skelet + eerste insight-type (sterkste woordassociatie, Layer 1) ✅

Doel van Layer 7:
- Alle voorgaande lagen (0-6) periodiek combineren tot "meta-inzichten"
  over Kevin (bv. "je sterkste woordverband is X met Y").
- BELANGRIJKE GRENS (vastgelegd in overleg, zie layer7_startbericht.md):
  * Insight-HERKENNING (patronen/clusters vinden over de lagen heen)
    mag later een bounded ML-specialist worden (net als de geplande
    intent classifier) — dat is toegestaan.
  * De output-TAAL (de zin die Nova effectief zegt) blijft ALTIJD
    sjabloon-gebaseerd. Geen LLM, geen generatie van vrije tekst.
    ML mag dus ooit "wat is belangrijk" herkennen, nooit "hoe zeg ik
    dit" verzinnen.
- In DEZE eerste versie zit nog helemaal geen ML — puur tellen/lezen
  van wat Layer 1 al berekend heeft (PMI-scores), en dat invullen in
  vaste sjabloonzinnen.

Wat dit bestand NOG NIET doet (latere, aparte stappen):
- Nog maar 1 van de geplande 3-4 insight-types (topic-frequentie via
  Layer 1). Tijdspatroon (Layer 2), kennisdichtheid (Layer 3), en
  personality drift (Layer 6) volgen in latere uitbreidingen.
- Nog GEEN listener die "emergence:insight" naar "layer4_response"
  doorstuurt (met confidence-gate). Dit event wordt nu enkel
  gepubliceerd, niemand luistert er nog naar — dus Nova zegt er nog
  NIETS over. Dat is bewust: eerst deze basis testen, dan pas de
  tone-pipeline erbij koppelen.
- Nog GEEN timing-gate (mag Nova dit NU zeggen). Activity-Aware
  Interaction bestaat nog niet. Dit wordt in een latere stap
  opgelost — voorlopig is er simpelweg geen automatische trigger,
  Kevin roept "reflect()" zelf handmatig aan (bv. via een testcommando
  in main.py) om te zien wat de Engine zou zeggen.
- `feedback()` is een LEGE STUB — publiceert enkel een event, slaat
  niets op. Wordt in een latere stap uitgebreid met een echt
  opslagbestand (insight_feedback.json of SQLite-tabel), bijgehouden
  PER INSIGHT-TYPE (niet per losse insight-tekst).

Alles hier is pure Python-logica (dictionary-opvragingen, sorteren,
random.choice op vaste tekstlijsten) — geen ML, geen LLM.
"""

import random
from typing import Dict, List, Optional


class EmergenceEngine:
    """
    Layer 7: Emergence Engine (wordt fase per fase uitgebreid).

    Combineert de andere lagen (via een meegegeven "layers"-dictionary,
    zelfde patroon als response_engine.py/context_manager.py) tot
    meta-inzichten over Kevin, geformuleerd via vaste sjablonen.
    """

    def __init__(self, event_bus=None, layers=None):
        self.event_bus = event_bus
        self.layers = layers or {}

        # Laatst gegenereerde inzichten, puur voor debug/nazicht.
        self.insights: List[Dict] = []

        # ─────────────────────────────────
        # Sjablonen — sterkste woordassociatie (Layer 1)
        # ─────────────────────────────────
        # Klein en gecontroleerd gehouden (zie layer7_startbericht.md):
        # 4-6 openingen, 4-6 middenstukken, 2-3 afsluitingen.
        # Een sjabloonzin wordt opgebouwd als: opening + midden + afsluiting.
        self._sjablonen_woordverband = {
            "opening": [
                "Weet je wat me opvalt, Kevin?",
                "Iets wat ik merk in onze gesprekken:",
                "Ik zie een patroon terugkomen.",
                "Dit viel me op.",
                "Interessant weetje over ons gesprekspatroon:",
            ],
            "midden": [
                "\"{woord1}\" en \"{woord2}\" komen bij jou opvallend vaak samen voor.",
                "je koppelt \"{woord1}\" en \"{woord2}\" aan elkaar, sterker dan de meeste andere woorden.",
                "\"{woord1}\" hangt bij jou stevig samen met \"{woord2}\".",
                "van alle woordverbanden die ik ken, springt \"{woord1}\" ↔ \"{woord2}\" er het meest uit.",
                "\"{woord1}\" en \"{woord2}\" lijken bij jou een vast duo.",
            ],
            "afsluiting": [
                "Tja.",
                "Interessant, vind ik.",
                "Gewoon een observatie.",
            ],
        }

        # Drempel: onder deze PMI-score is een associatie te zwak om
        # als "insight" de moeite waard te zijn. Vaste, symbolische
        # waarde — geen geleerde/dynamische drempel.
        self.MIN_CONFIDENCE_WOORDVERBAND = 0.5

        # Tweede, even belangrijke drempel: hoe vaak moeten twee
        # woorden ECHT samen voorgekomen zijn vóór het een insight
        # mag worden? Zonder deze check kiest analyze_topic_frequency()
        # soms een woordpaar dat maar 1x toevallig samen opdook (PMI
        # is bij weinig data onbetrouwbaar hoog) i.p.v. een écht
        # terugkerend patroon. Vaste, symbolische waarde — zelfde soort
        # aanpak als Layer 2's MIN_OBSERVATIES_VOOR_ANOMALIE.
        self.MIN_CO_OCCURRENCE_WOORDVERBAND = 5

    # ─────────────────────────────────
    # Insight-type 1: sterkste woordassociatie (Layer 1)
    # ─────────────────────────────────

    def analyze_topic_frequency(self) -> Optional[Dict]:
        """
        Kijkt naar Layer 1 (word_associations_learner.py) en zoekt de
        sterkste, BETROUWBARE woordassociatie over de hele dataset.

        BELANGRIJK — eerlijkheid over wat dit wel/niet is:
        Layer 1's get_stats() geeft GEEN "meest voorkomende woord"
        terug (dat veld bestaat niet in de echte code, enkel in een
        oudere roadmap-tekst die niet meer klopt met
        word_associations_learner.py). Wat WEL bestaat is
        "strongest_associations": een lijst van (woord1, woord2, score)
        -tuples, gesorteerd op PMI-sterkte — maar GEEN co_occurrence
        erbij, dus die lijst alleen volstaat niet.

        Waarom niet gewoon strongest_associations[0] nemen (zoals de
        eerste versie deed)? Getest tegen Kevin's echte data (20 juli
        2026): PMI wordt onbetrouwbaar HOOG bij woorden die maar 1-2
        keer toevallig samen voorkwamen (weinig data = extreme score).
        Zonder extra filter koos deze functie daardoor eenmalige
        toevalstreffers (bv. "meubelstuk" <-> "specifiek", 1x samen
        genoemd) i.p.v. een echt terugkerend patroon (bv. "python" <->
        "snel", 10x samen genoemd). Daarom wordt hier het RUWE
        associations-attribuut gebruikt (dat co_occurrence wel bevat),
        met een eigen, tweede filter: enkel woordparen die minstens
        MIN_CO_OCCURRENCE_WOORDVERBAND keer ECHT samen voorkwamen tellen
        mee, naast de bestaande PMI-confidence-drempel.

        Retourneert None als er nog te weinig BETROUWBARE data is (geen
        enkel woordpaar haalt beide drempels) — een eerlijk "nog geen
        insight" in plaats van iets verzinnen op basis van toeval.
        """
        word_assoc = self.layers.get("word_associations")
        if word_assoc is None:
            return None

        # Ruwe data rechtstreeks uitlezen (niet via get_stats(), die
        # geeft geen co_occurrence terug). Defensief: als het attribuut
        # om wat voor reden dan ook ontbreekt, geen insight i.p.v. crash.
        ruwe_associaties = getattr(word_assoc, "associations", None)
        if not ruwe_associaties:
            return None

        kandidaten = []
        for woord1, buren in ruwe_associaties.items():
            for woord2, gegevens in buren.items():
                score = gegevens.get("pmi", 0)
                cooc = gegevens.get("co_occurrence", 0)

                if score < self.MIN_CONFIDENCE_WOORDVERBAND:
                    continue
                if cooc < self.MIN_CO_OCCURRENCE_WOORDVERBAND:
                    continue

                kandidaten.append((woord1, woord2, score, cooc))

        if not kandidaten:
            return None

        # Sorteren op PMI-sterkte (aftopping op cooc gebeurde al hierboven)
        kandidaten.sort(key=lambda x: x[2], reverse=True)
        woord1, woord2, score, cooc = kandidaten[0]

        return {
            "type": "woordverband",
            "woord1": woord1,
            "woord2": woord2,
            "confidence": score,
        }

    def _formuleer_woordverband(self, insight: Dict) -> str:
        """
        Bouwt een sjabloonzin voor een 'woordverband'-insight.

        Puur string-formatting op vaste tekstlijsten — geen generatie.
        """
        opening = random.choice(self._sjablonen_woordverband["opening"])
        midden = random.choice(self._sjablonen_woordverband["midden"]).format(
            woord1=insight["woord1"], woord2=insight["woord2"]
        )
        afsluiting = random.choice(self._sjablonen_woordverband["afsluiting"])

        return f"{opening} {midden} {afsluiting}"

    # ─────────────────────────────────
    # Overkoepelende analyse
    # ─────────────────────────────────

    def analyze_meta_patterns(self) -> List[Dict]:
        """
        Verzamelt insights van alle beschikbare insight-types.

        Momenteel enkel 'woordverband' (Layer 1). Latere uitbreidingen
        (tijdspatroon/Layer 2, kennisdichtheid/Layer 3, personality
        drift/Layer 6) komen hier later apart bij, elk als eigen
        analyze_*()-methode, zelfde patroon als hierboven.
        """
        insights = []

        woordverband = self.analyze_topic_frequency()
        if woordverband is not None:
            insights.append(woordverband)

        return insights

    def reflect(self) -> List[Dict]:
        """
        Voert een volledige reflectie-ronde uit: analyseert alle
        beschikbare lagen, formuleert elk insight via de juiste
        sjabloon-methode, en publiceert "emergence:insight" per insight.

        Publiceert NIETS naar "layer4_response" — dat is bewust een
        latere, aparte stap (zie module-docstring). Dit event heeft
        dus voorlopig nog geen luisteraar; reflect() is voorlopig enkel
        handmatig/via een testcommando aan te roepen, geen automatische
        achtergrond-trigger.
        """
        ruwe_insights = self.analyze_meta_patterns()
        geformuleerd = []

        for insight in ruwe_insights:
            if insight["type"] == "woordverband":
                tekst = self._formuleer_woordverband(insight)
            else:
                # Toekomstige insight-types die nog geen sjabloon
                # hebben: bewust overslaan i.p.v. een kale/rare tekst
                # tonen.
                continue

            resultaat = {
                "text": tekst,
                "confidence": insight["confidence"],
                "insight_type": insight["type"],
                "brondata": insight,
            }
            geformuleerd.append(resultaat)

            if self.event_bus is not None:
                self.event_bus.publish("emergence:insight", resultaat)

        self.insights = geformuleerd
        return geformuleerd

    def get_insights(self) -> List[Dict]:
        """Geeft de laatst gegenereerde inzichten terug (debug/nazicht)."""
        return self.insights

    def debug_layers_status(self) -> Dict:
        """
        TIJDELIJKE debug-methode (mag later weer verwijderd worden).

        Toont exact wat self.layers bevat en of word_associations
        correct is doorgegeven — bedoeld om te controleren of de
        dynamische module_loader-scan deze module per ongeluk óók al
        (fout) heeft geladen vóór stap 3E de juiste, met-layers-dict
        versie erover heen zet.
        """
        return {
            "type_van_self_layers": type(self.layers).__name__,
            "is_dict": isinstance(self.layers, dict),
            "keys_indien_dict": list(self.layers.keys()) if isinstance(self.layers, dict) else None,
            "word_associations_aanwezig": (
                isinstance(self.layers, dict)
                and self.layers.get("word_associations") is not None
            ),
            "word_associations_type": (
                type(self.layers.get("word_associations")).__name__
                if isinstance(self.layers, dict) and self.layers.get("word_associations") is not None
                else None
            ),
        }

    # ─────────────────────────────────
    # Feedback (LEGE STUB — latere uitbreiding)
    # ─────────────────────────────────

    def feedback(self, insight_type: str, success: bool):
        """
        LET OP: dit is bewust nog een LEGE STUB.

        Publiceert enkel een event, slaat nog NIETS op naar schijf.
        Een latere stap breidt dit uit met een echt opslagbestand
        (bv. insight_feedback.json of een SQLite-tabel) dat per
        insight-TYPE (niet per losse insight-tekst) een succes/falen-
        score bijhoudt.

        insight_type: bv. "woordverband" — het TYPE, niet de exacte
        gegenereerde zin (zoals afgesproken in layer7_startbericht.md).
        """
        if self.event_bus is None:
            return

        event_naam = "emergence:learned_success" if success else "emergence:learned_failure"
        self.event_bus.publish(event_naam, {"insight_type": insight_type})


def init_module(event_bus, layers=None):
    """
    Wordt HANDMATIG aangeroepen door module_loader.py (net als
    response_engine.py en context_manager.py), niet via de dynamische
    pkgutil-scan — Layer 7 heeft een "layers"-dictionary nodig met
    meerdere andere lagen erin, niet enkel het standaard "sem"-argument.
    """
    instance = EmergenceEngine(event_bus, layers=layers)
    if event_bus is not None:
        event_bus.publish("module_loaded", {"name": "emergence_engine"})
    return instance