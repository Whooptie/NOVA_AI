# tests/test_kandidaat_suggesties67.py
"""
Punt 67 (5 november 2026): rare kandidaat-suggesties.

Na "onthoud: ik hou van thee" stelde Nova "hoort 'houden' daar ook bij?" voor
(en eerder "wis"). Layer 1 leert van alles wat Kevin typt, dus ook van de
commandowoorden zelf. KandidaatSuggesties filtert nu in twee lagen:

1. Negeerlijst (NEGEER_KANDIDATEN + stopwoorden)
2. Concept-filter: alleen woorden die al een concept zijn

Alles draait met kleine nepobjecten en een tijdelijk "gesuggereerd"-bestand
(tmp_path). Je echte kandidaat_suggesties_gedaan.json en concepts.json
worden nooit aangeraakt.
"""
from pathlib import Path

import pytest

from core.event_bus import EventBus
from modules.preferences.kandidaat_suggesties import KandidaatSuggesties


class NepAssociaties:
    """Doet alsof Layer 1 deze woorden sterk aan 'thee' koppelt."""

    def __init__(self, lijst):
        self.lijst = lijst

    def find_related(self, woord, top_k=5, min_confidence=0.0):
        return self.lijst[:top_k]


class NepProfiel:
    def __init__(self, bekend=()):
        self.bekend = set(bekend)

    def get_preference(self, woord):
        return {"sentiment": "positief"} if woord in self.bekend else None


class NepStore:
    def __init__(self, concepten):
        self.concepten = set(concepten)

    def has_concept(self, woord):
        return woord in self.concepten


class NepSemantic:
    def __init__(self, concepten):
        self.store = NepStore(concepten)


def _maak(tmp_path, associaties, concepten=None, profiel=None):
    bus = EventBus()
    module = KandidaatSuggesties(
        bus,
        kevin_profile=profiel or NepProfiel(),
        word_associations=NepAssociaties(associaties),
        semantic=None if concepten is None else NepSemantic(concepten),
    )
    # Nooit naar je echte bestand schrijven
    module._gesuggereerd_pad = str(tmp_path / "gedaan.json")
    module._al_gesuggereerd = set()
    antwoorden = []
    bus.subscribe("layer4_response", lambda d, *a, **k: antwoorden.append(d.get("text", "")))
    return bus, module, antwoorden


def _voorkeur(bus, woord="thee"):
    bus.publish("preference_learned", {"woord": woord, "actief_sentiment": "positief"})


# ---------------------------------------------------------------
# De twee echte gevallen uit kandidaat_suggesties_gedaan.json
# ---------------------------------------------------------------
def test_houden_wordt_niet_voorgesteld(tmp_path):
    bus, _, antwoorden = _maak(tmp_path, [("houden", 0.9)], concepten={"thee", "houden"})
    _voorkeur(bus)
    assert antwoorden == []


def test_wis_wordt_niet_voorgesteld(tmp_path):
    bus, _, antwoorden = _maak(tmp_path, [("wis", 0.8)], concepten={"thee", "wis"})
    _voorkeur(bus)
    assert antwoorden == []


def test_negeerlijst_werkt_ook_als_het_woord_toevallig_een_concept_is(tmp_path):
    # Laag 1 staat los van laag 2: zelfs een concept "houden" wordt geweigerd.
    bus, module, _ = _maak(tmp_path, [("houden", 0.9)], concepten={"houden"})
    assert module._vind_kandidaat("thee") == (None, None)


# ---------------------------------------------------------------
# Concept-filter
# ---------------------------------------------------------------
def test_bekend_concept_wordt_wel_voorgesteld(tmp_path):
    bus, _, antwoorden = _maak(tmp_path, [("koffie", 0.7)], concepten={"thee", "koffie"})
    _voorkeur(bus)
    assert len(antwoorden) == 1
    assert "koffie" in antwoorden[0]
    assert "onthoud: ik hou van koffie" in antwoorden[0]


def test_onbekend_woord_wordt_niet_voorgesteld(tmp_path):
    bus, _, antwoorden = _maak(tmp_path, [("blorf", 0.7)], concepten={"thee"})
    _voorkeur(bus)
    assert antwoorden == []


def test_volgende_geschikte_kandidaat_wordt_gekozen(tmp_path):
    # Het sterkste woord is rommel, het tweede is een echt concept.
    bus, _, antwoorden = _maak(
        tmp_path,
        [("houden", 0.9), ("wis", 0.8), ("koffie", 0.5)],
        concepten={"thee", "koffie"},
    )
    _voorkeur(bus)
    assert len(antwoorden) == 1
    assert "koffie" in antwoorden[0]


def test_zonder_semantic_staat_het_concept_filter_uit(tmp_path):
    # Werkt als voorheen: onbekende woorden mogen door (maar de negeerlijst blijft).
    bus, module, _ = _maak(tmp_path, [("blorf", 0.7)], concepten=None)
    assert module._vind_kandidaat("thee") == ("blorf", 0.7)
    bus2, module2, _ = _maak(tmp_path, [("houden", 0.9)], concepten=None)
    assert module2._vind_kandidaat("thee") == (None, None)


def test_sense_sleutel_wordt_op_het_kale_woord_getoetst(tmp_path):
    _, module, _ = _maak(tmp_path, [("python#2", 0.7)], concepten={"python"})
    assert module._vind_kandidaat("thee") == ("python#2", 0.7)


def test_kapotte_semantic_blokkeert_veilig(tmp_path):
    class Kapot:
        @property
        def store(self):
            raise RuntimeError("kapot")

    _, module, _ = _maak(tmp_path, [("koffie", 0.7)], concepten={"koffie"})
    module.semantic = Kapot()
    assert module._vind_kandidaat("thee") == (None, None)


# ---------------------------------------------------------------
# Bestaand gedrag blijft werken
# ---------------------------------------------------------------
def test_woord_dat_al_in_profiel_staat_wordt_overgeslagen(tmp_path):
    bus, _, antwoorden = _maak(
        tmp_path, [("koffie", 0.7)], concepten={"thee", "koffie"},
        profiel=NepProfiel(bekend={"koffie"}),
    )
    _voorkeur(bus)
    assert antwoorden == []


def test_zelfde_suggestie_komt_niet_twee_keer(tmp_path):
    bus, _, antwoorden = _maak(tmp_path, [("koffie", 0.7)], concepten={"thee", "koffie"})
    _voorkeur(bus)
    _voorkeur(bus)
    assert len(antwoorden) == 1


def test_neutraal_sentiment_geeft_geen_suggestie(tmp_path):
    bus, _, antwoorden = _maak(tmp_path, [("koffie", 0.7)], concepten={"thee", "koffie"})
    bus.publish("preference_learned", {"woord": "thee", "actief_sentiment": "neutraal_gemengd"})
    assert antwoorden == []


# ---------------------------------------------------------------
# Koppeling in module_loader.py
# ---------------------------------------------------------------
def test_module_loader_prikt_semantic_in():
    bron = (Path(__file__).resolve().parent.parent / "core" / "module_loader.py").read_text(encoding="utf-8")
    assert "kandidaat_module.semantic = sem" in bron