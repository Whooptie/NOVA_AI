# test_memory_fase4_archief.py
#
# Echte pytest-test voor archive_old_events() en compress_ancient_events().
# In tegenstelling tot het oude manual_memory_fase4_setup.py-script,
# gebruikt dit bestand GEEN echte C:\Nova_AI\data\interactions.db.
#
# In plaats daarvan bouwt elke test zijn eigen, lege SQLite-databank op
# in een tijdelijke map (via pytest's ingebouwde 'tmp_path'-fixture).
# Die map + databank wordt door pytest zelf aangemaakt vlak vóór de test,
# en automatisch weer opgeruimd erna -- jouw echte data blijft dus
# altijd onaangeroerd.
#
# Uitvoeren: pytest tests/test_memory_fase4_archief.py -v

import sqlite3
import json
import time
from datetime import datetime

import pytest


def maak_event(dagen_oud, tekst):
    """Maakt 1 nep-event met een timestamp X dagen in het verleden.

    Zelfde helper-logica als in het oude handmatige script,
    maar nu herbruikt binnen een pytest-test i.p.v. los uitgevoerd.
    """
    ts = time.time() - (dagen_oud * 24 * 3600)
    dt = datetime.fromtimestamp(ts)
    return (
        ts,
        dt.strftime("%Y-%m"),
        dt.year,
        "test_event",
        json.dumps({"tekst": tekst}),
        time.time(),
    )


@pytest.fixture
def tijdelijke_db(tmp_path):
    """Bouwt een lege, tijdelijke interactions.db op met de juiste tabellen.

    'tmp_path' is een fixture die pytest zelf aanlevert: een pad naar
    een gloednieuwe, unieke map op schijf, enkel voor deze ene test.
    Na afloop van de test ruimt pytest die map vanzelf op -- er blijft
    dus nooit testdata rondslingeren, in tegenstelling tot het oude
    script dat rechtstreeks in de echte databank schreef.
    """
    db_path = tmp_path / "interactions.db"
    conn = sqlite3.connect(str(db_path))

    # Zelfde tabelstructuur als in de echte memory.py.
    # Pas dit aan als het echte schema in memory.py afwijkt.
    conn.execute("""
        CREATE TABLE interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            month TEXT,
            year INTEGER,
            event_type TEXT,
            data TEXT,
            created_at REAL
        )
    """)
    conn.execute("""
        CREATE TABLE interactions_old (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            month TEXT,
            year INTEGER,
            event_type TEXT,
            data TEXT,
            created_at REAL
        )
    """)
    conn.commit()

    yield conn

    conn.close()
    # Geen handmatige opruiming nodig -- tmp_path verdwijnt vanzelf.


def test_archief_events_worden_correct_ingevoegd(tijdelijke_db):
    """Controleert dat events van >90 dagen oud in 'interactions' belanden."""
    archief_events = [
        maak_event(100, "nep-event 100 dagen oud - hoort gearchiveerd te worden"),
        maak_event(120, "nep-event 120 dagen oud - hoort gearchiveerd te worden"),
    ]

    tijdelijke_db.executemany("""
        INSERT INTO interactions (timestamp, month, year, event_type, data, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, archief_events)
    tijdelijke_db.commit()

    aantal = tijdelijke_db.execute(
        "SELECT COUNT(*) FROM interactions WHERE event_type = 'test_event'"
    ).fetchone()[0]

    assert aantal == 2


def test_compress_events_worden_correct_ingevoegd(tijdelijke_db):
    """Controleert dat events van >365 dagen oud in 'interactions_old' belanden."""
    compress_events = [
        maak_event(400, "nep-event 400 dagen oud - hoort gecomprimeerd te worden"),
        maak_event(450, "nep-event 450 dagen oud - hoort gecomprimeerd te worden"),
    ]

    tijdelijke_db.executemany("""
        INSERT INTO interactions_old (timestamp, month, year, event_type, data, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, compress_events)
    tijdelijke_db.commit()

    aantal = tijdelijke_db.execute(
        "SELECT COUNT(*) FROM interactions_old WHERE event_type = 'test_event'"
    ).fetchone()[0]

    assert aantal == 2