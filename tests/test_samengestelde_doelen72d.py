# tests/test_samengestelde_doelen72d.py
"""
Punt 72d (5 november 2026): "is een kat een dier en een zoogdier".

Het doel bestaat uit twee delen. ChatModule.on_relation_check splitst het op
"en", controleert elk deel apart en zegt alleen "Ja" als ALLE delen kloppen.
Een doel dat zelf een bekend concept is ("dier en plant") blijft heel.

Alles draait op een tijdelijke concepts.json (tmp_path); je echte data wordt
nooit aangeraakt.
"""
import pytest

import core.semantic as semantic_mod
from core.event_bus import EventBus
from core.intent_router import IntentRouter
from core.semantic import ConceptStore, SemanticConceptsModule
from modules.chat.chat import ChatModule


@pytest.fixture
def omgeving(tmp_path, monkeypatch):
    echte_klasse = ConceptStore
    concepts = str(tmp_path / "data" / "concepts.json")
    log = str(tmp_path / "logs" / "concepts.jsonl")
    monkeypatch.setattr(semantic_mod, "ConceptStore", lambda: echte_klasse(concepts, log))
    bus = EventBus()
    sem = SemanticConceptsModule(bus)
    for woord in ["kat", "hond", "dier", "zoogdier", "vis", "plant", "dier en plant"]:
        sem.sense_engine.add_sense(woord, f"een {woord}", source="user", confidence=1.0)
    sem.add_relation("kat", "is_a", "zoogdier")
    sem.add_relation("kat", "is_a", "dier")
    sem.add_relation("hond", "is_a", "zoogdier")
    sem.add_relation("zoogdier", "is_a", "dier")
    return bus, sem


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
        uitkomst.append(" ".join(antwoorden))
    return uitkomst


def test_beide_delen_kloppen_geeft_ja(omgeving):
    (antwoord,) = _stel(omgeving, "is een kat een dier en een zoogdier")
    assert "Ja, een kat is een dier en een zoogdier." in antwoord


def test_volgorde_maakt_niet_uit(omgeving):
    (antwoord,) = _stel(omgeving, "is een kat een zoogdier en een dier")
    assert "Ja, een kat is een zoogdier en een dier." in antwoord


def test_een_deel_klopt_niet_geeft_geen_ja(omgeving):
    (antwoord,) = _stel(omgeving, "is een kat een dier en een vis")
    assert not antwoord.startswith("Ja, een kat is een dier en een vis")
    assert "Ja, een kat is een dier" in antwoord      # het ware deel blijft zichtbaar
    assert "vis" in antwoord                           # en het onware deel wordt benoemd


def test_geen_enkel_deel_klopt(omgeving):
    (antwoord,) = _stel(omgeving, "is een kat een vis en een plant")
    assert "Ja, een kat is" not in antwoord


def test_enkel_doel_werkt_als_voorheen(omgeving):
    (antwoord,) = _stel(omgeving, "is een kat een dier")
    assert "Ja" in antwoord and "een kat is een dier" in antwoord


def test_doel_dat_zelf_een_concept_is_blijft_heel(omgeving):
    _, sem = omgeving
    chat = ChatModule(EventBus(), semantic_module=sem)
    assert chat._splits_doel("dier en plant") == ["dier en plant"]


@pytest.mark.parametrize("doel, verwacht", [
    ("dier en een zoogdier", ["dier", "zoogdier"]),
    ("dier en zoogdier", ["dier", "zoogdier"]),
    ("dier en de zoogdier", ["dier", "zoogdier"]),
    ("dier", ["dier"]),
    ("groot dier en zoogdier", ["groot dier en zoogdier"]),   # deel met spatie: niet raden
    ("dier en", ["dier en"]),
])
def test_splits_doel(omgeving, doel, verwacht):
    _, sem = omgeving
    chat = ChatModule(EventBus(), semantic_module=sem)
    assert chat._splits_doel(doel) == verwacht