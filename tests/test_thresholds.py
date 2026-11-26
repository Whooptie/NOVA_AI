import pytest

from core.thresholds import Drempel


def test_vuurt_een_keer_bij_overschrijding():
    d = Drempel(0.7, 0.6)
    assert d.kruist(0.75) is True
    assert d.kruist(0.8) is False
    assert d.kruist(0.9) is False


def test_herwapent_pas_onder_de_onderdrempel():
    d = Drempel(0.7, 0.6)
    d.kruist(0.75)
    assert d.kruist(0.65) is False
    assert d.kruist(0.55) is False
    assert d.kruist(0.71) is True


def test_blijft_hangen_rond_de_grens_zonder_spam():
    d = Drempel(0.7, 0.6)
    d.kruist(0.71)
    for w in (0.69, 0.72, 0.68, 0.73):
        assert d.kruist(w) is False


def test_set_initialiseert_zonder_te_vuren():
    d = Drempel(0.7, 0.6)
    d.set(0.9)
    assert d.kruist(0.95) is False
    d.kruist(0.5)
    assert d.kruist(0.8) is True


def test_laag_boven_hoog_is_fout():
    with pytest.raises(ValueError):
        Drempel(0.5, 0.9)