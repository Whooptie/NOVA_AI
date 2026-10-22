"""Tests voor modules/knowledge/graph_render.py (Semantic Fase 13.2). Schrijft alleen in tmp_path."""

import os

import pytest

pytest.importorskip("pyvis")

from modules.knowledge import graph_data as gd
from modules.knowledge import graph_render as gr


def _sense(woord, definitie="een ding", relaties=None):
    return {"sense_id": f"{woord}#1", "definition": definitie, "status": "confirmed",
            "relations": relaties or []}


def _rel(type_, target, status="confirmed"):
    return {"type": type_, "target": target, "status": status, "source": "user", "confidence": 1.0}


@pytest.fixture
def concepten():
    return {
        "fiets": {"senses": [_sense("fiets", "een voertuig", [_rel("is_a", "voertuig"), _rel("has_part", "wiel", "unverified")])]},
        "wiel": {"senses": [_sense("wiel", "rond", [_rel("part_of", "fiets")])]},
        "voertuig": {"senses": [_sense("voertuig", "om mee te rijden", [])]},
    }


def test_html_bevat_woorden_en_is_offline(concepten):
    html = gr.render_html(gd.bouw_graaf(concepten, "fiets"))
    assert "fiets" in html and "voertuig" in html
    assert "cdnjs.cloudflare.com" not in html and "unpkg.com" not in html
    assert "cdn.jsdelivr.net" not in html                                   # alles zit er zelf in


def test_gevaarlijke_tekst_komt_niet_in_de_pagina(concepten):
    concepten["fiets"]["senses"][0]["definition"] = '</script><script>alert("x")</script>'
    html = gr.render_html(gd.bouw_graaf(concepten, "fiets"))
    assert 'alert("x")' not in html and "</script><script>alert" not in html


def test_gevaarlijke_woordnaam(concepten):
    concepten["<b>hack</b>"] = {"senses": [_sense("x", "d", [_rel("related_to", "fiets")])]}
    html = gr.render_html(gd.bouw_graaf(concepten, "fiets", diepte=2))
    assert "<b>hack</b>" not in html


def test_lege_graaf_geeft_fout(concepten):
    with pytest.raises(ValueError):
        gr.render_html(gd.bouw_graaf(concepten, "bestaatniet"))


def test_pad_wordt_rood(concepten):
    graaf = gd.bouw_graaf(concepten, "fiets")
    pad = gd.vind_pad(concepten, "wiel", "voertuig")
    assert gr.KLEUR_PAD in gr.render_html(graaf, pad=pad)
    assert gr.KLEUR_PAD not in gr.render_html(graaf)


def test_titel_en_afkapmelding(concepten):
    graaf = gd.bouw_graaf(concepten, "fiets", max_nodes=2)
    html = gr.render_html(graaf, titel="Mijn graaf")
    assert "Mijn graaf" in html and "afgekapt" in html


@pytest.mark.parametrize("invoer,verwacht", [
    ("Mijn Fiets!!", "mijn_fiets.html"),
    ("../../etc/passwd", "passwd.html"),
    ("graaf.html", "graaf.html"),
    ("", "graaf.html"),
    ("C:\\windows\\x.exe", "c_windows_x_exe.html"),
])
def test_bestandsnaam_wordt_gezuiverd(invoer, verwacht):
    assert gr.veilige_bestandsnaam(invoer) == verwacht


def test_schrijf_html_maakt_map_en_bestand(concepten, tmp_path):
    map_pad = str(tmp_path / "graphs")
    pad = gr.schrijf_html(gd.bouw_graaf(concepten, "fiets"), "fiets", map_pad=map_pad)
    assert os.path.dirname(pad) == map_pad and os.path.isfile(pad)
    assert not os.path.exists(pad + ".tmp")
    with open(pad, encoding="utf-8") as f:
        assert "fiets" in f.read()


def test_schrijf_html_blijft_in_de_map(concepten, tmp_path):
    map_pad = str(tmp_path / "graphs")
    pad = gr.schrijf_html(gd.bouw_graaf(concepten, "fiets"), "../../uitbraak", map_pad=map_pad)
    assert os.path.dirname(os.path.abspath(pad)) == os.path.abspath(map_pad)