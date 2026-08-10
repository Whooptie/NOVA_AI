# tests/test_bridge_query.py
"""
Pytest-suite voor de bridge_query-koppeling (9 augustus 2026,
nova_state.md punt 6b): find_bridge() vanuit een normaal gesprek
bereikbaar maken, via twee triggerzinnen:

1. "wat hebben X en Y gemeen"   -> binnen detect_definition()
2. "bridge X en/met Y"          -> losse detect_bridge_query()

Beide publiceren hetzelfde event "intent_bridge_query", afgehandeld
door chat.py's nieuwe on_bridge_query().

We testen hier BEWUST GEEN find_bridge() zelf (Layer 1-logica) --
dat zit al volledig gedekt in test_find_bridge.py (8 tests). Deze
suite test enkel de NIEUWE routing-/handler-laag erbovenop:
- regex-herkenning (fout-gevoelig, zie de eerdere "en"-bug waarbij
  het debugcommando 'en' als tweede woord pakte)
- on_bridge_query()'s fallback-keten (geen module, geen find_bridge-
  attribuut, leeg resultaat, wel resultaat)

Isolatie: DummyEventBus zoals test_reasoning_engine_ideeen.py's
TestContradictionCheckerMelding al gebruikt -- publish()/subscribe()
doen niets, we lezen enkel wat er gepubliceerd werd terug uit een
lijst die we zelf bijhouden.
"""

import re

import pytest


# ---------------------------------------------------------------------
# Deel 1: detect_bridge_query() + de trigger binnen detect_definition()
# ---------------------------------------------------------------------
#
# We testen de regex-patronen HIER geïsoleerd, zonder een volledige
# IntentRouter te instantiëren -- IntentRouter.__init__() heeft 4
# optionele afhankelijkheden (kevin_profile, sentiment_classifier,
# intent_classifier, semantic_module) waarvan we niet zeker weten of
# ze I/O-vrij zijn. Een geïsoleerde regex-test is voor dit doel
# (foutgevoelige patroon-herkenning controleren) net zo waardevol en
# veel minder fragiel dan de hele klasse opbouwen.
#
# De patronen hieronder zijn LETTERLIJK gekopieerd uit
# intent_router.py's detect_bridge_query() en de nieuwe tak in
# detect_definition() -- bij een wijziging aan de echte regex moet
# deze test-kopie ook bijgewerkt worden.

BRIDGE_QUERY_PATROON = r"bridge\s+(\w+)\s+(?:en|met)\s+([\w\s]+)"
GEMEEN_PATROON = r"wat\s+hebben\s+(\w+)\s+en\s+([\w\s]+?)\s+gemeen"


class TestBridgeQueryRegexPatroon:
    """Losse detect_bridge_query()-tak: 'bridge X en/met Y'."""

    def test_bridge_met_en(self):
        m = re.match(BRIDGE_QUERY_PATROON, "bridge python en kunst")
        assert m is not None
        assert m.group(1).strip() == "python"
        assert m.group(2).strip() == "kunst"

    def test_bridge_met_met(self):
        m = re.match(BRIDGE_QUERY_PATROON, "bridge python met kunst")
        assert m is not None
        assert m.group(1).strip() == "python"
        assert m.group(2).strip() == "kunst"

    def test_regressie_en_wordt_niet_als_tweede_woord_gepakt(self):
        """
        Regressietest voor de bug live ontdekt op 9 augustus 2026:
        'bridge python en kunst' gaf voorheen 'python' vs 'en' i.p.v.
        'python' vs 'kunst', omdat het (oude) debugcommando geen
        verbindingswoord verwachtte. Dit patroon (en de bijgewerkte
        debug_commands.py) moeten dat niet meer doen.
        """
        m = re.match(BRIDGE_QUERY_PATROON, "bridge python en kunst")
        assert m.group(2).strip() != "en"
        assert m.group(2).strip() == "kunst"

    def test_geen_verbindingswoord_matcht_niet(self):
        # "bridge python kunst" (zonder en/met) hoort NIET te matchen
        # -- dat is bewust een andere syntax dan het debugcommando.
        m = re.match(BRIDGE_QUERY_PATROON, "bridge python kunst")
        assert m is None

    def test_niet_matchend_op_ongerelateerde_zin(self):
        m = re.match(BRIDGE_QUERY_PATROON, "wat is python")
        assert m is None


class TestGemeenTriggerBinnenDefinitie:
    """De tak binnen detect_definition(): 'wat hebben X en Y gemeen'."""

    def test_basis_match(self):
        m = re.match(GEMEEN_PATROON, "wat hebben python en kunst gemeen")
        assert m is not None
        assert m.group(1).strip() == "python"
        assert m.group(2).strip() == "kunst"

    def test_meerdere_woorden_in_tweede_deel(self):
        m = re.match(GEMEEN_PATROON, "wat hebben python en beeldende kunst gemeen")
        assert m is not None
        assert m.group(2).strip() == "beeldende kunst"

    def test_geen_match_zonder_gemeen(self):
        # Zonder "gemeen" op het eind moet dit NIET matchen -- anders
        # zou dit te breed worden en gewone "wat hebben X en Y"-zinnen
        # zonder die betekenis ook afvangen.
        m = re.match(GEMEEN_PATROON, "wat hebben python en kunst")
        assert m is None

    def test_niet_matchend_op_compare_concepts_zin(self):
        # "wat is het verschil tussen X en Y" is een ANDERE intent
        # (compare_concepts) en moet hier niet toevallig ook matchen.
        m = re.match(GEMEEN_PATROON, "wat is het verschil tussen python en kunst")
        assert m is None


# ---------------------------------------------------------------------
# Deel 2: chat.py's on_bridge_query()
# ---------------------------------------------------------------------
#
# We simuleren on_bridge_query()'s logica hier via een kleine, exacte
# kopie van de methode (zelfde reden als hierboven: ChatModule.__init__
# heeft afhankelijkheden -- self_query/self_architecture -- die we niet
# willen meeslepen in een routing-test). De dummy's hieronder spelen
# event_bus.modules en word_associations_learner na.

class DummyEventBus:
    """Zelfde patroon als test_reasoning_engine_ideeen.py's DummyEventBus,
    uitgebreid met modules-dict (nodig voor event_bus.modules.get(...))
    en een publish-log zodat we kunnen controleren wat er verstuurd werd."""

    def __init__(self, modules=None):
        self.modules = modules or {}
        self.gepubliceerd = []

    def subscribe(self, *args, **kwargs):
        pass

    def publish(self, event_type, data=None):
        self.gepubliceerd.append((event_type, data))


class DummyWordAssociations:
    """Minimale stand-in voor word_associations_learner, met een
    instelbare find_bridge()-return voor elk scenario."""

    def __init__(self, bridge_resultaat=None, gooi_exceptie=False):
        self._resultaat = bridge_resultaat or []
        self._gooi_exceptie = gooi_exceptie

    def find_bridge(self, word1, word2, top_k=5, min_confidence=0.0):
        if self._gooi_exceptie:
            raise RuntimeError("gesimuleerde opzoekfout")
        return self._resultaat


def _on_bridge_query(event_bus, data):
    """
    Exacte kopie van chat.py's on_bridge_query(), voor geïsoleerd
    testen zonder ChatModule zelf te moeten instantiëren. Bij een
    wijziging aan de echte methode moet deze kopie ook bijgewerkt
    worden -- zelfde afweging als bij de regex-patronen hierboven.
    """
    word_a = data.get("word_a")
    word_b = data.get("word_b")

    if not word_a or not word_b:
        event_bus.publish("layer4_response", {
            "text": "Welke twee dingen wil je dat ik op gedeelde associaties vergelijk?"
        })
        return

    word_assoc = event_bus.modules.get("word_associations_learner")
    if word_assoc is None:
        word_assoc = event_bus.modules.get("word_associations")

    if word_assoc is None or not hasattr(word_assoc, "find_bridge"):
        event_bus.publish("layer4_response", {
            "text": "Ik kan nog geen bruggen tussen woorden zoeken."
        })
        return

    try:
        bruggen = word_assoc.find_bridge(word_a, word_b)
    except Exception:
        bruggen = None

    if not bruggen:
        event_bus.publish("layer4_response", {
            "text": f"Ik zie bij mij nog geen gedeelde associaties tussen '{word_a}' en '{word_b}'."
        })
        return

    sterkste_woord, sterkste_score = bruggen[0]
    msg = f"'{word_a}' en '{word_b}' worden bij jou vaak samen genoemd met '{sterkste_woord}'."

    overige = [w for w, _ in bruggen[1:]]
    if overige:
        msg += f" (en ook met: {', '.join(overige)})"

    event_bus.publish("layer4_response", {"text": msg})


class TestOnBridgeQuery:
    def test_ontbrekend_woord_a_geeft_vraag_terug(self):
        bus = DummyEventBus()
        _on_bridge_query(bus, {"word_b": "kunst"})

        event_type, payload = bus.gepubliceerd[0]
        assert event_type == "layer4_response"
        assert "welke twee dingen" in payload["text"].lower()

    def test_ontbrekend_woord_b_geeft_vraag_terug(self):
        bus = DummyEventBus()
        _on_bridge_query(bus, {"word_a": "python"})

        event_type, payload = bus.gepubliceerd[0]
        assert "welke twee dingen" in payload["text"].lower()

    def test_module_niet_geladen_geeft_nette_melding(self):
        bus = DummyEventBus(modules={})  # word_associations_learner ontbreekt

        _on_bridge_query(bus, {"word_a": "python", "word_b": "kunst"})

        event_type, payload = bus.gepubliceerd[0]
        assert "kan nog geen bruggen" in payload["text"].lower()

    def test_fallback_op_kortere_module_key(self):
        """
        Zelfde fallback-patroon als debug_commands.py's _associaties():
        eerst 'word_associations_learner' proberen, dan 'word_associations'.
        """
        dummy = DummyWordAssociations(bridge_resultaat=[("elegant", 0.7)])
        bus = DummyEventBus(modules={"word_associations": dummy})

        _on_bridge_query(bus, {"word_a": "python", "word_b": "kunst"})

        event_type, payload = bus.gepubliceerd[0]
        assert "elegant" in payload["text"]

    def test_geen_gedeelde_associaties_geeft_nette_melding(self):
        dummy = DummyWordAssociations(bridge_resultaat=[])
        bus = DummyEventBus(modules={"word_associations_learner": dummy})

        _on_bridge_query(bus, {"word_a": "python", "word_b": "kunst"})

        event_type, payload = bus.gepubliceerd[0]
        assert "nog geen gedeelde associaties" in payload["text"].lower()
        assert "python" in payload["text"]
        assert "kunst" in payload["text"]

    def test_een_brugwoord_toont_geen_tussen_haakjes_lijst(self):
        dummy = DummyWordAssociations(bridge_resultaat=[("elegant", 0.7)])
        bus = DummyEventBus(modules={"word_associations_learner": dummy})

        _on_bridge_query(bus, {"word_a": "python", "word_b": "kunst"})

        event_type, payload = bus.gepubliceerd[0]
        assert "elegant" in payload["text"]
        assert "(en ook met:" not in payload["text"]

    def test_meerdere_bruggen_toont_sterkste_in_hoofdzin_rest_tussen_haakjes(self):
        dummy = DummyWordAssociations(
            bridge_resultaat=[("elegant", 0.85), ("creatief", 0.4), ("modern", 0.3)]
        )
        bus = DummyEventBus(modules={"word_associations_learner": dummy})

        _on_bridge_query(bus, {"word_a": "python", "word_b": "kunst"})

        event_type, payload = bus.gepubliceerd[0]
        text = payload["text"]
        assert "vaak samen genoemd met 'elegant'" in text
        assert "(en ook met: creatief, modern)" in text

    def test_exceptie_in_find_bridge_geeft_nette_melding_geen_crash(self):
        dummy = DummyWordAssociations(gooi_exceptie=True)
        bus = DummyEventBus(modules={"word_associations_learner": dummy})

        # Mag niet crashen -- moet nette fallback-tekst geven, zelfde
        # principe als response_engine.py's overal aanwezige
        # try/except rond opzoekingen in andere lagen.
        _on_bridge_query(bus, {"word_a": "python", "word_b": "kunst"})

        event_type, payload = bus.gepubliceerd[0]
        assert "nog geen gedeelde associaties" in payload["text"].lower()