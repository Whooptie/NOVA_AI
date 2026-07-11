# identity/emotion/emotion_engine.py
import json
import os
import time


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
        # OVERSTIMULATION: TIJD-DECAY
        # -----------------------------
        # Voordat we eventueel opnieuw ophogen: kijk hoeveel tijd er
        # verstreken is sinds de vorige trigger, en laat het niveau
        # geleidelijk zakken. Zo "herstelt" Nova vanzelf tijdens
        # stiltes, i.p.v. voor altijd op hetzelfde niveau te blijven.
        self._apply_overstimulation_decay()

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
            # Trigger die Nova opjaagt (bv. excitement) → niveau stijgt
            self.state["overstimulation"]["last_overflow_behavior"] = rule["overflow_behavior"]
            self.state["overstimulation"]["level"] = self._clamp(
                self.state["overstimulation"]["level"] + 0.15
            )
        else:
            # Trigger zonder overflow_behavior (bv. confusion, focus
            # zonder piek) → kleine, natuurlijke afkoeling. Dit is de
            # interactie-gebaseerde decay: niet elke trigger jaagt
            # Nova op, sommige laten haar juist even bijkomen.
            self.state["overstimulation"]["level"] = self._clamp(
                self.state["overstimulation"]["level"] - 0.05
            )

        # Tijdstip van deze trigger onthouden voor de volgende
        # tijd-decay-berekening.
        self.state["overstimulation"]["last_trigger_timestamp"] = time.time()

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
    #  OVERSTIMULATION: TIJD-DECAY
    # ---------------------------------------------------------
    def _apply_overstimulation_decay(self):
        """
        Laat overstimulation.level geleidelijk zakken op basis van
        hoeveel tijd er verstreken is sinds de vorige trigger.
        Wordt aangeroepen VOOR de nieuwe trigger verwerkt wordt, dus
        hij werkt op de "oude" tijd -> "nu"-periode, los van wat de
        huidige trigger zelf nog gaat doen.

        Waarom hier en niet als losse achtergrond-timer: Nova's
        hoofdlus is nu nog synchroon (blocking input() in main.py,
        zie bekende architecturale blokkade) - een losse
        achtergrondthread zou wel kunnen, maar dan zou hij ook de
        JSON-file moeten wegschrijven op een moment dat apply_trigger
        dat ook doet, wat een race condition kan geven. Berekenen bij
        elke trigger is de veilige, eenvoudige aanpak die past bij
        Nova's huidige architectuur.
        """
        last_ts = self.state["overstimulation"].get("last_trigger_timestamp")
        if last_ts is None:
            # Eerste trigger ooit sinds opstarten, of nog nooit
            # opgeslagen -> niets om te decayen.
            return

        verstreken_seconden = time.time() - last_ts
        if verstreken_seconden <= 0:
            return

        verstreken_minuten = verstreken_seconden / 60.0
        decay_per_minuut = self.state["overstimulation"].get("decay_per_minute", 0.05)

        daling = verstreken_minuten * decay_per_minuut
        if daling <= 0:
            return

        self.state["overstimulation"]["level"] = self._clamp(
            self.state["overstimulation"]["level"] - daling
        )

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