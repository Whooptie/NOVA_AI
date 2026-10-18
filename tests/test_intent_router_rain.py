# Tests voor de rain-intent en de rain-koppeling met de Intent Classifier
# (18 oktober 2026).
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


# ---------------------------------------------------------
# detect_rain (regex-route)
# ---------------------------------------------------------
@pytest.mark.parametrize("zin", [
    "gaat het regenen?",
    "wanneer stopt de regen",
    "wanneer is het weer droog",
    "gaat het sneeuwen",
    "gaat het onweren?",
    "komt er een bui aan?",
])
def test_regenvraag_gaat_naar_intent_rain(router, zin):
    assert router.detect_rain(zin) is True
    assert router.event_bus.gepubliceerd == [("intent_rain", {"text": zin})]


@pytest.mark.parametrize("zin", [
    "gaat het morgen regenen?",
    "regent het zaterdag",
    "gaat het overmorgen sneeuwen",
])
def test_regenvraag_met_dagwoord_gaat_naar_weather(router, zin):
    assert router.detect_rain(zin) is True
    assert router.event_bus.gepubliceerd == [("intent_weather", {"text": zin})]


@pytest.mark.parametrize("zin", [
    "ik hou van regen",
    "regen is water dat uit wolken valt",
    "wat is regen",
    "hoe is het weer",
    "",
])
def test_geen_regenvraag(router, zin):
    assert router.detect_rain(zin) is False
    assert router.event_bus.gepubliceerd == []


def test_rain_staat_in_de_tabel_voor_weather():
    r = object.__new__(IntentRouter)
    r.event_bus = NepBus()
    namen = [naam for naam, _ in r._build_intent_tabel_deel1()]
    assert namen.index("rain") < namen.index("weather")


# ---------------------------------------------------------
# Classifier-koppeling
# ---------------------------------------------------------
def test_rain_staat_in_het_classifier_actie_register():
    assert "rain" in IntentRouter._CLASSIFIER_ACTIE_REGISTER


@pytest.mark.parametrize("zin", [
    "moet ik een paraplu meenemen",
    "ga ik nat worden onderweg",
    "heb ik een regenjas nodig",
])
def test_classifier_actie_stuurt_zin_naar_regenradar(router, zin):
    IntentRouter._CLASSIFIER_ACTIE_REGISTER["rain"](router, zin)
    assert router.event_bus.gepubliceerd == [("intent_rain", {"text": zin})]


@pytest.mark.parametrize("zin", [
    "moet ik morgen een paraplu meenemen",
    "heb ik zaterdag een regenjas nodig",
])
def test_classifier_actie_met_dagwoord_gaat_naar_weather(router, zin):
    IntentRouter._CLASSIFIER_ACTIE_REGISTER["rain"](router, zin)
    assert router.event_bus.gepubliceerd == [("intent_weather", {"text": zin})]


@pytest.mark.parametrize("zin", [
    "gaat het morgen regenen?",
    "wanneer stopt de regen",
    "moet ik een paraplu meenemen",
    "regent het zaterdag",
    "gaat het overmorgen sneeuwen",
])
def test_regex_route_en_classifier_route_kiezen_hetzelfde(zin):
    """Beide routes delen _stuur_regen_vraag(): zelfde zin, zelfde event."""
    a = object.__new__(IntentRouter)
    a.event_bus = NepBus()
    b = object.__new__(IntentRouter)
    b.event_bus = NepBus()
    a._stuur_regen_vraag(zin)
    IntentRouter._CLASSIFIER_ACTIE_REGISTER["rain"](b, zin)
    assert a.event_bus.gepubliceerd == b.event_bus.gepubliceerd


def test_elk_label_in_het_register_heeft_nederlandse_tekst_voor_vraag_en_bevestiging():
    for label in IntentRouter._CLASSIFIER_ACTIE_REGISTER:
        assert label in IntentRouter._CLASSIFIER_LABEL_NL_VRAAG, label
        assert label in IntentRouter._CLASSIFIER_LABEL_NL_BEVESTIGING, label