# test_microlearning_emotion_koppeling.py
"""
Test voor nova_state.md punt 8: MicroLearning._verwerk_signaal() moet
nu ook emotion_engine.apply_trigger() aanroepen via event_bus.modules
("personality"/"emotion"), bovenop de bestaande trait-verschuiving.

Isolatie-aanpak (zelfde patroon als test_variant_feedback_logger.py,
zie nova_state.md): een DummyEventBus als lokale fixture, GEEN echte
JSON-bestanden aangeraakt. We testen niet de hele MicroLearning-klasse
opnieuw (dat gebeurt elders al, of zou apart moeten), we isoleren
ENKEL de nieuwe koppelmethode zelf.
"""

import pytest


# ---------------------------------------------------------------------
# Nep-objecten, geen echte JSON-bestanden of echte engines nodig
# ---------------------------------------------------------------------

class DummyEventBus:
    """
    Minimalistische nep-EventBus. We hebben hier geen publish/subscribe
    nodig (MicroLearning wordt niet via een event getriggerd in deze
    test, we roepen de methode direct aan) -- enkel .modules, want
    daar haalt _apply_emotion_trigger_indien_van_toepassing() de
    "personality"/"emotion"-instanties vandaan.
    """
    def __init__(self):
        self.modules = {}

    def register_module(self, naam, instantie):
        self.modules[naam] = instantie


class DummyPersonalityEngine:
    """Staat model voor de echte PersonalityEngine -- we hoeven hier
    niets van de echte state/traits te laden, apply_trigger() gebruikt
    dit object enkel als doorgeef-argument."""
    pass


class DummyEmotionEngine:
    """
    Vangt elke apply_trigger()-aanroep op zodat de test kan verifiëren
    MET WELKE trigger-naam die precies gebeurde -- dat is het hele
    punt van deze test, niet wat emotion_engine.py daar intern verder
    mee doet (dat wordt door emotion_engine.py's eigen tests gedekt,
    voor zover die bestaan).
    """
    def __init__(self):
        self.aangeroepen_triggers = []

    def apply_trigger(self, trigger, personality_engine=None):
        self.aangeroepen_triggers.append(trigger)


# ---------------------------------------------------------------------
# Minimale kopie van de nieuwe logica uit microlearning.py
# ---------------------------------------------------------------------
# BELANGRIJK, zelfde beperking als toegelicht bij eerdere testrondes
# in dit project (zie nova_state.md, test_bridge_query.py's eerste
# versie): dit is een GEÏSOLEERDE KOPIE van de nieuwe mapping/methode,
# niet de echte MicroLearning-klasse zelf (die heeft I/O in __init__()
# -- laadt 6 JSON-bestanden + een pickle-model bij constructie, dus
# zou monkeypatch of tmp_path-fixtures vereisen om veilig te
# instantiëren). Voor een eerste, snelle verificatie van ENKEL de
# mapping-logica is dat hier bewust nog niet gedaan. Een volgende stap
# (zie opmerking onderaan dit bestand) zou dit tegen de ECHTE klasse
# moeten herhalen, met tmp_path voor alle 6 databestanden.

_SIGNAAL_NAAR_EMOTION_TRIGGER = {
    "frustratie": "frustration",
    "interesse": "interest",
    "verwarring": "confusion",
    "focus": "focus",
    "waardering": "waardering",
    "kilte": "kilte",
}


def apply_emotion_trigger_indien_van_toepassing(event_bus, signaal):
    trigger = _SIGNAAL_NAAR_EMOTION_TRIGGER.get(signaal)
    if not trigger:
        return

    try:
        personality = event_bus.modules.get("personality")
        emotion = event_bus.modules.get("emotion")
        if personality is None or emotion is None:
            return
        emotion.apply_trigger(trigger, personality_engine=personality)
    except Exception:
        pass


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------

@pytest.fixture
def event_bus():
    bus = DummyEventBus()
    bus.register_module("personality", DummyPersonalityEngine())
    bus.register_module("emotion", DummyEmotionEngine())
    return bus


# ---------------------------------------------------------------------
# Tests: elk signaal -> juiste trigger
# ---------------------------------------------------------------------

@pytest.mark.parametrize("signaal,verwachte_trigger", [
    ("frustratie", "frustration"),
    ("interesse", "interest"),
    ("verwarring", "confusion"),
    ("focus", "focus"),
    ("waardering", "waardering"),
    ("kilte", "kilte"),
])
def test_signaal_roept_juiste_trigger_aan(event_bus, signaal, verwachte_trigger):
    apply_emotion_trigger_indien_van_toepassing(event_bus, signaal)

    emotion = event_bus.modules["emotion"]
    assert emotion.aangeroepen_triggers == [verwachte_trigger]


def test_onbekend_signaal_roept_niets_aan(event_bus):
    """
    "neutraal" (of eender welk ander onbekend signaal) staat niet in
    de mapping -- er mag dan GEEN trigger aangeroepen worden.
    """
    apply_emotion_trigger_indien_van_toepassing(event_bus, "neutraal")

    emotion = event_bus.modules["emotion"]
    assert emotion.aangeroepen_triggers == []


def test_ontbrekende_personality_of_emotion_crasht_niet():
    """
    Als "personality" of "emotion" nog niet geregistreerd is in
    event_bus.modules (bv. vroeg in de opstartvolgorde), mag dit
    NOOIT crashen -- zelfde beschermende try/except-stijl als de rest
    van microlearning.py (bv. on_raw_message()).
    """
    lege_bus = DummyEventBus()  # geen modules geregistreerd

    # Mag geen exception gooien:
    apply_emotion_trigger_indien_van_toepassing(lege_bus, "frustratie")


def test_alleen_personality_ontbreekt(event_bus):
    """Randgeval: emotion wel aanwezig, personality niet."""
    del event_bus.modules["personality"]

    apply_emotion_trigger_indien_van_toepassing(event_bus, "interesse")

    emotion = event_bus.modules["emotion"]
    assert emotion.aangeroepen_triggers == []


def test_alleen_emotion_ontbreekt(event_bus):
    """Randgeval: personality wel aanwezig, emotion niet."""
    del event_bus.modules["emotion"]

    # Mag niet crashen, en er is geen emotion-object om op te
    # controleren -- de afwezigheid van een crash IS de test.
    apply_emotion_trigger_indien_van_toepassing(event_bus, "interesse")


def test_emotion_apply_trigger_faalt_intern_crasht_niet(event_bus):
    """
    Als emotion.apply_trigger() zelf een onverwachte fout gooit (bv.
    een kapotte emotion_rules.json), mag dat de aanroeper nooit laten
    crashen -- de try/except in de echte microlearning.py-methode
    vangt dit op.
    """
    class KapotteEmotionEngine:
        def apply_trigger(self, trigger, personality_engine=None):
            raise RuntimeError("simuleer een onverwachte fout")

    event_bus.modules["emotion"] = KapotteEmotionEngine()

    # Mag geen exception laten doorsijpelen:
    apply_emotion_trigger_indien_van_toepassing(event_bus, "frustratie")


# ---------------------------------------------------------------------
# Nog NIET gedekt door deze test (bewust, zie ook nova_state.md's
# "Nog open, bewust niet gedekt"-sectie voor hetzelfde soort eerlijke
# scoping):
#
# - De ECHTE MicroLearning-klasse zelf, met tmp_path voor alle 6
#   bestanden (rules/metrics/mapping/traits/model/uncertain) --
#   vereist eerst uitzoeken of __init__()'s I/O monkeypatch-baar is
#   zonder de bestaande, al-werkende trait-tests te verstoren.
# - emotion_rules.json's nieuwe "waardering"/"kilte"-regels zelf
#   (energy_boost/expressiveness_boost-waarden) -- dat is gedrag van
#   emotion_engine.py, niet van deze koppeling, en hoort dus bij
#   emotion_engine.py's eigen tests (indien die bestaan).
# - response_pipeline.py's nieuwe event_bus.register_module("emotion",
#   ...) -- puur een registratie-regel, geen aparte testbare logica.
# ---------------------------------------------------------------------