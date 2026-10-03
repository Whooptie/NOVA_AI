# test_afwezigheid.py
#
# Test de afwezigheid-feature (3 oktober 2026): laptop vergrendeld ->
# Nova zwijgt proactief, bewaart haar berichten, en zegt bij terugkomst
# "welkom terug" met wat ze wilde vertellen.
#
# Betrokken bestanden:
# - modules/context/afwezigheid.py (nieuw)
# - modules/context/context_manager.py (harde stopregel)
# - modules/activity/session_watcher.py (niet vragen/melden, pauze-reset)
# - modules/network/client_bridge.py (geen data -> niets publiceren)
# main.py's onderschep-stap wordt hier getest via een nagebootste
# on_chat_response (main.py zelf importeren zou de hele Nova opstarten).
#
# Isolatie: context_manager schrijft normaal naar data/context_log.jsonl
# -- in deze tests altijd omgeleid naar tmp_path.

import threading
import time

import pytest

from modules.activity.session_watcher import SessionWatcher
from modules.context import afwezigheid as afwezigheid_module
from modules.context.afwezigheid import AfwezigheidModule
from modules.context.context_manager import ContextManager
from modules.network.client_bridge import RemoteActivityDetector


# ------------------------------------------------------------------
# Hulpmiddelen
# ------------------------------------------------------------------

class EchteBus:
    """Kleine EventBus die events ECHT doorgeeft, incl. de "*"-wildcard,
    zodat de samenwerking tussen modules getest kan worden."""

    def __init__(self):
        self._subs = {}
        self.modules = {}
        self.gepubliceerd = []

    def subscribe(self, event_type, handler):
        self._subs.setdefault(event_type, []).append(handler)

    def register_module(self, naam, instance):
        self.modules[naam] = instance

    def publish(self, event_type, data=None):
        data = data if data is not None else {}
        self.gepubliceerd.append((event_type, data))
        for handler in list(self._subs.get(event_type, [])) + list(self._subs.get("*", [])):
            handler(data, event_type=event_type)

    def teksten(self, event_type="chat_response"):
        return [d.get("text") for t, d in self.gepubliceerd if t == event_type]

    def aantal(self, event_type):
        return sum(1 for t, _ in self.gepubliceerd if t == event_type)


class NepKlok:
    def __init__(self, start=1_000_000.0):
        self.nu = start

    def __call__(self):
        return self.nu

    def verder(self, minuten):
        self.nu += minuten * 60


def _detected(bus, label, titel="Een venster"):
    bus.publish(
        f"activity_started:{label}_gedetecteerd",
        {"activity": label, "raw_window_title": titel},
    )


@pytest.fixture
def bus():
    return EchteBus()


@pytest.fixture
def klok():
    return NepKlok()


@pytest.fixture
def afw(bus, klok):
    module = AfwezigheidModule(bus, klok=klok)
    bus.register_module("afwezigheid", module)
    return module


# ==================================================================
# 1. afwezigheid.py — begin en einde van een afwezigheid
# ==================================================================

class TestStatus:

    def test_start_aanwezig(self, afw):
        assert afw.is_afwezig() is False
        assert afw.afwezig_minuten() is None

    def test_vergrendelscherm_maakt_afwezig(self, bus, afw):
        _detected(bus, "afwezig", "Windows-standaardvergrendelingsscherm")
        assert afw.is_afwezig() is True
        assert bus.aantal("afwezigheid:vertrokken") == 1

    def test_tweede_vergrendel_event_geeft_geen_tweede_vertrek(self, bus, afw):
        _detected(bus, "afwezig")
        _detected(bus, "afwezig")
        assert bus.aantal("afwezigheid:vertrokken") == 1

    def test_ander_venster_maakt_terug(self, bus, afw, klok):
        _detected(bus, "afwezig")
        klok.verder(30)
        _detected(bus, "coding")
        assert afw.is_afwezig() is False
        terug = [d for t, d in bus.gepubliceerd if t == "afwezigheid:terug"]
        assert terug == [{"duur_minuten": 30.0, "aantal_berichten": 0}]

    def test_onbekend_venster_telt_ook_als_terug(self, bus, afw):
        """Ontgrendelen naar een nog niet gemapt venster is evengoed
        terugkomen."""
        _detected(bus, "afwezig")
        _detected(bus, "unknown", "Reddit - Google Chrome")
        assert afw.is_afwezig() is False

    def test_expliciete_activiteit_zonder_gedetecteerd_wordt_genegeerd(self, bus, afw):
        """'ik ga slapen' (expliciet, geen _gedetecteerd) zegt niets over
        de laptop en mag een afwezigheid niet beëindigen."""
        _detected(bus, "afwezig")
        bus.publish("activity_started:slapen", {"naam": "slapen"})
        assert afw.is_afwezig() is True

    def test_activiteitswissel_zonder_afwezigheid_doet_niets(self, bus, afw):
        _detected(bus, "coding")
        _detected(bus, "gaming")
        assert bus.aantal("afwezigheid:terug") == 0
        assert bus.teksten() == []

    def test_afwezig_minuten(self, bus, afw, klok):
        _detected(bus, "afwezig")
        klok.verder(12)
        assert afw.afwezig_minuten() == pytest.approx(12.0)


# ==================================================================
# 2. Berichten onderscheppen (main.py's onderschep-stap)
# ==================================================================

class TestOnderscheppen:

    def test_hoofdthread_wordt_nooit_onderschept(self, bus, afw):
        """Een antwoord op iets wat Kevin net typte moet hij altijd zien."""
        _detected(bus, "afwezig")
        assert afw.onderschep_bericht({"text": "Antwoord"}, is_hoofdthread=True) is False
        assert afw.aantal_bewaarde_berichten() == 0

    def test_niet_afwezig_wordt_niet_onderschept(self, afw):
        assert afw.onderschep_bericht({"text": "Proactief"}, is_hoofdthread=False) is False

    def test_proactief_tijdens_afwezigheid_wordt_bewaard(self, bus, afw):
        _detected(bus, "afwezig")
        assert afw.onderschep_bericht({"text": "Onweer op komst"}, is_hoofdthread=False) is True
        assert afw.aantal_bewaarde_berichten() == 1

    def test_msg_veld_wordt_ook_herkend(self, bus, afw):
        _detected(bus, "afwezig")
        assert afw.onderschep_bericht({"msg": "Oude stijl"}, is_hoofdthread=False) is True

    def test_lege_tekst_wordt_niet_onderschept(self, bus, afw):
        _detected(bus, "afwezig")
        assert afw.onderschep_bericht({"text": "   "}, is_hoofdthread=False) is False

    def test_dubbel_bericht_wordt_onderschept_maar_1x_bewaard(self, bus, afw):
        _detected(bus, "afwezig")
        afw.onderschep_bericht({"text": "Zelfde"}, is_hoofdthread=False)
        assert afw.onderschep_bericht({"text": "Zelfde"}, is_hoofdthread=False) is True
        assert afw.aantal_bewaarde_berichten() == 1

    def test_maximum_aantal_berichten(self, bus, afw, klok):
        _detected(bus, "afwezig")
        for i in range(AfwezigheidModule.MAX_BEWAARDE_BERICHTEN + 2):
            afw.onderschep_bericht({"text": f"Bericht {i}"}, is_hoofdthread=False)
        assert afw.aantal_bewaarde_berichten() == AfwezigheidModule.MAX_BEWAARDE_BERICHTEN

        klok.verder(10)
        _detected(bus, "coding")
        tekst = bus.teksten()[-1]
        assert "Bericht 0" not in tekst  # oudste viel weg
        assert "Bericht 11" in tekst
        assert "en nog 2 oudere meldingen" in tekst


# ==================================================================
# 3. Welkom terug
# ==================================================================

class TestWelkomTerug:

    def test_korte_afwezigheid_zonder_berichten_geen_begroeting(self, bus, afw, klok):
        _detected(bus, "afwezig")
        klok.verder(2)
        _detected(bus, "coding")
        assert bus.teksten() == []

    def test_lange_afwezigheid_geeft_begroeting_met_duur(self, bus, afw, klok):
        _detected(bus, "afwezig")
        klok.verder(30)
        _detected(bus, "coding")
        tekst = bus.teksten()[-1]
        assert "Je was 30 minuten weg." in tekst
        assert "Terwijl je weg was" not in tekst

    def test_korte_afwezigheid_met_berichten_toont_berichten(self, bus, afw, klok):
        _detected(bus, "afwezig")
        afw.onderschep_bericht({"text": "Het gaat sneeuwen"}, is_hoofdthread=False)
        klok.verder(2)
        _detected(bus, "coding")
        tekst = bus.teksten()[-1]
        assert "Terwijl je weg was:" in tekst
        assert "Het gaat sneeuwen" in tekst
        assert "Je was" not in tekst  # te kort om de duur te noemen

    def test_berichten_worden_na_terugkomst_leeggemaakt(self, bus, afw, klok):
        _detected(bus, "afwezig")
        afw.onderschep_bericht({"text": "Eenmalig"}, is_hoofdthread=False)
        _detected(bus, "coding")
        assert afw.aantal_bewaarde_berichten() == 0

        _detected(bus, "afwezig")
        klok.verder(30)
        _detected(bus, "gaming")
        assert "Eenmalig" not in bus.teksten()[-1]

    def test_te_oude_berichten_worden_enkel_geteld(self, bus, afw, klok):
        _detected(bus, "afwezig")
        afw.onderschep_bericht({"text": "Heel oud"}, is_hoofdthread=False)
        klok.verder(AfwezigheidModule.MAX_BERICHT_LEEFTIJD_UUR * 60 + 30)
        afw.onderschep_bericht({"text": "Recent"}, is_hoofdthread=False)
        _detected(bus, "coding")
        tekst = bus.teksten()[-1]
        assert "Heel oud" not in tekst
        assert "Recent" in tekst
        assert "en nog 1 oudere melding" in tekst

    def test_terug_event_komt_voor_de_begroeting(self, bus, afw, klok):
        """session_watcher moet zijn teller al kunnen resetten voor Nova
        iets zegt."""
        _detected(bus, "afwezig")
        klok.verder(30)
        _detected(bus, "coding")
        types = [t for t, _ in bus.gepubliceerd]
        assert types.index("afwezigheid:terug") < types.index("chat_response")


# ==================================================================
# 4. Kevin praat met Nova terwijl de laptop vergrendeld is
# ==================================================================

class TestPratenTijdensAfwezigheid:

    def test_bericht_van_kevin_toont_bewaarde_berichten(self, bus, afw):
        _detected(bus, "afwezig")
        afw.onderschep_bericht({"text": "Weerwaarschuwing"}, is_hoofdthread=False)
        bus.publish("raw_user_message", {"text": "hey"})
        tekst = bus.teksten()[-1]
        assert tekst.startswith("Terwijl je laptop vergrendeld is")
        assert "Weerwaarschuwing" in tekst
        assert afw.aantal_bewaarde_berichten() == 0
        # De laptop blijft vergrendeld: afwezigheid loopt gewoon door.
        assert afw.is_afwezig() is True

    def test_bericht_van_kevin_zonder_bewaarde_berichten_doet_niets(self, bus, afw):
        _detected(bus, "afwezig")
        bus.publish("raw_user_message", {"text": "hey"})
        assert bus.teksten() == []

    def test_bericht_van_kevin_terwijl_aanwezig_doet_niets(self, bus, afw):
        bus.publish("raw_user_message", {"text": "hey"})
        assert bus.teksten() == []


# ==================================================================
# 5. Duur-tekst
# ==================================================================

@pytest.mark.parametrize("minuten, verwacht", [
    (0.5, "minder dan een minuut"),
    (1, "1 minuut"),
    (45, "45 minuten"),
    (60, "1 uur"),
    (61, "1 uur en 1 minuut"),
    (135, "2 uur en 15 minuten"),
])
def test_duur_tekst(minuten, verwacht):
    assert AfwezigheidModule._duur_tekst(minuten) == verwacht


# ==================================================================
# 6. Deadlock-regressie (zelfde les als client_bridge.py, 19 sept)
# ==================================================================

def test_geen_deadlock_als_chat_response_terug_onderschept(bus, afw, klok):
    """
    In Nova zelf roept main.py's on_chat_response() bij ELK
    chat_response-bericht afwezigheid.onderschep_bericht() aan, die de
    lock neemt. Als afwezigheid.py zelf binnen zijn lock zou publiceren,
    blokkeert dat voor altijd. Deze test bootst on_chat_response() na en
    faalt (i.p.v. eeuwig te hangen) als dat ooit terugkomt.
    """
    getoond = []

    def nep_on_chat_response(data, event_type=None):
        if afw.onderschep_bericht(data, is_hoofdthread=False):
            return
        getoond.append(data.get("text"))

    bus.subscribe("chat_response", nep_on_chat_response)

    _detected(bus, "afwezig")
    afw.onderschep_bericht({"text": "Bewaard"}, is_hoofdthread=False)
    klok.verder(30)

    thread = threading.Thread(target=_detected, args=(bus, "coding"), daemon=True)
    thread.start()
    thread.join(timeout=2)

    assert not thread.is_alive(), "Deadlock: terugkomst bleef hangen"
    assert len(getoond) == 1
    assert "Bewaard" in getoond[0]


# ==================================================================
# 7. init_module (automatische ontdekking door module_loader.py)
# ==================================================================

def test_init_module(bus):
    instance = afwezigheid_module.init_module(bus, sem=object())
    assert isinstance(instance, AfwezigheidModule)
    assert ("module_loaded", {"name": "afwezigheid"}) in bus.gepubliceerd


# ==================================================================
# 8. client_bridge.py — geen data mag geen nep-"unknown" geven
# ==================================================================

class NepBridge:
    def __init__(self, reeks):
        self._reeks = list(reeks)
        self._i = 0

    def get_laatste_activity(self):
        waarde = self._reeks[min(self._i, len(self._reeks) - 1)]
        self._i += 1
        return waarde


def _data(label, titel="Venster"):
    return {
        "activity": label,
        "duration_minutes": 1.0,
        "raw_window_title": titel,
        "raw_process_name": None,
        "is_working_on_nova": False,
        "time": "2026-10-03T20:00:00",
    }


class TestRemoteActivityDetectorGeenData:

    def test_geen_data_publiceert_niets(self, bus):
        detector = RemoteActivityDetector(NepBridge([None]), event_bus=bus)
        resultaat = detector.detect_activity()
        assert resultaat["activity"] == "unknown"
        assert bus.gepubliceerd == []

    def test_slaapstand_na_vergrendelen_beeindigt_afwezigheid_niet(self, bus, afw):
        """Vergrendelen -> laptop slaapt (geen data) -> nog steeds weg."""
        detector = RemoteActivityDetector(
            NepBridge([_data("afwezig"), None, None]), event_bus=bus
        )
        detector.detect_activity()
        detector.detect_activity()
        detector.detect_activity()
        assert afw.is_afwezig() is True

    def test_ontwaken_naar_venster_beeindigt_afwezigheid(self, bus, afw):
        """Na de slaapstand vergelijkt de eerste echte meting zich met het
        laatste ECHTE label ('afwezig'), dus terugkomst wordt gezien."""
        detector = RemoteActivityDetector(
            NepBridge([_data("afwezig"), None, _data("unknown", "Reddit")]), event_bus=bus
        )
        detector.detect_activity()
        detector.detect_activity()
        detector.detect_activity()
        assert afw.is_afwezig() is False


# ==================================================================
# 9. context_manager.py — harde stopregel
# ==================================================================

class NepActivity:
    def __init__(self, label):
        self.label = label

    def detect_activity(self):
        return {"activity": self.label, "duration_minutes": 20.0, "raw_window_title": "x"}


class NepFocus:
    def __init__(self, niveau):
        self.niveau = niveau

    def get_focus_info(self):
        return {"focus_level": self.niveau, "seconds_since_input": 900}


def _context_manager(bus, tmp_path, label, focus="waarschijnlijk_weg"):
    cm = ContextManager(bus, layers={
        "activity_detector": NepActivity(label),
        "focus_detector": NepFocus(focus),
    })
    cm.log_path = tmp_path / "context_log.jsonl"
    return cm


class TestContextManager:

    def test_label_afwezig_mag_niet_onderbreken(self, bus, tmp_path):
        ctx = _context_manager(bus, tmp_path, "afwezig").get_current()
        assert ctx["should_interrupt"] is False
        assert ctx["is_afwezig"] is True
        assert "vergrendeld" in ctx["reden"]

    def test_afwezigheid_module_mag_niet_onderbreken(self, bus, tmp_path, afw):
        """Laptop slaapt (label 'unknown'), maar afwezigheid.py weet dat
        Kevin weg is."""
        _detected(bus, "afwezig")
        ctx = _context_manager(bus, tmp_path, "unknown").get_current()
        assert ctx["should_interrupt"] is False
        assert ctx["is_afwezig"] is True

    def test_regressie_vergrendeld_tijdens_coding_telde_vroeger_positief(self, bus, tmp_path, afw):
        """Zonder de stopregel gaf 'coding + waarschijnlijk_weg' +1 (pleit
        VOOR onderbreken). Met afwezigheid mag dat nooit meer winnen."""
        _detected(bus, "afwezig")
        ctx = _context_manager(bus, tmp_path, "coding").get_current()
        assert ctx["should_interrupt"] is False

    def test_aanwezig_gebruikt_gewone_score(self, bus, tmp_path, afw):
        cm = _context_manager(bus, tmp_path, "coding", focus="actief")
        # Zichtbaarheid (30 sept 2026): Kevin moet recent getypt hebben,
        # anders geldt de "kan het niet zien"-stopregel al.
        bus.publish("chat_message", {"sender": "Kevin", "text": "hoi"})
        ctx = cm.get_current()
        assert ctx["is_afwezig"] is False
        assert ctx["kevin_kan_zien"] is True
        assert ctx["reden"].startswith("score")

    def test_net_getypt_en_dan_vergrendeld_kan_niet_zien(self, bus, tmp_path, afw):
        """De zichtbaarheidsregel zegt 'kan zien' tot 10 min na Kevin's
        laatste bericht. Vergrendelt hij meteen daarna, dan moet
        afwezigheid toch winnen."""
        cm = _context_manager(bus, tmp_path, "coding", focus="actief")
        bus.publish("chat_message", {"sender": "Kevin", "text": "even weg"})
        _detected(bus, "afwezig")
        ctx = cm.get_current()
        assert ctx["kevin_kan_zien"] is False
        assert ctx["should_interrupt"] is False
        assert "vergrendeld" in ctx["reden"]

    def test_zonder_afwezigheid_module_geen_crash(self, tmp_path):
        class KaleBus:
            def publish(self, *a, **k):
                pass
        ctx = _context_manager(KaleBus(), tmp_path, "coding", focus="actief").get_current()
        assert ctx["is_afwezig"] is False

    def test_samenvatting_toont_afwezig(self, bus, tmp_path):
        tekst = _context_manager(bus, tmp_path, "afwezig").get_context_summary()
        assert "Afwezig: True" in tekst


# ==================================================================
# 10. session_watcher.py — zwijgen tijdens afwezigheid, pauze-reset
# ==================================================================

class NepResponseEngine:
    def __init__(self):
        self.aangeroepen = False

    def beslis_interruption_gedrag(self, activiteit, tijd_sinds_start=None):
        self.aangeroepen = True
        return {"actie": "ga_gewoon_door", "tekst": "Mag ik storen?", "confidence": 0.9}


class NepFocusDetector:
    """Zelfde vorm als RemoteFocusDetector.get_focus_info()."""
    def __init__(self, niveau="actief"):
        self.niveau = niveau

    def get_focus_info(self):
        return {"focus_level": self.niveau, "seconds_since_input": 1}


class TestSessionWatcher:

    def test_geen_pauze_melding_tijdens_afwezigheid(self, bus, afw):
        """Wachtwoord intypen op het vergrendelscherm is ook input
        (focus 'actief') -- toch geen pauze-melding."""
        bus.register_module("focus_detector", NepFocusDetector("actief"))
        watcher = SessionWatcher(bus)
        watcher._sessie_start = time.time() - watcher.PAUZE_DREMPEL_SECONDEN - 10
        _detected(bus, "afwezig")
        aantal_voor = bus.aantal("chat_response")
        watcher.check_pauze()
        assert bus.aantal("chat_response") == aantal_voor

    def test_pauze_melding_werkt_nog_als_aanwezig(self, bus, afw):
        bus.register_module("focus_detector", NepFocusDetector("actief"))
        watcher = SessionWatcher(bus)
        watcher._sessie_start = time.time() - watcher.PAUZE_DREMPEL_SECONDEN - 10
        aantal_voor = bus.aantal("chat_response")
        watcher.check_pauze()
        assert bus.aantal("chat_response") == aantal_voor + 1

    def test_vergrendelen_is_geen_nieuwe_activiteit(self, bus, afw):
        """Het vergrendelscherm mag de lopende activiteit niet vervangen
        (anders: 'mag ik storen?' over 'afwezig' na 15 minuten)."""
        watcher = SessionWatcher(bus)
        watcher.actieve_activiteit = "coding_gedetecteerd"
        watcher.activiteit_start_tijd = 123
        _detected(bus, "afwezig")
        assert watcher.actieve_activiteit == "coding_gedetecteerd"
        assert watcher.activiteit_start_tijd == 123

    def test_geen_storen_vraag_tijdens_afwezigheid(self, bus, afw):
        watcher = SessionWatcher(bus)
        engine = NepResponseEngine()
        bus.register_module("response_engine", engine)
        _detected(bus, "afwezig")
        # Bewust NA het vergrendel-event gezet, zodat deze test enkel de
        # afwezigheid-check meet en niet de activiteitswissel.
        watcher.actieve_activiteit = "coding_gedetecteerd"
        watcher.activiteit_start_tijd = 0  # lang geleden

        watcher.check_activity_interruption()

        assert engine.aangeroepen is False
        # Vlag NIET gezet: na terugkomst mag de vraag nog komen.
        assert watcher._al_gevraagd_voor_activiteit is None

    def test_storen_vraag_werkt_nog_als_aanwezig(self, bus, afw):
        watcher = SessionWatcher(bus)
        engine = NepResponseEngine()
        bus.register_module("response_engine", engine)
        watcher.actieve_activiteit = "coding_gedetecteerd"
        watcher.activiteit_start_tijd = 0

        watcher.check_activity_interruption()

        assert engine.aangeroepen is True

    def test_lange_afwezigheid_reset_pauze_teller(self, bus, afw):
        watcher = SessionWatcher(bus)
        watcher._sessie_start = 100
        watcher._laatst_actief = 200
        watcher.laatste_melding_time = 150
        watcher.activiteit_start_tijd = 0

        bus.publish("afwezigheid:terug", {"duur_minuten": 30, "aantal_berichten": 0})

        assert watcher._sessie_start is None
        assert watcher._laatst_actief is None
        assert watcher.laatste_melding_time is None
        assert watcher.activiteit_start_tijd > 0

    def test_na_reset_begint_nieuwe_sessie_bij_eerste_input(self, bus, afw):
        bus.register_module("focus_detector", NepFocusDetector("actief"))
        watcher = SessionWatcher(bus)
        watcher._sessie_start = 100  # oude, lange sessie
        bus.publish("afwezigheid:terug", {"duur_minuten": 30, "aantal_berichten": 0})
        voor = time.time()
        watcher.check_pauze()
        assert watcher._sessie_start >= voor
        # en dus (nog) geen pauze-melding
        assert bus.aantal("chat_response") == 0

    def test_korte_afwezigheid_reset_niets(self, bus, afw):
        watcher = SessionWatcher(bus)
        watcher._sessie_start = 100
        watcher.activiteit_start_tijd = 0
        bus.publish("afwezigheid:terug", {"duur_minuten": 2, "aantal_berichten": 0})
        assert watcher._sessie_start == 100
        assert watcher.activiteit_start_tijd == 0

    def test_zonder_afwezigheid_module_oud_gedrag(self):
        """Ontbreekt afwezigheid.py, dan blijft alles werken zoals vroeger."""
        bus = EchteBus()
        watcher = SessionWatcher(bus)
        assert watcher._is_kevin_afwezig() is False


# ==================================================================
# 11. Volledige keten: vergrendelen -> weerwaarschuwing -> ontgrendelen
# ==================================================================

def test_volledige_keten(bus, afw, klok):
    getoond = []

    def nep_on_chat_response(data, event_type=None):
        # Zelfde stap als main.py: eerst afwezigheid laten beslissen.
        if afw.onderschep_bericht(data, is_hoofdthread=False):
            return
        getoond.append(data.get("text"))

    bus.subscribe("chat_response", nep_on_chat_response)
    detector = RemoteActivityDetector(
        NepBridge([_data("coding"), _data("afwezig"), None, _data("coding")]),
        event_bus=bus,
    )

    detector.detect_activity()                     # aan het coderen
    detector.detect_activity()                     # vergrendeld
    bus.publish("chat_response", {"text": "Onweer verwacht vanavond."})
    klok.verder(40)
    detector.detect_activity()                     # slaapstand, geen data
    detector.detect_activity()                     # ontgrendeld

    assert len(getoond) == 1
    assert "Je was 40 minuten weg." in getoond[0]
    assert "Onweer verwacht vanavond." in getoond[0]