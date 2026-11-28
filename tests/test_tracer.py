# tests/test_tracer.py
#
# Test de tracer van de live brein-weergave (punt 79, stap 1): core/tracer.py,
# de koppeling in core/event_bus.py, en de debug-commando's "trace ..." en
# "handlers dekking".
#
# Uitvoeren: pytest tests/test_tracer.py -v

import threading

import pytest

import core.event_bus as eb
from core.event_bus import EventBus
from core.tracer import Tracer
from modules.debug import trace_overzicht
from modules.debug.debug_commands import DebugCommands


@pytest.fixture(autouse=True)
def log_in_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(eb, "_LOGBESTAND", tmp_path / "logs" / "handler_fouten.log")


class Module:
    def __init__(self, bus=None):
        self.bus = bus
        self.aangeroepen = []

    def op_x(self, data):
        self.aangeroepen.append(data)

    def op_chat(self, data):
        # een handler die zelf een ander event publiceert (zoals Nova doet)
        self.bus.publish("antwoord", {"ok": 1})

    def kapot(self, data):
        raise ValueError("boem")


def records(bus, soort="handler"):
    return [r for r in bus.tracer.log if r["soort"] == soort]


# ---------- standaard uit ----------

def test_standaard_uit_en_geen_records():
    bus = EventBus()
    m = Module()
    bus.subscribe("x", m.op_x)
    bus.publish("x", {"a": 1})
    assert m.aangeroepen == [{"a": 1}]          # de handler draait gewoon
    assert bus.tracer.aan is False
    assert len(bus.tracer.log) == 0
    assert bus.tracer.totaal == 0


# ---------- aan ----------

def test_handler_wordt_vastgelegd_met_naam_module_en_duur():
    bus = EventBus()
    m = Module()
    bus.subscribe("x", m.op_x)
    bus.tracer.zet(True)
    bus.publish("x", {"a": 1})
    (r,) = records(bus)
    assert r["handler"] == "Module.op_x"
    assert r["module"] == "test_tracer"
    assert r["event"] == "x"
    assert r["duur_ms"] >= 0
    assert r["keten"] is None                    # geen antwoord op Kevin: achtergrond
    assert bus.tracer.totaal == 1


def test_wildcard_handler_wordt_ook_vastgelegd():
    bus = EventBus()
    gezien = []
    bus.subscribe("*", lambda data, event: gezien.append(event))
    bus.tracer.zet(True)
    bus.publish("iets", {})
    assert gezien == ["iets"]
    assert records(bus)[0]["event"] == "iets"


def test_handler_met_fout_wordt_toch_vastgelegd_en_stopt_de_rest_niet():
    bus = EventBus()
    m = Module()
    bus.subscribe("x", m.kapot)
    bus.subscribe("x", m.op_x)
    bus.tracer.zet(True)
    bus.publish("x", {"a": 1})
    assert m.aangeroepen == [{"a": 1}]
    assert [r["handler"] for r in records(bus)] == ["Module.kapot", "Module.op_x"]
    assert bus.fout_teller == 1


def test_gedrag_van_handlers_is_identiek_met_en_zonder_tracer():
    for aan in (False, True):
        bus = EventBus()
        een, twee = [], []
        bus.subscribe("x", lambda data: een.append(data))
        bus.subscribe("x", lambda data, event: twee.append((data, event)))
        bus.tracer.zet(aan)
        bus.publish("x", 5)
        assert een == [5] and twee == [(5, "x")]


# ---------- keten ----------

def test_chat_message_start_een_keten_en_alles_erbinnen_krijgt_het_nummer():
    bus = EventBus()
    m = Module(bus)
    bus.subscribe("chat_message", m.op_chat)
    bus.subscribe("antwoord", m.op_x)
    bus.tracer.zet(True)
    bus.publish("chat_message", {"sender": "Kevin", "text": "geheim"})
    handlers = records(bus)
    assert [r["handler"] for r in handlers] == ["Module.op_x", "Module.op_chat"]
    assert {r["keten"] for r in handlers} == {1}
    assert [r["soort"] for r in bus.tracer.log if r["soort"].startswith("keten")] == [
        "keten_start", "keten_eind"]
    assert bus.tracer.keten_id() is None          # na afloop weer achtergrond


def test_volgend_bericht_krijgt_een_nieuw_nummer():
    bus = EventBus()
    m = Module()
    bus.subscribe("chat_message", m.op_x)
    bus.tracer.zet(True)
    bus.publish("chat_message", {})
    bus.publish("chat_message", {})
    assert [r["keten"] for r in records(bus)] == [1, 2]


def test_ander_event_start_geen_keten():
    bus = EventBus()
    m = Module()
    bus.subscribe("weer", m.op_x)
    bus.tracer.zet(True)
    bus.publish("weer", {})
    assert records(bus)[0]["keten"] is None
    assert not [r for r in bus.tracer.log if r["soort"] == "keten_start"]


def test_keten_na_een_fout_in_een_handler_wordt_toch_gesloten():
    bus = EventBus()
    m = Module()
    bus.subscribe("chat_message", m.kapot)
    bus.tracer.zet(True)
    bus.publish("chat_message", {})
    assert bus.tracer.keten_id() is None


def test_keten_hoort_bij_een_thread():
    bus = EventBus()
    resultaat = []
    t = Tracer()
    t.zet(True)
    with t.keten("chat_message"):
        draad = threading.Thread(target=lambda: resultaat.append(t.keten_id()))
        draad.start()
        draad.join()
        assert t.keten_id() == 1
    assert resultaat == [None]                    # een nieuwe thread valt buiten de keten


def test_keten_bewaart_nooit_de_tekst_van_kevin():
    bus = EventBus()
    m = Module()
    bus.subscribe("chat_message", m.op_x)
    bus.tracer.zet(True)
    bus.publish("chat_message", {"sender": "Kevin", "text": "mijn geheime zin"})
    assert "geheime" not in repr(list(bus.tracer.log))


# ---------- trace() voor code buiten de bus ----------

def test_trace_vanuit_een_lus():
    bus = EventBus()
    bus.tracer.zet(True)
    bus.trace("session_watcher.check_pauze")
    (r,) = records(bus, "trace")
    assert r["module"] == "session_watcher"
    assert r["handler"] == "session_watcher.check_pauze"
    assert r["keten"] is None
    assert bus.tracer.per_module["session_watcher"] == 1


def test_trace_doet_niets_als_de_tracer_uit_staat():
    bus = EventBus()
    bus.trace("x.y")
    assert len(bus.tracer.log) == 0


# ---------- luisteraars ----------

def test_luisteraar_krijgt_de_records():
    bus = EventBus()
    m = Module()
    bus.subscribe("x", m.op_x)
    ontvangen = []
    bus.tracer.voeg_toe(ontvangen.append)
    bus.tracer.zet(True)
    bus.publish("x", {})
    assert [r["soort"] for r in ontvangen] == ["handler"]


def test_kapotte_luisteraar_stopt_niets():
    bus = EventBus()
    m = Module()
    bus.subscribe("x", m.op_x)

    def stuk(record):
        raise RuntimeError("pagina weg")

    bus.tracer.voeg_toe(stuk)
    bus.tracer.zet(True)
    bus.publish("x", {"a": 1})
    assert m.aangeroepen == [{"a": 1}]
    assert len(records(bus)) == 1


def test_luisteraar_verwijderen():
    t = Tracer()
    ontvangen = []
    t.voeg_toe(ontvangen.append)
    t.verwijder(ontvangen.append)
    t.zet(True)
    t.trace("a.b")
    assert ontvangen == []                        # na verwijderen krijgt hij niets meer


def test_ring_buffer_houdt_maximaal_het_ingestelde_aantal():
    t = Tracer(max_records=5)
    t.zet(True)
    for i in range(20):
        t.trace(f"m.f{i}")
    assert len(t.log) == 5
    assert t.totaal == 20


def test_leeg_maakt_alles_leeg():
    t = Tracer()
    t.zet(True)
    t.trace("m.f")
    t.leeg()
    assert len(t.log) == 0 and t.totaal == 0 and t.gezien() == set()


# ---------- dekking ----------

class Geladen:
    pass


def test_dekking_gezien_en_ongezien():
    t = Tracer()
    t.zet(True)
    t.trace("weer.check")
    gezien, ongezien = t.dekking({"weer": object(), "rain": object()})
    assert gezien == ["weer"]
    assert ongezien == ["rain"]


def test_dekking_herkent_module_via_het_bestand_van_haar_klasse():
    t = Tracer()
    t.zet(True)
    m = Module()
    bus = EventBus()
    bus.tracer = t
    bus.subscribe("x", m.op_x)
    bus.publish("x", {})
    # klasse Module staat in test_tracer, dus een module met een andere naam telt toch mee
    gezien, ongezien = t.dekking({"mijn_module": m})
    assert gezien == ["mijn_module"]


def test_dekking_zonder_modules():
    assert Tracer().dekking(None) == ([], [])


# ---------- tekst en commando's ----------

def test_status_tekst_uit_en_aan():
    t = Tracer()
    assert "uit" in trace_overzicht.status_tekst(t)
    assert "trace aan" in trace_overzicht.status_tekst(t)
    t.zet(True)
    t.trace("m.f")
    tekst = trace_overzicht.status_tekst(t)
    assert "AAN" in tekst and "m" in tekst


def test_laatste_tekst():
    t = Tracer()
    assert "Nog geen records" in trace_overzicht.laatste_tekst(t)
    t.zet(True)
    t.trace("weer.check")
    assert "weer.check" in trace_overzicht.laatste_tekst(t)


def test_dekking_tekst_legt_uit_als_hij_uit_staat():
    tekst = trace_overzicht.dekking_tekst(Tracer(), {"a": object()})
    assert "trace aan" in tekst


def test_dekking_tekst_toont_ongeziene_modules():
    t = Tracer()
    t.zet(True)
    t.trace("a.f")
    tekst = trace_overzicht.dekking_tekst(t, {"a": object(), "b": object()})
    assert "Nog NIET gezien: 1" in tekst and "  b" in tekst


class StubLoader:
    loaded_modules = {"a": object()}


def maak_commando(bus):
    return DebugCommands(bus, StubLoader())


def test_commando_herkenning():
    dc = maak_commando(EventBus())
    for tekst in ("trace aan", "Trace Uit", "trace status", "trace leeg",
                  "trace laatste", "trace laatste 5", "handlers dekking"):
        assert dc.is_debug_command(tekst), tekst
    assert not dc.is_debug_command("trace")
    assert not dc.is_debug_command("tracering")


def test_commando_aan_en_uit(capsys):
    bus = EventBus()
    dc = maak_commando(bus)
    dc.handle_debug_command({"text": "trace aan"})
    assert bus.tracer.aan is True
    assert "AAN" in capsys.readouterr().out
    dc.handle_debug_command({"text": "trace uit"})
    assert bus.tracer.aan is False
    assert "uit" in capsys.readouterr().out


def test_commando_status_laatste_leeg_en_dekking(capsys):
    bus = EventBus()
    dc = maak_commando(bus)
    dc.handle_debug_command({"text": "trace aan"})
    bus.trace("a.check")
    dc.handle_debug_command({"text": "trace status"})
    dc.handle_debug_command({"text": "trace laatste 3"})
    dc.handle_debug_command({"text": "handlers dekking"})
    uit = capsys.readouterr().out
    assert "Tracer: AAN" in uit
    assert "a.check" in uit
    assert "Gezien door de tracer: 1" in uit
    dc.handle_debug_command({"text": "trace leeg"})
    assert bus.tracer.totaal == 0


def test_commando_bij_bus_zonder_tracer_crasht_niet(capsys):
    class OudeBus:
        def subscribe(self, *a, **k):
            pass

    dc = maak_commando(OudeBus())
    dc.handle_debug_command({"text": "trace aan"})
    dc.handle_debug_command({"text": "handlers dekking"})
    assert capsys.readouterr().out.count("geen tracer") == 2