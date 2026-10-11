# Tests voor de detector-restgaten (11 oktober 2026).
import pytest

from core.intent_router import IntentRouter


class NepBus:
    def __init__(self):
        self.gepubliceerd = []
        self.modules = {}

    def publish(self, event_type, data=None):
        self.gepubliceerd.append((event_type, data))

    def subscribe(self, *args, **kwargs):
        pass


@pytest.fixture
def router():
    r = object.__new__(IntentRouter)
    r.event_bus = NepBus()
    return r


def soorten(r):
    return [s for s, _ in r.event_bus.gepubliceerd]


@pytest.mark.parametrize("zin", [
    "hoelang nog tot kerst",
    "hoe lang nog tot kerst",
    "Hoelang nog tot pasen?",
    "hoeveel dagen tot kerst",
])
def test_hoelang_tot_is_kalender(router, zin):
    assert router.detect_calendar(zin) is True
    assert router.event_bus.gepubliceerd[-1] == (
        "intent_calendar_query", {"text": zin, "type": "dagen_tot"}
    )


def test_hoelang_tot_vakantie_is_vakantie(router):
    assert router.detect_vakantie("hoelang nog tot de vakantie") is True
    soort, data = router.event_bus.gepubliceerd[-1]
    assert soort == "intent_vakantie_query"
    assert data["type"] == "dagen_tot_vakantie"


@pytest.mark.parametrize("zin", [
    "wat gebeurde er op 9 december",
    "wat is er gebeurd op 9 december",
])
def test_on_this_day_herkent_beide_vormen(router, zin):
    assert router.detect_on_this_day(zin) is True
    assert router.event_bus.gepubliceerd[-1][0] == "intent_on_this_day_query"


def test_wat_gebeurt_er_blijft_voor_self_architecture(router):
    assert router.detect_on_this_day("wat gebeurt er als ik iets tegen je zeg") is False
    assert router.event_bus.gepubliceerd == []


@pytest.mark.parametrize("zin,woord", [
    ("wat weet je van fysica", "fysica"),
    ("wat weet je over fysica", "fysica"),
    ("wat weet je allemaal over gitaar", "gitaar"),
    ("wat weet je van de gitaar", "gitaar"),
])
def test_overzichtsvraag_met_woord(router, zin, woord):
    assert router.detect_definition(zin) is True
    assert ("intent_concept_overview", {"word": woord}) in router.event_bus.gepubliceerd


@pytest.mark.parametrize("zin", [
    "wat weet je over mij",
    "wat weet je van mij",
    "wat weet je allemaal over mij",
    "wat weet je over kevin",
    "wat weet je van jezelf",
])
def test_persoonlijke_vraag_is_geen_woordopzoeking(router, zin):
    assert router.detect_definition(zin) is False
    assert "intent_concept_overview" not in soorten(router)


def test_wat_hoort_bij_is_related_to(router):
    assert router.detect_definition("wat hoort bij regen") is True
    assert ("intent_related_to", {"word": "regen"}) in router.event_bus.gepubliceerd