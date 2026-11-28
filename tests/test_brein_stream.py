# tests/test_brein_stream.py
#
# Test modules/network/brein_stream.py en de pagina (punt 79): het kanaal naar de browser.
# De servertests starten echt een webservertje op een vrije poort (poort 0) op 127.0.0.1.
#
# Uitvoeren: pytest tests/test_brein_stream.py -v

import http.client
import json
import socket
import time
from pathlib import Path

import pytest

import core.event_bus as eb
from core.event_bus import EventBus
from modules.network import brein_stream as bs
from modules.network.brein_stream import (
    BreinStream, bouw_topologie, groep_van, maak_record_voor_pagina, token_klopt, wildcard_namen,
)

TOKEN = "testtoken-123"
ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def rustig(tmp_path, monkeypatch):
    monkeypatch.setattr(eb, "_LOGBESTAND", tmp_path / "logs" / "handler_fouten.log")
    monkeypatch.setattr(bs, "load_dotenv", None)            # lees nooit de echte .env
    monkeypatch.setattr(bs, "BATCH_SECONDEN", 0.02)


class Dummy:
    def werk(self, data=None):
        pass


def maak_server(bus=None, token=TOKEN):
    bus = bus or EventBus()
    stream = BreinStream(bus, poort=0, token=token, host="127.0.0.1")
    return bus, stream


def get(stream, pad, timeout=3):
    c = http.client.HTTPConnection("127.0.0.1", stream.poort, timeout=timeout)
    c.request("GET", pad)
    r = c.getresponse()
    body = r.read()
    c.close()
    return r.status, r.getheader("Content-Type"), body


def open_stream(stream, token=TOKEN, timeout=3):
    c = http.client.HTTPConnection("127.0.0.1", stream.poort, timeout=timeout)
    c.request("GET", f"/stream?token={token}")
    return c, c.getresponse()


def sluit(c, resp):
    """Sluit de verbinding echt (de response houdt de socket anders open, zoals een browser dat niet doet)."""
    resp.close()
    c.close()


def lees_event(resp):
    """Leest een SSE-event: (naam, data-dict/list). Slaat hartslagen en lege regels over."""
    naam, data = None, None
    while True:
        regel = resp.fp.readline().decode("utf-8")
        if not regel:
            return None, None
        regel = regel.rstrip("\n")
        if regel.startswith("event: "):
            naam = regel[7:]
        elif regel.startswith("data: "):
            data = json.loads(regel[6:])
        elif regel == "" and naam is not None and data is not None:
            return naam, data


def wacht_tot(voorwaarde, seconden=3.0):
    eind = time.time() + seconden
    while time.time() < eind:
        if voorwaarde():
            return True
        time.sleep(0.02)
    return False


# ---------- hulpfuncties ----------

def test_token_klopt():
    assert token_klopt("abc", "abc")
    assert not token_klopt("abd", "abc")
    assert not token_klopt("", "abc")
    assert not token_klopt("abc", None)
    assert not token_klopt(None, None)


def test_haal_token_uit_omgeving(monkeypatch):
    monkeypatch.setenv(bs.TOKEN_NAAM, "  geheim  ")
    assert bs.haal_token() == "geheim"
    monkeypatch.setenv(bs.TOKEN_NAAM, "   ")
    assert bs.haal_token() is None
    monkeypatch.delenv(bs.TOKEN_NAAM)
    assert bs.haal_token() is None


def test_record_voor_pagina_neemt_alleen_toegestane_velden_over():
    record = {"soort": "handler", "module": "chat", "pad": "modules.chat.chat", "handler": "ChatModule.on_x",
              "event": "chat_message", "duur_ms": 3.0, "eigen_ms": 1.0, "keten": 4, "treffer": None,
              "t": 1.0, "start_t": 0.9, "tekst": "GEHEIM wat Kevin typte", "data": {"text": "GEHEIM"}}
    uit = maak_record_voor_pagina(record, wildcards={"Andere.x"})
    assert set(uit) <= set(bs.PAGINA_VELDEN)
    assert "GEHEIM" not in json.dumps(uit)
    assert uit["m"] == "chat" and uit["f"] == "ChatModule.on_x" and uit["k"] == 4 and uit["w"] is False


def test_record_voor_pagina_wildcard_trace_keten_en_main():
    w = maak_record_voor_pagina({"soort": "handler", "module": "memory", "handler": "MemoryModule.on_event",
                                 "event": "e"}, wildcards={"MemoryModule.on_event"})
    assert w["w"] is True
    t = maak_record_voor_pagina({"soort": "trace", "module": "intent_router", "handler": "intent_router.detect_math",
                                 "treffer": True, "keten": 1})
    assert t["s"] == "t" and t["tr"] is True and t["w"] is False
    assert maak_record_voor_pagina({"soort": "keten_start", "keten": 2}) == {"s": "k0", "k": 2}
    assert maak_record_voor_pagina({"soort": "keten_eind", "keten": 2}) == {"s": "k1", "k": 2}
    assert maak_record_voor_pagina({"soort": "onbekend"}) is None
    m = maak_record_voor_pagina({"soort": "handler", "module": "__main__", "handler": "on_chat_response"})
    assert m["m"] == "main"


def test_groep_van():
    class A:
        pass

    A.__module__ = "modules.network.client_bridge"
    assert groep_van(A()) == "network"
    A.__module__ = "core.memory"
    assert groep_van(A()) == "core"
    A.__module__ = "iets.anders"
    assert groep_van(A()) == "overig"


def test_topologie_en_wildcards():
    bus = EventBus()

    class Mod:
        def op_a(self, data=None):
            pass

        def op_alles(self, data=None):
            pass

    Mod.__module__ = "modules.chat.chat"
    m = Mod()
    bus.register_module("chat", m)
    bus.subscribe("a", m.op_a)
    bus.subscribe("b", m.op_a)
    bus.subscribe("*", m.op_alles)
    t = bouw_topologie(bus)
    (mod,) = t["modules"]
    assert mod["n"] == "chat" and mod["a"] == "chat" and mod["g"] == "chat"
    assert mod["l"] == ["*", "a", "b"]
    assert any("op_alles" in w for w in t["wildcard"])
    assert wildcard_namen(bus) == set(t["wildcard"])


def test_topologie_koppelt_een_gewone_functie_via_bestandsnaam():
    bus = EventBus()

    def gewone_handler(data=None):
        pass

    gewone_handler.__module__ = "core.logger"

    class Log:
        pass

    Log.__module__ = "core.logger"
    bus.register_module("logger", Log())
    bus.subscribe("x", gewone_handler)
    (mod,) = bouw_topologie(bus)["modules"]
    assert mod["l"] == ["x"]


# ---------- starten ----------

def test_zonder_token_start_de_server_niet(capsys):
    bus, stream = maak_server(token=None)
    assert stream._server is None
    assert "UIT" in capsys.readouterr().out
    assert "geen token" in stream.status_tekst()
    assert stream.link_tekst() == stream.status_tekst()


def test_bus_zonder_tracer_start_niet():
    class OudeBus:
        modules = {}
        _subscribers = {}

    stream = BreinStream(OudeBus(), poort=0, token=TOKEN, host="127.0.0.1")
    assert stream._server is None


def test_poort_bezet_is_geen_crash(capsys):
    bezet = socket.socket()
    bezet.bind(("127.0.0.1", 0))
    bezet.listen(1)
    try:
        stream = BreinStream(EventBus(), poort=bezet.getsockname()[1], token=TOKEN, host="127.0.0.1")
        assert stream._server is None
        assert "UIT" in capsys.readouterr().out
    finally:
        bezet.close()


def test_init_module_geeft_een_breinstream(monkeypatch):
    monkeypatch.delenv(bs.TOKEN_NAAM, raising=False)
    assert isinstance(bs.init_module(EventBus()), BreinStream)


def test_link_en_status_tekst_bevatten_het_token_alleen_in_de_link(monkeypatch):
    monkeypatch.setenv(bs.HOST_NAAM, "100.1.2.3")
    bus, stream = maak_server()
    try:
        assert TOKEN not in stream.status_tekst()
        link = stream.link_tekst()
        assert f"http://100.1.2.3:{stream.poort}/?token={TOKEN}" in link
        assert "internet" in link
    finally:
        stream.shutdown()


# ---------- de server ----------

def test_pagina_is_bereikbaar_zonder_token_en_bevat_geen_data():
    bus, stream = maak_server()
    try:
        status, soort, body = get(stream, "/")
        assert status == 200 and "text/html" in soort
        assert b"<canvas" in body and b"EventSource" in body
    finally:
        stream.shutdown()


def test_topologie_en_stream_vragen_een_token():
    bus, stream = maak_server()
    try:
        assert get(stream, "/topologie")[0] == 403
        assert get(stream, "/topologie?token=fout")[0] == 403
        assert get(stream, "/stream?token=fout")[0] == 403
        status, soort, body = get(stream, f"/topologie?token={TOKEN}")
        assert status == 200 and "json" in soort
        assert "modules" in json.loads(body)
        assert get(stream, "/bestaat-niet")[0] == 404
        assert get(stream, "/../etc/passwd")[0] == 404
    finally:
        stream.shutdown()


def test_stream_stuurt_eerst_de_topologie_dan_batches():
    bus = EventBus()
    d = Dummy()
    bus.register_module("dummy", d)
    bus.subscribe("evt", d.werk)
    bus, stream = maak_server(bus)
    try:
        c, resp = open_stream(stream)
        assert resp.status == 200 and "event-stream" in resp.getheader("Content-Type")
        naam, data = lees_event(resp)
        assert naam == "topologie"
        assert [m["n"] for m in data["modules"]] == ["dummy"]
        assert wacht_tot(lambda: bus.tracer.aan)
        bus.trace("dummy.doe_iets")
        naam, data = lees_event(resp)
        assert naam == "batch"
        assert any(r["f"] == "dummy.doe_iets" and r["m"] == "dummy" for r in data)
        sluit(c, resp)
    finally:
        stream.shutdown()


def test_stream_bevat_nooit_de_tekst_van_kevin():
    bus, stream = maak_server()
    try:
        c, resp = open_stream(stream)
        lees_event(resp)
        d = Dummy()
        bus.subscribe("chat_message", d.werk)
        wacht_tot(lambda: bus.tracer.aan)
        bus.publish("chat_message", {"text": "SUPERGEHEIME TEKST"})
        naam, data = lees_event(resp)
        assert naam == "batch"
        assert "SUPERGEHEIME" not in json.dumps(data)
        assert any(r["s"] == "k0" for r in data) or any(r["k"] == 1 for r in data if "k" in r)
        sluit(c, resp)
    finally:
        stream.shutdown()


def test_tracer_gaat_aan_bij_de_eerste_kijker_en_uit_bij_de_laatste():
    bus, stream = maak_server()
    try:
        assert not bus.tracer.aan
        c1, r1 = open_stream(stream)
        lees_event(r1)
        assert bus.tracer.aan
        c2, r2 = open_stream(stream)
        lees_event(r2)
        assert len(stream._kijkers) == 2
        sluit(c1, r1)
        assert wacht_tot(lambda: len(stream._kijkers) == 1)
        assert bus.tracer.aan                              # er kijkt nog iemand
        sluit(c2, r2)
        assert wacht_tot(lambda: len(stream._kijkers) == 0)
        assert wacht_tot(lambda: not bus.tracer.aan)
    finally:
        stream.shutdown()


def test_tracer_blijft_aan_als_jij_hem_zelf_aanzette():
    bus, stream = maak_server()
    bus.tracer.zet(True)
    try:
        c, r = open_stream(stream)
        lees_event(r)
        sluit(c, r)
        assert wacht_tot(lambda: len(stream._kijkers) == 0)
        assert bus.tracer.aan
    finally:
        stream.shutdown()


def test_maximum_aantal_kijkers(monkeypatch):
    monkeypatch.setattr(bs, "MAX_CLIENTS", 1)
    bus, stream = maak_server()
    try:
        c1, r1 = open_stream(stream)
        lees_event(r1)
        status, _, _ = get(stream, f"/stream?token={TOKEN}")
        assert status == 503
        sluit(c1, r1)
    finally:
        stream.shutdown()


def test_achtergrond_getter_wordt_afgeremd_maar_een_antwoord_nooit():
    bus = EventBus()
    stream = BreinStream(bus, poort=0, token=TOKEN, start=False)
    kijker = bs._Kijker()
    stream._kijkers.append(kijker)
    for _ in range(50):
        stream._op_record({"soort": "trace", "module": "a", "handler": "a.getter", "keten": None})
    assert len(kijker.haal(0.01)) == 1
    for _ in range(5):
        stream._op_record({"soort": "trace", "module": "a", "handler": "a.getter", "keten": 3})
    assert len(kijker.haal(0.01)) == 5


def test_kijker_met_volle_wachtrij_laat_oudste_vallen(monkeypatch):
    k = bs._Kijker()
    for i in range(bs.WACHTRIJ_MAX + 50):
        k.zet({"i": i})
    items = k.haal(0.01)
    assert len(items) == bs.WACHTRIJ_MAX and items[-1]["i"] == bs.WACHTRIJ_MAX + 49


def test_shutdown_geeft_de_poort_vrij_en_zet_de_tracer_terug():
    bus, stream = maak_server()
    poort = stream.poort
    c, r = open_stream(stream)
    lees_event(r)
    stream.shutdown()
    assert not bus.tracer.aan
    s = socket.socket()
    s.settimeout(1)
    assert s.connect_ex(("127.0.0.1", poort)) != 0
    s.close()
    stream.shutdown()                                      # tweede keer mag niet crashen


# ---------- de pagina ----------

def test_pagina_gebruikt_geen_externe_bronnen_en_geen_innerhtml():
    html = (ROOT / "modules" / "network" / "brein_pagina.html").read_text(encoding="utf-8")
    assert "http://" not in html and "https://" not in html      # werkt offline en lekt niets
    assert "innerHTML" not in html                               # namen uit de stream: alleen textContent
    assert "eval(" not in html
    assert "/stream?token=" in html


def test_module_wordt_niet_door_de_trace_router_omhuld():
    from core.trace_router import UITGESLOTEN_MODULES
    assert "brein_stream" in UITGESLOTEN_MODULES


# ---------- debug-commando's ----------

def test_brein_commandos(capsys, monkeypatch):
    from modules.debug.debug_commands import DebugCommands
    monkeypatch.setenv(bs.HOST_NAAM, "100.9.9.9")
    bus, stream = maak_server()

    class Loader:
        loaded_modules = {"brein_stream": stream}

    try:
        dc = DebugCommands(bus, Loader())
        assert dc.is_debug_command("brein status") and dc.is_debug_command("Brein Link")
        assert not dc.is_debug_command("brein")
        dc.handle_debug_command({"text": "brein status"})
        uit = capsys.readouterr().out
        assert "AAN" in uit and TOKEN not in uit
        dc.handle_debug_command({"text": "brein link"})
        assert f"http://100.9.9.9:{stream.poort}/?token={TOKEN}" in capsys.readouterr().out
    finally:
        stream.shutdown()


def test_brein_commando_zonder_module(capsys):
    from modules.debug.debug_commands import DebugCommands

    class Loader:
        loaded_modules = {}

    DebugCommands(EventBus(), Loader()).handle_debug_command({"text": "brein status"})
    assert "niet gevonden" in capsys.readouterr().out