# tests/test_math_veilige_macht.py
"""
"9**9**9" liet Nova minutenlang vastlopen (gevonden door de rommel-invoertest, 14 november 2026).
modules/math/math.py weigert nu een macht met een absurd groot geheel getal als uitkomst.
"""
from fractions import Fraction

import pytest

from modules.math import math as m


@pytest.mark.parametrize("basis,exponent,waarde", [
    (2, 10, 1024), (2, 10000, 2 ** 10000), (10, -5, 10 ** -5), (2, 0.5, 2 ** 0.5), (0, 99999999, 0),
    (1, 99999999, 1), (-1, 99999999, -1), (Fraction(1, 3), 3, Fraction(1, 27)), (5, 1, 5), (7, 0, 1),
])
def test_gewone_machten_blijven_werken(basis, exponent, waarde):
    assert m.veilige_macht(basis, exponent) == waarde


@pytest.mark.parametrize("basis,exponent", [
    (9, 9 ** 9), (10, 10_000_000), (99999999999, 99999999), (2, 100_001), (Fraction(1, 3), 10 ** 9),
    (-9, 9 ** 9),
])
def test_absurd_grote_machten_worden_geweigerd(basis, exponent):
    with pytest.raises(ValueError, match="veel te groot"):
        m.veilige_macht(basis, exponent)


def test_de_grens_is_een_bovengrens_op_het_aantal_bits():
    assert m.veilige_macht(2, 50_000) > 0               # 2 telt als 2 bits: 50.000 x 2 = precies de grens
    with pytest.raises(ValueError):
        m.veilige_macht(2, 50_001)


def test_booleans_en_floats_worden_niet_geblokkeerd():
    assert m.veilige_macht(True, 5) == 1
    assert m.veilige_macht(9.0, 100) == 9.0 ** 100


class NepBus:
    modules = {}

    def subscribe(self, *a, **k):
        pass

    def publish(self, *a, **k):
        pass


def test_de_rekenmodule_gebruikt_de_veilige_macht():
    rekenaar = m.MathModule(NepBus())
    assert rekenaar.ops[m.ast.Pow] is m.veilige_macht
    assert rekenaar._eval(m.ast.parse("2**10", mode="eval").body) == 1024
    with pytest.raises(ValueError, match="veel te groot"):
        rekenaar._eval(m.ast.parse("9**9**9", mode="eval").body)