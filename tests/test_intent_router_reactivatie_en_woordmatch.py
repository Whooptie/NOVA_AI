# test_intent_router_reactivatie_en_woordmatch.py
#
# Pytest-tests voor twee losse punten in intent_router.py, beide
# ontdekt/opgelost tijdens de Bug #32/#36-sessie (8 augustus 2026):
#
#   Deel 1 -- de nieuwe "-1F Pending sense-reactivatie"-stap in route():
#   moet semantic.pending_reactivation VOOR de generieke ja/nee-confirm-
#   check afvangen, zodat een reactivatie-vraag nooit genegeerd wordt
#   als er toevallig ook een gewone relatie-bevestiging (pending_relation)
#   openstaat.
#
#   Deel 2 -- Bug #37: de "andere betekenissen van X"-kernzin-matching
#   zocht op " van "/" voor " MET voorloop-spatie tegen een al gestripte
#   string, en matchte daardoor nooit. Live ontdekt door Kevin.
#
# Isolatie: IntentRouter is te bouwen met enkel een nep-EventBus en
# (voor deel 1) een nep-semantic-object -- geen echte modules, geen
# netwerk, geen bestanden nodig. We gebruiken hier GEEN echte
# SemanticConceptsModule (dat hoort thuis in
# test_reactivatie_flow.py) -- hier testen we alleen de ROUTING zelf:
# wordt handle_reactivation_confirm() aangeroepen op het juiste moment,
# vóór de rest van de routing draait.
#
# Uitvoeren: pytest tests/test_intent_router_reactivatie_en_woordmatch.py -v

import pytest

from core.intent_router import IntentRouter


class NepEventBus:
    def __init__(self):
        self.gepubliceerde_berichten = []
        self.modules = {}

    def publish(self, event_type, data):
        if event_type == "chat_response":
            self.gepubliceerde_berichten.append(data.get("text", ""))

    def subscribe(self, event_type, handler):
        pass


class NepSemanticVoorRoutingTest:
    """
    Minimale nep-semantic: enkel wat de -1F-routingstap en de generieke
    ja/nee-confirm-check nodig hebben. Houdt bij WELKE methode
    aangeroepen werd (handle_reactivation_confirm vs. handle_confirm),
    zodat de test kan verifiëren dat de JUISTE flow wint bij een
    botsing tussen de twee pending-mechanismen.
    """
    def __init__(self):
        self.pending_reactivation = None
        self.pending_relation_actief = False  # simuleert flow_engine.pending_relation
        self.aangeroepen_methodes = []

    def handle_reactivation_confirm(self, user_input):
        self.aangeroepen_methodes.append(("handle_reactivation_confirm", user_input))
        self.pending_reactivation = None

    def handle_confirm(self, user_input):
        self.aangeroepen_methodes.append(("handle_confirm", user_input))
        self.pending_relation_actief = False

    def handle_sense_choice(self, user_input):
        self.aangeroepen_methodes.append(("handle_sense_choice", user_input))

    def _detect_relation(self, text):
        return False  # niet relevant voor deze tests, altijd False


@pytest.fixture
def router_met_nep_semantic():
    bus = NepEventBus()
    nep_semantic = NepSemanticVoorRoutingTest()
    router = IntentRouter(bus, semantic_module=nep_semantic)
    return router, bus, nep_semantic


# ─────────────────────────────────────────────────────────────
# Deel 1: -1F pending_reactivation-routing
# ─────────────────────────────────────────────────────────────

def test_pending_reactivation_wordt_afgevangen_door_ja(router_met_nep_semantic):
    """Basisgeval: als pending_reactivation gezet is, moet 'ja' naar
    handle_reactivation_confirm() gaan."""
    router, bus, nep_semantic = router_met_nep_semantic
    nep_semantic.pending_reactivation = {"word": "hond", "sense_id": "hond#1"}

    router.route({"text": "ja"})

    assert ("handle_reactivation_confirm", "ja") in nep_semantic.aangeroepen_methodes, (
        f"handle_reactivation_confirm() werd niet aangeroepen. "
        f"Aangeroepen methodes: {nep_semantic.aangeroepen_methodes}"
    )


def test_pending_reactivation_wordt_afgevangen_door_nee(router_met_nep_semantic):
    router, bus, nep_semantic = router_met_nep_semantic
    nep_semantic.pending_reactivation = {"word": "kat", "sense_id": "kat#1"}

    router.route({"text": "nee"})

    assert ("handle_reactivation_confirm", "nee") in nep_semantic.aangeroepen_methodes


def test_pending_reactivation_krijgt_voorrang_op_pending_relation_confirm(router_met_nep_semantic):
    """
    KERN VAN DE -1F-FIX: als BEIDE pending_reactivation EN een gewone
    pending_relation-confirm tegelijk "openstaan" (een botsing-scenario
    dat zonder de -1F-stap zou kunnen misgaan), moet de reactivatie-
    vraag VOORRANG krijgen -- handle_confirm() (voor pending_relation)
    mag dan NIET aangeroepen worden voor datzelfde bericht.
    """
    router, bus, nep_semantic = router_met_nep_semantic
    nep_semantic.pending_reactivation = {"word": "vis", "sense_id": "vis#1"}
    nep_semantic.pending_relation_actief = True  # simuleert een gelijktijdig openstaande relatie-vraag

    router.route({"text": "ja"})

    assert ("handle_reactivation_confirm", "ja") in nep_semantic.aangeroepen_methodes
    assert ("handle_confirm", "ja") not in nep_semantic.aangeroepen_methodes, (
        "handle_confirm() (voor pending_relation) werd AANGEROEPEN terwijl "
        "pending_reactivation ook actief was -- de -1F-voorrang werkt niet, "
        "de reactivatie-vraag zou genegeerd kunnen worden."
    )


def test_geen_pending_reactivation_laat_normale_confirm_gewoon_werken(router_met_nep_semantic):
    """Regressiecheck: als pending_reactivation NIET gezet is, moet de
    normale ja/nee-confirm-flow (handle_confirm, voor pending_relation)
    gewoon nog steeds werken -- de -1F-stap mag dat pad niet blokkeren."""
    router, bus, nep_semantic = router_met_nep_semantic
    nep_semantic.pending_reactivation = None

    router.route({"text": "ja"})

    assert ("handle_confirm", "ja") in nep_semantic.aangeroepen_methodes
    assert not any(m[0] == "handle_reactivation_confirm" for m in nep_semantic.aangeroepen_methodes)


def test_pending_reactivation_negeert_berichten_die_geen_ja_nee_zijn():
    """
    Randgeval: de -1F-check zelf test enkel OF pending_reactivation
    gezet is (niet OF de tekst 'ja'/'nee' is) -- elk bericht tijdens
    een openstaande reactivatie-vraag gaat dus naar
    handle_reactivation_confirm(), ook een onduidelijk antwoord (die
    methode zelf beslist dan wat ermee te doen, zie
    test_reactivatie_flow.py). Dit bevestigt enkel de ROUTING, niet de
    inhoudelijke afhandeling van een onduidelijk antwoord.
    """
    bus = NepEventBus()
    nep_semantic = NepSemanticVoorRoutingTest()
    nep_semantic.pending_reactivation = {"word": "boom", "sense_id": "boom#1"}
    router = IntentRouter(bus, semantic_module=nep_semantic)

    router.route({"text": "misschien"})

    assert ("handle_reactivation_confirm", "misschien") in nep_semantic.aangeroepen_methodes


# ─────────────────────────────────────────────────────────────
# Deel 2: Bug #37 -- "andere betekenissen van X"-woordherkenning
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def router_kaal():
    """Voor Bug #37 is geen semantic-module nodig -- de detectie zelf
    publiceert enkel een event, geen semantic-aanroep."""
    bus = NepEventBus()
    router = IntentRouter(bus)
    return router, bus


def test_andere_betekenissen_van_woord_herkent_het_genoemde_woord():
    """
    HET EXACTE LIVE-SCENARIO (Kevin, 8 augustus 2026): 'zijn er nog
    andere betekenissen van fysica' moet 'fysica' als woord herkennen,
    NIET terugvallen op een eerder, ongerelateerd _laatste_definitie_woord.
    """
    class BusMetEventLog(NepEventBus):
        def __init__(self):
            super().__init__()
            self.events = []

        def publish(self, event_type, data):
            self.events.append((event_type, data))
            super().publish(event_type, data)

    bus = BusMetEventLog()
    router = IntentRouter(bus)
    router._laatste_definitie_woord = "betekent gitaar"  # simuleert een oud, verouderd woord

    gevonden = router.detect_definition("zijn er nog andere betekenissen van fysica")

    assert gevonden is True
    wiki_events = [d for e, d in bus.events if e == "intent_wiki_andere_betekenis"]
    assert len(wiki_events) == 1, f"Verwachtte precies 1 intent_wiki_andere_betekenis-event, kreeg: {bus.events}"
    assert wiki_events[0]["word"] == "fysica", (
        f"REGRESSIE/BUG NIET GEFIXT: verwachtte woord 'fysica', kreeg "
        f"'{wiki_events[0]['word']}' -- viel terug op het verouderde "
        f"_laatste_definitie_woord i.p.v. het genoemde woord te herkennen."
    )


def test_andere_betekenissen_voor_woord_herkent_het_genoemde_woord():
    """Zelfde soort scenario maar met het 'voor '-koppelwoord i.p.v. 'van '."""
    class BusMetEventLog(NepEventBus):
        def __init__(self):
            super().__init__()
            self.events = []

        def publish(self, event_type, data):
            self.events.append((event_type, data))
            super().publish(event_type, data)

    bus = BusMetEventLog()
    router = IntentRouter(bus)
    router._laatste_definitie_woord = "oudwoord"

    gevonden = router.detect_definition("zijn er nog andere betekenissen voor bank")

    assert gevonden is True
    wiki_events = [d for e, d in bus.events if e == "intent_wiki_andere_betekenis"]
    assert len(wiki_events) == 1
    assert wiki_events[0]["word"] == "bank", (
        f"Verwachtte woord 'bank', kreeg: {wiki_events[0]['word']}"
    )


def test_andere_betekenissen_zonder_genoemd_woord_valt_terug_op_laatste(router_kaal):
    """Regressiecheck: ZONDER expliciet genoemd woord ('van X') moet de
    fallback naar _laatste_definitie_woord nog gewoon werken."""
    class BusMetEventLog(NepEventBus):
        def __init__(self):
            super().__init__()
            self.events = []

        def publish(self, event_type, data):
            self.events.append((event_type, data))
            super().publish(event_type, data)

    bus = BusMetEventLog()
    router = IntentRouter(bus)
    router._laatste_definitie_woord = "python"

    gevonden = router.detect_definition("zijn er nog andere betekenissen")

    assert gevonden is True
    wiki_events = [d for e, d in bus.events if e == "intent_wiki_andere_betekenis"]
    assert len(wiki_events) == 1
    assert wiki_events[0]["word"] == "python"


def test_andere_betekenissen_zonder_woord_en_zonder_fallback_vraagt_door(router_kaal):
    """Randgeval: geen genoemd woord EN geen _laatste_definitie_woord
    -> Nova moet vragen waar het over gaat, niet crashen of gokken."""
    router, bus = router_kaal
    # _laatste_definitie_woord bestaat hier niet (nieuwe router, nooit gezet)

    gevonden = router.detect_definition("zijn er nog andere betekenissen")

    assert gevonden is True
    assert any("Waarvan wil je andere betekenissen" in b for b in bus.gepubliceerde_berichten)