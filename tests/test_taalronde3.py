"""Tests voor ronde 3 van punt 62d (context_resolver) en de synoniemregels in de normalizer.

Eigen voorbeelden met andere woorden dan de blinde batches, zodat de regels algemeen blijven.
"""
import pytest

from core import context_resolver as cr
from core.language_normalizer import normaliseer

DEF = ("wat is {x}", "een hond", "np")
GEVOLG = ("wat zijn de gevolgen van {x}", "regen", "kaal")
REL = ("is {x} een dier", "een zebra", "np")


# ---- "NP ook/dan/wel?" ----
@pytest.mark.parametrize("tekst,verwacht", [
    ("een konijn ook?", "wat is een konijn"),
    ("konijn ook", "wat is konijn"),
    ("en een konijn dan?", "wat is een konijn"),
    ("en wortel dan?", "wat is wortel"),
    ("een zebra wel?", "wat is een zebra"),
    ("een zebra ook nog", "wat is een zebra"),
    ("en brood dan", "wat is brood"),
])
def test_ellips_met_woord_erachter(tekst, verwacht):
    assert cr.los_op(tekst, *DEF) == (verwacht, "ellips")


def test_ellips_achter_in_relatievraag():
    assert cr.los_op("een paard ook?", *REL) == ("is een paard een dier", "ellips")


def test_ellips_achter_in_gevolgvraag_zonder_lidwoord():
    assert cr.los_op("brand dan?", *GEVOLG) == ("wat zijn de gevolgen van brand", "ellips")


# ---- kale woorden en vulwoorden ----
@pytest.mark.parametrize("tekst,verwacht,regel", [
    ("hoe komt dat eigenlijk", "wat veroorzaakt regen", "oorzaak_verwijzing"),
    ("hoe komt die dan", "wat veroorzaakt regen", "oorzaak_verwijzing"),
    ("waardoor gebeurt dat", "wat veroorzaakt regen", "oorzaak_verwijzing"),
    ("oorzaken", "wat veroorzaakt regen", "oorzaak_verwijzing"),
    ("de oorzaak daarvan", "wat veroorzaakt regen", "oorzaak_verwijzing"),
    ("gevolgen", "wat zijn de gevolgen van regen", "gevolg_verwijzing"),
    ("de gevolgen daarvan", "wat zijn de gevolgen van regen", "gevolg_verwijzing"),
    ("en de effecten", "wat zijn de gevolgen van regen", "gevolg_verwijzing"),
    ("ander woord", "wat is een synoniem van regen", "synoniem_verwijzing"),
    ("synoniemen", "wat is een synoniem van regen", "synoniem_verwijzing"),
    ("en een ander woord ervoor", "wat is een synoniem van regen", "synoniem_verwijzing"),
])
def test_kale_woorden(tekst, verwacht, regel):
    assert cr.los_op(tekst, *GEVOLG) == (verwacht, regel)


# ---- grenzen ----
@pytest.mark.parametrize("tekst", [
    "en dan?", "en wat dan", "en nu?", "dat ook", "dit wel", "ja dan", "nou ook",
    "ook", "dan", "een koe", "hond dan nog twee",
])
def test_ronde3_grenzen(tekst):
    assert cr.los_op(tekst, *DEF) is None


def test_kale_woorden_zonder_kader_vragen_terug():
    for zin in ["gevolgen", "synoniem", "ander woord", "hoe komt dat eigenlijk"]:
        assert cr.is_verwijzing_zonder_onderwerp(zin), zin


def test_gewone_zinnen_zijn_geen_verwijzing():
    for zin in ["een konijn ook?", "wat is een hond", "gevolgen van regen"]:
        assert not cr.is_verwijzing_zonder_onderwerp(zin), zin


# ---- normalizer: synoniem als eerste vraag ----
@pytest.mark.parametrize("invoer,verwacht,regel", [
    ("Hoe noem je een stoel anders?", "wat is een synoniem van stoel", "synoniem_hoe_noem"),
    ("hoe zeg je een auto ook wel", "wat is een synoniem van auto", "synoniem_hoe_noem"),
    ("Hoe heet een leraar ook wel?", "wat is een synoniem van leraar", "synoniem_hoe_heet"),
    ("hoe heet een fiets anders", "wat is een synoniem van fiets", "synoniem_hoe_heet"),
    ("hoe kun je een huis ook noemen", "wat is een synoniem van huis", "synoniem_ook_noemen"),
    ("wat is een andere naam voor tuin", "wat is een synoniem van tuin", "synoniem_andere_naam"),
    ("wat is de andere benaming voor tuin", "wat is een synoniem van tuin", "synoniem_andere_naam"),
    ("wat is dat precies", "wat is dat", "definitie_kale_verwijzing"),
    ("wat is dat eigenlijk", "wat is dat", "definitie_kale_verwijzing"),
])
def test_normalizer_ronde3(invoer, verwacht, regel):
    assert normaliseer(invoer) == (verwacht, regel)


@pytest.mark.parametrize("zin", [
    "Hoe heet een hond?",          # naam vragen, geen synoniem
    "hoe heet jouw broer",
    "hoe noem je dit",             # geen begrip
    "hoe zeg je dat",
    "wat is dat",                  # al in de korte vorm
])
def test_normalizer_ronde3_laat_rest_staan(zin):
    assert normaliseer(zin) == (zin, None)


# ---- "bij" is met lidwoord een insect, zonder lidwoord een voorzetsel ----
def test_een_bij_is_een_onderwerp():
    assert cr.herken_vraag("is een bij een insect") == ("is {x} een insect", "een bij", "np")
    assert cr.los_op("een wesp ook?", "is {x} een insect", "een bij", "np") == (
        "is een wesp een insect", "ellips")


def test_kale_bij_is_geen_onderwerp():
    assert cr.herken_vraag("wat is bij") is None
    assert cr.los_op("en bij?", *DEF) is None