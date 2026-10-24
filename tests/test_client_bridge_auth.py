"""Tests voor de token-controle in modules/network/client_bridge.py (punt 32)."""
import asyncio
import json
import threading

import pytest

from modules.network import client_bridge as cb


class NepWebsocket:
    """Doet alsof het een websocket is: geeft vooraf ingestelde berichten terug."""

    remote_address = ("1.2.3.4", 5555)

    def __init__(self, berichten=(), blijf_hangen=False):
        self._berichten = list(berichten)
        self._hang = blijf_hangen
        self.gesloten_met = None

    async def recv(self):
        if self._hang:
            await asyncio.sleep(60)
        if not self._berichten:
            raise ConnectionError("verbinding weg")
        return self._berichten.pop(0)

    async def close(self, code=1000, reason=""):
        self.gesloten_met = (code, reason)

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


def maak_bridge():
    # __new__: geen echte server starten, enkel de velden die we nodig hebben.
    b = cb.ClientBridge.__new__(cb.ClientBridge)
    b._lock = threading.Lock()
    b._actieve_websocket = None
    b._verbonden_clients = 0
    return b


@pytest.fixture(autouse=True)
def vast_token(monkeypatch):
    monkeypatch.setattr(cb, "_haal_verwacht_token", lambda: "geheim123")
    monkeypatch.setattr(cb, "AUTH_TIMEOUT_SECONDEN", 0.2)


def controleer(ws):
    return asyncio.run(maak_bridge()._controleer_token(ws))


def auth(token):
    return json.dumps({"type": "auth", "token": token})


def test_juist_token_wordt_geaccepteerd():
    ws = NepWebsocket([auth("geheim123")])
    assert controleer(ws) is True
    assert ws.gesloten_met is None


def test_fout_token_wordt_geweigerd():
    ws = NepWebsocket([auth("fout")])
    assert controleer(ws) is False
    assert ws.gesloten_met[0] == 1008


def test_geen_token_ingesteld_weigert_alles(monkeypatch):
    monkeypatch.setattr(cb, "_haal_verwacht_token", lambda: None)
    ws = NepWebsocket([auth("geheim123")])
    assert controleer(ws) is False
    assert ws.gesloten_met[0] == 1008


def test_timeout_wordt_geweigerd():
    ws = NepWebsocket(blijf_hangen=True)
    assert controleer(ws) is False
    assert ws.gesloten_met[0] == 1008


def test_kapotte_json_wordt_geweigerd():
    ws = NepWebsocket(["dit is geen json"])
    assert controleer(ws) is False


def test_verkeerd_type_wordt_geweigerd():
    ws = NepWebsocket([json.dumps({"type": "sensor", "token": "geheim123"})])
    assert controleer(ws) is False


@pytest.mark.parametrize("waarde", [None, 123, ["geheim123"], {"a": 1}])
def test_token_geen_tekst_wordt_geweigerd(waarde):
    ws = NepWebsocket([json.dumps({"type": "auth", "token": waarde})])
    assert controleer(ws) is False


def test_json_geen_dict_wordt_geweigerd():
    ws = NepWebsocket([json.dumps(["auth", "geheim123"])])
    assert controleer(ws) is False


def test_geweigerde_verbinding_wordt_niet_geregistreerd():
    b = maak_bridge()
    ws = NepWebsocket([auth("fout")])
    asyncio.run(b._verwerk_client(ws))
    assert b._actieve_websocket is None
    assert b._verbonden_clients == 0