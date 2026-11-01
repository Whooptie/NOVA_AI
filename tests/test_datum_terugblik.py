# tests/test_datum_terugblik.py
#
# Tests voor modules/knowledge/datum_terugblik.py.
# Isolatie: alles via tmp_path, een lichte stub-EventBus en een in-memory
# sqlite-database. De echte data/-bestanden worden nooit aangeraakt.

import json
import sqlite3
import threading
from datetime import date, datetime, time, timedelta

import pytest

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

    def antwoorden(self):
        return [d["text"] for n, d in self.gepubliceerd if n == "layer4_response"]


class StubMemory:
    def __init__(self, rijen):
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        for tabel in ("interactions", "interactions_old"):
            self.conn.execute(
                f"CREATE TABLE {tabel} (timestamp REAL, event_type TEXT, data TEXT)")
        self.lock = threading.Lock()
        for ts, tekst in rijen:
            self.conn.execute("INSERT INTO interactions VALUES (?,?,?)",
                              (ts, "raw_user_message", json.dumps({"text": tekst})))
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


def maak_rijen(nu=NU, met_match=True):
    """40 dagen vulling ('koffie drinken' elke dag) + een match 1 maand geleden en nu."""
    rijen = []
    for i in range(40):
        d = nu.date() - timedelta(days=i)
        rijen.append((ts(d, 9), "koffie drinken"))
    een_maand = dt.maanden_terug(nu.date(), 1)
    if met_match:
        rijen += [
            (ts(een_maand, 10), "mijn fietsband is lek, reparatie nodig"),
            (ts(een_maand - timedelta(days=1), 11), "reparatie fietsband gedaan"),
            (ts(een_maand, 15), "koffie en fietsband"),
            (ts(nu.date() - timedelta(days=1), 10), "fietsband reparatie bestellen"),
            (ts(nu.date(), 10), "reparatie plannen voor de fietsband"),
        ]
    return rijen


def maak_module(tmp_path, rijen=None, mag=True, modus="aan"):
    bus = StubBus()
    bus.modules["memory"] = StubMemory(rijen if rijen is not None else maak_rijen())
    if mag is not None:
        bus.modules["context_manager"] = StubContext(mag)
    mod = dt.DatumTerugblik(bus, pad=tmp_path / "state.json", modus=modus,
                            klok=lambda: NU, start_thread=False, kies=lambda lst: lst[0])
    return mod, bus


# ---------------------------------------------------------------
class TestMaandenTerug:
    def test_gewone_maand(self):
        assert dt.maanden_terug(date(2026, 11, 1), 1) == date(2026, 10, 1)

    def test_jaargrens(self):
        assert dt.maanden_terug(date(2026, 2, 10), 3) == date(2025, 11, 10)

    def test_dag_past_niet_in_maand(self):
        assert dt.maanden_terug(date(2026, 3, 31), 1) == date(2026, 2, 28)

    def test_schrikkeljaar(self):
        assert dt.maanden_terug(date(2028, 3, 31), 1) == date(2028, 2, 29)

    def test_een_jaar_en_twee_jaar(self):
        assert dt.maanden_terug(date(2027, 3, 15), 12) == date(2026, 3, 15)
        assert dt.maanden_terug(date(2028, 3, 15), 24) == date(2026, 3, 15)


class TestWoordStammen:
    def test_filtert_stop_korte_en_negatie(self):
        w = dt.woord_stammen("ik heb geen zin om de fietsband te repareren 123")
        tokens = set(w.values())
        assert "fietsband" in tokens
        assert "geen" not in tokens
        assert "123" not in tokens
        assert "zin" not in tokens  # korter dan 4 letters

    def test_negeer_woorden(self):
        assert dt.woord_stammen("nova kevin") == {}


class TestVindTerugblik:
    def test_vindt_match_en_negeert_vast_woord(self):
        a = dt.vind_terugblik(maak_rijen(), NU.date())
        assert a["kandidaten"], a
        k = a["kandidaten"][0]
        assert k["afstand_maanden"] == 1
        assert set(k["woorden"]) == {"fietsband", "reparatie"}
        assert "koffie" not in k["woorden"]  # elke dag gebruikt: niet opvallend

    def test_te_weinig_data(self):
        a = dt.vind_terugblik(maak_rijen()[:5], NU.date())
        assert not a["kandidaten"]
        assert "te weinig dagen" in a["reden"]

    def test_geen_match_zonder_overeenkomst(self):
        a = dt.vind_terugblik(maak_rijen(met_match=False), NU.date())
        assert not a["kandidaten"]

    def test_een_jaar_zonder_data_wordt_afgewezen(self):
        a = dt.vind_terugblik(maak_rijen(), NU.date())
        redenen = dict(a["afgewezen"])
        assert 12 in redenen and "te weinig berichten" in redenen[12]

    def test_een_zwak_woord_is_niet_genoeg(self):
        rijen = maak_rijen(met_match=False)
        een_maand = dt.maanden_terug(NU.date(), 1)
        rijen += [(ts(een_maand, 10), "fietsband"), (ts(een_maand, 11), "iets anders"),
                  (ts(een_maand, 12), "nog iets"),
                  (ts(NU.date(), 10), "fietsband"), (ts(NU.date(), 11), "dingen"),
                  (ts(NU.date(), 12), "zaken")]
        a = dt.vind_terugblik(rijen, NU.date())
        assert not a["kandidaten"]


class TestCodeFilter:
    @pytest.mark.parametrize("tekst", [
        "snelheid_na(0, 9.81, 3)", "bereken 12 * 3", "x = 5", "zie https://nova.be",
        "open main.py", "pad naar data.json",
    ])
    def test_code_wordt_herkend(self, tekst):
        assert dt.lijkt_op_code(tekst)

    @pytest.mark.parametrize("tekst", [
        "mijn fietsband is lek, reparatie nodig", "ik ga koken (lasagne)", "het was 20 graden",
    ])
    def test_gewone_zin_niet(self, tekst):
        assert not dt.lijkt_op_code(tekst)

    def test_testsessie_geeft_geen_treffer(self):
        rijen = maak_rijen(met_match=False)
        een_maand = dt.maanden_terug(NU.date(), 1)
        for dag in (een_maand, NU.date()):
            for i in range(4):
                rijen.append((ts(dag, 10 + i), f"snelheid_na({i}, 9.81, 3) reeks sitting"))
        a = dt.vind_terugblik(rijen, NU.date())
        assert not a["kandidaten"]

    def test_woord_van_een_enkele_dag_telt_niet(self):
        rijen = maak_rijen(met_match=False)
        een_maand = dt.maanden_terug(NU.date(), 1)
        rijen += [(ts(een_maand, 10), "fietsband reparatie"), (ts(een_maand, 11), "fietsband reparatie"),
                  (ts(een_maand, 12), "fietsband reparatie"),
                  (ts(NU.date(), 10), "fietsband reparatie"), (ts(NU.date(), 11), "fietsband"),
                  (ts(NU.date(), 12), "reparatie")]
        assert not dt.vind_terugblik(rijen, NU.date())["kandidaten"]


class TestFormuleer:
    def test_zin_bevat_onderdelen(self):
        a = dt.vind_terugblik(maak_rijen(), NU.date())
        zin = dt.formuleer(a["kandidaten"][0], kies=lambda lst: lst[0])
        assert "Een maand geleden" in zin
        assert "1 oktober" in zin
        assert "'" in zin and "Toen schreef je bijvoorbeeld" in zin

    def test_zonder_voorbeeld(self):
        a = dt.vind_terugblik(maak_rijen(), NU.date())
        zin = dt.formuleer(a["kandidaten"][0], voorbeeld=False, kies=lambda lst: lst[0])
        assert "Toen schreef je" not in zin

    def test_woordenlijst(self):
        assert dt._woordenlijst(["a"]) == "'a'"
        assert dt._woordenlijst(["a", "b"]) == "'a' en 'b'"
        assert dt._woordenlijst(["a", "b", "c"]) == "'a', 'b' en 'c'"


class TestCheckNu:
    def test_spreekt_en_bewaart(self, tmp_path):
        mod, bus = maak_module(tmp_path)
        gesproken, reden = mod.check_nu()
        assert gesproken, reden
        assert len(bus.antwoorden()) == 1
        staat = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
        assert staat["laatst_gemeld_datum"] == "2026-11-01"
        assert "fietsband" in staat["gemeld"]

    def test_hoogstens_een_per_dag(self, tmp_path):
        mod, bus = maak_module(tmp_path)
        assert mod.check_nu()[0]
        gesproken, reden = mod.check_nu()
        assert not gesproken and "al gemeld" in reden
        assert len(bus.antwoorden()) == 1

    def test_layer5_nee_zwijgt(self, tmp_path):
        mod, bus = maak_module(tmp_path, mag=False)
        gesproken, reden = mod.check_nu()
        assert not gesproken and "Layer 5" in reden
        assert bus.antwoorden() == []

    def test_zonder_context_manager_zwijgt(self, tmp_path):
        mod, bus = maak_module(tmp_path, mag=None)
        assert not mod.check_nu()[0]
        assert bus.antwoorden() == []

    def test_buiten_spreekuren(self, tmp_path):
        mod, bus = maak_module(tmp_path)
        mod.klok = lambda: datetime(2026, 11, 1, 23, 0)
        gesproken, reden = mod.check_nu()
        assert not gesproken and "spreekuren" in reden

    def test_droge_modus_zegt_niets(self, tmp_path, capsys):
        mod, bus = maak_module(tmp_path, modus="droog")
        gesproken, reden = mod.check_nu()
        assert not gesproken and reden == "droge run"
        assert bus.antwoorden() == []
        assert "zou zeggen" in capsys.readouterr().out

    def test_modus_uit(self, tmp_path):
        mod, bus = maak_module(tmp_path, modus="uit")
        assert mod.check_nu() == (False, "modus uit")

    def test_woord_cooldown_over_dagen(self, tmp_path):
        mod, bus = maak_module(tmp_path)
        assert mod.check_nu()[0]
        mod.staat["laatst_gemeld_datum"] = "2026-10-31"  # gisteren: dagregel is voorbij
        gesproken, reden = mod.check_nu()
        assert not gesproken and "recent al gemeld" in reden

    def test_cooldown_verloopt(self, tmp_path):
        mod, bus = maak_module(tmp_path)
        assert mod.check_nu()[0]
        mod.staat["laatst_gemeld_datum"] = "2026-09-01"
        mod.staat["gemeld"] = {k: "2026-09-01" for k in mod.staat["gemeld"]}
        assert mod.check_nu()[0]
        assert len(bus.antwoorden()) == 2

    def test_forceer_negeert_spamregels(self, tmp_path):
        mod, bus = maak_module(tmp_path, mag=False)
        assert mod.check_nu(forceer=True)[0]

    def test_geen_data_geen_melding_en_geen_crash(self, tmp_path):
        mod, bus = maak_module(tmp_path, rijen=[])
        gesproken, reden = mod.check_nu()
        assert not gesproken and "te weinig dagen" in reden

    def test_kapotte_state_wordt_genegeerd(self, tmp_path):
        (tmp_path / "state.json").write_text("{kapot", encoding="utf-8")
        mod, bus = maak_module(tmp_path)
        assert mod.check_nu()[0]

    def test_status_tekst(self, tmp_path):
        mod, bus = maak_module(tmp_path)
        tekst = mod.status_tekst()
        assert "Modus: aan" in tekst and "fietsband" in tekst


class TestThreadEnInit:
    def test_shutdown_stopt_thread(self, tmp_path):
        bus = StubBus()
        mod = dt.DatumTerugblik(bus, pad=tmp_path / "s.json", modus="aan", start_thread=True)
        assert mod._thread.is_alive()
        mod.shutdown()
        assert not mod._thread.is_alive()

    def test_modus_uit_start_geen_thread(self, tmp_path):
        mod = dt.DatumTerugblik(StubBus(), pad=tmp_path / "s.json", modus="uit")
        assert mod._thread is None

    def test_ongeldige_modus_wordt_aan(self, tmp_path):
        mod = dt.DatumTerugblik(StubBus(), pad=tmp_path / "s.json", modus="raar", start_thread=False)
        assert mod.modus == "aan"

    def test_init_module_signatuur(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATUM_TERUGBLIK_MODUS", "uit")
        bus = StubBus()
        mod = dt.init_module(bus, None)
        assert ("module_loaded", {"name": "datum_terugblik"}) in bus.gepubliceerd
        mod.shutdown()


class TestNegeerlijstEnDetails:
    def test_aanspreekwoorden_vallen_weg(self):
        assert dt.woord_stammen("weet jij hoe laat het ongeveer is, bereken dit") == {}

    def test_status_toont_details_per_woord(self):
        a = dt.vind_terugblik(maak_rijen(), NU.date())
        tekst = dt.formatteer_status(a, NU.date())
        assert "fietsband:" in tekst and "dag(en) totaal" in tekst