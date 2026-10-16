# tests/test_self_uiterlijk.py
"""
Tests voor identity/self_uiterlijk.py (Nova beschrijft haar uiterlijk).
Gebruikt een EIGEN tijdelijk JSON-bestand (tmp_path), nooit het echte
data/uiterlijk.json, zodat deze tests niet breken als Kevin zinnen aanpast.
"""

import json
import os
import time

import pytest

from identity import self_uiterlijk


class DummyEventBus:
    """Neemt gepubliceerde events op; doet verder niets."""
    def __init__(self):
        self.gepubliceerd = []
        self.modules = {}

    def publish(self, naam, data=None):
        self.gepubliceerd.append((naam, data))


DATA = {
    "delen": {
        "algemeen": {
            "zinnen": ["hoe zie je eruit", "wat is je uiterlijk"],
            "zinsdelen": {"opening": ["A1", "A2"], "midden": ["A3"], "slot": ["A4"]},
        },
        "haar": {
            "namen": ["haar", "kapsel"],
            "zinsdelen": {"opening": ["H1", "H2"], "midden": ["H3", "H4"], "slot": ["H5", "H6"]},
        },
        "ogen": {
            "namen": ["ogen", "oog", "oogkleur"],
            "zinsdelen": {"opening": ["O1"], "midden": ["O2", "O3"], "slot": ["O4"]},
        },
        "kin": {
            "namen": ["kin"],
            "zinsdelen": {"opening": ["K1"], "midden": ["K2"], "slot": ["K3"]},
        },
    }
}


@pytest.fixture
def pad(tmp_path):
    p = tmp_path / "uiterlijk.json"
    p.write_text(json.dumps(DATA), encoding="utf-8")
    return p


# ---------------- vind_deel ----------------

def test_vind_deel_vindt_naam(pad):
    assert self_uiterlijk.vind_deel("welke kleur hebben je ogen", pad) == "ogen"


def test_vind_deel_hele_woorden_enkel(pad):
    # 'kin' zit in 'kind', maar dat is geen hele-woord-match
    assert self_uiterlijk.vind_deel("hoe ziet een kind eruit", pad) is None


def test_vind_deel_geen_treffer(pad):
    assert self_uiterlijk.vind_deel("hoe laat is het", pad) is None


# ---------------- herken_vraag ----------------

@pytest.mark.parametrize("zin,verwacht", [
    ("hoe ziet je haar eruit?", (True, "haar")),
    ("Hoe ziet jouw haar eruit", (True, "haar")),
    ("hoe zien je ogen eruit", (True, "ogen")),
    ("welke kleur hebben je ogen", (True, "ogen")),
    ("wat voor kapsel heb je", (True, "haar")),
    ("beschrijf je haar", (True, "haar")),
    ("hoe zijn je ogen", (True, "ogen")),
    ("hoe zie je eruit", (True, "algemeen")),
    ("wat is je uiterlijk?", (True, "algemeen")),
])
def test_herken_vraag_ja(pad, zin, verwacht):
    assert self_uiterlijk.herken_vraag(zin, pad) == verwacht


@pytest.mark.parametrize("zin", [
    "ik zie haar morgen",            # 'haar' als voornaamwoord, geen vraagvorm
    "hoe laat is het",
    "wie ben je",
    "beschrijf jezelf",              # identity, niet uiterlijk
    "wat voor muziek heb je",        # trigger zonder bekend deel -> niet claimen
    "hoe ziet het weer eruit",       # geen 'je'
])
def test_herken_vraag_nee(pad, zin):
    assert self_uiterlijk.herken_vraag(zin, pad) == (False, None)


def test_herken_vraag_onbekend_deel_geeft_none(pad):
    # Een deel dat NIET in de JSON staat: wel herkend als uiterlijkvraag,
    # maar deel=None -> neutrale afwijzing.
    assert self_uiterlijk.herken_vraag("hoe ziet jouw buik eruit", pad) == (True, None)


# ---------------- get_beschrijving ----------------

def test_beschrijving_bestaat_uit_drie_delen(pad):
    for _ in range(30):
        tekst = self_uiterlijk.get_beschrijving("haar", pad=pad)
        o, m, s = tekst.split(" ")
        assert o in ("H1", "H2")
        assert m in ("H3", "H4")
        assert s in ("H5", "H6")


def test_beschrijving_alle_combinaties_mogelijk(pad):
    gezien = {self_uiterlijk.get_beschrijving("haar", pad=pad) for _ in range(500)}
    assert len(gezien) == 8  # 2 x 2 x 2


def test_onbekend_deel_geeft_afwijzing(pad):
    tekst = self_uiterlijk.get_beschrijving("buik", pad=pad)
    assert tekst in self_uiterlijk._ONBEKEND


def test_none_geeft_afwijzing(pad):
    assert self_uiterlijk.get_beschrijving(None, pad=pad) in self_uiterlijk._ONBEKEND


def test_ontbrekend_bestand_crasht_niet(tmp_path):
    pad = tmp_path / "bestaat_niet.json"
    assert self_uiterlijk.get_beschrijving("haar", pad=pad) in self_uiterlijk._ONBEKEND
    # Zonder JSON kent Nova geen enkel deel: een duidelijke uiterlijkvraag
    # krijgt dan de neutrale afwijzing (deel=None), geen crash.
    assert self_uiterlijk.herken_vraag("hoe ziet je haar eruit", pad) == (True, None)
    assert self_uiterlijk.herken_vraag("hoe laat is het", pad) == (False, None)


def test_publiceert_variant_gekozen_via_kiezer(pad):
    bus = DummyEventBus()
    self_uiterlijk.get_beschrijving("ogen", event_bus=bus, pad=pad)
    namen = [d["sjabloon_naam"] for n, d in bus.gepubliceerd if n == "variant_gekozen"]
    assert namen == ["uiterlijk_ogen_opening", "uiterlijk_ogen_midden", "uiterlijk_ogen_slot"]


# ---------------- uitbreidbaarheid ----------------

def test_nieuw_deel_zonder_code(pad):
    # Kevin voegt later een deel toe: enkel de JSON verandert.
    nieuwe = json.loads(pad.read_text(encoding="utf-8"))
    nieuwe["delen"]["neus"] = {
        "namen": ["neus"],
        "zinsdelen": {"opening": ["N1"], "midden": ["N2"], "slot": ["N3"]},
    }
    pad.write_text(json.dumps(nieuwe), encoding="utf-8")
    # wijzigingstijd zeker anders (sommige bestandssystemen zijn grof)
    nu = time.time() + 5
    os.utime(pad, (nu, nu))

    assert self_uiterlijk.herken_vraag("hoe ziet je neus eruit", pad) == (True, "neus")
    assert self_uiterlijk.get_beschrijving("neus", pad=pad) == "N1 N2 N3"


def test_kapotte_json_houdt_vorige_versie(pad):
    assert self_uiterlijk.vind_deel("je haar", pad) == "haar"   # laadt en cachet
    pad.write_text("{ dit is kapot", encoding="utf-8")
    nu = time.time() + 5
    os.utime(pad, (nu, nu))
    assert self_uiterlijk.vind_deel("je haar", pad) == "haar"   # oude versie blijft