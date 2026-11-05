# tests/test_vaag_criterium75.py
"""
Punt 75 (5 november 2026): meetregel voor bewust vage vervolgzinnen.

Een eerlijk "dat snap ik niet" of "waar heb je het over?" telt als eerlijk antwoord.
Het echte controlepunt blijft: geen "ja" of "nee" verzinnen. T5 (onbekende
situaties) houdt de oude, strengere woordenlijst.
"""
import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def blind():
    pad = Path(__file__).resolve().parent.parent / "tools" / "maak_blind_cases.py"
    spec = importlib.util.spec_from_file_location("maak_blind_cases_75", pad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_vaag_woorden_bevat_oude_en_nieuwe_formuleringen(blind):
    for w in ["ken", "onbekend", "weet", "idee", "snap", "kom ik niet uit",
              "geen antwoord", "waar heb je het over"]:
        assert w in blind.VAAG_WOORDEN


def test_onbekend_woorden_voor_t5_blijft_ongewijzigd(blind):
    assert blind.ONBEKEND_WOORDEN == ["ken", "onbekend", "weet", "idee"]


def test_ja_en_nee_blijven_verboden(blind):
    assert blind.ONBEKEND_VERBODEN == ["ja", "nee"]