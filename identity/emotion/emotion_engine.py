# identity/emotion/emotion_engine.py
import json
import os


class EmotionEngine:
    def __init__(self):
        base = os.path.dirname(__file__)

        rules_path = os.path.join(base, "emotion_rules.json")
        state_path = os.path.join(base, "emotion_state.json")

        with open(rules_path, "r", encoding="utf-8") as f:
            self.rules = json.load(f)

        with open(state_path, "r", encoding="utf-8") as f:
            self.state = json.load(f)

        self._state_path = state_path

    # ---------------------------------------------------------
    #  APPLY TRIGGER
    # ---------------------------------------------------------
    def apply_trigger(self, trigger: str, personality_engine=None):
        if trigger not in self.rules["mood_shifts"]:
            return

        rule = self.rules["mood_shifts"][trigger]

        # -----------------------------
        # MOOD + INTENSITY
        # -----------------------------
        self.state["current_mood"] = rule.get("target_mood", self.state["current_mood"])
        self.state["intensity"] = self._clamp(
            self.state["intensity"] + rule.get("intensity_delta", 0.0)
        )

        # -----------------------------
        # AFFECT
        # -----------------------------
        if "reaction" in rule:
            self.state["last_reaction"] = rule["reaction"]

        # -----------------------------
        # ENERGY / EXPRESSIVENESS / CHAOS
        # (door personality_engine verwerkt)
        # -----------------------------
        if personality_engine is not None:
            personality_engine.update_state(trigger)

        # -----------------------------
        # OVERSTIMULATION
        # -----------------------------
        if "overflow_behavior" in rule:
            self.state["overstimulation"]["last_overflow_behavior"] = rule["overflow_behavior"]
            self.state["overstimulation"]["level"] = self._clamp(
                self.state["overstimulation"]["level"] + 0.15
            )

        # -----------------------------
        # RECOVERY HINT
        # -----------------------------
        self.state["last_recovery_hint"] = rule.get("recovery_hint", None)

        # -----------------------------
        # SYNC
        # -----------------------------
        self._apply_sync(trigger)

        # -----------------------------
        # DRAMATIC FLAIR
        # -----------------------------
        self._apply_dramatic_flair(trigger)

        # -----------------------------
        # SAVE
        # -----------------------------
        self._save()

    # ---------------------------------------------------------
    #  SYNC LOGICA
    # ---------------------------------------------------------
    def _apply_sync(self, trigger):
        sync_rules = self.rules.get("emotional_sync", {})
        sync_state = self.state.get("sync", {})

        if not sync_rules:
            return

        # voorbeeld: als Kevin positief is → energie omhoog
        if trigger == "excitement":
            sync_state["last_sync_event"] = "kevin_positive"
        elif trigger == "frustration":
            sync_state["last_sync_event"] = "kevin_negative"

        self.state["sync"] = sync_state

    # ---------------------------------------------------------
    #  DRAMATIC FLAIR
    # ---------------------------------------------------------
    def _apply_dramatic_flair(self, trigger):
        flair_rules = self.rules.get("dramatic_flair_rules", {})
        flair_state = self.state.get("dramatic_flair", {})

        if not flair_rules.get("enabled", False):
            return

        conditions = flair_rules.get("conditions", [])
        if trigger in conditions:
            flair_state["active"] = True
            flair_state["level"] = flair_rules.get("intensity", 0.5)
            flair_state["last_expression"] = flair_rules["expressions"][0]
        else:
            flair_state["active"] = False

        self.state["dramatic_flair"] = flair_state

    # ---------------------------------------------------------
    #  CLAMP
    # ---------------------------------------------------------
    def _clamp(self, value):
        return max(0.0, min(1.0, value))

    # ---------------------------------------------------------
    #  SAVE
    # ---------------------------------------------------------
    def _save(self):
        with open(self._state_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)