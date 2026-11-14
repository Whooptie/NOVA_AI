# tests/test_math_matrix_bewerkingen.py
# Legt vast hoe getallen, vectoren en matrices met elkaar rekenen.
#
# Achtergrond: voorheen werd de gevraagde bewerking soms genegeerd.
# "[[1,2],[3,4]] / 2" en "[[1,2],[3,4]] ** 2" deden stilletjes een
# VERMENIGVULDIGING, en "matrix + vector" deed een matrix-vector-product.
# Nu geldt: of het antwoord klopt, of er komt een duidelijke foutmelding.
import pytest

from modules.math.math import MathModule


class FakeBus:
    def __init__(self):
        self.events = []

    def subscribe(self, naam, fn):
        pass

    def publish(self, naam, data=None):
        self.events.append((naam, data))


@pytest.fixture
def m():
    return MathModule(FakeBus())


def rek(m, expr):
    return m.eval_expr(m.preprocess(expr))


M = "[[1,2],[3,4]]"


# ---------- getal en matrix: elementsgewijs ----------
@pytest.mark.parametrize("expr, verwacht", [
    (f"2 * {M}", [[2, 4], [6, 8]]),
    (f"{M} * 2", [[2, 4], [6, 8]]),
    (f"2 + {M}", [[3, 4], [5, 6]]),
    (f"{M} + 2", [[3, 4], [5, 6]]),
    (f"10 - {M}", [[9, 8], [7, 6]]),
    (f"{M} - 1", [[0, 1], [2, 3]]),
    (f"{M} / 2", [[0.5, 1.0], [1.5, 2.0]]),
])
def test_getal_en_matrix_elementsgewijs(m, expr, verwacht):
    assert rek(m, expr) == verwacht


@pytest.mark.parametrize("expr", [
    f"2 / {M}",
    f"{M} ** 2",
    f"2 ** {M}",
])
def test_getal_en_matrix_niet_ondersteund(m, expr):
    with pytest.raises(ValueError, match="wordt niet ondersteund"):
        rek(m, expr)


# ---------- matrix en matrix ----------
def test_matrix_keer_matrix(m):
    assert rek(m, f"{M} * [[0,1],[1,0]]") == [[2, 1], [4, 3]]


def test_matrix_plus_en_min_matrix(m):
    assert rek(m, f"{M} + {M}") == [[2, 4], [6, 8]]
    assert rek(m, f"{M} - {M}") == [[0, 0], [0, 0]]


@pytest.mark.parametrize("expr", [f"{M} / {M}", f"{M} ** {M}"])
def test_matrix_delen_of_macht_matrix_niet_ondersteund(m, expr):
    with pytest.raises(ValueError, match="wordt niet ondersteund"):
        rek(m, expr)


# ---------- matrix en vector ----------
def test_matrix_keer_vector(m):
    assert rek(m, f"{M} * [1,2]") == [5, 11]


@pytest.mark.parametrize("expr", [f"{M} + [1,2]", f"{M} - [1,2]", f"{M} / [1,2]", f"{M} ** [1,2]"])
def test_matrix_en_vector_alleen_vermenigvuldigen(m, expr):
    with pytest.raises(ValueError, match="wordt niet ondersteund"):
        rek(m, expr)


# ---------- vectoren: ongewijzigd ----------
@pytest.mark.parametrize("expr, verwacht", [
    ("[1,2,3] + [4,5,6]", [5, 7, 9]),
    ("[1,2,3] * 2", [2, 4, 6]),
    ("2 + [1,2,3]", [3, 4, 5]),
    ("[1,2,3] ** 2", [1, 4, 9]),
    ("[2,4] / 2", [1.0, 2.0]),
])
def test_vectoren_blijven_zoals_ze_waren(m, expr, verwacht):
    assert rek(m, expr) == verwacht


def test_vectoren_verschillende_lengte(m):
    with pytest.raises(ValueError, match="even lang"):
        rek(m, "[1,2,3] + [1,2]")


def test_matrix_dimensies_kloppen_niet(m):
    with pytest.raises(ValueError, match="dimensies"):
        rek(m, f"{M} + [[1,2,3],[4,5,6]]")
    with pytest.raises(ValueError, match="dimensies"):
        rek(m, f"{M} * [[1,2,3],[4,5,6],[7,8,9]]")


# ---------- de losse variabele x werkt ook binnen .to() ----------
def test_variabele_x_binnen_to(m):
    assert str(rek(m, "polyeval((x*m).to(cm), 2)")) == "200.0 cm"