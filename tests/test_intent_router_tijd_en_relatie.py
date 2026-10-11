# tests/test_intent_router_tijd_en_relatie.py
"""
Tests voor twee detector-gaten uit nova_state.md punt 30(c), 9 oktober 2026:

1. detect_time() ving kennisvragen over het woord "tijd"/"klok" op
   ("waarop lijkt tijd", "wat is een klok") omdat de losse-woordcheck
   op elk voorkomen van het woord reageerde, en detect_time() in
   route() vóór detect_definition() staat.
2. detect_relation_check() kende "is X een Y" zonder lidwoord niet
   ("is wandelen een activiteit" viel in de fallback).

Tegen de ECHTE IntentRouter, met een nep-EventBus. IntentRouter doet
geen I/O in __init__(), dus geen tmp_path/monkeypatch nodig.
"""
import pytest

from core.intent_router import IntentRouter


class NepBus:
    def __init__(self):
        self.modules = {}
        self.gepubliceerd = []

    def subscribe(self, *args, **kwargs):
        pass

    def publish(self, event, data=None):
        self.gepubliceerd.append((event, data or {}))

    def events(self, naam):
        return [d for e, d in self.gepubliceerd if e == naam]

    def leeg(self):
        self.gepubliceerd.clear()


@pytest.fixture
def router_en_bus():
    bus = NepBus()
    router = IntentRouter(bus)
    bus.leeg()  # eventuele opstart-events niet meetellen
    return router, bus


# ---------------------------------------------------------
# 1. detect_time(): echte tijdsvragen blijven werken
# ---------------------------------------------------------
@pytest.mark.parametrize("zin", [
    "hoe laat is het",
    "wat is de tijd",
    "wat is het uur",
    "hoeveel tijd heb ik nog",
    "tijd",
    "klok",
    "geef me de tijd",
])
def test_echte_tijdsvragen_blijven_tijdsvraag(router_en_bus, zin):
    router, bus = router_en_bus
    assert router.detect_time(zin) is True
    assert len(bus.events("intent_time_query")) == 1


# ---------------------------------------------------------
# 1. detect_time(): kennisvragen over het woord zelf NIET meer
# ---------------------------------------------------------
@pytest.mark.parametrize("zin", [
    "waarop lijkt tijd",
    "waar lijkt tijd op",
    "wat is tijd",
    "wat is een klok",
    "wat betekent tijd",
    "synoniemen van tijd",
    "waarvoor dient een klok",
    "wiki tijd",
])
def test_kennisvraag_over_tijd_is_geen_tijdsvraag(router_en_bus, zin):
    router, bus = router_en_bus
    assert router.detect_time(zin) is False
    assert bus.events("intent_time_query") == []


def test_route_waarop_lijkt_tijd_gaat_naar_related_to(router_en_bus):
    router, bus = router_en_bus
    router.route({"text": "waarop lijkt tijd"})
    assert bus.events("intent_time_query") == []
    related = bus.events("intent_related_to")
    assert len(related) == 1
    assert related[0]["word"] == "tijd"


def test_route_wat_is_de_tijd_blijft_tijdsvraag(router_en_bus):
    router, bus = router_en_bus
    router.route({"text": "wat is de tijd"})
    assert len(bus.events("intent_time_query")) == 1


# ---------------------------------------------------------
# 2. detect_relation_check(): nieuw patroon "is X een Y"
# ---------------------------------------------------------
@pytest.mark.parametrize("zin, source, target", [
    ("is wandelen een activiteit", "wandelen", "activiteit"),
    ("is kind een mens", "kind", "mens"),
    ("is koffie een drank?", "koffie", "drank"),
])
def test_is_x_een_y_zonder_lidwoord(router_en_bus, zin, source, target):
    router, bus = router_en_bus
    assert router.detect_relation_check(zin) is True
    events = bus.events("intent_relation_check")
    assert len(events) == 1
    assert events[0] == {"source": source, "target": target, "lidwoord": False}
    assert router._laatste_concept_kandidaat == source


def test_bestaand_patroon_is_een_x_een_y_ongewijzigd(router_en_bus):
    router, bus = router_en_bus
    assert router.detect_relation_check("is een kind een mens") is True
    assert bus.events("intent_relation_check")[0] == {"source": "kind", "target": "mens"}


def test_bestaand_patroon_x_is_een_y_ongewijzigd(router_en_bus):
    router, bus = router_en_bus
    assert router.detect_relation_check("egel is een zoogdier") is True
    assert bus.events("intent_relation_check")[0] == {"source": "egel", "target": "zoogdier"}


@pytest.mark.parametrize("zin", [
    "is het een goed idee",
    "is er een probleem",
    "is dit een test",
    "is dat een vraag",
    "is hij een vriend",
    "is nova een ai",
])
def test_stopwoord_als_x_wordt_niet_opgevangen(router_en_bus, zin):
    router, bus = router_en_bus
    assert router.detect_relation_check(zin) is False
    assert bus.events("intent_relation_check") == []


def test_route_is_wandelen_een_activiteit_geen_fallback(router_en_bus):
    router, bus = router_en_bus
    router.route({"text": "is wandelen een activiteit"})
    assert bus.events("intent_fallback") == []
    assert bus.events("intent_relation_check") == [
        {"source": "wandelen", "target": "activiteit", "lidwoord": False}
    ]


def test_oude_patronen_geven_geen_lidwoord_veld_mee(router_en_bus):
    # Ontbrekend veld = chat.py gebruikt True = oud gedrag ("Ja, een kind ...").
    router, bus = router_en_bus
    router.detect_relation_check("is een kind een mens")
    router.detect_relation_check("egel is een zoogdier")
    for event in bus.events("intent_relation_check"):
        assert "lidwoord" not in event


# ---------------------------------------------------------
# 3. Antwoordzin volgt de vraagvorm (10 oktober 2026)
#    "Ja, wandelen is een activiteit" i.p.v. "Ja, een wandelen ..."
# ---------------------------------------------------------
import inspect

import core.semantic as semantic_mod


def _reasoning_klasse():
    """Zoekt dynamisch de klasse met de echte explain_is_a (die ook
    is_a_chained heeft) -- zo breekt de test niet als de klasse ooit
    hernoemd wordt."""
    for _, klasse in inspect.getmembers(semantic_mod, inspect.isclass):
        if klasse.__module__ != semantic_mod.__name__:
            continue
        if hasattr(klasse, "is_a_chained") and hasattr(klasse, "explain_is_a"):
            return klasse
    pytest.fail("Geen klasse met is_a_chained + explain_is_a gevonden in core/semantic.py")


class _NepRelationEngine:
    def __init__(self, relaties):
        self.relaties = relaties

    def get_relations(self, woord, relation_type=None):
        return list(self.relaties)


def _maak_reasoning(gevonden, pad, alternatieven=()):
    klasse = _reasoning_klasse()
    obj = klasse.__new__(klasse)  # __init__ overslaan: geen bestanden/engines nodig
    obj.is_a_chained = lambda s, t: (gevonden, list(pad))
    obj.relation_engine = _NepRelationEngine(alternatieven)
    return obj


def test_explain_is_a_zonder_lidwoord_direct():
    r = _maak_reasoning(True, ["wandelen", "activiteit"])
    assert r.explain_is_a("wandelen", "activiteit", lidwoord=False) == "Ja, wandelen is een activiteit."


def test_explain_is_a_standaard_houdt_een():
    r = _maak_reasoning(True, ["kind", "mens"])
    assert r.explain_is_a("kind", "mens") == "Ja, een kind is een mens."


def test_explain_is_a_zonder_lidwoord_met_keten():
    r = _maak_reasoning(True, ["wandelen", "beweging", "activiteit"])
    assert r.explain_is_a("wandelen", "activiteit", lidwoord=False) == (
        "Ja, wandelen is een activiteit, want: wandelen → beweging → activiteit."
    )


def test_explain_is_a_negatief_alternatief_zonder_lidwoord():
    r = _maak_reasoning(False, [], alternatieven=["beweging"])
    antwoord = r.explain_is_a("wandelen", "dier", lidwoord=False)
    assert antwoord.endswith("maar ik weet wel dat wandelen een beweging is.")
    assert "een wandelen" not in antwoord


def test_explain_is_a_negatief_alternatief_standaard_houdt_een():
    r = _maak_reasoning(False, [], alternatieven=["dier"])
    antwoord = r.explain_is_a("hond", "meubel")
    assert antwoord.endswith("maar ik weet wel dat een hond een dier is.")


def test_explain_is_a_kaal_negatief_ongewijzigd():
    r = _maak_reasoning(False, [], alternatieven=[])
    assert r.explain_is_a("wandelen", "dier", lidwoord=False) == (
        "Ik kan niet bewijzen dat 'wandelen' een 'dier' is."
    )


# --- chat.py geeft het veld correct door ---
class _NepSemantic:
    def __init__(self):
        self.aanroepen = []

    def explain_is_a(self, source, target, lidwoord=True):
        self.aanroepen.append((source, target, lidwoord))
        return "ok"


def _maak_chat():
    chat_mod = pytest.importorskip("modules.chat.chat")
    for _, klasse in inspect.getmembers(chat_mod, inspect.isclass):
        if klasse.__module__ == chat_mod.__name__ and hasattr(klasse, "on_relation_check"):
            obj = klasse.__new__(klasse)
            obj.event_bus = NepBus()
            obj.semantic = _NepSemantic()
            return obj
    pytest.fail("Geen klasse met on_relation_check gevonden in modules/chat/chat.py")


def test_chat_geeft_lidwoord_false_door():
    chat = _maak_chat()
    chat.on_relation_check({"source": "wandelen", "target": "activiteit", "lidwoord": False})
    assert chat.semantic.aanroepen == [("wandelen", "activiteit", False)]


def test_chat_zonder_veld_gebruikt_true():
    chat = _maak_chat()
    chat.on_relation_check({"source": "kind", "target": "mens"})
    assert chat.semantic.aanroepen == [("kind", "mens", True)]