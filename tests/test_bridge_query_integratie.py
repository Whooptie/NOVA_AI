# tests/test_bridge_query_integratie.py
"""
"Echte" vervolgtests op test_bridge_query.py (dat enkel geïsoleerde
KOPIEEN van de regex/handler-logica testte, zie de docstring daar).

Dit bestand roept IntentRouter.detect_bridge_query() en
ChatModule.on_bridge_query() rechtstreeks aan op echte instanties,
zelfde patroon als test_intent_router_reactivatie_en_woordmatch.py
(NepEventBus, IntentRouter(bus, semantic_module=...)) en
test_reactivatie_flow.py (NepEventBus met .modules-dict en een
publish()-log).

Bewust GEEN herhaling van elk scenario uit test_bridge_query.py --
die 17 tests dekken de regex-randgevallen en on_bridge_query()'s
volledige fallback-keten al grondig op de kopie. Dit bestand bevestigt
enkel dat de ECHTE klassen hetzelfde gedrag vertonen: 1-2 tests per
scenario, plus het end-to-end-pad (detect -> event -> handler) dat de
kopie-tests per definitie niet konden testen.

Isolatie: geen bestanden, geen netwerk -- IntentRouter en ChatModule
doen beide geen I/O in __init__(), dus rechtstreeks instantieerbaar
met enkel een NepEventBus.

Uitvoeren: pytest tests/test_bridge_query_integratie.py -v
"""

import pytest

from core.intent_router import IntentRouter
from modules.chat.chat import ChatModule


class NepEventBus:
    """
    Zelfde patroon als test_reactivatie_flow.py's NepEventBus,
    uitgebreid met een modules-dict (nodig voor
    event_bus.modules.get("word_associations_learner")) en een
    volledige publish()-log (niet enkel chat_response, ook
    layer4_response en intent_bridge_query zelf -- nodig om het
    end-to-end-pad te kunnen volgen).
    """

    def __init__(self):
        self.modules = {}
        self.gepubliceerd = []
        self._handlers = {}

    def publish(self, event_type, data=None):
        self.gepubliceerd.append((event_type, data))
        # Simpele synchrone dispatch, zodat detect_bridge_query()'s
        # publish("intent_bridge_query", ...) meteen ChatModule's
        # on_bridge_query() triggert -- zelfde als de echte EventBus
        # in Nova (subscribe/publish is er ook synchroon).
        for handler in self._handlers.get(event_type, []):
            handler(data, event_type)

    def subscribe(self, event_type, handler):
        self._handlers.setdefault(event_type, []).append(handler)

    def _laatste(self, event_type):
        """Hulpmethode: laatste gepubliceerde payload voor een event_type."""
        for e, d in reversed(self.gepubliceerd):
            if e == event_type:
                return d
        return None


class NepWordAssociations:
    """Minimale stand-in voor word_associations_learner, zelfde als
    test_bridge_query.py's DummyWordAssociations."""

    def __init__(self, bridge_resultaat=None):
        self._resultaat = bridge_resultaat or []

    def find_bridge(self, word1, word2, top_k=5, min_confidence=0.0):
        return self._resultaat


@pytest.fixture
def bus_met_chat_en_router():
    """
    Bouwt EN de echte IntentRouter EN de echte ChatModule op dezelfde
    NepEventBus, zodat detect_bridge_query()'s publish() ook echt
    ChatModule.on_bridge_query() triggert -- het volledige, echte pad
    zoals het ook in Nova zelf loopt (via intent_router.route() ->
    event_bus.publish("intent_bridge_query", ...) -> chat.py's
    subscribe-handler).
    """
    bus = NepEventBus()
    router = IntentRouter(bus)  # geen semantic_module nodig voor bridge_query zelf
    chat = ChatModule(bus, semantic_module=None)
    return bus, router, chat


# ---------------------------------------------------------------------
# Deel 1: IntentRouter.detect_bridge_query() op de ECHTE klasse
# ---------------------------------------------------------------------

class TestDetectBridgeQueryEcht:
    def test_bridge_en_publiceert_intent_bridge_query(self, bus_met_chat_en_router):
        bus, router, chat = bus_met_chat_en_router

        gevonden = router.detect_bridge_query("bridge python en kunst")

        assert gevonden is True
        payload = bus._laatste("intent_bridge_query")
        assert payload == {"word_a": "python", "word_b": "kunst"}

    def test_bridge_met_publiceert_intent_bridge_query(self, bus_met_chat_en_router):
        bus, router, chat = bus_met_chat_en_router

        gevonden = router.detect_bridge_query("bridge python met kunst")

        assert gevonden is True
        payload = bus._laatste("intent_bridge_query")
        assert payload == {"word_a": "python", "word_b": "kunst"}

    def test_regressie_en_wordt_niet_als_woord_b_gepakt(self, bus_met_chat_en_router):
        """
        Regressietest op de ECHTE klasse voor de live ontdekte bug
        (9 augustus 2026): 'bridge python en kunst' mag NOOIT
        word_b='en' opleveren.
        """
        bus, router, chat = bus_met_chat_en_router

        router.detect_bridge_query("bridge python en kunst")

        payload = bus._laatste("intent_bridge_query")
        assert payload["word_b"] != "en"
        assert payload["word_b"] == "kunst"

    def test_geen_match_geeft_false_en_publiceert_niets(self, bus_met_chat_en_router):
        bus, router, chat = bus_met_chat_en_router

        gevonden = router.detect_bridge_query("wat is python")

        assert gevonden is False
        assert bus._laatste("intent_bridge_query") is None


class TestGemeenTriggerViaDetectDefinition:
    """
    De "wat hebben X en Y gemeen"-tak zit BINNEN detect_definition(),
    niet in een eigen methode -- zie intent_router.py. We roepen dus
    detect_definition() aan, niet detect_bridge_query().
    """

    def test_gemeen_zin_via_detect_definition_publiceert_intent_bridge_query(
        self, bus_met_chat_en_router
    ):
        bus, router, chat = bus_met_chat_en_router

        gevonden = router.detect_definition("wat hebben python en kunst gemeen")

        assert gevonden is True
        payload = bus._laatste("intent_bridge_query")
        assert payload == {"word_a": "python", "word_b": "kunst"}

    def test_gemeen_zin_publiceert_niet_intent_compare_concepts(
        self, bus_met_chat_en_router
    ):
        """
        Onderscheid met de naastliggende compare_concepts-tak: een
        "gemeen"-zin mag NIET ook (of in plaats van) intent_compare_
        concepts publiceren -- dat zou op de verkeerde databron
        (semantic i.p.v. Layer 1) uitkomen.
        """
        bus, router, chat = bus_met_chat_en_router

        router.detect_definition("wat hebben python en kunst gemeen")

        assert bus._laatste("intent_compare_concepts") is None

    def test_verschil_tussen_zin_blijft_naar_compare_concepts_gaan(
        self, bus_met_chat_en_router
    ):
        """
        Regressiecheck: de bestaande "verschil tussen"-zin (compare_
        concepts, Idee #6) mag door de nieuwe "gemeen"-tak niet
        per ongeluk gekaapt worden -- beide triggers staan na elkaar
        in detect_definition(), moeten elkaar niet overlappen.
        """
        bus, router, chat = bus_met_chat_en_router

        gevonden = router.detect_definition(
            "wat is het verschil tussen python en kunst"
        )

        assert gevonden is True
        assert bus._laatste("intent_compare_concepts") == {
            "word_a": "python",
            "word_b": "kunst",
        }
        assert bus._laatste("intent_bridge_query") is None


# ---------------------------------------------------------------------
# Deel 2: end-to-end -- detect_bridge_query() -> ChatModule.on_bridge_query()
# ---------------------------------------------------------------------

class TestEindToEindViaEchteEventBus:
    """
    Het stuk dat test_bridge_query.py NIET kon testen: dat de echte
    IntentRouter en de echte ChatModule daadwerkelijk met elkaar
    praten via de EventBus, niet enkel elk apart correct zijn.
    """

    def test_bridge_zin_leidt_tot_layer4_response_met_brugwoord(
        self, bus_met_chat_en_router
    ):
        bus, router, chat = bus_met_chat_en_router
        bus.modules["word_associations_learner"] = NepWordAssociations(
            bridge_resultaat=[("elegant", 0.7)]
        )

        router.detect_bridge_query("bridge python en kunst")

        payload = bus._laatste("layer4_response")
        assert payload is not None
        assert "elegant" in payload["text"]
        assert "python" in payload["text"]
        assert "kunst" in payload["text"]

    def test_gemeen_zin_leidt_ook_tot_layer4_response(self, bus_met_chat_en_router):
        """Beide triggerzinnen (detect_bridge_query EN de tak in
        detect_definition) moeten uiteindelijk bij dezelfde handler
        uitkomen, met hetzelfde soort antwoord."""
        bus, router, chat = bus_met_chat_en_router
        bus.modules["word_associations_learner"] = NepWordAssociations(
            bridge_resultaat=[("elegant", 0.7)]
        )

        router.detect_definition("wat hebben python en kunst gemeen")

        payload = bus._laatste("layer4_response")
        assert payload is not None
        assert "elegant" in payload["text"]

    def test_geen_module_geladen_geeft_nette_layer4_response(
        self, bus_met_chat_en_router
    ):
        """Geen word_associations_learner in bus.modules (nooit
        geladen/nog niet opgestart) -- ChatModule mag niet crashen,
        moet een nette fallback-tekst publiceren."""
        bus, router, chat = bus_met_chat_en_router
        # bus.modules blijft leeg

        router.detect_bridge_query("bridge python en kunst")

        payload = bus._laatste("layer4_response")
        assert payload is not None
        assert "kan nog geen bruggen" in payload["text"].lower()

    def test_geen_gedeelde_associaties_geeft_nette_layer4_response(
        self, bus_met_chat_en_router
    ):
        bus, router, chat = bus_met_chat_en_router
        bus.modules["word_associations_learner"] = NepWordAssociations(
            bridge_resultaat=[]
        )

        router.detect_bridge_query("bridge python en kunst")

        payload = bus._laatste("layer4_response")
        assert "nog geen gedeelde associaties" in payload["text"].lower()