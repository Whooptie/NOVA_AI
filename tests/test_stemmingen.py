# tests/test_stemmingen.py
"""
Stemmingen "verveeld" en "gepikeerd" (identity/expression/tone_engine.py).

Ze worden afgeleid van de LAATSTE emotie-trigger (kilte / frustration), enkel
kort na die trigger, enkel bij een brutale Nova (bravoure) en nooit boven
focus, irritatie of overprikkeling. De emotie-engine zelf blijft ongemoeid.
"""
import time

import pytest

from identity.expression.tone_engine import ToneEngine


class NepPersoonlijkheid:
    def __init__(self, bravoure=0.7):
        self.traits = {"bravoure": bravoure, "impulsivity": 0.42, "social_warmth": 0.54}


class NepEmotie:
    def __init__(self, trigger, leeftijd_seconden=5, mood="positief_speels", overstim=0.1):
        self.state = {
            "current_mood": mood,
            "intensity": 0.5,
            "last_trigger": trigger,
            "dramatic_flair": {"active": False, "level": 0.0},
            "overstimulation": {
                "level": overstim,
                "last_trigger_timestamp": time.time() - leeftijd_seconden,
            },
        }


def _tone(trigger, bravoure=0.7, **kw):
    return ToneEngine().generate_tone(NepPersoonlijkheid(bravoure), NepEmotie(trigger, **kw))


def test_kilte_geeft_verveeld():
    tone = _tone("kilte")
    assert tone["tone"] == "verveeld"
    assert tone["pace"] == "traag"
    assert tone["emoji_style"] == ["🙄"]


def test_frustration_geeft_gepikeerd():
    tone = _tone("frustration")
    assert tone["tone"] == "gepikeerd"
    assert tone["emoji_style"]  # een eigen profiel, niet leeg


def test_andere_triggers_veranderen_niets():
    for trigger in ("excitement", "interest", "waardering", None):
        assert _tone(trigger)["tone"] not in ("verveeld", "gepikeerd")


def test_stemming_verloopt_na_tien_minuten():
    assert _tone("kilte", leeftijd_seconden=601)["tone"] != "verveeld"
    assert _tone("kilte", leeftijd_seconden=599)["tone"] == "verveeld"


def test_zonder_tijdstip_geen_stemming():
    emotie = NepEmotie("kilte")
    emotie.state["overstimulation"].pop("last_trigger_timestamp")
    tone = ToneEngine().generate_tone(NepPersoonlijkheid(), emotie)
    assert tone["tone"] != "verveeld"


def test_lage_bravoure_geen_stemming():
    assert _tone("kilte", bravoure=0.4)["tone"] != "verveeld"


def test_overprikkeling_wint():
    assert _tone("kilte", overstim=0.9)["tone"] == "overprikkeld"


def test_focus_en_irritatie_blijven_zoals_ze_zijn():
    assert _tone("kilte", mood="focus")["tone"] == "kortaf"
    assert _tone("kilte", mood="frustratie")["tone"] == "geïrriteerd"


def test_elke_stemming_heeft_een_profiel_zonder_fallback_melding(capsys):
    for trigger in ("kilte", "frustration"):
        _tone(trigger)
    assert "geen enkel profiel gevonden" not in capsys.readouterr().out