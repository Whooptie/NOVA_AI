"""
Tests voor modules/debug/audit_zoeken.py (het debug-commando `audit`).

Isolatie: elke test schrijft een eigen concepts.json in tmp_path.
Er wordt NOOIT de echte data/concepts.json aangeraakt.
"""

import json
from datetime import datetime

import pytest

from modules.debug import audit_zoeken as az

NU = datetime(2026, 11, 2, 12, 0, 0)


@pytest.fixture
def concepts_pad(tmp_path):
    data = {
        "hond": {
            "senses": [
                {
                    "sense_id": "hond#1",
                    "definition": "een huisdier dat blaft",
                    "source": "user",
                    "status": "confirmed",
                    "relations": [
                        {"type": "is_a", "target": "dier", "source": "user", "status": "confirmed"},
                        {"type": "is_a", "target": "meubel", "source": "auto", "status": "rejected"},
                    ],
                    "audit_log": [
                        {"event": "sense_created", "timestamp": "2026-10-01T10:00:00", "source": "user"},
                        {"event": "relation_rejected", "timestamp": "2026-10-28T09:30:00",
                         "reason": "onzin", "target": "meubel"},
                    ],
                }
            ],
            "audit_log": [
                {"event": "concept_created", "timestamp": "2026-10-01T09:59:00", "source": "user"}
            ],
        },
        "narwal": {
            "senses": [
                {
                    "sense_id": "narwal#1",
                    "definition": "een walvisachtige met een slagtand",
                    "source": "wikipedia",
                    "status": "unverified",
                    "relations": [
                        {"type": "is_a", "target": "walvis", "source": "wikipedia", "status": "unverified"}
                    ],
                    "audit_log": [
                        {"event": "sense_created", "timestamp": "2026-08-01T10:00:00", "source": "wikipedia"},
                        {"event": "sense_rejected", "timestamp": "2026-08-02T10:00:00"},
                        {"event": "sense_upgrade"},  # bewust zonder tijdstip
                    ],
                }
            ],
        },
        "bron": {  # een concept dat zo heet als een sleutelwoord
            "senses": [],
            "audit_log": [{"event": "concept_created", "timestamp": "2026-10-15T08:00:00"}],
        },
    }
    pad = tmp_path / "concepts.json"
    pad.write_text(json.dumps(data), encoding="utf-8")
    return pad


def run(argumenten, pad):
    return az.voer_audit_uit(argumenten, concepts_pad=pad, nu=NU)


class TestHulpEnFouten:
    def test_zonder_argumenten_geeft_hulp(self, concepts_pad):
        assert "Audit-log doorzoeken" in run("", concepts_pad)

    def test_ontbrekend_bestand_crasht_niet(self, tmp_path):
        antwoord = run("hond", tmp_path / "bestaat_niet.json")
        assert "niet gevonden" in antwoord

    def test_kapot_bestand_crasht_niet(self, tmp_path):
        pad = tmp_path / "kapot.json"
        pad.write_text("{ dit is geen json", encoding="utf-8")
        assert "kon niet gelezen worden" in run("hond", pad)

    def test_kapotte_entries_worden_overgeslagen(self, tmp_path):
        pad = tmp_path / "c.json"
        pad.write_text(json.dumps({
            "x": {"senses": ["geen dict", {"audit_log": ["ook geen dict", {"event": "ok"}]}],
                  "audit_log": "geen lijst"},
            "y": "geen concept",
        }), encoding="utf-8")
        assert "ok" in run("x", pad)


class TestWoord:
    def test_toont_concept_en_sense_regels_nieuwste_eerst(self, concepts_pad):
        antwoord = run("hond", concepts_pad)
        assert "3 regels" in antwoord
        assert antwoord.index("relation_rejected") < antwoord.index("sense_created")

    def test_onbekend_woord(self, concepts_pad):
        assert "ken het woord 'kat' niet" in run("kat", concepts_pad)

    def test_hoofdletters_maken_niet_uit(self, concepts_pad):
        assert "Audit-log van 'hond'" in run("HOND", concepts_pad)

    def test_woord_dat_een_sleutelwoord_is(self, concepts_pad):
        assert "Audit-log van 'bron'" in run("woord bron", concepts_pad)


class TestLaatste:
    def test_standaard_en_begrensd(self, concepts_pad):
        assert "nieuwste audit-regels" in run("laatste", concepts_pad)
        assert "De 2 nieuwste" in run("laatste 2", concepts_pad)

    def test_ongeldig_getal_valt_terug_op_standaard(self, concepts_pad):
        assert "nieuwste" in run("laatste abc", concepts_pad)


class TestAfgewezen:
    def test_binnen_periode(self, concepts_pad):
        antwoord = run("afgewezen 30", concepts_pad)
        assert "relation_rejected" in antwoord
        assert "sense_rejected" not in antwoord  # augustus valt buiten 30 dagen

    def test_ruimere_periode_pakt_ook_oudere(self, concepts_pad):
        assert "sense_rejected" in run("afgewezen 365", concepts_pad)

    def test_zonder_tijd_wordt_gemeld(self, concepts_pad):
        # 'sense_upgrade' zonder tijdstip is geen afwijzing, dus geen melding
        assert "zonder tijdstip" not in run("afgewezen 30", concepts_pad)

    def test_geen_resultaat(self, concepts_pad):
        assert "Geen afwijzingen" in run("afgewezen 1", concepts_pad)


class TestEchtFormaat:
    """Het formaat zoals Nova het echt wegschrijft: 'event_type' i.p.v. 'event'."""

    @pytest.fixture
    def echt_pad(self, tmp_path):
        data = {
            "sorteer": {
                "senses": [{
                    "sense_id": "sorteer#1",
                    "audit_log": [{
                        "timestamp": "2026-10-31T21:30:00",
                        "source": "user",
                        "event_type": "sense_rejected",
                        "old_value": "unverified",
                        "new_value": "rejected",
                    }],
                }],
            },
        }
        pad = tmp_path / "echt.json"
        pad.write_text(json.dumps(data), encoding="utf-8")
        return pad

    def test_afgewezen_vindt_event_type(self, echt_pad):
        antwoord = run("afgewezen 30", echt_pad)
        assert "sense_rejected" in antwoord
        assert "?" not in antwoord

    def test_event_filter_vindt_event_type(self, echt_pad):
        assert "sense_rejected" in run("event rejected", echt_pad)


class TestEvent:
    def test_filtert_op_stukje_eventnaam(self, concepts_pad):
        antwoord = run("event created", concepts_pad)
        assert "concept_created" in antwoord and "sense_created" in antwoord
        assert "rejected" not in antwoord

    def test_met_dagen(self, concepts_pad):
        antwoord = run("event created 20", concepts_pad)
        assert "concept_created" in antwoord
        assert "narwal" not in antwoord  # augustus valt buiten 20 dagen

    def test_zonder_argument(self, concepts_pad):
        assert "Geef een stukje" in run("event", concepts_pad)

    def test_zonder_tijdstip_wordt_gemeld_bij_periode(self, concepts_pad):
        assert "zonder tijdstip" in run("event upgrade 365", concepts_pad)


class TestBron:
    def test_vindt_sense_en_relatie(self, concepts_pad):
        antwoord = run("bron wikipedia", concepts_pad)
        assert "narwal#1  betekenis" in antwoord
        assert "is_a walvis" in antwoord
        assert "hond" not in antwoord

    def test_statusfilter(self, concepts_pad):
        antwoord = run("bron auto rejected", concepts_pad)
        assert "status 'rejected'" in antwoord
        assert "is_a meubel" in antwoord
        antwoord = run("bron user confirmed", concepts_pad)
        assert "is_a dier" in antwoord
        assert "meubel" not in antwoord

    def test_statusfilter_zonder_treffer(self, concepts_pad):
        assert "Niets gevonden" in run("bron wikipedia rejected", concepts_pad)

    def test_lijst_toont_woord_niet_dubbel(self, concepts_pad):
        antwoord = run("laatste 20", concepts_pad)
        regel = next(r for r in antwoord.splitlines() if "concept_created" in r and r.startswith("hond"))
        assert regel.count("hond") == 1

    def test_onbekende_bron(self, concepts_pad):
        assert "Niets gevonden" in run("bron bestaatniet", concepts_pad)

    def test_zonder_argument(self, concepts_pad):
        assert "Geef een bron" in run("bron", concepts_pad)


class TestAfkappenEnTijd:
    def test_meer_dan_max_regels(self, tmp_path):
        entries = [{"event": "e", "timestamp": f"2026-10-{(i % 28) + 1:02d}T10:00:00"} for i in range(40)]
        pad = tmp_path / "c.json"
        pad.write_text(json.dumps({"w": {"senses": [], "audit_log": entries}}), encoding="utf-8")
        assert "en nog 15 meer" in run("w", pad)

    @pytest.mark.parametrize("waarde", ["2026-10-24T14:03:11", "2026-10-24T14:03:11Z",
                                          "2026-10-24T14:03:11+02:00", 1792000000])
    def test_tijdformaten(self, waarde):
        assert az._parse_tijd(waarde) is not None

    def test_onzin_tijd_geeft_none(self):
        assert az._parse_tijd("morgen") is None