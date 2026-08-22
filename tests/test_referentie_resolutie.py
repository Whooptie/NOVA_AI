# tests/test_referentie_resolutie.py
"""
Test tegen de ECHTE IntentRouter (core/intent_router.py) en de ECHTE
LastContext (core/last_context.py) -- Taal & Redeneerlimieten, idee
1+2 (zie taal_en_redeneerlimieten_roadmap.md).

IntentRouter doet geen I/O in __init__() en is injecteerbaar zonder
monkeypatch (zelfde bevestigde patroon als de bestaande
bridge_query/memory_query-tests, zie nova_state.md). Een nep-EventBus
(publish/subscribe/register_module/.modules-dict) volstaat.

Dekking:
- _is_kale_verwijzing(): woordenlijst-classificatie zelf, los van de
  rest van de routing.
- _verwerk_referentie(): de drie paden (geen verwijzing / oplosbaar /
  niet oplosbaar).
- verwerk_referentie_antwoord(): de "waar heb je het over?"-vervolgvraag.
- _emit_topic(concept=...): vult last_context correct, bestaande
  aanroepen zonder concept blijven ongewijzigd werken.
- De 7 detect_*()-methodes uit _build_intent_tabel_deel2() die
  _laatste_concept_kandidaat zetten, en de tabel-lus die dit
  doorgeeft + altijd reset.
- Een volledig end-to-end scenario door de echte route()-methode heen.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from core.intent_router import IntentRouter
from core.last_context import LastContext


class DummyEventBus:
    """Zelfde nep-EventBus-patroon als bevestigd werkend voor
    IntentRouter/ChatModule in nova_state.md: publish/subscribe/
    register_module/.modules-dict, geen echte I/O."""

    def __init__(self):
        self.published = []
        self.subscribers = {}
        self.modules = {}

    def subscribe(self, event, handler):
        self.subscribers.setdefault(event, []).append(handler)

    def publish(self, event, data=None):
        self.published.append((event, data))

    def register_module(self, name, instance):
        self.modules[name] = instance

    # Helpers voor leesbare assertions in de tests hieronder.
    def laatste(self):
        return self.published[-1] if self.published else None

    def events(self):
        return [e for e, _ in self.published]

    def vind(self, event_naam):
        for e, d in self.published:
            if e == event_naam:
                return d
        return None


@pytest.fixture
def bus():
    return DummyEventBus()


@pytest.fixture
def last_ctx(bus):
    ctx = LastContext()
    bus.register_module("last_context", ctx)
    return ctx


@pytest.fixture
def router(bus):
    return IntentRouter(bus)


# ------------------------------------------------------------
# _is_kale_verwijzing() -- woordenlijst-classificatie zelf
# ------------------------------------------------------------

@pytest.mark.parametrize("zin", [
    "wat is dat",
    "wat is dat?",
    "en die?",
    "hetzelfde als net",
    "hetzelfde als daarnet",
    "wat is die",
    "is dat zo",
    "bedoel je dat",
])
def test_kale_verwijzingen_herkend(router, zin):
    assert router._is_kale_verwijzing(zin) is True


@pytest.mark.parametrize("zin", [
    "wat is python",
    "wat is dat schaakstuk",
    "hallo daar",
    "hoe laat is het",
    "vergelijk python met java",
    "",
])
def test_geen_kale_verwijzing_bij_eigen_zelfstandig_naamwoord(router, zin):
    assert router._is_kale_verwijzing(zin) is False


def test_zin_zonder_verwijswoord_is_nooit_kaal(router):
    """Randgeval: een zin met enkel functiewoorden, maar GEEN
    verwijswoord, mag niet als 'kaal' gezien worden (er is dan niets
    om op te lossen)."""
    assert router._is_kale_verwijzing("wat is en of") is False


# ------------------------------------------------------------
# _herschrijf_met_concept() -- woordvervanging
# ------------------------------------------------------------

def test_herschrijf_vervangt_eerste_verwijswoord(router):
    resultaat = router._herschrijf_met_concept("wat is dat", "python")
    assert resultaat == "wat is python"


def test_herschrijf_behoudt_rest_van_de_zin(router):
    resultaat = router._herschrijf_met_concept("en wat is dat dan?", "python")
    assert resultaat == "en wat is python dan?"


def test_herschrijf_zonder_verwijswoord_verandert_niets(router):
    resultaat = router._herschrijf_met_concept("hallo daar", "python")
    assert resultaat == "hallo daar"


# ------------------------------------------------------------
# _verwerk_referentie() -- de drie paden
# ------------------------------------------------------------

def test_geen_verwijzing_geeft_tekst_ongewijzigd_terug(router, last_ctx):
    last_ctx.set_concept("python")
    resultaat = router._verwerk_referentie("wat is java")
    assert resultaat == "wat is java"


def test_oplosbare_verwijzing_herschrijft_tekst(router, last_ctx):
    last_ctx.set_concept("python")
    resultaat = router._verwerk_referentie("wat is dat")
    assert resultaat == "wat is python"


def test_oplosbare_verwijzing_ververst_timestamp_niet_content(router, last_ctx, monkeypatch):
    """Kernpunt uit het ontwerp: een geslaagde resolutie mag de
    INHOUD niet aanraken, enkel de geldigheidsduur verlengen."""
    calls = []
    monkeypatch.setattr(last_ctx, "ververs_timestamp", lambda: calls.append(True))
    last_ctx.set_concept("python", antwoord_type="definitie_python")

    router._verwerk_referentie("wat is dat")

    assert calls == [True]
    assert last_ctx.get_concept() == "python"
    assert last_ctx.get_antwoord_type() == "definitie_python"


def test_niet_oplosbare_verwijzing_stelt_tegenvraag(router, bus, last_ctx):
    """last_ctx bestaat wel, maar is leeg/verlopen."""
    resultaat = router._verwerk_referentie("wat is dat")

    assert resultaat is None
    laatste = bus.vind("chat_response")
    assert laatste == {"text": "Waar heb je het over?"}


def test_niet_oplosbare_verwijzing_zet_pending_referentie_vraag(router, last_ctx):
    router._verwerk_referentie("wat is dat")
    assert router._pending_referentie_vraag == {"oorspronkelijke_tekst": "wat is dat"}


def test_geen_last_context_module_valt_veilig_terug(router, bus):
    """Als last_context (nog) niet geregistreerd is (bv. laadvolgorde-
    probleem), mag dit nooit crashen -- moet zich gedragen als
    'niet oplosbaar', consistent met hoe andere Layer-ontbrekingen
    elders in dit bestand worden afgehandeld."""
    assert bus.modules.get("last_context") is None
    resultaat = router._verwerk_referentie("wat is dat")
    assert resultaat is None
    assert bus.vind("chat_response") == {"text": "Waar heb je het over?"}


# ------------------------------------------------------------
# verwerk_referentie_antwoord() -- vervolg op "Waar heb je het over?"
# ------------------------------------------------------------

def test_geen_open_referentie_vraag_geeft_false(router):
    assert router.verwerk_referentie_antwoord("python") is False


def test_antwoord_op_referentie_vraag_herbouwt_en_route_opnieuw(router, bus, last_ctx, monkeypatch):
    router._pending_referentie_vraag = {"oorspronkelijke_tekst": "wat is dat"}

    herroutet = []
    monkeypatch.setattr(router, "route", lambda data: herroutet.append(data))

    resultaat = router.verwerk_referentie_antwoord("python")

    assert resultaat is True
    assert herroutet == [{"text": "wat is python"}]


def test_antwoord_op_referentie_vraag_wist_pending_state(router, monkeypatch):
    router._pending_referentie_vraag = {"oorspronkelijke_tekst": "wat is dat"}
    monkeypatch.setattr(router, "route", lambda data: None)

    router.verwerk_referentie_antwoord("python")

    assert router._pending_referentie_vraag is None


def test_antwoord_op_referentie_vraag_zet_nieuw_concept(router, last_ctx, monkeypatch):
    """Kevin noemt het woord nu zelf expliciet -- dat MOET meteen als
    nieuw, expliciet onderwerp gelden (veiligheidsklep)."""
    router._pending_referentie_vraag = {"oorspronkelijke_tekst": "wat is dat"}
    monkeypatch.setattr(router, "route", lambda data: None)

    router.verwerk_referentie_antwoord("python")

    assert last_ctx.get_concept() == "python"


def test_leeg_antwoord_op_referentie_vraag_geeft_nette_boodschap(router, bus):
    router._pending_referentie_vraag = {"oorspronkelijke_tekst": "wat is dat"}

    resultaat = router.verwerk_referentie_antwoord("   ")

    assert resultaat is True
    assert bus.vind("chat_response") == {
        "text": "Dat heb ik niet goed verstaan, laten we het hier maar bij laten."
    }


def test_leeg_antwoord_wist_toch_de_pending_state(router):
    """Voorkomt dat een onherkend antwoord de vraag voor altijd open
    laat staan."""
    router._pending_referentie_vraag = {"oorspronkelijke_tekst": "wat is dat"}
    router.verwerk_referentie_antwoord("   ")
    assert router._pending_referentie_vraag is None


def test_geen_last_context_module_bij_antwoord_crasht_niet(router, monkeypatch):
    router._pending_referentie_vraag = {"oorspronkelijke_tekst": "wat is dat"}
    monkeypatch.setattr(router, "route", lambda data: None)
    # Geen last_context geregistreerd in bus.modules.
    resultaat = router.verwerk_referentie_antwoord("python")
    assert resultaat is True


# ------------------------------------------------------------
# _emit_topic(concept=...) -- vult last_context correct
# ------------------------------------------------------------

def test_emit_topic_zonder_concept_laat_last_context_ongewijzigd(router, last_ctx, bus):
    router._emit_topic("greeting")
    assert last_ctx.get_concept() is None
    assert bus.vind("topic_detected:greeting") == {"bron": "detect"}


def test_emit_topic_met_concept_vult_last_context(router, last_ctx):
    router._emit_topic("definitie_python", concept="python")
    assert last_ctx.get_concept() == "python"
    assert last_ctx.get_antwoord_type() == "definitie_python"


def test_emit_topic_met_concept_maar_geen_last_context_module_crasht_niet(router, bus):
    # Geen last_context geregistreerd.
    router._emit_topic("definitie_python", concept="python")
    assert bus.vind("topic_detected:definitie_python") == {"bron": "detect"}


def test_emit_topic_met_lege_concept_string_vult_niets(router, last_ctx):
    """concept='' (bv. concept_overview zonder herkend woord) mag
    last_context niet met een lege string vullen."""
    router._emit_topic("concept_overview", concept="")
    assert last_ctx.get_concept() is None


# ------------------------------------------------------------
# De 7 detect_*()-methodes: zetten ze _laatste_concept_kandidaat
# correct, en altijd het EERST genoemde woord (vaste regel)?
# ------------------------------------------------------------

@pytest.mark.parametrize("zin, verwacht_kandidaat", [
    ("is een hond een dier", "hond"),
    ("hond is een dier", "hond"),
])
def test_relation_check_zet_eerst_genoemde_term(router, zin, verwacht_kandidaat):
    assert router.detect_relation_check(zin) is True
    assert router._laatste_concept_kandidaat == verwacht_kandidaat


@pytest.mark.parametrize("zin, verwacht_kandidaat", [
    ("is een wiel onderdeel van een fiets", "wiel"),
    ("zit een wiel in een fiets", "wiel"),
])
def test_part_of_check_zet_eerst_genoemde_term(router, zin, verwacht_kandidaat):
    assert router.detect_part_of_check(zin) is True
    assert router._laatste_concept_kandidaat == verwacht_kandidaat


def test_subtypes_query_zet_het_enige_woord(router):
    assert router.detect_subtypes_query("welke soorten dier ken je") is True
    assert router._laatste_concept_kandidaat == "dier"


def test_parts_query_zet_het_enige_woord(router):
    assert router.detect_parts_query("welke onderdelen heeft fiets") is True
    assert router._laatste_concept_kandidaat == "fiets"


@pytest.mark.parametrize("zin, verwacht_kandidaat", [
    ("is python gerelateerd aan java", "python"),
    ("heeft python te maken met java", "python"),
])
def test_related_to_check_zet_eerst_genoemde_term(router, zin, verwacht_kandidaat):
    assert router.detect_related_to_check(zin) is True
    assert router._laatste_concept_kandidaat == verwacht_kandidaat


def test_compare_concepts_zet_eerst_genoemde_term(router):
    assert router.detect_compare_concepts("vergelijk python met java") is True
    assert router._laatste_concept_kandidaat == "python"


def test_bridge_query_zet_eerst_genoemde_term(router):
    assert router.detect_bridge_query("bridge python en java") is True
    assert router._laatste_concept_kandidaat == "python"


def test_detect_zonder_match_zet_geen_kandidaat(router):
    """Randgeval: een onherkende zin mag _laatste_concept_kandidaat
    niet aanraken (blijft None, zoals bij __init__)."""
    assert router.detect_relation_check("dit matcht helemaal niets") is False
    assert router._laatste_concept_kandidaat is None


# ------------------------------------------------------------
# Tabel-lus (_intent_tabel_deel2 via route()): geeft de kandidaat
# door aan _emit_topic() en reset ALTIJD, ook bij _topic_al_ge_emit
# ------------------------------------------------------------

def test_tabel_lus_geeft_kandidaat_door_aan_last_context(router, last_ctx):
    router.route({"text": "vergelijk python met java"})
    assert last_ctx.get_concept() == "python"


def test_tabel_lus_reset_kandidaat_na_gebruik(router, last_ctx):
    router.route({"text": "vergelijk python met java"})
    assert router._laatste_concept_kandidaat is None


def test_tabel_lus_zonder_match_laat_last_context_ongewijzigd(router, last_ctx):
    last_ctx.set_concept("bestaand")
    # "hallo" matcht greeting (deel1), niet deel2 -- geen kandidaat.
    router.route({"text": "hallo"})
    assert last_ctx.get_concept() == "bestaand"


def test_tabel_lus_reset_kandidaat_ook_bij_topic_al_ge_emit(router):
    """Als een detect_*() al een specifieker topic heeft ge-emit
    (_topic_al_ge_emit == True), moet de kandidaat ALSNOG gereset
    worden -- anders 'lekt' hij door naar een volgend, ongerelateerd
    bericht."""
    router._laatste_concept_kandidaat = "moet-verdwijnen"
    router._topic_al_ge_emit = True
    # Forceer een match in deel2 via een gestubde detect-functie op de
    # eerste tabel-regel, om de vroege-return-tak te raken zonder van
    # een specifieke echte triggerzin afhankelijk te zijn.
    router._intent_tabel_deel2 = [("dummy_topic", lambda text: True)]

    router.route({"text": "willekeurige zin"})

    assert router._laatste_concept_kandidaat is None
    assert router._topic_al_ge_emit is False


# ------------------------------------------------------------
# End-to-end door de echte route() heen
# ------------------------------------------------------------

def test_end_to_end_definitie_daarna_kale_verwijzing(router, bus, last_ctx):
    """Kernscenario uit het ontwerp: 'wat is python' -> last_context
    gevuld -> 'wat is dat' wordt herschreven en herkend als dezelfde
    definitievraag."""
    router.route({"text": "wat is python"})
    assert last_ctx.get_concept() == "python"

    bus.published.clear()
    router.route({"text": "wat is dat"})

    definitie_event = bus.vind("intent_definition")
    assert definitie_event is not None
    assert definitie_event["word"] == "python"
    assert bus.vind("topic_detected:definitie_python") is not None


def test_end_to_end_niet_oplosbare_verwijzing_daarna_antwoord(router, bus, last_ctx):
    """'wat is dat' zonder voorafgaand onderwerp -> tegenvraag ->
    Kevin antwoordt 'python' -> alsnog correct als definitievraag
    verwerkt."""
    router.route({"text": "wat is dat"})
    assert bus.vind("chat_response") == {"text": "Waar heb je het over?"}
    assert router._pending_referentie_vraag is not None

    bus.published.clear()
    router.route({"text": "python"})

    definitie_event = bus.vind("intent_definition")
    assert definitie_event is not None
    assert definitie_event["word"] == "python"
    assert last_ctx.get_concept() == "python"


def test_end_to_end_nieuw_expliciet_onderwerp_overschrijft_oud(router, last_ctx):
    """Veiligheidsklep: een nieuw, expliciet genoemd onderwerp wint
    altijd, ongeacht de vervaltijd."""
    router.route({"text": "wat is python"})
    assert last_ctx.get_concept() == "python"

    router.route({"text": "wat is java"})
    assert last_ctx.get_concept() == "java"


def test_end_to_end_vergelijking_vult_last_context_voor_latere_verwijzing(router, bus, last_ctx):
    """De tweede uitbreiding (tabel-gedreven detects): een
    vergelijkingsvraag moet ook bruikbaar zijn als latere
    verwijzingsanker."""
    router.route({"text": "vergelijk python met java"})
    assert last_ctx.get_concept() == "python"

    bus.published.clear()
    router.route({"text": "wat is dat"})

    definitie_event = bus.vind("intent_definition")
    assert definitie_event is not None
    assert definitie_event["word"] == "python"


def test_end_to_end_ellipsis_zin_zonder_last_context_valt_terug_op_tegenvraag(router, bus):
    """Zonder enige voorgeschiedenis moet 'en die?' netjes om
    verduidelijking vragen, niet crashen of stil de fallback ingaan."""
    router.route({"text": "en die?"})
    assert bus.vind("chat_response") == {"text": "Waar heb je het over?"}