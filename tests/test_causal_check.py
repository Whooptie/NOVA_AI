# tests/test_causal_check.py
"""
Pytest-suite voor Semantic Fase 8.2 (11 oktober 2026):

- ReasoningEngine.explain_causes()   -- kortste pad, zelfde diepte als
                                         get_all_effects(), "waarom niet"
- IntentRouter.detect_causes_check() -- 4 zinsvormen + guards + vroege
                                         routing in route()
- RelationParser " leidt tot " en RelationFlowEngine's Nederlandse
  bevestigingszinnen
- ChatModule.on_causes_check()

Isolatie: ConceptStore op tmp_path, nep-EventBus, nooit de echte
data/concepts.json.

Uitvoeren: pytest tests/test_causal_check.py -v
"""

import pytest

from core.semantic import (
    ConceptStore,
    SenseEngine,
    RelationEngine,
    ReasoningEngine,
    RelationParser,
    RelationFlowEngine,
)
from core.intent_router import IntentRouter
from modules.chat.chat import ChatModule


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

    def namen(self):
        return [t for t, _ in self.gepubliceerd]


@pytest.fixture
def engines(tmp_path):
    store = ConceptStore(
        concepts_file=str(tmp_path / "concepts.json"),
        log_file=str(tmp_path / "concepts.jsonl"),
    )
    sense_engine = SenseEngine(store)
    relation_engine = RelationEngine(store, sense_engine)
    reasoning_engine = ReasoningEngine(store, relation_engine)
    return store, sense_engine, relation_engine, reasoning_engine


def _causes(relation_engine, sense_engine, oorzaak, gevolg):
    if not sense_engine.get_senses(oorzaak):
        sense_engine.add_sense(oorzaak, "testdefinitie", source="user")
    sense_id = sense_engine.get_senses(oorzaak)[0]["sense_id"]
    relation_engine.add_relation(oorzaak, "causes", gevolg, sense_id=sense_id)


# ---------------------------------------------------------------------
# explain_causes
# ---------------------------------------------------------------------

class TestExplainCauses:
    def test_directe_oorzaak(self, engines):
        _, se, re_, rs = engines
        _causes(re_, se, "regen", "modder")

        assert rs.explain_causes("regen", "modder") == "Ja, regen veroorzaakt modder."

    def test_keten_toont_pad(self, engines):
        _, se, re_, rs = engines
        _causes(re_, se, "regen", "modder")
        _causes(re_, se, "modder", "uitglijden")

        tekst = rs.explain_causes("regen", "uitglijden")

        assert tekst.startswith("Waarschijnlijk wel")
        assert "regen → modder → uitglijden" in tekst
        assert "Ja," not in tekst

    def test_kiest_kortste_pad(self, engines):
        _, se, re_, rs = engines
        _causes(re_, se, "a", "b")
        _causes(re_, se, "b", "c")
        _causes(re_, se, "a", "c")

        assert rs.explain_causes("a", "c") == "Ja, a veroorzaakt c."

    def test_negatief_met_alternatief(self, engines):
        _, se, re_, rs = engines
        _causes(re_, se, "regen", "modder")

        tekst = rs.explain_causes("regen", "zonneschijn")

        assert "kan niet bewijzen" in tekst
        assert "regen modder veroorzaakt" in tekst

    def test_negatief_zonder_alternatief_blijft_kaal(self, engines):
        _, se, re_, rs = engines
        se.add_sense("ei", "testdefinitie", source="user")

        tekst = rs.explain_causes("ei", "server")

        assert tekst == "Ik kan niet bewijzen dat 'ei' leidt tot 'server'."
        assert "maar ik weet wel" not in tekst

    def test_onbekend_woord_geen_crash(self, engines):
        _, _, _, rs = engines
        assert "kan niet bewijzen" in rs.explain_causes("nooitgezien", "ook_niet")

    def test_rejected_relatie_telt_niet_mee(self, engines):
        _, se, re_, rs = engines
        _causes(re_, se, "regen", "modder")
        sense_id = se.get_senses("regen")[0]["sense_id"]
        re_.reject_relation("regen", sense_id, "causes", "modder")

        assert "kan niet bewijzen" in rs.explain_causes("regen", "modder")

    def test_diepte_grens_vier_stappen_lukt_zes_niet(self, engines):
        _, se, re_, rs = engines
        keten = ["a", "b", "c", "d", "e", "f", "g"]
        for bron, doel in zip(keten, keten[1:]):
            _causes(re_, se, bron, doel)

        assert "kan niet bewijzen" not in rs.explain_causes("a", "e")  # 4 stappen
        assert "kan niet bewijzen" in rs.explain_causes("a", "g")  # 6 stappen

    def test_check_en_gevolgenlijst_zijn_consistent(self, engines):
        _, se, re_, rs = engines
        keten = ["a", "b", "c", "d", "e", "f"]
        for bron, doel in zip(keten, keten[1:]):
            _causes(re_, se, bron, doel)

        in_lijst = {g["woord"] for g in rs.get_all_effects("a")}
        for woord in keten[1:]:
            bewezen = not rs.explain_causes("a", woord).startswith("Ik kan niet bewijzen")
            assert bewezen == (woord in in_lijst)

    def test_hoofdletters_en_spaties(self, engines):
        _, se, re_, rs = engines
        _causes(re_, se, "regen", "modder")

        assert rs.explain_causes("  REGEN ", " Modder").startswith("Ja,")


# ---------------------------------------------------------------------
# IntentRouter.detect_causes_check
# ---------------------------------------------------------------------

@pytest.fixture
def router():
    bus = DummyEventBus()
    return IntentRouter(bus), bus


class TestDetectCausesCheck:
    @pytest.mark.parametrize("zin,source,target", [
        ("leidt regen tot modder", "regen", "modder"),
        ("leidt de regen tot de modder?", "regen", "modder"),
        ("leidt regen tot zware modder", "regen", "zware modder"),
        ("veroorzaakt regen modder", "regen", "modder"),
        ("veroorzaakt de regen een modderpoel", "regen", "modderpoel"),
        ("zorgt regen voor modder", "regen", "modder"),
        ("zorgt de regen voor het uitglijden?", "regen", "uitglijden"),
        ("kan regen modder veroorzaken", "regen", "modder"),
        ("Kan regen uitglijden veroorzaken?", "regen", "uitglijden"),
    ])
    def test_herkent_alle_vormen(self, router, zin, source, target):
        r, bus = router
        assert r.detect_causes_check(zin) is True
        assert bus.events("intent_causes_check") == [{"source": source, "target": target}]

    @pytest.mark.parametrize("zin", [
        "zorgt hij voor het eten",
        "zorgt het voor problemen",
        "leidt dat tot problemen",
        "leidt dit tot niets",
        "kan je de tijd zeggen",
        "kan jij dat veroorzaken",
        "wat veroorzaakt regen",
        "wat zijn de gevolgen van regen",
        "regen veroorzaakt modder",
        "leidt regen",
        "hoe laat is het",
    ])
    def test_negeert_andere_zinnen(self, router, zin):
        r, bus = router
        assert r.detect_causes_check(zin) is False
        assert bus.events("intent_causes_check") == []

    def test_emit_eigen_topic(self, router):
        r, bus = router
        r.detect_causes_check("leidt regen tot modder")

        assert "topic_detected:causes_check" in bus.namen()


class TestRouteVroegeStap:
    def test_leidt_regen_tot_tijd_is_geen_tijdvraag(self, router):
        r, bus = router
        r.route({"text": "leidt regen tot tijd"})

        assert bus.events("intent_causes_check") == [{"source": "regen", "target": "tijd"}]
        assert bus.events("intent_time_query") == []

    def test_veroorzaakt_regen_weer_is_geen_weervraag(self, router):
        r, bus = router
        r.route({"text": "veroorzaakt regen weer"})

        assert bus.events("intent_causes_check") == [{"source": "regen", "target": "weer"}]
        assert bus.events("intent_weather") == []

    def test_gewone_tijdvraag_blijft_werken(self, router):
        r, bus = router
        r.route({"text": "hoe laat is het"})

        assert len(bus.events("intent_time_query")) == 1
        assert bus.events("intent_causes_check") == []


# ---------------------------------------------------------------------
# Parser + bevestigingszinnen
# ---------------------------------------------------------------------

class TestParserEnBevestiging:
    def test_leidt_tot_is_causes(self):
        parser = RelationParser()

        gevonden = parser.detect_relation("regen leidt tot modder")
        assert gevonden["relation_type"] == "causes"

        geparsed = parser.parse_relation("regen leidt tot modder", gevonden["pattern"])
        assert geparsed == {"subject": "regen", "object": "modder"}

    def test_stopwoord_onderwerp_wordt_niet_aangemaakt(self):
        """'dat leidt tot niets' is geen kennis: is_ruiswoord('dat')."""
        assert RelationParser().is_ruiswoord("dat") is True

    def test_bevestigingsvraag_is_nederlands(self, engines):
        store, se, re_, _ = engines
        bus = DummyEventBus()
        flow = RelationFlowEngine(store, se, re_, bus)

        flow.start_relation_flow("regen", "causes", "modder")

        tekst = bus.events("chat_response")[-1]["text"]
        assert tekst == "Mag ik onthouden dat 'regen' veroorzaakt 'modder'?"
        assert "causes" not in tekst

    def test_bevestiging_ja_is_nederlands_en_slaat_op(self, engines):
        store, se, re_, _ = engines
        bus = DummyEventBus()
        flow = RelationFlowEngine(store, se, re_, bus)
        flow.start_relation_flow("regen", "causes", "modder")

        flow.handle_confirm("ja")

        tekst = bus.events("chat_response")[-1]["text"]
        assert tekst == "Oké, ik onthoud: 'regen' veroorzaakt 'modder'."
        assert re_.get_causes("regen") == ["modder"]

    def test_onbekend_relatietype_valt_terug_op_ruwe_naam(self, engines):
        store, se, re_, _ = engines
        flow = RelationFlowEngine(store, se, re_, DummyEventBus())

        assert flow._rel_tekst("is_a") == "is een soort van"
        assert flow._rel_tekst("nieuw_type") == "nieuw_type"


# ---------------------------------------------------------------------
# ChatModule.on_causes_check
# ---------------------------------------------------------------------

class FakeSemantic:
    def __init__(self, antwoord="Ja, test.", crash=False):
        self.antwoord = antwoord
        self.crash = crash
        self.aanroepen = []

    def explain_causes(self, source, target):
        self.aanroepen.append((source, target))
        if self.crash:
            raise RuntimeError("kapot")
        return self.antwoord


def _antwoord(bus):
    return bus.events("layer4_response")[-1]["text"]


class TestOnCausesCheck:
    def test_geeft_uitleg_door(self):
        bus = DummyEventBus()
        sem = FakeSemantic("Ja, regen veroorzaakt modder.")
        chat = ChatModule(bus, semantic_module=sem)

        chat.on_causes_check({"source": "regen", "target": "modder"})

        assert _antwoord(bus) == "Ja, regen veroorzaakt modder."
        assert sem.aanroepen == [("regen", "modder")]

    def test_ontbrekend_veld(self):
        bus = DummyEventBus()
        chat = ChatModule(bus, semantic_module=FakeSemantic())

        chat.on_causes_check({"source": "regen"})

        assert "begrijp" in _antwoord(bus)

    def test_exception_crasht_niet(self):
        bus = DummyEventBus()
        chat = ChatModule(bus, semantic_module=FakeSemantic(crash=True))

        chat.on_causes_check({"source": "regen", "target": "modder"})

        assert "Ik kan nu niet controleren" in _antwoord(bus)

    def test_zonder_semantic(self):
        bus = DummyEventBus()
        chat = ChatModule(bus, semantic_module=None)

        chat.on_causes_check({"source": "regen", "target": "modder"})

        assert "Ik kan nog niet controleren" in _antwoord(bus)



# ---------------------------------------------------------------------
# Fase 8.3: formulering bij ketens + cirkels zijn GEEN contradictie
# ---------------------------------------------------------------------

class TestKetenFormulering:
    def test_directe_oorzaak_blijft_stellig(self, engines):
        _, se, re_, rs = engines
        _causes(re_, se, "regen", "modder")

        assert rs.explain_causes("regen", "modder") == "Ja, regen veroorzaakt modder."

    def test_keten_van_twee_schakels_is_waarschijnlijk(self, engines):
        _, se, re_, rs = engines
        _causes(re_, se, "regen", "modder")
        _causes(re_, se, "modder", "uitglijden")

        assert rs.explain_causes("regen", "uitglijden") == (
            "Waarschijnlijk wel: regen leidt tot uitglijden, "
            "via: regen → modder → uitglijden."
        )

    def test_lange_keten_toont_volledig_pad(self, engines):
        _, se, re_, rs = engines
        for bron, doel in zip(["a", "b", "c", "d", "e"], ["b", "c", "d", "e", "f"]):
            _causes(re_, se, bron, doel)

        tekst = rs.explain_causes("a", "d")

        assert tekst.startswith("Waarschijnlijk wel")
        assert "a → b → c → d" in tekst

    def test_negatief_antwoord_blijft_ongewijzigd(self, engines):
        _, se, re_, rs = engines
        se.add_sense("ei", "testdefinitie", source="user")

        assert rs.explain_causes("ei", "server").startswith("Ik kan niet bewijzen")


class TestCausaleCirkelIsGeenContradictie:
    """
    BEWUSTE ONTWERPKEUZE (11 oktober 2026): anders dan een part_of-cirkel
    is een causale kringloop (stress -> slecht slapen -> stress) niet
    logisch onmogelijk. find_contradictions() mag die dus NIET melden.
    Deze test voorkomt dat iemand dit later 'repareert'.
    """

    def test_causes_cirkel_is_geen_conflict(self, engines):
        _, se, re_, rs = engines
        _causes(re_, se, "stress", "slecht_slapen")
        _causes(re_, se, "slecht_slapen", "stress")

        assert rs.find_contradictions("stress") == []
        assert rs.find_contradictions("slecht_slapen") == []

    def test_cirkel_blokkeert_gevolgen_en_check_niet(self, engines):
        _, se, re_, rs = engines
        _causes(re_, se, "stress", "slecht_slapen")
        _causes(re_, se, "slecht_slapen", "stress")

        assert [g["woord"] for g in rs.get_all_effects("stress")] == ["slecht_slapen"]
        assert rs.explain_causes("stress", "slecht_slapen") == (
            "Ja, stress veroorzaakt slecht_slapen."
        )