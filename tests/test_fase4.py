# test_fase4.py
#
# Echte pytest-test voor Fase 4 van Layer 1 (Word Associations Learner):
# de query-functies get_associations, find_related, word_distance,
# get_word_sentiment, get_stats.
#
# LET OP (eerlijkheid over dekking): het originele script specificeerde
# geen exacte verwachte getallen voor deze functies, enkel kwalitatieve
# verwachtingen ("hoge score", "gesorteerd van hoog naar laag", "positief-
# leunend"). Deze test controleert daarom die kwalitatieve garanties,
# niet exacte cijfers -- dat is eerlijker dan cijfers verzinnen die niet
# uit het origineel kwamen.
#
# Uitvoeren: pytest tests/test_fase4.py -v

import time

import pytest

from modules.learning.word_associations_learner import WordAssociationsLearner


class NepEventBus:
    def __init__(self):
        self.subscribers = {}

    def subscribe(self, event_type, callback):
        self.subscribers.setdefault(event_type, []).append(callback)

    def publish(self, event_type, data):
        for callback in self.subscribers.get(event_type, []):
            callback(data)


def stuur_interactie(bus, user_input, nova_response=None):
    """Zie toelichting in test_fase2.py: event_type moet 'chat_message'
    zijn en de tekst moet in data['text'] staan, anders breekt
    learn_from() meteen af zonder iets te leren."""
    bus.publish("memory:interaction_added", {
        "timestamp": time.time(),
        "event_type": "chat_message",
        "data": {"text": user_input},
    })


@pytest.fixture
def leerder_met_gesprekken(tmp_path):
    """save_path wordt bewust altijd meegegeven -- zie toelichting in
    test_fase2.py: zonder dit laadt __init__() automatisch je echte
    data/word_associations.json in via load_from_disk()."""
    bus = NepEventBus()
    leerder = WordAssociationsLearner(
        event_bus=bus,
        save_path=str(tmp_path / "test_word_associations.json"),
    )

    for _ in range(6):
        stuur_interactie(bus, "Python is heel snel en elegant", "Ja, Python is top!")
    for _ in range(4):
        stuur_interactie(bus, "Java is traag en saai", "Dat hoor ik vaker over Java.")
    for _ in range(5):
        stuur_interactie(bus, "Ik hou van kaas op brood", "Kaas is heerlijk, ja.")

    return leerder


def test_get_associations_bevat_verwachte_woorden(leerder_met_gesprekken):
    """get_associations('python') hoort o.a. 'snel' en 'elegant' te bevatten,
    aflopend gesorteerd (hoogste score eerst)."""
    result = leerder_met_gesprekken.get_associations("python")

    assert "snel" in result
    assert "elegant" in result

    scores = list(result.values())
    assert scores == sorted(scores, reverse=True), (
        "get_associations() hoort van hoog naar laag gesorteerd te zijn."
    )


def test_find_related_geeft_top_k_resultaten(leerder_met_gesprekken):
    """find_related('python', top_k=3) hoort maximaal 3 resultaten te geven."""
    result = leerder_met_gesprekken.find_related("python", top_k=3)
    assert len(result) <= 3
    assert len(result) > 0


def test_word_distance_direct_kleiner_dan_indirect(leerder_met_gesprekken):
    """
    word_distance() geeft, ondanks de naam, geen 'afstand' terug maar
    een sterkte-score: bij een direct verband (python<->snel, komen
    samen voor) is dat gewoon de PMI-score zelf (hoger = sterker
    verbonden). Bij een indirect verband (python<->saai, komen nooit
    samen voor) wordt een gemiddelde van gedeelde associaties genomen,
    met een korting van 0.5 (zie word_distance() in de broncode) --
    dat hoort dus LAGER te zijn dan een direct verband, niet hoger.

    LET OP (tweede correctie t.o.v. eerdere versies): eerst nam ik aan
    dat een hoger getal verder weg betekende, toen dat een direct
    verband altijd 0.0 zou zijn. Beide waren gokken zonder de
    broncode. Nu gebaseerd op de echte implementatie (regel 594-621
    van word_associations_learner.py): word_distance() retourneert bij
    een directe match gewoon assoc1[word2] (de PMI-score), dus een
    HOGER getal = een STERKER/dichterbij verband.
    """
    afstand_direct = leerder_met_gesprekken.word_distance("python", "snel")
    afstand_indirect = leerder_met_gesprekken.word_distance("python", "saai")

    assert afstand_direct is not None
    assert 0.0 < afstand_direct <= 1.0, (
        f"Verwachtte een PMI-score tussen 0 en 1 voor het directe "
        f"verband python<->snel, kreeg {afstand_direct}."
    )
    # Indirect verband: krijgt een korting (x0.5) t.o.v. een direct
    # verband, en hoort dus LAGER te liggen dan het directe verband.
    if afstand_indirect is not None and afstand_indirect > 0:
        assert afstand_indirect < afstand_direct, (
            f"Verwachtte dat het indirecte verband ({afstand_indirect}) "
            f"lager zou liggen dan het directe verband ({afstand_direct})."
        )


def test_sentiment_snel_is_positief(leerder_met_gesprekken):
    """get_word_sentiment('snel') hoort een hoge 'positive'-score te geven."""
    sentiment = leerder_met_gesprekken.get_word_sentiment("snel")
    assert sentiment["positive"] > sentiment["negative"]


def test_sentiment_traag_is_negatief(leerder_met_gesprekken):
    """get_word_sentiment('traag') hoort een hoge 'negative'-score te geven."""
    sentiment = leerder_met_gesprekken.get_word_sentiment("traag")
    assert sentiment["negative"] > sentiment["positive"]


def test_sentiment_python_leunt_positief_via_associaties(leerder_met_gesprekken):
    """
    'python' heeft zelf geen eigen sentiment-label, maar is geassocieerd
    met 'snel'/'elegant' (positief) -- get_word_sentiment('python') hoort
    daarom positief-leunend te zijn (afgeleid via Layer 1-associaties).
    """
    sentiment = leerder_met_gesprekken.get_word_sentiment("python")
    assert sentiment["positive"] >= sentiment["negative"]


def test_get_stats_bevat_verwachte_velden(leerder_met_gesprekken):
    """get_stats() hoort total_words, total_associations en
    strongest_associations te bevatten, met minstens 1 woord/associatie."""
    stats = leerder_met_gesprekken.get_stats()

    assert stats["total_words"] > 0
    assert stats["total_associations"] > 0
    assert len(stats["strongest_associations"]) > 0