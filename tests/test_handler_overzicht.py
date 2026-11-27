# tests/test_handler_overzicht.py
# Test het telwerk van "handlers debug" (modules/debug/handler_overzicht.py)
# en dat het commando herkend wordt.

from modules.debug.handler_overzicht import maak_tekst, tel_handlers
from modules.debug.debug_commands import DebugCommands


class A:
    def een(self, data):
        pass

    def twee(self, data):
        pass


class B:
    def drie(self, data, event_type):
        pass


def los(data):
    pass


def test_leeg():
    t = tel_handlers({})
    assert t["handlers"] == 0 and t["abonnementen"] == 0 and t["events"] == 0
    assert t["per_module"] == []
    assert t["wildcard"] == 0


def test_none_geeft_geen_crash():
    assert tel_handlers(None)["handlers"] == 0


def test_dezelfde_functie_op_drie_events_is_een_handler():
    a = A()
    t = tel_handlers({"x": [a.een], "y": [a.een], "z": [a.een]})
    assert t["handlers"] == 1
    assert t["abonnementen"] == 3
    assert t["events"] == 3


def test_twee_objecten_van_dezelfde_klasse_zijn_twee_handlers():
    t = tel_handlers({"x": [A().een, A().een]})
    assert t["handlers"] == 2


def test_verschillende_methodes_zijn_verschillende_handlers():
    a = A()
    t = tel_handlers({"x": [a.een, a.twee]})
    assert t["handlers"] == 2


def test_wildcard_wordt_apart_geteld():
    a = A()
    t = tel_handlers({"*": [a.een, los], "x": [a.een]})
    assert t["wildcard"] == 2
    assert t["handlers"] == 2
    assert t["abonnementen"] == 3


def test_lege_lijst_telt_niet_als_event():
    t = tel_handlers({"x": [], "y": [los]})
    assert t["events"] == 1


def test_per_module_grootste_eerst():
    a, b = A(), B()
    t = tel_handlers({"x": [a.een, a.twee, b.drie]})
    assert t["per_module"][0][1] == 3           # alles staat in dit testbestand
    assert t["per_module"][0][0] == __name__


def test_ongeldige_handler_zonder_module_crasht_niet():
    class Zonder:
        __module__ = None

        def __call__(self, data):
            pass

    t = tel_handlers({"x": [Zonder()]})
    assert t["handlers"] == 1
    assert t["per_module"][0][0] == "(onbekend)"


def test_tekst_bevat_de_getallen():
    a = A()
    tekst = maak_tekst({"*": [a.een], "x": [a.een, a.twee]}, aantal_geladen=70)
    assert "Unieke handlers: 2" in tekst
    assert "Abonnementen (functie op een event): 3" in tekst
    assert "Handlers op '*' (luisteren naar alles): 1" in tekst
    assert "Geladen modules: 70" in tekst


def test_tekst_zonder_aantal_geladen():
    assert "Geladen modules" not in maak_tekst({"x": [los]})


def test_top_beperkt_het_aantal_regels():
    subs = {"x": [A().een for _ in range(3)]}
    tekst = maak_tekst(subs, top=1)
    assert "top 1" in tekst


# ----- het commando zelf -----

class EchteBus:
    def __init__(self):
        self._subscribers = {"x": [los]}

    def subscribe(self, *a, **k):
        pass


class StubLoader:
    loaded_modules = {"een": object(), "twee": object()}


def test_commando_wordt_herkend():
    dc = DebugCommands(EchteBus(), StubLoader())
    assert dc.is_debug_command("handlers debug")
    assert dc.is_debug_command("Handlers Debug")
    assert not dc.is_debug_command("handlers")


def test_commando_print_overzicht(capsys):
    dc = DebugCommands(EchteBus(), StubLoader())
    dc.handle_debug_command({"text": "handlers debug"})
    uit = capsys.readouterr().out
    assert "Unieke handlers: 1" in uit
    assert "Geladen modules: 2" in uit


def test_commando_zonder_subscribers_attribuut_crasht_niet(capsys):
    class ZonderAttr:
        def subscribe(self, *a, **k):
            pass

    dc = DebugCommands(ZonderAttr(), StubLoader())
    dc.handle_debug_command({"text": "handlers debug"})
    assert "Unieke handlers: 0" in capsys.readouterr().out