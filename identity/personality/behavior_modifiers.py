# identify/personality/behavior_modifiers.py
class BehaviorModifiers:
    def __init__(self, traits, state):
        self.traits = traits
        self.state = state

    def apply_energy_modulation(self):
        base = self.traits["energy_level"]
        chaos = self.traits["chaotic_variability"]

        self.state["current_energy"] = (
            base * 0.7 +
            chaos * 0.3 +
            self.state["current_energy"] * 0.2
        )

    def apply_impulsivity(self):
        self.state["impulsivity_modulation"] = self.traits["impulsivity"]

    def apply_dramatic_flair(self):
        self.state["dramatic_flair_state"] = self.traits["dramatic_flair"]
