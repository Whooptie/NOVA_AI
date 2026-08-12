# tests/test_trending_query.py
"""
Tests voor de gespreks-koppeling van get_trending() (nova_state.md
punt 6b, tweede deel — na find_bridge()).

Zelfde patroon als test_bridge_query.py: test GEÏSOLEERDE kopieën
van de detectielogica en de handler, niet de echte IntentRouter/
ChatModule-klassen (die hebben constructor-afhankelijkheden die hier
niet nodig zijn om de kernlogica te bevestigen).
"""

import pytest


# ─────────────────────────────────
# Geïsoleerde kopie van detect_trending_query()'s kernlogica
# ─────────────────────────────────

TRENDING_ZINNEN = [
    "waar leer ik nu over",
    "waar leer ik nu allemaal over",
    "waar ben ik nu mee bezig",
    "waar ben ik de laatste tijd mee bezig",
    "wat heb ik je laatst geleerd",
    "wat heb ik je de laatste tijd geleerd",
    "waar praat ik de laatste tijd veel over",
    "waarover praat ik de laatste tijd veel",
]


def detect_trending_query(text):
    t = text.lower().strip().rstrip("?.")
    if t in TRENDING_ZINNEN:
        return True
    return False


class TestDetectTrendingQuery:
    @pytest.mark.parametrize("zin", TRENDING_ZINNEN)
    def test_alle_triggerzinnen_matchen(self, zin):
        assert detect_trending_query(zin) is True

    def test_matcht_met_vraagteken(self):
        assert detect_trending_query("waar leer ik nu over?") is True

    def test_matcht_hoofdletterongevoelig(self):
        assert detect_trending_query("Waar Leer Ik Nu Over") is True

    def test_matcht_niet_bij_willekeurige_zin(self):
        assert detect_trending_query("wat is een gitaar") is False

    def test_matcht_niet_bij_bridge_query_zin(self):
        # Regressie-achtige check: dit mag niet per ongeluk ook
        # trending_query triggeren.
        assert detect_trending_query("wat hebben python en kunst gemeen") is False

    def test_matcht_niet_bij_gedeeltelijke_zin(self):
        # Bewust EXACTE match (geen startswith), i.t.t. detect_bridge_query
        # dat wel regex/startswith gebruikt -- get_trending() heeft geen
        # los woord nodig, dus geen reden om ruimere zinnen te vangen.
        assert detect_trending_query("waar leer ik nu over vandaag") is False


# ─────────────────────────────────
# Geïsoleerde kopie van on_trending_query()'s kernlogica
# ─────────────────────────────────

class DummyEventBus:
    def __init__(self, modules=None):
        self.modules = modules or {}
        self.published = []

    def publish(self, event_type, data):
        self.published.append((event_type, data))


class DummyWordAssocMetTrending:
    def __init__(self, resultaat):
        self._resultaat = resultaat

    def get_trending(self, window_days=7, top_k=10):
        return self._resultaat


class DummyWordAssocCrasht:
    def get_trending(self, window_days=7, top_k=10):
        raise RuntimeError("kapot")


def on_trending_query(event_bus, data):
    """Geïsoleerde kopie van ChatModule.on_trending_query()."""
    word_assoc = event_bus.modules.get("word_associations_learner")
    if word_assoc is None:
        word_assoc = event_bus.modules.get("word_associations")

    if word_assoc is None or not hasattr(word_assoc, "get_trending"):
        event_bus.publish("layer4_response", {
            "text": "Ik kan nog niet bijhouden waar je de laatste tijd mee bezig bent."
        })
        return

    try:
        trending = word_assoc.get_trending(window_days=7, top_k=5)
    except Exception:
        trending = None

    if not trending:
        event_bus.publish("layer4_response", {
            "text": "Ik zie de laatste tijd nog geen duidelijk terugkerend onderwerp bij jou."
        })
        return

    sterkste_woord, _ = trending[0]
    msg = f"De laatste tijd praat je opvallend veel over '{sterkste_woord}'."

    overige = [w for w, _ in trending[1:]]
    if overige:
        msg += f" (en ook over: {', '.join(overige)})"

    event_bus.publish("layer4_response", {"text": msg})


class TestOnTrendingQuery:
    def test_module_niet_geladen(self):
        bus = DummyEventBus(modules={})
        on_trending_query(bus, {})
        event_type, payload = bus.published[0]
        assert event_type == "layer4_response"
        assert "kan nog niet bijhouden" in payload["text"]

    def test_module_key_fallback_word_associations(self):
        # Zelfde defensieve fallback-patroon als on_bridge_query()
        wa = DummyWordAssocMetTrending([("python", 5.0)])
        bus = DummyEventBus(modules={"word_associations": wa})
        on_trending_query(bus, {})
        event_type, payload = bus.published[0]
        assert "python" in payload["text"]

    def test_geen_trending_resultaat(self):
        wa = DummyWordAssocMetTrending([])
        bus = DummyEventBus(modules={"word_associations_learner": wa})
        on_trending_query(bus, {})
        event_type, payload = bus.published[0]
        assert "nog geen duidelijk terugkerend onderwerp" in payload["text"]

    def test_een_trending_woord(self):
        wa = DummyWordAssocMetTrending([("neuraal", 8.0)])
        bus = DummyEventBus(modules={"word_associations_learner": wa})
        on_trending_query(bus, {})
        event_type, payload = bus.published[0]
        assert "'neuraal'" in payload["text"]
        assert "en ook over" not in payload["text"]

    def test_meerdere_trending_woorden(self):
        wa = DummyWordAssocMetTrending([
            ("neuraal", 8.0), ("debug", 3.5), ("gitaar", 2.0),
        ])
        bus = DummyEventBus(modules={"word_associations_learner": wa})
        on_trending_query(bus, {})
        event_type, payload = bus.published[0]
        assert "'neuraal'" in payload["text"]
        assert "en ook over: debug, gitaar" in payload["text"]

    def test_exceptie_crasht_niet(self):
        wa = DummyWordAssocCrasht()
        bus = DummyEventBus(modules={"word_associations_learner": wa})
        on_trending_query(bus, {})  # mag geen exceptie doorlaten
        event_type, payload = bus.published[0]
        assert "nog geen duidelijk terugkerend onderwerp" in payload["text"]

    def test_module_zonder_get_trending_methode(self):
        class ModuleZonderMethode:
            pass
        bus = DummyEventBus(modules={"word_associations_learner": ModuleZonderMethode()})
        on_trending_query(bus, {})
        event_type, payload = bus.published[0]
        assert "kan nog niet bijhouden" in payload["text"]