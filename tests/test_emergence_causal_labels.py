"""Tests voor de Layer 7-labels van de causale topics (Fase 8)."""

from modules.experimental.emergence_engine import EmergenceEngine


def _maak_engine():
    # Omzeilt __init__ bewust: _onderwerp_label gebruikt enkel
    # deze twee opzoektabellen.
    engine = object.__new__(EmergenceEngine)
    engine._event_type_labels = {}
    engine._topic_naam_labels = {
        "causes_check": "oorzaak-en-gevolg-vragen",
        "related_to_check": "of concepten verwant zijn",
    }
    return engine


def test_causes_check_krijgt_nederlands_label():
    e = _maak_engine()
    assert e._onderwerp_label("topic_detected:causes_check") == "oorzaak-en-gevolg-vragen"


def test_oorzaken_prefix():
    e = _maak_engine()
    assert e._onderwerp_label("topic_detected:oorzaken_regen") == "oorzaken van regen"


def test_gevolgen_prefix():
    e = _maak_engine()
    assert e._onderwerp_label("topic_detected:gevolgen_regen") == "gevolgen van regen"


def test_bestaande_tak_open_app_blijft_werken():
    e = _maak_engine()
    assert e._onderwerp_label("topic_detected:open_app_chrome") == "chrome openen"


def test_onbekend_topic_valt_terug_op_kale_naam():
    e = _maak_engine()
    assert e._onderwerp_label("topic_detected:iets_nieuws") == "iets_nieuws"