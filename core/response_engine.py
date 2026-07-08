# core/response_engine.py
"""
Layer 4: Response Generation Engine
====================================

Combineert de drie voorgaande lagen tot één antwoord:

- Layer 3 (semantic.py)              -> WAT iets betekent
- Layer 1 (word_associations_learner) -> WAARMEE Kevin het associeert
- Layer 2 (pattern_matcher)           -> WANNEER dit onderwerp meestal
                                          voorkomt

BELANGRIJK — eerlijkheid over wat dit wel/niet is:
Dit is 100% symbolisch. Er wordt GEEN tekst "gegenereerd" door een taal-
model. Elk antwoord komt uit een vaste Nederlandse zin-sjabloon
(hieronder in self.templates), met alleen de ontbrekende stukjes
("{entity}", "{definition}", ...) ingevuld vanuit de drie lagen. Als
er geen sjabloon past of geen data beschikbaar is, antwoordt Nova
eerlijk dat ze het niet weet — ze verzint nooit een antwoord.

FASE 1 (klaar):
- Sjabloon "definitie": pure Layer 3 (semantic), zonder personal touch.

FASE 2 (dit bestand, huidige versie):
- Layer 1 (word_associations_learner) toegevoegd via _sterkste_associatie().
- ALLEEN als er al een definitie gevonden is EN er een sterk genoege
  associatie bestaat (score >= MIN_ASSOCIATIE_SCORE), wordt het
  uitgebreide sjabloon "met_associatie" gebruikt. Anders gewoon de
  kale definitie — geen geforceerde "personal touch" als die er niet
  echt is.
- Vroeg in Nova's leven (weinig chatgeschiedenis) zal Layer 1 vaak nog
  niets of te weinig teruggeven — dat is verwacht gedrag, geen bug.

FASE 3 (dit bestand, huidige versie):
- Layer 2 (pattern_matcher) toegevoegd via get_timing_hint(topic_naam).
- BEWUST NOG NIET gekoppeld aan generate()! generate() krijgt enkel
  een los woord ("entity") binnen, geen topic-naam, en die twee komen
  bijna nooit letterlijk overeen (bv. "python" vs. topic "chess").
  get_timing_hint() bestaat dus als losse, apart testbare methode.
  De echte koppeling gebeurt pas in Fase 4, wanneer intent_router.py
  het actieve topic van het gesprek meegeeft aan Layer 4.

Nog GEEN koppeling met de EventBus/intent_router — dat is stap 4.
Voor nu is dit een losstaande klasse die je apart kan testen (zie
test_response_engine.py).

Volgende stappen (samen met Kevin, niet in dit bestand):
- FASE 4: Echte integratie in module_loader.py + intent_router.py,
          zodat Nova dit ook echt gebruikt tijdens een gesprek, en
          get_timing_hint() voor het eerst echt wordt aangeroepen.
"""

from typing import Dict, Optional


class ResponseEngine:
    """
    Layer 4: Response Generation Engine.

    Krijgt bij het opstarten een "layers"-dictionary mee met de al
    geladen instanties van de andere modules, bijvoorbeeld:

        layers = {
            "semantic": sem,                # SemanticConceptsModule
            "word_associations": word_assoc, # WordAssociationsLearner
            "pattern_matcher": pm,           # PatternMatcher
        }

    Layer 4 roept deze rechtstreeks aan als gewone Python-methodes
    (dus NIET via de EventBus) — dat is een bewuste, al afgesproken
    architectuurkeuze, omdat dit gewoon opzoekingen zijn, geen acties
    die andere modules moeten weten.
    """

    def __init__(self, event_bus=None, layers: Optional[Dict] = None):
        self.event_bus = event_bus
        self.layers = layers or {}

        # Sjablonen: vaste Nederlandse zinnen met invulplekken.
        # Fase 1 heeft er maar één ("definitie"); in latere fases
        # komen er sjablonen bij voor "met_associatie" en "met_timing".
        self.templates = {
            "definitie": "{entity} betekent: {definition}",
            "met_associatie": "{entity} betekent: {definition} Je associeert dat trouwens vaak met '{associatie}'.",
            "is_a_fallback": "{entity} is een soort van {parent}.",
            "onbekend": "Ik weet nog niet wat '{entity}' betekent.",
            "timing_hint": "Trouwens, je vraagt hier meestal rond {uur}u naar.",
        }

        # Vanaf welke PMI-score (0.0-1.0) vinden we een associatie sterk
        # genoeg om aan een antwoord toe te voegen? Layer 1 geeft in het
        # begin (weinig chat-geschiedenis) vaak zwakke/toevallige
        # associaties terug — die willen we NIET tonen, want dat zou
        # als ruis aanvoelen in plaats van als "Nova kent me".
        # 0.5 is bewust dezelfde drempel als Layer 1's eigen
        # min_confidence-conventie (zie word_associations_learner.py).
        self.MIN_ASSOCIATIE_SCORE = 0.5

    # ------------------------------------------------------------
    # Interne hulpmethodes
    # ------------------------------------------------------------

    def _sterkste_associatie(self, entity: str) -> Optional[str]:
        """
        Vraagt Layer 1 (word_associations_learner) op of er een sterke
        associatie bestaat voor 'entity', en geeft het sterkste
        geassocieerde woord terug — maar ALLEEN als de score minstens
        self.MIN_ASSOCIATIE_SCORE haalt.

        Geeft None terug als:
        - Layer 1 niet beschikbaar is (nog niet meegegeven in layers)
        - er nog helemaal geen associaties zijn voor dit woord (heel
          normaal vroeg in Nova's leven, Layer 1 moet eerst chatten
          verzamelen)
        - de sterkste associatie te zwak is om betrouwbaar te tonen

        find_related() geeft altijd AL gesorteerd terug van sterk naar
        zwak (zie word_associations_learner.py), dus we hoeven hier
        zelf niet te sorteren — enkel het eerste resultaat pakken en
        de score controleren.
        """
        word_assoc = self.layers.get("word_associations")
        if word_assoc is None:
            return None

        try:
            related = word_assoc.find_related(entity, top_k=1)
        except Exception:
            # Ook hier: een opzoekfout in Layer 1 mag nooit Nova's
            # antwoord laten crashen. Gewoon doen alsof er niets was.
            return None

        if not related:
            return None

        woord, score = related[0]
        if score < self.MIN_ASSOCIATIE_SCORE:
            return None

        return woord

    def get_timing_hint(self, topic_naam: str) -> Optional[str]:
        """
        Layer 2 (pattern_matcher): geeft een timing-zinnetje terug
        voor een TOPIC (bv. "chess", "weather" — de naam die
        intent_router.py doorgeeft via _emit_topic(), zonder het
        "topic_detected:"-voorvoegsel).

        BELANGRIJK — dit is een LOSSTAANDE methode, nog NIET gebruikt
        in generate(). Reden: generate() krijgt momenteel enkel een
        los woord ("entity") binnen, geen topic-naam — en een los
        woord zoals "python" komt bijna nooit letterlijk overeen met
        een topic-naam zoals "chess". Deze methode wordt pas echt
        ingeschakeld in Fase 4, wanneer intent_router.py het actieve
        topic van het gesprek doorgeeft aan Layer 4.

        Geeft None terug als:
        - Layer 2 niet beschikbaar is (nog niet meegegeven in layers)
        - het patroon nog niet actief is op dit moment
          (is_pattern_active() geeft False bij te weinig data OF
          simpelweg omdat dit niet het gebruikelijke moment is)
        """
        pattern_matcher = self.layers.get("pattern_matcher")
        if pattern_matcher is None:
            return None

        event_type = f"topic_detected:{topic_naam}"

        try:
            actief = pattern_matcher.is_pattern_active(event_type)
        except Exception:
            # Zelfde principe als bij Layer 1/3: een opzoekfout in
            # Layer 2 mag Nova's antwoord nooit laten crashen.
            return None

        if not actief:
            return None

        try:
            pattern = pattern_matcher.get_pattern(event_type)
        except Exception:
            return None

        if not pattern:
            return None

        uur = pattern.get("most_common_hour")
        if uur is None:
            return None

        return self.templates["timing_hint"].format(uur=uur)

    # ------------------------------------------------------------
    # Publieke API
    # ------------------------------------------------------------

    def generate(self, entity: str) -> Dict:
        """
        Genereert een antwoord over 'entity', puur op basis van
        Layer 3 (semantic).

        Output-formaat (zelfde stijl als de rest van Nova's modules):
            {
                "text": "...",
                "confidence": 0.0-1.0,
                "sources": ["semantic"],
            }

        Fase 1: alleen semantic.get_meaning() en, als fallback,
        get_relations(entity, "is_a"). Geen Layer 1/2 nog.
        """
        entity = (entity or "").strip()
        if not entity:
            return {
                "text": "Waarover wil je meer weten?",
                "confidence": 0.0,
                "sources": [],
            }

        semantic = self.layers.get("semantic")

        # --- Stap 1: probeer een echte definitie te vinden ---
        definition = None
        if semantic is not None:
            try:
                definition = semantic.get_meaning(entity)
            except Exception:
                # Nova mag hier nooit crashen op een opzoekfout —
                # gewoon doorgaan alsof er niets gevonden is.
                definition = None

        if definition:
            # --- Layer 1: is er een sterke, persoonlijke associatie? ---
            # We proberen dit ALLEEN als er al een definitie is gevonden
            # — een associatie zonder definitie zou een vreemde,
            # betekenisloze zin opleveren ("betekent: ... trouwens vaak
            # met..." zonder eerst te weten wat het woord is).
            associatie_woord = self._sterkste_associatie(entity)

            if associatie_woord:
                text = self.templates["met_associatie"].format(
                    entity=entity,
                    definition=definition,
                    associatie=associatie_woord,
                )
                return {
                    "text": text,
                    "confidence": 0.9,
                    "sources": ["semantic", "word_associations"],
                }

            text = self.templates["definitie"].format(
                entity=entity, definition=definition
            )
            return {
                "text": text,
                "confidence": 0.9,
                "sources": ["semantic"],
            }

        # --- Stap 2: geen directe definitie -> probeer is_a-relatie ---
        if semantic is not None:
            try:
                parents = semantic.get_relations(entity, "is_a")
            except Exception:
                parents = []

            if parents:
                text = self.templates["is_a_fallback"].format(
                    entity=entity, parent=parents[0]
                )
                return {
                    "text": text,
                    "confidence": 0.6,
                    "sources": ["semantic"],
                }

        # --- Stap 3: echt niets gevonden -> eerlijk toegeven ---
        text = self.templates["onbekend"].format(entity=entity)
        return {
            "text": text,
            "confidence": 0.2,
            "sources": [],
        }


def init_module(event_bus, layers=None):
    """
    Wordt later (Fase 4) aangeroepen door module_loader.py.

    LET OP: dit accepteert bewust een aparte 'layers'-dictionary,
    NIET het gebruikelijke 'semantic_module'-argument dat de andere
    modules krijgen — Layer 4 heeft namelijk meerdere lagen tegelijk
    nodig, niet enkel semantic. module_loader.py moet dit dus apart
    aanroepen (dat regelen we in Fase 4), niet via de generieke
    "init_module(event_bus, sem)"-aanroep die de andere modules
    krijgen.
    """
    instance = ResponseEngine(event_bus, layers=layers)
    if event_bus is not None:
        event_bus.publish("module_loaded", {"name": "response_engine"})
    return instance