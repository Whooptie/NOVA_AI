from core.concept_hint import bouw_graaf, zoek_hint, hint_voor_zin
import json


def maak(relaties):
    """relaties: lijst van (woord, doel, type, status)."""
    concepts = {}
    for woord, doel, typ, status in relaties:
        for w in (woord, doel):
            concepts.setdefault(w, {"senses": [{"relations": [], "status": "confirmed"}]})
        concepts[woord]["senses"][0]["relations"].append(
            {"type": typ, "target": doel, "status": status})
    return concepts


def test_direct_verbonden_woord_geeft_hint():
    c = maak([("nat", "regen", "related_to", "confirmed")])
    hint = zoek_hint("is het nat", c)
    assert hint["label"] == "rain" and hint["afstand"] == 1


def test_omgekeerde_richting_werkt():
    c = maak([("regen", "paraplu", "related_to", "confirmed")])
    assert zoek_hint("paraplu mee", c)["label"] == "rain"


def test_rejected_relatie_wordt_genegeerd():
    c = maak([("nat", "regen", "related_to", "rejected")])
    assert zoek_hint("is het nat", c) is None


def test_onbekend_woord_geeft_geen_hint():
    c = maak([("nat", "regen", "related_to", "confirmed")])
    assert zoek_hint("blorpfzz", c) is None


def test_te_ver_weg_geeft_geen_hint():
    c = maak([("a", "b", "related_to", "confirmed"),
              ("b", "c", "related_to", "confirmed"),
              ("c", "regen", "related_to", "confirmed")])
    assert zoek_hint("a", c) is None  # 3 stappen > MAX_AFSTAND


def test_gelijkspel_tussen_categorieen_geeft_geen_hint():
    c = maak([("x", "regen", "related_to", "confirmed"),
              ("x", "weer", "related_to", "confirmed")])
    assert zoek_hint("x", c) is None


def test_hint_voor_zin_leest_bestand(tmp_path):
    c = maak([("nat", "regen", "related_to", "confirmed")])
    pad = tmp_path / "concepts.json"
    pad.write_text(json.dumps(c), encoding="utf-8")
    assert hint_voor_zin("is het nat", str(pad))["label"] == "rain"
    assert hint_voor_zin("is het nat", str(tmp_path / "bestaat_niet.json")) is None


def test_via_tussenwoord_geeft_geen_hint():
    # a -> b -> regen is 2 stappen; sinds de ruis-analyse (2 nov 2026)
    # tellen alleen directe verbindingen mee.
    c = maak([("a", "b", "related_to", "confirmed"),
              ("b", "regen", "related_to", "confirmed")])
    assert zoek_hint("a", c) is None