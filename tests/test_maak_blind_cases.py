# tests/test_maak_blind_cases.py
"""Tests voor tools/maak_blind_cases.py (eigen zinnen omzetten naar blinde taalcases)."""
import importlib.util
import json
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "tools" / "maak_blind_cases.py"
_spec = importlib.util.spec_from_file_location("maak_blind_cases_test", TOOL)
mb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mb)


def _sets(tmp_path, vast=None, blind=None):
    vp, bp = tmp_path / "vast.json", tmp_path / "blind.json"
    vp.write_text(json.dumps({"cases": vast or []}), encoding="utf-8")
    bp.write_text(json.dumps({"cases": blind or []}), encoding="utf-8")
    return vp, bp


def _tekst(tmp_path, inhoud):
    p = tmp_path / "zinnen.txt"
    p.write_text(inhoud, encoding="utf-8")
    return p


def test_definitie_regel_wordt_case(tmp_path):
    cases, fouten = mb.lees_regels(_tekst(tmp_path, "definitie | wat is een hond | wolf, dier\n"))
    assert fouten == []
    c = cases[0]
    assert c["taalniveau"] == 2 and c["dimensie"] == "intentie"
    assert c["moet_event"] == ["intent_definition"]
    assert c["moet_bevatten_een_van"] == ["wolf", "dier"]


@pytest.mark.parametrize("soort,event", [
    ("relatie", "intent_relation_check"), ("oorzaak", "intent_causes"),
    ("gevolg", "intent_effects"), ("synoniem", "intent_synonym"),
])
def test_elk_type_krijgt_zijn_event(tmp_path, soort, event):
    cases, fouten = mb.lees_regels(_tekst(tmp_path, f"{soort} | een vraag | ja\n"))
    assert fouten == [] and cases[0]["moet_event"] == [event]


def test_onbekend_is_taalniveau_5_en_verbiedt_ja_nee(tmp_path):
    cases, fouten = mb.lees_regels(_tekst(tmp_path, "onbekend | is een glorbix een vis\n"))
    assert fouten == []
    c = cases[0]
    assert c["taalniveau"] == 5 and c["dimensie"] == "onzekerheid"
    assert c["mag_niet_bevatten"] == ["ja", "nee"]
    assert "moet_event" not in c


def test_lege_regels_en_commentaar_worden_overgeslagen(tmp_path):
    cases, fouten = mb.lees_regels(_tekst(tmp_path, "# commentaar\n\nrelatie | is een kat een dier | ja\n"))
    assert fouten == [] and len(cases) == 1


def test_verwacht_woord_ontbreekt_is_fout(tmp_path):
    cases, fouten = mb.lees_regels(_tekst(tmp_path, "definitie | wat is een hond\n"))
    assert cases == [] and "verwacht woord" in fouten[0]


def test_onbekend_type_is_fout(tmp_path):
    _, fouten = mb.lees_regels(_tekst(tmp_path, "rekenen | wat is 1 plus 1 | 2\n"))
    assert "onbekend type" in fouten[0]


def test_regel_zonder_streepje_is_fout(tmp_path):
    _, fouten = mb.lees_regels(_tekst(tmp_path, "gewoon een zin\n"))
    assert "type | vraag | woorden" in fouten[0]


def test_droog_schrijft_niets(tmp_path):
    vp, bp = _sets(tmp_path)
    cases, _ = mb.lees_regels(_tekst(tmp_path, "relatie | is een kat een dier | ja\n"))
    nieuw, fouten = mb.voeg_toe(cases, vp, bp, schrijf=False)
    assert fouten == [] and len(nieuw) == 1
    assert json.loads(bp.read_text(encoding="utf-8"))["cases"] == []


def test_schrijf_voegt_toe_met_vervolgnummer(tmp_path):
    vp, bp = _sets(tmp_path, blind=[{"id": "blind-t2-03", "vraag": "oude vraag"}])
    cases, _ = mb.lees_regels(_tekst(tmp_path, "relatie | is een kat een dier | ja\nonbekend | is een glorbix een vis\n"))
    nieuw, fouten = mb.voeg_toe(cases, vp, bp, schrijf=True)
    assert fouten == []
    ids = [c["id"] for c in json.loads(bp.read_text(encoding="utf-8"))["cases"]]
    assert ids == ["blind-t2-03", "blind-t2-04", "blind-t5-01"]


def test_dubbele_vraag_in_vaste_set_wordt_geweigerd_en_niets_geschreven(tmp_path):
    vp, bp = _sets(tmp_path, vast=[{"id": "x", "vraag": "Is een kat een dier"}])
    cases, _ = mb.lees_regels(_tekst(tmp_path, "relatie | is een kat een dier | ja\nrelatie | is een hond een dier | ja\n"))
    nieuw, fouten = mb.voeg_toe(cases, vp, bp, schrijf=True)
    assert nieuw == [] and "staat al" in fouten[0]
    assert json.loads(bp.read_text(encoding="utf-8"))["cases"] == []


def test_dubbele_vraag_binnen_het_bestand_wordt_geweigerd(tmp_path):
    vp, bp = _sets(tmp_path)
    cases, _ = mb.lees_regels(_tekst(tmp_path, "relatie | is een kat een dier | ja\nrelatie | is een kat een dier | ja\n"))
    nieuw, fouten = mb.voeg_toe(cases, vp, bp, schrijf=True)
    assert nieuw == [] and fouten


def test_gemaakte_cases_zijn_geldig_voor_de_runner(tmp_path):
    """Elke gemaakte case heeft de velden die test_taalbenchmark.py eist."""
    cases, _ = mb.lees_regels(_tekst(tmp_path, "definitie | wat is een hond | dier\nonbekend | wat is een plimpstok\n"))
    for c in cases:
        assert c["taalniveau"] in (1, 2, 3, 4, 5) and c["dimensie"] and c["categorie"] and c["vraag"]
        assert any(c.get(k) for k in ("moet_event", "moet_bevatten_een_van", "mag_niet_bevatten"))


def test_main_geeft_exitcode_1_bij_fout_en_0_bij_succes(tmp_path, capsys):
    fout = _tekst(tmp_path, "definitie | wat is een hond\n")
    assert mb.main([str(fout)]) == 1
    goed = tmp_path / "goed.txt"
    goed.write_text("relatie | zeg eens, is een walvis een zoogdier | ja\n", encoding="utf-8")
    assert mb.main([str(goed)]) == 0