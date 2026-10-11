# tests/test_intent_router_tijd_relatievraag.py
"""
Ja/nee-kennisvragen over "tijd"/"klok" mogen niet meer als tijdsvraag
opgevangen worden ("is een klok een apparaat" gaf voorheen het uur).
Echte tijdsvragen moeten ongewijzigd blijven werken.
"""
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
    r._laatste_concept_kandidaat = None
    r._topic_al_ge_emit = False
    return r


class TestLijktRelatievraag:
    @pytest.mark.parametrize("zin", [
        "is een klok een apparaat",
        "is een klok een apparaat?",
        "is een klok onderdeel van een kerk",
        "is tijd een begrip",
        "heeft tijd iets te maken met geld",
        "heeft tijd te maken met leeftijd",
        "is klok gerelateerd aan uur",
        "is een klok gerelateerd aan tijd",
    ])
    def test_relatievorm_herkend(self, router, zin):
        assert router._lijkt_relatievraag(zin) is True

    @pytest.mark.parametrize("zin", [
        "is het al tijd om te gaan",
        "is het een goede tijd",
        "is er tijd genoeg",
        "hoe laat is het",
        "tijd",
        "klok",
        "heeft het iets te maken met tijd",
    ])
    def test_geen_relatievorm(self, router, zin):
        assert router._lijkt_relatievraag(zin) is False


class TestDetectTimeMetRelatievragen:
    @pytest.mark.parametrize("zin", [
        "is een klok een apparaat",
        "is tijd een begrip",
        "heeft tijd iets te maken met geld",
    ])
    def test_relatievraag_is_geen_tijdsvraag(self, router, zin):
        assert router.detect_time(zin) is False
        assert not any(e == "intent_time_query" for e, _ in router.event_bus.gepubliceerd)

    @pytest.mark.parametrize("zin", [
        "hoe laat is het",
        "tijd",
        "klok",
        "is het al tijd om te gaan",
    ])
    def test_echte_tijdsvraag_blijft_werken(self, router, zin):
        assert router.detect_time(zin) is True