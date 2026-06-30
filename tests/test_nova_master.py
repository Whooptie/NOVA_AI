from identity.blueprint.loader import load_identity_blueprint
from identity.personality.personality_engine import PersonalityEngine
from identity.emotion.emotion_engine import EmotionEngine
from identity.expression.tone_engine import ToneEngine


def print_section(title):
    print("\n" + "=" * 70)
    print("⭐ " + title)
    print("=" * 70)


def test_nova_master():
    print_section("NOVA MASTER TEST GESTART")

    # ---------------------------------------------------------
    # 1. BLUEPRINT LADEN
    # ---------------------------------------------------------
    print_section("Blueprint laden")
    blueprint = load_identity_blueprint()
    print("Naam:", blueprint.get("name"))
    print("Waarden:", blueprint.get("values"))
    print("Energie:", blueprint.get("energy_profile"))

    # ---------------------------------------------------------
    # 2. PERSONALITY ENGINE
    # ---------------------------------------------------------
    print_section("Personality Engine initialiseren")
    personality = PersonalityEngine()
    print("Traits geladen:", personality.traits)

    # ---------------------------------------------------------
    # 3. EMOTION ENGINE
    # ---------------------------------------------------------
    print_section("Emotion Engine initialiseren")
    emotion = EmotionEngine()
    print("Start mood:", emotion.state["current_mood"])
    print("Start intensity:", emotion.state["intensity"])

    # ---------------------------------------------------------
    # 4. TRIGGER TESTEN
    # ---------------------------------------------------------
    trigger = "excitement"
    print_section(f"Trigger toepassen: {trigger}")
    emotion.apply_trigger(trigger, personality_engine=personality)

    print("Nieuwe mood:", emotion.state["current_mood"])
    print("Intensity:", emotion.state["intensity"])
    print("Affect:", emotion.state["affect"])
    print("Overstimulation:", emotion.state["overstimulation"])
    print("Dramatic flair:", emotion.state["dramatic_flair"])
    print("Sync:", emotion.state["sync"])

    # ---------------------------------------------------------
    # 5. PERSONALITY STYLE OUTPUT
    # ---------------------------------------------------------
    print_section("Personality style output")
    style = personality.generate_response_style()
    print(style)

    # ---------------------------------------------------------
    # 6. TONE ENGINE
    # ---------------------------------------------------------
    print_section("Tone Engine genereren")
    tone_engine = ToneEngine()
    tone = tone_engine.generate_tone(personality, emotion)
    print("Tone output:", tone)

    # ---------------------------------------------------------
    # 7. GESTURE PROFILE
    # ---------------------------------------------------------
    print_section("Gesture profile ophalen")
    gesture_key = tone.get("gesture_profile")
    gestures = tone_engine.gesture_profiles.get(gesture_key, {})
    print("Gebruikte gesture profile:", gesture_key)
    print("Gesture data:", gestures)

    # ---------------------------------------------------------
    # 8. EINDE
    # ---------------------------------------------------------
    print_section("🎉 NOVA MASTER TEST GESLAAGD!")
    print("Alle lagen werken samen: Blueprint → Personality → Emotion → Tone → Gestures")


if __name__ == "__main__":
    test_nova_master()