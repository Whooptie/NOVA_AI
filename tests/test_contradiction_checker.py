# test_contradiction_checker.py
#
# Echte pytest-test voor modules/knowledge/contradiction_checker.py --
# de aanroeper voor semantic.py's find_contradictions(), die periodiek
# (elke 15 min, via main.py's achtergrond_loop()) over de hele
# kennisgraaf loopt en Kevin proactief waarschuwt bij nieuwe conflicten.
#
# GEEN echte semantic.py wordt hier gebruikt -- ContradictionChecker
# roept enkel self.semantic.find_contradictions(woord) en
# self.semantic.store.concepts aan, dus een klein NEP-semantic-object
# met precies die twee dingen is voldoende en houdt de test volledig
# onder controle van het scenario, los van semantic.py's eigen gedrag
# (dat wordt al apart gedekt door test_tombstone.py).
#
# Isolatie: __init__() gebruikt get_project_root(__file__) om
# data/contradiction_state.json te vinden -- een vast, niet-
# injecteerbaar pad. In plaats van dat mechanisme te moeten kennen/
# monkeypatchen, wordt self.state_pad na constructie EXPLICIET
# overschreven naar een pad binnen tmp_path, vóór er iets gelezen of
# geschreven wordt. Zo raakt geen enkele test de echte
# data/contradiction_state.json.
#
# Uitvoeren: pytest tests/test_contradiction_checker.py -v

import json

import pytest

from modules.knowledge.contradiction_checker import ContradictionChecker


class DummyEventBus:
    """Vangt publish()-aanroepen op zodat we kunnen controleren wat
    ContradictionChecker daadwerkelijk zou melden."""
    def __init__(self):
        self.gepubliceerd = []

    def subscribe(self, *args, **kwargs):
        pass

    def publish(self, event_type, data):
        self.gepubliceerd.append((event_type, data))


class NepSemantic:
    """
    Minimale stand-in voor SemanticConceptsModule -- ContradictionChecker
    gebruikt enkel .store.concepts.keys() (om te weten welke woorden te
    checken) en .find_contradictions(woord) (om conflicten per woord op
    te vragen). Met dit nep-object bepaalt de TEST zelf precies welke
    conflicten er "gevonden" worden, i.p.v. een echte concepts.json met
    is_a-relaties te moeten opbouwen -- dat maakt het scenario expliciet
    en leesbaar.
    """
    def __init__(self, conflicten_per_woord: dict):
        # conflicten_per_woord: {"hond": [{"word": "hond", "conflict": [...]}]}
        self._conflicten_per_woord = conflicten_per_woord

        class _Store:
            def __init__(self, woorden):
                self.concepts = {w: {} for w in woorden}

        self.store = _Store(conflicten_per_woord.keys())

    def find_contradictions(self, woord):
        return self._conflicten_per_woord.get(woord, [])


@pytest.fixture
def maak_checker(tmp_path):
    """
    Factory-fixture: geeft een functie terug waarmee elke test zijn
    eigen ContradictionChecker + NepSemantic-scenario kan opbouwen,
    met state_pad al veilig naar tmp_path omgeleid.
    """
    def _maak(conflicten_per_woord: dict):
        bus = DummyEventBus()
        nep_semantic = NepSemantic(conflicten_per_woord)
        checker = ContradictionChecker(bus, nep_semantic)
        # Isolatie: state_pad EXPLICIET overschrijven naar tmp_path,
        # vóór enige check_contradictions()-aanroep -- _laad_state()
        # in __init__() draaide al op het (nog niet bestaande) echte
        # pad en vond dus toch niets, maar _sla_state_op() zou zonder
        # deze regel naar de echte project-map schrijven.
        checker.state_pad = tmp_path / "contradiction_state.json"
        checker._al_gemelde_conflicten = set()  # opnieuw, nu gegarandeerd leeg
        return checker, bus

    return _maak


# ─────────────────────────────────────────────────────────────
# Basis: nieuw conflict wordt gemeld
# ─────────────────────────────────────────────────────────────

def test_nieuw_conflict_wordt_gemeld(maak_checker):
    checker, bus = maak_checker({
        "hond": [{"word": "hond", "conflict": ["dier", "meubel"],
                  "reason": "'hond' kan niet tegelijk dier en meubel zijn"}]
    })

    checker.check_contradictions()

    assert len(bus.gepubliceerd) == 1
    event_type, data = bus.gepubliceerd[0]
    assert event_type == "layer4_response"
    assert "hond" in data["text"]
    assert "weerleg:" in data["text"]


def test_geen_conflicten_publiceert_niets(maak_checker):
    checker, bus = maak_checker({
        "hond": [],
        "kat": [],
    })

    checker.check_contradictions()

    assert bus.gepubliceerd == []


# ─────────────────────────────────────────────────────────────
# Spam-preventie: kernfunctionaliteit van deze module
# ─────────────────────────────────────────────────────────────

def test_zelfde_conflict_wordt_niet_dubbel_gemeld(maak_checker):
    """
    HET KERNGEDRAG: een conflict dat al eens gemeld is, mag niet
    opnieuw gemeld worden bij de volgende check_contradictions()-
    aanroep, zolang het onopgelost blijft -- anders zou Kevin elke
    15 minuten dezelfde melding krijgen (spam).
    """
    checker, bus = maak_checker({
        "hond": [{"word": "hond", "conflict": ["dier", "meubel"], "reason": "x"}]
    })

    checker.check_contradictions()
    assert len(bus.gepubliceerd) == 1

    # Tweede cyclus, EXACT hetzelfde conflict nog steeds aanwezig
    checker.check_contradictions()
    assert len(bus.gepubliceerd) == 1, (
        "Een al-gemeld, nog niet opgelost conflict werd opnieuw "
        "gepubliceerd -- spam-preventie werkt niet."
    )


def test_conflict_sleutel_is_orde_onafhankelijk(maak_checker):
    """
    Dezelfde botsing moet dezelfde sleutel geven ongeacht de volgorde
    van de conflict-lijst (bv. ["dier","meubel"] vs ["meubel","dier"])
    -- anders zou eenzelfde conflict soms toch dubbel gemeld worden
    puur door een andere interne volgorde in is_a-relaties.
    """
    checker, bus = maak_checker({
        "hond": [{"word": "hond", "conflict": ["dier", "meubel"], "reason": "x"}]
    })
    checker.check_contradictions()
    assert len(bus.gepubliceerd) == 1

    # "Nieuwe" cyclus met dezelfde botsing, maar conflict-lijst omgedraaid
    checker._conflicten_per_woord_override = None  # geen effect, enkel leesbaarheid
    checker.semantic._conflicten_per_woord["hond"] = [
        {"word": "hond", "conflict": ["meubel", "dier"], "reason": "x"}
    ]
    checker.check_contradictions()

    assert len(bus.gepubliceerd) == 1, (
        "Dezelfde botsing met omgedraaide conflict-volgorde werd "
        "toch als NIEUW conflict gezien -- de sleutel is niet "
        "orde-onafhankelijk."
    )


def test_opgelost_conflict_verdwijnt_uit_state_en_kan_later_opnieuw_melden(maak_checker):
    """
    Als een conflict niet meer voorkomt bij een volgende check (bv.
    Kevin heeft 'weerleg: hond is_a meubel' gedaan), hoort het uit de
    spam-preventie-state verwijderd te worden. Duikt DIEZELFDE
    combinatie later ooit weer op (bv. een nieuwe foute Wikipedia-
    match), dan moet die weer als NIEUW conflict gemeld worden --
    de state mag niet voor altijd blijven aangroeien.
    """
    checker, bus = maak_checker({
        "hond": [{"word": "hond", "conflict": ["dier", "meubel"], "reason": "x"}]
    })
    checker.check_contradictions()
    assert len(bus.gepubliceerd) == 1

    # Conflict is "opgelost" -- find_contradictions() geeft nu niets meer
    checker.semantic._conflicten_per_woord["hond"] = []
    checker.check_contradictions()
    assert len(bus.gepubliceerd) == 1, "Geen nieuwe melding verwacht (niets nieuws)."
    assert checker._al_gemelde_conflicten == set(), (
        "Het opgeloste conflict had uit de spam-preventie-state "
        "verwijderd moeten worden."
    )

    # Dezelfde botsing duikt later weer op -- hoort weer als NIEUW te tellen
    checker.semantic._conflicten_per_woord["hond"] = [
        {"word": "hond", "conflict": ["dier", "meubel"], "reason": "x"}
    ]
    checker.check_contradictions()
    assert len(bus.gepubliceerd) == 2, (
        "Een eerder opgelost, nu terugkerend conflict had opnieuw "
        "gemeld moeten worden."
    )


def test_state_wordt_weggeschreven_naar_schijf(maak_checker, tmp_path):
    """De spam-preventie-state hoort na een check ook echt op schijf
    te staan, zodat een herstart van Nova de state niet verliest."""
    checker, bus = maak_checker({
        "hond": [{"word": "hond", "conflict": ["dier", "meubel"], "reason": "x"}]
    })
    checker.check_contradictions()

    assert checker.state_pad.exists()
    with open(checker.state_pad, "r", encoding="utf-8") as f:
        opgeslagen = json.load(f)
    assert "hond::dier|meubel" in opgeslagen["al_gemeld"]


def test_state_wordt_herladen_bij_nieuwe_instantie(tmp_path):
    """
    Een NIEUWE ContradictionChecker-instantie die hetzelfde state-pad
    krijgt, hoort de eerder opgeslagen 'al gemeld'-lijst terug te
    lezen -- bevestigt dat de spam-preventie een herstart overleeft.
    """
    state_pad = tmp_path / "contradiction_state.json"
    conflicten = {
        "hond": [{"word": "hond", "conflict": ["dier", "meubel"], "reason": "x"}]
    }

    bus1 = DummyEventBus()
    checker1 = ContradictionChecker(bus1, NepSemantic(conflicten))
    checker1.state_pad = state_pad
    checker1._al_gemelde_conflicten = set()
    checker1.check_contradictions()
    assert len(bus1.gepubliceerd) == 1

    # Nieuwe instantie, ANDER event-bus-object (simuleert een herstart),
    # maar state_pad wijst naar hetzelfde bestand op schijf.
    bus2 = DummyEventBus()
    checker2 = ContradictionChecker(bus2, NepSemantic(conflicten))
    checker2.state_pad = state_pad
    checker2._al_gemelde_conflicten = checker2._laad_state()

    checker2.check_contradictions()
    assert bus2.gepubliceerd == [], (
        "Na herladen van de state had dit conflict als 'al gemeld' "
        "herkend moeten worden, niet opnieuw gepubliceerd."
    )


# ─────────────────────────────────────────────────────────────
# alle_contradicties_nu(): debug-commando-pad, wijzigt state NIET
# ─────────────────────────────────────────────────────────────

def test_alle_contradicties_nu_geeft_alles_terug_ongeacht_gemeld(maak_checker):
    """
    alle_contradicties_nu() is voor het 'contradicties' debug-commando
    -- hoort ALTIJD alle huidige conflicten te tonen, ook al waren ze
    al eerder gemeld via check_contradictions(). Kevin moet nooit
    "niets nieuws" te zien krijgen puur omdat de spam-preventie het
    al meldde.
    """
    checker, bus = maak_checker({
        "hond": [{"word": "hond", "conflict": ["dier", "meubel"], "reason": "x"}]
    })
    checker.check_contradictions()  # meldt het conflict, zet in state

    resultaat = checker.alle_contradicties_nu()
    assert len(resultaat) == 1
    assert resultaat[0]["word"] == "hond"


def test_alle_contradicties_nu_wijzigt_state_niet(maak_checker):
    """alle_contradicties_nu() mag de spam-preventie-state NIET
    aanpassen -- puur lezen, geen bijwerking."""
    checker, bus = maak_checker({
        "hond": [{"word": "hond", "conflict": ["dier", "meubel"], "reason": "x"}]
    })

    state_voor = set(checker._al_gemelde_conflicten)
    checker.alle_contradicties_nu()
    state_na = set(checker._al_gemelde_conflicten)

    assert state_voor == state_na


# ─────────────────────────────────────────────────────────────
# Meerdere conflicten tegelijk: samengevat bericht, geen losse spam
# ─────────────────────────────────────────────────────────────

def test_meerdere_nieuwe_conflicten_geven_1_samengevat_bericht(maak_checker):
    """
    Bij meerdere NIEUWE conflicten tegelijk hoort er ÉÉN samengevat
    bericht gepubliceerd te worden (Kevin's voorkeur), niet één
    losse publicatie per conflict.
    """
    checker, bus = maak_checker({
        "hond": [{"word": "hond", "conflict": ["dier", "meubel"], "reason": "x"}],
        "steen": [{"word": "steen", "conflict": ["levend", "niet-levend"], "reason": "y"}],
    })

    checker.check_contradictions()

    assert len(bus.gepubliceerd) == 1, (
        "Meerdere conflicten hadden in EEN publicatie samengevat "
        "moeten worden, niet als losse berichten."
    )
    tekst = bus.gepubliceerd[0][1]["text"]
    assert "hond" in tekst
    assert "steen" in tekst