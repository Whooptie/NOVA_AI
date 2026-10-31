# tests/test_run_benchmark.py
"""
Tests voor tools/run_benchmark.py zelf: de beoordeling, de placeholders,
de willekeurige ketens en het inladen van cases. Geen mini-Nova nodig.
"""
import datetime
import importlib.util
import json
from pathlib import Path

import pytest

RUNNER = Path(__file__).resolve().parents[1] / "tools" / "run_benchmark.py"
_spec = importlib.util.spec_from_file_location("run_benchmark_onder_test", RUNNER)
rb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rb)


def antwoord(tekst, event="layer4_response"):
    return [("raw_user_message", {"text": "vraag"}), (event, {"text": tekst})]


# ---------------------------------------------------------
# bevat_woord() en antwoord_tekst()
# ---------------------------------------------------------
def test_bevat_woord_enkel_hele_woorden():
    assert rb.bevat_woord("het antwoord is 84.", "84")
    assert rb.bevat_woord("ja, een hond is een dier", "ja")
    assert not rb.bevat_woord("jammer genoeg", "ja")
    assert not rb.bevat_woord("het is 184", "84")


def test_bevat_woord_negeert_hoofdletters_van_het_zoekwoord():
    assert rb.bevat_woord("het is maandag", "Maandag")


def test_antwoord_tekst_enkel_antwoord_events_en_kleine_letters():
    events = [
        ("intent_math", {"expression": "12 * 7"}),
        ("layer4_response", {"text": "Het Antwoord is 84"}),
        ("chat_response", {"text": "Nog iets"}),
    ]
    assert rb.antwoord_tekst(events) == "het antwoord is 84 nog iets"


def test_antwoord_tekst_zonder_text_veld_pakt_alle_tekstvelden():
    events = [("chat_response", {"bericht": "Hoi", "extra": {"x": "daar"}})]
    assert rb.antwoord_tekst(events) == "hoi daar"


# ---------------------------------------------------------
# beoordeel(): events
# ---------------------------------------------------------
def test_moet_event_geslaagd_en_gefaald():
    case = {"moet_event": ["intent_math"]}
    assert rb.beoordeel(case, [("intent_math", {})], None, 1)[0] == "geslaagd"
    status, reden = rb.beoordeel(case, [("intent_fallback", {})], None, 1)
    assert status == "gefaald"
    assert "intent_fallback" in reden


def test_moet_event_is_prefix_match():
    case = {"moet_event": ["intent_relation"]}
    assert rb.beoordeel(case, [("intent_relation_check", {})], None, 1)[0] == "geslaagd"


def test_mag_event_niet():
    case = {"mag_event_niet": ["intent_effects"]}
    assert rb.beoordeel(case, [("intent_causes", {})], None, 1)[0] == "geslaagd"
    assert rb.beoordeel(case, [("intent_effects", {})], None, 1)[0] == "gefaald"


def test_fout_wint_van_alles():
    assert rb.beoordeel({"moet_event": ["x"]}, [], "ZeroDivisionError: x", 2) == (
        "fout", "ZeroDivisionError: x")


def test_case_zonder_controles_is_niet_meetbaar():
    assert rb.beoordeel({"id": "x"}, [], None, 2)[0] == "niet_meetbaar"


# ---------------------------------------------------------
# beoordeel(): tekstcontroles
# ---------------------------------------------------------
def test_moet_bevatten_een_van():
    case = {"moet_bevatten_een_van": ["84", "vierentachtig"]}
    assert rb.beoordeel(case, antwoord("dat is 84"), None, 2)[0] == "geslaagd"
    assert rb.beoordeel(case, antwoord("dat is 85"), None, 2)[0] == "gefaald"


def test_moet_bevatten_alle_vraagt_alle_woorden():
    case = {"moet_bevatten_alle": ["28", "maart"]}
    assert rb.beoordeel(case, antwoord("pasen is op 28 maart 2027"), None, 2)[0] == "geslaagd"
    status, reden = rb.beoordeel(case, antwoord("pasen is op 28 april"), None, 2)
    assert status == "gefaald"
    assert "maart" in reden


def test_moet_overeenkomen_een_van_regex():
    case = {"moet_overeenkomen_een_van": [r"\d{1,2}\s*[:.hu]\s*\d{2}"]}
    assert rb.beoordeel(case, antwoord("het is 14:35"), None, 3)[0] == "geslaagd"
    assert rb.beoordeel(case, antwoord("het is laat"), None, 3)[0] == "gefaald"


def test_ongeldige_regex_is_een_duidelijke_fout_geen_crash():
    case = {"moet_overeenkomen_een_van": ["(onafgesloten"]}
    status, reden = rb.beoordeel(case, antwoord("tekst"), None, 3)
    assert status == "gefaald"
    assert "ongeldige" in reden


def test_mag_niet_bevatten():
    case = {"mag_niet_bevatten": ["ja"]}
    assert rb.beoordeel(case, antwoord("nee, dat klopt niet"), None, 2)[0] == "geslaagd"
    assert rb.beoordeel(case, antwoord("ja, zeker"), None, 2)[0] == "gefaald"


def test_niveau1_tekstcontrole_zonder_antwoord_is_niet_meetbaar():
    case = {"moet_bevatten_een_van": ["84"]}
    assert rb.beoordeel(case, [], None, 1)[0] == "niet_meetbaar"


def test_niveau1_event_geslaagd_met_open_antwoordcontrole():
    case = {"moet_event": ["intent_math"], "moet_bevatten_een_van": ["84"]}
    assert rb.beoordeel(case, [("intent_math", {})], None, 1) == ("geslaagd", rb.ANTWOORD_OPEN)


def test_niveau2_tekstcontrole_zonder_antwoord_is_gefaald():
    case = {"moet_bevatten_een_van": ["84"]}
    status, reden = rb.beoordeel(case, [], None, 2)
    assert status == "gefaald"
    assert "geen antwoord" in reden


# ---------------------------------------------------------
# niveau 3: extra controles en ontbrekende modules
# ---------------------------------------------------------
def test_niveau3_controles_gelden_niet_op_niveau_2():
    case = {"moet_event": ["intent_math"], "niveau3": {"moet_bevatten_een_van": ["84"]}}
    events = [("intent_math", {})]
    assert rb.beoordeel(case, events, None, 2)[0] == "geslaagd"
    assert rb.beoordeel(case, events, None, 3)[0] == "gefaald"


def test_niveau3_overschrijft_dezelfde_sleutel():
    case = {"moet_bevatten_een_van": ["oud"], "niveau3": {"moet_bevatten_een_van": ["nieuw"]}}
    assert rb.beoordeel(case, antwoord("oud"), None, 2)[0] == "geslaagd"
    assert rb.beoordeel(case, antwoord("oud"), None, 3)[0] == "gefaald"
    assert rb.beoordeel(case, antwoord("nieuw"), None, 3)[0] == "geslaagd"


def test_niveau3_ontbrekende_module_maakt_niet_meetbaar_geen_gefaald():
    case = {"moet_event": ["intent_math"], "niveau3": {"moet_bevatten_een_van": ["84"]}}
    status, reden = rb.beoordeel(
        case, [("intent_math", {})], None, 3, {"modules.math.math": "ImportError: x"})
    assert status == "niet_meetbaar"
    assert "modules.math.math" in reden


def test_niveau3_ontbrekende_module_maar_event_faalt_blijft_gefaald():
    case = {"moet_event": ["intent_math"], "niveau3": {"moet_bevatten_een_van": ["84"]}}
    status, _ = rb.beoordeel(case, [("intent_fallback", {})], None, 3, {"modules.math.math": "x"})
    assert status == "gefaald"


def test_niveau3_ontbrekende_module_maar_antwoord_aanwezig_wordt_gewoon_beoordeeld():
    case = {"niveau3": {"moet_bevatten_een_van": ["84"]}}
    assert rb.beoordeel(case, antwoord("84"), None, 3, {"modules.time.zone": "x"})[0] == "geslaagd"


# ---------------------------------------------------------
# placeholders
# ---------------------------------------------------------
def test_placeholders_weekdagen():
    zaterdag = datetime.datetime(2026, 10, 31, 12, 0)  # 31 oktober 2026 is een zaterdag
    case = {
        "vraag": "welke dag is het morgen",
        "moet_bevatten_een_van": ["$morgen_weekdag"],
        "niveau3": {"moet_bevatten_een_van": ["$vandaag_weekdag", "$overmorgen_weekdag"]},
    }
    nieuw = rb.los_placeholders_op(case, zaterdag)
    assert nieuw["moet_bevatten_een_van"] == ["zondag"]
    assert nieuw["niveau3"]["moet_bevatten_een_van"] == ["zaterdag", "maandag"]
    assert nieuw["vraag"] == "welke dag is het morgen"


def test_placeholders_week_loopt_rond():
    zondag = datetime.datetime(2026, 11, 1, 9, 0)
    nieuw = rb.los_placeholders_op({"x": ["$morgen_weekdag", "$overmorgen_weekdag"]}, zondag)
    assert nieuw["x"] == ["maandag", "dinsdag"]


def test_placeholders_onbekende_waarden_blijven_staan_en_origineel_blijft_heel():
    case = {"x": ["$onbekend", "gewoon"]}
    nieuw = rb.los_placeholders_op(case, datetime.datetime(2026, 10, 31))
    assert nieuw == case
    assert nieuw is not case


# ---------------------------------------------------------
# willekeurige ketens
# ---------------------------------------------------------
def _sense(naam, *relaties):
    return {
        "sense_id": f"{naam}#1",
        "definition": "x",
        "status": "confirmed",
        "relations": [
            {"type": "is_a", "target": doel, "status": status} for doel, status in relaties
        ],
    }


@pytest.fixture
def concepts_pad(tmp_path):
    data = {
        "hond": {"senses": [_sense("hond", ("zoogdier", "confirmed"))]},
        "kat": {"senses": [_sense("kat", ("zoogdier", "confirmed"))]},
        "zoogdier": {"senses": [_sense("zoogdier", ("dier", "confirmed"))]},
        "dier": {"senses": [_sense("dier")]},
        # onbevestigde eerste schakel telt niet mee
        "slang": {"senses": [_sense("slang", ("reptiel", "unverified"))]},
        "reptiel": {"senses": [_sense("reptiel", ("dier", "confirmed"))]},
        # afgewezen schakel telt niet mee
        "tafel": {"senses": [_sense("tafel", ("meubel", "rejected"))]},
        "meubel": {"senses": [_sense("meubel", ("ding", "confirmed"))]},
        # kringetje a -> b -> a telt niet mee
        "x": {"senses": [_sense("x", ("y", "confirmed"))]},
        "y": {"senses": [_sense("y", ("x", "confirmed"))]},
    }
    pad = tmp_path / "concepts.json"
    pad.write_text(json.dumps(data), encoding="utf-8")
    return str(pad)


def test_ketenvragen_alleen_bevestigde_tweestaps_ketens(concepts_pad):
    cases = rb.maak_ketenvragen(concepts_pad, 10, seed=1)
    vragen = {c["vraag"] for c in cases}
    assert vragen == {"is een hond een dier", "is een kat een dier"}


def test_ketenvragen_hebben_de_juiste_vorm(concepts_pad):
    case = rb.maak_ketenvragen(concepts_pad, 1, seed=1)[0]
    assert case["categorie"] == rb.CATEGORIE_KETENS
    assert case["id"] == "ketting-01"
    assert case["moet_event"] == ["intent_relation_check"]
    assert case["moet_bevatten_een_van"] == ["ja"]


def test_ketenvragen_zelfde_seed_zelfde_vragen(concepts_pad):
    a = rb.maak_ketenvragen(concepts_pad, 1, seed=7)
    b = rb.maak_ketenvragen(concepts_pad, 1, seed=7)
    assert [c["vraag"] for c in a] == [c["vraag"] for c in b]


def test_ketenvragen_aantal_wordt_begrensd(concepts_pad):
    assert len(rb.maak_ketenvragen(concepts_pad, 1, seed=1)) == 1
    assert len(rb.maak_ketenvragen(concepts_pad, 99, seed=1)) == 2


def test_ketenvragen_nul_of_ontbrekend_bestand(tmp_path, concepts_pad):
    assert rb.maak_ketenvragen(concepts_pad, 0, seed=1) == []
    assert rb.maak_ketenvragen(str(tmp_path / "bestaat_niet.json"), 5, seed=1) == []


# ---------------------------------------------------------
# cases inladen en score
# ---------------------------------------------------------
def test_laad_cases_dict_en_lijstvorm_met_categoriefilter(tmp_path):
    cases = [
        {"id": "a", "categorie": "x", "vraag": "1"},
        {"id": "b", "categorie": "y", "vraag": "2"},
    ]
    p1 = tmp_path / "dict.json"
    p1.write_text(json.dumps({"cases": cases}), encoding="utf-8")
    p2 = tmp_path / "lijst.json"
    p2.write_text(json.dumps(cases), encoding="utf-8")
    assert [c["id"] for c in rb.laad_cases(str(p1), None)] == ["a", "b"]
    assert [c["id"] for c in rb.laad_cases(str(p2), "y")] == ["b"]


def test_score():
    assert rb._score({"geslaagd": 3, "gefaald": 1, "fout": 0, "niet_meetbaar": 5}) == "75%"
    assert rb._score({"geslaagd": 0, "gefaald": 0, "fout": 0, "niet_meetbaar": 4}) == "-"