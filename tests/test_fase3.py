# test_fase3.py
#
# Echte pytest-test voor Fase 3 van Layer 1 (Word Associations Learner):
# of calculate_pmi() zinvolle sterkte-scores geeft. Woorden die STEEDS
# samen voorkomen (python + snel) horen een hogere score te krijgen
# dan woorden die maar TOEVALLIG 1 keer samen opdoken (snel + kaas).
#
# Uitvoeren: pytest tests/test_fase3.py -v

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

    # "python" en "snel" komen HERHAALDELIJK samen voor -> sterke band
    for _ in range(8):
        stuur_interactie(bus, "Python is heel snel", "Ja, Python is snel!")

    # "kaas" komt vaak VOOR (hoge eigen frequentie), maar bijna nooit
    # samen met "snel" -> zwakke band ondanks dat het woord vaak voorkomt
    stuur_interactie(bus, "Ik at snel wat kaas", "Kaas is lekker.")
    for _ in range(7):
        stuur_interactie(bus, "Ik hou van kaas op brood", "Kaas is heerlijk, ja.")

    # Wat neutrale ruis
    stuur_interactie(bus, "Het weer is mooi vandaag", "Fijn dat de zon schijnt.")
    stuur_interactie(bus, "Ik ga morgen fietsen", "Veel plezier met fietsen!")

    return leerder


def test_python_snel_sterker_dan_snel_kaas(leerder_met_gesprekken):
    """
    'snel' <-> 'python' (8x samen voorgekomen) hoort een hogere
    pmi-score te hebben dan 'snel' <-> 'kaas' (1x toevallig samen).
    """
    snapshot = leerder_met_gesprekken.get_debug_snapshot()
    snel_assoc = snapshot["associations"].get("snel", {})

    assert "python" in snel_assoc, "Geen associatie snel<->python gevonden."
    assert "kaas" in snel_assoc, "Geen associatie snel<->kaas gevonden."

    pmi_python = snel_assoc["python"].get("pmi", 0)
    pmi_kaas = snel_assoc["kaas"].get("pmi", 0)

    assert pmi_python > pmi_kaas, (
        f"Verwachtte pmi(snel,python)={pmi_python} > pmi(snel,kaas)={pmi_kaas}, "
        f"maar het sterke, herhaalde verband scoort niet hoger dan het "
        f"toevallige, eenmalige verband."
    )


def test_alle_pmi_scores_binnen_bereik(leerder_met_gesprekken):
    """Alle PMI-scores horen tussen 0.0 en 1.0 te liggen (genormaliseerd)."""
    snapshot = leerder_met_gesprekken.get_debug_snapshot()

    for woord, associaties in snapshot["associations"].items():
        for ander_woord, info in associaties.items():
            pmi = info.get("pmi", 0)
            assert 0.0 <= pmi <= 1.0, (
                f"pmi({woord},{ander_woord})={pmi} valt buiten het "
                f"verwachte bereik [0.0, 1.0]"
            )