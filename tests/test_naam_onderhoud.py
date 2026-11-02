import json
import pytest

from modules.knowledge import naam_onderhoud as no


class FakeBus:
    def __init__(self):
        self.modules = {}
        self.berichten = []

    def publish(self, event, payload):
        self.berichten.append((event, payload))


class FakePM:
    def __init__(self, patronen):
        self.patronen = patronen

    def get_all_patterns(self):
        return self.patronen


class FakeCM:
    def __init__(self, ok=True):
        self.ok = ok

    def can_interrupt(self):
        return self.ok


class FakeEM:
    """Gebruikt de echte beoordeel_naam-logica via een mini-versie."""
    def __init__(self):
        from modules.experimental.emergence_engine import EmergenceEngine
        self.echt = EmergenceEngine.__new__(EmergenceEngine)
        self.echt.INSIGHT_WAARDIGE_ACTIVITEITEN = {"schaken"}
        self.echt.BEWUST_UITGESLOTEN_ACTIVITEITEN = {"unknown_gedetecteerd"}
        self.echt.DYNAMISCHE_TOPIC_VOORVOEGSELS = ("definitie_", "open_app_")
        self.echt._topic_naam_labels = {"chess": "schaken"}

    def beoordeel_naam(self, et):
        return self.echt.beoordeel_naam(et)


def maak(tmp_path, patronen, cm_ok=True):
    bus = FakeBus()
    bus.modules["pattern_matcher"] = FakePM(patronen)
    bus.modules["emergence_engine"] = FakeEM()
    bus.modules["context_manager"] = FakeCM(cm_ok)
    return bus, no.NaamOnderhoud(
        bus, state_pad=str(tmp_path / "s.json"), start_thread=False)


def p(total):
    return {"total": total}


def test_meldt_nieuwe_activiteit_en_topic(tmp_path):
    bus, n = maak(tmp_path, {
        "activity_started:gamen": p(5),
        "topic_detected:weer2": p(4),
    })
    tekst = n.check_nieuwe_namen()
    assert "gamen" in tekst and "weer2" in tekst
    assert bus.berichten[0][0] == "chat_response"


def test_onder_drempel_en_bekende_namen_stil(tmp_path):
    bus, n = maak(tmp_path, {
        "activity_started:gamen": p(3),
        "activity_started:schaken": p(50),
        "activity_started:unknown_gedetecteerd": p(50),
        "topic_detected:chess": p(50),
        "topic_detected:definitie_kat": p(50),
        "topic_detected:open_app_chrome": p(50),
        "chat_message": p(500),
    })
    assert n.check_nieuwe_namen() is None
    assert bus.berichten == []


def test_niet_twee_keer_melden_en_persistent(tmp_path):
    bus, n = maak(tmp_path, {"activity_started:gamen": p(9)})
    assert n.check_nieuwe_namen() is not None
    assert n.check_nieuwe_namen() is None
    n2 = no.NaamOnderhoud(bus, state_pad=str(tmp_path / "s.json"),
                          start_thread=False)
    assert n2.check_nieuwe_namen() is None
    assert "activity_started:gamen" in json.load(
        open(tmp_path / "s.json"))["gemeld"]


def test_niet_melden_als_interrupt_niet_mag(tmp_path):
    bus, n = maak(tmp_path, {"activity_started:gamen": p(9)}, cm_ok=False)
    assert n.check_nieuwe_namen() is None
    bus.modules["context_manager"].ok = True
    assert n.check_nieuwe_namen() is not None


def test_max_namen_per_bericht(tmp_path):
    patronen = {f"activity_started:a{i}": p(10 + i) for i in range(15)}
    bus, n = maak(tmp_path, patronen)
    n.check_nieuwe_namen()
    assert len(n.gemeld) == no.MAX_NAMEN_PER_BERICHT
    n.check_nieuwe_namen()
    assert len(n.gemeld) == 15


def test_ontbrekende_modules_geen_crash(tmp_path):
    bus = FakeBus()
    n = no.NaamOnderhoud(bus, state_pad=str(tmp_path / "s.json"),
                         start_thread=False)
    assert n.check_nieuwe_namen() is None