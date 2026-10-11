# Tests voor detect_thanks() (11 oktober 2026).
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


@pytest.mark.parametrize("zin", [
    "dank je", "dankje", "dankjewel", "bedankt", "merci", "thanks", "thx",
    "Dank u", "dank je wel", "hartelijk dank", "ok dankje", "top bedankt",
    "dankjewel, dat helpt echt", "dank je, dat is duidelijk!", "BEDANKT!",
    "super bedankt", "dank",
])
def test_bedankjes_worden_herkend(router, zin):
    assert router.detect_thanks(zin) is True
    soort, data = router.event_bus.gepubliceerd[-1]
    assert soort == "layer4_response"
    assert data["text"] in IntentRouter._THANKS_ANTWOORDEN


@pytest.mark.parametrize("zin", [
    "bedankt maar het werkt niet",
    "dank je, dat werkt niet",
    "wat is dank",
    "ik wil je bedanken voor alles wat je gedaan hebt de laatste weken",
    "hoe laat is het",
    "dankbaarheid is een gevoel",
    "hey",
    "",
])
def test_geen_bedankje(router, zin):
    assert router.detect_thanks(zin) is False
    assert router.event_bus.gepubliceerd == []


def test_thanks_staat_in_de_intent_tabel_na_greeting():
    r = object.__new__(IntentRouter)
    r.event_bus = NepBus()
    namen = [naam for naam, _ in r._build_intent_tabel_deel1()]
    assert "thanks" in namen
    assert namen.index("thanks") == namen.index("greeting") + 1