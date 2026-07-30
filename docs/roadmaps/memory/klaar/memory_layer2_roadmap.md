# Layer 2 Roadmap: Pattern Matcher

**Status:** Ready to implement  
**Depends on:** memory.py (Layer 0) ✅  
**Used by:** Layer 5 (Context), Layer 7 (Emergence)  
**Date:** June 29, 2026  

---

## WAT IS LAYER 2?

Pattern Matcher detecteert **gedragspatronen** in interacties.

```
Inputs:
├─ Kevin codeert: 19:00, 19:30, 19:15, 20:00
├─ Kevin codeert: morgen 19:00, 19:45
├─ Kevin codeert: overmorgen 19:30, 20:15
└─ PATTERN: Kevin codeert altijd ~19:00-23:00

Outputs: patterns.json
├─ Pattern: "coding_time"
│  ├─ hours: 19-23
│  ├─ frequency: daily (mon-fri)
│  ├─ confidence: 0.92
│  └─ anomalies: Saturday (0.3)
└─ Pattern: "focus_mode"
   ├─ trigger: "coding started"
   ├─ duration: ~4 hours
   └─ confidence: 0.88
```

## HOE WERKT HET?

```
STAP 1: Verzamel events met timestamps
├─ "coding:started" at 19:15
├─ "coding:started" at 19:00 (next day)
└─ "coding:started" at 19:30 (next day)

STAP 2: Groepeer op dimensie
├─ By hour: 19, 19, 19 → Strong pattern!
├─ By day: Mon, Tue, Wed → Daily
└─ By location: office, office, office → Consistent

STAP 3: Bereken frequentie & confidence
├─ Occurs 5/7 days → 0.71 frequency
├─ Within 30-min window → 0.92 confidence
└─ Pattern strength = 0.82

STAP 4: Detecteer anomalies
├─ Saturday: 0/1 (rare)
├─ Sunday: 0/1 (rare)
└─ Mark as: Low confidence for weekends

STAP 5: Publish
└─ event_bus.publish("pattern:detected", {...})
```

## DATA STRUCTURE

```json
{
  "metadata": {
    "version": "1.0",
    "total_patterns": 12,
    "last_updated": "2026-06-29T15:30:00"
  },
  
  "patterns": {
    "coding_time": {
      "type": "temporal",
      "trigger": "coding:started",
      "hours": {
        "start": 19,
        "end": 23,
        "window_minutes": 30
      },
      "frequency": {
        "days_detected": 142,
        "occurrences": 130,
        "frequency": 0.92,
        "confidence": 0.92
      },
      "day_breakdown": {
        "monday": 0.95,
        "tuesday": 0.94,
        "wednesday": 0.93,
        "thursday": 0.91,
        "friday": 0.89,
        "saturday": 0.15,
        "sunday": 0.10
      },
      "anomalies": [
        {
          "date": "2026-06-15",
          "expected": true,
          "actual": false,
          "reason": "sick"
        }
      ],
      "first_seen": 1704067200.0,
      "last_seen": 1719662735.123
    },
    
    "focus_mode": {
      "type": "behavioral",
      "trigger": "coding:started",
      "duration_minutes": 240,
      "duration_window": 120,
      "frequency": 0.87,
      "confidence": 0.88,
      "indicators": [
        "no_interruptions",
        "single_app_focus",
        "no_music",
        "headphones_on"
      ]
    }
  }
}
```

## API DESIGN

```python
# Initialize
patterns = PatternMatcher(event_bus, config)

# Detect patterns (auto-called on events)
patterns.detect_from(interaction)

# Query
active_patterns = patterns.get_active_patterns()
coding_pattern = patterns.get_pattern("coding_time")

# Check if pattern active now
is_coding_time = patterns.is_pattern_active("coding_time")
# Output: True/False

# Get anomalies
anomalies = patterns.get_anomalies(days=7)
# Output: List of pattern deviations

# Statistics
stats = patterns.get_stats()
```

## 5-FASE ROADMAP

### FASE 1: Event grouping (Week 1-2)

**Doel:** Group events by temporal/categorical dimensions

**Deliverables:**
- ✅ Time-based grouping (hour, day, week)
- ✅ Category-based grouping (event_type)
- ✅ Frequency calculation

### FASE 2: Pattern detection (Week 3-4)

**Doel:** Identify recurring patterns

**Deliverables:**
- ✅ Detect temporal patterns (time-of-day)
- ✅ Detect behavioral patterns (sequences)
- ✅ Calculate confidence scores

### FASE 3: Anomaly detection (Week 5-6)

**Doel:** Find deviations from patterns

**Deliverables:**
- ✅ Detect anomalies (missing expected events)
- ✅ Flag unusual combinations
- ✅ Rate anomaly severity

### FASE 4: Query & prediction (Week 7-8)

**Doel:** Query patterns and make predictions

**Deliverables:**
- ✅ is_pattern_active()
- ✅ predict_next_occurrence()
- ✅ get_anomalies()

### FASE 5: Integration (Week 9+)

**Doel:** Full integration with event_bus and other layers

**Deliverables:**
- ✅ Publish pattern updates
- ✅ Persist to disk
- ✅ Bidirectional sync

## IMPLEMENTATION SKELETON

```python
# modules/learning/pattern_matcher.py

from collections import defaultdict
from datetime import datetime, timedelta
import json
import time

class PatternMatcher:
    """
    Layer 2: Pattern Matcher
    
    Detects behavioral and temporal patterns in interactions.
    Used by Layer 5 (Context) to understand when things happen.
    """
    
    def __init__(self, event_bus, config=None):
        self.event_bus = event_bus
        self.config = config or {}
        
        self.patterns = {}
        self.save_path = self.config.get("save_path", "patterns.json")
        
        event_bus.subscribe("memory:interaction_added", self.detect_from)
    
    def detect_from(self, interaction):
        """Detect patterns from interaction"""
        
        event_type = interaction.get("event_type")
        timestamp = interaction.get("timestamp")
        
        # Group by hour
        dt = datetime.fromtimestamp(timestamp)
        hour = dt.hour
        day = dt.strftime("%A").lower()
        
        # Track occurrences
        if event_type not in self.patterns:
            self.patterns[event_type] = {
                "hours": defaultdict(int),
                "days": defaultdict(int),
                "total": 0
            }
        
        self.patterns[event_type]["hours"][hour] += 1
        self.patterns[event_type]["days"][day] += 1
        self.patterns[event_type]["total"] += 1
        
        # Recalculate
        self._update_pattern_stats()
    
    def _update_pattern_stats(self):
        """Calculate confidence and frequency"""
        
        for event_type, data in self.patterns.items():
            total = data["total"]
            
            if total == 0:
                continue
            
            # Most common hour
            hours = data["hours"]
            most_common_hour = max(hours, key=hours.get)
            occurrences_at_hour = hours[most_common_hour]
            
            # Confidence: how often at most common hour?
            confidence = occurrences_at_hour / total
            
            self.patterns[event_type]["most_common_hour"] = most_common_hour
            self.patterns[event_type]["confidence"] = confidence
            
            # Day frequency
            days = data["days"]
            total_days = sum(days.values())
            
            day_frequency = {}
            for day_name in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
                day_freq = days.get(day_name, 0) / (total_days / 7) if total_days > 0 else 0
                day_frequency[day_name] = min(1.0, day_freq)
            
            self.patterns[event_type]["day_frequency"] = day_frequency
    
    def get_pattern(self, event_type):
        """Get pattern info for event"""
        return self.patterns.get(event_type)
    
    def is_pattern_active(self, event_type):
        """Check if pattern is active now"""
        
        pattern = self.get_pattern(event_type)
        if not pattern:
            return False
        
        now = datetime.now()
        current_hour = now.hour
        current_day = now.strftime("%A").lower()
        
        expected_hour = pattern.get("most_common_hour")
        day_freq = pattern.get("day_frequency", {}).get(current_day, 0)
        
        # Is it the right hour AND the right day?
        return (
            current_hour == expected_hour and 
            day_freq > 0.5  # More common than rare
        )
    
    def get_anomalies(self, days=7):
        """Get recent anomalies"""
        # To be implemented in FASE 3
        return []
    
    def save_to_disk(self):
        """Save patterns"""
        with open(self.save_path, "w") as f:
            json.dump(self.patterns, f, indent=2, default=str)


def init_module(event_bus, config=None):
    instance = PatternMatcher(event_bus, config)
    event_bus.publish("module_loaded", {"name": "pattern_matcher"})
    return instance
```

---

**Status:** READY FOR IMPLEMENTATION
