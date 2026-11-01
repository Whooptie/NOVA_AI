# tests/test_debug_datum_terugblik.py
# Test de debugcommando's 'datum terugblik' en 'datum terugblik forceer'.

from modules.debug.debug_commands import DebugCommands


class StubBus:
    def subscribe(self, *a, **k):
        pass


class StubLoader:
    def __init__(self, modules):
        self.loaded_modules = modules


class StubTerugblik:
    def __init__(self, resultaat=(True, "gemeld")):
        self.resultaat = resultaat
        self.forceer_aangeroepen = False

    def status_tekst(self):
        return "Modus: aan\nDatum: 1 november 2026"

    def check_nu(self, forceer=False):
        self.forceer_aangeroepen = forceer
        return self.resultaat


def maak(modules):
    return DebugCommands(StubBus(), StubLoader(modules))


def test_commando_wordt_herkend():
    dc = maak({})
    assert dc.is_debug_command("datum terugblik")
    assert dc.is_debug_command("Datum Terugblik Forceer")
    assert not dc.is_debug_command("terugblik")


def test_status_wordt_getoond(capsys):
    dc = maak({"datum_terugblik": StubTerugblik()})
    dc.handle_debug_command({"text": "datum terugblik"})
    uit = capsys.readouterr().out
    assert "Datum-terugblik" in uit and "1 november 2026" in uit


def test_forceer_meldt(capsys):
    stub = StubTerugblik((True, "gemeld"))
    dc = maak({"datum_terugblik": stub})
    dc.handle_debug_command({"text": "datum terugblik forceer"})
    assert stub.forceer_aangeroepen is True
    assert "gemeld" in capsys.readouterr().out.lower()


def test_forceer_zonder_treffer_toont_reden(capsys):
    dc = maak({"datum_terugblik": StubTerugblik((False, "geen sterke overeenkomst"))})
    dc.handle_debug_command({"text": "datum terugblik forceer"})
    assert "geen sterke overeenkomst" in capsys.readouterr().out


def test_module_ontbreekt(capsys):
    dc = maak({})
    dc.handle_debug_command({"text": "datum terugblik"})
    dc.handle_debug_command({"text": "datum terugblik forceer"})
    assert capsys.readouterr().out.count("niet gevonden") == 2