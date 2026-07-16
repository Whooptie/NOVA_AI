# 🧠 Nova — State of the Project

> Laatste update: 16 juli 2026
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
│   ├── reboot_manager.py
│   ├── semantic.py
│   └── response_engine.py
├── modules/
│   ├── activity/
│   │   └── session_watcher.py
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
│   ├── knowledge/
│   │   └── wikipedia_teacher.py
│   ├── learning/
│   │   ├── word_associations_learner.py
│   │   └── pattern_matcher.py
│   └── context/
│       ├── context_manager.py
│       ├── activity_detector.py
│       ├── focus_detector.py
│       └── presence_detector.py
├── identity/
│   ├── self_query.py
│   ├── blueprint/
│   │   ├── loader.py
│   │   ├── identity.json
│   │   └── schema.json
│   ├── personality/
│   │   ├── personality_engine.py
│   │   ├── behavior_modifiers.py
│   │   ├── traits.json
│   │   ├── microlearning.py
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
│   ├── interactions.db
│   ├── concepts.json
│   ├── word_associations.json
│   ├── patterns_layer2.json
│   └── context_log.jsonl
│   └── models/
│       └── blaze_face_short_range.tflite
├── logs/
│   ├── nova.log
│   └── concepts.jsonl
└── main.py
```

---

## ✅ Modules — Status overzicht

### CORE

| Module | Status | Opmerkingen |
| --- | --- | --- |
| event_bus.py | ✅ Klaar | Stabiel, publish/subscribe + wildcard werkt |
| module_loader.py | ✅ Klaar | Auto-discovery via pkgutil, laadtijdmeting |
| intent_router.py | ✅ Klaar | Volledig semantic-aware. Wikipedia, synoniemen, antoniemen, relaties, definitievragen gekoppeld. handle_confirmation() nog leeg. |
| memory.py | ✅ Klaar | v2.0 daemon-mode volledig gebouwd (Fase 1-4): portable pad, WAL-SQLite, write-buffering, Query API, achtergrond-onderhoud (archiveren/comprimeren/VACUUM elke 6u). Fase 5 (optimalisatie/polish) nog open, lage prioriteit. |
| patterns.py | ✅ Klaar | Woordtelling + event-counts. Wordt later vervangen door Layer 2 (pattern_matcher.py). |
| logger.py | ✅ Klaar | Logt enkel fouten/waarschuwingen naar nova.log (RotatingFileHandler, max 5MB × 3 backups). Volledige eventgeschiedenis zit in memory.py (data/interactions.jsonl + .db). |
| reboot_manager.py | ✅ Klaar en volledig getest | `/reboot`-commando (Fase 1 van reboot_hotreload_roadmap.md). Sluit memory-buffer + alle modules met `shutdown()` (o.a. Stockfish via chess_engine.py) netjes af, start dan een nieuw los proces via `subprocess.Popen` + `CREATE_NEW_CONSOLE`. Zie volledige sectie "Reboot & Hot Reload" verderop voor details en opgeloste bugs. |
| semantic.py | ✅ VOLLEDIG KLAAR | Alle 7 fases klaar. Reasoning Layer actief (chaining, inference, contradiction detection). Auto-extract is_a. Wikipedia fallback geïntegreerd. Nieuw:`teach_example` event → eigen voorbeeldzinnen toevoegen via `example <woord> <zin>`. **Nieuw (12 juli 2026):** `part_of_chained`/`explain_part_of` (analoog aan is_a_chained/explain_is_a, keten-redenering voor part_of-relaties) en `get_all_subtypes` (omgekeerde is_a-lookup: alle concepten die direct/via keten naar een categorie verwijzen) — beide gebouwd, getest en werkend. Zie sectie "Reasoning Engine — Fase 7.1b/7.5" verderop. |
| response_engine.py | ✅ Klaar (Layer 4, Fase 1-5 + 7) | Combineert semantic + word_associations + pattern_matcher tot sjabloon-antwoorden voor definitievragen. Zie volledige sectie "Layer 4" onder 7-Laags Memory Architectuur. |

### MODULES

| Module | Status | Opmerkingen |
| --- | --- | --- |
| time.py | ✅ Klaar | Zone-aware tijdsvraag |
| zone.py | ✅ Klaar | Auto-timezone via IP, fallback naar OS |
| weather.py | ✅ Klaar | API-key in .env, huidig weer + 5-daagse forecast, kledingadvies, weerwaarschuwingen, dag-detectie (morgen/overmorgen/weekdag) |
| math.py | ✅ Klaar | Berekeningen, temperatuurconversie, wiskundige functies |
| chat.py | ✅ Klaar | Automatische Wikipedia fallback bij onbekend woord. Dode code aanwezig. |
| response_pipeline.py | ✅ Klaar | **Alleen greeting + fallback gaan door personality/tone pipeline — rest nog niet.** Nieuw (8 juli 2026): `on_fallback()` roept nu ook `_auto_learn_from_sentence()` aan — filtert zelfstandige naamwoorden uit de fallback-zin (via `detect_pos`) en slaat onbekende woorden automatisch op als `unknown`-concept via `semantic.auto_learn()`. Functiewoorden (bezittelijke voornaamwoorden, vervoegingen van "gebruiken", etc.) worden expliciet uitgesloten via een stopwoordenlijst — die hoort thuis in Layer 1 (word_associations), niet in concepts.json. |
| chat_response_engine.py | ✅ Klaar | Doorsturen van pipeline_response naar expression_inject |
| expression_injector.py | ✅ Klaar | Emoji, gesture, puberal flair injectie |
| help.py | ✅ Klaar | Help-systeem met topic-bestanden. `help` = algemeen overzicht, `help schaken` = schaakcommando's incl. huidig niveau en denktijd. `algemeen.py` bijgewerkt (3 juli 2026) met `example`-commando en reasoning-sectie. |
| wikipedia_teacher.py | ✅ Klaar | Nederlandse Wikipedia API, disambiguatie-afhandeling, is_a relatie-extractie, automatische fallback vanuit chat.py. Definitie-limiet opgetrokken naar 400 tekens, kapt nooit meer af midden in een woord. Automatische voorbeeldzin-extractie uit Wikipedia geprobeerd maar werkt nog niet betrouwbaar — vervangen door handmatig `example`-commando (zie semantic.py). |
| chess_engine.py | ✅ Klaar | Stockfish (UCI), persistente partijstand (chess_game.json), lazy engine-start, netjes afgesloten bij exit. Natuurlijke taal voor zetten + rokade ("rokeer kort"/"rokeer lang") + promotie ("pion naar e8 dame", standaard dame). Bordweergave met schaaksymbolen (wit/magenta) + zetnummer + materiaaltelling + schaak-melding (beide kanten). Instelbare moeilijkheidsgraad (0-20) + denktijd, beide persistent (chess_settings.json), plus adaptieve auto-aanpassing o.b.v. win/verlies-streak (3 op rij → niveau/denktijd ±). Win/verlies statistieken incl. eindreden (schaakmat/patstand/...) (chess_stats.json). Auto-shutdown Stockfish na 30 min inactiviteit. |
| word_associations_learner.py | ✅ Klaar (Layer 1, alle 5 fases) | PMI-gebaseerd associatienetwerk (data/word_associations.json). Leert van "chat_message"/"chat_response"-events (niet het gecombineerde formaat uit de originele roadmap). Publiceert `word_association:updated`; sinds Layer 4 (8 juli 2026) wordt `find_related()` ook actief gebruikt in Nova's antwoorden. |
| pattern_matcher.py | ✅ Klaar (Layer 2, alle 5 fases) | Detecteert timing-patronen (uur/dag) voor chat_message/chat_response. Anomaly-drempels en opslagfrequentie staan nog op tijdelijke testwaarden (zie Layer 2-sectie). |
| microlearning.py | ❌ Leeg | Bestand bestaat maar is volledig leeg — nog te bouwen |
| context_manager.py | ✅ Fase 1-4 KLAAR (Layer 5) | Combineert tijd + pattern_matcher + activity/focus/presence-detectors tot interruption-advies (`should_interrupt`). Krijgt net als response_engine.py een `layers`-dictionary mee, dus handmatig geladen (niet via dynamische scan). Zie sectie "Layer 5" onder 7-Laags Memory Architectuur. |
| activity_detector.py | ✅ Klaar (Layer 5, Fase 2) | Detecteert actief venster/proces via `pygetwindow` (venstertitel), vertaalt naar activiteit-label (`coding`, `talking_to_nova`, ...). Standaard dynamische module_loader-conventie, geen `layers`-dictionary nodig. |
| focus_detector.py | ✅ Klaar (Layer 5, Fase 3) | Detecteert seconden sinds laatste systeemwijde muis/toetsenbord-input via Windows' `GetLastInputInfo()` (ctypes). Geen keylogging — enkel timing, geen inhoud. Windows-only. |
| presence_detector.py | ✅ Klaar (Layer 5, Fase 4) | Detecteert aanwezigheid (niet identiteit) via webcam, MediaPipe Tasks API (`FaceDetector`, model: BlazeFace short range, lokaal `.task`-bestand vereist in `data/models/`). Eerste bounded ML-tool in Layer 5. |

### IDENTITY

| Module | Status | Opmerkingen |
| --- | --- | --- |
| loader.py | ✅ Klaar | Laadt + valideert identity.json tegen schema.json |
| identity.json | ✅ Klaar | Volledig persoonlijkheidsprofiel |
| schema.json | ✅ Klaar | JSON Schema validatie |
| personality_engine.py | ✅ Klaar | Traits + state + behavior modifier |
| behavior_modifiers.py | ✅ Klaar | Energie, impulsiviteit, dramatic flair |
| traits.json | ✅ Klaar | Numerieke persoonlijkheidswaarden (0.0–1.0) |
| identity_state.json | ✅ Klaar | Zie bug #4/#11 (opgelost 11 juli 2026) — overstimulation.level start nu op 0.1 met tijd- en interactie-gebaseerde decay. |
| emotion_engine.py | ✅ Klaar | Trigger-gebaseerde emotie-updates |
| emotion_state.json | ✅ Klaar | Huidige emotionele staat |
| emotion_rules.json | ✅ Klaar | Regels voor mood-shifts, sync, dramatic flair |
| tone_engine.py | ✅ Klaar | Mood → tone → style profile |
| style_profiles.json | ✅ Klaar | 8 stijlprofielen (emoji, gesture, pitch, volume...) |
| gesture_profiles.json | ✅ Klaar | 7 gebarenprofielen voor toekomstige avatar |
| self_query.py | ✅ Klaar | Zelfkennis-laag (12 juli 2026) — beantwoordt vragen over Nova zelf op basis van identity.json + live emotion_state |

---

## 🐛 Bekende bugs (prioriteit)

| # | Bug | Bestand | Urgentie | Status |
| --- | --- | --- | --- | --- |
| 1 | OpenWeatherMap API-key hardcoded én gelekt in chat. | weather.py | 🔴 DIRECT | ✅ Opgelost (2 juli 2026 — key naar .env, python-dotenv) |
| 1b | Stad-extractie pakte leestekens mee (bv. "gent?" i.p.v. "gent") | weather.py | 🟢 Laag | ✅ Opgelost (2 juli 2026 — strip(".,!?;:") toegevoegd) |
| 1c | Weer-intent werd niet herkend bij korte zinnen ("weer in Gent?") | intent_router.py | 🟡 Medium | ✅ Opgelost (2 juli 2026 — losse woord-detectie i.p.v. vaste triggerzinnen) |
| 1d | Weekdagnaam kwam in het Engels terug ("Monday" i.p.v. "maandag") | weather.py | 🟢 Laag | ✅ Opgelost (3 juli 2026 — eigen NL-weekdaglijst i.p.v. strftime %A) |
| 2 | Windows-pad hardcoded in save_path | memory.py | 🟡 Medium | ✅ Opgelost (2 juli 2026 — portable pad via Path(**file**), werkt op elke PC/gebruiker) |
| 3 | Dode code (uitgecommentarieerde handlers) | chat.py | 🟢 Laag | ✅ Opgelost (11 juli 2026 — meegenomen bij bug #5: dode `on_weather_response()` + subscribe verwijderd uit `chat.py`, dode `time_response`/`weather_response`/`date_response`/`math_response`-afdruktakken verwijderd uit `main.py`) |
| 4 | overstimulation.level = 1.0 als standaard | emotion_state.json | 🟢 Laag | 🔲 Open — zie uitgebreide beschrijving bij bug#11 |
| 5 | Personality/tone pipeline bypassed door weer/tijd/math | response_pipeline.py | 🟡 Medium | ✅ Opgelost (11 juli 2026 — `weather.py`, `time.py` en `math.py` publiceren nu `layer4_response` i.p.v. rechtstreeks `chat_response`/`math_response`; lopen zo alle drie door dezelfde tone-keten als definities. Bijvangst: `math.py` publiceerde voorheen `math_response`/`msg`, een event dat nergens meer werd afgeluisterd — rekenvragen waren dus stil; nu ook zichtbaar. Dode restanten opgeruimd: `chat.py`'s `on_weather_response()` + subscribe (zie ook bug #3), en de dode `time_response`/`weather_response`/`date_response`/`math_response`-afdruktakken in `main.py`.) |
| 6 | Punt aan einde van woord wordt meegenomen bij wiki-aanroep | chat.py | 🟢 Laag | 🔲 Open |
| 7 | Oude concepts.json entries hebben geen auto_extract relaties | concepts.json | 🟢 Laag | 🔲 Open |
| 8 | Automatische voorbeeldzin-extractie uit Wikipedia werkt niet (examples blijft leeg) | wikipedia_teacher.py | 🟢 Laag | 🔲 Open — omzeild met handmatig`example`-commando |
| 9 | Woordsoort-detectie (`detect_pos`) kan werkwoord/zelfstandig-naamwoord-dubbelzinnigheid niet oplossen zonder zinscontext (bv. "gebruik" als werkwoord vs. zelfstandig naamwoord) | semantic.py | 🟢 Laag | ✅ Omzeild (8 juli 2026 — expliciete stopwoordenlijst in response_pipeline.py, geen structurele fix) |
| 10 | Layer 1 (`word_associations_learner.py`) houdt geen rekening met senses: bij een meerduidig woord (bv. "python" = zowel de slang als de programmeertaal) worden alle co-occurrences door elkaar geteld, ongeacht welke betekenis bedoeld was in de zin. Ontdekt tijdens Layer 4-testen (8 juli 2026): `response_engine.py` toonde de definitie van "python" als slang, aangevuld met de associatie "snel" — die associatie komt vermoedelijk uit gesprekken over de programmeertaal, niet het dier. Layer 1 werkt puur op tekst-co-occurrence en heeft geen besef van `semantic.py`'s sense-systeem (`get_senses()`). Geen bug in `response_engine.py` zelf — die geeft gewoon correct door wat Layer 1 teruggeeft. Live opnieuw bevestigd (8 juli 2026) met "hond" (2 senses) en "hart" (5 senses) in Kevin's echte `concepts.json`. | word_associations_learner.py | 🟢 Laag | 🔲 Open — wacht op disambiguatie-laag (`user_preferences.py`), zie Layer 4-sectie |
| 11 | Nova's `emotion_state.json` stond structureel op een hoge `overstimulation.level` — elk antwoord, ongeacht onderwerp, kreeg het "overprikkeld_chaotisch_snel"-sjabloon (😵⚡💥) van `tone_engine.py`. Twee samenhangende oorzaken gevonden: (1) startwaarde stond op 1.0 (max), ver boven de threshold van 0.75 — Nova begon dus al overprikkeld bij het opstarten; (2) `emotion_engine.py` had geen enkel pad naar beneden — `apply_trigger()` verhoogde `overstimulation.level` bij triggers met `overflow_behavior` (bv. `excitement`, `focus`) met +0.15, maar niets liet het ooit weer zakken. | emotion_engine.py / Layer 6 | 🟡 Medium | ✅ Opgelost (11 juli 2026 — startwaarde naar 0.1 in `emotion_state.json`; `_apply_overstimulation_decay()` toegevoegd aan `emotion_engine.py` met TWEE decay-vormen die samenwerken: (a) tijd-gebaseerd — `last_trigger_timestamp` bijgehouden, elke minuut stilte laat het niveau zakken met `decay_per_minute` (standaard 0.05, instelbaar in `emotion_state.json` zonder code te wijzigen); (b) interactie-gebaseerd — triggers ZONDER `overflow_behavior` (bv. `confusion`) geven nu ook -0.05. Live getest: Nova start rustig bij `enthousiast_snel`, en bij snel herhaalde `excitement`-triggers (sneller dan de decay kan bijbenen) schakelt ze terecht over naar `overprikkeld_chaotisch_snel` — het systeem is nu omkeerbaar i.p.v. permanent vast te zitten.) |

---

## 🧩 Reasoning Engine — Fase 7.1b/7.5 uitbreidingen (12 juli 2026)

Twee nieuwe, symbolische uitbreidingen op de bestaande Reasoning Engine (`semantic.py`, `ReasoningEngine`-klasse), gebouwd en getest in dezelfde sessie waarin een reeks bugs in `RelationParser.parse_relation()` en `intent_router.py`'s `detect_math()` werden gevonden en gefixt (zie apart, hieronder).

### part_of_chained / explain_part_of (sectie 7.1b)

Analoog aan het al bestaande `is_a_chained`/`explain_is_a`, maar volgt uitsluitend `part_of`-relaties i.p.v. `is_a`. Drie nieuwe onderdelen:

- `part_of_chained()` + `explain_part_of()` in `ReasoningEngine` (semantic.py)
- `part_of()` + `explain_part_of()` doorverwijzingen in `SemanticConceptsModule`-facade (semantic.py) — deze schakel ontbrak eerst en veroorzaakte een korte, snel gevonden bug (`hasattr(semantic, "explain_part_of")` gaf `False` terug)
- `detect_part_of_check()` in `intent_router.py` — herkent "is X onderdeel van Y" en "zit X in Y"
- `on_part_of_check()` handler in `chat.py`

**Getest:** live in Nova, met de keten `snaar → part_of → gitaar → part_of → orkest`. Vraag "is een snaar onderdeel van een orkest?" gaf correct: *"Ja, een snaar is onderdeel van orkest, want: snaar → gitaar → orkest."*

### get_all_subtypes (sectie 7.5)

Omgekeerde `is_a`-lookup: geeft alle concepten terug die (direct of via een keten) naar een gegeven categorie verwijzen. **Let op:** dit is niet hetzelfde als de `is_a`-relatie zelf omdraaien (dat zou inhoudelijk fout zijn — "dier is_a grizzlybeer" klopt niet) — het is een aparte query die de bestaande relatie-graaf omgekeerd doorloopt door alle concepten te checken met de al bestaande `is_a_chained()`.

- `get_all_subtypes()` in `ReasoningEngine` (semantic.py)
- Doorverwijzing in `SemanticConceptsModule`-facade
- `detect_subtypes_query()` in `intent_router.py` — herkent "welke soorten X ken je", "noem soorten van X", "wat zijn allemaal X"
- `on_subtypes_query()` handler in `chat.py`

**Getest:** live in Nova, "welke soorten dier ken je?" gaf correct 16 concepten terug (hond, huiskat, octopus, honingbeer, grizzlybeer, zoogdier, kat, wolf, weekdier, beer, bruine beer, paard, kip, vogel, tijger, roofdier).

### Losse uitbreidingsideeën (niet ingepland)

Tijdens dit gesprek kwamen 6 losse vervolgideeën naar boven (get_all_parts, related_to_chained, part_of-contradictiedetectie, multi-hop vragen, "waarom niet"-uitleg, concept-vergelijkingen). Deze zijn **niet volledig identiek** aan de bestaande Fase 8-10 in `semantic_extension_roadmap.md`, en daarom apart vastgelegd in een nieuw document: **reasoning_engine_ideeen_roadmap.md** — puur een ideeënbak, geen bouwvolgorde.

---

## 🐞 Bugfixes buiten de reguliere bug-tabel (11-12 juli 2026)

Tijdens het testen van bovenstaande Reasoning Engine-uitbreidingen kwamen twee onafhankelijke, niet eerder gedocumenteerde bugs naar boven:

**1. `RelationParser.parse_relation()` (semantic.py) — geen zin-/bijzin-afkapping.**
Bij het leren van een `is_a`-relatie uit een langere tekst (bv. een geplakte alinea van meerdere zinnen) werd het object niet afgekapt bij de eerste zinsgrens, waardoor de VOLLEDIGE rest van de tekst als relatie-target werd opgeslagen. Voorbeeld: "Een vulkaan is een berg waaruit... [nog 4 zinnen]" werd letterlijk als één object opgeslagen. Twee deel-fixes:
    - Afkapping bij zinseinde-tekens (`. `, `! `, `? `, newline)
    - Afkapping bij bijzin-markers (`waaruit`, `waarbij`, `waarvan`, `waarmee`, `waarop`, `waar`, `die`, `dat`, `wat`, `wie`)

Resultaat: van een hele alinea wordt nu enkel het eerste, korte kernbegrip overgehouden (bv. "vulkaan is_a berg" i.p.v. de volledige alinea). Bekende, geaccepteerde beperking: bij meerdere leerbare zinnen in één geplakte tekst wordt enkel de eerste zin verwerkt, de rest wordt genegeerd (geen crash, gewoon geen actie) — dit was nooit anders en is geen regressie.

**Opruiming nodig geweest:** Nova's `ensure_concept`-mechanisme (hetzelfde dat `levend wezen` ooit als auto-placeholder aanmaakte) had de kapotte, te lange test-targets automatisch als eigen concepten vastgelegd in `concepts.json` — inclusief één concept met een 470 tekens lange naam. Deze zijn achteraf handmatig opgeruimd.

**2. `detect_math()` (intent_router.py) — geen woordgrenzen bij math_keywords.**
De check `if any(k in t for k in math_keywords)` gebruikte een kale substring-check zonder woordgrenzen. Hierdoor werd het woord "toestand" (bevat "tan") foutief herkend als de wiskundefunctie `tan()`, waardoor bv. "IJs is een materietoestand" naar de math-module werd gerouteerd in plaats van als relatie-leerzin herkend te worden. Fix: `re.search(rf"\b{k}\b", t)` i.p.v. de kale `in`-check.

**3. `detect_relation_check()`, `detect_part_of_check()`, `detect_subtypes_query()` (intent_router.py) — ontbrekende `_emit_topic()`-aanroepen.**
Ontdekt bij het bijwerken van `algemeen.py`'s help-tekst (12 juli 2026): drie routes in `route()` misten de verplichte `self._emit_topic(...)`-aanroep uit het vaste recept (zie "Architectuurprincipes om te onthouden" verderop). `detect_part_of_check` en `detect_subtypes_query` waren nieuw van vandaag en misten 'm simpelweg nog. **Belangrijker: `detect_relation_check` (de originele "is een hond een dier"-vraag) miste deze aanroep al langer, onopgemerkt** — dit was dus geen regressie van vandaag, maar een al langer bestaand, stil gat. Fix: alle drie routes emitten nu een topic (`relatie`, `part_of`, `subtypes`). `algemeen.py`'s patronen-sectie is aangevuld met deze drie nieuwe `topic_detected:*`-namen, en de REDENEREN-sectie met de nieuwe part_of/subtypes-commando's.

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
| --- | --- | --- | --- |
| Layer 0 | memory.py (v2.0) | ✅ KLAAR (alle 4 fases) | memory_layer0_roadmap.md + memory_24-7_daemon_addendum.md |
| Layer 1 | word_associations_learner.py | ✅ KLAAR (alle 5 fases) | memory_layer1_roadmap.md |
| Layer 2 | pattern_matcher.py | ✅ KLAAR (alle 5 fases) | memory_layer2_roadmap.md |
| Layer 3 | semantic.py | ✅ KLAAR | semantic_roadmap.md |
| Layer 4 | response_engine.py | ✅ KLAAR (Fase 1-5, 7; Fase 6 uitgesteld) | memory_layer4_roadmap.md |
| Layer 5 | context_manager.py + activity/focus/presence_detector.py | ✅ Fase 1-4 KLAAR (tijd, activiteit, focus, aanwezigheid) — enkel Fase 5 (verfijnde combinatie-logica) nog te bouwen | memory_layer5_roadmap.md |
| Layer 6 | personality_engine.py | ✅ KLAAR | identity_ROADMAP.md |
| Layer 7 | emergence_engine.py | ❌ Nog te bouwen | memory_layer7_roadmap.md |

**Bouwvolgorde:** Layer 0 eerst (foundation), dan 1 → 2 → 4 → 5 → 7.
**Extra, buiten de 7 lagen:** een losse "User Preferences"-module (Kevin's voorkeuren/afkeuren) staat gepland — zie memory_user_preferences_roadmap.md

### Layer 1 — Word Associations Learner (afgerond 4 juli 2026)

Alle 5 fases gebouwd, getest (los + binnen de echte Nova) en werkend:

| Fase | Omschrijving | Status |
| --- | --- | --- |
| 1 | Tokenization & filtering (NL-stopwoorden, eenvoudige lemmatizer) | ✅ |
| 2 | Co-occurrence tellen (sliding window, window_size=5) | ✅ |
| 3 | PMI-berekening (sigmoid-genormaliseerd naar 0-1) | ✅ |
| 4 | Opvragen/queries (get_associations, find_related, word_distance, get_word_sentiment, get_stats) | ✅ |
| 5 | Opslaan naar schijf (data/word_associations.json) + EventBus-publicatie | ✅ |

**Belangrijke afwijkingen t.o.v. de originele roadmap (memory_layer1_roadmap.md):**

- De roadmap veronderstelde dat `memory:interaction_added` één gecombineerd `{"user_input": ..., "nova_response": ...}`-object bevat. In de echte Nova luistert `memory.py` met `event_bus.subscribe("*", ...)` naar ALLE events en herverpakt elk los event (bv. `chat_message`, `chat_response`) apart. `learn_from()` filtert daarom op `event_type in ("chat_message", "chat_response")` en gebruikt de `"text"`-sleutel, niet `user_input`/`nova_response`.
- `init_module(event_bus, config=None)` is aangepast naar `init_module(event_bus, semantic_module=None)`, omdat `module_loader.py` altijd `init_module(event_bus, sem)` aanroept voor dynamische modules (dezelfde conventie als chat.py en response_pipeline.py). Er is geen apart config-systeem — `min_word_length`/`window_size` staan vast in de code, `save_path` is een losse parameter.
- `learn_from(self, interaction, event_type=None)` accepteert nu ook een tweede positioneel argument, omdat `event_bus.py` handlers standaard aanroept als `handler(data, event_type)`.
- De lemmatizer is een Nederlandse *benadering* (verkleinwoorden, regelmatig meervoud, bijvoeglijke vorm op -e), geen volledige taalkundige lemmatizer — onregelmatige vervoegingen (bv. "liep" → "lopen") worden bewust niet afgevangen.

**Bekend, verwacht gedrag (geen bug):**

- Nova's vaste fallback-zin ("Ik weet nog niet goed... Je zei: '...'") wordt bij elk onbegrepen bericht meegeleerd, waardoor woorden als "weet", "goed", "antwoord", "leer", "graag", "zei" hoge, onderling sterke associaties opbouwen. Dit is ruis die vanzelf minder dominant wordt zodra Nova's antwoorden gevarieerder worden (latere layers).

**Huidige status: actief gebruikt sinds Layer 4 (8 juli 2026).**

De module bouwt het associatienetwerk op in `data/word_associations.json` en publiceert `word_association:updated`-events. Sinds Layer 4 (`response_engine.py`) wordt `find_related()` daadwerkelijk aangeroepen bij elke definitie-vraag — zie de Layer 4-sectie hieronder voor details.

### Layer 2 — Pattern Matcher (afgerond 5 juli 2026)

Alle 5 fases gebouwd, getest (los + binnen de echte Nova) en werkend:

|Fase|Omschrijving|Status|
|---|---|---|
|1|Event grouping (per uur, per dag, per event_type)|✅|
|2|Pattern detection (most_common_hour, confidence, day_frequency)|✅|
|3|Anomaly detection (ongewone timing + gemiste events via achtergrondtimer)|✅|
|4|Query & predictie (is_pattern_active, predict_next_occurrence, get_anomalies)|✅|
|5|Integratie (pattern:detected event, opslaan + herladen bij opstarten)|✅|

**Belangrijke afwijkingen t.o.v. de originele roadmap (memory_layer2_roadmap.md):**

- De roadmap-voorbeelden (bv. `"reason": "sick"` bij anomalieën) suggereerden dat Nova zelf zou "weten" waarom iets afwijkt. Dat is bewust NIET gebouwd — Nova kan enkel zeggen DAT iets afwijkt (ongewone timing / gemist event), nooit waarom, want dat zou een verzonnen verklaring zijn.
- `detect_from()` filtert bewust enkel op `event_type in ("chat_message", "chat_response")` via een `RELEVANTE_EVENT_TYPES`-set (klasse-attribuut) — zonder deze filter werden ALLE interne pipeline-events (`pipeline_response`, `expression_inject`, `module_loaded`, ...) ook meegeteld, wat 4-5 aanroepen per gebruikersbericht gaf i.p.v. 1-2, en initieel zelfs een `RecursionError` veroorzaakte (zie hieronder).
- **Belangrijke bug, gefixt:** de eerste versie luisterde naar het letterlijke event-type `"memory:interaction_added"` als functie-argument, maar dat argument is ALTIJD die ene string (want dat is wat `memory.py` zelf publiceert) — het ECHTE, originele event_type (bv. `"chat_message"`) zit genest in `interaction["event_type"]`. Zonder deze fix, gecombineerd met het ontbreken van de `RELEVANTE_EVENT_TYPES`-filter, ontstond een oneindige recursielus tussen `memory.py` (die naar `"*"` luistert) en de events die `pattern_matcher.py` zelf publiceerde, met exponentieel groeiende geneste payloads tot een `RecursionError`.
- `"pattern:detected"` moest expliciet toegevoegd worden aan `memory.py`'s `ignore_types`-set (naast het al bestaande `"pattern_update"`) om dezelfde recursie te voorkomen bij het Fase 5-event.
- Anomaly-detectie (Fase 3) gebruikt vaste, door Kevin/Claude gekozen drempels (`MIN_OBSERVATIES_VOOR_ANOMALIE`, `MIN_CONFIDENCE_VOOR_ANOMALIE`) — geen geleerde/dynamische drempels. Tijdens ontwikkeling tijdelijk verlaagd (3 i.p.v. 10) om te kunnen testen; **nog terug te zetten naar een realistischere waarde (10+) voor productiegebruik.**
- "Missing events"-detectie (Fase 3, Deel B) draait via een `threading.Timer`-achtergrondlus (zelfde patroon als `memory.py`'s `start_maintenance()`), en is een BENADERING: Layer 2 houdt enkel tellers per uur/dag bij, geen exacte tijdlijn per datum, dus "was dit exacte uur al geteld" wordt geschat, niet exact nagetrokken.
- Opslag gebeurt momenteel elke 2 observaties (`total % 2 == 0`) i.p.v. tijdgebaseerd zoals `memory.py`'s write-buffer — tijdelijk verlaagd om te kunnen testen, **nog te herzien voor een definitieve, efficiëntere strategie.**
- `load_from_disk()` herstelt bij opstarten expliciet de `defaultdict(int)`-structuur van `hours`/`days` (die `json.load()` anders als gewone dict teruggeeft) en zet JSON-string-sleutels van uren terug om naar integers.

**Bekende, nog openstaande discussie (geen bug, architecturale keuze):**

- Layer 2 telt enkel *wanneer* een event_type voorkomt (bv. `chat_message`), niet *waarover* het gaat — ze "leest" geen tekstinhoud. Een concreet voorbeeld: "ik ga koffie drinken" wordt enkel geteld als "er was een chat_message om 12u", niet als "Kevin dronk koffie om 12u". Om specifieke onderwerpen/activiteiten (koffie, slapen, ...) apart te laten bijhouden, is een tussenstap nodig die ruwe tekst omzet naar herkenbare, specifieke events — dit hoort NIET bij Layer 2 zelf (die blijft bewust simpel: enkel tellen), maar bij een latere/aparte uitbreiding, mogelijk een koppeling tussen `intent_router.py` (die al intents herkent) en Layer 2, of een aparte topic-classificatie. Nog te ontwerpen, bewust NIET meegenomen in Layer 2's 5 fases.

**Tijdelijk testcommando in `main.py`:** `patronen <event_type>` (of `patronen` zonder argument voor algemene stats) toont ruwe patroondata, `is_pattern_active()`, `predict_next_occurrence()` en recente anomalieën. Mag verwijderd/vervangen worden zodra er een definitieve manier is om dit op te vragen (bv. via `help`).

### Layer 4 — Response Generation Engine (afgerond 8 juli 2026)

Nieuw bestand `core/response_engine.py`. Combineert Layer 3 (semantic), Layer 1 (word_associations) en Layer 2 (pattern_matcher) tot sjabloon-antwoorden voor definitievragen. Roept de andere lagen rechtstreeks aan als Python-methodes (niet via EventBus) via een `layers`-dictionary, meegegeven bij `init_module(event_bus, layers)` — een bewust andere signatuur dan de andere modules (`init_module(event_bus, sem)`), dus `module_loader.py` roept dit apart aan (stap 3B, na de dynamische modules-lus, vóór de intent_router).

| Fase | Omschrijving | Status |
| --- | --- | --- |
| 1 | Sjabloon "definitie": `semantic.get_meaning()`, met `get_relations(entity, "is_a")` als fallback, eerlijk "weet ik niet"-antwoord anders | ✅ |
| 2 | Layer 1 (`find_related()`) toegevoegd via `_sterkste_associatie()` — toont "personal touch" alleen bij PMI-score ≥ `MIN_ASSOCIATIE_SCORE` (0.5) | ✅ |
| 3 | Layer 2 (`is_pattern_active()`/`get_pattern()`) gebouwd via `get_timing_hint(topic_naam)` | ✅ |
| 4 | Integratie in `module_loader.py` + `intent_router.py` — Nova gebruikt dit nu echt tijdens een gesprek | ✅ |
| 5 | Sjablonen natuurlijker: elk sjabloon is een LIJST van 3-5 warme varianten, willekeurig gekozen via `_kies_variant()` (`random.choice()`) | ✅ |
| 6 | Bug#10 aanpakken (associatie enkel tonen bij juiste sense) | 🔲 Uitgesteld tot disambiguatie-laag (zie User Preferences-sectie) |
| 7 | Tone/personality via bestaande tone-keten (`response_pipeline.py`/`chat_response_engine.py`/`expression_injector.py`) | ✅ |
| — | Layer 2 écht gekoppeld aan `generate()` via `_voeg_timing_hint_toe()` (was aanvankelijk vergeten — Layer 2 bleef los na Fase 3) | ✅ |

**Architectuurkeuzes:**

- **Optie A gekozen** voor de integratie: Layer 4 vervangt `chat.py`'s `on_definition()` als hoofdroute voor definitievragen. `intent_router.py` probeert eerst `response_engine.generate()`; alleen bij confidence ≤ 0.2 valt het terug op de oude route via `chat.py`, die zijn automatische Wikipedia-fallback behoudt (bewust niet overgebouwd naar `response_engine.py` — voorkomt duplicatie, elke module blijft verantwoordelijk voor zijn eigen taak).
- **Tone-integratie (Fase 7):** `intent_router.py` en `chat.py`'s vangnet publiceren `layer4_response` i.p.v. rechtstreeks `chat_response`. `response_pipeline.py` kreeg een nieuwe listener `on_layer4_response()` (zelfde patroon als `on_greeting()`/`on_fallback()`) die de AL KLARE Layer 4-tekst door de bestaande tone-keten stuurt — verzint geen nieuwe tekst, voegt enkel Nova's stemming (emoji's, uitroeptekens) toe.
- **Layer 2-koppeling gebruikt het GENERIEKE topic `"definitie"`** (hetzelfde topic dat élke definitievraag al triggert via `_emit_topic("definitie")`), niet per-woord-timing — Layer 2 houdt geen per-woord-patronen bij, dus een eerlijke "je stelt hier over het algemeen rond dit tijdstip definitievragen"-hint, geen "je vraagt vooral 's avonds naar python" (zou doen alsof Layer 2 iets weet dat het niet weet). Timing-hint wordt toegevoegd na elk succesvol antwoord, bewust NIET bij "onbekend".
- **Caching en feedback-loop (`response_engine.feedback()`) bewust NIET gebouwd**, ondanks dat de originele roadmap ze voorzag: caching zou conflicteren met Fase 5's willekeurige variant-keuze en de tijdsgevoelige Layer 2-koppeling (een gecached antwoord kan verouderd/inconsistent worden); feedback-loop vereist actieve bevestiging van Kevin en hoort inhoudelijk thuis bij de toekomstige `user_preferences.py`-module (zie hieronder), niet als losse toevoeging aan Layer 4.

**Bekend, genoteerd voor later:**

- **Bug #10#10:** meerduidige woorden (bv. "hond" met 2 senses, "python" met 2 senses, "hart" met 5 senses in `concepts.json`) — `semantic.get_best_definition()` kiest de sense met hoogste confidence, niet noodzakelijk de bedoelde. Live bevestigd tijdens testen (8 juli 2026): "hond" gaf soms de korte definitie ("een dier") i.p.v. de volledige biologische definitie. Wachten op disambiguatie-laag.
- **Per-woord-timing:** mogelijke toekomstige uitbreiding — zou vereisen dat `intent_router.py` een woord-specifieke topic-naam doorgeeft aan `_emit_topic()` i.p.v. het vaste `"definitie"`. `response_engine.py` zelf zou dan ONGEWIJZIGD blijven. Raakt ook Kevin's activiteit-suggestie-idee (bv. koffie voorstellen tijdens het coderen) — dat hoort echter bij `activity_awareness_roadmap.md`, niet bij Layer 4.
- **Emotion/overstimulation-observatie:** tijdens Layer 4-testen viel op dat Nova's `emotion_state.json` structureel op een hoge `overstimulation.level` staat, waardoor elk antwoord het "overprikkeld_chaotisch_snel"-sjabloon (😵⚡💥) kreeg, ongeacht onderwerp. Geen Layer 4-bug — hoorde bij Layer 6, niet bij Layer 4. **Opgelost (11 juli 2026), zie bug #4/#11.**
- **Toekomstige uitbreiding, DEELS OPGELOST (12 juli 2026, zie werkpunt #2 hierboven): Layer 4 laten gelden voor de andere semantic-gerelateerde intents.** Twee aparte dingen om uit elkaar te houden: (1) **de tone-pipeline** (emoji's/stemming via `expression_injector.py`) — dit is nu opgelost, alle semantic-intents publiceren `layer4_response` en klinken dus warm. (2) **De échte Layer 4-combinatie** (`response_engine.generate()`, die semantic + word_associations (Layer 1, "personal touch") + pattern_matcher (Layer 2, timing-hint) samenbrengt) — dit blijft ENKEL gekoppeld aan `detect_definition()`'s hoofdroute. De andere semantic-intents (`intent_synonym`, `intent_antonym`, `intent_used_for`, `intent_causes`, `intent_properties`, `intent_related_to`, `intent_relation_check`, `intent_part_of_check`, `intent_subtypes_query`) gaan nog altijd rechtstreeks naar hun eigen handler in `chat.py`/`semantic.py`, zonder Layer 1/Layer 2-verrijking. Bewust NIET uitgebreid naar weer/tijd/math/schaken/help — die modules hebben geen semantic/word_associations/pattern_matcher-achtige databronnen om te combineren. Of dit dieptepunt (2) de moeite waard is, hangt af van of "synoniemen van hond, met personal touch/timing-hint erbij" een zinvolle uitbreiding is — nog niet besloten, geen prioriteit.

**Getest:** los (`test_response_engine.py` tegen echte `concepts.json`), end-to-end binnen de echte Nova (6 representatieve concepten: hond, appel, python, democratie, zwart gat, blablabla), en de volledige tone-keten inclusief live emoji/stemmings-integratie.

### Layer 5 — Context Manager (Fase 1-4 afgerond, 13-16 juli 2026)

Eerste, symbolische basisversie gebouwd en getest — enkel tijd + Layer 2 (pattern_matcher.py) gecombineerd tot een simpele interruption-beslissing. Geen mouse/keyboard-tracking, geen webcam/presence-detectie, geen identiteitsherkenning — die blijven latere, aparte fases (en sommige vereisen bounded ML, zoals gezichtsherkenning, wat expliciet NIET in dit bestand zit).

**Nieuw bestand:** `modules/context/context_manager.py`. Volgt NIET de standaard dynamische module_loader-conventie (`init_module(event_bus, sem)`) — krijgt net als `response_engine.py` een `layers`-dictionary mee (met `pattern_matcher` erin), en wordt daarom HANDMATIG geladen in `module_loader.py`, na de dynamische modules-stap (zodat `pattern_matcher` al bestaat).

**Kernlogica (`_bepaal_interrupt()`):**
    - 3+ anomalieën vandaag (via `pattern_matcher.get_anomalies(days=1)`) → `should_interrupt = False`
    - Gebruikelijk moment volgens Layer 2 (via `pattern_matcher.is_pattern_active("chat_message")`) → `should_interrupt = True`
    - Geen sterke aanwijzing in beide richtingen → standaard `True` (nog geen reden om terughoudend te zijn)

Elke beslissing krijgt ook een `reden`-veld (bv. `"te veel anomalieën vandaag (>=3)"`), puur voor debug/nazicht — wordt niet voorgelezen aan Kevin.

**Opslag:** `data/context_log.jsonl` — een append-only geschiedenis van elke berekende context (JSON Lines, 1 regel per `get_current()`-aanroep), afgekapt op 2000 regels. BELANGRIJK verschil met `patterns_layer2.json`: dit is GEEN state die bij opstarten opnieuw ingeladen wordt — Layer 5 herberekent zijn context altijd live; enkel de geschiedenis van beslissingen wordt bewaard, voor Kevin's nazicht.

**Koppeling met `session_watcher.py` (eerste echte consument van Layer 5):** `check_pauze()` roept nu `context_manager.can_interrupt()` op vóór hij zijn pauze-melding publiceert. Als Layer 5 het afraadt, wordt de melding stilzwijgend uitgesteld (niet geannuleerd — `laatste_melding_time` wordt dan NIET bijgewerkt, dus de check probeert het de volgende minuut opnieuw) en verschijnt er een console-print `[SESSION_WATCHER] Pauze-melding uitgesteld door Layer 5 (...)`, enkel zichtbaar voor Kevin, niet voorgelezen door Nova. `context_manager` ontbreken mag nooit blokkeren: als de referentie `None` is (bv. laadvolgorde-probleem), wordt `mag_onderbreken = True` verondersteld — Layer 5 ontbreken mag de bestaande pauze-functionaliteit nooit stiller maken dan voorheen.

**Laadvolgorde-afhankelijkheid:** `session_watcher` wordt geladen via de dynamische modules-scan (stap 3, vóór `context_manager` bestaat). `module_loader.py` "prikt" daarom de `context_manager`-referentie pas ná stap 3C handmatig in bij de al bestaande `session_watcher`-instance (`watcher.context_manager = ctx_mgr`), in plaats van dit via een constructor-argument te doen.

**Debug-commando's in `main.py`:** `context` (huidige beslissing + reden) en `context geschiedenis [n]` (laatste n regels uit `context_log.jsonl`, standaard 10).

**Getest (13 juli 2026):** beide paden bevestigd — normale/gebruikelijke situatie geeft `should_interrupt: True`, en een geforceerd scenario met 3 nepanomalieën (los testscript `test_forceer_anomalieen.py`, niet onderdeel van Nova zelf) geeft correct `should_interrupt: False` met de juiste reden.

#### Layer 5 — Fase 2: Activity Tracking (afgerond 13 juli 2026)

Activiteit-detectie toegevoegd — WELK PROGRAMMA nu actief is (voorgrondvenster), en hoe lang al. Nog steeds 100% symbolisch: leest enkel af welk venster focus heeft via `pygetwindow`, classificeert niets met ML.

**Nieuw bestand:** `modules/context/activity_detector.py`. Volgt WEL de standaard dynamische module_loader-conventie (`init_module(event_bus, sem)`) — in tegenstelling tot `context_manager.py`, want dit bestand heeft geen `layers`-dictionary nodig (het publiceert enkel events, leest geen andere lagen uit). Wordt dus automatisch opgepikt door de bestaande `pkgutil`-scan, geen aparte handmatige laadstap nodig zoals bij `context_manager.py` zelf.

**Vereist extern pakket:** `pygetwindow` (`pip install pygetwindow`). Bewust NIET `psutil` gebruikt voor de detectie zelf — `psutil` kent enkel DRAAIENDE processen, niet welk venster op de VOORGROND staat (focus heeft), en dat onderscheid is precies waar het om gaat ("Chrome staat open ergens" ≠ "Chrome is het venster waarin Kevin nu werkt"). Zonder `pygetwindow` geïnstalleerd print het bestand een duidelijke waarschuwing bij opstarten en valt netjes terug op `"unknown"` — geen crash.

**`ACTIVITEIT_MAPPING`:** een dictionary (venstertitel/procesnaam-fragment → activiteit-label) die Kevin zelf verder aanvult. Volgorde is belangrijk — eerste match wint.

**Belangrijke architecturale nuance, ontdekt tijdens live testen (13 juli 2026): `talking_to_nova` vs. `coding`.** Nova's eigen consolevenster toont `"python.exe"` als titel wanneer los opgestart (bv. via een gewoon PowerShell-venster), inclusief bij een nieuw venster geopend via `/reboot` (`reboot_manager.py`'s `subprocess.Popen` + `CREATE_NEW_CONSOLE`) — dat zou zonder onderscheid ALTIJD als "coding" geteld worden, ook al is Kevin gewoon met Nova aan het praten, niet aan het coderen. Opgelost door een apart label `"talking_to_nova"` te geven aan `"python.exe"`/`"nova_ai"`-matches, bewust NIET opgenomen in `context_manager.py`'s `STORINGSGEVOELIGE_ACTIVITEITEN` — praten met Nova blijft dus altijd onderbreekbaar, ongeacht duur. Enkel echte code-editors (`"code.exe"`, `"visual studio code"`, `"pycharm"`) tellen als `"coding"`. **Nuance hierbij:** als Nova draait in VS Code's geïntegreerde terminal (i.p.v. een los PowerShell-venster), toont Windows de VS Code-venstertitel (bv. `"bestand.json - Nova_AI - Visual Studio Code"`), die matcht op `"visual studio code"` → wordt dus terecht als `"coding"` geteld, want Kevin zit dan sowieso in VS Code te werken.

**Uitbreiding `context_manager.py`:** `get_current()` haalt nu ook `activity` + `activity_duration_minutes` op bij `activity_detector.detect_activity()`. Nieuwe instelling `CODING_ONDERBREEK_DREMPEL_MINUTEN = 15` (teruggezet naar deze productiewaarde na testen, tijdelijk op 0.1/1 gezet tijdens ontwikkeling) en `STORINGSGEVOELIGE_ACTIVITEITEN = {"coding"}`. `_bepaal_interrupt()` uitgebreid: 15+ minuten ononderbroken `"coding"` → `should_interrupt = False`, met voorrang op de "gebruikelijk moment"-regel (een actieve coding-sessie is een sterker signaal dan enkel "dit is meestal een chat-moment").

**Laadvolgorde-aanpassing in `module_loader.py`:** `context_layers`-dictionary in stap 3C bevat nu ook `"activity_detector": self.loaded_modules.get("activity_detector")`, naast `pattern_matcher`.

**Nieuw debug-commando in `main.py`:** `activiteit debug` — toont de ruwe venstertitel/procesnaam plus het herkende label, gebruikt om de `talking_to_nova`/`coding`-nuance hierboven te ontdekken en te verifiëren.

**Getest (13 juli 2026), drie scenario's stuk voor stuk bevestigd:**
- Los PowerShell-venster met Nova erin → `talking_to_nova`, `should_interrupt` blijft altijd `True` ongeacht duur
- VS Code met Nova in geïntegreerde terminal → correct herkend als `coding`
- Duur-teller loopt logisch op (0.0 → 0.6 → 1.2 min, met tijdelijk verlaagde testdrempel) en `should_interrupt` slaat op het juiste moment om naar `False`, met de juiste `reden`-tekst

#### Layer 5 — Fase 3: Focus Detection (afgerond 15 juli 2026)

Focus-detectie toegevoegd — HOELANG GELEDEN was er systeemwijde muis-/toetsenbordactiviteit. Lost een gat op dat Fase 2 liet liggen: een venster kan lang "open" staan (bv. 20 min "coding" volgens Fase 2) terwijl Kevin er allang niet meer actief mee bezig is. Nog steeds 100% symbolisch: gebruikt Windows' eigen `GetLastInputInfo()`-API via `ctypes` om enkel WANNEER de laatste input was op te vragen — geen keylogging, geen inhoud, geen ML.

**Nieuw bestand:** `modules/context/focus_detector.py`. Volgt, net als `activity_detector.py`, de standaard dynamische module_loader-conventie (`init_module(event_bus, sem)`) — geen `layers`-dictionary nodig, automatisch opgepikt door de bestaande `pkgutil`-scan.

**Kern:** `GetLastInputInfo()` + `GetTickCount()` (beide Win32 via `ctypes`) → aantal seconden sinds laatste input, systeemwijd (niet per venster — Windows biedt geen ingebouwde manier om input per programma te meten zonder een veel ingrijpendere hook; bewust aanvaarde beperking). Windows-only: op andere platformen geeft dit altijd "geen info" terug, geen crash.

**Drempels (`_bepaal_focus_niveau()`):** vaste, symbolische grenzen — `< 120s` → `"actief"`, `120-600s` → `"mogelijk_afwezig"`, `> 600s` → `"waarschijnlijk_weg"`, geen info → `"onbekend"`.

**Uitbreiding `context_manager.py`:** `get_current()` haalt nu ook `focus_level` + `seconds_since_input` op. `_bepaal_interrupt()` uitgebreid: als een storingsgevoelige activiteit (bv. `coding`) de tijdsdrempel haalt, wordt nu EERST gecheckt of `focus_level` in `FOCUS_NIVEAUS_ZONDER_ACTIEVE_AANWEZIGHEID` (`mogelijk_afwezig`/`waarschijnlijk_weg`) zit — zo ja, dan vervalt de coding-blokkade alsnog en valt de beslissing terug op de normale gebruikelijk-moment-regel. Bij `focus_level: "onbekend"` (bv. API-fout) wordt bewust de voorzichtige kant gekozen (net als bij `coding` zonder afwezigheid): niet onderbreken.

**Belangrijke transparantie-nuance (besproken met Kevin, 15 juli 2026):** dit is GEEN keylogger en GEEN schermopname — enkel *wanneer* de laatste input was (1 timestamp), nooit *wat* er getypt/geklikt werd of *wat* er op het scherm te zien is. `activity_detector.py` leest enkel de venstertitel (bv. programmanaam), nooit de inhoud van dat venster. Alles blijft lokaal in `data/context_log.jsonl`, nergens naar buiten verstuurd.

**Laadvolgorde-aanpassing in `module_loader.py`:** `context_layers`-dictionary in stap 3C bevat nu ook `"focus_detector": self.loaded_modules.get("focus_detector")`.

**Periodieke polling toegevoegd aan `main.py`'s `achtergrond_loop()`:** naast `activity_detector.detect_activity()` nu ook `focus_detector.get_focus_info()` ÉN `context_manager.get_current()` zelf, elke minuut. Dit was nodig omdat een handmatige test via het `context`/`focus debug`-commando de meting altijd vervuilde — het TYPEN van het commando telt zelf als input, dus gaf altijd `0.0s`/`"actief"` terug, ongeacht hoelang je voordien niets deed. Enkel via de achtergrondthread (die niet typt) kan de meting eerlijk zijn.

**Nieuw debug-commando in `main.py`:** `focus debug` — toont ruwe `seconds_since_input` + `focus_level`. Kanttekening: dit commando zelf is dus niet geschikt om afwezigheid te testen (zie hierboven); enkel bruikbaar om te bevestigen dat de API werkt op het moment van typen (geeft dan altijd `actief` terug).

**Getest (15 juli 2026), via de achtergrondthread (niet handmatig, om vervuiling te vermijden):**
- Focus-teller loopt eerlijk op zonder input (bv. 62s → 122s → 182s → ... telkens +60s, exact het pollinginterval)
- Drempel-overgang bevestigd op het exacte grensmoment: bij 62s (< 120s) → `actief`; bij 122s (≥ 120s) → `mogelijk_afwezig`
- **Combinatietest met Fase 2 (het hoofddoel van Fase 3):** VS Code 16+ minuten open gehouden (ruim boven de 15 min coding-drempel) mét periodes zonder input → `focus_level: "mogelijk_afwezig"` → `should_interrupt` bleef `True`, in plaats van `False` zoals Fase 2 alleen zou geven. Bevestigt dat de coding-blokkade correct vervalt zodra er geen actieve aanwezigheid meer is, ondanks dat het venster nog openstaat.

#### Layer 5 — Fase 4: Presence Detection (afgerond 16 juli 2026)

Aanwezigheidsdetectie toegevoegd via webcam — de EERSTE Layer 5-fase die een extern ML-model gebruikt (MediaPipe Face Detection), in tegenstelling tot Fase 1-3 die allemaal pure Python/OS-API's waren. Dit is bewust en correct volgens Nova's architectuurprincipe: het model is een BOUNDED, EXTERNAL SPECIALIST TOOL — levert enkel "aantal gezichten" terug, Nova's symbolische kern beslist zelf wat ze ermee doet. Puur AANWEZIGHEID (hoeveel gezichten?), GEEN IDENTITEIT (wiens gezicht?) — dat laatste blijft een latere, aparte uitbreiding (Kevin's presence/identiteits-roadmap, nog te schrijven, incl. Windows Hello-koppeling en stemherkenning-ideeën die al besproken zijn).

**Modelkeuze (afweging met Kevin, 16 juli 2026):** MediaPipe gekozen boven RetinaFace na vergelijking — voor dit scenario (1 gezicht, dichtbij, webcam, goed licht) is MediaPipe ruim voldoende nauwkeurig, officieel Google-onderhouden (`pip install mediapipe`), en snel genoeg. RetinaFace's extra precisie is gericht op drukke scenes met kleine/verre/gedeeltelijk verborgen gezichten — irrelevant voor Kevin's gebruik, en vereist bovendien handmatige ONNX-conversie via minder onderhouden community-repo's.

**BELANGRIJKE TECHNISCHE NOOT — MediaPipe API-breuk:** MediaPipe verwijderde de oude "Solutions"-API (`mp.solutions.face_detection`) volledig vanaf versie 0.10.35 (bevestigd via `test_mediapipe_debug.py`: `hasattr(mp, "solutions")` → `False`). `presence_detector.py` gebruikt daarom de nieuwe **Tasks API** (`mp.tasks.vision.FaceDetector`), die een apart, lokaal `.task`-modelbestand vereist (niet meer intern meegeleverd). Model: BlazeFace "short range" (bedoeld voor gezichten < 2 meter, precies een laptop-webcam), gedownload van `https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite` naar `data/models/blaze_face_short_range.tflite`. **Als dit bestand ontbreekt, print `presence_detector.py` een duidelijke waarschuwing en valt netjes terug op "geen info" — geen crash.**

**Nieuw bestand:** `modules/context/presence_detector.py`. Volgt de standaard dynamische module_loader-conventie (geen `layers`-dictionary nodig). Webcam gaat telkens open/dicht PER meting (niet continu open) — zo blijft het cameralampje niet permanent branden en blijft de webcam vrij voor andere apps tussendoor. Heeft een `shutdown()`-methode (net als `chess_engine.py` voor Stockfish), aangeroepen bij `exit` in `main.py`.

**Belangrijke terminologie-nuance (16 juli 2026):** `is_alone` betekent "is NOVA alleen" (niemand om tegen te praten), NIET "is Kevin sociaal alleen in de kamer". Kevin's eigen gezicht telt dus mee als "iemand aanwezig" — 1 gezicht (Kevin) → `is_alone: False` → Nova mag spreken. 0 gezichten → `is_alone: True` → Nova is "alleen", niemand om tegen te praten.

**Uitbreiding `context_manager.py`:** nieuwe methode `update_presence_info()`, BEWUST APART van `get_current()` — `get_current()` opent NOOIT zelf de webcam (dat zou het lampje bij elke minuutcheck laten flikkeren). In plaats daarvan onthoudt `context_manager` een `_laatst_bekende_presence`, enkel bijgewerkt via `update_presence_info()`, die vanuit `main.py` spaarzaam wordt aangeroepen (zie hieronder). Als een meting faalt (webcam-hik), wordt de vorige laatst-bekende waarde NIET overschreven met "onbekend" — een tijdelijke hik mag een goede laatste meting niet wissen.

**Nieuwe regel in `_bepaal_interrupt()` (na afweging met Kevin — Optie B gekozen):** is er NIEMAND aanwezig (`is_alleen is True`)? Dan mag Nova NIET onderbreken — spreken heeft geen zin als er niemand is om het te zien/horen, dat zou enkel een misplaatste, opgestapelde melding worden tegen de tijd dat Kevin terugkomt. Deze regel staat vlak NA de anomalie-check maar VOOR de coding/focus-logica (webcam-info is een directer, feitelijker signaal dan input-timing). `is_alleen is True` wordt EXPLICIET gecheckt (niet `if is_alleen`), zodat `None` (geen info) nooit per ongeluk als "niemand aanwezig" behandeld wordt.

**Nieuwe instelling in `main.py`:** `PRESENCE_CHECK_INTERVAL_MINUTEN = 5` (instelbare constante, makkelijk later aan te passen). Webcam-check gebeurt SPAARZAMER dan activity/focus (elke 5 min i.p.v. elke minuut) — bewuste keuze na gesprek met Kevin: het cameralampje flikkert onvermijdelijk mee bij elke ECHTE meting (hardwarematig gekoppeld aan de sensor, geen software-instelling die dit kan omzeilen — bewuste privacybescherming, niet iets om te omzeilen). `achtergrond_loop()` houdt een `aantal_loops`-teller bij en roept `context_manager.update_presence_info()` aan (niet `presence_detector` rechtstreeks) enkel elke N loops.

**Nieuw debug-commando's in `main.py`:** `presence debug` (forceert een meting, toont ruw resultaat, logt NIET naar context_log.jsonl — gaat niet via context_manager) en `presence debug context` (forceert een meting ÉN laat context_manager die onthouden via update_presence_info(), toont volledige summary — gebruikt om de volledige keten te testen zonder 5 minuten te wachten).

**Bekende, bewust geaccepteerde cosmetische eigenaardigheid:** MediaPipe 0.10.35 print ongevraagd, ongedocumenteerde Google-telemetrie-foutmeldingen naar de console (`E0000 ... portable_clearcut_uploader.cc ... Failed to send to clearcut ...`), plus onschuldige TFLite/XNNPACK-initialisatielogs. Bevestigd via community GitHub-issues (`google-ai-edge/mediapipe#6291`, `#4991`) dat dit een bekend, niet-officieel-oplosbaar probleem is sinds ergens tussen MediaPipe 0.10.21-0.10.35 — geen referentie naar "clearcut" bestaat in de open-source MediaPipe-repo, en de PyPI-pakketten zijn intern bij Google gebouwd. De upload FAALT altijd (`FAILED_PRECONDITION`), maar een netwerkverbindingspoging naar `play.googleapis.com` (216.239.*) werd door een andere gebruiker bevestigd via Wireshark. **Mitigatie:** Windows Firewall-regel ingesteld (`New-NetFirewallRule -DisplayName "Block MediaPipe Clearcut Telemetry" -Direction Outbound -RemoteAddress 216.239.32.0/19 -Action Block`) — blokkeert de daadwerkelijke netwerkverbinding volledig, ongeacht wat MediaPipe intern probeert. De console-rommel zelf blijft zichtbaar (meerdere pogingen tot onderdrukking via `GLOG_minloglevel`/OS-niveau stderr-redirect faalden — Windows' consolelaag bleek te broos voor dat soort low-level trucs, gaf `OSError: [WinError 1] Onjuiste functie`) — bewust geaccepteerd als puur cosmetisch, functioneel onschadelijk zolang de firewall-regel actief blijft.

**Getest (16 juli 2026):**
- `presence debug` alleen (zonder context-koppeling): 1 gezicht correct gedetecteerd bij aanwezig zijn, 0 bij wegkijken/wegdraaien
- `presence debug context` (volledige keten): `Gezichten: 1` → `Mag onderbreken: True`; `Gezichten: 0` → `Mag onderbreken: False` met reden `"niemand aanwezig volgens webcam (Fase 4)"` — bevestigt de volledige, correcte werking van de nieuwe regel

**Nog te bouwen (Fase 5):** verfijnde interruption-logica op basis van alle sensoren samen (Layer 2 + activiteit + focus + aanwezigheid), mogelijk gewogen i.p.v. de huidige simpele if/else-volgorde.

---

## 🔄 Semantic — Status & Roadmap

### Fases 1-7 (VOLLEDIG KLAAR ✅)

| Fase | Omschrijving | Status |
| --- | --- | --- |
| 1 | Datastructuur & opslag | ✅ |
| 2 | Teach & Auto-Lear | ✅ |
| 3 | Relation Engine | ✅ |
| 4 | Query Engine | ✅ |
| 5 | Integratie (intent_router, chat, pipeline) | ✅ |
| 6 | Wikipedia-module | ✅ |
| 7 | Reasoning Layer (chaining, inference) | ✅ |

### Fases 8-13 (Toekomst — semantic_extension_roadmap.md)

| Fase | Omschrijving                      | Type              | Status        |
| --- | --- | --- | --- |
| 8    | Causal Reasoning                  | Pure symbolisch   | ❌ Toekomst   |
| 9    | Temporal Semantics                | Pure symbolisch   | ❌ Toekomst   |
| 10   | Uncertainty Tracking              | Pure symbolisch   | ❌ Toekomst   |
| 11   | Knowledge Extraction (spaCy)      | ML                | ❌ Toekomst   |
| 12   | Semantic Similarity (embeddings)  | ML                | ❌ Toekomst   |
| 13   | Graph Visualization (Plotly)      | ML                | ❌ Toekomst   |

**concepts.json:** gevuld met testdata (hond, dier, appel, pitvrucht, vliegtuig, democratie...) — productiedata, niet wissen.

---

## ♟️ Games — Status & Roadmap

| Spel                                   | Modul               | Status      | Engine                   |
| --------------------------------------- | ------------------- |  ------------| ------------------------ |
| Schaak                                | chess_engine.py     | ✅ Klaar    | Stockfish (symbolisch)   |
| Dammen                                | checkers_engine.py  | ❌ Toekomst | Symbolic engine          |
| Go                                    | go_engine.py        | ❌ Toekomst | KataGo (neural, bounded) |
| Meerdere bordspellen (dammen, Go, ...)| active_game systeem | ❌ Toekomst | via IntentRouter         |

**Geplande features:**

- Langzame partijen over weken/maanden
- GUI bord + chat sidebar (tegelijk praten en spelen)
- Commentary per zet ("Interessante zet!")
- Leren van Kevin's spelstijl via Layer 2 (pattern_matcher)

---

## 🔁 Reboot & Hot Reload


| Feature                                 | Status                      | Roadmap                     |
| ----------------------------------------- | ----------------------------- | ----------------------------- |
| /reboot commando (full restart, ~5 sec) | ✅ Klaar en volledig getest | reboot_hotreload_roadmap.md |
| /reload module (manual hot reload)      | ❌ Later                    | reboot_hotreload_roadmap.md |
| Auto file watcher (Ctrl+S → reload)    | ❌ Veel later               | reboot_hotreload_roadmap.md |

**Implementatie:** `core/reboot_manager.py` — luistert naar event `system:reboot`. Bij triggeren: memory-buffer geflusht + achtergrondtimer gestopt, alle modules met een `shutdown()`-methode netjes afgesloten (via `loaded_modules`-dictionary, meegegeven door `module_loader.py`), daarna een **volledig nieuw, los proces** gestart via `subprocess.Popen(..., creationflags=CREATE_NEW_CONSOLE)`, gevolgd door `sys.exit(0)` van het oude proces. Hierdoor worden alle `.py`-bestanden én alle `.json`/`.jsonl`/`.db`-bestanden opnieuw van schijf ingelezen — geen enkele module blijft met oude code of oude data in het geheugen hangen.

**Waarom geen `os.execv()`?** Eerste versie gebruikte `os.execv()`, maar op Windows bestaat er geen echte "exec"-systeemaanroep zoals op Linux/Mac — Python simuleert dit door een nieuw kindproces te starten terwijl het oude nog even blijft hangen. Dat gaf trage/gemiste toetsaanslagen in de terminal (twee processen die kort om dezelfde stdin concurreren) — een bekend, gedocumenteerd Python-probleem op Windows (bugs.python.org/issue19124), geen fout in Nova's eigen code. Opgelost door over te stappen op `subprocess.Popen` met een eigen console-venster per herstart.

Getriggerd via `/reboot` in `intent_router.py` (`detect_reboot()`, als allereerste check in `route()`, vóór alle andere intents). Afscheidsboodschap ("Oké, ik herstart even...") gebeurt bewust via een directe `print()` in `reboot_manager.py` zelf, NIET via een `chat_response`-event — een event zou pas later door `main.py` opgehaald worden, maar tegen die tijd is het oude proces mogelijk al bezig met afsluiten.

**main.py bevat nu ook een VT100-fix** (helemaal bovenaan, vóór alle imports): via `ctypes`/`SetConsoleMode` wordt `ENABLE_VIRTUAL_TERMINAL_PROCESSING` expliciet aangezet. Nodig omdat een vers Windows-console-venster (ontstaan door `subprocess.Popen` met `CREATE_NEW_CONSOLE`) niet altijd gegarandeerd ANSI-kleurcodes correct interpreteert — zonder deze fix verschenen kleurcodes soms letterlijk als tekst (`←[92m`) in plaats van als kleur.

**Vijf bugs gevonden en opgelost tijdens testen (5 juli 2026):**

1. Windows-input-probleem door `os.execv()` → opgelost met `subprocess.Popen` + eigen console-venster (zie boven).
2. `sqlite3.ProgrammingError: Cannot operate on a closed database` bij afsluiten — `reboot_manager.py` sloot de SQLite-connectie zelf af, terwijl `memory.py`'s eigen `atexit`-hook (`_on_shutdown`) dat via `sys.exit(0)` sowieso al deed → dubbele sluiting. Opgelost door in `reboot_manager.py` enkel nog de write-buffer te flushen, en het effectieve sluiten van de connectie volledig aan `memory.py`'s eigen `atexit`-hook over te laten.
3. Oud terminalvenster bleef na `/reboot` hangen zolang een schaakpartij actief was — Stockfish (extern UCI-proces, gestart door `chess_engine.py`) werd niet afgesloten vóór de herstart. Opgelost door `reboot_manager.py` de volledige `loaded_modules`-dictionary te laten meekrijgen van `module_loader.py`, en bij `/reboot` via `_shutdown_external_processes()` op élke module met een `shutdown()`-methode die methode aan te roepen (dus ook `chess_engine.py`, en automatisch ook toekomstige modules met externe processen zoals KataGo).
4. `TypeError: init_module() got an unexpected keyword argument 'loaded_modules'` — bij het doorvoeren van bugfix #3 werd de klasse `RebootManager.__init__` wel aangepast om `loaded_modules` te accepteren, maar de losstaande `init_module()`-functie onderaan het bestand (die `module_loader.py` effectief aanroept) werd vergeten mee te updaten. Opgelost door ook `init_module(event_bus, memory=None, loaded_modules=None)` de parameter te laten doorgeven aan `RebootManager(...)`.
5. `interactions.db-wal` en `interactions.db-shm` (SQLite WAL-mode hulpbestanden) bleven na afsluiten op schijf staan — onschuldig voor de data zelf (die staat er nog steeds veilig in), maar niet netjes opgeruimd. `memory.py`'s `_on_shutdown()` deed wel `commit()` + `close()`, maar geen expliciete WAL-checkpoint, waardoor SQLite het logboekbestand niet altijd automatisch leegmaakte bij het sluiten. Opgelost door vlak vóór `conn.close()` een `PRAGMA wal_checkpoint(TRUNCATE)` toe te voegen, die alle wijzigingen definitief naar `interactions.db` overzet en `-wal`/`-shm` weer naar 0 bytes brengt.

Getest op 5 juli 2026: partij (schaak, inclusief actieve Stockfish-verbinding) en patronen (Layer 2) correct teruggevonden na herstart, alle modules netjes herladen en afgesloten, geen dataverlies, geen achterblijvende processen of vensters. WAL-checkpoint bij afsluiten nog te bevestigen door Kevin (verwacht: `-wal`/`-shm` verdwijnen of blijven op 0 bytes na `exit`/`/reboot`).

---

## 💡 Idee (nog niet ingepland): fijner tijdsraster in Layer 2

Kevin's vraag (7 juli 2026): wat als hij binnen hetzelfde uur zowel schaakt als codeert, of als hij consistent rond een specifiek half uur (bv. 21u30) iets doet — kan Layer 2 dat preciezer vastleggen dan het huidige uur-niveau?

**Belangrijk onderscheid, vastgesteld tijdens dit gesprek:** een fijner raster (bv. 30 of 15 minuten) lost NIET vanzelf op dat Nova ooit kan zeggen "het is 19u30, je codeert al 3u30 zonder te eten" — dat is een apart vraagstuk (duur-detectie + afwezigheid van een ander event), al uitgewerkt in **activity_awareness_roadmap.md, Deel D**. Een fijner tijdsraster lost enkel op: "op welk specifiek moment binnen het uur gebeurt dit meestal", niet "hoe lang loopt dit al" of "is er ondertussen iets anders NIET gebeurd."

**Voorstel indien dit ooit gebouwd wordt:** een `minute_bucket`-veld toevoegen NAAST het bestaande `hours`-veld (bv. blokken van 30 min: `{"21:30": 4, "21:00": 1}`), puur additief — niet als vervanging. Reden: `hours` zit diep verweven doorheen `_check_ongewone_timing()` (met een vaste "4 uur"-anomaliedrempel), de achtergrondtimer (`_check_missing_events()`, draait zelf op een uur-interval), `is_pattern_active()` en `predict_next_occurrence()`. Dat allemaal laten meeschalen naar een fijner raster zou een grote herwerking zijn met weinig garantie op winst. Een aparte, optionele teller ernaast is veel kleiner en breekt niets bestaands.

**Waarom nu nog niet bouwen:** met de huidige, nog kleine hoeveelheid observaties per topic zou elk 30-minuten-blok meestal maar 1 observatie hebben — de confidence-score zou dan kunstmatig op 1.0 staan zonder dat het iets betekent. Pas zinvol zodra uur-patronen na verloop van tijd al een stabiele, hoge confidence tonen én blijkt dat uur-niveau te grof is voor wat Kevin ermee wil doen.

---

## 👤 User Preferences (concept, nog niet ingepland)

Losse module die expliciete feiten over Kevin onthoudt (voorkeuren/afkeuren), los van Layer 1.

| Fase | Omschrijving                          | Status              |
| --- | --- | --- |
| 1    | Databestand + basis CRUD              | ❌ Nog te bouwen    |
| 2    | Expliciet commando (onthoud:/vergeet:)| ❌ Nog te bouwen    |
| 3    | Automatische patroonherkenning        | ❌ Nog te bouwen    |
| 4    | Integratie in chat.py                 | ❌ Nog te bouwen    |

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
| --- | --- | --- |
| 1 | Foundation Fix (paden, retry, log rotation) | ✅ |
| 2 | SQLite + Daemon Basis (WAL, write buffer, graceful shutdown) | ✅ |
| 3 | Query API (search, query, get_stats, find_similar) | ✅ |
| 4 | Achtergrond-onderhoud timer, layer-integratie | ✅ Getest (archiveren, comprimeren, VACUUM, event publishing) |
| 5 | Optimization & polish (query caching, memory leaks, concurrent access, backup, health check) | 🟢 Later — pas nodig bij grote databank/veel gelijktijdige toegang |

Volledig beschreven in: **memory_24-7_daemon_addendum.md**

---

## 🚀 Volgende stappen (in volgorde van prioriteit)

1. ✅ **Personality pipeline (deel 1)** — uitgebreid naar weer/tijd/math (11 juli 2026, zie bug #5 en `layer4_response`-sectie). Nu door de tone-pipeline: greeting, fallback, Layer 4-definities, weer, tijd, math.
2. ✅ **Personality pipeline (deel 2) — opgelost (12 juli 2026).** Alle 10 semantic-gerelateerde handlers in `chat.py` publiceren nu `layer4_response` i.p.v. rechtstreeks `chat_response`: `on_relation_check`, `on_part_of_check`, `on_subtypes_query`, `on_related_to`, `on_synonym`, `on_antonym`, `on_used_for`, `on_causes`, `on_properties`, `on_meaning`. Zowel het succespad als het "geen resultaat"-pad (bv. "Welk woord bedoel je?") lopen nu door de tone-pipeline, voor een consistente warme toon ongeacht uitkomst. `on_greeting` bewust ongewijzigd gelaten — die loopt al via `response_pipeline.py`'s eigen, aparte `on_greeting()`-handler (zelfde patroon als `on_fallback()`), dus ombouwen naar `layer4_response` zou dat bestaande specifieke pad juist doorbreken. Schaken en help blijven bewust rechtstreeks op `chat_response` (zie `layer4_response`-sectie) — schaken wordt herbekeken zodra Kevin's huidige chess-uitbreidingen klaar zijn.

    **Bijvangst tijdens het testen: `related_to` had geen enkele trigger in `intent_router.py`.** `on_related_to()` in `chat.py` en de bijbehorende `related_to`-relaties in `concepts.json` (bv. `geluid → muziek`, `vloeistof → water`) bestonden al, maar waren via geen enkele natuurlijke zin bereikbaar — `detect_definition()` had wel blokken voor synoniemen/antoniemen/used_for/causes/properties, maar nooit een voor related_to. Toegevoegd: een nieuw detectieblok (`"waarop lijkt "`, `"waar lijkt "`, `"wat lijkt op "`) volgens exact hetzelfde patroon als de bestaande vier blokken, incl. lidwoord-stripping. Getest en werkend: "waarop lijkt geluid" → "geluid lijkt op: muziek", plus het "geen resultaat"-pad ("waarop lijkt een hond" → "Ik weet niet waarop hond lijkt.").
3. 🟢 **microlearning.py** — bouwen (bestand bestaat, is leeg)
4. 🟢 **User preferences-module** — nog te plannen (memory_user_preferences_roadmap.md). Groeiend takenpakket: expliciete voorkeuren (ik hou van/haat X), disambiguatie-keuzes voor meerduidige woorden (zie bug #10, Layer 4-sectie), en mogelijk een feedback-loop voor Layer 4-antwoorden.
5. 🟢 **memory.py Fase 5** — optimalisatie/polish, enkel nodig bij grote databank of trage queries (geen haast)
6. 🟢 **Layer 2 opruimwerk** — anomaly-drempels (MIN_OBSERVATIES_VOOR_ANOMALIE, MIN_CONFIDENCE_VOOR_ANOMALIE) en opslagfrequentie (nu elke 2 observaties) staan nog op tijdelijke, verlaagde testwaarden — terugzetten naar realistischere waarden voor normaal gebruik. **Bekende bijwerking hiervan (7 juli 2026, geen bug, bestaand tijdelijk gedrag):** `save_to_disk()` wordt enkel aangeroepen als `total` van een event_type even is (`% 2 == 0`). Bij een oneven `total` (bv. na 1 of 3 observaties van een `topic_detected:*`-event) toont `patterns_layer2.json` op schijf dus tijdelijk een lager aantal dan wat `patronen <event_type>` live in het geheugen toont. Dit lost zichzelf op zodra deze opslagfrequentie later realistischer gemaakt wordt (zie hierboven), maar is voor nu iets om bij te houden tijdens testen: het JSON-bestand is niet altijd de meest actuele bron, het live geheugen wel.
7. 🟢 **Intent classifier (ML-specialist)** — concept, nog niet ingepland. Los van Layer 1-7, hangt enkel af van Layer 0-data. Volledig uitgewerkt in: intent_classifier_roadmap.md.
8. 🟢 **Activity Awareness (activiteiten herkennen, correleren, proactief reageren)** — concept uitgewerkt (6 juli 2026), nog niet ingepland. Kern: generiek `"ik ga <activiteit>"`-patroon in intent_router.py publiceert `activity_started`-events die Layer 2 al generiek meetelt; daarnaast co-occurrence tussen activiteiten (bv. koffie + coderen) en duur-detectie met drempelwaarde voor proactieve pauze-suggesties — beide pure statistiek/timer-logica, geen ML. Optioneel scherm-detectie (psutil, geen ML) en camera-detectie (vereist extern vision-model als sensor, met privacy-ontwerp vooraf). Ook: mogelijke uitbreiding naar per-woord-timing voor Layer 4 (zie Layer 4-sectie). Volledig uitgewerkt in: **activity_awareness_roadmap.md**.
9. 🟢 **Activity-Aware Interaction (interruption learning + contextuele suggesties)** — concept uitgewerkt (9 juli 2026), nog niet ingepland. Bouwt voort op Activity Awareness + Layer 5 (Layer 5 Fase 1-4 zijn intussen klaar, zie punt 13.5 hieronder): leert per activiteit een confidence-score op ("mag ik storen tijdens coderen?"), met vaste sjabloonvariatie zodat het niet elke keer identiek klinkt. Aparte, grotere uitbreiding: contextuele suggesties tussen activiteiten (bv. Plex → lichten dimmen) — puur co-occurrence-tellen zoals Activity Awareness Deel C, maar vereist voor "alledaagse" acties (zoals lichten dimmen via schakelaar) een aparte sensor/integratie-laag (bv. Home Assistant/Hue) om dat moment uberhaupt als Nova-event zichtbaar te maken. Volledig uitgewerkt in: **interruption_learning_roadmap.md**.
13.5 ✅ **Layer 5 Fase 1-4 (Context Manager, Activity/Focus/Presence Detection)** — gebouwd en getest (13-16 juli 2026). Fase 1: tijd + Layer 2-koppeling. Fase 2: activiteit-detectie via venstertitel (`activity_detector.py`, `pygetwindow`). Fase 3: focus-detectie via input-timing (`focus_detector.py`, `GetLastInputInfo`). Fase 4: aanwezigheidsdetectie via webcam (`presence_detector.py`, MediaPipe Tasks API — eerste bounded ML-tool in Layer 5). Enkel Fase 5 (verfijnde combinatie-logica) nog te bouwen. Zie sectie "Layer 5 — Context Manager" onder 7-Laags Memory Architectuur voor volledige details.
10. ✅ **emotion_engine.py decay/recovery-mechanisme** — opgelost (11 juli 2026), zie bug #4/#11. `overstimulation.level` heeft nu zowel tijd- als interactie-gebaseerde decay.
11. 🟡 **Layer 6/7 — identity-blueprint grotendeels niet aangesloten op de tone-pipeline.** Ontdekt tijdens bug #4/#11-onderzoek (11 juli 2026): er ligt een rijk uitgewerkt fundament klaar dat niet of nauwelijks gebruikt wordt in de praktijk:
    - **`identity.json`** (volledige blueprint: `regulation_profile`, `overstimulation_signs`, `recovery_behavior`, `sensorimotor_profile`, `embodied_cognition`, `interaction_nuance`, enz.) wordt door `loader.py` ingeladen en tegen `schema.json` gevalideerd, maar buiten die validatie leest niemand deze velden ooit uit om er gedrag op te baseren.
    - **`personality_engine.py`** wordt wel aangeroepen (`generate_response_style()` levert `pace`/`tone`/`interrupts`/`dramatic` op), maar die output wordt in `chat_response_engine.py`/`expression_injector.py` enkel doorgegeven in de event-data — niet gebruikt om de uiteindelijke tekst te beïnvloeden. Enkel `tone_engine.py`'s output (emoji's/flair) heeft echt effect.
    - **`behavior_modifiers.py`** (`BehaviorModifiers`) wordt aangemaakt in `PersonalityEngine.__init__()`, maar geen van zijn methodes (`apply_energy_modulation()`, `apply_impulsivity()`, `apply_dramatic_flair()`) wordt ooit ergens aangeroepen — volledig dode klasse in de praktijk.

    Geen bug — dit is nooit "verkeerd" gebouwd, gewoon nog niet de volgende bouwfase. Hoort thuis bij **Layer 6 (Personality Engine)** volgens `identity_ROADMAP.md`, met raakvlakken naar **Layer 7 (Emergent Behaviors)** voor de niet-gebruikte `dramatic_flair`/`sync_with_kevin`/`behavior_modifiers`-mechanismen. Nog niet ingepland — apart op te pakken wanneer Layer 6/7 aan de beurt zijn.

    **Aanvulling (12 juli 2026):** los van dit werkpunt is er wél een nieuwe, kleinere identity-gerelateerde laag bijgekomen: `identity/self_query.py` leest `identity.json` (via de bestaande `loader.py`) en de live `emotion_state.json` uit om vragen als "wie ben je"/"wat vind je leuk"/"hoe voel je je" te beantwoorden. Dit is GEEN oplossing van bovenstaand werkpunt — `personality_engine.py` en `behavior_modifiers.py` blijven net zo ongebruikt als hierboven beschreven — maar een apart, direct pad van vaste blueprint-velden naar spreektekst, zonder over de personality/behavior-laag te lopen. Zie sectie "Zelfkennis-laag" verderop voor details.
12. ✅ **Fundamentele voorwaarde voor proactief gedrag: `main.py`'s blocking `input()`-lus — opgelost (12 juli 2026).** Achtergrondthread + directe EventBus-subscriber op `chat_response` gebouwd en getest met een eerste echte proactieve feature (`session_watcher.py`, pauze-melding na inactiviteitsdrempel). Volledige uitleg van het patroon in de nieuwe sectie **"Proactief spreken — het achtergrondthread-patroon"** hieronder.
13. ✅ **Zelfkennis-laag — Nova kan vragen over zichzelf beantwoorden — gebouwd en getest (12 juli 2026).** Nieuw bestand `identity/self_query.py` (17 `antwoord_*()`-functies, laadt `identity.json` via de bestaande `load_identity_blueprint()`) + `detect_identity_question()` in `intent_router.py` (18 herkende categorieën, publiceert `intent_identity` met `sub_intent`) + `on_identity_question()`-handler in `chat.py` (routeert naar de juiste functie, antwoord via `layer4_response`). Enige uitzondering op "leest identity.json": de stemmingsvraag ("hoe voel je je") leest de LEVENDE `EmotionEngine.state` via `response_pipeline`, niet de statische blueprint. **Architecturale les:** `identity/` wordt niet gescand door `module_loader.py`'s dynamische lus (die doet enkel `modules/`), dus `self_query.py` laadt zijn data op module-niveau bij import, niet via een `init_module()`-conventie die hier nooit aangeroepen zou worden. Getest en werkend: "wie ben je", "wat is je doel", "waar ben je goed in", "hoe voel je je" geven correct de juiste blueprint-/live-data terug.

---

## 📚 Roadmap documenten (in project)

- Nova_Roadmap.md — Overkoepelende/algemene roadmap van het project
- memory_layer0_roadmap.md — Layer 0: memory.py v2.0 (SQLite, tiering, query API)
- memory_24-7_daemon_addendum.md — 24/7 daemon aanpassingen voor memory.py
- memory_layer1_roadmap.md — Layer 1: Word Associations Learner (PMI scoring)
- memory_layer2_roadmap.md — Layer 2: Pattern Matcher (gedragspatronen)
- memory_layer4_roadmap.md — Layer 4: Response Generation Engine
- memory_layer5_roadmap.md — Layer 5: Context Manager (interruption logic)
- memory_layer7_roadmap.md — Layer 7: Emergence Engine (zelfbewustzijn)
- semantic_roadmap.md — Semantic Fases 1-7 (KLAAR — referentie bewaren)
- semantic_extension_roadmap.md — Semantic Fases 8-13 (toekomstige uitbreidingen)
- semantic_architecture.md — Architectuurdocument semantic.py: engines (ConceptStore, SenseEngine, RelationEngine, TeachEngine, RelationParser, RelationFlowEngine) en hoe ze samenwerken
- semantic_api.md — API-referentie voor semantic.py (beschikbare functies/aanroepen)
- semantic_teachengine.md — Detail-documentatie van de TeachEngine binnen semantic.py
- reboot_hotreload_roadmap.md — Reboot + Hot Reload (3 fases)
- memory_user_preferences_roadmap.md — User Preferences: wat Nova over Kevin onthoudt (voorkeuren/afkeuren)
- topic_events_roadmap.md — `topic_detected`-events: hoe Layer 2 specifieke onderwerpen (schaak, Plex, ...) op tijdstip leert koppelen, en hoe Layer 4 dat later in vaste sjabloonzinnen gebruikt
- identity_ROADMAP.md — Identity-opbouw in 6 fases: Blueprint → Personality Engine → Emotion Engine → Expression Engine → Integration Layer → Adaptive Learning (later)
- math_roadmap.md — Roadmap voor math.py-uitbreidingen
- intent_classifier_roadmap.md — ML-specialist naast intent_router.py: klein lokaal classificatiemodel (scikit-learn) dat nieuwe, onbekende zinnen naar een bekende intent-categorie voorspelt. Concept, nog niet ingepland in bouwvolgorde.
- activity_awareness_roadmap.md — Activiteiten herkennen via intent/scherm/camera, co-occurrence tussen activiteiten, duur-detectie + proactieve pauze-suggestie. Concept, nog niet ingepland in bouwvolgorde.
- interruption_learning_roadmap.md — Activity-Aware Interaction: (1) leren wanneer Nova mag storen tijdens een activiteit (confidence-score per activiteit, generiek), (2) variatie in formulering zodat het niet mechanisch aanvoelt, (3) contextuele suggesties tussen activiteiten (bv. Plex → lichten dimmen) — dit laatste vereist een aparte sensor/integratie-laag voor alledaagse acties die nog geen Nova-event zijn. Concept (9 juli 2026), nog niet ingepland; hangt af van Activity Awareness Deel A en Layer 5 Fase 1-2.
- ml_components_overview.md — Overzicht per laag (1/2/3/4) van mogelijke bounded ML-toevoegingen — referentiedocument, geen bouwvolgorde. Layer 3 (GNN voor concepts.json) is Kevin's belangrijkste "achterhoofd"-optie, grootste ingreep van de lijst.
- llm_codegen_tool_roadmap.md — Claude API als externe tool: (1) fallback/missing-intent tracking blijft 100% symbolisch in Nova zelf, (2) Claude API als codeer-tool ("live typen" in VSCode) en voor fallback-log-analyse — beide altijd Kevin-getriggerd, nooit autonoom binnen Nova's daemon-loop. Bevat kernprincipe "wie beslist wanneer" en uitleg waarom de kale API geen geheugen heeft tussen aanroepen. Concept (11 juli 2026), nog niet ingepland.
- reasoning_engine_ideeen_roadmap.md — Losse ideeënbak (géén bouwvolgorde) voor 6 mogelijke Reasoning Engine-uitbreidingen: get_all_parts, related_to_chained, part_of-contradictiedetectie, multi-hop vragen combineren, "waarom niet"-uitleg bij negatief antwoord, concept-vergelijkingen. Ontstaan tijdens het bouwen van part_of_chained/get_all_subtypes (12 juli 2026); deels overlap met semantic_extension_roadmap.md Fase 7.4/8, deels compleet nieuw.

---

## 🧵 Proactief spreken — het achtergrondthread-patroon (sinds 12 juli 2026)

**Probleem dat dit oplost:** `main.py`'s hoofdlus draait rond een blocking `input()`-aanroep. Zolang die op Kevin's toetsaanslag wacht, staat de rest van het programma stil — Nova kon dus nooit uit zichzelf iets zeggen (reminders, pauze-suggesties, straks Layer 5-meldingen), enkel reageren nadat Kevin al iets typte.

**Oplossing — twee losse onderdelen die samenwerken:**

1. **Een `daemon=True`-achtergrondthread in `main.py`** (`achtergrond_loop()`), gestart via `threading.Thread(...)` vlak na het laden van de modules. Deze thread loopt volledig onafhankelijk van de `input()`-lus en kan op elk moment code aanroepen — voorlopig enkel `session_watcher.check_pauze()` elke 60 seconden, maar dit is de plek waar Layer 5 straks op aansluit.
2. **Een rechtstreekse EventBus-subscriber op `chat_response`** (`on_chat_response()` in `main.py`, geregistreerd via `bus.subscribe("chat_response", on_chat_response)`). Dit was de kern van de fix: de oude aanpak printte `chat_response`-berichten enkel via polling in de hoofdlus (`mem.get_recent_events()`, pas uitgevoerd **na** dat Kevin zelf iets typte) — een proactief bericht van de achtergrondthread bleef daardoor onzichtbaar in de memory-buffer liggen tot Kevin toevallig weer iets intypte. Met een directe subscriber print het bericht **onmiddellijk**, ongeacht welke thread het publiceerde. De oude polling-tak voor `etype == "chat_response"` in de hoofdlus is bewust leeggemaakt (`pass`) om dubbel printen te voorkomen — alle andere event-types (`semantic_update`, `pattern_update`, `time_zone_ready`) lopen nog gewoon via de oude polling-weg.

**Het "verse prompt"-mechanisme (`wachten_op_input`):** een proactief bericht dat verschijnt terwijl Kevin's `Jij: `-prompt al op het scherm staat, oogt rommelig — de prompt-tekst raakt visueel "begraven" onder Nova's nieuwe tekst. Opgelost met een globale vlag `wachten_op_input`, die `True` is exact zolang de hoofdthread binnen de `input()`-aanroep zit. `on_chat_response()` controleert deze vlag na het printen: staat hij op `True`, dan was dit bericht proactief (van de achtergrondthread) en wordt de `Jij: `-prompt handmatig opnieuw getekend. Komt het bericht als normaal antwoord op Kevin's eigen typen, dan staat de vlag op `False` en gebeurt er niets extra — de volgende `input()`-aanroep toont vanzelf een nieuwe prompt.

**Bekende, geaccepteerde beperking:** als Kevin *net* een paar letters aan het typen is op het exacte moment dat een proactief bericht binnenkomt, kan die halfgetypte tekst nog even kort door elkaar lopen met Nova's output vóór de prompt zich herstelt. Dit is een inherente grens van `input()` in een console-app zonder externe libraries zoals `prompt_toolkit` — geen bug, bewust geaccepteerd als aanvaardbare edge case voor een lokale terminal-tool.

**Eerste proactieve feature gebouwd op dit patroon: `modules/activity/session_watcher.py`.** Houdt via `time.time()` bij hoe lang de sessie loopt sinds start (of sinds de vorige melding), en publiceert éénmalig een `chat_response`-event zodra `PAUZE_DREMPEL_SECONDEN` (standaard 1800 = 30 min) overschreden is. Puur symbolisch — enkel tijd bijhouden en vergelijken, geen ML. Volgt de standaard `init_module(event_bus, sem=None)`-conventie, dus automatisch opgepikt door `module_loader.py`'s dynamische lus.

**Voor toekomstige proactieve modules (zoals Layer 5 straks):** dit patroon is nu de vaste weg. Nieuwe proactieve logica hoort in een aparte module met een `check_*()`-achtige methode, aangeroepen vanuit `achtergrond_loop()` in `main.py`, die zelf `event_bus.publish("chat_response", {...})` of `event_bus.publish("layer4_response", {...})` publiceert — nooit rechtstreeks `print()` vanuit de achtergrondthread zelf, anders mis je de tone-pipeline en het "verse prompt"-mechanisme.

---

## 📡 `layer4_response` — universele route naar de tone-pipeline (sinds 11 juli 2026)

Ondanks de naam is `layer4_response` intussen **niet meer exclusief voor Layer 4** (response_engine.py/definities). Elke module die een al-kant-en-klare, spreektalige tekst heeft en enkel nog Nova's stemming (emoji's, uitroeptekens, gestures) wil laten toevoegen, publiceert dit event i.p.v. rechtstreeks `chat_response`:

- **Layer 4 / definities** (`response_engine.py`, `chat.py`'s Wikipedia-vangnet)
- **Weer** (`weather.py`)
- **Tijd** (`time.py`)
- **Math** (`math.py`)

`response_pipeline.py`'s `on_layer4_response()`-handler verzint zelf geen tekst — die stuurt enkel door naar de tone-keten (`pipeline_response` → `chat_response_engine.py` → `expression_injector.py` → uiteindelijk `chat_response`). Bij nieuwe modules die korte, spreektalige antwoorden geven (bv. de toekomstige datum/feestdagen-module) is dit dus meteen het juiste event om op aan te sluiten, i.p.v. rechtstreeks `chat_response` te publiceren.

**Bewust NIET via `layer4_response`, blijft rechtstreeks op `chat_response`:**

- **Help** (`help.py`) — vaste, opgemaakte referentietekst (commando-overzicht); een uitroepteken/emoji's achteraan voegt daar niets toe. Definitieve keuze (11 juli 2026).
- **Schaken** (`chess_engine.py`) — bordweergave (ANSI-kleurcodes, multi-regel) en statistieken zijn gestructureerde output, geen conversatie-antwoorden; `expression_injector.py` plakt emoji's/uitroeptekens achteraan de tekst, wat na een schaakbord visueel niet klopt. **Bewust uitgesteld** (11 juli 2026) — Kevin breidt chess_engine.py nog uit (zie openstaande schaak-punten: check-notificatie #3, last-move-highlighting #4, promotie #5, etc.); dit wordt in één beurt herbekeken zodra die uitbreidingen klaar zijn, incl. de vraag of korte meldingen (nieuwe partij, moeilijkheidsgraad/denktijd instellen) wél door de tone-pipeline zouden mogen, en bord/mat-melding niet.
- De synoniem/antoniem/relatie/eigenschappen-intents in `chat.py` gaan sinds 12 juli 2026 wél door de tone-pipeline (zie werkpunt #2), maar nog niet door de volledige Layer 4-combinatie (`response_engine.generate()` met Layer 1/Layer 2-verrijking) — zie de bijgewerkte notitie bij Layer 4 hieronder.

---

## 💡 Architectuurprincipes om te onthouden

- **Local first** — alles draait op Kevin's eigen machine
- **Transparent always** — alles gelogd, audit_log op elk concept
- **Nooit handelen zonder toestemming** — kernprincipe
- **Geen LLM in de kern** — wel externe gespecialiseerde modellen (vision, ML-classificatie) als aparte modules
- **ML mag als sensor** — een classifier die zinnen categoriseert is oké, zolang Nova zelf beslist wat ze doet
- **confidence-schaal:** user = 1.0 / auto_extract = 0.9 / wikipedia = 0.8 / auto = 0.1
- **EventBus-patroon:** élke module communiceert via publish/subscribe, nooit direct
- **Actief spel:** IntentRouter houdt een `active_game` variabele bij — losse spelcommando's ("bord", "statistieken") gaan naar het actieve spel; expliciet spel vermelden ("schaak bord") overschrijft dit tijdelijk zonder `active_game` te wijzigen
- **Vast recept bij nieuwe modules/intents (sinds 7 juli 2026):** elke nieuwe `detect_*`-methode in `intent_router.py` die een intent herkent, moet ook `self._emit_topic("<naam>")` aanroepen vlak voor haar `return True` in de `route()`-methode. Zonder deze stap telt Layer 2 (`pattern_matcher.py`) dat onderwerp gewoon niet mee — er verschijnt dan geen foutmelding, het patroon blijft stilzwijgend onbestaand. Dit is dus een vaste, terugkerende stap bij élke nieuwe module (Plex, dammen, Go, activity-awareness, ...), geen eenmalige toevoeging.
- **24/7 daemon** — Nova stopt nooit vanzelf, enkel via /reboot of manueel
- **Autonomie-principe** — Nova suggereert altijd eerst, handelt pas na bevestiging van Kevin

---

## 📊 Grote visie

- **498+ geplande modules** (nova_modules_overview.md beschikbaar)
- **7-laags learning brain** (volledig uitgewerkt in roadmaps)
- **Neuro-symbolisch toekomstpad** (Jaar 3-5): kleine gespecialiseerde neural models als extra sensoren (vision, audio, anomaly detection)
- **Avatar / desktop companion** (Jaar 3-4): bewegende avatar op scherm, real-time emotie-animaties, lipsync
- **Bordspellen** (Jaar 2-3): dammen + Go naast schaak, langzame partijen over weken/maanden
- **Anatomisch lichaamsschema** (ver toekomst)
- **Robotica-integratie** (ver toekomst)
- **Emergent behavior** — Layer 7 (ver toekomst)
