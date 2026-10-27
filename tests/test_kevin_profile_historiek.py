# tests/test_kevin_profile_historiek.py
"""
Tests voor de bi-temporele geschiedenis in kevin_profile.py (v3,
27 oktober 2026).

Isolatie: KevinProfile heeft geen pad-parameter en leest al in
__init__(). Daarom wordt get_project_root (zoals geimporteerd in
kevin_profile.py) VOOR het aanmaken omgeleid naar tmp_path -- de
echte data/kevin_profile.json wordt nooit aangeraakt.
"""

import json

import pytest

from modules.preferences import kevin_profile as kp


class DummyEventBus:
    def __init__(self):
        self.events = []

    def publish(self, naam, data=None):
        self.events.append((naam, data))


@pytest.fixture
def bus():
    return DummyEventBus()


@pytest.fixture
def maak_profiel(tmp_path, monkeypatch, bus):
    """
    Fabriek: maakt een KevinProfile in tmp_path. Optioneel eerst een
    bestaand databestand neerzetten (voor migratie-tests).
    """
    monkeypatch.setattr(kp, "get_project_root", lambda _f: tmp_path)

    def _maak(bestaande_inhoud=None):
        if bestaande_inhoud is not None:
            data_map = tmp_path / "data"
            data_map.mkdir(parents=True, exist_ok=True)
            (data_map / "kevin_profile.json").write_text(
                json.dumps(bestaande_inhoud), encoding="utf-8"
            )
        return kp.KevinProfile(bus)

    return _maak


@pytest.fixture
def profiel(maak_profiel):
    return maak_profiel()


def zet_datum(profiel, datum):
    profiel._vandaag = lambda: datum


class TestNieuweVoorkeur:
    def test_nieuw_woord_krijgt_valid_from_vandaag(self, profiel):
        zet_datum(profiel, "2026-01-10")
        profiel.add_preference("thee", "positief", "expliciet")
        blok = profiel.data["voorkeuren"]["thee"]["expliciet"]
        assert blok["valid_from"] == "2026-01-10"
        assert "valid_until" not in blok

    def test_herhaling_zelfde_sentiment_behoudt_valid_from(self, profiel):
        zet_datum(profiel, "2026-01-10")
        profiel.add_preference("thee", "positief", "expliciet")
        zet_datum(profiel, "2026-03-01")
        profiel.add_preference("thee", "positief", "expliciet")
        blok = profiel.data["voorkeuren"]["thee"]["expliciet"]
        assert blok["valid_from"] == "2026-01-10"
        assert blok["aantal_keer_genoemd"] == 2
        assert profiel.data["historiek"] == {}


class TestSentimentVeranderen:
    def test_verandering_sluit_oud_blok_af(self, profiel):
        zet_datum(profiel, "2026-01-10")
        profiel.add_preference("thee", "positief", "expliciet")
        zet_datum(profiel, "2026-07-01")
        profiel.add_preference("thee", "negatief", "expliciet")

        oud = profiel.data["historiek"]["thee"][0]
        assert oud["sentiment"] == "positief"
        assert oud["valid_from"] == "2026-01-10"
        assert oud["valid_until"] == "2026-07-01"
        assert oud["bron"] == "expliciet"

        nieuw = profiel.data["afkeuren"]["thee"]["expliciet"]
        assert nieuw["sentiment"] == "negatief"
        assert nieuw["valid_from"] == "2026-07-01"
        assert nieuw["aantal_keer_genoemd"] == 1
        assert "thee" not in profiel.data["voorkeuren"]

    def test_event_meldt_verandering(self, profiel, bus):
        zet_datum(profiel, "2026-01-10")
        profiel.add_preference("thee", "positief", "expliciet")
        profiel.add_preference("thee", "negatief", "expliciet")
        laatste = [d for n, d in bus.events if n == "preference_learned"][-1]
        assert laatste["sentiment_veranderd"] is True

    def test_conflict_tussen_bronnen_is_geen_verandering(self, profiel):
        profiel.add_preference("kou", "positief", "expliciet")
        profiel.add_preference("kou", "negatief", "automatisch")
        assert profiel.data["historiek"] == {}


class TestBeeindigen:
    def test_beeindig_haalt_woord_uit_actuele_lijsten(self, profiel):
        zet_datum(profiel, "2026-01-10")
        profiel.add_preference("thee", "positief", "expliciet")
        zet_datum(profiel, "2026-07-01")
        assert profiel.beeindig_preference("thee") is True

        assert profiel.get_preference("thee") is None
        assert "thee" not in profiel.data["voorkeuren"]
        assert profiel.data["historiek"]["thee"][0]["valid_until"] == "2026-07-01"

    def test_beeindig_stuurt_event(self, profiel, bus):
        profiel.add_preference("thee", "positief", "expliciet")
        profiel.beeindig_preference("thee")
        namen = [n for n, _ in bus.events]
        assert "preference_ended" in namen

    def test_beeindig_onbekend_woord_geeft_false(self, profiel):
        assert profiel.beeindig_preference("bestaatniet") is False

    def test_beeindigd_woord_zit_niet_meer_in_get_by_sentiment(self, profiel):
        # Kernrisico van dit hele ontwerp: een beeindigde voorkeur
        # mag nooit meer als actueel gezien worden.
        profiel.add_preference("thee", "positief", "expliciet")
        profiel.add_preference("schaken", "positief", "expliciet")
        profiel.beeindig_preference("thee")
        assert profiel.get_by_sentiment("positief") == ["schaken"]

    def test_beeindigd_woord_kan_terugkomen_met_behoud_historiek(self, profiel):
        zet_datum(profiel, "2026-01-10")
        profiel.add_preference("thee", "positief", "expliciet")
        zet_datum(profiel, "2026-07-01")
        profiel.beeindig_preference("thee")
        zet_datum(profiel, "2026-10-01")
        profiel.add_preference("thee", "positief", "expliciet")

        verloop = profiel.get_historiek("thee")
        assert len(verloop) == 2
        assert verloop[0]["valid_until"] == "2026-07-01"
        assert verloop[1]["valid_from"] == "2026-10-01"
        assert verloop[1]["valid_until"] is None


class TestDefinitiefWissen:
    def test_remove_preference_wist_ook_historiek(self, profiel):
        profiel.add_preference("thee", "positief", "expliciet")
        profiel.add_preference("thee", "negatief", "expliciet")
        assert "thee" in profiel.data["historiek"]
        assert profiel.remove_preference("thee") is True
        assert "thee" not in profiel.data["historiek"]

    def test_wis_definitief_op_beeindigd_woord(self, profiel):
        profiel.add_preference("thee", "positief", "expliciet")
        profiel.beeindig_preference("thee")
        assert profiel.wis_definitief("thee") is True
        assert profiel.get_historiek("thee") == []

    def test_wis_definitief_onbekend_woord(self, profiel):
        assert profiel.wis_definitief("bestaatniet") is False


class TestVeranderingenVoorLayer7:
    def test_venster_wordt_gerespecteerd(self, profiel):
        zet_datum(profiel, "2026-01-10")
        profiel.add_preference("thee", "positief", "expliciet")
        zet_datum(profiel, "2026-07-01")
        profiel.beeindig_preference("thee")
        zet_datum(profiel, "2026-10-27")

        assert profiel.get_veranderingen(30) == []
        recent = profiel.get_veranderingen(200)
        assert len(recent) == 1
        assert recent[0]["woord"] == "thee"
        assert recent[0]["beeindigd"] is True
        assert recent[0]["huidig_sentiment"] is None
        assert recent[0]["oud_sentiment"] == "positief"

    def test_verandering_zonder_beeindigen_toont_huidig_sentiment(self, profiel):
        zet_datum(profiel, "2026-01-10")
        profiel.add_preference("thee", "positief", "expliciet")
        zet_datum(profiel, "2026-10-20")
        profiel.add_preference("thee", "negatief", "expliciet")
        zet_datum(profiel, "2026-10-27")

        res = profiel.get_veranderingen(30)
        assert len(res) == 1
        assert res[0]["beeindigd"] is False
        assert res[0]["huidig_sentiment"] == "negatief"
        assert res[0]["oud_sentiment"] == "positief"


class TestMigratie:
    def test_v2_bestand_krijgt_valid_from_none(self, maak_profiel):
        profiel = maak_profiel({
            "voorkeuren": {
                "koffie": {
                    "expliciet": {
                        "sentiment": "positief",
                        "datum": "2026-07-26",
                        "aantal_keer_genoemd": 2,
                    }
                }
            },
            "afkeuren": {},
            "sense_voorkeuren": {"python": "python#1"},
        })
        blok = profiel.data["voorkeuren"]["koffie"]["expliciet"]
        assert blok["valid_from"] is None
        assert profiel.data["historiek"] == {}
        # Bestaand gedrag blijft werken
        assert profiel.get_preference("koffie")["sentiment"] == "positief"
        assert profiel.get_sense_voorkeur("python") == "python#1"

    def test_v1_bestand_wordt_ook_volledig_gemigreerd(self, maak_profiel):
        profiel = maak_profiel({
            "voorkeuren": {
                "schaken": {"sentiment": "positief", "bron": "expliciet",
                            "datum": "2026-07-25", "aantal_keer_genoemd": 1}
            },
            "afkeuren": {},
        })
        blok = profiel.data["voorkeuren"]["schaken"]["expliciet"]
        assert blok["sentiment"] == "positief"
        assert blok["valid_from"] is None

    def test_verandering_na_migratie_bewaart_onbekend_begin(self, maak_profiel):
        profiel = maak_profiel({
            "voorkeuren": {
                "koffie": {
                    "expliciet": {
                        "sentiment": "positief",
                        "datum": "2026-07-26",
                        "aantal_keer_genoemd": 2,
                    }
                }
            },
            "afkeuren": {},
            "sense_voorkeuren": {},
        })
        zet_datum(profiel, "2026-10-27")
        profiel.add_preference("koffie", "negatief", "expliciet")
        oud = profiel.data["historiek"]["koffie"][0]
        assert oud["valid_from"] is None
        assert oud["valid_until"] == "2026-10-27"

    def test_corrupt_bestand_geeft_volledige_lege_structuur(self, tmp_path, monkeypatch, bus):
        monkeypatch.setattr(kp, "get_project_root", lambda _f: tmp_path)
        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "kevin_profile.json").write_text("{kapot", encoding="utf-8")
        profiel = kp.KevinProfile(bus)
        assert profiel.data["historiek"] == {}
        assert profiel.data["sense_voorkeuren"] == {}


class TestPersistentie:
    def test_historiek_overleeft_herladen(self, tmp_path, maak_profiel, bus):
        profiel = maak_profiel()
        zet_datum(profiel, "2026-01-10")
        profiel.add_preference("thee", "positief", "expliciet")
        zet_datum(profiel, "2026-07-01")
        profiel.beeindig_preference("thee")

        nieuw = kp.KevinProfile(bus)
        assert nieuw.get_historiek("thee")[0]["valid_until"] == "2026-07-01"