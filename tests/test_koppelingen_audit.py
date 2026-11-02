# tests/test_koppelingen_audit.py
# Test scripts/koppelingen_audit.py op kleine, tijdelijke nepprojecten (tmp_path).
# Raakt nooit de echte code of data aan.

import importlib.util
from pathlib import Path

PAD = Path(__file__).resolve().parent.parent / "scripts" / "koppelingen_audit.py"
_spec = importlib.util.spec_from_file_location("koppelingen_audit", PAD)
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)


def maak_project(tmp_path, bestanden):
    for naam, inhoud in bestanden.items():
        p = tmp_path / naam
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(inhoud, encoding="utf-8")
    return tmp_path


BRON_CHECK_ZONDER_POORT = '''
class A:
    def check_iets(self):
        self.event_bus.publish("layer4_response", {"text": "hoi"})
'''

BRON_CHECK_MET_POORT = '''
class A:
    def check_iets(self):
        if not self.ctx.can_interrupt():
            return
        self.event_bus.publish("layer4_response", {"text": "hoi"})
'''

BRON_REACTIEF = '''
import threading
class A:
    def on_vraag(self, data):
        self.event_bus.publish("chat_response", {"text": "antwoord"})
    def start(self):
        threading.Thread(target=self.on_vraag).start()
'''

BRON_THREAD = '''
import threading
class A:
    def start(self):
        threading.Thread(target=self.x).start()
'''


# ---- bevinding 1: proactief zonder Layer 5-poort ----
def test_check_zonder_poort_wordt_gevonden(tmp_path):
    maak_project(tmp_path, {"modules/a.py": BRON_CHECK_ZONDER_POORT})
    uit = audit.bevindingen(audit.verzamel(tmp_path))
    assert uit["proactief_zonder_layer5"] == ["modules/a.py (check_iets)"]


def test_check_met_can_interrupt_is_in_orde(tmp_path):
    maak_project(tmp_path, {"modules/a.py": BRON_CHECK_MET_POORT})
    uit = audit.bevindingen(audit.verzamel(tmp_path))
    assert uit["proactief_zonder_layer5"] == []


def test_reactieve_handler_telt_niet_als_proactief(tmp_path):
    maak_project(tmp_path, {"modules/a.py": BRON_REACTIEF})
    uit = audit.bevindingen(audit.verzamel(tmp_path))
    assert uit["proactief_zonder_layer5"] == []


def test_main_py_wordt_niet_gemeld(tmp_path):
    maak_project(tmp_path, {"main.py": BRON_CHECK_ZONDER_POORT + BRON_THREAD})
    uit = audit.bevindingen(audit.verzamel(tmp_path))
    assert uit["proactief_zonder_layer5"] == []
    assert uit["thread_zonder_shutdown"] == []


# ---- bevinding 2: thread zonder shutdown ----
def test_thread_zonder_shutdown_wordt_gevonden(tmp_path):
    maak_project(tmp_path, {"modules/a.py": BRON_THREAD})
    uit = audit.bevindingen(audit.verzamel(tmp_path))
    assert uit["thread_zonder_shutdown"] == ["modules/a.py"]


def test_on_shutdown_telt_als_shutdown(tmp_path):
    bron = BRON_THREAD + "\n    def _on_shutdown(self):\n        pass\n"
    maak_project(tmp_path, {"core/memory.py": bron})
    uit = audit.bevindingen(audit.verzamel(tmp_path))
    assert uit["thread_zonder_shutdown"] == []


# ---- bevinding 5: dynamische intent_*-luisteraars ----
def test_intent_luisteraar_wordt_apart_gehouden(tmp_path):
    bron = ('class A:\n'
            '    def __init__(self, bus):\n'
            '        bus.subscribe("intent_iets", self.h)\n'
            '        bus.subscribe("echt_dood", self.h)\n')
    maak_project(tmp_path, {"modules/a.py": bron})
    uit = audit.bevindingen(audit.verzamel(tmp_path))
    assert uit["luisteraars_dynamisch"] == ["intent_iets"]
    assert uit["luisteraars_zonder_zender"] == ["echt_dood"]


# ---- identity/ = Layer 6 ----
def test_identity_bestand_telt_als_layer_6(tmp_path):
    maak_project(tmp_path, {"identity/foo.py": "x = 1\n"})
    infos = audit.verzamel(tmp_path)
    assert audit.lagen_van(infos["identity/foo.py"])[2] == 6


# ---- bevinding 7: bestanden zonder test ----
def test_bestand_zonder_test_wordt_gevonden(tmp_path):
    maak_project(tmp_path, {"modules/a.py": "x = 1\n", "modules/b.py": "y = 1\n"})
    uit = audit.bevindingen(audit.verzamel(tmp_path), tests_tekst="from modules.a import x")
    assert uit["zonder_test"] == ["modules/b.py"]


def test_zonder_tests_map_wordt_bevinding_overgeslagen(tmp_path):
    maak_project(tmp_path, {"modules/a.py": "x = 1\n"})
    assert audit.lees_tests(tmp_path) is None
    uit = audit.bevindingen(audit.verzamel(tmp_path), tests_tekst=None)
    assert uit["zonder_test"] is None


def test_lees_tests_houdt_enkel_projectimports(tmp_path):
    maak_project(tmp_path, {
        "tests/test_a.py": "import math\nfrom modules.a import x\n    from core.b import y\n",
        "tests/manual_demo.py": "from modules.c import z\n",
        "tests/manual/test_d.py": "from modules.d import z\n",
    })
    tekst = audit.lees_tests(tmp_path)
    assert "modules.a" in tekst and "core.b" in tekst
    assert "import math" not in tekst
    assert "modules.c" not in tekst and "modules.d" not in tekst


# ---- rapport ----
def test_rapport_draait_met_en_zonder_tests(tmp_path):
    maak_project(tmp_path, {"identity/foo.py": "x = 1\n", "modules/a.py": "x = 1\n"})
    infos = audit.verzamel(tmp_path)
    assert "7a." not in audit.maak_rapport(infos)
    rapport = audit.maak_rapport(infos, tests_tekst="")
    assert "7a." in rapport and "identity/foo.py" in rapport


# ---- bevinding 3: topics uit een intent-tabel ----
def test_topics_uit_intent_tabel_worden_gezien(tmp_path):
    router = ('class R:\n'
              '    def _tabel(self):\n'
              '        return [("body", self.detect_body), ("greeting", self.detect_greeting)]\n')
    emergence = ('class E:\n'
                 '    def __init__(self):\n'
                 '        self._topic_naam_labels = {"greeting": "groeten"}\n')
    maak_project(tmp_path, {"core/intent_router.py": router,
                            "modules/experimental/emergence_engine.py": emergence})
    uit = audit.bevindingen(audit.verzamel(tmp_path))
    assert uit["topics_zonder_label"] == ["body"]


def test_gewone_tuples_tellen_niet_als_topic(tmp_path):
    router = ('class R:\n'
              '    def _x(self):\n'
              '        return [("a", 5), ("b", self.iets_anders)]\n')
    emergence = ('class E:\n'
                 '    def __init__(self):\n'
                 '        self._topic_naam_labels = {}\n')
    maak_project(tmp_path, {"core/intent_router.py": router,
                            "modules/experimental/emergence_engine.py": emergence})
    uit = audit.bevindingen(audit.verzamel(tmp_path))
    assert uit["topics_zonder_label"] == []