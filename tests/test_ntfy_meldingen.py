# tests/test_ntfy_meldingen.py
#
# Test voor modules/network/ntfy_meldingen.py (punt 55, stap 2a) en voor de
# nieuwe max_leeftijd-parameter in client_bridge.py.
#
# Geen netwerk nodig: het versturen wordt vervangen door een nep-functie, en
# de laptopverbinding door een nep-bridge. Eén klasse test de ECHTE
# ClientBridge (zonder echte WebSocket-server).

import threading
import time

import pytest

from modules.network import ntfy_meldingen
from modules.network.ntfy_meldingen import (
    FOCUS_MAX_LEEFTIJD_SECONDEN,
    MAX_BERICHTEN_PER_UUR,
    NtfyMeldingen,
    init_module,
    kort_in,
)


# ----------------------------------------------------------------
# Hulpklassen
# ----------------------------------------------------------------

class DummyEventBus:
    def __init__(self):
        self.abonnementen = []
        self.gepubliceerd = []
        self.modules = {}

    def subscribe(self, event_type, handler):
        self.abonnementen.append((event_type, handler))

    def publish(self, event_type, data=None):
        self.gepubliceerd.append((event_type, data))


class FakeBridge:
    """Nep-ClientBridge met dezelfde methodenamen als de echte."""

    def __init__(self, verbonden=True, focus="actief", activiteit="coding",
                 focus_data="standaard", activiteit_data="standaard",
                 fout=None):
        self.verbonden = verbonden
        if focus_data == "standaard":
            focus_data = {"type": "focus_status", "focus_level": focus}
        if activiteit_data == "standaard":
            activiteit_data = {"type": "activity_status", "activity": activiteit}
        self.focus_data = focus_data
        self.activiteit_data = activiteit_data
        self.fout = fout
        self.focus_leeftijden = []
        self.activiteit_leeftijden = []

    def is_laptop_verbonden(self):
        if self.fout:
            raise self.fout
        return self.verbonden

    def get_laatste_focus(self, max_leeftijd=180):
        self.focus_leeftijden.append(max_leeftijd)
        return self.focus_data

    def get_laatste_activity(self, max_leeftijd=180):
        self.activiteit_leeftijden.append(max_leeftijd)
        return self.activiteit_data


class NepAntwoord:
    def __init__(self, status_code=200):
        self.status_code = status_code


class NepPost:
    """Vervangt requests.post en onthoudt elke aanroep."""

    def __init__(self, status_code=200, fout=None):
        self.aanroepen = []
        self.status_code = status_code
        self.fout = fout

    def __call__(self, url, data=None, headers=None, timeout=None):
        self.aanroepen.append(
            {"url": url, "data": data, "headers": headers, "timeout": timeout}
        )
        if self.fout:
            raise self.fout
        return NepAntwoord(self.status_code)


URL = "http://ntfy.test:8090"
TOPIC = "geheim-kanaal-123"


def maak(bridge="standaard", post=None, klok=None):
    """Maakt een NtfyMeldingen met nep-bus, nep-bridge en nep-post."""
    bus = DummyEventBus()
    if bridge == "standaard":
        bridge = FakeBridge()
    if bridge is not None:
        bus.modules["client_bridge"] = bridge
    post = post if post is not None else NepPost()
    module = NtfyMeldingen(
        bus, url=URL, topic=TOPIC, http_post=post,
        achtergrond=False, klok=klok, zelftest_na_seconden=0,
        opstart_melding=False,
    )
    return module, bus, post, bridge


BERICHT = {"text": "Let op: er wordt mist verwacht!"}


# ----------------------------------------------------------------
# Instellingen en opstarten
# ----------------------------------------------------------------

class TestInstellingen:
    def test_zonder_url_en_topic_staat_de_module_uit(self):
        bus = DummyEventBus()
        post = NepPost()
        module = NtfyMeldingen(bus, url="", topic="", http_post=post, zelftest_na_seconden=0, opstart_melding=False)
        assert module.aan is False
        assert bus.abonnementen == []

    def test_zonder_topic_staat_de_module_uit(self):
        module = NtfyMeldingen(DummyEventBus(), url=URL, topic="", http_post=NepPost(), zelftest_na_seconden=0, opstart_melding=False)
        assert module.aan is False

    def test_met_instellingen_abonneert_op_chat_response(self):
        module, bus, _, _ = maak()
        assert module.aan is True
        assert len(bus.abonnementen) == 1
        assert bus.abonnementen[0][0] == "chat_response"

    def test_slash_achter_url_en_voor_topic_wordt_weggehaald(self):
        post = NepPost()
        module = NtfyMeldingen(DummyEventBus(), url=URL + "/", topic="/" + TOPIC + "/",
                               http_post=post, achtergrond=False, zelftest_na_seconden=0, opstart_melding=False)
        assert module.url == URL
        assert module.topic == TOPIC

    def test_init_module_zonder_env_staat_uit_en_meldt_geladen(self, monkeypatch):
        monkeypatch.setattr(ntfy_meldingen, "load_dotenv", None)
        monkeypatch.delenv("NTFY_URL", raising=False)
        monkeypatch.delenv("NTFY_TOPIC", raising=False)
        monkeypatch.delenv("NTFY_ZELFTEST_NA_SECONDEN", raising=False)
        monkeypatch.setenv("NTFY_OPSTARTMELDING", "uit")
        bus = DummyEventBus()
        instantie = init_module(bus)
        assert isinstance(instantie, NtfyMeldingen)
        assert instantie.aan is False
        assert ("module_loaded", {"name": "ntfy_meldingen"}) in bus.gepubliceerd

    def test_init_module_leest_de_omgeving(self, monkeypatch):
        monkeypatch.setattr(ntfy_meldingen, "load_dotenv", None)
        monkeypatch.setenv("NTFY_URL", URL)
        monkeypatch.setenv("NTFY_TOPIC", TOPIC)
        monkeypatch.delenv("NTFY_ZELFTEST_NA_SECONDEN", raising=False)
        monkeypatch.setenv("NTFY_OPSTARTMELDING", "uit")
        bus = DummyEventBus()
        instantie = init_module(bus)
        assert instantie.aan is True
        assert instantie.url == URL
        assert instantie.topic == TOPIC


# ----------------------------------------------------------------
# De beslissing: naar de gsm of niet
# ----------------------------------------------------------------

class TestBeslissing:
    def test_antwoord_op_eigen_bericht_gaat_nooit_naar_de_gsm(self):
        module, _, post, _ = maak(FakeBridge(verbonden=False))
        assert module.verwerk_bericht(BERICHT, is_hoofdthread=True) is False
        assert post.aanroepen == []

    def test_proactief_en_actief_op_laptop_gaat_niet_naar_de_gsm(self):
        module, _, post, _ = maak(FakeBridge(verbonden=True, focus="actief", activiteit="coding"))
        assert module.verwerk_bericht(BERICHT, is_hoofdthread=False) is False
        assert post.aanroepen == []

    def test_proactief_laptop_niet_verbonden_gaat_naar_de_gsm(self):
        module, _, post, _ = maak(FakeBridge(verbonden=False))
        assert module.verwerk_bericht(BERICHT, is_hoofdthread=False) is True
        assert len(post.aanroepen) == 1

    def test_proactief_laptop_vergrendeld_gaat_naar_de_gsm(self):
        # Het vergrendelscherm komt binnen als activiteit "afwezig",
        # ook als de focus nog even "actief" lijkt (wachtwoord intypen).
        module, _, post, _ = maak(FakeBridge(focus="actief", activiteit="afwezig"))
        assert module.verwerk_bericht(BERICHT, is_hoofdthread=False) is True
        assert len(post.aanroepen) == 1

    @pytest.mark.parametrize("niveau", ["inactief", "onbekend", "weg", ""])
    def test_proactief_focus_niet_actief_gaat_naar_de_gsm(self, niveau):
        module, _, post, _ = maak(FakeBridge(focus=niveau))
        assert module.verwerk_bericht(BERICHT, is_hoofdthread=False) is True
        assert len(post.aanroepen) == 1

    def test_geen_verse_focusdata_gaat_naar_de_gsm(self):
        module, _, post, _ = maak(FakeBridge(focus_data=None))
        assert module.verwerk_bericht(BERICHT, is_hoofdthread=False) is True

    def test_geen_verse_activiteitsdata_gaat_naar_de_gsm(self):
        module, _, post, _ = maak(FakeBridge(activiteit_data=None))
        assert module.verwerk_bericht(BERICHT, is_hoofdthread=False) is True

    def test_client_bridge_niet_gevonden_gaat_naar_de_gsm(self):
        module, _, post, _ = maak(bridge=None)
        assert module.verwerk_bericht(BERICHT, is_hoofdthread=False) is True
        assert len(post.aanroepen) == 1

    def test_fout_in_de_bridge_gaat_naar_de_gsm_zonder_crash(self):
        module, _, post, _ = maak(FakeBridge(fout=RuntimeError("kapot")))
        assert module.verwerk_bericht(BERICHT, is_hoofdthread=False) is True
        assert len(post.aanroepen) == 1

    def test_oude_bridge_zonder_max_leeftijd_gaat_naar_de_gsm(self):
        # Als de aanpassing in client_bridge.py nog niet gedaan is, mag dat
        # nooit een crash geven: dan gaat het (veilig) naar de gsm.
        class OudeBridge:
            def is_laptop_verbonden(self):
                return True

            def get_laatste_activity(self):
                return {"activity": "coding"}

            def get_laatste_focus(self):
                return {"focus_level": "actief"}

        module, _, post, _ = maak(OudeBridge())
        assert module.verwerk_bericht(BERICHT, is_hoofdthread=False) is True

    def test_vraagt_korte_vers_tijd_aan_de_bridge(self):
        bridge = FakeBridge()
        module, _, _, _ = maak(bridge)
        module.verwerk_bericht(BERICHT, is_hoofdthread=False)
        assert bridge.focus_leeftijden == [FOCUS_MAX_LEEFTIJD_SECONDEN]
        assert bridge.activiteit_leeftijden == [FOCUS_MAX_LEEFTIJD_SECONDEN]
        assert FOCUS_MAX_LEEFTIJD_SECONDEN == 45

    def test_module_gevonden_via_loaded_modules_als_modules_ontbreekt(self):
        class BusZonderModules:
            def __init__(self):
                self.loaded_modules = {"client_bridge": FakeBridge(verbonden=False)}

            def subscribe(self, *a):
                pass

        post = NepPost()
        module = NtfyMeldingen(BusZonderModules(), url=URL, topic=TOPIC,
                               http_post=post, achtergrond=False, zelftest_na_seconden=0, opstart_melding=False)
        assert module.verwerk_bericht(BERICHT, is_hoofdthread=False) is True


# ----------------------------------------------------------------
# De hoofdthread-regel via het echte event
# ----------------------------------------------------------------

class TestThreadRegel:
    def test_event_vanuit_hoofdthread_wordt_niet_verstuurd(self):
        module, _, post, _ = maak(FakeBridge(verbonden=False))
        module._on_chat_response(dict(BERICHT))
        assert post.aanroepen == []

    def test_event_vanuit_achtergrondthread_wordt_verstuurd(self):
        module, _, post, _ = maak(FakeBridge(verbonden=False))
        draad = threading.Thread(target=module._on_chat_response, args=(dict(BERICHT),))
        draad.start()
        draad.join()
        assert len(post.aanroepen) == 1

    def test_handler_accepteert_een_of_twee_argumenten(self):
        module, _, post, _ = maak(FakeBridge(verbonden=False))
        draad = threading.Thread(target=module._on_chat_response,
                                 args=(dict(BERICHT), "chat_response"))
        draad.start()
        draad.join()
        assert len(post.aanroepen) == 1

    @pytest.mark.parametrize("rommel", [None, "tekst", 42, [], ("a", "b")])
    def test_kapotte_data_geeft_geen_crash(self, rommel):
        module, _, post, _ = maak(FakeBridge(verbonden=False))
        draad = threading.Thread(target=module._on_chat_response, args=(rommel,))
        draad.start()
        draad.join()
        assert post.aanroepen == []


# ----------------------------------------------------------------
# Versturen
# ----------------------------------------------------------------

class TestVersturen:
    def test_juiste_adres_inhoud_titel_en_timeout(self):
        module, _, post, _ = maak(FakeBridge(verbonden=False))
        module.verwerk_bericht({"text": "Mist in Aartrijke 🙂"}, is_hoofdthread=False)
        aanroep = post.aanroepen[0]
        assert aanroep["url"] == f"{URL}/{TOPIC}"
        assert aanroep["data"] == "Mist in Aartrijke 🙂".encode("utf-8")
        assert aanroep["headers"] == {"Title": "Nova"}
        assert aanroep["timeout"] == 5

    def test_msg_veld_werkt_ook(self):
        module, _, post, _ = maak(FakeBridge(verbonden=False))
        module.verwerk_bericht({"msg": "via msg"}, is_hoofdthread=False)
        assert post.aanroepen[0]["data"] == b"via msg"

    @pytest.mark.parametrize("data", [{}, {"text": ""}, {"text": "   "}, {"text": None}, {"text": 5}])
    def test_lege_of_ongeldige_tekst_wordt_niet_verstuurd(self, data):
        module, _, post, _ = maak(FakeBridge(verbonden=False))
        assert module.verwerk_bericht(data, is_hoofdthread=False) is False
        assert post.aanroepen == []

    def test_serverfout_geeft_geen_crash(self, capsys):
        module, _, post, _ = maak(FakeBridge(verbonden=False), post=NepPost(status_code=500))
        module.verwerk_bericht(BERICHT, is_hoofdthread=False)
        assert "500" in capsys.readouterr().out

    def test_onbereikbare_server_geeft_geen_crash_en_toont_het_kanaal_niet(self, capsys):
        fout = ConnectionError(f"kon {URL}/{TOPIC} niet bereiken")
        module, _, _, _ = maak(FakeBridge(verbonden=False), post=NepPost(fout=fout))
        module.verwerk_bericht(BERICHT, is_hoofdthread=False)
        uitvoer = capsys.readouterr().out
        assert "Versturen mislukt" in uitvoer
        assert TOPIC not in uitvoer
        assert "<kanaal>" in uitvoer

    def test_kanaalnaam_komt_nooit_in_het_log_bij_succes(self, capsys):
        module, _, _, _ = maak(FakeBridge(verbonden=False))
        module.verwerk_bericht(BERICHT, is_hoofdthread=False)
        assert TOPIC not in capsys.readouterr().out

    def test_verzenden_in_achtergrondthread_blokkeert_niet(self):
        # Een trage server mag de aanroeper niet ophouden.
        gestart = threading.Event()
        vrijgeven = threading.Event()

        def trage_post(url, data=None, headers=None, timeout=None):
            gestart.set()
            vrijgeven.wait(5)
            return NepAntwoord(200)

        bus = DummyEventBus()
        bus.modules["client_bridge"] = FakeBridge(verbonden=False)
        module = NtfyMeldingen(bus, url=URL, topic=TOPIC, http_post=trage_post,
                               achtergrond=True, zelftest_na_seconden=0, opstart_melding=False)

        begin = time.time()
        assert module.verwerk_bericht(BERICHT, is_hoofdthread=False) is True
        assert time.time() - begin < 1.0
        assert gestart.wait(2)
        vrijgeven.set()
        module._laatste_thread.join(2)

    def test_lang_bericht_wordt_ingekort_en_blijft_geldige_utf8(self):
        lang = "ééé🙂" * 2000
        module, _, post, _ = maak(FakeBridge(verbonden=False))
        module.verwerk_bericht({"text": lang}, is_hoofdthread=False)
        verstuurd = post.aanroepen[0]["data"]
        assert len(verstuurd) <= 4096
        verstuurd.decode("utf-8")  # mag niet crashen

    def test_kort_bericht_blijft_ongewijzigd(self):
        assert kort_in("hallo 🙂") == "hallo 🙂"


# ----------------------------------------------------------------
# Veiligheidsgrens: maximaal 20 per uur
# ----------------------------------------------------------------

class TestUurLimiet:
    def test_na_de_limiet_wordt_niets_meer_verstuurd(self):
        tijd = [1000.0]
        module, _, post, _ = maak(FakeBridge(verbonden=False), klok=lambda: tijd[0])
        for i in range(MAX_BERICHTEN_PER_UUR):
            assert module.verwerk_bericht({"text": f"bericht {i}"}, is_hoofdthread=False) is True
        assert module.verwerk_bericht({"text": "te veel"}, is_hoofdthread=False) is False
        assert len(post.aanroepen) == MAX_BERICHTEN_PER_UUR

    def test_na_een_uur_mag_het_weer(self):
        tijd = [1000.0]
        module, _, post, _ = maak(FakeBridge(verbonden=False), klok=lambda: tijd[0])
        for i in range(MAX_BERICHTEN_PER_UUR):
            module.verwerk_bericht({"text": f"bericht {i}"}, is_hoofdthread=False)
        tijd[0] += 3601
        assert module.verwerk_bericht({"text": "weer ruimte"}, is_hoofdthread=False) is True

    def test_limiet_wordt_maar_een_keer_gemeld(self, capsys):
        module, _, _, _ = maak(FakeBridge(verbonden=False), klok=lambda: 1000.0)
        for i in range(MAX_BERICHTEN_PER_UUR + 5):
            module.verwerk_bericht({"text": f"bericht {i}"}, is_hoofdthread=False)
        assert capsys.readouterr().out.count("Limiet van") == 1

    def test_berichten_die_niet_naar_de_gsm_gaan_tellen_niet_mee(self):
        module, _, post, _ = maak(FakeBridge(verbonden=True, focus="actief"), klok=lambda: 1000.0)
        for i in range(MAX_BERICHTEN_PER_UUR + 5):
            module.verwerk_bericht({"text": f"bericht {i}"}, is_hoofdthread=False)
        assert post.aanroepen == []
        assert module._verstuurd == []


# ----------------------------------------------------------------
# Opstartmelding ("Nova is opgestart om HH:MM")
# ----------------------------------------------------------------

class TestOpstartmelding:
    def _maak(self, post, slaap=None, **extra):
        bus = DummyEventBus()
        # Bewust GEEN client_bridge: de opstartmelding mag daar niet van afhangen.
        return NtfyMeldingen(bus, url=URL, topic=TOPIC, http_post=post,
                             achtergrond=False, zelftest_na_seconden=0,
                             slaap=slaap or (lambda s: None), **extra)

    def test_uit_als_opgegeven(self):
        post = NepPost()
        module = self._maak(post, opstart_melding=False)
        assert module._opstart_thread is None
        assert post.aanroepen == []

    def test_aan_stuurt_een_melding_met_het_tijdstip(self):
        import re
        post = NepPost()
        module = self._maak(post, opstart_melding=True)
        module._opstart_thread.join(3)
        assert len(post.aanroepen) == 1
        tekst = post.aanroepen[0]["data"].decode("utf-8")
        assert re.fullmatch(r"Nova is opgestart om \d\d:\d\d\.", tekst)
        assert post.aanroepen[0]["url"] == f"{URL}/{TOPIC}"
        assert post.aanroepen[0]["headers"] == {"Title": "Nova"}

    def test_gaat_altijd_naar_de_gsm_ook_als_je_actief_op_de_laptop_bent(self):
        bus = DummyEventBus()
        bus.modules["client_bridge"] = FakeBridge(verbonden=True, focus="actief")
        post = NepPost()
        module = NtfyMeldingen(bus, url=URL, topic=TOPIC, http_post=post,
                               achtergrond=False, zelftest_na_seconden=0,
                               opstart_melding=True, slaap=lambda s: None)
        module._opstart_thread.join(3)
        assert len(post.aanroepen) == 1

    def test_probeert_opnieuw_tot_ntfy_bereikbaar_is(self):
        pogingen = {"n": 0}
        geslapen = []

        def wisselvallig(url, data=None, headers=None, timeout=None):
            pogingen["n"] += 1
            if pogingen["n"] < 3:
                raise ConnectionError("ntfy start nog op")
            return NepAntwoord(200)

        bus = DummyEventBus()
        module = NtfyMeldingen(bus, url=URL, topic=TOPIC, http_post=wisselvallig,
                               achtergrond=False, zelftest_na_seconden=0,
                               opstart_melding=False, slaap=geslapen.append)
        assert module._opstartmelding() is True
        assert pogingen["n"] == 3
        assert geslapen == [30, 30]

    def test_geeft_op_na_tien_pogingen_zonder_crash(self, capsys):
        geslapen = []
        post = NepPost(fout=ConnectionError(f"geen verbinding met {URL}/{TOPIC}"))
        bus = DummyEventBus()
        module = NtfyMeldingen(bus, url=URL, topic=TOPIC, http_post=post,
                               achtergrond=False, zelftest_na_seconden=0,
                               opstart_melding=False, slaap=geslapen.append)
        assert module._opstartmelding() is False
        assert len(post.aanroepen) == 10
        assert len(geslapen) == 9   # niet na de laatste poging
        uitvoer = capsys.readouterr().out
        assert "niet gelukt na 10 pogingen" in uitvoer
        assert TOPIC not in uitvoer

    def test_serverfout_telt_als_mislukte_poging(self):
        post = NepPost(status_code=503)
        bus = DummyEventBus()
        module = NtfyMeldingen(bus, url=URL, topic=TOPIC, http_post=post,
                               achtergrond=False, zelftest_na_seconden=0,
                               opstart_melding=False, slaap=lambda s: None)
        assert module._opstartmelding() is False
        assert len(post.aanroepen) == 10

    def test_telt_mee_voor_de_uurlimiet_en_wordt_geblokkeerd_bij_limiet(self):
        post = NepPost()
        bus = DummyEventBus()
        module = NtfyMeldingen(bus, url=URL, topic=TOPIC, http_post=post,
                               achtergrond=False, zelftest_na_seconden=0,
                               opstart_melding=False, slaap=lambda s: None,
                               klok=lambda: 1000.0)
        module._verstuurd = [1000.0] * MAX_BERICHTEN_PER_UUR
        assert module._opstartmelding() is False
        assert post.aanroepen == []

    @pytest.mark.parametrize("ruw, verwacht", [
        ("uit", False), ("UIT", False), ("nee", False), ("0", False),
        ("false", False), ("off", False),
        ("aan", True), ("", True), ("ja", True), ("1", True),
    ])
    def test_env_instelling(self, monkeypatch, ruw, verwacht):
        monkeypatch.setattr(ntfy_meldingen, "load_dotenv", None)
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.setenv("NTFY_OPSTARTMELDING", ruw)
        module, _, _, _ = maak()
        assert module._opstart_melding_aan(None) is verwacht

    def test_standaard_zonder_env_staat_aan(self, monkeypatch):
        monkeypatch.setattr(ntfy_meldingen, "load_dotenv", None)
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.delenv("NTFY_OPSTARTMELDING", raising=False)
        module, _, _, _ = maak()
        assert module._opstart_melding_aan(None) is True

    def test_tijdens_een_pytest_run_nooit_automatisch_aan(self, monkeypatch):
        # Veiligheid: een test die per ongeluk de hele module laadt, mag
        # nooit een echte melding naar Kevins gsm sturen.
        monkeypatch.setattr(ntfy_meldingen, "load_dotenv", None)
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "iets")
        monkeypatch.delenv("NTFY_OPSTARTMELDING", raising=False)
        module, _, _, _ = maak()
        assert module._opstart_melding_aan(None) is False
        # ...maar een expliciete opdracht in een test blijft werken.
        assert module._opstart_melding_aan(True) is True

    def test_geen_opstartmelding_als_de_module_uit_staat(self):
        post = NepPost()
        module = NtfyMeldingen(DummyEventBus(), url="", topic="", http_post=post,
                               zelftest_na_seconden=0, opstart_melding=True)
        assert module._opstart_thread is None
        assert post.aanroepen == []


# ----------------------------------------------------------------
# Zelftest (NTFY_ZELFTEST_NA_SECONDEN)
# ----------------------------------------------------------------

class TestZelftest:
    def test_zonder_instelling_geen_timer(self):
        module, _, _, _ = maak()
        assert module._zelftest_timer is None

    def test_zelftest_stuurt_naar_gsm_als_laptop_niet_actief(self):
        module, _, post, _ = maak(FakeBridge(verbonden=False))
        module._zelftest()
        assert len(post.aanroepen) == 1
        assert b"testbericht" in post.aanroepen[0]["data"]

    def test_zelftest_stuurt_niet_als_je_actief_bent_op_de_laptop(self, capsys):
        module, _, post, _ = maak(FakeBridge(verbonden=True, focus="actief"))
        module._zelftest()
        assert post.aanroepen == []
        assert "Niet naar de gsm" in capsys.readouterr().out

    def test_timer_vuurt_echt_af(self):
        bus = DummyEventBus()
        bus.modules["client_bridge"] = FakeBridge(verbonden=False)
        post = NepPost()
        module = NtfyMeldingen(bus, url=URL, topic=TOPIC, http_post=post,
                               achtergrond=False, zelftest_na_seconden=0.05, opstart_melding=False)
        assert module._zelftest_timer is not None
        module._zelftest_timer.join(3)
        assert len(post.aanroepen) == 1

    def test_zelftest_met_fout_in_de_bridge_crasht_niet(self):
        module, _, post, _ = maak(FakeBridge(fout=RuntimeError("kapot")))
        module._zelftest()
        assert len(post.aanroepen) == 1

    @pytest.mark.parametrize("ruw, verwacht", [
        ("90", 90), ("1", 5), ("9999", 600), ("5", 5), ("600", 600),
        ("0", 0), ("-3", 0), ("abc", 0), ("", 0), ("2.5", 0),
    ])
    def test_wachttijd_uit_env_wordt_begrensd(self, monkeypatch, ruw, verwacht):
        monkeypatch.setattr(ntfy_meldingen, "load_dotenv", None)
        monkeypatch.setenv("NTFY_ZELFTEST_NA_SECONDEN", ruw)
        module, _, _, _ = maak()
        assert module._bepaal_zelftest_wachttijd(None) == verwacht

    def test_zonder_env_geen_zelftest(self, monkeypatch):
        monkeypatch.setattr(ntfy_meldingen, "load_dotenv", None)
        monkeypatch.delenv("NTFY_ZELFTEST_NA_SECONDEN", raising=False)
        module, _, _, _ = maak()
        assert module._bepaal_zelftest_wachttijd(None) == 0

    def test_init_module_met_env_plant_de_zelftest(self, monkeypatch):
        monkeypatch.setattr(ntfy_meldingen, "load_dotenv", None)
        monkeypatch.setenv("NTFY_URL", URL)
        monkeypatch.setenv("NTFY_TOPIC", TOPIC)
        monkeypatch.setenv("NTFY_ZELFTEST_NA_SECONDEN", "600")
        monkeypatch.setenv("NTFY_OPSTARTMELDING", "uit")
        instantie = init_module(DummyEventBus())
        try:
            assert instantie._zelftest_timer is not None
        finally:
            instantie._zelftest_timer.cancel()


# ----------------------------------------------------------------
# De ECHTE ClientBridge: nieuwe max_leeftijd-parameter
# ----------------------------------------------------------------

@pytest.fixture
def echte_bridge(monkeypatch):
    from modules.network.client_bridge import ClientBridge
    monkeypatch.setattr(ClientBridge, "_start_server_in_achtergrond", lambda self: None)
    return ClientBridge(DummyEventBus())


class TestEchteClientBridge:
    def test_standaard_blijft_180_seconden(self, echte_bridge):
        echte_bridge._laatste_focus = {"focus_level": "actief"}
        echte_bridge._laatste_focus_tijd = time.time() - 100
        echte_bridge._laatste_activity = {"activity": "coding"}
        echte_bridge._laatste_activity_tijd = time.time() - 100
        assert echte_bridge.get_laatste_focus() == {"focus_level": "actief"}
        assert echte_bridge.get_laatste_activity() == {"activity": "coding"}

    def test_standaard_vervalt_na_180_seconden(self, echte_bridge):
        echte_bridge._laatste_focus = {"focus_level": "actief"}
        echte_bridge._laatste_focus_tijd = time.time() - 200
        echte_bridge._laatste_activity = {"activity": "coding"}
        echte_bridge._laatste_activity_tijd = time.time() - 200
        assert echte_bridge.get_laatste_focus() is None
        assert echte_bridge.get_laatste_activity() is None

    def test_met_korte_leeftijd_vervalt_data_van_100_seconden(self, echte_bridge):
        echte_bridge._laatste_focus = {"focus_level": "actief"}
        echte_bridge._laatste_focus_tijd = time.time() - 100
        echte_bridge._laatste_activity = {"activity": "coding"}
        echte_bridge._laatste_activity_tijd = time.time() - 100
        assert echte_bridge.get_laatste_focus(45) is None
        assert echte_bridge.get_laatste_activity(45) is None

    def test_met_korte_leeftijd_blijft_verse_data_geldig(self, echte_bridge):
        echte_bridge._laatste_focus = {"focus_level": "actief"}
        echte_bridge._laatste_focus_tijd = time.time() - 10
        echte_bridge._laatste_activity = {"activity": "coding"}
        echte_bridge._laatste_activity_tijd = time.time() - 10
        assert echte_bridge.get_laatste_focus(45) == {"focus_level": "actief"}
        assert echte_bridge.get_laatste_activity(45) == {"activity": "coding"}

    def test_nooit_ontvangen_data_is_nooit_vers(self, echte_bridge):
        assert echte_bridge.get_laatste_focus(45) is None
        assert echte_bridge.get_laatste_activity(45) is None

    def test_presence_ongewijzigd(self, echte_bridge):
        echte_bridge._laatste_presence = {"faces_detected": 1}
        echte_bridge._laatste_presence_tijd = time.time() - 300
        assert echte_bridge.get_laatste_presence() == {"faces_detected": 1}

    def test_ntfy_met_de_echte_bridge_van_actief_naar_dicht(self, echte_bridge):
        # Hele keten: laptop actief -> geen gsm; verbinding weg -> wel gsm.
        bus = DummyEventBus()
        bus.modules["client_bridge"] = echte_bridge
        post = NepPost()
        module = NtfyMeldingen(bus, url=URL, topic=TOPIC, http_post=post,
                               achtergrond=False, zelftest_na_seconden=0, opstart_melding=False)

        echte_bridge._actieve_websocket = object()
        echte_bridge._laatste_focus = {"focus_level": "actief"}
        echte_bridge._laatste_focus_tijd = time.time()
        echte_bridge._laatste_activity = {"activity": "coding"}
        echte_bridge._laatste_activity_tijd = time.time()
        assert module.verwerk_bericht(BERICHT, is_hoofdthread=False) is False

        # Laptop dichtgeklapt: de verbinding valt weg.
        echte_bridge._actieve_websocket = None
        assert module.verwerk_bericht(BERICHT, is_hoofdthread=False) is True
        assert len(post.aanroepen) == 1

    def test_ntfy_met_de_echte_bridge_bij_oude_data_en_vergrendeling(self, echte_bridge):
        bus = DummyEventBus()
        bus.modules["client_bridge"] = echte_bridge
        post = NepPost()
        module = NtfyMeldingen(bus, url=URL, topic=TOPIC, http_post=post,
                               achtergrond=False, zelftest_na_seconden=0, opstart_melding=False)
        echte_bridge._actieve_websocket = object()

        # Half open verbinding: nog "verbonden", maar de data is 100 s oud.
        echte_bridge._laatste_focus = {"focus_level": "actief"}
        echte_bridge._laatste_focus_tijd = time.time() - 100
        echte_bridge._laatste_activity = {"activity": "coding"}
        echte_bridge._laatste_activity_tijd = time.time() - 100
        assert module.verwerk_bericht(BERICHT, is_hoofdthread=False) is True

        # Verse data, maar vergrendeld.
        echte_bridge._laatste_focus_tijd = time.time()
        echte_bridge._laatste_activity = {"activity": "afwezig"}
        echte_bridge._laatste_activity_tijd = time.time()
        assert module.verwerk_bericht(BERICHT, is_hoofdthread=False) is True
        assert len(post.aanroepen) == 2