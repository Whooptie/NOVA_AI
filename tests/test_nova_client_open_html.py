"""Tests voor modules/knowledge/graph_commands.py (Semantic Fase 13.3). Schrijft alleen in tmp_path."""

import os

import pytest

from core.intent_router import IntentRouter
from modules.knowledge import graph_commands as gc
from modules.knowledge import graph_render_3d as r3

pytestmark = pytest.mark.skipif(not os.path.isfile(r3.LIB_PAD), reason="vendor/3d-force-graph.min.js ontbreekt")


class NepBus:
    def __init__(self):
        self.gepubliceerd, self.modules, self.abonnees = [], {}, {}

    def subscribe(self, naam, functie):
        self.abonnees.setdefault(naam, []).append(functie)

    def publish(self, naam, data=None):
        self.gepubliceerd.append((naam, data or {}))
        for f in self.abonnees.get(naam, []):
            f(data or {})

    def antwoorden(self):
        return [d["text"] for n, d in self.gepubliceerd if n == "layer4_response"]


def _sense(woord, definitie, relaties=()):
    return {"sense_id": f"{woord}#1", "definition": definitie, "status": "confirmed",
            "relations": [{"type": t, "target": x, "status": "confirmed", "source": "user", "confidence": 1.0}
                          for t, x in relaties]}


class Store:
    def __init__(self, concepts):
        self.concepts = concepts


class NepSemantic:
    pending_reactivation = None

    def __init__(self, concepts):
        self.store = Store(concepts)

    def get_senses(self, woord):
        return self.store.concepts.get(woord, {}).get("senses", [])

    def _detect_relation(self, text):
        return False


@pytest.fixture
def concepten():
    return {
        "fiets": {"senses": [_sense("fiets", "een voertuig", [("is_a", "voertuig"), ("has_part", "wiel")])]},
        "voertuig": {"senses": [_sense("voertuig", "om mee te rijden")]},
        "auto": {"senses": [_sense("auto", "een voertuig met motor", [("is_a", "voertuig")])]},
        "wiel": {"senses": [_sense("wiel", "rond")]},
        "hond": {"senses": [_sense("hond", "een dier", [("is_a", "dier")])]},
        "dier": {"senses": [_sense("dier", "levend wezen")]},
        "eenzaam": {"senses": [_sense("eenzaam", "alleen")]},
    }


@pytest.fixture
def opstelling(concepten, tmp_path):
    """Echte IntentRouter + echte GraafCommands op 1 nep-bus: test de HELE keten."""
    bus = NepBus()
    sem = NepSemantic(concepten)
    map_pad = str(tmp_path / "graphs")
    commands = gc.GraafCommands(bus, sem, map_pad=map_pad)
    router = IntentRouter(bus, semantic_module=sem)
    return router, bus, map_pad


def _vraag(opstelling, tekst):
    router, bus, _ = opstelling
    bus.gepubliceerd.clear()
    router.route({"text": tekst})
    return bus.antwoorden()


def test_toon_graaf_maakt_bestand_en_antwoordt(opstelling):
    antwoorden = _vraag(opstelling, "toon graaf van fiets")
    _, _, map_pad = opstelling
    assert os.path.isfile(os.path.join(map_pad, "fiets_3d.html"))
    assert len(antwoorden) == 1 and "fiets" in antwoorden[0] and "fiets_3d.html" in antwoorden[0]


def test_diepte_wordt_doorgegeven_en_begrensd(opstelling, concepten):
    _vraag(opstelling, "toon graaf van fiets diepte 9")
    # 9 wordt 3 (MAX_DIEPTE_CHAT); het bestand bestaat gewoon
    assert os.path.isfile(os.path.join(opstelling[2], "fiets_3d.html"))


def test_onbekend_woord(opstelling):
    antwoorden = _vraag(opstelling, "toon graaf van bestaatniet")
    assert "ken" in antwoorden[0] and "nog niet" in antwoorden[0]
    assert not os.path.exists(os.path.join(opstelling[2], "bestaatniet_3d.html"))


def test_woord_zonder_relaties(opstelling):
    antwoorden = _vraag(opstelling, "toon graaf van eenzaam")
    assert "nog geen relaties" in antwoorden[0]


def test_pad_antwoord_in_gewone_zinnen(opstelling):
    antwoorden = _vraag(opstelling, "hoe zijn fiets en auto verbonden")
    tekst = antwoorden[0]
    assert "2 stappen" in tekst
    assert "fiets is een voertuig" in tekst and "auto is een voertuig" in tekst
    assert os.path.isfile(os.path.join(opstelling[2], "pad_fiets_auto.html"))


def test_pad_omgekeerde_relatie_leest_in_opgeslagen_richting(opstelling):
    tekst = _vraag(opstelling, "hoe zijn wiel en fiets verbonden")[0]
    assert "fiets heeft als deel wiel" in tekst          # zo staat het in concepts.json


def test_geen_pad(opstelling):
    tekst = _vraag(opstelling, "hoe zijn fiets en hond verbonden")[0]
    assert "geen verbinding" in tekst


def test_pad_met_onbekend_woord(opstelling):
    tekst = _vraag(opstelling, "hoe zijn fiets en bestaatniet verbonden")[0]
    assert "'bestaatniet'" in tekst and "nog niet" in tekst


def test_statistieken(opstelling):
    tekst = _vraag(opstelling, "graaf statistieken")[0]
    assert "7 concepten" in tekst and "unieke verbindingen" in tekst


def test_zonder_kennis_geen_crash(tmp_path):
    bus = NepBus()
    gc.GraafCommands(bus, None, map_pad=str(tmp_path))
    bus.publish("intent_graph_show", {"word": "fiets", "diepte": 1})
    bus.publish("intent_graph_path", {"word_a": "a", "word_b": "b"})
    bus.publish("intent_graph_stats", {})
    assert len(bus.antwoorden()) == 3 and all("niet geladen" in t for t in bus.antwoorden())


def test_ontbrekende_bibliotheek_geeft_nette_melding(opstelling, monkeypatch, tmp_path):
    monkeypatch.setattr(r3, "LIB_PAD", str(tmp_path / "weg.js"))
    tekst = _vraag(opstelling, "toon graaf van fiets")[0]
    assert "lukte niet" in tekst and "3d-force-graph" in tekst


def test_pad_blijft_een_antwoord_zonder_bibliotheek(opstelling, monkeypatch, tmp_path):
    monkeypatch.setattr(r3, "LIB_PAD", str(tmp_path / "weg.js"))
    tekst = _vraag(opstelling, "hoe zijn fiets en auto verbonden")[0]
    assert "2 stappen" in tekst and "Bestand" not in tekst


def test_init_module_geeft_instantie_terug():
    bus = NepBus()
    assert isinstance(gc.init_module(bus, None), gc.GraafCommands)


# ---------- toon de hele kennisgraaf (overzicht) ----------

@pytest.mark.parametrize("tekst", [
    "toon de hele kennisgraaf", "toon de hele graaf", "laat de volledige graaf zien",
    "toon alles in de graaf", "de hele kennisgraaf",
])
def test_hele_graaf_maakt_overzicht(opstelling, tekst):
    antwoorden = _vraag(opstelling, tekst)
    assert os.path.isfile(os.path.join(opstelling[2], "alles_3d.html"))
    assert len(antwoorden) == 1 and "alles_3d.html" in antwoorden[0]


def test_hele_graaf_zonder_kennis(tmp_path):
    bus = NepBus()
    gc.GraafCommands(bus, None, map_pad=str(tmp_path))
    bus.publish("intent_graph_all", {})
    assert "niet geladen" in bus.antwoorden()[0]


# ---------- naar de laptop sturen (open_html) ----------

class NepBridge:
    def __init__(self, verbonden=True, resultaat=None):
        self.verbonden = verbonden
        self.resultaat = resultaat or {"ok": True}
        self.commandos = []

    def is_laptop_verbonden(self):
        return self.verbonden

    def stuur_commando_naar_laptop(self, soort, payload, timeout_seconden=10):
        self.commandos.append((soort, payload))
        return self.resultaat


def test_pagina_gaat_naar_laptop_en_is_uitpakbaar(opstelling):
    import base64
    import gzip
    router, bus, map_pad = opstelling
    bus.modules["client_bridge"] = NepBridge()
    antwoorden = _vraag(opstelling, "toon graaf van fiets")
    soort, payload = bus.modules["client_bridge"].commandos[0]
    assert soort == "open_html" and payload["bestandsnaam"] == "fiets_3d.html"
    html = gzip.decompress(base64.b64decode(payload["inhoud"]))
    assert html == open(os.path.join(map_pad, "fiets_3d.html"), "rb").read()
    assert html.lstrip().lower().startswith(b"<!doctype html")
    assert "geopend op je laptop" in antwoorden[0] and "fiets_3d.html" in antwoorden[0]


def test_laptop_niet_verbonden_stuurt_niets(opstelling):
    _, bus, map_pad = opstelling
    bus.modules["client_bridge"] = NepBridge(verbonden=False)
    antwoorden = _vraag(opstelling, "toon graaf van fiets")
    assert bus.modules["client_bridge"].commandos == []
    assert "niet verbonden" in antwoorden[0]
    assert os.path.isfile(os.path.join(map_pad, "fiets_3d.html"))


def test_laptop_weigert_wordt_eerlijk_gemeld(opstelling):
    _, bus, _ = opstelling
    bus.modules["client_bridge"] = NepBridge(resultaat={"ok": False, "reden": "Geen antwoord van de laptop binnen de tijd."})
    antwoorden = _vraag(opstelling, "toon de hele kennisgraaf")
    assert "lukte niet" in antwoorden[0] and "Geen antwoord" in antwoorden[0]


def test_pad_en_overzicht_gaan_ook_naar_laptop(opstelling):
    _, bus, _ = opstelling
    bus.modules["client_bridge"] = NepBridge()
    _vraag(opstelling, "hoe zijn fiets en auto verbonden")
    _vraag(opstelling, "toon de hele kennisgraaf")
    namen = [p["bestandsnaam"] for _, p in bus.modules["client_bridge"].commandos]
    assert namen == ["pad_fiets_auto.html", "alles_3d.html"]


def test_bridge_die_crasht_breekt_het_antwoord_niet(opstelling):
    _, bus, _ = opstelling

    class Kapot(NepBridge):
        def stuur_commando_naar_laptop(self, *a, **k):
            raise RuntimeError("boem")
    bus.modules["client_bridge"] = Kapot()
    antwoorden = _vraag(opstelling, "toon graaf van fiets")
    assert "fiets_3d.html" in antwoorden[0] and "boem" in antwoorden[0]