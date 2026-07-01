# core/memory.py

import time
import json
import os
from pathlib import Path
from datetime import datetime

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
        else:
            # Als er expliciet een ander pad wordt meegegeven, gebruiken we dat
            self.save_path = Path(save_path)

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

        event_bus.subscribe("*", self.on_event)

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

        # Append naar JSONL (nu met retry-logica)
        self.append_to_disk(event)

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


def init_module(event_bus):
    instance = MemoryModule(event_bus)
    event_bus.publish("module_loaded", {"name": "memory"})
    return instance