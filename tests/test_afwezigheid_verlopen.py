# tests/test_afwezigheid_verlopen.py
"""
Punt 55c: bewaarde berichten met een relatieve tijd ("over ongeveer 10
minuten") vervallen in afwezigheid.py na RELATIEVE_TIJD_VERLOOPT_MINUTEN.

Alleen de laptop-kant (het welkom-terug-lijstje): een bericht dat al naar de
gsm gestuurd is, blijft daar staan. Er is geen netwerk nodig; de teksten
komen uit de echte functies van rain.py, zodat de herkenning getest wordt
op wat Nova echt zegt.
"""

from datetime import datetime, timedelta

import pytest

from modules.context.afwezigheid import AfwezigheidModule
from modules.weather import rain


# ----------------------------------------------------------------
# Hulpmiddelen
# ----------------------------------------------------------------

class EchteBus:
    def __init__(self):
        self._subs = {}
        self.gepubliceerd = []

    def subscribe(self, event_type, handler):
        self._subs.setdefault(event_type, []).append(handler)

    def publish(self, event_type, data=None):
        data = data if data is not None else {}
        self.gepubliceerd.append((event_type, data))
        for handler in list(self._subs.get(event_type, [])) + list(self._subs.get("*", [])):
            handler(data, event_type=event_type)

    def teksten(self):
        return [d.get("text") for t, d in self.gepubliceerd if t == "chat_response"]


class NepKlok:
    def __init__(self, start=1_000_000.0):
        self.nu = start

    def __call__(self):
        return self.nu

    def verder(self, minuten):
        self.nu += minuten * 60


@pytest.fixture
def bus():
    return EchteBus()


@pytest.fixture
def klok():
    return NepKlok()


@pytest.fixture
def afw(bus, klok):
    return AfwezigheidModule(bus, klok=klok)


def vertrek(bus):
    bus.publish("activity_started:afwezig_gedetecteerd", {})


def terug(bus):
    bus.publish("activity_started:coding_gedetecteerd", {})


def bewaar(afw, tekst):
    assert afw.onderschep_bericht({"text": tekst}, is_hoofdthread=False) is True


def welkom_na(bus, afw, klok, minuten_weg):
    klok.verder(minuten_weg)
    terug(bus)
    return bus.teksten()[-1]


# ----------------------------------------------------------------
# Echte teksten uit rain.py
# ----------------------------------------------------------------

NU = datetime(2026, 11, 2, 14, 0)


def _regenzin():
    analyse = {
        "regent_nu": False, "intensiteit": 2.0, "begin_min": 15,
        "stop_min": None, "daarna_min": None, "horizon_min": 120,
    }
    zin, _ = rain.beslis_proactief(analyse, NU, {"gemeld": False, "laatste": None})
    return zin


def _onweerzin():
    info = {"nu": False, "begin_min": 25, "einde_min": None, "horizon_min": 180}
    zin, _ = rain.beslis_onweer(info, NU, {"gemeld": False, "laatste": None})
    return zin


def _gevaarzinnen():
    info = {
        "horizon_min": 180,
        "gladheid": {"nu": False, "begin_min": 60, "einde_min": None, "temp": 1.0},
        "wind": {"nu": False, "begin_min": 50, "einde_min": None, "wind": 16.0, "vlagen": 22.0},
    }
    zinnen, _ = rain.beslis_gevaar(info, NU, {})
    return zinnen


class TestHerkenning:
    def test_de_echte_teksten_hebben_een_relatieve_tijd(self):
        teksten = [_regenzin(), _onweerzin(), *_gevaarzinnen()]
        assert len(teksten) == 4
        for tekst in teksten:
            assert AfwezigheidModule._RELATIEVE_TIJD.search(tekst), tekst

    @pytest.mark.parametrize("tekst", [
        "Let op: het begint zo meteen te regenen (lichte regen).",
        "Over ongeveer 20 minuten begint het te regenen.",
        "Let op: kans op gladheid nu, nog ongeveer 45 minuten (rond -1°C met neerslag).",
    ])
    def test_zinnen_met_relatieve_tijd(self, tekst):
        assert AfwezigheidModule._RELATIEVE_TIJD.search(tekst)

    @pytest.mark.parametrize("tekst", [
        "Let op: er wordt onweer verwacht.",
        "Even een seintje: het weer in Aartrijke verandert. Let op: er wordt mist verwacht.",
        "Je zit al een tijdje te coderen. Tijd voor een pauze?",
    ])
    def test_zinnen_zonder_relatieve_tijd(self, tekst):
        assert not AfwezigheidModule._RELATIEVE_TIJD.search(tekst)


# ----------------------------------------------------------------
# Gedrag bij terugkomst
# ----------------------------------------------------------------

class TestVerlopen:
    def test_vers_bericht_met_relatieve_tijd_blijft_staan(self, bus, afw, klok):
        vertrek(bus)
        bewaar(afw, _regenzin())
        tekst = welkom_na(bus, afw, klok, 10)
        assert "begint over ongeveer" in tekst

    def test_oud_bericht_met_relatieve_tijd_valt_weg(self, bus, afw, klok):
        vertrek(bus)
        bewaar(afw, _regenzin())
        tekst = welkom_na(bus, afw, klok, 160)  # 2 uur 40, zoals op 23 oktober
        assert "over ongeveer" not in tekst
        assert "en nog 1 oudere melding" in tekst

    def test_precies_op_de_grens_valt_weg_en_net_ervoor_niet(self, bus, afw, klok):
        grens = AfwezigheidModule.RELATIEVE_TIJD_VERLOOPT_MINUTEN
        vertrek(bus)
        bewaar(afw, "Let op: het begint over ongeveer 5 minuten te regenen (lichte regen).")
        klok.verder(grens - 1)
        bewaar(afw, "Let op: kans op onweer over ongeveer 20 minuten.")
        tekst = welkom_na(bus, afw, klok, 1)  # eerste is nu precies 'grens' minuten oud
        assert "over ongeveer 5 minuten" not in tekst
        assert "over ongeveer 20 minuten" in tekst

    def test_bericht_zonder_relatieve_tijd_blijft_na_uren_staan(self, bus, afw, klok):
        vertrek(bus)
        bewaar(afw, "Let op: er wordt onweer verwacht.")
        tekst = welkom_na(bus, afw, klok, 5 * 60)
        assert "Let op: er wordt onweer verwacht." in tekst
        assert "oudere" not in tekst

    def test_gemengd_enkel_het_verlopen_bericht_valt_weg(self, bus, afw, klok):
        vertrek(bus)
        bewaar(afw, _regenzin())
        bewaar(afw, "Let op: er wordt mist verwacht.")
        tekst = welkom_na(bus, afw, klok, 120)
        assert "mist verwacht" in tekst
        assert "over ongeveer" not in tekst
        assert "en nog 1 oudere melding" in tekst

    def test_de_gewone_grens_van_12_uur_blijft_gelden(self, bus, afw, klok):
        vertrek(bus)
        bewaar(afw, "Let op: er wordt hagel verwacht.")
        tekst = welkom_na(bus, afw, klok, AfwezigheidModule.MAX_BERICHT_LEEFTIJD_UUR * 60 + 30)
        assert "hagel" not in tekst
        assert "en nog 1 oudere melding" in tekst

    def test_praten_tijdens_afwezigheid_laat_ook_verlopen(self, bus, afw, klok):
        vertrek(bus)
        bewaar(afw, _regenzin())
        bewaar(afw, "Let op: er wordt mist verwacht.")
        klok.verder(90)
        bus.publish("raw_user_message", {"text": "hey"})
        tekst = bus.teksten()[-1]
        assert "mist verwacht" in tekst
        assert "over ongeveer" not in tekst
        assert "en nog 1 oudere melding" in tekst

    def test_ochtendsamenvatting_met_radarzin_verloopt_ook(self, bus, afw, klok):
        vertrek(bus)
        bewaar(afw, "Goedemorgen Kevin! Vandaag wordt het tussen 8°C en 13°C. "
                    "Over ongeveer 40 minuten begint het te regenen (lichte regen).")
        tekst = welkom_na(bus, afw, klok, 240)
        assert "Goedemorgen" not in tekst

    def test_een_bericht_dat_bij_terugkomst_vers_is_krijgt_geen_oudere_regel(self, bus, afw, klok):
        vertrek(bus)
        bewaar(afw, _onweerzin())
        tekst = welkom_na(bus, afw, klok, 3)
        assert "oudere" not in tekst