# cleanup_test_events.py
#
# Los eenmalig script om test_event rijen te verwijderen
# die door test_memory_fase4.py zijn aangemaakt.
#
# Gebruik: python cleanup_test_events.py
# (Nova mag hierbij NIET open staan)

import sqlite3
from pathlib import Path

db_path = Path(r"C:\Nova_AI\data\interactions.db")

if not db_path.exists():
    print("Databank niet gevonden.")
    exit()

conn = sqlite3.connect(str(db_path))

verwijderd_1 = conn.execute(
    "DELETE FROM interactions WHERE event_type = 'test_event'"
).rowcount

verwijderd_2 = conn.execute(
    "DELETE FROM interactions_old WHERE event_type = 'test_event'"
).rowcount

conn.commit()
conn.execute("VACUUM")
conn.commit()
conn.close()

print(f"Verwijderd uit 'interactions': {verwijderd_1}")
print(f"Verwijderd uit 'interactions_old': {verwijderd_2}")
print("Database opgeschoond.")