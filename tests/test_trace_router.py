# tests/test_trace_router.py
#
# Test core/trace_router.py (punt 79): alle modules automatisch zichtbaar, de router
# (detect_*-functies met "treffer") en de "eigen tijd" zonder de omhulde kinderen.
#
# Uitvoeren: pytest tests/test_trace_router.py -v

from pathlib import Path

import pytest

import core.event_bus as eb
from core.event_bus import EventBus
from core.trace_router import installeer_auto
from core.tracer import Tracer

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def log_in_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(eb, "_LOGBESTAND", tmp_path / "logs" / "handler_fouten.log")


class Voorbeeld:
    def __init__(self):
        self.aantal = 0
        self.property_gelezen = 0

    def werk(self, x, y=1):
        self.aantal += 1
        return x + y

    def kapot(self):
        raise ValueError("boem")

    def _prive(self):
        return 1

    @property
    def lastig(self):
        self.property_gelezen += 1
        return 5

    @staticmethod
    def statisch():
        return 1

    @classmethod
    def klas(cls):
        return 2

    async def asynchroon(self):
        return 3


def maak(modules=None):
    bus = EventBus()
    inst = Voorbeeld()
    res = installeer_auto(bus, modules if modules is not None else {"voorbeeld": inst})
    return bus, inst, res


# ---------- wat wordt omhuld ----------

def test_publieke_functies_worden_omhuld_en_de_rest_niet():
    bus, inst, res = maak()
    assert getattr(inst.werk, "_getraceerd", False)
    assert getattr(inst.kapot, "_getraceerd", False)
    assert not getattr(inst._prive, "_getraceerd", False)
    assert res["per_module"] == {"voorbeeld": 2}
    assert res["omhuld"] == 2


def test_property_wordt_niet_uitgevoerd_en_niet_omhuld():
    bus, inst, _ = maak()
    assert inst.property_gelezen == 0
    assert inst.lastig == 5


def test_static_class_en_async_blijven_zoals_ze_waren():
    bus, inst, _ = maak()
    assert Voorbeeld.statisch() == 1
    assert Voorbeeld.klas() == 2
    assert inst.asynchroon.__func__ is Voorbeeld.asynchroon


def test_modules_logger_en_none_worden_overgeslagen():
    import json
    bus = EventBus()
    res = installeer_auto(bus, {"logger": Voorbeeld(), "leeg": None, "json": json})
    assert res["omhuld"] == 0


def test_installeren_twee_keer_omhult_maar_een_keer():
    bus, inst, _ = maak()
    res2 = installeer_auto(bus, {"voorbeeld": inst})
    assert res2["omhuld"] == 0
    bus.tracer.zet(True)
    inst.werk(1)
    assert len([r for r in bus.tracer.log if r["soort"] == "trace"]) == 1


def test_een_nieuwe_module_doet_vanzelf_mee():
    class Nieuw:
        def doe_iets(self):
            return "ok"

    bus = EventBus()
    n = Nieuw()
    installeer_auto(bus, {"nieuwe_module": n})
    bus.tracer.zet(True)
    assert n.doe_iets() == "ok"
    (r,) = [r for r in bus.tracer.log if r["soort"] == "trace"]
    assert r["handler"] == "nieuwe_module.doe_iets"
    assert r["module"] == "nieuwe_module"


def test_object_met_slots_wordt_overgeslagen_zonder_crash():
    class Slots:
        __slots__ = ()

        def werk(self):
            return 1

    res = installeer_auto(EventBus(), {"s": Slots()})
    assert res["omhuld"] == 0
    assert "kon niet omhullen" in res["overgeslagen"][0][1]


def test_bus_zonder_tracer_crasht_niet():
    class Oud:
        pass

    res = installeer_auto(Oud(), {"v": Voorbeeld()})
    assert res["omhuld"] == 0 and res["overgeslagen"]


def test_geen_modules():
    assert installeer_auto(EventBus(), None)["omhuld"] == 0


# ---------- gedrag van de omhulling ----------

def test_tracer_uit_geeft_geen_records_en_zelfde_uitkomst():
    bus, inst, _ = maak()
    assert inst.werk(2, y=5) == 7
    assert inst.aantal == 1
    assert len(bus.tracer.log) == 0


def test_tracer_aan_zelfde_uitkomst_en_een_record():
    bus, inst, _ = maak()
    bus.tracer.zet(True)
    assert inst.werk(2, y=5) == 7
    (r,) = [r for r in bus.tracer.log if r["soort"] == "trace"]
    assert r["handler"] == "voorbeeld.werk"
    assert r["duur_ms"] >= 0 and r["eigen_ms"] >= 0
    assert r["treffer"] is None                 # geen detect_*


def test_fout_gaat_ongewijzigd_door_en_stapel_blijft_in_balans():
    from core import trace_router
    bus, inst, _ = maak()
    bus.tracer.zet(True)
    with pytest.raises(ValueError):
        inst.kapot()
    assert trace_router._lokaal.stapel == []
    assert [r["handler"] for r in bus.tracer.log if r["soort"] == "trace"] == ["voorbeeld.kapot"]


def test_signatuur_blijft_leesbaar_voor_de_bus():
    import inspect
    bus, inst, _ = maak()
    assert list(inspect.signature(inst.werk).parameters) == ["x", "y"]


# ---------- treffer ----------

def test_detect_functie_krijgt_treffer_true_of_false():
    class R:
        def detect_a(self, t):
            return t == "a"

        def detect_b(self, t):
            return None

    bus = EventBus()
    r = R()
    installeer_auto(bus, {"r": r})
    bus.tracer.zet(True)
    r.detect_a("a")
    r.detect_a("x")
    r.detect_b("a")
    assert [x["treffer"] for x in bus.tracer.log if x["soort"] == "trace"] == [True, False, False]


def test_treffer_bij_vreemd_resultaat_crasht_niet():
    class Raar:
        def __bool__(self):
            raise RuntimeError("nee")

    class R:
        def detect_x(self):
            return Raar()

    bus = EventBus()
    r = R()
    installeer_auto(bus, {"r": r})
    bus.tracer.zet(True)
    assert isinstance(r.detect_x(), Raar)
    (rec,) = [x for x in bus.tracer.log if x["soort"] == "trace"]
    assert rec["treffer"] is None


# ---------- eigen tijd ----------

def test_eigen_tijd_is_duur_min_omhulde_kinderen():
    tijd = [100.0]

    class Kind:
        def werk(self):
            tijd[0] += 0.010

    class Ouder:
        def __init__(self, kind):
            self.kind = kind

        def werk(self):
            tijd[0] += 0.005
            self.kind.werk()
            tijd[0] += 0.002

    bus = EventBus()
    bus.tracer = Tracer(klok=lambda: tijd[0])
    kind = Kind()
    ouder = Ouder(kind)
    installeer_auto(bus, {"kind": kind, "ouder": ouder})
    bus.tracer.zet(True)
    ouder.werk()
    recs = {r["handler"]: r for r in bus.tracer.log if r["soort"] == "trace"}
    assert recs["kind.werk"]["duur_ms"] == pytest.approx(10.0)
    assert recs["kind.werk"]["eigen_ms"] == pytest.approx(10.0)
    assert recs["ouder.werk"]["duur_ms"] == pytest.approx(17.0)
    assert recs["ouder.werk"]["eigen_ms"] == pytest.approx(7.0)


# ---------- de router ----------

def test_router_privestappen_en_tabellen_worden_opnieuw_opgebouwd():
    class FakeRouter:
        def __init__(self):
            self._intent_tabel_deel1 = self._build_intent_tabel_deel1()

        def _build_intent_tabel_deel1(self):
            return [("math", self.detect_math)]

        def detect_math(self, t):
            return "+" in t

        def _route_tabel_deel1(self, t):
            return any(f(t) for _, f in self._intent_tabel_deel1)

    bus = EventBus()
    r = FakeRouter()
    installeer_auto(bus, {"intent_router": r})
    assert getattr(r._intent_tabel_deel1[0][1], "_getraceerd", False)
    bus.tracer.zet(True)
    assert r._route_tabel_deel1("5+5") is True
    namen = [x["handler"] for x in bus.tracer.log if x["soort"] == "trace"]
    assert "intent_router.detect_math" in namen
    assert "intent_router._route_tabel_deel1" in namen


def test_prive_functies_van_andere_modules_blijven_onaangeroerd():
    class Andere:
        def detect_x(self):
            return True

        def _route_x(self):
            return True

    a = Andere()
    installeer_auto(EventBus(), {"andere": a})
    assert getattr(a.detect_x, "_getraceerd", False)
    assert not getattr(a._route_x, "_getraceerd", False)   # alleen bij de router


def test_echte_router_met_tracer_aan_toont_de_winnende_detector():
    from core.intent_router import IntentRouter
    bus = EventBus()
    router = IntentRouter(bus)
    res = installeer_auto(bus, {"intent_router": router})
    assert res["per_module"]["intent_router"] > 30
    bus.tracer.zet(True)
    router.route({"text": "hoeveel is 5+5"})
    winnaars = [x["handler"] for x in bus.tracer.log if x.get("treffer") is True]
    assert "intent_router.detect_math" in winnaars
    # de zoekende detectoren die eerder afvielen, staan er ook in
    assert any(x.get("treffer") is False for x in bus.tracer.log)


def test_main_installeert_de_automatische_tracing():
    bron = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "installeer_trace_auto(bus, loader.loaded_modules)" in bron
    # NA de lijst uit trace_punten, zodat die omhullingen blijven
    assert bron.index("installeer_trace_punten(bus,") < bron.index("installeer_trace_auto(bus,")


# ---------- "trace laatste": zoekende detectoren verbergen ----------

def test_trace_laatste_verbergt_niet_aanslaande_detectoren_tenzij_alles():
    from modules.debug.trace_overzicht import laatste_tekst

    class R:
        def detect_a(self, t):
            return t == "a"

    bus = EventBus()
    r = R()
    installeer_auto(bus, {"r": r})
    bus.tracer.zet(True)
    r.detect_a("a")
    r.detect_a("x")
    kort = laatste_tekst(bus.tracer, 10)
    lang = laatste_tekst(bus.tracer, 10, alles=True)
    assert kort.count("r.detect_a") == 1 and "✓" in kort
    assert lang.count("r.detect_a") == 2


def test_trace_laatste_verbergt_wildcard_ruis_tenzij_alles():
    from modules.debug.trace_overzicht import laatste_tekst
    bus = EventBus()
    bus.tracer.zet(True)

    class Alles:
        def luister(self, data=None):
            pass

    class Gericht:
        def luister(self, data=None):
            pass

    a, g = Alles(), Gericht()
    for ev in ("e1", "e2", "e3", "e4", "e5"):
        bus.subscribe(ev, a.luister)
    bus.subscribe("e1", g.luister)
    for ev in ("e1", "e2", "e3", "e4", "e5"):
        bus.publish(ev, {})
    kort = laatste_tekst(bus.tracer, 50)
    lang = laatste_tekst(bus.tracer, 50, alles=True)
    assert "Alles.luister" not in kort and "Gericht.luister" in kort
    assert "Alles.luister" in lang


# ---------- keten_log en "trace antwoord" ----------

def test_antwoord_records_worden_niet_door_achtergrondwerk_weggeduwd():
    t = Tracer(max_records=5)
    t.zet(True)
    with t.keten("chat_message", {}):
        t.trace("a.vraag")
    for _ in range(50):
        t.trace("x.achtergrond")
    assert not any(r.get("handler") == "a.vraag" for r in t.log)          # uit de gewone log gerold
    assert any(r.get("handler") == "a.vraag" for r in t.alle_records())   # maar nog wel bewaard
    t.leeg()
    assert t.alle_records() == []


def test_trace_antwoord_toont_de_laatste_echte_vraag_op_volgorde():
    from modules.debug.trace_overzicht import antwoord_tekst

    class R:
        def detect_a(self, t):
            return False

        def detect_b(self, t):
            return True

    bus = EventBus()
    r = R()
    installeer_auto(bus, {"intent_router": r})
    bus.tracer.zet(True)
    with bus.tracer.keten("chat_message", {}):          # echte vraag: b slaat aan
        r.detect_a("x")
        r.detect_b("x")
    with bus.tracer.keten("chat_message", {}):          # debug-commando erna: geen treffer
        bus.tracer.trace("debug_commands.is_debug_command")
    tekst = antwoord_tekst(bus.tracer)
    assert "Antwoord #1" in tekst
    assert "detect_b" in tekst and "detect_a" not in tekst and "is_debug_command" not in tekst
    assert "Antwoord #2" in antwoord_tekst(bus.tracer, 2)
    assert "niet (meer)" in antwoord_tekst(bus.tracer, 99)


def test_trace_antwoord_zonder_records():
    from modules.debug.trace_overzicht import antwoord_tekst
    assert "Nog geen antwoord" in antwoord_tekst(Tracer())