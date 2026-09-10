# tests/test_find_bridge.py
"""
Tests voor WordAssociationsLearner.find_bridge() (Layer 1, "Advanced queries").

find_bridge() zoekt brugwoorden tussen twee woorden: woorden die met
BEIDE geassocieerd zijn. De score per brugwoord is het gemiddelde van
beide losse associatiesterktes.

We testen hier puur de query-laag: self.associations wordt handmatig
klaargezet (geen learn_from()/PMI-berekening nodig, dat zit al in
andere testbestanden). Isolatie via tmp_path, zodat de echte
data/word_associations.json nooit aangeraakt wordt.
"""

import pytest

from modules.learning.word_associations_learner import WordAssociationsLearner


@pytest.fixture
def learner(tmp_path):
    """
    Maakt een WordAssociationsLearner die met een tijdelijk save_path
    werkt, zodat er geen echte data/word_associations.json geraakt of
    overschreven wordt. Geen event_bus nodig voor deze query-tests.
    """
    save_path = tmp_path / "word_associations.json"
    instance = WordAssociationsLearner(event_bus=None, save_path=save_path)
    return instance


def _zet_associatie(learner, word1, word2, pmi):
    """
    Kleine helper om self.associations rechtstreeks te vullen, zonder
    via learn_from()/calculate_pmi() te moeten gaan. We zetten de
    associatie in BEIDE richtingen, zoals de echte co-occurrence-
    logica dat ook altijd doet (symmetrisch).
    """
    learner.associations.setdefault(word1, {})[word2] = {"pmi": pmi}
    learner.associations.setdefault(word2, {})[word1] = {"pmi": pmi}


class TestFindBridgeBasis:
    def test_vindt_een_gedeeld_brugwoord(self, learner):
        # "python" en "kunst" delen allebei een link met "elegant"
        _zet_associatie(learner, "python", "elegant", 0.60)
        _zet_associatie(learner, "kunst", "elegant", 0.40)

        resultaat = learner.find_bridge("python", "kunst")

        assert resultaat == [("elegant", 0.50)]  # gemiddelde van 0.60 en 0.40

    def test_geen_gedeelde_associaties_geeft_lege_lijst(self, learner):
        _zet_associatie(learner, "python", "snel", 0.70)
        _zet_associatie(learner, "kunst", "creatief", 0.65)

        resultaat = learner.find_bridge("python", "kunst")

        assert resultaat == []

    def test_onbekend_woord_geeft_lege_lijst(self, learner):
        _zet_associatie(learner, "python", "snel", 0.70)

        # "kunst" komt nergens voor in self.associations
        resultaat = learner.find_bridge("python", "kunst")

        assert resultaat == []

    def test_beide_woorden_onbekend_geeft_lege_lijst(self, learner):
        resultaat = learner.find_bridge("python", "kunst")

        assert resultaat == []


class TestFindBridgeSortering:
    def test_meerdere_bruggen_gesorteerd_sterkste_eerst(self, learner):
        # Twee gedeelde brugwoorden, met verschillende gemiddelde sterkte
        _zet_associatie(learner, "python", "elegant", 0.90)
        _zet_associatie(learner, "kunst", "elegant", 0.80)  # gem. 0.85

        _zet_associatie(learner, "python", "creatief", 0.30)
        _zet_associatie(learner, "kunst", "creatief", 0.20)  # gem. 0.25

        resultaat = learner.find_bridge("python", "kunst")

        # Woorden en volgorde exact controleren...
        woorden = [w for w, _ in resultaat]
        assert woorden == ["elegant", "creatief"]

        # ...scores met een kleine tolerantie, want (0.90 + 0.80) / 2
        # levert door floating-point afronding net geen exacte 0.85 op
        # (0.8500000000000001).
        scores = [s for _, s in resultaat]
        assert scores == pytest.approx([0.85, 0.25])

    def test_top_k_beperkt_het_aantal_resultaten(self, learner):
        # Drie gedeelde brugwoorden, maar top_k=2 vragen
        _zet_associatie(learner, "python", "a", 0.90)
        _zet_associatie(learner, "kunst", "a", 0.90)  # gem. 0.90

        _zet_associatie(learner, "python", "b", 0.70)
        _zet_associatie(learner, "kunst", "b", 0.70)  # gem. 0.70

        _zet_associatie(learner, "python", "c", 0.50)
        _zet_associatie(learner, "kunst", "c", 0.50)  # gem. 0.50

        resultaat = learner.find_bridge("python", "kunst", top_k=2)

        assert resultaat == [("a", 0.90), ("b", 0.70)]
        assert len(resultaat) == 2


class TestFindBridgeMinConfidence:
    def test_min_confidence_filtert_zwakke_associaties_weg(self, learner):
        # "zwak" ligt onder de min_confidence-drempel bij python -> valt weg
        _zet_associatie(learner, "python", "elegant", 0.60)
        _zet_associatie(learner, "kunst", "elegant", 0.60)

        _zet_associatie(learner, "python", "zwak", 0.10)
        _zet_associatie(learner, "kunst", "zwak", 0.60)

        resultaat = learner.find_bridge("python", "kunst", min_confidence=0.5)

        # "zwak" heeft bij python maar 0.10 pmi -> valt buiten get_associations()
        # dus komt niet meer voor in de gedeelde-associaties-doorsnede
        assert resultaat == [("elegant", 0.60)]


class TestFindBridgeSymmetrie:
    def test_volgorde_van_de_twee_ingevoerde_woorden_maakt_niet_uit(self, learner):
        _zet_associatie(learner, "python", "elegant", 0.60)
        _zet_associatie(learner, "kunst", "elegant", 0.40)

        resultaat_a = learner.find_bridge("python", "kunst")
        resultaat_b = learner.find_bridge("kunst", "python")

        assert resultaat_a == resultaat_b