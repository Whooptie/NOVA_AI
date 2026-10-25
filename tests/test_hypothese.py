# tests/test_hypothese.py -- Hypothetisch redeneren (idee 4)
import threading
import pytest

from core.semantic import (
    SemanticConceptsModule, ConceptStore, SenseEngine, RelationEngine,
    ReasoningEngine,
)
from modules.knowledge.hypothese import HypotheseModule


class DummyEventBus:
    def __init__(self):
        self.modules = {}
        self.handlers = {}
        self.gepubliceerd = []

    def register_module(self, naam, instance):
        self.modules[naam] = instance

    def subscribe(self, event_type, handler):
        self.handlers.setdefault(event_type, []).append(handler)

    def publish(self, event_type, data=None):
        self.gepubliceerd.append((event_type, data))
        for h in self.handlers.get(event_type, []):
            h(data, event_type)

    def antwoorden(self):
        return [d["text"] for e, d in self.gepubliceerd if e == "chat_response"]


class Klok:
    def __init__(self):
        self.nu = 1000.0

    def __call__(self):
        return self.nu


@pytest.fixture
def omgeving(tmp_path):
    bus = DummyEventBus()
    # SemanticConceptsModule.__init__ laadt de ECHTE concepts.json;
    # daarom bouwen we hem zelf op met een tijdelijk pad (tmp_path).
    sem = SemanticConceptsModule.__new__(SemanticConceptsModule)
    sem.event_bus = bus
    sem.memory = None
    sem.pending_reactivation = None   # de router kijkt hiernaar bij elk bericht
    sem.store = ConceptStore(
        concepts_file=str(tmp_path / "concepts.json"),
        log_file=str(tmp_path / "concepts_log.jsonl"),
    )
    sem.sense_engine = SenseEngine(sem.store)
    sem.relation_engine = RelationEngine(sem.store, sem.sense_engine)
    sem.reasoning_engine = ReasoningEngine(sem.store, sem.relation_engine)
    sem.sense_engine.add_sense("hond", "een huisdier", source="user", confidence=1.0)
    sem.sense_engine.add_sense("dier", "een levend wezen", source="user", confidence=1.0)
    sem.sense_engine.add_sense("meubel", "iets om in te wonen", source="user", confidence=1.0)
    sem.relation_engine.add_relation("hond", "is_a", "dier")
    klok = Klok()
    hyp = HypotheseModule(bus, semantic=sem, klok=klok)
    bus.register_module("hypothese", hyp)
    return bus, sem, hyp, klok


def stel(bus, subject, relation, target):
    bus.publish("intent_hypothese_stel", {"subject": subject, "relation": relation, "target": target})


def test_aanname_wordt_gezien_binnen_beurt(omgeving):
    bus, sem, hyp, klok = omgeving
    stel(bus, "hond", "is_a", "meubel")
    hyp.betreed_beurt()
    assert sem.is_a("hond", "meubel") is True
    hyp.verlaat_beurt()


def test_aanname_onzichtbaar_buiten_beurt(omgeving):
    bus, sem, hyp, klok = omgeving
    stel(bus, "hond", "is_a", "meubel")
    assert sem.is_a("hond", "meubel") is False


def test_aanname_onzichtbaar_voor_andere_thread(omgeving):
    bus, sem, hyp, klok = omgeving
    stel(bus, "hond", "is_a", "meubel")
    hyp.betreed_beurt()
    resultaat = []
    t = threading.Thread(target=lambda: resultaat.append(sem.is_a("hond", "meubel")))
    t.start(); t.join()
    hyp.verlaat_beurt()
    assert resultaat == [False]


def test_store_blijft_onaangeroerd(omgeving):
    bus, sem, hyp, klok = omgeving
    voor = sem.store.get_concept("hond")["senses"][0]["relations"][:]
    stel(bus, "hond", "is_a", "meubel")
    hyp.betreed_beurt(); sem.is_a("hond", "meubel"); sem.find_contradictions("hond"); hyp.verlaat_beurt()
    assert sem.store.get_concept("hond")["senses"][0]["relations"] == voor


def test_wis_aannames(omgeving):
    bus, sem, hyp, klok = omgeving
    stel(bus, "hond", "is_a", "meubel")
    bus.publish("intent_hypothese_wis", {})
    hyp.betreed_beurt()
    assert sem.is_a("hond", "meubel") is False
    hyp.verlaat_beurt()
    assert "gewist" in bus.antwoorden()[-1]


def test_verval_na_tien_minuten(omgeving):
    bus, sem, hyp, klok = omgeving
    stel(bus, "hond", "is_a", "meubel")
    klok.nu += 601
    hyp.betreed_beurt()
    assert sem.is_a("hond", "meubel") is False
    hyp.verlaat_beurt()
    assert hyp.aannames == []


def test_maximaal_vijf(omgeving):
    bus, sem, hyp, klok = omgeving
    for i in range(5):
        stel(bus, "hond", "is_a", f"ding{i}")
    stel(bus, "hond", "is_a", "ding9")
    assert len(hyp.aannames) == 5
    assert "maximaal 5" in bus.antwoorden()[-1]


def test_onbekend_onderwerp_geweigerd(omgeving):
    bus, sem, hyp, klok = omgeving
    stel(bus, "xyzzy", "is_a", "meubel")
    assert hyp.aannames == []
    assert "ken 'xyzzy' nog niet" in bus.antwoorden()[-1]


def test_al_waar_en_dubbel(omgeving):
    bus, sem, hyp, klok = omgeving
    stel(bus, "hond", "is_a", "dier")
    assert hyp.aannames == []
    stel(bus, "hond", "is_a", "meubel")
    stel(bus, "hond", "is_a", "meubel")
    assert len(hyp.aannames) == 1
    assert "al" in bus.antwoorden()[-1]


def test_cirkel_geweigerd(omgeving):
    bus, sem, hyp, klok = omgeving
    stel(bus, "hond", "is_a", "hond")
    assert hyp.aannames == []


def test_gevolg_meldt_tegenstrijdigheid_en_voorouders(omgeving):
    bus, sem, hyp, klok = omgeving
    stel(bus, "hond", "is_a", "meubel")
    bus.publish("intent_hypothese_gevolg", {})
    tekst = bus.antwoorden()[-1]
    assert "meubel" in tekst and "botst" in tekst


def test_gevolg_via_keten(omgeving):
    bus, sem, hyp, klok = omgeving
    sem.sense_engine.add_sense("ding", "iets", source="user", confidence=1.0)
    sem.relation_engine.add_relation("meubel", "is_a", "ding") if sem.store.has_concept("meubel") else None
    stel(bus, "hond", "is_a", "meubel")
    bus.publish("intent_hypothese_gevolg", {})
    assert "ding" in bus.antwoorden()[-1]


def test_causes_aanname_en_gevolgen(omgeving):
    bus, sem, hyp, klok = omgeving
    sem.sense_engine.add_sense("regen", "water uit lucht", source="user", confidence=1.0)
    sem.sense_engine.add_sense("modder", "natte aarde", source="user", confidence=1.0)
    stel(bus, "regen", "causes", "modder")
    hyp.betreed_beurt()
    assert sem.get_all_effects("regen")[0]["woord"] == "modder"
    hyp.verlaat_beurt()
    assert sem.get_all_effects("regen") == []


def test_notice_na_gebruik(omgeving):
    bus, sem, hyp, klok = omgeving
    stel(bus, "hond", "is_a", "meubel")
    aantal = len(bus.antwoorden())
    hyp.betreed_beurt()
    sem.is_a("hond", "meubel")
    hyp.verlaat_beurt()
    nieuw = bus.antwoorden()[aantal:]
    assert len(nieuw) == 1 and "tijdelijke aanname" in nieuw[0]


def test_geen_notice_zonder_gebruik(omgeving):
    bus, sem, hyp, klok = omgeving
    stel(bus, "hond", "is_a", "meubel")
    aantal = len(bus.antwoorden())
    hyp.betreed_beurt()
    sem.is_a("dier", "meubel")   # een woord waar GEEN aanname over gaat
    hyp.verlaat_beurt()
    assert bus.antwoorden()[aantal:] == []


def test_toon(omgeving):
    bus, sem, hyp, klok = omgeving
    bus.publish("intent_hypothese_toon", {})
    assert "niets" in bus.antwoorden()[-1]
    stel(bus, "hond", "is_a", "meubel")
    bus.publish("intent_hypothese_toon", {})
    assert "hond is een meubel" in bus.antwoorden()[-1]


# ---------------- router-detectie ----------------
@pytest.fixture
def router(omgeving):
    from core.intent_router import IntentRouter
    bus, sem, hyp, klok = omgeving
    r = IntentRouter(bus, semantic_module=sem)
    return r, bus, sem, hyp


@pytest.mark.parametrize("zin,rel,bron,doel", [
    ("stel dat een hond een meubel is", "is_a", "hond", "meubel"),
    ("Stel dat een hond een meubel is?", "is_a", "hond", "meubel"),
    ("veronderstel dat de hond een meubel is", "is_a", "hond", "meubel"),
    ("neem aan dat een wiel een onderdeel van een boom is", "part_of", "wiel", "boom"),
    ("stel dat een wiel deel van een auto is", "part_of", "wiel", "auto"),
    ("stel dat regen droogte veroorzaakt", "causes", "regen", "droogte"),
    ("stel dat regen tot droogte leidt", "causes", "regen", "droogte"),
])
def test_detect_stel(router, zin, rel, bron, doel):
    r, bus, sem, hyp = router
    assert r.detect_hypothese(zin) is True
    e, d = [x for x in bus.gepubliceerd if x[0] == "intent_hypothese_stel"][-1]
    assert d == {"subject": bron, "relation": rel, "target": doel}


@pytest.mark.parametrize("zin", [
    "stel dat het mooi weer is",
    "hallo nova",
    "is een hond een meubel",
    "wat betekent dat dan",   # zonder aannames niet claimen
])
def test_detect_negatief(router, zin):
    r, bus, sem, hyp = router
    assert r.detect_hypothese(zin) is False


def test_detect_zonder_module_is_false(omgeving):
    from core.intent_router import IntentRouter
    bus, sem, hyp, klok = omgeving
    del bus.modules["hypothese"]
    assert IntentRouter(bus, semantic_module=sem).detect_hypothese("stel dat een hond een meubel is") is False


def test_detect_gevolg_wis_toon(router):
    r, bus, sem, hyp = router
    r.detect_hypothese("stel dat een hond een meubel is")
    assert r.detect_hypothese("wat zou dat betekenen?") is True
    assert r.detect_hypothese("welke aannames heb ik") is True
    assert r.detect_hypothese("wis de aannames") is True
    assert hyp.aannames == []


def test_route_volledig(router):
    r, bus, sem, hyp = router
    r.route({"text": "stel dat een hond een meubel is"})
    assert hyp.aannames and hyp.aannames[0]["target"] == "meubel"
    assert hyp._diepte() == 0
    r.route({"text": "wis de aannames"})
    assert hyp.aannames == []


def test_route_gevolgvraag_en_toon(router):
    r, bus, sem, hyp = router
    r.route({"text": "stel dat een hond een meubel is"})
    r.route({"text": "wat zou dat betekenen"})
    assert "botst" in bus.antwoorden()[-1]
    r.route({"text": "welke aannames heb ik"})
    assert "hond is een meubel" in bus.antwoorden()[-1]


def test_route_stel_schrijft_niets_naar_schijf(router, tmp_path):
    r, bus, sem, hyp = router
    voor = (tmp_path / "concepts.json").read_text() if (tmp_path / "concepts.json").exists() else ""
    r.route({"text": "stel dat een hond een meubel is"})
    na = (tmp_path / "concepts.json").read_text() if (tmp_path / "concepts.json").exists() else ""
    assert voor == na