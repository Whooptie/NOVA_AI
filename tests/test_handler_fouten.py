# tests/test_handler_fouten.py
#
# Nova leest haar eigen foutenlogboek en meldt het (25 oktober 2026,
# vervolg op bug #46): modules/debug/handler_fouten.py, de router-herkenning
# in IntentRouter.detect_handler_fouten() en de teller/rotatie in EventBus.
#
# Uitvoeren: pytest tests/test_handler_fouten.py -v

import pytest

import core.event_bus as eb
from core.event_bus import EventBus
from core.intent_router import IntentRouter
from modules.context import handler_fouten as hf
from modules.context.handler_fouten import (
    HandlerFoutenModule, lees_logbestand, groepeer, maak_overzicht,
    MIN_INTERVAL, HEROPEN_NA,
)

LOG = """\
[2026-10-25 10:33:45] event='chat_message' handler=_NepLoader.discover_and_load.<locals>.crashende_handler
Traceback (most recent call last):
  File "/app/core/event_bus.py", line 73, in _roep_aan
    handler(data)
  File "/app/tests/x.py", line 148, in crashende_handler
    raise ValueError("bewust veroorzaakte testfout")
ValueError: bewust veroorzaakte testfout

[2026-10-25 11:02:10] event='intent_rain' handler=RainModule.on_rain
Traceback (most recent call last):
  File "/app/modules/weather/rain.py", line 1, in on_rain
KeyError: 'text'

[2026-10-25 11:05:00] event='intent_rain' handler=RainModule.on_rain
Traceback (most recent call last):
  File "/app/modules/weather/rain.py", line 1, in on_rain
KeyError: 'text'

"""


@pytest.fixture
def logpad(tmp_path, monkeypatch):
    pad = tmp_path / "logs" / "handler_fouten.log"
    pad.parent.mkdir(parents=True)
    monkeypatch.setattr(eb, "_LOGBESTAND", pad)
    return pad


class Klok:
    def __init__(self, t=1_000_000.0):
        self.t = t
    def __call__(self):
        return self.t


def antwoorden(bus):
    teksten = []
    bus.subscribe("layer4_response", lambda d, n: teksten.append(d["text"]))
    return teksten


# ---------- plek van de module ----------
def test_module_staat_niet_in_de_door_de_lader_overgeslagen_debug_map():
    # module_loader.py slaat modules/debug/ over (if group == "debug": continue).
    # Stond dit bestand daar, dan werd het nooit geladen (live gezien, 25 okt 2026).
    from pathlib import Path
    pad = Path(hf.__file__).resolve()
    assert pad.parent.name != "debug", "module_loader laadt modules/debug/ niet automatisch"
    assert callable(getattr(hf, "init_module", None))


# ---------- logbestand lezen ----------
def test_lees_logbestand_parst_alle_fouten(logpad):
    logpad.write_text(LOG, encoding="utf-8")
    fouten = lees_logbestand(logpad)
    assert len(fouten) == 3
    assert fouten[0]["event"] == "chat_message"
    assert fouten[0]["fout"] == "ValueError: bewust veroorzaakte testfout"
    assert fouten[1]["fout"] == "KeyError: 'text'"
    assert fouten[2]["tijd"] == "11:05:00"


def test_lees_logbestand_zonder_bestand_of_leeg(tmp_path):
    assert lees_logbestand(tmp_path / "bestaat_niet.log") == []
    leeg = tmp_path / "leeg.log"
    leeg.write_text("", encoding="utf-8")
    assert lees_logbestand(leeg) == []


def test_lees_logbestand_onzin_geeft_geen_crash(tmp_path):
    p = tmp_path / "onzin.log"
    p.write_bytes(b"\xff\xfe geen log \x00\x01\n[kapot\n")
    assert lees_logbestand(p) == []


def test_lees_logbestand_leest_alleen_het_einde_van_een_groot_bestand(tmp_path):
    p = tmp_path / "groot.log"
    p.write_text(LOG * 200, encoding="utf-8")
    fouten = lees_logbestand(p, max_bytes=2000)
    assert 0 < len(fouten) < 600
    assert all(f["event"] for f in fouten)


# ---------- samenvatten ----------
def test_groepeer_voegt_gelijke_fouten_samen(logpad):
    logpad.write_text(LOG, encoding="utf-8")
    groepen = groepeer(lees_logbestand(logpad))
    assert len(groepen) == 2
    assert groepen[0]["handler"] == "RainModule.on_rain" and groepen[0]["aantal"] == 2


def test_overzicht_leeg():
    assert "leeg" in maak_overzicht([])


def test_overzicht_toont_kop_en_regels(logpad):
    logpad.write_text(LOG, encoding="utf-8")
    tekst = maak_overzicht(lees_logbestand(logpad))
    assert "3 fouten" in tekst and "2 verschillende" in tekst
    assert "2026-10-25 11:05:00" in tekst
    assert "RainModule.on_rain" in tekst and "(2x)" in tekst
    assert "<locals>" not in tekst
    assert "crashende_handler" in tekst


def test_overzicht_beperkt_aantal_regels():
    fouten = [{"datum": "2026-10-25", "tijd": f"10:{i:02d}:00", "event": "e",
               "handler": f"H{i}", "fout": "X"} for i in range(9)]
    tekst = maak_overzicht(fouten)
    assert tekst.count("•") == 5
    assert "nog 4 andere" in tekst


# ---------- commando's ----------
def test_commando_laatste_fouten_leest_het_logboek(logpad):
    logpad.write_text(LOG, encoding="utf-8")
    bus = EventBus()
    teksten = antwoorden(bus)
    HandlerFoutenModule(bus)
    bus.publish("intent_handler_fouten", {})
    assert len(teksten) == 1 and "3 fouten" in teksten[0]


def test_commando_valt_terug_op_geheugen_als_logbestand_ontbreekt(logpad):
    bus = EventBus()
    teksten = antwoorden(bus)
    HandlerFoutenModule(bus)
    bus.subscribe("x", lambda d, n: 1 / 0)
    logpad.unlink(missing_ok=True)
    bus.publish("x", {})
    logpad.unlink()                       # bestand weg, geheugen blijft
    bus.publish("intent_handler_fouten", {})
    assert "1 fout" in teksten[-1] and "ZeroDivisionError" in teksten[-1]


def test_wissen_maakt_log_en_geheugen_leeg(logpad):
    logpad.write_text(LOG, encoding="utf-8")
    bus = EventBus()
    teksten = antwoorden(bus)
    HandlerFoutenModule(bus)
    bus.publish("intent_handler_fouten_wissen", {})
    assert "leeg" in teksten[-1]
    assert logpad.read_text(encoding="utf-8") == ""
    assert len(bus.fouten) == 0
    bus.publish("intent_handler_fouten_wissen", {})
    assert "al leeg" in teksten[-1]


# ---------- spontane melding ----------
def maak(logpad):
    bus, klok = EventBus(), Klok()
    teksten = antwoorden(bus)
    mod = HandlerFoutenModule(bus, klok=klok)
    return bus, mod, klok, teksten


def veroorzaak(bus, naam="stuk", fout=ValueError, bericht="oeps"):
    def h(d, n):
        raise fout(bericht)
    h.__qualname__ = naam
    bus.subscribe("evt_" + naam, h)
    bus.publish("evt_" + naam, {})


def test_geen_fouten_geen_melding(logpad):
    bus, mod, klok, teksten = maak(logpad)
    assert mod.check_nieuwe_fouten() is None
    assert teksten == []


def test_nieuwe_fout_wordt_gemeld_met_verwijzing(logpad):
    bus, mod, klok, teksten = maak(logpad)
    veroorzaak(bus)
    zin = mod.check_nieuwe_fouten()
    assert zin and "stuk" in zin and "ValueError: oeps" in zin
    assert "laatste fouten" in zin
    assert teksten == [zin]


def test_dezelfde_fout_wordt_niet_twee_keer_gemeld(logpad):
    bus, mod, klok, teksten = maak(logpad)
    veroorzaak(bus)
    mod.check_nieuwe_fouten()
    klok.t += MIN_INTERVAL + 1
    veroorzaak(bus)                       # exact dezelfde fout opnieuw
    assert mod.check_nieuwe_fouten() is None
    klok.t += HEROPEN_NA + 1
    veroorzaak(bus)                       # na een uur mag het weer
    assert mod.check_nieuwe_fouten() is not None


def test_nieuwe_fouten_wachten_tot_het_interval_om_is_en_worden_gebundeld(logpad):
    bus, mod, klok, teksten = maak(logpad)
    veroorzaak(bus, "een")
    mod.check_nieuwe_fouten()
    klok.t += 60
    veroorzaak(bus, "twee", KeyError, "a")
    veroorzaak(bus, "drie", KeyError, "b")
    assert mod.check_nieuwe_fouten() is None      # te snel na de vorige
    klok.t += MIN_INTERVAL
    zin = mod.check_nieuwe_fouten()
    assert zin and "2 nieuwe fouten" in zin
    assert len(teksten) == 2


def test_melding_is_geen_lus_als_de_meldingsroute_zelf_faalt(logpad):
    bus, mod, klok, teksten = maak(logpad)
    bus.subscribe("layer4_response", lambda d, n: 1 / 0)    # kapotte route
    veroorzaak(bus)
    meldingen = 0
    for _ in range(12):                                     # ~2,2 uur, elke 11 min
        if mod.check_nieuwe_fouten():
            meldingen += 1
        klok.t += 660
    assert 1 <= meldingen <= 4


def test_bus_zonder_fout_teller_crasht_niet():
    class Dom:
        def subscribe(self, *a): pass
        def publish(self, *a): pass
    mod = HandlerFoutenModule(Dom())
    assert mod.check_nieuwe_fouten() is None


# ---------- EventBus: teller en rotatie ----------
def test_fout_teller_telt_alle_fouten_ook_voorbij_50(logpad):
    bus = EventBus()
    bus.subscribe("x", lambda d, n: 1 / 0)
    for _ in range(60):
        bus.publish("x", {})
    assert bus.fout_teller == 60 and len(bus.fouten) == 50


def test_logbestand_roteert_boven_de_grens(logpad, monkeypatch):
    monkeypatch.setattr(eb, "_MAX_LOG_BYTES", 300)
    bus = EventBus()
    bus.subscribe("x", lambda d, n: 1 / 0)
    for _ in range(5):
        bus.publish("x", {})
    assert logpad.with_name(logpad.name + ".1").exists()
    assert logpad.exists() and logpad.stat().st_size > 0


# ---------- router ----------
class FakeBus:
    def __init__(self):
        self.subs, self.events, self.modules = {}, [], {}
    def subscribe(self, naam, fn):
        self.subs.setdefault(naam, []).append(fn)
    def publish(self, naam, data=None):
        self.events.append((naam, data))
        for fn in self.subs.get(naam, []):
            fn(data or {}, naam)
    def namen(self):
        return [n for n, _ in self.events]
    def antwoorden(self):
        return [d["text"] for n, d in self.events if n == "layer4_response"]


@pytest.fixture
def router_bus(logpad):
    logpad.write_text(LOG, encoding="utf-8")
    bus = FakeBus()
    HandlerFoutenModule(bus)
    return IntentRouter(bus), bus


@pytest.mark.parametrize("zin", [
    "laatste fouten", "Laatste fouten?", "toon fouten", "toon de laatste fouten",
    "laat de fouten zien", "geef me de fouten", "fouten", "foutenlog",
    "zijn er fouten", "zijn er fouten geweest?", "waren er nog fouten",
    "heb je fouten gehad", "heb je nog fouten?", "welke fouten heb je gehad",
    "toon technische fouten", "foutmeldingen",
])
def test_router_toont_fouten(router_bus, zin):
    router, bus = router_bus
    router.route({"text": zin})
    assert "intent_handler_fouten" in bus.namen(), zin
    assert "3 fouten" in bus.antwoorden()[0]


@pytest.mark.parametrize("zin", [
    "wis de fouten", "wis fouten", "fouten wissen", "maak de foutenlog leeg",
    "verwijder de foutmeldingen",
])
def test_router_wist_fouten(router_bus, zin):
    router, bus = router_bus
    router.route({"text": zin})
    assert "intent_handler_fouten_wissen" in bus.namen(), zin


@pytest.mark.parametrize("zin", [
    "ik maak veel fouten", "fouten maken is menselijk", "wat zijn fouten",
    "wat is een fout", "heb je fouten gemaakt", "ik heb fouten gevonden in mijn code",
    "wat is drie plus vijf", "hey",
])
def test_router_kaapt_gewone_zinnen_niet(router_bus, zin):
    router, bus = router_bus
    router.route({"text": zin})
    assert "intent_handler_fouten" not in bus.namen(), zin
    assert "intent_handler_fouten_wissen" not in bus.namen(), zin