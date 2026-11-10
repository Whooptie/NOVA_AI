# tests/test_welkom_groet30.py
"""
Punt 30 (10 november 2026): geen dubbele begroeting na terugkomst.

Zegt Nova net "welkom terug" (afwezigheid.py) en zegt Kevin meteen "hey", dan komt er geen
tweede "Hey Kevin, leuk dat je er bent" maar een korte, bijdehande vervolgzin
(response_pipeline.py, WELKOM_VERVOLG_ZINNEN). Na 60 seconden, of als er geen welkom was,
blijft de gewone groet.
"""
import pytest

from core.event_bus import EventBus
from modules.chat.response_pipeline import ResponsePipeline
from modules.context.afwezigheid import AfwezigheidModule

VERTREK = "activity_started:afwezig_gedetecteerd"
TERUG = "activity_started:browser_gedetecteerd"
GEWONE_GROET = "Hey Kevin, leuk dat je er bent"


class NepKlok:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def omgeving():
    klok = NepKlok()
    bus = EventBus()
    bus.modules = getattr(bus, "modules", {})
    afw = AfwezigheidModule(bus, klok=klok)
    bus.modules["afwezigheid"] = afw
    pipeline = ResponsePipeline(bus)
    basis = []
    bus.subscribe("pipeline_response", lambda d, *a, **k: basis.append(d.get("base_text")))
    return bus, afw, klok, pipeline, basis


def _weg_en_terug(bus, klok, minuten):
    bus.publish(VERTREK, {})
    klok.t += minuten * 60
    bus.publish(TERUG, {})


def _groet(bus, basis):
    basis.clear()
    bus.publish("intent_greeting", {"sender": "Kevin"})
    return basis[-1]


# ---------------------------------------------------------------------------
# afwezigheid.welkom_net_gezegd
# ---------------------------------------------------------------------------
def test_nog_nooit_welkom_gezegd(omgeving):
    _, afw, *_ = omgeving
    assert afw.welkom_net_gezegd() is False


def test_welkom_na_lange_afwezigheid_telt(omgeving):
    bus, afw, klok, *_ = omgeving
    _weg_en_terug(bus, klok, 9)
    assert afw.welkom_net_gezegd() is True


def test_korte_afwezigheid_zonder_berichten_zegt_geen_welkom(omgeving):
    bus, afw, klok, *_ = omgeving
    _weg_en_terug(bus, klok, 2)
    assert afw.welkom_net_gezegd() is False


def test_welkom_verloopt_na_het_tijdvenster(omgeving):
    bus, afw, klok, *_ = omgeving
    _weg_en_terug(bus, klok, 9)
    klok.t += 59
    assert afw.welkom_net_gezegd() is True
    klok.t += 2
    assert afw.welkom_net_gezegd() is False


def test_eigen_tijdvenster_is_mogelijk(omgeving):
    bus, afw, klok, *_ = omgeving
    _weg_en_terug(bus, klok, 9)
    klok.t += 100
    assert afw.welkom_net_gezegd(binnen_seconden=120) is True


# ---------------------------------------------------------------------------
# De groet zelf
# ---------------------------------------------------------------------------
def test_groet_na_welkom_is_een_vervolgzin(omgeving):
    bus, _, klok, pipeline, basis = omgeving
    _weg_en_terug(bus, klok, 9)
    zin = _groet(bus, basis)
    assert zin in ResponsePipeline.WELKOM_VERVOLG_ZINNEN
    assert GEWONE_GROET not in zin


def test_groet_zonder_welkom_blijft_gewoon(omgeving):
    bus, _, _, _, basis = omgeving
    assert _groet(bus, basis) == GEWONE_GROET


def test_groet_na_korte_afwezigheid_blijft_gewoon(omgeving):
    bus, _, klok, _, basis = omgeving
    _weg_en_terug(bus, klok, 2)          # geen welkom gezegd
    assert _groet(bus, basis) == GEWONE_GROET


def test_groet_lang_na_het_welkom_is_weer_gewoon(omgeving):
    bus, _, klok, _, basis = omgeving
    _weg_en_terug(bus, klok, 9)
    klok.t += 120
    assert _groet(bus, basis) == GEWONE_GROET


def test_zonder_afwezigheid_module_blijft_de_groet_gewoon():
    bus = EventBus()
    bus.modules = getattr(bus, "modules", {})
    ResponsePipeline(bus)
    basis = []
    bus.subscribe("pipeline_response", lambda d, *a, **k: basis.append(d.get("base_text")))
    assert _groet(bus, basis) == GEWONE_GROET


def test_nooit_twee_keer_dezelfde_vervolgzin_na_elkaar(omgeving):
    bus, _, klok, _, basis = omgeving
    _weg_en_terug(bus, klok, 9)
    vorige = None
    for _ in range(60):
        zin = _groet(bus, basis)
        assert zin != vorige
        vorige = zin


def test_er_zijn_genoeg_varianten_en_ze_zijn_uniek():
    zinnen = ResponsePipeline.WELKOM_VERVOLG_ZINNEN
    assert len(zinnen) >= 12
    assert len(set(zinnen)) == len(zinnen)
    assert all(z.strip() and not z.startswith("Hey Kevin") for z in zinnen)