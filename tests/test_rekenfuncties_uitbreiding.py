# tests/test_rekenfuncties_uitbreiding.py
#
# Deel 2 van core/rekenfuncties.py (28 oktober 2026): vectoren, matrices,
# fysica, kansen, breuken, reeksen, sorteren/zoeken, precisie.
# Uitvoeren: pytest tests/test_rekenfuncties_uitbreiding.py -v

import pytest

from core.rekenfuncties import vertaal_functiezin


@pytest.mark.parametrize("zin, verwacht", [
    # vectoren
    ("het inproduct van [1,2,3] en [4,5,6]", "dot([1, 2, 3], [4, 5, 6])"),
    ("kruisproduct van (1,0,0) en (0,1,0)", "cross([1, 0, 0], [0, 1, 0])"),
    ("de lengte van vector [3,4]", "norm([3, 4])"),
    ("de eenheidsvector van [3,4]", "unit([3, 4])"),
    ("de projectie van [1,2] op [1,0]", "proj([1, 2], [1, 0])"),
    # matrices
    ("de determinant van [[1,2],[3,4]]", "det([[1, 2], [3, 4]])"),
    ("de determinant van [1 2; 3 4]", "det([[1, 2], [3, 4]])"),
    ("de inverse van [[1,2],[3,4]]", "inverse([[1, 2], [3, 4]])"),
    ("inverteer [[1,2],[3,4]]", "inverse([[1, 2], [3, 4]])"),
    ("transponeer [[1,2],[3,4]]", "transpose([[1, 2], [3, 4]])"),
    ("de eenheidsmatrix van 3", "identity(3)"),
    ("3x3 eenheidsmatrix", "identity(3)"),
    ("los het stelsel [[2,1],[1,3]] met [5,10] op", "solve([[2, 1], [1, 3]], [5, 10])"),
    # math.py rekent rot* in radialen: graden worden hier omgerekend
    ("de rotatiematrix rond de x-as met 90 graden", "rotX(1.5707963267948966)"),
    ("roteer rond de z-as met 45 graden", "rotZ(0.7853981633974483)"),
    ("de rotatiematrix rond de y-as met 0 graden", "rotY(0.0)"),
    ("de rotatiematrix rond de x-as met 1,5 radialen", "rotX(1.5)"),
    # fysica
    ("wat is de kracht bij een massa van 1000 kg en een versnelling van 3 m/s²", "kracht(1000, 3)"),
    ("de kinetische energie bij een massa van 5 en een snelheid van 10", "energie_kinetisch(5, 10)"),
    ("de potentiële energie bij een massa van 2 kg en een hoogte van 10 m", "energie_potentieel(2, 10)"),
    ("de potentiele energie bij een massa van 2 en een hoogte van 10", "energie_potentieel(2, 10)"),
    ("de arbeid bij een kracht van 50 N over een afstand van 3 m", "arbeid(50, 3)"),
    ("de snelheid na 3 seconden bij een beginsnelheid van 0 en een versnelling van 9,81",
     "snelheid_na(0, 9.81, 3)"),
    ("de afstand na 4 s bij een beginsnelheid van 20 en een versnelling van min 5",
     "afstand_na(20, -5, 4)"),
    ("het bereik van een projectiel met snelheid 20 m/s onder een hoek van 45 graden",
     "projectiel(20, 45)"),
    ("de kracht bij een massa van tien en een versnelling van twee", "kracht(10, 2)"),
    # kansen en statistiek
    ("de kans op een som van 7 met 2 dobbelstenen", "kans_dobbelsteen(2, 7)"),
    ("de kans om 7 te gooien met 2 dobbelstenen", "kans_dobbelsteen(2, 7)"),
    ("de kans op minstens een van de 4 gewenste kaarten als ik 5 kaarten trek uit 52",
     "kans_kaart(4, 52, 5)"),
    ("de kans op precies 3 successen bij 10 pogingen en een kans van 0,5", "binomiaal(10, 3, 0.5)"),
    ("de normale kans bij z = 1,96", "normaal(1.96)"),
    ("de correlatie tussen [1,2,3,4] en [2,4,6,8]", "correlatie([1, 2, 3, 4], [2, 4, 6, 8])"),
    ("de lineaire regressie van [1,2,3,4] en [2,4,6,8]", "regressie([1, 2, 3, 4], [2, 4, 6, 8])"),
    ("het gemiddelde van [1,2,3,4]", "gemiddelde([1, 2, 3, 4])"),
    # breuken en reeksen
    ("1/3 + 1/6 als breuk", "breuk(1, 3) + breuk(1, 6)"),
    ("de som van x^2 voor x van 1 tot 5", "sigma(x^2, 1, 5)"),
    ("meetkundige reeks met beginwaarde 1, factor 2 en 5 termen", "meetkundige_reeks(1, 2, 5)"),
    # punt, nulpunt, precisie
    ("x^2 + 2x + 1 voor x = 3", "bereken(x^2 + 2x + 1, 3)"),
    ("een nulpunt van x^2 - 4 vanaf 1", "nulpunt(x^2 - 4, 1)"),
    ("stel de precisie in op 3", "stel_precisie_in(3)"),
    ("reset de precisie", "reset_precisie()"),
    ("rond 123456 af op 3 significante cijfers", "significante_cijfers(123456, 3)"),
    # sorteren, zoeken, woorden
    ("sorteer [5,2,8,1]", "quick_sort([5, 2, 8, 1])"),
    ("de positie van 7 in [1,3,5,7,9]", "binary_search([1, 3, 5, 7, 9], 7)"),
    ("de levenshtein afstand tussen kitten en sitting", 'levenshtein("kitten", "sitting")'),
])
def test_uitbreiding(zin, verwacht):
    assert vertaal_functiezin(zin) == verwacht


@pytest.mark.parametrize("zin", [
    "kruisproduct van [1,0] en [0,1]",               # alleen 3D
    "het inproduct van [1,2] en [1,2,3]",            # verschillende lengte
    "de determinant van [[1,2],[3,4],[5,6]]",        # niet vierkant
    "de determinant van [[1,2],[3]]",                # ongelijke rijen
    "los het stelsel [[2,1],[1,3]] met [5,10,1] op", # lengte klopt niet
    "de kracht bij een massa van een hond en een versnelling van 3",
    "de positie van 7 in [5,3,1]",                   # lijst niet gesorteerd
    "2 en 3 als breuk",
    "1/3 + x als breuk",
    "sorteer mijn kamer",
    "sorteer [5,hond,8]",
    "de kans op regen",
    "wat is een breuk",
    "de inverse van een probleem",
])
def test_uitbreiding_afwijzingen(zin):
    assert vertaal_functiezin(zin) is None