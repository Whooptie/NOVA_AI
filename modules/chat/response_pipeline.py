# modules/chat/response_pipeline.py

import random
import re

from core.nl_stopwoorden import STOPWOORDEN
from identity.personality.personality_engine import PersonalityEngine
from identity.emotion.emotion_engine import EmotionEngine
from identity.expression.tone_engine import ToneEngine
from modules.response_learning.variant_kiezer import kies_variant

# Auto-learn-filter (5 oktober 2026): simplemma's woordenboek als
# controle "is dit een echt Nederlands woord?" -- houdt typfouten
# (hyey, emercence) uit concepts.json. Pure opzoeking, geen ML.
# Optioneel: zonder simplemma valt enkel deze controle weg.
try:
    import simplemma
except ImportError:
    simplemma = None

# Woorden die in Layer 1 WEL mogen meetellen (staan dus niet in de
# gedeelde lijst), maar als concept enkel rommel zijn. "beter" is in
# Layer 1 bv. een beschermd woord.
AUTO_LEARN_EXTRA_STOPWOORDEN = frozenset({
    "hou", "houd", "houden", "gebruik", "gebruikt", "gebruiken",
    "beter", "anders", "laat", "daarnet", "normaal", "nova", "kevin",
})


class ResponsePipeline:
    """
    Fase 5 – centrale response-pipeline:
    intent → personality → emotion → tone → base_text
    """

    def __init__(self, event_bus, semantic_module=None):
        self.event_bus = event_bus
        self.semantic = semantic_module

        # Eigen stateful engines
        # event_bus meegeven aan PersonalityEngine (Layer 6, Fase 5):
        # nodig zodat update_state() "identity_state:updated" kan
        # publiceren, wat memory.py automatisch oppikt via zijn
        # bestaande wildcard-subscribe.
        self.personality = PersonalityEngine(event_bus=event_bus)
        self.emotion = EmotionEngine()
        self.tone_engine = ToneEngine()

                # Registratie zodat andere modules (bv. conversation_engine.py)
        # de actuele Layer 6-state kunnen opvragen via
        # event_bus.modules.get("personality"), net zoals dat al voor
        # context_manager (Layer 5) gebeurt. PersonalityEngine wordt
        # hier aangemaakt i.p.v. via module_loader.py, dus zonder deze
        # regel zou het nergens in event_bus.modules terechtkomen.
        event_bus.register_module("personality", self.personality)

        # Zelfde reden, nu ook voor EmotionEngine (nova_state.md punt 8,
        # koppeling met microlearning.py): zonder deze registratie kan
        # geen enkele andere module apply_trigger() aanroepen op DEZE
        # actieve emotion-instantie -- ze zouden anders per ongeluk een
        # eigen, aparte EmotionEngine() aanmaken met een eigen state,
        # los van wat de tone-pipeline hierboven al gebruikt.
        event_bus.register_module("emotion", self.emotion)

        # Voor nu: greeting + fallback + Layer 4 (definitie-antwoorden)
        event_bus.subscribe("intent_greeting", self.on_greeting)
        event_bus.subscribe("intent_fallback", self.on_fallback)
        event_bus.subscribe("layer4_response", self.on_layer4_response)

        # Sjablonen voor de generieke fallback ("ik snap dat niet").
        # Puur string-combinatie via random.choice(), geen generatie --
        # zelfde patroon als session_watcher.py, weather.py en
        # chess_engine.py. De "je zei: '...'"-toevoeging blijft apart
        # bestaan (zie on_fallback()), dit varieert enkel de kernzin.
        self._sjablonen_fallback = [
            "Ik weet nog niet goed hoe ik daarop moet antwoorden, maar ik leer graag bij.",
            "Dat ken ik nog niet, maar ik sta open om het te leren.",
            "Hier heb ik nog geen goed antwoord op, maar vertel gerust meer.",
            "Dat snap ik nog niet helemaal, maar ik onthoud het wel.",
            "Daar kom ik nog niet uit, maar ik leer er graag bij.",
        ]

    def _apply_emotion_trigger(self, trigger: str):
        try:
            self.emotion.apply_trigger(trigger, personality_engine=self.personality)
        except Exception:
            pass

    def _get_response_style(self):
        """
        Haalt Layer 5's response_style-advies op ("kort"/"normaal"/
        "uitgebreid") via context_manager, als die beschikbaar is.

        BELANGRIJK: dit bestand (response_pipeline.py) kent
        context_manager niet automatisch — het wordt nooit als
        argument doorgegeven aan ResponsePipeline.__init__(). We
        halen het daarom op via event_bus.modules (dezelfde manier
        waarop main.py bv. "zone" opvraagt), zodat we geen wijziging
        nodig hebben in module_loader.py of hoe deze klasse
        geïnitialiseerd wordt.

        Geeft "normaal" terug als context_manager (nog) niet
        beschikbaar is of er iets misgaat — nooit een crash, gewoon
        een neutrale, veilige standaardwaarde.
        """
        try:
            ctx_mgr = self.event_bus.modules.get("context_manager")
            if ctx_mgr is None:
                return "normaal"
            ctx = ctx_mgr.get_current()
            return ctx.get("response_style", "normaal")
        except Exception:
            return "normaal"

    # -------------------------
    # 1. Greeting
    # -------------------------
    def on_greeting(self, data, event_type=None):
        # Layer 6, stap 5 (17 juli 2026): "Kevin" i.p.v. het vage "jij"
        # als fallback — intent_router.py stuurt normaal altijd al een
        # sender mee via presence_detector.get_current_speaker(), dus
        # deze default wordt in de praktijk zelden bereikt, maar moet
        # wel consistent zijn met de rest van de aanspreekvorm-stijl.
        sender = data.get("sender", "Kevin")

        # 1) Emotion: excitement bij greeting
        self._apply_emotion_trigger("excitement")

        # 2) Tone genereren
        tone = self.tone_engine.generate_tone(self.personality, self.emotion)

        # 3) Basis-tekst (zonder emoji’s / flair)
        base = f"Hey {sender}, leuk dat je er bent"

        # 4) Stuur ruwe data naar pipeline_response
        self.event_bus.publish("pipeline_response", {
            "base_text": base,
            "tone": tone,
            "personality_style": self.personality.generate_response_style(),
            "emotion_state": self.emotion.state,
            "response_style": self._get_response_style()
        })

    # -------------------------
    # 1B. Layer 4 (definitie-antwoorden, incl. Wikipedia-vangnet)
    # -------------------------
    def on_layer4_response(self, data, event_type=None):
        """
        Neemt een AL KLARE tekst over van Layer 4 (response_engine.py)
        of van chat.py's Wikipedia-vangnet, en stuurt die enkel nog
        door de tone-verrijkingsstap (emotie -> tone -> expression_
        injector), zonder de tekst zelf te wijzigen.

        BELANGRIJK: dit verzint GEEN nieuwe tekst — 'base' hieronder
        is letterlijk wat Layer 4 (of het vangnet) al besliste. Deze
        methode voegt enkel Nova's stemming/expressie (emoji's,
        uitroeptekens, gestures) toe, net als bij greeting/fallback.
        """
        base = data.get("text", "")
        if not base:
            return

        # Geen vaste emotion-trigger hier (zoals "excitement" bij
        # greeting) — Layer 4-antwoorden zijn informatief van aard,
        # dus we laten Nova's HUIDIGE emotionele staat gewoon meespelen
        # via de tone-engine, zonder die kunstmatig te sturen.
        tone = self.tone_engine.generate_tone(self.personality, self.emotion)

        self.event_bus.publish("pipeline_response", {
            "base_text": base,
            "tone": tone,
            "personality_style": self.personality.generate_response_style(),
            "emotion_state": self.emotion.state,
            "response_style": self._get_response_style()
        })

    # -------------------------
    # 2. Fallback
    # -------------------------
    def on_fallback(self, data, event_type=None):
        user_text = (data.get("text") or "").strip()

        # Onbekende zelfstandige naamwoorden automatisch als "unknown"
        # opslaan, zodat Nova ze later kan herkennen bij teach/wiki.
        # Puur passief geheugensteuntje — GEEN betekenis-gok.
        self._auto_learn_from_sentence(user_text)

        tone = self.tone_engine.generate_tone(self.personality, self.emotion)

        # Eerst proberen: conversation_engine.py's contextuele
        # activiteit-observatie (Layer 5-data). Geeft None terug als
        # er geen bruikbare context is — dan valt dit terug op de
        # bestaande sjabloon-fallback. Zelfde beslispatroon als
        # intent_router.py's confidence-check bij response_engine.py.
        conv_engine = self.event_bus.modules.get("conversation_engine")
        base = None
        if conv_engine is not None:
            # Volgorde bewust: mood_observatie eerst, want een
            # overprikkelde/opvallende emotionele staat is doorgaans
            # betekenisvoller dan een activiteit-observatie. Beide
            # respecteren hetzelfde tijdvenster (_mag_opnieuw_
            # observeren()), dus er is nooit overlap.
            base = conv_engine.probeer_mood_observatie()
            if base is None:
                base = conv_engine.probeer_activiteit_observatie()

        if base is None:
            # Patroon-gebaseerde zin-reflectie (decompositie +
            # keyword-vangnet) -- geeft None terug als geen van
            # beide lagen iets herkende, dan valt dit gewoon door
            # naar de kale sjabloon-fallback hieronder.
            reflectie = self.event_bus.modules.get("fallback_reflectie")
            if reflectie is not None:
                base = reflectie.reflecteer(user_text)

        if base is None:
            response_style = self._get_response_style()
            base = kies_variant(
                self._sjablonen_fallback,
                sjabloon_naam="fallback_algemeen",
                event_bus=self.event_bus,
                variant_feedback_logger=self.event_bus.modules.get("variant_feedback_logger"),
                entity=None,
                response_style=response_style,
            )
            if user_text:
                base += f" Je zei: '{user_text}'."

        self.event_bus.publish("pipeline_response", {
            "base_text": base,
            "tone": tone,
            "personality_style": self.personality.generate_response_style(),
            "emotion_state": self.emotion.state,
            "response_style": self._get_response_style()
        })

    # -------------------------
    # 2B. Auto-learn onbekende woorden uit fallback-zinnen
    # -------------------------
    def _auto_learn_from_sentence(self, text: str):
        """
        Haalt zelfstandige naamwoorden uit een fallback-zin en slaat
        onbekende woorden op als 'unknown' via semantic.auto_learn().
        Puur passief geheugensteuntje -- GEEN betekenis-gok.

        Herzien (5 oktober 2026, data-oogst 1 oktober): het oude filter
        liet veel rommel door in concepts.json (wat, hoe, over, omdat,
        hey, debug, hyey, emercence, data\\layer0_gebruikt.jsonl,
        21-jarige). Oorzaken: een eigen korte stopwoordenlijst,
        splitsen op spaties, en semantic.detect_pos() die voor elk
        onbekend woord standaard "noun" teruggeeft. Nu, per woord:

        1. Tokeniseren zoals Layer 1: enkel reeksen letters.
        2. Minstens 3 letters.
        3. Niet in de gedeelde stopwoordenlijst (core/nl_stopwoorden.py)
           of AUTO_LEARN_EXTRA_STOPWOORDEN.
        4. Een echt Nederlands woord volgens simplemma's woordenboek
           (houdt typfouten buiten). Zonder simplemma: deze stap valt
           stil weg.
        4b. Geen vervoegde vorm op -e (nieuwe, grote, werkte): eindigt
           het woord op -e, en is simplemma's grondvorm anders en
           eindigt die zelf niet op -e, dan wordt het overgeslagen.
           Toegevoegd 5 oktober 2026 na live test ("nieuwe" glipte
           door). Grenzen: dubbelzinnige woorden als "ronde" mogen door.
        5. detect_pos() moet "noun" zeggen (filtert bekende werkwoorden).
        6. Nog geen concept.

        Bewust GEEN lemmatisering: dat zou onbekende naamwoorden soms in
        werkwoorden veranderen (fiets -> fietsen). Een iets te letterlijk
        opgeslagen concept ("betekenissen") is minder erg dan een fout.

        Bekende beperking: echte werkwoordsvormen die detect_pos() niet
        kent (bespreken, nadenken, bereikt) glippen nog door.
        """
        if not self.semantic or not text:
            return

        gezien = set()
        for woord in re.findall(r"[a-zà-ÿ]+", text.lower()):
            if woord in gezien:
                continue
            gezien.add(woord)

            if len(woord) < 3:
                continue
            if woord in STOPWOORDEN or woord in AUTO_LEARN_EXTRA_STOPWOORDEN:
                continue

            if simplemma is not None:
                try:
                    if not simplemma.is_known(woord, lang="nl"):
                        continue
                    # Vervoegde vorm op -e (nieuwe, grote, werkte)?
                    # De grondvorm wordt enkel gebruikt om te beoordelen,
                    # nooit om op te slaan (vergiet -> vergieten!).
                    grondvorm = simplemma.lemmatize(woord, lang="nl")
                    if (woord.endswith("e")
                            and grondvorm != woord
                            and not grondvorm.endswith("e")):
                        continue
                except Exception:
                    pass

            try:
                pos_guess = self.semantic.sense_engine.detect_pos(woord)
            except Exception:
                continue
            if pos_guess != "noun":
                continue

            try:
                if self.semantic.store.has_concept(woord):
                    continue
            except Exception:
                continue

            try:
                self.semantic.auto_learn(woord)
            except Exception:
                pass


def init_module(event_bus, semantic_module=None):
    rp = ResponsePipeline(event_bus, semantic_module=semantic_module)
    event_bus.publish("module_loaded", {"name": "response_pipeline"})
    return rp