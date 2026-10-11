# tests/test_causal_reasoning.py
"""
Pytest-suite voor Semantic Fase 8.1 (11 oktober 2026):

- ReasoningEngine.get_all_effects()  -- alle gevolgen (BFS, kortste pad)
- ReasoningEngine.get_all_causes()   -- alle oorzaken (omgekeerd)
- IntentRouter: "wat veroorzaakt X" (= oorzaken) en
  "wat zijn de gevolgen van X" (= gevolgen), incl. detect_time-botsing
- ChatModule.on_causes()/on_effects() + _formatteer_causale_lijst()

Isolatie: elke test bouwt een eigen ConceptStore op tmp_path, nooit de
echte data/concepts.json. IntentRouter/ChatModule doen geen I/O in
__init__(), een nep-EventBus volstaat.

Uitvoeren: pytest tests/test_causal_reasoning.py -v
"""

import pytest

from core.semantic import (
    ConceptStore,
    SenseEngine,
    RelationEngine,
    ReasoningEngine,
)
from core.intent_router import IntentRouter
from modules.chat.chat import ChatModule


# ---------------------------------------------------------------------
# Gedeelde hulpmiddelen
# ---------------------------------------------------------------------

@pytest.fixture
def engines(tmp_path):
    store = ConceptStore(
        concepts_file=str(tmp_path / "concepts.json"),
        log_file=str(tmp_path / "concepts.jsonl"),
    )
    sense_engine = SenseEngine(store)
    relation_engine = RelationEngine(store, sense_engine)
    reasoning_engine = ReasoningEngine(store, relation_engine)
    return sense_engine, relation_engine, reasoning_engine


def _causes(relation_engine, sense_engine, oorzaak, gevolg):
    """Legt 'oorzaak causes gevolg' vast (maakt de sense aan indien nodig)."""
    if not sense_engine.get_senses(oorzaak):
        sense_engine.add_sense(oorzaak, "testdefinitie", source="user")
    sense_id = sense_engine.get_senses(oorzaak)[0]["sense_id"]
    relation_engine.add_relation(oorzaak, "causes", gevolg, sense_id=sense_id)


class DummyEventBus:
    def __init__(self):
        self.modules = {}
        self.gepubliceerd = []

    def subscribe(self, *args, **kwargs):
        pass

    def publish(self, event_type, data=None):
        self.gepubliceerd.append((event_type, data))

    def events(self, naam):
        return [d for t, d in self.gepubliceerd if t == naam]


# ---------------------------------------------------------------------
# get_all_effects
# ---------------------------------------------------------------------

class TestGetAllEffects:
    def test_direct_gevolg(self, engines):
        sense_engine, relation_engine, reasoning = engines
        _causes(relation_engine, sense_engine, "regen", "modder")

        resultaat = reasoning.get_all_effects("regen")

        assert resultaat == [
            {"woord": "modder", "diepte": 1, "pad": ["regen", "modder"]}
        ]

    def test_keten_met_diepte_en_pad(self, engines):
        sense_engine, relation_engine, reasoning = engines
        _causes(relation_engine, sense_engine, "regen", "modder")
        _causes(relation_engine, sense_engine, "modder", "uitglijden")

        resultaat = reasoning.get_all_effects("regen")

        assert [r["woord"] for r in resultaat] == ["modder", "uitglijden"]
        assert resultaat[1]["diepte"] == 2
        assert resultaat[1]["pad"] == ["regen", "modder", "uitglijden"]

    def test_vertakking_geeft_alle_takken(self, engines):
        sense_engine, relation_engine, reasoning = engines
        _causes(relation_engine, sense_engine, "regen", "modder")
        _causes(relation_engine, sense_engine, "regen", "nat")

        resultaat = reasoning.get_all_effects("regen")

        assert {r["woord"] for r in resultaat} == {"modder", "nat"}

    def test_kortste_pad_bij_twee_routes(self, engines):
        sense_engine, relation_engine, reasoning = engines
        _causes(relation_engine, sense_engine, "a", "b")
        _causes(relation_engine, sense_engine, "b", "c")
        _causes(relation_engine, sense_engine, "a", "c")  # directe route

        resultaat = reasoning.get_all_effects("a")
        c = next(r for r in resultaat if r["woord"] == "c")

        assert c["diepte"] == 1
        assert c["pad"] == ["a", "c"]

    def test_cirkel_geeft_geen_oneindige_lus(self, engines):
        sense_engine, relation_engine, reasoning = engines
        _causes(relation_engine, sense_engine, "a", "b")
        _causes(relation_engine, sense_engine, "b", "a")

        resultaat = reasoning.get_all_effects("a")

        assert [r["woord"] for r in resultaat] == ["b"]  # 'a' zelf niet terug

    def test_respecteert_max_depth_causal(self, engines):
        sense_engine, relation_engine, reasoning = engines
        keten = ["a", "b", "c", "d", "e", "f", "g"]  # 6 stappen
        for bron, doel in zip(keten, keten[1:]):
            _causes(relation_engine, sense_engine, bron, doel)

        resultaat = reasoning.get_all_effects("a")

        assert [r["woord"] for r in resultaat] == ["b", "c", "d", "e"]  # max 4 diep

    def test_rejected_relatie_wordt_genegeerd(self, engines):
        sense_engine, relation_engine, reasoning = engines
        _causes(relation_engine, sense_engine, "regen", "modder")
        sense_id = sense_engine.get_senses("regen")[0]["sense_id"]
        relation_engine.reject_relation("regen", sense_id, "causes", "modder")

        assert reasoning.get_all_effects("regen") == []

    def test_onbekend_woord_geeft_lege_lijst(self, engines):
        _, _, reasoning = engines
        assert reasoning.get_all_effects("bestaat_niet") == []

    def test_hoofdletters_en_spaties_worden_genegeerd(self, engines):
        sense_engine, relation_engine, reasoning = engines
        _causes(relation_engine, sense_engine, "regen", "modder")

        assert len(reasoning.get_all_effects("  REGEN ")) == 1


# ---------------------------------------------------------------------
# get_all_causes
# ---------------------------------------------------------------------

class TestGetAllCauses:
    def test_directe_oorzaak(self, engines):
        sense_engine, relation_engine, reasoning = engines
        _causes(relation_engine, sense_engine, "regen", "modder")

        resultaat = reasoning.get_all_causes("modder")

        assert resultaat == [
            {"woord": "regen", "diepte": 1, "pad": ["regen", "modder"]}
        ]

    def test_keten_pad_loopt_van_oorzaak_naar_target(self, engines):
        sense_engine, relation_engine, reasoning = engines
        _causes(relation_engine, sense_engine, "regen", "modder")
        _causes(relation_engine, sense_engine, "modder", "uitglijden")

        resultaat = reasoning.get_all_causes("uitglijden")

        assert [r["woord"] for r in resultaat] == ["modder", "regen"]
        assert resultaat[1]["diepte"] == 2
        assert resultaat[1]["pad"] == ["regen", "modder", "uitglijden"]

    def test_meerdere_oorzaken(self, engines):
        sense_engine, relation_engine, reasoning = engines
        _causes(relation_engine, sense_engine, "regen", "modder")
        _causes(relation_engine, sense_engine, "overstroming", "modder")

        resultaat = reasoning.get_all_causes("modder")

        assert {r["woord"] for r in resultaat} == {"regen", "overstroming"}

    def test_cirkel_geeft_geen_oneindige_lus(self, engines):
        sense_engine, relation_engine, reasoning = engines
        _causes(relation_engine, sense_engine, "a", "b")
        _causes(relation_engine, sense_engine, "b", "a")

        resultaat = reasoning.get_all_causes("a")

        assert [r["woord"] for r in resultaat] == ["b"]

    def test_respecteert_max_depth_causal(self, engines):
        sense_engine, relation_engine, reasoning = engines
        keten = ["a", "b", "c", "d", "e", "f", "g"]
        for bron, doel in zip(keten, keten[1:]):
            _causes(relation_engine, sense_engine, bron, doel)

        resultaat = reasoning.get_all_causes("g")

        assert [r["woord"] for r in resultaat] == ["f", "e", "d", "c"]

    def test_rejected_relatie_wordt_genegeerd(self, engines):
        sense_engine, relation_engine, reasoning = engines
        _causes(relation_engine, sense_engine, "regen", "modder")
        sense_id = sense_engine.get_senses("regen")[0]["sense_id"]
        relation_engine.reject_relation("regen", sense_id, "causes", "modder")

        assert reasoning.get_all_causes("modder") == []

    def test_onbekend_woord_geeft_lege_lijst(self, engines):
        _, _, reasoning = engines
        assert reasoning.get_all_causes("bestaat_niet") == []

    def test_is_het_spiegelbeeld_van_get_all_effects(self, engines):
        sense_engine, relation_engine, reasoning = engines
        _causes(relation_engine, sense_engine, "regen", "modder")
        _causes(relation_engine, sense_engine, "modder", "uitglijden")

        gevolg_paden = {tuple(r["pad"]) for r in reasoning.get_all_effects("regen")
                        if r["woord"] == "uitglijden"}
        oorzaak_paden = {tuple(r["pad"]) for r in reasoning.get_all_causes("uitglijden")
                         if r["woord"] == "regen"}

        assert gevolg_paden == oorzaak_paden


# ---------------------------------------------------------------------
# IntentRouter: routing van de vraagzinnen
# ---------------------------------------------------------------------

@pytest.fixture
def router():
    bus = DummyEventBus()
    return IntentRouter(bus), bus


class TestIntentRouterCausaal:
    @pytest.mark.parametrize("zin,woord", [
        ("wat veroorzaakt uitglijden", "uitglijden"),
        ("wat veroorzaakt de regen?", "regen"),
        ("wat zorgt voor modder", "modder"),
        ("wat leidt tot uitglijden", "uitglijden"),
    ])
    def test_oorzaken_zinnen(self, router, zin, woord):
        r, bus = router
        assert r.detect_definition(zin) is True
        assert bus.events("intent_causes") == [{"word": woord}]
        assert bus.events("intent_effects") == []

    @pytest.mark.parametrize("zin,woord", [
        ("wat zijn de gevolgen van regen", "regen"),
        ("wat zijn gevolgen van regen?", "regen"),
        ("wat is het gevolg van de regen", "regen"),
        ("waartoe leidt regen", "regen"),
    ])
    def test_gevolgen_zinnen(self, router, zin, woord):
        r, bus = router
        assert r.detect_definition(zin) is True
        assert bus.events("intent_effects") == [{"word": woord}]
        assert bus.events("intent_causes") == []

    def test_emit_eigen_topic_en_zet_vlag(self, router):
        r, bus = router
        r.detect_definition("wat zijn de gevolgen van regen")

        assert "topic_detected:gevolgen_regen" in [t for t, _ in bus.gepubliceerd]
        assert r._topic_al_ge_emit is True

    def test_oorzaken_emit_eigen_topic(self, router):
        r, bus = router
        r.detect_definition("wat veroorzaakt regen")

        assert "topic_detected:oorzaken_regen" in [t for t, _ in bus.gepubliceerd]

    def test_detect_time_vangt_causale_vraag_over_tijd_niet_op(self, router):
        """'waartoe leidt tijd' is een kennisvraag, geen vraag naar de klok."""
        r, bus = router
        assert r.detect_time("waartoe leidt tijd") is False
        assert r.detect_time("wat leidt tot tijd") is False

    def test_gewone_tijdvraag_blijft_werken(self, router):
        r, bus = router
        assert r.detect_time("hoe laat is het") is True

    def test_gewone_definitievraag_blijft_door_naar_definitie(self, router):
        """Regressie: de nieuwe blokken mogen 'wat is X' niet opeten."""
        r, bus = router
        r.detect_definition("wat is een gitaar")

        assert bus.events("intent_causes") == []
        assert bus.events("intent_effects") == []


# ---------------------------------------------------------------------
# ChatModule: handlers
# ---------------------------------------------------------------------

class FakeSemantic:
    def __init__(self, oorzaken=None, gevolgen=None, crash=False):
        self._oorzaken = oorzaken or []
        self._gevolgen = gevolgen or []
        self._crash = crash

    def get_all_causes(self, woord):
        if self._crash:
            raise RuntimeError("kapot")
        return self._oorzaken

    def get_all_effects(self, woord):
        if self._crash:
            raise RuntimeError("kapot")
        return self._gevolgen


def _antwoord(bus):
    return bus.events("layer4_response")[-1]["text"]


class TestChatCausaal:
    def test_on_causes_toont_directe_en_verdere_oorzaken(self):
        bus = DummyEventBus()
        sem = FakeSemantic(oorzaken=[
            {"woord": "modder", "diepte": 1, "pad": ["modder", "uitglijden"]},
            {"woord": "regen", "diepte": 2, "pad": ["regen", "modder", "uitglijden"]},
        ])
        chat = ChatModule(bus, semantic_module=sem)

        chat.on_causes({"word": "uitglijden"})

        assert _antwoord(bus) == "Oorzaken van 'uitglijden': modder (verder weg: regen)."

    def test_on_causes_zonder_resultaat(self):
        bus = DummyEventBus()
        chat = ChatModule(bus, semantic_module=FakeSemantic())

        chat.on_causes({"word": "uitglijden"})

        assert _antwoord(bus) == "Ik ken geen oorzaken van 'uitglijden'."

    def test_on_causes_exception_crasht_niet(self):
        bus = DummyEventBus()
        chat = ChatModule(bus, semantic_module=FakeSemantic(crash=True))

        chat.on_causes({"word": "uitglijden"})

        assert "Ik ken geen oorzaken" in _antwoord(bus)

    def test_on_causes_zonder_woord(self):
        bus = DummyEventBus()
        chat = ChatModule(bus, semantic_module=FakeSemantic())

        chat.on_causes({"word": ""})

        assert _antwoord(bus) == "Welk woord bedoel je?"

    def test_on_effects_toont_gevolgen(self):
        bus = DummyEventBus()
        sem = FakeSemantic(gevolgen=[
            {"woord": "modder", "diepte": 1, "pad": ["regen", "modder"]},
            {"woord": "nat", "diepte": 1, "pad": ["regen", "nat"]},
            {"woord": "uitglijden", "diepte": 2, "pad": ["regen", "modder", "uitglijden"]},
        ])
        chat = ChatModule(bus, semantic_module=sem)

        chat.on_effects({"word": "regen"})

        assert _antwoord(bus) == "Gevolgen van 'regen': modder, nat (verder weg: uitglijden)."

    def test_on_effects_zonder_resultaat(self):
        bus = DummyEventBus()
        chat = ChatModule(bus, semantic_module=FakeSemantic())

        chat.on_effects({"word": "regen"})

        assert _antwoord(bus) == "Ik ken geen gevolgen van 'regen'."

    def test_on_effects_zonder_semantic_module(self):
        bus = DummyEventBus()
        chat = ChatModule(bus, semantic_module=None)

        chat.on_effects({"word": "regen"})

        assert "Ik ken geen gevolgen" in _antwoord(bus)

    def test_formatteer_alleen_directe(self):
        tekst = ChatModule._formatteer_causale_lijst(
            [{"woord": "modder", "diepte": 1, "pad": []}]
        )
        assert tekst == "modder"