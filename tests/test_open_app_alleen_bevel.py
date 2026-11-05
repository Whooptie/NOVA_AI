# tests/test_open_app_alleen_bevel.py
"""
5 november 2026: "open", "start", "sluit" en "stop" zijn alleen een app-commando als ze een BEVEL
zijn (aan het begin van de zin, eventueel na een aanhef of "kun je"). Gevonden met de blinde
set: "wat is het gevolg van een open deur" gaf "ik kan geen apps openen".
"""
import pytest

from core.event_bus import EventBus
from core.intent_router import IntentRouter


@pytest.fixture
def router():
    return IntentRouter(EventBus())


@pytest.mark.parametrize("zin", [
    "open chrome", "Open Chrome", "start notepad", "open mijn chrome", "open de verkenner",
    "hey nova open chrome", "nova, start notepad", "kun je open chrome", "alsjeblieft open chrome",
])
def test_open_als_bevel_blijft_werken(router, zin):
    assert router.detect_open_app(zin) is True


@pytest.mark.parametrize("zin", [
    "wat is het gevolg van een open deur",
    "wat volgt er als een deur open gaat",
    "wat gebeurt er als de motor start",
    "een open deur is niet dicht",
    "hoe lang duurt het voor de show start",
])
def test_open_in_gewone_zin_is_geen_commando(router, zin):
    assert router.detect_open_app(zin) is False


@pytest.mark.parametrize("zin", ["sluit chrome", "close notepad", "hey nova sluit chrome", "kan je sluit chrome"])
def test_sluit_als_bevel_blijft_werken(router, zin):
    assert router.detect_close_app(zin) is True


@pytest.mark.parametrize("zin", [
    "wat gebeurt er als de deur sluit",
    "wat gebeurt er als je stop",
    "waarom werkt de pomp niet meer als de stroom stop",
])
def test_sluit_in_gewone_zin_is_geen_commando(router, zin):
    assert router.detect_close_app(zin) is False


def test_door_de_hele_router_geen_app_commando():
    from core.semantic import SemanticConceptsModule
    from modules.chat.chat import ChatModule
    bus = EventBus()
    events = []
    orig = bus.publish
    bus.publish = lambda e, d=None, *a, **k: (events.append(e), orig(e, d, *a, **k))[1]
    sem = SemanticConceptsModule(bus)
    bus.modules = getattr(bus, "modules", {})
    bus.modules["semantic"] = sem
    ChatModule(bus, semantic_module=sem)
    router = IntentRouter(bus, semantic_module=sem)
    for zin in ["wat is het gevolg van een open deur", "wat volgt er als een deur open gaat"]:
        events.clear()
        router.route({"text": zin}, "chat_message")
        assert "open_app" not in events
        assert not any(e.startswith("topic_detected:open_app") for e in events)
        assert "intent_effects" in events