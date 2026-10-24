"""Tests voor modules/knowledge/graph_render_3d.py (Semantic Fase 13.2b). Schrijft alleen in tmp_path."""

import json
import os
import re

import pytest

from modules.knowledge import graph_data as gd
from modules.knowledge import graph_render_3d as r3

pytestmark = pytest.mark.skipif(not os.path.isfile(r3.LIB_PAD),
                                reason="vendor/3d-force-graph.min.js ontbreekt")


def _sense(woord, definitie="een ding", relaties=None):
    return {"sense_id": f"{woord}#1", "definition": definitie, "status": "confirmed",
            "relations": [{"type": t, "target": x, "status": "confirmed", "source": "user", "confidence": 1.0}
                          for t, x in (relaties or [])]}


@pytest.fixture
def concepten():
    return {
        "fiets": {"senses": [_sense("fiets", "een voertuig", [("is_a", "voertuig"), ("has_part", "wiel")])]},
        "voertuig": {"senses": [_sense("voertuig", "om mee te rijden", [("related_to", "weg")])]},
        "wiel": {"senses": [_sense("wiel", "rond")]},
        "weg": {"senses": [_sense("weg", "strook")]},
    }


def _data(html):
    m = re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S)
    return json.loads(m.group(1))


def test_pagina_bevat_data_en_bibliotheek(concepten):
    html = r3.render_html_3d(concepten, "fiets")
    data = _data(html)
    assert data["centrum"] == "fiets"
    assert {n["id"] for n in data["nodes"]} == {"fiets", "voertuig", "wiel", "weg"}   # ALLES zit erin
    assert "ForceGraph3D" in html


def test_start_volgt_diepte(concepten):
    assert set(_data(r3.render_html_3d(concepten, "fiets", diepte=1))["start"]) == {"fiets", "voertuig", "wiel"}
    assert "weg" in _data(r3.render_html_3d(concepten, "fiets", diepte=2))["start"]


def test_geen_externe_bronnen(concepten):
    html = r3.render_html_3d(concepten, "fiets")
    assert not re.search(r'(src|href)\s*=\s*["\']https?:', html)
    assert "cdn." not in html.split("<script>")[0]


def test_gevaarlijke_definitie_kan_pagina_niet_uitbreken(concepten):
    concepten["fiets"]["senses"][0]["definition"] = '</script><img src=x onerror=alert(1)>&'
    html = r3.render_html_3d(concepten, "fiets")
    blob = re.search(r'id="data">(.*?)</script>', html, re.S).group(1)
    assert "<" not in blob and ">" not in blob and "&" not in blob
    assert _data(html)["nodes"][0]["def"] or True          # nog steeds geldige JSON


def test_titel_wordt_geescaped(concepten):
    html = r3.render_html_3d(concepten, "fiets", titel="<b>x</b>")
    assert "<title>&lt;b&gt;x&lt;/b&gt;</title>" in html


def test_onbekend_concept(concepten):
    with pytest.raises(ValueError):
        r3.render_html_3d(concepten, "bestaatniet")


def test_pad_wordt_meegegeven(concepten):
    pad = gd.vind_pad(concepten, "wiel", "weg")
    assert _data(r3.render_html_3d(concepten, "fiets", pad=pad))["pad"] == ["wiel", "fiets", "voertuig", "weg"]


def test_ontbrekende_bibliotheek_geeft_duidelijke_fout(concepten, monkeypatch, tmp_path):
    monkeypatch.setattr(r3, "LIB_PAD", str(tmp_path / "bestaat_niet.js"))
    with pytest.raises(RuntimeError, match="3d-force-graph"):
        r3.render_html_3d(concepten, "fiets")


def test_schrijf_html_3d_blijft_in_map(concepten, tmp_path):
    map_pad = str(tmp_path / "graphs")
    pad = r3.schrijf_html_3d(concepten, "fiets", bestandsnaam="../../uitbraak", map_pad=map_pad)
    assert os.path.dirname(os.path.abspath(pad)) == os.path.abspath(map_pad)
    assert os.path.isfile(pad) and not os.path.exists(pad + ".tmp")


def test_standaard_bestandsnaam(concepten, tmp_path):
    pad = r3.schrijf_html_3d(concepten, "fiets", map_pad=str(tmp_path))
    assert os.path.basename(pad) == "fiets_3d.html"


def test_volledige_graaf_ontdubbelt(concepten):
    alles = gd.volledige_graaf(concepten)
    paren = [(e["van"], e["type"], e["naar"]) for e in alles["edges"]]
    assert ("wiel", "part_of", "fiets") in paren and len(paren) == len(set(paren)) == 3


def test_bekende_types_hebben_kleur_en_naam(concepten):
    data = _data(r3.render_html_3d(concepten, "fiets"))
    for t in ("is_a", "part_of", "causes", "related_to", "synonym", "antonym", "property_of", "used_for", "None"):
        assert t in data["kleuren"] and t in data["labels"]
    assert data["invers"]["is_a"] == "hiervan zijn soorten"


# ---------- v2: overzicht, groepen, hubs ----------

def test_overzicht_start_met_alle_woorden_met_relaties(concepten):
    data = _data(r3.render_html_3d(concepten, None))
    assert data["centrum"] is None
    assert set(data["start"]) == {"fiets", "voertuig", "wiel", "weg"}


def test_data_heeft_groepen_hubs_en_kleur_per_node(concepten):
    data = _data(r3.render_html_3d(concepten, None))
    assert {"groepen", "hubs"} <= set(data)
    assert all("c" in n for n in data["nodes"])
    assert data["hubs"][0] == "fiets" or data["hubs"][0] == "voertuig"


def test_overzicht_bestandsnaam(concepten, tmp_path):
    pad = r3.schrijf_html_3d(concepten, None, map_pad=str(tmp_path))
    assert os.path.basename(pad) == "alles_3d.html"


# ---------- v2.1: vertakking per betekenis ----------

@pytest.fixture
def vertakt():
    c = {
        "trap": {"senses": [
            {"sense_id": "trap#1", "definition": "pedaal", "status": "confirmed",
             "relations": [{"type": "part_of", "target": "fiets", "status": "confirmed", "source": "u", "confidence": 1}]},
            {"sense_id": "trap#2", "definition": "treden", "status": "confirmed",
             "relations": [{"type": "part_of", "target": "huis", "status": "confirmed", "source": "u", "confidence": 1}]},
        ]},
        "fiets": {"senses": [_sense("fiets", "voertuig")]},
        "huis": {"senses": [_sense("huis", "gebouw")]},
    }
    return c


def test_overzicht_heeft_takken_met_stam_en_groep(vertakt):
    data = _data(r3.render_html_3d(vertakt, None))
    nodes = {n["id"]: n for n in data["nodes"]}
    assert nodes["trap#1"]["stam"] == "trap" and nodes["trap#1"]["betekenis"] == "1"
    assert nodes["trap#1"]["c"] == nodes["trap"]["c"]
    assert {"trap#1", "trap#2"} <= set(data["start"])


def test_takken_zijn_geen_hubs(vertakt):
    assert not any("#" in h for h in _data(r3.render_html_3d(vertakt, None))["hubs"])


def test_centrum_start_bevat_takken_van_woorden_in_beeld(vertakt):
    data = _data(r3.render_html_3d(vertakt, "fiets"))
    assert "trap#1" in data["start"] and "trap#2" in data["start"]


def test_pagina_met_pad_blijft_op_woordniveau(vertakt):
    stappen = gd.vind_pad(vertakt, "fiets", "trap")
    data = _data(r3.render_html_3d(vertakt, "fiets", pad=stappen, per_betekenis=False))
    assert not any("stam" in n for n in data["nodes"])


def test_betekenis_heeft_naam_en_kleur(vertakt):
    data = _data(r3.render_html_3d(vertakt, None))
    assert data["labels"]["betekenis"] and data["kleuren"]["betekenis"] and data["invers"]["betekenis"]