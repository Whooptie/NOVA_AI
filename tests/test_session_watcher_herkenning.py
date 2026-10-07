# tests/test_session_watcher_herkenning.py
"""
Herkenningsreactie "je werkt aan mijn eigen broncode" (7 oktober 2026).

Controleert:
- max 1x per dag, ook na een uitstapje naar een ander herkend venster
- ook na een herstart (nieuwe SessionWatcher, zelfde state-bestand)
- een nieuwe dag mag opnieuw
- niet vlak na een bericht van Kevin, en dan ook niet als "gegeven" geteld
"""
import json
import time
from datetime import date, timedelta

import pytest

from modules.activity.session_watcher import SessionWatcher


class FakeBus:
    """Minimale EventBus: onthoudt enkel wat er gepubliceerd wordt."""

    def __init__(self):
        self.gepubliceerd = []
        self.modules = {}  # geen focus_detector -> Kevin telt als actief

    def subscribe(self, event_type, callback):
        pass

    def publish(self, event_type, data):
        self.gepubliceerd.append((event_type, data))


def _herkenningen(bus):
    """Telt enkel de herkenningsreacties (chat_response met een sjabloon-midden)."""
    middens = SessionWatcher._sjablonen_werken_aan_nova["midden"]
    return [
        d["text"] for (t, d) in bus.gepubliceerd
        if t == "chat_response" and any(m in d.get("text", "") for m in middens)
    ]


def _activiteit(watcher, naam):
    watcher._on_any_event({"naam": naam}, event_type=f"activity_started:{naam}")


@pytest.fixture
def state_pad(tmp_path, monkeypatch):
    pad = tmp_path / "session_watcher_state.json"
    monkeypatch.setattr(SessionWatcher, "HERKENNING_STATE_BESTAND", str(pad))
    return pad


def test_eerste_keer_geeft_reactie_en_bewaart_dag(state_pad):
    bus = FakeBus()
    watcher = SessionWatcher(bus)

    _activiteit(watcher, "werken_aan_nova_gedetecteerd")

    assert len(_herkenningen(bus)) == 1
    bewaard = json.loads(state_pad.read_text(encoding="utf-8"))
    assert bewaard["herkenning_laatste_dag"] == date.today().isoformat()


def test_uitstapje_naar_ander_venster_geeft_geen_tweede_reactie(state_pad):
    bus = FakeBus()
    watcher = SessionWatcher(bus)

    _activiteit(watcher, "werken_aan_nova_gedetecteerd")
    _activiteit(watcher, "talking_to_nova_gedetecteerd")
    _activiteit(watcher, "werken_aan_nova_gedetecteerd")
    _activiteit(watcher, "bestanden_beheren_gedetecteerd")
    _activiteit(watcher, "werken_aan_nova_gedetecteerd")

    assert len(_herkenningen(bus)) == 1
    # De activiteit zelf wordt wel nog gewoon bijgehouden (oud gedrag).
    assert watcher.actieve_activiteit == "werken_aan_nova_gedetecteerd"


def test_na_herstart_zelfde_dag_geen_reactie(state_pad):
    bus1 = FakeBus()
    _activiteit(SessionWatcher(bus1), "werken_aan_nova_gedetecteerd")
    assert len(_herkenningen(bus1)) == 1

    # "Herstart": nieuwe instantie, zelfde state-bestand.
    bus2 = FakeBus()
    _activiteit(SessionWatcher(bus2), "werken_aan_nova_gedetecteerd")
    assert len(_herkenningen(bus2)) == 0


def test_nieuwe_dag_mag_opnieuw(state_pad):
    gisteren = (date.today() - timedelta(days=1)).isoformat()
    state_pad.write_text(
        json.dumps({"herkenning_laatste_dag": gisteren}), encoding="utf-8"
    )

    bus = FakeBus()
    _activiteit(SessionWatcher(bus), "werken_aan_nova_gedetecteerd")

    assert len(_herkenningen(bus)) == 1


def test_vlak_na_bericht_van_kevin_geen_reactie_maar_later_wel(state_pad):
    bus = FakeBus()
    watcher = SessionWatcher(bus)

    # De paraplu-situatie van 5 oktober: bericht, en meteen daarna
    # komt VS Code weer op de voorgrond.
    watcher._on_any_event(
        {"text": "hey wat hoeveel hyey over mijn paraplu"},
        event_type="raw_user_message",
    )
    _activiteit(watcher, "werken_aan_nova_gedetecteerd")

    assert len(_herkenningen(bus)) == 0
    assert not state_pad.exists()  # niet als "gegeven" geteld

    # Later, na een rustig moment: het bericht is lang genoeg geleden.
    watcher._laatste_bericht_kevin = time.time() - (
        SessionWatcher.HERKENNING_STIL_NA_BERICHT_SECONDEN + 10
    )
    _activiteit(watcher, "talking_to_nova_gedetecteerd")
    _activiteit(watcher, "werken_aan_nova_gedetecteerd")

    assert len(_herkenningen(bus)) == 1


def test_kapot_state_bestand_crasht_niet(state_pad):
    state_pad.write_text("{dit is geen json", encoding="utf-8")

    bus = FakeBus()
    _activiteit(SessionWatcher(bus), "werken_aan_nova_gedetecteerd")

    assert len(_herkenningen(bus)) == 1