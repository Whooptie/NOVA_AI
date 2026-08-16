"""
Tests voor punt 14 (stap 2): natuurlijke-taal memory-vragen.

Twee delen, zelfde opzet als test_bridge_query.py/test_trending_query.py
(zie nova_state.md):
  1) Geïsoleerde kopie van detect_memory_query()'s regex-logica --
     bevestigt welke zinnen wel/niet matchen, los van de rest van
     IntentRouter (die hier niet volledig geimporteerd wordt).
  2) Een nep-ChatModule met on_memory_query() zoals voorgesteld,
     getest via een nep-EventBus (publish/subscribe/.modules) --
     bevestigt de twee paden (keyword vs. algemeen) en de
     event_type-filter (raw_user_message vs. chat_response-ruis).
"""

import re
import pytest


# ============================================================
# Deel 1: geïsoleerde regex-logica (kopie van detect_memory_query())
# ============================================================

def detect_memory_query_logica(text):
    """Letterlijke kopie van de patronen in intent_router.py's
    detect_memory_query(), puur om de regex zelf te testen."""
    t = text.lower().strip().rstrip("?.")

    algemene_zinnen = [
        "wat komt vaak terug in onze gesprekken",
        "wat komt er vaak terug in onze gesprekken",
        "waar praten we vaak over",
        "waar praten wij vaak over",
        "waar hebben we het vaak over",
    ]
    if t in algemene_zinnen:
        return ("algemeen", None)

    patronen = [
        r"wat heb ik je (?:al )?(?:eens )?gevraagd over ([\w\s]+)",
        r"hebben we het (?:al )?(?:eens )?gehad over ([\w\s]+)",
        r"heb ik je al eens iets gevraagd over ([\w\s]+)",
        r"wat weet je over onze gesprekken over ([\w\s]+)",
    ]
    for patroon in patronen:
        m = re.match(patroon, t)
        if m:
            return ("woord", m.group(1).strip())

    return (None, None)


class TestDetectMemoryQueryPatroon:

    @pytest.mark.parametrize("zin,verwacht_woord", [
        ("wat heb ik je al gevraagd over python?", "python"),
        ("wat heb ik je gevraagd over schaken", "schaken"),
        ("wat heb ik je eens gevraagd over koffie", "koffie"),
        ("hebben we het al gehad over katten", "katten"),
        ("hebben we het gehad over honden", "honden"),
        ("heb ik je al eens iets gevraagd over sterren", "sterren"),
        ("wat weet je over onze gesprekken over voetbal", "voetbal"),
    ])
    def test_woord_patronen_matchen(self, zin, verwacht_woord):
        soort, woord = detect_memory_query_logica(zin)
        assert soort == "woord"
        assert woord == verwacht_woord

    @pytest.mark.parametrize("zin", [
        "wat komt vaak terug in onze gesprekken",
        "wat komt vaak terug in onze gesprekken?",
        "wat komt er vaak terug in onze gesprekken",
        "waar praten we vaak over",
        "waar praten wij vaak over?",
        "waar hebben we het vaak over",
    ])
    def test_algemene_zinnen_matchen(self, zin):
        soort, woord = detect_memory_query_logica(zin)
        assert soort == "algemeen"
        assert woord is None

    @pytest.mark.parametrize("zin", [
        "vergelijk hond met kat",
        "wat is python",
        "bridge python en snake",
        "waar leer ik nu over",          # trending_query, mag niet overlappen
        "hoe laat is het",
    ])
    def test_niet_matchende_zinnen_geven_geen_match(self, zin):
        soort, woord = detect_memory_query_logica(zin)
        assert soort is None
        assert woord is None

    def test_matcht_hoofdletterongevoelig(self):
        soort, woord = detect_memory_query_logica("Wat Heb Ik Je Gevraagd Over Python?")
        assert soort == "woord"
        assert woord == "python"


# ============================================================
# Deel 2: on_memory_query()-integratie via nep-EventBus
# ============================================================

class NepEventBus:
    def __init__(self):
        self.modules = {}
        self._subscribers = {}
        self.gepubliceerd = []  # (event_type, data) -- voor assertions

    def subscribe(self, event_type, handler):
        self._subscribers.setdefault(event_type, []).append(handler)

    def publish(self, event_type, data):
        self.gepubliceerd.append((event_type, data))
        for handler in self._subscribers.get(event_type, []):
            handler(data, event_type=event_type)


class NepChatModule:
    """
    Zelfde logica als het voorgestelde on_memory_query() in chat.py,
    hier als losse nep-klasse zodat we 'm kunnen testen zonder de hele
    echte ChatModule (met al zijn semantic/wiki-afhankelijkheden) te
    moeten opzetten -- zelfde isolatie-aanpak als test_bridge_query.py.
    """
    def __init__(self, event_bus):
        self.event_bus = event_bus
        event_bus.subscribe("intent_memory_query", self.on_memory_query)

    def on_memory_query(self, data, event_type=None):
        keyword = data.get("keyword")

        if keyword is None:
            word_assoc = self.event_bus.modules.get("word_associations_learner")
            if word_assoc is None:
                word_assoc = self.event_bus.modules.get("word_associations")

            if word_assoc is None or not hasattr(word_assoc, "get_trending"):
                self.event_bus.publish("layer4_response", {
                    "text": "Ik kan nog niet goed bijhouden wat er vaak terugkomt in onze gesprekken."
                })
                return

            try:
                trending = word_assoc.get_trending(window_days=7, top_k=5)
            except Exception:
                trending = None

            if not trending:
                self.event_bus.publish("layer4_response", {
                    "text": "Ik zie nog geen duidelijk terugkerend onderwerp in onze gesprekken."
                })
                return

            sterkste_woord, _ = trending[0]
            msg = f"We hebben het opvallend vaak over '{sterkste_woord}' gehad."
            overige = [w for w, _ in trending[1:]]
            if overige:
                msg += f" (en ook over: {', '.join(overige)})"

            self.event_bus.publish("layer4_response", {"text": msg})
            return

        mem = self.event_bus.modules.get("memory")
        if mem is None:
            self.event_bus.publish("layer4_response", {
                "text": "Ik kan er nu even niet bij, mijn geheugen-module is niet beschikbaar."
            })
            return

        try:
            resultaten = mem.search(keyword, limit=20)
        except Exception:
            resultaten = []

        eigen_berichten = [
            r for r in resultaten if r.get("event_type") == "raw_user_message"
        ]

        if not eigen_berichten:
            self.event_bus.publish("layer4_response", {
                "text": f"Ik vind niets terug over '{keyword}' in onze eerdere gesprekken."
            })
            return

        aantal = len(eigen_berichten)
        if aantal == 1:
            msg = f"Je hebt me één keer iets gevraagd over '{keyword}'."
        else:
            msg = f"Je hebt me al {aantal} keer iets gevraagd over '{keyword}'."

        self.event_bus.publish("layer4_response", {"text": msg})


class NepMemory:
    """Simuleert memory.search() met vaste, controleerbare resultaten."""
    def __init__(self, resultaten):
        self._resultaten = resultaten

    def search(self, keyword, limit=20):
        return self._resultaten


class NepWordAssociations:
    def __init__(self, trending):
        self._trending = trending

    def get_trending(self, window_days=7, top_k=5):
        return self._trending


@pytest.fixture
def bus():
    return NepEventBus()


class TestOnMemoryQueryMetKeyword:

    def test_geen_module_geeft_nette_melding(self, bus):
        chat = NepChatModule(bus)
        bus.publish("intent_memory_query", {"keyword": "python"})

        event_type, data = bus.gepubliceerd[-1]
        assert event_type == "layer4_response"
        assert "niet beschikbaar" in data["text"]

    def test_geen_resultaten_geeft_nette_melding(self, bus):
        bus.modules["memory"] = NepMemory([])
        chat = NepChatModule(bus)
        bus.publish("intent_memory_query", {"keyword": "python"})

        event_type, data = bus.gepubliceerd[-1]
        assert event_type == "layer4_response"
        assert "niets terug" in data["text"]
        assert "python" in data["text"]

    def test_filtert_chat_response_ruis_eruit(self, bus):
        """
        Regressietest voor het live-geconstateerde probleem: 'memory
        search koffie' vond het help-menu terug omdat dat toevallig
        het woord bevatte. on_memory_query() moet enkel
        raw_user_message-events tellen, geen chat_response.
        """
        bus.modules["memory"] = NepMemory([
            {"event_type": "chat_response", "data": '{"text": "help-menu met koffie erin"}'},
            {"event_type": "chat_response", "data": '{"text": "nog een help-menu"}'},
        ])
        chat = NepChatModule(bus)
        bus.publish("intent_memory_query", {"keyword": "koffie"})

        event_type, data = bus.gepubliceerd[-1]
        assert "niets terug" in data["text"]

    def test_telt_enkel_raw_user_message(self, bus):
        bus.modules["memory"] = NepMemory([
            {"event_type": "raw_user_message", "data": '{"text": "iets over koffie"}'},
            {"event_type": "chat_response", "data": '{"text": "koffie in help-menu"}'},
            {"event_type": "raw_user_message", "data": '{"text": "koffie nog eens"}'},
        ])
        chat = NepChatModule(bus)
        bus.publish("intent_memory_query", {"keyword": "koffie"})

        event_type, data = bus.gepubliceerd[-1]
        assert event_type == "layer4_response"
        assert "2 keer" in data["text"]
        assert "koffie" in data["text"]

    def test_precies_1_resultaat_gebruikt_enkelvoud(self, bus):
        bus.modules["memory"] = NepMemory([
            {"event_type": "raw_user_message", "data": '{"text": "iets over schaken"}'},
        ])
        chat = NepChatModule(bus)
        bus.publish("intent_memory_query", {"keyword": "schaken"})

        event_type, data = bus.gepubliceerd[-1]
        assert "één keer" in data["text"]

    def test_exceptie_in_search_crasht_niet(self, bus):
        class KapotteMemory:
            def search(self, keyword, limit=20):
                raise RuntimeError("db weg")

        bus.modules["memory"] = KapotteMemory()
        chat = NepChatModule(bus)
        # Mag geen exceptie doorgeven aan de aanroeper
        bus.publish("intent_memory_query", {"keyword": "python"})

        event_type, data = bus.gepubliceerd[-1]
        assert event_type == "layer4_response"
        assert "niets terug" in data["text"]


class TestOnMemoryQueryAlgemeen:

    def test_geen_woord_associations_module_geeft_nette_melding(self, bus):
        chat = NepChatModule(bus)
        bus.publish("intent_memory_query", {"keyword": None})

        event_type, data = bus.gepubliceerd[-1]
        assert event_type == "layer4_response"
        assert "nog niet goed bijhouden" in data["text"]

    def test_geen_trending_data_geeft_nette_melding(self, bus):
        bus.modules["word_associations_learner"] = NepWordAssociations([])
        chat = NepChatModule(bus)
        bus.publish("intent_memory_query", {"keyword": None})

        event_type, data = bus.gepubliceerd[-1]
        assert "nog geen duidelijk terugkerend onderwerp" in data["text"]

    def test_sterkste_trending_woord_wordt_genoemd(self, bus):
        bus.modules["word_associations_learner"] = NepWordAssociations([
            ("python", 0.9), ("schaken", 0.5), ("koffie", 0.3)
        ])
        chat = NepChatModule(bus)
        bus.publish("intent_memory_query", {"keyword": None})

        event_type, data = bus.gepubliceerd[-1]
        assert "python" in data["text"]
        assert "schaken" in data["text"]
        assert "koffie" in data["text"]

    def test_fallback_op_kortere_module_key(self, bus):
        """Zelfde fallback-patroon als on_trending_query()."""
        bus.modules["word_associations"] = NepWordAssociations([("python", 0.9)])
        chat = NepChatModule(bus)
        bus.publish("intent_memory_query", {"keyword": None})

        event_type, data = bus.gepubliceerd[-1]
        assert "python" in data["text"]

    def test_exceptie_in_get_trending_crasht_niet(self, bus):
        class KapotteWordAssoc:
            def get_trending(self, window_days=7, top_k=5):
                raise RuntimeError("kapot")

        bus.modules["word_associations_learner"] = KapotteWordAssoc()
        chat = NepChatModule(bus)
        bus.publish("intent_memory_query", {"keyword": None})

        event_type, data = bus.gepubliceerd[-1]
        assert "nog geen duidelijk terugkerend onderwerp" in data["text"]