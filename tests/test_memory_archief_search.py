"""
Test voor punt 14 (stap 1): search()/query()/get_stats() moeten sinds
16 augustus 2026 ook interactions_old (gearchiveerde events, >90 dagen)
meenemen via UNION ALL, niet enkel de recente hoofdtabel.

Isolatie via tmp_path (vaste werkwijze, zie nova_state.md) -- nooit de
echte data/-bestanden. MemoryModule doet I/O in __init__() (_init_db(),
start_maintenance() zet een timer) -- save_path wordt daarom expliciet
meegegeven zodat alles binnen tmp_path blijft.
"""

import sys
import time
import sqlite3
import pytest

sys.path.insert(0, ".")

from core.memory import MemoryModule


class NepEventBus:
    """Minimale nep-EventBus: publish/subscribe/.modules volstaat."""
    def __init__(self):
        self.modules = {}
        self._subscribers = {}

    def subscribe(self, event_type, handler):
        self._subscribers.setdefault(event_type, []).append(handler)

    def publish(self, event_type, data):
        for handler in self._subscribers.get(event_type, []):
            handler(data, event_type=event_type)
        for handler in self._subscribers.get("*", []):
            handler(data, event_type=event_type)

    def register_module(self, naam, module):
        self.modules[naam] = module


@pytest.fixture
def mem(tmp_path):
    bus = NepEventBus()
    save_path = tmp_path / "interactions.jsonl"
    m = MemoryModule(bus, save_path=save_path)
    yield m
    # Achtergrond-timer netjes afsluiten zodat pytest niet blijft hangen
    if m.maintenance_timer is not None:
        m.maintenance_timer.cancel()


def _voeg_direct_toe_aan_interactions_old(mem, keyword, dagen_oud=120):
    """
    Schrijft rechtstreeks een rij in interactions_old, zoals
    archive_old_events() dat zou doen -- simuleert '>90 dagen oud'
    zonder 120 dagen te moeten wachten.
    """
    ts = time.time() - (dagen_oud * 24 * 3600)
    dt_maand = time.strftime("%Y-%m", time.localtime(ts))
    dt_jaar = int(time.strftime("%Y", time.localtime(ts)))
    data_json = f'{{"tekst": "gesprek over {keyword}"}}'
    with mem.lock:
        mem.conn.execute(
            """
            INSERT INTO interactions_old
                (timestamp, month, year, event_type, data, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (ts, dt_maand, dt_jaar, "chat_message", data_json, ts)
        )
        mem.conn.commit()


def test_search_vindt_archief_by_default(mem):
    _voeg_direct_toe_aan_interactions_old(mem, "python")
    resultaten = mem.search("python")
    assert len(resultaten) == 1
    assert "python" in resultaten[0]["data"]


def test_search_include_archief_false_negeert_archief(mem):
    _voeg_direct_toe_aan_interactions_old(mem, "python")
    resultaten = mem.search("python", include_archief=False)
    assert resultaten == []


def test_search_vindt_zowel_recent_als_archief(mem):
    # Recent event via het normale pad (on_event -> buffer -> flush)
    mem.on_event({"tekst": "gesprek over python vandaag"}, event_type="chat_message")
    mem._flush_buffer()
    # Archief-event direct toegevoegd
    _voeg_direct_toe_aan_interactions_old(mem, "python")

    resultaten = mem.search("python")
    assert len(resultaten) == 2


def test_query_vindt_archief_by_default(mem):
    _voeg_direct_toe_aan_interactions_old(mem, "schaken")
    resultaten = mem.query({"keyword": "schaken"})
    assert len(resultaten) == 1


def test_query_include_archief_false(mem):
    _voeg_direct_toe_aan_interactions_old(mem, "schaken")
    resultaten = mem.query({"keyword": "schaken", "include_archief": False})
    assert resultaten == []


def test_query_sort_oldest_first_met_archief(mem):
    _voeg_direct_toe_aan_interactions_old(mem, "oud_topic", dagen_oud=200)
    mem.on_event({"tekst": "recent_topic"}, event_type="chat_message")
    mem._flush_buffer()

    resultaten = mem.query({"sort": "oldest_first", "limit": 10})
    # Het oudste (archief) event moet eerst staan
    assert len(resultaten) == 2
    assert resultaten[0]["timestamp"] < resultaten[1]["timestamp"]


def test_get_stats_telt_archief_mee(mem):
    _voeg_direct_toe_aan_interactions_old(mem, "a")
    _voeg_direct_toe_aan_interactions_old(mem, "b")
    mem.on_event({"tekst": "recent"}, event_type="chat_message")
    mem._flush_buffer()

    stats = mem.get_stats(force_refresh=True)
    assert stats["totaal_events_recent"] == 1
    assert stats["totaal_events_archief"] == 2
    assert stats["totaal_events"] == 3


def test_get_stats_periode_omvat_archief(mem):
    _voeg_direct_toe_aan_interactions_old(mem, "oud", dagen_oud=300)
    mem.on_event({"tekst": "recent"}, event_type="chat_message")
    mem._flush_buffer()

    stats = mem.get_stats(force_refresh=True)
    vroegste, laatste = stats["periode"]
    # Vroegste datum moet ~300 dagen terug liggen, niet enkel vandaag
    verwacht_vroeg = time.strftime("%Y-%m-%d", time.localtime(time.time() - 300 * 24 * 3600))
    assert vroegste == verwacht_vroeg


def test_get_stats_geen_archief_geeft_nul(mem):
    mem.on_event({"tekst": "recent"}, event_type="chat_message")
    mem._flush_buffer()

    stats = mem.get_stats(force_refresh=True)
    assert stats["totaal_events_archief"] == 0
    assert stats["totaal_events_recent"] == 1


def test_search_recent_weeks_werkt_nog_samen_met_archief(mem):
    # Archief-event van 120 dagen oud valt buiten "recent_weeks=4"
    _voeg_direct_toe_aan_interactions_old(mem, "python", dagen_oud=120)
    mem.on_event({"tekst": "python vandaag"}, event_type="chat_message")
    mem._flush_buffer()

    resultaten = mem.search("python", recent_weeks=4)
    assert len(resultaten) == 1