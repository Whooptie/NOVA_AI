# identity/personality/personality_engine.py
import json
import os
from identity.blueprint.loader import load_identity_blueprint
from identity.personality.behavior_modifiers import BehaviorModifiers


class PersonalityEngine:
    def __init__(self, event_bus=None):
        # Layer 6, Fase 5 (Integration Layer, "identity_state → memory"):
        # event_bus wordt hier NIEUW meegegeven, zodat update_state()
        # straks een event kan publiceren zodra Nova's stemming/energie
        # verandert. memory.py (core/memory.py) subscribet al op "*"
        # (event_bus.subscribe("*", self.on_event)) en slaat AUTOMATISCH
        # alles op wat gepubliceerd wordt — er is dus GEEN wijziging
        # nodig in memory.py zelf, enkel hier een nieuw event publiceren.
        #
        # event_bus=None blijft toegestaan (bv. voor losse tests van
        # PersonalityEngine zonder volledige Nova-opstart) — in dat
        # geval wordt er gewoon niets gepubliceerd, geen crash.
        self.event_bus = event_bus

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

        # Layer 6, Fase 6 onderdeel 5 (17 juli 2026): live-koppeling
        # met microlearning.py. Zonder dit zou een trait-verschuiving
        # wel op schijf terechtkomen (microlearning.py schrijft naar
        # hetzelfde traits.json), maar PersonalityEngine's eigen
        # self.traits — die al bij __init__() is ingelezen en sindsdien
        # enkel in het geheugen leeft — zou dat nooit weten, dus Nova's
        # gedrag zou pas na een herstart van main.py meebewegen.
        #
        # event_bus kan hier None zijn (bv. losse tests) — dan gewoon
        # geen subscribe, geen crash, precies zoals bij
        # _publish_state_update() eerder in dit bestand.
        if self.event_bus is not None:
            self.event_bus.subscribe("trait_shifted", self._on_trait_shifted)

    def _on_trait_shifted(self, data, event_type=None):
        """
        Houdt self.traits (in-memory) synchroon zodra microlearning.py
        een trait daadwerkelijk laat verschuiven. We lezen hier BEWUST
        NIET het hele traits.json opnieuw in (dat zou een onnodige
        schijf-operatie zijn voor elke verschuiving, en een race
        condition riskeren als microlearning.py het bestand op dat
        moment nog aan het wegschrijven is) — we passen enkel de ene,
        specifieke trait aan met de waarde die microlearning.py zelf
        al berekend en gevalideerd heeft (binnen de min/max-grenzen
        uit adaptive_rules.json).
        """
        try:
            trait_naam = data.get("trait")
            nieuwe_waarde = data.get("nieuwe_waarde")
            if trait_naam is not None and nieuwe_waarde is not None:
                self.traits[trait_naam] = nieuwe_waarde
        except Exception:
            pass

    def update_state(self, trigger: str):
        if trigger not in self.emotion_rules["mood_shifts"]:
            return

        rules = self.emotion_rules["mood_shifts"][trigger]

        if "energy_boost" in rules:
            self.state["current_energy"] += rules["energy_boost"]
        if "energy_drop" in rules:
            self.state["current_energy"] -= rules["energy_drop"]

        # Bugfix (17 juli 2026, vervolg op de apply_energy_modulation()-
        # gewichtenfix): energy_boost/energy_drop hierboven clampten
        # nooit zelf — dat gebeurde pas helemaal aan het einde via
        # _clamp_state(). Vroeger was dat onschadelijk (de te-hoge
        # tussenwaarde werd simpelweg pas aan het eind teruggezet).
        # Sinds apply_energy_modulation() ECHT wordt aangeroepen,
        # rekent die met deze tussenwaarde als invoer — een tussen-
        # waarde van bv. 1.30 (0.9 + energy_boost 0.40) leverde daar
        # nog steeds >1.0 op, en bleef dus telkens tegen de bovengrens
        # plakken. Met deze tussentijdse clamp krijgt
        # apply_energy_modulation() altijd een eerlijke, al-begrensde
        # waarde te verwerken, en kan het evenwicht (~0.90 bij Kevin's
        # huidige traits) zich ook bij herhaalde triggers stabiliseren
        # in plaats van steeds opnieuw naar 1.0 te worden geduwd.
        self.state["current_energy"] = max(0.0, min(1.0, self.state["current_energy"]))

        if "expressiveness_boost" in rules:
            self.state["expressive_intensity"] += rules["expressiveness_boost"]

        if "chaos_variability" in rules:
            self.state["behavior_modulation_state"]["chaotic_variability_state"] += rules["chaos_variability"]

        self.state["emotion_engine_state"]["last_trigger"] = trigger
        self.state["emotion_engine_state"]["last_reaction"] = rules.get("reaction", None)
        self.state["emotion_engine_state"]["last_recovery"] = rules.get("recovery_hint", None)

        # Layer 6, laatste stuk (17 juli 2026): BehaviorModifiers werd
        # in __init__() al aangemaakt (self.modifiers), maar zijn 3
        # methodes werden nooit ergens aangeroepen — traits.json's
        # impulsivity/dramatic_flair/energy_level hadden dus GEEN
        # invloed op identity_state.json, enkel de vaste JSON-waarden
        # golden. Nu wordt de state bij elke trigger herberekend op
        # basis van de traits, VOOR de clamp hieronder (belangrijk:
        # apply_energy_modulation()'s som (0.7+0.3+0.2=1.2×) kan anders
        # tijdelijk boven 1.0 uitkomen — _clamp_state() vangt dit op).
        self.modifiers.apply_energy_modulation()
        self.modifiers.apply_impulsivity()
        self.modifiers.apply_dramatic_flair()

        self._clamp_state()
        self._save_state()
        self._publish_state_update(trigger)

    def _publish_state_update(self, trigger: str):
        """
        Layer 6, Fase 5: publiceert "identity_state:updated" telkens
        Nova's stemming/energie/impulsiviteit verandert. memory.py
        vangt dit AUTOMATISCH op via zijn bestaande wildcard-subscribe
        (event_bus.subscribe("*", ...)) en slaat het net als elk ander
        event op in interactions.jsonl/interactions.db — "identity_
        state:updated" staat NIET in memory.py's ignore_types, dus
        hoeft daar niets voor aangepast te worden.

        We sturen enkel een COMPACTE samenvatting mee (niet de volledige
        self.state-dictionary) — de relevante, doorzoekbare velden voor
        Kevin om later op terug te kunnen zoeken (bv. "wanneer was Nova
        overprikkeld"), zonder de hele geneste identity_state.json-
        structuur 1-op-1 te dupliceren in memory's opslag.

        Faalt dit ooit (event_bus is None, of een onverwachte fout) —
        dan gewoon stilzwijgend niets doen. Dit mag NOOIT de rest van
        update_state() laten crashen; het opslaan van identity_state.json
        zelf (_save_state(), hierboven al gebeurd) is de belangrijke
        stap, dit is puur een extra, niet-kritieke logging-stap erbovenop.
        """
        if self.event_bus is None:
            return

        try:
            self.event_bus.publish("identity_state:updated", {
                "trigger": trigger,
                "current_mood": self.state.get("current_mood"),
                "current_energy": self.state.get("current_energy"),
                "expressive_intensity": self.state.get("expressive_intensity"),
                "impulsivity_modulation": self.state.get("impulsivity_modulation"),
                "dramatic_flair_state": self.state.get("dramatic_flair_state"),
                "overstimulation_level": self.state.get("overstimulation_level"),
            })
        except Exception:
            pass

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