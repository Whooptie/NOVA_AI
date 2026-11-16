# tests/test_module_loader_zacht_falen.py
"""
Tests voor het 'zacht falen' van de module_loader (16 nov 2026).

Een module uit de automatische scan die crasht bij het laden mag Nova niet meer
plat leggen. De loader onthoudt de fout (mislukte_modules), main.py toont een
rode [ FAIL ]-regel en stuurt een melding naar de gsm.

Alles met nep-modules: er wordt niets van de echte data/ aangeraakt.
Uitvoeren: pytest tests/test_module_loader_zacht_falen.py -v
"""

from types import SimpleNamespace

import pytest

import main
from core import module_loader
from core.module_loader import ModuleLoader


class NepBus:
    def __init__(self):
        self.modules = {}

    def register_module(self, naam, instance):
        self.modules[naam] = instance


class NepInstantie:
    pass


def maak_loader():
    return ModuleLoader(NepBus())


def nep_import(monkeypatch, modules):
    """Laat importlib.import_module namen uit 'modules' teruggeven (of de fout die erin staat)."""
    def importeer(naam):
        wat = modules[naam]
        if isinstance(wat, Exception):
            raise wat
        return wat
    monkeypatch.setattr(module_loader.importlib, "import_module", importeer)


def goede_module(argumenten=2):
    if argumenten == 2:
        return SimpleNamespace(init_module=lambda bus, sem=None: NepInstantie())
    return SimpleNamespace(init_module=lambda bus: NepInstantie())


# ---------------------------------------------------------------------------
# _probeer_te_laden
# ---------------------------------------------------------------------------

def test_goede_module_wordt_geladen(monkeypatch):
    nep_import(monkeypatch, {"modules.x.goed": goede_module()})
    loader = maak_loader()
    assert loader._probeer_te_laden("modules.x.goed", "x", "goed", "sem") is True
    assert isinstance(loader.loaded_modules["goed"], NepInstantie)
    assert loader.loaded_modules["goed"].__load_time_ms__ >= 0
    assert "goed" in loader.event_bus.modules
    assert loader.mislukte_modules == {}


def test_module_zonder_sem_parameter_valt_terug(monkeypatch):
    nep_import(monkeypatch, {"modules.x.oud": goede_module(argumenten=1)})
    loader = maak_loader()
    assert loader._probeer_te_laden("modules.x.oud", "x", "oud", "sem") is True
    assert "oud" in loader.loaded_modules


def test_module_zonder_init_module_wordt_overgeslagen(monkeypatch):
    nep_import(monkeypatch, {"modules.x.hulp": SimpleNamespace()})
    loader = maak_loader()
    assert loader._probeer_te_laden("modules.x.hulp", "x", "hulp", "sem") is True
    assert loader.loaded_modules == {} and loader.mislukte_modules == {}


def test_fout_bij_importeren_wordt_onthouden(monkeypatch, capsys):
    nep_import(monkeypatch, {"modules.x.kapot": ImportError("geen module met naam foo")})
    loader = maak_loader()
    assert loader._probeer_te_laden("modules.x.kapot", "x", "kapot", "sem") is False
    assert "kapot" not in loader.loaded_modules
    assert loader.mislukte_modules["kapot"].startswith("ImportError: geen module")
    uit = capsys.readouterr().out
    assert "FOUT: module 'kapot'" in uit and "Traceback" in uit


def test_fout_in_init_module_wordt_onthouden(monkeypatch):
    def stuk(bus, sem=None):
        raise ValueError("kapot bestand")
    nep_import(monkeypatch, {"modules.x.stuk": SimpleNamespace(init_module=stuk)})
    loader = maak_loader()
    assert loader._probeer_te_laden("modules.x.stuk", "x", "stuk", "sem") is False
    assert loader.mislukte_modules["stuk"] == "ValueError: kapot bestand"


def test_fout_in_chat_module_wordt_ook_opgevangen(monkeypatch):
    def stuk(bus, sem):
        raise RuntimeError("chat kapot")
    nep_import(monkeypatch, {"modules.chat.stuk": SimpleNamespace(init_module=stuk)})
    loader = maak_loader()
    assert loader._probeer_te_laden("modules.chat.stuk", "chat", "stuk", "sem") is False
    assert "chat kapot" in loader.mislukte_modules["stuk"]


def test_andere_modules_laden_gewoon_door(monkeypatch):
    def stuk(bus, sem=None):
        raise ValueError("nee")
    nep_import(monkeypatch, {
        "modules.x.a": goede_module(),
        "modules.x.b": SimpleNamespace(init_module=stuk),
        "modules.x.c": goede_module(),
    })
    loader = maak_loader()
    resultaten = [loader._probeer_te_laden(f"modules.x.{n}", "x", n, "sem") for n in "abc"]
    assert resultaten == [True, False, True]
    assert sorted(loader.loaded_modules) == ["a", "c"]
    assert list(loader.mislukte_modules) == ["b"]


def test_ctrl_c_wordt_niet_ingeslikt(monkeypatch):
    def stop(bus, sem=None):
        raise KeyboardInterrupt()
    nep_import(monkeypatch, {"modules.x.stop": SimpleNamespace(init_module=stop)})
    loader = maak_loader()
    with pytest.raises(KeyboardInterrupt):
        loader._probeer_te_laden("modules.x.stop", "x", "stop", "sem")


def test_reden_is_kort_en_op_een_regel(monkeypatch):
    nep_import(monkeypatch, {"modules.x.lang": ValueError("regel een\nregel twee " + "x" * 500)})
    loader = maak_loader()
    loader._probeer_te_laden("modules.x.lang", "x", "lang", "sem")
    reden = loader.mislukte_modules["lang"]
    assert "\n" not in reden and len(reden) <= 150


def test_nieuwe_loader_begint_zonder_mislukte_modules():
    assert maak_loader().mislukte_modules == {}


# ---------------------------------------------------------------------------
# main.py: banner en gsm-melding
# ---------------------------------------------------------------------------

def test_banner_regels_leeg_als_alles_goed_ging():
    assert main.mislukte_modules_regels(SimpleNamespace(mislukte_modules={})) == []


def test_banner_regels_tonen_naam_en_reden_alfabetisch():
    loader = SimpleNamespace(mislukte_modules={"weer": "KeyError: x", "agenda": "OSError: y"})
    regels = main.mislukte_modules_regels(loader)
    assert len(regels) == 2
    assert "[ FAIL ]" in regels[0] and "agenda" in regels[0] and "OSError: y" in regels[0]
    assert "weer" in regels[1]


def test_banner_regels_zonder_attribuut_geven_niets():
    assert main.mislukte_modules_regels(SimpleNamespace()) == []


class NepNtfy:
    def __init__(self, gelukt=True):
        self.berichten, self.gelukt = [], gelukt

    def _verstuur(self, tekst, meld_fout=True):
        self.berichten.append((tekst, meld_fout))
        return self.gelukt


def test_melding_wordt_niet_gestuurd_als_alles_goed_ging():
    ntfy = NepNtfy()
    loader = SimpleNamespace(mislukte_modules={}, loaded_modules={"ntfy_meldingen": ntfy})
    assert main.meld_mislukte_modules(loader) is False and ntfy.berichten == []


def test_melding_noemt_de_modules():
    ntfy = NepNtfy()
    loader = SimpleNamespace(mislukte_modules={"weer": "x", "agenda": "y"},
                             loaded_modules={"ntfy_meldingen": ntfy})
    assert main.meld_mislukte_modules(loader) is True
    tekst, meld_fout = ntfy.berichten[0]
    assert "2 module(s)" in tekst and "agenda, weer" in tekst and meld_fout is False


def test_melding_zonder_ntfy_gooit_geen_fout(capsys):
    loader = SimpleNamespace(mislukte_modules={"weer": "x"}, loaded_modules={})
    assert main.meld_mislukte_modules(loader) is False
    assert "ntfy_meldingen is niet geladen" in capsys.readouterr().out


def test_melding_mislukt_zonder_crash():
    class Stuk:
        def _verstuur(self, tekst, meld_fout=True):
            raise OSError("geen netwerk")
    loader = SimpleNamespace(mislukte_modules={"weer": "x"}, loaded_modules={"ntfy_meldingen": Stuk()})
    assert main.meld_mislukte_modules(loader) is False


def test_melding_geeft_false_als_versturen_mislukt():
    loader = SimpleNamespace(mislukte_modules={"weer": "x"},
                             loaded_modules={"ntfy_meldingen": NepNtfy(gelukt=False)})
    assert main.meld_mislukte_modules(loader) is False