# Intent Classifier Roadmap: ML als specialist naast intent_router

**Status:** Concept — nog niet gepland in bouwvolgorde
**Depends on:** memory.py (Layer 0) ✅ Fase 1-4 klaar
**Gebruikt door:** intent_router.py (als extra, optionele check)
**Datum:** 4 juli 2026

---

## INHOUDSOPGAVE

1. [Wat is dit?](#wat-is-dit)
2. [Waarom dit NIET symbolisch kan](#waarom-niet-symbolisch)
3. [Waarom dit WEL mag met ML](#waarom-wel-met-ml)
4. [Hoe werkt het?](#hoe-werkt-het)
5. [Data structure](#data-structure)
6. [API design](#api-design)
7. [Fase-roadmap](#fase-roadmap)
8. [Eerlijkheid: wat kan wel/niet](#eerlijkheid)

---

## WAT IS DIT?

Een **klein, lokaal ML-classificatiemodel** dat naast `intent_router.py` draait. Het lost een specifiek probleem op:

```
Kevin typt: "schaak" 
→ intent_router herkent dit (bekend patroon) ✅

Kevin typt: "laten we verder schaken"
→ intent_router herkent dit NIET (geen bekend patroon) ❌
→ Nova reageert niet zoals verwacht
```

Een intent-classifier voorspelt bij een NIEUWE, onbekende zin naar welke categorie (chess, weather, time, ...) die waarschijnlijk hoort — ook al staat die exacte zin niet letterlijk in `intent_router.py`.

---

## WAAROM DIT NIET SYMBOLISCH KAN {#waarom-niet-symbolisch}

Dit is een belangrijk, eerlijk punt — geen "nog een Layer" oplossing.

```
ALLE 7 MEMORY-LAGEN (Layer 0-7) WERKEN NÁ intent_router:

Layer 0 (memory)     → slaat events op die AL een event_type hebben
Layer 1 (word assoc) → telt woorden die AL getokenized zijn
Layer 2 (patterns)   → telt timestamps van AL herkende events
Layer 3 (semantic)   → zoekt concepten op met een BEKENDE naam
Layer 7 (emergence)  → analyseert patronen die AL ontdekt zijn

= Geen van deze lagen kan intent_router VOORAF
  helpen een NIEUWE zinsvorm te herkennen.
  Dat zou taalbegrip/generalisatie vereisen —
  precies wat symbolische patroonmatching niet kan
  zonder dat je elke variant handmatig toevoegt.
```

**Een "Layer 8" die dit symbolisch zou proberen op te lossen, zou in feite een taalmodel moeten worden.** Dat willen we niet — dus dit wordt geen nieuwe memory-laag, maar een aparte, begrensde specialist-tool.

---

## WAAROM DIT WEL MAG MET ML {#waarom-wel-met-ml}

```
Nova's kernprincipe (nova_state.md):
"Geen LLM in de kern — wel externe gespecialiseerde
 modellen (vision, audio, ML-classificatie) als
 aparte modules. ML mag als sensor, zolang Nova
 zelf beslist wat ze ermee doet."

Een intent-classifier past HIER PRECIES in:
├── Het is een KLEIN, begrensd model
├── Het kiest ALLEEN uit een vaste lijst categorieën
│   (chess, weather, time, math, definitie, ...)
├── Het genereert NOOIT tekst, het classificeert alleen
├── Het draait 100% lokaal, geen cloud
└── Het is dus een SPECIALIST-TOOL, net als Stockfish
    voor schaak of straks KataGo voor Go
```

**Het cruciale verschil met een LLM:**


|                  | LLM                       | Intent classifier (dit document)         |
| ------------------ | --------------------------- | ------------------------------------------ |
| Output           | Vrije tekst, open-eindig  | Eén label uit een vaste, beperkte lijst |
| Voorspelbaarheid | Kan variëren, "creatief" | Deterministisch bij zelfde input         |
| Reikwijdte       | Onbeperkt onderwerp       | Alleen categorieën die jij trainde      |
| Leert bij        | Continu, impliciet        | Alleen bij expliciet hertrainen          |

---

## HOE WERKT HET?

### Twee databronnen voor training

**1. Handmatige startset (Kevin verzint voorbeelden)**

```python
training_data = [
    ("schaak", "chess"),
    ("speel schaak", "chess"),
    ("laten we schaken", "chess"),
    ("nog een potje schaak?", "chess"),
    ("wat is het weer", "weather"),
    ("hoe laat is het", "time"),
    ("wat is een kat", "definition"),
    # ... jij vult dit initieel aan
]
```

**2. Layer 0 als groeiende databron (memory.py)**

```
Kevin gebruikt Nova normaal:
├── "schaak" → chess_engine activeert → Layer 0 slaat op:
│   {"input": "schaak", "matched_intent": "chess"}
│
├── "zullen we een potje schaken?" → NIET herkend
│   Layer 0 slaat op: {"input": "...", "matched_intent": null}
│
└── Kevin corrigeert achteraf (simpel commando, bv.
    "dat ging over schaken") → wordt een NIEUW,
    gelabeld trainingsvoorbeeld

= Layer 0 levert dus de RUWE data, maar Kevin blijft
  nodig om onherkende zinnen te labelen. Dit is GEEN
  volledig autonoom zelflerend systeem.
```

### Verwerking

```
Zin komt binnen
   ↓
intent_router probeert EERST bestaande patroonmatching
   ↓
Match gevonden? → gebruik die (snelst, meest voorspelbaar)
   ↓
Geen match? → stuur zin naar intent_classifier.py
   ↓
Classifier geeft: (label, confidence)
   ↓
confidence > drempel (bv. 0.75)?
   ├── JA → gebruik dat label, voer actie uit
   └── NEE → val terug op fallback / vraag verduidelijking
   ↓
Resultaat + input opslaan in Layer 0 (voor toekomstig hertrainen)
```

**Belangrijk:** de classifier is een AANVULLING, geen vervanging. Bestaande patroonmatching blijft de eerste, snelste, meest betrouwbare laag.

---

## DATA STRUCTURE

### training_data.json

```json
{
  "voorbeelden": [
    {"tekst": "schaak", "label": "chess", "bron": "handmatig"},
    {"tekst": "laten we verder schaken", "label": "chess", "bron": "gecorrigeerd"},
    {"tekst": "wat is het weer in gent", "label": "weather", "bron": "handmatig"},
    {"tekst": "hoe laat is het", "label": "time", "bron": "handmatig"}
  ],
  "metadata": {
    "laatst_getraind": "2026-07-04",
    "aantal_voorbeelden": 4,
    "categorieën": ["chess", "weather", "time", "math", "definition"]
  }
}
```

### Opgeslagen model

```
data/intent_classifier_model.pkl   ← getraind scikit-learn model
data/intent_classifier_vectorizer.pkl   ← tekst-naar-getallen omzetter
```

---

## API DESIGN

```python
classifier = IntentClassifier(config)

# Voorspel intentie van een nieuwe zin
resultaat = classifier.predict("laten we verder schaken")
# → {"label": "chess", "confidence": 0.87}

# Nieuw gelabeld voorbeeld toevoegen (bv. na correctie door Kevin)
classifier.add_training_example("nog een potje schaak?", "chess")

# Hertrainen met alle verzamelde voorbeelden
classifier.retrain()

# Statistieken
classifier.get_stats()
# → {"aantal_voorbeelden": 47, "categorieën": [...], "laatst_getraind": "..."}
```

---

## FASE-ROADMAP


| Fase | Omschrijving                                                                                              | Geschat werk                                               |
| ------ | ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| 1    | Startset trainingsvoorbeelden verzamelen (handmatig, samen met Kevin)                                     | Klein — een lijstje zinnen per categorie                  |
| 2    | `intent_classifier.py` bouwen — model trainen + `predict()` (scikit-learn: TF-IDF + Logistic Regression) | Middel — nieuwe module, maar bekende, simpele ML-aanpak   |
| 3    | Integratie in`intent_router.py` als fallback-check ná bestaande patroonmatching                          | Klein — zoek/vervang in bestaande fallback-afhandeling    |
| 4    | Correctie-commando zodat Kevin onherkende zinnen kan labelen (bv. "dat ging over schaken")                | Middel — nieuw commando-patroon, vergelijkbaar met`teach` |
| 5    | Periodiek hertrainen vanuit Layer 0-data (achtergrondtaak, vergelijkbaar met memory.py's 6-uur-onderhoud) | Middel — hergebruikt bestaande timer-aanpak               |

**Geen daemon-complexiteit nodig** voor het model zelf — het hertrainen kan een simpele, losse taak zijn die af en toe (bv. 1x per dag/week) draait, niet continu.

---

## EERLIJKHEID: WAT KAN WEL/NIET {#eerlijkheid}

- ✅ **Classificeren van een zin naar een vaste, bekende categorie** — 100% legitiem ML-gebruik als specialist-tool, net als Stockfish voor schaak
- ✅ **Confidence-score gebruiken om te beslissen of Nova de classificatie vertrouwt** — symbolische beslissingslogica bovenop het ML-resultaat, Nova beslist zelf
- ✅ **Hertrainen op basis van Layer 0-data + Kevin's correcties** — reproduceerbaar, uitlegbaar proces, geen black-box
# Intent Classifier Roadmap: ML als specialist naast intent_router

**Status:** Concept — nog niet gepland in bouwvolgorde
**Depends on:** memory.py (Layer 0) ✅ Fase 1-4 klaar
**Gebruikt door:** intent_router.py (als extra, optionele check)
**Datum:** 4 juli 2026

---

## INHOUDSOPGAVE

1. [Wat is dit?](#wat-is-dit)
2. [Waarom dit NIET symbolisch kan](#waarom-niet-symbolisch)
3. [Waarom dit WEL mag met ML](#waarom-wel-met-ml)
4. [Hoe werkt het?](#hoe-werkt-het)
5. [Data structure](#data-structure)
6. [API design](#api-design)
7. [Fase-roadmap](#fase-roadmap)
8. [Eerlijkheid: wat kan wel/niet](#eerlijkheid)

---

## WAT IS DIT?

Een **klein, lokaal ML-classificatiemodel** dat naast `intent_router.py` draait. Het lost een specifiek probleem op:

```
Kevin typt: "schaak" 
→ intent_router herkent dit (bekend patroon) ✅

Kevin typt: "laten we verder schaken"
→ intent_router herkent dit NIET (geen bekend patroon) ❌
→ Nova reageert niet zoals verwacht
```

Een intent-classifier voorspelt bij een NIEUWE, onbekende zin naar welke categorie (chess, weather, time, ...) die waarschijnlijk hoort — ook al staat die exacte zin niet letterlijk in `intent_router.py`.

---

## WAAROM DIT NIET SYMBOLISCH KAN {#waarom-niet-symbolisch}

Dit is een belangrijk, eerlijk punt — geen "nog een Layer" oplossing.

```
ALLE 7 MEMORY-LAGEN (Layer 0-7) WERKEN NÁ intent_router:

Layer 0 (memory)     → slaat events op die AL een event_type hebben
Layer 1 (word assoc) → telt woorden die AL getokenized zijn
Layer 2 (patterns)   → telt timestamps van AL herkende events
Layer 3 (semantic)   → zoekt concepten op met een BEKENDE naam
Layer 7 (emergence)  → analyseert patronen die AL ontdekt zijn

= Geen van deze lagen kan intent_router VOORAF
  helpen een NIEUWE zinsvorm te herkennen.
  Dat zou taalbegrip/generalisatie vereisen —
  precies wat symbolische patroonmatching niet kan
  zonder dat je elke variant handmatig toevoegt.
```

**Een "Layer 8" die dit symbolisch zou proberen op te lossen, zou in feite een taalmodel moeten worden.** Dat willen we niet — dus dit wordt geen nieuwe memory-laag, maar een aparte, begrensde specialist-tool.

---

## WAAROM DIT WEL MAG MET ML {#waarom-wel-met-ml}

```
Nova's kernprincipe (nova_state.md):
"Geen LLM in de kern — wel externe gespecialiseerde
 modellen (vision, audio, ML-classificatie) als
 aparte modules. ML mag als sensor, zolang Nova
 zelf beslist wat ze ermee doet."

Een intent-classifier past HIER PRECIES in:
├── Het is een KLEIN, begrensd model
├── Het kiest ALLEEN uit een vaste lijst categorieën
│   (chess, weather, time, math, definitie, ...)
├── Het genereert NOOIT tekst, het classificeert alleen
├── Het draait 100% lokaal, geen cloud
└── Het is dus een SPECIALIST-TOOL, net als Stockfish
    voor schaak of straks KataGo voor Go
```

**Het cruciale verschil met een LLM:**


|                  | LLM                       | Intent classifier (dit document)         |
| ------------------ | --------------------------- | ------------------------------------------ |
| Output           | Vrije tekst, open-eindig  | Eén label uit een vaste, beperkte lijst |
| Voorspelbaarheid | Kan variëren, "creatief" | Deterministisch bij zelfde input         |
| Reikwijdte       | Onbeperkt onderwerp       | Alleen categorieën die jij trainde      |
| Leert bij        | Continu, impliciet        | Alleen bij expliciet hertrainen          |

---

## HOE WERKT HET?

### Twee databronnen voor training

**1. Handmatige startset (Kevin verzint voorbeelden)**

```python
training_data = [
    ("schaak", "chess"),
    ("speel schaak", "chess"),
    ("laten we schaken", "chess"),
    ("nog een potje schaak?", "chess"),
    ("wat is het weer", "weather"),
    ("hoe laat is het", "time"),
    ("wat is een kat", "definition"),
    # ... jij vult dit initieel aan
]
```

**2. Layer 0 als groeiende databron (memory.py)**

```
Kevin gebruikt Nova normaal:
├── "schaak" → chess_engine activeert → Layer 0 slaat op:
│   {"input": "schaak", "matched_intent": "chess"}
│
├── "zullen we een potje schaken?" → NIET herkend
│   Layer 0 slaat op: {"input": "...", "matched_intent": null}
│
└── Kevin corrigeert achteraf (simpel commando, bv.
    "dat ging over schaken") → wordt een NIEUW,
    gelabeld trainingsvoorbeeld

= Layer 0 levert dus de RUWE data, maar Kevin blijft
  nodig om onherkende zinnen te labelen. Dit is GEEN
  volledig autonoom zelflerend systeem.
```

### Verwerking

```
Zin komt binnen
   ↓
intent_router probeert EERST bestaande patroonmatching
   ↓
Match gevonden? → gebruik die (snelst, meest voorspelbaar)
   ↓
Geen match? → stuur zin naar intent_classifier.py
   ↓
Classifier geeft: (label, confidence)
   ↓
confidence > drempel (bv. 0.75)?
   ├── JA → gebruik dat label, voer actie uit
   └── NEE → val terug op fallback / vraag verduidelijking
   ↓
Resultaat + input opslaan in Layer 0 (voor toekomstig hertrainen)
```

**Belangrijk:** de classifier is een AANVULLING, geen vervanging. Bestaande patroonmatching blijft de eerste, snelste, meest betrouwbare laag.

### Onbekende/niet-passende intents zichtbaar maken

Twee aparte gevallen die niet verward mogen worden:

```
GEVAL 1 — twijfel tussen BEKENDE categorieën
"speel iets rustigs" → classifier: label="chess", confidence=0.55
→ confidence in twijfelzone → pending_question:
  "Bedoel je dat je wil schaken?"
→ Kevin antwoordt ja/nee via bestaand pending_question-mechanisme
  (zelfde patroon als _verwerk_pending_antwoord() nu al gebruikt)
→ "ja" → direct bruikbaar trainingsvoorbeeld voor dat label
→ "nee" → enkel uitsluiting van dat ene label, GEEN nieuw
  trainingsvoorbeeld (Kevin weet dan nog niet wat het WEL was,
  tenzij hij het expliciet zegt: "nee ik bedoelde X")

GEVAL 2 — NIETS past goed (alle scores laag, niet enkel de hoogste)
"kan je mijn planten water geven volgende week" → confidence over
de hele lijn laag → dit is waarschijnlijk een compleet nieuw soort
verzoek, geen twijfel tussen bekende opties
→ NIET gokken, NIET nabevragen als "bedoel je X?" (want er is geen
  goede kandidaat) → apart event + logbestand:

    self.event_bus.publish("onbekend_intent_gedetecteerd", {
        "tekst": text,
        "hoogste_gok": resultaat["label"],
        "confidence": resultaat["confidence"]
    })

→ opslaan in bv. unmatched_intents.jsonl (vergelijkbaar met Layer
  0-logging) → Kevin kan dit later rustig doorlopen als hint-lijst
  voor mogelijke nieuwe modules, i.p.v. blind te moeten verzinnen
  welke modules nog ontbreken
```

**Belangrijke technische kanttekening:** een scikit-learn classificatiemodel kiest altijd het minst-slechte label uit zijn bekende lijst — het heeft geen ingebouwde "ik ken dit helemaal niet"-status. Dat onderscheid (geval 1 vs. geval 2) wordt dus NIET door het model zelf gemaakt, maar symbolisch erbovenop gebouwd: door niet alleen naar de hoogste confidence te kijken, maar naar de hele score-verdeling (plat/laag over de hele lijn = vermoedelijk onbekend, één hoge uitschieter tussen een paar opties = twijfel tussen bekenden).

**Relatie tot LLM — twee gescheiden dingen, niet verwarren:**
- `llm_codegen_tool_roadmap.md` (Kevin roept Claude aan om CODE te genereren) staat hier volledig los van — dat is een ontwikkel-hulpmiddel, geen runtime-gedrag van Nova.
- Scenario 4 "Versneller" (zie recente brainstorm, niet in dit document) is wél relevant: `unmatched_intents.jsonl` zou een goede, natuurlijke input kunnen zijn voor een offline, Kevin-getriggerd LLM-verzoek als "genereer varianten op deze onherkende zinnen" om trainingsdata sneller te laten groeien. Dit blijft ALTIJD Kevin-getriggerd en offline — nooit een automatische aanroep vanuit Nova's eigen daemon-loop naar een LLM tijdens een lopend gesprek.

---

## DATA STRUCTURE

### training_data.json

```json
{
  "voorbeelden": [
    {"tekst": "schaak", "label": "chess", "bron": "handmatig"},
    {"tekst": "laten we verder schaken", "label": "chess", "bron": "gecorrigeerd"},
    {"tekst": "wat is het weer in gent", "label": "weather", "bron": "handmatig"},
    {"tekst": "hoe laat is het", "label": "time", "bron": "handmatig"}
  ],
  "metadata": {
    "laatst_getraind": "2026-07-04",
    "aantal_voorbeelden": 4,
    "categorieën": ["chess", "weather", "time", "math", "definition"]
  }
}
```

### Opgeslagen model

```
data/intent_classifier_model.pkl   ← getraind scikit-learn model
data/intent_classifier_vectorizer.pkl   ← tekst-naar-getallen omzetter
```

---

## API DESIGN

```python
classifier = IntentClassifier(config)

# Voorspel intentie van een nieuwe zin
resultaat = classifier.predict("laten we verder schaken")
# → {"label": "chess", "confidence": 0.87}

# Nieuw gelabeld voorbeeld toevoegen (bv. na correctie door Kevin)
classifier.add_training_example("nog een potje schaak?", "chess")

# Hertrainen met alle verzamelde voorbeelden
classifier.retrain()

# Statistieken
classifier.get_stats()
# → {"aantal_voorbeelden": 47, "categorieën": [...], "laatst_getraind": "..."}
```

---

## FASE-ROADMAP


| Fase | Omschrijving                                                                                              | Geschat werk                                               |
| ------ | ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| 1    | Startset trainingsvoorbeelden verzamelen (handmatig, samen met Kevin)                                     | Klein — een lijstje zinnen per categorie                  |
| 2    | `intent_classifier.py` bouwen — model trainen + `predict()` (scikit-learn: TF-IDF + Logistic Regression) | Middel — nieuwe module, maar bekende, simpele ML-aanpak   |
| 3    | Integratie in`intent_router.py` als fallback-check ná bestaande patroonmatching                          | Klein — zoek/vervang in bestaande fallback-afhandeling    |
| 4    | Correctie-commando zodat Kevin onherkende zinnen kan labelen (bv. "dat ging over schaken")                | Middel — nieuw commando-patroon, vergelijkbaar met`teach` |
| 5    | Periodiek hertrainen vanuit Layer 0-data (achtergrondtaak, vergelijkbaar met memory.py's 6-uur-onderhoud) | Middel — hergebruikt bestaande timer-aanpak               |

**Geen daemon-complexiteit nodig** voor het model zelf — het hertrainen kan een simpele, losse taak zijn die af en toe (bv. 1x per dag/week) draait, niet continu.

---

## EERLIJKHEID: WAT KAN WEL/NIET {#eerlijkheid}

- ✅ **Classificeren van een zin naar een vaste, bekende categorie** — 100% legitiem ML-gebruik als specialist-tool, net als Stockfish voor schaak
- ✅ **Confidence-score gebruiken om te beslissen of Nova de classificatie vertrouwt** — symbolische beslissingslogica bovenop het ML-resultaat, Nova beslist zelf
- ✅ **Hertrainen op basis van Layer 0-data + Kevin's correcties** — reproduceerbaar, uitlegbaar proces, geen black-box
- ❌ **Volledig autonoom, zonder Kevin's input, nieuwe categorieën leren begrijpen** — dit model leert NIET vanzelf bij; het moet actief hertraind worden met nieuwe, gelabelde voorbeelden
- ❌ **Dit gebruiken om vrije, open conversatie te "begrijpen"** — de classifier kiest alleen uit een gesloten lijst van categorieën, het is geen taalbegrip in brede zin
- ❌ **Verwachten dat dit perfect is bij weinig trainingsdata** — met slechts een paar voorbeelden per categorie zal de nauwkeurigheid laag zijn; dit groeit pas nuttig na verloop van tijd, mét actieve input van Kevin

**Status in de bouwvolgorde:** nog niet ingepland. Logisch startpunt is zodra er behoefte is aan bredere zinsherkenning voor een specifieke module (bv. chess_engine) — kan als op zichzelf staand project, onafhankelijk van Layer 1-7.

---

## RELATIE TOT DE 7 MEMORY-LAGEN

```
Layer 0 (memory.py) ✅ AL KLAAR
└── Levert de RUWE databron: elke input + welk label
    (indien bekend) erbij hoorde — noodzakelijke basis

Layer 1 (word_associations) — optioneel, niet noodzakelijk
└── Zou als extra feature kunnen dienen (bv. statistische
    woordverbanden invoeren als extra signaal), maar de
    classifier werkt ook zonder Layer 1

Layer 2, 3, 4, 5, 6, 7 — niet relevant voor dit specifieke stuk
└── Deze gebruiken het RESULTAAT van intent-herkenning,
    ze voeden de classifier niet

Conclusie: dit is vooral een Layer 0-toepassing,
niet iets dat op alle 7 lagen wacht.
```

---

**Status:** PLANNING — nog niet gebouwd
**Auteur:** Claude + Kevin

