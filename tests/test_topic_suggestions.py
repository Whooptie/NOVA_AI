"""
Tests voor TopicSuggestions (modules/knowledge/topic_suggestions.py),
punt 7 van nova_state.md's "Volgende stappen" (13 augustus 2026).

We testen hier de KERNLOGICA (check_suggesties()) volledig in isolatie:
pattern_matcher en context_manager worden als lichte stubs meegegeven
(zelfde soort aanpak als DummyEventBus elders in de testsuite), zodat
we niet afhankelijk zijn van hun echte, zwaardere implementaties.

Isolatie van de state-file: get_project_root() kennen we niet exact
(niet in deze upload-set), dus we monkeypatchen self.state_pad na
constructie naar tmp_path -- dat is de kleinste aanname die nog steeds
volledige schrijf/lees-isolatie van data/topic_suggestion_state.json
garandeert.
"""

import json
from datetime import datetime

import pytest

from modules.knowledge.topic_suggestions import TopicSuggestions, init_module


class DummyEventBus:
    """Vangt publish()-aanroepen op zodat we kunnen controleren of/wat
    er gepubliceerd werd, zonder een echte EventBus nodig te hebben."""

    def __init__(self):
        self.gepubliceerd = []

    def publish(self, event_type, data):
        self.gepubliceerd.append((event_type, data))

    def subscribe(self, event_type, callback):
        pass


class StubPatternMatcher:
    """Simuleert is_pattern_active() met een vast, door de test
    ingesteld antwoord per event_type -- geen echte patroondata nodig."""

    def __init__(self, actieve_event_types=None, gooi_exceptie_voor=None):
        self.actieve_event_types = actieve_event_types or set()
        self.gooi_exceptie_voor = gooi_exceptie_voor or set()

    def is_pattern_active(self, event_type):
        if event_type in self.gooi_exceptie_voor:
            raise RuntimeError("gesimuleerde fout")
        return event_type in self.actieve_event_types


class StubContextManager:
    """Simuleert can_interrupt() met een vast, door de test ingesteld
    antwoord."""

    def __init__(self, mag_onderbreken=True):
        self.mag_onderbreken = mag_onderbreken

    def can_interrupt(self):
        return self.mag_onderbreken


@pytest.fixture
def event_bus():
    return DummyEventBus()


def _maak_topic_suggestions(event_bus, tmp_path, pattern_matcher=None, context_manager=None):
    """
    Bouwt een TopicSuggestions-instantie en herleidt state_pad naar
    tmp_path, zodat data/topic_suggestion_state.json nooit echt
    aangeraakt wordt. Zie module-docstring hierboven voor de reden
    waarom dit via monkeypatch gebeurt i.p.v. een save_path-parameter
    (die bestaat niet in de huidige __init__-signature).
    """
    instance = TopicSuggestions(event_bus, pattern_matcher, context_manager)
    instance.state_pad = tmp_path / "topic_suggestion_state.json"
    instance._laatst_voorgesteld = {}  # opnieuw leeg, state_pad bestond nog niet
    return instance


class TestCheckSuggestiesGeenPatternMatcher:
    def test_zonder_pattern_matcher_gebeurt_er_niets(self, event_bus, tmp_path):
        instance = _maak_topic_suggestions(event_bus, tmp_path, pattern_matcher=None)

        instance.check_suggesties()

        assert event_bus.gepubliceerd == []


class TestCheckSuggestiesActiefPatroon:
    def test_actief_patroon_en_mag_onderbreken_geeft_suggestie(self, event_bus, tmp_path):
        pm = StubPatternMatcher(actieve_event_types={"topic_detected:chess"})
        cm = StubContextManager(mag_onderbreken=True)
        instance = _maak_topic_suggestions(event_bus, tmp_path, pm, cm)

        instance.check_suggesties()

        assert len(event_bus.gepubliceerd) == 1
        event_type, data = event_bus.gepubliceerd[0]
        assert event_type == "layer4_response"
        assert "schaken" in data["text"]
        assert "u —" in data["text"]  # bevat het huidige uur

    def test_niet_actief_patroon_geeft_geen_suggestie(self, event_bus, tmp_path):
        pm = StubPatternMatcher(actieve_event_types=set())  # niets actief
        cm = StubContextManager(mag_onderbreken=True)
        instance = _maak_topic_suggestions(event_bus, tmp_path, pm, cm)

        instance.check_suggesties()

        assert event_bus.gepubliceerd == []


class TestCheckSuggestiesTimingGate:
    def test_can_interrupt_false_blokkeert_suggestie(self, event_bus, tmp_path):
        pm = StubPatternMatcher(actieve_event_types={"topic_detected:chess"})
        cm = StubContextManager(mag_onderbreken=False)
        instance = _maak_topic_suggestions(event_bus, tmp_path, pm, cm)

        instance.check_suggesties()

        assert event_bus.gepubliceerd == []

    def test_ontbrekende_context_manager_blokkeert_niet(self, event_bus, tmp_path):
        """
        Zelfde 'nooit stiller dan voorheen'-principe als session_watcher.py/
        emergence_engine.py: als context_manager None is (bv. laadvolgorde-
        probleem), mag dat de suggestie niet tegenhouden.
        """
        pm = StubPatternMatcher(actieve_event_types={"topic_detected:chess"})
        instance = _maak_topic_suggestions(event_bus, tmp_path, pm, context_manager=None)

        instance.check_suggesties()

        assert len(event_bus.gepubliceerd) == 1


class TestCheckSuggestiesSpamPreventie:
    def test_zelfde_topic_zelfde_uur_wordt_niet_herhaald(self, event_bus, tmp_path):
        pm = StubPatternMatcher(actieve_event_types={"topic_detected:chess"})
        cm = StubContextManager(mag_onderbreken=True)
        instance = _maak_topic_suggestions(event_bus, tmp_path, pm, cm)

        instance.check_suggesties()
        instance.check_suggesties()  # zelfde cyclus, zelfde uur

        assert len(event_bus.gepubliceerd) == 1

    def test_state_wordt_correct_weggeschreven(self, event_bus, tmp_path):
        pm = StubPatternMatcher(actieve_event_types={"topic_detected:chess"})
        cm = StubContextManager(mag_onderbreken=True)
        instance = _maak_topic_suggestions(event_bus, tmp_path, pm, cm)

        instance.check_suggesties()

        assert instance.state_pad.exists()
        with open(instance.state_pad, "r", encoding="utf-8") as f:
            opgeslagen = json.load(f)

        huidig_uur = datetime.now().hour
        vandaag = datetime.now().strftime("%Y-%m-%d")
        assert opgeslagen["chess"] == f"{vandaag}:{huidig_uur}"

    def test_ander_uur_in_state_laat_nieuwe_suggestie_toe(self, event_bus, tmp_path):
        """
        Simuleert dat het topic een ANDER (vorig) uur al voorgesteld
        werd -- vandaag/dit uur moet het dan alsnog opnieuw mogen.
        """
        pm = StubPatternMatcher(actieve_event_types={"topic_detected:chess"})
        cm = StubContextManager(mag_onderbreken=True)
        instance = _maak_topic_suggestions(event_bus, tmp_path, pm, cm)
        instance._laatst_voorgesteld = {"chess": "2020-01-01:3"}  # allang geleden

        instance.check_suggesties()

        assert len(event_bus.gepubliceerd) == 1


class TestCheckSuggestiesWhitelist:
    def test_niet_gewhitelist_topic_wordt_genegeerd_ook_al_actief(self, event_bus, tmp_path):
        """
        Bewust een topic simuleren dat NIET in TOPIC_WHITELIST staat --
        de check zelf loopt enkel over TOPIC_WHITELIST, dus een actief
        patroon op een ander topic_detected:*-event mag nooit een
        suggestie triggeren.
        """
        pm = StubPatternMatcher(actieve_event_types={"topic_detected:weather"})
        cm = StubContextManager(mag_onderbreken=True)
        instance = _maak_topic_suggestions(event_bus, tmp_path, pm, cm)

        instance.check_suggesties()

        assert event_bus.gepubliceerd == []


class TestCheckSuggestiesExceptieAfhandeling:
    def test_exceptie_in_is_pattern_active_crasht_niet(self, event_bus, tmp_path):
        pm = StubPatternMatcher(gooi_exceptie_voor={"topic_detected:chess"})
        cm = StubContextManager(mag_onderbreken=True)
        instance = _maak_topic_suggestions(event_bus, tmp_path, pm, cm)

        instance.check_suggesties()  # mag geen exceptie doorlaten

        assert event_bus.gepubliceerd == []


class TestSjabloonVoor:
    def test_sjabloon_gebruikt_vertaling_uit_topic_naam_labels(self, event_bus, tmp_path):
        instance = _maak_topic_suggestions(event_bus, tmp_path)

        tekst = instance._sjabloon_voor("chess", 19)

        assert tekst == "Het is 19u — wil je een potje schaken?"

    def test_onbekend_topic_valt_terug_op_kale_naam(self, event_bus, tmp_path):
        instance = _maak_topic_suggestions(event_bus, tmp_path)

        tekst = instance._sjabloon_voor("dammen", 20)

        assert "dammen" in tekst


class TestStatusNu:
    """
    Tests voor status_nu() — de read-only variant t.b.v. het debug-
    commando 'topic suggesties' (13 augustus 2026). Moet nooit de
    spam-preventie-state wijzigen of iets publiceren, enkel de huidige
    status per gewhitelist topic teruggeven.
    """

    def test_geeft_lijst_terug_met_1_entry_per_whitelist_topic(self, event_bus, tmp_path):
        pm = StubPatternMatcher(actieve_event_types=set())
        cm = StubContextManager(mag_onderbreken=True)
        instance = _maak_topic_suggestions(event_bus, tmp_path, pm, cm)

        resultaat = instance.status_nu()

        assert len(resultaat) == len(TopicSuggestions.TOPIC_WHITELIST)
        assert {r["topic"] for r in resultaat} == TopicSuggestions.TOPIC_WHITELIST

    def test_wijzigt_de_state_niet(self, event_bus, tmp_path):
        pm = StubPatternMatcher(actieve_event_types={"topic_detected:chess"})
        cm = StubContextManager(mag_onderbreken=True)
        instance = _maak_topic_suggestions(event_bus, tmp_path, pm, cm)

        instance.status_nu()
        instance.status_nu()

        assert instance._laatst_voorgesteld == {}
        assert not instance.state_pad.exists()

    def test_publiceert_niets(self, event_bus, tmp_path):
        pm = StubPatternMatcher(actieve_event_types={"topic_detected:chess"})
        cm = StubContextManager(mag_onderbreken=True)
        instance = _maak_topic_suggestions(event_bus, tmp_path, pm, cm)

        instance.status_nu()

        assert event_bus.gepubliceerd == []

    def test_actief_patroon_en_mag_onderbreken_geeft_zou_nu_spreken_true(self, event_bus, tmp_path):
        pm = StubPatternMatcher(actieve_event_types={"topic_detected:chess"})
        cm = StubContextManager(mag_onderbreken=True)
        instance = _maak_topic_suggestions(event_bus, tmp_path, pm, cm)

        resultaat = instance.status_nu()

        chess_status = next(r for r in resultaat if r["topic"] == "chess")
        assert chess_status["patroon_actief"] is True
        assert chess_status["mag_onderbreken"] is True
        assert chess_status["al_voorgesteld_dit_uur"] is False
        assert chess_status["zou_nu_spreken"] is True

    def test_niet_actief_patroon_geeft_zou_nu_spreken_false(self, event_bus, tmp_path):
        pm = StubPatternMatcher(actieve_event_types=set())
        cm = StubContextManager(mag_onderbreken=True)
        instance = _maak_topic_suggestions(event_bus, tmp_path, pm, cm)

        resultaat = instance.status_nu()

        chess_status = next(r for r in resultaat if r["topic"] == "chess")
        assert chess_status["patroon_actief"] is False
        assert chess_status["zou_nu_spreken"] is False

    def test_mag_niet_onderbreken_geeft_zou_nu_spreken_false(self, event_bus, tmp_path):
        pm = StubPatternMatcher(actieve_event_types={"topic_detected:chess"})
        cm = StubContextManager(mag_onderbreken=False)
        instance = _maak_topic_suggestions(event_bus, tmp_path, pm, cm)

        resultaat = instance.status_nu()

        chess_status = next(r for r in resultaat if r["topic"] == "chess")
        assert chess_status["mag_onderbreken"] is False
        assert chess_status["zou_nu_spreken"] is False

    def test_al_voorgesteld_dit_uur_geeft_zou_nu_spreken_false(self, event_bus, tmp_path):
        pm = StubPatternMatcher(actieve_event_types={"topic_detected:chess"})
        cm = StubContextManager(mag_onderbreken=True)
        instance = _maak_topic_suggestions(event_bus, tmp_path, pm, cm)
        huidig_uur = datetime.now().hour
        vandaag = datetime.now().strftime("%Y-%m-%d")
        instance._laatst_voorgesteld = {"chess": f"{vandaag}:{huidig_uur}"}

        resultaat = instance.status_nu()

        chess_status = next(r for r in resultaat if r["topic"] == "chess")
        assert chess_status["al_voorgesteld_dit_uur"] is True
        assert chess_status["zou_nu_spreken"] is False

    def test_zonder_pattern_matcher_geeft_patroon_actief_false_geen_crash(self, event_bus, tmp_path):
        cm = StubContextManager(mag_onderbreken=True)
        instance = _maak_topic_suggestions(event_bus, tmp_path, pattern_matcher=None, context_manager=cm)

        resultaat = instance.status_nu()

        chess_status = next(r for r in resultaat if r["topic"] == "chess")
        assert chess_status["patroon_actief"] is False

    def test_zonder_context_manager_valt_terug_op_mag_onderbreken_true(self, event_bus, tmp_path):
        """Zelfde 'nooit stiller dan voorheen'-principe als check_suggesties()."""
        pm = StubPatternMatcher(actieve_event_types={"topic_detected:chess"})
        instance = _maak_topic_suggestions(event_bus, tmp_path, pm, context_manager=None)

        resultaat = instance.status_nu()

        chess_status = next(r for r in resultaat if r["topic"] == "chess")
        assert chess_status["mag_onderbreken"] is True

    def test_exceptie_in_is_pattern_active_geeft_patroon_actief_false_geen_crash(self, event_bus, tmp_path):
        pm = StubPatternMatcher(gooi_exceptie_voor={"topic_detected:chess"})
        cm = StubContextManager(mag_onderbreken=True)
        instance = _maak_topic_suggestions(event_bus, tmp_path, pm, cm)

        resultaat = instance.status_nu()  # mag geen exceptie doorlaten

        chess_status = next(r for r in resultaat if r["topic"] == "chess")
        assert chess_status["patroon_actief"] is False


class TestInitModule:
    def test_init_module_geeft_werkende_instantie_terug(self, event_bus):
        instance = init_module(event_bus, pattern_matcher=None, context_manager=None)

        assert isinstance(instance, TopicSuggestions)
        # module_loaded-event moet gepubliceerd zijn
        types = [e for e, _ in event_bus.gepubliceerd]
        assert "module_loaded" in types