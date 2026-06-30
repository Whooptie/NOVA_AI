# modules/chat/expression_injector.py

class ExpressionInjector:
    """
    Zet tone + gestures + personality flair om naar expressieve tekst.
    Dit is de laatste stap in de Fase‑5 pipeline.
    """

    def __init__(self, event_bus):
        self.event_bus = event_bus

        # Luistert naar ChatResponseEngine output
        event_bus.subscribe("expression_inject", self.on_expression_inject)

    # ---------------------------------------------------------
    # 1. Emoji-injectie
    # ---------------------------------------------------------
    def _inject_emojis(self, text: str, tone: dict) -> str:
        emojis = tone.get("emoji_style") or []
        if not emojis:
            return text

        return text + " " + " ".join(emojis[:3])

    # ---------------------------------------------------------
    # 2. Gesture-injectie
    # ---------------------------------------------------------
    def _inject_gestures(self, text: str, tone: dict) -> str:
        gesture_key = tone.get("gesture_profile")
        gestures = tone.get("gesture_data") or {}

        if not gesture_key or not gestures:
            return text

        gesture_text = gestures.get("text_hint")
        if gesture_text:
            return f"{text} {gesture_text}"

        return text

    # ---------------------------------------------------------
    # 3. Puberale flair
    # ---------------------------------------------------------
    def _inject_puberal(self, text: str, tone: dict) -> str:
        expressiveness = tone.get("expressiveness", 0.5)

        if expressiveness > 0.9:
            if not text.endswith("!"):
                text += "!"
        elif expressiveness < 0.3:
            text = text.rstrip("!.")

        return text

    # ---------------------------------------------------------
    # 4. Finale injectie
    # ---------------------------------------------------------
    def on_expression_inject(self, data, event_type=None):
        """
        Ontvangt:
        - text: basistekst
        - tone: tone-engine output
        - personality: personality style
        - emotion: emotion state
        """

        text = data.get("text", "")
        tone = data.get("tone", {})
        personality = data.get("personality", {})
        emotion = data.get("emotion", {})

        # 1) Puberale flair
        text = self._inject_puberal(text, tone)

        # 2) Gestures
        text = self._inject_gestures(text, tone)

        # 3) Emoji’s
        text = self._inject_emojis(text, tone)

        # 4) Stuur finale tekst naar Nova
        self.event_bus.publish("chat_response", {
            "text": text,
            "tone": tone,
            "personality": personality,
            "emotion": emotion
        })


def init_module(event_bus, semantic_module=None):
    injector = ExpressionInjector(event_bus)
    event_bus.publish("module_loaded", {"name": "expression_injector"})
    return injector
