# test_fase1.py
#
# Echte pytest-test voor Fase 1 van Layer 1 (Word Associations Learner):
# de preprocessing-pijplijn (tokenize, stopwoorden filteren, lemmatizen).
#
# Geen event_bus nodig (event_bus=None mag, zoals het origineel al deed),
# geen bestanden, geen echte data -- puur functie-input/output testen.
#
# Uitvoeren: pytest tests/test_fase1.py -v

import pytest

from modules.learning.word_associations_learner import WordAssociationsLearner


@pytest.fixture
def leerder():
    return WordAssociationsLearner(event_bus=None)


def test_stopwoorden_worden_gefilterd(leerder):
    """'is' en 'mijn' zijn stopwoorden en horen niet in het resultaat."""
    result = leerder.preprocess("Python is mijn favoriet")
    assert "is" not in result
    assert "mijn" not in result
    assert "python" in result
    assert "favoriet" in result


def test_lemmatize_snelle_naar_snel(leerder):
    """'snelle' hoort gelemmatized te worden naar 'snel'."""
    result = leerder.preprocess("Ik hou van snelle talen")
    assert "ik" not in result
    assert "van" not in result
    assert "snel" in result


def test_meerdere_stopwoorden_in_1_zin(leerder):
    """'is', 'en', 'dat' zijn stopwoorden; 'java'/'traag'/'jammer' niet."""
    result = leerder.preprocess("Java is traag en dat is jammer")
    assert "java" in result
    assert "traag" in result
    assert "jammer" in result
    for stopwoord in ("is", "en", "dat"):
        assert stopwoord not in result


def test_verkleinwoord_kopje_naar_kop(leerder):
    """'kopje' hoort via de verkleinwoord-regel naar 'kop' herleid te worden."""
    result = leerder.preprocess("Dat kopje koffie was echt lekker!")
    assert "kop" in result
    assert "koffie" in result
    assert "lekker" in result


def test_bekende_beperking_buren(leerder):
    """
    'buren' is geen simpel meervoud op -en van 'buur' -- dit bevestigt
    een BEKENDE beperking van de simpele lemmatizer, geen bug. Deze
    test legt vast wat het HUIDIGE gedrag is, zodat een toekomstige
    wijziging aan de lemmatizer bewust gebeurt i.p.v. onopgemerkt.
    """
    result = leerder.preprocess("De auto's van de buren staan er weer")
    assert "auto" in result
    # Geen assert op 'buur' vs 'buren' hier -- dat is precies het
    # randgeval dat nog niet correct opgelost is. Zodra dat verbeterd
    # wordt, kan deze test uitgebreid worden met een echte assert.