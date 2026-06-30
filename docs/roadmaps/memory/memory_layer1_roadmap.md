# Layer 1 Roadmap: Word Associations Learner

**Status:** Ready to implement  
**Depends on:** memory.py (Layer 0) ✅  
**Used by:** Layer 3 (Semantic), Layer 4 (Response generation)  
**Date:** June 29, 2026  

---

## INHOUDSOPGAVE

1. [Wat is Layer 1?](#wat-is-layer-1)
2. [Hoe werkt het?](#hoe-werkt-het)
3. [Data structure](#data-structure)
4. [API design](#api-design)
5. [5-fase roadmap](#5-fase-roadmap)
6. [Implementation](#implementation)

---

## WAT IS LAYER 1?

### Doel

Word Associations Learner analyzeert interacties en bouwt een **associatienetwerk** op van woorden.

```
Input: interactions.jsonl
│
├─ "Python is mijn favoriet"
├─ "Python is snel"
├─ "Ik hou van snelle talen"
├─ "Java is traag"
└─ "Rust is ook snel"

Output: word_associations.json
│
├─ "python" ↔ "favoriet" (0.92)
├─ "python" ↔ "snel" (0.87)
├─ "snel" ↔ "talen" (0.78)
├─ "java" ↔ "traag" (0.85)
└─ "rust" ↔ "snel" (0.81)
```

### Waarom nodig?

```
Zonder Layer 1:
Kevin: "Wat is Rust?"
Nova: Zoekt in semantic.py
      → Vindt: "Rust is programmeertaal"
      → Antwoordt: "Rust is programmeertaal"
      ❌ Mist context dat Kevin van snel houdt

Met Layer 1:
Kevin: "Wat is Rust?"
Nova: Zoekt in semantic.py
      → Vindt: "Rust is programmeertaal"
      → Zoekt word associations
      → Ziet: "rust" ↔ "snel" (0.81)
      → Ziet: "snel" ↔ "favoriet" (via python)
      → Antwoordt: "Rust is programmeertaal, snel (net als Python)"
      ✅ Voelt personeel!
```

---

## HOE WERKT HET?

### Input: Memory events

```python
# Memory publiceert:
event_bus.publish("memory:interaction_added", {
    "timestamp": 1719662735.123,
    "event_type": "user:chat",
    "data": {
        "user_input": "Python is mijn favoriet",
        "nova_response": "Leuk! Waarom?"
    }
})

# Layer 1 luistert:
event_bus.subscribe("memory:interaction_added", 
                   word_associations.learn_from)
```

### Processing pipeline

```
1. TOKENIZE
   "Python is mijn favoriet"
   → ["python", "is", "mijn", "favoriet"]

2. FILTER
   Remove stopwords ("is", "mijn", "het", "de", etc)
   → ["python", "favoriet"]

3. CALCULATE CO-OCCURRENCE
   Zag: "python" + "favoriet" in zelfde zin
   Verhoog co-occurrence counter

4. CALCULATE PMI (Pointwise Mutual Information)
   PMI = log(P(x,y) / (P(x) * P(y)))
   = Hoe sterk zijn x en y gerelateerd?
   
   If PMI > 0: Positief gerelateerd
   If PMI = 0: Onafhankelijk
   If PMI < 0: Negatief gerelateerd

5. STORE
   word_associations.json:
   {
     "python": {
       "favoriet": 0.92,
       "snel": 0.87,
       "elegant": 0.79
     }
   }

6. PUBLISH
   event_bus.publish("word_association:updated", {
     "word1": "python",
     "word2": "favoriet",
     "pmi": 0.92
   })
```

### Learning curve

```
Dag 1-7:
├─ 50 interactions
├─ ~200 words
├─ Associations nog zwak
└─ Veel noise

Week 2-4:
├─ 500 interactions
├─ ~1000 words
├─ Patterns beginnen zichtbaar
└─ PMI scores stabiliseren

Maand 1-3:
├─ 2000 interactions
├─ ~3000 words
├─ Sterke associations
├─ Persoonlijkheid zichtbaar
└─ "Nova kent Kevin"

Jaar 1:
├─ 20.000+ interactions
├─ ~10.000 words
├─ Zeer nauwkeurige associations
├─ Machine kan je stijl herkennen
└─ "Nova voelt als haar"
```

---

## DATA STRUCTURE

### word_associations.json format

```json
{
  "metadata": {
    "version": "1.0",
    "created_at": 1719662735.123,
    "last_updated": 1719662735.123,
    "total_words": 3247,
    "total_associations": 12450,
    "confidence_threshold": 0.5
  },
  
  "associations": {
    "python": {
      "favoriet": {
        "pmi": 0.92,
        "co_occurrence": 47,
        "first_seen": 1719000000.0,
        "last_seen": 1719662735.123,
        "confidence": 0.95
      },
      "snel": {
        "pmi": 0.87,
        "co_occurrence": 38,
        "first_seen": 1718900000.0,
        "last_seen": 1719662735.123,
        "confidence": 0.92
      },
      "elegant": {
        "pmi": 0.79,
        "co_occurrence": 22,
        "first_seen": 1718700000.0,
        "last_seen": 1719662735.123,
        "confidence": 0.88
      }
    },
    
    "rust": {
      "snel": {
        "pmi": 0.81,
        "co_occurrence": 18,
        "first_seen": 1719500000.0,
        "last_seen": 1719662735.123,
        "confidence": 0.89
      },
      "veilig": {
        "pmi": 0.85,
        "co_occurrence": 24,
        "first_seen": 1719400000.0,
        "last_seen": 1719662735.123,
        "confidence": 0.91
      }
    }
  },
  
  "word_stats": {
    "python": {
      "frequency": 156,
      "first_seen": 1718000000.0,
      "contexts": ["favoriet", "snel", "elegant", "code", "learning"]
    },
    "snel": {
      "frequency": 89,
      "first_seen": 1718500000.0,
      "contexts": ["python", "rust", "talen", "performance"]
    }
  }
}
```

### Statistics schema

```python
{
  "top_words": [
    ("python", 156),
    ("code", 89),
    ("learning", 76),
    ("snel", 65),
    ("rust", 42)
  ],
  
  "strongest_associations": [
    ("python", "favoriet", 0.92),
    ("rust", "veilig", 0.85),
    ("java", "traag", 0.83),
    ("python", "snel", 0.87),
    ("code", "interessant", 0.81)
  ],
  
  "sentiment_associations": {
    "positive": ["favoriet", "snel", "elegant", "interessant"],
    "negative": ["traag", "verbose", "boring"],
    "neutral": ["language", "framework", "tool"]
  }
}
```

---

## API DESIGN

### Core API

```python
# Initialize
word_associations = WordAssociationsLearner(event_bus, config)

# Learn from interaction
word_associations.learn_from(interaction)

# Query
associations = word_associations.get_associations("python")
# Output: {"favoriet": 0.92, "snel": 0.87, "elegant": 0.79}

# Find related words
related = word_associations.find_related("python", top_k=5)
# Output: [("favoriet", 0.92), ("snel", 0.87), ...]

# Get stats
stats = word_associations.get_stats()
# Output: {"total_words": 3247, "total_associations": 12450}

# Search by sentiment
positive_words = word_associations.get_positive_words()
negative_words = word_associations.get_negative_words()

# Publish for Layer 3 (Semantic)
event_bus.publish("word_association:updated", {...})
```

### Advanced queries

```python
# Find bridge words (connecting two concepts)
bridge = word_associations.find_bridge("python", "art")
# Output: ["programming", "creativity", "elegance"]
# = Python is elegant, art is creative, both elegant

# Sentiment of a word
sentiment = word_associations.get_word_sentiment("python")
# Output: {"positive": 0.89, "negative": 0.05, "neutral": 0.06}

# Word distance (how related are two words?)
distance = word_associations.word_distance("python", "rust")
# Output: 0.78 (pretty related)

# Trending associations (what's Kevin learning about?)
trending = word_associations.get_trending(window_days=7)
# Output: [("neural_networks", "interesting", 0.91), ...]
```

---

## 5-FASE ROADMAP

### FASE 1: Tokenization & filtering (Week 1-2)

**Doel:** Tekst → woorden met proper noise filtering

**Deliverables:**
- ✅ Tokenizer (split on whitespace/punctuation)
- ✅ Stopword filter (remove "is", "de", "het", etc)
- ✅ Stemming/lemmatization (python → python, coding → code)
- ✅ Lowercase normalization

**Code skeleton:**
```python
class WordAssociationsLearner:
    def __init__(self, event_bus, config=None):
        self.event_bus = event_bus
        self.config = config or {}
        self.associations = {}
        self.word_stats = {}
        
        self.stopwords = set([
            "is", "het", "de", "een", "in", "op", "van", "en", "or",
            "the", "a", "an", "in", "on", "at", "to", "for", "of"
        ])
        
        event_bus.subscribe("memory:interaction_added", self.learn_from)
    
    def tokenize(self, text):
        """Split text into words"""
        import re
        # Convert to lowercase
        text = text.lower()
        # Split on non-alphanumeric
        words = re.findall(r'\b[a-z_]+\b', text)
        return words
    
    def filter_stopwords(self, words):
        """Remove common words"""
        return [w for w in words if w not in self.stopwords]
    
    def lemmatize(self, word):
        """Normalize word forms"""
        # Simple: remove common suffixes
        if word.endswith('ing'):
            return word[:-3]  # coding → code (approximate)
        if word.endswith('ed'):
            return word[:-2]  # learned → learn
        return word
    
    def preprocess(self, text):
        """Full pipeline: tokenize → filter → lemmatize"""
        tokens = self.tokenize(text)
        tokens = self.filter_stopwords(tokens)
        tokens = [self.lemmatize(t) for t in tokens]
        return tokens
```

**Testing:**
- [ ] "Python is mijn favoriet" → ["python", "favoriet"]
- [ ] "I'm learning machine learning" → ["learn", "machine", "learn"]
- [ ] Stopwords removed correctly
- [ ] No empty tokens

---

### FASE 2: Co-occurrence counting (Week 3-4)

**Doel:** Count how often words appear together

**Deliverables:**
- ✅ Co-occurrence matrix
- ✅ Window-based counting (words within N tokens)
- ✅ Update statistics

**Code:**
```python
def learn_from(self, interaction):
    """Learn from a single interaction"""
    
    # Extract text from interaction
    user_text = interaction.get("data", {}).get("user_input", "")
    nova_text = interaction.get("data", {}).get("nova_response", "")
    
    # Combine
    full_text = user_text + " " + nova_text
    
    # Preprocess
    words = self.preprocess(full_text)
    
    if len(words) < 2:
        return  # Not enough words
    
    # Co-occurrence: sliding window (window_size=5)
    window_size = 5
    for i, word in enumerate(words):
        # Track word frequency
        if word not in self.word_stats:
            self.word_stats[word] = {
                "frequency": 0,
                "first_seen": interaction["timestamp"]
            }
        self.word_stats[word]["frequency"] += 1
        self.word_stats[word]["last_seen"] = interaction["timestamp"]
        
        # Co-occurrence with nearby words
        window_start = max(0, i - window_size)
        window_end = min(len(words), i + window_size)
        
        for j in range(window_start, window_end):
            if i != j:
                other_word = words[j]
                
                if word not in self.associations:
                    self.associations[word] = {}
                
                if other_word not in self.associations[word]:
                    self.associations[word][other_word] = {
                        "co_occurrence": 0,
                        "first_seen": interaction["timestamp"]
                    }
                
                self.associations[word][other_word]["co_occurrence"] += 1
                self.associations[word][other_word]["last_seen"] = interaction["timestamp"]
```

**Testing:**
- [ ] "Python is snel" learns: python↔snel
- [ ] Window size works correctly
- [ ] Frequency counts increment
- [ ] Multiple interactions accumulate

---

### FASE 3: PMI calculation (Week 5-6)

**Doel:** Calculate statistical strength of associations

**Deliverables:**
- ✅ PMI (Pointwise Mutual Information) calculation
- ✅ Confidence scoring
- ✅ Normalize scores to 0-1

**PMI formula:**
```
PMI(x,y) = log(P(x,y) / (P(x) * P(y)))

Where:
P(x,y) = Probability of seeing x and y together
P(x) = Probability of seeing x
P(y) = Probability of seeing y

Result:
PMI > 0 = Positive correlation (words appear together more than chance)
PMI = 0 = Independent (no correlation)
PMI < 0 = Negative correlation (words avoid each other)
```

**Code:**
```python
import math

def calculate_pmi(self):
    """Calculate PMI for all associations"""
    
    total_pairs = sum(
        sum(assoc[w]["co_occurrence"] for w in assoc) 
        for assoc in self.associations.values()
    )
    
    if total_pairs == 0:
        return
    
    total_words = sum(stats["frequency"] for stats in self.word_stats.values())
    
    for word1, assoc in self.associations.items():
        p_x = self.word_stats[word1]["frequency"] / total_words
        
        for word2, data in assoc.items():
            p_y = self.word_stats[word2]["frequency"] / total_words
            p_xy = data["co_occurrence"] / total_pairs
            
            # Calculate PMI
            if p_xy > 0 and p_x > 0 and p_y > 0:
                pmi = math.log(p_xy / (p_x * p_y))
                
                # Normalize to 0-1 range
                # (empirically: PMI ranges roughly -5 to +10)
                normalized_pmi = 1 / (1 + math.exp(-pmi))  # Sigmoid
                
                self.associations[word1][word2]["pmi"] = float(normalized_pmi)
                self.associations[word1][word2]["confidence"] = float(normalized_pmi)
```

**Testing:**
- [ ] PMI scores calculate without errors
- [ ] Scores are in range 0-1
- [ ] Strong associations have high scores
- [ ] Weak associations have low scores

---

### FASE 4: Querying & filtering (Week 7-8)

**Doel:** Retrieve associations with filtering

**Deliverables:**
- ✅ get_associations() → sorted by strength
- ✅ find_related() → top K
- ✅ Filter by confidence threshold
- ✅ Sentiment detection

**Code:**
```python
def get_associations(self, word, min_confidence=0.5):
    """Get all associations for a word"""
    if word not in self.associations:
        return {}
    
    assoc = self.associations[word]
    
    # Filter by confidence
    filtered = {
        w: data["pmi"] 
        for w, data in assoc.items() 
        if data.get("pmi", 0) >= min_confidence
    }
    
    # Sort by strength
    sorted_assoc = dict(sorted(
        filtered.items(), 
        key=lambda x: x[1], 
        reverse=True
    ))
    
    return sorted_assoc

def find_related(self, word, top_k=5, min_confidence=0.5):
    """Find top K related words"""
    assoc = self.get_associations(word, min_confidence)
    return list(assoc.items())[:top_k]

def get_word_sentiment(self, word):
    """Determine if word is positive/negative"""
    positive_keywords = ["favoriet", "snel", "elegant", "mooi", "goed"]
    negative_keywords = ["traag", "boring", "slecht", "lelijk", "dom"]
    
    if word in positive_keywords:
        return {"positive": 0.9, "negative": 0.05, "neutral": 0.05}
    elif word in negative_keywords:
        return {"positive": 0.05, "negative": 0.9, "neutral": 0.05}
    else:
        # Infer from associations
        assoc = self.get_associations(word)
        pos_score = sum(
            score for w, score in assoc.items() 
            if w in positive_keywords
        ) / len(assoc) if assoc else 0
        
        neg_score = sum(
            score for w, score in assoc.items() 
            if w in negative_keywords
        ) / len(assoc) if assoc else 0
        
        total = pos_score + neg_score + 0.3  # Neutral baseline
        
        return {
            "positive": pos_score / total,
            "negative": neg_score / total,
            "neutral": (1 - pos_score - neg_score) / total
        }
```

**Testing:**
- [ ] get_associations() returns sorted results
- [ ] find_related() returns top K
- [ ] Filtering works correctly
- [ ] Sentiment detection reasonable

---

### FASE 5: Integration & publishing (Week 9+)

**Doel:** Full integration met event_bus en Layer 3

**Deliverables:**
- ✅ Publish updates to event_bus
- ✅ Persist to disk (word_associations.json)
- ✅ Load from disk on startup
- ✅ Bidirectional sync met semantic.py

**Code:**
```python
def save_to_disk(self, path="word_associations.json"):
    """Save associations to file"""
    import json
    from datetime import datetime
    
    data = {
        "metadata": {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "total_words": len(self.word_stats),
            "total_associations": sum(
                len(v) for v in self.associations.values()
            )
        },
        "associations": self.associations,
        "word_stats": self.word_stats
    }
    
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def load_from_disk(self, path="word_associations.json"):
    """Load associations from file"""
    import json
    
    try:
        with open(path) as f:
            data = json.load(f)
        self.associations = data.get("associations", {})
        self.word_stats = data.get("word_stats", {})
    except FileNotFoundError:
        pass

def publish_update(self, word1, word2, pmi):
    """Publish to event_bus for Layer 3"""
    self.event_bus.publish("word_association:updated", {
        "word1": word1,
        "word2": word2,
        "pmi": float(pmi),
        "timestamp": time.time()
    })
```

**Testing:**
- [ ] Saves to JSON correctly
- [ ] Loads from JSON correctly
- [ ] Events published to event_bus
- [ ] Semantic.py can receive events
- [ ] No data loss on restart

---

## IMPLEMENTATION

### Complete Layer 1 module

```python
# modules/learning/word_associations_learner.py

import json
import math
import time
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

class WordAssociationsLearner:
    """
    Layer 1: Word Associations Learner
    
    Analyzes interactions and builds a network of word associations.
    Used by Layer 3 (Semantic) to understand context.
    """
    
    def __init__(self, event_bus, config=None):
        self.event_bus = event_bus
        self.config = config or {}
        
        # Storage
        self.associations = {}  # word1 → {word2: {pmi, co_occurrence}}
        self.word_stats = {}    # word → {frequency, first_seen, last_seen}
        
        # Configuration
        self.save_path = Path(self.config.get("save_path", "word_associations.json"))
        self.min_confidence = self.config.get("min_confidence", 0.5)
        self.window_size = self.config.get("window_size", 5)
        
        # Stopwords
        self.stopwords = set([
            "is", "het", "de", "een", "in", "op", "van", "en", "or",
            "aan", "voor", "bij", "door", "met", "naar", "over",
            "the", "a", "an", "in", "on", "at", "to", "for", "of",
            "and", "or", "but", "be", "have", "do", "would", "could"
        ])
        
        # Load existing data
        self.load_from_disk()
        
        # Subscribe to memory events
        event_bus.subscribe("memory:interaction_added", self.learn_from)
    
    # ─────────────────────────────────
    # Tokenization & Preprocessing
    # ─────────────────────────────────
    
    def tokenize(self, text: str) -> List[str]:
        """Split text into words"""
        text = text.lower()
        words = re.findall(r'\b[a-z_]+\b', text)
        return words
    
    def filter_stopwords(self, words: List[str]) -> List[str]:
        """Remove common words"""
        return [w for w in words if w not in self.stopwords and len(w) > 2]
    
    def lemmatize(self, word: str) -> str:
        """Simple lemmatization"""
        if word.endswith('ing'):
            return word[:-3]
        if word.endswith('ed'):
            return word[:-2]
        if word.endswith('s') and len(word) > 3:
            return word[:-1]
        return word
    
    def preprocess(self, text: str) -> List[str]:
        """Full preprocessing pipeline"""
        tokens = self.tokenize(text)
        tokens = self.filter_stopwords(tokens)
        tokens = [self.lemmatize(t) for t in tokens]
        # Remove duplicates (keep first occurrence)
        seen = set()
        result = []
        for t in tokens:
            if t not in seen:
                result.append(t)
                seen.add(t)
        return result
    
    # ─────────────────────────────────
    # Learning
    # ─────────────────────────────────
    
    def learn_from(self, interaction: Dict):
        """Learn from a memory interaction"""
        
        # Extract text
        data = interaction.get("data", {})
        user_text = data.get("user_input", "")
        nova_text = data.get("nova_response", "")
        
        if not user_text and not nova_text:
            return
        
        # Preprocess
        words = self.preprocess(user_text + " " + nova_text)
        
        if len(words) < 2:
            return
        
        ts = interaction.get("timestamp", time.time())
        
        # Learn word statistics
        for word in words:
            if word not in self.word_stats:
                self.word_stats[word] = {
                    "frequency": 0,
                    "first_seen": ts
                }
            self.word_stats[word]["frequency"] += 1
            self.word_stats[word]["last_seen"] = ts
        
        # Learn co-occurrence
        for i, word in enumerate(words):
            window_start = max(0, i - self.window_size)
            window_end = min(len(words), i + self.window_size + 1)
            
            for j in range(window_start, window_end):
                if i != j:
                    other_word = words[j]
                    
                    if word not in self.associations:
                        self.associations[word] = {}
                    
                    if other_word not in self.associations[word]:
                        self.associations[word][other_word] = {
                            "co_occurrence": 0,
                            "first_seen": ts
                        }
                    
                    self.associations[word][other_word]["co_occurrence"] += 1
                    self.associations[word][other_word]["last_seen"] = ts
        
        # Recalculate PMI
        self.calculate_pmi()
    
    def calculate_pmi(self):
        """Calculate PMI for all associations"""
        
        if not self.associations:
            return
        
        total_pairs = sum(
            sum(assoc[w].get("co_occurrence", 0) for w in assoc) 
            for assoc in self.associations.values()
        )
        
        if total_pairs == 0:
            return
        
        total_words = sum(
            stats.get("frequency", 0) for stats in self.word_stats.values()
        )
        
        if total_words == 0:
            return
        
        for word1, assoc in self.associations.items():
            if word1 not in self.word_stats:
                continue
            
            p_x = self.word_stats[word1]["frequency"] / total_words
            
            for word2, data in assoc.items():
                if word2 not in self.word_stats:
                    continue
                
                p_y = self.word_stats[word2]["frequency"] / total_words
                p_xy = data.get("co_occurrence", 0) / total_pairs
                
                if p_xy > 0 and p_x > 0 and p_y > 0:
                    # Calculate PMI
                    pmi = math.log(p_xy / (p_x * p_y))
                    
                    # Normalize to 0-1 using sigmoid
                    normalized_pmi = 1.0 / (1.0 + math.exp(-pmi / 2.0))
                    
                    self.associations[word1][word2]["pmi"] = normalized_pmi
                    self.associations[word1][word2]["confidence"] = normalized_pmi
    
    # ─────────────────────────────────
    # Querying
    # ─────────────────────────────────
    
    def get_associations(self, word: str, min_confidence: float = None) -> Dict[str, float]:
        """Get all associations for a word, sorted by strength"""
        
        if min_confidence is None:
            min_confidence = self.min_confidence
        
        if word not in self.associations:
            return {}
        
        assoc = self.associations[word]
        
        # Filter by confidence
        filtered = {
            w: data.get("pmi", 0) 
            for w, data in assoc.items() 
            if data.get("pmi", 0) >= min_confidence
        }
        
        # Sort by strength (descending)
        sorted_assoc = dict(sorted(
            filtered.items(),
            key=lambda x: x[1],
            reverse=True
        ))
        
        return sorted_assoc
    
    def find_related(self, word: str, top_k: int = 5, min_confidence: float = None) -> List[Tuple[str, float]]:
        """Find top K related words"""
        
        assoc = self.get_associations(word, min_confidence)
        return list(assoc.items())[:top_k]
    
    def word_distance(self, word1: str, word2: str) -> float:
        """Calculate distance between two words (0-1, higher = closer)"""
        
        assoc1 = self.get_associations(word1)
        
        if word2 in assoc1:
            return assoc1[word2]
        
        # If not directly connected, check indirect paths
        # Simple: average common associates
        assoc2 = self.get_associations(word2)
        
        common = set(assoc1.keys()) & set(assoc2.keys())
        
        if not common:
            return 0.0
        
        avg_distance = sum(
            (assoc1[c] + assoc2[c]) / 2
            for c in common
        ) / len(common)
        
        return avg_distance * 0.5  # Scale down indirect connections
    
    # ─────────────────────────────────
    # Statistics
    # ─────────────────────────────────
    
    def get_word_sentiment(self, word: str) -> Dict[str, float]:
        """Determine sentiment of a word"""
        
        positive_keywords = [
            "favoriet", "snel", "elegant", "mooi", "goed", "leuk", 
            "interessant", "cool", "awesome", "geweldig", "perfect"
        ]
        negative_keywords = [
            "traag", "boring", "slecht", "lelijk", "dom", "vervelend",
            "stom", "idioot", "verschrikkelijk", "afschuwelijk"
        ]
        
        if word in positive_keywords:
            return {"positive": 0.9, "negative": 0.05, "neutral": 0.05}
        elif word in negative_keywords:
            return {"positive": 0.05, "negative": 0.9, "neutral": 0.05}
        else:
            # Infer from associations
            assoc = self.get_associations(word)
            
            if not assoc:
                return {"positive": 0.33, "negative": 0.33, "neutral": 0.34}
            
            pos_score = sum(
                score for w, score in assoc.items()
                if w in positive_keywords
            ) / len(assoc)
            
            neg_score = sum(
                score for w, score in assoc.items()
                if w in negative_keywords
            ) / len(assoc)
            
            neutral_score = 1.0 - pos_score - neg_score
            
            return {
                "positive": pos_score,
                "negative": neg_score,
                "neutral": max(0, neutral_score)
            }
    
    def get_stats(self) -> Dict:
        """Get statistics"""
        
        total_associations = sum(
            len(v) for v in self.associations.values()
        )
        
        return {
            "total_words": len(self.word_stats),
            "total_associations": total_associations,
            "strongest_associations": [
                (w1, w2, score)
                for w1, assoc in self.associations.items()
                for w2, score in sorted(
                    [(w, d.get("pmi", 0)) for w, d in assoc.items()],
                    key=lambda x: x[1],
                    reverse=True
                )[:3]  # Top 3 per word
            ][:20]  # Top 20 overall
        }
    
    # ─────────────────────────────────
    # Persistence
    # ─────────────────────────────────
    
    def save_to_disk(self):
        """Save associations to JSON"""
        
        data = {
            "metadata": {
                "version": "1.0",
                "updated_at": datetime.now().isoformat(),
                "total_words": len(self.word_stats),
                "total_associations": sum(len(v) for v in self.associations.values())
            },
            "associations": self.associations,
            "word_stats": self.word_stats
        }
        
        try:
            with open(self.save_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving word associations: {e}")
    
    def load_from_disk(self):
        """Load associations from JSON"""
        
        if not self.save_path.exists():
            return
        
        try:
            with open(self.save_path) as f:
                data = json.load(f)
            
            self.associations = data.get("associations", {})
            self.word_stats = data.get("word_stats", {})
        except Exception as e:
            print(f"Error loading word associations: {e}")
    
    # ─────────────────────────────────
    # Publishing
    # ─────────────────────────────────
    
    def publish_update(self, word1: str, word2: str):
        """Publish association update to event_bus"""
        
        if word1 in self.associations and word2 in self.associations[word1]:
            pmi = self.associations[word1][word2].get("pmi", 0)
            
            self.event_bus.publish("word_association:updated", {
                "word1": word1,
                "word2": word2,
                "pmi": float(pmi),
                "timestamp": time.time()
            })


def init_module(event_bus, config=None):
    """Initialize Layer 1 module"""
    instance = WordAssociationsLearner(event_bus, config)
    event_bus.publish("module_loaded", {"name": "word_associations"})
    return instance
```

---

## NEXT STEPS

1. **FASE 1 starten:** Tokenization + filtering
2. **Test met real data:** Upload memory.jsonl
3. **FASE 2:** Co-occurrence counting
4. **FASE 3:** PMI calculation
5. **Integratie:** Publish naar Layer 3

---

**Status:** READY FOR IMPLEMENTATION  
**Author:** Claude + Kevin  
**Date:** June 29, 2026
