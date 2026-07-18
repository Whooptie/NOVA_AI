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
    def _inject_puberal(self, text: str, tone: dict, personality: dict) -> str:
        expressiveness = tone.get("expressiveness", 0.5)

        # Bugfix (17 juli 2026): "...4 maanden.!" -- een "!" werd
        # zomaar achter een tekst geplakt die al op "." (of een ander
        # leesteken) eindigde, wat een lelijk dubbel leesteken gaf.
        # Nu wordt een bestaand eindteken eerst gestript voor er een
        # "!" bijkomt, zodat het altijd een schone tekst blijft.

        # Layer 6: hoge impulsiviteit (personality["interrupts"] is True
        # bij traits["impulsivity"] > 0.7, zie
        # personality_engine.generate_response_style()) maakt Nova iets
        # sneller/directer op zinsniveau — een extra duwtje bovenop wat
        # expressiveness al doet, niet in de plaats ervan.
        if personality.get("interrupts") and expressiveness > 0.6:
            if not text.endswith("!"):
                text = text.rstrip(".!?") + "!"
            return text

        if expressiveness > 0.9:
            if not text.endswith("!"):
                text = text.rstrip(".!?") + "!"
        elif expressiveness < 0.3:
            text = text.rstrip("!.")

        return text

    # ---------------------------------------------------------
    # 3B. Layer 6: dramatic flair (personality_style["dramatic"])
    # ---------------------------------------------------------
    def _inject_dramatic_flair(self, text: str, personality: dict, response_style: str) -> str:
        """
        personality["dramatic"] komt uit
        personality_engine.generate_response_style() en is True zodra
        state["dramatic_flair_state"] > 0.5 (zie behavior_modifiers.py/
        personality_engine.py). Dit was tot nu toe dode data — hier
        krijgt het voor het eerst een echt, zichtbaar effect.

        BEWUST NIET toegepast bij response_style == "kort": Layer 5
        besliste dan al dat Kevin met iets anders bezig is, en extra
        flair zou daar net tegenin gaan.
        """
        if response_style == "kort":
            return text

        if personality.get("dramatic") and not text.endswith("!"):
            return text.rstrip(".!?") + "!"

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
        - response_style: Layer 5-advies ("kort"/"normaal"/"uitgebreid")
        """

        text = data.get("text", "")
        tone = data.get("tone", {})
        personality = data.get("personality", {})
        emotion = data.get("emotion", {})
        response_style = data.get("response_style", "normaal")

        # Layer 5: "kort" betekent Kevin is duidelijk met iets anders
        # bezig (bv. actief aan het coderen) — dan GEEN extra flair,
        # geen gestures, geen emoji's, ongeacht wat tone/personality
        # zouden toevoegen. Dit is de eerste plek waar response_style
        # ECHT iets doet, i.p.v. enkel berekend en doorgegeven te
        # worden (zie context_manager.py's eigen toelichting hierover).
        if response_style == "kort":
            text = text.rstrip("!")
            self.event_bus.publish("chat_response", {
                "text": text,
                "tone": tone,
                "personality": personality,
                "emotion": emotion,
                "response_style": response_style
            })
            return

        # 1) Puberale flair (nu ook Layer 6-bewust via personality)
        text = self._inject_puberal(text, tone, personality)

        # 1B) Dramatic flair (Layer 6, nieuw)
        text = self._inject_dramatic_flair(text, personality, response_style)

        # 2) Gestures
        text = self._inject_gestures(text, tone)

        # 3) Emoji’s
        text = self._inject_emojis(text, tone)

        # 4) Stuur finale tekst naar Nova
        self.event_bus.publish("chat_response", {
            "text": text,
            "tone": tone,
            "personality": personality,
            "emotion": emotion,
            "response_style": response_style
        })


def init_module(event_bus, semantic_module=None):
    injector = ExpressionInjector(event_bus)
    event_bus.publish("module_loaded", {"name": "expression_injector"})
    return injector
