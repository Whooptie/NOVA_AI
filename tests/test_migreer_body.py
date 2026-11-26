import json

from scripts.migreer_body_persistent import main


def test_migreert_en_bewaart_bak(tmp_path):
    bron = tmp_path / "body_persistent.json"
    bron.write_text(json.dumps({"bloos": 0.3, "maagd": {"vagina": True}}), encoding="utf-8")
    doel = tmp_path / "state.json"

    assert main(bron, doel) == 0

    data = json.loads(doel.read_text(encoding="utf-8"))["namespaces"]["body"]["data"]
    assert data["bloos"] == 0.3
    assert bron.exists()
    assert (tmp_path / "body_persistent.json.bak").exists()


def test_onbekende_sleutels_worden_overgeslagen(tmp_path, capsys):
    bron = tmp_path / "body_persistent.json"
    bron.write_text(json.dumps({"bloos": 0.1, "rommel": 1}), encoding="utf-8")
    doel = tmp_path / "state.json"

    assert main(bron, doel) == 0
    data = json.loads(doel.read_text(encoding="utf-8"))["namespaces"]["body"]["data"]
    assert "rommel" not in data
    assert "rommel" in capsys.readouterr().out


def test_geen_bron_geeft_1(tmp_path):
    assert main(tmp_path / "weg.json", tmp_path / "state.json") == 1