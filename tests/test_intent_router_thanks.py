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


# ---------------------------------------------------------------------
# Thanks via de Intent Classifier (18 oktober 2026)
# ---------------------------------------------------------------------
# Als geen enkele regex een bedankje herkent, kan de Intent Classifier
# het label "thanks" gokken. Daarna voert _CLASSIFIER_ACTIE_REGISTER
# ["thanks"] -> _actie_thanks_classifier() de actie uit. Deze tests
# bewaken dat die koppeling bestaat, hetzelfde antwoord geeft als de
# regex-route, en dat de Nederlandse vraagtekst niet ontbreekt.

def test_classifier_actie_stuurt_een_bedankt_antwoord(router):
    router._actie_thanks_classifier("heel erg bedankt voor je hulp")

    # kies_variant() publiceert zelf ook een "variant_gekozen"-event
    # (voor de variant-feedback), dus tel enkel de layer4_response-events.
    antwoorden = [
        data for soort, data in router.event_bus.gepubliceerd
        if soort == "layer4_response"
    ]
    assert len(antwoorden) == 1
    assert antwoorden[0]["text"] in IntentRouter._THANKS_ANTWOORDEN


def test_thanks_staat_in_het_classifier_actie_register(router):
    """Het register wordt aangeroepen als actie(self, text) -- precies
    zoals _voer_classifier_intent_uit() het doet."""
    actie = IntentRouter._CLASSIFIER_ACTIE_REGISTER.get("thanks")
    assert actie is not None, "thanks ontbreekt in _CLASSIFIER_ACTIE_REGISTER"

    actie(router, "ontzettend bedankt")

    soort, data = router.event_bus.gepubliceerd[-1]
    assert soort == "layer4_response"
    assert data["text"] in IntentRouter._THANKS_ANTWOORDEN


def test_regex_route_en_classifier_route_delen_dezelfde_antwoordkeuze(router, monkeypatch):
    """detect_thanks() en _actie_thanks_classifier() horen allebei via
    _stuur_bedankt_antwoord() te lopen (zelfde varianten en
    variant-feedback), niet elk hun eigen kopie van die logica."""
    aanroepen = []
    monkeypatch.setattr(router, "_stuur_bedankt_antwoord", lambda: aanroepen.append("x"))

    assert router.detect_thanks("bedankt") is True
    router._actie_thanks_classifier("heel erg bedankt")

    assert aanroepen == ["x", "x"]


def test_elk_label_in_het_register_heeft_nederlandse_tekst_voor_vraag_en_bevestiging():
    """Regressie voor bug #38: een label zonder Nederlandse tekst toont
    de rauwe labelnaam ("Bedoel je dat je memory_query?"). Elk label dat
    een actie in het register heeft, hoort in BEIDE mappings te staan."""
    for label in IntentRouter._CLASSIFIER_ACTIE_REGISTER:
        assert label in IntentRouter._CLASSIFIER_LABEL_NL_VRAAG, (
            f"'{label}' ontbreekt in _CLASSIFIER_LABEL_NL_VRAAG")
        assert label in IntentRouter._CLASSIFIER_LABEL_NL_BEVESTIGING, (
            f"'{label}' ontbreekt in _CLASSIFIER_LABEL_NL_BEVESTIGING")