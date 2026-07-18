# 🧠 Nova Roadmap (update)

## ✅ Reeds afgeronde stappen
- **Projectstructuur opgezet**  
  Scheiding tussen `core/`, `modules/`, `tests/`, `data/`, `logs/`, enz.  
  Configuratiebestanden (`config.yaml`, `.env`, `requirements.txt`) toegevoegd.

- **EventBus geïmplementeerd**  
  Centrale communicatie tussen modules.

- **MemoryModule gebouwd**  
  Houdt recente events bij en schrijft naar `logs/interactions.jsonl`.

- **SemanticConceptsModule gebouwd**  
  - Auto‑learning van onbekende woorden → `"unknown"`  
  - Teach‑concept events → `"new"` of `"updated"`  
  - Snapshot (`data/concepts.json`) en logboek (`logs/concepts.jsonl`) persistent gemaakt  
  - **Q&A‑laag toegevoegd**: antwoorden op “wie ben jij?”, “wat is mijn naam?”, “wat betekent <woord>?”  
  - **Teach‑commando werkt live in chat** → woorden leren en updaten direct via input

- **Volledige test suite**  
  13 tests geschreven en groen gekregen (pytest alles passed).  
  Fixture toegevoegd voor schone testomgeving.

- **Bestanden verplaatst naar juiste mappen**  
  Snapshots in `data/`, logs in `logs/`.

- **Runtime chat (main.py)**  
  Input van jou → output van Nova (events + updates).  
  Live feedback op leren en Q&A.

---

## 🚀 Volgende stappen
- **Personality Engine**  
  Module die bepaalt hoe Nova antwoordt (toon, stijl, karakter).  
  Combineert semantische kennis met een “stem”.

- **Emergent Behavior**  
  Nova combineert concepten tot nieuwe inzichten.  
  Voorbeeld: `"pizza = eten"` + `"Kevin = user"` → “Kevin houdt van pizza”.

- **SentenceLearningModule (toekomst)**  
  Opslaan van volledige zinnen met structuur (subject, verb, object).  
  Gescheiden van woordenboek (`sentences.json`).

- **Auto‑teacher module**  
  Periodiek onbekende woorden ophalen via een gratis woordenboek‑API.  
  Transparant loggen met `"status": "auto"`.

- **Audit dashboard**  
  Overzicht van wat Nova geleerd heeft, wanneer, en hoe (auto, teach, update).  
  Start als CLI‑tool, later mogelijk webinterface.

---

## 🚀 Milestones

### Milestone 1 — Kernwoorden leren
- Batchjes van 5–10 woorden per sessie
- Start met vraagwoorden, pronouns, basiswerkwoorden, begroetingen
- Audit logs checken na elke batch
- Testen met betekenisvragen (*“wat betekent X?”*)

### Milestone 2 — Personality Engine (prototype)
- Module die toon en stijl bepaalt
- Begin met 2–3 varianten (formeel, speels, filosofisch)
- Combineer met semantische kennis voor antwoorden

### Milestone 3 — Audit Dashboard (CLI)
- Simpele tool die `concepts.jsonl` uitleest
- Statistieken: aantal woorden geleerd, aantal updates, aantal unknown
- Geeft inzicht en motivatie

### Milestone 4 — SentenceLearningModule
- Opslaan van zinnen met structuur (subject, verb, object)
- Gescheiden bestand (`sentences.json`)
- Eerste patronen: "ik hou van X", "wat is Y?"

### Milestone 5 — Emergent Behavior
- Combineren van concepten tot nieuwe inzichten
- Voorbeeld: `"pizza = eten"` + `"Kevin = user"` → “Kevin houdt van pizza”
- Later uitbreiden naar voorkeuren en simpele redeneringen

### Milestone 6 — AutoTeacher
- Periodiek onbekende woorden ophalen via dictionary‑API
- Transparant loggen met `"status": "auto"`
- Auditabel en controleerbaar

### Milestone 7 — Semantic Expansion
- Uitbreiden van conceptstructuur met definitie, relaties en voorbeelden
- Woorden krijgen meerdere betekenissen via sense_id
- Auditabel loggen met status: polysemy

---

## 📊 Visueel overzicht

    Chat input -> EventBus
    ├─ MemoryModule -> logs/interactions.jsonl
    └─ SemanticConceptsModule
    ├─ auto-learning -> data/concepts.json + logs/concepts.jsonl
    ├─ teach-concept -> data/concepts.json + logs/concepts.jsonl
    ├─ semantic_update -> EventBus
    └─ Q&A -> antwoorden op vragen over woorden en identiteit

    Toekomst:
    ├─ PersonalityEngine -> bepaalt toon van antwoorden
    ├─ EmergentBehavior -> combineert kennis tot nieuwe inzichten
    ├─ SentenceLearningModule -> leert zinnen en structuren
    ├─ AutoTeacher -> verrijkt unknown woorden via API
    └─ AuditDashboard -> inzicht in leerproces

---

## 🔮 Volgende stappen

Integratie Weather API

Koppeling met OpenWeather of vergelijkbare service

Input: “wat is het weer in Brugge?”

Output: EventBus event + log "status": "api"

Uitbreiding Dictionary API (AutoTeacher)

Unknown woorden automatisch verrijken via externe woordenboek‑API

Transparant loggen met "status": "auto"

Personality Engine verfijnen

Meer varianten van toon en stijl

Mogelijkheid tot spiegelend gedrag (reflectie van jouw communicatiestijl)

Audit Dashboard uitbreiden

Van CLI naar webinterface

Grafieken en filters voor leerproces

Emergent Behavior verdiepen

Complexere redeneringen en voorkeuren

Basis voor echte agency en zelfreflectie

Semantic Expansion implementeren

Definitie, relaties en voorbeelden toevoegen aan elk concept

Meerdere betekenissen per woord via sense_id

Auditabel loggen met status: polysemy
