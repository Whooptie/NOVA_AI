# tests/test_event_bus_bug46.py
#
# Bug #46 (25 oktober 2026): een handler mag nooit twee keer draaien door een
# TypeError, en een fout in een handler wordt gelogd zonder andere handlers te
# stoppen.
#
# Uitvoeren: pytest tests/test_event_bus_bug46.py -v

import functools

import pytest

import core.event_bus as eb
from core.event_bus import EventBus


@pytest.fixture(autouse=True)
def log_in_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(eb, "_LOGBESTAND", tmp_path / "logs" / "handler_fouten.log")
    return tmp_path / "logs" / "handler_fouten.log"


def test_handler_met_twee_argumenten():
    bus, ontvangen = EventBus(), []
    bus.subscribe("x", lambda data, naam: ontvangen.append((data, naam)))
    bus.publish("x", {"a": 1})
    assert ontvangen == [({"a": 1}, "x")]


def test_handler_met_een_argument():
    bus, ontvangen = EventBus(), []
    bus.subscribe("x", lambda data: ontvangen.append(data))
    bus.publish("x", {"a": 1})
    assert ontvangen == [{"a": 1}]


def test_gebonden_methodes_een_en_twee_argumenten():
    class M:
        def __init__(self):
            self.een, self.twee = [], []
        def on_een(self, data):
            self.een.append(data)
        def on_twee(self, data, naam):
            self.twee.append((data, naam))
    bus, m = EventBus(), M()
    bus.subscribe("x", m.on_een)
    bus.subscribe("x", m.on_twee)
    bus.publish("x", 5)
    assert m.een == [5] and m.twee == [(5, "x")]


def test_args_en_partial_en_standaardwaarde():
    bus, ontvangen = EventBus(), []
    def a(*args): ontvangen.append(("a", args))
    def b(data, naam="?"): ontvangen.append(("b", data, naam))
    def c(prefix, data): ontvangen.append((prefix, data))
    bus.subscribe("x", a)
    bus.subscribe("x", b)
    bus.subscribe("x", functools.partial(c, "p"))
    bus.publish("x", 1)
    assert ("a", (1, "x")) in ontvangen
    assert ("b", 1, "x") in ontvangen
    assert ("p", 1) in ontvangen


def test_BUG46_handler_met_interne_typeerror_draait_maar_een_keer():
    bus, teller = EventBus(), {"n": 0}
    def kapot(data, naam=None):
        teller["n"] += 1
        return "abc" + 5          # echte TypeError IN de handler
    bus.subscribe("x", kapot)
    bus.publish("x", {})
    assert teller["n"] == 1, "handler draaide dubbel"
    assert "abc" in bus.fouten[0]["fout"] or "str" in bus.fouten[0]["fout"]  # de ECHTE fout, niet een argumentfout


def test_fout_in_handler_stopt_andere_handlers_niet():
    bus, ontvangen = EventBus(), []
    bus.subscribe("x", lambda d, n: 1 / 0)
    bus.subscribe("x", lambda d, n: ontvangen.append("tweede"))
    bus.subscribe("*", lambda d, n: ontvangen.append("wildcard"))
    bus.publish("x", {})
    assert ontvangen == ["tweede", "wildcard"]


def test_fout_wordt_gelogd_in_geheugen_en_bestand(log_in_tmp):
    bus = EventBus()
    def stuk(data, naam):
        raise ValueError("oeps")
    bus.subscribe("mijn_event", stuk)
    bus.publish("mijn_event", {})
    assert len(bus.fouten) == 1
    f = bus.fouten[0]
    assert f["event"] == "mijn_event" and "ValueError: oeps" in f["fout"]
    assert "stuk" in f["handler"]
    tekst = log_in_tmp.read_text(encoding="utf-8")
    assert "mijn_event" in tekst and "ValueError: oeps" in tekst and "Traceback" in tekst


def test_traceback_blijft_zichtbaar_in_de_console(capsys):
    bus = EventBus()
    def stuk(data, naam):
        raise ValueError("zichtbare testfout")
    bus.subscribe("x", stuk)
    bus.publish("x", {})
    uitvoer = capsys.readouterr()
    assert "[EVENTBUS] Fout in handler" in uitvoer.out
    assert "zichtbare testfout" in uitvoer.err


def test_fouten_geheugen_is_beperkt_tot_50():
    bus = EventBus()
    bus.subscribe("x", lambda d, n: 1 / 0)
    for _ in range(60):
        bus.publish("x", {})
    assert len(bus.fouten) == 50


def test_wildcard_krijgt_eventnaam():
    bus, ontvangen = EventBus(), []
    bus.subscribe("*", lambda d, n: ontvangen.append(n))
    bus.publish("abc", {})
    assert ontvangen == ["abc"]


def test_zich_afmelden_tijdens_publish_geeft_geen_fout():
    bus, ontvangen = EventBus(), []
    def eenmalig(d, n):
        ontvangen.append("eenmalig")
        bus._subscribers["x"].remove(eenmalig)
    bus.subscribe("x", eenmalig)
    bus.subscribe("x", lambda d, n: ontvangen.append("rest"))
    bus.publish("x", {})
    assert ontvangen == ["eenmalig", "rest"]
    assert not bus.fouten


def test_dubbele_subscribe_blijft_voorkomen():
    bus, ontvangen = EventBus(), []
    def h(d, n): ontvangen.append(1)
    bus.subscribe("x", h)
    bus.subscribe("x", h)
    bus.publish("x", {})
    assert ontvangen == [1]