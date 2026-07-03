# 🧠 Nova — State of the Project

> Laatste update: juli 2026
> Doel van dit bestand: altijd als eerste uploaden in een nieuw Claude-gesprek zodat context volledig is.

---

## 👤 Developer

- **Naam:** Kevin
- **Locatie:** Brugge, België
- **Ervaring:** ~1 jaar zelfgeleerd, ~6 maanden actief aan Nova
- **Codeerkennis:** geen voorkennis, werkt volledig met AI-hulp (copy-paste workflow)
- **Taal:** Nederlands (altijd)

---

## 🤖 Wat is Nova?

Nova is een **volledig symbolische, lokale, privacy-first AI companion** — geen LLM, geen cloud.
Ze leert via expliciete concepten (`concepts.json`), relaties en patronen.
Architectuur: **GOFAI / symbolische AI** (expert-systeem-achtig, event-driven).
Kernprincipe: **nooit handelen zonder toestemming van Kevin**.

Gespecialiseerde externe modellen (vision, audio, ML-classificatie) mogen later als "ingehuurde specialisten" via aparte modules worden aangeroepen — maar vormen nooit Nova's kern.

**Nova draait 24/7 als daemon** (1 continue sessie, nooit gestopt behalve manueel of bij reboot).

---

## 📁 Projectstructuur

```
Nova_AI/
├── core/
│   ├── event_bus.py
│   ├── module_loader.py
│   ├── intent_router.py
│   ├── memory.py
│   ├── patterns.py
│   ├── logger.py
│   └── semantic.py
├── modules/
│   ├── time/
│   │   ├── time.py
│   │   └── zone.py
│   ├── weather/
│   │   └── weather.py
│   ├── math/
│   │   └── math.py
│   ├── chat/
│   │   ├── chat.py
│   │   ├── response_pipeline.py
│   │   ├── chat_response_engine.py
│   │   └── expression_injector.py
│   ├── chess/
│   │   └── chess_engine.py
│   ├── help/
│   │   ├── help.py
│   │   └── topics/
│   │       ├── algemeen.py
│   │       └── schaken.py
│   └── knowledge/
│       └── wikipedia_teacher.py
├── identity/
│   ├── blueprint/
│   │   ├── loader.py
│   │   ├── identity.json
│   │   └── schema.json
│   ├── personality/
│   │   ├── personality_engine.py
│   │   ├── behavior_modifiers.py
│   │   ├── traits.json
│   │   └── identity_state.json
│   ├── emotion/
│   │   ├── emotion_engine.py
│   │   ├── emotion_state.json
│   │   └── emotion_rules.json
│   └── expression/
│       ├── tone_engine.py
│       ├── style_profiles.json
│       └── gesture_profiles.json
├── data/
│   ├── chess_game.json
│   ├── chess_stats.json
│   ├── chess_settings.json
│   ├── interactions.jsonl
│   └── concepts.json
├── logs/
│   ├── nova.log
│   └── concepts.jsonl
└── main.py
```

---

## ✅ Modules — Status overzicht

### CORE

| Module           | Status   | Opmerkingen |
| ---------------- | -------- | ----------- |
| event_bus.py     | ✅ Klaar | Stabiel, publish/subscribe + wildcard werkt |
| module_loader.py | ✅ Klaar | Auto-discovery via pkgutil, laadtijdmeting |
| intent_router.py | ✅ Klaar | Volledig semantic-aware. Wikipedia, synoniemen, antoniemen, relaties, definitievragen gekoppeld. handle_confirmation() nog leeg. |
| memory.py        | ✅ Klaar | v2.0 daemon-mode volledig gebouwd (Fase 1-4): portable pad, WAL-SQLite, write-buffering, Query API, achtergrond-onderhoud (archiveren/comprimeren/VACUUM elke 6u). Fase 5 (optimalisatie/polish) nog open, lage prioriteit. |
| patterns.py      | ✅ Klaar | Woordtelling + event-counts. Wordt later vervangen door Layer 2 (pattern_matcher.py). |
| logger.py         | ✅ Klaar | Logt enkel fouten/waarschuwingen naar nova.log (RotatingFileHandler, max 5MB × 3 backups). Volledige eventgeschiedenis zit in memory.py (data/interactions.jsonl + .db). |
| semantic.py      | ✅ VOLLEDIG KLAAR | Alle 7 fases klaar. Reasoning Layer actief (chaining, inference, contradiction detection). Auto-extract is_a. Wikipedia fallback geïntegreerd. |

### MODULES

| Module                  | Status   | Opmerkingen |
| ----------------------- | -------- | ----------- |
| time.py                 | ✅ Klaar | Zone-aware tijdsvraag |
| zone.py                 | ✅ Klaar | Auto-timezone via IP, fallback naar OS |
| weather.py               | ✅ Klaar | API-key in .env, huidig weer + 5-daagse forecast, kledingadvies, weerwaarschuwingen, dag-detectie (morgen/overmorgen/weekdag) |
| math.py                 | ✅ Klaar | Berekeningen, temperatuurconversie, wiskundige functies |
| chat.py                 | ✅ Klaar | Automatische Wikipedia fallback bij onbekend woord. Dode code aanwezig. |
| response_pipeline.py    | ✅ Klaar | **Alleen greeting + fallback gaan door personality/tone pipeline — rest nog niet** |
| chat_response_engine.py | ✅ Klaar | Doorsturen van pipeline_response naar expression_inject |
| expression_injector.py  | ✅ Klaar | Emoji, gesture, puberal flair injectie |
| help.py                 | ✅ Klaar | Help-systeem met topic-bestanden. `help` = algemeen overzicht, `help schaken` = schaakcommando's incl. huidig niveau en denktijd. |
| wikipedia_teacher.py    | ✅ Klaar | Nederlandse Wikipedia API, disambiguatie-afhandeling, is_a relatie-extractie, automatische fallback vanuit chat.py |
| chess_engine.py         | ✅ Klaar | Stockfish (UCI), persistente partijstand (chess_game.json), lazy engine-start, netjes afgesloten bij exit. Natuurlijke taal voor zetten. Bordweergave met schaaksymbolen (wit/magenta). Instelbare moeilijkheidsgraad (0-20) + denktijd, beide persistent (chess_settings.json). Win/verlies statistieken (chess_stats.json). Auto-shutdown Stockfish na 30 min inactiviteit. |
| microlearning.py        | ❌ Leeg  | Bestand bestaat maar is volledig leeg — nog te bouwen |

### IDENTITY

| Module                | Status   | Opmerkingen |
| --------------------- | -------- | ----------- |
| loader.py             | ✅ Klaar | Laadt + valideert identity.json tegen schema.json |
| identity.json         | ✅ Klaar | Volledig persoonlijkheidsprofiel |
| schema.json           | ✅ Klaar | JSON Schema validatie |
| personality_engine.py | ✅ Klaar | Traits + state + behavior modifiers |
| behavior_modifiers.py | ✅ Klaar | Energie, impulsiviteit, dramatic flair |
| traits.json           | ✅ Klaar | Numerieke persoonlijkheidswaarden (0.0–1.0) |
| identity_state.json   | ✅ Klaar | **overstimulation.level staat standaard op 1.0 (max) — fix nodig** |
| emotion_engine.py     | ✅ Klaar | Trigger-gebaseerde emotie-updates |
| emotion_state.json    | ✅ Klaar | Huidige emotionele staat |
| emotion_rules.json    | ✅ Klaar | Regels voor mood-shifts, sync, dramatic flair |
| tone_engine.py        | ✅ Klaar | Mood → tone → style profile |
| style_profiles.json   | ✅ Klaar | 8 stijlprofielen (emoji, gesture, pitch, volume...) |
| gesture_profiles.json | ✅ Klaar | 7 gebarenprofielen voor toekomstige avatar |

---

## 🐛 Bekende bugs (prioriteit)

| # | Bug | Bestand | Urgentie | Status |
| - | --- | ------- | -------- | ------ |
| 1 | OpenWeatherMap API-key hardcoded én gelekt in chat | weather.py | 🔴 DIRECT | ✅ Opgelost (2 juli 2026 — key naar .env, python-dotenv) |
| 1b | Stad-extractie pakte leestekens mee (bv. "gent?" i.p.v. "gent") | weather.py | 🟢 Laag | ✅ Opgelost (2 juli 2026 — strip(".,!?;:") toegevoegd) |
| 1c | Weer-intent werd niet herkend bij korte zinnen ("weer in Gent?") | intent_router.py | 🟡 Medium | ✅ Opgelost (2 juli 2026 — losse woord-detectie i.p.v. vaste triggerzinnen) |
| 1d | Weekdagnaam kwam in het Engels terug ("Monday" i.p.v. "maandag") | weather.py | 🟢 Laag | ✅ Opgelost (3 juli 2026 — eigen NL-weekdaglijst i.p.v. strftime %A) |
| 2 | Windows-pad hardcoded in save_path | memory.py | 🟡 Medium | ✅ Opgelost (2 juli 2026 — portable pad via Path(__file__), werkt op elke PC/gebruiker) |
| 3 | Dode code (uitgecommentarieerde handlers) | chat.py | 🟢 Laag | 🔲 Open |
| 4 | overstimulation.level = 1.0 als standaard | emotion_state.json | 🟢 Laag | 🔲 Open |
| 5 | Personality/tone pipeline bypassed door weer/tijd/math/definities | response_pipeline.py | 🟡 Medium | 🔲 Open |
| 6 | Punt aan einde van woord wordt meegenomen bij wiki-aanroep | chat.py | 🟢 Laag | 🔲 Open |
| 7 | Oude concepts.json entries hebben geen auto_extract relaties | concepts.json | 🟢 Laag | 🔲 Open |

---

## 🌦️ Weather-module — functionaliteit (bijgewerkt 3 juli 2026)

`weather.py` ondersteunt nu:
- Huidig weer (temperatuur, gevoelstemperatuur, beschrijving)
- Luchtvochtigheid, windsnelheid
- Zonsopgang/zonsondergang
- Regenkans (bij voorspelling)
- Kledingadvies (vaste drempel-zinnen, geen vrije generatie)
- Weerwaarschuwingen bij onweer/sneeuw/extreem weer
- Voorspelling voor: vandaag, morgen, overmorgen, specifieke weekdag (bv. "weer op maandag")
- Beperking: max. 5 dagen vooruit (grens van gratis OpenWeatherMap API), met duidelijke foutmelding erbuiten

**Architectuurnotitie:** volledig symbolisch — API-data wordt uitgelezen en in vaste Nederlandse zinsjablonen gegoten (if/else op basis van temperatuur/categorie). Geen LLM, geen vrije tekstgeneratie.

**Mogelijke toekomstige uitbreidingen (nog niet gebouwd):**

1. **Vergelijking met gisteren** — temperatuur van vandaag vergelijken met gisteren (vereist opslag van vorige waarde).

2. **Meer weerwaarschuwingen** — `weerwaarschuwing()` uitbreiden met extra categorieën die nu nog ontbreken: mist ("Mist"), harde wind, hagel. Kleine aanpassing — enkel het `waarschuwingen`-dictionary in `weather.py` aanvullen.

3. **Proactieve automatische weerwaarschuwing** (zonder dat Kevin ernaar vraagt):
   - **Wat:** Nova checkt zelf periodiek (bv. elke 30 min) het weer voor de standaardstad, en stuurt spontaan een `chat_response` als er onweer/sneeuw/extreem weer op komst is.
   - **Architectuur:** vereist een achtergrond-timer, vergelijkbaar met de 6-uur-cyclus in `memory.py` (tiering/maintenance). Past bij Nova's 24/7-daemon-karakter.
   - **Symbolisch:** 100% haalbaar zonder LLM — hergebruikt dezelfde if/else-check die al in `weerwaarschuwing()` zit, plus een simpel "vandaag al gemeld?"-vlaggetje om spam te voorkomen.
   - **Ethiek-overweging:** spontaan spreken is een vorm van handelen zonder directe vraag, maar Kevin heeft hiervoor al vooraf toestemming gegeven (3 juli 2026) — automatische waarschuwing bij noodweer (onweer/sneeuw/extreem weer) mag direct gebouwd worden zonder aparte aan/uit-instelling of bevestigingsvraag vooraf. 
   - **Hangt samen met:** het nog te bouwen proactieve-suggesties-systeem (nog geen aparte module/roadmap voor).

---

## 🧠 7-Laags Memory Architectuur

Nova heeft een volledig uitgewerkt 7-laags geheugen systeem.
**Layer 3 (semantic.py) en Layer 6 (personality_engine.py) zijn al klaar.**

| Laag | Module | Status | Roadmap |
| ---- | ------ | ------ | ------- |
| Layer 0 | memory.py (v2.0) | ✅ KLAAR (alle 4 fases) | memory_layer0_roadmap.md + memory_24-7_daemon_addendum.md |
| Layer 1 | word_associations_learner.py | ❌ Nog te bouwen | memory_layer1_roadmap.md |
| Layer 2 | pattern_matcher.py | ❌ Nog te bouwen | memory_layer2_roadmap.md |
| Layer 3 | semantic.py | ✅ KLAAR | semantic_roadmap.md |
| Layer 4 | response_engine.py | ❌ Nog te bouwen | memory_layer4_roadmap.md |
| Layer 5 | context_manager.py | ❌ Nog te bouwen | memory_layer5_roadmap.md |
| Layer 6 | personality_engine.py | ✅ KLAAR | — |
| Layer 7 | emergence_engine.py | ❌ Nog te bouwen | memory_layer7_roadmap.md |

**Bouwvolgorde:** Layer 0 eerst (foundation), dan 1 → 2 → 4 → 5 → 7.
**Extra, buiten de 7 lagen:** een losse "User Preferences"-module (Kevin's voorkeuren/afkeuren) staat gepland — zie memory_user_preferences_roadmap.md.
---

## 🔄 Semantic — Status & Roadmap

### Fases 1-7 (VOLLEDIG KLAAR ✅)

| Fase | Omschrijving | Status |
| ---- | ------------ | ------ |
| 1 | Datastructuur & opslag | ✅ |
| 2 | Teach & Auto-Learn | ✅ |
| 3 | Relation Engine | ✅ |
| 4 | Query Engine | ✅ |
| 5 | Integratie (intent_router, chat, pipeline) | ✅ |
| 6 | Wikipedia-module | ✅ |
| 7 | Reasoning Layer (chaining, inference) | ✅ |

### Fases 8-13 (Toekomst — semantic_extension_roadmap.md)

| Fase | Omschrijving | Type | Status |
| ---- | ------------ | ---- | ------ |
| 8 | Causal Reasoning | Pure symbolisch | ❌ Toekomst |
| 9 | Temporal Semantics | Pure symbolisch | ❌ Toekomst |
| 10 | Uncertainty Tracking | Pure symbolisch | ❌ Toekomst |
| 11 | Knowledge Extraction (spaCy) | ML | ❌ Toekomst |
| 12 | Semantic Similarity (embeddings) | ML | ❌ Toekomst |
| 13 | Graph Visualization (Plotly) | ML | ❌ Toekomst |

**concepts.json:** gevuld met testdata (hond, dier, appel, pitvrucht, vliegtuig, democratie...) — productiedata, niet wissen.

---

## ♟️ Games — Status & Roadmap

| Spel | Module | Status | Engine |
| ---- | ------ | ------ | ------ |
| Schaak | chess_engine.py | ✅ Klaar | Stockfish (symbolisch) |
| Dammen | checkers_engine.py | ❌ Toekomst | Symbolic engine |
| Go | go_engine.py | ❌ Toekomst | KataGo (neural, bounded) |

**Geplande features:**
- Langzame partijen over weken/maanden
- GUI bord + chat sidebar (tegelijk praten en spelen)
- Commentary per zet ("Interessante zet!")
- Leren van Kevin's spelstijl via Layer 2 (pattern_matcher)

---

## 🔁 Reboot & Hot Reload

| Feature | Status | Roadmap |
| ------- | ------ | ------- |
| /reboot commando (full restart, ~5 sec) | ❌ Bouwen (10 min werk) | reboot_hotreload_roadmap.md |
| /reload module (manual hot reload) | ❌ Later | reboot_hotreload_roadmap.md |
| Auto file watcher (Ctrl+S → reload) | ❌ Veel later | reboot_hotreload_roadmap.md |

---

## 👤 User Preferences (concept, nog niet ingepland)

Losse module die expliciete feiten over Kevin onthoudt (voorkeuren/afkeuren), los van Layer 1.

| Fase | Omschrijving | Status |
| ---- | ------------ | ------ |
| 1 | Databestand + basis CRUD | ❌ Nog te bouwen |
| 2 | Expliciet commando (onthoud:/vergeet:) | ❌ Nog te bouwen |
| 3 | Automatische patroonherkenning | ❌ Nog te bouwen |
| 4 | Integratie in chat.py | ❌ Nog te bouwen |

Leert zowel automatisch (patroonherkenning) als expliciet (commando). Volledig beschreven in: **memory_user_preferences_roadmap.md**

---

## 🌐 24/7 Daemon Mode

Nova draait als **continue daemon** (niet in losse sessies).

Belangrijkste gevolgen voor memory.py v2.0:
- Persistente SQLite-connectie met WAL-mode ✅
- Write buffering + batching ✅
- Achtergrond-onderhoud timer (elke 6u: tiering, compressie, vacuum) ❌ Fase 4
- RAM groeit overdag, krimpt 's nachts (trim naar 500 events) ✅
- Graceful shutdown (atexit + signal handlers) ✅
- Crash recovery bij herstart (JSONL = source of truth) ✅
- Log rotation (JSONL max 50MB) ✅
- clock_tick in ignore_types (anti-ruis bij 24/7) ✅

### memory.py v2.0 — Fase-status

| Fase | Omschrijving | Status |
| ---- | ------------ | ------ |
| 1 | Foundation Fix (paden, retry, log rotation) | ✅ |
| 2 | SQLite + Daemon Basis (WAL, write buffer, graceful shutdown) | ✅ |
| 3 | Query API (search, query, get_stats, find_similar) | ✅ |
| 4 | Achtergrond-onderhoud timer, layer-integratie | ✅ Getest (archiveren, comprimeren, VACUUM, event publishing) |
| 5 | Optimization & polish (query caching, memory leaks, concurrent access, backup, health check) | 🟢 Later — pas nodig bij grote databank/veel gelijktijdige toegang |

Volledig beschreven in: **memory_24-7_daemon_addendum.md**

---

## 🚀 Volgende stappen (in volgorde van prioriteit)

1. 🟡 **reboot_manager.py** — /reboot commando (10 minuten werk)
2. 🟡 **Personality pipeline** — uitbreiden naar alle intents
3. 🟢 **Layer 1** — word_associations_learner.py (memory v2.0 is nu volledig klaar)
4. 🟢 **microlearning.py** — bouwen
5. 🟢 **User preferences-module** — nog te plannen (memory_user_preferences_roadmap.md)
6. 🟢 **memory.py Fase 5** — optimalisatie/polish, enkel nodig bij grote databank of trage queries (geen haast)

---

## 📚 Roadmap documenten (in project)

| Document | Beschrijft |
| -------- | ---------- |
| memory_layer0_roadmap.md | Layer 0: memory.py v2.0 (SQLite, tiering, query API) |
| memory_24-7_daemon_addendum.md | 24/7 daemon aanpassingen voor memory.py |
| memory_layer1_roadmap.md | Layer 1: Word Associations Learner (PMI scoring) |
| memory_layer2_roadmap.md | Layer 2: Pattern Matcher (gedragspatronen) |
| memory_layer4_roadmap.md | Layer 4: Response Generation Engine |
| memory_layer5_roadmap.md | Layer 5: Context Manager (interruption logic) |
| memory_layer7_roadmap.md | Layer 7: Emergence Engine (zelfbewustzijn) |
| semantic_roadmap.md | Semantic Fases 1-7 (KLAAR — referentie bewaren) |
| semantic_extension_roadmap.md | Semantic Fases 8-13 (toekomstige uitbreidingen) |
| reboot_hotreload_roadmap.md | Reboot + Hot Reload (3 fases) |
| memory_user_preferences_roadmap.md | User Preferences: wat Nova over Kevin onthoudt (voorkeuren/afkeuren) |

---

## 💡 Architectuurprincipes om te onthouden

- **Local first** — alles draait op Kevin's eigen machine
- **Transparent always** — alles gelogd, audit_log op elk concept
- **Nooit handelen zonder toestemming** — kernprincipe
- **Geen LLM in de kern** — wel externe gespecialiseerde modellen (vision, ML-classificatie) als aparte modules
- **ML mag als sensor** — een classifier die zinnen categoriseert is oké, zolang Nova zelf beslist wat ze doet
- **confidence-schaal:** user = 1.0 / auto_extract = 0.9 / wikipedia = 0.8 / auto = 0.1
- **EventBus-patroon:** élke module communiceert via publish/subscribe, nooit direct
- **24/7 daemon** — Nova stopt nooit vanzelf, enkel via /reboot of manueel
- **Autonomie-principe** — Nova suggereert altijd eerst, handelt pas na bevestiging van Kevin

---

## 📊 Grote visie

- **476+ geplande modules** (nova_modules_overview.md beschikbaar)
- **7-laags learning brain** (volledig uitgewerkt in roadmaps)
- **Neuro-symbolisch toekomstpad** (Jaar 3-5): kleine gespecialiseerde neural models als extra sensoren (vision, audio, anomaly detection)
- **Avatar / desktop companion** (Jaar 3-4): bewegende avatar op scherm, real-time emotie-animaties, lipsync
- **Bordspellen** (Jaar 2-3): dammen + Go naast schaak, langzame partijen over weken/maanden
- **Anatomisch lichaamsschema** (ver toekomst)
- **Robotica-integratie** (ver toekomst)
- **Emergent behavior** — Layer 7 (ver toekomst)