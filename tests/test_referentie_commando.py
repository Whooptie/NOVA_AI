# tests/test_referentie_commando.py
"""
Een commando dat met "/" begint is nooit het antwoord op "Waar heb je het over?".
Voorheen werd "/reboot" na een onopgeloste "wat is dat" omgebouwd tot "wat is /reboot".
"""
from core.event_bus import EventBus
from core.intent_router import IntentRouter


def _router():
    bus = EventBus()
    router = IntentRouter(bus)
    teksten = []
    bus.subscribe("chat_response", lambda d, *a, **k: teksten.append(d.get("text", "")))
    gebeurtenissen = []
    bus.subscribe("system:reboot", lambda d, *a, **k: gebeurtenissen.append(d))
    return router, teksten, gebeurtenissen


def test_reboot_na_openstaande_referentievraag_werkt_meteen():
    router, teksten, reboots = _router()
    router.route({"text": "wat is dat"}, "chat_message")
    assert any("Waar heb je het over" in t for t in teksten)
    router.route({"text": "/reboot"}, "chat_message")
    assert len(reboots) == 1
    assert not any("wat is /reboot" in t for t in teksten)


def test_gewoon_antwoord_werkt_nog_steeds_als_referentie():
    router, teksten, _ = _router()
    router.route({"text": "wat is dat"}, "chat_message")
    teksten.clear()
    router.route({"text": "hond"}, "chat_message")
    assert not any("Waar heb je het over" in t for t in teksten)


def test_open_vraag_is_weg_na_een_commando():
    router, _, _ = _router()
    router.route({"text": "wat is dat"}, "chat_message")
    router.route({"text": "/reboot"}, "chat_message")
    assert router._pending_referentie_vraag is None