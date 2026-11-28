# tests/test_trace_punten.py
#
# Test core/trace_punten.py (punt 79): de aanroepen die niet via de EventBus lopen
# melden zich bij de tracer. Bevat ook de controle dat ELKE aanroep in de
# achtergrondlussen van main.py in de lijst staat: voeg je er later een toe zonder hem
# in TRACE_PUNTEN te zetten, dan wordt deze test rood.
#
# Uitvoeren: pytest tests/test_trace_punten.py -v

import ast
import re
from pathlib import Path

import pytest

import core.event_bus as eb
from core.event_bus import EventBus
from core.trace_punten import TRACE_PUNTEN, installeer
from core.tracer import Tracer

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def log_in_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(eb, "_LOGBESTAND", tmp_path / "logs" / "handler_fouten.log")


class Module:
    def __init__(self):
        self.aantal = 0

    def werk(self, x, y=1):
        self.aantal += 1
        return x + y

    def kapot(self):
        raise ValueError("boem")


PUNTEN = {"mijn": ["werk", "kapot"]}


def maak():
    bus = EventBus()
    m = Module()
    res = installeer(bus, {"mijn": m}, PUNTEN)
    return bus, m, res


# ---------- omhullen ----------

def test_functies_worden_omhuld():
    bus, m, res = maak()
    assert res["omhuld"] == ["mijn.werk", "mijn.kapot"]
    assert res["overgeslagen"] == []


def test_uitkomst_en_argumenten_blijven_gelijk_met_tracer_uit():
    bus, m, _ = maak()
    assert m.werk(2, y=5) == 7
    assert m.aantal == 1
    assert len(bus.tracer.log) == 0           # tracer uit: geen records


def test_uitkomst_en_argumenten_blijven_gelijk_met_tracer_aan():
    bus, m, _ = maak()
    bus.tracer.zet(True)
    assert m.werk(2, y=5) == 7
    assert m.aantal == 1


def test_met_tracer_aan_komt_er_een_record_met_duur():
    bus, m, _ = maak()
    bus.tracer.zet(True)
    m.werk(1)
    (r,) = [r for r in bus.tracer.log if r["soort"] == "trace"]
    assert r["handler"] == "mijn.werk"
    assert r["module"] == "mijn"
    assert r["duur_ms"] >= 0
    assert r["start_t"] <= r["t"]


def test_fout_in_de_functie_gaat_ongewijzigd_door_en_wordt_toch_vastgelegd():
    bus, m, _ = maak()
    bus.tracer.zet(True)
    with pytest.raises(ValueError):
        m.kapot()
    assert [r["handler"] for r in bus.tracer.log if r["soort"] == "trace"] == ["mijn.kapot"]


def test_twee_keer_installeren_omhult_maar_een_keer():
    bus, m, _ = maak()
    res2 = installeer(bus, {"mijn": m}, PUNTEN)
    assert res2["omhuld"] == []
    bus.tracer.zet(True)
    m.werk(1)
    assert len([r for r in bus.tracer.log if r["soort"] == "trace"]) == 1


def test_trace_hoort_bij_de_keten_van_kevin():
    bus, m, _ = maak()
    bus.subscribe("chat_message", lambda data: m.werk(1))
    bus.tracer.zet(True)
    bus.publish("chat_message", {})
    (r,) = [r for r in bus.tracer.log if r["soort"] == "trace"]
    assert r["keten"] == 1


# ---------- overslaan ----------

def test_ontbrekende_module_en_functie_worden_overgeslagen():
    bus = EventBus()
    res = installeer(bus, {"a": Module()}, {"a": ["bestaat_niet", "werk"], "b": ["x"]})
    assert res["omhuld"] == ["a.werk"]
    assert ("a.bestaat_niet", "functie bestaat niet") in res["overgeslagen"]
    assert ("b.x", "module niet geladen") in res["overgeslagen"]


def test_attribuut_dat_geen_functie_is_wordt_overgeslagen():
    class M:
        waarde = 5

    res = installeer(EventBus(), {"m": M()}, {"m": ["waarde"]})
    assert res["omhuld"] == []
    assert res["overgeslagen"][0][1] == "functie bestaat niet"


def test_object_dat_geen_attributen_toelaat_wordt_overgeslagen():
    class Slots:
        __slots__ = ()

        def werk(self):
            return 1

    res = installeer(EventBus(), {"s": Slots()}, {"s": ["werk"]})
    assert res["omhuld"] == []
    assert "kon niet omhullen" in res["overgeslagen"][0][1]


def test_bus_zonder_tracer_crasht_niet():
    class OudeBus:
        pass

    res = installeer(OudeBus(), {"mijn": Module()}, PUNTEN)
    assert res["omhuld"] == []
    assert len(res["overgeslagen"]) == 2


def test_geen_modules_en_geen_punten():
    assert installeer(EventBus(), None, {}) == {"omhuld": [], "overgeslagen": []}
    assert installeer(EventBus(), None, {"a": ["b"]})["overgeslagen"] == [("a.b", "module niet geladen")]


# ---------- starttijd in de tracer ----------

def test_start_t_is_de_eindtijd_min_de_duur():
    tijden = iter([100.0, 100.5])
    t = Tracer(klok=lambda: next(tijden), tijd=lambda: 1000.0)
    t.zet(True)
    start = t.begin()
    t.trace("m.f", start)
    (r,) = t.log
    assert r["duur_ms"] == 500.0
    assert r["start_t"] == pytest.approx(999.5)


def test_trace_zonder_start_heeft_geen_duur():
    t = Tracer(tijd=lambda: 50.0)
    t.zet(True)
    t.trace("m.f")
    (r,) = t.log
    assert r["duur_ms"] is None and r["start_t"] == 50.0


# ---------- de lijst zelf ----------

def _alle_functienamen():
    namen = set()
    for pad in list(ROOT.glob("core/*.py")) + list(ROOT.glob("modules/**/*.py")) + list(ROOT.glob("identity/**/*.py")):
        namen.update(re.findall(r"^\s*def (\w+)\(", pad.read_text(encoding="utf-8"), re.M))
    return namen


def test_elke_functie_in_de_lijst_bestaat_ergens_in_de_code():
    bestaand = _alle_functienamen()
    ontbrekend = [f"{m}.{f}" for m, fs in TRACE_PUNTEN.items() for f in fs if f not in bestaand]
    assert ontbrekend == []


def test_lijst_heeft_geen_dubbelen():
    for m, fs in TRACE_PUNTEN.items():
        assert len(fs) == len(set(fs)), m


def _lus_aanroepen():
    """(modulenaam, functie) voor elke aanroep in de lussen van main.py."""
    boom = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
    gevonden = set()
    for knoop in ast.walk(boom):
        if isinstance(knoop, ast.FunctionDef) and knoop.name in ("achtergrond_loop", "snelle_activiteit_loop"):
            variabelen = {}
            for sub in ast.walk(knoop):
                if (isinstance(sub, ast.Assign) and len(sub.targets) == 1
                        and isinstance(sub.targets[0], ast.Name)
                        and isinstance(sub.value, ast.Call)
                        and isinstance(sub.value.func, ast.Attribute)
                        and sub.value.func.attr == "get"
                        and isinstance(sub.value.func.value, ast.Attribute)
                        and sub.value.func.value.attr == "loaded_modules"
                        and sub.value.args and isinstance(sub.value.args[0], ast.Constant)):
                    variabelen[sub.targets[0].id] = sub.value.args[0].value
            for sub in ast.walk(knoop):
                if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                        and isinstance(sub.func.value, ast.Name)
                        and sub.func.value.id in variabelen):
                    gevonden.add((variabelen[sub.func.value.id], sub.func.attr))
    return gevonden


def test_de_lussen_in_main_worden_echt_gevonden():
    # vangnet voor deze test zelf: als main.py anders wordt opgebouwd, moet hij niet stil niets vinden
    assert len(_lus_aanroepen()) >= 10


def test_elke_aanroep_in_de_achtergrondlussen_staat_in_trace_punten():
    ontbreekt = [f"{m}.{f}" for m, f in sorted(_lus_aanroepen()) if f not in TRACE_PUNTEN.get(m, [])]
    assert ontbreekt == [], f"Zet deze in core/trace_punten.py (TRACE_PUNTEN): {ontbreekt}"


def test_router_roept_response_engine_generate_aan_en_dat_staat_in_de_lijst():
    bron = (ROOT / "core" / "intent_router.py").read_text(encoding="utf-8")
    assert "response_engine.generate(" in bron
    assert "generate" in TRACE_PUNTEN["response_engine"]


def test_main_installeert_de_trace_punten():
    bron = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "installeer_trace_punten(bus, loader.loaded_modules)" in bron