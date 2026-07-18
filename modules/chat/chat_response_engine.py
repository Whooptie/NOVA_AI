# modules/chat/chat_response_engine.py

class ChatResponseEngine:
    """
    Bouwt het uiteindelijke antwoord:
    - ontvangt base_text + tone + personality + emotion
    - doet zelf geen emoji/flair
    - stuurt door naar ExpressionInjector
    """

    def __init__(self, event_bus, semantic_module=None):
        self.event_bus = event_bus
        self.semantic = semantic_module

        # Luistert naar pipeline-events
        event_bus.subscribe("pipeline_response", self.on_pipeline_response)

    def on_pipeline_response(self, data, event_type=None):
        """
        Data bevat:
        - base_text: ruwe tekst van pipeline
        - tone: tone-engine output
        - personality_style: personality-engine output
        - emotion_state: emotion-engine state
        """

        base = data.get("base_text", "")
        tone = data.get("tone", {})
        personality_style = data.get("personality_style", {})
        emotion_state = data.get("emotion_state", {})
        response_style = data.get("response_style", "normaal")

        # Geen extra flair hier – dat doet ExpressionInjector
        self.event_bus.publish("expression_inject", {
            "text": base,
            "tone": tone,
            "personality": personality_style,
            "emotion": emotion_state,
            "response_style": response_style
        })


def init_module(event_bus, semantic_module=None):
    engine = ChatResponseEngine(event_bus, semantic_module)
    event_bus.publish("module_loaded", {"name": "chat_response_engine"})
    return engine
