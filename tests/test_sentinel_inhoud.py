"""Inhoud (entity, definition, parent) moet tussen ⟦ ⟧ staan, anders maakt
de brugs-filter er dialect van."""

from core.response_engine import ResponseEngine


class NepBus:
    def __init__(self):
        self.gepubliceerd = []

    def subscribe(self, naam, handler):
        pass

    def publish(self, naam, data=None):
        self.gepubliceerd.append((naam, data))


class NepSemantic:
    def __init__(self, definitie=None, ouders=None):
        self.definitie = definitie
        self.ouders = ouders or []

    def get_meaning(self, entity, context_words=None):
        return self.definitie

    def get_relations(self, entity, soort):
        return self.ouders


def test_definitie_en_entity_staan_tussen_sentinel():
    eng = ResponseEngine(NepBus(), layers={"semantic": NepSemantic("een programmeertaal")})
    tekst = eng.generate("python")["text"]
    assert "⟦python⟧" in tekst
    assert "⟦een programmeertaal⟧" in tekst


def test_parent_staat_tussen_sentinel():
    eng = ResponseEngine(NepBus(), layers={"semantic": NepSemantic(None, ["dier"])})
    tekst = eng.generate("hond")["text"]
    assert "⟦hond⟧" in tekst
    assert "⟦dier⟧" in tekst


def test_onbekend_wikkelt_entity_in_sentinel():
    eng = ResponseEngine(NepBus(), layers={"semantic": NepSemantic(None)})
    tekst = eng.generate("flubber")["text"]
    assert "⟦flubber⟧" in tekst