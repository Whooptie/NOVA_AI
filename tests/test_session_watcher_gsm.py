# tests/test_session_watcher_gsm.py
"""
3 november 2026: de pauze-melding ("30 minuten verder zonder pauze") mag niet
komen als ntfy_meldingen zegt dat Kevin niet vers actief is op de laptop
(laptop net dichtgeklapt, focusdata nog "geldig" in de bridge).
"""

import pytest

from modules.activity import session_watcher as sw
from modules.activity.session_watcher import SessionWatcher


class DummyBus:
    def __init__(self):
        self.modules = {}
        self.events = []

    def subscribe(self, event_type, handler):
        pass

    def publish(self, event_type, data=None):
        self.events.append((event_type, data or {}))

    def teksten(self):
        return [d.get("text") for t, d in self.events if t == "chat_response"]


class FakeFocus:
    def __init__(self, niveau="actief"):
        self.niveau = niveau

    def get_focus_info(self):
        return {"focus_level": self.niveau}


class FakeContext:
    def __init__(self, mag=True):
        self.mag = mag

    def can_interrupt(self):
        return self.mag


class FakeNtfy:
    def __init__(self, antwoord=True, fout=False):
        self.antwoord = antwoord
        self.fout = fout

    def gsm_vangt_op(self):
        if self.fout:
            raise RuntimeError("kapot")
        return self.antwoord


class Klok:
    def __init__(self):
        self.nu = 1_000_000.0

    def __call__(self):
        return self.nu

    def verder(self, minuten):
        self.nu += minuten * 60


@pytest.fixture
def klok(monkeypatch):
    k = Klok()
    monkeypatch.setattr(sw.time, "time", k)
    return k


@pytest.fixture
def opzet(tmp_path, klok, monkeypatch):
    monkeypatch.setattr(SessionWatcher, "HERKENNING_STATE_BESTAND", str(tmp_path / "state.json"))
    bus = DummyBus()
    bus.modules["focus_detector"] = FakeFocus("actief")
    watcher = SessionWatcher(bus, context_manager=FakeContext(True))
    return bus, watcher, klok


def start_sessie_en_wacht_30_min(watcher, klok):
    watcher.check_pauze()           # sessie start
    klok.verder(31)
    # tussendoor blijft focus actief; check_pauze draait elke minuut, maar een
    # enkele check na 31 minuten is genoeg voor deze situatie.


class TestPauzeMetGsmPoort:
    def test_ntfy_zegt_niet_actief_dan_geen_melding(self, opzet):
        bus, watcher, klok = opzet
        bus.modules["ntfy_meldingen"] = FakeNtfy(True)
        start_sessie_en_wacht_30_min(watcher, klok)
        watcher.check_pauze()
        assert bus.teksten() == []

    def test_ntfy_zegt_wel_actief_dan_wel_melding(self, opzet):
        bus, watcher, klok = opzet
        bus.modules["ntfy_meldingen"] = FakeNtfy(False)
        start_sessie_en_wacht_30_min(watcher, klok)
        watcher.check_pauze()
        assert len(bus.teksten()) == 1
        assert "31" in bus.teksten()[0] or "30" in bus.teksten()[0]

    def test_zonder_ntfy_module_blijft_het_oude_gedrag(self, opzet):
        bus, watcher, klok = opzet
        start_sessie_en_wacht_30_min(watcher, klok)
        watcher.check_pauze()
        assert len(bus.teksten()) == 1

    def test_fout_in_ntfy_geeft_het_oude_gedrag(self, opzet):
        bus, watcher, klok = opzet
        bus.modules["ntfy_meldingen"] = FakeNtfy(fout=True)
        start_sessie_en_wacht_30_min(watcher, klok)
        watcher.check_pauze()
        assert len(bus.teksten()) == 1

    @pytest.mark.parametrize("antwoord", [None, False, "ja", 1])
    def test_enkel_een_echte_true_blokkeert(self, opzet, antwoord):
        bus, watcher, klok = opzet
        bus.modules["ntfy_meldingen"] = FakeNtfy(antwoord)
        start_sessie_en_wacht_30_min(watcher, klok)
        watcher.check_pauze()
        assert len(bus.teksten()) == 1

    def test_melding_komt_zodra_kevin_weer_vers_actief_is(self, opzet):
        bus, watcher, klok = opzet
        ntfy = FakeNtfy(True)
        bus.modules["ntfy_meldingen"] = ntfy
        start_sessie_en_wacht_30_min(watcher, klok)
        watcher.check_pauze()
        assert bus.teksten() == []
        assert watcher.laatste_melding_time is None   # wachttijd niet "verbruikt"
        ntfy.antwoord = False
        klok.verder(1)
        watcher.check_pauze()
        assert len(bus.teksten()) == 1

    def test_wachtregel_komt_hoogstens_een_keer_per_sessie_in_de_log(self, opzet, capsys):
        bus, watcher, klok = opzet
        bus.modules["ntfy_meldingen"] = FakeNtfy(True)
        start_sessie_en_wacht_30_min(watcher, klok)
        for _ in range(5):
            watcher.check_pauze()
            klok.verder(1)
        assert capsys.readouterr().out.count("Pauze-melding wacht") == 1

    def test_layer5_blijft_ook_gelden(self, opzet):
        bus, watcher, klok = opzet
        watcher.context_manager = FakeContext(False)
        bus.modules["ntfy_meldingen"] = FakeNtfy(False)
        start_sessie_en_wacht_30_min(watcher, klok)
        watcher.check_pauze()
        assert bus.teksten() == []

    def test_kort_dicht_klappen_houdt_de_sessie_in_stand(self, opzet):
        # Laptop 5 minuten dicht (minder dan PAUZE_RESET_SECONDEN): de sessie
        # loopt door, de melding wacht en komt bij terugkomst.
        bus, watcher, klok = opzet
        ntfy = FakeNtfy(False)
        bus.modules["ntfy_meldingen"] = ntfy
        watcher.check_pauze()
        klok.verder(26)
        watcher.check_pauze()
        ntfy.antwoord = True
        bus.modules["focus_detector"].niveau = "actief"   # bridge-data nog "geldig"
        klok.verder(5)
        watcher.check_pauze()
        assert bus.teksten() == []
        ntfy.antwoord = False
        klok.verder(1)
        watcher.check_pauze()
        assert len(bus.teksten()) == 1