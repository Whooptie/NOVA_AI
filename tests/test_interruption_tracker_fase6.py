# test_interruption_tracker_fase6.py
"""
Tests voor Fase 6 (optioneel, tijdsvenster-verfijning) van
interruption_tracker.py.

Isolatie via tmp_path (zelfde conventie als de rest van Nova's
testsuite, zie nova_state.md): InterruptionTracker.__init__() doet
I/O (load_from_disk() met een hardcoded relatief pad), dus we
monkeypatchen self.save_path NA constructie, vóór er iets
weggeschreven wordt.

Draai met: pytest test_interruption_tracker_fase6.py -v
"""

import sys
from pathlib import Path

import pytest

# Projectroot toevoegen aan het zoekpad (dit testbestand staat in
# tests/, interruption_tracker.py staat in core/ -- dus we moeten
# een niveau omhoog, niet enkel naar de eigen map van dit bestand).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.interruption_tracker import InterruptionTracker


@pytest.fixture
def tracker(tmp_path):
    """
    Geeft een verse InterruptionTracker terug die naar een tijdelijk
    bestand schrijft/leest, zodat tests elkaar nooit raken en er
    nooit per ongeluk in de echte data/interruption_patterns.json
    geschreven wordt.
    """
    t = InterruptionTracker(event_bus=None)
    # Pas save_path AAN NA constructie -- __init__() heeft al
    # load_from_disk() aangeroepen op het echte pad (dat gewoon
    # "bestand bestaat niet" teruggeeft, geen probleem), maar vanaf
    # hier moet elke save_to_disk()/load_from_disk() naar de tijdelijke
    # testlocatie gaan.
    t.save_path = tmp_path / "interruption_patterns.json"
    t.patterns = {}  # zeker starten vanaf leeg, ongeacht wat init deed
    return t


# ──────────────────────────────────────────────────────────
# Backward-compatibility: bestaand gedrag mag NIET breken
# ──────────────────────────────────────────────────────────

class TestBackwardCompatibiliteit:
    def test_record_feedback_zonder_tijd_werkt_zoals_voorheen(self, tracker):
        """Geen tijd_sinds_start meegeven -- puur het oude pad."""
        tracker.record_feedback("coderen", True)
        tracker.record_feedback("coderen", True)
        tracker.record_feedback("coderen", False)

        pattern = tracker.get_pattern("coderen")
        assert pattern["totaal_pogingen"] == 3
        assert pattern["aantal_toegestaan"] == 2
        assert pattern["confidence"] == pytest.approx(2 / 3, rel=1e-3)

    def test_get_confidence_zonder_venster_ongewijzigd(self, tracker):
        for _ in range(5):
            tracker.record_feedback("coderen", True)
        assert tracker.get_confidence("coderen") == 1.0

    def test_has_enough_data_zonder_venster_ongewijzigd(self, tracker):
        for _ in range(4):
            tracker.record_feedback("coderen", True)
        assert tracker.has_enough_data("coderen") is False

        tracker.record_feedback("coderen", True)  # 5e observatie
        assert tracker.has_enough_data("coderen") is True

    def test_oude_data_zonder_vensters_sleutel_crasht_niet(self, tracker):
        """
        Simuleert data die al bestond VOOR Fase 6 (geen "vensters"
        -sleutel in de opgeslagen JSON). record_feedback() met een
        tijd_sinds_start moet dit alsnog kunnen verwerken zonder
        KeyError/crash.
        """
        tracker.patterns["oude_activiteit"] = {
            "totaal_pogingen": 10,
            "aantal_toegestaan": 8,
            "confidence": 0.8,
            "laatst_bijgewerkt": "2026-01-01T00:00:00",
            # BEWUST geen "vensters"-sleutel -- dit simuleert oude data
        }

        tracker.record_feedback("oude_activiteit", True, tijd_sinds_start=5)

        pattern = tracker.get_pattern("oude_activiteit")
        assert pattern["totaal_pogingen"] == 11  # activiteit-breed telt gewoon door
        assert "vensters" in pattern  # nu alsnog aangemaakt
        assert pattern["vensters"]["vroeg"]["totaal_pogingen"] == 1


# ──────────────────────────────────────────────────────────
# Nieuw gedrag: venster-specifieke tellingen
# ──────────────────────────────────────────────────────────

class TestVensterVerfijning:
    def test_vroeg_en_laat_apart_geteld(self, tracker):
        # Vroeg venster (< 20 min): vooral "nee"
        tracker.record_feedback("coderen", False, tijd_sinds_start=5)
        tracker.record_feedback("coderen", False, tijd_sinds_start=10)
        tracker.record_feedback("coderen", True, tijd_sinds_start=15)

        # Laat venster (>= 20 min): vooral "ja"
        tracker.record_feedback("coderen", True, tijd_sinds_start=25)
        tracker.record_feedback("coderen", True, tijd_sinds_start=40)

        pattern = tracker.get_pattern("coderen")
        assert pattern["vensters"]["vroeg"]["totaal_pogingen"] == 3
        assert pattern["vensters"]["vroeg"]["aantal_toegestaan"] == 1
        assert pattern["vensters"]["laat"]["totaal_pogingen"] == 2
        assert pattern["vensters"]["laat"]["aantal_toegestaan"] == 2

        # Activiteit-breed totaal blijft gewoon correct meelopen
        assert pattern["totaal_pogingen"] == 5
        assert pattern["aantal_toegestaan"] == 3

    def test_venstergrens_exact_op_20_minuten(self, tracker):
        """
        20.0 minuten moet in het 'laat'-venster vallen (< grens, niet
        <= grens) -- expliciet testen op de grenswaarde zelf, want
        dat is precies waar off-by-one-fouten meestal zitten.
        """
        tracker.record_feedback("coderen", True, tijd_sinds_start=19.9)
        tracker.record_feedback("coderen", True, tijd_sinds_start=20.0)

        pattern = tracker.get_pattern("coderen")
        assert pattern["vensters"]["vroeg"]["totaal_pogingen"] == 1
        assert pattern["vensters"]["laat"]["totaal_pogingen"] == 1

    def test_get_confidence_met_venster_geeft_venster_specifieke_score(self, tracker):
        for _ in range(5):
            tracker.record_feedback("coderen", False, tijd_sinds_start=5)
        for _ in range(5):
            tracker.record_feedback("coderen", True, tijd_sinds_start=30)

        assert tracker.get_confidence("coderen", tijd_sinds_start=5) == 0.0
        assert tracker.get_confidence("coderen", tijd_sinds_start=30) == 1.0
        # Activiteit-breed (geen venster) blijft het gemiddelde
        assert tracker.get_confidence("coderen") == 0.5

    def test_has_enough_data_per_venster_apart(self, tracker):
        """
        Kernscenario uit het ontwerp: activiteit-breed genoeg data,
        maar EEN venster nog te dun -- has_enough_data() moet dat
        per venster correct onderscheiden, niet enkel het totaal
        checken.
        """
        # 6x "laat" -- boven MIN_OBSERVATIES (5)
        for _ in range(6):
            tracker.record_feedback("coderen", True, tijd_sinds_start=30)
        # 2x "vroeg" -- ONDER MIN_OBSERVATIES
        tracker.record_feedback("coderen", False, tijd_sinds_start=5)
        tracker.record_feedback("coderen", False, tijd_sinds_start=10)

        # Activiteit-breed: 8 observaties totaal -> genoeg
        assert tracker.has_enough_data("coderen") is True

        # Maar het 'vroeg'-venster zelf heeft er maar 2 -> NIET genoeg
        assert tracker.has_enough_data("coderen", tijd_sinds_start=5) is False
        # Het 'laat'-venster heeft er 6 -> wel genoeg
        assert tracker.has_enough_data("coderen", tijd_sinds_start=30) is True

    def test_get_confidence_none_als_venster_te_weinig_data(self, tracker):
        tracker.record_feedback("coderen", True, tijd_sinds_start=5)
        # Maar 1 observatie in 'vroeg' -- ver onder de drempel
        assert tracker.get_confidence("coderen", tijd_sinds_start=5) is None

    def test_onbekende_activiteit_geeft_none_of_false(self, tracker):
        assert tracker.get_confidence("nooit_gezien") is None
        assert tracker.get_confidence("nooit_gezien", tijd_sinds_start=10) is None
        assert tracker.has_enough_data("nooit_gezien") is False
        assert tracker.has_enough_data("nooit_gezien", tijd_sinds_start=10) is False


# ──────────────────────────────────────────────────────────
# Persistentie: venster-data moet ook echt herladen worden
# ──────────────────────────────────────────────────────────

class TestPersistentie:
    def test_vensters_overleven_save_en_load(self, tmp_path):
        t1 = InterruptionTracker(event_bus=None)
        t1.save_path = tmp_path / "interruption_patterns.json"
        t1.patterns = {}

        t1.record_feedback("coderen", True, tijd_sinds_start=5)
        t1.record_feedback("coderen", False, tijd_sinds_start=30)

        # Nieuwe instantie, zelfde pad -- simuleert een herstart/reboot
        t2 = InterruptionTracker(event_bus=None)
        t2.save_path = tmp_path / "interruption_patterns.json"
        t2.patterns = {}
        t2.load_from_disk()

        pattern = t2.get_pattern("coderen")
        assert pattern is not None
        assert pattern["vensters"]["vroeg"]["totaal_pogingen"] == 1
        assert pattern["vensters"]["laat"]["totaal_pogingen"] == 1