# tests/test_zelftest.py
"""
Tests voor modules/diagnose/zelftest.py (13 november 2026).

Er wordt in deze tests NIETS echt gestart: pytest, pyflakes en radon worden vervangen
door een nep-runner met vaste uitvoer. Alle bestanden staan in tmp_path, dus Kevin's
echte data/ blijft onaangeraakt.
"""
import json
import os
import pkgutil
import sqlite3
import threading
from datetime import datetime, time as dagtijd
from types import SimpleNamespace

import pytest

import modules
from modules.diagnose import zelftest as z


# ----------------------------------------------------------------------------
# Hulpmiddelen
# ----------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _geen_zelftest_instellingen_uit_de_omgeving(monkeypatch):
    """Op de echte server staan ZELFTEST_* misschien in de omgeving (via .env); deze tests mogen daar niet van afhangen."""
    for naam in list(os.environ):
        if naam.startswith("ZELFTEST_"):
            monkeypatch.delenv(naam, raising=False)


class NepBus:
    def __init__(self):
        self.subs = {}
        self.out = []

    def subscribe(self, event, handler):
        self.subs.setdefault(event, []).append(handler)

    def publish(self, event, data=None):
        self.out.append((event, data))
        for h in self.subs.get(event, []):
            h(data, event)

    def berichten(self, event):
        return [d for e, d in self.out if e == event]


PYTEST_OK = "...\n4563 passed, 2 skipped, 8656 warnings in 19.00s\nMemory: netjes afgesloten.\nMemory: netjes afgesloten.\n"
PYTEST_FOUT = (
    "FAILED tests/test_a.py::test_een - assert 1 == 2\n"
    "FAILED tests/test_a.py::test_twee\n"
    "ERROR tests/test_b.py\n"
    "1 failed, 4296 passed, 2 skipped, 8656 warnings, 1 error in 14.21s\n"
)
PYFLAKES_OK = "core/memory.py:5:1: 'os' imported but unused\nmodules/x.py:3:9: f-string is missing placeholders\n"
RADON_OK = json.dumps({
    "core/a.py": [
        {"type": "function", "rank": "A", "complexity": 2, "name": "klein", "lineno": 1},
        {"type": "method", "rank": "F", "complexity": 50, "name": "groot", "classname": "Router", "lineno": 5},
        {"type": "class", "rank": "A", "complexity": 40, "name": "Router", "methods": []},
        {"type": "function", "rank": "D", "complexity": 22, "name": "middel", "lineno": 90},
    ],
    "core/kapot.py": {"error": "invalid syntax"},
})


def maak_project(tmp_path):
    root = tmp_path / "project"
    for sub in ("core", "modules", "tests", "data", "logs"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    (root / "main.py").write_text("print('hoi')\n", encoding="utf-8")
    (root / "data" / "gegevens.json").write_text('{"a": 1}', encoding="utf-8")
    return root


class NepRunner:
    """Geeft per programma vaste uitvoer terug en onthoudt wat er gestart werd."""

    def __init__(self, pytest_uit=PYTEST_OK, pytest_rc=0, pyflakes_uit=PYFLAKES_OK, pyflakes_rc=1,
                 radon_uit=RADON_OK, te_laat=False):
        self.aanroepen = []
        self.pytest_uit, self.pytest_rc = pytest_uit, pytest_rc
        self.pyflakes_uit, self.pyflakes_rc = pyflakes_uit, pyflakes_rc
        self.radon_uit = radon_uit
        self.te_laat = te_laat

    def __call__(self, cmd, cwd, timeout, env=None, samenvoegen=True):
        self.aanroepen.append({"cmd": cmd, "cwd": cwd, "timeout": timeout, "env": env})
        if "pyflakes" in cmd:
            return self.pyflakes_rc, self.pyflakes_uit, False
        if "radon" in cmd:
            return 0, self.radon_uit, False
        if "pytest" in cmd:
            return self.pytest_rc, self.pytest_uit, self.te_laat
        return 127, "onbekend", False

    def soorten(self):
        uit = []
        for a in self.aanroepen:
            for naam in ("pyflakes", "radon", "pytest"):
                if naam in a["cmd"]:
                    uit.append(naam)
        return uit


def maak_zelftest(tmp_path, runner=None, **extra):
    root = maak_project(tmp_path)
    bus = NepBus()
    kopie_map = tmp_path / "kopie_tmp"

    def kopieer(project_root):
        kopie_map.mkdir(exist_ok=True)
        return kopie_map, kopie_map

    opties = dict(
        project_root=root,
        historie_pad=tmp_path / "historie.json",
        logbestand=tmp_path / "geen_log.log",
        runner=runner or NepRunner(),
        kopieer=kopieer,
        tool_beschikbaar=lambda naam: True,
        opstart=False, nacht=None, achtergrond=False,
        drukaf=lambda *a, **k: None,
    )
    opties.update(extra)
    return z.Zelftest(bus, **opties), bus, opties["runner"]


# ----------------------------------------------------------------------------
# Kleine hulpfuncties
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("tekst,verwacht", [
    ("03:30", dagtijd(3, 30)), ("3", dagtijd(3, 0)), ("23:59", dagtijd(23, 59)),
    ("uit", None), ("", None), ("nee", None), ("25:00", None), ("12:99", None), ("rommel", None), (None, None),
])
def test_parse_tijd(tekst, verwacht):
    assert z.parse_tijd(tekst) == verwacht


def test_veilige_omgeving_haalt_sleutels_weg_en_zet_de_guard():
    omgeving = {"PATH": "/usr/bin", "NTFY_TOPIC": "geheim", "OPENWEATHER_API_KEY": "x",
                "NOVA_CLIENT_TOKEN": "y", "HOME": "/root"}
    schoon = z.veilige_omgeving(omgeving)
    assert schoon["PATH"] == "/usr/bin" and schoon["HOME"] == "/root"
    assert "NTFY_TOPIC" not in schoon and "OPENWEATHER_API_KEY" not in schoon and "NOVA_CLIENT_TOKEN" not in schoon
    assert schoon[z.ENV_GUARD] == "pytest"
    assert "NTFY_TOPIC" in omgeving            # het origineel blijft ongemoeid


def test_standaard_runner_geeft_code_127_bij_onbestaand_programma(tmp_path):
    rc, uit, te_laat = z.standaard_runner(["dit_programma_bestaat_niet_zelftest"], tmp_path, 5)
    assert rc == 127 and te_laat is False


def test_standaard_runner_leest_uitvoer_en_code(tmp_path):
    import sys
    rc, uit, te_laat = z.standaard_runner([sys.executable, "-c", "print('hallo')"], tmp_path, 30)
    assert rc == 0 and "hallo" in uit and te_laat is False


def test_standaard_runner_knipt_grote_uitvoer_niet_af(tmp_path):
    """Regressie: radon geeft ~0,6 MB JSON; een te kleine grens maakte die ongeldig."""
    import sys
    rc, uit, te_laat = z.standaard_runner(
        [sys.executable, "-c", "print('x' * 900_000)"], tmp_path, 30)
    assert rc == 0 and len(uit.strip()) == 900_000


def test_standaard_runner_stopt_bij_tijdslimiet(tmp_path):
    import sys
    rc, uit, te_laat = z.standaard_runner([sys.executable, "-c", "import time; time.sleep(30)"], tmp_path, 1)
    assert te_laat is True


# ----------------------------------------------------------------------------
# Uitvoer ontleden
# ----------------------------------------------------------------------------

def test_parse_pytest_alles_geslaagd_ook_als_de_samenvatting_niet_onderaan_staat():
    res = z.parse_pytest(PYTEST_OK, 0)
    assert res["gelukt"] is True
    assert (res["geslaagd"], res["gefaald"], res["fouten"], res["overgeslagen"]) == (4563, 0, 0, 2)
    assert res["duur"] == 19.0 and res["reden"] is None


def test_parse_pytest_met_mislukte_tests():
    res = z.parse_pytest(PYTEST_FOUT, 1)
    assert res["gelukt"] is False and res["reden"] is None
    assert (res["geslaagd"], res["gefaald"], res["fouten"]) == (4296, 1, 1)
    assert res["mislukt"] == ["tests/test_a.py::test_een", "tests/test_a.py::test_twee", "tests/test_b.py"]


def test_parse_pytest_tijdslimiet_geen_samenvatting_en_geen_tests():
    assert "tijdslimiet" in z.parse_pytest("", -1, te_laat=True)["reden"]
    assert "samenvatting" in z.parse_pytest("rommel", 1)["reden"]
    assert "geen enkele test" in z.parse_pytest("no tests ran in 0.01s", 5)["reden"]
    assert "niet gestart" in z.parse_pytest("", 127)["reden"]


def test_parse_pyflakes_splitst_opruimwerk_en_echte_fouten():
    uit = (PYFLAKES_OK +
           "tests/test_k.py:368:55: undefined name 'pytest'\n"
           "core/x.py:12:1: 'from y import *' used; unable to detect undefined names\n")
    res = z.parse_pyflakes(uit, 1)
    assert res["meldingen"] == 4
    assert res["ernstig_aantal"] == 1
    assert res["ernstig"] == ["tests/test_k.py:368: undefined name 'pytest'"]


def test_parse_pyflakes_syntaxfout_telt_een_keer_ondanks_de_extra_regels():
    uit = "/p/syn.py:1:7: invalid syntax\ndef f(:\n      ^\n"
    res = z.parse_pyflakes(uit, 1)
    assert res["meldingen"] == 1 and res["ernstig_aantal"] == 1


def test_parse_pyflakes_schoon_en_fouten_van_het_programma_zelf():
    assert z.parse_pyflakes("", 0)["meldingen"] == 0
    assert z.parse_pyflakes("", 2)["gelukt"] is False
    assert z.parse_pyflakes("", 127)["gelukt"] is False
    assert z.parse_pyflakes("", -1, te_laat=True)["gelukt"] is False


def test_parse_radon_telt_enkel_functies_en_methodes():
    res = z.parse_radon(RADON_OK, 0)
    assert res["gelukt"] is True
    assert res["functies"] == 3                       # de klasse telt niet mee
    assert res["gemiddelde"] == round((2 + 50 + 22) / 3, 1)
    assert res["zwaar"] == 2                          # rang F en D
    assert res["zwaarste"][0] == {"score": 50, "bestand": "core/a.py", "naam": "Router.groot"}
    assert res["onleesbaar"] == ["core/kapot.py"]


def test_parse_radon_rommel():
    assert z.parse_radon("geen json", 0)["gelukt"] is False
    assert z.parse_radon("[1, 2]", 0)["gelukt"] is False
    assert z.parse_radon("", 127)["gelukt"] is False
    assert z.parse_radon("{}", 0)["gelukt"] is True


# ----------------------------------------------------------------------------
# Data en foutenlog
# ----------------------------------------------------------------------------

def test_check_data_goede_en_kapotte_json(tmp_path):
    root = maak_project(tmp_path)
    (root / "data" / "stuk.json").write_text("{ dit is geen json", encoding="utf-8")
    res = z.check_data(root)
    assert res["json_gecontroleerd"] == 1
    assert len(res["json_stuk"]) == 1 and res["json_stuk"][0].startswith("stuk.json")
    assert res["db"] == "niet aanwezig"


def test_check_data_databank_ok_en_stuk(tmp_path):
    root = maak_project(tmp_path)
    db = root / "data" / "interactions.db"
    con = sqlite3.connect(db)
    con.execute("create table t (x)")
    con.execute("insert into t values (1)")
    con.commit()
    con.close()
    assert z.check_data(root)["db"] == "ok"

    db.write_bytes(b"dit is zeker geen sqlite-bestand" * 200)
    assert z.check_data(root)["db"].startswith("stuk")


def test_check_data_wijzigt_de_databank_niet(tmp_path):
    root = maak_project(tmp_path)
    db = root / "data" / "interactions.db"
    con = sqlite3.connect(db)
    con.execute("create table t (x)")
    con.commit()
    con.close()
    voor = db.read_bytes()
    z.check_data(root)
    assert db.read_bytes() == voor


def test_check_log_telt_alleen_de_laatste_24_uur(tmp_path):
    log = tmp_path / "handler_fouten.log"
    log.write_text(
        "[2026-11-10 10:00:00] event='oud' handler=Oud.handler\nTraceback (most recent call last):\nValueError: oud\n\n"
        "[2026-11-13 09:00:00] event='nieuw' handler=Klas.methode.<locals>.functie\nTraceback (most recent call last):\nKeyError: 'x'\n\n",
        encoding="utf-8")
    res = z.check_log(log, datetime(2026, 11, 13, 12, 0, 0))
    assert res["gelukt"] and res["laatste_24u"] == 1
    assert "Klas.methode.functie" in res["laatste"] and "KeyError" in res["laatste"]


def test_check_log_zonder_bestand_is_nul(tmp_path):
    res = z.check_log(tmp_path / "bestaat_niet.log", datetime(2026, 11, 13, 12, 0, 0))
    assert res["gelukt"] and res["laatste_24u"] == 0 and res["laatste"] is None


# ----------------------------------------------------------------------------
# Tijdelijke testkopie
# ----------------------------------------------------------------------------

def test_testkopie_neemt_code_mee_maar_geen_echte_data_of_geheimen(tmp_path):
    root = maak_project(tmp_path)
    (root / "core" / "x.py").write_text("x = 1\n", encoding="utf-8")
    (root / ".env").write_text("NTFY_TOPIC=geheim\n", encoding="utf-8")
    (root / "logs" / "handler_fouten.log").write_text("oud\n", encoding="utf-8")
    (root / "data" / "interactions.db").write_bytes(b"db")
    (root / "data" / "interactions.db-wal").write_bytes(b"wal")
    (root / "data" / "interactions.jsonl").write_text("{}\n", encoding="utf-8")
    (root / "data" / "interactions_2026-11-01_1.jsonl").write_text("{}\n", encoding="utf-8")
    (root / "data" / "backups").mkdir()
    (root / "data" / "backups" / "oud.db").write_bytes(b"x")
    (root / "data" / "models").mkdir()
    (root / "core" / "__pycache__").mkdir()
    (root / "engines").mkdir()
    (root / "engines" / "stockfish").write_text("binary", encoding="utf-8")

    tijdelijk, kopie = z.maak_testkopie(root, basismap=tmp_path)
    try:
        assert (kopie / "core" / "x.py").read_text(encoding="utf-8") == "x = 1\n"
        assert (kopie / "data" / "gegevens.json").exists()
        assert (kopie / "main.py").exists()
        for weg in (".env", "logs", "data/interactions.db", "data/interactions.db-wal",
                    "data/interactions.jsonl", "data/interactions_2026-11-01_1.jsonl",
                    "data/backups", "data/models", "core/__pycache__"):
            assert not (kopie / weg).exists(), weg
        engines = kopie / "engines"
        assert not engines.exists() or engines.is_symlink()      # gekoppeld, nooit gekopieerd (Windows: soms geen symlink)
        if engines.is_symlink():
            assert (engines / "stockfish").exists()
    finally:
        z.ruim_op(tijdelijk)
    assert not tijdelijk.exists()
    assert (root / "data" / "interactions.db").read_bytes() == b"db"      # origineel ongemoeid
    assert (root / ".env").exists()


def test_ruim_op_faalt_stil():
    z.ruim_op(None)
    z.ruim_op("/bestaat/zeker/niet/zelftest")


# ----------------------------------------------------------------------------
# Beoordelen en rapporteren
# ----------------------------------------------------------------------------

def basisresultaat(**wijzig):
    res = {
        "modus": "volledig", "duur": 20.0, "tijd": "2026-11-13T21:00:00",
        "pytest": z.parse_pytest(PYTEST_OK, 0),
        "pyflakes": z.parse_pyflakes(PYFLAKES_OK, 1),
        "radon": z.parse_radon(RADON_OK, 0),
        "data": {"json_gecontroleerd": 3, "json_stuk": [], "db": "ok"},
        "log": {"gelukt": True, "laatste_24u": 0, "laatste": None, "reden": None},
    }
    res.update(wijzig)
    return res


def test_beoordeel_alles_in_orde():
    b = z.beoordeel(basisresultaat())
    assert b["status"] == "ok" and b["punten"] == []


def test_beoordeel_gefaalde_tests_is_fout():
    b = z.beoordeel(basisresultaat(pytest=z.parse_pytest(PYTEST_FOUT, 1)))
    assert b["status"] == "fout"
    assert "1 test gefaald" in b["punten"][0] and "1 fout bij het laden" in b["punten"][0]


def test_beoordeel_echte_pyflakes_fout_kapotte_json_en_kapotte_db_zijn_fout():
    pf = z.parse_pyflakes("a.py:1:1: undefined name 'x'\n", 1)
    assert z.beoordeel(basisresultaat(pyflakes=pf))["status"] == "fout"
    da = {"json_gecontroleerd": 3, "json_stuk": ["x.json (ValueError)"], "db": "ok"}
    assert z.beoordeel(basisresultaat(data=da))["status"] == "fout"
    da = {"json_gecontroleerd": 3, "json_stuk": [], "db": "stuk: malformed"}
    assert z.beoordeel(basisresultaat(data=da))["status"] == "fout"


def test_beoordeel_database_die_bezet_is_geeft_geen_fout():
    da = {"json_gecontroleerd": 3, "json_stuk": [], "db": "niet gecontroleerd (database is locked)"}
    assert z.beoordeel(basisresultaat(data=da))["status"] == "ok"


def test_beoordeel_nieuwe_fouten_in_het_log_en_meer_meldingen_zijn_let_op():
    lg = {"gelukt": True, "laatste_24u": 2, "laatste": "X: boem", "reden": None}
    assert z.beoordeel(basisresultaat(log=lg))["status"] == "let_op"
    vorig = basisresultaat()
    nu = basisresultaat(pyflakes=z.parse_pyflakes(PYFLAKES_OK + "a.py:1:1: 'x' imported but unused\n", 1))
    b = z.beoordeel(nu, vorig)
    assert b["status"] == "let_op"
    assert any("pyflakes-melding" in p for p in b["punten"])
    assert "pyflakes-meldingen 2 → 3" in b["vergelijking"]


def test_beoordeel_minder_geslaagde_tests_zonder_falen_is_let_op():
    vorig = basisresultaat()
    nu = basisresultaat(pytest=z.parse_pytest("4000 passed in 5.00s\n", 0))
    b = z.beoordeel(nu, vorig)
    assert b["status"] == "let_op"
    assert any("563 tests minder" in p for p in b["punten"])


def test_beoordeel_meer_zware_functies_is_let_op_en_minder_is_alleen_vergelijking():
    vorig = basisresultaat()
    meer = basisresultaat(radon=dict(vorig["radon"], zwaar=vorig["radon"]["zwaar"] + 1))
    assert z.beoordeel(meer, vorig)["status"] == "let_op"
    minder = basisresultaat(radon=dict(vorig["radon"], zwaar=vorig["radon"]["zwaar"] - 1))
    b = z.beoordeel(minder, vorig)
    assert b["status"] == "ok" and b["vergelijking"]


def test_beoordeel_ontbrekende_tools_zijn_let_op():
    res = basisresultaat(pyflakes={"beschikbaar": False, "gelukt": False, "reden": "niet geïnstalleerd"},
                         radon={"beschikbaar": False, "gelukt": False, "reden": "niet geïnstalleerd"})
    b = z.beoordeel(res)
    assert b["status"] == "let_op"
    assert any("pyflakes is niet geïnstalleerd" in p for p in b["punten"])


def test_rapport_bevat_alle_onderdelen():
    res = basisresultaat()
    res.update(z.beoordeel(res))
    tekst = z.maak_rapport(res)
    assert "alles in orde" in tekst
    assert "4563 geslaagd, 0 gefaald" in tekst and "2 overgeslagen" in tekst
    assert "2 meldingen, 0 echte fouten" in tekst
    assert "3 functies, gemiddelde" in tekst and "Router.groot (50)" in tekst
    assert "3 JSON-bestanden gecontroleerd" in tekst and "databank: ok" in tekst
    assert "geen fouten in de laatste 24 uur" in tekst


def test_rapport_bij_fouten_toont_namen_en_waarschuwing():
    res = basisresultaat(pytest=z.parse_pytest(PYTEST_FOUT, 1))
    res.update(z.beoordeel(res))
    tekst = z.maak_rapport(res)
    assert "er is iets mis" in tekst
    assert "tests/test_a.py::test_een" in tekst
    assert tekst.count("Let op:") == 1


def test_meldingtekst_is_kort_en_noemt_het_commando():
    res = basisresultaat(pytest=z.parse_pytest(PYTEST_FOUT, 1))
    res.update(z.beoordeel(res))
    tekst = z.maak_meldingtekst(res)
    assert tekst.startswith("Zelftest (volledig):") and "zelftest status" in tekst
    assert len(tekst) < 300


# ----------------------------------------------------------------------------
# De module zelf
# ----------------------------------------------------------------------------

def test_volledige_zelftest_draait_alle_stappen_en_bewaart_de_historie(tmp_path):
    zt, bus, runner = maak_zelftest(tmp_path)
    res = zt.voer_uit("volledig")
    assert res["status"] == "ok"
    assert sorted(runner.soorten()) == ["pyflakes", "pytest", "radon"]
    assert res["pytest"]["geslaagd"] == 4563
    assert res["data"]["json_gecontroleerd"] == 1
    opgeslagen = json.loads((tmp_path / "historie.json").read_text(encoding="utf-8"))
    assert len(opgeslagen["runs"]) == 1 and opgeslagen["runs"][0]["status"] == "ok"
    assert not (tmp_path / "historie.json.tmp").exists()


def test_snelle_zelftest_slaat_pytest_en_radon_over(tmp_path):
    zt, bus, runner = maak_zelftest(tmp_path)
    res = zt.voer_uit("snel")
    assert runner.soorten() == ["pyflakes"]
    assert "pytest" not in res and "radon" not in res


def test_onbekende_modus_wordt_volledig(tmp_path):
    zt, bus, runner = maak_zelftest(tmp_path)
    assert zt.voer_uit("raar")["modus"] == "volledig"


def test_pytest_krijgt_de_kopie_een_schone_omgeving_en_een_tijdslimiet(tmp_path, monkeypatch):
    monkeypatch.setenv("NTFY_TOPIC", "geheim")
    monkeypatch.setenv("OPENWEATHER_API_KEY", "sleutel")
    zt, bus, runner = maak_zelftest(tmp_path, pytest_timeout=123)
    zt.voer_uit("volledig")
    aanroep = [a for a in runner.aanroepen if "pytest" in a["cmd"]][0]
    assert aanroep["cwd"] == tmp_path / "kopie_tmp"
    assert aanroep["timeout"] == 123
    assert aanroep["env"][z.ENV_GUARD] == "pytest"
    assert "NTFY_TOPIC" not in aanroep["env"] and "OPENWEATHER_API_KEY" not in aanroep["env"]
    assert "--continue-on-collection-errors" in aanroep["cmd"]


def test_de_tijdelijke_kopie_wordt_altijd_gewist_ook_bij_een_crash(tmp_path):
    gewist = []

    def kopieer(root):
        map_ = tmp_path / "kopie_tmp"
        map_.mkdir()
        return map_, map_

    def crashende_runner(*a, **k):
        if "pytest" in a[0]:
            raise RuntimeError("boem")
        return NepRunner()(*a, **k)

    zt, bus, _ = maak_zelftest(tmp_path, runner=crashende_runner, kopieer=kopieer)
    import modules.diagnose.zelftest as zmod
    originele = zmod.ruim_op
    zmod.ruim_op = lambda pad: (gewist.append(pad), originele(pad))
    try:
        res = zt.voer_uit("volledig")
    finally:
        zmod.ruim_op = originele
    assert "kon pytest niet voorbereiden" in res["pytest"]["reden"]
    assert res["status"] == "fout"
    assert gewist == [tmp_path / "kopie_tmp"]
    assert not (tmp_path / "kopie_tmp").exists()


def test_een_crashende_stap_houdt_de_rest_niet_tegen(tmp_path):
    def runner(cmd, cwd, timeout, env=None, samenvoegen=True):
        if "pyflakes" in cmd:
            raise ValueError("pyflakes crashte")
        return NepRunner()(cmd, cwd, timeout, env, samenvoegen)

    zt, bus, _ = maak_zelftest(tmp_path, runner=runner)
    res = zt.voer_uit("volledig")
    assert res["pyflakes"]["gelukt"] is False and "crashte" in res["pyflakes"]["reden"]
    assert res["pytest"]["gelukt"] is True and res["radon"]["gelukt"] is True


def test_tijdslimiet_van_pytest_is_een_fout(tmp_path):
    zt, bus, _ = maak_zelftest(tmp_path, runner=NepRunner(pytest_uit="", pytest_rc=-1, te_laat=True))
    res = zt.voer_uit("volledig")
    assert res["status"] == "fout" and "tijdslimiet" in res["pytest"]["reden"]


def test_ontbrekende_tools_geven_let_op_en_geen_crash(tmp_path):
    zt, bus, runner = maak_zelftest(tmp_path, tool_beschikbaar=lambda naam: naam == "pytest")
    res = zt.voer_uit("volledig")
    assert res["pyflakes"]["beschikbaar"] is False and res["radon"]["beschikbaar"] is False
    assert res["status"] == "let_op"
    assert runner.soorten() == ["pytest"]
    assert "niet geïnstalleerd" in zt.rapport(res)


def test_zonder_pytest_of_tests_map_geen_crash(tmp_path):
    zt, bus, runner = maak_zelftest(tmp_path, tool_beschikbaar=lambda naam: naam != "pytest")
    assert "niet geïnstalleerd" in zt.voer_uit("volledig")["pytest"]["reden"]
    zt2, bus2, runner2 = maak_zelftest(tmp_path / "twee")
    (zt2.root / "tests").rmdir()
    assert "geen tests-map" in zt2.voer_uit("volledig")["pytest"]["reden"]


def test_tweede_run_vergelijkt_met_de_eerste(tmp_path):
    zt, bus, runner = maak_zelftest(tmp_path)
    eerste = zt.voer_uit("volledig")
    assert eerste["vorige_tijd"] is None
    runner.pytest_uit = "4600 passed in 20.00s\n"
    tweede = zt.voer_uit("volledig")
    assert "geslaagde tests 4563 → 4600" in tweede["vergelijking"]
    assert tweede["vorige_tijd"] == eerste["tijd"]
    assert "Sinds de vorige keer" in zt.rapport(tweede)


def test_vergelijking_gebeurt_per_soort_run(tmp_path):
    zt, bus, runner = maak_zelftest(tmp_path)
    zt.voer_uit("volledig")
    snel = zt.voer_uit("snel")
    assert snel["vorige_tijd"] is None                  # er was nog geen snelle run


def test_er_loopt_nooit_twee_zelftests_tegelijk(tmp_path):
    zt, bus, runner = maak_zelftest(tmp_path)
    assert zt._bezig.acquire(blocking=False)
    try:
        assert zt.voer_uit("volledig") is None
        meldingen = []
        assert zt.start_op_commando("volledig", meldingen.append) is False
        assert "al een zelftest" in meldingen[0]
    finally:
        zt._bezig.release()


def test_historie_wordt_beperkt_en_herlaadt(tmp_path):
    zt, bus, runner = maak_zelftest(tmp_path)
    for _ in range(z.HISTORIE_MAX + 5):
        zt.voer_uit("snel")
    assert len(zt._historie["runs"]) == z.HISTORIE_MAX
    opnieuw, _, _ = maak_zelftest(tmp_path)
    assert len(opnieuw._historie["runs"]) == z.HISTORIE_MAX


def test_kapotte_historie_geeft_een_lege_start(tmp_path):
    (tmp_path / "historie.json").write_text("{ kapot", encoding="utf-8")
    zt, bus, runner = maak_zelftest(tmp_path)
    assert zt._historie["runs"] == []
    assert zt.voer_uit("snel")["status"] in ("ok", "let_op")


def test_status_tekst_zonder_en_met_runs(tmp_path):
    zt, bus, runner = maak_zelftest(tmp_path)
    assert "nog niet getest" in zt.status_tekst()
    zt.voer_uit("volledig")
    zt.voer_uit("snel")
    tekst = zt.status_tekst()
    assert "Laatste uitslagen" in tekst and "volledig ok" in tekst and "snel ok" in tekst


def test_start_op_commando_draait_in_een_thread_en_meldt_klaar(tmp_path):
    zt, bus, runner = maak_zelftest(tmp_path)
    berichten, klaar = [], threading.Event()

    def uitvoer(tekst):
        berichten.append(tekst)
        if tekst.startswith("Zelftest"):
            klaar.set()

    assert zt.start_op_commando("snel", uitvoer) is True
    assert klaar.wait(10)
    assert berichten[0].startswith("Ik test mezelf (snel)")
    assert "klaar" in berichten[1]


# ----------------------------------------------------------------------------
# Automatisch: opstart en nacht
# ----------------------------------------------------------------------------

def test_fout_bij_automatische_run_gaat_naar_de_gsm_via_layer4_response(tmp_path):
    zt, bus, runner = maak_zelftest(tmp_path, runner=NepRunner(pytest_uit=PYTEST_FOUT, pytest_rc=1))
    res = zt._run_automatisch("volledig", "nacht")
    assert res["status"] == "fout"
    berichten = bus.berichten("layer4_response")
    assert len(berichten) == 1 and berichten[0]["text"].startswith("Zelftest (volledig):")


def test_alles_ok_bij_automatische_run_blijft_in_de_console(tmp_path):
    uitvoer = []
    zt, bus, runner = maak_zelftest(tmp_path, drukaf=uitvoer.append)
    res = zt._run_automatisch("snel", "opstart")
    assert res["status"] == "ok"
    assert bus.berichten("layer4_response") == []
    assert any("opstart" in r and "status ok" in r for r in uitvoer)


def test_let_op_bij_automatische_run_stuurt_geen_gsm_melding(tmp_path):
    zt, bus, runner = maak_zelftest(tmp_path, tool_beschikbaar=lambda naam: False)
    res = zt._run_automatisch("snel", "opstart")
    assert res["status"] == "let_op"
    assert bus.berichten("layer4_response") == []


def make_klok(start):
    stand = {"t": start.timestamp()}
    return stand, (lambda: stand["t"])


def test_nachtrun_wacht_tot_het_tijd_is_en_draait_een_keer_per_dag(tmp_path):
    stand, klok = make_klok(datetime(2026, 11, 14, 2, 0))
    zt, bus, runner = maak_zelftest(tmp_path, nacht=dagtijd(3, 30), klok=klok)

    assert zt.controleer_nacht(datetime(2026, 11, 14, 2, 0)) is None          # nog te vroeg
    stand["t"] = datetime(2026, 11, 14, 3, 40).timestamp()
    eerste = zt.controleer_nacht(datetime(2026, 11, 14, 3, 40))
    assert eerste is not None and eerste["bron"] == "nacht" and eerste["modus"] == "volledig"
    assert zt.controleer_nacht(datetime(2026, 11, 14, 4, 0)) is None          # vandaag al gedaan
    assert zt._historie["laatste_nacht_datum"] == "2026-11-14"

    stand["t"] = datetime(2026, 11, 15, 3, 31).timestamp()
    assert zt.controleer_nacht(datetime(2026, 11, 15, 3, 31)) is not None     # volgende dag opnieuw


def test_nachtrun_wacht_als_kevin_net_nog_een_bericht_stuurde(tmp_path):
    stand, klok = make_klok(datetime(2026, 11, 14, 3, 40))
    zt, bus, runner = maak_zelftest(tmp_path, nacht=dagtijd(3, 30), klok=klok)
    bus.publish("raw_user_message", {"text": "hallo"})                         # net een bericht
    assert zt.controleer_nacht(datetime(2026, 11, 14, 3, 40)) is None
    stand["t"] += z.RUSTIG_NA_SECONDEN + 1
    assert zt.controleer_nacht(datetime(2026, 11, 14, 3, 51)) is not None


def test_nachtrun_start_niet_opnieuw_na_een_herstart_dezelfde_dag(tmp_path):
    stand, klok = make_klok(datetime(2026, 11, 14, 3, 40))
    zt, bus, runner = maak_zelftest(tmp_path, nacht=dagtijd(3, 30), klok=klok)
    assert zt.controleer_nacht(datetime(2026, 11, 14, 3, 40)) is not None
    herstart, bus2, runner2 = maak_zelftest(tmp_path, nacht=dagtijd(3, 30), klok=klok)
    assert herstart.controleer_nacht(datetime(2026, 11, 14, 3, 45)) is None


def test_nachtrun_staat_standaard_uit(tmp_path, monkeypatch):
    monkeypatch.delenv("ZELFTEST_NACHT", raising=False)
    zt, bus, runner = maak_zelftest(tmp_path, nacht=None)
    zt._nacht = z.Zelftest._lees_nacht(None)
    assert zt._nacht is None
    assert zt.controleer_nacht(datetime(2026, 11, 14, 3, 40)) is None


def test_instellingen_uit_de_omgeving(monkeypatch):
    monkeypatch.setenv("ZELFTEST_NACHT", "04:15")
    monkeypatch.setenv("ZELFTEST_OPSTART", "uit")
    monkeypatch.setenv("ZELFTEST_OPSTART_VERTRAGING", "99999")
    monkeypatch.setenv("ZELFTEST_PYTEST_TIMEOUT", "rommel")
    assert z.Zelftest._lees_nacht(None) == dagtijd(4, 15)
    assert z.Zelftest._lees_opstart(None) is False
    assert z.Zelftest._lees_getal(None, "ZELFTEST_OPSTART_VERTRAGING", 180, 0, 3600) == 3600
    assert z.Zelftest._lees_getal(None, "ZELFTEST_PYTEST_TIMEOUT", 600, 30, 7200) == 600


def test_instellingen_worden_uit_env_gelezen_buiten_pytest(tmp_path, monkeypatch):
    """module_loader laadt deze module voor ntfy; .env moet dus door de module zelf gelezen worden."""
    root = maak_project(tmp_path)
    (root / ".env").write_text("ZELFTEST_NACHT=05:15\nZELFTEST_OPSTART=uit\n", encoding="utf-8")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("ZELFTEST_NACHT", raising=False)
    monkeypatch.delenv("ZELFTEST_OPSTART", raising=False)
    try:
        zt = z.Zelftest(NepBus(), project_root=root, historie_pad=tmp_path / "h.json",
                        achtergrond=False, drukaf=lambda *a, **k: None)
        assert zt._nacht == dagtijd(5, 15)
        assert zt._opstart_aan is False
    finally:
        os.environ.pop("ZELFTEST_NACHT", None)
        os.environ.pop("ZELFTEST_OPSTART", None)


def test_env_wordt_niet_gelezen_tijdens_pytest(tmp_path, monkeypatch):
    # Op de echte server kan ZELFTEST_NACHT al in de omgeving staan (via .env of
    # de container). Deze test gaat over "wordt .env gelezen", dus begin schoon.
    monkeypatch.delenv("ZELFTEST_NACHT", raising=False)
    root = maak_project(tmp_path)
    (root / ".env").write_text("ZELFTEST_NACHT=05:15\n", encoding="utf-8")
    assert "ZELFTEST_NACHT" not in os.environ
    zt = z.Zelftest(NepBus(), project_root=root, historie_pad=tmp_path / "h.json",
                    achtergrond=False, drukaf=lambda *a, **k: None)
    assert zt._nacht is None and "ZELFTEST_NACHT" not in os.environ


def test_er_start_geen_thread_onder_pytest_of_met_de_guard(tmp_path, monkeypatch):
    zt, bus, runner = maak_zelftest(tmp_path, opstart=True, nacht=dagtijd(3, 0), achtergrond=None)
    assert zt._thread is None                       # PYTEST_CURRENT_TEST staat tijdens deze test
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv(z.ENV_GUARD, "pytest")
    zt2, bus2, runner2 = maak_zelftest(tmp_path / "b", opstart=True, nacht=dagtijd(3, 0), achtergrond=None)
    assert zt2._thread is None


def test_achtergrondthread_start_en_stopt_netjes(tmp_path):
    zt, bus, runner = maak_zelftest(tmp_path, opstart=True, opstart_vertraging=0, achtergrond=True)
    assert zt._thread is not None
    zt.shutdown()
    zt._thread.join(timeout=10)
    assert not zt._thread.is_alive()


# ----------------------------------------------------------------------------
# Aansluiting op Nova: auto-discovery en het debug-commando
# ----------------------------------------------------------------------------

def test_module_loader_vindt_de_module_automatisch():
    namen = [naam for _, naam, _ in pkgutil.walk_packages(modules.__path__, prefix="modules.")]
    assert "modules.diagnose.zelftest" in namen
    assert len("modules.diagnose.zelftest".split(".")) == 3          # zoals module_loader.py het eist
    assert hasattr(z, "init_module")


def test_init_module_geeft_een_instantie_en_meldt_dat_hij_geladen_is(monkeypatch, tmp_path):
    monkeypatch.setenv("ZELFTEST_OPSTART", "uit")
    bus = NepBus()
    instance = z.init_module(bus, object())               # module_loader geeft 'sem' mee
    assert isinstance(instance, z.Zelftest)
    assert ("module_loaded", {"name": "zelftest"}) in bus.out
    assert instance._thread is None


def maak_debug(zelftest_module):
    from modules.debug.debug_commands import DebugCommands
    loader = SimpleNamespace(loaded_modules={"zelftest": zelftest_module} if zelftest_module else {})
    return DebugCommands(NepBus(), loader)


class NepZelftest:
    def __init__(self):
        self.gestart = []

    def start_op_commando(self, modus, uitvoer):
        self.gestart.append(modus)
        uitvoer(f"gestart {modus}")

    def status_tekst(self):
        return "STATUSTEKST"


@pytest.mark.parametrize("zin", ["zelftest", "zelftest snel", "zelftest status", "test jezelf",
                                 "Zelftest", "  zelftest  snel "])
def test_debug_herkent_de_zelftest_commandos(zin):
    assert maak_debug(NepZelftest()).is_debug_command(zin) is True


@pytest.mark.parametrize("zin", ["zelftesten", "test", "ik wil mezelf testen", "test jezelf nu"])
def test_debug_herkent_gewone_zinnen_niet(zin):
    assert maak_debug(NepZelftest()).is_debug_command(zin) is False


def test_debug_zelftest_kiest_de_juiste_modus(capsys):
    nep = NepZelftest()
    dbg = maak_debug(nep)
    dbg.handle_debug_command({"text": "zelftest"})
    dbg.handle_debug_command({"text": "zelftest snel"})
    dbg.handle_debug_command({"text": "test jezelf"})
    dbg.handle_debug_command({"text": "zelftest volledig"})
    assert nep.gestart == ["volledig", "snel", "volledig", "volledig"]


def test_debug_zelftest_status_en_onbekend_argument(capsys):
    nep = NepZelftest()
    dbg = maak_debug(nep)
    dbg.handle_debug_command({"text": "zelftest status"})
    assert "STATUSTEKST" in capsys.readouterr().out
    dbg.handle_debug_command({"text": "zelftest raar"})
    assert "Onbekend argument" in capsys.readouterr().out
    assert nep.gestart == []


def test_debug_zelftest_zonder_module_geeft_een_nette_melding(capsys):
    maak_debug(None).handle_debug_command({"text": "zelftest"})
    assert "zelftest-module niet gevonden" in capsys.readouterr().out