# tests/test_en_dan77.py
"""
Punt 77 (6 november 2026): "en dan?" na een gevolgvraag.

Nova onthoudt in last_context welke gevolgen ze net noemde (en tot welke diepte ze keek).
- "en dan?" / "en wat dan" / "en wat gebeurt er daarna" kijkt een blok (MAX_DEPTH_CAUSAL = 4)
  verder, met een harde grens van 8, en noemt ALLEEN gevolgen die nog niet gezegd waren.
- Is er niets nieuws, dan zegt Nova dat eerlijk en herhaalt ze wat ze al noemde (terugval B).
- Zonder onthouden gevolgenvraag blijft "en dan?" ongemoeid (fallback zoals voorheen).

Gebruikt een tijdelijke concepts.json (tmp_path); je echte data wordt nooit aangeraakt.
"""
import pytest

import core.semantic as semantic_mod
from core import context_resolver as cr
from core.event_bus import EventBus
from core.intent_router import IntentRouter
from core.last_context import LastContext, init_module as init_last_context
from core.semantic import ConceptStore, SemanticConceptsModule
from modules.chat.chat import ChatModule


# ---------------------------------------------------------------------------
# Pure tests: herkennen van "en dan?"
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("zin", [
    "en dan?", "En dan", "en wat dan", "en wat dan?", "wat dan?", "en daarna?",
    "en wat gebeurt er dan", "en wat gebeurt er daarna?", "wat gebeurt er daarna",
    "ok en dan?", "en vervolgens?",
])
def test_is_en_dan_herkent_de_vormen(zin):
    assert cr.is_en_dan(zin)


@pytest.mark.parametrize("zin", [
    "dan", "verder", "en dan een tafel", "en dan de kat?", "wat is dan een kat",
    "en een kat dan", "dan niet", "en nu?", "en dat?", "wat zijn de gevolgen van roken",
])
def test_is_en_dan_laat_andere_zinnen_met_rust(zin):
    assert not cr.is_en_dan(zin)


# ---------------------------------------------------------------------------
# last_context
# ---------------------------------------------------------------------------
def test_last_context_onthoudt_gevolgen():
    lc = LastContext()
    assert lc.get_gevolgen() is None
    lc.set_concept("roken", antwoord_type="gevolgen_roken")
    lc.set_gevolgen("roken", [{"woord": "hoesten", "diepte": 1, "pad": ["roken", "hoesten"]}], 4)
    bron, getoond, diepte = lc.get_gevolgen()
    assert bron == "roken" and diepte == 4 and getoond[0]["woord"] == "hoesten"


def test_last_context_nieuw_onderwerp_wist_gevolgen():
    lc = LastContext()
    lc.set_gevolgen("roken", [{"woord": "hoesten", "diepte": 1, "pad": ["roken", "hoesten"]}], 4)
    lc.set_concept("appel")
    assert lc.get_gevolgen() is None


def test_last_context_clear_wist_gevolgen():
    lc = LastContext()
    lc.set_gevolgen("roken", [{"woord": "hoesten", "diepte": 1, "pad": ["roken", "hoesten"]}], 4)
    lc.clear()
    assert lc.get_gevolgen() is None


def test_last_context_onthoudt_ook_dat_er_geen_gevolgen_zijn():
    lc = LastContext()
    lc.set_gevolgen("roken", [], 4)
    assert lc.get_gevolgen() == ("roken", [], 4)


def test_last_context_negeert_lege_bron():
    lc = LastContext()
    lc.set_gevolgen("", [{"woord": "x", "diepte": 1, "pad": []}], 4)
    assert lc.get_gevolgen() is None


# ---------------------------------------------------------------------------
# Door de hele router heen
# ---------------------------------------------------------------------------
def _keten(sem, *woorden):
    for a, b in zip(woorden, woorden[1:]):
        sem.add_relation(a, "causes", b)


@pytest.fixture
def omgeving(tmp_path, monkeypatch):
    echte_klasse = ConceptStore
    concepts = str(tmp_path / "data" / "concepts.json")
    log = str(tmp_path / "logs" / "concepts.jsonl")
    monkeypatch.setattr(semantic_mod, "ConceptStore", lambda: echte_klasse(concepts, log))
    bus = EventBus()
    sem = SemanticConceptsModule(bus)
    for woord in ["appel", "fruit"]:
        sem.sense_engine.add_sense(woord, f"een {woord}", source="user", confidence=1.0)
    # Lange keten: 7 schakels = 7 gevolgen van "roken" (diepte 1 t/m 7).
    _keten(sem, "roken", "hoesten", "longschade", "kanker", "zuurstoftekort",
           "vermoeidheid", "bedlegerigheid", "spierverlies")
    # Korte keten: alles past al in het eerste antwoord.
    _keten(sem, "koffie", "onrust", "slapeloosheid")
    # Zeer lange keten (12) om de harde grens te testen.
    _keten(sem, "a0", "a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8", "a9", "a10", "a11", "a12")
    return bus, sem


def _stel(omgeving, *zinnen):
    bus, sem = omgeving
    opgenomen, teksten = [], []
    orig = bus.publish

    def opnemen(event_type, data=None, *a, **k):
        opgenomen.append((event_type, data))
        return orig(event_type, data, *a, **k)

    bus.publish = opnemen
    bus.subscribe("layer4_response", lambda d, *a, **k: teksten.append(d.get("text", "")))
    bus.subscribe("chat_response", lambda d, *a, **k: teksten.append(d.get("text", "")))
    bus.modules = getattr(bus, "modules", {})
    bus.modules["semantic"] = sem
    bus.register_module("last_context", init_last_context(bus))
    ChatModule(bus, semantic_module=sem)
    router = IntentRouter(bus, semantic_module=sem)
    uitkomst = []
    for z in zinnen:
        opgenomen.clear()
        teksten.clear()
        router.route({"text": z}, "chat_message")
        uitkomst.append(([(e, d) for e, d in opgenomen], " ".join(teksten)))
    return uitkomst


def test_eerste_antwoord_loopt_tot_diepte_4_en_en_dan_noemt_de_rest(omgeving):
    eerste, dan = _stel(omgeving, "Wat is het gevolg van roken?", "en dan?")
    assert "zuurstoftekort" in eerste[1]          # diepte 4: nog in het eerste antwoord
    assert "vermoeidheid" not in eerste[1]        # diepte 5: pas bij "en dan?"
    events, tekst = dan
    assert any(e == "intent_effects" for e, _ in events)
    for nieuw in ("vermoeidheid", "bedlegerigheid", "spierverlies"):
        assert nieuw in tekst
    # Wat al gezegd was komt NIET opnieuw als nieuw gevolg
    assert "hoesten" not in tekst and "kanker" not in tekst
    assert "minder zeker" in tekst


def test_tweede_en_dan_geeft_de_eerlijke_terugval(omgeving):
    _, dan1, dan2 = _stel(omgeving, "Wat is het gevolg van roken?", "en dan?", "en dan?")
    tekst = dan2[1]
    assert "Verder dan wat ik al noemde ken ik geen gevolgen" in tekst
    # De terugval herhaalt wat Nova al noemde, zodat de gebruiker het niet kwijt is
    assert "hoesten" in tekst and "spierverlies" in tekst


def test_herhaalde_terugval_is_kort(omgeving):
    _, dan1, dan2, dan3 = _stel(omgeving, "Wat is het gevolg van koffie?", "en dan?", "en wat dan", "en dan?")
    assert dan1[1].startswith("Verder dan wat ik al noemde ken ik geen gevolgen")
    assert dan2[1] == "Nee, dat was het. Meer weet ik er niet van."
    assert dan3[1] == "Nee, dat was het. Meer weet ik er niet van."


def test_korte_herhaling_begint_opnieuw_bij_nieuwe_gevolgvraag(omgeving):
    teksten = [t for _, t in _stel(omgeving, "Wat is het gevolg van koffie?", "en dan?", "en dan?",
                                   "Wat is het gevolg van koffie?", "en dan?")]
    assert teksten[2] == "Nee, dat was het. Meer weet ik er niet van."
    assert teksten[4].startswith("Verder dan wat ik al noemde ken ik geen gevolgen")


def test_herhaald_zonder_kennis_is_ook_kort(omgeving):
    _, dan1, dan2 = _stel(omgeving, "Wat is het gevolg van wolken?", "en dan?", "en dan?")
    assert dan1[1].startswith("Ik ken geen gevolgen van 'wolken', dus ook")
    assert dan2[1] == "Nee, dat was het. Meer weet ik er niet van."


def test_korte_keten_geeft_meteen_de_terugval(omgeving):
    eerste, dan = _stel(omgeving, "Wat is het gevolg van koffie?", "en dan?")
    assert "slapeloosheid" in eerste[1]
    events, tekst = dan
    assert any(e == "intent_effects" for e, _ in events)
    assert "Verder dan wat ik al noemde ken ik geen gevolgen van 'koffie'" in tekst
    assert "onrust" in tekst and "slapeloosheid" in tekst


@pytest.mark.parametrize("vervolg", ["en wat dan", "En wat dan?", "en daarna?", "en wat gebeurt er daarna"])
def test_andere_vormen_werken_ook(omgeving, vervolg):
    _, (events, tekst) = _stel(omgeving, "Wat is het gevolg van roken?", vervolg)
    assert any(e == "intent_effects" for e, _ in events)
    assert "vermoeidheid" in tekst


def test_harde_grens_diepte_8(omgeving):
    teksten = [t for _, t in _stel(omgeving, "Wat is het gevolg van a0?", "en dan?", "en dan?")]
    eerste, dan1, dan2 = teksten
    assert "a4" in eerste and "a5" not in eerste
    assert "a5" in dan1 and "a8" in dan1 and "a9" not in dan1
    # Geen derde blok: de grens is 8, ook al bestaat de keten verder.
    assert "a9" not in dan2
    assert "Verder dan wat ik al noemde ken ik geen gevolgen" in dan2


def test_en_dan_zonder_gevolgvraag_blijft_ongemoeid(omgeving):
    _, (events, tekst) = _stel(omgeving, "wat is een appel", "en dan?")
    assert not any(e == "intent_effects" for e, _ in events)
    assert tekst == ""


def test_en_dan_zonder_enige_voorgaande_vraag_blijft_ongemoeid(omgeving):
    (events, tekst), = _stel(omgeving, "en dan?")
    assert not any(e == "intent_effects" for e, _ in events)


def test_en_dan_na_gevolgvraag_zonder_kennis_geeft_eerlijk_antwoord(omgeving):
    # Nova kent geen gevolgen van "wolken": "en dan?" mag geen stilte of verzinsel geven.
    eerste, (events, tekst) = _stel(omgeving, "Wat is het gevolg van wolken?", "en dan?")
    assert "Ik ken geen gevolgen van 'wolken'" in eerste[1]
    assert any(e == "intent_effects" for e, _ in events)
    assert tekst == "Ik ken geen gevolgen van 'wolken', dus ook niets dat daarna komt."


def test_nieuw_onderwerp_tussendoor_maakt_en_dan_ongeldig(omgeving):
    _, _, (events, _) = _stel(omgeving, "Wat is het gevolg van roken?", "wat is een appel", "en dan?")
    assert not any(e == "intent_effects" for e, _ in events)


def test_en_dan_een_tafel_blijft_een_nieuw_onderwerp(omgeving):
    # "en dan een tafel" is de bestaande ellips-vorm (punt 62d) en mag niet gekaapt worden.
    _, (events, _) = _stel(omgeving, "wat is een appel", "en dan een fruit")
    assert not any(e == "intent_effects" for e, _ in events)