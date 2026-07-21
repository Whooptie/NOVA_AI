# modules/experimental/emergence_engine.py
"""
Layer 7: Emergence Engine
=========================

FASE 1a: Skelet + eerste insight-type (sterkste woordverband, Layer 1) ✅
FASE 1b: Tweede insight-type (sterkste tijdspatroon, Layer 2) ✅
FASE 1c: Derde insight-type (kennisdichtheid, Layer 3) ✅
FASE 1d: Optioneel vierde insight-type (personality drift, Layer 6) ✅

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
- Alle 4 insight-types (3 kern + 1 optioneel) zijn nu gebouwd:
  topic-frequentie (Layer 1), tijdspatroon (Layer 2), kennisdichtheid
  (Layer 3), personality drift (Layer 6). Belangrijke kanttekening bij
  personality drift: meet "welke trait het vaakst daadwerkelijk
  verschoof" (growth_metrics.json's total_shifts), NIET "hoeveel is
  dit afgeweken van de originele startwaarde" — dat laatste is met de
  beschikbare data (traits.json bevat geen startwaarden) niet eerlijk
  te berekenen.
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
        # Sjablonen — sterkste tijdspatroon (Layer 2)
        # ─────────────────────────────────
        self._sjablonen_tijdspatroon = {
            "opening": [
                "Nog iets wat ik zie in je ritme, Kevin:",
                "Ik heb een tijdspatroon opgemerkt.",
                "Timing-observatie:",
                "Dit valt me op qua tijdstip.",
                "Iets over wanneer je actief bent:",
            ],
            "midden": [
                "je bent meestal rond {uur}u bezig met {onderwerp}.",
                "{onderwerp} gebeurt bij jou opvallend vaak rond {uur}u.",
                "rond {uur}u is het moment waarop {onderwerp} meestal terugkomt.",
                "ik zie een duidelijk terugkerend moment: {uur}u, voor {onderwerp}.",
                "{onderwerp} en {uur}u lijken bij jou stevig samen te horen.",
            ],
            "afsluiting": [
                "Gewoon een observatie.",
                "Interessant ritme.",
                "Tja.",
            ],
        }

        # Vertaalt een intern event_type-label naar een leesbaar
        # onderwerp voor in de sjabloonzin. Puur symbolisch, vaste
        # opzoektabel — geen taalverwerking. "topic_detected:<naam>"
        # wordt apart afgehandeld (zie _onderwerp_label()), staat
        # daarom niet in deze tabel.
        self._event_type_labels = {
            "chat_message": "onze gesprekken",
            "chat_response": "onze gesprekken",
        }

        # Vertaalt de INTERNE topic-naam (het stuk na de dubbele punt
        # in "topic_detected:<naam>") naar een Nederlands woord.
        # Nodig omdat intent_router.py's _emit_topic() bewust de
        # Engelse, interne categorienaam gebruikt (bv. "chess", zie
        # topic_events_roadmap.md) — dat is geen bug, maar zonder
        # vertaling zou een Nederlandse sjabloonzin een los Engels
        # woord bevatten ("chess en 19u lijken..."). Vaste opzoektabel,
        # geen vertaal-ML. Onbekende/nieuwe topic-namen vallen terug
        # op de kale naam zelf (zie _onderwerp_label()) — dus nieuwe
        # modules (Plex, dammen, Go, ...) breken hier nooit op, ze
        # klinken enkel iets minder Nederlands totdat iemand ze hier
        # bijvoegt.
        self._topic_naam_labels = {
            "chess": "schaken",
        }

        # ─────────────────────────────────
        # Sjablonen — kennisdichtheid (Layer 3, semantic.py)
        # ─────────────────────────────────
        self._sjablonen_kennisdichtheid = {
            "opening": [
                "Nog iets over wat ik heb opgestoken:",
                "Kennis-observatie:",
                "Iets over wat ik allemaal weet:",
                "Dit valt op als ik terugkijk op wat ik geleerd heb:",
                "Interessant vanuit mijn eigen geheugen:",
            ],
            "midden": [
                "van alles wat ik ken, weet ik het meest over \"{concept}\" — {aantal_relaties} verbanden opgeslagen.",
                "\"{concept}\" is het concept waarover ik de meeste verbanden ken: {aantal_relaties} stuks.",
                "geen enkel ander concept heeft zoveel relaties als \"{concept}\" ({aantal_relaties}).",
                "\"{concept}\" springt eruit qua kennis — {aantal_relaties} verbanden ernaartoe.",
            ],
            "afsluiting": [
                "Tja.",
                "Gewoon een observatie.",
                "Interessant, vind ik.",
            ],
        }

        # Minimum aantal relaties vóór een concept de moeite waard is
        # om als insight te noemen. Vaste, symbolische waarde — zonder
        # deze drempel zou een concept met bv. maar 1 relatie al als
        # "meeste kennis" kunnen gelden zolang niets anders meer heeft.
        self.MIN_RELATIES_VOOR_KENNISDICHTHEID = 3

        # ─────────────────────────────────
        # Sjablonen — personality drift (Layer 6, optioneel insight-type)
        # ─────────────────────────────────
        # BELANGRIJKE EERLIJKHEIDSNOTITIE: dit meet NIET "drift sinds
        # het allereerste begin" — traits.json bevat enkel de HUIDIGE
        # waarden, geen originele startwaarden, dus die vergelijking
        # is met de beschikbare data niet te maken. In plaats daarvan
        # meet dit welke trait het VAAKST daadwerkelijk is verschoven
        # (growth_metrics.json's total_shifts) — een eerlijke, andere
        # maar wel natelbare invulling van "personality drift".
        self._sjablonen_drift = {
            "opening": [
                "Iets wat ik over mezelf merk:",
                "Zelfreflectie:",
                "Ik zie dat ik zelf ook verander.",
                "Dit valt me op over mijn eigen groei:",
            ],
            "midden": [
                "\"{trait}\" is bij mij het vaakst bijgesteld — {aantal_shifts} keer al.",
                "van al mijn eigenschappen is \"{trait}\" het meest in beweging geweest, {aantal_shifts} keer.",
                "ik verander het meest op het vlak van \"{trait}\" ({aantal_shifts} verschuivingen).",
            ],
            "afsluiting": [
                "Tja.",
                "Interessant om te merken.",
                "Gewoon een observatie over mezelf.",
            ],
        }

        # Vertaalt een interne trait-naam (uit traits.json/
        # growth_metrics.json) naar een leesbare Nederlandse omschrijving
        # voor in de sjabloonzin. Vaste opzoektabel, geen NLP. Traits
        # die hier nog niet in staan vallen terug op de kale naam zelf
        # (zie _trait_label()) — geen crash, enkel iets minder vloeiend
        # Nederlands totdat iemand ze hier bijvoegt.
        self._trait_labels = {
            "social_warmth": "hoe warm ik overkom",
            "loyalty": "loyaliteit",
            "self_regulation": "zelfbeheersing",
            "curiosity": "nieuwsgierigheid",
            "reflection_depth": "hoe diep ik nadenk",
            "stubbornness_soft": "koppigheid",
            "expressiveness": "expressiviteit",
            "emotional_color_intensity": "emotionele kleur",
            "associative_thinking": "associatief denken",
            "focus_hyperfocus_tendency": "focusneiging",
            "reactivity": "reactiviteit",
            "impulsivity": "impulsiviteit",
            "chaotic_variability": "chaotische variatie",
            "energy_level": "energieniveau",
            "dramatic_flair": "dramatische flair",
        }

    def _trait_label(self, trait_naam: str) -> str:
        """
        Vertaalt een interne trait-naam naar leesbaar Nederlands.
        Puur symbolische opzoektabel, geen NLP. Onbekende/nieuwe
        traits vallen terug op de kale naam zelf.
        """
        return self._trait_labels.get(trait_naam, trait_naam)

    def _onderwerp_label(self, event_type: str) -> str:
        """
        Vertaalt een intern event_type-label naar een leesbaar
        onderwerp voor in de sjabloonzin. Puur symbolische
        string-verwerking (opzoektabel + string-slicing), geen NLP.

        - "chat_message"/"chat_response" -> "onze gesprekken"
        - "topic_detected:chess" -> "schaken" (via _topic_naam_labels;
          intent_router.py gebruikt bewust de Engelse, interne
          categorienaam achter de dubbele punt, zie
          topic_events_roadmap.md)
        - "topic_detected:<onbekende naam>" -> de kale naam zelf,
          als eerlijke fallback voor topics die nog niet in
          _topic_naam_labels staan
        - ander onbekend event_type -> de kale naam zelf
        """
        if event_type in self._event_type_labels:
            return self._event_type_labels[event_type]

        if event_type.startswith("topic_detected:"):
            topic_naam = event_type.split(":", 1)[1]
            return self._topic_naam_labels.get(topic_naam, topic_naam)

        return event_type

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
    # Insight-type 2: sterkste tijdspatroon (Layer 2)
    # ─────────────────────────────────

    def analyze_timing_pattern(self) -> Optional[Dict]:
        """
        Kijkt naar Layer 2 (pattern_matcher.py) en zoekt het sterkste,
        BETROUWBARE tijdspatroon over alle bijgehouden event_types.

        BELANGRIJK — eerlijkheid over wat dit wel/niet is:
        pattern_matcher.py's get_stats() geeft GEEN per-patroon-info
        terug (enkel aantallen). Wat WEL bestaat is get_all_patterns(),
        die voor elk event_type een dict teruggeeft met "total",
        "most_common_hour", "confidence" en "day_frequency" — dat is
        wat deze functie gebruikt.

        Betrouwbaarheidsgrens: hergebruikt bewust dezelfde
        MIN_OBSERVATIES_VOOR_ANOMALIE-drempel die Layer 2 zelf al
        gebruikt om anomalieën te toetsen (consistentie i.p.v. een
        nieuwe, losse drempel verzinnen) — een patroon met minder
        observaties dan dat vindt Layer 2 zelf ook nog niet
        betrouwbaar genoeg.

        Retourneert None als er geen enkel event_type genoeg
        observaties EN een geldig most_common_hour/confidence heeft.
        """
        pattern_matcher = self.layers.get("pattern_matcher")
        if pattern_matcher is None:
            return None

        alle_patronen = pattern_matcher.get_all_patterns()
        if not alle_patronen:
            return None

        # Zelfde drempel die Layer 2 zelf gebruikt voor anomalieën —
        # bewust hergebruikt i.p.v. een eigen, nieuwe waarde te kiezen.
        min_observaties = getattr(
            pattern_matcher, "MIN_OBSERVATIES_VOOR_ANOMALIE", 10
        )

        kandidaten = []
        for event_type, data in alle_patronen.items():
            total = data.get("total", 0)
            confidence = data.get("confidence")
            uur = data.get("most_common_hour")

            if total < min_observaties:
                continue
            if confidence is None or uur is None:
                continue

            kandidaten.append((event_type, uur, confidence, total))

        if not kandidaten:
            return None

        kandidaten.sort(key=lambda x: x[2], reverse=True)
        event_type, uur, confidence, total = kandidaten[0]

        return {
            "type": "tijdspatroon",
            "event_type": event_type,
            "onderwerp": self._onderwerp_label(event_type),
            "uur": uur,
            "confidence": confidence,
        }

    def _formuleer_tijdspatroon(self, insight: Dict) -> str:
        """
        Bouwt een sjabloonzin voor een 'tijdspatroon'-insight.

        Puur string-formatting op vaste tekstlijsten — geen generatie.
        """
        opening = random.choice(self._sjablonen_tijdspatroon["opening"])
        midden = random.choice(self._sjablonen_tijdspatroon["midden"]).format(
            uur=insight["uur"], onderwerp=insight["onderwerp"]
        )
        afsluiting = random.choice(self._sjablonen_tijdspatroon["afsluiting"])

        return f"{opening} {midden} {afsluiting}"

    # ─────────────────────────────────
    # Insight-type 3: kennisdichtheid (Layer 3, semantic.py)
    # ─────────────────────────────────

    def analyze_knowledge_density(self) -> Optional[Dict]:
        """
        Kijkt naar Layer 3 (semantic.py) en zoekt het concept waarover
        Nova de MEESTE relaties kent — een ruwe maatstaf voor "waarover
        weet ik het meest".

        BELANGRIJK — eerlijkheid over wat dit wel/niet is:
        semantic.py's publieke API (SemanticConceptsModule) heeft GEEN
        get_stats() of vergelijkbare telmethode. Wat WEL bestaat: het
        publieke (niet-underscore) attribuut `store` (een ConceptStore
        -instantie), met `store.concepts` als ruwe dictionary
        {woord: {"senses": [...], ...}}. Elke sense heeft op zijn beurt
        een "relations"-lijst. Deze functie leest dat rechtstreeks uit
        — zelfde aanpak als Layer 1's `associations`-attribuut eerder.

        "Kennisdichtheid" wordt hier gemeten als: het TOTAAL aantal
        relaties over ALLE senses van een concept samen (niet enkel de
        eerste/beste sense) — een concept met meerdere betekenissen
        die elk een paar relaties hebben, telt dus terecht als
        "kennisrijk".

        Retourneert None als er geen enkel concept minstens
        MIN_RELATIES_VOOR_KENNISDICHTHEID relaties heeft — een eerlijk
        "nog geen insight" i.p.v. een concept met amper 1 relatie
        uitroepen tot "belangrijkste".
        """
        semantic = self.layers.get("semantic")
        if semantic is None:
            return None

        store = getattr(semantic, "store", None)
        if store is None:
            return None

        alle_concepten = getattr(store, "concepts", None)
        if not alle_concepten:
            return None

        kandidaten = []
        for concept_naam, concept_data in alle_concepten.items():
            senses = concept_data.get("senses", [])
            aantal_relaties = sum(
                len(sense.get("relations", [])) for sense in senses
            )
            if aantal_relaties >= self.MIN_RELATIES_VOOR_KENNISDICHTHEID:
                kandidaten.append((concept_naam, aantal_relaties))

        if not kandidaten:
            return None

        kandidaten.sort(key=lambda x: x[1], reverse=True)
        concept_naam, aantal_relaties = kandidaten[0]

        return {
            "type": "kennisdichtheid",
            "concept": concept_naam,
            "aantal_relaties": aantal_relaties,
            # Geen natuurlijke 0-1-confidence beschikbaar zoals bij
            # PMI/Layer 2-confidence — hier gebruiken we het aantal
            # relaties zelf als ruwe sterkte-indicator, enkel voor
            # sortering/nazicht (get_insights()), niet als percentage.
            "confidence": aantal_relaties,
        }

    def _formuleer_kennisdichtheid(self, insight: Dict) -> str:
        """
        Bouwt een sjabloonzin voor een 'kennisdichtheid'-insight.

        Puur string-formatting op vaste tekstlijsten — geen generatie.
        """
        opening = random.choice(self._sjablonen_kennisdichtheid["opening"])
        midden = random.choice(self._sjablonen_kennisdichtheid["midden"]).format(
            concept=insight["concept"], aantal_relaties=insight["aantal_relaties"]
        )
        afsluiting = random.choice(self._sjablonen_kennisdichtheid["afsluiting"])

        return f"{opening} {midden} {afsluiting}"

    # ─────────────────────────────────
    # Insight-type 4 (optioneel): personality drift (Layer 6)
    # ─────────────────────────────────

    def analyze_personality_drift(self) -> Optional[Dict]:
        """
        Kijkt naar Layer 6 (microlearning.py) en zoekt de trait die het
        VAAKST daadwerkelijk is verschoven sinds Nova draait.

        BELANGRIJKE EERLIJKHEIDSNOTITIE (zie ook __init__): dit meet
        NIET "hoe ver is deze trait van zijn originele startwaarde
        afgeweken" — traits.json bevat enkel de HUIDIGE waarden, geen
        losse "startwaarde"-veld, dus die berekening is met de
        beschikbare data niet eerlijk te maken (zou een verzonnen
        referentiepunt vereisen). In plaats daarvan gebruikt dit
        growth_metrics.json's `total_shifts` — hoe vaak een trait al
        daadwerkelijk is bijgesteld (niet enkel hoe vaak een signaal
        geteld werd, dat leidt pas tot een shift bij het bereiken van
        de drempel in adaptive_rules.json). Dat is een andere, maar
        wel volledig natelbare invulling van "personality drift".

        Bij een gelijkstand in total_shifts kiest de meest recente
        `last_shift`-timestamp — simpele, voorspelbare tie-breaker.

        Retourneert None als geen enkele trait ooit al verschoven is
        (total_shifts altijd 0) — een eerlijk "nog geen insight" i.p.v.
        een trait noemen die in werkelijkheid nog nooit bewogen heeft.
        """
        microlearning = self.layers.get("microlearning")
        if microlearning is None:
            return None

        get_metrics = getattr(microlearning, "get_growth_metrics", None)
        if get_metrics is None:
            return None

        alle_metrics = get_metrics()
        if not alle_metrics:
            return None

        kandidaten = []
        for trait_naam, data in alle_metrics.items():
            total_shifts = data.get("total_shifts", 0)
            if total_shifts <= 0:
                continue
            last_shift = data.get("last_shift") or ""
            kandidaten.append((trait_naam, total_shifts, last_shift))

        if not kandidaten:
            return None

        # Sorteren op total_shifts (hoogste eerst), bij gelijkstand op
        # de meest recente last_shift-timestamp (ISO-strings sorteren
        # correct alfabetisch/chronologisch).
        kandidaten.sort(key=lambda x: (x[1], x[2]), reverse=True)
        trait_naam, total_shifts, _ = kandidaten[0]

        return {
            "type": "personality_drift",
            "trait": trait_naam,
            "trait_label": self._trait_label(trait_naam),
            "aantal_shifts": total_shifts,
            # Zelfde kanttekening als bij kennisdichtheid: geen
            # natuurlijke 0-1-score beschikbaar, aantal shifts zelf
            # dient als ruwe sterkte-indicator voor sortering/nazicht.
            "confidence": total_shifts,
        }

    def _formuleer_drift(self, insight: Dict) -> str:
        """
        Bouwt een sjabloonzin voor een 'personality_drift'-insight.

        Puur string-formatting op vaste tekstlijsten — geen generatie.
        """
        opening = random.choice(self._sjablonen_drift["opening"])
        midden = random.choice(self._sjablonen_drift["midden"]).format(
            trait=insight["trait_label"], aantal_shifts=insight["aantal_shifts"]
        )
        afsluiting = random.choice(self._sjablonen_drift["afsluiting"])

        return f"{opening} {midden} {afsluiting}"

    # ─────────────────────────────────
    # Overkoepelende analyse
    # ─────────────────────────────────

    def analyze_meta_patterns(self) -> List[Dict]:
        """
        Verzamelt insights van alle beschikbare insight-types.

        Kernscope compleet: 'woordverband' (Layer 1), 'tijdspatroon'
        (Layer 2), 'kennisdichtheid' (Layer 3). Plus het optionele
        vierde type 'personality_drift' (Layer 6), zoals besproken in
        layer7_startbericht.md ("evt. personality drift").
        """
        insights = []

        woordverband = self.analyze_topic_frequency()
        if woordverband is not None:
            insights.append(woordverband)

        tijdspatroon = self.analyze_timing_pattern()
        if tijdspatroon is not None:
            insights.append(tijdspatroon)

        kennisdichtheid = self.analyze_knowledge_density()
        if kennisdichtheid is not None:
            insights.append(kennisdichtheid)

        drift = self.analyze_personality_drift()
        if drift is not None:
            insights.append(drift)

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
            elif insight["type"] == "tijdspatroon":
                tekst = self._formuleer_tijdspatroon(insight)
            elif insight["type"] == "kennisdichtheid":
                tekst = self._formuleer_kennisdichtheid(insight)
            elif insight["type"] == "personality_drift":
                tekst = self._formuleer_drift(insight)
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