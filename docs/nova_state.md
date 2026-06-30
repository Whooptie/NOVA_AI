# 🧠 Nova — State of the Project

> Laatste update: juni 2026
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

Gespecialiseerde externe modellen (codeer, vision, ML) mogen later als "ingehuurde specialisten" via aparte modules worden aangeroepen — maar vormen nooit Nova's kern.

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
│	└── knowledge/
│		└── wikipedia_teacher.py
├── identity/
│   ├── blueprint/
│   │   ├── loader.py
│   │   ├── identity.json
│   │   └── schema.json
│   ├── personality/
│   │   ├── personality_engine.py
│   │   ├── behavior_modifiers.py
│   │   ├── traits.json
│   │   ├── identity_state.json
│   │   └──	traits.json
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
| intent_router.py | ✅ Klaar | Volledig semantic-aware. Wikipedia, synoniemen, antoniemen, relaties, definitievragen gekoppeld. time_query bug opgelost (uur-in-woord). handle_confirmation() nog leeg. |
| memory.py        | ✅ Klaar | **Windows-pad hardcoded** (`C:\Nova_AI\data\`) — aanpassen bij OS-wissel |
| patterns.py      | ✅ Klaar | Woordtelling + event-counts, geen ritme/gewoonte-detectie |
| logger.py        | ✅ Klaar | Logt alle events naar nova.log |
| semantic.py      | ✅ Klaar | Alle 7 fases volledig. Reasoning Layer actief (chaining, inference, contradiction detection). Auto-extract is_a uit definities. Wikipedia fallback geïntegreerd. |

### MODULES

| Module                  | Status   | Opmerkingen |
| ----------------------- | -------- | ----------- |
| time.py                 | ✅ Klaar | Zone-aware tijdsvraag |
| zone.py                 | ✅ Klaar | Auto-timezone via IP, fallback naar OS |
| weather.py              | ✅ Klaar | **⚠️ URGENT: API-key hardcoded én publiek geworden in chat — nieuwe key aanmaken + naar .env** |
| math.py                 | ✅ Klaar | Berekeningen, temperatuurconversie, wiskundige functies |
| chat.py                 | ✅ Klaar | Automatische Wikipedia fallback bij onbekend woord. Dode code aanwezig: on_greeting + on_fallback uitgecommentarieerd. |
| response_pipeline.py    | ✅ Klaar | **Alleen greeting + fallback gaan door personality/tone pipeline — rest nog niet** |
| chat_response_engine.py | ✅ Klaar | Doorsturen van pipeline_response naar expression_inject |
| expression_injector.py  | ✅ Klaar | Emoji, gesture, puberal flair injectie |
| wikipedia_teacher.py    | ✅ Klaar | Nederlandse Wikipedia API, disambiguatie-afhandeling, is_a relatie-extractie, automatische fallback vanuit chat.py |
| chess_engine.py          | ✅ Klaar | Stockfish-koppeling via python-chess (UCI). Persistente partijstand (chess_game.json), lazy engine-start, netjes afgesloten bij exit. Natuurlijke taal voor zetten. Bordweergave met schaaksymbolen (wit/magenta). Instelbare moeilijkheidsgraad (niveau 0-20). Win/verlies statistieken (chess_stats.json). |

### IDENTITY

| Module                | Status   | Opmerkingen |
| --------------------- | -------- | ----------- |
| loader.py             | ✅ Klaar | Laadt + valideert identity.json tegen schema.json |
| identity.json         | ✅ Klaar | Volledig persoonlijkheidsprofiel |
| schema.json           | ✅ Klaar | JSON Schema validatie |
| personality_engine.py | ✅ Klaar | Traits + state + behavior modifiers |
| behavior_modifiers.py | ✅ Klaar | Energie, impulsiviteit, dramatic flair |
| traits.json           | ✅ Klaar | Numerieke persoonlijkheidswaarden (0.0–1.0) |
| identity_state.json   | ✅ Klaar | Dynamische staat — **overstimulation.level staat standaard op 1.0 (max)** |
| emotion_engine.py     | ✅ Klaar | Trigger-gebaseerde emotie-updates |
| emotion_state.json    | ✅ Klaar | Huidige emotionele staat |
| emotion_rules.json    | ✅ Klaar | Regels voor mood-shifts, sync, dramatic flair |
| tone_engine.py        | ✅ Klaar | Mood → tone → style profile |
| style_profiles.json   | ✅ Klaar | 8 stijlprofielen (emoji, gesture, pitch, volume...) |
| gesture_profiles.json | ✅ Klaar | 7 gebarenprofielen voor toekomstige avatar |
| microlearning.py      | ❌ Leeg  | Bestand bestaat maar is volledig leeg — nog te bouwen |

---

## 🐛 Bekende bugs (prioriteit)

| # | Bug | Bestand | Urgentie |
| - | --- | ------- | -------- |
| 1 | OpenWeatherMap API-key hardcoded én gelekt in chat | weather.py | 🔴 DIRECT |
| 2 | Windows-pad hardcoded in save_path | memory.py | 🟡 Medium |
| 3 | Dode code (uitgecommentarieerde handlers) | chat.py | 🟢 Laag |
| 4 | overstimulation.level = 1.0 als standaard | emotion_state.json | 🟢 Laag |
| 5 | Personality/tone pipeline bypassed door weer/tijd/math/definities | response_pipeline.py | 🟡 Medium |
| 6 | Punt aan einde van woord wordt meegenomen bij wiki-aanroep | chat.py | 🟢 Laag |
| 7 | Oude concepts.json entries hebben geen auto_extract relaties | concepts.json | 🟢 Laag |

---

## 🔄 Semantic v2 — Aparte roadmap

| Fase | Omschrijving | Status |
| ---- | ------------ | ------ |
| 1 | Datastructuur & opslag | 100% ✅ |
| 2 | Teach & Auto-Learn | 100% ✅ |
| 3 | Relation Engine | 100% ✅ |
| 4 | Query Engine | 100% ✅ |
| 5 | Integratie (intent_router, chat, pipeline) | 100% ✅ |
| 6 | Wikipedia-module | 100% ✅ |
| 7 | Reasoning Layer (chaining, inference) | 100% ✅ |

**concepts.json:** gevuld met testdata (hond, dier, appel, pitvrucht, vliegtuig, democratie...) — productiedata, niet wissen.

---

## 🚀 Volgende stappen (in volgorde van prioriteit)

1. **memory.py** uitbreiden — search_memory(), conversatie-geheugen, pad-fix
2. **Personality pipeline** uitbreiden naar alle intents
3. **microlearning.py** bouwen
4. **weather.py** — API-key naar .env (nog steeds urgent)
5. **ML-classifier** toevoegen als sensor voor vrije conversatie (emoties, complimenten, verzoeken)

## ♟️ Chess-module — Aparte roadmap

| Feature | Status |
| ------- | ------ |
| Stockfish-koppeling (UCI) | ✅ Klaar |
| Persistente partijstand (JSON, sessie-onafhankelijk) | ✅ Klaar |
| Netjes afsluiten (engine.quit() bij exit) | ✅ Klaar |
| Natuurlijke taal voor zetten ("pion naar e4") | ✅ Klaar |
| Bordweergave met schaaksymbolen (♔♕) | ✅ Klaar |
| Instelbare moeilijkheidsgraad (Skill Level) | ✅ Klaar |
| Win/verlies statistieken | ✅ Klaar |
| Help-systeem (commando-overzicht per spel) | ✅ Klaar |
| Meerdere bordspellen (dammen, Go, ...) | ❌ Toekomst |
---

## 💡 Architectuurprincipes om te onthouden

- **Local first** — alles draait op Kevin's eigen machine
- **Transparent always** — alles gelogd, audit_log op elk concept
- **Nooit handelen zonder toestemming** — kernprincipe
- **Geen LLM in de kern** — wel externe gespecialiseerde modellen (vision, ML-classificatie) als aparte modules
- **ML mag als sensor** — een classifier die zinnen categoriseert is oké, zolang Nova zelf beslist wat ze doet
- **confidence-schaal:** user = 1.0 / auto_extract = 0.9 / wikipedia = 0.8 / auto = 0.1
- **EventBus-patroon:** élke module communiceert via publish/subscribe, nooit direct

---

## 📊 Grote visie (niet voor morgen)

- 476 geplande modules (xlsx beschikbaar)
- 7-laags learning brain
- Anatomisch lichaamsschema (ver toekomst)
- Robotica-integratie (ver toekomst)
- Emergent behavior / zelf modules specificeren (ver toekomst)