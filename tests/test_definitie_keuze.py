# tests/test_definitie_keuze.py
"""
Tests voor de betekenis-keuze bij meerduidige woorden (30 oktober 2026):
"wat is een bank" -> Nova vraagt welke betekenis je bedoelt.

Alles draait op een tijdelijke concepts.json (tmp_path); je echte data
wordt nooit aangeraakt.
"""
import pytest

import core.semantic as semantic_mod
from core.semantic import ConceptStore, SemanticConceptsModule
from core.intent_router import IntentRouter

GELD = "een financieel instituut waar je geld kunt bewaren"
MEUBEL = "een zitmeubel voor meerdere personen"


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


class NepKevinProfile:
    def __init__(self, voorkeur):
        self.voorkeur = voorkeur

    def get_sense_voorkeur(self, woord):
        return self.voorkeur


@pytest.fixture
def omgeving(tmp_path, monkeypatch):
    echte_klasse = ConceptStore
    concepts = str(tmp_path / "data" / "concepts.json")
    log = str(tmp_path / "logs" / "concepts.jsonl")
    monkeypatch.setattr(
        semantic_mod, "ConceptStore", lambda: echte_klasse(concepts, log)
    )
    bus = NepBus()
    sem = SemanticConceptsModule(bus)
    bus.leeg()
    return sem, bus


def _voeg_toe(sem, woord, definitie, confidence=1.0, signaal=None):
    sense = sem.sense_engine.add_sense(
        woord, definitie, source="user", confidence=confidence
    )
    if signaal:
        for s in sem.store.get_concept(woord)["senses"]:
            if s.get("sense_id") == sense["sense_id"]:
                s["signaalwoorden"] = signaal
    return sense


def _maak_bank(sem):
    _voeg_toe(sem, "bank", GELD, confidence=1.0)
    _voeg_toe(sem, "bank", MEUBEL, confidence=0.5)


# ---------------------------------------------------------
# get_betekenis_keuzes()
# ---------------------------------------------------------
def test_woord_met_een_betekenis_geeft_geen_keuze(omgeving):
    sem, _ = omgeving
    _voeg_toe(sem, "hond", "een huisdier")
    assert sem.get_betekenis_keuzes("hond", ["wat", "is", "een", "hond"]) is None


def test_onbekend_woord_geeft_geen_keuze(omgeving):
    sem, _ = omgeving
    assert sem.get_betekenis_keuzes("flurbo", ["wat", "is", "een", "flurbo"]) is None


def test_meerduidig_woord_geeft_keuzes_beste_eerst(omgeving):
    sem, _ = omgeving
    _voeg_toe(sem, "bank", MEUBEL, confidence=0.5)
    _voeg_toe(sem, "bank", GELD, confidence=1.0)
    woord, senses = sem.get_betekenis_keuzes("bank", ["wat", "is", "een", "bank"])
    assert woord == "bank"
    assert [s["definition"] for s in senses] == [GELD, MEUBEL]


def test_signaalwoord_in_zin_voorkomt_de_vraag(omgeving):
    sem, _ = omgeving
    _voeg_toe(sem, "python", "een programmeertaal", confidence=1.0)
    _voeg_toe(sem, "python", "een grote slang", confidence=0.5,
              signaal=["slang", "dier"])
    assert sem.get_betekenis_keuzes("python", ["wat", "is", "python", "slang"]) is None
    assert sem.get_betekenis_keuzes("python", ["wat", "is", "python"]) is not None


def test_afgewezen_sense_telt_niet_mee(omgeving):
    sem, _ = omgeving
    _voeg_toe(sem, "bank", GELD, confidence=1.0)
    tweede = _voeg_toe(sem, "bank", MEUBEL, confidence=0.5)
    sem.reject_sense("bank", tweede["sense_id"], "test")
    assert sem.get_betekenis_keuzes("bank", ["wat", "is", "een", "bank"]) is None


def test_ingestelde_voorkeur_voorkomt_de_vraag(omgeving):
    sem, bus = omgeving
    _voeg_toe(sem, "bank", GELD, confidence=1.0)
    tweede = _voeg_toe(sem, "bank", MEUBEL, confidence=0.5)
    bus.modules["kevin_profile"] = NepKevinProfile(tweede["sense_id"])
    assert sem.get_betekenis_keuzes("bank", ["wat", "is", "een", "bank"]) is None


# ---------------------------------------------------------
# start_definitie_keuze() en handle_definitie_keuze()
# ---------------------------------------------------------
def test_start_stelt_vraag_en_onthoudt(omgeving):
    sem, bus = omgeving
    _maak_bank(sem)
    assert sem.start_definitie_keuze("bank", ["wat", "is", "een", "bank"]) is True
    assert sem.pending_definitie_keuze is not None
    tekst = bus.events("chat_response")[0]["text"]
    assert "welke bedoel je" in tekst
    assert f"1. {GELD}" in tekst
    assert f"2. {MEUBEL}" in tekst


def test_start_zonder_keuze_stelt_geen_vraag(omgeving):
    sem, bus = omgeving
    _voeg_toe(sem, "hond", "een huisdier")
    assert sem.start_definitie_keuze("hond", ["wat", "is", "een", "hond"]) is False
    assert sem.pending_definitie_keuze is None
    assert bus.events("chat_response") == []


def test_antwoord_met_nummer_geeft_gekozen_betekenis(omgeving):
    sem, bus = omgeving
    _maak_bank(sem)
    sem.start_definitie_keuze("bank", ["bank"])
    bus.leeg()
    assert sem.handle_definitie_keuze("2") is True
    assert bus.events("layer4_response") == [{"text": f"bank betekent: {MEUBEL}"}]
    assert sem.pending_definitie_keuze is None


def test_antwoord_met_ordinaal(omgeving):
    sem, bus = omgeving
    _maak_bank(sem)
    sem.start_definitie_keuze("bank", ["bank"])
    bus.leeg()
    assert sem.handle_definitie_keuze("de eerste") is True
    assert bus.events("layer4_response") == [{"text": f"bank betekent: {GELD}"}]


def test_ongeldig_nummer_laat_vraag_open(omgeving):
    sem, bus = omgeving
    _maak_bank(sem)
    sem.start_definitie_keuze("bank", ["bank"])
    bus.leeg()
    assert sem.handle_definitie_keuze("9") is True
    assert sem.pending_definitie_keuze is not None
    assert "tussen 1 en 2" in bus.events("chat_response")[0]["text"]


def test_ander_bericht_laat_vraag_vervallen(omgeving):
    sem, bus = omgeving
    _maak_bank(sem)
    sem.start_definitie_keuze("bank", ["bank"])
    assert sem.handle_definitie_keuze("hallo nova") is False
    assert sem.pending_definitie_keuze is None


def test_zonder_wachtende_vraag_doet_handle_niets(omgeving):
    sem, bus = omgeving
    assert sem.handle_definitie_keuze("2") is False
    assert bus.events("layer4_response") == []


# ---------------------------------------------------------
# Router + ChatModule samen
# ---------------------------------------------------------
def test_router_meerduidig_woord_stuurt_keuze_aanduiding(omgeving):
    sem, bus = omgeving
    _maak_bank(sem)
    router = IntentRouter(bus, sem)
    bus.leeg()
    router.route({"text": "wat is een bank"})
    events = bus.events("intent_definition")
    assert len(events) == 1
    assert events[0]["word"] == "bank"
    assert events[0]["betekenis_keuze"] is True
    assert bus.events("layer4_response") == []


def test_router_eenduidig_woord_krijgt_geen_keuze_aanduiding(omgeving):
    sem, bus = omgeving
    _voeg_toe(sem, "hond", "een huisdier")
    router = IntentRouter(bus, sem)
    bus.leeg()
    router.route({"text": "wat is een hond"})
    events = bus.events("intent_definition")
    assert len(events) == 1
    assert "betekenis_keuze" not in events[0]


def test_volledig_gesprek_vraag_en_antwoord(omgeving):
    chat_mod = pytest.importorskip("modules.chat.chat")
    sem, bus = omgeving
    _maak_bank(sem)
    router = IntentRouter(bus, sem)
    chat = chat_mod.ChatModule(bus, sem)
    bus.leeg()

    router.route({"text": "wat is een bank"})
    chat.on_definition(bus.events("intent_definition")[0])
    vraag = bus.events("chat_response")[0]["text"]
    assert "welke bedoel je" in vraag
    assert sem.pending_definitie_keuze is not None

    bus.leeg()
    router.route({"text": "2"})
    assert bus.events("layer4_response") == [{"text": f"bank betekent: {MEUBEL}"}]
    assert sem.pending_definitie_keuze is None


def test_ander_bericht_na_vraag_wordt_gewoon_verwerkt(omgeving):
    chat_mod = pytest.importorskip("modules.chat.chat")
    sem, bus = omgeving
    _maak_bank(sem)
    router = IntentRouter(bus, sem)
    chat = chat_mod.ChatModule(bus, sem)
    router.route({"text": "wat is een bank"})
    chat.on_definition(bus.events("intent_definition")[0])
    bus.leeg()

    router.route({"text": "hallo nova"})
    assert sem.pending_definitie_keuze is None
    assert len(bus.events("intent_greeting")) == 1