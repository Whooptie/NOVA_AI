# tests/test_vervolgzinnen76.py
"""
Punt 76 (5 november 2026): vervolgzinnen na oorzaak-, gevolg- en definitievragen.

Uit de benchmark (13 cases met "waardoor gebeurt dat", "gevolgen", "is dat fruit", ...):

  A. core/language_normalizer.py: "Waarom smelt sneeuw", "Waardoor krijg je een blaar" en
     "Waarom gaat melk schiften" werden niet begrepen, dus er was geen onderwerp om op
     voort te bouwen.
  B. core/context_resolver.py: alleen "wat zijn de gevolgen van X" met X van hoogstens 2
     woorden werd onthouden. Nu ook gebeurtenissen ("te veel koffie drinkt") en de vorm
     "wat is het gevolg van X".
  C. core/context_resolver.py: "is dat fruit" (doel zonder lidwoord, alleen met een bekend
     concept), "waardoor smelt dat" (werkwoord + verwijzing) en "hoe ontstaat zo'n ding".

Groep D ("en dan?" / "en wat dan" na een gevolgvraag) was hier bewust niet gebouwd; dat
kwam later in punt 77 (zie tests/test_en_dan77.py).

Eerst pure tests op de twee modules, daarna een paar tests door de hele router heen op een
tijdelijke concepts.json (tmp_path); je echte data wordt nooit aangeraakt.
"""
import pytest

import core.semantic as semantic_mod
from core import context_resolver as cr
from core.event_bus import EventBus
from core.intent_router import IntentRouter
from core.language_normalizer import normaliseer
from core.semantic import ConceptStore, SemanticConceptsModule
from modules.chat.chat import ChatModule


# ---------------------------------------------------------------------------
# A. Normalizer
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("zin, verwacht, regel", [
    ("Waarom smelt sneeuw?", "wat veroorzaakt sneeuw smelt", "oorzaak_waarom_zin"),
    ("Waarom gaat melk schiften?", "wat veroorzaakt melk gaat schiften", "oorzaak_waarom_zin"),
    ("waarom wordt iemand moe", "wat veroorzaakt iemand wordt moe", "oorzaak_waarom_zin"),
    ("Waardoor krijg je een blaar?", "wat veroorzaakt blaar", "oorzaak_krijg"),
    ("Waardoor krijg je hoofdpijn?", "wat veroorzaakt hoofdpijn", "oorzaak_krijg"),
    ("waarom krijg je dorst", "wat veroorzaakt dorst", "oorzaak_krijg"),
])
def test_normalizer_nieuwe_oorzaakvormen(zin, verwacht, regel):
    assert normaliseer(zin) == (verwacht, regel)


@pytest.mark.parametrize("zin", [
    "waarom is de lucht blauw",        # koppelwerkwoord: reden, geen gebeurtenis
    "waarom kan een vogel vliegen",    # modaal werkwoord
    "waarom ben je boos",              # vraag aan Nova zelf
    "waarom doe je dat",
    "waarom krijg je een update",      # gaat over Nova zelf
])
def test_normalizer_laat_andere_waarom_vragen_met_rust(zin):
    nieuw, regel = normaliseer(zin)
    assert regel is None
    assert nieuw == zin


def test_normalizer_bestaande_waarom_regels_blijven_werken():
    assert normaliseer("waarom ontstaat regen") == ("wat veroorzaakt regen", "oorzaak_waarom")
    assert normaliseer("waarom is een kat een zoogdier") == ("is een kat een zoogdier", "relatie_waarom")


# ---------------------------------------------------------------------------
# B. Resolver: wat wordt er onthouden?
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("zin, verwacht", [
    ("wat zijn de gevolgen van te veel koffie drinkt",
     ("wat zijn de gevolgen van {x}", "te veel koffie drinkt", "kaal")),
    ("wat zijn de gevolgen van te lang in de kou staat",
     ("wat zijn de gevolgen van {x}", "te lang in de kou staat", "kaal")),
    ("wat is het gevolg van roken", ("wat zijn de gevolgen van {x}", "roken", "kaal")),
    ("wat is het gevolg van te weinig slaap",
     ("wat zijn de gevolgen van {x}", "te weinig slaap", "kaal")),
    ("wat veroorzaakt sneeuw smelt", ("wat veroorzaakt {x}", "sneeuw smelt", "kaal")),
    ("wat veroorzaakt melk gaat schiften", ("wat veroorzaakt {x}", "melk gaat schiften", "kaal")),
])
def test_herken_vraag_onthoudt_gebeurtenissen(zin, verwacht):
    assert cr.herken_vraag(zin) == verwacht


@pytest.mark.parametrize("zin", [
    "wat zijn de gevolgen van dat",
    "wat zijn de gevolgen van nu",
    "wat veroorzaakt wat ik doe",
    "wat zijn de gevolgen van waardoor dat gebeurt",
])
def test_herken_vraag_onthoudt_geen_verwijzingen(zin):
    assert cr.herken_vraag(zin) is None


def test_herken_vraag_oude_vormen_blijven_werken():
    assert cr.herken_vraag("wat is een hond") == ("wat is {x}", "een hond", "np")
    assert cr.herken_vraag("wat zijn de gevolgen van regen") == ("wat zijn de gevolgen van {x}", "regen", "kaal")
    assert cr.herken_vraag("is een zebra een dier") == ("is {x} een dier", "een zebra", "np")


# ---------------------------------------------------------------------------
# C. Resolver: nieuwe vervolgvormen
# ---------------------------------------------------------------------------
APPEL = ("wat is {x}", "een appel", "np")
IJS = ("wat is {x}", "ijs", "np")
GEVOLG = ("wat zijn de gevolgen van {x}", "te weinig water drinkt", "kaal")


def _concept(woord):
    return woord in {"fruit", "dier"}


def test_is_dat_fruit_met_bekend_concept():
    assert cr.los_op("is dat fruit", *APPEL, is_concept=_concept) == ("is een appel fruit", "relatie_verwijzing")


def test_is_dat_fruit_zonder_concept_functie_blijft_ongemoeid():
    assert cr.los_op("is dat fruit", *APPEL) is None


@pytest.mark.parametrize("zin", ["is dat goed", "is dat gevaarlijk", "is dat heel groot", "is dat waar"])
def test_is_dat_met_gewoon_woord_wordt_niet_herschreven(zin):
    assert cr.los_op(zin, *APPEL, is_concept=_concept) is None


def test_is_dat_een_dier_werkt_nog_zonder_concept_functie():
    assert cr.los_op("is dat een dier", *APPEL) == ("is een appel een dier", "relatie_verwijzing")


def test_waardoor_smelt_dat():
    assert cr.los_op("waardoor smelt dat", *IJS) == (
        "wat veroorzaakt ijs smelt", "oorzaak_werkwoord_verwijzing")


def test_waarom_werkt_dat_met_en_ervoor():
    assert cr.los_op("en waarom smelt dat", *IJS) == (
        "wat veroorzaakt ijs smelt", "oorzaak_werkwoord_verwijzing")


@pytest.mark.parametrize("zin", ["waarom is dat", "waarom kan dat", "waarom doet dat"])
def test_koppel_en_modale_werkwoorden_geen_gebeurtenis(zin):
    assert cr.los_op(zin, *IJS) is None


def test_hoe_ontstaat_zon_ding():
    vraag = ("wat veroorzaakt {x}", "blaar", "kaal")
    assert cr.los_op("hoe ontstaat zo'n ding", *vraag) == ("wat veroorzaakt blaar", "oorzaak_verwijzing")


def test_oude_verwijzingen_blijven_werken():
    assert cr.los_op("waardoor ontstaat dat", *IJS) == ("wat veroorzaakt ijs", "oorzaak_verwijzing")
    assert cr.los_op("gevolgen", *GEVOLG) == (
        "wat zijn de gevolgen van te weinig water drinkt", "gevolg_verwijzing")
    assert cr.los_op("gevolgen daarvan", *GEVOLG)[1] == "gevolg_verwijzing"


def test_verwijzing_zonder_onderwerp():
    assert cr.is_verwijzing_zonder_onderwerp("waardoor smelt dat")
    assert cr.is_verwijzing_zonder_onderwerp("hoe ontstaat zo'n ding")
    assert not cr.is_verwijzing_zonder_onderwerp("waarom is dat")


# ---------------------------------------------------------------------------
# Door de hele router heen
# ---------------------------------------------------------------------------
@pytest.fixture
def omgeving(tmp_path, monkeypatch):
    echte_klasse = ConceptStore
    concepts = str(tmp_path / "data" / "concepts.json")
    log = str(tmp_path / "logs" / "concepts.jsonl")
    monkeypatch.setattr(semantic_mod, "ConceptStore", lambda: echte_klasse(concepts, log))
    bus = EventBus()
    sem = SemanticConceptsModule(bus)
    for woord in ["appel", "fruit", "ijs"]:
        sem.sense_engine.add_sense(woord, f"een {woord}", source="user", confidence=1.0)
    sem.add_relation("appel", "is_a", "fruit")
    return bus, sem


def _stel(omgeving, *zinnen):
    """Stuurt de zinnen door de router. Geeft per zin (events, tekst) terug."""
    bus, sem = omgeving
    opgenomen = []
    teksten = []
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


def _woord(events, soort):
    return [d.get("word") for e, d in events if e == soort]


def test_router_is_dat_fruit(omgeving):
    _, (events, tekst) = _stel(omgeving, "wat is een appel", "is dat fruit")
    assert any(e == "intent_relation_check" for e, _ in events)
    assert "Ja" in tekst


def test_router_is_dat_goed_blijft_ongemoeid(omgeving):
    _, (events, _) = _stel(omgeving, "wat is een appel", "is dat goed")
    assert not any(e == "context_resolved" for e, _ in events)


def test_router_waarom_smelt_sneeuw_en_vervolg(omgeving):
    (e1, _), (e2, _) = _stel(omgeving, "Waarom smelt sneeuw?", "waardoor gebeurt dat")
    assert _woord(e1, "intent_causes") == ["sneeuw smelt"]
    assert _woord(e2, "intent_causes") == ["sneeuw smelt"]


def test_router_waardoor_krijg_je_hoofdpijn_en_vervolg(omgeving):
    (e1, _), (e2, _) = _stel(omgeving, "Waardoor krijg je hoofdpijn?", "hoe ontstaat dat")
    assert _woord(e1, "intent_causes") == ["hoofdpijn"]
    assert _woord(e2, "intent_causes") == ["hoofdpijn"]


@pytest.mark.parametrize("vervolg", ["gevolgen", "gevolgen daarvan", "wat is het gevolg ervan"])
def test_router_gevolg_van_gebeurtenis_en_vervolg(omgeving, vervolg):
    (e1, _), (e2, _) = _stel(omgeving, "Wat gebeurt er als je te weinig water drinkt?", vervolg)
    assert _woord(e1, "intent_effects") == ["te weinig water drinkt"]
    assert _woord(e2, "intent_effects") == ["te weinig water drinkt"]


def test_router_wat_is_het_gevolg_van_roken_en_vervolg(omgeving):
    (e1, _), (e2, _) = _stel(omgeving, "Wat is het gevolg van roken?", "gevolgen")
    assert _woord(e1, "intent_effects") == ["roken"]
    assert _woord(e2, "intent_effects") == ["roken"]


def test_router_waardoor_smelt_dat_na_definitie(omgeving):
    _, (events, _) = _stel(omgeving, "wat is ijs", "waardoor smelt dat")
    assert _woord(events, "intent_causes") == ["ijs smelt"]


def test_router_verwijzing_zonder_voorvraag_vraagt_terug(omgeving):
    ((events, tekst),) = _stel(omgeving, "gevolgen")
    assert "Waar heb je het over" in tekst
    assert not any(e == "intent_effects" for e, _ in events)


def test_router_en_dan_geeft_niet_stilletjes_dezelfde_gevolgen_opnieuw(omgeving):
    # Punt 77: "en dan?" na een gevolgvraag is nu gebouwd (tests/test_en_dan77.py). Hier blijft
    # de eis staan dat het nooit stilletjes DEZELFDE gevolgen opnieuw geeft: in deze omgeving
    # kent Nova geen gevolgen van roken, dus het antwoord is de eerlijke "niets dat daarna komt".
    _, (events, tekst) = _stel(omgeving, "Wat is het gevolg van roken?", "en dan?")
    assert tekst == "Ik ken geen gevolgen van 'roken', dus ook niets dat daarna komt."
    assert not tekst.startswith("Gevolgen van")