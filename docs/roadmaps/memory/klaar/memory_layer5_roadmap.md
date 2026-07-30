# Layer 5 Roadmap: Context Manager

**Status:** Ready to implement  
**Depends on:** Layers 1-4, external sensors  
**Used by:** Notification system, Interruption logic  
**Date:** June 29, 2026  

---

## WAT IS LAYER 5?

Context Manager bepaalt **WAT NU BELANGRIJK IS** en **WANNEER NOVA MAG SPREKEN**.

```
Inputs:
├─ Time: 19:15
├─ Activity: "coding" (via screen tracking)
├─ Focus level: High (no mouse movement 10min)
├─ People nearby: None (webcam)
├─ Mode: "PRIVATE" (Bluetooth: headphones)

Context output:
├─ NOW: Coding
├─ Mood: Focused
├─ Should interrupt: FALSE
├─ Relevant topics: code, python, bugs
└─ Silent mode: TRUE (headphones)
```

## HOE WERKT HET?

```
STAP 1: Verzamel sensoren
├─ Time sensor
├─ Activity sensor (screen)
├─ Focus sensor (mouse/keyboard activity)
├─ Presence sensor (webcam)
├─ Device mode (Bluetooth, WiFi)

STAP 2: Combine met patterns
├─ Layer 2: Is het coding time?
├─ Confidence: 0.92
└─ Expected activity: coding

STAP 3: Bepaal context
├─ Status: ACTIVE (coding)
├─ Focus: HIGH (no interruptions)
├─ Mood: FOCUSED
└─ Should interrupt: FALSE

STAP 4: Publish
└─ event_bus.publish("context:updated", {...})

STAP 5: Layers luisteren
├─ Notification system: "Don't notify now"
├─ Response engine: "Keep it short"
├─ Personality: "Be more direct"
```

## DATA STRUCTURE

```json
{
  "current_context": {
    "timestamp": 1719662735.123,
    
    "environment": {
      "time": "19:15",
      "hour": 19,
      "day": "monday",
      "location": "office"
    },
    
    "activity": {
      "current": "coding",
      "expected": "coding",
      "confidence": 0.92,
      "duration_minutes": 45,
      "matches_pattern": true
    },
    
    "focus": {
      "level": "high",
      "mouse_activity": 0.1,  # Low = focused
      "keyboard_activity": 0.8,  # High = active
      "last_interruption": 600,  # 10 minutes ago
      "screen_focus": "vs_code",
      "is_focused": true
    },
    
    "presence": {
      "people_nearby": 0,
      "faces_detected": 0,
      "is_alone": true
    },
    
    "device_mode": {
      "headphones_connected": true,
      "mode": "PRIVATE",
      "wifi_network": "home",
      "battery": 87
    },
    
    "recommendations": {
      "should_interrupt": false,
      "response_style": "short",
      "notification_level": "silent",
      "relevant_topics": ["code", "python", "bugs"]
    }
  }
}
```

## API DESIGN

```python
# Initialize
context = ContextManager(event_bus)

# Get current context
ctx = context.get_current()
# {activity: "coding", focus: "high", should_interrupt: false}

# Check interruption allowance
if context.can_interrupt():
    notify_user()

# Get relevant topics
topics = context.get_relevant_topics()
# ["code", "python", "debugging"]
```

## 5-FASE ROADMAP

### FASE 1: Time & pattern sensors (Week 1-2)

Get time and match with Layer 2 patterns.

### FASE 2: Activity tracking (Week 3-4)

Detect what Kevin is doing (coding, gaming, working, sleeping).

### FASE 3: Focus detection (Week 5-6)

Track mouse/keyboard activity to measure focus level.

### FASE 4: Presence detection (Week 7-8)

Use webcam to detect if people are nearby.

### FASE 5: Interruption logic (Week 9+)

Decide if/when Nova should speak.

## IMPLEMENTATION SKELETON

```python
# modules/core/context_manager.py

from datetime import datetime
import time

class ContextManager:
    """
    Layer 5: Context Manager
    
    Determines current context (time, activity, focus level).
    Decides if Nova should interrupt.
    """
    
    def __init__(self, event_bus, layers=None):
        self.event_bus = event_bus
        self.layers = layers or {}
        self.last_mouse_activity = time.time()
        self.context = {}
    
    def get_current(self):
        """Get current context"""
        
        now = datetime.now()
        hour = now.hour
        
        # Get pattern info
        patterns = self.layers.get("pattern_matcher", {})
        
        # Determine activity
        is_coding_time = patterns.is_pattern_active("coding_time") if patterns else False
        
        # Determine focus (simplified)
        focus_level = "high" if not self._has_recent_mouse_activity() else "low"
        
        context = {
            "time": now.isoformat(),
            "hour": hour,
            "activity": "coding" if is_coding_time else "unknown",
            "focus": focus_level,
            "should_interrupt": False if is_coding_time and focus_level == "high" else True,
            "relevant_topics": ["code"] if is_coding_time else []
        }
        
        self.context = context
        
        # Publish
        self.event_bus.publish("context:updated", context)
        
        return context
    
    def can_interrupt(self):
        """Check if safe to interrupt"""
        ctx = self.get_current()
        return ctx.get("should_interrupt", True)
    
    def _has_recent_mouse_activity(self, window_seconds=60):
        """Check if mouse moved recently"""
        # To be implemented: actual mouse tracking
        return False
    
    def get_relevant_topics(self):
        """Get topics relevant to current context"""
        ctx = self.get_current()
        return ctx.get("relevant_topics", [])


def init_module(event_bus, layers=None):
    instance = ContextManager(event_bus, layers)
    event_bus.publish("module_loaded", {"name": "context_manager"})
    return instance
```

---

**Status:** READY FOR IMPLEMENTATION
