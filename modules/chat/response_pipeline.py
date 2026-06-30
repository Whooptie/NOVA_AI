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


def init_module(event_bus, semantic_module=None):
    rp = ResponsePipeline(event_bus, semantic_module=semantic_module)
    event_bus.publish("module_loaded", {"name": "response_pipeline"})
    return rp