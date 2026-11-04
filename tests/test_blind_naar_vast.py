# tests/test_blind_naar_vast.py
"""Tests voor tools/blind_naar_vast.py (punt 62a)."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("blind_naar_vast_test", ROOT / "tools" / "blind_naar_vast.py")
bnv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bnv)


def _case(id_, niveau, vraag):
    return {"id": id_, "taalniveau": niveau, "dimensie": "intentie", "categorie": "definitie",
            "vraag": vraag, "moet_event": ["intent_definition"]}


def _sets(tmp_path, vast, blind):
    vp, bp = tmp_path / "vast.json", tmp_path / "blind.json"
    vp.write_text(json.dumps({"_uitleg": "v", "cases": vast}), encoding="utf-8")
    bp.write_text(json.dumps({"_uitleg": "b", "cases": blind}), encoding="utf-8")
    return vp, bp


def test_nummering_gaat_door_per_niveau():
    vast = {"cases": [_case("taal-t2-01", 2, "a"), _case("taal-t2-07", 2, "b"), _case("taal-t5-03", 5, "c")]}
    blind = {"cases": [_case("blind-t2-01", 2, "d"), _case("blind-t2-02", 2, "e"), _case("blind-t5-01", 5, "f")]}
    nieuw, over = bnv.plan_verhuizing(vast, blind)
    assert [c["id"] for _, c in nieuw] == ["taal-t2-08", "taal-t2-09", "taal-t5-04"]
    assert over == []


def test_dubbele_vraag_wordt_overgeslagen():
    vast = {"cases": [_case("taal-t2-01", 2, "Wat is een hond")]}
    blind = {"cases": [_case("blind-t2-01", 2, "wat is een hond"), _case("blind-t2-02", 2, "wat is regen")]}
    nieuw, over = bnv.plan_verhuizing(vast, blind)
    assert [c["vraag"] for _, c in nieuw] == ["wat is regen"]
    assert over == ["wat is een hond"]


def test_droog_schrijft_niets(tmp_path, capsys):
    vp, bp = _sets(tmp_path, [_case("taal-t2-01", 2, "a")], [_case("blind-t2-01", 2, "b")])
    voor_v, voor_b = vp.read_text(encoding="utf-8"), bp.read_text(encoding="utf-8")
    assert bnv.main([], vast_pad=str(vp), blind_pad=str(bp)) == 0
    assert vp.read_text(encoding="utf-8") == voor_v
    assert bp.read_text(encoding="utf-8") == voor_b
    assert "Niets geschreven" in capsys.readouterr().out


def test_schrijf_verhuist_en_leegt_blind(tmp_path):
    vp, bp = _sets(tmp_path, [_case("taal-t2-01", 2, "a")], [_case("blind-t2-01", 2, "b")])
    assert bnv.main(["--schrijf"], vast_pad=str(vp), blind_pad=str(bp)) == 0
    vast = json.loads(vp.read_text(encoding="utf-8"))
    blind = json.loads(bp.read_text(encoding="utf-8"))
    assert [c["id"] for c in vast["cases"]] == ["taal-t2-01", "taal-t2-02"]
    assert vast["cases"][1]["vraag"] == "b"
    assert blind["cases"] == []
    assert blind["_uitleg"] == "b"


def test_lege_blinde_set_is_geen_fout(tmp_path):
    vp, bp = _sets(tmp_path, [_case("taal-t2-01", 2, "a")], [])
    assert bnv.main(["--schrijf"], vast_pad=str(vp), blind_pad=str(bp)) == 0