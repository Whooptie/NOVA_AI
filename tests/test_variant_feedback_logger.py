# tests/test_variant_feedback_logger.py
"""
Tests voor Response Variant Learning Fase 1+2
(modules/response_learning/variant_feedback_logger.py).

Volgt Nova's vaste pytest-patroon: tmp_path-isolatie (geen enkele
test raakt het echte data/-bestand), en counter-tests waar een fix
tijdelijk gebroken wordt om te bevestigen dat de test dan ook echt
faalt.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.response_learning.variant_feedback_logger import VariantFeedbackLogger


class FakeEventBus:
    """Minimale EventBus-simulatie: subscribe/publish, synchroon."""

    def __init__(self):
        self.subs = {}

    def subscribe(self, event_type, callback):
        self.subs.setdefault(event_type, []).append(callback)

    def publish(self, event_type, data):
        for cb in list(self.subs.get(event_type, [])):
            cb(data, event_type=event_type)


class FakeSentimentClassifier:
    """
    Simuleert sentiment_classifier.py. model=None simuleert "nog niet
    getraind" (classificeer() mag dan NIET aangeroepen worden door
    variant_feedback_logger.py, zie punt 3 in de module-docstring).
    """

    def __init__(self, model_geladen=True, vast_antwoord="positief"):
        self.model = "fake_model" if model_geladen else None
        self.vast_antwoord = vast_antwoord
        self.aanroepen = []

    def classificeer(self, tekst, grof_sentiment=None):
        self.aanroepen.append(tekst)
        return self.vast_antwoord


def _variant_gekozen_event(sjabloon_naam="definitie", index=0, entity="python"):
    return {
        "sjabloon_naam": sjabloon_naam,
        "gekozen_variant_index": index,
        "variant_tekst": "sjabloontekst",
        "entity": entity,
        "response_style": "normaal",
        "moment": "2026-08-20T10:00:00",
    }


# ------------------------------------------------------------
# Fase 1: logging
# ------------------------------------------------------------

def test_variant_gekozen_wordt_gelogd_naar_bestand(tmp_path):
    bus = FakeEventBus()
    logger = VariantFeedbackLogger(bus, sentiment_classifier=None, data_dir=tmp_path)

    bus.publish("variant_gekozen", _variant_gekozen_event())

    pad = tmp_path / "variant_feedback.jsonl"
    assert pad.exists()
    regels = [json.loads(r) for r in pad.read_text(encoding="utf-8").splitlines() if r.strip()]
    assert len(regels) == 1
    assert regels[0]["sjabloon_naam"] == "definitie"
    assert regels[0]["gekozen_variant_index"] == 0
    assert regels[0]["reactie_sentiment"] is None


def test_logging_verandert_geen_gedrag_zonder_genoeg_data(tmp_path):
    """Fase 1 alleen: get_gewichten() moet None geven zonder observaties."""
    bus = FakeEventBus()
    logger = VariantFeedbackLogger(bus, sentiment_classifier=None, data_dir=tmp_path)

    bus.publish("variant_gekozen", _variant_gekozen_event())

    assert logger.get_gewichten("definitie", 5) is None


# ------------------------------------------------------------
# Fase 2: sentiment koppelen
# ------------------------------------------------------------

def test_eerstvolgende_reactie_wordt_gekoppeld(tmp_path):
    bus = FakeEventBus()
    sc = FakeSentimentClassifier(vast_antwoord="positief")
    logger = VariantFeedbackLogger(bus, sentiment_classifier=sc, data_dir=tmp_path)

    bus.publish("variant_gekozen", _variant_gekozen_event(index=2))
    bus.publish("raw_user_message", {"text": "dat helpt, dankjewel!"})

    assert logger._scores["definitie"][2]["aantal"] == 1
    assert sc.aanroepen == ["dat helpt, dankjewel!"]


def test_geen_model_geladen_logt_geen_vals_sentiment(tmp_path):
    """
    COUNTER-TEST-relevante regel: zonder geladen model mag
    classificeer() NOOIT aangeroepen worden (dat zou "positief" als
    hardcoded terugval geven -- valse data in het trainingsbestand).
    """
    bus = FakeEventBus()
    sc = FakeSentimentClassifier(model_geladen=False)
    logger = VariantFeedbackLogger(bus, sentiment_classifier=sc, data_dir=tmp_path)

    bus.publish("variant_gekozen", _variant_gekozen_event())
    bus.publish("raw_user_message", {"text": "reactie"})

    assert sc.aanroepen == [], "classificeer() had niet aangeroepen mogen worden zonder model"
    assert logger._scores == {}, "geen score mag opgebouwd worden zonder een geladen model"


def test_geen_sentiment_classifier_module_geeft_geen_crash(tmp_path):
    """sentiment_classifier=None (nog niet geladen) mag nooit crashen."""
    bus = FakeEventBus()
    logger = VariantFeedbackLogger(bus, sentiment_classifier=None, data_dir=tmp_path)

    bus.publish("variant_gekozen", _variant_gekozen_event())
    bus.publish("raw_user_message", {"text": "reactie"})  # mag niet crashen

    assert logger._scores == {}


def test_precies_een_open_koppeling_per_sjabloon(tmp_path):
    """
    Twee variant-keuzes voor HETZELFDE sjabloon zonder tussenliggende
    reactie: enkel de LAATSTE mag de eerstvolgende reactie krijgen,
    de eerste blijft permanent ongekoppeld.
    """
    bus = FakeEventBus()
    sc = FakeSentimentClassifier(vast_antwoord="positief")
    logger = VariantFeedbackLogger(bus, sentiment_classifier=sc, data_dir=tmp_path)

    bus.publish("variant_gekozen", _variant_gekozen_event(index=0))
    bus.publish("variant_gekozen", _variant_gekozen_event(index=3))
    bus.publish("raw_user_message", {"text": "reactie"})

    assert 3 in logger._scores["definitie"]
    assert logger._scores["definitie"][3]["aantal"] == 1
    assert 0 not in logger._scores.get("definitie", {})


def test_verschillende_sjablonen_interfereren_niet(tmp_path):
    bus = FakeEventBus()
    sc = FakeSentimentClassifier(vast_antwoord="positief")
    logger = VariantFeedbackLogger(bus, sentiment_classifier=sc, data_dir=tmp_path)

    bus.publish("variant_gekozen", _variant_gekozen_event(sjabloon_naam="definitie", index=1))
    bus.publish("variant_gekozen", _variant_gekozen_event(sjabloon_naam="interruption_vraag", index=4, entity=None))
    bus.publish("raw_user_message", {"text": "ok"})

    assert logger._scores["definitie"][1]["aantal"] == 1
    assert logger._scores["interruption_vraag"][4]["aantal"] == 1


# ------------------------------------------------------------
# get_gewichten(): drempel en garanties
# ------------------------------------------------------------

def test_geen_gewichten_onder_de_drempel(tmp_path):
    bus = FakeEventBus()
    sc = FakeSentimentClassifier(vast_antwoord="positief")
    logger = VariantFeedbackLogger(bus, sentiment_classifier=sc, data_dir=tmp_path)

    for _ in range(logger.MIN_OBSERVATIES_PER_VARIANT - 1):
        bus.publish("variant_gekozen", _variant_gekozen_event(index=0))
        bus.publish("raw_user_message", {"text": "top"})

    assert logger.get_gewichten("definitie", 5) is None


def test_gewichten_actief_zodra_drempel_gehaald(tmp_path):
    bus = FakeEventBus()
    sc = FakeSentimentClassifier(vast_antwoord="positief")
    logger = VariantFeedbackLogger(bus, sentiment_classifier=sc, data_dir=tmp_path)

    for _ in range(logger.MIN_OBSERVATIES_PER_VARIANT):
        bus.publish("variant_gekozen", _variant_gekozen_event(index=0))
        bus.publish("raw_user_message", {"text": "top"})

    gewichten = logger.get_gewichten("definitie", 5)
    assert gewichten is not None
    assert len(gewichten) == 5
    # Variant 0: enkel positieve reacties -> hoogste gewicht
    assert gewichten[0] == max(gewichten)


def test_geen_gewicht_ooit_nul_ook_niet_bij_enkel_negatief(tmp_path):
    bus = FakeEventBus()
    sc = FakeSentimentClassifier(vast_antwoord="negatief")
    logger = VariantFeedbackLogger(bus, sentiment_classifier=sc, data_dir=tmp_path)

    for _ in range(logger.MIN_OBSERVATIES_PER_VARIANT):
        bus.publish("variant_gekozen", _variant_gekozen_event(index=0))
        bus.publish("raw_user_message", {"text": "kut, werkt niet"})

    gewichten = logger.get_gewichten("definitie", 5)
    assert all(g > 0 for g in gewichten), "geen enkel gewicht mag ooit exact 0 zijn"
    assert gewichten[0] == pytest.approx(logger.MIN_GEWICHT)


def test_variant_zonder_eigen_data_krijgt_neutraal_gewicht(tmp_path):
    """Variant 1 heeft geen enkele observatie -> moet het neutrale gewicht (0.5 + MIN_GEWICHT) krijgen, niet gestraft worden."""
    bus = FakeEventBus()
    sc = FakeSentimentClassifier(vast_antwoord="positief")
    logger = VariantFeedbackLogger(bus, sentiment_classifier=sc, data_dir=tmp_path)

    for _ in range(logger.MIN_OBSERVATIES_PER_VARIANT):
        bus.publish("variant_gekozen", _variant_gekozen_event(index=0))
        bus.publish("raw_user_message", {"text": "top"})

    gewichten = logger.get_gewichten("definitie", 5)
    verwacht_neutraal = logger.MIN_GEWICHT + 0.5
    assert gewichten[1] == pytest.approx(verwacht_neutraal)


# ------------------------------------------------------------
# Herstart: scores herbouwen uit bestaand bestand
# ------------------------------------------------------------

def test_scores_worden_herbouwd_bij_herstart(tmp_path):
    bus1 = FakeEventBus()
    sc1 = FakeSentimentClassifier(vast_antwoord="positief")
    logger1 = VariantFeedbackLogger(bus1, sentiment_classifier=sc1, data_dir=tmp_path)

    for _ in range(3):
        bus1.publish("variant_gekozen", _variant_gekozen_event(index=2))
        bus1.publish("raw_user_message", {"text": "top"})

    # Nieuwe instantie op hetzelfde data_dir simuleert een herstart
    bus2 = FakeEventBus()
    sc2 = FakeSentimentClassifier(vast_antwoord="positief")
    logger2 = VariantFeedbackLogger(bus2, sentiment_classifier=sc2, data_dir=tmp_path)

    assert logger2._scores["definitie"][2]["aantal"] == 3


def test_beschadigde_regel_blokkeert_inlezen_niet(tmp_path):
    pad = tmp_path / "variant_feedback.jsonl"
    pad.write_text(
        '{"sjabloon_naam": "definitie", "gekozen_variant_index": 0, "reactie_sentiment": "positief"}\n'
        "DIT IS GEEN GELDIGE JSON\n"
        '{"sjabloon_naam": "definitie", "gekozen_variant_index": 0, "reactie_sentiment": "positief"}\n',
        encoding="utf-8",
    )

    bus = FakeEventBus()
    logger = VariantFeedbackLogger(bus, sentiment_classifier=None, data_dir=tmp_path)

    assert logger._scores["definitie"][0]["aantal"] == 2