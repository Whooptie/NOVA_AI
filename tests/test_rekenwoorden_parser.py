# tests/test_rekenwoorden_parser.py
import pytest

from core.rekenwoorden import vertaal_rekenzin, getalwoord_naar_int


# --- dingen die al werkten en moeten blijven werken -----------------------
@pytest.mark.parametrize("zin, verwacht", [
    ("wat is drie plus vijf", "3 + 5"),
    ("hoeveel is twintig gedeeld door vier", "20 / 4"),
    ("bereken 3+5", "3 + 5"),
    ("wat is 9/11", "9 / 11"),
    ("wat is 3 x 4", "3 * 4"),
    ("wat is zeven min twee", "7 - 2"),
    ("wat is tweeduizend vijfhonderd plus een", "2500 + 1"),
    ("wat is tweeëntwintig maal twee", "22 * 2"),
    ("wat is 2,5 plus 1", "2.5 + 1"),
    ("wat is twee tot de macht tien", "2 ^ 10"),
    ("wat is drie min twee min een", "3 - 2 - 1"),
    ("wat is drie plus vijf?", "3 + 5"),
    ("twee plus twee", "2 + 2"),
])
def test_oude_gevallen(zin, verwacht):
    assert vertaal_rekenzin(zin) == verwacht


@pytest.mark.parametrize("zin", [
    "3+5",                      # bestaand pad, niet aanraken
    "3 x 4",
    "(3+5)*2",
    "wat is zes",               # een los getal is geen som
    "wat is drie plus",
    "wat is plus drie",
    "wat is drie drie",
    "wat is een hond",
    "wat is de tijd plus vijf",
    "wat is drie plus vijf alsjeblieft",
    "wat is er gebeurd op 9/11",
    "wat is 3 + + 4",
    "wat is -3 plus 5",
    "",
    "   ",
    None,
    123,
])
def test_oude_afwijzingen(zin):
    assert vertaal_rekenzin(zin) is None


# --- nieuw: de som van, product, verschil ---------------------------------
@pytest.mark.parametrize("zin, verwacht", [
    ("wat is de som van drie en vijf", "3 + 5"),
    ("wat is de som van 3, 4 en 5", "3 + 4 + 5"),
    ("wat is het product van drie en vier", "3 * 4"),
    ("wat is het product van 2, 3 en 4", "2 * 3 * 4"),
    ("wat is het verschil tussen tien en vier", "abs(10 - 4)"),
    ("wat is het verschil tussen 4 en 10", "abs(4 - 10)"),
    ("wat is het quotiënt van twintig en vier", "20 / 4"),
    ("wat is twee maal de som van drie en vijf", "2 * (3 + 5)"),
    ("wat is de som van drie en vijf", "3 + 5"),
    ("wat is tien min de som van twee en drie", "10 - (2 + 3)"),
])
def test_som_product_verschil(zin, verwacht):
    assert vertaal_rekenzin(zin) == verwacht


# --- nieuw: haakjes -------------------------------------------------------
@pytest.mark.parametrize("zin, verwacht", [
    ("wat is (3+5)*2", "(3 + 5) * 2"),
    ("bereken (drie plus vijf) maal twee", "(3 + 5) * 2"),
    ("wat is 2*(3+4)", "2 * (3 + 4)"),
    ("wat is ((2+3))", None),   # geen bewerking buiten de haakjes? -> wel een som
    ("wat is 10 - (2 + 3)", "10 - (2 + 3)"),
    ("wat is 10 / (2 * 5)", "10 / (2 * 5)"),
    ("wat is haakje openen drie plus vijf haakje sluiten maal twee", "(3 + 5) * 2"),
])
def test_haakjes(zin, verwacht):
    if verwacht is None:
        # ((2+3)) is gewoon 2 + 3
        assert vertaal_rekenzin(zin) == "2 + 3"
    else:
        assert vertaal_rekenzin(zin) == verwacht


@pytest.mark.parametrize("zin", [
    "wat is (3 + 5",
    "wat is 3 + 5)",
    "wat is ()",
])
def test_haakjes_fout(zin):
    assert vertaal_rekenzin(zin) is None


# --- nieuw: komma-getallen ------------------------------------------------
@pytest.mark.parametrize("zin, verwacht", [
    ("wat is twee komma vijf plus een", "2.5 + 1"),
    ("wat is drie komma een vier maal twee", "3.14 * 2"),
    ("wat is twee komma nul vijf plus een", "2.05 + 1"),
    ("wat is 2 komma 5 plus 1", "2.5 + 1"),
    ("wat is tweeëntwintig komma vijf min twee", "22.5 - 2"),
])
def test_komma_getallen(zin, verwacht):
    assert vertaal_rekenzin(zin) == verwacht


@pytest.mark.parametrize("zin", [
    "wat is komma vijf plus een",
    "wat is twee komma plus een",
    "wat is twee komma vijf komma vier plus een",
    "wat is twee komma 5 plus een",         # mix cijfers en woorden: bewust niet
    "wat is twee komma tien plus een",      # na de komma enkel losse cijferwoorden
])
def test_komma_getallen_fout(zin):
    assert vertaal_rekenzin(zin) is None


# --- nieuw: procent, helft, dubbele, kwadraat, wortel ---------------------
@pytest.mark.parametrize("zin, verwacht", [
    ("wat is twintig procent van tachtig", "20 * 80 / 100"),
    ("hoeveel is 15% van 200", "15 * 200 / 100"),
    ("wat is de helft van twintig", "20 / 2"),
    ("wat is het dubbele van zeven", "7 * 2"),
    ("wat is vijf kwadraat", "5 ^ 2"),
    ("wat is het kwadraat van vier", "4 ^ 2"),
    ("wat is de derde macht van twee", "2 ^ 3"),
    ("wat is drie tot de derde macht", "3 ^ 3"),
    ("wat is de wortel van negen", "sqrt(9)"),
    ("wat is twee maal de helft van zes", "2 * 6 / 2"),
    ("wat is de helft van de som van drie en vijf", "(3 + 5) / 2"),
    ("wat is de uitkomst van drie plus vijf", "3 + 5"),
    ("wat is het resultaat van twee maal vier", "2 * 4"),
])
def test_procent_helft_macht_wortel(zin, verwacht):
    assert vertaal_rekenzin(zin) == verwacht


# --- dubbelzinnig of onvolledig -> niets doen ----------------------------
@pytest.mark.parametrize("zin", [
    "wat is de helft van twintig plus vier",
    "wat is de som van drie en vijf maal twee",
    "wat is het dubbele van vijf kwadraat",
    "wat is twintig procent van tachtig plus tien",
    "wat is de som van drie",
    "wat is het verschil tussen 1, 2 en 3",
    "wat is de som van",
    "wat is de wortel van",
    "wat is de helft van",
    "wat is de som van het product van twee en drie en vier",
    "wat is de helft van de tijd",
    "wat is de som van drie en",
    "wat is 5 %",
])
def test_dubbelzinnig_of_onvolledig(zin):
    assert vertaal_rekenzin(zin) is None


def test_te_lange_zin():
    assert vertaal_rekenzin("wat is " + "drie plus " * 40 + "vijf") is None


def test_getalwoord_blijft_werken():
    assert getalwoord_naar_int("drie") == 3
    assert getalwoord_naar_int("tweeëntwintig") == 22
    assert getalwoord_naar_int("honderdvijf") == 105
    assert getalwoord_naar_int("tweeduizendvijfhonderd") == 2500
    assert getalwoord_naar_int("hond") is None
    assert getalwoord_naar_int("") is None