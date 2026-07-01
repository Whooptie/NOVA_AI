# core/memory.py

import time
import json
import os
from pathlib import Path
from datetime import datetime
import sqlite3
import atexit
import signal

class MemoryModule:
    def __init__(self, event_bus, max_events=200,
                 save_path=None):
        self.event_bus = event_bus
        self.max_events = max_events
        self.max_file_size_mb = 50  # Bij hoeveel MB roteren we het logbestand?

        # ----------------------------------------------------
        # Pad bepalen
        # ----------------------------------------------------
        if save_path is None:
            # Vaste standaardlocatie: Nova's eigen datamap
            self.save_path = Path(r"C:\Nova_AI\data") / "interactions.jsonl"
            # Pad voor de SQLite-database (naast het JSONL-bestand)
            self.db_path = Path(r"C:\Nova_AI\data") / "interactions.db"
        else:
            # Als er expliciet een ander pad wordt meegegeven, gebruiken we dat
            self.save_path = Path(save_path)
            self.db_path = self.save_path.parent / "interactions.db"

        # ALLE events in RAM
        self.events = []

        # Alleen events sinds laatste read (voor UI)
        self.recent = []

        # Event types die we NIET opslaan
        self.ignore_types = {
            "semantic_update",
            "pattern_update",
            "weather_response",
            "time_engine_response",
            "time_response",
            "date_response",
            "module_loaded"
        }

        # Zorg dat map bestaat (maakt 'm aan als hij nog niet bestaat)
        self.save_path.parent.mkdir(parents=True, exist_ok=True)

        # Write buffer (events verzamelen, in groepjes wegschrijven naar SQLite)
        self.write_buffer = []
        self.buffer_max_events  = 50   # Flush na 50 events
        self.buffer_max_seconds = 5    # OF na 5 seconden
        self.last_flush = time.time()

        # Persistente SQLite-connectie (wordt aangemaakt in _init_db)
        self.conn = None

        # SQLite-database aanmaken (of openen als hij al bestaat)
        self._init_db()

        event_bus.subscribe("*", self.on_event)

        # Graceful shutdown: buffer leegmaken bij afsluiten
        atexit.register(self._on_shutdown)
        signal.signal(signal.SIGTERM, self._on_signal)

    # -------------------------
    # Veilig kopiëren
    # -------------------------
    def safe_copy(self, data):
        try:
            return json.loads(json.dumps(data))
        except Exception:
            if isinstance(data, dict):
                return {k: str(v) for k, v in data.items()}
            return str(data)

    # -------------------------
    # SQLite database initialiseren
    # -------------------------
    def _init_db(self):
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp  REAL    NOT NULL,
                month      TEXT    NOT NULL,
                year       INTEGER NOT NULL,
                event_type TEXT    NOT NULL,
                data       TEXT    NOT NULL,
                created_at REAL    NOT NULL
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp  ON interactions(timestamp)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_month      ON interactions(month)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_event_type ON interactions(event_type)")
        self.conn.commit()
        print("Memory: SQLite-database klaar.")
        
    # -------------------------
    # Event handler
    # -------------------------
    def on_event(self, data, event_type=None):
        if event_type in self.ignore_types:
            return

        event = {
            "timestamp": time.time(),
            "event_type": event_type,
            "data": self.safe_copy(data)
        }

        # Bewaar in RAM
        self.events.append(event)
        self.recent.append(event)

        # FIFO trim
        if len(self.events) > self.max_events:
            self.events.pop(0)

        # Append naar JSONL (meteen, veiligheidsnet)
        self.append_to_disk(event)

        # In buffer voor SQLite (wordt in groepjes weggeschreven)
        self.write_buffer.append(event)
        self._maybe_flush()

    # -------------------------
    # Recente events voor UI
    # -------------------------
    def get_recent_events(self):
        out = self.recent[:]
        self.recent.clear()
        return out

    # -------------------------
    # Logbestand roteren indien te groot
    # -------------------------
    def _rotate_if_needed(self):
        if not self.save_path.exists():
            return

        size_mb = self.save_path.stat().st_size / (1024 * 1024)
        if size_mb < self.max_file_size_mb:
            return

        # Bestand is te groot → hernoem naar archief met datum+tijd
        timestamp_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        archive_name = f"interactions_{timestamp_str}.jsonl"
        archive_path = self.save_path.parent / archive_name

        try:
            self.save_path.rename(archive_path)
            print(f"Memory: logbestand geroteerd naar {archive_name}")
        except Exception as e:
            print("Memory rotate error:", e)
            
    # -------------------------
    # Append naar JSONL (met retry bij mislukking)
    # -------------------------
    def append_to_disk(self, event, max_retries=3, retry_delay=0.2):
        self._rotate_if_needed()
        line = json.dumps(event) + "\n"

        for attempt in range(1, max_retries + 1):
            try:
                with open(self.save_path, "a", encoding="utf-8") as f:
                    f.write(line)
                return  # Gelukt, klaar
            except Exception as e:
                print(f"Memory save error (poging {attempt}/{max_retries}):", e)
                if attempt < max_retries:
                    time.sleep(retry_delay)

        # Alle pogingen mislukt → meld dit via de event bus
        self.event_bus.publish("memory_write_failed", {
            "save_path": str(self.save_path),
            "event_type": event.get("event_type"),
            "timestamp": event.get("timestamp")
        })

    # -------------------------
    # Buffer flushen naar SQLite
    # -------------------------
    def _maybe_flush(self):
        genoeg_events = len(self.write_buffer) >= self.buffer_max_events
        genoeg_tijd   = (time.time() - self.last_flush) >= self.buffer_max_seconds
        if genoeg_events or genoeg_tijd:
            self._flush_buffer()

    def _flush_buffer(self):
        if not self.write_buffer:
            return
        try:
            rijen = []
            for e in self.write_buffer:
                ts = e["timestamp"]
                dt = datetime.fromtimestamp(ts)
                rijen.append((
                    ts,
                    dt.strftime("%Y-%m"),
                    dt.year,
                    e["event_type"],
                    json.dumps(e["data"]),
                    time.time()
                ))
            self.conn.executemany("""
                INSERT INTO interactions
                    (timestamp, month, year, event_type, data, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, rijen)
            self.conn.commit()
            self.write_buffer.clear()
            self.last_flush = time.time()
        except Exception as e:
            print("Memory SQLite flush error:", e)

    # -------------------------
    # Graceful shutdown
    # -------------------------
    def _on_shutdown(self):
        """Wordt aangeroepen bij normaal afsluiten (exit, Ctrl+C)"""
        self._flush_buffer()
        if self.conn:
            self.conn.commit()
            self.conn.close()
            self.conn = None
        print("Memory: netjes afgesloten.")

    def _on_signal(self, signum, frame):
        """Wordt aangeroepen bij SIGTERM (kill, reboot)"""
        self._on_shutdown()

def init_module(event_bus):
    instance = MemoryModule(event_bus)
    event_bus.publish("module_loaded", {"name": "memory"})
    return instance