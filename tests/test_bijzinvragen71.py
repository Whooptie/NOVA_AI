# tests/test_bijzinvragen71.py
"""
Tests voor punt 71 (4 november 2026): vragen met een gebeurtenis als onderwerp
("wat gebeurt er als je een ballon loslaat", "waardoor breekt een tak").

Dit is GEEN begrip van de gebeurtenis. De regels herkennen de vorm en sturen
de gebeurtenis door naar "wat zijn de gevolgen van X" / "wat veroorzaakt X".
Het antwoord is daardoor bijna altijd een eerlijk "Ik ken geen ... van ...".
"""
import pytest

from core.language_normalizer import normaliseer


@pytest.mark.parametrize("zin, verwacht", [
    # gevolg
    ("wat gebeurt er als je een ballon loslaat", "wat zijn de gevolgen van een ballon loslaat"),
    ("Wat gebeurt er als een plant geen water krijgt?", "wat zijn de gevolgen van een plant geen water krijgt"),
    ("wat gebeurt er als je een sleutel omdraait", "wat zijn de gevolgen van een sleutel omdraait"),
    ("wat ontstaat er als een tak breekt", "wat zijn de gevolgen van een tak breekt"),
    ("wat gebeurt er wanneer ijs smelt", "wat zijn de gevolgen van ijs smelt"),
    ("wat zou er gebeuren als het sneeuwt", "wat zijn de gevolgen van het sneeuwt"),
    ("wat komt er van te lang in de zon zitten", "wat zijn de gevolgen van te lang in de zon zitten"),
    ("wat gebeurt er eigenlijk als je te veel koffie drinkt", "wat zijn de gevolgen van te veel koffie drinkt"),
    # oorzaak
    ("wat zorgt ervoor dat een ballon opstijgt", "wat veroorzaakt een ballon opstijgt"),
    ("wat zorgt er voor dat ijs smelt in de zon", "wat veroorzaakt ijs smelt in de zon"),
    ("wat maakt dat een kaars brandt", "wat veroorzaakt een kaars brandt"),
    ("waardoor breekt een tak", "wat veroorzaakt een tak breekt"),
    ("waardoor wordt een plant geel", "wat veroorzaakt een plant wordt geel"),
    ("waardoor wordt iemand verkouden", "wat veroorzaakt iemand wordt verkouden"),
    ("waardoor smelt sneeuw", "wat veroorzaakt sneeuw smelt"),
])
def test_bijzinvraag_wordt_herschreven(zin, verwacht):
    nieuw, regel = normaliseer(zin)
    assert nieuw == verwacht
    assert regel is not None


@pytest.mark.parametrize("zin", [
    # Vragen over Nova zelf blijven ongemoeid.
    "wat gebeurt er als ik je uitzet",
    "wat gebeurt er als je me negeert",
    "wat gebeurt er als je een update krijgt",
    "wat gebeurt er als je stopt",
    "wat gebeurt er als je dood gaat",
    "wat gebeurt er als nova crasht",
    "wat zorgt ervoor dat jij werkt",
    "waardoor werk jij",
    "waardoor kun je praten",
    # Kale verwijzing is geen gebeurtenis.
    "wat gebeurt er als dat gebeurt",
    "wat zorgt ervoor dat dat gebeurt",
    "waardoor smelt dat",
    # 'dat' als aanwijzend woord, geen oorzaakvraag.
    "wat maakt dat huis zo bijzonder",
    "wat maakt dat zo mooi",
    # Eén woord is geen gebeurtenis.
    "wat gebeurt er als regen",
    # Waarom-vragen met een koppel- of modaal werkwoord zijn een reden, geen oorzaak van een
    # gebeurtenis. ("waarom smelt sneeuw" is sinds punt 76 wel een oorzaakvraag.)
    "waarom is de lucht blauw",
    "waarom kan een vogel vliegen",
])
def test_bijzinvraag_blijft_ongemoeid(zin):
    nieuw, regel = normaliseer(zin)
    assert nieuw == zin
    assert regel is None


def test_oude_regels_blijven_winnen():
    # Korte vormen met een woord vallen nog onder de oude regels.
    assert normaliseer("waardoor ontstaat modder") == ("wat veroorzaakt modder", "oorzaak_waardoor")
    assert normaliseer("wat gebeurt er na de regen") == ("wat zijn de gevolgen van regen", "gevolg_ontstaat")


def test_idempotent():
    for zin in ["waardoor breekt een tak", "wat gebeurt er als je een ballon loslaat"]:
        eerste, _ = normaliseer(zin)
        tweede, regel = normaliseer(eerste)
        assert tweede == eerste
        assert regel is None


def test_router_geeft_eerlijk_antwoord():
    """Door de echte router en chat: een onbekende gebeurtenis geeft 'Ik ken geen ...'."""
    from core.event_bus import EventBus
    from core.semantic import SemanticConceptsModule
    from modules.chat.chat import ChatModule
    from core.intent_router import IntentRouter

    bus = EventBus()
    antwoorden = []
    bus.subscribe("layer4_response", lambda d, *a, **k: antwoorden.append(d.get("text", "")))
    sem = SemanticConceptsModule(bus)
    bus.modules = getattr(bus, "modules", {})
    bus.modules["semantic"] = sem
    ChatModule(bus, semantic_module=sem)
    router = IntentRouter(bus, semantic_module=sem)

    router.route({"text": "wat gebeurt er als een tak breekt"}, "chat_message")
    router.route({"text": "waardoor breekt een tak"}, "chat_message")
    assert any("Ik ken geen gevolgen van 'tak breekt'" in a for a in antwoorden)
    assert any("Ik ken geen oorzaken van 'tak breekt'" in a for a in antwoorden)