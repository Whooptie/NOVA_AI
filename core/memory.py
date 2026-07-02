# core/memory.py

import time
import json
import os
from pathlib import Path
from datetime import datetime
import sqlite3
import atexit
import signal
from difflib import SequenceMatcher

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
            # Portable standaardlocatie: automatisch de 'data'-map naast main.py,
            # ongeacht op welke PC of onder welke gebruikersnaam Nova draait.
            project_root = Path(__file__).resolve().parent.parent
            data_dir = project_root / "data"
            self.save_path = data_dir / "interactions.jsonl"
            self.db_path = data_dir / "interactions.db"
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
            "module_loaded",
            "memory:interaction_added"   # voorkomt oneindige lus (memory luistert naar alles, ook naar zichzelf)
        }

        # Zorg dat map bestaat (maakt 'm aan als hij nog niet bestaat)
        self.save_path.parent.mkdir(parents=True, exist_ok=True)

        # Write buffer (events verzamelen, in groepjes wegschrijven naar SQLite)
        self.write_buffer = []
        self.buffer_max_events  = 50   # Flush na 50 events
        self.buffer_max_seconds = 5    # OF na 5 seconden
        self.last_flush = time.time()

        # --- Fase 4: instellingen voor achtergrond-onderhoud ---
        self.ram_grow_max      = 5000   # Overdag mag RAM tot dit aantal groeien
        self.ram_keep_nightly  = 500    # 's Nachts terugbrengen naar dit aantal
        self.archive_after_days  = 90   # Events ouder dan 3 maanden -> archief-tabel
        self.compress_after_days = 365  # Events ouder dan 1 jaar -> gzip-bestand
        self.maintenance_interval_hours = 6  # Elke 6 uur onderhoud draaien
        self.maintenance_timer = None   # Wordt gezet in start_maintenance()

        # Persistente SQLite-connectie (wordt aangemaakt in _init_db)
        self.conn = None

        # SQLite-database aanmaken (of openen als hij al bestaat)
        self._init_db()

        event_bus.subscribe("*", self.on_event)

        # Graceful shutdown: buffer leegmaken bij afsluiten
        atexit.register(self._on_shutdown)
        signal.signal(signal.SIGTERM, self._on_signal)

        # Fase 4: achtergrond-onderhoud starten (elke X uur)
        self.start_maintenance()

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

        # Aparte tabel voor oudere events (>3 maanden) — zelfde structuur
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS interactions_old (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp  REAL    NOT NULL,
                month      TEXT    NOT NULL,
                year       INTEGER NOT NULL,
                event_type TEXT    NOT NULL,
                data       TEXT    NOT NULL,
                created_at REAL    NOT NULL
            )
        """)
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

        # Laat Layers 1-7 weten dat er een nieuw event is (voor later gebruik)
        self.event_bus.publish("memory:interaction_added", event)

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
        self.stop_maintenance()
        self._flush_buffer()
        if self.conn:
            self.conn.commit()
            self.conn.close()
            self.conn = None
        print("Memory: netjes afgesloten.")

    def _on_signal(self, signum, frame):
        """Wordt aangeroepen bij SIGTERM (kill, reboot)"""
        self._on_shutdown()

    # -------------------------
    # Fase 3: Query API
    # -------------------------

    def search(self, keyword, recent_weeks=None, limit=50):
        """
        Simpel zoeken op een trefwoord.

        Hoe het werkt: we zoeken in de 'data' kolom van SQLite (dat is
        de JSON-inhoud van elk event) naar het opgegeven woord.

        Voorbeeld:
            memory.search("python")
            memory.search("python", recent_weeks=4)   # enkel laatste 4 weken
            memory.search("python", limit=10)          # max 10 resultaten
        """
        if not self.conn:
            return []

        # Zorg dat alles wat nog in de buffer zit ook echt doorzoekbaar is
        self._flush_buffer()

        sql = "SELECT * FROM interactions WHERE data LIKE ?"
        params = [f"%{keyword}%"]

        if recent_weeks is not None:
            cutoff = time.time() - (recent_weeks * 7 * 24 * 3600)
            sql += " AND timestamp >= ?"
            params.append(cutoff)

        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        try:
            self.conn.row_factory = sqlite3.Row
            cursor = self.conn.execute(sql, params)
            resultaten = [dict(row) for row in cursor.fetchall()]
            return resultaten
        except Exception as e:
            print("Memory search error:", e)
            return []

    def query(self, filters):
        """
        Uitgebreid zoeken met meerdere filters tegelijk.

        'filters' is een dictionary. Alle sleutels zijn optioneel:
            {
                "keyword": "python",
                "event_type": "user:chat",
                "date_start": "2026-01-01",   # formaat: JJJJ-MM-DD
                "date_end": "2026-06-30",
                "min_confidence": 0.7,
                "sort": "recent_first",       # of "oldest_first"
                "limit": 20
            }

        Voorbeeld:
            memory.query({"keyword": "python", "limit": 10})
        """
        if not self.conn:
            return []

        self._flush_buffer()

        sql = "SELECT * FROM interactions WHERE 1=1"
        params = []

        if "keyword" in filters:
            sql += " AND data LIKE ?"
            params.append(f"%{filters['keyword']}%")

        if "event_type" in filters:
            sql += " AND event_type = ?"
            params.append(filters["event_type"])

        if "date_start" in filters:
            try:
                dt = datetime.strptime(filters["date_start"], "%Y-%m-%d")
                sql += " AND timestamp >= ?"
                params.append(dt.timestamp())
            except ValueError:
                print("Memory query: ongeldig date_start formaat, verwacht JJJJ-MM-DD")

        if "date_end" in filters:
            try:
                dt = datetime.strptime(filters["date_end"], "%Y-%m-%d")
                sql += " AND timestamp <= ?"
                params.append(dt.timestamp())
            except ValueError:
                print("Memory query: ongeldig date_end formaat, verwacht JJJJ-MM-DD")

        if "min_confidence" in filters and "confidence" in self._get_columns():
            sql += " AND confidence >= ?"
            params.append(filters["min_confidence"])

        if filters.get("sort") == "oldest_first":
            sql += " ORDER BY timestamp ASC"
        else:
            sql += " ORDER BY timestamp DESC"

        limit = filters.get("limit", 100)
        sql += " LIMIT ?"
        params.append(limit)

        try:
            self.conn.row_factory = sqlite3.Row
            cursor = self.conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print("Memory query error:", e)
            return []

    def _get_columns(self):
        """Hulpfunctie: welke kolommen heeft de interactions-tabel echt?"""
        try:
            cursor = self.conn.execute("PRAGMA table_info(interactions)")
            return [row[1] for row in cursor.fetchall()]
        except Exception:
            return []

    def get_stats(self):
        """
        Geeft statistieken terug over het volledige geheugen.

        Voorbeeld:
            stats = memory.get_stats()
            print(stats)
        """
        if not self.conn:
            return {}

        self._flush_buffer()

        try:
            cursor = self.conn.execute("SELECT COUNT(*) FROM interactions")
            totaal = cursor.fetchone()[0]

            cursor = self.conn.execute(
                "SELECT MIN(timestamp), MAX(timestamp) FROM interactions"
            )
            min_ts, max_ts = cursor.fetchone()

            date_range = None
            if min_ts and max_ts:
                date_range = [
                    datetime.fromtimestamp(min_ts).strftime("%Y-%m-%d"),
                    datetime.fromtimestamp(max_ts).strftime("%Y-%m-%d")
                ]

            db_size_mb = 0
            if self.db_path.exists():
                db_size_mb = round(self.db_path.stat().st_size / (1024 * 1024), 2)

            return {
                "totaal_events": totaal,
                "periode": date_range,
                "events_in_ram": len(self.events),
                "database_grootte_mb": db_size_mb
            }
        except Exception as e:
            print("Memory get_stats error:", e)
            return {}

    def find_similar(self, text, top_k=5, min_ratio=0.6):
        """
        Fuzzy matching: vindt events waarvan de inhoud QUA SPELLING lijkt
        op 'text' (dus ook bij typo's). Dit is PUUR symbolisch (difflib,
        standaard in Python) — GEEN ML, GEEN embeddings, GEEN betekenis-
        matching. "hond" wordt dus niet gelinkt aan "kat" met deze methode,
        enkel woorden die er letterlijk op lijken (bv. "pyton" -> "python").

        Voorbeeld:
            memory.find_similar("pyton")   # vindt ook events met "python"
        """
        if not self.conn:
            return []

        self._flush_buffer()

        try:
            cursor = self.conn.execute("SELECT * FROM interactions ORDER BY timestamp DESC LIMIT 500")
            self.conn.row_factory = sqlite3.Row
            cursor = self.conn.execute("SELECT * FROM interactions ORDER BY timestamp DESC LIMIT 500")
            rijen = [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print("Memory find_similar error:", e)
            return []

        gescoord = []
        for rij in rijen:
            ratio = SequenceMatcher(None, text.lower(), rij["data"].lower()).ratio()
            if ratio >= min_ratio:
                rij["similarity"] = round(ratio, 3)
                gescoord.append(rij)

        gescoord.sort(key=lambda r: r["similarity"], reverse=True)
        return gescoord[:top_k]
        
    # -------------------------
    # Fase 4: Achtergrond-onderhoud
    # -------------------------

    def trim_ram_cache(self, keep_recent=None):
        """
        Houdt enkel de laatste N events in RAM (self.events).
        Overdag mag dit groeien, 's nachts brengen we het terug.
        """
        if keep_recent is None:
            keep_recent = self.ram_keep_nightly

        if len(self.events) <= keep_recent:
            return

        self.events = self.events[-keep_recent:]
        print(f"Memory: RAM-cache opgeschoond naar {keep_recent} events.")

    def archive_old_events(self):
        """
        Verplaatst events ouder dan 'archive_after_days' van de
        hoofdtabel naar 'interactions_old'. Blijft gewoon doorzoekbaar,
        maar houdt de hoofdtabel klein en snel.
        """
        if not self.conn:
            return

        cutoff = time.time() - (self.archive_after_days * 24 * 3600)

        try:
            # Kopieer oude rijen naar interactions_old
            self.conn.execute("""
                INSERT INTO interactions_old
                    (timestamp, month, year, event_type, data, created_at)
                SELECT timestamp, month, year, event_type, data, created_at
                FROM interactions
                WHERE timestamp < ?
            """, (cutoff,))

            # Verwijder ze daarna uit de hoofdtabel
            cursor = self.conn.execute(
                "DELETE FROM interactions WHERE timestamp < ?", (cutoff,)
            )
            verplaatst = cursor.rowcount
            self.conn.commit()

            if verplaatst > 0:
                print(f"Memory: {verplaatst} oude events gearchiveerd (>{self.archive_after_days} dagen).")
        except Exception as e:
            print("Memory archive_old_events error:", e)

    def compress_ancient_events(self):
        """
        Events ouder dan 'compress_after_days' (standaard 1 jaar) worden
        uit interactions_old gehaald, weggeschreven naar een gzip-bestand
        op schijf, en daar verwijderd. Dit houdt zelfs de archief-tabel klein.
        """
        if not self.conn:
            return

        import gzip

        cutoff = time.time() - (self.compress_after_days * 24 * 3600)

        try:
            self.conn.row_factory = sqlite3.Row
            cursor = self.conn.execute(
                "SELECT * FROM interactions_old WHERE timestamp < ?", (cutoff,)
            )
            rijen = [dict(row) for row in cursor.fetchall()]

            if not rijen:
                return

            archive_dir = self.save_path.parent / "archive"
            archive_dir.mkdir(parents=True, exist_ok=True)

            timestamp_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            archive_file = archive_dir / f"interactions_compressed_{timestamp_str}.jsonl.gz"

            with gzip.open(archive_file, "wt", encoding="utf-8") as f:
                for rij in rijen:
                    f.write(json.dumps(rij) + "\n")

            self.conn.execute(
                "DELETE FROM interactions_old WHERE timestamp < ?", (cutoff,)
            )
            self.conn.commit()

            print(f"Memory: {len(rijen)} zeer oude events gecomprimeerd naar {archive_file.name}")
        except Exception as e:
            print("Memory compress_ancient_events error:", e)

    def vacuum_db(self):
        """Maakt de SQLite-database weer compact nadat er veel verwijderd is."""
        if not self.conn:
            return
        try:
            self.conn.execute("VACUUM")
            self.conn.commit()
            print("Memory: database compact gemaakt (VACUUM).")
        except Exception as e:
            print("Memory vacuum_db error:", e)

    def run_maintenance(self):
        """Voert één volledige onderhoudsronde uit. Wordt elke X uur aangeroepen."""
        try:
            self._flush_buffer()
            self.archive_old_events()
            self.compress_ancient_events()
            self.trim_ram_cache()
            self.vacuum_db()
            self._rotate_if_needed()
            print("Memory: onderhoudsronde afgerond.")
        except Exception as e:
            print("Memory run_maintenance error:", e)

    def start_maintenance(self):
        """Start de achtergrond-timer die elke 'maintenance_interval_hours' draait."""
        import threading

        def _tick():
            self.run_maintenance()
            self.start_maintenance()  # plan de volgende ronde in

        interval_seconds = self.maintenance_interval_hours * 3600
        self.maintenance_timer = threading.Timer(interval_seconds, _tick)
        self.maintenance_timer.daemon = True  # stopt automatisch als Nova stopt
        self.maintenance_timer.start()

    def stop_maintenance(self):
        """Zet de achtergrond-timer stil (bij netjes afsluiten)."""
        if self.maintenance_timer:
            self.maintenance_timer.cancel()
            self.maintenance_timer = None

def init_module(event_bus):
    instance = MemoryModule(event_bus)
    event_bus.publish("module_loaded", {"name": "memory"})
    return instance