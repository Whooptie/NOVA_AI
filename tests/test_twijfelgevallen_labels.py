# tests/test_twijfelgevallen_labels.py
"""
Fase A (2 oktober 2026): twijfelgevallen tellen enkel nog als
trainingsdata als Kevin ze labelde ("label_kevin"), en twijfel zonder
bevestiging telt niet meer als signaal/oordeel.

Isolatie: MicroLearning en SentimentClassifier lezen in __init__()
echte bestanden en starten meteen een hertraining-check. Daarom maken
we ze aan ZONDER __init__ (object.__new__) en zetten we enkel de
attributen die de geteste methodes nodig hebben, allemaal naar tmp_path.
De echte data/-bestanden worden nooit aangeraakt.
"""
import json

import pytest

from identity.personality import microlearning as ml_module
from identity.personality import train_classifier
from modules.preferences import sentiment_classifier as sc_module
from modules.preferences import train_sentiment_classifier


# ---------------------------------------------------------------
# Hulpmiddelen
# ---------------------------------------------------------------
class NepModel:
    """Nep-classifier met vaste kansen, zodat de test zelf de marge bepaalt."""

    def __init__(self, kansen):
        self.classes_ = list(kansen.keys())
        self._proba = [list(kansen.values())]

    def predict_proba(self, teksten):
        return self._proba


def _schrijf_jsonl(pad, items):
    with open(pad, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def _lees_jsonl(pad):
    with open(pad, "r", encoding="utf-8") as f:
        return [json.loads(r) for r in f if r.strip()]


@pytest.fixture
def micro(tmp_path):
    m = object.__new__(ml_module.MicroLearning)
    m._uncertain_path = str(tmp_path / "uncertain_signals.jsonl")
    m._hertraining_status_pad = str(tmp_path / "hertraining_status.json")
    m.HERTRAINING_DREMPEL = 10
    m.model = None
    return m


@pytest.fixture
def sentiment(tmp_path):
    s = object.__new__(sc_module.SentimentClassifier)
    s.event_bus = None
    s._uncertain_pad = str(tmp_path / "sentiment_uncertain.jsonl")
    s._hertraining_status_pad = str(tmp_path / "sentiment_hertraining_status.json")
    s.HERTRAINING_DREMPEL = 10
    s.model = None
    return s


# Marge 0.05 (< 0.10) = twijfel
TWIJFEL_KILTE = {"kilte": 0.40, "neutraal": 0.35, "focus": 0.25}


# ---------------------------------------------------------------
# microlearning.py -- signaaldetectie
# ---------------------------------------------------------------
def test_twijfel_zonder_woordenlijst_geeft_geen_signaal(micro):
    micro.model = NepModel(TWIJFEL_KILTE)
    assert micro._detecteer_signaal("pion naar e4") == []


def test_twijfel_wordt_wel_gelogd_zonder_kevin_label(micro):
    micro.model = NepModel(TWIJFEL_KILTE)
    micro._detecteer_signaal("pion naar e4")
    regels = _lees_jsonl(micro._uncertain_path)
    assert len(regels) == 1
    assert regels[0]["text"] == "pion naar e4"
    assert "label_kevin" not in regels[0]


def test_twijfel_met_woordenlijst_match_gebruikt_woordenlijst(micro):
    micro.model = NepModel(TWIJFEL_KILTE)
    assert micro._detecteer_signaal("dank je, dat helpt") == ["waardering"]


def test_duidelijke_marge_gebruikt_model(micro):
    micro.model = NepModel({"interesse": 0.70, "neutraal": 0.20, "kilte": 0.10})
    assert micro._detecteer_signaal("vertel daar eens meer over") == ["interesse"]


def test_duidelijk_neutraal_geeft_lege_lijst(micro):
    micro.model = NepModel({"neutraal": 0.70, "kilte": 0.20, "focus": 0.10})
    assert micro._detecteer_signaal("hoe laat is het") == []


def test_kort_bericht_is_geen_kilte_meer(micro):
    assert micro._detecteer_signaal_woordenlijst("hey") == []
    assert micro._detecteer_signaal_woordenlijst("3") == []


# ---------------------------------------------------------------
# microlearning.py -- tellen en hertraining-trigger
# ---------------------------------------------------------------
def test_tel_gelabelde_twijfelzinnen(micro):
    _schrijf_jsonl(micro._uncertain_path, [
        {"text": "pion naar e4", "signaal": "kilte", "label_kevin": "neutraal"},
        {"text": "Pion naar e4 ", "signaal": "kilte", "label_kevin": "neutraal"},
        {"text": "open vlc", "signaal": "kilte", "label_kevin": "skip"},
        {"text": "help", "signaal": "kilte"},
        {"text": "dank je", "signaal": "waardering", "label_kevin": "waardering"},
    ])
    assert micro._tel_gelabelde_twijfelzinnen() == 2


def test_oud_statusbestand_triggert_geen_hertraining(micro, monkeypatch):
    with open(micro._hertraining_status_pad, "w", encoding="utf-8") as f:
        json.dump({"aantal_bij_laatste_training": 600,
                   "laatste_training": "2026-07-18T16:00:00"}, f)

    aangeroepen = []

    def nep_train():
        aangeroepen.append(1)
        return {"succes": True, "wordt_actief": False}

    monkeypatch.setattr(train_classifier, "train_model", nep_train)
    micro._check_hertraining(bij_opstart=True)
    assert aangeroepen == []


def test_genoeg_gelabelde_zinnen_triggert_hertraining(micro, monkeypatch):
    _schrijf_jsonl(micro._uncertain_path, [
        {"text": f"zin {i}", "signaal": "kilte", "label_kevin": "neutraal"}
        for i in range(10)
    ])
    with open(micro._hertraining_status_pad, "w", encoding="utf-8") as f:
        json.dump({"gelabeld_bij_laatste_training": 0,
                   "laatste_training": "2026-07-18T16:00:00"}, f)

    aangeroepen = []

    def nep_train():
        aangeroepen.append(1)
        return {"succes": True, "wordt_actief": False}

    monkeypatch.setattr(train_classifier, "train_model", nep_train)
    micro._check_hertraining(bij_opstart=False)

    assert aangeroepen == [1]
    with open(micro._hertraining_status_pad, encoding="utf-8") as f:
        assert json.load(f)["gelabeld_bij_laatste_training"] == 10


# ---------------------------------------------------------------
# train_classifier.py -- enkel Kevin-labels als trainingsdata
# ---------------------------------------------------------------
def test_signaal_trainer_gebruikt_enkel_kevin_labels(tmp_path, monkeypatch):
    pad = tmp_path / "uncertain_signals.jsonl"
    _schrijf_jsonl(pad, [
        {"text": "pion naar e4", "signaal": "kilte", "label_kevin": "neutraal"},
        {"text": "pion naar e4", "signaal": "kilte", "label_kevin": "neutraal"},
        {"text": "open vlc", "signaal": "kilte"},
        {"text": "help", "signaal": "kilte", "label_kevin": "skip"},
        {"text": "bord", "signaal": "kilte", "label_kevin": "neutrall"},
    ])
    monkeypatch.setattr(train_classifier, "UNCERTAIN_PAD", str(pad))

    resultaat = train_classifier._laad_uncertain_voorbeelden({"neutraal", "kilte"})
    assert resultaat == [{"text": "pion naar e4", "signaal": "neutraal"}]


def test_signaal_trainer_zonder_bestand_geeft_lege_lijst(tmp_path, monkeypatch):
    monkeypatch.setattr(train_classifier, "UNCERTAIN_PAD", str(tmp_path / "bestaat_niet.jsonl"))
    assert train_classifier._laad_uncertain_voorbeelden({"neutraal"}) == []


# ---------------------------------------------------------------
# train_sentiment_classifier.py -- idem
# ---------------------------------------------------------------
def test_sentiment_trainer_gebruikt_enkel_kevin_labels(tmp_path, monkeypatch):
    pad = tmp_path / "sentiment_uncertain.jsonl"
    _schrijf_jsonl(pad, [
        {"text": "/reboot", "categorie": "negatief", "label_kevin": "neutraal_gemengd"},
        {"text": "wat is python", "categorie": "positief"},
        {"text": "dank je!", "categorie": "negatief", "label_kevin": "positief"},
        {"text": "hey", "categorie": "negatief", "label_kevin": "skip"},
    ])
    monkeypatch.setattr(train_sentiment_classifier, "UNCERTAIN_PAD", str(pad))

    resultaat = train_sentiment_classifier._laad_uncertain_voorbeelden(
        {"positief", "neutraal_gemengd", "negatief"}
    )
    assert {"text": "/reboot", "categorie": "neutraal_gemengd"} in resultaat
    assert {"text": "dank je!", "categorie": "positief"} in resultaat
    assert len(resultaat) == 2


# ---------------------------------------------------------------
# sentiment_classifier.py -- twijfel zonder/met regex-context
# ---------------------------------------------------------------
def test_sentiment_twijfel_zonder_regex_is_neutraal(sentiment):
    sentiment.model = NepModel({"negatief": 0.40, "positief": 0.35, "neutraal_gemengd": 0.25})
    assert sentiment.classificeer("/reboot") == "neutraal_gemengd"


def test_sentiment_twijfel_met_regex_houdt_top_klasse(sentiment):
    sentiment.model = NepModel({"negatief": 0.40, "positief": 0.35, "neutraal_gemengd": 0.25})
    assert sentiment.classificeer("ik hou niet zo van kou", grof_sentiment="negatief") == "negatief"


def test_sentiment_duidelijke_marge_ongewijzigd(sentiment):
    sentiment.model = NepModel({"positief": 0.80, "negatief": 0.10, "neutraal_gemengd": 0.10})
    assert sentiment.classificeer("dank je wel") == "positief"


def test_sentiment_twijfel_wordt_gelogd(sentiment):
    sentiment.model = NepModel({"negatief": 0.40, "positief": 0.35, "neutraal_gemengd": 0.25})
    sentiment.classificeer("/reboot")
    regels = _lees_jsonl(sentiment._uncertain_pad)
    assert len(regels) == 1
    assert "label_kevin" not in regels[0]


def test_sentiment_oud_statusbestand_triggert_geen_hertraining(sentiment, monkeypatch):
    with open(sentiment._hertraining_status_pad, "w", encoding="utf-8") as f:
        json.dump({"aantal_bij_laatste_training": 300,
                   "laatste_training": "2026-07-26T12:00:00"}, f)

    aangeroepen = []

    def nep_train():
        aangeroepen.append(1)
        return {"succes": True, "wordt_actief": False}

    monkeypatch.setattr(train_sentiment_classifier, "train_model", nep_train)
    sentiment._check_hertraining(bij_opstart=True)
    assert aangeroepen == []


# ---------------------------------------------------------------
# debug_commands.py -- 'preferences debug' na de Fase A-hernoeming
# ---------------------------------------------------------------
def test_preferences_debug_crasht_niet_na_fase_a(sentiment, capsys):
    from modules.debug.debug_commands import DebugCommands

    class NepBus:
        def subscribe(self, *args, **kwargs):
            pass

    class NepLoader:
        loaded_modules = {"sentiment_classifier": sentiment}

    debug = DebugCommands(NepBus(), NepLoader())
    debug._preferences_debug("preferences debug")

    uitvoer = capsys.readouterr().out
    assert "Gelabelde twijfelzinnen: 0 totaal" in uitvoer