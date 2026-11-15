# tests/test_main_opstartregel.py
"""
Tests voor de opstarttijd-regel in de opstartbanner van main.py.
Uitvoeren: pytest tests/test_main_opstartregel.py -v
"""

import main
from core import opstarttijd
from modules.diagnose import controles_robuust


def test_geen_klaar_moment_geen_regel(monkeypatch):
    monkeypatch.setattr(opstarttijd, "_klaar", None)
    assert main.opstarttijd_regel() is None


def test_regel_toont_seconden_met_een_decimaal(monkeypatch):
    monkeypatch.setattr(opstarttijd, "_klaar", 123.0)
    monkeypatch.setattr(controles_robuust, "meet_opstart_s", lambda klaar: 38.24)
    assert main.opstarttijd_regel() == " Opgestart in 38.2 s"


def test_niet_meetbaar_geen_regel(monkeypatch):
    monkeypatch.setattr(opstarttijd, "_klaar", 123.0)
    monkeypatch.setattr(controles_robuust, "meet_opstart_s", lambda klaar: None)
    assert main.opstarttijd_regel() is None


def test_fout_in_meting_breekt_het_opstarten_niet(monkeypatch):
    monkeypatch.setattr(opstarttijd, "_klaar", 123.0)

    def stuk(klaar):
        raise RuntimeError("kapot")

    monkeypatch.setattr(controles_robuust, "meet_opstart_s", stuk)
    assert main.opstarttijd_regel() is None


def test_echte_meting_geeft_een_tekst_of_niets(monkeypatch):
    opstarttijd_nu = __import__("time").time()
    monkeypatch.setattr(opstarttijd, "_klaar", opstarttijd_nu)
    regel = main.opstarttijd_regel()
    assert regel is None or regel.startswith(" Opgestart in ")