"""Inhoud (entity, definition, parent, associatie) moet tussen ⟦ ⟧ staan,
anders maakt de brugs-filter er dialect van. De tekens zelf mogen de
gebruiker nooit bereiken."""

from core.response_engine import ResponseEngine
from modules.chat.brugs_filter import BrugsFilter
from modules.chat.expression_injector import ExpressionInjector


class NepBus:
    def __init__(self, modules=None):
        self.gepubliceerd = []
        self.modules = modules or {}

    def subscribe(self, naam, handler):
        pass

    def publish(self, naam, data=None):
        self.gepubliceerd.append((naam, data))

    def register_module(self, naam, module):
        self.modules[naam] = module


class NepSemantic:
    def __init__(self, definitie=None, ouders=None):
        self.definitie = definitie
        self.ouders = ouders or []

    def get_meaning(self, entity, context_words=None):
        return self.definitie

    def get_relations(self, entity, soort):
        return self.ouders


class NepAssociaties:
    """find_related() geeft AL gesorteerd terug, sterk naar zwak."""

    def __init__(self, woord="snel", score=0.9):
        self.woord = woord
        self.score = score

    def find_related(self, zoeksleutel, top_k=1):
        return [(self.woord, self.score)]


class NepPatronen:
    def __init__(self):
        self.gevraagd = []

    def is_pattern_active(self, event_type):
        self.gevraagd.append(event_type)
        return False


def _engine(modules=None, associatie="snel", definitie="een goed voertuig"):
    bus = NepBus(modules)
    eng = ResponseEngine(bus, layers={
        "semantic": NepSemantic(definitie),
        "word_associations": NepAssociaties(associatie),
    })
    return eng, bus


def _filtertje_aan():
    filtertje = BrugsFilter(bewaar=False)
    filtertje.aan = True
    return filtertje


def test_definitie_en_entity_staan_tussen_sentinel():
    eng = ResponseEngine(NepBus(), layers={"semantic": NepSemantic("een programmeertaal")})
    eng.templates["definitie"] = ["{entity}? Dat is {definition}."]
    tekst = eng.generate("python")["text"]
    assert "⟦python⟧" in tekst
    assert "⟦een programmeertaal⟧" in tekst


def test_parent_staat_tussen_sentinel():
    eng = ResponseEngine(NepBus(), layers={"semantic": NepSemantic(None, ["dier"])})
    eng.templates["is_a_fallback"] = ["'{entity}' valt onder {parent}. Meer krijg je niet."]
    tekst = eng.generate("hond")["text"]
    assert "⟦hond⟧" in tekst
    assert "⟦dier⟧" in tekst


def test_onbekend_wikkelt_entity_in_sentinel():
    eng = ResponseEngine(NepBus(), layers={"semantic": NepSemantic(None)})
    # Eén van de vijf varianten ("Hmm, dat weet ik niet.") gebruikt
    # {entity} niet. Forceer daarom de variant die hem wel gebruikt,
    # anders is deze test willekeurig rood bij ongeveer 1 op 5 runs.
    eng.templates["onbekend"] = ["Pff, '{entity}' ken ik niet."]
    tekst = eng.generate("flubber")["text"]
    assert "⟦flubber⟧" in tekst


def test_associatie_staat_tussen_sentinel():
    eng, _ = _engine()
    tekst = eng.generate("python")["text"]
    assert "⟦snel⟧" in tekst
    assert "⟦een goed voertuig⟧" in tekst


def test_associatie_overleeft_de_brugs_filter():
    """De filter mag de definitie en de associatie niet aanraken; de
    tekens moeten er daarna uit zijn."""
    eng, bus = _engine({"brugs_filter": _filtertje_aan()})
    tekst = eng.generate("python")["text"]
    assert "⟦snel⟧" in tekst

    uit = ExpressionInjector(bus)._brugs(tekst, "normaal")

    assert "⟦" not in uit
    assert "⟧" not in uit
    assert "een goed voertuig" in uit
    assert "snel" in uit
    assert "rap" not in uit
    assert "een goe voertuig" not in uit


def test_associatie_wordt_gestript_zonder_filter_module():
    """Lek van 22 november 2026: zonder brugs_filter-module bleven de
    tekens letterlijk in het antwoord staan."""
    eng, bus = _engine()
    tekst = eng.generate("python")["text"]

    uit = ExpressionInjector(bus)._brugs(tekst, "normaal")

    assert "⟦" not in uit
    assert "⟧" not in uit
    assert "snel" in uit


def test_entity_blijft_als_variabele_schoon():
    """De entity gaat ook naar de Layer 2-topicnaam; daar mogen geen
    sentinels in zitten, anders groeit er een patroon
    'definitie_⟦python⟧'."""
    patronen = NepPatronen()
    bus = NepBus()
    eng = ResponseEngine(bus, layers={
        "semantic": NepSemantic("een goed voertuig"),
        "word_associations": NepAssociaties("snel"),
        "pattern_matcher": patronen,
    })

    eng.generate("python")

    assert patronen.gevraagd == ["topic_detected:definitie_python"]
    assert "⟦" not in patronen.gevraagd[0]