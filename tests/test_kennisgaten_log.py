# tests/test_kennisgaten_log.py
"""Tests voor het kennisgaten-logboek (punt 72a, 4 november 2026)."""
import json
import sys
from pathlib import Path

import pytest

from core.event_bus import EventBus
from modules.knowledge.kennisgaten_log import KennisgatenLog, herken_kennisgat, init_module

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import kennisgaten_overzicht as overzicht_tool  # noqa: E402


@pytest.mark.parametrize("antwoord, verwacht", [
    ("Ik ken geen synoniemen van 'snel'.", ("synoniemen", "snel")),
    ("Ik ken geen tegendeel van 'groot'.", ("tegendeel", "groot")),
    ("Ik ken geen oorzaken van 'modder'.", ("oorzaken", "modder")),
    ("Ik ken geen gevolgen van 'tak breekt'!", ("gevolgen", "tak breekt")),
    ("Ik ken geen eigenschappen van 'klok'.", ("eigenschappen", "klok")),
    ("Ik ken 'glorbix' niet.", ("woord", "glorbix")),
    ("Ik ken 'glorbix' nog niet. Leer het me met: teach glorbix <betekenis>", ("woord", "glorbix")),
    ("Ik ken de relatie 'hond is_a kat' niet.", ("relatie", "hond is_a kat")),
    ("Ik kon 'zwabbel' niet vinden op Wikipedia.", ("wikipedia", "zwabbel")),
    # na de toon-laag staat er extra tekst omheen
    ("Hmm… Ik ken geen oorzaken van 'mist'! *kleine glimlach* 🙂", ("oorzaken", "mist")),
    ("IK KEN GEEN OORZAKEN VAN 'MIST'", ("oorzaken", "MIST")),
])
def test_herken_kennisgat(antwoord, verwacht):
    assert herken_kennisgat(antwoord) == verwacht


@pytest.mark.parametrize("antwoord", [
    "Oorzaken van 'modder': regen.",
    "Wat ik weet over 'hond': een dier.",
    "Hmm… dat ken ik niet. Je zei: 'abc'",
    "",
    None,
    123,
])
def test_geen_kennisgat(antwoord):
    assert herken_kennisgat(antwoord) is None


def _lees(pad):
    return [json.loads(r) for r in Path(pad).read_text(encoding="utf-8").splitlines() if r.strip()]


@pytest.fixture
def opstelling(tmp_path):
    bus = EventBus()
    log = KennisgatenLog(bus, data_dir=tmp_path)
    return bus, log, tmp_path / "kennisgaten.jsonl"


def test_logt_vraag_en_gat(opstelling):
    bus, _, pad = opstelling
    bus.publish("raw_user_message", {"text": "wat veroorzaakt modder"})
    bus.publish("layer4_response", {"text": "Ik ken geen oorzaken van 'modder'."})
    regels = _lees(pad)
    assert len(regels) == 1
    assert regels[0]["vraag"] == "wat veroorzaakt modder"
    assert regels[0]["soort"] == "oorzaken"
    assert regels[0]["woord"] == "modder"
    assert regels[0]["tijd"]


def test_zelfde_antwoord_via_twee_events_is_een_regel(opstelling):
    bus, _, pad = opstelling
    bus.publish("raw_user_message", {"text": "wat veroorzaakt modder"})
    bus.publish("layer4_response", {"text": "Ik ken geen oorzaken van 'modder'."})
    bus.publish("chat_response", {"text": "Ik ken geen oorzaken van 'modder'! *kleine glimlach*"})
    assert len(_lees(pad)) == 1


def test_nieuw_bericht_nieuwe_regel(opstelling):
    bus, _, pad = opstelling
    for vraag, woord in [("wat veroorzaakt modder", "modder"), ("wat veroorzaakt mist", "mist")]:
        bus.publish("raw_user_message", {"text": vraag})
        bus.publish("chat_response", {"text": f"Ik ken geen oorzaken van '{woord}'."})
    assert [r["woord"] for r in _lees(pad)] == ["modder", "mist"]


def test_gewoon_antwoord_wordt_niet_gelogd(opstelling):
    bus, _, pad = opstelling
    bus.publish("raw_user_message", {"text": "wat is een hond"})
    bus.publish("layer4_response", {"text": "Wat ik weet over 'hond': een dier."})
    assert not pad.exists()


def test_zonder_bericht_van_kevin_geen_log(opstelling):
    """Antwoorden die niet op een bericht van Kevin volgen (bv. proactief) tellen niet."""
    bus, _, pad = opstelling
    bus.publish("chat_response", {"text": "Ik ken geen oorzaken van 'modder'."})
    assert not pad.exists()


def test_fout_bij_schrijven_wordt_ingeslikt(tmp_path):
    bus = EventBus()
    # data_dir is een BESTAND: aanmaken van de map en schrijven mislukken
    bestand = tmp_path / "geen_map"
    bestand.write_text("x", encoding="utf-8")
    KennisgatenLog(bus, data_dir=bestand)
    bus.publish("raw_user_message", {"text": "wat veroorzaakt modder"})
    bus.publish("chat_response", {"text": "Ik ken geen oorzaken van 'modder'."})  # mag niet crashen


def test_kapotte_data_is_geen_probleem(opstelling):
    bus, log, pad = opstelling
    log.on_raw_user_message(None)
    log.on_antwoord(None)
    log.on_antwoord({"text": None})


def test_init_module_patroon_van_module_loader(tmp_path):
    """module_loader.py roept init_module(event_bus, sem) aan."""
    bus = EventBus()
    instance = init_module(bus, object())
    assert isinstance(instance, KennisgatenLog)


def test_door_de_echte_router_en_chat(tmp_path):
    from core.semantic import SemanticConceptsModule
    from modules.chat.chat import ChatModule
    from core.intent_router import IntentRouter

    bus = EventBus()
    KennisgatenLog(bus, data_dir=tmp_path)
    sem = SemanticConceptsModule(bus)
    bus.modules = getattr(bus, "modules", {})
    bus.modules["semantic"] = sem
    ChatModule(bus, semantic_module=sem)
    router = IntentRouter(bus, semantic_module=sem)
    router.route({"text": "waardoor breekt een tak"}, "chat_message")
    router.route({"text": "wat is een ander woord voor glorbix"}, "chat_message")
    regels = _lees(tmp_path / "kennisgaten.jsonl")
    assert any(r["soort"] == "oorzaken" and r["woord"] == "tak breekt" for r in regels)
    assert regels[0]["vraag"] == "waardoor breekt een tak"


# ---------------------------------------------------------------- overzichtsscript
def test_overzicht_telt_per_soort(tmp_path, capsys):
    pad = tmp_path / "k.jsonl"
    rijen = [
        {"soort": "oorzaken", "woord": "modder"},
        {"soort": "oorzaken", "woord": "modder"},
        {"soort": "oorzaken", "woord": "mist"},
        {"soort": "synoniemen", "woord": "snel"},
    ]
    pad.write_text("\n".join(json.dumps(r) for r in rijen) + "\nkapotte regel\n", encoding="utf-8")
    assert overzicht_tool.main(["--pad", str(pad)]) == 0
    uit = capsys.readouterr().out
    assert "4 kennisgaten in totaal" in uit
    assert "2x  modder" in uit
    assert uit.index("== oorzaken (3) ==") < uit.index("== synoniemen (1) ==")


def test_overzicht_filtert_op_soort(tmp_path, capsys):
    pad = tmp_path / "k.jsonl"
    pad.write_text(json.dumps({"soort": "oorzaken", "woord": "modder"}) + "\n", encoding="utf-8")
    overzicht_tool.main(["gevolgen", "--pad", str(pad)])
    assert "Geen kennisgaten van het soort 'gevolgen'" in capsys.readouterr().out


def test_overzicht_zonder_bestand(tmp_path, capsys):
    overzicht_tool.main(["--pad", str(tmp_path / "bestaat_niet.jsonl")])
    assert "Nog geen kennisgaten gelogd" in capsys.readouterr().out