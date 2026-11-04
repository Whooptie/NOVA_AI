# tests/test_meervoud70.py
"""
Tests voor punt 70 (4 november 2026): "hoort een hond bij de dieren" en het
meervoud op het pad van relatievragen.

Alles draait op een tijdelijke concepts.json (tmp_path); je echte data wordt
nooit aangeraakt.
"""
import pytest

import core.semantic as semantic_mod
from core.context_resolver import los_op
from core.event_bus import EventBus
from core.intent_router import IntentRouter
from core.language_normalizer import normaliseer
from core.semantic import ConceptStore, SemanticConceptsModule
from modules.chat.chat import ChatModule


# ---------------------------------------------------------------- normalizer
@pytest.mark.parametrize("zin, verwacht", [
    ("hoort een hond bij de dieren", "is een hond een dieren"),
    ("Hoort een stoel bij de meubels?", "is een stoel een meubels"),
    ("hoort een gitaar bij de muziekinstrumenten", "is een gitaar een muziekinstrumenten"),
    ("hoort een berg bij de landschappen", "is een berg een landschappen"),
    ("hoort een beker bij de drinkbekers", "is een beker een drinkbekers"),
    ("hoort een kat ook bij de huisdieren", "is een kat een huisdieren"),
    ("behoort een hond tot de dieren", "is een hond een dieren"),
    ("valt een tomaat onder de groenten", "is een tomaat een groenten"),
    ("kun je me zeggen of een hond bij de dieren hoort", None),  # andere vorm: niet in dit punt
])
def test_hoort_bij_wordt_herschreven(zin, verwacht):
    nieuw, regel = normaliseer(zin)
    if verwacht is None:
        assert regel is None
    else:
        assert (nieuw, regel) == (verwacht, "relatie_hoort_bij")


@pytest.mark.parametrize("zin", [
    "hoort een wiel bij een auto",          # enkelvoud, kan part_of zijn
    "hoort een kat bij de buurman",         # geen meervoud
    "hoort een hond bij de familie",
    "hoort een wiel bij de auto",
    "hoort die bij de zoogdieren",          # verwijzing: doet de context_resolver
    "hoort dat bij de dieren",
    "hoort jij bij de dieren",              # over Nova zelf
    "hoort een hond bij",                   # onvolledig
    "een hond hoort bij de dieren",         # stelling, geen vraag
])
def test_hoort_bij_blijft_ongemoeid(zin):
    assert normaliseer(zin) == (zin, None)


def test_idempotent():
    eerste, _ = normaliseer("hoort een hond bij de dieren")
    assert normaliseer(eerste) == (eerste, None)


# ---------------------------------------------------------------- vervolgvraag
def test_hoort_die_bij_gebruikt_het_onthouden_onderwerp():
    assert los_op("hoort die bij de zoogdieren", "wat is {}", "een kat", "np") == \
        ("is een kat een zoogdieren", "hoort_verwijzing")
    assert los_op("en hoort dat dan ook bij de dieren", "wat is {}", "een kat", "np") == \
        ("is een kat een dieren", "hoort_verwijzing")


def test_hoort_die_bij_zonder_meervoud_of_kaal_onderwerp_blijft_staan():
    assert los_op("hoort die bij de auto", "wat is {}", "een kat", "np") is None
    assert los_op("hoort die bij de zoogdieren", "wat is {}", "wandelen", "kaal") is None


# ---------------------------------------------------------------- meervoudsfunctie
@pytest.fixture
def omgeving(tmp_path, monkeypatch):
    echte_klasse = ConceptStore
    concepts = str(tmp_path / "data" / "concepts.json")
    log = str(tmp_path / "logs" / "concepts.jsonl")
    monkeypatch.setattr(semantic_mod, "ConceptStore", lambda: echte_klasse(concepts, log))
    bus = EventBus()
    sem = SemanticConceptsModule(bus)
    for woord in ["hond", "dier", "zoogdier", "kat", "landschap", "berg", "groente", "tomaat",
                  "plaats", "plaat", "plek", "boom", "auto", "wiel"]:
        sem.sense_engine.add_sense(woord, f"een {woord}", source="user", confidence=1.0)
    sem.add_relation("hond", "is_a", "zoogdier")
    sem.add_relation("zoogdier", "is_a", "dier")
    sem.add_relation("kat", "is_a", "zoogdier")
    sem.add_relation("tomaat", "is_a", "groente")
    sem.add_relation("plaats", "is_a", "plek")
    return bus, sem


@pytest.mark.parametrize("meervoud, enkelvoud", [
    ("dieren", "dier"),                 # bestond al
    ("honden", "hond"),
    ("landschappen", "landschap"),      # dubbele medeklinker
    ("bomen", "boom"),                  # lange klinker
    ("tomaten", "tomaat"),
    ("groenten", "groente"),            # enkelvoud op -e
    ("auto's", "auto"),
    ("zoogdieren", "zoogdier"),
])
def test_meervoud_naar_enkelvoud(omgeving, meervoud, enkelvoud):
    _, sem = omgeving
    assert sem.teach_engine._normalize_plural_if_noun(meervoud, "noun") == enkelvoud


def test_onbekend_woord_en_bestaand_woord_blijven_staan(omgeving):
    _, sem = omgeving
    te = sem.teach_engine
    assert te._normalize_plural_if_noun("flurbens", "noun") == "flurbens"
    # 'plaats' is zelf een concept: de nieuwe regels mogen er geen 'plaat' van maken
    assert te._normalize_plural_if_noun("plaatsen", "noun") == "plaats"
    assert te._normalize_plural_if_noun("bomen", "verb") == "bomen"


# ---------------------------------------------------------------- door de echte router en chat
def _stel(omgeving, *zinnen):
    bus, sem = omgeving
    antwoorden = []
    bus.subscribe("layer4_response", lambda d, *a, **k: antwoorden.append(d.get("text", "")))
    bus.subscribe("chat_response", lambda d, *a, **k: antwoorden.append(d.get("text", "")))
    bus.modules = getattr(bus, "modules", {})
    bus.modules["semantic"] = sem
    from core.last_context import init_module as init_last_context
    bus.register_module("last_context", init_last_context(bus))
    ChatModule(bus, semantic_module=sem)
    router = IntentRouter(bus, semantic_module=sem)
    uitkomst = []
    for z in zinnen:
        antwoorden.clear()
        router.route({"text": z}, "chat_message")
        uitkomst.append(list(antwoorden))
    return uitkomst


def test_meervoud_in_relatievraag(omgeving):
    (antwoord,) = _stel(omgeving, "is een hond een dieren")
    assert any("Ja, een hond is een dier" in a for a in antwoord)


def test_hoort_bij_geeft_hetzelfde_antwoord_als_is_een(omgeving):
    (a,) = _stel(omgeving, "hoort een hond bij de dieren")
    (b,) = _stel(omgeving, "is een hond een dier")
    assert any("Ja, een hond is een dier" in x for x in a)
    assert any("Ja, een hond is een dier" in x for x in b)


def test_groenten_en_plaats(omgeving):
    (a,) = _stel(omgeving, "valt een tomaat onder de groenten")
    assert any("Ja, een tomaat is een groente" in x for x in a)
    (b,) = _stel(omgeving, "is een plaats een plek")
    assert any("Ja, een plaats is een plek" in x for x in b)


def test_vervolgvraag_hoort_die_bij(omgeving):
    _, antwoord = _stel(omgeving, "is een kat een dier", "hoort die bij de zoogdieren")
    assert any("Ja, een kat is een zoogdier" in a for a in antwoord)


def test_enkelvoud_wiel_auto_blijft_een_andere_vraag(omgeving):
    """'hoort een wiel bij een auto' wordt NIET naar is_a gezet (kan part_of zijn)."""
    (antwoord,) = _stel(omgeving, "hoort een wiel bij een auto")
    assert not any("is een auto" in a and a.startswith("Ja") for a in antwoord)