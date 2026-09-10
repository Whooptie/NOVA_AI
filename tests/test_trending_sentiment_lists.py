# tests/test_trending_sentiment_lists.py
"""
Tests voor Layer 1's laatste 2 "Advanced queries" uit
memory_layer1_roadmap.md (punt 6 in nova_state.md):

- get_trending(window_days)
- get_positive_words() / get_negative_words()

Zelfde patroon als test_find_bridge.py:
- tmp_path-isolatie voor save_path (want __init__() roept altijd
  load_from_disk() aan)
- word_stats/associations rechtstreeks handmatig gevuld, geen
  learn_from()/PMI-berekening nodig
"""

import time

import pytest

from modules.learning.word_associations_learner import WordAssociationsLearner


class DummyEventBus:
    def subscribe(self, *args, **kwargs):
        pass

    def publish(self, *args, **kwargs):
        pass


@pytest.fixture
def learner(tmp_path):
    save_path = tmp_path / "word_associations.json"
    instance = WordAssociationsLearner(
        event_bus=DummyEventBus(), save_path=save_path
    )
    return instance


# ─────────────────────────────────
# get_trending()
# ─────────────────────────────────

class TestGetTrending:
    def test_recent_nieuw_woord_scoort_hoog(self, learner):
        nu = time.time()
        learner.word_stats["neuraal"] = {
            "frequency": 8,
            "first_seen": nu - 2 * 86400,   # 2 dagen geleden: nieuw
            "last_seen": nu - 1 * 86400,
        }
        resultaat = learner.get_trending(window_days=7)
        woorden = [w for w, _ in resultaat]
        assert "neuraal" in woorden

    def test_oud_maar_nog_actief_woord_telt_mee_maar_lager(self, learner):
        nu = time.time()
        # Nieuw woord: recent ontstaan, frequency 5
        learner.word_stats["nieuw"] = {
            "frequency": 5,
            "first_seen": nu - 1 * 86400,
            "last_seen": nu - 1 * 86400,
        }
        # Oud woord: al 100 dagen bekend, maar deze week nog gebruikt,
        # zelfde frequency
        learner.word_stats["oud"] = {
            "frequency": 5,
            "first_seen": nu - 100 * 86400,
            "last_seen": nu - 1 * 86400,
        }
        resultaat = dict(learner.get_trending(window_days=7))
        assert resultaat["nieuw"] > resultaat["oud"]

    def test_niet_recent_woord_valt_weg(self, learner):
        nu = time.time()
        learner.word_stats["allangvergeten"] = {
            "frequency": 50,
            "first_seen": nu - 400 * 86400,
            "last_seen": nu - 30 * 86400,  # 30 dagen geleden
        }
        resultaat = learner.get_trending(window_days=7)
        woorden = [w for w, _ in resultaat]
        assert "allangvergeten" not in woorden

    def test_sortering_sterkste_eerst(self, learner):
        nu = time.time()
        learner.word_stats["laag"] = {
            "frequency": 1, "first_seen": nu, "last_seen": nu,
        }
        learner.word_stats["hoog"] = {
            "frequency": 10, "first_seen": nu, "last_seen": nu,
        }
        resultaat = learner.get_trending(window_days=7)
        assert resultaat[0][0] == "hoog"

    def test_top_k_limiet(self, learner):
        nu = time.time()
        for i in range(15):
            learner.word_stats[f"woord{i}"] = {
                "frequency": i, "first_seen": nu, "last_seen": nu,
            }
        resultaat = learner.get_trending(window_days=7, top_k=5)
        assert len(resultaat) == 5

    def test_leeg_bij_geen_data(self, learner):
        assert learner.get_trending(window_days=7) == []


# ─────────────────────────────────
# get_positive_words() / get_negative_words()
# ─────────────────────────────────

class TestPositiveNegativeWords:
    def test_positief_woord_uit_vaste_lijst_wordt_gevonden(self, learner):
        learner.word_stats["snel"] = {
            "frequency": 3, "first_seen": time.time(), "last_seen": time.time(),
        }
        resultaat = learner.get_positive_words()
        woorden = [w for w, _ in resultaat]
        assert "snel" in woorden

    def test_negatief_woord_uit_vaste_lijst_wordt_gevonden(self, learner):
        learner.word_stats["traag"] = {
            "frequency": 3, "first_seen": time.time(), "last_seen": time.time(),
        }
        resultaat = learner.get_negative_words()
        woorden = [w for w, _ in resultaat]
        assert "traag" in woorden

    def test_resultaat_bevat_score_als_tuple(self, learner):
        learner.word_stats["snel"] = {
            "frequency": 3, "first_seen": time.time(), "last_seen": time.time(),
        }
        resultaat = learner.get_positive_words()
        woord, score = resultaat[0]
        assert woord == "snel"
        assert score == pytest.approx(0.9)

    def test_drempel_filtert_zwak_scorend_woord_weg(self, learner):
        # "onbekendwoord" heeft geen associaties en geen vaste
        # sentiment-match -> scoort neutraal (0.33/0.33/0.34),
        # ver onder de standaarddrempel van 0.5.
        learner.word_stats["onbekendwoord"] = {
            "frequency": 100, "first_seen": time.time(), "last_seen": time.time(),
        }
        resultaat_pos = learner.get_positive_words()
        resultaat_neg = learner.get_negative_words()
        woorden_pos = [w for w, _ in resultaat_pos]
        woorden_neg = [w for w, _ in resultaat_neg]
        assert "onbekendwoord" not in woorden_pos
        assert "onbekendwoord" not in woorden_neg

    def test_woord_kan_niet_in_beide_lijsten_tegelijk_zitten(self, learner):
        # Dit was het live-geconstateerde probleem: zonder drempel kon
        # bv. "snel" in zowel positief als negatief verschijnen.
        learner.word_stats["snel"] = {
            "frequency": 3, "first_seen": time.time(), "last_seen": time.time(),
        }
        positief = [w for w, _ in learner.get_positive_words()]
        negatief = [w for w, _ in learner.get_negative_words()]
        assert not (set(positief) & set(negatief))

    def test_expliciete_min_score_override(self, learner):
        learner.word_stats["onbekendwoord"] = {
            "frequency": 1, "first_seen": time.time(), "last_seen": time.time(),
        }
        # Met een heel lage drempel komt het neutrale woord er nu wél
        # door -- bevestigt dat min_score effectief de filter stuurt.
        resultaat = learner.get_positive_words(min_score=0.0)
        woorden = [w for w, _ in resultaat]
        assert "onbekendwoord" in woorden

    def test_top_k_limiet_positief(self, learner):
        for w in ["snel", "mooi", "goed", "leuk", "cool", "top"]:
            learner.word_stats[w] = {
                "frequency": 1, "first_seen": time.time(), "last_seen": time.time(),
            }
        resultaat = learner.get_positive_words(top_k=2)
        assert len(resultaat) == 2

    def test_leeg_bij_geen_data(self, learner):
        assert learner.get_positive_words() == []
        assert learner.get_negative_words() == []