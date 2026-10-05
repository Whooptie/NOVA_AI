"""
Tests voor regel 4b van _auto_learn_from_sentence (5 oktober 2026):
vervoegde vormen op -e (nieuwe, grote, werkte) worden niet geleerd,
echte zelfstandige naamwoorden op -e (liefde, ziekte, kade) wel.

De nep-semantic zegt voor ELK woord "noun", zodat we zeker weten dat
het nieuwe filter het werk doet en niet detect_pos().
"""

from unittest.mock import MagicMock

import pytest

pytest.importorskip("simplemma")

import modules.chat.response_pipeline as rp

# Zoek de klasse die de methode bevat (klassenaam niet hardcoderen).
KLASSE = next(
    obj for obj in vars(rp).values()
    if isinstance(obj, type) and hasattr(obj, "_auto_learn_from_sentence")
)


def _geleerde_woorden(zin):
    """Draait het filter op een zin en geeft de geleerde woorden terug."""
    if rp.simplemma is None:
        pytest.skip("simplemma niet geladen in response_pipeline")

    nep_self = MagicMock()
    nep_self.semantic.sense_engine.detect_pos.return_value = "noun"
    nep_self.semantic.store.has_concept.return_value = False

    KLASSE._auto_learn_from_sentence(nep_self, zin)

    geleerd = set()
    for aanroep in nep_self.semantic.auto_learn.call_args_list:
        if aanroep.args:
            geleerd.add(aanroep.args[0])
        else:
            geleerd.update(
                v for v in aanroep.kwargs.values() if isinstance(v, str)
            )
    return geleerd


def test_vervoegde_vormen_op_e_worden_niet_geleerd():
    geleerd = _geleerde_woorden("nieuwe grote mooie werkte vriendelijke")
    for woord in ["nieuwe", "grote", "mooie", "werkte", "vriendelijke"]:
        assert woord not in geleerd, f"'{woord}' had niet geleerd mogen worden"


def test_echte_naamwoorden_op_e_worden_wel_geleerd():
    geleerd = _geleerde_woorden("liefde ziekte kade")
    for woord in ["liefde", "ziekte", "kade"]:
        assert woord in geleerd, f"'{woord}' had wel geleerd moeten worden"


def test_live_zin_van_5_oktober():
    geleerd = _geleerde_woorden(
        "ik heb gisteren een nieuwe kapstok en een vergiet gekocht"
    )
    assert "kapstok" in geleerd
    assert "vergiet" in geleerd          # niet "vergieten"!
    assert "vergieten" not in geleerd
    assert "nieuwe" not in geleerd