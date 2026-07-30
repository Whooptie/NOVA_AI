# Nova Memory Roadmap

**Status:** Memory.py (Layer 0) fundament gebouwd, Layers 1-7 nog te implementeren  
**Knowledge Cutoff:** Juni 2026  
**Author:** Kevin (Brugge)  

---

## INHOUDSOPGAVE

1. [7-lagen geheugen model](#7-lagen-geheugen-model)
2. [Huidge memory.py analyse](#huidge-memorypy-analyse)
3. [Kritische problemen](#kritische-problemen)
4. [Architecture design](#architecture-design)
5. [Data schema](#data-schema)
6. [Query API](#query-api)
7. [5-fase roadmap](#5-fase-roadmap)
8. [Implementation details](#implementation-details)

---

## 7-LAGEN GEHEUGEN MODEL

### **Layer 0: Raw Memory (Foundation)**

```
┌─────────────────────────────────────────┐
│ Layer 0: Raw Memory                     │
├─────────────────────────────────────────┤
│ • Slaat ALLES op (events)               │
│ • Geen processing                       │
│ • interactions.jsonl (JSONL format)     │
│ • interactions.db (SQLite index)        │
│ • Recent in RAM (200 events)            │
│ • Tiered: recent/old/archived          │
│ • Publiceert events naar Layers 1-7     │
└─────────────────────────────────────────┘
         ↓ feeds ↓
```

**Verantwoordelijkheden:**
- Append-only logging (audit trail)
- Event deduplication
- Tiered storage (3mo/1yr/5yr+)
- Compression van oud data
- Fast query indexing (SQLite)
- Event publishing (für andere lagen)

---

### **Layer 1: Word Associations**

```
┌─────────────────────────────────────────┐
│ Layer 1: Word Associations              │
├─────────────────────────────────────────┤
│ Inputs: Layer 0 events                  │
│ Output: word_associations.json          │
│                                         │
│ word1  ←→ word2  (co-occurrence)       │
│ "python" ↔ "favoriet"  (0.92)          │
│ "python" ↔ "snel"      (0.87)          │
│ "focussen" ↔ "19:00"   (0.85)          │
└─────────────────────────────────────────┘
```

**Hoe het werkt:**
1. Layer 0 publiceert: "Kevin zei: Python is mijn favoriet"
2. Layer 1 parsed: ["kevin", "zei", "python", "mijn", "favoriet"]
3. Berekent co-occurrence: python+favoriet = sterke link
4. Slaat op: `{"python": {"favoriet": 0.92, "snel": 0.87}}`
5. Publiceert: "word_association:updated" event

**Nova kan:**
- "Python is het beste" → herkent jouw voorkeur
- "Iets snel?" → denkt aan Python

---

### **Layer 2: Pattern Matching**

```
┌─────────────────────────────────────────┐
│ Layer 2: Pattern Matching               │
├─────────────────────────────────────────┤
│ Inputs: Layer 0 events + timestamps    │
│ Output: patterns.json                   │
│                                         │
│ Pattern: Kevin codeert 19:00-23:00      │
│ Confidence: 0.92 (92% van de dagen)     │
│ Frequency: Daily                        │
│ Anomaly: Zaterdag niet (0.3)           │
└─────────────────────────────────────────┘
```

**Hoe het werkt:**
1. Verzamelt: "Kevin started coding" events
2. Groept op: per dag, per uur
3. Berekent: correlatie met tijd
4. Detecteert: "19:00-23:00 = coding time"
5. Slaat op: `{"coding_time": {"hour_start": 19, "hour_end": 23, "confidence": 0.92}}`

**Nova kan:**
- 18:45 → "Je gaat zo waarschijnlijk coderen?"
- 15:00 → "Nu je niet aan het coderen bent"
- Maandag vs Zaterdag → andere verwachtingen

---

### **Layer 3: Semantic Concepts**

```
┌─────────────────────────────────────────┐
│ Layer 3: Semantic Concepts              │
├─────────────────────────────────────────┤
│ Inputs: Layer 1 + Layer 0               │
│ Output: concepts.json (knowledge graph) │
│                                         │
│ "Python" (concept)                      │
│  ├─ is_a: "programmeertaal"            │
│  ├─ property: "snel"                    │
│  ├─ property: "elegant"                 │
│  ├─ associated_with: "Kevin"            │
│  └─ confidence: 0.95                    │
└─────────────────────────────────────────┘
```

**Dit is jouw semantic.py!** (KLAAR)

---

### **Layer 4: Response Generation**

```
┌─────────────────────────────────────────┐
│ Layer 4: Response Generation            │
├─────────────────────────────────────────┤
│ Inputs: Layers 1-3                      │
│ Output: intelligent replies             │
│                                         │
│ Kevin: "Wat is Rust?"                   │
│ Layer 3 zegt: Rust = programmeertaal   │
│ Layer 1 zegt: python + favoriet link    │
│ Layer 2 zegt: Kevin codeert graag       │
│                                         │
│ Nova: "Rust is ook programmeertaal,     │
│       net als Python die je leuk vindt.│
│       Snel en veilig!"                  │
└─────────────────────────────────────────┘
```

**Hoe het werkt:**
1. User input → semantic lookup
2. Context uit Layers 1-2
3. Persoonlijkheid uit Layer 6
4. Genereer response
5. Slaat op als interaction (Layer 0)

---

### **Layer 5: Context Understanding**

```
┌─────────────────────────────────────────┐
│ Layer 5: Context Understanding          │
├─────────────────────────────────────────┤
│ Inputs: Alles (Layers 0-4)              │
│ Output: context.json                    │
│                                         │
│ NOW:                                    │
│  ├─ time: 14:32                         │
│  ├─ location: "office"                  │
│  ├─ activity: "coding"                  │
│  ├─ mood: "focused"                     │
│  ├─ people_nearby: 0                    │
│  ├─ mode: "PRIVATE"                     │
│  └─ should_interrupt: false             │
└─────────────────────────────────────────┘
```

**Hoe het werkt:**
1. Verzamelt: webcam, time, activity, sensors
2. Bepaalt: "Nu is Kevin gefocust"
3. Beslist: "Niet interrupteren"
4. Nova spreekt: alleen als relevant
5. Leert: Wanneer Nova interessant is

---

### **Layer 6: Personality Engine**

```
┌─────────────────────────────────────────┐
│ Layer 6: Personality Engine             │
├─────────────────────────────────────────┤
│ Inputs: Layers 0-5 + identity.json      │
│ Output: personality-filtered responses  │
│                                         │
│ Traits (jouw keuze):                    │
│  ├─ sarcasm: 0.6                        │
│  ├─ warmth: 0.8                         │
│  ├─ directness: 0.9                     │
│  └─ formality: 0.3                      │
│                                         │
│ Mood aanpassen:                         │
│  ├─ Jij blij → Nova enthousiast         │
│  ├─ Jij boos → Nova voorzichtig         │
│  └─ Jij gefocust → Nova kort            │
└─────────────────────────────────────────┘
```

**Du hebt dit al!** (personality_engine.py)

---

### **Layer 7: Emergent Behaviors**

```
┌─────────────────────────────────────────┐
│ Layer 7: Emergent Behaviors             │
├─────────────────────────────────────────┤
│ Inputs: Alle lagen tegelijk             │
│ Output: Self-awareness + learning       │
│                                         │
│ Voorbeelden:                            │
│  ├─ "Ik merk dat je van Python houdt"  │
│  ├─ "Je pattern: coderen 's avonds"    │
│  ├─ "Je bent consistent in sarcasme"   │
│  ├─ "Jouw prioriteit: snelheid"        │
│  └─ "Ik groei met elke interactie"     │
└─────────────────────────────────────────┘
```

**Hoe het werkt:**
1. Analyseert: alle eerdere lagen
2. Herkent: patronen IN de patronen
3. Zelf-reflects: "Ik heb geleerd dat..."
4. Adapteert: gedrag op basis van groei
5. Voelt: echt levend

---

## HUIDGE MEMORY.PY ANALYSE

### Wat goed is ✅

```python
✅ Event-based architecture (event_bus)
✅ FIFO trimming (RAM-efficient)
✅ Append-only logging (audit trail)
✅ safe_copy() (serialization handled)
✅ Ignore types (noise filtering)
✅ JSONL format (human-readable)
```

### Kritische problemen ❌

```python
❌ Problem 1: Hardcoded Windows path
   save_path=r"C:\Nova_AI\data\interactions.jsonl"
   → Breekt op Linux/Mac
   → Moet: os.path.join() of config-driven

❌ Problem 2: Geen tiered retention
   max_events=200 → Te klein voor jaren
   → Moet: Recent (RAM) / Archive (disk) / Compress (old)

❌ Problem 3: Geen SQLite
   Alleen JSONL → Traag voor queries
   → Moet: Parallel SQLite index

❌ Problem 4: Geen semantic integratie
   Publiceert niet naar Layers 1-7
   → Moet: event_bus.publish("memory:*") voor lagen

❌ Problem 5: Geen query API
   Alleen on_event() / get_recent_events()
   → Moet: memory.query() / memory.search()

❌ Problem 6: Geen bidirectional sync
   Semantic kan niet memory BIJWERKEN
   → Moet: memory kan events van semantic ontvangen

❌ Problem 7: Geen data lifecycle
   Geen archivering / compressie
   → Moet: Automatisch tiered storage
```

---

## KRITISCHE PROBLEMEN

### 1. Path portabiliteit

**Huidge code:**
```python
save_path=r"C:\Nova_AI\data\interactions.jsonl"  # ❌ Windows only
```

**Moet zijn:**
```python
import os
from pathlib import Path

# Config-driven
save_path = Path(config.get("memory.save_path", 
                           Path.home() / "nova_data" / "interactions.jsonl"))
os.makedirs(save_path.parent, exist_ok=True)
```

---

### 2. Tiered storage

**Huidge code:**
```python
if len(self.events) > self.max_events:
    self.events.pop(0)  # ❌ Verwerpt data!
```

**Moet zijn:**
```
Recent (3 maanden): RAM + SQLite
├─ Full data
├─ ~2000 entries
└─ Fast queries

Old (1 jaar): Disk
├─ Samengevat (Layer 1 data)
├─ ~10.000 entries
└─ Queries mogelijk

Archive (5+ jaar): Compressed
├─ Metadata only
├─ Search via index
└─ Retrieval traag maar mogelijk
```

---

### 3. Geen indexing

**Huidge code:**
```python
# Alle data in JSONL
# Search = lineaire scan
# Time: O(n) → Traag!
```

**Moet zijn:**
```python
# SQLite parallell
CREATE TABLE interactions (
    id INTEGER PRIMARY KEY,
    timestamp REAL,
    event_type TEXT,
    data TEXT,
    month TEXT,  # Index!
    year INTEGER, # Index!
    keywords TEXT # Index!
);

CREATE INDEX idx_timestamp ON interactions(timestamp);
CREATE INDEX idx_month ON interactions(month);
```

---

### 4. Query API ontbreekt

**Huidge code:**
```python
memory.get_recent_events()  # Alleen recente
# Geen: "Wat zei Kevin vorige maand?"
```

**Moet zijn:**
```python
# Simple
memory.search("python")

# Complex
memory.query({
    "keyword": "python",
    "date_range": ["2025-01-01", "2025-06-01"],
    "min_confidence": 0.7
})

# Fuzzy
memory.find_similar("machine learning")
```

---

## ARCHITECTURE DESIGN

### High-level diagram

```
┌──────────────────────────────────────────────────────┐
│                    NOVA MEMORY SYSTEM                 │
├──────────────────────────────────────────────────────┤
│                                                       │
│  ┌─────────────────────────────────────┐            │
│  │ Layer 0: Raw Memory (memory.py)     │            │
│  ├─────────────────────────────────────┤            │
│  │ • Event capture                     │            │
│  │ • RAM cache (200 recent)            │            │
│  │ • SQLite index (fast queries)       │            │
│  │ • JSONL archive (append-only)       │            │
│  │ • Tiered storage (recent/old/arch)  │            │
│  │ • Event publishing                  │            │
│  └─────────────────────────────────────┘            │
│           ↓ publiceert events           ↓            │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────┐    │
│  │ Layer 1:    │  │ Layer 2:    │  │ Layer 3: │    │
│  │ Word        │  │ Pattern     │  │ Semantic │    │
│  │ Associat.   │  │ Matching    │  │ Concepts │    │
│  └─────────────┘  └─────────────┘  └──────────┘    │
│           ↓              ↓              ↓             │
│  ┌─────────────────────────────────────┐            │
│  │ Layer 4: Response Generation        │            │
│  └─────────────────────────────────────┘            │
│           ↓                                           │
│  ┌─────────────────────────────────────┐            │
│  │ Layer 5: Context Understanding      │            │
│  └─────────────────────────────────────┘            │
│           ↓                                           │
│  ┌─────────────────────────────────────┐            │
│  │ Layer 6: Personality Engine         │            │
│  └─────────────────────────────────────┘            │
│           ↓                                           │
│  ┌─────────────────────────────────────┐            │
│  │ Layer 7: Emergent Behaviors         │            │
│  └─────────────────────────────────────┘            │
│                                                       │
└──────────────────────────────────────────────────────┘
```

### Module structure

```
core/
├── memory.py (Layer 0: Raw storage + queries)
│
modules/learning/
├── word_associations_learner.py (Layer 1)
├── pattern_matcher.py (Layer 2)
│
modules/semantic/
├── semantic.py (Layer 3: concepts.json)
│
modules/core/
├── response_engine.py (Layer 4)
├── context_manager.py (Layer 5)
│
core/
├── personality_engine.py (Layer 6)
│
modules/experimental/
├── emergence_engine.py (Layer 7)
```

---

## DATA SCHEMA

### interactions.jsonl format

```json
{
  "timestamp": 1719662735.123,
  "event_type": "user:chat",
  "data": {
    "user_input": "Wat is een kat?",
    "nova_response": "Kat is een huisdier, felidae familie",
    "confidence": 0.95,
    "source": "semantic"
  },
  "metadata": {
    "month": "2026-06",
    "context": {
      "mode": "PRIVATE",
      "activity": "coding",
      "mood": "focused"
    }
  }
}
```

### interactions.db schema

```sql
CREATE TABLE interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    month TEXT NOT NULL,
    year INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    data TEXT NOT NULL,  -- JSON
    keywords TEXT,  -- comma-separated for search
    confidence REAL,
    source TEXT,
    indexed BOOLEAN DEFAULT 0
);

CREATE INDEX idx_timestamp ON interactions(timestamp);
CREATE INDEX idx_month ON interactions(month);
CREATE INDEX idx_year ON interactions(year);
CREATE INDEX idx_event_type ON interactions(event_type);
CREATE INDEX idx_source ON interactions(source);
```

### Tiered storage

```
interactions_recent.json (3 maanden)
├─ ~2000 entries
├─ Full detail
├─ In SQLite
└─ Fast queries

interactions_old.json (1 jaar)
├─ ~10.000 entries
├─ Samengevat (Layer 1 aggregates)
├─ In separate table
└─ Queries mogelijk

interactions_archive.json.gz (5+ jaar)
├─ ~50.000+ entries
├─ Metadata only
├─ Compressed
└─ Zelden accessed
```

---

## QUERY API

### Simple search

```python
# Find all entries with keyword
results = memory.search("python")
# Output: List of matching interactions

results = memory.search("python", limit=10)
# Output: Last 10 matches

results = memory.search("python", recent_weeks=4)
# Output: Last 4 weeks with "python"
```

### Complex query

```python
results = memory.query({
    "keyword": "python",
    "date_range": {
        "start": "2026-01-01",
        "end": "2026-06-30"
    },
    "event_type": "user:chat",
    "min_confidence": 0.7,
    "sort": "recent_first",
    "limit": 20
})
```

### Semantic integration

```python
# Layer 1 luistert:
memory.on_event("memory:interaction_added", data)
word_associations.learn_from(data)

# Layer 3 zoekt:
similar_concepts = memory.find_semantically_similar("python")
# Returns: Concepts linked via word associations
```

### Statistics

```python
stats = memory.get_stats()
# {
#   "total_interactions": 2547,
#   "date_range": ["2025-01-08", "2026-06-29"],
#   "events_per_day": 7.2,
#   "most_common_topics": ["python", "machine_learning", "ai"]
# }
```

---

## 5-FASE ROADMAP

### FASE 1: Foundation fix (Week 1-2)

**Doel:** memory.py production-ready maken

**Deliverables:**
- ✅ Path portabiliteit (config-driven)
- ✅ Error handling (retry logic)
- ✅ Safe serialization (JSON schema)
- ✅ Log rotation (prevent disk full)

**Code changes:**
```python
# OLD:
save_path=r"C:\Nova_AI\data\interactions.jsonl"

# NEW:
from pathlib import Path
import configparser

config = configparser.ConfigParser()
config.read('nova_config.yaml')

save_path = Path(config.get('memory', 'save_path',
                            fallback=str(Path.home() / 'nova_data')))
```

**Testing:**
- [ ] Can append 1000 events
- [ ] No data loss on crash
- [ ] Portable to Linux/Mac
- [ ] Performance: <10ms per event

---

### FASE 2: Tiered storage (Week 3-4)

**Doel:** Scalable storage voor jaren data

**Deliverables:**
- ✅ SQLite indexing (parallel JSONL)
- ✅ Auto-archival (3mo/1yr/5yr+)
- ✅ Compression pipeline
- ✅ Migration script

**Architecture:**
```
interactions_recent.db (SQLite)
├─ Last 3 months
├─ Full data
├─ Fast queries
└─ Auto-maintained

interactions_old.jsonl.gz
├─ 1 year old
├─ Compressed
├─ Searchable via index
└─ Auto-maintained

interactions_archive/
├─ 5+ years
├─ Metadata only
├─ Rare access
└─ Annual cleanup
```

**Testing:**
- [ ] Archive automation works
- [ ] Query speed: <100ms for 50k entries
- [ ] Compression: 80% size reduction
- [ ] Restore: Can access archived data

---

### FASE 3: Query API (Week 5-6)

**Doel:** Intelligent search en querying

**Deliverables:**
- ✅ Simple search (keyword)
- ✅ Complex query (filters + sorts)
- ✅ Fuzzy matching
- ✅ Semantic integration hooks

**API:**
```python
# Search
memory.search("python")
memory.search("python", recent_weeks=4)

# Query
memory.query({
    "keyword": "python",
    "date_range": ["2025-01-01", "2026-06-01"],
    "confidence_min": 0.7,
    "sort": "recent_first"
})

# Fuzzy
memory.find_similar("machine learning", top_k=5)

# Stats
memory.get_stats()
memory.get_topic_frequency("python")
```

**Testing:**
- [ ] Search returns correct results
- [ ] Query filters work (date, type, confidence)
- [ ] Fuzzy matching works (typos handled)
- [ ] Performance: <100ms for complex query

---

### FASE 4: Layer integration (Week 7-8)

**Doel:** Lagen 1-7 kunnen van memory lezen/schrijven

**Deliverables:**
- ✅ Event publishing (memory → layers)
- ✅ Bidirectional sync (layers → memory)
- ✅ Hooks for layers 1-2 (word/pattern learners)
- ✅ Test harness

**Code:**
```python
# Layer 0 publiceert:
event_bus.publish("memory:interaction_added", interaction)

# Layer 1 luistert:
event_bus.subscribe("memory:interaction_added", 
                   word_associations.learn_from)

# Layer 1 publiceert terug:
event_bus.publish("word_association:updated", {
    "word1": "python",
    "word2": "favoriet",
    "confidence": 0.92
})

# Memory slaat feedback op:
memory.add_metadata(interaction_id, {
    "layers_informed": ["1", "2", "3"],
    "associations_created": 5
})
```

**Testing:**
- [ ] Event flow works
- [ ] Layer 1 learns from memory events
- [ ] Memory receives layer feedback
- [ ] No data loss in bidirectional sync

---

### FASE 5: Optimization & polish (Week 9+)

**Doel:** Production-grade reliability en performance

**Deliverables:**
- ✅ Performance optimization (query caching)
- ✅ Memory leaks fixed
- ✅ Concurrent access safe (threading)
- ✅ Backup strategy
- ✅ Documentation complete

**Optimizations:**
```python
# Query caching
cache = LRUCache(max_size=100)

def search(keyword):
    if keyword in cache:
        return cache[keyword]
    results = _query_db(keyword)
    cache[keyword] = results
    return results

# Batch operations
memory.batch_append(events)  # Faster than loop

# Lazy loading
old_interactions = memory.lazy_load_archive("2021-2022")
```

**Testing:**
- [ ] Can handle 50k+ queries/day
- [ ] Memory usage stable (<500MB)
- [ ] Thread-safe (concurrent access)
- [ ] Backup/restore works
- [ ] No data loss scenarios

---

## IMPLEMENTATION DETAILS

### memory.py refactored (v2.0)

```python
# core/memory.py (v2.0)

import json
import time
import sqlite3
import os
from pathlib import Path
from typing import Dict, List, Optional
import threading
from collections import OrderedDict

class MemoryModule:
    """
    Layer 0: Raw Memory
    - Event capture (append-only)
    - RAM cache (recent events)
    - SQLite index (fast queries)
    - JSONL archive (audit trail)
    - Tiered storage (auto-archival)
    - Event publishing (to Layers 1-7)
    """
    
    def __init__(self, event_bus, config=None):
        self.event_bus = event_bus
        self.config = config or self._default_config()
        
        # Storage paths
        self.data_path = Path(self.config.get("data_path", 
                                              Path.home() / "nova_data"))
        self.data_path.mkdir(exist_ok=True, parents=True)
        
        self.jsonl_path = self.data_path / "interactions_recent.jsonl"
        self.db_path = self.data_path / "interactions_recent.db"
        self.archive_path = self.data_path / "archive"
        
        # RAM cache (LRU)
        self.max_ram_events = self.config.get("max_ram_events", 200)
        self.events_ram = OrderedDict()
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Initialize databases
        self._init_db()
        self._load_recent_from_disk()
        
        # Subscribe to events
        event_bus.subscribe("*", self.on_event)
        
    def _init_db(self):
        """Create SQLite schema if not exists"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    month TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    data TEXT NOT NULL,
                    keywords TEXT,
                    confidence REAL DEFAULT 1.0,
                    source TEXT DEFAULT 'core',
                    created_at REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON interactions(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_month ON interactions(month)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_type ON interactions(event_type)")
            conn.commit()
    
    def on_event(self, data, event_type=None):
        """Capture event"""
        if event_type in self.config.get("ignore_types", []):
            return
        
        with self.lock:
            interaction = {
                "timestamp": time.time(),
                "event_type": event_type,
                "data": self._safe_copy(data)
            }
            
            # RAM cache
            self._add_to_ram(interaction)
            
            # Disk (JSONL)
            self._append_to_jsonl(interaction)
            
            # Database (SQLite)
            self._append_to_db(interaction)
            
            # Publish for Layers 1-7
            self.event_bus.publish("memory:interaction_added", interaction)
    
    def search(self, keyword: str, recent_weeks: Optional[int] = None) -> List[Dict]:
        """Simple keyword search"""
        with self.lock:
            results = []
            
            # Query SQLite
            query = "SELECT * FROM interactions WHERE keywords LIKE ?"
            params = [f"%{keyword}%"]
            
            if recent_weeks:
                # Add date filter
                # ...
                pass
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(query, params)
                results = [dict(row) for row in cursor.fetchall()]
            
            return results
    
    def query(self, filters: Dict) -> List[Dict]:
        """Complex query with multiple filters"""
        with self.lock:
            # Build dynamic SQL
            query = "SELECT * FROM interactions WHERE 1=1"
            params = []
            
            if "keyword" in filters:
                query += " AND keywords LIKE ?"
                params.append(f"%{filters['keyword']}%")
            
            if "date_range" in filters:
                query += " AND timestamp >= ? AND timestamp <= ?"
                # Convert dates to timestamps...
            
            if "event_type" in filters:
                query += " AND event_type = ?"
                params.append(filters["event_type"])
            
            if "min_confidence" in filters:
                query += " AND confidence >= ?"
                params.append(filters["min_confidence"])
            
            # Execute
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(query, params)
                results = [dict(row) for row in cursor.fetchall()]
            
            # Sort
            if filters.get("sort") == "recent_first":
                results.sort(key=lambda x: x["timestamp"], reverse=True)
            
            return results[:filters.get("limit", 100)]
    
    def get_stats(self) -> Dict:
        """Return memory statistics"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM interactions")
                total = cursor.fetchone()[0]
                
                cursor = conn.execute(
                    "SELECT MIN(timestamp), MAX(timestamp) FROM interactions"
                )
                min_ts, max_ts = cursor.fetchone()
            
            return {
                "total_interactions": total,
                "date_range": [min_ts, max_ts] if min_ts else None,
                "ram_events": len(self.events_ram),
                "database_size_mb": os.path.getsize(self.db_path) / 1024 / 1024
            }
    
    def _safe_copy(self, data):
        """Safe JSON serialization"""
        try:
            return json.loads(json.dumps(data))
        except:
            return {"raw": str(data)}
    
    def _add_to_ram(self, interaction):
        """Add to RAM cache (FIFO)"""
        ts = interaction["timestamp"]
        self.events_ram[ts] = interaction
        
        if len(self.events_ram) > self.max_ram_events:
            self.events_ram.popitem(last=False)
    
    def _append_to_jsonl(self, interaction):
        """Append to JSONL (audit trail)"""
        with open(self.jsonl_path, "a") as f:
            f.write(json.dumps(interaction) + "\n")
    
    def _append_to_db(self, interaction):
        """Append to SQLite (indexed)"""
        ts = interaction["timestamp"]
        import datetime
        dt = datetime.datetime.fromtimestamp(ts)
        month = dt.strftime("%Y-%m")
        year = dt.year
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO interactions 
                (timestamp, month, year, event_type, data, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                ts,
                month,
                year,
                interaction["event_type"],
                json.dumps(interaction["data"]),
                time.time()
            ))
            conn.commit()
    
    def _default_config(self):
        return {
            "data_path": str(Path.home() / "nova_data"),
            "max_ram_events": 200,
            "ignore_types": [
                "semantic_update",
                "pattern_update",
                "module_loaded"
            ]
        }
    
    def _load_recent_from_disk(self):
        """Load recent events on startup"""
        if self.jsonl_path.exists():
            with open(self.jsonl_path) as f:
                for line in f.readlines()[-self.max_ram_events:]:
                    try:
                        event = json.loads(line)
                        self.events_ram[event["timestamp"]] = event
                    except:
                        pass

def init_module(event_bus, config=None):
    instance = MemoryModule(event_bus, config)
    event_bus.publish("module_loaded", {"name": "memory"})
    return instance
```

---

## NEXT STEPS

1. **FASE 1 starten:** Path portabiliteit + config
2. **memory.py refactoren:** Via nieuwe chat in project
3. **Testen:** Before/after performance
4. **Layers 1-2 voorbereiding:** Standby voor FASE 3

---

## REFERENCES

- Nova_Roadmap.md (project planning)
- semantic_architecture.md (Layer 3)
- personality_engine.py (Layer 6)
- interaction.jsonl spec (this document)

---

**Status:** READY FOR IMPLEMENTATION  
**Last updated:** June 29, 2026  
**Author:** Claude + Kevin  
