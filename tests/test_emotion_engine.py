from identity.emotion.emotion_engine import EmotionEngine
from identity.personality.personality_engine import PersonalityEngine

def test_emotion_engine():
    print("🔍 Emotion engine test gestart...")

    personality = PersonalityEngine()
    emotion = EmotionEngine()

    trigger = "excitement"
    emotion.apply_trigger(trigger, personality_engine=personality)

    print("✅ Trigger toegepast:", trigger)
    print("Huidige mood:", emotion.state["current_mood"])
    print("Intensiteit:", emotion.state["intensity"])
    print("Laatste reactie:", emotion.state["last_reaction"])

    style = personality.generate_response_style()
    print("🎭 Personality style output:", style)

    print("🎉 Test geslaagd!")


if __name__ == "__main__":
    test_emotion_engine()