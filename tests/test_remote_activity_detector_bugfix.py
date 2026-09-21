# test_remote_activity_detector_bugfix.py
#
# Regressietest voor een structurele bug, gevonden 19 september 2026
# tijdens het uitpluizen van "waarom komt mijn nieuwe activity-label
# niet in patterns_layer2.json terecht".
#
# DE BUG: sinds de overstap naar de Windows-companion-client
# (13 september 2026), leest module_loader.py's context_layers
# "activity_detector" in als een RemoteActivityDetector-instance (zie
# module_loader.py) -- maar RemoteActivityDetector.detect_activity()
# gaf enkel een dict terug, het publiceerde NOOIT het
# "activity_started:<label>_gedetecteerd"-event dat het ORIGINELE
# activity_detector.py (vóór de Remote-overstap) wel publiceerde.
# Gevolg: pattern_matcher.py (Layer 2) kreeg sinds 13 september 2026
# GEEN ENKELE nieuwe activiteit-telling meer binnen, voor GEEN ENKEL
# label (niet enkel voor nieuwe/onbekende labels) -- de bestaande
# tellingen in patterns_layer2.json (bv. "coding_gedetecteerd: 683")
# waren allemaal HISTORISCH, van vóór die overstap.
#
# DE FIX: RemoteActivityDetector krijgt nu zelf een event_bus
# (doorgegeven vanuit module_loader.py) en publiceert zelf het
# event -- maar ENKEL bij een ECHTE wissel van activiteit-label
# (_vorig_label), niet bij elke detect_activity()-aanroep (die
# gebeurt elke paar seconden via main.py's achtergrond_loop() zolang
# de laptop verbonden is) -- anders zou Layer 2 "coding" honderden
# keren per minuut tellen zolang je gewoon in hetzelfde venster blijft.

import pytest

from modules.network import client_bridge


class NepEventBus:
    def __init__(self):
        self.gepubliceerde_events = []

    def publish(self, event_type, data=None):
        self.gepubliceerde_events.append((event_type, data))


class NepBridge:
    """Vervangt de echte ClientBridge -- levert enkel
    get_laatste_activity() met een instelbaar resultaat per test."""

    def __init__(self, resultaten=None):
        self._resultaten = list(resultaten) if resultaten else [None]
        self._index = 0

    def get_laatste_activity(self):
        # Bij elke aanroep het VOLGENDE ingestelde resultaat teruggeven
        # (of het laatste blijven herhalen als de lijst op is) -- zo
        # kan een test meerdere opeenvolgende detect_activity()-
        # aanroepen simuleren met wisselende of gelijkblijvende data.
        waarde = self._resultaten[min(self._index, len(self._resultaten) - 1)]
        self._index += 1
        return waarde


def _activity_data(label, **overrides):
    basis = {
        "activity": label,
        "duration_minutes": 1.0,
        "raw_window_title": f"Titel voor {label}",
        "raw_process_name": None,
        "is_working_on_nova": False,
        "time": "2026-09-19T20:00:00",
    }
    basis.update(overrides)
    return basis


# ------------------------------------------------------------------
# Basisgedrag: eerste detect_activity()-aanroep publiceert altijd
# (er was nog geen "vorig label" om tegen te vergelijken).
# ------------------------------------------------------------------

def test_eerste_aanroep_publiceert_altijd():
    event_bus = NepEventBus()
    bridge = NepBridge([_activity_data("coding")])
    detector = client_bridge.RemoteActivityDetector(bridge, event_bus=event_bus)

    detector.detect_activity()

    event_types = [e[0] for e in event_bus.gepubliceerde_events]
    assert "activity_started:coding_gedetecteerd" in event_types
    assert "activity_detected" in event_types


def test_geen_event_bus_geeft_geen_crash_en_geen_publicatie():
    """Als geen event_bus wordt meegegeven (bv. oude aanroepstijl),
    moet detect_activity() nog steeds gewoon een dict teruggeven,
    zonder crash -- enkel de publicatie zelf blijft dan achterwege."""
    bridge = NepBridge([_activity_data("coding")])
    detector = client_bridge.RemoteActivityDetector(bridge, event_bus=None)

    resultaat = detector.detect_activity()

    assert resultaat["activity"] == "coding"


# ------------------------------------------------------------------
# KERNTEST van de bugfix: geen bridge-data (data is None) mag ook
# een correcte "unknown"-publicatie geven, niet enkel een dict.
# ------------------------------------------------------------------

def test_geen_data_publiceert_unknown():
    event_bus = NepEventBus()
    bridge = NepBridge([None])
    detector = client_bridge.RemoteActivityDetector(bridge, event_bus=event_bus)

    resultaat = detector.detect_activity()

    assert resultaat["activity"] == "unknown"
    assert ("activity_started:unknown_gedetecteerd", resultaat) in event_bus.gepubliceerde_events


# ------------------------------------------------------------------
# KERNTEST: GEEN herhaalde publicatie zolang het label ongewijzigd
# blijft -- dit is de eigenlijke reden waarom _vorig_label nodig is,
# en het belangrijkste gedrag om hier te bewaken (zonder deze check
# zou Layer 2 bij elke meting opnieuw tellen, wat de tellingen
# betekenisloos zou opblazen).
# ------------------------------------------------------------------

def test_zelfde_label_na_elkaar_publiceert_maar_1_keer():
    event_bus = NepEventBus()
    bridge = NepBridge([
        _activity_data("coding"),
        _activity_data("coding"),
        _activity_data("coding"),
    ])
    detector = client_bridge.RemoteActivityDetector(bridge, event_bus=event_bus)

    detector.detect_activity()
    detector.detect_activity()
    detector.detect_activity()

    coding_events = [
        e for e in event_bus.gepubliceerde_events
        if e[0] == "activity_started:coding_gedetecteerd"
    ]
    assert len(coding_events) == 1, (
        "Een ongewijzigd label mag maar EENMAAL een activity_started-"
        "event publiceren, niet bij elke detect_activity()-aanroep."
    )


def test_labelwissel_publiceert_opnieuw():
    event_bus = NepEventBus()
    bridge = NepBridge([
        _activity_data("coding"),
        _activity_data("coding"),
        _activity_data("gaming"),
    ])
    detector = client_bridge.RemoteActivityDetector(bridge, event_bus=event_bus)

    detector.detect_activity()
    detector.detect_activity()
    detector.detect_activity()

    event_types = [e[0] for e in event_bus.gepubliceerde_events]
    assert event_types.count("activity_started:coding_gedetecteerd") == 1
    assert event_types.count("activity_started:gaming_gedetecteerd") == 1


def test_terug_naar_eerder_label_publiceert_opnieuw():
    """coding -> gaming -> coding: de TWEEDE keer "coding" is een
    NIEUWE wissel (t.o.v. "gaming"), dus moet WEL opnieuw publiceren
    -- _vorig_label onthoudt enkel het ALLERLAATSTE label, geen
    volledige geschiedenis."""
    event_bus = NepEventBus()
    bridge = NepBridge([
        _activity_data("coding"),
        _activity_data("gaming"),
        _activity_data("coding"),
    ])
    detector = client_bridge.RemoteActivityDetector(bridge, event_bus=event_bus)

    detector.detect_activity()
    detector.detect_activity()
    detector.detect_activity()

    event_types = [e[0] for e in event_bus.gepubliceerde_events]
    assert event_types.count("activity_started:coding_gedetecteerd") == 2
    assert event_types.count("activity_started:gaming_gedetecteerd") == 1


# ------------------------------------------------------------------
# Nieuw, eigen (door Kevin toegevoegd) label -- dit is letterlijk het
# scenario dat de bug blootlegde: "werken_aan_uurrooster" moet exact
# hetzelfde behandeld worden als elk ander label, geen speciale
# uitzondering nodig.
# ------------------------------------------------------------------

def test_nieuw_eigen_label_publiceert_normaal():
    event_bus = NepEventBus()
    bridge = NepBridge([_activity_data("werken_aan_uurrooster")])
    detector = client_bridge.RemoteActivityDetector(bridge, event_bus=event_bus)

    detector.detect_activity()

    event_types = [e[0] for e in event_bus.gepubliceerde_events]
    assert "activity_started:werken_aan_uurrooster_gedetecteerd" in event_types


# ------------------------------------------------------------------
# is_working_on_nova: apart, AANVULLEND event, enkel bij True --
# zelfde gedrag als het origineel (activity_detector.py).
# ------------------------------------------------------------------

def test_working_on_nova_publiceert_extra_event():
    event_bus = NepEventBus()
    bridge = NepBridge([_activity_data("coding", is_working_on_nova=True)])
    detector = client_bridge.RemoteActivityDetector(bridge, event_bus=event_bus)

    detector.detect_activity()

    event_types = [e[0] for e in event_bus.gepubliceerde_events]
    assert "activity_started:coding_gedetecteerd" in event_types
    assert "activity_started:werken_aan_nova_gedetecteerd" in event_types


def test_working_on_nova_false_publiceert_geen_extra_event():
    event_bus = NepEventBus()
    bridge = NepBridge([_activity_data("coding", is_working_on_nova=False)])
    detector = client_bridge.RemoteActivityDetector(bridge, event_bus=event_bus)

    detector.detect_activity()

    event_types = [e[0] for e in event_bus.gepubliceerde_events]
    assert "activity_started:werken_aan_nova_gedetecteerd" not in event_types


def test_working_on_nova_alleen_gepubliceerd_bij_labelwissel():
    """is_working_on_nova blijft True over meerdere metingen, maar het
    activiteit-LABEL zelf wisselt niet -- dan mag het extra event ook
    maar 1x verschijnen, net als het hoofd-event."""
    event_bus = NepEventBus()
    bridge = NepBridge([
        _activity_data("coding", is_working_on_nova=True),
        _activity_data("coding", is_working_on_nova=True),
    ])
    detector = client_bridge.RemoteActivityDetector(bridge, event_bus=event_bus)

    detector.detect_activity()
    detector.detect_activity()

    event_types = [e[0] for e in event_bus.gepubliceerde_events]
    assert event_types.count("activity_started:werken_aan_nova_gedetecteerd") == 1


# ------------------------------------------------------------------
# Het kale "activity_detected"-event blijft ALTIJD meegepubliceerd
# (voor context_manager.py en eventuele andere listeners) -- exact
# zoals het origineel deed, ongeacht welk label.
# ------------------------------------------------------------------

def test_activity_detected_altijd_mee_gepubliceerd_bij_wissel():
    event_bus = NepEventBus()
    bridge = NepBridge([_activity_data("browsen_reddit")])
    detector = client_bridge.RemoteActivityDetector(bridge, event_bus=event_bus)

    detector.detect_activity()

    event_types = [e[0] for e in event_bus.gepubliceerde_events]
    assert "activity_detected" in event_types


# ------------------------------------------------------------------
# detect_activity() blijft ALTIJD de volledige, correcte dict
# teruggeven, ongeacht of er gepubliceerd werd -- de aanroeper
# (context_manager.py) mag dit gedrag nooit voelen veranderen.
# ------------------------------------------------------------------

def test_return_waarde_blijft_ongewijzigd_ook_bij_herhaald_label():
    event_bus = NepEventBus()
    data = _activity_data("coding", duration_minutes=5.5)
    bridge = NepBridge([data, data])
    detector = client_bridge.RemoteActivityDetector(bridge, event_bus=event_bus)

    eerste = detector.detect_activity()
    tweede = detector.detect_activity()

    assert eerste == data
    assert tweede == data