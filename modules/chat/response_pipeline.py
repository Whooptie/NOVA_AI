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
        self.personality = PersonalityEngine()
        self.emotion = EmotionEngine()
        self.tone_engine = ToneEngine()

        # Voor nu: alleen greeting + fallback overnemen
        event_bus.subscribe("intent_greeting", self.on_greeting)
        event_bus.subscribe("intent_fallback", self.on_fallback)

    def _apply_emotion_trigger(self, trigger: str):
        try:
            self.emotion.apply_trigger(trigger, personality_engine=self.personality)
        except Exception:
            pass

    # -------------------------
    # 1. Greeting
    # -------------------------
    def on_greeting(self, data, event_type=None):
        sender = data.get("sender", "jij")

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
            "emotion_state": self.emotion.state
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
            "emotion_state": self.emotion.state
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