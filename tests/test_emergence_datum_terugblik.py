# tests/test_emergence_datum_terugblik.py
#
# Koppeling emergence_engine (Layer 7) <-> datum_terugblik: het terugblik-inzicht
# gaat als 7e insight-type door dezelfde gates (Layer 5, cooldowns, feedback,
# max. 1 per ronde) als de andere inzichten.
# Alles via tmp_path: er wordt niets in de echte data/ geschreven.

import json
import sqlite3
import threading
from datetime import datetime, time, timedelta

import pytest

from modules.experimental import emergence_engine
from modules.knowledge import datum_terugblik as dt

NU = datetime(2026, 11, 1, 14, 0)


class StubBus:
    def __init__(self):
        self.modules = {}
        self.gepubliceerd = []

    def publish(self, naam, data=None):
        self.gepubliceerd.append((naam, data))

    def subscribe(self, *a, **k):
        pass

    def gezegd(self):
        return [d["text"] for n, d in self.gepubliceerd if n == "layer4_response"]


class StubMemory:
    def __init__(self, rijen):
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        for tabel in ("interactions", "interactions_old"):
            self.conn.execute(f"CREATE TABLE {tabel} (timestamp REAL, event_type TEXT, data TEXT)")
        self.lock = threading.Lock()
        for t, tekst in rijen:
            self.conn.execute("INSERT INTO interactions VALUES (?,?,?)",
                              (t, "raw_user_message", json.dumps({"text": tekst})))
        self.conn.commit()

    def _flush_buffer(self):
        pass


class StubContext:
    def __init__(self, mag=True):
        self.mag = mag

    def can_interrupt(self):
        return self.mag


def ts(d, uur=12):
    return datetime.combine(d, time(uur)).timestamp()


def rijen_met_match():
    rijen = [(ts(NU.date() - timedelta(days=i), 9), "koffie drinken") for i in range(40)]
    een_maand = dt.maanden_terug(NU.date(), 1)
    rijen += [
        (ts(een_maand, 10), "mijn fietsband is lek, reparatie nodig"),
        (ts(een_maand - timedelta(days=1), 11), "reparatie fietsband gedaan"),
        (ts(een_maand, 15), "koffie en fietsband"),
        (ts(NU.date() - timedelta(days=1), 10), "fietsband reparatie bestellen"),
        (ts(NU.date(), 10), "reparatie plannen voor de fietsband"),
    ]
    return rijen


@pytest.fixture
def opstelling(tmp_path, monkeypatch):
    monkeypatch.setattr(emergence_engine, "get_project_root", lambda f=None: tmp_path)
    bus = StubBus()
    bus.modules["memory"] = StubMemory(rijen_met_match())
    context = StubContext(True)
    bus.modules["context_manager"] = context
    module = dt.DatumTerugblik(bus, pad=tmp_path / "terugblik.json", modus="aan",
                               klok=lambda: NU, start_thread=False, kies=lambda lst: lst[0])
    engine = emergence_engine.EmergenceEngine(
        bus, layers={"datum_terugblik": module, "context_manager": context})
    bus.modules["emergence_engine"] = engine
    return bus, module, engine, context


class TestAnalyze:
    def test_geeft_insight_met_verwachte_velden(self, opstelling):
        bus, module, engine, _ = opstelling
        i = engine.analyze_datum_terugblik()
        assert i["type"] == "datum_terugblik"
        assert i["confidence"] >= 4.0
        assert set(i["woorden"]) == {"fietsband", "reparatie"}
        assert "Een maand geleden" in i["tekst"]

    def test_zonder_laag_geen_insight(self, opstelling):
        bus, module, engine, _ = opstelling
        engine.layers.pop("datum_terugblik")
        assert engine.analyze_datum_terugblik() is None

    def test_fout_in_laag_wordt_opgevangen(self, opstelling):
        bus, module, engine, _ = opstelling

        class Kapot:
            def vind_insight(self):
                raise RuntimeError("boem")

        engine.layers["datum_terugblik"] = Kapot()
        assert engine.analyze_datum_terugblik() is None

    def test_zit_in_meta_patterns_en_heeft_een_drempel(self, opstelling):
        bus, module, engine, _ = opstelling
        types = [i["type"] for i in engine.analyze_meta_patterns()]
        assert "datum_terugblik" in types
        assert engine._effectieve_drempel("datum_terugblik") == 4.0

    def test_droge_modus_geeft_niets_door(self, opstelling, capsys):
        bus, module, engine, _ = opstelling
        module.modus = "droog"
        assert engine.analyze_datum_terugblik() is None
        assert "zou zeggen" in capsys.readouterr().out


class TestReflect:
    def test_spreekt_een_keer_en_onthoudt_het(self, opstelling):
        bus, module, engine, _ = opstelling
        engine.reflect()
        assert len(bus.gezegd()) == 1
        assert "fietsband" in bus.gezegd()[0]
        assert module.staat["laatst_gemeld_datum"] == "2026-11-01"
        assert "fietsband" in module.staat["gemeld"]
        engine.reflect()  # volgende ronde: niet nog eens
        assert len(bus.gezegd()) == 1

    def test_layer5_nee_dan_stil_en_state_blijft_schoon(self, opstelling):
        bus, module, engine, context = opstelling
        context.mag = False
        engine.reflect()
        assert bus.gezegd() == []
        assert module.staat["laatst_gemeld_datum"] is None
        context.mag = True  # volgende ronde krijgt hetzelfde inzicht een nieuwe kans
        engine.reflect()
        assert len(bus.gezegd()) == 1

    def test_inzicht_wordt_ook_intern_gepubliceerd(self, opstelling):
        bus, module, engine, _ = opstelling
        engine.reflect()
        assert any(n == "emergence:insight" and d["insight_type"] == "datum_terugblik"
                   for n, d in bus.gepubliceerd)

    def test_fout_in_markeer_gemeld_raakt_reflect_niet(self, opstelling):
        bus, module, engine, _ = opstelling

        def kapot(insight):
            raise RuntimeError("boem")

        module.markeer_gemeld = kapot
        engine.reflect()
        assert len(bus.gezegd()) == 1


class TestSpreekwijze:
    def test_gekoppeld_spreekt_de_eigen_thread_niet(self, opstelling):
        bus, module, engine, _ = opstelling
        assert module.via_emergence() is True
        assert module.check_nu() == (False, "loopt via emergence_engine")
        assert bus.gezegd() == []

    def test_forceer_blijft_rechtstreeks_werken(self, opstelling):
        bus, module, engine, _ = opstelling
        assert module.check_nu(forceer=True)[0] is True
        assert len(bus.gezegd()) == 1

    def test_niet_gekoppeld_spreekt_de_module_zelf(self, opstelling):
        bus, module, engine, _ = opstelling
        engine.layers.pop("datum_terugblik")
        assert module.via_emergence() is False
        assert module.check_nu()[0] is True

    def test_status_zegt_hoe_er_gesproken_wordt(self, opstelling):
        bus, module, engine, _ = opstelling
        assert "emergence_engine" in module.status_tekst()
        engine.layers.pop("datum_terugblik")
        assert "eigen thread" in module.status_tekst()


class TestFeedback:
    def test_slechte_feedback_verhoogt_de_drempel(self, opstelling):
        bus, module, engine, _ = opstelling
        for _ in range(6):
            engine.feedback("datum_terugblik", success=False)
        assert engine._effectieve_drempel("datum_terugblik") > 4.0

    def test_goede_feedback_verlaagt_hem(self, opstelling):
        bus, module, engine, _ = opstelling
        for _ in range(6):
            engine.feedback("datum_terugblik", success=True)
        assert engine._effectieve_drempel("datum_terugblik") < 4.0