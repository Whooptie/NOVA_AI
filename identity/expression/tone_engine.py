# identity/expression/tone_engine.py
import json
import os


class ToneEngine:
    def __init__(self):
        base = os.path.dirname(__file__)

        # Style profiles (worden later uitgebreid)
        style_path = os.path.join(base, "style_profiles.json")
        if os.path.exists(style_path):
            with open(style_path, "r", encoding="utf-8") as f:
                self.style_profiles = json.load(f)
        else:
            self.style_profiles = {}

        # Gesture profiles (optioneel)
        gesture_path = os.path.join(base, "gesture_profiles.json")
        if os.path.exists(gesture_path):
            with open(gesture_path, "r", encoding="utf-8") as f:
                self.gesture_profiles = json.load(f)
        else:
            self.gesture_profiles = {}

    # ---------------------------------------------------------
    #  GENERATE TONE
    # ---------------------------------------------------------
    def generate_tone(self, personality_engine, emotion_engine):
        """
        Combine personality + emotion → tone profile
        """

        mood = emotion_engine.state["current_mood"]
        intensity = emotion_engine.state["intensity"]
        flair = emotion_engine.state["dramatic_flair"]
        overstim = emotion_engine.state["overstimulation"]["level"]

        traits = personality_engine.traits

        # -----------------------------
        # BASE TONE (afgeleid van mood)
        # -----------------------------
        tone = self._tone_from_mood(mood, intensity)

        # -----------------------------
        # PERSONALITY MODIFIERS
        # -----------------------------
        tone = self._apply_personality_modifiers(tone, traits)

        # -----------------------------
        # DRAMATIC FLAIR
        # -----------------------------
        if flair["active"]:
            tone = self._apply_dramatic_flair(tone, flair)

        # -----------------------------
        # OVERSTIMULATION EFFECTS
        # -----------------------------
        tone = self._apply_overstimulation(tone, overstim)

        # -----------------------------
        # STYLE PROFILE (optioneel)
        # -----------------------------
        tone = self._apply_style_profile(tone)

        return tone

    # ---------------------------------------------------------
    #  MOOD → TONE
    # ---------------------------------------------------------
    def _tone_from_mood(self, mood, intensity):
        base = {
            "positief_speels": {
                "tone": "enthousiast",
                "pace": "snel" if intensity > 0.6 else "normaal",
                "expressiveness": 0.8 + intensity * 0.2
            },
            "focus": {
                "tone": "kortaf",
                "pace": "traag",
                "expressiveness": 0.2
            },
            "frustratie": {
                "tone": "geïrriteerd",
                "pace": "snel",
                "expressiveness": 0.9
            }
        }

        return base.get(mood, {
            "tone": "neutraal",
            "pace": "normaal",
            "expressiveness": 0.5
        })

    # ---------------------------------------------------------
    #  PERSONALITY MODIFIERS
    # ---------------------------------------------------------
    def _apply_personality_modifiers(self, tone, traits):
        impulsivity = traits.get("impulsivity", 0.5)
        warmth = traits.get("warmth", 0.5)

        # Impulsiviteit → snellere pacing + meer expressie
        tone["expressiveness"] += impulsivity * 0.2
        if impulsivity > 0.7:
            tone["pace"] = "snel"

        # Warmte → zachtere toon
        if warmth > 0.6 and tone["tone"] not in ["geïrriteerd"]:
            tone["tone"] = "warm"

        return tone

    # ---------------------------------------------------------
    #  DRAMATIC FLAIR
    # ---------------------------------------------------------
    def _apply_dramatic_flair(self, tone, flair):
        level = flair.get("level", 0.5)

        tone["expressiveness"] += level * 0.3

        if level > 0.6:
            tone["tone"] = "overdreven_enthousiast"

        return tone

    # ---------------------------------------------------------
    #  OVERSTIMULATION
    # ---------------------------------------------------------
    def _apply_overstimulation(self, tone, overstim):
        if overstim > 0.7:
            tone["pace"] = "chaotisch_snel"
            tone["tone"] = "overprikkeld"
            tone["expressiveness"] += 0.3

        return tone

    # ---------------------------------------------------------
    #  STYLE PROFILE (optioneel)
    # ---------------------------------------------------------
    def _apply_style_profile(self, tone):
        if not self.style_profiles:
            return tone

        key = f"{tone['tone']}_{tone['pace']}"
        print("STYLE KEY:", key)

        if key in self.style_profiles:
            tone.update(self.style_profiles[key])

        return tone

    