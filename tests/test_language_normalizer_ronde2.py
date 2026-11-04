"""Tests voor ronde 2 van de taalnormalizer (punt 62a).

Elke regel uit ronde 2 krijgt hier een positief voorbeeld, plus een lijst
zinnen die ongewijzigd moeten blijven (grenzen van wat vaste regels kunnen).
"""
import pytest

from core.language_normalizer import normaliseer


POSITIEF = [
    # aanhalingstekens
    ('wat betekent "flurble"', "wat is flurble", "definitie_citaat"),
    ('wat betekent het woord "regen"', "wat is regen", "definitie_woord"),
    ('wat is een ander woord voor "kinderen"', "wat is een ander woord voor kinderen",
     "synoniem_ander_woord"),
    # definities
    ("hoe zou je een stoel beschrijven", "wat is een stoel", "definitie_beschrijven"),
    ("hoe definieer je een rivier", "wat is een rivier", "definitie_hoe"),
    ("wat voor iets is een appel", "wat is een appel", "definitie_wat_voor"),
    ("wat voor iets is een krimzot", "wat is een krimzot", "definitie_wat_voor"),
    # relaties met "soort/vorm van"
    ("is een appel een soort fruit", "is een appel een fruit", "relatie_kaal"),
    ("is regen een vorm van neerslag", "is regen een neerslag", "relatie_kaal"),
    # gevolgen
    ("wat komt er van regen", "wat zijn de gevolgen van regen", "gevolg_komt"),
    ("wat ontstaat er na een brand", "wat zijn de gevolgen van brand", "gevolg_ontstaat"),
    ("wat is het resultaat van slapen", "wat zijn de gevolgen van slapen", "gevolg_resultaat"),
    # synoniemen
    ("welk woord heeft dezelfde betekenis als huis", "wat is een synoniem van huis",
     "synoniem_betekenis"),
    ('welk woord betekent ook "klein"', "wat is een synoniem van klein", "synoniem_hetzelfde"),
    ('welk woord is synoniem aan "groot"', "wat is een synoniem van groot", "synoniem_is"),
    ('wat betekent hetzelfde als "dierenarts"', "wat is een synoniem van dierenarts",
     "synoniem_hetzelfde"),
]


@pytest.mark.parametrize("invoer,verwacht,regel", POSITIEF)
def test_ronde2_positief(invoer, verwacht, regel):
    assert normaliseer(invoer) == (verwacht, regel)


@pytest.mark.parametrize("invoer,verwacht,regel", POSITIEF)
def test_ronde2_idempotent(invoer, verwacht, regel):
    """Een al genormaliseerde zin mag niet nog eens veranderen."""
    assert normaliseer(verwacht)[0] == verwacht


ONGEWIJZIGD = [
    "wat gebeurt er als ijs smelt",       # bijzin als onderwerp: buiten bereik
    "waardoor wordt iemand moe",          # idem
    "hoort een hond bij de dieren",       # meervoud: lemmatizer nodig
    "wat betekent flurble",               # zonder aanhalingstekens: werkt al
    "wat is regen",
    "wat is een synoniem van mooi",
    "wat is een ander woord voor auto",
    "een soort fruit",                    # geen vraag
]


@pytest.mark.parametrize("invoer", ONGEWIJZIGD)
def test_ronde2_blijft_ongewijzigd(invoer):
    assert normaliseer(invoer) == (invoer, None)


def test_apostrof_in_woord_blijft():
    assert "auto's" in normaliseer("wat betekent het woord auto's")[0]


# --- "klok" en "tijd" in een kennisvraag zijn geen tijdsvraag ----------------
import core.intent_router as ir


class _Bus:
    def __init__(self):
        self.events = []

    def publish(self, naam, data=None, *a, **k):
        self.events.append(naam)

    def subscribe(self, *a, **k):
        pass


@pytest.mark.parametrize("zin", [
    "klopt het dat een klok tijd meet",
    "kun je zeggen wat een klok doet",
    "is het waar dat tijd kostbaar is",
])
def test_kennisvraag_over_klok_is_geen_tijdsvraag(zin):
    router = ir.IntentRouter(_Bus())
    assert router.detect_time(zin) is False


@pytest.mark.parametrize("zin", ["hoe laat is het", "wat is de tijd", "klok", "hoeveel tijd"])
def test_echte_tijdsvragen_blijven_werken(zin):
    router = ir.IntentRouter(_Bus())
    assert router.detect_time(zin) is True