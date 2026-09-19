# test_nova_client_app_controller.py
#
# Test de AppController-klasse in nova_client.py (Deel A,
# client_server_control_roadmap.md) -- de kant die op de LAPTOP draait
# en effectief subprocess.Popen()/proces.terminate() aanroept.
#
# BELANGRIJKE BEPERKING, EERLIJK VERMELD: nova_client.py is een
# Windows-specifiek bestand (pygetwindow, ctypes.wintypes, cv2,
# mediapipe, ...) dat normaal enkel op Kevins Windows-laptop draait,
# niet in een Linux-testomgeving. Deze test importeert daarom NIET
# het hele nova_client.py-bestand (dat zou crashen op de
# Windows-only-imports/ctypes.wintypes buiten Windows) -- in plaats
# daarvan wordt de AppController-klasse (en APP_WHITELIST) hier
# ZELFSTANDIG, letterlijk gekopieerd getest, exact zoals de klasse in
# nova_client.py bedoeld is. subprocess.Popen() zelf wordt met
# monkeypatch vervangen door een nep-versie, zodat deze test op ELK
# platform draait EN nooit een echt programma opstart.
#
# Als je dit liever ANDERS test (bv. door het echte bestand alsnog te
# importeren op een Windows-testmachine), kan dat -- verwijder dan
# gewoon de lokale kopie hieronder en vervang 'import' door
# 'from nova_client import AppController, APP_WHITELIST'.
#
# GEEN pytest-asyncio NODIG: het project draait met de 'anyio'-plugin,
# niet met 'pytest-asyncio' -- en @pytest.mark.asyncio is een marker
# van pytest-asyncio zelf, die anyio niet herkent. Alle testfuncties
# hieronder zijn daarom gewone (niet-async) functies, die zelf via
# _run(...) (een kleine lokale helper rond asyncio.run()) de
# eigenlijke async-methode uitvoeren.
#
# NIEUW (19 september 2026): _close_app() + self._lopende_processen.
# Kernprincipe, zie ook de docstring in AppController.__init__()
# hieronder: Nova kan ENKEL sluiten wat ZIJZELF via _open_app() heeft
# geopend -- geen aparte whitelist-check nodig bij het sluiten zelf,
# want de garantie zit al in "staat het in _lopende_processen".

import asyncio
import json

import pytest


# ------------------------------------------------------------------
# Lokale, letterlijke kopie van APP_WHITELIST + AppController uit
# nova_client.py, om Windows-only imports te vermijden in deze
# testomgeving (zie toelichting hierboven).
# ------------------------------------------------------------------

APP_WHITELIST = {
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "notepad": r"C:\Windows\System32\notepad.exe",
    "verkenner": r"C:\Windows\explorer.exe",
}


class AppController:
    def __init__(self, websocket, event_loop):
        self.websocket = websocket
        self.event_loop = event_loop
        self._lopende_processen = {}

    async def verwerk_commando(self, data):
        commando_type = data.get("type")

        if commando_type == "open_app":
            await self._open_app(data)
        elif commando_type == "close_app":
            await self._close_app(data)
        else:
            pass  # in het echt: logger.warning(...)

    async def _open_app(self, data):
        app_naam = (data.get("app") or "").strip().lower()
        command_id = data.get("command_id")

        pad = APP_WHITELIST.get(app_naam)

        if pad is None:
            await self._stuur_resultaat(
                command_id, ok=False,
                reden=f"'{app_naam}' staat niet in mijn toegestane app-lijst.",
                app=app_naam,
            )
            return

        try:
            import subprocess
            proces = subprocess.Popen([pad])
            self._lopende_processen[app_naam] = proces
            await self._stuur_resultaat(command_id, ok=True, app=app_naam)
        except Exception as e:
            await self._stuur_resultaat(
                command_id, ok=False, reden=str(e), app=app_naam,
            )

    async def _close_app(self, data):
        app_naam = (data.get("app") or "").strip().lower()
        command_id = data.get("command_id")

        proces = self._lopende_processen.get(app_naam)

        if proces is None:
            await self._stuur_resultaat(
                command_id, ok=False,
                reden=f"Ik heb '{app_naam}' niet zelf geopend, dus ik kan het niet sluiten.",
                app=app_naam,
            )
            return

        if proces.poll() is not None:
            self._lopende_processen.pop(app_naam, None)
            await self._stuur_resultaat(
                command_id, ok=False,
                reden=f"'{app_naam}' was al gestopt.",
                app=app_naam,
            )
            return

        try:
            proces.terminate()
            self._lopende_processen.pop(app_naam, None)
            await self._stuur_resultaat(command_id, ok=True, app=app_naam)
        except Exception as e:
            await self._stuur_resultaat(
                command_id, ok=False, reden=str(e), app=app_naam,
            )

    async def _stuur_resultaat(self, command_id, ok, app, reden=None):
        bericht = {
            "type": "command_result",
            "command_id": command_id,
            "ok": ok,
            "app": app,
            "reden": reden,
        }
        try:
            await self.websocket.send(json.dumps(bericht, default=str))
        except Exception:
            pass  # in het echt: logger.error(...)


# ------------------------------------------------------------------
# Nep-websocket: legt vast welke resultaat-berichten verstuurd zijn.
# ------------------------------------------------------------------
class NepWebSocket:
    def __init__(self):
        self.verstuurde_berichten = []

    async def send(self, bericht):
        self.verstuurde_berichten.append(json.loads(bericht))


# ------------------------------------------------------------------
# Nep-proces: vervangt het object dat subprocess.Popen() teruggeeft.
# Simuleert poll() (None = leeft nog, getal = exitcode) en
# terminate(), zonder ooit een echt proces te starten.
# ------------------------------------------------------------------
class NepProces:
    def __init__(self, al_gestopt=False):
        self._gestopt = al_gestopt
        self.terminate_aangeroepen = False

    def poll(self):
        return 0 if self._gestopt else None

    def terminate(self):
        self.terminate_aangeroepen = True
        self._gestopt = True


def _run(coroutine):
    return asyncio.run(coroutine)


@pytest.fixture
def websocket():
    return NepWebSocket()


@pytest.fixture
def controller(websocket):
    return AppController(websocket, event_loop=None)


# ------------------------------------------------------------------
# open_app -- ongewijzigd gedrag, plus de NIEUWE registratie in
# _lopende_processen (nodig voor alle close_app-tests hieronder).
# ------------------------------------------------------------------

def test_open_app_whitelisted_roept_popen_aan_met_juist_pad(controller, websocket, monkeypatch):
    aangeroepen_met = {}

    class NepPopen:
        def __init__(self, argumenten):
            aangeroepen_met["argumenten"] = argumenten

    monkeypatch.setattr("subprocess.Popen", NepPopen)

    _run(controller.verwerk_commando({
        "type": "open_app", "app": "chrome", "command_id": 1,
    }))

    assert aangeroepen_met["argumenten"] == [APP_WHITELIST["chrome"]]
    assert websocket.verstuurde_berichten == [{
        "type": "command_result",
        "command_id": 1,
        "ok": True,
        "app": "chrome",
        "reden": None,
    }]


def test_open_app_registreert_proces_in_lopende_processen(controller, websocket, monkeypatch):
    nep_proces = NepProces()
    monkeypatch.setattr("subprocess.Popen", lambda argumenten: nep_proces)

    _run(controller.verwerk_commando({
        "type": "open_app", "app": "chrome", "command_id": 1,
    }))

    assert controller._lopende_processen["chrome"] is nep_proces


def test_open_app_hoofdlettergevoeligheid_en_spaties(controller, websocket, monkeypatch):
    monkeypatch.setattr("subprocess.Popen", lambda argumenten: NepProces())

    _run(controller.verwerk_commando({
        "type": "open_app", "app": "  Chrome  ", "command_id": 2,
    }))

    assert websocket.verstuurde_berichten[0]["ok"] is True
    assert websocket.verstuurde_berichten[0]["app"] == "chrome"


def test_open_app_niet_whitelisted_wordt_geweigerd(controller, websocket, monkeypatch):
    popen_aangeroepen = {"ja": False}

    def nep_popen(argumenten):
        popen_aangeroepen["ja"] = True
        return NepProces()

    monkeypatch.setattr("subprocess.Popen", nep_popen)

    _run(controller.verwerk_commando({
        "type": "open_app", "app": "malware.exe", "command_id": 3,
    }))

    assert popen_aangeroepen["ja"] is False, (
        "Popen() mag NOOIT aangeroepen worden voor een app buiten de whitelist"
    )
    assert websocket.verstuurde_berichten == [{
        "type": "command_result",
        "command_id": 3,
        "ok": False,
        "app": "malware.exe",
        "reden": "'malware.exe' staat niet in mijn toegestane app-lijst.",
    }]


def test_open_app_met_pad_injectie_poging_wordt_geweigerd(controller, websocket, monkeypatch):
    popen_aangeroepen = {"ja": False}
    monkeypatch.setattr(
        "subprocess.Popen",
        lambda argumenten: (popen_aangeroepen.update(ja=True), NepProces())[1],
    )

    _run(controller.verwerk_commando({
        "type": "open_app",
        "app": r"C:\Windows\System32\cmd.exe /c del /f /s /q C:\*",
        "command_id": 4,
    }))

    assert popen_aangeroepen["ja"] is False
    assert websocket.verstuurde_berichten[0]["ok"] is False


def test_open_app_popen_exception_geeft_nette_foutmelding(controller, websocket, monkeypatch):
    def nep_popen_die_faalt(argumenten):
        raise FileNotFoundError("Het systeem kan het opgegeven bestand niet vinden")

    monkeypatch.setattr("subprocess.Popen", nep_popen_die_faalt)

    _run(controller.verwerk_commando({
        "type": "open_app", "app": "chrome", "command_id": 5,
    }))

    resultaat = websocket.verstuurde_berichten[0]
    assert resultaat["ok"] is False
    assert resultaat["app"] == "chrome"
    assert "bestand niet vinden" in resultaat["reden"]

    # Een MISLUKTE open mag de app nooit als "lopend" registreren.
    assert "chrome" not in controller._lopende_processen


def test_onbekend_commandotype_wordt_genegeerd(controller, websocket, monkeypatch):
    popen_aangeroepen = {"ja": False}
    monkeypatch.setattr(
        "subprocess.Popen",
        lambda argumenten: (popen_aangeroepen.update(ja=True), NepProces())[1],
    )

    _run(controller.verwerk_commando({
        "type": "vernietig_alles", "app": "chrome", "command_id": 6,
    }))

    assert popen_aangeroepen["ja"] is False
    assert websocket.verstuurde_berichten == []


def test_command_id_nul_wordt_correct_teruggegeven(controller, websocket, monkeypatch):
    monkeypatch.setattr("subprocess.Popen", lambda argumenten: NepProces())

    _run(controller.verwerk_commando({
        "type": "open_app", "app": "notepad", "command_id": 0,
    }))

    assert websocket.verstuurde_berichten[0]["command_id"] == 0


def test_ontbrekend_command_id_wordt_als_none_teruggegeven(controller, websocket, monkeypatch):
    monkeypatch.setattr("subprocess.Popen", lambda argumenten: NepProces())

    _run(controller.verwerk_commando({
        "type": "open_app", "app": "notepad",
    }))

    assert websocket.verstuurde_berichten[0]["command_id"] is None


# ------------------------------------------------------------------
# close_app -- NIEUW (19 september 2026)
# ------------------------------------------------------------------

def test_close_app_die_nova_zelf_opende_lukt(controller, websocket, monkeypatch):
    nep_proces = NepProces()
    monkeypatch.setattr("subprocess.Popen", lambda argumenten: nep_proces)

    _run(controller.verwerk_commando({
        "type": "open_app", "app": "chrome", "command_id": 1,
    }))
    _run(controller.verwerk_commando({
        "type": "close_app", "app": "chrome", "command_id": 2,
    }))

    assert nep_proces.terminate_aangeroepen is True
    assert websocket.verstuurde_berichten[-1] == {
        "type": "command_result",
        "command_id": 2,
        "ok": True,
        "app": "chrome",
        "reden": None,
    }
    # Na het sluiten mag de registratie niet blijven hangen -- anders
    # zou een TWEEDE "sluit chrome" ten onrechte opnieuw "gelukt"
    # melden op een allang gesloten proces-object.
    assert "chrome" not in controller._lopende_processen


def test_close_app_die_nova_nooit_opende_wordt_geweigerd(controller, websocket):
    """
    KERNTEST voor de hele ontwerpbeslissing: een app die Nova nooit
    zelf startte (bv. Kevin had Chrome al open staan, buiten Nova om)
    mag NOOIT gesloten worden -- er is hier bewust GEEN aparte
    whitelist-check, dus deze test is de enige verdedigingslinie die
    bevestigt dat _lopende_processen ECHT de poort is.
    """
    _run(controller.verwerk_commando({
        "type": "close_app", "app": "chrome", "command_id": 1,
    }))

    assert websocket.verstuurde_berichten == [{
        "type": "command_result",
        "command_id": 1,
        "ok": False,
        "app": "chrome",
        "reden": "Ik heb 'chrome' niet zelf geopend, dus ik kan het niet sluiten.",
    }]


def test_close_app_die_al_handmatig_gesloten_was(controller, websocket, monkeypatch):
    """
    Kevin sluit Chrome zelf (kruisje) vóórdat hij "sluit chrome" typt.
    poll() geeft dan al een exitcode terug (niet None) -- Nova moet
    dit eerlijk melden i.p.v. te doen alsof ZIJ het net gesloten heeft
    (terminate() zou hier zelfs een fout kunnen geven op een al-dood
    proces, dus dit pad MOET vóór terminate() gecontroleerd worden).
    """
    nep_proces = NepProces()
    monkeypatch.setattr("subprocess.Popen", lambda argumenten: nep_proces)

    _run(controller.verwerk_commando({
        "type": "open_app", "app": "chrome", "command_id": 1,
    }))

    # Simuleer dat Kevin het venster intussen zelf al gesloten heeft.
    nep_proces._gestopt = True

    _run(controller.verwerk_commando({
        "type": "close_app", "app": "chrome", "command_id": 2,
    }))

    assert nep_proces.terminate_aangeroepen is False, (
        "terminate() mag niet aangeroepen worden op een reeds gestopt proces"
    )
    assert websocket.verstuurde_berichten[-1] == {
        "type": "command_result",
        "command_id": 2,
        "ok": False,
        "app": "chrome",
        "reden": "'chrome' was al gestopt.",
    }
    assert "chrome" not in controller._lopende_processen


def test_close_app_terminate_exception_geeft_nette_foutmelding(controller, websocket, monkeypatch):
    class NepProcesDieFaalt(NepProces):
        def terminate(self):
            raise PermissionError("Toegang geweigerd")

    nep_proces = NepProcesDieFaalt()
    monkeypatch.setattr("subprocess.Popen", lambda argumenten: nep_proces)

    _run(controller.verwerk_commando({
        "type": "open_app", "app": "chrome", "command_id": 1,
    }))
    _run(controller.verwerk_commando({
        "type": "close_app", "app": "chrome", "command_id": 2,
    }))

    resultaat = websocket.verstuurde_berichten[-1]
    assert resultaat["ok"] is False
    assert "Toegang geweigerd" in resultaat["reden"]


def test_close_app_hoofdlettergevoeligheid(controller, websocket, monkeypatch):
    nep_proces = NepProces()
    monkeypatch.setattr("subprocess.Popen", lambda argumenten: nep_proces)

    _run(controller.verwerk_commando({
        "type": "open_app", "app": "chrome", "command_id": 1,
    }))
    _run(controller.verwerk_commando({
        "type": "close_app", "app": "  Chrome  ", "command_id": 2,
    }))

    assert nep_proces.terminate_aangeroepen is True


def test_close_app_na_tweede_open_sluit_het_meest_recente_proces(controller, websocket, monkeypatch):
    """
    Vastgelegde, bewuste beperking (zie de docstring in _open_app()):
    een TWEEDE "open chrome" overschrijft de registratie van de
    eerste. Deze test legt dat gedrag expliciet vast, zodat een
    toekomstige wijziging hiervan een bewuste keuze is, geen stille
    regressie.
    """
    eerste_proces = NepProces()
    tweede_proces = NepProces()
    processen = iter([eerste_proces, tweede_proces])
    monkeypatch.setattr("subprocess.Popen", lambda argumenten: next(processen))

    _run(controller.verwerk_commando({
        "type": "open_app", "app": "chrome", "command_id": 1,
    }))
    _run(controller.verwerk_commando({
        "type": "open_app", "app": "chrome", "command_id": 2,
    }))
    _run(controller.verwerk_commando({
        "type": "close_app", "app": "chrome", "command_id": 3,
    }))

    assert eerste_proces.terminate_aangeroepen is False
    assert tweede_proces.terminate_aangeroepen is True


def test_close_app_command_id_wordt_correct_teruggegeven(controller, websocket, monkeypatch):
    monkeypatch.setattr("subprocess.Popen", lambda argumenten: NepProces())

    _run(controller.verwerk_commando({
        "type": "open_app", "app": "notepad", "command_id": 1,
    }))
    _run(controller.verwerk_commando({
        "type": "close_app", "app": "notepad", "command_id": 0,
    }))

    assert websocket.verstuurde_berichten[-1]["command_id"] == 0