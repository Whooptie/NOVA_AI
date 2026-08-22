# test_emotion_engine_last_trigger.py
"""
Regressietest voor de last_trigger-bug, live ontdekt op 22 augustus
2026 tijdens het testen van de nieuwe microlearning.py-koppeling
(nova_state.md punt 8).

BUG: EmotionEngine.apply_trigger() werkte self.state["last_trigger"]
nergens bij -- enkel last_reaction/last_recovery_hint kregen een
update. Viel niet op zolang "excitement" (via een groet) de ENIGE
trigger-bron was (last_trigger toonde toevallig altijd de juiste
waarde). Zodra frustration/waardering/kilte ook triggerden, bleef
last_trigger permanent op "excitement" hangen.

Isolatie: EmotionEngine laadt in __init__() emotion_rules.json en
emotion_state.json van schijf (os.path.join(base, ...)) -- geen
injecteerbaar pad, dus we monkeypatchen __init__() zelf, zelfde
patroon als bij ContradictionChecker/PatternMatcher (zie nova_state.md,
"__init__() I/O-patroon"). We bouwen self.rules/self.state/
self._state_path handmatig op, MET DEZELFDE STRUCTUUR als de echte
emotion_rules.json/emotion_state.json, i.p.v. de echte bestanden te
lezen.
"""

import pytest
from identity.emotion.emotion_engine import EmotionEngine


# ---------------------------------------------------------------------
# Fixture: een EmotionEngine-instantie zonder I/O, met een kleine,
# gecontroleerde set regels/state -- zelfde vorm als de echte
# emotion_rules.json/emotion_state.json, maar in-memory.
# ---------------------------------------------------------------------

@pytest.fixture
def engine(tmp_path):
    obj = EmotionEngine.__new__(EmotionEngine)  # __init__() overslaan (I/O)

    obj.rules = {
        "mood_shifts": {
            "excitement": {
                "energy_boost": 0.15,
                "chaos_variability": 0.05,
                "reaction": "kleine_glimlach_alertere_blik",
                "overflow_behavior": "iets_sneller_pratend",
            },
            "waardering": {
                "energy_boost": 0.08,
                "expressiveness_boost": 0.08,
                "reaction": "warme_glimlach",
                "recovery_hint": None,
            },
            "frustration": {
                "energy_boost": 0.05,
                "expressiveness_boost": 0.05,
                "reaction": "droge_opmerking",
                "recovery_hint": "rustig_blijven",
            },
            "kilte": {
                "energy_drop": 0.05,
                "expressiveness_boost": -0.05,
                "reaction": "neutrale_blik",
                "recovery_hint": "even_afstand_nemen",
            },
        },
        "emotional_sync": {"sync_with_kevin": 0.55, "sync_with_others": 0.20},
        "dramatic_flair_rules": {"enabled": False},
    }

    obj.state = {
        "current_mood": "positief_speels",
        "intensity": 0.5,
        "last_trigger": None,
        "last_reaction": None,
        "last_recovery_hint": None,
        "overstimulation": {
            "level": 0.06,
            "threshold": 0.75,
            "signs_active": [],
            "last_overflow_behavior": None,
            "last_trigger_timestamp": None,
            "decay_per_minute": 0.10,
        },
        "sync": {},
        "dramatic_flair": {"active": False, "level": 0.0, "last_expression": None},
    }

    obj._state_path = tmp_path / "emotion_state_test.json"

    return obj


# ---------------------------------------------------------------------
# De regressietest zelf
# ---------------------------------------------------------------------

def test_last_trigger_wordt_bijgewerkt_bij_elke_aanroep(engine):
    """
    Kern van de bug: na meerdere ACHTEREENVOLGENDE, VERSCHILLENDE
    triggers, moet last_trigger telkens de MEEST RECENTE trigger
    tonen -- niet blijven hangen op de eerst-ooit-aangeroepen trigger.
    """
    engine.apply_trigger("excitement")
    assert engine.state["last_trigger"] == "excitement"

    engine.apply_trigger("waardering")
    assert engine.state["last_trigger"] == "waardering", (
        "last_trigger bleef op 'excitement' hangen na een 'waardering'-"
        "trigger -- dit is exact de live-ontdekte bug van 22 augustus 2026."
    )

    engine.apply_trigger("frustration")
    assert engine.state["last_trigger"] == "frustration"

    engine.apply_trigger("kilte")
    assert engine.state["last_trigger"] == "kilte"


def test_last_reaction_blijft_ook_correct_zoals_voorheen(engine):
    """
    Bewaakt dat de FIX (last_trigger toevoegen) het al-werkende
    last_reaction-gedrag niet per ongeluk verstoort.
    """
    engine.apply_trigger("waardering")
    assert engine.state["last_reaction"] == "warme_glimlach"

    engine.apply_trigger("frustration")
    assert engine.state["last_reaction"] == "droge_opmerking"


def test_onbekende_trigger_wijzigt_last_trigger_niet(engine):
    """
    apply_trigger() geeft vroegtijdig terug bij een trigger die niet in
    rules["mood_shifts"] voorkomt (zie de "if trigger not in ...: return"
    -- de eerste regel van de methode). last_trigger mag dan NIET
    gewijzigd worden, want er gebeurt verder ook niets anders.
    """
    engine.apply_trigger("waardering")
    assert engine.state["last_trigger"] == "waardering"

    engine.apply_trigger("onbekende_trigger_xyz")
    assert engine.state["last_trigger"] == "waardering", (
        "Een onbekende trigger mag last_trigger niet overschrijven "
        "-- apply_trigger() had hier al vroeg moeten stoppen."
    )