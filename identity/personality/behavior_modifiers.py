# identify/personality/behavior_modifiers.py
class BehaviorModifiers:
    def __init__(self, traits, state):
        self.traits = traits
        self.state = state

    def apply_energy_modulation(self):
        """
        Bugfix (17 juli 2026): de oorspronkelijke gewichten (0.7 + 0.3
        + 0.2 = 1.2) telden op tot BOVEN 1.0, waardoor deze berekening
        bij hoge trait-waarden (Kevin's energy_level=0.92,
        chaotic_variability=0.85) altijd naar de bovengrens clampte —
        en die geclampte 1.0 voedde zichzelf weer terug in de volgende
        ronde, een zelfversterkende val waar current_energy nooit meer
        uit kon zakken. Gefixt door de 3 gewichten een eerlijk gewogen
        gemiddelde te laten vormen (samen exact 1.0), zodat het
        resultaat altijd binnen het bereik van de invoerwaarden zelf
        blijft, ongeacht welke trait-waarden Kevin later nog instelt.
        """
        base = self.traits["energy_level"]
        chaos = self.traits["chaotic_variability"]

        self.state["current_energy"] = (
            base * 0.5 +
            chaos * 0.2 +
            self.state["current_energy"] * 0.3
        )

    def apply_impulsivity(self):
        self.state["impulsivity_modulation"] = self.traits["impulsivity"]

    def apply_dramatic_flair(self):
        self.state["dramatic_flair_state"] = self.traits["dramatic_flair"]
