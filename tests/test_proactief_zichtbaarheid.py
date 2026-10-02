# tests/test_proactief_zichtbaarheid.py
"""
Tests voor de "Nova praat niet meer tegen een lege kamer"-wijzigingen
(30 september 2026):

1. context_manager.py -- nieuwe harde stopregel "Kevin kan het niet zien"
   (laatste eigen bericht < 10 min geleden, OF actief in Nova's eigen
   venster/project).
2. session_watcher.py -- pauzetimer meet Kevin's onafgebroken
   activiteit op de laptop, niet meer Nova's opstarttijd.
3. emergence_engine.py -- reflect() spreekt maximaal 1 insight per
   ronde uit, enkel bij nieuwe inhoud, met een lange, gespreide
   cooldown per insight-type.

Alles met tmp_path-isolatie: geen enkele test leest of schrijft in de
echte data/-map.
"""

import time

import pytest

import modules.activity.session_watcher as session_watcher_module
import modules.experimental.emergence_engine as emergence_module
from modules.activity.session_watcher import SessionWatcher
from modules.context.context_manager import ContextManager
from modules.experimental.emergence_engine import EmergenceEngine


# ─────────────────────────────────────────────────────────────
# Gedeelde hulpklassen
# ─────────────────────────────────────────────────────────────

class DummyEventBus:
    """Minimale EventBus: onthoudt subscribers en gepubliceerde events."""

    def __init__(self):
        self.subscribers = {}
        self.published = []
        self.modules = {}

    def subscribe(self, event_type, callback):
        self.subscribers.setdefault(event_type, []).append(callback)

    def publish(self, event_type, data):
        self.published.append((event_type, data))
        for callback in self.subscribers.get(event_type, []):
            callback(data, event_type=event_type)
        for callback in self.subscribers.get("*", []):
            callback(data, event_type=event_type)

    def teksten(self, event_type):
        return [d.get("text") for (t, d) in self.published if t == event_type]


class NepActivity:
    def __init__(self, activity="unknown", is_working_on_nova=False):
        self.activity = activity
        self.is_working_on_nova = is_working_on_nova

    def detect_activity(self):
        return {
            "activity": self.activity,
            "duration_minutes": 0.0,
            "raw_window_title": None,
            "is_working_on_nova": self.is_working_on_nova,
        }


class NepFocus:
    def __init__(self, niveau="onbekend"):
        self.niveau = niveau

    def get_focus_info(self):
        return {"focus_level": self.niveau, "seconds_since_input": None}


class NepPatternMatcher:
    """Altijd 'gebruikelijk moment', geen anomalieen -> score +2."""

    def is_pattern_active(self, event_type):
        return True

    def get_anomalies(self, days=1):
        return []


# ─────────────────────────────────────────────────────────────
# 1. context_manager.py -- zichtbaarheid
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def context_manager(tmp_path):
    bus = DummyEventBus()
    activity = NepActivity()
    focus = NepFocus()
    cm = ContextManager(bus, layers={
        "pattern_matcher": NepPatternMatcher(),
        "activity_detector": activity,
        "focus_detector": focus,
    })
    # __init__ doet geen I/O, maar get_current() logt naar schijf --
    # dus het logpad naar tmp_path omleiden.
    cm.log_path = tmp_path / "context_log.jsonl"
    return cm, bus, activity, focus


class TestZichtbaarheid:

    def test_niets_getypt_sinds_opstart_is_niet_zichtbaar(self, context_manager):
        cm, _, _, _ = context_manager
        kan_zien, reden = cm._bepaal_zichtbaarheid("unknown", False, "onbekend")
        assert kan_zien is False
        assert "nog niets getypt" in reden

    def test_chat_message_van_kevin_maakt_zichtbaar(self, context_manager):
        cm, bus, _, _ = context_manager
        bus.publish("chat_message", {"sender": "Kevin", "text": "hey"})
        kan_zien, _ = cm._bepaal_zichtbaarheid("unknown", False, "onbekend")
        assert kan_zien is True

    def test_debug_command_telt_ook_als_typen(self, context_manager):
        cm, bus, _, _ = context_manager
        bus.publish("debug_command", {"text": "context"})
        assert cm._laatste_bericht_van_kevin is not None

    def test_bericht_van_iemand_anders_telt_niet(self, context_manager):
        cm, bus, _, _ = context_manager
        bus.publish("chat_message", {"sender": "Nova", "text": "iets"})
        assert cm._laatste_bericht_van_kevin is None

    def test_bericht_ouder_dan_10_minuten_is_niet_meer_zichtbaar(self, context_manager):
        cm, _, _, _ = context_manager
        cm._laatste_bericht_van_kevin = time.time() - 11 * 60
        kan_zien, reden = cm._bepaal_zichtbaarheid("unknown", False, "onbekend")
        assert kan_zien is False
        assert "11 min" in reden

    def test_bericht_van_9_minuten_geleden_is_nog_zichtbaar(self, context_manager):
        cm, _, _, _ = context_manager
        cm._laatste_bericht_van_kevin = time.time() - 9 * 60
        kan_zien, _ = cm._bepaal_zichtbaarheid("unknown", False, "onbekend")
        assert kan_zien is True

    def test_actief_in_nova_project_is_zichtbaar_zonder_typen(self, context_manager):
        cm, _, _, _ = context_manager
        kan_zien, _ = cm._bepaal_zichtbaarheid("coding", True, "actief")
        assert kan_zien is True

    def test_nova_project_open_maar_niet_actief_is_niet_zichtbaar(self, context_manager):
        cm, _, _, _ = context_manager
        kan_zien, _ = cm._bepaal_zichtbaarheid("coding", True, "mogelijk_afwezig")
        assert kan_zien is False

    def test_talking_to_nova_venster_actief_is_zichtbaar(self, context_manager):
        cm, _, _, _ = context_manager
        kan_zien, _ = cm._bepaal_zichtbaarheid("talking_to_nova", False, "actief")
        assert kan_zien is True

    def test_gewoon_coderen_in_ander_project_is_niet_zichtbaar(self, context_manager):
        cm, _, _, _ = context_manager
        kan_zien, _ = cm._bepaal_zichtbaarheid("coding", False, "actief")
        assert kan_zien is False


class TestBepaalInterruptMetZichtbaarheid:

    def test_zonder_nieuwe_parameter_gedrag_ongewijzigd(self, context_manager):
        # Bestaande aanroepen (6 argumenten) moeten exact zoals vroeger werken.
        cm, _, _, _ = context_manager
        ok, _ = cm._bepaal_interrupt(True, [], "unknown", 0.0, "onbekend", None)
        assert ok is True

    def test_niet_zichtbaar_blokkeert_ook_bij_hoge_score(self, context_manager):
        cm, _, _, _ = context_manager
        ok, reden = cm._bepaal_interrupt(
            True, [], "unknown", 0.0, "onbekend", None,
            kevin_kan_zien=False, zichtbaarheid_reden="Kevin kan het nu niet zien (test)",
        )
        assert ok is False
        assert "harde stopregel" in reden

    def test_niemand_aanwezig_blijft_voorrang_houden(self, context_manager):
        cm, _, _, _ = context_manager
        ok, reden = cm._bepaal_interrupt(
            True, [], "unknown", 0.0, "onbekend", True, kevin_kan_zien=True,
        )
        assert ok is False
        assert "niemand aanwezig" in reden


class TestGetCurrentEnCanInterrupt:

    def test_laptop_uit_en_niets_getypt_mag_niet_onderbreken(self, context_manager):
        # Precies de situatie van Kevin's log: laptop niet verbonden,
        # Nova draait gewoon door op de server.
        cm, _, _, _ = context_manager
        assert cm.can_interrupt() is False
        assert cm.context["kevin_kan_zien"] is False

    def test_na_een_bericht_mag_nova_weer_onderbreken(self, context_manager):
        cm, bus, _, _ = context_manager
        bus.publish("chat_message", {"sender": "Kevin", "text": "hey"})
        assert cm.can_interrupt() is True
        assert cm.context["kevin_kan_zien"] is True

    def test_actief_in_nova_project_zonder_typen_mag_onderbreken(self, context_manager):
        cm, _, activity, focus = context_manager
        activity.activity = "coding"
        activity.is_working_on_nova = True
        focus.niveau = "actief"
        # "coding" korter dan 15 min -> geen storingsgevoelige aftrek,
        # dus enkel de zichtbaarheid is hier bepalend.
        assert cm.can_interrupt() is True

    def test_samenvatting_toont_zichtbaarheid(self, context_manager):
        cm, _, _, _ = context_manager
        assert "Kevin kan het zien: False" in cm.get_context_summary()

    def test_eventbus_zonder_subscribe_crasht_niet(self, tmp_path):
        class BusZonderSubscribe:
            def publish(self, event_type, data):
                pass

        cm = ContextManager(BusZonderSubscribe(), layers={})
        cm.log_path = tmp_path / "log.jsonl"
        assert cm.can_interrupt() is False


# ─────────────────────────────────────────────────────────────
# 2. session_watcher.py -- pauzetimer
# ─────────────────────────────────────────────────────────────

class NepKlok:
    def __init__(self, start=1_000_000.0):
        self.nu = start

    def __call__(self):
        return self.nu

    def minuten_verder(self, minuten):
        self.nu += minuten * 60


class NepContextManagerVoorPauze:
    def __init__(self, mag=True):
        self.mag = mag
        self.aantal_vragen = 0

    def can_interrupt(self):
        self.aantal_vragen += 1
        return self.mag


@pytest.fixture
def watcher(monkeypatch):
    klok = NepKlok()
    monkeypatch.setattr(session_watcher_module.time, "time", klok)
    bus = DummyEventBus()
    focus = NepFocus("onbekend")
    bus.modules["focus_detector"] = focus
    cm = NepContextManagerVoorPauze(mag=True)
    w = SessionWatcher(bus, context_manager=cm)
    return w, bus, focus, cm, klok


def _minuten_lang_checken(w, klok, minuten):
    """Simuleert achtergrond_loop(): elke minuut check_pauze()."""
    for _ in range(minuten):
        klok.minuten_verder(1)
        w.check_pauze()


class TestPauzeTimer:

    def test_nova_draait_zonder_laptop_geen_melding(self, watcher):
        # Het oude probleem: Nova draait 2 uur, niemand aanwezig.
        w, bus, _, _, klok = watcher
        _minuten_lang_checken(w, klok, 120)
        assert bus.teksten("chat_response") == []

    def test_zonder_focus_detector_geen_melding(self, monkeypatch):
        klok = NepKlok()
        monkeypatch.setattr(session_watcher_module.time, "time", klok)
        bus = DummyEventBus()
        w = SessionWatcher(bus, context_manager=NepContextManagerVoorPauze())
        _minuten_lang_checken(w, klok, 60)
        assert bus.teksten("chat_response") == []

    def test_30_minuten_actief_geeft_een_melding(self, watcher):
        w, bus, focus, _, klok = watcher
        focus.niveau = "actief"
        _minuten_lang_checken(w, klok, 29)
        assert bus.teksten("chat_response") == []
        _minuten_lang_checken(w, klok, 2)
        meldingen = bus.teksten("chat_response")
        assert len(meldingen) == 1
        assert "30" in meldingen[0]

    def test_tweede_melding_na_nog_eens_30_minuten_met_echte_duur(self, watcher):
        w, bus, focus, _, klok = watcher
        focus.niveau = "actief"
        _minuten_lang_checken(w, klok, 61)
        meldingen = bus.teksten("chat_response")
        assert len(meldingen) == 2
        assert "60" in meldingen[1]

    def test_kort_even_niet_actief_reset_niet(self, watcher):
        w, bus, focus, _, klok = watcher
        focus.niveau = "actief"
        _minuten_lang_checken(w, klok, 20)
        focus.niveau = "mogelijk_afwezig"
        _minuten_lang_checken(w, klok, 5)
        focus.niveau = "actief"
        _minuten_lang_checken(w, klok, 6)
        assert len(bus.teksten("chat_response")) == 1

    def test_10_minuten_weg_is_een_echte_pauze(self, watcher):
        w, bus, focus, _, klok = watcher
        focus.niveau = "actief"
        _minuten_lang_checken(w, klok, 25)
        focus.niveau = "waarschijnlijk_weg"
        _minuten_lang_checken(w, klok, 11)
        assert w._sessie_start is None
        focus.niveau = "actief"
        _minuten_lang_checken(w, klok, 25)
        # 25 + 25 minuten actief, maar met een echte pauze ertussen:
        # geen melding.
        assert bus.teksten("chat_response") == []

    def test_laptop_valt_weg_telt_ook_als_pauze(self, watcher):
        w, _, focus, _, klok = watcher
        focus.niveau = "actief"
        _minuten_lang_checken(w, klok, 20)
        focus.niveau = "onbekend"  # geen verse data meer van de laptop
        _minuten_lang_checken(w, klok, 11)
        assert w._sessie_start is None

    def test_geen_melding_als_kevin_net_even_niet_actief_is(self, watcher):
        w, bus, focus, _, klok = watcher
        focus.niveau = "actief"
        _minuten_lang_checken(w, klok, 29)
        focus.niveau = "mogelijk_afwezig"
        _minuten_lang_checken(w, klok, 3)
        assert bus.teksten("chat_response") == []
        focus.niveau = "actief"
        _minuten_lang_checken(w, klok, 1)
        assert len(bus.teksten("chat_response")) == 1

    def test_layer5_zegt_nee_dan_later_opnieuw_proberen(self, watcher):
        w, bus, focus, cm, klok = watcher
        focus.niveau = "actief"
        cm.mag = False
        _minuten_lang_checken(w, klok, 35)
        assert bus.teksten("chat_response") == []
        assert cm.aantal_vragen > 1
        cm.mag = True
        _minuten_lang_checken(w, klok, 1)
        assert len(bus.teksten("chat_response")) == 1


# ─────────────────────────────────────────────────────────────
# 3. emergence_engine.py -- max 1 insight, nieuwe inhoud, lange cooldown
# ─────────────────────────────────────────────────────────────

class NepContextManagerVoorEmergence:
    def __init__(self, mag=True):
        self.mag = mag

    def can_interrupt(self):
        return self.mag


@pytest.fixture
def engine(tmp_path, monkeypatch):
    # __init__ leest feedback- en cooldown-bestanden via
    # get_project_root() -> omleiden naar tmp_path.
    monkeypatch.setattr(emergence_module, "get_project_root", lambda _f: tmp_path)
    bus = DummyEventBus()
    cm = NepContextManagerVoorEmergence(mag=True)
    e = EmergenceEngine(bus, layers={"context_manager": cm})

    insights = {
        "lijst": [
            # marge 0.92 / 0.85 = 1.08
            {"type": "woordverband", "woord1": "oké", "woord2": "top", "confidence": 0.92},
            # marge 13 / 8 = 1.625  -> ruimste marge
            {"type": "kennisdichtheid", "concept": "python", "aantal_relaties": 13, "confidence": 13},
            # marge 23 / 3 = 7.67 zou nog ruimer zijn -- zie tests die dit type toevoegen
        ]
    }
    monkeypatch.setattr(e, "analyze_meta_patterns", lambda: [dict(i) for i in insights["lijst"]])
    return e, bus, cm, insights


def _periodiek(e, insight_type):
    return e._laatst_gemeld["_periodiek"][insight_type]


class TestReflectMaxEen:

    def test_maar_een_insight_hardop(self, engine):
        e, bus, _, _ = engine
        resultaat = e.reflect()
        assert len(bus.teksten("layer4_response")) == 1
        # Alle insights worden nog wel intern bijgehouden:
        assert len(bus.teksten("emergence:insight")) == 2
        assert len(resultaat) == 2

    def test_ruimste_marge_wint(self, engine):
        e, bus, _, _ = engine
        resultaat = e.reflect()
        gekozen = [r for r in resultaat if r["uitgesproken"]]
        assert len(gekozen) == 1
        assert gekozen[0]["insight_type"] == "kennisdichtheid"

    def test_tweede_ronde_zegt_het_andere_insight(self, engine):
        e, bus, _, _ = engine
        e.reflect()
        e.reflect()
        teksten = bus.teksten("layer4_response")
        assert len(teksten) == 2
        assert "python" in teksten[0]
        assert "oké" in teksten[1] or "top" in teksten[1]

    def test_derde_ronde_zegt_niets_meer(self, engine):
        e, bus, _, _ = engine
        for _ in range(3):
            e.reflect()
        assert len(bus.teksten("layer4_response")) == 2

    def test_ook_na_de_15_min_cooldown_geen_herhaling(self, engine):
        # Precies het oude probleem: na 20 minuten kwam alles terug.
        e, bus, _, _ = engine
        e.reflect()
        e.reflect()
        for sleutel, waarde in list(e._laatst_gemeld.items()):
            if sleutel != "_periodiek":
                e._laatst_gemeld[sleutel] = waarde - 60 * 60  # 1 uur terug
        e.reflect()
        assert len(bus.teksten("layer4_response")) == 2

    def test_geen_goed_moment_dan_niets_en_geen_geheugen(self, engine):
        e, bus, cm, _ = engine
        cm.mag = False
        e.reflect()
        assert bus.teksten("layer4_response") == []
        assert "_periodiek" not in e._laatst_gemeld or e._laatst_gemeld["_periodiek"] == {}
        cm.mag = True
        e.reflect()
        assert len(bus.teksten("layer4_response")) == 1

    def test_drempel_niet_gehaald_blijft_stil(self, engine):
        e, bus, _, insights = engine
        insights["lijst"] = [
            {"type": "woordverband", "woord1": "a", "woord2": "b", "confidence": 0.5},
        ]
        e.reflect()
        assert bus.teksten("layer4_response") == []


class TestNieuweInhoudEnLangeCooldown:

    def _cooldowns_verlopen(self, e):
        for sleutel, waarde in list(e._laatst_gemeld.items()):
            if sleutel == "_periodiek":
                for info in waarde.values():
                    info["volgende_toegestaan"] = 0
            else:
                e._laatst_gemeld[sleutel] = 0

    def test_cooldown_ligt_tussen_18_en_30_uur(self, engine):
        e, _, _, _ = engine
        e.reflect()
        info = _periodiek(e, "kennisdichtheid")
        wacht_uur = (info["volgende_toegestaan"] - info["gezegd_op"]) / 3600
        assert 18 <= wacht_uur <= 30

    def test_zelfde_inhoud_na_cooldown_blijft_stil(self, engine):
        e, bus, _, insights = engine
        insights["lijst"] = [insights["lijst"][1]]  # enkel kennisdichtheid
        e.reflect()
        self._cooldowns_verlopen(e)
        e.reflect()
        assert len(bus.teksten("layer4_response")) == 1

    def test_ander_concept_na_cooldown_wordt_uitgesproken(self, engine):
        e, bus, _, insights = engine
        insights["lijst"] = [insights["lijst"][1]]
        e.reflect()
        self._cooldowns_verlopen(e)
        insights["lijst"] = [{"type": "kennisdichtheid", "concept": "schaken",
                              "aantal_relaties": 14, "confidence": 14}]
        e.reflect()
        teksten = bus.teksten("layer4_response")
        assert len(teksten) == 2
        assert "schaken" in teksten[1]

    def test_ander_concept_maar_cooldown_nog_niet_voorbij_blijft_stil(self, engine):
        e, bus, _, insights = engine
        insights["lijst"] = [insights["lijst"][1]]
        e.reflect()
        # enkel de korte cooldown laten verlopen, de lange niet
        for sleutel in list(e._laatst_gemeld):
            if sleutel != "_periodiek":
                e._laatst_gemeld[sleutel] = 0
        insights["lijst"] = [{"type": "kennisdichtheid", "concept": "schaken",
                              "aantal_relaties": 14, "confidence": 14}]
        e.reflect()
        assert len(bus.teksten("layer4_response")) == 1

    def test_getal_licht_gestegen_is_niet_nieuw(self, engine):
        e, bus, _, insights = engine
        insights["lijst"] = [{"type": "personality_drift", "trait": "expressiveness",
                              "trait_label": "expressiviteit", "aantal_shifts": 23, "confidence": 23}]
        e.reflect()
        self._cooldowns_verlopen(e)
        insights["lijst"][0].update({"aantal_shifts": 25, "confidence": 25})
        e.reflect()
        assert len(bus.teksten("layer4_response")) == 1

    def test_getal_duidelijk_gestegen_is_wel_nieuw(self, engine):
        e, bus, _, insights = engine
        insights["lijst"] = [{"type": "personality_drift", "trait": "expressiveness",
                              "trait_label": "expressiviteit", "aantal_shifts": 23, "confidence": 23}]
        e.reflect()
        self._cooldowns_verlopen(e)
        insights["lijst"][0].update({"aantal_shifts": 29, "confidence": 29})
        e.reflect()
        teksten = bus.teksten("layer4_response")
        assert len(teksten) == 2
        assert "29" in teksten[1]

    def test_woordverband_volgorde_maakt_niet_uit(self, engine):
        e, _, _, _ = engine
        a = e._inhoud_van({"type": "woordverband", "woord1": "oké", "woord2": "top"})
        b = e._inhoud_van({"type": "woordverband", "woord1": "top", "woord2": "oké"})
        assert a == b

    def test_geheugen_overleeft_herstart(self, engine, tmp_path, monkeypatch):
        e, _, _, _ = engine
        e.reflect()
        monkeypatch.setattr(emergence_module, "get_project_root", lambda _f: tmp_path)
        nieuwe = EmergenceEngine(DummyEventBus(), layers={})
        assert "kennisdichtheid" in nieuwe._laatst_gemeld["_periodiek"]

    def test_kapotte_periodiek_state_crasht_niet(self, engine):
        e, bus, _, _ = engine
        e._laatst_gemeld["_periodiek"] = "kapot"
        e.reflect()
        assert len(bus.teksten("layer4_response")) == 1


class TestReactiefPadRegistreertOok:

    def test_reactief_tijdspatroon_blokkeert_periodieke_herhaling(self, engine, monkeypatch):
        e, bus, _, insights = engine
        tijdspatroon = {"type": "tijdspatroon", "event_type": "topic_detected:chess",
                        "onderwerp": "schaken", "uur": 19, "confidence": 0.95}
        monkeypatch.setattr(e, "_check_topic_sterkte", lambda naam: dict(tijdspatroon))
        e._on_elk_event({}, event_type="topic_detected:chess")
        assert len(bus.teksten("layer4_response")) == 1
        assert "tijdspatroon" in e._laatst_gemeld["_periodiek"]

        # Korte cooldown laten verlopen: het periodieke pad mag dit
        # toch niet meteen opnieuw zeggen (zelfde inhoud + lange cooldown).
        for sleutel in list(e._laatst_gemeld):
            if sleutel != "_periodiek":
                e._laatst_gemeld[sleutel] = 0
        insights["lijst"] = [dict(tijdspatroon)]
        e.reflect()
        assert len(bus.teksten("layer4_response")) == 1


# ─────────────────────────────────────────────────────────────
# 4. Webcam-fixes (30 sept 2026, na live-test)
# ─────────────────────────────────────────────────────────────

class TestWebcamGemistMaarWelInput:

    def test_nul_gezichten_maar_actief_is_geen_harde_stop(self, context_manager):
        cm, _, _, _ = context_manager
        ok, reden = cm._bepaal_interrupt(True, [], "unknown", 0.0, "actief", True)
        assert ok is True
        assert "recente input" in reden

    def test_nul_gezichten_en_geen_input_blijft_harde_stop(self, context_manager):
        cm, _, _, _ = context_manager
        for focus in ("mogelijk_afwezig", "waarschijnlijk_weg", "onbekend"):
            ok, reden = cm._bepaal_interrupt(True, [], "unknown", 0.0, focus, True)
            assert ok is False
            assert "niemand aanwezig" in reden

    def test_score_blijft_gewoon_meetellen(self, context_manager):
        # Webcam-stopregel vervalt, maar een ongebruikelijk moment met
        # anomalieen kan nog altijd "nee" geven.
        cm, _, _, _ = context_manager
        ok, _ = cm._bepaal_interrupt(False, ["a", "b"], "unknown", 0.0, "actief", True)
        assert ok is False

    def test_niet_zichtbaar_blijft_blokkeren(self, context_manager):
        cm, _, _, _ = context_manager
        ok, _ = cm._bepaal_interrupt(
            True, [], "unknown", 0.0, "actief", True,
            kevin_kan_zien=False, zichtbaarheid_reden="niet zichtbaar",
        )
        assert ok is False


class TestPresenceVervaltijd:

    @pytest.fixture
    def bridge(self, monkeypatch):
        import modules.network.client_bridge as cb
        # Geen echte WebSocket-server starten in een test.
        monkeypatch.setattr(cb.ClientBridge, "_start_server_in_achtergrond", lambda self: None)
        klok = NepKlok()
        monkeypatch.setattr(cb.time, "time", klok)
        return cb.ClientBridge(DummyEventBus()), klok, cb

    def _stuur(self, bridge, bericht_type, **velden):
        import json
        bridge._verwerk_bericht(json.dumps(dict(type=bericht_type, **velden)))

    def test_webcammeting_blijft_geldig_tot_de_volgende(self, bridge):
        b, klok, _ = bridge
        self._stuur(b, "presence_status", faces_detected=1, is_alone=False)
        klok.minuten_verder(5)
        assert b.get_laatste_presence() is not None

    def test_webcammeting_vervalt_na_7_minuten(self, bridge):
        b, klok, _ = bridge
        self._stuur(b, "presence_status", faces_detected=1, is_alone=False)
        klok.minuten_verder(7.5)
        assert b.get_laatste_presence() is None

    def test_activity_en_focus_houden_hun_3_minuten(self, bridge):
        b, klok, _ = bridge
        self._stuur(b, "activity_status", activity="coding")
        self._stuur(b, "focus_status", focus_level="actief")
        klok.minuten_verder(3.5)
        assert b.get_laatste_activity() is None
        assert b.get_laatste_focus() is None

    def test_vervaltijd_webcam_is_langer_dan_meetinterval(self, bridge):
        _, _, cb = bridge
        # nova_client.py meet de webcam elke 5 minuten (300 s).
        assert cb.PRESENCE_VERVAL_SECONDEN > 300