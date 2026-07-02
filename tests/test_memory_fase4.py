
# test_memory_fase4.py
#
# Los test-scriptje, GEEN onderdeel van Nova zelf.
# Maakt nep-oude events aan in de database, zodat je kan testen
# of archive_old_events() en compress_ancient_events() echt werken.
#
# Gebruik: python test_memory_fase4.py
# Daarna: start Nova en typ 'onderhoud' in de chat.

import sqlite3
import json
import time
from pathlib import Path
from datetime import datetime

db_path = Path(r"C:\Nova_AI\data\interactions.db")

if not db_path.exists():
    print("Databank niet gevonden. Start Nova minstens 1x op zodat interactions.db bestaat.")
    exit()

conn = sqlite3.connect(str(db_path))

def maak_event(dagen_oud, tekst):
    """Maakt 1 nep-event met een timestamp X dagen in het verleden."""
    ts = time.time() - (dagen_oud * 24 * 3600)
    dt = datetime.fromtimestamp(ts)
    return (
        ts,
        dt.strftime("%Y-%m"),
        dt.year,
        "test_event",
        json.dumps({"tekst": tekst}),
        time.time()
    )

# --- Testdata voor ARCHIVEREN (>90 dagen oud, komt in 'interactions') ---
archief_events = [
    maak_event(100, "nep-event 100 dagen oud - hoort gearchiveerd te worden"),
    maak_event(120, "nep-event 120 dagen oud - hoort gearchiveerd te worden"),
]

conn.executemany("""
    INSERT INTO interactions (timestamp, month, year, event_type, data, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
""", archief_events)

# --- Testdata voor COMPRIMEREN (>365 dagen oud, direct in 'interactions_old') ---
compress_events = [
    maak_event(400, "nep-event 400 dagen oud - hoort gecomprimeerd te worden"),
    maak_event(450, "nep-event 450 dagen oud - hoort gecomprimeerd te worden"),
]

conn.executemany("""
    INSERT INTO interactions_old (timestamp, month, year, event_type, data, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
""", compress_events)

conn.commit()
conn.close()

print("Testdata aangemaakt:")
print(f"  - {len(archief_events)} events van 100-120 dagen oud (in 'interactions')")
print(f"  - {len(compress_events)} events van 400-450 dagen oud (in 'interactions_old')")
print("Start nu Nova en typ 'onderhoud' in de chat.")