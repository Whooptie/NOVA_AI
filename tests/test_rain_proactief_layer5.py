"""Tests voor punt 47: rain.check_proactief respecteert Layer 5 (can_interrupt)."""
from datetime import datetime, timedelta

import pytest

from modules.weather import rain
from modules.weather.rain import RainModule, Slot, Kwartier, Weerpunt


NU = datetime(2026, 12, 10, 14, 0)   # overdag, buiten de stille uren


class FakeBus:
    def __init__(self):
        self.gepubliceerd = []

    def subscribe(self, *a, **k):
        pass

    def publish(self, naam, data=None):
        self.gepubliceerd.append((naam, data))


def regen_slots():
    # droog nu, regen (2 mm/u) vanaf over 10 minuten
    slots = []
    for i in range(12):
        start = NU + timedelta(minutes=5 * i)
        mm = 0.0 if i < 2 else 2.0
        slots.append(Slot(start, start + timedelta(minutes=5), mm))
    return slots


def kwartieren(code=0):
    return [
        Kwartier(NU + timedelta(minutes=15 * i), NU + timedelta(minutes=15 * (i + 1)),
                 False, False, code)
        for i in range(12)
    ]


def onweer_kwartieren():
    # onweer vanaf over 30 min
    return [
        Kwartier(NU + timedelta(minutes=15 * i), NU + timedelta(minutes=15 * (i + 1)),
                 False, False, 95 if i >= 2 else 0)
        for i in range(12)
    ]


def gevaar_punten(temp=-2.0):
    return [
        Weerpunt(NU + timedelta(minutes=15 * i), NU + timedelta(minutes=15 * (i + 1)),
                 temp, 0.4 if i >= 2 else 0.0, 3.0, 5.0)
        for i in range(12)
    ]


def maak_module(monkeypatch, slots=None, typeinfo=None, punten=None):
    bus = FakeBus()
    m = RainModule(bus, None)
    monkeypatch.setattr(m, "get_coordinates", lambda stad: (51.0, 3.0))
    monkeypatch.setattr(RainModule, "haal_typeinfo", staticmethod(lambda la, lo: typeinfo or kwartieren()))
    monkeypatch.setattr(RainModule, "haal_slots", staticmethod(lambda la, lo, nu: (slots or [], False)))
    monkeypatch.setattr(rain, "haal_gevaar", lambda la, lo: punten or [])
    return m, bus


def teksten(bus):
    return [d["text"] for n, d in bus.gepubliceerd if n == "layer4_response"]


def test_zonder_mag_spreken_werkt_alles_zoals_voorheen(monkeypatch):
    m, bus = maak_module(monkeypatch, slots=regen_slots())
    assert m.check_proactief(nu=NU) is not None
    assert len(teksten(bus)) == 1


def test_regen_wordt_gemeld_als_layer5_ja_zegt(monkeypatch):
    m, bus = maak_module(monkeypatch, slots=regen_slots())
    m.check_proactief(nu=NU, mag_spreken=lambda: True)
    assert len(teksten(bus)) == 1
    assert m._proactief_staat["gemeld"] is True


def test_regen_wacht_als_layer5_nee_zegt(monkeypatch):
    m, bus = maak_module(monkeypatch, slots=regen_slots())
    assert m.check_proactief(nu=NU, mag_spreken=lambda: False) is None
    assert teksten(bus) == []
    assert m._proactief_staat["gemeld"] is False   # staat NIET bijgewerkt


def test_melding_komt_alsnog_als_layer5_later_ja_zegt(monkeypatch):
    m, bus = maak_module(monkeypatch, slots=regen_slots())
    m.check_proactief(nu=NU, mag_spreken=lambda: False)
    m.check_proactief(nu=NU + timedelta(minutes=5), mag_spreken=lambda: True)
    assert len(teksten(bus)) == 1


def test_na_melding_geen_herhaling(monkeypatch):
    m, bus = maak_module(monkeypatch, slots=regen_slots())
    m.check_proactief(nu=NU, mag_spreken=lambda: True)
    m.check_proactief(nu=NU + timedelta(minutes=5), mag_spreken=lambda: True)
    assert len(teksten(bus)) == 1


def test_onweer_wacht_en_komt_later(monkeypatch):
    m, bus = maak_module(monkeypatch, typeinfo=onweer_kwartieren())
    m.check_proactief(nu=NU, mag_spreken=lambda: False)
    assert teksten(bus) == []
    assert m._onweer_staat["gemeld"] is False
    m.check_proactief(nu=NU + timedelta(minutes=5), mag_spreken=lambda: True)
    assert len(teksten(bus)) == 1
    assert "onweer" in teksten(bus)[0]


def test_gladheid_onder_nul_wacht_en_komt_later(monkeypatch):
    m, bus = maak_module(monkeypatch, punten=gevaar_punten(-2.0))
    m.check_proactief(nu=NU, mag_spreken=lambda: False)
    assert teksten(bus) == []
    assert m._gevaar_staat["gladheid"]["gemeld"] is False
    m.check_proactief(nu=NU + timedelta(minutes=5), mag_spreken=lambda: True)
    assert any("gladheid" in t for t in teksten(bus))


def test_layer5_wordt_hoogstens_een_keer_per_check_gevraagd(monkeypatch):
    m, bus = maak_module(monkeypatch, slots=regen_slots(),
                         typeinfo=onweer_kwartieren(), punten=gevaar_punten(-2.0))
    teller = []
    m.check_proactief(nu=NU, mag_spreken=lambda: teller.append(1) or True)
    assert len(teller) == 1
    assert len(teksten(bus)) >= 3


def test_layer5_wordt_niet_gevraagd_als_er_niets_te_melden_is(monkeypatch):
    m, bus = maak_module(monkeypatch)
    teller = []
    m.check_proactief(nu=NU, mag_spreken=lambda: teller.append(1) or True)
    assert teller == []


def test_fout_in_layer5_betekent_wachten_en_geen_crash(monkeypatch):
    m, bus = maak_module(monkeypatch, slots=regen_slots())

    def kapot():
        raise RuntimeError("boem")

    assert m.check_proactief(nu=NU, mag_spreken=kapot) is None
    assert teksten(bus) == []
    assert m._proactief_staat["gemeld"] is False