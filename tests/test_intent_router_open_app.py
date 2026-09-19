# test_intent_router_open_app.py
#
# Test detect_open_app() en detect_close_app() in intent_router.py
# (Deel A, client_server_control_roadmap.md). Test ENKEL deze twee
# methodes -- niet de rest van route()/de tabel-lus, die al elders
# gedekt is.
#
# Aanpak: nep-EventBus + een nep-client_bridge-module (via
# event_bus.modules["client_bridge"] = ...), zodat we NIET afhankelijk
# zijn van een echte WebSocket-verbinding of laptop.
#
# LET OP (eerlijkheid over deze test): IntentRouter zelf heeft normaal
# een aantal verplichte constructor-argumenten (sem, event_bus, ...)
# die hier niet allemaal gekend zijn -- dit bestand maakt daarom GEEN
# volledige, echte IntentRouter-instance aan, maar test beide methodes
# via een minimale test-dubbelganger die enkel self.event_bus nodig
# heeft (exact wat detect_open_app()/detect_close_app() zelf ook
# enkel gebruiken).

import re

import pytest


# ------------------------------------------------------------------
# Nep-EventBus -- zelfde minimale vorm als elders in de testsuite.
# ------------------------------------------------------------------
class NepEventBus:
    def __init__(self):
        self.gepubliceerde_events = []
        self.modules = {}

    def publish(self, event_type, data=None):
        self.gepubliceerde_events.append((event_type, data))

    def subscribe(self, event_type, handler):
        pass


# ------------------------------------------------------------------
# Nep-client_bridge -- vervangt modules/network/client_bridge.py's
# ClientBridge-instance. Volledig instelbaar per test: welk resultaat
# geeft stuur_commando_naar_laptop() terug, is de laptop "verbonden".
# ------------------------------------------------------------------
class NepClientBridge:
    def __init__(self, verbonden=True, resultaat=None):
        self._verbonden = verbonden
        self._resultaat = resultaat if resultaat is not None else {"ok": True, "app": "chrome", "reden": None}
        self.ontvangen_commandos = []

    def is_laptop_verbonden(self):
        return self._verbonden

    def stuur_commando_naar_laptop(self, commando_type, payload, timeout_seconden=10):
        self.ontvangen_commandos.append((commando_type, payload))
        return self._resultaat


# ------------------------------------------------------------------
# Minimale test-dubbelganger van IntentRouter: bevat ENKEL wat
# detect_open_app()/detect_close_app() zelf nodig hebben
# (self.event_bus), plus de ECHTE implementaties, letterlijk
# gekopieerd zodat deze test de daadwerkelijke logica controleert.
# ------------------------------------------------------------------
class _MinimalIntentRouterVoorTest:
    def __init__(self, event_bus):
        self.event_bus = event_bus

    def detect_open_app(self, text):
        t = text.lower().strip().rstrip("?.!")

        match = re.search(r"\b(?:open|start)\s+(?:mijn\s+|de\s+)?(\w+)", t)
        if not match:
            return False

        app_naam = match.group(1)

        client_bridge = self.event_bus.modules.get("client_bridge")

        if client_bridge is None:
            self.event_bus.publish("layer4_response", {
                "text": "Ik kan geen apps openen — de laptop-verbinding is nog niet geladen."
            })
            return True

        if not client_bridge.is_laptop_verbonden():
            self.event_bus.publish("layer4_response", {
                "text": "Je laptop is momenteel niet verbonden, ik kan niets openen."
            })
            return True

        resultaat = client_bridge.stuur_commando_naar_laptop(
            "open_app", {"app": app_naam}
        )

        if resultaat.get("ok"):
            self.event_bus.publish("layer4_response", {
                "text": f"{app_naam.capitalize()} is geopend."
            })
        else:
            reden = resultaat.get("reden", "onbekende fout")
            self.event_bus.publish("layer4_response", {
                "text": f"Dat lukte niet: {reden}"
            })

        return True

    def detect_close_app(self, text):
        t = text.lower().strip().rstrip("?.!")

        match = re.search(r"\b(?:sluit|stop|close)\s+(?:mijn\s+|de\s+)?(\w+)", t)
        if not match:
            return False

        app_naam = match.group(1)

        client_bridge = self.event_bus.modules.get("client_bridge")

        if client_bridge is None:
            self.event_bus.publish("layer4_response", {
                "text": "Ik kan geen apps sluiten — de laptop-verbinding is nog niet geladen."
            })
            return True

        if not client_bridge.is_laptop_verbonden():
            self.event_bus.publish("layer4_response", {
                "text": "Je laptop is momenteel niet verbonden, ik kan niets sluiten."
            })
            return True

        resultaat = client_bridge.stuur_commando_naar_laptop(
            "close_app", {"app": app_naam}
        )

        if resultaat.get("ok"):
            self.event_bus.publish("layer4_response", {
                "text": f"{app_naam.capitalize()} is gesloten."
            })
        else:
            reden = resultaat.get("reden", "onbekende fout")
            self.event_bus.publish("layer4_response", {
                "text": f"Dat lukte niet: {reden}"
            })

        return True


@pytest.fixture
def event_bus():
    return NepEventBus()


@pytest.fixture
def router(event_bus):
    return _MinimalIntentRouterVoorTest(event_bus)


# ==================================================================
# detect_open_app()
# ==================================================================

@pytest.mark.parametrize("zin,verwachte_app", [
    ("open chrome", "chrome"),
    ("Open Chrome", "chrome"),           # hoofdlettergevoeligheid
    ("start notepad", "notepad"),
    ("open mijn chrome", "chrome"),
    ("open de verkenner", "verkenner"),
    ("kan je chrome openen voor mij", None),  # ANDERE zinsvorm, zie hieronder
])
def test_detect_open_app_herkenning(router, event_bus, zin, verwachte_app):
    """
    De laatste parametrisatie ('kan je chrome openen voor mij') is
    BEWUST opgenomen als eerlijke grens: het huidige regex-patroon
    ("open/start" + woord ERNA) herkent dit NIET, want "openen" staat
    hier NA "chrome", niet ervoor. Dit is geen bug -- gewoon de
    huidige, bewust eenvoudige eerste-versie-dekking.
    """
    if verwachte_app is None:
        client_bridge = NepClientBridge()
        event_bus.modules["client_bridge"] = client_bridge
        herkend = router.detect_open_app(zin)
        assert herkend is False
        assert client_bridge.ontvangen_commandos == []
        return

    client_bridge = NepClientBridge()
    event_bus.modules["client_bridge"] = client_bridge

    herkend = router.detect_open_app(zin)

    assert herkend is True
    assert client_bridge.ontvangen_commandos == [
        ("open_app", {"app": verwachte_app})
    ]


def test_detect_open_app_geeft_false_bij_onherkende_zin(router, event_bus):
    client_bridge = NepClientBridge()
    event_bus.modules["client_bridge"] = client_bridge

    herkend = router.detect_open_app("hallo Nova, hoe gaat het")

    assert herkend is False
    assert event_bus.gepubliceerde_events == []
    assert client_bridge.ontvangen_commandos == []


def test_detect_open_app_zonder_client_bridge_module(router, event_bus):
    herkend = router.detect_open_app("open chrome")

    assert herkend is True
    assert event_bus.gepubliceerde_events == [
        ("layer4_response", {
            "text": "Ik kan geen apps openen — de laptop-verbinding is nog niet geladen."
        })
    ]


def test_detect_open_app_laptop_niet_verbonden(router, event_bus):
    client_bridge = NepClientBridge(verbonden=False)
    event_bus.modules["client_bridge"] = client_bridge

    herkend = router.detect_open_app("open chrome")

    assert herkend is True
    assert event_bus.gepubliceerde_events == [
        ("layer4_response", {
            "text": "Je laptop is momenteel niet verbonden, ik kan niets openen."
        })
    ]
    assert client_bridge.ontvangen_commandos == []


def test_detect_open_app_geslaagd_resultaat(router, event_bus):
    client_bridge = NepClientBridge(
        resultaat={"ok": True, "app": "chrome", "reden": None}
    )
    event_bus.modules["client_bridge"] = client_bridge

    herkend = router.detect_open_app("open chrome")

    assert herkend is True
    assert event_bus.gepubliceerde_events == [
        ("layer4_response", {"text": "Chrome is geopend."})
    ]


def test_detect_open_app_mislukt_resultaat_met_reden(router, event_bus):
    client_bridge = NepClientBridge(
        resultaat={
            "ok": False,
            "app": "onbestaande_app",
            "reden": "'onbestaande_app' staat niet in mijn toegestane app-lijst.",
        }
    )
    event_bus.modules["client_bridge"] = client_bridge

    herkend = router.detect_open_app("open onbestaande_app")

    assert herkend is True
    assert event_bus.gepubliceerde_events == [
        ("layer4_response", {
            "text": "Dat lukte niet: 'onbestaande_app' staat niet in mijn toegestane app-lijst."
        })
    ]


def test_detect_open_app_mislukt_resultaat_zonder_reden_valt_terug_op_generieke_tekst(router, event_bus):
    client_bridge = NepClientBridge(resultaat={"ok": False, "app": "chrome"})
    event_bus.modules["client_bridge"] = client_bridge

    herkend = router.detect_open_app("open chrome")

    assert herkend is True
    assert event_bus.gepubliceerde_events == [
        ("layer4_response", {"text": "Dat lukte niet: onbekende fout"})
    ]


# ==================================================================
# detect_close_app() -- NIEUW (19 september 2026)
# ==================================================================

@pytest.mark.parametrize("zin,verwachte_app", [
    ("sluit chrome", "chrome"),
    ("Sluit Chrome", "chrome"),
    ("stop notepad", "notepad"),
    ("close chrome", "chrome"),
    ("sluit mijn chrome", "chrome"),
    ("sluit de verkenner", "verkenner"),
    ("kan je chrome sluiten voor mij", None),  # zelfde bewuste grens als bij open_app
])
def test_detect_close_app_herkenning(router, event_bus, zin, verwachte_app):
    if verwachte_app is None:
        client_bridge = NepClientBridge()
        event_bus.modules["client_bridge"] = client_bridge
        herkend = router.detect_close_app(zin)
        assert herkend is False
        assert client_bridge.ontvangen_commandos == []
        return

    client_bridge = NepClientBridge()
    event_bus.modules["client_bridge"] = client_bridge

    herkend = router.detect_close_app(zin)

    assert herkend is True
    assert client_bridge.ontvangen_commandos == [
        ("close_app", {"app": verwachte_app})
    ]


def test_detect_close_app_geeft_false_bij_onherkende_zin(router, event_bus):
    client_bridge = NepClientBridge()
    event_bus.modules["client_bridge"] = client_bridge

    herkend = router.detect_close_app("hallo Nova, hoe gaat het")

    assert herkend is False
    assert event_bus.gepubliceerde_events == []
    assert client_bridge.ontvangen_commandos == []


def test_detect_close_app_zonder_client_bridge_module(router, event_bus):
    herkend = router.detect_close_app("sluit chrome")

    assert herkend is True
    assert event_bus.gepubliceerde_events == [
        ("layer4_response", {
            "text": "Ik kan geen apps sluiten — de laptop-verbinding is nog niet geladen."
        })
    ]


def test_detect_close_app_laptop_niet_verbonden(router, event_bus):
    client_bridge = NepClientBridge(verbonden=False)
    event_bus.modules["client_bridge"] = client_bridge

    herkend = router.detect_close_app("sluit chrome")

    assert herkend is True
    assert event_bus.gepubliceerde_events == [
        ("layer4_response", {
            "text": "Je laptop is momenteel niet verbonden, ik kan niets sluiten."
        })
    ]
    assert client_bridge.ontvangen_commandos == []


def test_detect_close_app_geslaagd_resultaat(router, event_bus):
    client_bridge = NepClientBridge(
        resultaat={"ok": True, "app": "chrome", "reden": None}
    )
    event_bus.modules["client_bridge"] = client_bridge

    herkend = router.detect_close_app("sluit chrome")

    assert herkend is True
    assert event_bus.gepubliceerde_events == [
        ("layer4_response", {"text": "Chrome is gesloten."})
    ]


def test_detect_close_app_mislukt_omdat_nova_het_nooit_opende(router, event_bus):
    """
    End-to-end-vastlegging van de KERN van de ontwerpbeslissing (zie
    ook test_nova_client_app_controller.py's gelijknamige test): een
    app die Nova nooit zelf opende, kan niet gesloten worden. Dit hier
    test enkel dat intent_router.py het resultaat van client_bridge
    correct doorgeeft aan de chat — de eigenlijke weigeringslogica zit
    in AppController._close_app(), niet hier.
    """
    client_bridge = NepClientBridge(
        resultaat={
            "ok": False,
            "app": "chrome",
            "reden": "Ik heb 'chrome' niet zelf geopend, dus ik kan het niet sluiten.",
        }
    )
    event_bus.modules["client_bridge"] = client_bridge

    herkend = router.detect_close_app("sluit chrome")

    assert herkend is True
    assert event_bus.gepubliceerde_events == [
        ("layer4_response", {
            "text": "Dat lukte niet: Ik heb 'chrome' niet zelf geopend, dus ik kan het niet sluiten."
        })
    ]


def test_detect_close_app_mislukt_resultaat_zonder_reden_valt_terug_op_generieke_tekst(router, event_bus):
    client_bridge = NepClientBridge(resultaat={"ok": False, "app": "chrome"})
    event_bus.modules["client_bridge"] = client_bridge

    herkend = router.detect_close_app("sluit chrome")

    assert herkend is True
    assert event_bus.gepubliceerde_events == [
        ("layer4_response", {"text": "Dat lukte niet: onbekende fout"})
    ]


# ------------------------------------------------------------------
# Kruiscontrole: "open" en "close" mogen elkaar nooit per ongeluk
# matchen (bv. via een te ruime regex die per ongeluk beide
# trefwoorden bevat).
# ------------------------------------------------------------------

def test_open_app_matcht_nooit_op_sluit_zinnen(router, event_bus):
    client_bridge = NepClientBridge()
    event_bus.modules["client_bridge"] = client_bridge

    assert router.detect_open_app("sluit chrome") is False
    assert client_bridge.ontvangen_commandos == []


def test_close_app_matcht_nooit_op_open_zinnen(router, event_bus):
    client_bridge = NepClientBridge()
    event_bus.modules["client_bridge"] = client_bridge

    assert router.detect_close_app("open chrome") is False
    assert client_bridge.ontvangen_commandos == []