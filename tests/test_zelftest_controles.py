# tests/test_zelftest_controles.py
"""
Tests voor modules/diagnose/controles.py en de uitbreiding van modules/diagnose/zelftest.py
(14 november 2026: de "volledige diagnose").

Er wordt NIETS echt gestart: coverage, vulture, bandit, pip-audit en de benchmark worden
vervangen door een nep-runner met vaste uitvoer. Alle bestanden staan in tmp_path.
"""
import json
import os
import pkgutil
import sqlite3
import time
from datetime import datetime, time as dagtijd, timedelta
from types import SimpleNamespace

import pytest

import modules
from modules.diagnose import controles as c
from modules.diagnose import zelftest as z

NU = datetime(2026, 11, 14, 12, 0, 0)


@pytest.fixture(autouse=True)
def _geen_zelftest_instellingen_uit_de_omgeving(monkeypatch):
    """Op de echte server staan ZELFTEST_* misschien in de omgeving (via .env); deze tests mogen daar niet van afhangen."""
    for naam in list(os.environ):
        if naam.startswith("ZELFTEST_"):
            monkeypatch.delenv(naam, raising=False)


# ----------------------------------------------------------------------------
# Hulpmiddelen
# ----------------------------------------------------------------------------

class NepBus:
    def __init__(self, geladen=None):
        self.subs = {}
        self.out = []
        if geladen is not None:
            self.modules = geladen

    def subscribe(self, event, handler):
        self.subs.setdefault(event, []).append(handler)

    def publish(self, event, data=None):
        self.out.append((event, data))
        for h in self.subs.get(event, []):
            h(data, event)


def bm_uitvoer(goed, fout, crash=0, nm=0, onterecht=(), router=None):
    """Bouwt uitvoer zoals tools/run_benchmark.py (met kleurcodes erin)."""
    totaal = goed + fout + crash
    pct = round(100 * goed / totaal) if totaal else 0
    regels = [
        "\x1b[96m[ROUTER]\x1b[0m \x1b[93mOntvangen: 'hoi'\x1b[0m",
        "=== RESULTAAT (niveau 2: antwoord; set: taal-vast) ===",
        "categorie              score  goed  fout  crash  n.m.",
        "definitie                83%    25     5      0     0",
        "-----------------------------------------------------",
        f"TOTAAL                   {pct}%   {goed}   {fout}      {crash}     {nm}",
        "(n.m. = niet meetbaar op dit niveau, telt niet mee in de score)",
        "",
        "Mislukte cases:",
        "  [taal-t5-02] 'wat is een zwabbelknoop'",
        "      gefaald: geen antwoord ontvangen",
        "--- ONTERECHTE ANTWOORDEN (de ergste fout) ---",
    ]
    regels += [f"  [{naam}] 'een zin'" for naam in onterecht] or ["  geen"]
    regels += ["--- NIET EERLIJK ONZEKER (stilte of onduidelijk, niet gevaarlijk) ---",
               "  [taal-t5-05] 'wie is de president van glorbistan'",
               "      geen antwoord ontvangen"]
    if router:
        regels += ["--- WAAROM FAALT HET? (taal, stilte, kennis) ---",
                   f"  Router begreep {router[0]}/{router[1]} zinnen ({round(100 * router[0] / router[1])}%): "
                   f"dit is de echte taalscore."]
    return "\n".join(regels) + "\n"


COVERAGE_JSON = json.dumps({
    "totals": {"percent_covered": 71.234},
    "files": {
        "core/a.py": {"summary": {"num_statements": 100, "percent_covered": 90.0}},
        "core/b.py": {"summary": {"num_statements": 50, "percent_covered": 0.0}},
        "core/c.py": {"summary": {"num_statements": 10, "percent_covered": 0.0}},
        "core/leeg.py": {"summary": {"num_statements": 0, "percent_covered": 100.0}},
    },
})
VULTURE_UIT = (
    "core/memory.py:365: unused variable 'frame' (100% confidence)\n"
    "core/memory.py:365: unused variable 'signum' (100% confidence)\n"
    "modules/x.py:10: unused import 'os' (90% confidence)\n"
    "modules/y.py:699: unreachable code after 'return' (100% confidence)\n"
)
BANDIT_JSON = json.dumps({"results": [
    {"issue_severity": "HIGH", "filename": "modules/a.py", "line_number": 171, "test_id": "B324",
     "issue_text": "Use of weak SHA1 hash for security."},
    {"issue_severity": "MEDIUM", "filename": "modules/b.py", "line_number": 5, "test_id": "B310", "issue_text": "x"},
    {"issue_severity": "LOW", "filename": "modules/c.py", "line_number": 6, "test_id": "B311", "issue_text": "y"},
    {"issue_severity": "LOW", "filename": "modules/c.py", "line_number": 9, "test_id": "B311", "issue_text": "y"},
], "errors": []})
PIPAUDIT_JSON = json.dumps({"dependencies": [
    {"name": "pillow", "version": "12.3.0", "vulns": [{"id": "A"}, {"id": "B"}]},
    {"name": "numpy", "version": "2.0", "vulns": []},
    {"name": "setuptools", "version": "68", "vulns": [{"id": "C"}]},
    {"name": "lokaal", "skip_reason": "niet op PyPI"},
]})


def maak_project(tmp_path):
    root = tmp_path / "project"
    for sub in ("core", "modules", "tests", "data", "logs", "tools"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    (root / "main.py").write_text("print('hoi')\n", encoding="utf-8")
    (root / "data" / "gegevens.json").write_text('{"a": 1}', encoding="utf-8")
    return root


def maak_backup(map_, naam, uren_oud, rijen=3, kapot=False):
    map_.mkdir(parents=True, exist_ok=True)
    pad = map_ / naam
    if kapot:
        pad.write_bytes(b"dit is geen databank" * 100)
    else:
        verbinding = sqlite3.connect(str(pad))
        verbinding.execute("CREATE TABLE interactions (id INTEGER)")
        verbinding.executemany("INSERT INTO interactions VALUES (?)", [(i,) for i in range(rijen)])
        verbinding.commit()
        verbinding.close()
    tijd = (NU - timedelta(hours=uren_oud)).timestamp()
    os.utime(pad, (tijd, tijd))
    return pad


# ----------------------------------------------------------------------------
# Backup
# ----------------------------------------------------------------------------

def test_backup_geen_databank_en_geen_backups_is_niet_nodig(tmp_path):
    root = maak_project(tmp_path)
    b = c.check_backup(root, NU)
    assert b["nodig"] is False and b["gevonden"] == 0
    assert c.beoordeel_backup(b, {}) == ([], [], [])
    assert "geen back-up nodig" in c.rapport_backup(b)[0]


def test_backup_databank_zonder_backups_geeft_let_op(tmp_path):
    root = maak_project(tmp_path)
    (root / "data" / "interactions.db").write_bytes(b"")
    b = c.check_backup(root, NU)
    assert b["nodig"] is True and b["gevonden"] == 0
    fouten, opm, _ = c.beoordeel_backup(b, {})
    assert fouten == [] and "geen enkele back-up" in opm[0]
    assert "GEEN enkele back-up" in c.rapport_backup(b)[0]


def test_verse_backup_is_ok_en_wordt_gelezen(tmp_path):
    root = maak_project(tmp_path)
    maak_backup(root / "data" / "backups", "interactions_2026-11-14_090000.db", 3, rijen=5)
    maak_backup(root / "data" / "backups", "interactions_2026-11-13_090000.db", 27)
    b = c.check_backup(root, NU)
    assert b["gevonden"] == 2
    assert b["nieuwste"] == "interactions_2026-11-14_090000.db"
    assert b["leeftijd_uur"] == 3.0
    assert b["db_ok"] is True and b["rijen"] == 5
    assert c.beoordeel_backup(b, {}) == ([], [], [])
    assert "5 rijen" in c.rapport_backup(b)[0] and "3 uur" in c.rapport_backup(b)[0]


def test_backup_origineel_wordt_niet_aangeraakt(tmp_path):
    root = maak_project(tmp_path)
    pad = maak_backup(root / "data" / "backups", "interactions_x.db", 1)
    voor = pad.stat()
    c.check_backup(root, NU)
    na = pad.stat()
    assert (voor.st_size, voor.st_mtime) == (na.st_size, na.st_mtime)
    assert sorted(p.name for p in (root / "data" / "backups").iterdir()) == ["interactions_x.db"]


@pytest.mark.parametrize("uren,verwacht", [(7, "ok"), (10, "let_op"), (80, "fout")])
def test_backup_leeftijd_bepaalt_de_status(uren, verwacht):
    b = {"nodig": True, "gevonden": 3, "nieuwste": "x.db", "leeftijd_uur": uren, "db_ok": True, "rijen": 1}
    fouten, opm, _ = c.beoordeel_backup(b, {})
    status = "fout" if fouten else ("let_op" if opm else "ok")
    assert status == verwacht


def test_kapotte_backup_is_een_fout(tmp_path):
    root = maak_project(tmp_path)
    maak_backup(root / "data" / "backups", "interactions_kapot.db", 1, kapot=True)
    b = c.check_backup(root, NU)
    assert b["db_ok"] is False
    fouten, _, _ = c.beoordeel_backup(b, {})
    assert "kapot" in fouten[0]
    assert "KAPOT" in c.rapport_backup(b)[0]


def test_backup_leeftijd_in_dagen_en_uren():
    assert c._tijdsduur(0.4) == "minder dan een uur"
    assert c._tijdsduur(5.5) == "5.5 uur"
    assert c._tijdsduur(96) == "4 dagen"


# ----------------------------------------------------------------------------
# Schijf
# ----------------------------------------------------------------------------

def test_schijf_meet_grootte_zonder_backups_in_data(tmp_path):
    root = maak_project(tmp_path)
    (root / "data" / "groot.bin").write_bytes(b"x" * 2_000_000)
    (root / "data" / "backups").mkdir()
    (root / "data" / "backups" / "b.db").write_bytes(b"y" * 3_000_000)
    (root / "logs" / "nova.log").write_bytes(b"z" * 500_000)
    s = c.check_schijf(root)
    assert s["gelukt"] is True
    assert 2.0 <= s["data_mb"] < 2.1               # inclusief gegevens.json, zonder backups
    assert s["backups_mb"] == 3.0
    assert s["logs_mb"] == 0.5
    assert s["vrij_gb"] > 0 and 0 < s["vrij_procent"] <= 100


def test_schijf_niet_meetbaar_wordt_netjes_gemeld(tmp_path, monkeypatch):
    def stuk(_):
        raise OSError("weg")
    monkeypatch.setattr(c.shutil, "disk_usage", stuk)
    s = c.check_schijf(tmp_path)
    assert s["gelukt"] is False
    assert c.beoordeel_schijf(s, {}) == ([], [], [])
    assert "kon niet gemeten worden" in c.rapport_schijf(s)[0]


@pytest.mark.parametrize("gb,procent,verwacht", [
    (500.0, 40.0, "ok"), (4.0, 50.0, "let_op"), (100.0, 9.0, "let_op"),
    (0.5, 50.0, "fout"), (100.0, 1.0, "fout")])
def test_schijf_drempels(gb, procent, verwacht):
    s = {"gelukt": True, "vrij_gb": gb, "vrij_procent": procent, "data_mb": 1, "backups_mb": 1, "logs_mb": 1}
    fouten, opm, _ = c.beoordeel_schijf(s, {})
    assert ("fout" if fouten else "let_op" if opm else "ok") == verwacht


def test_schijf_grote_logs_en_vergelijking():
    s = {"gelukt": True, "vrij_gb": 200.0, "vrij_procent": 50.0, "data_mb": 150.0, "backups_mb": 5.0, "logs_mb": 250.0}
    vorig = {"schijf": {"vrij_gb": 205.0, "data_mb": 100.0, "backups_mb": 5.0}}
    fouten, opm, verg = c.beoordeel_schijf(s, vorig)
    assert fouten == [] and "250 MB" in opm[0]
    assert "vrije ruimte (GB) 205 → 200" in verg
    assert "data (MB) 100 → 150" in verg
    assert not any("back-ups" in v for v in verg)


# ----------------------------------------------------------------------------
# Modules
# ----------------------------------------------------------------------------

def maak_modules(root):
    basis = root / "modules"
    for groep, bestanden in {
        "alfa": {"een.py": "def init_module(bus):\n    return 1\n", "twee.py": "x = 1\n",
                 "emergence_engine.py": "def init_module(bus):\n    return 1\n"},
        "debug": {"dbg.py": "def init_module(bus):\n    return 1\n"},
        "beta": {"drie.py": "def init_module(bus, sem=None):\n    return 1\n", "kapot.py": "def (:\n"},
    }.items():
        (basis / groep).mkdir(parents=True, exist_ok=True)
        (basis / groep / "__init__.py").write_text("", encoding="utf-8")
        for naam, inhoud in bestanden.items():
            (basis / groep / naam).write_text(inhoud, encoding="utf-8")
    (basis / "zonder_init").mkdir(exist_ok=True)               # geen __init__.py: loader slaat dit over
    (basis / "zonder_init" / "vier.py").write_text("def init_module(bus):\n    return 1\n", encoding="utf-8")


def test_modules_op_schijf_en_verwachte_modules(tmp_path):
    root = maak_project(tmp_path)
    maak_modules(root)
    alle = c.modules_op_schijf(root)
    assert alle == {"een": "alfa/een.py", "emergence_engine": "alfa/emergence_engine.py",
                    "dbg": "debug/dbg.py", "drie": "beta/drie.py"}
    assert c.verwachte_modules(root) == {"een": "alfa/een.py", "drie": "beta/drie.py"}


def test_modules_alles_geladen_is_in_orde(tmp_path):
    root = maak_project(tmp_path)
    maak_modules(root)
    m = c.check_modules(NepBus({"een": 1, "drie": 2, "memory": 3}), root)
    assert m["gelukt"] and m["verwacht"] == 2 and m["geladen"] == 3 and m["ontbreekt"] == []
    assert c.beoordeel_modules(m, {}) == ([], [], [])
    assert "alle 2 verwachte modules" in c.rapport_modules(m)[0]


def test_modules_een_ontbrekende_module_geeft_let_op(tmp_path):
    root = maak_project(tmp_path)
    maak_modules(root)
    m = c.check_modules(NepBus({"een": 1}), root)
    assert m["ontbreekt"] == ["beta/drie.py"]
    fouten, opm, _ = c.beoordeel_modules(m, {})
    assert fouten == [] and "1 module staat op schijf maar is niet geladen: beta/drie.py" in opm[0]
    assert "ontbreken: beta/drie.py" in c.rapport_modules(m)[0]


def test_modules_meervoud_en_vergelijking(tmp_path):
    root = maak_project(tmp_path)
    maak_modules(root)
    m = c.check_modules(NepBus({"x": 1}), root)
    _, opm, verg = c.beoordeel_modules(m, {"modules": {"geladen": 5}})
    assert "2 modules staan op schijf maar zijn niet geladen" in opm[0]
    assert verg == ["geladen modules 5 → 1"]


@pytest.mark.parametrize("bus", [object(), NepBus(), NepBus({})])
def test_modules_zonder_zicht_geeft_geen_oordeel(tmp_path, bus):
    m = c.check_modules(bus, maak_project(tmp_path))
    assert m["gelukt"] is False
    assert c.beoordeel_modules(m, {}) == ([], [], [])
    assert "niet gecontroleerd" in c.rapport_modules(m)[0]


# ----------------------------------------------------------------------------
# Consistentie
# ----------------------------------------------------------------------------

def schrijf_identity(root, identiteit, schema=None):
    map_ = root / "identity" / "blueprint"
    map_.mkdir(parents=True, exist_ok=True)
    (map_ / "identity.json").write_text(json.dumps(identiteit), encoding="utf-8")
    (map_ / "schema.json").write_text(json.dumps(schema or {"type": "object", "required": ["naam"]}),
                                      encoding="utf-8")


def test_consistentie_zonder_bestanden_is_neutraal(tmp_path):
    r = c.check_consistentie(maak_project(tmp_path))
    assert r["identity"] == "niet aanwezig" and r["concepten"] is None
    assert c.beoordeel_consistentie(r, {}) == ([], [], [])
    assert c.rapport_consistentie(r) == ["• Identiteit: niet aanwezig."]


def test_identity_geldig_en_ongeldig(tmp_path):
    root = maak_project(tmp_path)
    schrijf_identity(root, {"naam": "Nova"})
    assert c.check_consistentie(root)["identity"] == "ok"
    schrijf_identity(root, {"andere": 1})
    r = c.check_consistentie(root)
    assert r["identity"].startswith("ongeldig: ") and "naam" in r["identity"]
    fouten, _, _ = c.beoordeel_consistentie(r, {})
    assert "identity.json klopt niet met zijn schema" in fouten[0] and "naam" in fouten[0]


def test_identity_kapot_json_is_geen_ongeldig_maar_niet_te_lezen(tmp_path):
    root = maak_project(tmp_path)
    schrijf_identity(root, {"naam": "Nova"})
    (root / "identity" / "blueprint" / "identity.json").write_text("{kapot", encoding="utf-8")
    r = c.check_consistentie(root)
    assert r["identity"].startswith("niet te lezen")
    assert c.beoordeel_consistentie(r, {})[0] == []


def concept(woord, *relaties, sense_id=None):
    return {"senses": [{"sense_id": sense_id or f"{woord}#1", "definition": "d",
                        "relations": [{"type": "related_to", "target": t} for t in relaties]}]}


def test_concepten_gezond_telt_relaties_naar_onbekende_woorden(tmp_path):
    root = maak_project(tmp_path)
    (root / "data" / "concepts.json").write_text(json.dumps({
        "hond": concept("hond", "dier", "Kat"), "dier": concept("dier"), "kat": concept("kat", "bestaatniet"),
    }), encoding="utf-8")
    r = c.check_consistentie(root)
    assert (r["concepten"], r["relaties"], r["onbekend_doel"]) == (3, 3, 1)
    assert r["kapot_aantal"] == 0 and r["dubbel_aantal"] == 0
    fouten, opm, verg = c.beoordeel_consistentie(r, {"consistentie": {"concepten": 2, "onbekend_doel": 1}})
    assert fouten == [] and opm == [] and verg == ["concepten 2 → 3"]
    assert "3 concepten en 3 relaties" in c.rapport_consistentie(r)[-1]


def test_concepten_kapotte_opbouw_en_dubbele_sense_ids(tmp_path):
    root = maak_project(tmp_path)
    (root / "data" / "concepts.json").write_text(json.dumps({
        "a": "geen woordenboek", "b": {"senses": "geen lijst"}, "c": {"senses": [5]},
        "d": concept("d", sense_id="x#1"), "e": concept("e", sense_id="x#1"),
    }), encoding="utf-8")
    r = c.check_consistentie(root)
    assert r["kapot_aantal"] == 3 and sorted(r["kapot"]) == ["a", "b", "c"]
    assert r["dubbel"] == ["x#1"]
    fouten, opm, _ = c.beoordeel_consistentie(r, {})
    assert fouten == [] and "3 concepten hebben een kapotte opbouw" in opm[0]
    assert "1 sense_id komt dubbel voor: x#1" in opm[1]


@pytest.mark.parametrize("inhoud,reden", [("{kapot", "niet te lezen"), ("[1, 2]", "geen woordenboek")])
def test_concepten_onleesbaar_of_verkeerd_type(tmp_path, inhoud, reden):
    root = maak_project(tmp_path)
    (root / "data" / "concepts.json").write_text(inhoud, encoding="utf-8")
    r = c.check_consistentie(root)
    assert reden in r["reden"] and r["concepten"] is None
    assert c.beoordeel_consistentie(r, {})[0] == []
    assert reden in c.rapport_consistentie(r)[-1]


# ----------------------------------------------------------------------------
# Documentatie
# ----------------------------------------------------------------------------

def schrijf_overzicht(root, rijen):
    doc = root.joinpath(*c.DOC_PAD)
    doc.parent.mkdir(parents=True, exist_ok=True)
    regels = ["| # | Fase | Module | File | Pad | Description | Status |",
              "| - | ---- | ------ | ---- | --- | ----------- | ------ |"]
    for i, (bestand, pad, status) in enumerate(rijen, 1):
        regels.append(f"| {i} | 2 | Groep | {bestand} | {pad} | Een | symbool in de tekst | {status} |")
    doc.write_text("\n".join(regels) + "\n", encoding="utf-8")


def test_docs_ontbreekt_is_neutraal(tmp_path):
    d = c.check_docs(maak_project(tmp_path))
    assert d["aanwezig"] is False
    assert c.beoordeel_docs(d, {}) == ([], [], [])
    assert "niet gevonden" in c.rapport_docs(d)[0]


def test_docs_vindt_alle_soorten_afwijkingen(tmp_path):
    root = maak_project(tmp_path)
    maak_modules(root)
    (root / "core" / "bestaat.py").write_text("x = 1\n", encoding="utf-8")
    schrijf_overzicht(root, [
        ("bestaat.py", "core/", "Gebouwd"),
        ("weg.py", "core/", "Gebouwd"),
        ("later.py", "core/", "Nog niet gebouwd"),
        ("typfout.py", "core/", "Nog niet gebovered"),
        ("een.py", "modules/alfa/", "Gebouwd"),
    ])
    d = c.check_docs(root)
    assert d["aanwezig"] and d["gebouwd"] == 3
    assert d["ontbreekt_op_schijf"] == ["core/weg.py"]          # modules/alfa/een.py bestaat wel
    assert d["onbekende_status"] == ["typfout.py (Nog niet gebovered)"]
    assert d["niet_beschreven"] == ["alfa/emergence_engine.py", "beta/drie.py", "debug/dbg.py"]
    assert d["niet_beschreven_aantal"] == 3
    fouten, opm, _ = c.beoordeel_docs(d, {})
    assert fouten == [] and len(opm) == 2
    assert "core/weg.py" in opm[0] and "typfout.py" in opm[1]
    assert "3 modules staan er nog niet in" in c.rapport_docs(d)[0]


def test_docs_nieuwe_ongedocumenteerde_module_geeft_let_op(tmp_path):
    d = {"aanwezig": True, "gebouwd": 1, "ontbreekt_op_schijf": [], "onbekende_status": [],
         "niet_beschreven_aantal": 5, "niet_beschreven": []}
    _, opm, verg = c.beoordeel_docs(d, {"docs": {"niet_beschreven_aantal": 3}})
    assert opm == ["2 nieuwe modules staan nog niet in het modules-overzicht"]
    assert verg == ["modules zonder beschrijving 3 → 5"]
    assert c.beoordeel_docs(d, {})[1] == []                 # zonder vorige run: geen oordeel


def test_lees_modules_overzicht_slaat_kop_en_rommel_over(tmp_path):
    pad = tmp_path / "doc.md"
    pad.write_text("# Titel\n\n| # | Fase | Module | File | Pad | Description | Status |\n"
                   "| - | ---- | ------ | ---- | --- | ----------- | ------ |\n"
                   "| 1 | 2 | M | a.py | core/ | x | Gebouwd |\n| te | kort |\n", encoding="utf-8")
    assert c.lees_modules_overzicht(pad) == [{"file": "a.py", "pad": "core/", "status": "Gebouwd"}]
    assert c.lees_modules_overzicht(tmp_path / "bestaatniet.md") == []


# ----------------------------------------------------------------------------
# Benchmark
# ----------------------------------------------------------------------------

def test_parse_benchmark_taal():
    r = c.parse_benchmark(bm_uitvoer(131, 111, router=(237, 242)), 0)
    assert r["gelukt"] and (r["goed"], r["fout"], r["crash"], r["niet_meetbaar"]) == (131, 111, 0, 0)
    assert (r["router_begrepen"], r["router_totaal"]) == (237, 242)
    assert r["onterecht"] == 0                 # de regels bij 'mislukte cases' en 'niet eerlijk onzeker' tellen niet


def test_parse_benchmark_telt_onterechte_antwoorden():
    r = c.parse_benchmark(bm_uitvoer(10, 2, onterecht=("taal-t5-09", "taal-t5-11")), 1)
    assert r["onterecht"] == 2 and r["gelukt"]


def test_parse_benchmark_zonder_resultaat_of_te_laat():
    assert "gecrasht" in c.parse_benchmark("Traceback (most recent call last):\n", 1)["reden"]
    assert c.parse_benchmark("", 0, te_laat=True)["reden"] == "tijdslimiet overschreden"
    assert "niet gestart" in c.parse_benchmark("x", 127)["reden"]
    assert c.parse_benchmark(None, 1)["gelukt"] is False


def bm(goed, fout, crash=0, onterecht=(), router=None, duur=3.0):
    r = c.parse_benchmark(bm_uitvoer(goed, fout, crash, onterecht=onterecht, router=router), 0)
    r["duur"] = duur
    return r


def test_benchmark_onterecht_antwoord_is_een_fout():
    fouten, _, _ = c.beoordeel_benchmark({"taal": bm(100, 10, onterecht=("a",), router=(100, 110))}, {})
    assert len(fouten) == 1 and "1 onterecht antwoord" in fouten[0] and "taalbenchmark" in fouten[0]


def test_benchmark_crash_is_een_fout():
    fouten, _, _ = c.beoordeel_benchmark({"rook": bm(25, 0, crash=2)}, {})
    assert "2 vragen lieten een module crashen" in fouten[0]


def test_benchmark_gefaalde_vaste_vragen_geven_let_op_maar_gefaalde_taalvragen_niet():
    fouten, opm, _ = c.beoordeel_benchmark({"rook": bm(26, 3), "taal": bm(50, 50, router=(90, 100))}, {})
    assert fouten == []
    assert len(opm) == 1 and "3 van de 29 vaste vragen" in opm[0] and "rooktest" in opm[0]


def test_benchmark_daling_geeft_let_op_en_stijging_alleen_vergelijking():
    vorig = {"benchmark": {"taal": bm(60, 40, router=(98, 100)), "rook": bm(29, 0)}}
    nu = {"taal": bm(55, 45, router=(96, 100)), "rook": bm(29, 0)}
    _, opm, verg = c.beoordeel_benchmark(nu, vorig)
    assert any("score daalde van 60% naar 55%" in o for o in opm)
    assert any("taalbegrip daalde van 98% naar 96%" in o for o in opm)
    assert "taalbenchmark score 60% → 55%" in verg

    beter = {"taal": bm(70, 30, router=(99, 100)), "rook": bm(29, 0)}
    _, opm2, verg2 = c.beoordeel_benchmark(beter, vorig)
    assert opm2 == [] and any("60% → 70%" in v for v in verg2)


def test_benchmark_rooktest_veel_trager_geeft_let_op():
    vorig = {"benchmark": {"rook": bm(29, 0, duur=4.0)}}
    _, opm, _ = c.beoordeel_benchmark({"rook": bm(29, 0, duur=20.0)}, vorig)
    assert any("20 s tegenover 4 s" in o for o in opm)
    _, opm2, _ = c.beoordeel_benchmark({"rook": bm(29, 0, duur=7.0)}, vorig)      # trager, maar niet zeer
    assert opm2 == []


def test_benchmark_niet_beschikbaar_is_neutraal_maar_mislukt_geeft_let_op():
    weg = {"beschikbaar": False, "gelukt": False, "reden": "tools/run_benchmark.py niet gevonden"}
    assert c.beoordeel_benchmark({"taal": weg, "rook": weg}, {}) == ([], [], [])
    mislukt = c.parse_benchmark("Traceback", 1)
    _, opm, _ = c.beoordeel_benchmark({"taal": mislukt}, {})
    assert "taalbenchmark kon niet draaien" in opm[0]


def test_benchmark_rapport():
    regels = c.rapport_benchmark({"taal": bm(131, 111, router=(237, 242)), "rook": bm(29, 0, duur=2.4)})
    assert regels[0].startswith("• Taalbegrip: de router begreep 237 van de 242 zinnen (98%)")
    assert "131 van de 242 antwoorden goed (54%)" in regels[0] and "0 onterechte antwoorden" in regels[0]
    assert regels[1] == "• Rooktest: 29 van de 29 vaste vragen goed (100%), 0 crashes, 2 s."
    weg = {"beschikbaar": False, "gelukt": False, "reden": "niet gevonden"}
    assert "niet gecontroleerd" in c.rapport_benchmark({"taal": weg})[0]


# ----------------------------------------------------------------------------
# Dekking, dode code, beveiliging, pakketten (ontleden)
# ----------------------------------------------------------------------------

def test_parse_coverage():
    r = c.parse_coverage(COVERAGE_JSON, 0)
    assert r["gelukt"] and r["procent"] == 71.2 and r["bestanden"] == 3 and r["ongetest"] == 2
    assert r["minst"] == [{"bestand": "core/b.py", "procent": 0}, {"bestand": "core/a.py", "procent": 90}]


def test_parse_coverage_met_ruis_voor_de_json_en_fouten():
    assert c.parse_coverage("waarschuwing\n" + COVERAGE_JSON, 0)["gelukt"] is True
    assert "geen bruikbare" in c.parse_coverage("rommel", 1)["reden"]
    assert "geen bruikbare" in c.parse_coverage('{"totals": {}}', 0)["reden"]
    assert "niet gestart" in c.parse_coverage("", 127)["reden"]
    assert c.parse_coverage("", -1, te_laat=True)["reden"] == "tijdslimiet overschreden"


def test_parse_vulture_negeert_verplichte_parameters():
    r = c.parse_vulture(VULTURE_UIT, 3)
    assert r["gelukt"] and r["aantal"] == 2 and r["onbereikbaar"] == 1
    assert r["voorbeelden"][0] == "modules/x.py:10: unused import 'os'"


def test_parse_vulture_codes():
    assert c.parse_vulture("", 0)["aantal"] == 0 and c.parse_vulture("", 0)["gelukt"]
    assert c.parse_vulture("", 1)["gelukt"] is False
    assert "niet gestart" in c.parse_vulture("", 127)["reden"]
    assert c.parse_vulture("", -1, te_laat=True)["gelukt"] is False
    assert len(c.parse_vulture("a.py:1: unused import 'x' (90% confidence)\n" * 9, 3)["voorbeelden"]) == c.MAX_VOORBEELDEN


def test_parse_bandit():
    r = c.parse_bandit(BANDIT_JSON, 1)
    assert r["gelukt"] and (r["hoog"], r["middel"], r["laag"]) == (1, 1, 2)
    assert r["hoge"] == ["modules/a.py:171 B324: Use of weak SHA1 hash for security."]


def test_parse_bandit_fouten():
    assert "geen geldige JSON" in c.parse_bandit("Traceback", 2)["reden"]
    assert "geen geldige JSON" in c.parse_bandit('{"andere": 1}', 0)["reden"]
    assert "niet gestart" in c.parse_bandit("", 127)["reden"]
    assert c.parse_bandit("", -1, te_laat=True)["gelukt"] is False


def test_parse_pipaudit():
    r = c.parse_pipaudit(PIPAUDIT_JSON, 1)
    assert r["gelukt"] and r["pakketten"] == 4 and r["kwetsbaar_aantal"] == 2 and r["kwetsbaarheden"] == 3
    assert [k["naam"] for k in r["kwetsbaar"]] == ["pillow", "setuptools"]      # meeste kwetsbaarheden eerst


def test_parse_pipaudit_zonder_internet():
    r = c.parse_pipaudit("", 1)
    assert r["gelukt"] is False and "internet" in r["reden"]
    assert c.beoordeel_pakketten(r, {}) == ([], [], [])            # geen internet is geen reden voor let_op
    assert "kon niet draaien" in c.rapport_pakketten(r)[0]


# ----------------------------------------------------------------------------
# Dekking, dode code, beveiliging, pakketten (beoordelen en rapporteren)
# ----------------------------------------------------------------------------

def test_dekking_beoordelen_en_rapporteren():
    nu = c.parse_coverage(COVERAGE_JSON, 0)
    assert c.beoordeel_dekking(nu, {}) == ([], [], [])
    _, opm, verg = c.beoordeel_dekking(nu, {"dekking": {"procent": 75.0}})
    assert opm == ["de dekking daalde van 75% naar 71.2%"] and verg == ["dekking (%) 75 → 71.2"]
    _, opm2, verg2 = c.beoordeel_dekking(nu, {"dekking": {"procent": 71.0}})
    assert opm2 == [] and verg2 == []                              # verschil kleiner dan 0,5
    tekst = c.rapport_dekking(nu)[0]
    assert "71.2% van de code" in tekst and "core/b.py (0%)" in tekst and "2 helemaal niet" in tekst


def test_ontbrekende_tools_geven_een_installatietip():
    weg = {"beschikbaar": False, "gelukt": False, "reden": "niet geïnstalleerd"}
    for functie, tool in ((c.beoordeel_dekking, "coverage"), (c.beoordeel_dode_code, "vulture"),
                          (c.beoordeel_beveiliging, "bandit"), (c.beoordeel_pakketten, "pip-audit")):
        fouten, opm, _ = functie(weg, {})
        assert fouten == [] and f"{tool} is niet geïnstalleerd" in opm[0]


def test_dode_code_beoordelen_alleen_bij_toename():
    nu = c.parse_vulture(VULTURE_UIT, 3)
    assert c.beoordeel_dode_code(nu, {}) == ([], [], [])
    _, opm, verg = c.beoordeel_dode_code(nu, {"dode_code": {"aantal": 1}})
    assert opm == ["1 melding meer over dode code dan vorige keer"]
    assert verg == ["meldingen over dode code 1 → 2"]
    assert c.beoordeel_dode_code(nu, {"dode_code": {"aantal": 5}})[1] == []
    regels = c.rapport_dode_code(nu)
    assert regels[0] == "• Dode code: 2 meldingen, waarvan 1 onbereikbare code."
    assert regels[1].startswith("    - modules/x.py:10")


def test_beveiliging_beoordelen_alleen_bij_toename():
    nu = c.parse_bandit(BANDIT_JSON, 1)
    assert c.beoordeel_beveiliging(nu, {}) == ([], [], [])
    _, opm, verg = c.beoordeel_beveiliging(nu, {"beveiliging": {"hoog": 0, "middel": 3}})
    assert opm == ["1 nieuwe hoge beveiligingsbevinding"]
    assert "hoge bevindingen 0 → 1" in verg and "middelhoge bevindingen 3 → 1" in verg
    _, opm2, _ = c.beoordeel_beveiliging(nu, {"beveiliging": {"hoog": 0, "middel": 0}})
    assert opm2 == ["1 nieuwe hoge beveiligingsbevinding", "1 nieuwe middelhoge beveiligingsbevinding"]
    meer = dict(nu, hoog=3)
    assert c.beoordeel_beveiliging(meer, {"beveiliging": {"hoog": 0, "middel": 1}})[1] == \
        ["3 nieuwe hoge beveiligingsbevindingen"]
    assert c.rapport_beveiliging(nu)[0] == "• Beveiliging: 1 hoog, 1 middel, 2 laag (bandit)."


def test_pakketten_beoordelen_en_rapporteren():
    nu = c.parse_pipaudit(PIPAUDIT_JSON, 1)
    assert c.beoordeel_pakketten(nu, {}) == ([], [], [])
    _, opm, verg = c.beoordeel_pakketten(nu, {"pakketten": {"kwetsbaar_aantal": 1}})
    assert opm == ["1 pakket met een bekende kwetsbaarheid erbij"] and verg == ["kwetsbare pakketten 1 → 2"]
    tekst = c.rapport_pakketten(nu)[0]
    assert "2 pakketten van de 4" in tekst and "pillow 12.3.0" in tekst and "(3 in totaal)" in tekst


# ----------------------------------------------------------------------------
# Aansluiting op de zelftest
# ----------------------------------------------------------------------------

class NepRunner:
    """Geeft per programma vaste uitvoer terug en onthoudt wat er gestart werd."""

    def __init__(self, coverage_json=COVERAGE_JSON, taal=None, rook=None, vulture=VULTURE_UIT,
                 bandit=BANDIT_JSON, pipaudit=PIPAUDIT_JSON):
        self.aanroepen = []
        self.coverage_json = coverage_json
        self.taal = taal if taal is not None else bm_uitvoer(131, 111, router=(237, 242))
        self.rook = rook if rook is not None else bm_uitvoer(29, 0)
        self.vulture, self.bandit, self.pipaudit = vulture, bandit, pipaudit

    def __call__(self, cmd, cwd, timeout, env=None, samenvoegen=True):
        self.aanroepen.append({"cmd": cmd, "cwd": cwd, "timeout": timeout, "env": env})
        if any(str(x).endswith("run_benchmark.py") for x in cmd):
            return 0, (self.taal if "--taal" in cmd else self.rook), False
        if "coverage" in cmd and "json" in cmd:
            return 0, self.coverage_json, False
        if "pytest" in cmd:
            return 0, "4000 passed, 1 skipped in 20.00s\n", False
        if "pyflakes" in cmd:
            return 1, "core/a.py:1:1: 'os' imported but unused\n", False
        if "radon" in cmd:
            return 0, json.dumps({"core/a.py": [{"type": "function", "rank": "A", "complexity": 2, "name": "f"}]}), False
        if "vulture" in cmd:
            return 3, self.vulture, False
        if "bandit" in cmd:
            return 1, self.bandit, False
        if "pip_audit" in cmd:
            return 1, self.pipaudit, False
        return 127, "onbekend", False

    def gestart(self, woord):
        """Aanroepen waarvan 'woord' een onderdeel van het commando is (niet zomaar een stukje pad)."""
        return [a for a in self.aanroepen
                if woord in a["cmd"] or any(str(x).endswith(f"{woord}.py") for x in a["cmd"])]


def maak_z(tmp_path, runner=None, met_script=True, **extra):
    root = maak_project(tmp_path)
    if met_script:
        (root / "tools" / "run_benchmark.py").write_text("# nep\n", encoding="utf-8")
    kopie_map = tmp_path / "kopie_tmp"

    def kopieer(project_root):
        kopie_map.mkdir(exist_ok=True)
        return kopie_map, kopie_map

    opties = dict(project_root=root, historie_pad=tmp_path / "historie.json", logbestand=tmp_path / "geen.log",
                  runner=runner or NepRunner(), kopieer=kopieer, tool_beschikbaar=lambda naam: True,
                  opstart=False, nacht=None, achtergrond=False, drukaf=lambda *a, **k: None,
                  klok=lambda: NU.timestamp())
    opties.update(extra)
    bus = NepBus({"memory": 1})
    return z.Zelftest(bus, **opties), bus, opties["runner"]


def test_snel_doet_de_goedkope_gezondheidscontroles_maar_geen_zware_stappen(tmp_path):
    zt, _, runner = maak_z(tmp_path)
    res = zt.voer_uit("snel")
    for sleutel in ("pyflakes", "data", "log", "backup", "schijf", "modules", "consistentie", "docs"):
        assert sleutel in res, sleutel
    for sleutel in ("pytest", "radon", "benchmark", "dekking", "dode_code", "beveiliging", "pakketten"):
        assert sleutel not in res, sleutel
    assert runner.gestart("run_benchmark") == [] and runner.gestart("pytest") == []


def test_volledig_draait_de_benchmark_twee_keer_veilig(tmp_path, monkeypatch):
    monkeypatch.setenv("NTFY_TOPIC", "geheim")
    zt, _, runner = maak_z(tmp_path)
    res = zt.voer_uit("volledig")
    assert res["benchmark"]["taal"]["router_begrepen"] == 237
    assert res["benchmark"]["rook"]["goed"] == 29 and res["benchmark"]["rook"]["duur"] is not None
    assert "dekking" not in res and "dode_code" not in res
    aanroepen = runner.gestart("run_benchmark")
    assert len(aanroepen) == 2
    cmds = [a["cmd"] for a in aanroepen]
    assert all("--geen-opslaan" in cmd for cmd in cmds)           # schrijft niets in je echte data
    assert any("--taal" in cmd for cmd in cmds) and any(cmd[-3:-1] == ["--niveau", "3"] for cmd in cmds)
    assert all("NTFY_TOPIC" not in a["env"] for a in aanroepen)   # geen sleutels mee
    assert all(a["env"].get(z.ENV_GUARD) for a in aanroepen)
    assert all(a["timeout"] == z.BENCHMARK_TIMEOUT for a in aanroepen)


def test_volledig_zonder_benchmarkscript_slaat_die_stap_netjes_over(tmp_path):
    zt, _, runner = maak_z(tmp_path, met_script=False)
    res = zt.voer_uit("volledig")
    assert res["benchmark"]["taal"]["beschikbaar"] is False
    assert runner.gestart("run_benchmark") == []
    assert res["status"] == "let_op" or res["status"] == "ok"
    assert not any("benchmark" in p for p in res["punten"])
    assert "niet gecontroleerd" in zt.rapport(res)


def test_alles_meet_dekking_met_dezelfde_tests_run(tmp_path):
    zt, _, runner = maak_z(tmp_path)
    res = zt.voer_uit("alles")
    assert res["modus"] == "alles"
    assert res["dekking"]["procent"] == 71.2
    assert res["pytest"]["geslaagd"] == 4000
    pytest_runs = [a for a in runner.aanroepen if "pytest" in a["cmd"]]
    assert len(pytest_runs) == 1                                   # niet twee keer testen
    cmd = pytest_runs[0]["cmd"]
    assert "coverage" in cmd and "run" in cmd and "--source=core,modules,identity" in cmd
    assert len(runner.gestart("coverage")) == 2                    # run + json
    assert res["dode_code"]["aantal"] == 2 and res["beveiliging"]["hoog"] == 1
    assert "pakketten" not in res and runner.gestart("pip_audit") == []


def test_alles_met_pakketten_aan_draait_pip_audit(tmp_path):
    zt, _, runner = maak_z(tmp_path, pakketten=True)
    res = zt.voer_uit("alles")
    assert res["pakketten"]["kwetsbaar_aantal"] == 2
    assert len(runner.gestart("pip_audit")) == 1
    assert "Pakketten: 2 pakketten van de 4" in zt.rapport(res)


def test_alles_zonder_coverage_draait_gewone_pytest_en_meldt_het(tmp_path):
    zt, _, runner = maak_z(tmp_path, tool_beschikbaar=lambda naam: naam != "coverage")
    res = zt.voer_uit("alles")
    assert res["pytest"]["geslaagd"] == 4000
    assert res["dekking"]["beschikbaar"] is False
    assert runner.gestart("coverage") == []
    assert any("coverage is niet geïnstalleerd" in p for p in res["punten"])
    assert res["status"] == "let_op"


@pytest.mark.parametrize("ontbrekend", ["vulture", "bandit"])
def test_alles_zonder_vulture_of_bandit_geeft_let_op(tmp_path, ontbrekend):
    zt, _, _ = maak_z(tmp_path, tool_beschikbaar=lambda naam: naam != ontbrekend)
    res = zt.voer_uit("alles")
    assert res["status"] == "let_op"
    assert any(f"{ontbrekend} is niet geïnstalleerd" in p for p in res["punten"])


def test_volledige_diagnose_vergelijkt_met_de_vorige_diagnose(tmp_path):
    zt, _, runner = maak_z(tmp_path)
    eerste = zt.voer_uit("alles")
    assert eerste["vorige_tijd"] is None
    runner.coverage_json = COVERAGE_JSON.replace("71.234", "60.0")
    runner.vulture = VULTURE_UIT + "modules/z.py:3: unused import 'sys' (90% confidence)\n"
    tweede = zt.voer_uit("alles")
    assert tweede["vorige_tijd"] == eerste["tijd"]
    assert any("de dekking daalde van 71.2% naar 60%" in p for p in tweede["punten"])
    assert any("meer over dode code" in p for p in tweede["punten"])
    assert "dekking (%) 71.2 → 60" in tweede["vergelijking"]
    # snel en volledig vergelijken zich alleen met hun eigen soort
    assert zt.voer_uit("snel")["vorige_tijd"] is None


def test_onterecht_antwoord_in_de_diagnose_geeft_status_fout(tmp_path):
    taal = bm_uitvoer(100, 10, onterecht=("taal-t5-09",), router=(100, 110))
    zt, bus, _ = maak_z(tmp_path, runner=NepRunner(taal=taal))
    res = zt._run_automatisch("volledig", "nacht")
    assert res["status"] == "fout"
    gsm = [d for e, d in bus.out if e == "layer4_response"]
    assert len(gsm) == 1 and "onterecht antwoord" in gsm[0]["text"]


def test_kapotte_backup_in_snel_geeft_fout_en_gsm(tmp_path):
    zt, bus, _ = maak_z(tmp_path)
    maak_backup(zt.root / "data" / "backups", "interactions_kapot.db", 1, kapot=True)
    res = zt._run_automatisch("snel", "opstart")
    assert res["status"] == "fout"
    assert [d for e, d in bus.out if e == "layer4_response"]


def test_een_crashende_nieuwe_stap_houdt_de_rest_niet_tegen(tmp_path):
    zt, _, _ = maak_z(tmp_path)

    def stuk():
        raise RuntimeError("boem")
    zt._stap_backup = stuk
    res = zt.voer_uit("snel")
    assert res["backup"]["gelukt"] is False and "backup crashte" in res["backup"]["reden"]
    assert "schijf" in res and "docs" in res


def test_rapport_van_de_diagnose_heeft_een_eigen_kop_en_alle_onderdelen(tmp_path):
    zt, _, _ = maak_z(tmp_path)
    tekst = zt.rapport(zt.voer_uit("alles"))
    assert tekst.splitlines()[0].startswith("Zelftest (volledige diagnose) klaar in")
    for woord in ("Tests:", "Dekking:", "Taalbegrip:", "Rooktest:", "Pyflakes:", "Complexiteit:", "Dode code:",
                  "Beveiliging:", "Data:", "Identiteit:", "Documentatie:", "Back-up:", "Schijf:", "Modules:",
                  "Foutenlog:"):
        assert woord in tekst, woord


def test_gsm_tekst_noemt_de_volledige_diagnose():
    tekst = z.maak_meldingtekst({"modus": "alles", "punten": ["iets stuk"]})
    assert tekst.startswith("Zelftest (volledige diagnose): iets stuk.")


def test_commando_alles_geeft_een_eigen_startbericht(tmp_path):
    zt, _, _ = maak_z(tmp_path)
    berichten = []
    assert zt.start_op_commando("alles", berichten.append) is True
    assert berichten[0].startswith("Volledige diagnose gestart.")
    for _ in range(200):                                 # wacht tot de thread klaar is
        if len(berichten) > 1:
            break
        time.sleep(0.05)
    assert "Zelftest (volledige diagnose) klaar" in berichten[1]


def test_nachtmodus_uit_parameter_en_omgeving(tmp_path, monkeypatch):
    zt, _, _ = maak_z(tmp_path)
    assert zt._nacht_modus == "volledig"
    assert maak_z(tmp_path / "a", nacht_modus="alles")[0]._nacht_modus == "alles"
    assert maak_z(tmp_path / "b", nacht_modus="onzin")[0]._nacht_modus == "volledig"
    monkeypatch.setenv("ZELFTEST_NACHT_MODUS", "ALLES")
    assert maak_z(tmp_path / "c")[0]._nacht_modus == "alles"


def test_de_nachtrun_gebruikt_de_gekozen_modus(tmp_path):
    zt, _, runner = maak_z(tmp_path, nacht=dagtijd(3, 30), nacht_modus="alles")
    res = zt.controleer_nacht(datetime(2026, 11, 14, 4, 0))
    assert res is not None and res["modus"] == "alles" and res["bron"] == "nacht"
    assert runner.gestart("vulture")


def test_pakketten_staan_standaard_uit_en_gaan_aan_via_omgeving(tmp_path, monkeypatch):
    assert maak_z(tmp_path)[0]._pakketten_aan is False
    monkeypatch.setenv("ZELFTEST_PAKKETTEN", "aan")
    assert maak_z(tmp_path / "b")[0]._pakketten_aan is True
    monkeypatch.setenv("ZELFTEST_PAKKETTEN", "uit")
    assert maak_z(tmp_path / "c")[0]._pakketten_aan is False


# ----------------------------------------------------------------------------
# Bedrading: niets vergeten
# ----------------------------------------------------------------------------

def test_elke_stap_heeft_een_methode_en_een_plek_in_het_rapport():
    for sleutel, modi in z._STAPPEN:
        assert callable(getattr(z.Zelftest, f"_stap_{sleutel}")), sleutel
        assert set(modi) <= set(z._MODI)
    uitvoer_sleutels = {sleutel for sleutel, _ in z._STAPPEN} | {"dekking"}
    assert uitvoer_sleutels <= set(z._VOLGORDE)
    assert set(z._VOLGORDE) == set(z._BEOORDELAARS) == set(z._RAPPORTEERDERS)


def test_alle_controles_hebben_een_beoordelaar_en_een_rapporteerder():
    assert set(c.BEOORDELAARS) == set(c.RAPPORTEERDERS)


def test_controles_is_een_hulpbestand_en_geen_module():
    namen = [naam for _, naam, _ in pkgutil.walk_packages(modules.__path__, prefix="modules.")]
    assert "modules.diagnose.controles" in namen
    assert not hasattr(c, "init_module")                 # module_loader.py slaat het daardoor over


@pytest.mark.parametrize("zin,modus", [
    ("start full diagnostic", "alles"), ("Start Full Diagnostic.", "alles"), ("full diagnostic!", "alles"),
    ("run full diagnostic", "alles"), ("start volledige diagnose", "alles"), ("volledige diagnose", "alles"),
    ("zelftest alles", "alles"), ("zelftest diagnose", "alles"), ("zelftest", "volledig"),
    ("zelftest snel", "snel"), ("test jezelf", "volledig"), ("zelftest volledig", "volledig")])
def test_debug_commandos_kiezen_de_juiste_modus(zin, modus):
    from modules.debug.debug_commands import DebugCommands

    class Nep:
        def __init__(self):
            self.gestart = []

        def start_op_commando(self, m, uitvoer):
            self.gestart.append(m)

    nep = Nep()
    dbg = DebugCommands(NepBus(), SimpleNamespace(loaded_modules={"zelftest": nep}))
    assert dbg.is_debug_command(zin.lower().strip()) is True
    dbg.handle_debug_command({"text": zin})
    assert nep.gestart == [modus]


@pytest.mark.parametrize("zin", ["full diagnostic nu", "diagnose", "start diagnostic", "zelftesten", "wat is een diagnose"])
def test_debug_herkent_gewone_zinnen_over_diagnoses_niet(zin):
    from modules.debug.debug_commands import DebugCommands
    dbg = DebugCommands(NepBus(), SimpleNamespace(loaded_modules={}))
    assert dbg.is_debug_command(zin) is False


def test_debug_onbekend_argument_noemt_alles(capsys):
    from modules.debug.debug_commands import DebugCommands
    dbg = DebugCommands(NepBus(), SimpleNamespace(loaded_modules={"zelftest": object()}))
    dbg.handle_debug_command({"text": "zelftest raar"})
    assert "zelftest alles" in capsys.readouterr().out