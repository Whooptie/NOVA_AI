# Emotional Statement Classifier Roadmap: emotie herkennen in vrije zinnen

**Status:** Concept — nog niet gepland in bouwvolgorde
**Depends on:** intent_router.py ✅, `raw_user_message`-event ✅ (bestaat al dankzij microlearning.py)
**Niet te verwarren met:** `microlearning.py` (Layer 6, Fase 6) — zie expliciet onderscheid hieronder
**Datum:** 19 juli 2026

---

## INHOUDSOPGAVE

1. [Het gat dat dit oplost](#het-gat)
2. [Cruciaal onderscheid met microlearning.py](#onderscheid)
3. [Hoe werkt het?](#hoe-werkt-het)
4. [Data structure](#data-structure)
5. [API design](#api-design)
6. [Fase-roadmap](#fase-roadmap)
7. [Eerlijkheid: wat kan wel/niet](#eerlijkheid)

---

## HET GAT DAT DIT OPLOST {#het-gat}

```
Kevin: "ik ben moe"
         ↓
intent_router.py heeft geen detect_*() die dit herkent
als een emotionele mededeling over Kevin's TOESTAND
         ↓
Valt terug op de gewone fallback
         ↓
Nova geeft een generiek "ik snap het niet"-antwoord
         ↓
Er komt GEEN inhoudelijke, zichtbare reactie
("rust wat uit", "sterkte", ...)
```

Dit is dezelfde soort grens die eerder al besproken is bij "laten we verder schaken" — intent_router.py herkent alleen wat expliciet als patroon is voorzien. Een vrije uitspraak over hoe Kevin zich voelt (moe, blij, gestrest, verdrietig) valt daar op dit moment altijd buiten.

---

## CRUCIAAL ONDERSCHEID MET microlearning.py {#onderscheid}

Nova heeft **al** een werkend ML-classificatiemodel dat op elk bericht draait (`microlearning.py`, Layer 6, Fase 6, klaar sinds 17-18 juli 2026). Op het eerste gezicht lijkt dat hetzelfde probleem op te lossen — dat is het echter niet. Dit onderscheid is de kern van dit hele document:

| | `microlearning.py` (bestaand) | Dit nieuwe document |
|---|---|---|
| **Waar gaat het over?** | Hoe Kevin zich verhoudt tot Nova / het gesprek zelf | Kevin's eigen, algemene gemoedstoestand |
| **Categorieën** | frustratie, waardering, interesse, verwarring, focus, kilte | bv. moe, blij, verdrietig, gestrest, boos (nieuw te bepalen) |
| **Voorbeeldzin** | "dit snap ik echt niet" (verwarring, óver het gesprek) | "ik ben moe" (over Kevin, los van het gesprek) |
| **Gevolg van classificatie** | Past `traits.json` stilzwijgend aan (Nova's persoonlijkheid verschuift langzaam) | Triggert een zichtbaar, direct antwoord van Nova |
| **Zichtbaar voor Kevin?** | Nee — volledig een achtergrondproces | Ja — dit ís de reactie zelf |
| **Luistert al naar `raw_user_message`?** | Ja, al gebouwd | Zou hetzelfde event kunnen hergebruiken (zie verderop) |

**Waarom dit niet gewoon een uitbreiding van microlearning.py's categorieën kan zijn:** microlearning.py's hele ontwerp (marge-gebaseerde zekerheidscheck, koppeling aan `signal_trait_mapping.json`, trage, begrensde trait-aanpassingen) is specifiek gebouwd om **Nova's persoonlijkheid** langzaam te doen evolueren — niet om een concreet, direct antwoord te genereren. Een emotie als "moe" zou daar niet in passen: er is geen zinnige trait om "vermoeidheid" langzaam aan te verschuiven, want dat is geen eigenschap van Nova, het is een toestand van Kevin. Dit vraagt dus om een **eigen, nieuw model met een eigen doel** — geen extra categorie in het bestaande.

**Wat wél hergebruikt kan worden:** het `raw_user_message`-event bestaat al (gepubliceerd door `intent_router.py`'s `route()`, specifiek al gebouwd zodat élk bericht — ook niet-herkende — ergens naartoe gaat). Dit nieuwe model kan op exact hetzelfde event subscriben, volledig parallel aan microlearning.py, zonder dat de twee elkaar raken.

---

## HOE WERKT HET? {#hoe-werkt-het}

```
Kevin typt een zin
       ↓
intent_router.py publiceert (zoals al gebeurt) "raw_user_message"
       ↓
TWEE aparte luisteraars, onafhankelijk van elkaar:
   ├── microlearning.py (bestaand) → past traits.json aan
   └── emotional_statement_classifier.py (nieuw) → checkt
       of dit een emotionele zelf-uitspraak is
       ↓
       JA (bv. "moe", confidence > drempel)?
       ├── publiceert "emotional_statement:detected"
       │   {"emotie": "moe", "confidence": 0.88}
       └── een luisteraar (bv. response_pipeline.py) geeft
           een sjabloon-antwoord terug ("Rust wat uit,
           Kevin.")
       ↓
       NEE (geen duidelijke match)?
       └── niets gebeurt hier, normale fallback-flow
           blijft ongewijzigd
```

**Belangrijk:** dit model bepaalt zelf nooit de tekst van het antwoord — het levert enkel een label + confidence af. De uiteindelijke, vaste sjabloonzin per emotie-categorie is aparte, symbolische logica (zelfde principe als overal elders in Nova: het model classificeert, Nova beslist zelf wat ze ermee doet).

---

## DATA STRUCTURE

### emotional_training_data.json

```json
{
  "voorbeelden": [
    {"tekst": "ik ben moe", "label": "moe"},
    {"tekst": "ik ben doodop", "label": "moe"},
    {"tekst": "ik ben blij vandaag", "label": "blij"},
    {"tekst": "dit irriteert me enorm", "label": "boos"},
    {"tekst": "ik voel me rot", "label": "verdrietig"},
    {"tekst": "ik heb het zwaar momenteel", "label": "gestrest"}
  ],
  "metadata": {
    "laatst_getraind": "2026-07-19",
    "categorieën": ["moe", "blij", "verdrietig", "boos", "gestrest", "neutraal"]
  }
}
```

### Opgeslagen model

```
data/emotional_statement_model.pkl
data/emotional_statement_vectorizer.pkl
```

Zelfde technische aanpak als de bestaande classifiers (TF-IDF + Logistic Regression) — geen nieuwe ML-techniek, enkel een nieuw, eigen model met eigen trainingsdata en eigen doel.

---

## API DESIGN

```python
classifier = EmotionalStatementClassifier(config)

resultaat = classifier.predict("ik ben moe")
# → {"label": "moe", "confidence": 0.88}

classifier.add_training_example("ik ben op", "moe")
classifier.retrain()
```

---

## FASE-ROADMAP {#fase-roadmap}

| Fase | Omschrijving | ML nodig? | Geschat werk |
|---|---|---|---|
| 1 | Categorieën bepalen + startset trainingsvoorbeelden (samen met Kevin) | ❌ Nee | Klein |
| 2 | `emotional_statement_classifier.py` bouwen (TF-IDF + Logistic Regression, zelfde aanpak als bestaande classifiers) | ❌ Nee (klassieke, simpele ML) | Middel |
| 3 | Subscriben op het al bestaande `raw_user_message`-event | ❌ Nee | Klein — hergebruik van bestaande infrastructuur |
| 4 | Sjabloon-antwoorden per emotie-categorie (vaste, symbolische zinnen, met variatie) | ❌ Nee | Klein — vergelijkbaar met expression_injector.py |
| 5 | Drempelwaarde/marge-logica om te bepalen wanneer een classificatie zeker genoeg is (zelfde soort aanpak als microlearning.py's marge-check) | ❌ Nee | Klein — hergebruik van een al bewezen patroon |
| 6 (optioneel) | Periodiek hertrainen, eventueel gevoed door Layer 0-data + een correctie-commando (zelfde principe als `intent_classifier_roadmap.md`) | ❌ Nee | Middel |

**Afhankelijkheden:** vereist geen van de nog te bouwen lagen. Het benodigde event (`raw_user_message`) bestaat al. Volledig onafhankelijk van `microlearning.py` bouwbaar — beide luisteren naar hetzelfde event, maar raken elkaars data/logica nooit.

---

## EERLIJKHEID: WAT KAN WEL/NIET {#eerlijkheid}

- ✅ **Een korte, vrije zin classificeren naar een vaste, beperkte emotie-categorie** — zelfde legitieme ML-gebruik als de twee bestaande classifiers (signal_classifier, microlearning.py's model)
- ✅ **Hergebruik van het bestaande `raw_user_message`-event** — geen nieuwe infrastructuur nodig, enkel een nieuwe luisteraar
- ✅ **Een vast sjabloon-antwoord per herkende categorie** — 100% symbolisch, geen generatie
- ✅ **Confidence/marge gebruiken om te beslissen of Nova hierop reageert** — Nova beslist zelf, model levert enkel een signaal
- ❌ **Dit laten samenvloeien met microlearning.py's traits-aanpassing** — bewust twee gescheiden systemen met een verschillend doel (zie sectie hierboven); vermenging zou beide systemen onduidelijk maken
- ❌ **Verwachten dat elke mogelijke formulering van vermoeidheid/blijdschap/etc. herkend wordt** — net als bij elke classifier hier blijft dit beperkt tot wat er getraind is; nieuwe varianten vereisen nieuwe voorbeelden
- ❌ **Nova een origineel, invoelend antwoord laten verzinnen op basis van de herkende emotie** — de reactie blijft een vooraf geschreven sjabloon (eventueel met wat variatie), geen vrije, gegenereerde troost — dat zou weer de grens richting LLM overschrijden

**Status in de bouwvolgorde:** logisch, klein, onafhankelijk project. Kan gebouwd worden op elk moment, zonder te wachten op andere lagen — enkel het al bestaande `raw_user_message`-event is nodig.

---

## RELATIE TOT ANDERE DOCUMENTEN

```
emotional_statement_classifier (dit document)
├── Draait PARALLEL aan: microlearning.py (bestaand)
│   — zelfde event, ander doel, geen overlap in data/logica
├── Gebruikt dezelfde technische aanpak als: 
│   signal_classifier (Layer 6) en intent_classifier_roadmap.md
│   — telkens een eigen, klein, begrensd model, geen gedeelde inhoud
└── Zou, indien gewenst, later gekoppeld kunnen worden aan
    pending_question_roadmap.md — maar is daar niet van afhankelijk;
    dit reageert direct op een NIEUWE, ongevraagde uitspraak, niet
    op een antwoord op een eerdere vraag van Nova
```

---

**Status:** PLANNING — nog niet gebouwd
**Auteur:** Claude + Kevin
