"""Tests voor modules/knowledge/graph_data.py (Semantic Fase 13.1). Pure functies, geen bestanden."""

import pytest

from modules.knowledge import graph_data as g


def _sense(woord, definitie="een ding", relaties=None, status="confirmed", **extra):
    s = {"sense_id": f"{woord}#1", "definition": definitie, "status": status,
         "relations": relaties or []}
    s.update(extra)
    return s


def _rel(type_, target, status="confirmed", source="user"):
    return {"type": type_, "target": target, "status": status, "source": source, "confidence": 1.0}


@pytest.fixture
def concepten():
    return {
        "fiets": {"senses": [_sense("fiets", "een voertuig", [_rel("is_a", "voertuig"), _rel("has_part", "wiel")],
                                    ontstaan=1817)]},
        "wiel": {"senses": [_sense("wiel", "een rond onderdeel", [_rel("part_of", "fiets")])]},
        "voertuig": {"senses": [_sense("voertuig", "iets om mee te rijden", [_rel("related_to", "weg")])]},
        "weg": {"senses": [_sense("weg", "een verharde strook", [])]},
        "hond": {"senses": [_sense("hond", "een dier", [_rel("is_a", "dier")])]},
        "dier": {"senses": [_sense("dier", "een levend wezen", [])]},
        "eenzaam": {"senses": [_sense("eenzaam", "unknown", [])]},
    }


# ---------- bouw_graaf ----------

def test_directe_buren_in_beide_richtingen(concepten):
    r = g.bouw_graaf(concepten, "fiets", diepte=1)
    ids = {n["id"] for n in r["nodes"]}
    # wiel heeft zelf 'part_of fiets' (inkomend), voertuig is uitgaand
    assert ids == {"fiets", "wiel", "voertuig"}
    assert r["fout"] is None


def test_diepte_2_neemt_buren_van_buren_mee(concepten):
    ids = {n["id"] for n in g.bouw_graaf(concepten, "fiets", diepte=2)["nodes"]}
    assert "weg" in ids
    assert "hond" not in ids


def test_afstand_klopt(concepten):
    nodes = {n["id"]: n["afstand"] for n in g.bouw_graaf(concepten, "fiets", diepte=2)["nodes"]}
    assert nodes["fiets"] == 0 and nodes["wiel"] == 1 and nodes["weg"] == 2


def test_has_part_en_part_of_worden_een_verbinding(concepten):
    # fiets has_part wiel en wiel part_of fiets zeggen hetzelfde: 1 pijl, als 'wiel part_of fiets'
    edges = g.bouw_graaf(concepten, "fiets", diepte=1)["edges"]
    paren = [(e["van"], e["type"], e["naar"]) for e in edges]
    assert len(paren) == len(set(paren))
    assert ("wiel", "part_of", "fiets") in paren and ("fiets", "has_part", "wiel") not in paren


def test_symmetrische_relatie_beide_kanten_is_een_lijn(concepten):
    concepten["voertuig"]["senses"][0]["relations"].append(_rel("related_to", "weg"))
    concepten["weg"]["senses"][0]["relations"].append(_rel("related_to", "voertuig"))
    edges = [e for e in g.bouw_graaf(concepten, "weg", diepte=1)["edges"] if e["type"] == "related_to"]
    assert len(edges) == 1 and edges[0]["gericht"] is False


def test_zwakste_status_wint_bij_samenvoegen(concepten):
    concepten["fiets"]["senses"][0]["relations"][1]["status"] = "unverified"   # has_part wiel
    edges = g.bouw_graaf(concepten, "fiets", diepte=1)["edges"]
    wiel = [e for e in edges if e["type"] == "part_of"][0]
    assert wiel["status"] == "unverified"


def test_onbekend_concept(concepten):
    r = g.bouw_graaf(concepten, "xyz")
    assert r["fout"] == "onbekend" and r["nodes"] == []


def test_concept_zonder_relaties(concepten):
    r = g.bouw_graaf(concepten, "eenzaam")
    assert r["fout"] == "geen_relaties" and len(r["nodes"]) == 1


def test_hoofdletters_maken_niet_uit(concepten):
    assert g.bouw_graaf(concepten, "FIETS")["centrum"] == "fiets"


def test_max_nodes_kapt_af(concepten):
    r = g.bouw_graaf(concepten, "fiets", diepte=2, max_nodes=2)
    assert len(r["nodes"]) == 2 and r["afgekapt"] is True


def test_diepte_wordt_begrensd(concepten):
    assert g.bouw_graaf(concepten, "fiets", diepte=99)["diepte"] == g.MAX_DIEPTE_TOEGESTAAN


def test_afgewezen_relatie_wordt_genegeerd(concepten):
    concepten["fiets"]["senses"][0]["relations"][1]["status"] = "rejected"   # has_part wiel
    edges = g.bouw_graaf(concepten, "fiets", diepte=1)["edges"]
    assert ("fiets", "has_part", "wiel") not in [(e["van"], e["type"], e["naar"]) for e in edges]


def test_afgewezen_relatie_kan_getoond_worden(concepten):
    concepten["fiets"]["senses"][0]["relations"][1]["status"] = "rejected"
    edges = g.bouw_graaf(concepten, "fiets", diepte=1, toon_afgewezen=True)["edges"]
    assert any(e["status"] == "rejected" for e in edges)


def test_afgewezen_sense_valt_weg(concepten):
    concepten["hond"]["senses"][0]["status"] = "rejected"
    assert g.bouw_graaf(concepten, "hond")["fout"] == "geen_relaties"


def test_filter_op_relatietype(concepten):
    ids = {n["id"] for n in g.bouw_graaf(concepten, "fiets", diepte=1, relatietypes={"is_a"})["nodes"]}
    assert ids == {"fiets", "voertuig"}


def test_ontbrekend_doel_krijgt_bestaat_false(concepten):
    concepten["weg"]["senses"][0]["relations"].append(_rel("related_to", "asfalt"))
    nodes = {n["id"]: n for n in g.bouw_graaf(concepten, "weg", diepte=1)["nodes"]}
    assert nodes["asfalt"]["bestaat"] is False


def test_node_toont_definitie_en_ontstaansjaar(concepten):
    nodes = {n["id"]: n for n in g.bouw_graaf(concepten, "fiets", diepte=1)["nodes"]}
    assert nodes["fiets"]["definitie"] == "een voertuig" and nodes["fiets"]["ontstaan"] == 1817


def test_unknown_definitie_wordt_leeg(concepten):
    concepten["eenzaam"]["senses"][0]["relations"].append(_rel("related_to", "weg"))
    nodes = {n["id"]: n for n in g.bouw_graaf(concepten, "eenzaam", diepte=1)["nodes"]}
    assert nodes["eenzaam"]["definitie"] == ""


def test_zelfde_vraag_geeft_zelfde_graaf(concepten):
    assert g.bouw_graaf(concepten, "fiets") == g.bouw_graaf(concepten, "fiets")


def test_zelfverwijzing_geeft_geen_lus(concepten):
    concepten["weg"]["senses"][0]["relations"].append(_rel("related_to", "weg"))
    assert all(e["van"] != e["naar"] for e in g.bouw_graaf(concepten, "weg")["edges"])


# ---------- vind_pad ----------

def test_pad_direct(concepten):
    pad = g.vind_pad(concepten, "fiets", "voertuig")
    assert [(s["van"], s["type"], s["naar"]) for s in pad] == [("fiets", "is_a", "voertuig")]
    assert pad[0]["omgekeerd"] is False


def test_pad_over_meerdere_stappen(concepten):
    pad = g.vind_pad(concepten, "wiel", "weg")
    assert [s["naar"] for s in pad] == ["fiets", "voertuig", "weg"]


def test_pad_tegen_de_richting_in_is_omgekeerd(concepten):
    pad = g.vind_pad(concepten, "voertuig", "fiets")
    assert pad[0]["omgekeerd"] is True


def test_geen_pad_tussen_losse_eilanden(concepten):
    assert g.vind_pad(concepten, "fiets", "hond") is None


def test_pad_onbekend_woord(concepten):
    assert g.vind_pad(concepten, "fiets", "xyz") is None


def test_pad_zelfde_woord_is_lege_lijst(concepten):
    assert g.vind_pad(concepten, "fiets", "fiets") == []


def test_pad_respecteert_max_diepte(concepten):
    assert g.vind_pad(concepten, "wiel", "weg", max_diepte=2) is None


def test_pad_kiest_het_kortste(concepten):
    concepten["wiel"]["senses"][0]["relations"].append(_rel("related_to", "weg"))
    assert len(g.vind_pad(concepten, "wiel", "weg")) == 1


def test_pad_negeert_afgewezen_relatie(concepten):
    concepten["fiets"]["senses"][0]["relations"][0]["status"] = "rejected"   # fiets is_a voertuig
    assert g.vind_pad(concepten, "fiets", "weg") is None


# ---------- statistieken ----------

def test_statistieken_tellingen(concepten):
    s = g.statistieken(concepten)
    assert s["concepten"] == 7
    assert s["relaties"] == 5
    assert s["unieke_relaties"] == 4          # fiets has_part wiel == wiel part_of fiets
    assert s["per_type"]["is_a"] == 2
    assert s["gem_relaties_per_concept"] == round(5 / 7, 2)


def test_losse_concepten_en_stukken(concepten):
    s = g.statistieken(concepten)
    assert s["losse_concepten"] == ["eenzaam"]
    assert s["stukken"] == 2                  # fiets-groep (4 woorden) en hond-dier (2)
    assert s["grootste_stuk"] == 4


def test_ontbrekende_doelen(concepten):
    concepten["weg"]["senses"][0]["relations"].append(_rel("related_to", "asfalt"))
    assert g.statistieken(concepten)["ontbrekende_doelen"] == ["asfalt"]


def test_zekerheid_en_afgewezen(concepten):
    concepten["hond"]["senses"][0]["relations"][0]["status"] = "unverified"
    concepten["wiel"]["senses"][0]["relations"][0]["status"] = "rejected"
    s = g.statistieken(concepten)
    assert s["per_status"]["unverified"] == 1
    assert s["afgewezen_relaties"] == 1 and s["relaties"] == 4


def test_zonder_definitie_geteld(concepten):
    assert g.statistieken(concepten)["zonder_definitie"] == 1


def test_lege_graaf():
    s = g.statistieken({})
    assert s["concepten"] == 0 and s["gem_relaties_per_concept"] == 0.0
    assert "leeg" in g.statistieken_tekst(s)


def test_tekst_bevat_kerncijfers(concepten):
    tekst = g.statistieken_tekst(g.statistieken(concepten))
    assert "7 concepten" in tekst and "5 relaties" in tekst and "4 unieke" in tekst and "eenzaam" not in tekst.split("Losse")[0]


def test_relatie_met_type_none_wordt_gemeld(concepten):
    concepten["weg"]["senses"][0]["relations"].append(_rel("None", "fiets"))
    stats = g.statistieken(concepten)
    assert stats["type_ontbreekt"] == 1
    assert "None" in g.statistieken_tekst(stats)


# ---------- gemeenschappen (groepen voor de kleuren) ----------

def _groot(n=12):
    """Twee trossen van n woorden die elk intern sterk verbonden zijn, met 1 brug."""
    c = {}
    for naam in ("a", "b"):
        for i in range(n):
            w = f"{naam}{i}"
            rel = [_rel("related_to", f"{naam}{j}") for j in range(n) if j != i]
            c[w] = {"senses": [_sense(w, "x", rel)]}
    c["a0"]["senses"][0]["relations"].append(_rel("related_to", "b0"))
    return c


def test_gemeenschappen_vindt_twee_groepen():
    pytest.importorskip("networkx")
    v = g.volledige_graaf(_groot())
    toewijzing, groepen = g.gemeenschappen(v["nodes"], v["edges"])
    assert len(groepen) == 2 and {x["grootte"] for x in groepen} == {12}
    assert len({toewijzing[f"a{i}"] for i in range(12)}) == 1
    assert toewijzing["a1"] != toewijzing["b1"]


def test_gemeenschappen_is_deterministisch():
    pytest.importorskip("networkx")
    v = g.volledige_graaf(_groot())
    assert g.gemeenschappen(v["nodes"], v["edges"]) == g.gemeenschappen(v["nodes"], v["edges"])


def test_gemeenschappen_kleine_groepen_krijgen_min_een(concepten):
    pytest.importorskip("networkx")
    v = g.volledige_graaf(concepten)
    toewijzing, groepen = g.gemeenschappen(v["nodes"], v["edges"])
    assert groepen == [] and set(toewijzing.values()) == {-1}


def test_gemeenschappen_naam_is_best_verbonden_woord():
    pytest.importorskip("networkx")
    c = _groot()
    v = g.volledige_graaf(c)
    _, groepen = g.gemeenschappen(v["nodes"], v["edges"])
    assert groepen[0]["naam"] == "a0"          # a0 heeft de extra brug-relatie


def test_gemeenschappen_zonder_networkx(monkeypatch, concepten):
    import builtins
    echt = builtins.__import__

    def nep(naam, *a, **k):
        if naam == "networkx":
            raise ImportError
        return echt(naam, *a, **k)
    monkeypatch.setattr(builtins, "__import__", nep)
    v = g.volledige_graaf(concepten)
    assert g.gemeenschappen(v["nodes"], v["edges"]) == ({}, [])


# ---------- vertakking per betekenis (13.5) ----------

def _tweebetekenissen():
    """trap: pedaal (fiets) en trap in huis; huis noemt de trap ook zelf (zonder te weten welke)."""
    return {
        "trap": {"senses": [
            {"sense_id": "trap#1", "definition": "pedaal", "status": "confirmed",
             "relations": [_rel("part_of", "fiets")]},
            {"sense_id": "trap#2", "definition": "treden", "status": "confirmed",
             "relations": [_rel("part_of", "huis")]},
        ]},
        "fiets": {"senses": [_sense("fiets", "voertuig", [_rel("is_a", "voertuig")])]},
        "huis": {"senses": [_sense("huis", "gebouw", [_rel("has_part", "trap")])]},
        "voertuig": {"senses": [_sense("voertuig", "iets")]},
    }


def test_vertakte_woorden_vindt_enkel_meerdere_betekenissen():
    c = _tweebetekenissen()
    v = g.vertakte_woorden(c)
    assert list(v) == ["trap"] and [t["sense_id"] for t in v["trap"]] == ["trap#1", "trap#2"]
    assert v["trap"][0]["definitie"] == "pedaal" and v["trap"][1]["nr"] == "2"


def test_afgewezen_betekenis_telt_niet_mee():
    c = _tweebetekenissen()
    c["trap"]["senses"][1]["status"] = "rejected"
    assert g.vertakte_woorden(c) == {}


def test_unknown_definitie_wordt_leeg_bij_tak():
    c = _tweebetekenissen()
    c["trap"]["senses"][1]["definition"] = "unknown"
    assert g.vertakte_woorden(c)["trap"][1]["definitie"] == ""


def test_standaard_blijft_een_bolletje_per_woord():
    v = g.volledige_graaf(_tweebetekenissen())
    assert "trap#1" not in {n["id"] for n in v["nodes"]}
    assert not any(e["type"] == "betekenis" for e in v["edges"])


def test_per_betekenis_maakt_takken_en_stam_verbindingen():
    v = g.volledige_graaf(_tweebetekenissen(), per_betekenis=True)
    ids = {n["id"] for n in v["nodes"]}
    assert {"trap", "trap#1", "trap#2"} <= ids
    tak_edges = {(e["van"], e["naar"]) for e in v["edges"] if e["type"] == "betekenis"}
    assert tak_edges == {("trap", "trap#1"), ("trap", "trap#2")}
    assert all(e["gericht"] is False for e in v["edges"] if e["type"] == "betekenis")


def test_relatie_hangt_aan_de_juiste_betekenis():
    edges = {(e["van"], e["type"], e["naar"]) for e in g.volledige_graaf(_tweebetekenissen(), per_betekenis=True)["edges"]}
    assert ("trap#1", "part_of", "fiets") in edges
    assert ("trap#2", "part_of", "huis") in edges
    assert ("trap", "part_of", "fiets") not in edges


def test_relatie_van_de_andere_kant_blijft_aan_de_stam():
    # 'huis has_part trap' is enkel op huis opgeslagen: welke trap bedoeld is, weten we niet
    c = _tweebetekenissen()
    c["trap"]["senses"][1]["relations"] = []                    # trap#2 zegt zelf niets meer
    edges = {(e["van"], e["type"], e["naar"]) for e in g.volledige_graaf(c, per_betekenis=True)["edges"]}
    assert ("trap", "part_of", "huis") in edges


def test_zelfde_relatie_op_twee_betekenissen_geeft_twee_lijnen():
    c = _tweebetekenissen()
    for s in c["trap"]["senses"]:
        s["relations"] = [_rel("related_to", "voertuig")]
    edges = {(e["van"], e["naar"]) for e in g.volledige_graaf(c, per_betekenis=True)["edges"] if e["type"] == "related_to"}
    beide_richtingen = edges | {(b, a) for a, b in edges}
    assert {("trap#1", "voertuig"), ("trap#2", "voertuig")} <= beide_richtingen


def test_stam_houdt_zijn_woordgraad_en_tak_telt_zijn_eigen_lijnen():
    nodes = {n["id"]: n for n in g.volledige_graaf(_tweebetekenissen(), per_betekenis=True)["nodes"]}
    assert nodes["trap"]["aantal_relaties"] == 2          # woordniveau: fiets en huis
    assert nodes["trap#1"]["aantal_relaties"] == 1        # alleen zijn eigen relatie (fiets), de verbinding met de stam telt niet mee
    assert nodes["trap#1"]["stam"] == "trap" and nodes["trap#1"]["label"] == "trap 1"


def test_tak_krijgt_nooit_dezelfde_naam_als_een_woord():
    c = _tweebetekenissen()
    c["trap#1"] = {"senses": [_sense("trap#1", "raar woord")]}
    ids = [n["id"] for n in g.volledige_graaf(c, per_betekenis=True)["nodes"]]
    assert len(ids) == len(set(ids))


def test_statistieken_noemen_woorden_met_meerdere_betekenissen():
    s = g.statistieken(_tweebetekenissen())
    assert s["meerdere_betekenissen"] == {"trap": 2}
    assert "meerdere betekenissen: 1 (trap 2)" in g.statistieken_tekst(s)