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


# ---------------------------------------------------------------------------
# De race: de groet is er vóór het welkom (melding van de laptop loopt achter)
# ---------------------------------------------------------------------------
def test_welkom_verwacht_alleen_als_afwezig_en_lang_genoeg(omgeving):
    bus, afw, klok, *_ = omgeving
    assert afw.welkom_verwacht() is False            # niet afwezig
    bus.publish(VERTREK, {})
    klok.t += 3 * 60
    assert afw.welkom_verwacht() is False            # te kort weg
    klok.t += 3 * 60
    assert afw.welkom_verwacht() is True             # 6 minuten weg
    bus.publish(TERUG, {})
    assert afw.welkom_verwacht() is False            # weer terug


def test_welkom_verwacht_bij_bewaarde_berichten_ook_na_korte_afwezigheid(omgeving):
    bus, afw, klok, *_ = omgeving
    bus.publish(VERTREK, {})
    klok.t += 60
    afw.onderschep_bericht({"text": "Let op: onweer"}, is_hoofdthread=False)
    assert afw.welkom_verwacht() is True


def test_race_welkom_komt_pas_tijdens_het_wachten(omgeving):
    bus, _, klok, pipeline, basis = omgeving
    bus.publish(VERTREK, {})
    klok.t += 7 * 60                      # nog vergrendeld geregistreerd, 7 minuten weg
    wacht = []

    def slaap(s):
        wacht.append(s)
        if len(wacht) == 3:               # de ontgrendel-melding komt nu pas binnen
            bus.publish(TERUG, {})

    pipeline._slaap = slaap
    zin = _groet(bus, basis)
    assert zin in ResponsePipeline.WELKOM_VERVOLG_ZINNEN
    assert len(wacht) == 3                # stopte meteen toen het welkom er was


def test_race_welkom_komt_niet_dan_volgt_de_gewone_groet_na_het_wachten(omgeving):
    # Kevin typt via zijn gsm terwijl de laptop vergrendeld blijft: er komt nooit een welkom.
    bus, _, klok, pipeline, basis = omgeving
    bus.publish(VERTREK, {})
    klok.t += 7 * 60
    wacht = []
    pipeline._slaap = lambda s: wacht.append(s)
    assert _groet(bus, basis) == GEWONE_GROET
    assert len(wacht) == int(pipeline.WELKOM_WACHT_SECONDEN / pipeline.WELKOM_WACHT_STAP)


def test_geen_wachttijd_als_er_geen_welkom_verwacht_wordt(omgeving):
    bus, _, klok, pipeline, basis = omgeving
    wacht = []
    pipeline._slaap = lambda s: wacht.append(s)
    assert _groet(bus, basis) == GEWONE_GROET        # Kevin was niet weg
    bus.publish(VERTREK, {})
    klok.t += 2 * 60
    assert _groet(bus, basis) == GEWONE_GROET        # te kort weg voor een welkom
    assert wacht == []


def test_geen_wachttijd_als_het_welkom_er_al_is(omgeving):
    bus, _, klok, pipeline, basis = omgeving
    _weg_en_terug(bus, klok, 9)
    wacht = []
    pipeline._slaap = lambda s: wacht.append(s)
    assert _groet(bus, basis) in ResponsePipeline.WELKOM_VERVOLG_ZINNEN
    assert wacht == []


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