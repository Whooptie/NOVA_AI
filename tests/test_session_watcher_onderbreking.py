# tests/test_session_watcher_onderbreking.py
"""
Tests voor session_watcher.py, check_activity_interruption():

1. Layer 5-controle: geen "mag ik storen?"-vraag als
   context_manager.can_interrupt() False geeft (bv. Kevin zit in een
   ander venster, of de laptop is dichtgeklapt), en beslis_interruption_
   gedrag() wordt dan NIET eens aangeroepen (anders zou
   variant_feedback_logger een nooit getoonde zin loggen).
2. talking_to_nova_gedetecteerd krijgt nooit een onderbrekingsvraag.
3. Na een echte pauze (PAUZE_RESET_SECONDEN geen actieve focus) begint
   de teller van de lopende activiteit opnieuw.

Isolatie: echte SessionWatcher, maar met nep-lagen (FakeContextManager,
FakeResponseEngine, FakePendingQuestion, FakeFocusDetector) en een
nep-EventBus. Het state-bestand van de herkenningsreactie wordt naar
tmp_path omgeleid.
"""

import time

import pytest

from modules.activity.session_watcher import SessionWatcher


class DummyEventBus:
    def __init__(self):
        self.modules = {}
        self.gepubliceerd = []

    def subscribe(self, event_type, callback):
        pass

    def publish(self, event_type, data=None):
        self.gepubliceerd.append((event_type, data))

    def teksten(self):
        return [d["text"] for (e, d) in self.gepubliceerd if e == "chat_response"]


class FakeContextManager:
    def __init__(self, mag=True):
        self.mag = mag
        self.aantal_vragen = 0

    def can_interrupt(self):
        self.aantal_vragen += 1
        return self.mag


class KapotteContextManager:
    def can_interrupt(self):
        raise RuntimeError("kapot")


class FakeResponseEngine:
    def __init__(self, actie="vraag_eerst"):
        self.actie = actie
        self.aanroepen = []

    def beslis_interruption_gedrag(self, activiteit, tijd_sinds_start=None):
        self.aanroepen.append((activiteit, tijd_sinds_start))
        if self.actie == "blijf_stil":
            return {"actie": "blijf_stil", "tekst": None, "confidence": 0.1}
        if self.actie == "ga_gewoon_door":
            return {"actie": "ga_gewoon_door", "tekst": "Alles onder controle?", "confidence": 0.9}
        return {"actie": "vraag_eerst", "tekst": "Mag ik storen?", "confidence": None}


class FakePendingQuestion:
    def __init__(self):
        self.gezet = []

    def is_open(self):
        return False

    def set(self, vraag_type, verval_seconden=None):
        self.gezet.append((vraag_type, verval_seconden))


class FakeFocusDetector:
    def __init__(self, niveau="actief"):
        self.niveau = niveau

    def get_focus_info(self):
        return {"focus_level": self.niveau}


class Opstelling:
    pass


@pytest.fixture
def opstelling(tmp_path, monkeypatch):
    # Absoluut pad: _PROJECT_ROOT / "/abs/pad" blijft "/abs/pad".
    monkeypatch.setattr(
        SessionWatcher, "HERKENNING_STATE_BESTAND", str(tmp_path / "sw_state.json")
    )
    o = Opstelling()
    o.bus = DummyEventBus()
    o.engine = FakeResponseEngine()
    o.pending = FakePendingQuestion()
    o.focus = FakeFocusDetector("actief")
    o.ctx = FakeContextManager(mag=True)
    o.bus.modules["response_engine"] = o.engine
    o.bus.modules["pending_question"] = o.pending
    o.bus.modules["focus_detector"] = o.focus
    o.watcher = SessionWatcher(o.bus, context_manager=o.ctx)
    return o


def zet_activiteit(watcher, naam="werken_aan_nova_gedetecteerd", minuten_geleden=20):
    """Zet een activiteit die al langer dan de 15-minutengrens loopt."""
    watcher.actieve_activiteit = naam
    watcher.activiteit_start_tijd = time.time() - minuten_geleden * 60
    watcher._al_gevraagd_voor_activiteit = None


# ---------------------------------------------------------------
# Layer 5: can_interrupt()
# ---------------------------------------------------------------

def test_geen_vraag_als_can_interrupt_false(opstelling):
    o = opstelling
    o.ctx.mag = False
    zet_activiteit(o.watcher)
    o.watcher.check_activity_interruption()
    assert o.bus.teksten() == []
    assert o.pending.gezet == []


def test_uitstel_roept_beslis_interruption_gedrag_niet_aan(opstelling):
    o = opstelling
    o.ctx.mag = False
    zet_activiteit(o.watcher)
    o.watcher.check_activity_interruption()
    assert o.engine.aanroepen == []


def test_uitstel_zet_vlag_niet_en_vraag_komt_later_alsnog(opstelling):
    o = opstelling
    o.ctx.mag = False
    zet_activiteit(o.watcher)
    o.watcher.check_activity_interruption()
    assert o.watcher._al_gevraagd_voor_activiteit is None

    o.ctx.mag = True
    o.watcher.check_activity_interruption()
    assert o.bus.teksten() == ["Mag ik storen?"]
    assert o.pending.gezet == [("mag_ik_storen", 120)]
    assert o.watcher._al_gevraagd_voor_activiteit == "werken_aan_nova_gedetecteerd"


def test_vraag_komt_als_can_interrupt_true(opstelling):
    o = opstelling
    zet_activiteit(o.watcher)
    o.watcher.check_activity_interruption()
    assert o.bus.teksten() == ["Mag ik storen?"]
    assert len(o.engine.aanroepen) == 1


def test_zonder_context_manager_blijft_nova_vragen(opstelling):
    o = opstelling
    o.watcher.context_manager = None
    zet_activiteit(o.watcher)
    o.watcher.check_activity_interruption()
    assert o.bus.teksten() == ["Mag ik storen?"]


def test_fout_in_can_interrupt_is_fail_open(opstelling):
    o = opstelling
    o.watcher.context_manager = KapotteContextManager()
    zet_activiteit(o.watcher)
    o.watcher.check_activity_interruption()
    assert o.bus.teksten() == ["Mag ik storen?"]


def test_uitstel_melding_slechts_eenmaal_per_activiteit(opstelling, capsys):
    o = opstelling
    o.ctx.mag = False
    zet_activiteit(o.watcher)
    capsys.readouterr()  # eerdere uitvoer wissen
    o.watcher.check_activity_interruption()
    o.watcher.check_activity_interruption()
    o.watcher.check_activity_interruption()
    uitvoer = capsys.readouterr().out
    assert uitvoer.count("uitgesteld door Layer 5") == 1


def test_blijf_stil_zet_vlag_en_zegt_niets(opstelling):
    o = opstelling
    o.engine.actie = "blijf_stil"
    zet_activiteit(o.watcher)
    o.watcher.check_activity_interruption()
    assert o.bus.teksten() == []
    assert o.pending.gezet == []
    assert o.watcher._al_gevraagd_voor_activiteit == "werken_aan_nova_gedetecteerd"


# ---------------------------------------------------------------
# talking_to_nova: nooit een onderbrekingsvraag
# ---------------------------------------------------------------

def test_talking_to_nova_krijgt_nooit_een_vraag(opstelling):
    o = opstelling
    zet_activiteit(o.watcher, "talking_to_nova_gedetecteerd")
    o.watcher.check_activity_interruption()
    assert o.engine.aanroepen == []
    assert o.bus.teksten() == []
    assert o.ctx.aantal_vragen == 0


@pytest.mark.parametrize(
    "naam", ["werken_aan_nova_gedetecteerd", "coding_gedetecteerd", "lezen"]
)
def test_andere_activiteiten_krijgen_wel_een_vraag(opstelling, naam):
    o = opstelling
    zet_activiteit(o.watcher, naam)
    o.watcher.check_activity_interruption()
    assert o.bus.teksten() == ["Mag ik storen?"]


# ---------------------------------------------------------------
# Pauze op de laptop: de teller begint opnieuw
# ---------------------------------------------------------------

def test_lange_inactiviteit_herstart_de_teller(opstelling):
    o = opstelling
    zet_activiteit(o.watcher, minuten_geleden=20)
    o.watcher._activiteit_inactief_sinds = (
        time.time() - (SessionWatcher.PAUZE_RESET_SECONDEN + 60)
    )
    o.focus.niveau = "actief"
    o.watcher.check_activity_interruption()
    assert time.time() - o.watcher.activiteit_start_tijd < 5
    assert o.watcher._activiteit_inactief_sinds is None


def test_korte_inactiviteit_herstart_de_teller_niet(opstelling):
    o = opstelling
    zet_activiteit(o.watcher, minuten_geleden=20)
    start_voor = o.watcher.activiteit_start_tijd
    o.watcher._activiteit_inactief_sinds = time.time() - 120
    o.focus.niveau = "actief"
    o.watcher.check_activity_interruption()
    assert o.watcher.activiteit_start_tijd == start_voor
    assert o.watcher._activiteit_inactief_sinds is None
    assert o.bus.teksten() == ["Mag ik storen?"]


def test_niet_actief_zet_de_markering_en_overschrijft_ze_niet(opstelling):
    o = opstelling
    o.ctx.mag = False  # isoleren: hier gaat het enkel om de markering
    o.focus.niveau = "onbekend"
    zet_activiteit(o.watcher)
    assert o.watcher._activiteit_inactief_sinds is None
    o.watcher.check_activity_interruption()
    eerste = o.watcher._activiteit_inactief_sinds
    assert eerste is not None
    o.watcher.check_activity_interruption()
    assert o.watcher._activiteit_inactief_sinds == eerste


def test_nieuwe_activiteit_wist_de_markering(opstelling):
    o = opstelling
    o.watcher._activiteit_inactief_sinds = time.time() - 2000
    o.watcher._on_any_event({"naam": "lezen"}, event_type="activity_started:lezen")
    assert o.watcher.actieve_activiteit == "lezen"
    assert o.watcher._activiteit_inactief_sinds is None


def test_laptop_dicht_en_weer_open_geeft_geen_directe_vraag(opstelling):
    """Het scenario uit de praktijk: laptop dichtgeklapt, Nova vroeg toch."""
    o = opstelling
    zet_activiteit(o.watcher, minuten_geleden=20)

    # Laptop dicht: geen data (focus onbekend), Layer 5 zegt nee.
    o.focus.niveau = "onbekend"
    o.ctx.mag = False
    o.watcher.check_activity_interruption()
    assert o.bus.teksten() == []

    # Een uur later: laptop open, Kevin actief, Layer 5 zegt ja.
    o.watcher._activiteit_inactief_sinds = time.time() - 3600
    o.focus.niveau = "actief"
    o.ctx.mag = True
    o.watcher.check_activity_interruption()
    assert o.bus.teksten() == []
    assert o.engine.aanroepen == []