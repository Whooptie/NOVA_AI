# Tests voor de VOLGORDE waarin IntentRouter._route_intern de controles doorloopt
# (15 november 2026, na het opsplitsen van _route_intern).
#
# Alle detect_*/handle_*/verwerk_*-methoden worden hier vervangen door stubs die
# alleen noteren dat ze aangeroepen zijn en (op verzoek) True teruggeven. Zo test
# dit bestand enkel de sturing: wie komt eerst, wie stopt de routing, welke tekst
# krijgt de volgende stap. De echte detectors hebben hun eigen testbestanden.
#
# Wijzig je bewust de volgorde van _route_intern, pas dan ORDER hieronder aan.
import pytest

from core.intent_router import IntentRouter

# De volgorde bij een gewoon bericht dat nergens door wordt afgehandeld.
ORDER = [
    "_verwerk_pending_antwoord",
    "_check_uitleg_vervolg_bewerking",
    "wikipedia_teacher.verwerk_wiki_keuze",
    "wikipedia_teacher.verwerk_voorstel_antwoord",
    "on_this_day.verwerk_vervolg",
    "concept_overview.verwerk_overview_antwoord",
    "verwerk_preference_woord_antwoord",
    "verwerk_memory_query_woord_antwoord",
    "verwerk_referentie_antwoord",
    "_verwerk_pending_sense_voorkeur",
    "detect_reboot",
    "detect_handler_fouten",
    "handle_teach",
    "handle_example",
    "handle_weerleg",
    "handle_sense_voorkeur",
    "handle_preference",
    "detect_help",
    "detect_uitleg",
    "_normaliseer_omhulsel",
    "_verwerk_referentie",
    "_verwerk_en_dan",
    "_verwerk_vervolgvraag",
    "detect_hypothese",
    "detect_case_herinnering",
    "detect_causes_check",
    "detect_doel_check",
    "detect_temporal",
    "detect_uncertainty",
    "detect_uncertainty_lijst",
    "detect_uncertainty_keuze",
    "detect_kennis_extractie",
    "detect_kennis_keuze",
    "detect_gelijkenis_zoek",
    "detect_gelijkenis_overloop",
    "detect_gelijkenis_keuze",
    "detect_gelijkenis_ongedaan",
    "detect_graaf",
    "tabel1_a",
    "tabel1_b",
    "detect_memory_query",
    "detect_parts_with_property",
    "detect_definition",
    "semantic._detect_relation",
    "tabel2_a",
    "tabel2_b",
    "_probeer_intent_classifier",
    "fallback",
]

# Stappen die de tekst herschrijven (geen True/False) en de eindstap.
HERSCHRIJVERS = {"_normaliseer_omhulsel", "_verwerk_referentie", "_verwerk_vervolgvraag"}
STOPPERS = [n for n in ORDER if n not in HERSCHRIJVERS and n not in ("fallback", "_probeer_intent_classifier")]

BOOL_METHODEN = [
    "_verwerk_pending_antwoord", "_check_uitleg_vervolg_bewerking",
    "verwerk_preference_woord_antwoord", "verwerk_memory_query_woord_antwoord",
    "verwerk_referentie_antwoord", "_verwerk_pending_sense_voorkeur",
    "detect_reboot", "detect_handler_fouten", "handle_teach", "handle_example",
    "handle_weerleg", "handle_sense_voorkeur", "handle_preference", "detect_help",
    "detect_uitleg", "_verwerk_en_dan", "detect_hypothese", "detect_case_herinnering",
    "detect_causes_check", "detect_doel_check", "detect_temporal", "detect_uncertainty",
    "detect_uncertainty_lijst", "detect_uncertainty_keuze", "detect_kennis_extractie",
    "detect_kennis_keuze", "detect_gelijkenis_zoek", "detect_gelijkenis_overloop",
    "detect_gelijkenis_keuze", "detect_gelijkenis_ongedaan", "detect_graaf",
    "detect_memory_query", "detect_parts_with_property", "detect_definition",
    "_probeer_intent_classifier",
]
MODULES = {
    "wikipedia_teacher": ["verwerk_wiki_keuze", "verwerk_voorstel_antwoord"],
    "on_this_day": ["verwerk_vervolg"],
    "concept_overview": ["verwerk_overview_antwoord"],
}


class NepBus:
    def __init__(self):
        self.gepubliceerd = []
        self.modules = {}

    def publish(self, soort, data=None):
        self.gepubliceerd.append((soort, data))

    def subscribe(self, *args, **kwargs):
        pass


class NepLastContext:
    def __init__(self):
        self.aanroepen = []

    def set_concept(self, concept, antwoord_type=None):
        self.aanroepen.append((concept, antwoord_type))


class NepSemantic:
    def __init__(self, maak):
        self.pending_reactivation = False
        self.pending_definitie_keuze = None
        self._detect_relation = maak("semantic._detect_relation")
        self.handle_definitie_keuze = maak("semantic.handle_definitie_keuze")
        self.handle_reactivation_confirm = maak("semantic.handle_reactivation_confirm")
        self.handle_sense_choice = maak("semantic.handle_sense_choice")
        self.handle_confirm = maak("semantic.handle_confirm")


def bouw_router(trigger=None, **opties):
    """Een router waarvan alle controles stubs zijn. 'trigger' is de naam van de
    enige stub die True teruggeeft."""
    r = object.__new__(IntentRouter)
    r.event_bus = NepBus()
    r.calls = []          # (naam, tekst)
    r.last_context = NepLastContext()
    r.event_bus.modules["last_context"] = r.last_context
    r._topic_al_ge_emit = False
    r._laatste_concept_kandidaat = None
    r._laatste_help_topic = None
    r._laatste_uitleg_naam = None
    r._laatste_definitie_woord = None

    def maak(naam):
        def stub(*args):
            r.calls.append((naam, args[0] if args else None))
            if naam == trigger:
                if opties.get("emit_vlag"):
                    r._topic_al_ge_emit = True
                return True
            return False
        return stub

    for naam in BOOL_METHODEN:
        setattr(r, naam, maak(naam))
    r.fallback = maak("fallback")
    # De herschrijvers plakken een achtervoegsel aan de tekst, zodat zichtbaar is
    # welke tekst de volgende stap krijgt. Met houd_tekst=True blijft de tekst gelijk.
    plak = "" if opties.get("houd_tekst") else None
    r._normaliseer_omhulsel = lambda t: (r.calls.append(("_normaliseer_omhulsel", t)), t + ("|n" if plak is None else ""))[1]
    r._verwerk_referentie = lambda t: (r.calls.append(("_verwerk_referentie", t)), None if opties.get("referentie_none") else t + ("|r" if plak is None else ""))[1]
    r._verwerk_vervolgvraag = lambda t: (r.calls.append(("_verwerk_vervolgvraag", t)), None if opties.get("vervolg_none") else t + ("|v" if plak is None else ""))[1]
    r._intent_tabel_deel1 = [("T1A", maak("tabel1_a")), ("T1B", maak("tabel1_b"))]
    r._intent_tabel_deel2 = [("T2A", maak("tabel2_a")), ("T2B", maak("tabel2_b"))]
    r.event_bus.modules["last_context"] = r.last_context
    for mnaam, methoden in MODULES.items():
        class Module:
            pass
        m = Module()
        for methode in methoden:
            setattr(m, methode, maak(f"{mnaam}.{methode}"))
        r.event_bus.modules[mnaam] = m
    r.semantic = NepSemantic(maak)
    return r


def namen(r):
    return [n for n, _ in r.calls]


def soorten(r):
    return [s for s, _ in r.event_bus.gepubliceerd]


# ------------------------------------------------------------------
# De vaste volgorde
# ------------------------------------------------------------------
def test_gewoon_bericht_loopt_de_hele_volgorde_door():
    r = bouw_router()
    r._route_intern({"text": "hallo daar"})
    assert namen(r) == ORDER


@pytest.mark.parametrize("trigger", STOPPERS)
def test_de_eerste_stap_die_afhandelt_stopt_de_routing(trigger):
    r = bouw_router(trigger)
    r._route_intern({"text": "hallo daar"})
    assert namen(r) == ORDER[:ORDER.index(trigger) + 1]


def test_ruw_bericht_wordt_als_eerste_gepubliceerd():
    r = bouw_router()
    r._route_intern({"text": "  hallo  "})
    assert r.event_bus.gepubliceerd[0] == ("raw_user_message", {"text": "hallo"})


def test_superscripts_en_maalteken_worden_vooraf_omgezet():
    r = bouw_router()
    r._route_intern({"text": "x² × 3"})
    assert r.calls[0] == ("_verwerk_pending_antwoord", "x2 * 3")


@pytest.mark.parametrize("eerder, later", [
    ("_verwerk_pending_antwoord", "detect_reboot"),
    ("verwerk_referentie_antwoord", "detect_reboot"),
    ("detect_reboot", "handle_teach"),
    ("handle_sense_voorkeur", "handle_preference"),
    ("handle_weerleg", "handle_preference"),
    ("detect_help", "detect_definition"),
    ("detect_uitleg", "detect_definition"),
    ("detect_causes_check", "tabel1_a"),
    ("detect_graaf", "tabel1_a"),
    ("detect_parts_with_property", "detect_definition"),
    ("detect_definition", "semantic._detect_relation"),
    ("semantic._detect_relation", "tabel2_a"),
])
def test_belangrijke_voorrangsregels(eerder, later):
    assert ORDER.index(eerder) < ORDER.index(later)


# ------------------------------------------------------------------
# Openstaande vragen van semantic
# ------------------------------------------------------------------
def test_openstaande_sense_reactivatie_vangt_het_antwoord_af():
    r = bouw_router()
    r.semantic.pending_reactivation = True
    r._route_intern({"text": "ja"})
    assert namen(r)[-1] == "semantic.handle_reactivation_confirm"
    assert "detect_reboot" not in namen(r)


def test_openstaande_betekenis_keuze_vangt_het_antwoord_af():
    r = bouw_router("semantic.handle_definitie_keuze")
    r.semantic.pending_definitie_keuze = {"woord": "hart"}
    r._route_intern({"text": "2"})
    assert namen(r)[-1] == "semantic.handle_definitie_keuze"
    assert "detect_reboot" not in namen(r)


def test_betekenis_keuze_die_niet_past_laat_de_routing_doorlopen():
    r = bouw_router()
    r.semantic.pending_definitie_keuze = {"woord": "hart"}
    r._route_intern({"text": "wat is hond"})
    assert "semantic.handle_definitie_keuze" in namen(r)
    assert namen(r)[-1] == "fallback"


def test_zonder_semantic_loopt_alles_gewoon_door():
    r = bouw_router()
    r.semantic = None
    r._route_intern({"text": "hallo daar"})
    assert "semantic._detect_relation" not in namen(r)
    assert namen(r)[-1] == "fallback"


# ------------------------------------------------------------------
# De tekst die wordt herschreven en doorgegeven
# ------------------------------------------------------------------
def test_herschreven_tekst_gaat_naar_de_volgende_stappen():
    r = bouw_router()
    r._route_intern({"text": "hallo"})
    tekst = dict(r.calls)
    assert tekst["_normaliseer_omhulsel"] == "hallo"
    assert tekst["_verwerk_referentie"] == "hallo|n"
    assert tekst["_verwerk_en_dan"] == "hallo|n|r"
    assert tekst["_verwerk_vervolgvraag"] == "hallo|n|r"
    assert tekst["detect_hypothese"] == "hallo|n|r|v"
    assert tekst["detect_definition"] == "hallo|n|r|v"
    assert tekst["_probeer_intent_classifier"] == "hallo|n|r|v"
    assert tekst["fallback"] == "hallo|n|r|v"


def test_commando_s_zien_de_tekst_nog_niet_herschreven():
    r = bouw_router()
    r._route_intern({"text": "hallo"})
    tekst = dict(r.calls)
    assert tekst["detect_reboot"] == "hallo"
    assert tekst["detect_uitleg"] == "hallo"


def test_niet_oplosbare_verwijzing_stopt_de_routing():
    r = bouw_router(referentie_none=True)
    r._route_intern({"text": "wat is dat"})
    assert namen(r)[-1] == "_verwerk_referentie"


def test_en_dan_stopt_de_routing_voor_de_vervolgvraag():
    r = bouw_router("_verwerk_en_dan")
    r._route_intern({"text": "en dan"})
    assert namen(r)[-1] == "_verwerk_en_dan"
    assert "_verwerk_vervolgvraag" not in namen(r)


def test_vervolgvraag_die_none_geeft_stopt_de_routing():
    r = bouw_router(vervolg_none=True)
    r._route_intern({"text": "en een kat"})
    assert namen(r)[-1] == "_verwerk_vervolgvraag"
    assert "detect_hypothese" not in namen(r)


# ------------------------------------------------------------------
# Topics die na een herkenning worden gepubliceerd
# ------------------------------------------------------------------
def test_help_zonder_onderwerp_emit_het_algemene_topic():
    r = bouw_router("detect_help")
    r._route_intern({"text": "help"})
    assert "topic_detected:help" in soorten(r)


def test_help_met_onderwerp_emit_een_eigen_topic():
    r = bouw_router("detect_help")
    r._laatste_help_topic = "math"
    r._route_intern({"text": "help math"})
    assert "topic_detected:help_math" in soorten(r)


def test_uitleg_emit_de_canonieke_functienaam():
    r = bouw_router("detect_uitleg")
    r._laatste_uitleg_naam = "newton"
    r._route_intern({"text": "leg uit newton"})
    assert "topic_detected:uitleg_newton" in soorten(r)


def test_geheugenvraag_en_onderdelen_met_eigenschap_hebben_een_eigen_topic():
    r = bouw_router("detect_memory_query")
    r._route_intern({"text": "x"})
    assert "topic_detected:memory_query" in soorten(r)
    r = bouw_router("detect_parts_with_property")
    r._route_intern({"text": "x"})
    assert "topic_detected:parts_with_property" in soorten(r)


def test_definitievraag_emit_topic_met_woord_en_vult_last_context():
    r = bouw_router("detect_definition")
    r._laatste_definitie_woord = "hond"
    r._route_intern({"text": "wat is hond"})
    assert "topic_detected:definitie_hond" in soorten(r)
    assert r.last_context.aanroepen == [("hond", "definitie_hond")]


def test_definitievraag_zonder_woord_valt_terug_op_het_algemene_topic():
    r = bouw_router("detect_definition")
    r._route_intern({"text": "wat is hond"})
    assert "topic_detected:definitie" in soorten(r)
    assert r.last_context.aanroepen == []


def test_definitie_die_zelf_al_een_topic_emit_wordt_niet_dubbel_geteld():
    r = bouw_router("detect_definition", emit_vlag=True)
    r._laatste_definitie_woord = "fysica"
    r._route_intern({"text": "zijn er nog andere betekenissen"})
    assert not any(s.startswith("topic_detected:definitie") for s in soorten(r))
    assert r._topic_al_ge_emit is False


def test_eerste_tabel_emit_zijn_topic_of_slaat_het_over_bij_eigen_topic():
    r = bouw_router("tabel1_b")
    r._route_intern({"text": "x"})
    assert "topic_detected:T1B" in soorten(r)
    r = bouw_router("tabel1_b", emit_vlag=True)
    r._route_intern({"text": "x"})
    assert not any(s.startswith("topic_detected:T1") for s in soorten(r))
    assert r._topic_al_ge_emit is False


def test_tweede_tabel_geeft_het_concept_door_en_reset_het():
    r = bouw_router("tabel2_a")
    r._laatste_concept_kandidaat = "hond"
    r._route_intern({"text": "x"})
    assert "topic_detected:T2A" in soorten(r)
    assert r.last_context.aanroepen == [("hond", "T2A")]
    assert r._laatste_concept_kandidaat is None


def test_tweede_tabel_met_eigen_topic_reset_ook_het_concept():
    r = bouw_router("tabel2_a", emit_vlag=True)
    r._laatste_concept_kandidaat = "hond"
    r._route_intern({"text": "x"})
    assert not any(s.startswith("topic_detected:T2") for s in soorten(r))
    assert r.last_context.aanroepen == []
    assert r._laatste_concept_kandidaat is None
    assert r._topic_al_ge_emit is False


# ------------------------------------------------------------------
# Wat overblijft als niets het bericht herkende
# ------------------------------------------------------------------
def test_los_nummer_gaat_naar_de_sense_keuze():
    r = bouw_router(houd_tekst=True)
    r._route_intern({"text": "2"})
    assert namen(r)[-1] == "semantic.handle_sense_choice"
    assert "_probeer_intent_classifier" not in namen(r)


@pytest.mark.parametrize("antwoord", ["ja", "nee"])
def test_los_ja_of_nee_gaat_naar_de_bevestiging(antwoord):
    r = bouw_router(houd_tekst=True)
    r._route_intern({"text": antwoord})
    assert namen(r)[-1] == "semantic.handle_confirm"
    assert "_probeer_intent_classifier" not in namen(r)


def test_classifier_krijgt_een_kans_voor_de_fallback():
    r = bouw_router("_probeer_intent_classifier")
    r._route_intern({"text": "hallo daar"})
    assert namen(r)[-1] == "_probeer_intent_classifier"
    assert "fallback" not in namen(r)


def test_zonder_semantic_geeft_een_nummer_geen_fout():
    r = bouw_router(houd_tekst=True)
    r.semantic = None
    r._route_intern({"text": "2"})
    assert "fallback" not in namen(r)