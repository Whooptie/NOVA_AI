# identity/expression/tone_engine.py
import json
import os
import time

# Debug-print van de gekozen stijl-sleutel (bv. "STYLE KEY: warm_normaal")
# bij ELK antwoord. Stond vroeger altijd aan en verscheen daardoor ook
# midden in Nova's chatvenster, na elk proactief bericht (30 sept 2026).
# Zet op True als je tijdelijk wil zien welke stijl gekozen wordt.
TOON_STYLE_DEBUG = False


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
        # STEMMING NA EEN TRIGGER (verveeld / gepikeerd)
        # -----------------------------
        tone = self._apply_stemming_na_trigger(tone, emotion_engine.state, traits)

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
        warmth = traits.get("social_warmth", 0.5)

        # Impulsiviteit → meer expressie
        tone["expressiveness"] += impulsivity * 0.2

        # Tempo hangt aan ENERGIE, niet aan impulsiviteit: anders zet een
        # hoge impulsiviteit élke toon op "snel" en verdwijnen de
        # _traag/_stil-profielen, inclusief de kalme focus-modus.
        if traits.get("energy_level", 0.5) > 0.60:
            tone["pace"] = "snel"

        # Warmte → zachtere toon
        if warmth > 0.6 and tone["tone"] not in ["geïrriteerd"]:
            tone["tone"] = "warm"

        # Bravoure → brutale toon (de "brutaal_*"-profielen werden nog nooit gekozen).
        # Enkel vanuit een neutrale basis; focus/irritatie/warm blijven ongemoeid.
        if tone["tone"] == "neutraal" and traits.get("bravoure", 0.5) >= 0.65:
            tone["tone"] = "brutaal"

        return tone

    # ---------------------------------------------------------
    #  STEMMING NA EEN TRIGGER (verveeld / gepikeerd)
    # ---------------------------------------------------------
    STEMMING_DUUR_SECONDEN = 600
    TRIGGER_NAAR_STEMMING = {
        "kilte": "verveeld",         # Kevin klinkt koud/kortaf -> Nova haakt af
        "frustration": "gepikeerd",  # frustratie-signaal -> Nova wordt bits
    }
    STEMMING_RESPECTEERT = ("kortaf", "geïrriteerd")

    def _apply_stemming_na_trigger(self, tone, emotion_state, traits):
        """
        De laatste emotie-trigger bepaalt, zolang hij recent is, of Nova "verveeld"
        of "gepikeerd" klinkt. Enkel bij een brutale Nova (bravoure) en nooit boven
        focus/irritatie. Overprikkeling wint nog steeds van alles.
        """
        if traits.get("bravoure", 0.5) < 0.65:
            return tone

        stemming = self.TRIGGER_NAAR_STEMMING.get(emotion_state.get("last_trigger"))
        if stemming is None:
            return tone

        tijdstip = (emotion_state.get("overstimulation") or {}).get("last_trigger_timestamp")
        if not isinstance(tijdstip, (int, float)):
            return tone
        if time.time() - tijdstip > self.STEMMING_DUUR_SECONDEN:
            return tone

        if tone.get("tone") in self.STEMMING_RESPECTEERT:
            return tone

        tone["tone"] = stemming
        if stemming == "verveeld":
            tone["pace"] = "traag"
            tone["expressiveness"] = min(tone.get("expressiveness", 0.5), 0.35)
        else:
            tone["expressiveness"] = max(tone.get("expressiveness", 0.5), 0.7)
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
        if TOON_STYLE_DEBUG:
            print("STYLE KEY:", key)

        if key in self.style_profiles:
            tone.update(self.style_profiles[key])
            self._apply_gesture_data(tone)
            return tone

        # Fallback (Layer 6, 17 juli 2026): geen enkele nieuwe
        # mood/pace-combinatie mag nog stil zonder emoji_style/
        # gesture_profile blijven zoals "warm_snel" dat was vóór
        # style_profiles.json aangevuld werd. Als de EXACTE key
        # ontbreekt (bv. een combinatie die Kevin later nog niet
        # expliciet heeft ingevuld), zoeken we de EERSTE bestaande
        # key die met dezelfde 'tone' begint — beter een profiel dat
        # qua stemming klopt maar qua pace niet exact overeenkomt,
        # dan helemaal geen profiel.
        prefix = f"{tone['tone']}_"
        for bestaande_key, profiel in self.style_profiles.items():
            if bestaande_key.startswith(prefix):
                if TOON_STYLE_DEBUG:
                    print(f"STYLE KEY FALLBACK: '{key}' bestaat niet, gebruik '{bestaande_key}'")
                tone.update(profiel)
                return tone

        # Nog steeds niets gevonden (compleet nieuwe 'tone'-waarde,
        # nog nergens gedefinieerd) — dan pas echt niets toepassen,
        # net als voorheen.
        print(f"STYLE KEY: '{key}' — geen enkel profiel gevonden, ook niet via fallback")
        return tone

    def _apply_gesture_data(self, tone):
        """
        Layer 6, gesture-koppeling (17 juli 2026): tot nu toe werd
        gesture_profiles.json wel ingeladen (self.gesture_profiles),
        maar NERGENS gekoppeld aan de uiteindelijke tone-dictionary —
        expression_injector.py's _inject_gestures() zocht altijd naar
        tone["gesture_data"], die nooit gevuld werd, dus die stap deed
        in de praktijk nooit iets. Dit vult 'm nu, op basis van de
        gesture_profile-key die _apply_style_profile() hierboven al
        in tone['gesture_profile'] gezet heeft.

        BEWUST GEEN fallback zoals bij _apply_style_profile(): als de
        exacte gesture-key niet bestaat, blijft tone['gesture_data']
        gewoon leeg — expression_injector.py's eigen "geen data? dan
        geen tekst-hint"-logica vangt dat al netjes op, een fallback
        zou hier enkel onnodige complexiteit toevoegen.
        """
        gesture_key = tone.get("gesture_profile")
        if not gesture_key or not self.gesture_profiles:
            return

        if gesture_key in self.gesture_profiles:
            tone["gesture_data"] = self.gesture_profiles[gesture_key]

    