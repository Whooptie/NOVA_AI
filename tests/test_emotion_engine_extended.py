from identity.emotion.emotion_engine import EmotionEngine
from identity.personality.personality_engine import PersonalityEngine


def print_section(title):
    print("\n" + "=" * 60)
    print("⭐ " + title)
    print("=" * 60)


def test_emotion_engine_extended():
    print_section("EXTENDED EMOTION ENGINE TEST GESTART")

    personality = PersonalityEngine()
    emotion = EmotionEngine()

    # ---------------------------------------------------------
    # 1. BASIS: excitement trigger
    # ---------------------------------------------------------
    trigger = "excitement"
    print_section(f"Trigger toepassen: {trigger}")
    emotion.apply_trigger(trigger, personality_engine=personality)

    print("Mood:", emotion.state["current_mood"])
    print("Intensity:", emotion.state["intensity"])
    print("Reaction:", emotion.state["last_reaction"])
    print("Overflow behavior:", emotion.state["overstimulation"]["last_overflow_behavior"])
    print("Overstimulation level:", emotion.state["overstimulation"]["level"])

    # ---------------------------------------------------------
    # 2. AFFECT
    # ---------------------------------------------------------
    print_section("Affect controleren")
    print("Affect valence:", emotion.state["affect"]["valence"])
    print("Affect warmte:", emotion.state["affect"]["warmte"])
    print("Affect spanning:", emotion.state["affect"]["spanning"])

    # ---------------------------------------------------------
    # 3. REGULATION
    # ---------------------------------------------------------
    print_section("Regulation controleren")
    print("Recovery speed:", emotion.state["regulation"]["recovery_speed"])
    print("Regulation strength:", emotion.state["regulation"]["regulation_strength"])
    print("Cooldown timer:", emotion.state["regulation"]["cooldown_timer"])

    # ---------------------------------------------------------
    # 4. SYNC
    # ---------------------------------------------------------
    print_section("Sync controleren")
    print("Sync with Kevin:", emotion.state["sync"]["sync_with_kevin"])
    print("Last sync event:", emotion.state["sync"]["last_sync_event"])

    # ---------------------------------------------------------
    # 5. DRAMATIC FLAIR
    # ---------------------------------------------------------
    print_section("Dramatic flair controleren")
    print("Active:", emotion.state["dramatic_flair"]["active"])
    print("Level:", emotion.state["dramatic_flair"]["level"])
    print("Last expression:", emotion.state["dramatic_flair"]["last_expression"])

    # ---------------------------------------------------------
    # 6. PERSONALITY STYLE OUTPUT
    # ---------------------------------------------------------
    print_section("Personality style output")
    style = personality.generate_response_style()
    print(style)

    print_section("🎉 EXTENDED TEST GESLAAGD!")


if __name__ == "__main__":
    test_emotion_engine_extended()
