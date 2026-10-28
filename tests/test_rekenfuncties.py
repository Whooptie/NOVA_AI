# tests/test_rekenfuncties.py
#
# Gewone taal -> math.py-functies (core/rekenfuncties.py, 28 oktober 2026).
# Uitvoeren: pytest tests/test_rekenfuncties.py -v

import pytest

from core.rekenfuncties import vertaal_functiezin, vertaal_wiskundezin


@pytest.mark.parametrize("zin, verwacht", [
    # afgeleide / integraal / limiet
    ("wat is de afgeleide van x kwadraat in 3", "afgeleide(x^2, 3)"),
    ("de afgeleide van x^2 in het punt 3", "afgeleide(x^2, 3)"),
    ("de afgeleide van x^3 + 2x", "differentiate(x^3 + 2x)"),
    ("differentieer x^2", "differentiate(x^2)"),
    ("leid x^2 af", "differentiate(x^2)"),
    ("wat is de integraal van x^2 van 0 tot 3", "integraal(x^2, 0, 3)"),
    ("integraal van x^2 tussen nul en drie", "integraal(x^2, 0, 3)"),
    ("integreer x^2", "integrate_sym(x^2)"),
    ("de limiet van sin(x)/x als x naar 0 gaat", "limiet(sin(x) / x, 0)"),
    # algebra
    ("ontbind x^2 - 4", "factor_sym(x^2 - 4)"),
    ("ontbind x kwadraat min vier in factoren", "factor_sym(x^2 - 4)"),
    ("werk de haakjes uit van (x+1)^2", "expand_sym((x + 1)^2)"),
    ("werk (x+1)^2 uit", "expand_sym((x + 1)^2)"),
    ("vereenvoudig sin(x)^2 + cos(x)^2", "simplify_sym(sin(x)^2 + cos(x)^2)"),
    # vergelijkingen
    ("zoek de waarde van x, als 2x + 3 = 11", "solve_sym(2x + 3 = 11)"),
    ("zoek de waarde van x als twee x plus drie gelijk aan elf", "solve_sym(2x + 3 = 11)"),
    ("los x^2 - 5x + 6 = 0 op", "solve_sym(x^2 - 5x + 6 = 0)"),
    ("los op x^2 - 5x + 6 = 0", "solve_sym(x^2 - 5x + 6 = 0)"),
    ("los de vergelijking 3x = 12 op", "solve_sym(3x = 12)"),
    ("voor welke x geldt 3x = 12", "solve_sym(3x = 12)"),
    ("los x+y=10 en x-y=2 op", "solve_stelsel(x + y = 10, x - y = 2)"),
    ("de nulpunten van x^2 - 4", "solve_sym(x^2 - 4 = 0)"),
    # getaltheorie en combinatoriek
    ("de grootste gemene deler van 48 en 18", "ggd(48, 18)"),
    ("kun je de grootste gemene deler van 48 en 18 berekenen", "ggd(48, 18)"),
    ("het kleinste gemene veelvoud van 4 en 6", "kgv(4, 6)"),
    ("wat is de faculteit van vijf", "faculteit(5)"),
    ("zes faculteit", "faculteit(6)"),
    ("is zeventien een priemgetal", "is_priem(17)"),
    ("alle priemgetallen tot dertig", "priemgetallen(30)"),
    ("wat is de rest van 17 gedeeld door 5", "modulo(17, 5)"),
    ("17 modulo 5", "modulo(17, 5)"),
    ("combinaties van 2 uit 5", "combinaties(5, 2)"),
    ("hoeveel manieren zijn er om 2 uit 5 te kiezen", "combinaties(5, 2)"),
    ("permutaties van 2 uit 5", "permutaties(5, 2)"),
    ("de som van 1 tot 100", "som_reeks(1, 100)"),
    # statistiek
    ("wat is het gemiddelde van 2, 4 en 6", "gemiddelde([2, 4, 6])"),
    ("de mediaan van 1, 3, 2", "mediaan([1, 3, 2])"),
    ("de modus van 1, 2, 2, 3", "modus([1, 2, 2, 3])"),
    ("de standaardafwijking van 2, 4, 6", "stdafwijking([2, 4, 6])"),
    # talstelsels, afronden, absolute waarde
    ("255 naar binair", "naar_binair(255)"),
    ("zet 255 om naar hex", "naar_hex(255)"),
    ("ff hex naar decimaal", 'vanuit_talstelsel("ff", 16)'),
    ("rond 3,14159 af op 2 decimalen", "round(3.14159, 2)"),
    ("de absolute waarde van min vijf", "abs(-5)"),
])
def test_functiezinnen(zin, verwacht):
    assert vertaal_functiezin(zin) == verwacht


@pytest.mark.parametrize("zin", [
    "", "   ", None, 42,
    "los het probleem op",
    "ontbind mij",
    "vereenvoudig het",
    "werk dat uit",
    "wat is een hond",
    "de afgeleide van een hond",
    "is dit een priemgetal",
    "het gemiddelde van 5",
    "de grootste gemene deler van 48",
    "de grootste gemene deler van 4,5 en 3",     # alleen hele getallen
    "255,5 naar binair",
    "zet min 5 om naar binair",
    "los 2x + 3 op",                             # geen vergelijking
    "los x+y=10 en x-y=2",                       # onvolledig: 'op' ontbreekt
    "de limiet van sin(x)/x",
    "3+5",
    "wat is er gebeurd op 9/11",
])
def test_geen_functiezin_geeft_none(zin):
    assert vertaal_functiezin(zin) is None


# --- vertaal_wiskundezin = functies eerst, dan de gewone rekenzin ---------
@pytest.mark.parametrize("zin, verwacht", [
    ("ontbind x^2 - 4", "factor_sym(x^2 - 4)"),
    ("wat is de som van drie en vijf", "3 + 5"),
    ("de som van 1 tot 100", "som_reeks(1, 100)"),
    ("wat is vijf kwadraat", "5 ^ 2"),
    ("twee maal de som van drie en vijf", "2 * (3 + 5)"),
    ("wat is drie plus vijf", "3 + 5"),
])
def test_wiskundezin(zin, verwacht):
    assert vertaal_wiskundezin(zin) == verwacht


@pytest.mark.parametrize("zin", [
    "wat is een hond", "wat is x plus 3", "3+5", "wat is er gebeurd op 9/11", "",
])
def test_wiskundezin_none(zin):
    assert vertaal_wiskundezin(zin) is None