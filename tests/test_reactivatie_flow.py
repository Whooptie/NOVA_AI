# test_reactivatie_flow.py
#
# Pytest-tests voor het volledige Bug #32/#36-mechanisme op
# SemanticConceptsModule-niveau (het "vraag Kevin expliciet"-gedrag
# zelf), en voor de aparte vervolgfix in wikipedia_teacher.py.
#
# test_tombstone.py test bewust ALLEEN SenseEngine rechtstreeks (zie de
# moduledocstring daar) -- de rejected-guard in add_sense() zelf. Dit
# bestand test de LAAG ERBOVEN: SemanticConceptsModule.teach(),
# pending_reactivation, handle_reactivation_confirm() (de chat-vraag/
# antwoord-flow), en wikipedia_teacher.py's _teach_word().
#
# Isolatie: SemanticConceptsModule.__init__() roept altijd
# ConceptStore() aan MET HET STANDAARDPAD (Kevin's echte concepts.json)
# -- dat mag een test nooit aanraken. In plaats van de normale
# constructor te gebruiken, bouwen we de instantie via
# SemanticConceptsModule.__new__(...) (roept __init__ NIET aan) en
# wijzen we alle attributen handmatig toe met een tijdelijke
# ConceptStore op tmp_path. Zelfde soort tijdelijke-pad-isolatie als
# test_tombstone.py, maar dan voor de volledige module i.p.v. de losse
# engines.
#
# Uitvoeren: pytest tests/test_reactivatie_flow.py -v

import pytest

from core.semantic import (
    ConceptStore, SenseEngine, RelationEngine, ReasoningEngine,
    TeachEngine, RelationParser, RelationFlowEngine, SemanticConceptsModule,
)
from modules.knowledge.wikipedia_teacher import WikipediaTeacher, WIKI_CONFIDENCE


class NepEventBus:
    """Minimale nep-EventBus: enkel wat SemanticConceptsModule/
    WikipediaTeacher nodig hebben (publish/subscribe/modules). Vangt
    chat_response-berichten op zodat tests kunnen controleren wat Nova
    zou zeggen, zonder een echte EventBus of chat-laag nodig te hebben."""
    def __init__(self):
        self.gepubliceerde_berichten = []
        self.modules = {}

    def publish(self, event_type, data):
        if event_type == "chat_response":
            self.gepubliceerde_berichten.append(data.get("text", ""))

    def subscribe(self, event_type, handler):
        pass


@pytest.fixture
def semantic_module(tmp_path):
    """
    Bouwt een volledig geïsoleerde SemanticConceptsModule op tmp_path,
    ZONDER ooit de standaard ConceptStore() (Kevin's echte data) aan
    te raken. __new__() roept __init__() niet aan, dus we wijzen alle
    attributen die __init__() normaal zou zetten hier handmatig toe.
    """
    module = SemanticConceptsModule.__new__(SemanticConceptsModule)
    bus = NepEventBus()

    module.event_bus = bus
    module.memory = None
    module.store = ConceptStore(
        concepts_file=str(tmp_path / "concepts.json"),
        log_file=str(tmp_path / "concepts.jsonl"),
    )
    module.sense_engine = SenseEngine(module.store)
    module.relation_engine = RelationEngine(module.store, module.sense_engine)
    module.reasoning_engine = ReasoningEngine(module.store, module.relation_engine)
    module.teach_engine = TeachEngine(module.store, module.sense_engine)
    module.parser = RelationParser()
    module.pending_reactivation = None
    module.flow_engine = RelationFlowEngine(
        module.store, module.sense_engine, module.relation_engine, bus
    )
    return module, bus


@pytest.fixture
def wiki_teacher(semantic_module):
    """
    WikipediaTeacher gebouwd bovenop dezelfde geïsoleerde
    SemanticConceptsModule -- zelfde __new__()-truc, want
    WikipediaTeacher.__init__() doet netwerk-gerelateerde setup die we
    hier niet nodig hebben (we roepen enkel _teach_word() rechtstreeks
    aan, geen echte Wikipedia-API-calls).
    """
    module, bus = semantic_module
    teacher = WikipediaTeacher.__new__(WikipediaTeacher)
    teacher.semantic = module
    teacher.event_bus = bus
    return teacher, module, bus


# ─────────────────────────────────────────────────────────────
# Deel 1: SemanticConceptsModule.teach() + pending_reactivation +
# handle_reactivation_confirm() -- de chat-vraag/antwoord-flow zelf.
# ─────────────────────────────────────────────────────────────

def test_teach_user_herhaling_start_pending_reactivation_met_vraag(semantic_module):
    """
    Kern van Bug #32/#36: als Kevin (source='user') een eerder
    afgewezen sense met exact dezelfde tekst opnieuw aanbiedt, moet
    Nova NIET stilzwijgend heractiveren, maar een expliciete ja/nee-
    vraag stellen en pending_reactivation zetten.
    """
    module, bus = semantic_module

    sense = module.teach("hond", "een soort meubel")
    sense_id = sense["sense_id"]
    module.reject_sense("hond", sense_id)

    bus.gepubliceerde_berichten.clear()
    result = module.teach("hond", "een soort meubel")

    assert isinstance(result, dict) and result.get("blocked") == "rejected"
    assert module.pending_reactivation is not None
    assert module.pending_reactivation["word"] == "hond"
    assert module.pending_reactivation["sense_id"] == sense_id
    assert any(
        "eerder al" in b and "opnieuw bevestigen" in b
        for b in bus.gepubliceerde_berichten
    ), f"Verwachtte een expliciete ja/nee-vraag, kreeg: {bus.gepubliceerde_berichten}"

    # De sense zelf mag nog niet aangepast zijn -- pas na expliciete "ja"
    concept = module.store.get_concept("hond")
    assert concept["senses"][0]["status"] == "rejected"


def test_handle_reactivation_confirm_ja_heractiveert_correct(semantic_module):
    module, bus = semantic_module

    sense = module.teach("kat", "een soort auto")
    sense_id = sense["sense_id"]
    module.reject_sense("kat", sense_id)
    module.teach("kat", "een soort auto")
    assert module.pending_reactivation is not None

    bus.gepubliceerde_berichten.clear()
    module.handle_reactivation_confirm("ja")

    concept = module.store.get_concept("kat")
    sense_na = next(s for s in concept["senses"] if s["sense_id"] == sense_id)
    assert sense_na["status"] == "confirmed", (
        f"Na expliciete 'ja' had status 'confirmed' moeten worden, is '{sense_na['status']}'"
    )
    assert module.pending_reactivation is None, "pending_reactivation had leeggemaakt moeten worden"
    assert any("weer opnieuw" in b for b in bus.gepubliceerde_berichten)


def test_handle_reactivation_confirm_nee_blijft_rejected(semantic_module):
    module, bus = semantic_module

    sense = module.teach("vis", "een blikje bier")
    sense_id = sense["sense_id"]
    module.reject_sense("vis", sense_id)
    module.teach("vis", "een blikje bier")
    assert module.pending_reactivation is not None

    bus.gepubliceerde_berichten.clear()
    module.handle_reactivation_confirm("nee")

    concept = module.store.get_concept("vis")
    sense_na = next(s for s in concept["senses"] if s["sense_id"] == sense_id)
    assert sense_na["status"] == "rejected", (
        f"Na 'nee' had status 'rejected' moeten BLIJVEN, is '{sense_na['status']}'"
    )
    assert module.pending_reactivation is None
    assert any("blijft afgewezen" in b for b in bus.gepubliceerde_berichten)


def test_handle_reactivation_confirm_onduidelijk_antwoord_blijft_pending(semantic_module):
    """Een onduidelijk antwoord (geen 'ja'/'nee'/varianten) mag de
    pending-state niet zomaar wegvegen -- Nova moet opnieuw vragen."""
    module, bus = semantic_module

    sense = module.teach("boom", "iets metaligs")
    module.reject_sense("boom", sense["sense_id"])
    module.teach("boom", "iets metaligs")
    assert module.pending_reactivation is not None

    bus.gepubliceerde_berichten.clear()
    module.handle_reactivation_confirm("misschien wel misschien niet")

    assert module.pending_reactivation is not None, (
        "Een onduidelijk antwoord had de pending-vraag niet mogen wissen."
    )
    assert any("ja" in b.lower() and "nee" in b.lower() for b in bus.gepubliceerde_berichten)


def test_teach_niet_user_bron_meldt_zonder_pending_vraag(semantic_module):
    """
    Een niet-user-bron (bv. 'wikipedia', 'auto', 'auto_extract') mag
    NOOIT een ja/nee-vraag triggeren -- enkel Kevin zelf mag dat.
    In plaats daarvan enkel een neutrale melding, geen pending-state.
    """
    module, bus = semantic_module

    sense = module.teach("stoel", "een muzieknoot", source="user")
    module.reject_sense("stoel", sense["sense_id"])

    bus.gepubliceerde_berichten.clear()
    result = module.teach("stoel", "een muzieknoot", source="auto_extract")

    assert isinstance(result, dict) and result.get("blocked") == "rejected"
    assert module.pending_reactivation is None, (
        "Een niet-user-bron mag NOOIT pending_reactivation zetten."
    )
    assert any("genegeerd" in b for b in bus.gepubliceerde_berichten)

    concept = module.store.get_concept("stoel")
    assert concept["senses"][0]["status"] == "rejected"


def test_teach_normale_dedup_zonder_rejected_blijft_gewoon_werken(semantic_module):
    """Regressiecheck op module-niveau: een NIET-rejected dedup-match
    (bv. Kevin bevestigt een unverified wikipedia-sense) moet gewoon
    normaal werken, geen pending-vraag, geen blocked-signaal."""
    module, bus = semantic_module

    module.sense_engine.add_sense("appel", "een vrucht", source="wikipedia", confidence=0.7)

    bus.gepubliceerde_berichten.clear()
    result = module.teach("appel", "een vrucht")

    assert not (isinstance(result, dict) and result.get("blocked")), (
        f"Had niet geblokkeerd mogen worden (geen rejected sense): {result}"
    )
    assert result["status"] == "confirmed"
    assert module.pending_reactivation is None


# ─────────────────────────────────────────────────────────────
# Deel 2: wikipedia_teacher.py's _teach_word() -- beide guards
# (upgrade-pad + "bestaande wikipedia-sense overschrijven"-pad).
# ─────────────────────────────────────────────────────────────

def test_teach_word_nieuw_woord_gebruikt_source_wikipedia_direct(wiki_teacher):
    """
    Structurele fix-check: _teach_word() moet nu RECHTSTREEKS
    source="wikipedia" gebruiken (geen achteraf-correctie meer nodig).
    """
    teacher, module, bus = wiki_teacher

    bericht = teacher._teach_word(
        "trombone", "een koperen blaasinstrument",
        relations=[], examples=[], voeg_toe=False,
    )
    assert bericht.startswith("Wikipedia: 'trombone'")

    concept = module.store.get_concept("trombone")
    assert concept["senses"][0]["source"] == "wikipedia"
    assert concept["senses"][0]["status"] == "unverified"
    assert concept["senses"][0]["confidence"] == WIKI_CONFIDENCE


def test_teach_word_herhaling_van_rejected_wikipedia_sense_meldt_enkel(wiki_teacher):
    """
    DE VERVOLGBUG die Kevin live ontdekte (8 augustus 2026): de
    'bestaande wikipedia-sense overschrijven'-tak werkte rechtstreeks
    op concepts.json, buiten add_sense() om, en negeerde rejected-
    status volledig. Dit is het exacte scenario: 'gitaar' via wiki
    leren, weerleggen, opnieuw via wiki dezelfde tekst aanbieden.
    """
    teacher, module, bus = wiki_teacher

    teacher._teach_word(
        "gitaar",
        "Een gitaar is een snaarinstrument dat wordt bespeeld met de vingers of met een plectrum.",
        relations=[{"type": "is_a", "target": "snaarinstrument", "confidence": 0.7, "source": "wikipedia"}],
        examples=[], voeg_toe=False,
    )
    concept = module.store.get_concept("gitaar")
    sense_id = concept["senses"][0]["sense_id"]
    module.sense_engine.reject_sense("gitaar", sense_id, reason="test")

    bericht2 = teacher._teach_word(
        "gitaar",
        "Een gitaar is een snaarinstrument dat wordt bespeeld met de vingers of met een plectrum.",
        relations=[{"type": "is_a", "target": "snaarinstrument", "confidence": 0.7, "source": "wikipedia"}],
        examples=[], voeg_toe=False,
    )

    assert "bijgewerkt" not in bericht2, (
        f"BUG NIET GEFIXT: sense werd stilzwijgend bijgewerkt ondanks rejected-status. "
        f"Bericht: {bericht2}"
    )
    assert "eerder al afgewezen" in bericht2, f"Verwachtte een afwijzingsmelding, kreeg: {bericht2}"

    concept_na = module.store.get_concept("gitaar")
    assert concept_na["senses"][0]["status"] == "rejected", (
        f"REGRESSIE: status is '{concept_na['senses'][0]['status']}', had 'rejected' moeten blijven."
    )
    assert len(concept_na["senses"]) == 1, "Er had geen nieuwe, tweede sense aangemaakt mogen worden."


def test_teach_word_update_van_niet_rejected_wikipedia_sense_werkt_nog(wiki_teacher):
    """Regressiecheck: het NORMALE geval (bestaande wikipedia-sense is
    NIET rejected) moet gewoon blijven werken -- de vervolgfix mag dit
    niet per ongeluk ook blokkeren."""
    teacher, module, bus = wiki_teacher

    teacher._teach_word("vioolboog", "eerste versie", relations=[], examples=[], voeg_toe=False)
    bericht2 = teacher._teach_word("vioolboog", "een BIJGEWERKTE definitie", relations=[], examples=[], voeg_toe=False)

    assert "bijgewerkt" in bericht2, f"Had gewoon bijgewerkt moeten worden (geen rejected), kreeg: {bericht2}"
    concept = module.store.get_concept("vioolboog")
    assert concept["senses"][0]["definition"] == "een BIJGEWERKTE definitie"


def test_teach_word_bestaande_user_sense_blijft_geweigerd(wiki_teacher):
    """Regressiecheck op de OUDERE, apart bestaande guard (niet Bug
    #32-gerelateerd): Wikipedia mag een door Kevin getypte sense nog
    steeds nooit overschrijven, ongeacht rejected-status of niet."""
    teacher, module, bus = wiki_teacher

    module.teach("snaar", "een deel van een gitaar", source="user")

    bericht = teacher._teach_word("snaar", "een andere definitie", relations=[], examples=[], voeg_toe=False)

    assert "al van jou" in bericht
    concept = module.store.get_concept("snaar")
    assert concept["senses"][0]["definition"] == "een deel van een gitaar"
    assert concept["senses"][0]["source"] == "user"