# tests/test_watchdog.py
"""
Tests voor modules/diagnose/watchdog.py (levenssignaal en wekelijkse testmelding), 14 november 2026.

Er wordt nooit echt iets verstuurd: de webaanvraag en ntfy zijn nep, de klok is nep en de
achtergrondthread staat uit (we roepen tik() zelf aan).
"""
import json
import os
from datetime import datetime, time as dagtijd, timedelta
from types import SimpleNamespace

import pytest

from modules.diagnose import watchdog as w

GEHEIM = "https://hc-ping.example.com/0a1b2c3d-geheim-uuid-9999"
ZONDAG_10 = (6, dagtijd(10, 0))


@pytest.fixture(autouse=True)
def _geen_instellingen_uit_de_omgeving(monkeypatch):
    for naam in (w.URL_NAAM, w.MINUTEN_NAAM, w.METHODE_NAAM, w.TEST_NAAM):
        monkeypatch.delenv(naam, raising=False)


class Klok:
    def __init__(self, start):
        self.nu = start

    def __call__(self):
        return self.nu

    def loop(self, **kw):
        self.nu += timedelta(**kw)


class NepHttp:
    def __init__(self, status=200, fout=None):
        self.status, self.fout, self.aanroepen = status, fout, []

    def __call__(self, methode, url, timeout):
        self.aanroepen.append((methode, url, timeout))
        if self.fout:
            raise self.fout
        return SimpleNamespace(status_code=self.status)


class NepBus:
    def __init__(self, **modules):
        self.modules = dict(modules)
        self.gepubliceerd = []

    def publish(self, naam, data=None, *a, **k):
        self.gepubliceerd.append((naam, data))


def maak(tmp_path, klok=None, bus=None, **opties):
    meldingen = []
    klok = klok or Klok(datetime(2026, 11, 14, 12, 0, 0))             # een zaterdag
    opties.setdefault("achtergrond", False)
    wd = w.Watchdog(bus or NepBus(), project_root=tmp_path, klok=klok, drukaf=meldingen.append, **opties)
    return wd, klok, meldingen


def status(tmp_path):
    return json.loads((tmp_path / "data" / "hartslag_status.json").read_text(encoding="utf-8"))


# ----------------------------------------------------------------------------
# Schema
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("tekst,verwacht", [
    ("zondag 10:00", (6, dagtijd(10, 0))), ("Elke maandag 7.30", (0, dagtijd(7, 30))),
    ("vr 18u15", (4, dagtijd(18, 15))), ("10:00", (None, dagtijd(10, 0))),
    ("elke dag 09:05", (None, dagtijd(9, 5))),
    ("uit", None), ("", None), (None, None), ("zondag", None), ("25:00", None), ("zondag 10:99", None),
])
def test_parse_schema(tekst, verwacht):
    assert w.parse_schema(tekst) == verwacht


def test_schema_tekst():
    assert w.schema_tekst(ZONDAG_10) == "zondag 10:00"
    assert w.schema_tekst((None, dagtijd(9, 5))) == "elke dag 09:05"
    assert w.schema_tekst(None) == "uit"


def test_laatste_moment():
    zaterdag = datetime(2026, 11, 14, 12, 0)
    assert w.laatste_moment(zaterdag, ZONDAG_10) == datetime(2026, 11, 8, 10, 0)             # vorige zondag
    zondag_voor = datetime(2026, 11, 15, 9, 0)
    assert w.laatste_moment(zondag_voor, ZONDAG_10) == datetime(2026, 11, 8, 10, 0)           # nog niet 10:00
    zondag_na = datetime(2026, 11, 15, 10, 30)
    assert w.laatste_moment(zondag_na, ZONDAG_10) == datetime(2026, 11, 15, 10, 0)
    assert w.laatste_moment(zaterdag, (None, dagtijd(9, 0))) == datetime(2026, 11, 14, 9, 0)
    assert w.laatste_moment(datetime(2026, 11, 14, 8, 0), (None, dagtijd(9, 0))) == datetime(2026, 11, 13, 9, 0)


# ----------------------------------------------------------------------------
# Opstarten en instellingen
# ----------------------------------------------------------------------------

def test_standaard_staat_alles_uit_maar_er_komt_wel_een_statusbestand(tmp_path):
    wd, _, meldingen = maak(tmp_path)
    assert wd._hartslag_aan is False and wd._schema is None and wd._thread is None
    assert any("Staat UIT" in m for m in meldingen)
    s = status(tmp_path)
    assert s["hartslag"]["aan"] is False and s["meldingstest"]["aan"] is False


def test_instellingen_uit_parameters(tmp_path):
    wd, _, meldingen = maak(tmp_path, hartslag_url=GEHEIM, hartslag_minuten="15", methode="POST",
                            meldingstest="zondag 10:00", http=NepHttp())
    assert wd._hartslag_aan and wd._minuten == 15 and wd._methode == "post" and wd._schema == ZONDAG_10
    assert any("levenssignaal elke 15 minuten" in m and "testmelding zondag 10:00" in m for m in meldingen)
    assert all(GEHEIM not in m and "geheim" not in m for m in meldingen)                  # adres nooit in het log
    s = status(tmp_path)
    assert s["hartslag"]["interval_min"] == 15 and s["meldingstest"]["schema"] == "zondag 10:00"


@pytest.mark.parametrize("ruw,verwacht", [("5", 5), ("0", 1), ("99999", 1440), ("abc", 10), ("", 10), (None, 10)])
def test_minuten_worden_begrensd(ruw, verwacht):
    assert w.Watchdog._lees_minuten(ruw) == verwacht


def test_adres_zonder_http_wordt_geweigerd(tmp_path):
    wd, _, meldingen = maak(tmp_path, hartslag_url="ftp://onzin", http=NepHttp())
    assert wd._hartslag_aan is False and any("moet met http" in m for m in meldingen)


def test_onbekende_methode_wordt_get(tmp_path):
    wd, _, _ = maak(tmp_path, hartslag_url=GEHEIM, methode="put", http=NepHttp())
    assert wd._methode == "get"


def test_tijdens_pytest_wordt_de_omgeving_niet_gelezen(tmp_path, monkeypatch):
    monkeypatch.setenv(w.URL_NAAM, GEHEIM)
    monkeypatch.setenv(w.TEST_NAAM, "10:00")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "ja")
    wd, _, _ = maak(tmp_path)
    assert wd._hartslag_aan is False and wd._schema is None


def test_zonder_pytest_komt_de_instelling_uit_de_omgeving(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv(w.URL_NAAM, GEHEIM)
    monkeypatch.setenv(w.MINUTEN_NAAM, "20")
    monkeypatch.setattr(w.Watchdog, "_laad_dotenv", lambda self: None)
    wd, _, _ = maak(tmp_path, http=NepHttp())
    assert wd._hartslag_aan and wd._minuten == 20


# ----------------------------------------------------------------------------
# Levenssignaal
# ----------------------------------------------------------------------------

def test_hartslag_succes(tmp_path):
    http = NepHttp()
    wd, klok, _ = maak(tmp_path, hartslag_url=GEHEIM, http=http, methode="get")
    assert wd.stuur_hartslag() == (True, None)
    assert http.aanroepen == [("get", GEHEIM, w.TIMEOUT_SECONDEN)]
    h = status(tmp_path)["hartslag"]
    assert h["laatste_ok"] == klok().isoformat(timespec="seconds") and h["fouten_op_rij"] == 0


def test_hartslag_wordt_op_tijd_gestuurd_en_niet_vaker(tmp_path):
    http = NepHttp()
    wd, klok, _ = maak(tmp_path, hartslag_url=GEHEIM, hartslag_minuten=10, http=http)
    wd.tik()
    wd.tik()
    assert len(http.aanroepen) == 1
    klok.loop(minutes=9)
    wd.tik()
    assert len(http.aanroepen) == 1
    klok.loop(minutes=1)
    wd.tik()
    assert len(http.aanroepen) == 2


def test_mislukte_hartslag_wordt_sneller_herhaald_en_het_adres_blijft_geheim(tmp_path):
    http = NepHttp(fout=ConnectionError(f"kan {GEHEIM} niet bereiken"))
    wd, klok, meldingen = maak(tmp_path, hartslag_url=GEHEIM, hartslag_minuten=60, http=http)
    wd.tik()
    h = status(tmp_path)["hartslag"]
    assert h["fouten_op_rij"] == 1 and "<adres>" in h["reden"] and "geheim" not in json.dumps(status(tmp_path))
    klok.loop(minutes=5)                                   # interval is 60, maar na een fout proberen we na 5
    wd.tik()
    klok.loop(minutes=5)
    wd.tik()
    assert len(http.aanroepen) == 3
    assert any("Levenssignaal mislukt" in m for m in meldingen)
    assert all("geheim" not in m for m in meldingen)
    assert sum("Levenssignaal mislukt" in m for m in meldingen) == 1       # maar een keer melden per reeks


def test_hartslag_herstel_wordt_gemeld(tmp_path):
    http = NepHttp(status=500)
    wd, klok, meldingen = maak(tmp_path, hartslag_url=GEHEIM, hartslag_minuten=5, http=http)
    for _ in range(3):
        wd.tik()
        klok.loop(minutes=5)
    assert status(tmp_path)["hartslag"]["reden"] == "de dienst antwoordde 500"
    http.status = 200
    wd.tik()
    assert status(tmp_path)["hartslag"]["fouten_op_rij"] == 0
    assert any("komt weer aan" in m for m in meldingen)


def test_hartslag_uitgeschakeld_stuurt_niets(tmp_path):
    http = NepHttp()
    wd, _, _ = maak(tmp_path, http=http)
    wd.tik()
    assert http.aanroepen == [] and wd.stuur_hartslag() == (False, "het levenssignaal staat uit")


# ----------------------------------------------------------------------------
# Testmelding
# ----------------------------------------------------------------------------

class NepNtfy:
    def __init__(self, aan=True, gelukt=True):
        self.aan, self.gelukt, self.berichten = aan, gelukt, []

    def _verstuur(self, tekst, meld_fout=True):
        self.berichten.append(tekst)
        return self.gelukt


def test_testmelding_gaat_via_ntfy(tmp_path):
    ntfy = NepNtfy()
    wd, _, _ = maak(tmp_path, bus=NepBus(ntfy_meldingen=ntfy), meldingstest="zondag 10:00")
    assert wd.stuur_testmelding() == (True, None)
    assert len(ntfy.berichten) == 1 and "bereiken mijn meldingen je gsm" in ntfy.berichten[0]
    t = status(tmp_path)["meldingstest"]
    assert t["laatste_ok"] and t["fouten_op_rij"] == 0


@pytest.mark.parametrize("module,reden", [
    (None, "ntfy staat uit of is niet geladen"), (NepNtfy(aan=False), "ntfy staat uit of is niet geladen"),
    (NepNtfy(gelukt=False), "de ntfy-server nam het bericht niet aan"),
])
def test_testmelding_mislukt_met_een_reden(tmp_path, module, reden):
    bus = NepBus(ntfy_meldingen=module) if module else NepBus()
    wd, _, meldingen = maak(tmp_path, bus=bus, meldingstest="zondag 10:00")
    assert wd.stuur_testmelding() == (False, reden)
    t = status(tmp_path)["meldingstest"]
    assert t["fouten_op_rij"] == 1 and t["reden"] == reden and t["laatste_ok"] is None
    assert any("Testmelding naar de gsm mislukt" in m for m in meldingen)


def test_testmelding_die_crasht_stopt_niets(tmp_path):
    def stuur(tekst):
        raise RuntimeError("boem")
    wd, _, _ = maak(tmp_path, meldingstest="zondag 10:00", stuur_test=stuur)
    assert wd.stuur_testmelding() == (False, "RuntimeError")


def test_wanneer_is_een_testmelding_nodig(tmp_path):
    wd, klok, _ = maak(tmp_path, meldingstest="zondag 10:00", stuur_test=lambda t: (True, None))
    assert wd._test_nodig(klok()) is True                          # nog nooit gelukt: meteen (het is 12:00)
    klok.nu = datetime(2026, 11, 14, 23, 0)
    assert wd._test_nodig(klok()) is False                         # 's avonds laat nooit
    klok.nu = datetime(2026, 11, 14, 7, 0)
    assert wd._test_nodig(klok()) is False                         # 's ochtends vroeg ook niet
    klok.nu = datetime(2026, 11, 14, 12, 0)
    wd.stuur_testmelding()
    assert wd._test_nodig(klok()) is False                         # net gelukt
    klok.nu = datetime(2026, 11, 15, 9, 59)
    assert wd._test_nodig(klok()) is False                         # zondag, maar nog geen 10:00
    klok.nu = datetime(2026, 11, 15, 10, 0)
    assert wd._test_nodig(klok()) is True                          # zondag 10:00: de wekelijkse test
    wd.stuur_testmelding()
    klok.nu = datetime(2026, 11, 20, 12, 0)
    assert wd._test_nodig(klok()) is False                         # pas de volgende zondag weer
    klok.nu = datetime(2026, 11, 22, 10, 0)
    assert wd._test_nodig(klok()) is True
    klok.nu = datetime(2026, 11, 15, 10, 0)
    assert maak(tmp_path / "x")[0]._test_nodig(klok()) is False    # zonder schema nooit


def test_mislukte_testmelding_wordt_elk_uur_herhaald(tmp_path):
    pogingen = []

    def stuur(tekst):
        pogingen.append(tekst)
        return False, "geen verbinding"
    wd, klok, _ = maak(tmp_path, meldingstest="zondag 10:00", stuur_test=stuur)
    klok.nu = datetime(2026, 11, 15, 10, 0)
    wd.tik()
    klok.loop(minutes=30)
    wd.tik()
    assert len(pogingen) == 1
    klok.loop(minutes=30)
    wd.tik()
    assert len(pogingen) == 2
    assert status(tmp_path)["meldingstest"]["fouten_op_rij"] == 2


def test_stand_blijft_na_een_herstart_bewaard(tmp_path):
    wd, klok, _ = maak(tmp_path, hartslag_url=GEHEIM, http=NepHttp(), meldingstest="zondag 10:00",
                       stuur_test=lambda t: (True, None))
    wd.stuur_hartslag()
    wd.stuur_testmelding()
    nieuw, _, _ = maak(tmp_path, klok=klok, hartslag_url=GEHEIM, http=NepHttp(), meldingstest="zondag 10:00",
                       stuur_test=lambda t: (True, None))
    assert nieuw._status["hartslag"]["laatste_ok"] and nieuw._status["meldingstest"]["laatste_ok"]
    assert nieuw._test_nodig(klok()) is False                      # niet nog eens na een herstart


def test_kapot_statusbestand_wordt_genegeerd(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "hartslag_status.json").write_text("{kapot", encoding="utf-8")
    wd, _, _ = maak(tmp_path)
    assert wd._status["hartslag"]["laatste_ok"] is None
    assert status(tmp_path)["versie"] == 1                         # vervangen door een goede


def test_status_kan_niet_geschreven_worden_zonder_crash(tmp_path):
    bezet = tmp_path / "data"
    bezet.write_text("ik ben een bestand", encoding="utf-8")
    wd, _, _ = maak(tmp_path, hartslag_url=GEHEIM, http=NepHttp())
    assert wd.stuur_hartslag() == (True, None)


# ----------------------------------------------------------------------------
# Commando's en de lus
# ----------------------------------------------------------------------------

def test_ping_nu_en_meldingstest_nu_geven_tekst(tmp_path):
    wd, _, _ = maak(tmp_path)
    assert "staat uit" in wd.ping_nu() and "NOVA_HARTSLAG_URL" in wd.ping_nu()
    wd2, _, _ = maak(tmp_path / "b", hartslag_url=GEHEIM, http=NepHttp(), meldingstest="zondag 10:00",
                     stuur_test=lambda t: (True, None))
    tekst = wd2.ping_nu()
    assert "Levenssignaal verstuurd." in tekst and "elke 10 min" in tekst and "Testmelding: zondag 10:00" in tekst
    assert "Testmelding verstuurd" in wd2.meldingstest_nu()
    wd3, _, _ = maak(tmp_path / "c", http=NepHttp(status=503), hartslag_url=GEHEIM)
    assert "MISLUKT: de dienst antwoordde 503" in wd3.ping_nu()
    wd4, _, _ = maak(tmp_path / "d", meldingstest="zondag 10:00", stuur_test=lambda t: (False, "kapot"))
    assert wd4.meldingstest_nu() == "Testmelding MISLUKT: kapot."


def test_een_fout_in_de_ronde_doodt_de_lus_niet(tmp_path):
    wd, _, meldingen = maak(tmp_path, hartslag_url=GEHEIM, http=NepHttp())
    calls = []

    def kapotte_tik():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boem")
        wd._stop.set()
    wd.tik = kapotte_tik
    w.EERSTE_TIK_SECONDEN, oud = 0, w.EERSTE_TIK_SECONDEN
    w.TIK_SECONDEN, oud_tik = 0, w.TIK_SECONDEN
    try:
        wd._lus()
    finally:
        w.EERSTE_TIK_SECONDEN, w.TIK_SECONDEN = oud, oud_tik
    assert len(calls) == 2 and any("Fout in de controleronde" in m for m in meldingen)


def test_achtergrondthread_start_alleen_als_er_iets_aan_staat(tmp_path):
    wd, _, _ = maak(tmp_path, hartslag_url=GEHEIM, http=NepHttp(), achtergrond=True)
    try:
        assert wd._thread is not None and wd._thread.daemon
    finally:
        wd.shutdown()
        wd._thread.join(timeout=2)
    uit, _, _ = maak(tmp_path / "uit", achtergrond=True)
    assert uit._thread is None


def test_init_module_conventie(tmp_path):
    bus = NepBus()
    instance = w.init_module(bus)
    assert isinstance(instance, w.Watchdog) and ("module_loaded", {"name": "watchdog"}) in bus.gepubliceerd
    assert os.getenv("PYTEST_CURRENT_TEST") and instance._thread is None
    instance.shutdown()