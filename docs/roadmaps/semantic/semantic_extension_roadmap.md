# Semantic Extension Roadmap (Fases 8-13)

**Status:** Planning document  
**Depends on:** semantic.py (Fases 1-7) ✅  
**Timeline:** Jaar 2-5  
**Date:** June 29, 2026  

---

## OVERVIEW

Semantic.py is compleet (Fases 1-7), maar kan **VEEL dieper en breder** gaan.

```
Fases 1-7 (KLAAR): Knowledge graph basics
Fases 8-10: PURE SYMBOLISCH - Dieper redeneren
Fases 11-13: NEURAL + ML - Breder leren
= Ultimate semantic AI
```

---

## FASES 8-10: PURE SYMBOLISCH UITBREIDINGEN

### FASE 8: Causal Reasoning (Maand 1-2)

**Wat:** Oorzaak-gevolg relaties begrijpen

```
Huidge semantic:
├── Python = programmeertaal
├── Snel = property
└── = Statische feiten

Fase 8 semantic:
├── Python VEROORZAAKT snelheid
├── "Snelheid LEIDT TOT efficiëntie"
├── "Efficiëntie VERHOOGT productiviteit"
└── = Causale ketens!
```

**Data structure:**

```json
{
  "causal_relations": {
    "python": {
      "causes": [
        {"effect": "snelheid", "strength": 0.9},
        {"effect": "elegantie", "strength": 0.85}
      ]
    },
    "snelheid": {
      "causes": [
        {"effect": "efficiëntie", "strength": 0.88},
        {"effect": "tijdsbesparing", "strength": 0.92}
      ]
    }
  },
  
  "causal_chains": [
    ["python", "snelheid", "efficiëntie", "productiviteit"]
  ]
}
```

**API:**

```python
# Get causal chain
chain = semantic.get_causal_chain("python")
# Output: python → snelheid → efficiëntie → productiviteit

# Causal reasoning
effect = semantic.predict_causal_effect("python", depth=3)
# Output: Wat zijn alle gevolgen van Python? (3 lagen diep)
```

**Implementation sketch:**

```python
class CausalReasoner:
    def add_causal_relation(self, cause, effect, strength):
        """Add: cause LEADS TO effect"""
        if cause not in self.causal_graph:
            self.causal_graph[cause] = {"causes": []}
        
        self.causal_graph[cause]["causes"].append({
            "effect": effect,
            "strength": strength
        })
    
    def get_causal_chain(self, concept, max_depth=5):
        """Trace causal chain from concept"""
        chain = [concept]
        current = concept
        
        for depth in range(max_depth):
            if current not in self.causal_graph:
                break
            
            causes = self.causal_graph[current]["causes"]
            if not causes:
                break
            
            # Follow strongest causal link
            next_effect = max(causes, key=lambda x: x["strength"])
            chain.append(next_effect["effect"])
            current = next_effect["effect"]
        
        return chain
```

---

### FASE 9: Temporal Semantics (Maand 3-4)

**Wat:** Tijd toevoegen aan kennis

```
Huidge:
├── Python = populair
└── = Altijd waar

Fase 9:
├── Python = populair SINDS 2010
├── Machine learning = groeiend TREND
├── Quantum computing = TOEKOMST (2030+)
└── = Historische context!
```

**Data structure:**

```json
{
  "temporal_concepts": {
    "python": {
      "emerged": 1991,
      "popularity_start": 2010,
      "current_trend": "stable_high",
      "timeline": {
        "1991-2005": "niche",
        "2005-2010": "growing",
        "2010-present": "dominant"
      }
    },
    
    "ai": {
      "emerged": 1956,
      "AI_winter_1": [1974, 1980],
      "AI_winter_2": [1987, 1993],
      "current_trend": "explosive",
      "future_prediction": "AGI_2030+"
    }
  }
}
```

**API:**

```python
# When was concept popular?
timeline = semantic.get_temporal_timeline("python")
# Output: {1991: "niche", 2010: "growing", 2023: "dominant"}

# What's trending now?
trending = semantic.get_current_trends()
# Output: ["AI", "quantum", "neural_networks"]

# What's coming?
future = semantic.predict_future_concepts(years=5)
# Output: Concepts expected to rise in next 5 years
```

---

### FASE 10: Uncertainty & Confidence (Maand 5-6)

**Wat:** Nuance in kennis (niet alles is 100% zeker)

```
Huidge:
├── "Python is snel" = WAAR
└── = Zwart/wit

Fase 10:
├── "Python is snel" (0.95 confidence)
├── "Quantum breaks RSA" (0.3 confidence)
├── "AGI by 2030" (0.2 confidence)
└── = Grijstinten!
```

**Data structure:**

```json
{
  "concepts_with_confidence": {
    "python": {
      "definition": "programmeertaal",
      "confidence": 0.99,
      "properties": {
        "snel": {
          "value": true,
          "confidence": 0.95,
          "evidence_count": 147
        },
        "elegant": {
          "value": true,
          "confidence": 0.87,
          "evidence_count": 89
        }
      }
    },
    
    "quantum_computing": {
      "can_break_rsa": {
        "value": true,
        "confidence": 0.35,
        "evidence_count": 12,
        "uncertainty_reason": "Not yet practically demonstrated"
      }
    }
  }
}
```

**API:**

```python
# Get confidence of claim
conf = semantic.get_claim_confidence("python", "snel")
# Output: {"value": True, "confidence": 0.95, "evidence": 147}

# What do we NOT know?
unknowns = semantic.get_uncertain_claims(min_confidence=0.5)
# Output: Claims with <50% confidence (research needed!)

# Explain uncertainty
reason = semantic.explain_uncertainty("quantum_breaks_rsa")
# Output: "Not yet practically demonstrated"
```

---

## FASES 11-13: NEURAL + ML UITBREIDINGEN

### FASE 11: Knowledge Extraction (ML) (Maand 7-8)

**Wat:** Automatisch concepten + relaties leren van tekst

```
Huidge (manual):
Kevin: "/teach python programmeertaal"
Nova: (slaat op)

Fase 11 (auto):
Nova: (leest artikel over Python)
      (ML haalt automatisch uit)
      (voegt toe aan semantic)
= SNELLER LEREN!
```

**Tools:**

```
- spaCy (NLP)
- Named Entity Recognition
- Relation Extraction
- Dependency parsing
```

**API:**

```python
# Extract from text
concepts = semantic.extract_from_text(
    "Python is a programming language used for data science"
)
# Output: 
# {
#   "entities": ["Python", "programming language", "data science"],
#   "relations": [
#     ("Python", "is_a", "programming_language"),
#     ("Python", "used_for", "data_science")
#   ]
# }

# Auto-learn from URL
semantic.learn_from_url("https://en.wikipedia.org/wiki/Python")
# Automatically extracts and adds to knowledge graph
```

**Implementation sketch:**

```python
import spacy
from spacy.cli import download

class KnowledgeExtractor:
    def __init__(self):
        # Load Dutch NLP model
        self.nlp = spacy.load("nl_core_news_sm")
    
    def extract_concepts(self, text):
        """Extract entities from text"""
        doc = self.nlp(text)
        
        entities = []
        for ent in doc.ents:
            entities.append({
                "text": ent.text,
                "label": ent.label_,
                "confidence": 0.85
            })
        
        return entities
    
    def extract_relations(self, text):
        """Extract subject-verb-object relations"""
        doc = self.nlp(text)
        
        relations = []
        for token in doc:
            if token.dep_ == "ROOT":  # Main verb
                subject = self._get_subject(token)
                obj = self._get_object(token)
                
                if subject and obj:
                    relations.append({
                        "subject": subject,
                        "relation": token.text,
                        "object": obj
                    })
        
        return relations
    
    def _get_subject(self, verb_token):
        """Find subject of verb"""
        for child in verb_token.children:
            if child.dep_ in ["nsubj", "nsubjpass"]:
                return child.text
        return None
    
    def _get_object(self, verb_token):
        """Find object of verb"""
        for child in verb_token.children:
            if child.dep_ in ["dobj", "attr"]:
                return child.text
        return None
```

---

### FASE 12: Semantic Similarity (Embeddings) (Maand 9-10)

**Wat:** Numerical representations van concepten (word embeddings)

```
Huidge:
├── Python vs Ruby: ?
├── Python vs Rust: ?
└── = Manueel bepalen

Fase 12 (embeddings):
├── Python embedding: [0.45, 0.82, 0.21, ...]
├── Ruby embedding: [0.48, 0.79, 0.23, ...]
├── Distance: 0.08 (DICHT!)
├── Rust embedding: [0.52, 0.75, 0.18, ...]
├── Distance: 0.15 (verder)
└── = AUTOMATISCH bepaald!
```

**Tools:**

```
- Word2Vec
- GloVe
- FastText
- Sentence-Transformers (latest)
```

**API:**

```python
# Get embedding for concept
emb = semantic.get_embedding("python")
# Output: [0.45, 0.82, 0.21, ...]

# Calculate similarity
sim = semantic.similarity("python", "ruby")
# Output: 0.92 (very similar languages)

sim2 = semantic.similarity("python", "painting")
# Output: 0.15 (very different)

# Find similar concepts
similar = semantic.find_similar("python", top_k=5)
# Output: [("ruby", 0.92), ("javascript", 0.87), ...]
```

**Implementation sketch:**

```python
from sentence_transformers import SentenceTransformer
import numpy as np

class SemanticSimilarity:
    def __init__(self):
        # Load pre-trained model
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.embeddings = {}
    
    def get_embedding(self, concept):
        """Get or create embedding for concept"""
        
        if concept in self.embeddings:
            return self.embeddings[concept]
        
        # Create embedding from concept definition
        definition = semantic.get_definition(concept)
        text = f"{concept}: {definition}"
        
        embedding = self.model.encode(text)
        self.embeddings[concept] = embedding
        
        return embedding
    
    def similarity(self, concept1, concept2):
        """Calculate cosine similarity"""
        
        emb1 = self.get_embedding(concept1)
        emb2 = self.get_embedding(concept2)
        
        # Cosine similarity
        similarity = np.dot(emb1, emb2) / (
            np.linalg.norm(emb1) * np.linalg.norm(emb2)
        )
        
        return float(similarity)
    
    def find_similar(self, concept, top_k=5):
        """Find most similar concepts"""
        
        emb = self.get_embedding(concept)
        similarities = []
        
        for other_concept in semantic.all_concepts():
            if other_concept == concept:
                continue
            
            sim = self.similarity(concept, other_concept)
            similarities.append((other_concept, sim))
        
        # Sort and return top K
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]
```

---

### FASE 13: Graph Visualization & Advanced Queries (Maand 11-12)

**Wat:** Visualiseer en query de complete knowledge graph

```
Visualisatie:
├── Nodes = concepten
├── Edges = relaties
├── Colors = confidence
├── Size = importance
└── = Mooi overzicht!

Advanced queries:
├── "Alle concepten related aan Python?"
├── "Hoe zijn Python en AI verbonden?"
├── "Welke concepten zijn onzeker?"
└── = Complex reasoning!
```

**Tools:**

```
- Plotly / Pyvis (visualization)
- NetworkX (graph analysis)
- GraphQL (advanced queries)
```

**API:**

```python
# Visualize knowledge graph
semantic.visualize_graph(
    center="python",
    depth=2,
    show_confidence=True
)
# Output: Interactive HTML graph

# Advanced queries
results = semantic.query_graph(
    "all_concepts_related_to(python, depth=2)"
)
# Output: All concepts 2 hops away from Python

# Path finding
path = semantic.find_path("python", "AGI")
# Output: Shortest path between concepts
```

---

## INTEGRATION MET NOVA

### Hoe semantic extensions helpen andere lagen:

```
Layer 1 (Word Associations):
├── Similarity: "Rust lijkt op Python" (auto)
└── Uses: Embeddings (Fase 12)

Layer 4 (Response Generation):
├── "Python VEROORZAAKT snelheid"
├── "En snelheid LEIDT TOT efficiëntie"
└── Uses: Causal reasoning (Fase 8)

Layer 7 (Emergence):
├── "Python was populair SINDS 2010"
├── "Je interest in Python groeit"
├── "Quantum computing TOEKOMST"
└── Uses: Temporal semantics (Fase 9)
```

---

## IMPLEMENTATION TIMELINE

```
JAAR 2 (Maanden 1-6):
├── Fase 8: Causal Reasoning (pure symbolisch)
├── Fase 9: Temporal Semantics
├── Fase 10: Uncertainty Tracking
└── = Dieper redeneren, nóg steeds pure symbolisch

JAAR 2-3 (Maanden 7-12):
├── Fase 11: Knowledge Extraction (spaCy)
├── Fase 12: Embeddings (SentenceTransformers)
└── Fase 13: Visualization (Plotly)
   = Neural/ML integratie!
```

---

## REQUIREMENTS

### Pure symbolisch (Fases 8-10):
```
Geen externe libraries nodig!
- Standard Python
- Json
- Custom logic
```

### Neural/ML (Fases 11-13):

```python
pip install spacy
python -m spacy download nl_core_news_sm

pip install sentence-transformers

pip install networkx plotly pyvis

# Optioneel voor advanced:
pip install transformers torch  # Heavy, maar powerful
```

---

## SUMMARY

```
SEMANTIC.PY FASES 1-7 (KLAAR):
= Foundation + query + learning

SEMANTIC.PY FASES 8-10 (PURE SYMBOLISCH):
= Causal + Temporal + Uncertainty
= Dieper begrijpen zonder ML

SEMANTIC.PY FASES 11-13 (ML):
= Auto-learning + Similarity + Visualization
= Sneller en slimmer groeien

= ULTIMATE SEMANTIC ENGINE
```

---

**Status:** PLANNING  
**Complexity:** HIGH  
**Impact:** TRANSFORMATIVE  
**Timeline:** Jaar 2-3
