# tests/test_emergence_screen_focus.py
"""
Pytest-suite voor punt 17 (nova_state.md, 15 september 2026):
EmergenceEngine.analyze_screen_focus() + _formuleer_scherm_focus().

Koppelt context_manager.py's "screen_focus"-veld (13 sept 2026) aan
Layer 7 als vijfde insight-type. Test dekt:
- alle voorwaarden die GEEN insight mogen opleveren (elk apart)
- het gelukkige pad (insight + geformuleerde tekst)
- de whitelist-bugfix (SCHERM_FOCUS_ACTIVITEITEN i.p.v. de verkeerde
  INSIGHT_WAARDIGE_ACTIVITEITEN, ontdekt tijdens live-test 15 sept 2026)
- dat analyze_meta_patterns() het nieuwe insight-type meeneemt

Tmp_path-isolatie: EmergenceEngine.__init__() doet file-I/O
(insight_feedback.json, emergence_topic_cooldown_state.json via
get_project_root(__file__)) -- module_onder_test.get_project_root
wordt daarom gemonkeypatcht naar tmp_path, zelfde conventie als de
rest van de testsuite.
"""

import pytest

from modules.experimental import emergence_engine as module_onder_test
from modules.experimental.emergence_engine import EmergenceEngine


class DummyEventBus:
    """
    Minimale EventBus-stand-in. EmergenceEngine.__init__() roept
    self.event_bus.subscribe("*", ...) aan zodra layers een dict is --
    subscribe() moet dus bestaan, ook al gebruiken deze tests hem niet
    inhoudelijk.
    """

    def __init__(self):
        self.subscribed = []
        self.published = []

    def subscribe(self, event_type, handler):
        self.subscribed.append((event_type, handler))

    def publish(self, event_type, data):
        self.published.append((event_type, data))


class FakeContextManager:
    """Stand-in voor context_manager.py -- retourneert een vaste ctx-dict."""

    def __init__(self, ctx=None, raise_on_get_current=False):
        self._ctx = ctx or {}
        self._raise = raise_on_get_current

    def get_current(self):
        if self._raise:
            raise RuntimeError("gesimuleerde storing in context_manager")
        return self._ctx


@pytest.fixture
def make_engine(tmp_path, monkeypatch):
    """
    Fabriek-fixture: geeft een functie terug waarmee een test een
    EmergenceEngine kan bouwen met een specifieke context_manager,
    volledig geïsoleerd in tmp_path (geen echte data/-bestanden).
    """
    monkeypatch.setattr(module_onder_test, "get_project_root", lambda f: tmp_path)

    def _maak(context_manager=None):
        layers = {}
        if context_manager is not None:
            layers["context_manager"] = context_manager
        bus = DummyEventBus()
        engine = EmergenceEngine(event_bus=bus, layers=layers)
        return engine, bus

    return _maak


# ---------------------------------------------------------------------
# Voorwaarden die GEEN insight mogen opleveren
# ---------------------------------------------------------------------

def test_geen_context_manager_geeft_geen_insight(make_engine):
    engine, _ = make_engine(context_manager=None)
    assert engine.analyze_screen_focus() is None


def test_context_manager_die_faalt_geeft_geen_insight_en_crasht_niet(make_engine):
    cm = FakeContextManager(raise_on_get_current=True)
    engine, _ = make_engine(context_manager=cm)
    assert engine.analyze_screen_focus() is None


def test_geen_screen_focus_geeft_geen_insight(make_engine):
    cm = FakeContextManager({
        "activity": "coding",
        "screen_focus": None,
        "activity_duration_minutes": 30.0,
    })
    engine, _ = make_engine(context_manager=cm)
    assert engine.analyze_screen_focus() is None


def test_lege_string_screen_focus_geeft_geen_insight(make_engine):
    # "" is falsy in Python -- moet net als None behandeld worden.
    cm = FakeContextManager({
        "activity": "coding",
        "screen_focus": "",
        "activity_duration_minutes": 30.0,
    })
    engine, _ = make_engine(context_manager=cm)
    assert engine.analyze_screen_focus() is None


def test_activiteit_niet_in_whitelist_geeft_geen_insight(make_engine):
    cm = FakeContextManager({
        "activity": "gaming",
        "screen_focus": "Steam - Nova_AI",
        "activity_duration_minutes": 30.0,
    })
    engine, _ = make_engine(context_manager=cm)
    assert engine.analyze_screen_focus() is None


def test_te_kort_bezig_geeft_geen_insight(make_engine):
    cm = FakeContextManager({
        "activity": "coding",
        "screen_focus": "emergence_engine.py - Visual Studio Code",
        "activity_duration_minutes": 14.9,
    })
    engine, _ = make_engine(context_manager=cm)
    assert engine.analyze_screen_focus() is None


def test_exact_op_de_drempel_geeft_wel_een_insight(make_engine):
    # >= drempel, niet enkel strikt >.
    cm = FakeContextManager({
        "activity": "coding",
        "screen_focus": "emergence_engine.py - Visual Studio Code",
        "activity_duration_minutes": 15.0,
    })
    engine, _ = make_engine(context_manager=cm)
    insight = engine.analyze_screen_focus()
    assert insight is not None
    assert insight["duur"] == 15


# ---------------------------------------------------------------------
# Gelukkig pad
# ---------------------------------------------------------------------

def test_geschikte_context_geeft_correct_insight(make_engine):
    cm = FakeContextManager({
        "activity": "coding",
        "screen_focus": "emergence_engine.py - Visual Studio Code",
        "activity_duration_minutes": 22.4,
    })
    engine, _ = make_engine(context_manager=cm)

    insight = engine.analyze_screen_focus()

    assert insight is not None
    assert insight["type"] == "scherm_focus"
    assert insight["activiteit"] == "coderen"  # vertaald via _SCHERM_FOCUS_ACTIVITEIT_LABELS
    assert insight["screen_focus"] == "emergence_engine.py - Visual Studio Code"
    assert insight["duur"] == 22  # afgerond
    assert insight["confidence"] == 1.0


def test_onbekend_activiteitslabel_in_whitelist_valt_terug_op_kale_naam(make_engine):
    # Whitelist-check en vertaaltabel zijn twee losse stappen: als een
    # activiteit ooit aan SCHERM_FOCUS_ACTIVITEITEN wordt toegevoegd
    # zonder ook _SCHERM_FOCUS_ACTIVITEIT_LABELS bij te werken, mag dat
    # nooit crashen -- gewoon de kale naam tonen.
    cm = FakeContextManager({
        "activity": "coding",
        "screen_focus": "main.py - Visual Studio Code",
        "activity_duration_minutes": 20.0,
    })
    engine, _ = make_engine(context_manager=cm)
    engine.SCHERM_FOCUS_ACTIVITEITEN.add("nieuwe_activiteit")
    engine.layers["context_manager"] = FakeContextManager({
        "activity": "nieuwe_activiteit",
        "screen_focus": "main.py - Visual Studio Code",
        "activity_duration_minutes": 20.0,
    })

    insight = engine.analyze_screen_focus()

    assert insight is not None
    assert insight["activiteit"] == "nieuwe_activiteit"  # geen vertaling gevonden, kale naam


def test_formuleer_scherm_focus_bouwt_leesbare_zin(make_engine):
    engine, _ = make_engine(context_manager=None)
    insight = {
        "type": "scherm_focus",
        "activiteit": "coderen",
        "screen_focus": "emergence_engine.py - Visual Studio Code",
        "duur": 22,
        "confidence": 1.0,
    }

    tekst = engine._formuleer_scherm_focus(insight)

    assert "coderen" in tekst
    assert "emergence_engine.py - Visual Studio Code" in tekst
    assert "22" in tekst
    assert len(tekst) > 0


# ---------------------------------------------------------------------
# Bugfix-regressie: whitelist mag NOOIT terugvallen op de verkeerde tabel
# ---------------------------------------------------------------------

def test_pattern_matcher_namen_uit_insight_waardige_activiteiten_worden_genegeerd(make_engine):
    """
    Regressietest voor de live-testbug (15 sept 2026): "coderen" en
    "coding_gedetecteerd" zijn INSIGHT_WAARDIGE_ACTIVITEITEN-namen
    (pattern_matcher/activity_started:*), NIET wat context_manager.
    get_current()["activity"] teruggeeft (dat is "coding"). Deze
    namen mogen dus NOOIT door de scherm_focus-whitelist komen.
    """
    for verkeerd_label in ("coderen", "coding_gedetecteerd"):
        cm = FakeContextManager({
            "activity": verkeerd_label,
            "screen_focus": "iets - Visual Studio Code",
            "activity_duration_minutes": 30.0,
        })
        engine, _ = make_engine(context_manager=cm)
        assert engine.analyze_screen_focus() is None, (
            f"'{verkeerd_label}' hoort niet in SCHERM_FOCUS_ACTIVITEITEN te matchen"
        )


def test_scherm_focus_activiteiten_is_niet_hetzelfde_object_als_insight_waardige(make_engine):
    # Bewuste architecturale garantie: de twee whitelists moeten
    # onafhankelijk aanpasbaar zijn (zie de bugfix-toelichting in de
    # code zelf) -- dus nooit hetzelfde set-object.
    engine, _ = make_engine(context_manager=None)
    assert engine.SCHERM_FOCUS_ACTIVITEITEN is not engine.INSIGHT_WAARDIGE_ACTIVITEITEN


# ---------------------------------------------------------------------
# Integratie met analyze_meta_patterns()
# ---------------------------------------------------------------------

def test_analyze_meta_patterns_neemt_scherm_focus_mee_indien_geschikt(make_engine):
    cm = FakeContextManager({
        "activity": "coding",
        "screen_focus": "emergence_engine.py - Visual Studio Code",
        "activity_duration_minutes": 25.0,
    })
    engine, _ = make_engine(context_manager=cm)

    insights = engine.analyze_meta_patterns()

    types = [i["type"] for i in insights]
    assert "scherm_focus" in types


def test_analyze_meta_patterns_laat_scherm_focus_weg_indien_ongeschikt(make_engine):
    cm = FakeContextManager({
        "activity": "coding",
        "screen_focus": "emergence_engine.py - Visual Studio Code",
        "activity_duration_minutes": 1.0,  # te kort
    })
    engine, _ = make_engine(context_manager=cm)

    insights = engine.analyze_meta_patterns()

    types = [i["type"] for i in insights]
    assert "scherm_focus" not in types


# ---------------------------------------------------------------------
# LAYER4_DREMPELS-koppeling
# ---------------------------------------------------------------------

def test_scherm_focus_drempel_staat_op_1_0(make_engine):
    engine, _ = make_engine(context_manager=None)
    assert engine.LAYER4_DREMPELS.get("scherm_focus") == 1.0


def test_scherm_focus_confidence_haalt_altijd_de_layer4_drempel(make_engine):
    # confidence is bewust altijd 1.0 (zie module-docstring) -- moet
    # dus altijd exact op de drempel zitten, nooit eronder.
    engine, _ = make_engine(context_manager=None)
    assert engine._haalt_layer4_drempel("scherm_focus", 1.0) is True