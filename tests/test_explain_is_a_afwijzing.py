import pytest

from core.semantic import (
    ConceptStore, SenseEngine, RelationEngine, ReasoningEngine, RelationFlowEngine,
)


class NepBus:
    def __init__(self):
        self.berichten = []

    def publish(self, event_type, data=None, *args, **kwargs):
        self.berichten.append((event_type, data))


@pytest.fixture
def kennis(tmp_path):
    store = ConceptStore(str(tmp_path / "concepts.json"), str(tmp_path / "log.jsonl"))
    sense = SenseEngine(store)
    rel = RelationEngine(store, sense)
    red = ReasoningEngine(store, rel)
    for woord, definitie in [
        ("hond", "een huisdier dat blaft"), ("kat", "een huisdier dat miauwt"),
        ("dier", "een levend wezen"), ("zoogdier", "een dier met melkklieren"),
        ("vogel", "een dier met veren"), ("meubel", "een ding in huis"),
    ]:
        sense.add_sense(woord, definitie)
    rel.add_relation("hond", "is_a", "zoogdier")
    rel.add_relation("kat", "is_a", "zoogdier")
    rel.add_relation("zoogdier", "is_a", "dier")
    rel.add_relation("vogel", "is_a", "dier")
    return store, sense, rel, red


def test_positief_antwoord_blijft_werken(kennis):
    _, _, _, red = kennis
    assert red.explain_is_a("hond", "dier").lower().startswith("ja")


def test_botsende_categorie_wordt_uitgelegd(kennis):
    _, _, _, red = kennis
    antwoord = red.explain_is_a("kat", "vogel").lower()
    assert "nee" in antwoord and "zoogdier" in antwoord
    assert "ja" not in antwoord.split()


def test_botsing_via_keten(kennis):
    _, _, _, red = kennis
    antwoord = red.explain_is_a("hond", "meubel").lower()
    assert "nee" in antwoord and "dier" in antwoord


def test_afgewezen_relatie_wordt_benoemd(kennis):
    _, _, rel, red = kennis
    rel.add_relation("hond", "is_a", "meubel")
    rel.reject_relation("hond", "hond#1", "is_a", "meubel")
    antwoord = red.explain_is_a("hond", "meubel").lower()
    assert "afgewezen" in antwoord and "eerder" in antwoord


def test_onbekend_woord_wordt_benoemd(kennis):
    _, _, _, red = kennis
    antwoord = red.explain_is_a("flurbo", "dier").lower()
    assert "ken" in antwoord.split()


def test_zonder_botsing_blijft_het_oude_antwoord(kennis):
    _, _, _, red = kennis
    antwoord = red.explain_is_a("hond", "wolf").lower()
    assert "kan niet bewijzen" in antwoord


def test_bewering_over_afgewezen_feit(kennis):
    store, sense, rel, _ = kennis
    rel.add_relation("hond", "is_a", "meubel")
    rel.reject_relation("hond", "hond#1", "is_a", "meubel")
    bus = NepBus()
    flow = RelationFlowEngine(store, sense, rel, bus)
    flow.start_relation_flow("hond", "is_a", "meubel")
    tekst = bus.berichten[-1][1]["text"].lower()
    assert "afgewezen" in tekst and "eerder" in tekst
    assert flow.pending_relation is None