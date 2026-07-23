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

FASE 4 (klaar, live getest):
- Integratie in module_loader.py + intent_router.py: Nova gebruikt dit
  nu echt tijdens een gesprek. Zie nova_state.md voor details.

FASE 5 (dit bestand, huidige versie):
- Sjablonen zijn niet langer 1 vaste zin per situatie, maar een LIJST
  van meerdere natuurlijke, warmere varianten. _kies_variant() kiest
  er willekeurig eentje uit (zelfde principe als expression_injector.py
  met emoji's). Dit blijft 100% symbolisch: er wordt nooit een nieuwe
  zin gegenereerd, enkel gekozen uit vooraf geschreven varianten.
- Doel: minder "woordenboek-gevoel", meer klinken als gesprekspartner
  — zonder de architectuur te verraden (nog steeds geen LLM).

Nog GEEN koppeling met de EventBus/intent_router — dat is stap 4.
Voor nu is dit een losstaande klasse die je apart kan testen (zie
test_response_engine.py).

Volgende stappen (samen met Kevin, niet in dit bestand):
- FASE 6: bug #10 aanpakken (senses matchen aan associaties).
- FASE 7: tone_engine.py/personality_engine.py laten meespelen in
          welke variant gekozen wordt.
"""

import random
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
        #
        # FASE 5: elk sjabloon is nu een LIJST van varianten, in plaats
        # van 1 vaste zin. _kies_variant() kiest er willekeurig eentje
        # uit. Dit blijft 100% symbolisch/vast: er wordt niets nieuws
        # "verzonnen" of gegenereerd, we hebben gewoon vooraf meerdere
        # handgeschreven zinnen klaarstaan, en Nova kiest er toevallig
        # eentje — net zoals expression_injector.py al met emoji's
        # doet. Zo klinkt Nova minder als een woordenboek dat exact
        # dezelfde zin blijft herhalen.
        self.templates = {
            "definitie": [
                "{entity} betekent: {definition}",
                "Met '{entity}' bedoel je waarschijnlijk: {definition}",
                "Ik ken '{entity}' als: {definition}",
                "{entity}, dat is: {definition}",
                "Wat ik weet over '{entity}': {definition}",
            ],
            "met_associatie": [
                "{entity} betekent: {definition} Trouwens, dat woord duikt bij jou vaak op samen met '{associatie}'.",
                "Met '{entity}' bedoel je waarschijnlijk: {definition} Ik zie dat woord bij jou trouwens vaak in de buurt van '{associatie}'.",
                "Ik ken '{entity}' als: {definition} Grappig genoeg komt dat bij jou vaak samen voor met '{associatie}'.",
                "{entity}, dat is: {definition} Dat associeer je hier trouwens opvallend vaak met '{associatie}'.",
                "Wat ik weet over '{entity}': {definition} Bij jou hoort daar meestal ook '{associatie}' bij.",
            ],
            "is_a_fallback": [
                "{entity} is een soort van {parent}.",
                "Ik ken geen exacte definitie van '{entity}', maar het is wel een soort {parent}.",
                "'{entity}' hoort bij de {parent}'s, voor zover ik weet.",
                "Zoveel weet ik: '{entity}' valt onder {parent}.",
                "Ik ken '{entity}' vooral als een soort {parent}.",
            ],
            "onbekend": [
                "Ik weet nog niet wat '{entity}' betekent.",
                "Hmm, '{entity}' ken ik nog niet.",
                "Dat woord, '{entity}', is nieuw voor mij.",
                "Ik heb nog geen idee wat '{entity}' betekent.",
                "'{entity}' zegt me nog niets, sorry.",
            ],
            "timing_hint": [
                "Trouwens, je vraagt hier meestal rond {uur}u naar.",
                "Opvallend: dit komt bij jou meestal rond {uur}u ter sprake.",
                "Je hebt hier trouwens een patroon in — meestal rond {uur}u.",
            ],
            # Activity-Aware Interaction (22 juli 2026, stap 7 -- variatie
            # in formulering, interruption_learning_roadmap.md Deel 2):
            # ruime sjabloonlijsten zodat Nova niet elke keer letterlijk
            # dezelfde zin herhaalt. _kies_variant() kiest willekeurig,
            # exact hetzelfde principe als "definitie"/"met_associatie"
            # hierboven -- 100% symbolisch, geen generatie.
            "interruption_vraag": [
                "Mag ik storen?",
                "Heb je even?",
                "Stoor ik als ik nu iets zeg?",
                "Even een momentje?",
                "Kan ik je heel even onderbreken?",
                "Heb je een minuutje?",
                "Is dit een goed moment?",
                "Zeg het maar als het niet uitkomt, maar heb je even?",
            ],
            "interruption_ga_door": [
                "Lukt het? Kan ik helpen?",
                "Hoe gaat het ermee?",
                "Alles onder controle?",
                "Kom je er goed uit?",
                "Nog steeds lekker bezig?",
                "Hoe staat het ervoor?",
                "Alles naar wens?",
            ],
        }

        # Vanaf welke PMI-score (0.0-1.0) vinden we een associatie sterk
        # genoeg om aan een antwoord toe te voegen? Layer 1 geeft in het
        # begin (weinig chat-geschiedenis) vaak zwakke/toevallige
        # associaties terug — die willen we NIET tonen, want dat zou
        # als ruis aanvoelen in plaats van als "Nova kent me".
        # 0.5 is bewust dezelfde drempel als Layer 1's eigen
        # min_confidence-conventie (zie word_associations_learner.py).
        self.MIN_ASSOCIATIE_SCORE = 0.5

        # Activity-Aware Interaction (interruption_learning_roadmap.md,
        # 22 juli 2026): vanaf welke confidence-score (interruption_
        # tracker.py) beschouwen we het patroon als "duidelijk genoeg"
        # om NIET meer te vragen? Symmetrisch gekozen, besproken met
        # Kevin: >= 0.8 is duidelijk genoeg om altijd door te gaan,
        # <= 0.2 duidelijk genoeg om altijd stil te blijven. Alles
        # daartussen (of te weinig data) blijft het voorzichtige
        # "vraag eerst"-gedrag, zelfde principe als
        # pattern_matcher.py's MIN_OBSERVATIES_VOOR_ANOMALIE.
        self.INTERRUPTION_CONFIDENCE_HOOG = 0.8
        self.INTERRUPTION_CONFIDENCE_LAAG = 0.2

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

    def _kies_variant(self, sjabloon_naam: str, **invulwaarden) -> str:
        """
        Kiest willekeurig één variant uit self.templates[sjabloon_naam]
        en vult die in met invulwaarden (bv. entity=..., definition=...).

        Dit is de centrale plek waar Fase 5's "meerdere natuurlijke
        varianten"-aanpak gebeurt — elke aanroeper (generate(),
        get_timing_hint()) hoeft zelf niet te weten dat er meerdere
        varianten bestaan, die roepen gewoon deze ene methode aan.

        BLIJFT 100% VAST/SYMBOLISCH: random.choice() kiest enkel WELKE
        van de vooraf geschreven zinnen gebruikt wordt — er wordt nooit
        een nieuwe zin gegenereerd of samengesteld die niet letterlijk
        al in self.templates staat.
        """
        varianten = self.templates[sjabloon_naam]
        gekozen = random.choice(varianten)
        return gekozen.format(**invulwaarden)

    def get_timing_hint(self, topic_naam: str) -> Optional[str]:
        """
        Layer 2 (pattern_matcher): geeft een timing-zinnetje terug
        voor een TOPIC (bv. "chess", "weather", "definitie" — de naam
        die intent_router.py doorgeeft via _emit_topic(), zonder het
        "topic_detected:"-voorvoegsel).

        SINDS DE LAYER 2-KOPPELING (na Fase 7): wordt nu ECHT gebruikt
        in generate(), via _voeg_timing_hint_toe(). Gebruikt daar het
        generieke topic "definitie" — zie _voeg_timing_hint_toe() voor
        de volledige uitleg waarom (geen per-woord-timing, wel
        eerlijke algemene timing over "wanneer stel je definitievragen").

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

        return self._kies_variant("timing_hint", uur=uur)

    def _voeg_timing_hint_toe(self, text: str, entity: str = "") -> str:
        """
        Koppelt get_timing_hint() aan generate() — dit was het
        "vergeten stuk" uit de originele Layer 4-roadmap (STAP 3 in
        het "HOE WERKT HET"-diagram).

        PER-WOORD-TIMING (uitbreiding, zie intent_router.py's route()):
        gebruikt nu het topic "definitie_<entity>" — hetzelfde
        woord-specifieke topic dat intent_router.py sinds deze
        uitbreiding publiceert via _emit_topic(f"definitie_{woord}").
        Layer 2 (pattern_matcher.py) telt élk "topic_detected:"-voorvoegsel
        al generiek mee (zie RELEVANTE_EVENT_TYPES-check daar), dus deze
        nieuwe, fijnmazigere topic-naam werkt zonder dat pattern_matcher.py
        zelf iets hoeft te weten of te wijzigen.

        Als 'entity' leeg is (defensief, zou niet mogen voorkomen bij een
        normale aanroep vanuit generate()) valt dit terug op het oude,
        generieke topic "definitie" — zodat dit nooit stil een
        AttributeError of lege topic-naam kan geven.

        Belangrijke eerlijkheidsgrens: dit blijft PER WOORD, niet per
        SENSE (zie Bug #10 in nova_state.md — "python" als slang vs.
        programmeertaal wordt hier niet uit elkaar gehouden). Dat is een
        apart, groter werkpunt (disambiguatie-laag), niet iets wat deze
        kleine uitbreiding oplost of pretendeert op te lossen.
        """
        topic_naam = f"definitie_{entity}" if entity else "definitie"
        hint = self.get_timing_hint(topic_naam)
        if hint:
            return f"{text} {hint}"
        return text

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
                text = self._kies_variant(
                    "met_associatie",
                    entity=entity,
                    definition=definition,
                    associatie=associatie_woord,
                )
                text = self._voeg_timing_hint_toe(text, entity=entity)
                return {
                    "text": text,
                    "confidence": 0.9,
                    "sources": ["semantic", "word_associations"],
                }

            text = self._kies_variant(
                "definitie", entity=entity, definition=definition
            )
            text = self._voeg_timing_hint_toe(text, entity=entity)
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
                text = self._kies_variant(
                    "is_a_fallback", entity=entity, parent=parents[0]
                )
                text = self._voeg_timing_hint_toe(text, entity=entity)
                return {
                    "text": text,
                    "confidence": 0.6,
                    "sources": ["semantic"],
                }

        # --- Stap 3: echt niets gevonden -> eerlijk toegeven ---
        # GEEN timing-hint hier: "ik weet het niet, trouwens je vraagt
        # hier vaak naar" zou een vreemde, ongepaste combinatie zijn.
        text = self._kies_variant("onbekend", entity=entity)
        return {
            "text": text,
            "confidence": 0.2,
            "sources": [],
        }

    def beslis_interruption_gedrag(self, activiteit: str) -> Dict:
        """
        Activity-Aware Interaction (interruption_learning_roadmap.md,
        22 juli 2026): beslist wat Nova moet doen zodra de tijdsdrempel
        voor een activiteit bereikt is. Raadpleegt interruption_tracker
        (Layer "Activity-Aware Interaction") voor de confidence-score
        van deze specifieke activiteit.

        Dit is PURE if/else op een geteld getal -- geen generatie, geen
        interpretatie van TOON of motivatie (zie interruption_learning_
        roadmap.md, sectie "Eerlijkheid"). session_watcher.py roept dit
        aan en VOERT de teruggegeven actie uit -- deze methode zelf
        publiceert niets op de EventBus, exact dezelfde scheiding als
        de rest van dit bestand (Layer 4 beslist/formuleert, andere
        modules handelen).

        Geeft een dict terug:
            {
                "actie": "vraag_eerst" | "ga_gewoon_door" | "blijf_stil",
                "tekst": str of None,
                "confidence": float of None,
            }

        - "vraag_eerst": te weinig observaties (has_enough_data ==
          False) OF confidence in de onzekere middenzone. Voorzichtig
          standaardgedrag, zoals de roadmap voorschrijft: "onvoldoende
          observaties -> val terug op voorzichtig gedrag: altijd eerst
          vragen". "tekst" bevat dan de vraag zelf.
        - "ga_gewoon_door": confidence >= INTERRUPTION_CONFIDENCE_HOOG.
          Nova hoeft niet meer te vragen, mag gewoon een korte,
          betrokken vervolgzin geven. "tekst" bevat die zin.
        - "blijf_stil": confidence <= INTERRUPTION_CONFIDENCE_LAAG.
          Nova zegt HELEMAAL NIETS -- "tekst" is dan None.
        """
        tracker = self.layers.get("interruption_tracker")

        if tracker is None or not tracker.has_enough_data(activiteit):
            return {
                "actie": "vraag_eerst",
                "tekst": self._kies_variant("interruption_vraag"),
                "confidence": None,
            }

        try:
            confidence = tracker.get_confidence(activiteit)
        except Exception:
            # Zelfde principe als bij Layer 1/2/3 hierboven: een
            # opzoekfout mag Nova's gedrag nooit laten crashen --
            # gewoon terugvallen op het voorzichtige standaardgedrag.
            confidence = None

        if confidence is None:
            return {
                "actie": "vraag_eerst",
                "tekst": self._kies_variant("interruption_vraag"),
                "confidence": None,
            }

        if confidence >= self.INTERRUPTION_CONFIDENCE_HOOG:
            return {
                "actie": "ga_gewoon_door",
                "tekst": self._kies_variant("interruption_ga_door"),
                "confidence": confidence,
            }

        if confidence <= self.INTERRUPTION_CONFIDENCE_LAAG:
            return {
                "actie": "blijf_stil",
                "tekst": None,
                "confidence": confidence,
            }

        # Middenzone: nog niet duidelijk genoeg naar één kant, blijf
        # bij het voorzichtige gedrag.
        return {
            "actie": "vraag_eerst",
            "tekst": self._kies_variant("interruption_vraag"),
            "confidence": confidence,
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