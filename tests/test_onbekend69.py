# tests/test_onbekend69.py
"""
Punt 69 -- Eerlijk "dat weet ik niet".

- ReasoningEngine.explain_causes(): onbekend ONDERWERP wordt eerlijk benoemd.
  Een bekend onderwerp (of een onderwerp met gevolgen) gedraagt zich als voorheen.
  Een onbekend DOEL blijft ongewijzigd (doelen hoeven geen concept te zijn).
- tools/run_benchmark.py: vlag --met-antwoordlaag en ANTWOORDLAAG_MODULES,
  en een vaste random-seed per vraag in Keten.draai().

Isolatie: ConceptStore op tmp_path, nooit de echte data/concepts.json.
Uitvoeren: pytest tests/test_onbekend69.py -v
"""

import importlib.util
from pathlib import Path

import pytest

from core.semantic import (
    ConceptStore,
    SenseEngine,
    RelationEngine,
    ReasoningEngine,
)


@pytest.fixture
def engines(tmp_path):
    store = ConceptStore(
        concepts_file=str(tmp_path / "concepts.json"),
        log_file=str(tmp_path / "concepts.jsonl"),
    )
    se = SenseEngine(store)
    re_ = RelationEngine(store, se)
    rs = ReasoningEngine(store, re_)
    return se, re_, rs


def _causes(se, re_, oorzaak, gevolg):
    if not se.get_senses(oorzaak):
        se.add_sense(oorzaak, "testdefinitie", source="user")
    sense_id = se.get_senses(oorzaak)[0]["sense_id"]
    re_.add_relation(oorzaak, "causes", gevolg, sense_id=sense_id)


class TestOnbekendOnderwerp:
    def test_onbekend_onderwerp_wordt_eerlijk_benoemd(self, engines):
        _, _, rs = engines
        tekst = rs.explain_causes("blorf", "regen")
        assert tekst == "Ik ken 'blorf' niet, dus ik kan dat niet beoordelen."

    def test_bekend_onderwerp_zonder_pad_blijft_kaal(self, engines):
        se, _, rs = engines
        se.add_sense("ei", "testdefinitie", source="user")
        tekst = rs.explain_causes("ei", "server")
        assert tekst == "Ik kan niet bewijzen dat 'ei' leidt tot 'server'."

    def test_bekend_onderwerp_met_gevolgen_geeft_alternatief(self, engines):
        se, re_, rs = engines
        _causes(se, re_, "regen", "modder")
        tekst = rs.explain_causes("regen", "zonneschijn")
        assert "kan niet bewijzen" in tekst
        assert "Ik ken 'regen' niet" not in tekst

    def test_onbekend_doel_blijft_ongewijzigd(self, engines):
        # Doelen hoeven geen concept te zijn: geen "Ik ken ... niet" voor het doel.
        se, re_, rs = engines
        _causes(se, re_, "regen", "modder")
        tekst = rs.explain_causes("regen", "glorbix")
        assert "Ik ken 'glorbix' niet" not in tekst
        assert "kan niet bewijzen" in tekst

    def test_directe_oorzaak_werkt_nog(self, engines):
        se, re_, rs = engines
        _causes(se, re_, "regen", "modder")
        assert rs.explain_causes("regen", "modder") == "Ja, regen veroorzaakt modder."


class TestBenchmarkAntwoordlaag:
    @pytest.fixture
    def bench(self):
        pad = Path(__file__).resolve().parent.parent / "tools" / "run_benchmark.py"
        spec = importlib.util.spec_from_file_location("run_benchmark_69", pad)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_antwoordlaag_modules_bestaan_als_bestand(self, bench):
        root = Path(__file__).resolve().parent.parent
        assert bench.ANTWOORDLAAG_MODULES
        for naam in bench.ANTWOORDLAAG_MODULES:
            assert (root / (naam.replace(".", "/") + ".py")).exists(), naam

    def test_antwoordlaag_bevat_de_vier_lagen(self, bench):
        assert set(bench.ANTWOORDLAAG_MODULES) == {
            "modules.chat.response_pipeline",
            "modules.chat.chat_response_engine",
            "modules.chat.expression_injector",
            "modules.knowledge.wikipedia_teacher",
        }

    def test_vlag_staat_in_de_cli(self):
        pad = Path(__file__).resolve().parent.parent / "tools" / "run_benchmark.py"
        bron = pad.read_text(encoding="utf-8")
        assert '"--met-antwoordlaag"' in bron
        assert "args.met_antwoordlaag" in bron

    def test_keten_zet_vaste_seed_per_vraag(self):
        pad = Path(__file__).resolve().parent.parent / "tools" / "run_benchmark.py"
        bron = pad.read_text(encoding="utf-8")
        assert 'random.seed(f"benchmark:{vraag}")' in bron