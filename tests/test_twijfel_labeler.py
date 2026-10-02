# tests/test_twijfel_labeler.py
"""
Fase B (2 oktober 2026): labelen van twijfelgevallen.

- core/twijfel_labeler.py: volgende zin, label wegschrijven, status.
- microlearning.py: automatisch label via STRIKTE_TREFWOORDEN.
- Trainers/tellers: label_auto telt mee, label_kevin wint altijd.
- debug_commands.py: 'label signaal' / 'label status' end-to-end.

Isolatie: alles in tmp_path. twijfel_labeler._root wordt gemonkeypatcht
naar tmp_path; MicroLearning wordt aangemaakt zonder __init__ (die leest
echte bestanden), zelfde aanpak als test_twijfelgevallen_labels.py.
"""
import json

import pytest

from core import twijfel_labeler
from identity.personality import microlearning as ml_module
from identity.personality import train_classifier
from modules.debug.debug_commands import DebugCommands


def _schrijf_jsonl(pad, items):
    with open(pad, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def _lees_jsonl(pad):
    with open(pad, "r", encoding="utf-8") as f:
        return [json.loads(r) for r in f if r.strip()]


# ---------------------------------------------------------------
# core/twijfel_labeler.py
# ---------------------------------------------------------------
def test_volgende_ongelabelde_vaakst_voorkomend_eerst(tmp_path):
    pad = tmp_path / "u.jsonl"
    _schrijf_jsonl(pad, [
        {"text": "help", "signaal": "kilte"},
        {"text": "pion naar e4", "signaal": "kilte"},
        {"text": "Pion naar e4", "signaal": "neutraal"},
        {"text": "pion naar e4", "signaal": "kilte"},
    ])
    v = twijfel_labeler.volgende_ongelabelde(str(pad), "signaal")
    assert v["tekst"] == "pion naar e4"
    assert v["aantal"] == 3
    assert v["model_gok"] == "kilte"
    assert v["nog_te_gaan"] == 2


def test_volgende_slaat_gelabelde_zinnen_volledig_over(tmp_path):
    pad = tmp_path / "u.jsonl"
    _schrijf_jsonl(pad, [
        {"text": "help", "signaal": "kilte", "label_kevin": "neutraal"},
        {"text": "help", "signaal": "kilte"},
        {"text": "dank je", "signaal": "waardering", "label_auto": "waardering"},
        {"text": "bord", "signaal": "kilte"},
    ])
    v = twijfel_labeler.volgende_ongelabelde(str(pad), "signaal")
    assert v["tekst"] == "bord"
    assert v["nog_te_gaan"] == 1


def test_volgende_geeft_none_als_niets_te_labelen(tmp_path):
    pad = tmp_path / "u.jsonl"
    _schrijf_jsonl(pad, [{"text": "help", "signaal": "kilte", "label_kevin": "skip"}])
    assert twijfel_labeler.volgende_ongelabelde(str(pad), "signaal") is None
    assert twijfel_labeler.volgende_ongelabelde(str(tmp_path / "geen.jsonl"), "signaal") is None


def test_zet_label_op_alle_identieke_regels_en_behoudt_kapotte_regel(tmp_path):
    pad = tmp_path / "u.jsonl"
    pad.write_text(
        json.dumps({"text": "pion naar e4", "signaal": "kilte"}) + "\n"
        + "dit is geen json\n"
        + json.dumps({"text": "Pion naar e4 ", "signaal": "kilte"}) + "\n"
        + json.dumps({"text": "help", "signaal": "kilte"}) + "\n",
        encoding="utf-8",
    )
    aantal = twijfel_labeler.zet_label(str(pad), "pion naar e4", "neutraal")
    assert aantal == 2

    regels = pad.read_text(encoding="utf-8").splitlines()
    assert regels[1] == "dit is geen json"
    assert json.loads(regels[0])["label_kevin"] == "neutraal"
    assert json.loads(regels[2])["label_kevin"] == "neutraal"
    assert "label_kevin" not in json.loads(regels[3])
    assert not list(tmp_path.glob("*.tmp*"))


def test_zet_label_onbekende_zin_wijzigt_niets(tmp_path):
    pad = tmp_path / "u.jsonl"
    _schrijf_jsonl(pad, [{"text": "help", "signaal": "kilte"}])
    voor = pad.read_text(encoding="utf-8")
    assert twijfel_labeler.zet_label(str(pad), "bestaat niet", "neutraal") == 0
    assert pad.read_text(encoding="utf-8") == voor


def test_status_telt_per_unieke_zin(tmp_path):
    pad = tmp_path / "u.jsonl"
    _schrijf_jsonl(pad, [
        {"text": "a", "signaal": "kilte"},
        {"text": "a", "signaal": "kilte"},
        {"text": "b", "signaal": "kilte", "label_kevin": "neutraal"},
        {"text": "c", "signaal": "kilte", "label_auto": "waardering"},
        {"text": "c", "signaal": "kilte", "label_kevin": "skip"},
        {"text": "d", "signaal": "kilte", "label_auto": "focus"},
    ])
    assert twijfel_labeler.status(str(pad)) == {
        "regels": 6, "unieke_zinnen": 4,
        "ongelabeld": 1, "kevin": 1, "auto": 1, "skip": 1,
    }


def test_toegestane_labels(tmp_path):
    pad = tmp_path / "t.json"
    pad.write_text(json.dumps({"voorbeelden": [
        {"text": "x", "signaal": "kilte"},
        {"text": "y", "signaal": "neutraal"},
    ]}), encoding="utf-8")
    assert twijfel_labeler.toegestane_labels(str(pad), "signaal") == {"kilte", "neutraal"}
    assert twijfel_labeler.toegestane_labels(str(tmp_path / "geen.json"), "signaal") == set()


# ---------------------------------------------------------------
# microlearning.py -- automatisch label
# ---------------------------------------------------------------
@pytest.fixture
def micro(tmp_path):
    m = object.__new__(ml_module.MicroLearning)
    m._uncertain_path = str(tmp_path / "uncertain_signals.jsonl")
    m._hertraining_status_pad = str(tmp_path / "hertraining_status.json")
    m.HERTRAINING_DREMPEL = 10
    m.model = None
    return m


@pytest.mark.parametrize("zin, verwacht", [
    ("dank je, dat helpt echt", "waardering"),
    ("dit werkt niet, frustrerend", "frustratie"),
    ("wat bedoel je daarmee", "verwarring"),
    ("interessant, vertel meer", "interesse"),
    ("even niet storen nu", "focus"),
    ("niet interessant", None),
    ("dat helpt niet", None),
    ("ik ben niet geconcentreerd", None),
    ("dank je, maar dit werkt niet", None),
    ("stop daarmee", None),
    ("pion naar e4", None),
])
def test_auto_label(micro, zin, verwacht):
    assert micro._auto_label(zin) == verwacht


def test_twijfelgeval_krijgt_automatisch_label(micro):
    micro._log_uncertain("dank je, dat helpt echt", model_signaal="kilte",
                         marge=0.05, woordenlijst_signaal=["waardering"])
    regel = _lees_jsonl(micro._uncertain_path)[0]
    assert regel["label_auto"] == "waardering"
    assert regel["label_bron"] == "woordenlijst_strikt"
    assert "label_kevin" not in regel


def test_twijfelgeval_zonder_strikt_trefwoord_krijgt_geen_label(micro):
    micro._log_uncertain("pion naar e4", model_signaal="kilte",
                         marge=0.05, woordenlijst_signaal=[])
    assert "label_auto" not in _lees_jsonl(micro._uncertain_path)[0]


def test_auto_labels_tellen_mee_maar_kevin_skip_wint(micro):
    _schrijf_jsonl(micro._uncertain_path, [
        {"text": "a", "signaal": "kilte", "label_auto": "waardering"},
        {"text": "b", "signaal": "kilte", "label_kevin": "neutraal"},
        {"text": "c", "signaal": "kilte", "label_auto": "focus", "label_kevin": "skip"},
    ])
    assert micro._tel_gelabelde_twijfelzinnen() == 2


# ---------------------------------------------------------------
# train_classifier.py -- label_auto + label_kevin
# ---------------------------------------------------------------
def test_trainer_kevin_label_wint_van_auto_label(tmp_path, monkeypatch):
    pad = tmp_path / "uncertain_signals.jsonl"
    _schrijf_jsonl(pad, [
        {"text": "dank je", "signaal": "kilte", "label_auto": "waardering"},
        {"text": "top", "signaal": "kilte", "label_auto": "waardering", "label_kevin": "neutraal"},
        {"text": "wat bedoel je", "signaal": "kilte", "label_auto": "verwarring", "label_kevin": "skip"},
    ])
    monkeypatch.setattr(train_classifier, "UNCERTAIN_PAD", str(pad))

    resultaat = train_classifier._laad_uncertain_voorbeelden({"waardering", "neutraal", "verwarring"})
    assert {"text": "dank je", "signaal": "waardering"} in resultaat
    assert {"text": "top", "signaal": "neutraal"} in resultaat
    assert len(resultaat) == 2


# ---------------------------------------------------------------
# debug_commands.py -- 'label ...' end-to-end
# ---------------------------------------------------------------
class NepBus:
    def __init__(self):
        self.modules = {}

    def subscribe(self, *args, **kwargs):
        pass


class NepMicro:
    def __init__(self):
        self.checks = 0

    def _check_hertraining(self, bij_opstart):
        self.checks += 1


@pytest.fixture
def debug_omgeving(tmp_path, monkeypatch):
    monkeypatch.setattr(twijfel_labeler, "_root", lambda: tmp_path)

    (tmp_path / "identity" / "personality").mkdir(parents=True)
    (tmp_path / "modules" / "preferences").mkdir(parents=True)

    training = {"voorbeelden": [
        {"text": "x", "signaal": "neutraal"},
        {"text": "y", "signaal": "kilte"},
    ]}
    (tmp_path / "identity" / "personality" / "training_data.json").write_text(
        json.dumps(training), encoding="utf-8")
    _schrijf_jsonl(tmp_path / "identity" / "personality" / "uncertain_signals.jsonl", [
        {"text": "pion naar e4", "signaal": "kilte"},
        {"text": "pion naar e4", "signaal": "kilte"},
        {"text": "help", "signaal": "kilte"},
    ])

    micro = NepMicro()

    class NepLoader:
        loaded_modules = {"microlearning": micro}

    debug = DebugCommands(NepBus(), NepLoader())
    uncertain = tmp_path / "identity" / "personality" / "uncertain_signals.jsonl"
    return debug, micro, uncertain


def test_label_flow_toont_labelt_en_toont_volgende(debug_omgeving, capsys):
    debug, micro, uncertain = debug_omgeving

    debug.handle_debug_command({"text": "label signaal"})
    assert '"pion naar e4"' in capsys.readouterr().out

    debug.handle_debug_command({"text": "label signaal neutraal"})
    uitvoer = capsys.readouterr().out
    assert "2 regel(s) bijgewerkt" in uitvoer
    assert '"help"' in uitvoer

    labels = [r.get("label_kevin") for r in _lees_jsonl(uncertain)]
    assert labels == ["neutraal", "neutraal", None]
    assert micro.checks == 1


def test_label_onbekend_label_wordt_geweigerd(debug_omgeving, capsys):
    debug, micro, uncertain = debug_omgeving
    debug.handle_debug_command({"text": "label signaal"})
    capsys.readouterr()

    debug.handle_debug_command({"text": "label signaal neutrall"})
    assert "Onbekend label" in capsys.readouterr().out
    assert all("label_kevin" not in r for r in _lees_jsonl(uncertain))
    assert micro.checks == 0


def test_label_zonder_getoonde_zin(debug_omgeving, capsys):
    debug, micro, uncertain = debug_omgeving
    debug.handle_debug_command({"text": "label signaal neutraal"})
    assert "Typ eerst 'label signaal'" in capsys.readouterr().out
    assert micro.checks == 0


def test_label_skip_triggert_geen_hertraining(debug_omgeving, capsys):
    debug, micro, uncertain = debug_omgeving
    debug.handle_debug_command({"text": "label signaal"})
    debug.handle_debug_command({"text": "label signaal skip"})

    labels = [r.get("label_kevin") for r in _lees_jsonl(uncertain)]
    assert labels == ["skip", "skip", None]
    assert micro.checks == 0


def test_label_status(debug_omgeving, capsys):
    debug, micro, uncertain = debug_omgeving
    debug.handle_debug_command({"text": "label status"})
    uitvoer = capsys.readouterr().out
    assert "signaal: 2 unieke zinnen (3 regels)" in uitvoer
    assert "sentiment: 0 unieke zinnen (0 regels)" in uitvoer


def test_label_commandos_worden_herkend(debug_omgeving):
    debug, micro, uncertain = debug_omgeving
    assert debug.is_debug_command("label signaal")
    assert debug.is_debug_command("label status")
    assert debug.is_debug_command("Label Sentiment positief")
    assert not debug.is_debug_command("labels zijn handig")