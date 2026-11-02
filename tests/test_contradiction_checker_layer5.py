# tests/test_contradiction_checker_layer5.py
# Test de Layer 5-poort van ContradictionChecker met lichte stubs.

from modules.knowledge.contradiction_checker import ContradictionChecker

CONFLICT = {"word": "kat", "conflict": ["dier", "meubel"]}


class StubBus:
    def __init__(self, modules=None):
        self.gepubliceerd = []
        self.modules = modules if modules is not None else {}

    def publish(self, naam, data=None):
        self.gepubliceerd.append((naam, data))


class BusZonderModules:
    def __init__(self):
        self.gepubliceerd = []

    def publish(self, naam, data=None):
        self.gepubliceerd.append((naam, data))


class StubContext:
    def __init__(self, mag):
        self.mag = mag

    def can_interrupt(self):
        return self.mag


class KapotContext:
    def can_interrupt(self):
        raise RuntimeError("stuk")


class StubStore:
    def __init__(self, woorden):
        self.concepts = {w: {} for w in woorden}


class StubSemantic:
    def __init__(self):
        self.store = StubStore(["kat"])

    def find_contradictions(self, woord):
        return [dict(CONFLICT)] if woord == "kat" else []


def maak_checker(tmp_path, bus):
    checker = ContradictionChecker(bus, StubSemantic())
    checker.state_pad = tmp_path / "state.json"      # nooit de echte state aanraken
    checker._al_gemelde_conflicten = set()
    return checker


def test_layer5_zegt_nee_dan_geen_melding_en_niet_als_gemeld_gemarkeerd(tmp_path):
    bus = StubBus({"context_manager": StubContext(False)})
    checker = maak_checker(tmp_path, bus)
    checker.check_contradictions()
    assert bus.gepubliceerd == []
    assert checker._al_gemelde_conflicten == set()


def test_layer5_zegt_ja_dan_melding(tmp_path):
    bus = StubBus({"context_manager": StubContext(True)})
    checker = maak_checker(tmp_path, bus)
    checker.check_contradictions()
    assert len(bus.gepubliceerd) == 1
    assert bus.gepubliceerd[0][0] == "layer4_response"


def test_zonder_context_manager_blijft_het_werken(tmp_path):
    bus = StubBus({})
    checker = maak_checker(tmp_path, bus)
    checker.check_contradictions()
    assert len(bus.gepubliceerd) == 1


def test_bus_zonder_modules_attribuut_blijft_het_werken(tmp_path):
    bus = BusZonderModules()
    checker = maak_checker(tmp_path, bus)
    checker.check_contradictions()
    assert len(bus.gepubliceerd) == 1


def test_kapotte_context_manager_blokkeert_niet(tmp_path):
    bus = StubBus({"context_manager": KapotContext()})
    checker = maak_checker(tmp_path, bus)
    checker.check_contradictions()
    assert len(bus.gepubliceerd) == 1


def test_eerst_nee_dan_ja_meldt_alsnog_en_daarna_niet_dubbel(tmp_path):
    ctx = StubContext(False)
    bus = StubBus({"context_manager": ctx})
    checker = maak_checker(tmp_path, bus)
    checker.check_contradictions()
    assert bus.gepubliceerd == []
    ctx.mag = True
    checker.check_contradictions()
    assert len(bus.gepubliceerd) == 1
    checker.check_contradictions()          # spam-preventie blijft werken
    assert len(bus.gepubliceerd) == 1


def test_meegegeven_mag_spreken_heeft_voorrang(tmp_path):
    bus = StubBus({"context_manager": StubContext(True)})
    checker = maak_checker(tmp_path, bus)
    checker.check_contradictions(mag_spreken=lambda: False)
    assert bus.gepubliceerd == []
    checker.check_contradictions(mag_spreken=lambda: True)
    assert len(bus.gepubliceerd) == 1


def test_mag_spreken_ja_overrulet_layer5_nee(tmp_path):
    # Dit is het gsm-geval: Layer 5 zegt nee, maar de gsm vangt het bericht op.
    bus = StubBus({"context_manager": StubContext(False)})
    checker = maak_checker(tmp_path, bus)
    checker.check_contradictions(mag_spreken=lambda: True)
    assert len(bus.gepubliceerd) == 1