# tests/test_zelftest_robuust.py
"""
Tests voor modules/diagnose/controles_robuust.py (gebruik, terugzettest, meldingen, rommel),
tools/run_rommeltest.py en hun aansluiting op de zelftest (14 november 2026).

Er wordt niets echt gestart: alles staat in tmp_path, de zelftest krijgt een nep-runner.
"""
import json
import os
import sqlite3
from datetime import datetime, timedelta

import pytest

from modules.diagnose import controles_robuust as r
from modules.diagnose import trend
from modules.diagnose import zelftest as z
from tools import run_rommeltest as rr


@pytest.fixture(autouse=True)
def _geen_zelftest_instellingen_uit_de_omgeving(monkeypatch):
    for naam in list(os.environ):
        if naam.startswith(("ZELFTEST_", "NOVA_HARTSLAG", "NOVA_MELDINGSTEST")):
            monkeypatch.delenv(naam, raising=False)


# ----------------------------------------------------------------------------
# Gebruik
# ----------------------------------------------------------------------------

def maak_proc(tmp_path, rss_kb=204800, threads=7, fds=3, start_ticks=5000, boot=1_000_000):
    proc = tmp_path / "proc"
    (proc / "self" / "fd").mkdir(parents=True)
    (proc / "self" / "status").write_text(f"Name:\tnova\nVmRSS:\t  {rss_kb} kB\nThreads:\t{threads}\n", encoding="utf-8")
    velden = ["S"] + ["0"] * 18 + [str(start_ticks)]
    (proc / "self" / "stat").write_text("1234 (nova ai) " + " ".join(velden) + "\n", encoding="utf-8")
    (proc / "stat").write_text(f"cpu  1 2 3\nbtime {boot}\n", encoding="utf-8")
    for i in range(fds):
        (proc / "self" / "fd" / str(i)).write_text("", encoding="utf-8")
    return proc


def test_check_gebruik_leest_geheugen_threads_bestanden_en_uptime(tmp_path):
    proc = maak_proc(tmp_path)
    ticks = os.sysconf("SC_CLK_TCK")
    start = 1_000_000 + 5000 / ticks
    g = r.check_gebruik(nu=start + 7200, opstart_s=12.5, proc_root=str(proc))
    assert g["gelukt"] and g["rss_mb"] == 200.0 and g["threads"] == 7 and g["fds"] == 3
    assert g["uptime_uur"] == 2.0 and g["opstart_s"] == 12.5


def test_check_gebruik_zonder_proc_is_geen_fout(tmp_path):
    g = r.check_gebruik(proc_root=str(tmp_path / "bestaat_niet"))
    assert g["beschikbaar"] is False and g["gelukt"] is False
    assert r.beoordeel_gebruik(g, {}) == ([], [], [])
    assert "niet gemeten" in r.rapport_gebruik(g)[0]


def test_check_gebruik_op_dit_systeem_geeft_echte_getallen():
    g = r.check_gebruik()
    assert g["gelukt"] and g["rss_mb"] > 0 and g["threads"] >= 1


def test_check_gebruik_zonder_starttijd_laat_uptime_leeg(tmp_path):
    proc = maak_proc(tmp_path)
    (proc / "stat").write_text("cpu 1 2 3\n", encoding="utf-8")        # geen btime
    g = r.check_gebruik(nu=2_000_000, proc_root=str(proc))
    assert g["gelukt"] and g["uptime_uur"] is None


def gebruik(rss=300.0, threads=40, fds=60, uptime=5.0, gelukt=True):
    return {"gelukt": gelukt, "rss_mb": rss, "threads": threads, "fds": fds, "uptime_uur": uptime}


def test_gebruik_normaal_is_stil():
    assert r.beoordeel_gebruik(gebruik(), {"gebruik": gebruik(rss=290, uptime=3)}) == ([], [], [])


def test_gebruik_absoluut_te_hoog():
    _, ops, _ = r.beoordeel_gebruik(gebruik(rss=4500, threads=350, fds=900), {})
    assert len(ops) == 3
    assert "4500 MB" in ops[0] and "350 threads" in ops[1] and "900 bestanden" in ops[2]


def test_gebruik_groei_binnen_hetzelfde_proces_geeft_let_op():
    vorig = {"gebruik": gebruik(rss=300, threads=40, fds=60, uptime=2)}
    nieuw = gebruik(rss=900, threads=120, fds=200, uptime=6)
    _, ops, vergelijking = r.beoordeel_gebruik(nieuw, vorig)
    assert any("geheugengebruik groeit snel" in o and "300 → 900" in o for o in ops)
    assert any("aantal threads groeit (40 → 120)" in o for o in ops)
    assert "geheugen 300 → 900 MB" in vergelijking and "open bestanden 60 → 200" in vergelijking


def test_gebruik_na_een_herstart_wordt_niet_vergeleken():
    vorig = {"gebruik": gebruik(rss=3000, uptime=50)}
    assert r.beoordeel_gebruik(gebruik(rss=300, uptime=0.1), vorig) == ([], [], [])
    assert r.beoordeel_gebruik(gebruik(rss=900, uptime=0.1), vorig) == ([], [], [])      # lagere uptime: ander proces


def test_gebruik_kleine_groei_blijft_stil():
    _, ops, vergelijking = r.beoordeel_gebruik(gebruik(rss=340, threads=42), {"gebruik": gebruik(rss=300, uptime=1)})
    assert ops == [] and vergelijking == []


def test_gebruik_rapport():
    tekst = r.rapport_gebruik({"beschikbaar": True, "gelukt": True, "rss_mb": 312.4, "threads": 1, "fds": 58,
                               "uptime_uur": 5.0, "opstart_s": 38.2})[0]
    assert tekst == ("• Gebruik: 312.4 MB geheugen, 1 thread, 58 open bestanden, draait al 5 uur, "
                     "opstarten duurde 38 s.")
    assert "kon niet meten" in r.rapport_gebruik({"gelukt": False, "reden": "x"})[0]


# ----------------------------------------------------------------------------
# Herstel
# ----------------------------------------------------------------------------

def maak_db(pad, rijen=5, extra_tabel=False, extra_kolom=False):
    pad.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(pad))
    kolom = ", notitie TEXT" if extra_kolom else ""
    con.execute(f"CREATE TABLE interactions (id INTEGER PRIMARY KEY, tekst TEXT{kolom})")
    con.executemany("INSERT INTO interactions (tekst) VALUES (?)", [(f"zin {i}",) for i in range(rijen)])
    if extra_tabel:
        con.execute("CREATE TABLE archief (id INTEGER PRIMARY KEY, tekst TEXT)")
    con.commit()
    con.close()


def maak_project(tmp_path, backup=True, **live_opties):
    root = tmp_path / "project"
    maak_db(root / "data" / "interactions.db", **live_opties)
    if backup:
        maak_db(root / "data" / "backups" / "interactions_2026-11-14_100000.db")
    return root


def test_herstel_zet_de_back_up_terug_en_ruimt_op(tmp_path):
    root = maak_project(tmp_path)
    basis = tmp_path / "tijdelijk"
    basis.mkdir()
    h = r.check_herstel(root, tmp_basis=basis)
    assert h["gelukt"] and h["integriteit"] and h["tabellen"] == 1 and h["rijen"] == 5
    assert h["schema_gelijk"] is True and h["verschillen"] == [] and h["nieuwste"].endswith("100000.db")
    assert list(basis.iterdir()) == []                              # tijdelijke map is weg
    assert r.beoordeel_herstel(h, {}) == ([], [], [])
    assert "integriteit ok, 1 tabel, 5 rijen, schema gelijk" in r.rapport_herstel(h)[0]


def test_herstel_laat_de_echte_bestanden_ongemoeid(tmp_path):
    root = maak_project(tmp_path)
    voor = {p: p.read_bytes() for p in (root / "data").rglob("*.db")}
    r.check_herstel(root, tmp_basis=tmp_path)
    assert {p: p.read_bytes() for p in (root / "data").rglob("*.db")} == voor


def test_herstel_ziet_een_schema_dat_afwijkt(tmp_path):
    root = maak_project(tmp_path, extra_tabel=True, extra_kolom=True)
    h = r.check_herstel(root, tmp_basis=tmp_path)
    assert h["gelukt"] and h["schema_gelijk"] is False
    assert any("tabel 'archief' ontbreekt" in v for v in h["verschillen"])
    assert any("kolom notitie ontbreekt" in v for v in h["verschillen"])
    fouten, ops, _ = r.beoordeel_herstel(h, {})
    assert fouten == [] and len(ops) == 2 and "wijkt af van de echte databank" in ops[0]
    assert "WIJKT AF" in r.rapport_herstel(h)[0]


def test_herstel_van_een_kapotte_back_up_is_een_fout(tmp_path):
    root = maak_project(tmp_path)
    kapot = next((root / "data" / "backups").glob("*.db"))
    kapot.write_bytes(b"dit is geen databank" * 100)
    basis = tmp_path / "tijdelijk"
    basis.mkdir()
    h = r.check_herstel(root, tmp_basis=basis)
    assert h["gelukt"] is False and h["integriteit"] is False
    fouten, _, _ = r.beoordeel_herstel(h, {})
    assert len(fouten) == 1 and "laat zich niet terugzetten" in fouten[0]
    assert "MISLUKT" in r.rapport_herstel(h)[0]
    assert list(basis.iterdir()) == []


def test_herstel_zonder_back_up_en_met_te_weinig_ruimte(tmp_path, monkeypatch):
    root = maak_project(tmp_path, backup=False)
    h = r.check_herstel(root, tmp_basis=tmp_path)
    assert h["gevonden"] == 0 and r.beoordeel_herstel(h, {}) == ([], [], [])
    assert "geen back-up" in r.rapport_herstel(h)[0]

    root2 = maak_project(tmp_path / "twee")
    monkeypatch.setattr(r.shutil, "disk_usage", lambda p: type("D", (), {"free": 1000})())
    h2 = r.check_herstel(root2, tmp_basis=tmp_path)
    assert h2["gelukt"] is False and h2["integriteit"] is None and "schijfruimte" in h2["reden"]
    fouten, ops, _ = r.beoordeel_herstel(h2, {})
    assert fouten == [] and "kon niet draaien" in ops[0]


def test_herstel_zonder_echte_databank_vergelijkt_geen_schema(tmp_path):
    root = maak_project(tmp_path)
    (root / "data" / "interactions.db").unlink()
    h = r.check_herstel(root, tmp_basis=tmp_path)
    assert h["gelukt"] and h["schema_gelijk"] is None
    assert "schema niet vergeleken" in r.rapport_herstel(h)[0]


# ----------------------------------------------------------------------------
# Meldingen
# ----------------------------------------------------------------------------

NU = datetime(2026, 11, 14, 12, 0, 0)


def schrijf_status(root, hartslag=None, meldingstest=None):
    pad = root / "data" / "hartslag_status.json"
    pad.parent.mkdir(parents=True, exist_ok=True)
    pad.write_text(json.dumps({"versie": 1, "hartslag": hartslag, "meldingstest": meldingstest,
                               "bijgewerkt": NU.isoformat()}), encoding="utf-8")


def uit(m):
    return r.beoordeel_meldingen(m, {})


def ago(**kw):
    return (NU - timedelta(**kw)).isoformat()


def test_meldingen_zonder_statusbestand(tmp_path):
    m = r.check_meldingen(tmp_path, NU)
    assert m["gelezen"] is False and uit(m) == ([], [], [])
    assert "nog geen statusbestand" in r.rapport_meldingen(m)[0]


def test_meldingen_kapot_statusbestand_is_stil(tmp_path):
    pad = tmp_path / "data" / "hartslag_status.json"
    pad.parent.mkdir(parents=True)
    pad.write_text("{kapot", encoding="utf-8")
    assert r.check_meldingen(tmp_path, NU)["gelezen"] is False


def test_meldingen_alles_uit_is_neutraal_maar_noemt_het(tmp_path):
    schrijf_status(tmp_path, {"aan": False}, {"aan": False})
    m = r.check_meldingen(tmp_path, NU)
    assert uit(m) == ([], [], [])
    tekst = r.rapport_meldingen(m)[0]
    assert "levenssignaal naar buiten staat UIT" in tekst and "wekelijkse testmelding staat UIT" in tekst


def test_hartslag_gezond_en_verouderd(tmp_path):
    gezond = {"aan": True, "interval_min": 10, "laatste_ok": ago(minutes=4), "fouten_op_rij": 0}
    schrijf_status(tmp_path, gezond, None)
    m = r.check_meldingen(tmp_path, NU)
    assert uit(m) == ([], [], [])
    assert "elke 10 minuten, laatste gelukt: 4 minuten geleden" in r.rapport_meldingen(m)[0]
    schrijf_status(tmp_path, dict(gezond, laatste_ok=ago(hours=3)), None)
    f, o, _ = uit(r.check_meldingen(tmp_path, NU))
    assert f == [] and len(o) == 1 and "3.0 uur geleden" in o[0]


def test_hartslag_die_niet_aankomt_en_nog_nooit_lukte(tmp_path):
    schrijf_status(tmp_path, {"aan": True, "interval_min": 10, "laatste_ok": ago(minutes=1), "fouten_op_rij": 3}, None)
    f, o, _ = uit(r.check_meldingen(tmp_path, NU))
    assert f == [] and "komt niet aan" in o[0]
    schrijf_status(tmp_path, {"aan": True, "interval_min": 10, "laatste_ok": None, "fouten_op_rij": 1}, None)
    assert "nog nooit gelukt" in uit(r.check_meldingen(tmp_path, NU))[1][0]
    schrijf_status(tmp_path, {"aan": True, "interval_min": 10, "laatste_ok": None, "fouten_op_rij": 0}, None)
    assert uit(r.check_meldingen(tmp_path, NU)) == ([], [], [])          # net opgestart: nog geen oordeel


def test_hartslag_met_lang_interval_krijgt_meer_tijd(tmp_path):
    schrijf_status(tmp_path, {"aan": True, "interval_min": 60, "laatste_ok": ago(hours=2), "fouten_op_rij": 0}, None)
    assert uit(r.check_meldingen(tmp_path, NU)) == ([], [], [])          # 3 x 60 min = 3 uur speling


def test_meldingstest_mislukt_eerst_let_op_dan_fout(tmp_path):
    basis = {"aan": True, "schema": "zondag 10:00", "laatste_ok": ago(days=2), "reden": "ntfy staat uit"}
    schrijf_status(tmp_path, None, dict(basis, fouten_op_rij=1))
    f, o, _ = uit(r.check_meldingen(tmp_path, NU))
    assert f == [] and "laatste testmelding naar je gsm mislukte (ntfy staat uit)" in o[0]
    schrijf_status(tmp_path, None, dict(basis, fouten_op_rij=3))
    f, o, _ = uit(r.check_meldingen(tmp_path, NU))
    assert len(f) == 1 and "mislukt al 3 keer op rij" in f[0] and "echt alarm" in f[0]


def test_meldingstest_te_oud(tmp_path):
    schrijf_status(tmp_path, None, {"aan": True, "schema": "zondag 10:00", "laatste_ok": ago(days=12), "fouten_op_rij": 0})
    m = r.check_meldingen(tmp_path, NU)
    assert "12 dagen oud" in uit(m)[1][0]
    assert "testmelding naar je gsm (zondag 10:00), laatste gelukt: 12 dagen geleden" in r.rapport_meldingen(m)[0]


# ----------------------------------------------------------------------------
# Rommel: uitvoer van de tool
# ----------------------------------------------------------------------------

GOED = "ruis\nROMMELTEST: 155 invoeren, 0 crashes, 0 te traag, mediaan 26 ms, langste 220 ms (seed 1)\n"
SLECHT = ("ruis\n\x1b[91m--- CRASHES (invoer en fout)\x1b[0m\n  ['x'*10] ZeroDivisionError: boem\n"
          "  ['abc'] KeyError: 'a'\n--- TE TRAAG (tijdslimiet)\n  ['9**9**9'] tijdslimiet van 10s overschreden\n"
          "ROMMELTEST: 155 invoeren, 2 crashes, 1 te traag, mediaan 30 ms, langste 10002 ms (seed 1)\n")


def test_parse_rommel_goed_en_beoordeling():
    p = r.parse_rommel(GOED, 0)
    assert p["gelukt"] and (p["aantal"], p["crashes"], p["traag"], p["mediaan_ms"], p["langste_ms"]) == (155, 0, 0, 26, 220)
    assert r.beoordeel_rommel(p, {}) == ([], [], [])
    assert "155 rare invoeren" in r.rapport_rommel(p)[0] and "0 crashes" in r.rapport_rommel(p)[0]


def test_parse_rommel_met_crashes_en_hangers():
    p = r.parse_rommel(SLECHT, 1)
    assert p["crashes"] == 2 and p["traag"] == 1
    assert [s for s, _ in p["voorbeelden"]] == ["crash", "crash", "traag"]
    fouten, ops, _ = r.beoordeel_rommel(p, {})
    assert len(fouten) == 1 and "9**9**9" in fouten[0] and "kan me laten vastlopen" in fouten[0]
    assert len(ops) == 1 and "2 van de 155 rare invoeren veroorzaakten een fout" in ops[0] and "ZeroDivisionError" in ops[0]


def test_parse_rommel_mislukte_runs():
    assert "tijdslimiet" in r.parse_rommel(SLECHT, 1, te_laat=True)["reden"]
    assert "niet gestart" in r.parse_rommel("", 127)["reden"]
    assert "veiligheidscontrole" in r.parse_rommel("STOP", 2)["reden"]
    assert "geen resultaat" in r.parse_rommel("onzin", 0)["reden"]
    for p in (r.parse_rommel("onzin", 0), r.parse_rommel("", 127)):
        f, o, _ = r.beoordeel_rommel(p, {})
        assert f == [] and len(o) == 1 and "kon niet draaien" in o[0]
        assert "kon niet draaien" in r.rapport_rommel(p)[0]


def test_rommel_vergelijkt_de_antwoordtijd():
    oud = {"rommel": r.parse_rommel(GOED, 0)}
    nieuw = r.parse_rommel(GOED.replace("mediaan 26", "mediaan 90"), 0)
    assert r.beoordeel_rommel(nieuw, oud)[2] == ["antwoordtijd 26 → 90 ms"]
    assert r.beoordeel_rommel(r.parse_rommel(GOED.replace("mediaan 26", "mediaan 30"), 0), oud)[2] == []


# ----------------------------------------------------------------------------
# De tool zelf
# ----------------------------------------------------------------------------

def test_vaste_invoer_bevat_de_lastige_gevallen():
    invoer = rr.vaste_invoer()
    assert len(invoer) > 90 and all(isinstance(i, str) for i in invoer)
    for lastig in ("", "9**9**9", "\x00", "x" * 100000, "'; DROP TABLE interactions;--"):
        assert lastig in invoer
    assert any("‮" in i for i in invoer) and any("🙂" in i for i in invoer)


def test_willekeurige_invoer_is_herhaalbaar():
    een, twee, drie = rr.willekeurige_invoer(30, 5), rr.willekeurige_invoer(30, 5), rr.willekeurige_invoer(30, 6)
    assert een == twee and een != drie and len(een) == 30 and rr.willekeurige_invoer(0, 5) == []
    assert all(1 <= len(i) for i in een)


def test_kort_kapt_af():
    assert rr.kort("abc") == "'abc'"
    lang = rr.kort("x" * 500)
    assert len(lang) == rr.MAX_TOONBAAR and lang.endswith("…")


class NepKeten:
    def __init__(self, *a, **k):
        self.mislukt = {}

    def draai(self, vraag, voorvragen=None):
        if vraag == "boem":
            return [], "ZeroDivisionError: boem"
        if vraag == "hang":
            return [], "tijdslimiet van 10s overschreden"
        return [], None


def test_draai_sorteert_crashes_en_hangers(monkeypatch, capsys):
    monkeypatch.setattr(rr.rb, "importeer_modules", lambda namen: {})
    monkeypatch.setattr(rr.rb, "controleer_in_kopie", lambda kopie, lijst: True)
    monkeypatch.setattr(rr.rb, "Keten", NepKeten)
    crashes, traag, tijden = rr.draai(["ok", "boem", "hang", "ok2"], toon=True)
    assert [c[0] for c in crashes] == ["boem"] and [t[0] for t in traag] == ["hang"] and len(tijden) == 4
    assert "ok" in capsys.readouterr().out


def test_draai_stopt_als_de_kopie_niet_veilig_is(monkeypatch):
    monkeypatch.setattr(rr.rb, "importeer_modules", lambda namen: {})
    monkeypatch.setattr(rr.rb, "controleer_in_kopie", lambda kopie, lijst: False)
    monkeypatch.setattr(rr.rb, "Keten", NepKeten)
    assert rr.draai(["ok"], toon=False) is None


# ----------------------------------------------------------------------------
# Trend: nieuwe getallen
# ----------------------------------------------------------------------------

def test_trend_neemt_gebruik_en_antwoordtijd_mee():
    res = {"gebruik": {"gelukt": True, "rss_mb": 310.5, "threads": 41},
           "rommel": {"gelukt": True, "mediaan_ms": 26}}
    assert trend.meetpunt(res) == {"rss_mb": 310.5, "threads": 41, "antwoordtijd_ms": 26}
    assert trend.meetpunt({"gebruik": {"gelukt": False, "rss_mb": 1}, "rommel": {"gelukt": False}}) == {}


# ----------------------------------------------------------------------------
# Aansluiting op de zelftest
# ----------------------------------------------------------------------------

class NepBus:
    modules = {"memory": 1}

    def subscribe(self, *a):
        pass

    def publish(self, *a):
        pass


def maak_zelftest(tmp_path, rommel_uitvoer=GOED):
    root = tmp_path / "project"
    for sub in ("core", "modules", "tests", "data", "logs", "tools"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    (root / "main.py").write_text("print('hoi')\n", encoding="utf-8")
    (root / "tools" / "run_rommeltest.py").write_text("# nep\n", encoding="utf-8")
    maak_db(root / "data" / "interactions.db")
    maak_db(root / "data" / "backups" / "interactions_2026-11-14_100000.db")
    kopie = tmp_path / "kopie"
    aangeroepen = []

    def runner(cmd, cwd, timeout, env=None, samenvoegen=True):
        aangeroepen.append(cmd)
        if any(str(c).endswith("run_rommeltest.py") for c in cmd):
            return 0, rommel_uitvoer, False
        if "pyflakes" in cmd:
            return 0, "", False
        if "pytest" in cmd:
            return 0, "10 passed in 1.00s\n", False
        return 127, "onbekend", False

    def kopieer(_):
        kopie.mkdir(exist_ok=True)
        return kopie, kopie

    zt = z.Zelftest(NepBus(), project_root=root, historie_pad=tmp_path / "historie.json",
                    logbestand=tmp_path / "geen.log", runner=runner, kopieer=kopieer,
                    tool_beschikbaar=lambda n: True, opstart=False, nacht=None, achtergrond=False,
                    drukaf=lambda *a, **k: None, klok=lambda: datetime(2026, 11, 14, 12, 0).timestamp())
    return zt, root, aangeroepen


def test_snelle_zelftest_meet_gebruik_en_meldingen_maar_draait_geen_rommel(tmp_path):
    zt, _, aangeroepen = maak_zelftest(tmp_path)
    res = zt.voer_uit("snel")
    assert res["gebruik"]["gelukt"] and res["meldingen"]["gelezen"] is False
    assert "herstel" not in res and "rommel" not in res
    assert not any(str(c).endswith("run_rommeltest.py") for cmd in aangeroepen for c in cmd)
    tekst = zt.rapport(res)
    assert "• Gebruik:" in tekst and "• Meldingen:" in tekst


def test_volledige_zelftest_doet_de_terugzettest_maar_niet_de_rommeltest(tmp_path):
    zt, _, _ = maak_zelftest(tmp_path)
    res = zt.voer_uit("volledig")
    assert res["herstel"]["gelukt"] and res["herstel"]["rijen"] == 5 and "rommel" not in res
    assert "• Terugzettest:" in zt.rapport(res)


def test_volledige_diagnose_draait_ook_de_rommeltest(tmp_path):
    zt, _, _ = maak_zelftest(tmp_path)
    res = zt.voer_uit("alles")
    assert res["rommel"]["gelukt"] and res["rommel"]["aantal"] == 155 and res["rommel"]["duur"] is not None
    assert "• Rommel-invoertest: 155 rare invoeren" in zt.rapport(res)
    punt = trend.meetpunt(res)
    assert punt["antwoordtijd_ms"] == 26 and "rss_mb" in punt


def test_een_hangende_invoer_maakt_de_diagnose_een_fout(tmp_path):
    zt, _, _ = maak_zelftest(tmp_path, rommel_uitvoer=SLECHT)
    res = zt.voer_uit("alles")
    assert res["status"] == "fout" and any("9**9**9" in p for p in res["punten"])


def test_ontbrekende_rommeltest_is_een_opmerking_geen_crash(tmp_path):
    zt, root, _ = maak_zelftest(tmp_path)
    (root / "tools" / "run_rommeltest.py").unlink()
    res = zt.voer_uit("alles")
    assert res["rommel"]["beschikbaar"] is False
    assert any("rommel-invoertest kon niet draaien" in p for p in res["punten"])


def test_opstarttijd_wordt_onthouden(tmp_path):
    zt, _, _ = maak_zelftest(tmp_path)
    assert zt._opstart_s is None or zt._opstart_s >= 0
    assert zt.voer_uit("snel")["gebruik"]["opstart_s"] == zt._opstart_s


def test_hulpbestand_is_geen_module():
    assert not hasattr(r, "init_module")