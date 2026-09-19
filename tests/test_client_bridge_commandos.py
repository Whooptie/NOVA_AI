# test_client_bridge_commandos.py
#
# Test de NIEUWE server->laptop-uitbreiding van client_bridge.py
# (Deel A, client_server_control_roadmap.md): stuur_commando_naar_laptop(),
# is_laptop_verbonden(), en de interne resultaat-koppeling via
# _verwerk_commando_resultaat().
#
# Test BEWUST NIET opnieuw wat al bestond (de drie Remote*Detector-
# klassen, get_laatste_activity/focus/presence, de veroudering-check)
# -- dat is ongewijzigd gebleven en dus al gedekt door de bestaande
# testsuite. Enkel de NIEUWE code hieronder.
#
# Aanpak: GEEN echte WebSocket-server/verbinding opgestart (dat zou
# een trage, netwerk-afhankelijke test geven). In plaats daarvan wordt
# ClientBridge.__init__() z'n eigen _start_server_in_achtergrond()
# overgeslagen (via monkeypatch), en simuleren we een "verbonden
# laptop" gewoon door de interne attributen (_actieve_websocket,
# _event_loop) rechtstreeks te zetten -- exact zoals _verwerk_client()
# dat in het echt ook zou doen.

import asyncio
import json
import threading
import time

import pytest

from modules.network import client_bridge


# ----------------------------------------------------------------
# Nep-EventBus -- zelfde minimale vorm als de rest van de testsuite
# (publish/subscribe/modules-dict, geen echte routing nodig hier).
# ----------------------------------------------------------------
class NepEventBus:
    def __init__(self):
        self.gepubliceerde_events = []
        self.modules = {}

    def publish(self, event_type, data=None):
        self.gepubliceerde_events.append((event_type, data))

    def subscribe(self, event_type, handler):
        pass

    def register_module(self, naam, instance):
        self.modules[naam] = instance


# ----------------------------------------------------------------
# Nep-websocket: vervangt de echte 'websockets'-connectie. Houdt bij
# wat er verstuurd is (self.verstuurde_berichten), zodat een test kan
# nakijken of stuur_commando_naar_laptop() het juiste JSON-bericht
# effectief probeerde te versturen.
# ----------------------------------------------------------------
class NepWebSocket:
    def __init__(self, laat_versturen_falen=False):
        self.verstuurde_berichten = []
        self.laat_versturen_falen = laat_versturen_falen

    async def send(self, bericht):
        if self.laat_versturen_falen:
            raise ConnectionError("nep-verbinding is dood")
        self.verstuurde_berichten.append(bericht)


@pytest.fixture
def bridge(monkeypatch):
    """
    Een ClientBridge-instance MET een simulatie van een actieve
    event-loop, maar ZONDER echte WebSocket-server erbij (die start
    normaal in __init__ via _start_server_in_achtergrond() -- hier
    overgeslagen, want we testen enkel de commando-logica, niet de
    server-opstart zelf).
    """
    monkeypatch.setattr(
        client_bridge.ClientBridge, "_start_server_in_achtergrond", lambda self: None
    )
    event_bus = NepEventBus()
    instance = client_bridge.ClientBridge(event_bus)
    return instance


@pytest.fixture
def draaiende_loop():
    """
    Een ECHTE, draaiende asyncio-event-loop in een eigen achtergrond-
    thread -- nodig omdat stuur_commando_naar_laptop() intern
    asyncio.run_coroutine_threadsafe() gebruikt, wat een loop vereist
    die daadwerkelijk aan het draaien is (niet enkel aangemaakt).
    Wordt na de test netjes afgesloten.
    """
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    yield loop
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=2)
    loop.close()


def _simuleer_verbonden_laptop(bridge, websocket, event_loop):
    """Zet de interne staat alsof _verwerk_client() net een laptop-
    verbinding geaccepteerd heeft -- zonder de echte WebSocket-server
    nodig te hebben."""
    with bridge._lock:
        bridge._actieve_websocket = websocket
        bridge._event_loop = event_loop


# ------------------------------------------------------------------
# is_laptop_verbonden()
# ------------------------------------------------------------------

def test_is_laptop_verbonden_false_zonder_verbinding(bridge):
    assert bridge.is_laptop_verbonden() is False


def test_is_laptop_verbonden_true_na_simulatie(bridge, draaiende_loop):
    _simuleer_verbonden_laptop(bridge, NepWebSocket(), draaiende_loop)
    assert bridge.is_laptop_verbonden() is True


# ------------------------------------------------------------------
# stuur_commando_naar_laptop() -- geen laptop verbonden
# ------------------------------------------------------------------

def test_stuur_commando_zonder_verbonden_laptop_geeft_eerlijke_fout(bridge):
    resultaat = bridge.stuur_commando_naar_laptop("open_app", {"app": "chrome"})

    assert resultaat["ok"] is False
    assert "niet verbonden" in resultaat["reden"]


# ------------------------------------------------------------------
# stuur_commando_naar_laptop() -- verzending mislukt
# ------------------------------------------------------------------

def test_stuur_commando_verzendfout_geeft_eerlijke_fout(bridge, draaiende_loop):
    kapotte_websocket = NepWebSocket(laat_versturen_falen=True)
    _simuleer_verbonden_laptop(bridge, kapotte_websocket, draaiende_loop)

    resultaat = bridge.stuur_commando_naar_laptop(
        "open_app", {"app": "chrome"}, timeout_seconden=2
    )

    assert resultaat["ok"] is False
    assert "Versturen naar laptop mislukt" in resultaat["reden"]

    # Geen commando mag als "wachtend" blijven hangen na een mislukte
    # verzending -- zou anders een stil geheugenlek in
    # _wachtende_commandos geven bij herhaalde mislukkingen.
    assert bridge._wachtende_commandos == {}


# ------------------------------------------------------------------
# stuur_commando_naar_laptop() -- timeout (laptop antwoordt nooit)
# ------------------------------------------------------------------

def test_stuur_commando_timeout_als_laptop_niet_antwoordt(bridge, draaiende_loop):
    websocket = NepWebSocket()
    _simuleer_verbonden_laptop(bridge, websocket, draaiende_loop)

    # Kleine timeout, zodat de test niet nodeloos lang duurt --
    # simuleert een laptop die het bericht wel ontvangt (het staat
    # straks in websocket.verstuurde_berichten) maar NOOIT een
    # command_result terugstuurt.
    resultaat = bridge.stuur_commando_naar_laptop(
        "open_app", {"app": "chrome"}, timeout_seconden=0.3
    )

    assert resultaat["ok"] is False
    assert "Geen antwoord" in resultaat["reden"]

    # Het commando moet wel degelijk VERSTUURD zijn (de timeout zit 'm
    # in het uitblijven van een antwoord, niet in het versturen zelf).
    assert len(websocket.verstuurde_berichten) == 1
    verstuurd = json.loads(websocket.verstuurde_berichten[0])
    assert verstuurd["type"] == "open_app"
    assert verstuurd["app"] == "chrome"
    assert "command_id" in verstuurd

    # Na de timeout mag er niets blijvends achterblijven.
    assert bridge._wachtende_commandos == {}


# ------------------------------------------------------------------
# stuur_commando_naar_laptop() -- gelukt scenario, end-to-end
# ------------------------------------------------------------------

def test_stuur_commando_geslaagd_resultaat_end_to_end(bridge, draaiende_loop):
    """
    Simuleert het VOLLEDIGE gelukte pad: commando versturen, dan --
    alsof nova_client.py intussen geantwoord heeft -- een
    "command_result"-bericht laten binnenkomen via _verwerk_bericht(),
    en controleren dat stuur_commando_naar_laptop() daadwerkelijk het
    juiste resultaat teruggeeft (niet enkel een timeout).

    Het "antwoord van de laptop" wordt in een aparte thread ingepland
    met een kleine vertraging -- want stuur_commando_naar_laptop()
    zelf BLOKKEERT tot er een antwoord is (of een timeout), dus het
    antwoord moet van "buitenaf" binnenkomen terwijl de hoofdthread
    van de test al aan het wachten is.
    """
    websocket = NepWebSocket()
    _simuleer_verbonden_laptop(bridge, websocket, draaiende_loop)

    def stuur_nep_antwoord_na_korte_vertraging():
        # Wacht tot het commando effectief verstuurd is, zodat het
        # command_id al bestaat in _wachtende_commandos.
        deadline = time.time() + 2
        while time.time() < deadline:
            with bridge._lock:
                if bridge._wachtende_commandos:
                    commando_id = next(iter(bridge._wachtende_commandos))
                    break
            time.sleep(0.01)
        else:
            return  # commando kwam er nooit -- de hoofdtest zal falen op de timeout

        nep_bericht = json.dumps({
            "type": "command_result",
            "command_id": commando_id,
            "ok": True,
            "app": "chrome",
            "reden": None,
        })
        bridge._verwerk_bericht(nep_bericht)

    achtergrond_thread = threading.Thread(target=stuur_nep_antwoord_na_korte_vertraging)
    achtergrond_thread.start()

    resultaat = bridge.stuur_commando_naar_laptop(
        "open_app", {"app": "chrome"}, timeout_seconden=5
    )
    achtergrond_thread.join(timeout=2)

    assert resultaat == {"ok": True, "reden": None, "app": "chrome"}
    assert bridge._wachtende_commandos == {}


def test_stuur_commando_mislukt_resultaat_van_laptop(bridge, draaiende_loop):
    """Zelfde end-to-end-opzet als hierboven, maar de laptop meldt
    zelf terug dat de app niet in haar whitelist staat."""
    websocket = NepWebSocket()
    _simuleer_verbonden_laptop(bridge, websocket, draaiende_loop)

    def stuur_nep_weigering():
        deadline = time.time() + 2
        while time.time() < deadline:
            with bridge._lock:
                if bridge._wachtende_commandos:
                    commando_id = next(iter(bridge._wachtende_commandos))
                    break
            time.sleep(0.01)
        else:
            return

        nep_bericht = json.dumps({
            "type": "command_result",
            "command_id": commando_id,
            "ok": False,
            "app": "onbestaande_app",
            "reden": "'onbestaande_app' staat niet in mijn toegestane app-lijst.",
        })
        bridge._verwerk_bericht(nep_bericht)

    achtergrond_thread = threading.Thread(target=stuur_nep_weigering)
    achtergrond_thread.start()

    resultaat = bridge.stuur_commando_naar_laptop(
        "open_app", {"app": "onbestaande_app"}, timeout_seconden=5
    )
    achtergrond_thread.join(timeout=2)

    assert resultaat["ok"] is False
    assert "toegestane app-lijst" in resultaat["reden"]


# ------------------------------------------------------------------
# _verwerk_commando_resultaat() -- onbekend/verlopen command_id
# ------------------------------------------------------------------

def test_commando_resultaat_met_onbekend_id_wordt_genegeerd(bridge, capsys):
    """
    Een command_result met een command_id dat niet (meer) in
    _wachtende_commandos zit -- bv. na een timeout die het al
    opgeruimd heeft -- mag NOOIT een crash geven, enkel een nette
    log-regel (zelfde eerlijke, defensieve stijl als de rest van
    _verwerk_bericht()).
    """
    nep_bericht = json.dumps({
        "type": "command_result",
        "command_id": 9999,
        "ok": True,
        "app": "chrome",
    })

    bridge._verwerk_bericht(nep_bericht)  # mag geen exception gooien

    output = capsys.readouterr().out
    assert "onbekend/verlopen ID genegeerd" in output


# ------------------------------------------------------------------
# Meerdere commando's tegelijk -- command_id's mogen niet door elkaar
# lopen (elk commando krijgt terecht z'n EIGEN resultaat).
# ------------------------------------------------------------------

def test_twee_commandos_tegelijk_krijgen_elk_hun_eigen_resultaat(bridge, draaiende_loop):
    websocket = NepWebSocket()
    _simuleer_verbonden_laptop(bridge, websocket, draaiende_loop)

    resultaten = {}

    def stuur_commando(app_naam, key):
        resultaten[key] = bridge.stuur_commando_naar_laptop(
            "open_app", {"app": app_naam}, timeout_seconden=5
        )

    def beantwoord_beide_commandos():
        # Wacht tot BEIDE commando's daadwerkelijk VERSTUURD zijn (te
        # zien aan websocket.verstuurde_berichten, niet aan
        # _wachtende_commandos -- dat laatste kan een raceconditie geven
        # als commando 1 al beantwoord+opgeruimd is terwijl commando 2
        # nog onderweg is, waardoor len() nooit gelijktijdig op 2 komt).
        deadline = time.time() + 2
        while time.time() < deadline:
            if len(websocket.verstuurde_berichten) >= 2:
                break
            time.sleep(0.01)
        else:
            return

        # Koppel elk ID aan het juiste, verstuurde bericht zodat we
        # weten welk ID bij "chrome" en welk bij "notepad" hoort.
        for ruw_bericht in list(websocket.verstuurde_berichten):
            verstuurd = json.loads(ruw_bericht)
            bridge._verwerk_bericht(json.dumps({
                "type": "command_result",
                "command_id": verstuurd["command_id"],
                "ok": True,
                "app": verstuurd["app"],
                "reden": None,
            }))

    thread_chrome = threading.Thread(target=stuur_commando, args=("chrome", "chrome"))
    thread_notepad = threading.Thread(target=stuur_commando, args=("notepad", "notepad"))
    beantwoorder = threading.Thread(target=beantwoord_beide_commandos)

    thread_chrome.start()
    thread_notepad.start()
    beantwoorder.start()

    thread_chrome.join(timeout=3)
    thread_notepad.join(timeout=3)
    beantwoorder.join(timeout=3)

    assert resultaten["chrome"]["app"] == "chrome"
    assert resultaten["notepad"]["app"] == "notepad"
    assert bridge._wachtende_commandos == {}