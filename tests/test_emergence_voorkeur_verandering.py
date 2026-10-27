# tests/test_emergence_voorkeur_verandering.py
"""
Tests voor Layer 7's zesde insight-type 'voorkeur_verandering'
(27 oktober 2026).

Isolatie: EmergenceEngine bouwt zijn paden in __init__ via
get_project_root(__file__). Dat wordt VOOR het aanmaken omgeleid naar
tmp_path, zodat data/insight_feedback.json en de cooldown-state van
Kevin nooit aangeraakt worden. kevin_profile wordt vervangen door een
stub: hier wordt enkel Layer 7's gedrag getest, niet het profiel zelf.
"""

import pytest

from modules.experimental import emergence_engine as ee


class DummyEventBus:
    def __init__(self):
        self.events = []
        self.modules = {}

    def subscribe(self, naam, functie):
        pass

    def publish(self, naam, data=None):
        self.events.append((naam, data))

    def gepubliceerd(self, naam):
        return [d for n, d in self.events if n == naam]


class StubProfiel:
    def __init__(self, veranderingen):
        self.veranderingen = veranderingen
        self.dagen_gevraagd = None

    def get_veranderingen(self, dagen=90):
        self.dagen_gevraagd = dagen
        return list(self.veranderingen)


def verandering(woord, oud, huidig, datum, bron="expliciet", beeindigd=False):
    return {
        "woord": woord,
        "bron": bron,
        "oud_sentiment": oud,
        "valid_until": datum,
        "huidig_sentiment": huidig,
        "beeindigd": beeindigd,
    }


@pytest.fixture
def maak_engine(tmp_path, monkeypatch):
    monkeypatch.setattr(ee, "get_project_root", lambda _f: tmp_path)

    def _maak(profiel=None):
        bus = DummyEventBus()
        layers = {}
        if profiel is not None:
            layers["kevin_profile"] = profiel
        return ee.EmergenceEngine(bus, layers=layers), bus

    return _maak


class TestAnalyze:
    def test_geen_profiel_geeft_none(self, maak_engine):
        engine, _ = maak_engine()
        assert engine.analyze_preference_change() is None

    def test_geen_veranderingen_geeft_none(self, maak_engine):
        engine, _ = maak_engine(StubProfiel([]))
        assert engine.analyze_preference_change() is None

    def test_vraagt_het_juiste_venster(self, maak_engine):
        profiel = StubProfiel([])
        engine, _ = maak_engine(profiel)
        engine.analyze_preference_change()
        assert profiel.dagen_gevraagd == engine.VOORKEUR_VERANDERING_VENSTER_DAGEN

    def test_beeindigd_woord(self, maak_engine):
        profiel = StubProfiel([
            verandering("thee", "positief", None, "2026-10-27", beeindigd=True)
        ])
        engine, _ = maak_engine(profiel)
        res = engine.analyze_preference_change()
        assert res["type"] == "voorkeur_verandering"
        assert res["woord"] == "thee"
        assert res["beeindigd"] is True
        assert res["oud_sentiment"] == "positief"
        assert res["confidence"] == 1.0

    def test_expliciete_verandering(self, maak_engine):
        profiel = StubProfiel([
            verandering("koffie", "positief", "negatief", "2026-10-20")
        ])
        engine, _ = maak_engine(profiel)
        res = engine.analyze_preference_change()
        assert res["woord"] == "koffie"
        assert res["beeindigd"] is False
        assert res["huidig_sentiment"] == "negatief"

    def test_automatische_verandering_zonder_beeindigen_telt_niet(self, maak_engine):
        profiel = StubProfiel([
            verandering("koffie", "positief", "neutraal_gemengd", "2026-10-20",
                        bron="automatisch")
        ])
        engine, _ = maak_engine(profiel)
        assert engine.analyze_preference_change() is None

    def test_beeindigd_telt_ook_als_enkel_automatisch(self, maak_engine):
        profiel = StubProfiel([
            verandering("koffie", "positief", None, "2026-10-20",
                        bron="automatisch", beeindigd=True)
        ])
        engine, _ = maak_engine(profiel)
        assert engine.analyze_preference_change()["woord"] == "koffie"

    def test_terugkeer_met_zelfde_sentiment_is_geen_verandering(self, maak_engine):
        profiel = StubProfiel([
            verandering("thee", "positief", "positief", "2026-10-20")
        ])
        engine, _ = maak_engine(profiel)
        assert engine.analyze_preference_change() is None

    def test_kiest_de_nieuwste(self, maak_engine):
        profiel = StubProfiel([
            verandering("thee", "positief", None, "2026-10-01", beeindigd=True),
            verandering("koffie", "positief", "negatief", "2026-10-25"),
            verandering("cola", "positief", None, "2026-10-10", beeindigd=True),
        ])
        engine, _ = maak_engine(profiel)
        assert engine.analyze_preference_change()["woord"] == "koffie"

    def test_bij_gelijke_datum_wint_expliciet(self, maak_engine):
        profiel = StubProfiel([
            verandering("kou", "negatief", None, "2026-10-27",
                        bron="automatisch", beeindigd=True),
            verandering("kou", "positief", None, "2026-10-27",
                        bron="expliciet", beeindigd=True),
        ])
        engine, _ = maak_engine(profiel)
        assert engine.analyze_preference_change()["oud_sentiment"] == "positief"

    def test_kapotte_profiel_laag_crasht_niet(self, maak_engine):
        class Kapot:
            def get_veranderingen(self, dagen=90):
                raise RuntimeError("kapot")

        engine, _ = maak_engine(Kapot())
        assert engine.analyze_preference_change() is None


class TestFormuleer:
    def test_datum_leesbaar(self, maak_engine):
        engine, _ = maak_engine()
        assert engine._datum_leesbaar("2026-10-27") == "27 oktober"
        assert engine._datum_leesbaar("2026-07-01") == "1 juli"
        assert engine._datum_leesbaar("kapot") == "kapot"

    def test_beeindigd_noemt_woord_en_datum_nooit_een_reden(self, maak_engine):
        engine, _ = maak_engine()
        insight = {
            "type": "voorkeur_verandering", "woord": "thee",
            "oud_sentiment": "positief", "huidig_sentiment": None,
            "beeindigd": True, "datum": "2026-10-27", "confidence": 1.0,
        }
        for _ in range(40):
            tekst = engine._formuleer_voorkeur_verandering(insight)
            assert "thee" in tekst
            assert "27 oktober" in tekst
            assert "omdat" not in tekst and "waarom" not in tekst.lower()

    def test_veranderd_noemt_oud_en_nieuw(self, maak_engine):
        engine, _ = maak_engine()
        insight = {
            "type": "voorkeur_verandering", "woord": "koffie",
            "oud_sentiment": "positief", "huidig_sentiment": "negatief",
            "beeindigd": False, "datum": "2026-10-20", "confidence": 1.0,
        }
        for _ in range(40):
            tekst = engine._formuleer_voorkeur_verandering(insight)
            assert "koffie" in tekst
            assert "20 oktober" in tekst
            assert "hield van koffie" in tekst
            assert "niet van koffie" in tekst

    def test_onbekend_sentiment_crasht_niet(self, maak_engine):
        engine, _ = maak_engine()
        insight = {
            "type": "voorkeur_verandering", "woord": "x",
            "oud_sentiment": "raar", "huidig_sentiment": "raar",
            "beeindigd": False, "datum": "2026-10-20", "confidence": 1.0,
        }
        assert "x" in engine._formuleer_voorkeur_verandering(insight)


class TestGates:
    def test_haalt_layer4_drempel(self, maak_engine):
        engine, _ = maak_engine()
        assert engine._haalt_layer4_drempel("voorkeur_verandering", 1.0) is True

    def test_cooldown_sleutel_per_woord(self, maak_engine):
        engine, _ = maak_engine()
        a = {"type": "voorkeur_verandering", "woord": "thee"}
        b = {"type": "voorkeur_verandering", "woord": "koffie"}
        assert engine._cooldown_sleutel(a) != engine._cooldown_sleutel(b)

    def test_nieuwe_verandering_op_zelfde_woord_is_nieuwe_inhoud(self, maak_engine):
        engine, _ = maak_engine()
        eerste = {"type": "voorkeur_verandering", "woord": "thee",
                  "beeindigd": True, "huidig_sentiment": None,
                  "datum": "2026-10-01"}
        tweede = dict(eerste, datum="2026-10-27")
        engine._registreer_periodiek(eerste)
        assert engine._is_nieuwe_inhoud(eerste) is False
        assert engine._is_nieuwe_inhoud(tweede) is True


class TestReflectEndToEnd:
    def test_spreekt_een_keer_en_herhaalt_niet(self, maak_engine):
        profiel = StubProfiel([
            verandering("thee", "positief", None, "2026-10-27", beeindigd=True)
        ])
        engine, bus = maak_engine(profiel)

        resultaten = engine.reflect()
        assert any(r["insight_type"] == "voorkeur_verandering" for r in resultaten)
        gesproken = bus.gepubliceerd("layer4_response")
        assert len(gesproken) == 1
        assert "thee" in gesproken[0]["text"]

        # Tweede ronde: zelfde inhoud + cooldown -> stil
        engine.reflect()
        assert len(bus.gepubliceerd("layer4_response")) == 1

    def test_zonder_veranderingen_blijft_stil(self, maak_engine):
        engine, bus = maak_engine(StubProfiel([]))
        engine.reflect()
        assert bus.gepubliceerd("layer4_response") == []

    def test_zonder_profiel_laag_crasht_reflect_niet(self, maak_engine):
        engine, bus = maak_engine()
        assert engine.reflect() == []