# tests/test_taalbenchmark.py
"""
Tests voor de taalbenchmark (punt 61): de casebestanden zijn geldig en de nieuwe
tellers in tools/run_benchmark.py (per taalniveau, onterecht antwoord) kloppen.
Geen mini-Nova nodig.
"""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("run_benchmark_taal_test", ROOT / "tools" / "run_benchmark.py")
rb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rb)

VAST = ROOT / "tests" / "benchmark" / "benchmark_taalbegrip.json"
BLIND = ROOT / "tests" / "benchmark" / "benchmark_taalbegrip_blind.json"
CONTROLE_SLEUTELS = ("moet_event", "mag_event_niet", "moet_bevatten_een_van", "moet_bevatten_alle",
                     "moet_overeenkomen_een_van", "mag_niet_bevatten")


def _cases(pad):
    return json.loads(pad.read_text(encoding="utf-8"))["cases"]


ALLE = [(pad.name, c) for pad in (VAST, BLIND) for c in _cases(pad)]


def test_beide_bestanden_bestaan_en_hebben_cases():
    assert len(_cases(VAST)) >= 30
    assert len(_cases(BLIND)) >= 15


def test_id_s_zijn_uniek_over_beide_sets():
    ids = [c["id"] for _, c in ALLE]
    assert len(ids) == len(set(ids))


def test_vragen_zijn_niet_gedeeld_tussen_vast_en_blind():
    vast = {c["vraag"].lower() for c in _cases(VAST)}
    blind = {c["vraag"].lower() for c in _cases(BLIND)}
    assert not (vast & blind), "een blinde zin staat ook in de vaste set"


@pytest.mark.parametrize("bestand,case", ALLE, ids=[c["id"] for _, c in ALLE])
def test_case_is_geldig(bestand, case):
    assert case["vraag"].strip()
    assert case["taalniveau"] in (1, 2, 3, 4, 5)
    assert case["dimensie"] in rb.DIMENSIES
    assert case.get("categorie")
    assert any(case.get(k) for k in CONTROLE_SLEUTELS), "case heeft geen enkele controle"
    if "voorvragen" in case:
        assert isinstance(case["voorvragen"], list) and all(isinstance(v, str) and v.strip() for v in case["voorvragen"])


def test_contextcases_hebben_voorvragen_of_zijn_dubbelzinnig():
    for _, c in ALLE:
        if c["taalniveau"] == 4 and c["categorie"] in ("ellips", "verwijzing", "keuze"):
            assert c.get("voorvragen"), f"{c['id']} verwijst naar eerder, maar heeft geen voorvragen"


def test_onzekerheid_hoort_bij_taalniveau_5_en_andersom():
    for _, c in ALLE:
        assert (c["taalniveau"] == 5) == (c["dimensie"] == "onzekerheid"), c["id"]


def test_onbekende_woorden_krijgen_geen_stellig_ja_of_nee():
    """T5-vragen over een verzonnen woord moeten 'ja'/'nee' verbieden (anders meten ze niets)."""
    for _, c in ALLE:
        if c["taalniveau"] == 5 and c["categorie"] == "onbekend" and c["vraag"].lower().startswith("is een"):
            verboden = [w.lower() for w in c.get("mag_niet_bevatten", [])]
            assert "ja" in verboden and "nee" in verboden, c["id"]


def test_alle_taalniveaus_komen_voor_in_de_vaste_set():
    assert {c["taalniveau"] for c in _cases(VAST)} == {1, 2, 3, 4, 5}


# ---------------------------------------------------------
# tellers
# ---------------------------------------------------------
def _r(i, niveau, dim, status, reden=""):
    return ({"id": i, "taalniveau": niveau, "dimensie": dim, "vraag": f"vraag {i}"}, status, reden)


def test_tel_per_taalniveau():
    res = [_r("a", 1, "intentie", "geslaagd"), _r("b", 1, "intentie", "gefaald", "x"),
           _r("c", 2, "intentie", "geslaagd")]
    t = rb.tel_per(res, "taalniveau")
    assert t[1] == {"geslaagd": 1, "gefaald": 1, "fout": 0, "niet_meetbaar": 0}
    assert t[2]["geslaagd"] == 1


def test_tel_per_negeert_cases_zonder_het_veld():
    res = [({"id": "z", "vraag": "v"}, "geslaagd", "")]
    assert rb.tel_per(res, "taalniveau") == {}


def test_stellig_ja_is_onterecht_antwoord():
    res = [_r("a", 5, "onzekerheid", "gefaald", "antwoord bevat verboden woord(en) ['ja'] (antwoord: 'ja')")]
    assert [c["id"] for c, _ in rb.onterechte_antwoorden(res)] == ["a"]
    assert rb.niet_eerlijk_onzeker(res) == []


def test_stilte_is_geen_onterecht_antwoord_maar_wel_een_gat():
    res = [_r("a", 5, "onzekerheid", "gefaald", "geen antwoord ontvangen")]
    assert rb.onterechte_antwoorden(res) == []
    assert [c["id"] for c, _ in rb.niet_eerlijk_onzeker(res)] == ["a"]


def test_gefaalde_case_van_andere_dimensie_telt_niet_als_onterecht():
    res = [_r("a", 3, "redenering", "gefaald", "antwoord bevat verboden woord(en) ['nee']")]
    assert rb.onterechte_antwoorden(res) == []
    assert rb.niet_eerlijk_onzeker(res) == []


def test_geslaagde_onzekerheid_telt_niet_mee():
    res = [_r("a", 5, "onzekerheid", "geslaagd")]
    assert rb.onterechte_antwoorden(res) == []
    assert rb.niet_eerlijk_onzeker(res) == []


def test_rapporteer_geeft_exitcode_1_bij_onterecht_antwoord(capsys):
    res = [_r("a", 5, "onzekerheid", "gefaald", "antwoord bevat verboden woord(en) ['ja']")]
    assert rb.rapporteer(res, True, 2, "taal-vast", taal=True) == 1


def test_rapporteer_geeft_exitcode_0_bij_alleen_stilte(capsys):
    res = [_r("a", 5, "onzekerheid", "gefaald", "geen antwoord ontvangen")]
    assert rb.rapporteer(res, True, 2, "taal-vast", taal=True) == 0


def test_rapporteer_zonder_taalmodus_blijft_zoals_voorheen(capsys):
    res = [_r("a", 5, "onzekerheid", "gefaald", "antwoord bevat verboden woord(en) ['ja']")]
    assert rb.rapporteer(res, True, 2, "vast") == 0