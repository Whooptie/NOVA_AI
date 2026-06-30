from identity.personality.personality_engine import PersonalityEngine
from identity.emotion.emotion_engine import EmotionEngine
from identity.expression.tone_engine import ToneEngine


def print_section(title):
    print("\n" + "=" * 60)
    print("⭐ " + title)
    print("=" * 60)


def test_tone_engine():
    print_section("TONE ENGINE TEST GESTART")

    personality = PersonalityEngine()
    emotion = EmotionEngine()
    tone_engine = ToneEngine()

    # ---------------------------------------------------------
    # 1. BASIS: excitement trigger
    # ---------------------------------------------------------
    trigger = "excitement"
    print_section(f"Trigger toepassen: {trigger}")
    emotion.apply_trigger(trigger, personality_engine=personality)

    # ---------------------------------------------------------
    # 2. TONE GENEREREN
    # ---------------------------------------------------------
    print_section("Tone genereren op basis van personality + emotion")
    tone = tone_engine.generate_tone(personality, emotion)
    print("Tone output:", tone)

    # ---------------------------------------------------------
    # 3. STYLE PROFILE CHECK
    # ---------------------------------------------------------
    print_section("Style profile controleren")
    print("Tone:", tone.get("tone"))
    print("Pace:", tone.get("pace"))
    print("Expressiveness:", tone.get("expressiveness"))
    print("Pitch:", tone.get("pitch"))
    print("Volume:", tone.get("volume"))
    print("Pacing variation:", tone.get("pacing_variation"))
    print("Intonation:", tone.get("intonation"))
    print("Filler words:", tone.get("filler_words"))
    print("Emoji style:", tone.get("emoji_style"))
    print("Gesture profile:", tone.get("gesture_profile"))

    # ---------------------------------------------------------
    # 4. GESTURE PROFILE CHECK
    # ---------------------------------------------------------
    print_section("Gesture profile ophalen")
    gesture_key = tone.get("gesture_profile")
    gestures = tone_engine.gesture_profiles.get(gesture_key, {})
    print("Gebruikte gesture profile:", gesture_key)
    print("Gesture data:", gestures)

    # ---------------------------------------------------------
    # 5. PERSONALITY STYLE OUTPUT
    # ---------------------------------------------------------
    print_section("Personality style output")
    style = personality.generate_response_style()
    print(style)

    print_section("🎉 TONE ENGINE TEST GESLAAGD!")


if __name__ == "__main__":
    test_tone_engine()
