# tests/test_zelftest_trend.py
"""
Tests voor modules/diagnose/trend.py en modules/diagnose/samenvatting.py, en hun aansluiting
op de zelftest en de debug-commando's (14 november 2026).

Er wordt niets echt gestart: alle bestanden staan in tmp_path en de zelftest krijgt een
nep-runner met vaste uitvoer.
"""
import json
import os
from datetime import datetime
from types import SimpleNamespace

import pytest

from modules.diagnose import samenvatting as s
from modules.diagnose import trend as t
from modules.diagnose import zelftest as z


@pytest.fixture(autouse=True)
def _geen_zelftest_instellingen_uit_de_omgeving(monkeypatch):
    for naam in list(os.environ):
        if naam.startswith("ZELFTEST_"):
            monkeypatch.delenv(naam, raising=False)


def run(tijd="2026-11-14T10:00:00", router=(237, 242), taal=(131, 111), rook=(29, 0), dekking=71.7,
        tests=4931, zwaar=41, concepten=1264, data_mb=8412.2, **extra):
    """Een zelftest-resultaat zoals voer_uit() dat maakt (alleen de delen die de trend nodig heeft)."""
    res = {
        "tijd": tijd, "modus": "alles", "status": "ok", "punten": [],
        "pytest": {"gelukt": True, "geslaagd": tests},
        "benchmark": {
            "taal": {"gelukt": True, "goed": taal[0], "fout": taal[1], "crash": 0,
                     "router_begrepen": router[0], "router_totaal": router[1]},
            "rook": {"gelukt": True, "goed": rook[0], "fout": rook[1], "crash": 0},
        },
        "dekking": {"gelukt": True, "procent": dekking},
        "radon": {"gelukt": True, "zwaar": zwaar},
        "consistentie": {"concepten": concepten},
        "schijf": {"gelukt": True, "data_mb": data_mb},
        "backup": {"gevonden": 7, "db_ok": True, "leeftijd_uur": 0.2},
    }
    res.update(extra)
    return res


# ----------------------------------------------------------------------------
# Meetpunt en opslag
# ----------------------------------------------------------------------------

def test_meetpunt_haalt_de_getallen_uit_een_resultaat():
    assert t.meetpunt(run()) == {
        "taalbegrip": 97.9, "antwoorden": 54.1, "rooktest": 100.0, "dekking": 71.7,
        "tests": 4931, "zware_functies": 41, "concepten": 1264, "data_mb": 8412.2}


def test_meetpunt_neemt_alleen_mee_wat_gemeten_is():
    snel = {"consistentie": {"concepten": 5}, "schijf": {"gelukt": True, "data_mb": 1.5}, "pyflakes": {}}
    assert t.meetpunt(snel) == {"concepten": 5, "data_mb": 1.5}
    kapot = run()
    kapot["pytest"] = {"gelukt": False, "geslaagd": 0}
    kapot["dekking"] = {"gelukt": False}
    assert "tests" not in t.meetpunt(kapot) and "dekking" not in t.meetpunt(kapot)
    assert t.meetpunt({}) == {}


def test_meetpunt_zonder_taalzinnen_deelt_niet_door_nul():
    res = run()
    res["benchmark"]["taal"].update(router_totaal=0, goed=0, fout=0)
    punt = t.meetpunt(res)
    assert "taalbegrip" not in punt and "antwoorden" not in punt


def test_voeg_toe_meerdere_runs_op_een_dag_combineren_en_nieuw_wint():
    data = t.leeg()
    t.voeg_toe(data, "2026-11-14T03:30:00", {"tests": 4000, "dekking": 70.0})
    t.voeg_toe(data, "2026-11-14T10:00:00", {"tests": 4100, "concepten": 9})
    assert data["dagen"] == {"2026-11-14": {"tests": 4100, "dekking": 70.0, "concepten": 9}}


def test_voeg_toe_negeert_lege_punten_en_kapotte_tijden():
    data = t.leeg()
    t.voeg_toe(data, "2026-11-14T10:00:00", {})
    t.voeg_toe(data, "geen tijd", {"tests": 1})
    t.voeg_toe(data, None, {"tests": 1})
    assert data["dagen"] == {}


def test_voeg_toe_houdt_hoogstens_max_dagen_vast(monkeypatch):
    monkeypatch.setattr(t, "MAX_DAGEN", 3)
    data = t.leeg()
    for dag in range(1, 6):
        t.voeg_toe(data, f"2026-11-{dag:02d}T10:00:00", {"tests": dag})
    assert sorted(data["dagen"]) == ["2026-11-03", "2026-11-04", "2026-11-05"]


def test_opbouw_uit_historie_begint_niet_van_nul():
    runs = [run("2026-11-12T10:00:00", tests=4800), run("2026-11-13T10:00:00", tests=4900),
            {"tijd": "2026-11-13T12:00:00", "modus": "snel"}]
    data = t.opbouw_uit_historie(runs)
    assert sorted(data["dagen"]) == ["2026-11-12", "2026-11-13"]
    assert data["dagen"]["2026-11-13"]["tests"] == 4900


def test_bewaar_en_laad_rondje_zonder_tijdelijk_bestand(tmp_path):
    pad = tmp_path / "map" / "trend.json"
    data = t.voeg_toe(t.leeg(), "2026-11-14T10:00:00", {"tests": 5})
    assert t.bewaar(pad, data) is True
    assert t.laad(pad) == data
    assert [p.name for p in pad.parent.iterdir()] == ["trend.json"]


@pytest.mark.parametrize("inhoud", ["{kapot", "[1, 2]", '{"dagen": 5}', ""])
def test_laad_geeft_none_bij_een_kapot_bestand(tmp_path, inhoud):
    pad = tmp_path / "trend.json"
    pad.write_text(inhoud, encoding="utf-8")
    assert t.laad(pad) is None
    assert t.laad(tmp_path / "bestaatniet.json") is None


def test_bewaar_geeft_false_als_schrijven_mislukt(tmp_path):
    bezet = tmp_path / "bestand"
    bezet.write_text("x", encoding="utf-8")
    assert t.bewaar(bezet / "trend.json", t.leeg()) is False        # 'bestand' is geen map


# ----------------------------------------------------------------------------
# Tekst
# ----------------------------------------------------------------------------

def test_sparkline():
    assert t.sparkline([1, 2, 3, 4, 5, 6, 7, 8]) == "▁▂▃▄▅▆▇█"
    assert t.sparkline([5, 5, 5]) == "▄▄▄"
    assert t.sparkline([None, 1, None, 3]) == "▁█"
    assert t.sparkline([1]) == "" and t.sparkline([]) == "" and t.sparkline([None, None]) == ""


def test_trend_tekst_zonder_meetdagen():
    assert "Nog geen trend" in t.trend_tekst(t.leeg())
    assert "Nog geen trend" in t.trend_tekst(None)
    assert "Nog geen trend" in t.trend_tekst({"dagen": {"2026-11-14": {}}})


def test_trend_tekst_met_een_dag_belooft_groei_voor_morgen():
    data = t.opbouw_uit_historie([run()])
    tekst = t.trend_tekst(data)
    assert "1 meetdagen" in tekst and "14-11" in tekst and "97.9%" in tekst and "4931" in tekst
    assert "vanaf morgen" in tekst
    assert "Sinds" not in tekst


def test_trend_tekst_vergelijkt_met_een_week_eerder():
    runs = [run("2026-11-07T10:00:00", router=(230, 242), taal=(120, 122), tests=4800, concepten=1200),
            run("2026-11-10T10:00:00", router=(233, 242), taal=(125, 117), tests=4850, concepten=1230),
            run("2026-11-14T10:00:00", router=(237, 242), taal=(131, 111), tests=4931, concepten=1264)]
    tekst = t.trend_tekst(t.opbouw_uit_historie(runs))
    assert "3 meetdagen" in tekst
    regels = tekst.splitlines()
    assert regels[1].split()[:2] == ["datum", "taalbegrip"]
    assert regels[2].startswith("  07-11") and regels[-4].startswith("  Taalbegrip")
    sinds = [r for r in regels if r.startswith("Sinds")][0]
    assert sinds.startswith("Sinds 07-11:")                              # precies een week eerder
    assert "taalbegrip 95.0% → 97.9% (+2.9 punten)" in sinds or "taalbegrip 95%" in sinds
    assert "tests 4800 → 4931 (+131)" in sinds and "concepten 1200 → 1264 (+64)" in sinds


def test_trend_tekst_zonder_verandering_en_met_korte_geschiedenis():
    runs = [run("2026-11-13T10:00:00"), run("2026-11-14T10:00:00")]
    tekst = t.trend_tekst(t.opbouw_uit_historie(runs))
    assert "Sinds 13-11: geen verandering in deze cijfers." in tekst


def test_trend_tekst_toont_maximaal_het_gevraagde_aantal_dagen():
    runs = [run(f"2026-11-{d:02d}T10:00:00", tests=4000 + d) for d in range(1, 13)]
    tekst = t.trend_tekst(t.opbouw_uit_historie(runs), max_dagen=3)
    assert "12 meetdagen, laatste 3" in tekst
    assert "  10-11" in tekst and "  09-11" not in tekst


def test_trend_tekst_ontbrekende_waarden_worden_streepjes():
    data = t.opbouw_uit_historie([{"tijd": "2026-11-14T10:00:00", "consistentie": {"concepten": 7}}])
    rij = t.trend_tekst(data).splitlines()[2]
    assert rij.split()[1:] == ["-", "-", "-", "-", "-", "7"]


# ----------------------------------------------------------------------------
# Samenvatting
# ----------------------------------------------------------------------------

def test_samenvatting_alles_in_orde():
    tekst = s.maak_samenvatting(run())
    assert tekst.startswith("Diagnose voltooid. Alle systemen functioneren normaal.")
    assert "Al mijn 4931 tests slagen." in tekst
    assert "Ik begrijp 98 procent van de zinnen die ik ken." in tekst
    assert "Mijn geheugen bevat 1264 concepten." in tekst
    assert "Mijn laatste back-up is minder dan een uur oud en leesbaar." in tekst


def test_samenvatting_let_op_noemt_de_aandachtspunten():
    een = s.maak_samenvatting(run(status="let_op", punten=["rooktest duurde 30 s"]))
    assert "Ik functioneer, maar er is een punt dat aandacht verdient." in een
    assert "Aandachtspunt: rooktest duurde 30 s." in een
    veel = s.maak_samenvatting(run(status="let_op", punten=["a", "b", "c", "d", "e"]))
    assert "er zijn 5 punten" in veel
    assert veel.count("Aandachtspunt:") == s.MAX_PUNTEN
    leeg_let_op = s.maak_samenvatting({"status": "let_op", "punten": []})
    assert "er is iets om op te letten" in leeg_let_op


def test_samenvatting_fout_geeft_een_waarschuwing():
    tekst = s.maak_samenvatting(run(status="fout", punten=["de nieuwste back-up is kapot"]))
    assert "Waarschuwing: er is iets mis." in tekst and "Probleem: de nieuwste back-up is kapot." in tekst
    assert "Alle systemen functioneren normaal" not in tekst


def test_samenvatting_noemt_alleen_wat_gemeten_is():
    tekst = s.maak_samenvatting({"status": "ok", "punten": []})
    assert tekst == "Diagnose voltooid. Alle systemen functioneren normaal."
    kapotte_backup = s.maak_samenvatting(run(backup={"gevonden": 1, "db_ok": False}))
    assert "back-up" not in kapotte_backup
    assert "tests" not in s.maak_samenvatting(run(pytest={"gelukt": False}))


def test_samenvatting_zonder_resultaat():
    assert s.maak_samenvatting(None) == "Ik heb mezelf nog niet getest."


# ----------------------------------------------------------------------------
# Aansluiting op de zelftest
# ----------------------------------------------------------------------------

class NepBus:
    modules = {"memory": 1}

    def subscribe(self, *a):
        pass

    def publish(self, *a):
        pass


def nep_runner(cmd, cwd, timeout, env=None, samenvoegen=True):
    if "pyflakes" in cmd:
        return 0, "", False
    if "pytest" in cmd:
        return 0, "10 passed in 1.00s\n", False
    return 127, "onbekend", False


def maak_z(tmp_path, historie=None, **extra):
    root = tmp_path / "project"
    for sub in ("core", "modules", "tests", "data", "logs"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    (root / "main.py").write_text("print('hoi')\n", encoding="utf-8")
    historie_pad = tmp_path / "historie.json"
    if historie is not None:
        historie_pad.write_text(json.dumps({"versie": 1, "runs": historie, "laatste_nacht_datum": None}),
                                encoding="utf-8")
    kopie = tmp_path / "kopie"

    def kopieer(_):
        kopie.mkdir(exist_ok=True)
        return kopie, kopie

    opties = dict(project_root=root, historie_pad=historie_pad, logbestand=tmp_path / "geen.log",
                  runner=nep_runner, kopieer=kopieer, tool_beschikbaar=lambda n: True, opstart=False,
                  nacht=None, achtergrond=False, drukaf=lambda *a, **k: None,
                  klok=lambda: datetime(2026, 11, 14, 12, 0).timestamp())
    opties.update(extra)
    return z.Zelftest(NepBus(), **opties), root


def test_zelftest_schrijft_na_elke_run_een_meetpunt(tmp_path):
    zt, root = maak_z(tmp_path)
    zt.voer_uit("volledig")
    data = json.loads((root / "data" / "zelftest_trend.json").read_text(encoding="utf-8"))
    assert data["dagen"]["2026-11-14"]["tests"] == 10
    zt.voer_uit("snel")                                         # vult aan, wist niets
    data = json.loads((root / "data" / "zelftest_trend.json").read_text(encoding="utf-8"))
    assert data["dagen"]["2026-11-14"]["tests"] == 10
    assert "data_mb" in data["dagen"]["2026-11-14"]


def test_zelftest_bouwt_de_eerste_trend_uit_de_bestaande_historie(tmp_path):
    oud = [run("2026-11-10T10:00:00", tests=4700), run("2026-11-12T10:00:00", tests=4800)]
    zt, root = maak_z(tmp_path, historie=oud)
    assert sorted(zt._trend["dagen"]) == ["2026-11-10", "2026-11-12"]
    assert not (root / "data" / "zelftest_trend.json").exists()   # pas bij de eerste nieuwe run bewaard
    zt.voer_uit("volledig")
    data = json.loads((root / "data" / "zelftest_trend.json").read_text(encoding="utf-8"))
    assert sorted(data["dagen"]) == ["2026-11-10", "2026-11-12", "2026-11-14"]


def test_zelftest_gebruikt_een_bestaand_trendbestand(tmp_path):
    pad = tmp_path / "eigen_trend.json"
    t.bewaar(pad, t.voeg_toe(t.leeg(), "2026-01-01T10:00:00", {"tests": 1}))
    zt, _ = maak_z(tmp_path, trend_pad=pad, historie=[run("2026-11-10T10:00:00")])
    assert list(zt._trend["dagen"]) == ["2026-01-01"]            # niet opnieuw uit de historie gebouwd


def test_een_trend_die_niet_bewaard_kan_worden_stopt_de_zelftest_niet(tmp_path):
    meldingen = []
    bezet = tmp_path / "bestand"
    bezet.write_text("x", encoding="utf-8")
    zt, _ = maak_z(tmp_path, trend_pad=bezet / "trend.json", drukaf=meldingen.append)
    res = zt.voer_uit("snel")
    assert res is not None and "status" in res
    assert any("Trend niet bewaard" in m for m in meldingen)


def test_trend_tekst_en_samenvatting_van_de_zelftest(tmp_path):
    zt, _ = maak_z(tmp_path)
    assert "Nog geen trend" in zt.trend_tekst()
    assert zt.samenvatting_tekst() == "Ik heb mezelf nog niet getest."
    zt.voer_uit("volledig")
    assert "1 meetdagen" in zt.trend_tekst()
    assert zt.samenvatting_tekst().startswith("Diagnose voltooid.")


def test_rapport_van_de_volledige_diagnose_eindigt_met_een_samenvatting(tmp_path):
    zt, _ = maak_z(tmp_path)
    tekst = zt.rapport(zt.voer_uit("alles"))
    assert "\n\nSamenvatting: Diagnose voltooid." in tekst
    assert "Samenvatting" not in zt.rapport(zt.voer_uit("volledig"))
    assert "Samenvatting" not in zt.rapport(zt.voer_uit("snel"))


def test_hulpbestanden_zijn_geen_modules():
    assert not hasattr(t, "init_module") and not hasattr(s, "init_module")


# ----------------------------------------------------------------------------
# Debug-commando's
# ----------------------------------------------------------------------------

class NepZelftest:
    def trend_tekst(self):
        return "TRENDTEKST"

    def samenvatting_tekst(self):
        return "SAMENVATTINGSTEKST"

    def status_tekst(self):
        return "STATUS"

    def start_op_commando(self, modus, uitvoer):
        uitvoer(f"gestart {modus}")


def maak_debug():
    from modules.debug.debug_commands import DebugCommands
    return DebugCommands(NepBus(), SimpleNamespace(loaded_modules={"zelftest": NepZelftest()}))


@pytest.mark.parametrize("zin,verwacht", [("zelftest trend", "TRENDTEKST"),
                                          ("Zelftest Samenvatting", "SAMENVATTINGSTEKST")])
def test_debug_commandos_trend_en_samenvatting(zin, verwacht, capsys):
    dbg = maak_debug()
    assert dbg.is_debug_command(zin.lower()) is True
    dbg.handle_debug_command({"text": zin})
    assert verwacht in capsys.readouterr().out


def test_debug_onbekend_argument_noemt_trend_en_samenvatting(capsys):
    maak_debug().handle_debug_command({"text": "zelftest raar"})
    uit = capsys.readouterr().out
    assert "zelftest trend" in uit and "zelftest samenvatting" in uit