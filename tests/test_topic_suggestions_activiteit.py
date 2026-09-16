# tests/test_topic_suggestions_activiteit.py
"""
Pytest-suite voor punt 18 (nova_state.md, 15 september 2026):
TopicSuggestions._tijd_kandidaten(), _activiteit_kandidaten() en de
uitgebreide check_suggesties() die beide combineert.

Koppelt context_manager.py's get_relevant_topics() (13 sept 2026) als
TWEEDE, onafhankelijke trigger naast de bestaande TIJD-trigger
(pattern_matcher.is_pattern_active()). Test dekt:
- elke trigger apart (tijd alleen, activiteit alleen, geen van beide)
- dat beide triggers samen nog steeds maar 1 suggestie per cyclus geven
- dat get_relevant_topics()-resultaten buiten TOPIC_WHITELIST genegeerd worden
- dat can_interrupt() nog steeds een harde gate is voor ALLE kandidaten
- dat spam-preventie werkt ongeacht via welke trigger een topic gevonden werd
- dat een falende get_relevant_topics()/is_pattern_active() nooit crasht

Tmp_path-isolatie: TopicSuggestions.__init__() doet file-I/O
(topic_suggestion_state.json via get_project_root(__file__)) --
module_onder_test.get_project_root wordt daarom gemonkeypatcht naar
tmp_path, zelfde conventie als de rest van de testsuite.
"""

import pytest

from modules.knowledge import topic_suggestions as module_onder_test
from modules.knowledge.topic_suggestions import TopicSuggestions


class DummyEventBus:
    def __init__(self):
        self.published = []

    def publish(self, event_type, data):
        self.published.append((event_type, data))


class FakePatternMatcher:
    def __init__(self, actieve_topics=None, raise_on_check=False):
        # Set van topic-namen waarvoor is_pattern_active() True moet
        # teruggeven -- niet een simpele bool, zodat meerdere topics
        # onafhankelijk van elkaar getest kunnen worden.
        self._actieve_topics = actieve_topics or set()
        self._raise = raise_on_check

    def is_pattern_active(self, event_type):
        if self._raise:
            raise RuntimeError("gesimuleerde storing in pattern_matcher")
        topic_naam = event_type.replace("topic_detected:", "")
        return topic_naam in self._actieve_topics


class FakeContextManager:
    def __init__(self, relevante_topics=None, can_interrupt=True, raise_on_topics=False):
        self._topics = relevante_topics if relevante_topics is not None else []
        self._can_interrupt = can_interrupt
        self._raise = raise_on_topics

    def get_relevant_topics(self):
        if self._raise:
            raise RuntimeError("gesimuleerde storing in context_manager")
        return self._topics

    def can_interrupt(self):
        return self._can_interrupt


@pytest.fixture
def make_suggesties(tmp_path, monkeypatch):
    """
    Fabriek-fixture: bouwt een TopicSuggestions-instantie met gekozen
    pattern_matcher/context_manager, volledig geïsoleerd in tmp_path
    (geen echte data/topic_suggestion_state.json).
    """
    monkeypatch.setattr(module_onder_test, "get_project_root", lambda f: tmp_path)

    def _maak(pattern_matcher=None, context_manager=None):
        bus = DummyEventBus()
        sugg = TopicSuggestions(
            event_bus=bus,
            pattern_matcher=pattern_matcher,
            context_manager=context_manager,
        )
        return sugg, bus

    return _maak


# ---------------------------------------------------------------------
# _tijd_kandidaten() -- bestaande trigger, geïsoleerd getest
# ---------------------------------------------------------------------

def test_tijd_kandidaten_leeg_zonder_pattern_matcher(make_suggesties):
    sugg, _ = make_suggesties(pattern_matcher=None)
    assert sugg._tijd_kandidaten() == set()


def test_tijd_kandidaten_geeft_actief_topic_terug(make_suggesties):
    pm = FakePatternMatcher(actieve_topics={"chess"})
    sugg, _ = make_suggesties(pattern_matcher=pm)
    assert sugg._tijd_kandidaten() == {"chess"}


def test_tijd_kandidaten_leeg_als_niets_actief(make_suggesties):
    pm = FakePatternMatcher(actieve_topics=set())
    sugg, _ = make_suggesties(pattern_matcher=pm)
    assert sugg._tijd_kandidaten() == set()


def test_tijd_kandidaten_crasht_niet_bij_fout_in_pattern_matcher(make_suggesties):
    pm = FakePatternMatcher(raise_on_check=True)
    sugg, _ = make_suggesties(pattern_matcher=pm)
    assert sugg._tijd_kandidaten() == set()


# ---------------------------------------------------------------------
# _activiteit_kandidaten() -- nieuwe trigger, geïsoleerd getest
# ---------------------------------------------------------------------

def test_activiteit_kandidaten_leeg_zonder_context_manager(make_suggesties):
    sugg, _ = make_suggesties(context_manager=None)
    assert sugg._activiteit_kandidaten() == set()


def test_activiteit_kandidaten_geeft_gewhitelist_topic_terug(make_suggesties):
    cm = FakeContextManager(relevante_topics=["chess"])
    sugg, _ = make_suggesties(context_manager=cm)
    assert sugg._activiteit_kandidaten() == {"chess"}


def test_activiteit_kandidaten_filtert_niet_gewhitelist_topics_weg(make_suggesties):
    # "code"/"python"/"debugging" zijn ECHTE ACTIVITEIT_NAAR_TOPICS-
    # waarden in context_manager.py, maar staan niet in
    # TopicSuggestions.TOPIC_WHITELIST -- moeten dus genegeerd worden.
    cm = FakeContextManager(relevante_topics=["code", "python", "debugging"])
    sugg, _ = make_suggesties(context_manager=cm)
    assert sugg._activiteit_kandidaten() == set()


def test_activiteit_kandidaten_mengt_gewhitelist_en_niet_gewhitelist_correct(make_suggesties):
    cm = FakeContextManager(relevante_topics=["code", "chess", "python"])
    sugg, _ = make_suggesties(context_manager=cm)
    assert sugg._activiteit_kandidaten() == {"chess"}


def test_activiteit_kandidaten_crasht_niet_bij_fout_in_context_manager(make_suggesties):
    cm = FakeContextManager(raise_on_topics=True)
    sugg, _ = make_suggesties(context_manager=cm)
    assert sugg._activiteit_kandidaten() == set()


def test_activiteit_kandidaten_leeg_bij_lege_lijst(make_suggesties):
    cm = FakeContextManager(relevante_topics=[])
    sugg, _ = make_suggesties(context_manager=cm)
    assert sugg._activiteit_kandidaten() == set()


# ---------------------------------------------------------------------
# check_suggesties() -- de twee triggers gecombineerd
# ---------------------------------------------------------------------

def test_geen_enkele_trigger_geeft_geen_suggestie(make_suggesties):
    pm = FakePatternMatcher(actieve_topics=set())
    cm = FakeContextManager(relevante_topics=[], can_interrupt=True)
    sugg, bus = make_suggesties(pattern_matcher=pm, context_manager=cm)

    sugg.check_suggesties()

    assert bus.published == []


def test_enkel_tijd_trigger_geeft_suggestie(make_suggesties):
    pm = FakePatternMatcher(actieve_topics={"chess"})
    cm = FakeContextManager(relevante_topics=[], can_interrupt=True)
    sugg, bus = make_suggesties(pattern_matcher=pm, context_manager=cm)

    sugg.check_suggesties()

    assert len(bus.published) == 1
    event_type, data = bus.published[0]
    assert event_type == "layer4_response"
    assert "schaken" in data["text"]


def test_enkel_activiteit_trigger_geeft_suggestie(make_suggesties):
    pm = FakePatternMatcher(actieve_topics=set())
    cm = FakeContextManager(relevante_topics=["chess"], can_interrupt=True)
    sugg, bus = make_suggesties(pattern_matcher=pm, context_manager=cm)

    sugg.check_suggesties()

    assert len(bus.published) == 1
    event_type, data = bus.published[0]
    assert event_type == "layer4_response"
    assert "schaken" in data["text"]


def test_beide_triggers_actief_geeft_toch_maar_een_suggestie(make_suggesties):
    # TOPIC_WHITELIST bevat momenteel enkel "chess" -- met beide
    # triggers actief op hetzelfde topic is er sowieso maar 1
    # kandidaat, dus dit bevestigt vooral dat de union geen duplicaten
    # of dubbele publicaties oplevert.
    pm = FakePatternMatcher(actieve_topics={"chess"})
    cm = FakeContextManager(relevante_topics=["chess"], can_interrupt=True)
    sugg, bus = make_suggesties(pattern_matcher=pm, context_manager=cm)

    sugg.check_suggesties()

    assert len(bus.published) == 1


def test_can_interrupt_false_blokkeert_activiteit_trigger(make_suggesties):
    pm = FakePatternMatcher(actieve_topics=set())
    cm = FakeContextManager(relevante_topics=["chess"], can_interrupt=False)
    sugg, bus = make_suggesties(pattern_matcher=pm, context_manager=cm)

    sugg.check_suggesties()

    assert bus.published == []


def test_can_interrupt_false_blokkeert_ook_tijd_trigger(make_suggesties):
    # can_interrupt() is een gedeelde gate -- moet ALLE kandidaten
    # blokkeren, ongeacht via welke trigger ze gevonden zijn.
    pm = FakePatternMatcher(actieve_topics={"chess"})
    cm = FakeContextManager(relevante_topics=[], can_interrupt=False)
    sugg, bus = make_suggesties(pattern_matcher=pm, context_manager=cm)

    sugg.check_suggesties()

    assert bus.published == []


def test_ontbrekende_context_manager_blokkeert_can_interrupt_gate_niet(make_suggesties):
    # Zelfde "nooit stiller dan voorheen"-principe als elders in Nova:
    # een ontbrekende context_manager mag de tijd-trigger niet
    # blokkeren als can_interrupt() nergens gecheckt kan worden.
    pm = FakePatternMatcher(actieve_topics={"chess"})
    sugg, bus = make_suggesties(pattern_matcher=pm, context_manager=None)

    sugg.check_suggesties()

    assert len(bus.published) == 1


def test_spam_preventie_werkt_over_beide_triggers_heen(make_suggesties, monkeypatch):
    # Eerste keer via de tijd-trigger gepubliceerd -- een DIRECT
    # daaropvolgende aanroep via de activiteit-trigger (zelfde topic,
    # zelfde uur) mag NIET opnieuw publiceren.
    pm = FakePatternMatcher(actieve_topics={"chess"})
    cm = FakeContextManager(relevante_topics=[], can_interrupt=True)
    sugg, bus = make_suggesties(pattern_matcher=pm, context_manager=cm)

    sugg.check_suggesties()
    assert len(bus.published) == 1

    # Nu de activiteit-trigger activeren i.p.v. de tijd-trigger --
    # spam-preventie moet nog steeds gelden voor "chess" dit uur.
    sugg.pattern_matcher = FakePatternMatcher(actieve_topics=set())
    sugg.context_manager = FakeContextManager(relevante_topics=["chess"], can_interrupt=True)

    sugg.check_suggesties()

    assert len(bus.published) == 1  # geen tweede publicatie


def test_status_nu_blijft_ongewijzigd_puur_informatief(make_suggesties):
    # status_nu() gebruikt nog steeds enkel de tijd-trigger (bewust,
    # zie docstring) -- moet blijven werken zoals voorheen, wijzigt
    # niets aan de nieuwe kandidaat-methodes.
    pm = FakePatternMatcher(actieve_topics={"chess"})
    cm = FakeContextManager(relevante_topics=[], can_interrupt=True)
    sugg, bus = make_suggesties(pattern_matcher=pm, context_manager=cm)

    resultaat = sugg.status_nu()

    assert bus.published == []  # puur informatief, geen publicatie
    assert len(resultaat) == 1
    assert resultaat[0]["topic"] == "chess"
    assert resultaat[0]["patroon_actief"] is True
    assert resultaat[0]["zou_nu_spreken"] is True