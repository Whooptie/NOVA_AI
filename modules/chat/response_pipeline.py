# modules/chat/response_pipeline.py

from identity.personality.personality_engine import PersonalityEngine
from identity.emotion.emotion_engine import EmotionEngine
from identity.expression.tone_engine import ToneEngine


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

        # Voor nu: greeting + fallback + Layer 4 (definitie-antwoorden)
        event_bus.subscribe("intent_greeting", self.on_greeting)
        event_bus.subscribe("intent_fallback", self.on_fallback)
        event_bus.subscribe("layer4_response", self.on_layer4_response)

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

        base = (
            "Ik weet nog niet goed hoe ik daarop moet antwoorden, "
            "maar ik leer graag bij."
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
        Bewust beperkt tot zelfstandige naamwoorden — anders leert Nova
        ook lidwoorden, voorzetsels en werkwoorden aan als "concept",
        wat concepts.json zou vervuilen met ruis.
        """
        if not self.semantic or not text:
            return

        # Simpele stopwoordenlijst — woorden die nooit een zelfstandig
        # naamwoord zijn, ook al zou detect_pos ze verkeerd gokken.
        stopwoorden = {
            "ik", "jij", "je", "hij", "zij", "ze", "we", "wij", "jullie",
            "hun", "hem", "haar", "mij", "me", "ons", "onze", "u",
            "mijn", "jouw", "zijn", "uw",
            "de", "het", "een", "en", "of", "maar", "want", "dus",
            "van", "voor", "naar", "met", "bij", "op", "in", "uit",
            "is", "ben", "bent", "was", "waren", "wordt", "worden",
            "heb", "hebt", "heeft", "hebben", "had", "hadden",
            "niet", "wel", "ook", "nog", "al", "dat", "die", "dit", "deze",
            "hou", "houd", "houden", "gebruik", "gebruikt", "gebruiken"
        }

        woorden = text.lower().split()

        for woord in woorden:
            schoon = woord.strip(".,!?;:")
            if not schoon or len(schoon) <= 2:
                continue
            if schoon in stopwoorden:
                continue

            try:
                pos_guess = self.semantic.sense_engine.detect_pos(schoon)
            except Exception:
                continue

            if pos_guess != "noun":
                continue

            # Al gekend? Dan niets doen.
            if self.semantic.store.has_concept(schoon):
                continue

            try:
                self.semantic.auto_learn(schoon)
            except Exception:
                pass


def init_module(event_bus, semantic_module=None):
    rp = ResponsePipeline(event_bus, semantic_module=semantic_module)
    event_bus.publish("module_loaded", {"name": "response_pipeline"})
    return rp