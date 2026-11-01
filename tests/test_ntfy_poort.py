# tests/test_ntfy_poort.py
"""
Tests voor punt 55, stap 2b: de Layer 5-poort laat een proactief bericht door
als de gsm het zou ontvangen.

Er is geen netwerk nodig: de NtfyMeldingen-module krijgt een nep-bridge en een
nep-post, de regenradar krijgt nep-gegevens.

Wat getest wordt:
- NtfyMeldingen.gsm_vangt_op(): ja/nee/twijfel
- main._layer5_gsm_laat_spreken_toe() en main._layer5_ochtend_mag_spreken():
  het oude gedrag blijft exact gelijk zonder ntfy-module, en met ntfy mag
  een "nee" van Layer 5 omgedraaid worden naar "ja"
- het hele pad met de echte RainModule.check_proactief()
"""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

import main
from modules.network.ntfy_meldingen import NtfyMeldingen


# ----------------------------------------------------------------
# Hulpklassen
# ----------------------------------------------------------------

class DummyEventBus:
    def __init__(self):
        self.gepubliceerd = []
        self.modules = {}

    def subscribe(self, event_type, handler):
        pass

    def publish(self, event_type, data=None):
        self.gepubliceerd.append((event_type, data))


class FakeBridge:
    def __init__(self, verbonden=True, focus="actief", activiteit="coding", fout=None):
        self.verbonden = verbonden
        self.focus = focus
        self.activiteit = activiteit
        self.fout = fout

    def is_laptop_verbonden(self):
        if self.fout:
            raise self.fout
        return self.verbonden

    def get_laatste_activity(self, max_leeftijd=180):
        return {"activity": self.activiteit}

    def get_laatste_focus(self, max_leeftijd=180):
        return {"focus_level": self.focus}


class NepPost:
    def __call__(self, url, data=None, headers=None, timeout=None):
        return SimpleNamespace(status_code=200)


def maak_ntfy(bridge="standaard", aan=True):
    bus = DummyEventBus()
    if bridge == "standaard":
        bridge = FakeBridge()
    if bridge is not None:
        bus.modules["client_bridge"] = bridge
    return NtfyMeldingen(
        bus,
        url="http://ntfy.test:8090" if aan else "",
        topic="geheim" if aan else "",
        http_post=NepPost(),
        achtergrond=False,
        zelftest_na_seconden=0,
        opstart_melding=False,
    )


class FakeContext:
    """Nep-context_manager. antwoord kan True/False/tuple zijn, of een fout."""

    def __init__(self, antwoord=False, fout=None, context=None):
        self.antwoord = antwoord
        self.fout = fout
        self.context = context
        self.aantal = 0

    def can_interrupt(self):
        self.aantal += 1
        if self.fout:
            raise self.fout
        return self.antwoord

    def get_current(self):
        return self.context


class FakeGsm:
    """Nep-ntfy-module voor de poort, zonder bridge."""

    def __init__(self, antwoord=True, fout=None):
        self.antwoord = antwoord
        self.fout = fout
        self.aantal = 0

    def gsm_vangt_op(self):
        self.aantal += 1
        if self.fout:
            raise self.fout
        return self.antwoord


def maak_loader(context=None, gsm=None):
    modules = {}
    if context is not None:
        modules["context_manager"] = context
    if gsm is not None:
        modules["ntfy_meldingen"] = gsm
    return SimpleNamespace(loaded_modules=modules)


# ----------------------------------------------------------------
# NtfyMeldingen.gsm_vangt_op()
# ----------------------------------------------------------------

class TestGsmVangtOp:
    def test_actief_op_de_laptop_is_nee(self):
        assert maak_ntfy(FakeBridge()).gsm_vangt_op() is False

    def test_laptop_niet_verbonden_is_ja(self):
        assert maak_ntfy(FakeBridge(verbonden=False)).gsm_vangt_op() is True

    def test_laptop_vergrendeld_is_ja(self):
        assert maak_ntfy(FakeBridge(activiteit="afwezig")).gsm_vangt_op() is True

    @pytest.mark.parametrize("niveau", ["inactief", "onbekend", "weg", ""])
    def test_focus_niet_actief_is_ja(self, niveau):
        assert maak_ntfy(FakeBridge(focus=niveau)).gsm_vangt_op() is True

    def test_bridge_ontbreekt_is_ja(self):
        assert maak_ntfy(None).gsm_vangt_op() is True

    def test_fout_in_de_bridge_is_ja(self):
        assert maak_ntfy(FakeBridge(fout=RuntimeError("stuk"))).gsm_vangt_op() is True

    def test_module_uit_is_altijd_nee(self):
        # Zonder NTFY_URL/NTFY_TOPIC komt er niets op de gsm aan,
        # ook niet als de laptop dicht is.
        assert maak_ntfy(FakeBridge(verbonden=False), aan=False).gsm_vangt_op() is False

    def test_fout_in_laptop_actief_is_nee(self, monkeypatch):
        # Als zelfs de controle zelf crasht, houden we het bij het oude gedrag.
        module = maak_ntfy()

        def stuk():
            raise RuntimeError("boem")

        monkeypatch.setattr(module, "laptop_actief", stuk)
        assert module.gsm_vangt_op() is False


# ----------------------------------------------------------------
# main._layer5_gsm_laat_spreken_toe()
# ----------------------------------------------------------------

class TestPoort:
    # --- het oude gedrag blijft gelijk zonder ntfy-module ---

    def test_zonder_ntfy_layer5_nee_blijft_nee(self):
        assert main._layer5_gsm_laat_spreken_toe(maak_loader(FakeContext(False))) is False

    def test_zonder_ntfy_layer5_ja_blijft_ja(self):
        assert main._layer5_gsm_laat_spreken_toe(maak_loader(FakeContext(True))) is True

    def test_zonder_context_manager_blijft_ja(self):
        assert main._layer5_gsm_laat_spreken_toe(maak_loader()) is True

    def test_zonder_ntfy_fout_blijft_nee(self):
        loader = maak_loader(FakeContext(fout=RuntimeError("stuk")))
        assert main._layer5_gsm_laat_spreken_toe(loader) is False

    def test_zonder_ntfy_tuple_nee_blijft_nee(self):
        loader = maak_loader(FakeContext((False, "ongeschikt moment")))
        assert main._layer5_gsm_laat_spreken_toe(loader) is False

    # --- met ntfy ---

    def test_layer5_nee_maar_gsm_vangt_op_wordt_ja(self):
        gsm = FakeGsm(True)
        assert main._layer5_gsm_laat_spreken_toe(maak_loader(FakeContext(False), gsm)) is True
        assert gsm.aantal == 1

    def test_layer5_nee_en_gsm_vangt_niet_op_blijft_nee(self):
        loader = maak_loader(FakeContext(False), FakeGsm(False))
        assert main._layer5_gsm_laat_spreken_toe(loader) is False

    def test_layer5_ja_vraagt_de_gsm_niet_eens(self):
        gsm = FakeGsm(True)
        assert main._layer5_gsm_laat_spreken_toe(maak_loader(FakeContext(True), gsm)) is True
        assert gsm.aantal == 0

    def test_fout_in_layer5_maar_gsm_vangt_op_wordt_ja(self):
        loader = maak_loader(FakeContext(fout=RuntimeError("stuk")), FakeGsm(True))
        assert main._layer5_gsm_laat_spreken_toe(loader) is True

    def test_fout_in_layer5_en_gsm_vangt_niet_op_blijft_nee(self):
        loader = maak_loader(FakeContext(fout=RuntimeError("stuk")), FakeGsm(False))
        assert main._layer5_gsm_laat_spreken_toe(loader) is False

    def test_tuple_nee_maar_gsm_vangt_op_wordt_ja(self):
        loader = maak_loader(FakeContext((False, "ongeschikt")), FakeGsm(True))
        assert main._layer5_gsm_laat_spreken_toe(loader) is True

    def test_fout_in_gsm_vangt_op_blijft_nee(self):
        loader = maak_loader(FakeContext(False), FakeGsm(fout=RuntimeError("stuk")))
        assert main._layer5_gsm_laat_spreken_toe(loader) is False

    @pytest.mark.parametrize("raar", [1, "ja", [True], object(), None])
    def test_alleen_echt_true_telt(self, raar):
        # Een nep-object (of MagicMock) mag de poort nooit per ongeluk openen.
        loader = maak_loader(FakeContext(False), FakeGsm(raar))
        assert main._layer5_gsm_laat_spreken_toe(loader) is False

    def test_met_echte_ntfy_module_laptop_dicht_wordt_ja(self):
        ntfy = maak_ntfy(FakeBridge(verbonden=False))
        assert main._layer5_gsm_laat_spreken_toe(maak_loader(FakeContext(False), ntfy)) is True

    def test_met_echte_ntfy_module_actief_op_laptop_blijft_nee(self):
        ntfy = maak_ntfy(FakeBridge())
        assert main._layer5_gsm_laat_spreken_toe(maak_loader(FakeContext(False), ntfy)) is False


# ----------------------------------------------------------------
# main._layer5_ochtend_mag_spreken()
# ----------------------------------------------------------------

class TestOchtendPoort:
    def test_ochtend_layer5_nee_maar_gsm_vangt_op_wordt_ja(self):
        context = FakeContext(False, context={"is_afwezig": True})
        assert main._layer5_ochtend_mag_spreken(maak_loader(context, FakeGsm(True))) is True

    def test_ochtend_zonder_ntfy_blijft_nee(self):
        context = FakeContext(False, context={"is_afwezig": True})
        assert main._layer5_ochtend_mag_spreken(maak_loader(context)) is False

    def test_ochtend_gsm_vangt_niet_op_blijft_nee(self):
        context = FakeContext(False, context={"is_afwezig": True})
        assert main._layer5_ochtend_mag_spreken(maak_loader(context, FakeGsm(False))) is False


# ----------------------------------------------------------------
# Het hele pad: RainModule.check_proactief() met de poort uit main.py
# ----------------------------------------------------------------

class TestGewonePoortNegeertGsm:
    def test_gewone_poort_blijft_nee_ook_als_gsm_ontvangt(self):
        loader = maak_loader(FakeContext(False), FakeGsm(True))
        assert main._layer5_laat_spreken_toe(loader) is False

    def test_gewone_poort_vraagt_de_gsm_niet(self):
        gsm = FakeGsm(True)
        main._layer5_laat_spreken_toe(maak_loader(FakeContext(False), gsm))
        assert gsm.aantal == 0


class TestRegenEindeTotEinde:
    NU = datetime(2026, 11, 1, 15, 0)  # middag: buiten de stille uren

    def _poorten(self, loader):
        # Spiegelt achtergrond_loop(): rain krijgt EEN poort, de gsm-poort.
        return {"mag_spreken": lambda: main._layer5_gsm_laat_spreken_toe(loader)}

    def _droog(self):
        from modules.weather.rain import Slot
        return [Slot(self.NU + timedelta(minutes=5 * i), self.NU + timedelta(minutes=5 * (i + 1)), 0.0) for i in range(4)]

    def _regen(self):
        from modules.weather.rain import Slot
        slots = self._droog()
        slots[2] = Slot(slots[2].start, slots[2].einde, 2.0)
        slots[3] = Slot(slots[3].start, slots[3].einde, 2.0)
        return slots

    def _maak(self, monkeypatch, slots, typeinfo=None, gevaar=None):
        from modules.weather import rain
        from modules.weather.rain import RainModule

        monkeypatch.setattr(RainModule, "haal_slots", staticmethod(lambda lat, lon, nu: (slots, False)))
        monkeypatch.setattr(RainModule, "haal_typeinfo", staticmethod(lambda lat, lon: typeinfo or []))
        monkeypatch.setattr(rain, "haal_gevaar", lambda lat, lon: gevaar or [])
        bus = DummyEventBus()
        return RainModule(bus), bus

    def _onweer(self):
        from modules.weather.rain import Kwartier
        start = self.NU + timedelta(minutes=20)
        return [Kwartier(start, start + timedelta(minutes=15), 0.0, 0.0, 95)]

    def _wind(self):
        from modules.weather.rain import Weerpunt
        start = self.NU + timedelta(minutes=30)
        return [Weerpunt(start, start + timedelta(minutes=15), 8.0, 0.0, 18.0, 22.0)]

    # --- gewone regen: overdag ook via de gsm ---

    def test_gewone_regen_zonder_gsm_wordt_tegengehouden(self, monkeypatch):
        module, bus = self._maak(monkeypatch, self._regen())
        loader = maak_loader(FakeContext(False))
        module.check_proactief(nu=self.NU, **self._poorten(loader))
        assert bus.gepubliceerd == []

    def test_gewone_regen_met_gsm_komt_door(self, monkeypatch):
        module, bus = self._maak(monkeypatch, self._regen())
        loader = maak_loader(FakeContext(False), maak_ntfy(FakeBridge(verbonden=False)))
        module.check_proactief(nu=self.NU, **self._poorten(loader))
        assert len(bus.gepubliceerd) == 1
        assert "regenen" in bus.gepubliceerd[0][1]["text"]

    def test_gewone_regen_actief_op_laptop_blijft_tegengehouden(self, monkeypatch):
        module, bus = self._maak(monkeypatch, self._regen())
        loader = maak_loader(FakeContext(False), maak_ntfy(FakeBridge()))
        module.check_proactief(nu=self.NU, **self._poorten(loader))
        assert bus.gepubliceerd == []

    def test_gewone_regen_blijft_stil_in_de_nacht_ook_met_gsm(self, monkeypatch):
        # De stille uren van rain.py (23:00 tot 07:00) gelden los van de poort.
        from modules.weather.rain import Slot
        nacht = datetime(2026, 11, 1, 3, 0)
        slots = [Slot(nacht + timedelta(minutes=5 * i), nacht + timedelta(minutes=5 * (i + 1)), 0.0 if i < 2 else 2.0) for i in range(4)]
        module, bus = self._maak(monkeypatch, slots)
        loader = maak_loader(FakeContext(False), maak_ntfy(FakeBridge(verbonden=False)))
        module.check_proactief(nu=nacht, **self._poorten(loader))
        assert bus.gepubliceerd == []

    def test_gewone_regen_komt_door_als_layer5_ja_zegt(self, monkeypatch):
        module, bus = self._maak(monkeypatch, self._regen())
        loader = maak_loader(FakeContext(True))
        module.check_proactief(nu=self.NU, **self._poorten(loader))
        assert len(bus.gepubliceerd) == 1
        assert "regenen" in bus.gepubliceerd[0][1]["text"]

    # --- onweer en gladheid/wind: de gsm mag Layer 5 omdraaien ---

    def test_onweer_zonder_gsm_wordt_tegengehouden(self, monkeypatch):
        module, bus = self._maak(monkeypatch, self._droog(), typeinfo=self._onweer())
        loader = maak_loader(FakeContext(False))
        module.check_proactief(nu=self.NU, **self._poorten(loader))
        assert bus.gepubliceerd == []

    def test_onweer_met_gsm_komt_door(self, monkeypatch):
        module, bus = self._maak(monkeypatch, self._droog(), typeinfo=self._onweer())
        loader = maak_loader(FakeContext(False), maak_ntfy(FakeBridge(verbonden=False)))
        module.check_proactief(nu=self.NU, **self._poorten(loader))
        assert len(bus.gepubliceerd) == 1
        assert "onweer" in bus.gepubliceerd[0][1]["text"]

    def test_onweer_actief_op_laptop_blijft_tegengehouden(self, monkeypatch):
        module, bus = self._maak(monkeypatch, self._droog(), typeinfo=self._onweer())
        loader = maak_loader(FakeContext(False), maak_ntfy(FakeBridge()))
        module.check_proactief(nu=self.NU, **self._poorten(loader))
        assert bus.gepubliceerd == []

    def test_harde_wind_met_gsm_komt_door(self, monkeypatch):
        module, bus = self._maak(monkeypatch, self._droog(), gevaar=self._wind())
        loader = maak_loader(FakeContext(False), maak_ntfy(FakeBridge(verbonden=False)))
        module.check_proactief(nu=self.NU, **self._poorten(loader))
        assert len(bus.gepubliceerd) == 1
        assert "harde wind" in bus.gepubliceerd[0][1]["text"]

    def test_regen_en_onweer_samen_met_gsm_komen_beide_door_met_een_layer5_vraag(self, monkeypatch):
        module, bus = self._maak(monkeypatch, self._regen(), typeinfo=self._onweer())
        context = FakeContext(False)
        loader = maak_loader(context, maak_ntfy(FakeBridge(verbonden=False)))
        module.check_proactief(nu=self.NU, **self._poorten(loader))
        teksten = " ".join(d["text"] for _, d in bus.gepubliceerd)
        assert "regenen" in teksten and "onweer" in teksten
        assert context.aantal == 1

    def test_zonder_gevaarpoort_gebruikt_onweer_de_gewone_poort(self, monkeypatch):
        # Oude aanroep (enkel mag_spreken): gedrag zoals voor stap 2b.
        module, bus = self._maak(monkeypatch, self._droog(), typeinfo=self._onweer())
        module.check_proactief(nu=self.NU, mag_spreken=lambda: False)
        assert bus.gepubliceerd == []
        module.check_proactief(nu=self.NU, mag_spreken=lambda: True)
        assert len(bus.gepubliceerd) == 1


# ----------------------------------------------------------------
# De bedrading in achtergrond_loop()
# ----------------------------------------------------------------

class _Stop(Exception):
    pass


class TestBedrading:
    def test_rain_en_ochtend_krijgen_de_gsm_poort(self, monkeypatch):
        gezien = {}

        class FakeRain:
            def check_proactief(self, **kwargs):
                gezien["rain"] = kwargs

        class FakeWeather:
            def check_ochtend_samenvatting(self, **kwargs):
                gezien["ochtend"] = kwargs

        oproepen = {"n": 0}

        def slaap(seconden):
            oproepen["n"] += 1
            if oproepen["n"] > 5:   # 5 rondes: rain en ochtend zijn dan aan de beurt
                raise _Stop()

        monkeypatch.setattr(main.time, "sleep", slaap)
        loader = maak_loader(FakeContext(False, context={"is_afwezig": True}), FakeGsm(True))
        loader.loaded_modules["rain"] = FakeRain()
        loader.loaded_modules["weather"] = FakeWeather()
        with pytest.raises(_Stop):
            main.achtergrond_loop(loader)

        assert gezien["rain"]["mag_spreken"]() is True       # Layer 5 nee, gsm ja
        assert gezien["ochtend"]["mag_spreken"]() is True
        loader.loaded_modules["ntfy_meldingen"] = FakeGsm(False)
        assert gezien["rain"]["mag_spreken"]() is False      # gsm vangt niet op