# Memory Roadmap — 24/7 Daemon Addendum

**Status:** Aanvulling op memory_layer0_roadmap.md  
**Belangrijk:** Dit document WIJZIGT enkele keuzes uit de originele memory roadmap  
**Reden:** Nova draait 24/7 (1 continue sessie), niet in losse chat-sessies  
**Date:** June 29, 2026  

---

## WAAROM DIT DOCUMENT?

De originele memory roadmap ging (impliciet) uit van **losse sessies**:
- Start → laden → chatten → opslaan → stoppen

Maar Nova draait **24/7 continue**:
- Boot → laden (1x) → eeuwig events verwerken → nooit stoppen

Dit verandert een paar dingen in memory.py. **De 7-lagen structuur blijft identiek** — alleen Layer 0 (memory.py) krijgt daemon-eigenschappen. Layers 1-7 hoeven NIET aangepast (ze worden zelfs beter door continue events).

---

## WAT VERANDERT ER? (overzicht)

| Onderdeel | Origineel (losse sessies) | 24/7 Daemon |
|-----------|---------------------------|-------------|
| RAM cache | 200 events (FIFO) | Groeit gedurende de dag, 's nachts geflushed |
| Opslaan | Bij afsluiten | Continue streaming (elke event direct) |
| Tiering | Handmatig/bij opstart | Automatisch via achtergrond-timer |
| SQLite writes | Per event een connectie | Persistente connectie + batching |
| Startup | Elke sessie opnieuw | 1x bij boot |
| Crash-risico | Klein (korte sessie) | Groter (draait maanden) → auto-recovery nodig |
| Log rotation | Niet urgent | Kritisch (bestand groeit eindeloos) |

---

## KRITISCHE NIEUWE EISEN

### 1. Persistente SQLite-connectie (met WAL)

**Probleem origineel:**
```python
# Elke event opent + sluit een nieuwe connectie
with sqlite3.connect(self.db_path) as conn:
    conn.execute(...)
# = Bij 24/7 met duizenden events = traag + veel disk I/O
```

**24/7 oplossing:**
```python
# Open connectie 1x, hou hem open, gebruik WAL-mode
self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
self.conn.execute("PRAGMA journal_mode=WAL")   # Betere concurrency
self.conn.execute("PRAGMA synchronous=NORMAL") # Sneller, nog steeds veilig
```

**Waarom WAL (Write-Ahead Logging)?**
- Lezen en schrijven tegelijk mogelijk (Layers 1-7 lezen terwijl memory schrijft)
- Minder disk I/O
- Crash-safe (bij stroomuitval ben je enkel de laatste paar events kwijt)

---

### 2. Batching van writes

**Probleem:** Bij 24/7 komen events soms in bursts (bv. tijdens actief coderen). Elke event apart naar disk schrijven is inefficiënt.

**Oplossing:** Verzamel events in een buffer, schrijf ze in groepjes weg.

```python
class MemoryModule:
    def __init__(self, event_bus, config=None):
        # ...
        self.write_buffer = []
        self.buffer_max = 50          # Flush na 50 events
        self.buffer_max_seconds = 5   # OF na 5 seconden
        self.last_flush = time.time()

    def on_event(self, data, event_type=None):
        # RAM meteen (voor snelle reads)
        self._add_to_ram(interaction)
        # Publiceer meteen (Layers 1-7 mogen niet wachten)
        self.event_bus.publish("memory:interaction_added", interaction)
        # Disk: via buffer
        self.write_buffer.append(interaction)
        self._maybe_flush()

    def _maybe_flush(self):
        enough_events = len(self.write_buffer) >= self.buffer_max
        enough_time = (time.time() - self.last_flush) >= self.buffer_max_seconds
        if enough_events or enough_time:
            self._flush_buffer()

    def _flush_buffer(self):
        if not self.write_buffer:
            return
        # Schrijf hele buffer in 1 transactie (snel!)
        self.conn.executemany("INSERT INTO interactions (...) VALUES (...)",
                              [self._to_row(e) for e in self.write_buffer])
        self.conn.commit()
        # JSONL append
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            for e in self.write_buffer:
                f.write(json.dumps(e) + "\n")
        self.write_buffer.clear()
        self.last_flush = time.time()
```

**BELANGRIJK:** RAM en event-publishing gebeuren METEEN. Alleen de disk-write wordt gebufferd. Zo verliezen Layers 1-7 nooit tijd, maar bespaar je disk I/O.

---

### 3. Achtergrond-timer voor tiering (dag/nacht cyclus)

**Idee:** 's Nachts (of elke X uur) draait automatisch onderhoud:
- Oude events (>3 maanden) → verplaatsen naar `interactions_old`
- Heel oude events (>1 jaar) → comprimeren naar archief
- RAM cache opschonen (enkel recente houden)
- SQLite `VACUUM` (database compact maken)

```python
import threading

class MemoryMaintenance:
    def __init__(self, memory_module, interval_hours=6):
        self.memory = memory_module
        self.interval = interval_hours * 3600
        self._start_timer()

    def _start_timer(self):
        self.timer = threading.Timer(self.interval, self._run_maintenance)
        self.timer.daemon = True  # Stopt automatisch als Nova stopt
        self.timer.start()

    def _run_maintenance(self):
        try:
            self.memory.archive_old_events()      # >3mnd verplaatsen
            self.memory.compress_ancient_events()  # >1jr comprimeren
            self.memory.trim_ram_cache()           # RAM opschonen
            self.memory.vacuum_db()                # DB compact
            self.memory.rotate_jsonl_if_needed()   # Log rotation
        except Exception as e:
            print(f"[Memory maintenance error] {e}")
        finally:
            self._start_timer()  # Plan volgende ronde
```

**Waarom timer i.p.v. bij opstart?** Nova start maar 1x (bij boot). Als tiering enkel bij opstart gebeurt, draait het bijna nooit. Met een timer gebeurt onderhoud elke 6u vanzelf.

---

### 4. RAM cache: groeit overdag, krimpt 's nachts

**Origineel:** Vaste 200 events (FIFO).

**24/7:** Overdag mag RAM groeien (bv. tot enkele duizenden recente events voor snelle context). Tijdens nachtelijk onderhoud wordt de cache teruggebracht tot enkel de laatste N.

```python
def trim_ram_cache(self, keep_recent=500):
    """Behoud enkel de laatste N events in RAM"""
    with self.lock:
        if len(self.events_ram) <= keep_recent:
            return
        # Behoud enkel de nieuwste keep_recent
        items = list(self.events_ram.items())
        self.events_ram = OrderedDict(items[-keep_recent:])
```

**Waarom overdag groter?** Layer 5 (Context) en Layer 7 (Emergence) willen snel bij "wat gebeurde vandaag" kunnen. Uit RAM lezen is sneller dan SQLite. 's Nachts is die verse context minder kritisch → opschonen mag.

---

### 5. Crash recovery & graceful shutdown

Bij 24/7 draaien is de kans op een crash of herstart (updates, stroomuitval) reëel. Twee dingen nodig:

**A) Graceful shutdown — buffer legen bij afsluiten:**
```python
import atexit
import signal

class MemoryModule:
    def __init__(self, event_bus, config=None):
        # ...
        atexit.register(self._on_shutdown)          # Bij normale exit
        signal.signal(signal.SIGTERM, self._on_signal)  # Bij kill/reboot

    def _on_shutdown(self):
        """Laatste buffer nog wegschrijven"""
        self._flush_buffer()
        if self.conn:
            self.conn.commit()
            self.conn.close()

    def _on_signal(self, signum, frame):
        self._on_shutdown()
```

**B) Startup recovery — check of vorige sessie netjes stopte:**
```python
def _load_recent_from_disk(self):
    # JSONL is de "source of truth" (append-only).
    # Als SQLite achterloopt op JSONL (door crash), sync bij:
    self._reconcile_jsonl_and_db()
```

**Waarom JSONL als source of truth?** JSONL is append-only en crash-bestendig: elke regel die er staat, staat er echt. SQLite kan bij een crash net iets achterlopen. Bij opstart vergelijk je beide en vul je SQLite aan waar nodig.

---

### 6. Log rotation (kritisch bij 24/7!)

**Probleem:** `interactions_recent.jsonl` groeit ONEINDIG bij 24/7. Na maanden = gigabytes.

**Oplossing:** Als het bestand te groot wordt, hernoem + start nieuw.

```python
def rotate_jsonl_if_needed(self, max_mb=50):
    """Roteer JSONL als te groot"""
    if not self.jsonl_path.exists():
        return
    size_mb = self.jsonl_path.stat().st_size / 1024 / 1024
    if size_mb >= max_mb:
        # Hernoem naar timestamped archief
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archived = self.archive_path / f"interactions_{timestamp}.jsonl"
        self.archive_path.mkdir(exist_ok=True, parents=True)
        self.jsonl_path.rename(archived)
        # Optioneel: comprimeer het archief (gzip)
        # De data zit sowieso al veilig in SQLite
```

---

## AANGEPASTE FASE-ROADMAP (24/7)

De 5 fases blijven, maar met daemon-accenten:

### FASE 1: Foundation + Daemon basis (Week 1-2)
- Path portabiliteit (pathlib) — *zoals origineel*
- **NIEUW:** Persistente SQLite-connectie + WAL-mode
- **NIEUW:** Graceful shutdown (atexit + signal)
- **NIEUW:** Startup recovery (JSONL ↔ SQLite reconciliatie)

### FASE 2: Streaming writes + Log rotation (Week 3-4)
- **NIEUW:** Write buffer + batching
- **NIEUW:** Log rotation (JSONL max 50MB)
- SQLite indexing — *zoals origineel*

### FASE 3: Query API (Week 5-6)
- *Ongewijzigd t.o.v. origineel* (search, query, stats)

### FASE 4: Achtergrond-tiering + Layer integratie (Week 7-8)
- **NIEUW:** MemoryMaintenance timer (elke 6u)
- **NIEUW:** archive_old_events / compress_ancient_events
- **NIEUW:** trim_ram_cache (dag/nacht)
- Event publishing naar Layers 1-7 — *zoals origineel*

### FASE 5: Robuustheid & optimalisatie (Week 9+)
- **NIEUW:** VACUUM automation
- **NIEUW:** Health check ("draait alles nog?")
- Query caching — *zoals origineel*
- Thread-safety onder continue load — *extra belangrijk nu*

---

## CONFIG UITBREIDING (24/7)

```python
def _default_config(self):
    return {
        "data_path": str(Path.home() / "nova_data"),

        # RAM (24/7)
        "ram_grow_max": 5000,      # Max events in RAM overdag
        "ram_keep_nightly": 500,   # Behoud na nachtelijke trim

        # Write buffer
        "buffer_max_events": 50,
        "buffer_max_seconds": 5,

        # Onderhoud
        "maintenance_interval_hours": 6,
        "archive_after_days": 90,     # 3 maanden
        "compress_after_days": 365,   # 1 jaar

        # Log rotation
        "jsonl_max_mb": 50,

        # SQLite
        "use_wal": True,

        "ignore_types": [
            "semantic_update",
            "pattern_update",
            "module_loaded",
            "time_response",
            "clock_tick"   # Belangrijk: bij 24/7 geen kloktikken loggen!
        ]
    }
```

**Let op `clock_tick` / tijd-events:** Bij 24/7 met een lopende klok kan er heel veel tijd-ruis binnenkomen. Zorg dat pure kloktikken in `ignore_types` staan, anders vervuil je de memory met duizenden nutteloze events per dag.

---

## WAT BLIJFT HETZELFDE

- De 7-lagen architectuur (0 t/m 7)
- Alle Layer 1-7 roadmaps (ongewijzigd)
- Hybrid opslag (JSONL + SQLite)
- Tiered retention concept (recent/oud/archief)
- Query API (search / query / stats)
- Bidirectionele koppeling met semantic.py

---

## SAMENVATTING

```
Nova 24/7 = memory.py wordt een DAEMON

Nieuwe eigenschappen:
├── Persistente SQLite-connectie (WAL)
├── Write buffering + batching
├── Achtergrond-onderhoud (timer, elke 6u)
├── RAM groeit overdag, krimpt 's nachts
├── Crash recovery + graceful shutdown
├── Log rotation (anti-oneindige-groei)
└── clock_tick negeren (anti-ruis)

Layers 1-7:
└── ONGEWIJZIGD (worden zelfs beter met continue events)
```

Dit addendum + de originele memory roadmap samen = volledige 24/7-klare Layer 0.

---

**Status:** READY FOR IMPLEMENTATION  
**Vervangt:** Delen van FASE 1-2 + config uit origineel  
**Behoudt:** Alle overige structuur  
**Author:** Claude + Kevin
