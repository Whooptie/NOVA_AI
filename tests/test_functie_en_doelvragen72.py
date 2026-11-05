# tests/test_functie_en_doelvragen72.py
"""
Tests voor punt 72b/72c (5 november 2026): functievragen ("wat doet een klok") en doelvragen
("is een boek iets om te lezen", "is een paraplu bedoeld tegen regen").

Eerlijk over wat dit is: GEEN begrip van functies. Een functievraag wordt een gewone
definitievraag (de definitie bevat meestal wat iets doet). Een doelvraag zoekt het doel
als woord in de kennisgraaf of in de definitie. Staat het er niet, dan zegt Nova dat eerlijk
en nooit een stellig 'nee'. Een 'ja' op grond van de definitie kan, na jouw ja, onthouden worden.
"""
import pytest

import core.semantic as semantic_mod
from core.context_resolver import is_verwijzing_zonder_onderwerp, los_op
from core.event_bus import EventBus
from core.intent_router import IntentRouter
from core.language_normalizer import normaliseer
from core.semantic import ConceptStore, SemanticConceptsModule
from modules.chat.chat import ChatModule


# ---------------------------------------------------------------------------
# Normalizer
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("zin, verwacht", [
    ("wat doet een klok", "wat is een klok"),
    ("Wat doet een klok?", "wat is een klok"),
    ("kun je zeggen wat een klok doet", "wat is een klok"),
    ("wat meet een thermometer", "wat is een thermometer"),
    ("wat is de functie van een hart", "wat is een hart"),
    ("wat is de taak van een thermostaat", "wat is een thermostaat"),
])
def test_functievraag_wordt_definitievraag(zin, verwacht):
    nieuw, regel = normaliseer(zin)
    assert nieuw == verwacht
    assert regel is not None


@pytest.mark.parametrize("zin, verwacht", [
    ("is een boek iets om te lezen", "wordt boek gebruikt om te lezen"),
    ("is een sleutel iets om mee te openen", "wordt sleutel gebruikt om mee te openen"),
    ("is een paraplu bedoeld tegen regen", "wordt paraplu gebruikt tegen regen"),
    ("is een mes gemaakt om te snijden", "wordt mes gebruikt om te snijden"),
    ("kun je een mes gebruiken om te snijden", "wordt mes gebruikt om te snijden"),
    ("gebruik je een hamer om te slaan", "wordt hamer gebruikt om te slaan"),
    ("dient een hamer om te slaan", "wordt hamer gebruikt om te slaan"),
])
def test_doelvraag_wordt_canoniek(zin, verwacht):
    nieuw, regel = normaliseer(zin)
    assert nieuw == verwacht
    assert regel is not None


@pytest.mark.parametrize("zin", [
    "wat doet nova",
    "wat doet het",
    "wat doe jij",
    "wat doet een dokter in huis",          # te lang / niet kaal
    "wat doet je batterij",                 # over Nova zelf
    "is een boek iets goeds",               # geen doel
    "is nova bedoeld om te praten",         # over Nova zelf
])
def test_blijft_ongemoeid(zin):
    nieuw, regel = normaliseer(zin)
    assert nieuw == zin
    assert regel is None


def test_idempotent():
    for zin in ["wat doet een klok", "is een boek iets om te lezen"]:
        eerste, _ = normaliseer(zin)
        tweede, regel = normaliseer(eerste)
        assert tweede == eerste
        assert regel is None


# ---------------------------------------------------------------------------
# Vervolgvragen (context_resolver)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("zin", [
    "wat doet zo'n ding", "wat meet dat ding eigenlijk", "wat doet dat orgaan",
    "en wat doet dat", "wat is de functie van dat",
])
def test_functie_verwijzing_na_definitie(zin):
    assert los_op(zin, "wat is {x}", "een hart", "np") == ("wat is een hart", "functie_verwijzing")


def test_functie_verwijzing_alleen_na_definitie():
    # Na een kaal onderwerp (bv. een oorzaakvraag) is dit geen functievraag.
    assert los_op("wat doet dat ding", "wat veroorzaakt {x}", "regen", "kaal") is None


def test_functie_verwijzing_zonder_voorvraag_wordt_herkend():
    assert is_verwijzing_zonder_onderwerp("wat doet zo'n ding")
    assert not is_verwijzing_zonder_onderwerp("wat doet een klok")


# ---------------------------------------------------------------------------
# Door de hele router heen
# ---------------------------------------------------------------------------
DEFINITIES = {
    "boek": "Een boek is een verzameling bedrukte bladzijden, meestal om te lezen.",
    "sleutel": "Een sleutel is een klein metalen voorwerp waarmee je een slot opent of sluit.",
    "paraplu": "Een paraplu is een scherm dat je boven je hoofd houdt om je te beschermen tegen regen.",
    "thermometer": "Een thermometer is een instrument waarmee je de temperatuur meet.",
    "hart": "Het hart is het orgaan dat bloed door het lichaam pompt.",
}


@pytest.fixture
def omgeving(tmp_path, monkeypatch):
    echte_klasse = ConceptStore
    concepts = str(tmp_path / "data" / "concepts.json")
    log = str(tmp_path / "logs" / "concepts.jsonl")
    monkeypatch.setattr(semantic_mod, "ConceptStore", lambda: echte_klasse(concepts, log))
    bus = EventBus()
    sem = SemanticConceptsModule(bus)
    for woord, definitie in DEFINITIES.items():
        sem.sense_engine.add_sense(woord, definitie, source="user", confidence=1.0)
    return bus, sem


def _stel(omgeving, *zinnen):
    """Stuurt de zinnen door de router. Geeft per zin (events, tekst) terug."""
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
    from core.last_context import init_module as init_last_context
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


@pytest.mark.parametrize("zin, deel", [
    ("is een boek iets om te lezen", "lezen"),
    ("is een sleutel iets om mee te openen", "opent"),
    ("is een paraplu bedoeld tegen regen", "regen"),
])
def test_doelvraag_ja_via_definitie(omgeving, zin, deel):
    ((events, tekst),) = _stel(omgeving, zin)
    assert any(e == "intent_relation_check" for e, _ in events)
    assert tekst.startswith("Ja, dat staat in mijn definitie")
    assert deel in tekst


def test_doelvraag_onbevestigd_is_geen_nee(omgeving):
    ((_, tekst),) = _stel(omgeving, "is een boek iets om te slapen")
    assert "Dat staat niet in wat ik weet" in tekst
    assert "Nee" not in tekst
    assert "Mag ik onthouden" not in tekst


def test_doelvraag_onbekend_woord(omgeving):
    ((_, tekst),) = _stel(omgeving, "is een tang iets om te knijpen")
    assert "Ik ken 'tang' niet" in tekst


def test_doelvraag_over_nova_zelf_gaat_niet_langs_doelroute(omgeving):
    ((events, _),) = _stel(omgeving, "is nova bedoeld om te praten")
    assert not any(d and d.get("relatie") == "doel" for _, d in events if isinstance(d, dict))


def test_functievraag_geeft_definitie(omgeving):
    ((events, tekst),) = _stel(omgeving, "wat doet een thermometer")
    assert any(e == "intent_definition" for e, _ in events)
    assert "temperatuur" in tekst


def test_functievraag_achter_inleiding(omgeving):
    ((events, tekst),) = _stel(omgeving, "kun je zeggen wat een thermometer doet")
    assert any(e == "intent_definition" for e, _ in events)
    assert "temperatuur" in tekst


def test_functie_vervolgvraag(omgeving):
    _, (events, tekst) = _stel(omgeving, "wat is een thermometer", "wat meet dat ding eigenlijk")
    assert any(e == "intent_definition" for e, _ in events)
    assert "temperatuur" in tekst


# ---------------------------------------------------------------------------
# Deel 3: leren via ja/nee
# ---------------------------------------------------------------------------
def test_leren_vraagt_om_bevestiging_en_slaat_niets_automatisch_op(omgeving):
    _, sem = omgeving
    ((_, tekst),) = _stel(omgeving, "is een boek iets om te lezen")
    assert "Mag ik onthouden dat 'boek' wordt gebruikt voor 'lezen'?" in tekst
    assert "lezen" not in sem.get_used_for("boek")


def test_leren_ja_slaat_doel_op(omgeving):
    _, sem = omgeving
    _stel(omgeving, "is een boek iets om te lezen", "ja")
    assert "lezen" in sem.get_used_for("boek")


def test_leren_ja_en_daarna_antwoordt_nova_uit_de_graaf(omgeving):
    _stel(omgeving, "is een boek iets om te lezen", "ja")
    ((_, tekst),) = _stel_opnieuw(omgeving, "is een boek iets om te lezen")
    assert tekst.startswith("Ja, boek wordt gebruikt voor lezen.")
    assert "Mag ik onthouden" not in tekst


def test_leren_nee_slaat_niets_op_en_wordt_niet_opnieuw_gevraagd(omgeving):
    _, sem = omgeving
    _stel(omgeving, "is een boek iets om te lezen", "nee")
    assert "lezen" not in sem.get_used_for("boek")
    ((_, tekst),) = _stel_opnieuw(omgeving, "is een boek iets om te lezen")
    assert "Mag ik onthouden" not in tekst


def test_geen_leervraag_bij_naamwoorddoel(omgeving):
    # "tegen regen" is een naamwoord, geen werkwoord: wel antwoord, geen opslagvraag.
    ((_, tekst),) = _stel(omgeving, "is een paraplu bedoeld tegen regen")
    assert tekst.startswith("Ja, dat staat in mijn definitie")
    assert "Mag ik onthouden" not in tekst


def _stel_opnieuw(omgeving, *zinnen):
    """Nog een ronde in dezelfde omgeving: nieuwe router, zelfde kennis. Houdt de stub-bus eenvoudig."""
    bus, sem = omgeving
    teksten = []
    bus.subscribe("layer4_response", lambda d, *a, **k: teksten.append(d.get("text", "")))
    bus.subscribe("chat_response", lambda d, *a, **k: teksten.append(d.get("text", "")))
    router = IntentRouter(bus, semantic_module=sem)
    uitkomst = []
    for z in zinnen:
        teksten.clear()
        router.route({"text": z}, "chat_message")
        uitkomst.append(([], " ".join(teksten)))
    return uitkomst