# identity/personality/personality_engine.py
import json
import os
from identity.blueprint.loader import load_identity_blueprint
from identity.personality.behavior_modifiers import BehaviorModifiers


class PersonalityEngine:
    def __init__(self):
        # blueprint (statisch)
        self.blueprint = load_identity_blueprint()

        # state (dynamisch) uit identity/personality/identity_state.json
        base = os.path.dirname(__file__)
        state_path = os.path.join(base, "identity_state.json")
        with open(state_path, "r", encoding="utf-8") as f:
            self.state = json.load(f)
        self._state_path = state_path

        # traits
        traits_path = os.path.join(base, "traits.json")
        with open(traits_path, "r", encoding="utf-8") as f:
            self.traits = json.load(f)

        # emotion rules
        emotion_path = os.path.join(os.path.dirname(base), "emotion", "emotion_rules.json")
        with open(emotion_path, "r", encoding="utf-8") as f:
            self.emotion_rules = json.load(f)

        # behavior modifiers
        self.modifiers = BehaviorModifiers(self.traits, self.state)

    def update_state(self, trigger: str):
        if trigger not in self.emotion_rules["mood_shifts"]:
            return

        rules = self.emotion_rules["mood_shifts"][trigger]

        if "energy_boost" in rules:
            self.state["current_energy"] += rules["energy_boost"]
        if "energy_drop" in rules:
            self.state["current_energy"] -= rules["energy_drop"]

        if "expressiveness_boost" in rules:
            self.state["expressive_intensity"] += rules["expressiveness_boost"]

        if "chaos_variability" in rules:
            self.state["behavior_modulation_state"]["chaotic_variability_state"] += rules["chaos_variability"]

        self.state["emotion_engine_state"]["last_trigger"] = trigger
        self.state["emotion_engine_state"]["last_reaction"] = rules.get("reaction", None)
        self.state["emotion_engine_state"]["last_recovery"] = rules.get("recovery_hint", None)

        self._clamp_state()
        self._save_state()

    def generate_response_style(self):
        energy = self.state["current_energy"]
        expressiveness = self.state["expressive_intensity"]
        impulsivity = self.traits["impulsivity"]

        return {
            "pace": "snel" if energy > 0.8 else "normaal",
            "tone": "enthousiast" if expressiveness > 0.7 else "warm",
            "interrupts": impulsivity > 0.7,
            "dramatic": self.state["dramatic_flair_state"] > 0.5
        }

    def _clamp_state(self):
        self.state["current_energy"] = max(0.0, min(1.0, self.state["current_energy"]))
        self.state["expressive_intensity"] = max(0.0, min(1.0, self.state["expressive_intensity"]))
        self.state["behavior_modulation_state"]["chaotic_variability_state"] = max(
            0.0,
            min(1.0, self.state["behavior_modulation_state"]["chaotic_variability_state"])
        )

    def _save_state(self):
        with open(self._state_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)