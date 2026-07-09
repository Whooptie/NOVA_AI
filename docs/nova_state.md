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
│   ├── reboot_manager.py
│   ├── semantic.py
│   └── response_engine.py
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
│   ├── knowledge/
│   │   └── wikipedia_teacher.py
│   └── learning/
│       ├── word_associations_learner.py
│       └── pattern_matcher.py
├── identity/
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
│   └── patterns_layer2.json
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
| semantic.py | ✅ VOLLEDIG KLAAR | Alle 7 fases klaar. Reasoning Layer actief (chaining, inference, contradiction detection). Auto-extract is_a. Wikipedia fallback geïntegreerd. Nieuw:`teach_example` event → eigen voorbeeldzinnen toevoegen via `example <woord> <zin>`. |
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
| chat_response_engine.p | ✅ Klaar | Doorsturen van pipeline_response naar expression_inject |
| expression_injector.py | ✅ Klaar | Emoji, gesture, puberal flair injectie |
| help.py | ✅ Klaar | Help-systeem met topic-bestanden. `help` = algemeen overzicht, `help schaken` = schaakcommando's incl. huidig niveau en denktijd. `algemeen.py` bijgewerkt (3 juli 2026) met `example`-commando en reasoning-sectie. |
| wikipedia_teacher.py | ✅ Klaar | Nederlandse Wikipedia API, disambiguatie-afhandeling, is_a relatie-extractie, automatische fallback vanuit chat.py. Definitie-limiet opgetrokken naar 400 tekens, kapt nooit meer af midden in een woord. Automatische voorbeeldzin-extractie uit Wikipedia geprobeerd maar werkt nog niet betrouwbaar — vervangen door handmatig `example`-commando (zie semantic.py). |
| chess_engine.p | ✅ Klaar | Stockfish (UCI), persistente partijstand (chess_game.json), lazy engine-start, netjes afgesloten bij exit. Natuurlijke taal voor zetten. Bordweergave met schaaksymbolen (wit/magenta). Instelbare moeilijkheidsgraad (0-20) + denktijd, beide persistent (chess_settings.json). Win/verlies statistieken (chess_stats.json). Auto-shutdown Stockfish na 30 min inactiviteit. |
| word_associations_learner.py | ✅ Klaar (Layer 1, alle 5 fases) | PMI-gebaseerd associatienetwerk (data/word_associations.json). Leert van "chat_message"/"chat_response"-events (niet het gecombineerde formaat uit de originele roadmap). Publiceert `word_association:updated`; sinds Layer 4 (8 juli 2026) wordt `find_related()` ook actief gebruikt in Nova's antwoorden. |
| pattern_matcher.py | ✅ Klaar (Layer 2, alle 5 fases) | Detecteert timing-patronen (uur/dag) voor chat_message/chat_response. Anomaly-drempels en opslagfrequentie staan nog op tijdelijke testwaarden (zie Layer 2-sectie). |
| microlearning.py | ❌ Leeg | Bestand bestaat maar is volledig leeg — nog te bouwen |

### IDENTITY

| Module | Status | Opmerkingen |
| --- | --- | --- |
| loader.py | ✅ Klaar | Laadt + valideert identity.json tegen schema.json |
| identity.json | ✅ Klaar | Volledig persoonlijkheidsprofiel |
| schema.json | ✅ Klaar | JSON Schema validatie |
| personality_engine.py | ✅ Klaar | Traits + state + behavior modifier |
| behavior_modifiers.py | ✅ Klaar | Energie, impulsiviteit, dramatic flair |
| traits.json | ✅ Klaar | Numerieke persoonlijkheidswaarden (0.0–1.0) |
| identity_state.json | ✅ Klaar | **overstimulation.level staat standaard op 1.0 (max) — fix nodig. Bevestigd tijdens Layer 4-testen (8 juli 2026): elk antwoord kreeg hierdoor het "overprikkeld_chaotisch_snel"-sjabloon, ongeacht onderwerp. Vermoedelijk ontbreekt een decay/recovery-mechanisme in emotion_engine.py — hoort bij Layer 6, zie Layer 4-sectie.** |
| emotion_engine.py | ✅ Klaar | Trigger-gebaseerde emotie-updates |
| emotion_state.json | ✅ Klaar | Huidige emotionele staat |
| emotion_rules.json | ✅ Klaar | Regels voor mood-shifts, sync, dramatic flair |
| tone_engine.py | ✅ Klaar | Mood → tone → style profile |
| style_profiles.json | ✅ Klaar | 8 stijlprofielen (emoji, gesture, pitch, volume...) |
| gesture_profiles.json | ✅ Klaar | 7 gebarenprofielen voor toekomstige avatar |

---

## 🐛 Bekende bugs (prioriteit)

| # | Bug | Bestand | Urgentie | Status |
| --- | --- | --- | --- | --- |
| 1 | OpenWeatherMap API-key hardcoded én gelekt in chat. | weather.py | 🔴 DIRECT | ✅ Opgelost (2 juli 2026 — key naar .env, python-dotenv) |
| 1b | Stad-extractie pakte leestekens mee (bv. "gent?" i.p.v. "gent") | weather.py | 🟢 Laag | ✅ Opgelost (2 juli 2026 — strip(".,!?;:") toegevoegd) |
| 1c | Weer-intent werd niet herkend bij korte zinnen ("weer in Gent?") | intent_router.py | 🟡 Medium | ✅ Opgelost (2 juli 2026 — losse woord-detectie i.p.v. vaste triggerzinnen) |
| 1d | Weekdagnaam kwam in het Engels terug ("Monday" i.p.v. "maandag") | weather.py | 🟢 Laag | ✅ Opgelost (3 juli 2026 — eigen NL-weekdaglijst i.p.v. strftime %A) |
| 2 | Windows-pad hardcoded in save_path | memory.py | 🟡 Medium | ✅ Opgelost (2 juli 2026 — portable pad via Path(**file**), werkt op elke PC/gebruiker) |
| 3 | Dode code (uitgecommentarieerde handlers) | chat.p | 🟢 Laag | 🔲 Open |
| 4 | overstimulation.level = 1.0 als standaard | emotion_state.json | 🟢 Laag | 🔲 Open — zie uitgebreide beschrijving bij bug #11 |
| 5 | Personality/tone pipeline bypassed door weer/tijd/math/definities | response_pipeline.py | 🟡 Medium | 🔲 Open |
| 6 | Punt aan einde van woord wordt meegenomen bij wiki-aanroep | chat.p | 🟢 Laag | 🔲 Open |
| 7 | Oude concepts.json entries hebben geen auto_extract relaties | concepts.json | 🟢 Laag | 🔲 Open |
| 8 | Automatische voorbeeldzin-extractie uit Wikipedia werkt niet (examples blijft leeg) | wikipedia_teacher.py | 🟢 Laag | 🔲 Open — omzeild met handmatig `example`-commando |
| 9 | Woordsoort-detectie (`detect_pos`) kan werkwoord/zelfstandig-naamwoord-dubbelzinnigheid niet oplossen zonder zinscontext (bv. "gebruik" als werkwoord vs. zelfstandig naamwoord) | semantic.py | 🟢 Laag | ✅ Omzeild (8 juli 2026 — expliciete stopwoordenlijst in response_pipeline.py, geen structurele fix) |
| 10 | Layer 1 (`word_associations_learner.py`) houdt geen rekening met senses: bij een meerduidig woord (bv. "python" = zowel de slang als de programmeertaal) worden alle co-occurrences door elkaar geteld, ongeacht welke betekenis bedoeld was in de zin. Ontdekt tijdens Layer 4-testen (8 juli 2026): `response_engine.py` toonde de definitie van "python" als slang, aangevuld met de associatie "snel" — die associatie komt vermoedelijk uit gesprekken over de programmeertaal, niet het dier. Layer 1 werkt puur op tekst-co-occurrence en heeft geen besef van `semantic.py`'s sense-systeem (`get_senses()`). Geen bug in `response_engine.py` zelf — die geeft gewoon correct door wat Layer 1 teruggeeft. Live opnieuw bevestigd (8 juli 2026) met "hond" (2 senses) en "hart" (5 senses) in Kevin's echte `concepts.json`. | word_associations_learner.py | 🟢 Laag | 🔲 Open — wacht op disambiguatie-laag (`user_preferences.py`), zie Layer 4-sectie |
| 11 | Nova's `emotion_state.json` staat structureel op een hoge `overstimulation.level` (waargenomen tijdens Layer 4-tests, 8 juli 2026) — elk antwoord, ongeacht onderwerp, kreeg het "overprikkeld_chaotisch_snel"-sjabloon (😵⚡💥) van `tone_engine.py`. Vermoedelijke oorzaak: er lijkt geen decay/recovery-mechanisme te zijn dat `overstimulation.level` geleidelijk laat zakken over tijd — enkel triggers die het verhogen zijn gezien in `emotion_engine.py`. Dit is GEEN bug in Layer 4 (`response_engine.py`/`response_pipeline.py`) — die geven correct door wat de emotion/tone-engines op dat moment aanleveren. Vermoedelijk hoort dit thuis bij Layer 6 (personality/emotion-regulatie), niet bij Layer 4. Nog niet onderzocht/opgelost — apart op te pakken wanneer Layer 6 aan de beurt is. | emotion_engine.py / Layer 6 | 🟡 Medium | 🔲 Open |

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
| Layer 5 | context_manager.py | ❌ Nog te bouwen | memory_layer5_roadmap.md |
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

| Fase | Omschrijving | Status |
| --- | --- | --- |
| 1 | Event grouping (per uur, per dag, per event_type) | ✅ |
| 2 | Pattern detection (most_common_hour, confidence, day_frequency) | ✅ |
| 3 | Anomaly detection (ongewone timing + gemiste events via achtergrondtimer) | ✅ |
| 4 | Query & predictie (is_pattern_active, predict_next_occurrence, get_anomalies) | ✅ |
| 5 | Integratie (pattern:detected event, opslaan + herladen bij opstarten) | ✅ |

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
| 6 | Bug #10 aanpakken (associatie enkel tonen bij juiste sense) | 🔲 Uitgesteld tot disambiguatie-laag (zie User Preferences-sectie) |
| 7 | Tone/personality via bestaande tone-keten (`response_pipeline.py`/`chat_response_engine.py`/`expression_injector.py`) | ✅ |
| — | Layer 2 écht gekoppeld aan `generate()` via `_voeg_timing_hint_toe()` (was aanvankelijk vergeten — Layer 2 bleef los na Fase 3) | ✅ |

**Architectuurkeuzes:**

- **Optie A gekozen** voor de integratie: Layer 4 vervangt `chat.py`'s `on_definition()` als hoofdroute voor definitievragen. `intent_router.py` probeert eerst `response_engine.generate()`; alleen bij confidence ≤ 0.2 valt het terug op de oude route via `chat.py`, die zijn automatische Wikipedia-fallback behoudt (bewust niet overgebouwd naar `response_engine.py` — voorkomt duplicatie, elke module blijft verantwoordelijk voor zijn eigen taak).
- **Tone-integratie (Fase 7):** `intent_router.py` en `chat.py`'s vangnet publiceren `layer4_response` i.p.v. rechtstreeks `chat_response`. `response_pipeline.py` kreeg een nieuwe listener `on_layer4_response()` (zelfde patroon als `on_greeting()`/`on_fallback()`) die de AL KLARE Layer 4-tekst door de bestaande tone-keten stuurt — verzint geen nieuwe tekst, voegt enkel Nova's stemming (emoji's, uitroeptekens) toe.
- **Layer 2-koppeling gebruikt het GENERIEKE topic `"definitie"`** (hetzelfde topic dat élke definitievraag al triggert via `_emit_topic("definitie")`), niet per-woord-timing — Layer 2 houdt geen per-woord-patronen bij, dus een eerlijke "je stelt hier over het algemeen rond dit tijdstip definitievragen"-hint, geen "je vraagt vooral 's avonds naar python" (zou doen alsof Layer 2 iets weet dat het niet weet). Timing-hint wordt toegevoegd na elk succesvol antwoord, bewust NIET bij "onbekend".
- **Caching en feedback-loop (`response_engine.feedback()`) bewust NIET gebouwd**, ondanks dat de originele roadmap ze voorzag: caching zou conflicteren met Fase 5's willekeurige variant-keuze en de tijdsgevoelige Layer 2-koppeling (een gecached antwoord kan verouderd/inconsistent worden); feedback-loop vereist actieve bevestiging van Kevin en hoort inhoudelijk thuis bij de toekomstige `user_preferences.py`-module (zie hieronder), niet als losse toevoeging aan Layer 4.

**Bekend, genoteerd voor later:**

- **Bug #10:** meerduidige woorden (bv. "hond" met 2 senses, "python" met 2 senses, "hart" met 5 senses in `concepts.json`) — `semantic.get_best_definition()` kiest de sense met hoogste confidence, niet noodzakelijk de bedoelde. Live bevestigd tijdens testen (8 juli 2026): "hond" gaf soms de korte definitie ("een dier") i.p.v. de volledige biologische definitie. Wachten op disambiguatie-laag.
- **Per-woord-timing:** mogelijke toekomstige uitbreiding — zou vereisen dat `intent_router.py` een woord-specifieke topic-naam doorgeeft aan `_emit_topic()` i.p.v. het vaste `"definitie"`. `response_engine.py` zelf zou dan ONGEWIJZIGD blijven. Raakt ook Kevin's activiteit-suggestie-idee (bv. koffie voorstellen tijdens het coderen) — dat hoort echter bij `activity_awareness_roadmap.md`, niet bij Layer 4.
- **Emotion/overstimulation-observatie:** tijdens Layer 4-testen viel op dat Nova's `emotion_state.json` structureel op een hoge `overstimulation.level` staat, waardoor elk antwoord het "overprikkeld_chaotisch_snel"-sjabloon (😵⚡💥) kreeg, ongeacht onderwerp. Geen Layer 4-bug — vermoedelijk ontbreekt een decay/recovery-mechanisme in `emotion_engine.py`. Hoort bij Layer 6, niet bij Layer 4.

**Getest:** los (`test_response_engine.py` tegen echte `concepts.json`), end-to-end binnen de echte Nova (6 representatieve concepten: hond, appel, python, democratie, zwart gat, blablabla), en de volledige tone-keten inclusief live emoji/stemmings-integratie.

## 🔄 Semantic — Status & Roadmap

### Fases 1-7 (VOLLEDIG KLAAR ✅)

|Fase|Omschrijving|Status|
|---|---|---|
|1|Datastructuur & opslag|✅|
|2|Teach & Auto-Lear|✅|
|3|Relation Engine|✅|
|4|Query Engine|✅|
|5|Integratie (intent_router, chat, pipeline)|✅|
|6|Wikipedia-module|✅|
|7|Reasoning Layer (chaining, inference)|✅|

### Fases 8-13 (Toekomst — semantic_extension_roadmap.md)

| Fase | Omschrijving | Type | Statu |
| --- | --- | --- | --- |
| 8 | Causal Reasoning | Pure symbolisch | ❌ Toekomst |
| 9 | Temporal Semantics | Pure symbolisch | ❌ Toekomst |
| 10 | Uncertainty Tracking | Pure symbolisch | ❌ Toekomst |
| 11 | Knowledge Extraction (spaCy) | M | ❌ Toekomst |
| 12 | Semantic Similarity (embeddings) | M | ❌ Toekomst |
| 13 | Graph Visualization (Plotly) | M | ❌ Toekomst |

**concepts.json:** gevuld met testdata (hond, dier, appel, pitvrucht, vliegtuig, democratie...) — productiedata, niet wissen.

---

## ♟️ Games — Status & Roadmap

| Spel | Modul | Statu | Engine |
| --- | --- | --- | --- |
| Schaa | chess_engine.py | ✅ Klaar | Stockfish (symbolisch) |
| Damme | checkers_engine.py | ❌ Toekomst | Symbolic engine |
| Go | go_engine.py | ❌ Toekomst | KataGo (neural, bounded) |
| Meerdere bordspellen (dammen, Go, ...) | active_game systeem | ❌ Toekomst | via IntentRouter |

**Geplande features:**

- Langzame partijen over weken/maanden
- GUI bord + chat sidebar (tegelijk praten en spelen)
- Commentary per zet ("Interessante zet!")
- Leren van Kevin's spelstijl via Layer 2 (pattern_matcher)

---

## 🔁 Reboot & Hot Reload

| Feature | Status | Roadmap |
| --- | --- | --- |
| /reboot commando (full restart, ~5 sec) | ✅ Klaar en volledig getest | reboot_hotreload_roadmap.md |
| /reload module (manual hot reload) | ❌ Later | reboot_hotreload_roadmap.md |
| Auto file watcher (Ctrl+S → reload) | ❌ Veel later | reboot_hotreload_roadmap.md |

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

| Fase | Omschrijving | Status |
| --- | --- | --- |
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
| --- | --- | --- |
| 1 | Foundation Fix (paden, retry, log rotation) | ✅ |
| 2 | SQLite + Daemon Basis (WAL, write buffer, graceful shutdown) | ✅ |
| 3 | Query API (search, query, get_stats, find_similar) | ✅ |
| 4 | Achtergrond-onderhoud timer, layer-integratie | ✅ Getest (archiveren, comprimeren, VACUUM, event publishing) |
| 5 | Optimization & polish (query caching, memory leaks, concurrent access, backup, health check) | 🟢 Later — pas nodig bij grote databank/veel gelijktijdige toegang |

Volledig beschreven in: **memory_24-7_daemon_addendum.md**

---

## 🚀 Volgende stappen (in volgorde van prioriteit)

1. 🟡 **Personality pipeline** — uitbreiden naar alle intents (momenteel enkel greeting/fallback/Layer 4-definitievragen)
2. 🟢 **microlearning.py** — bouwen (bestand bestaat, is leeg)
3. 🟢 **User preferences-module** — nog te plannen (memory_user_preferences_roadmap.md). Groeiend takenpakket: expliciete voorkeuren (ik hou van/haat X), disambiguatie-keuzes voor meerduidige woorden (zie bug #10, Layer 4-sectie), en mogelijk een feedback-loop voor Layer 4-antwoorden.
4. 🟢 **memory.py Fase 5** — optimalisatie/polish, enkel nodig bij grote databank of trage queries (geen haast)
5. 🟢 **Layer 2 opruimwerk** — anomaly-drempels (MIN_OBSERVATIES_VOOR_ANOMALIE, MIN_CONFIDENCE_VOOR_ANOMALIE) en opslagfrequentie (nu elke 2 observaties) staan nog op tijdelijke, verlaagde testwaarden — terugzetten naar realistischere waarden voor normaal gebruik. **Bekende bijwerking hiervan (7 juli 2026, geen bug, bestaand tijdelijk gedrag):** `save_to_disk()` wordt enkel aangeroepen als `total` van een event_type even is (`% 2 == 0`). Bij een oneven `total` (bv. na 1 of 3 observaties van een `topic_detected:*`-event) toont `patterns_layer2.json` op schijf dus tijdelijk een lager aantal dan wat `patronen <event_type>` live in het geheugen toont. Dit lost zichzelf op zodra deze opslagfrequentie later realistischer gemaakt wordt (zie hierboven), maar is voor nu iets om bij te houden tijdens testen: het JSON-bestand is niet altijd de meest actuele bron, het live geheugen wel.
6. 🟢 **Intent classifier (ML-specialist)** — concept, nog niet ingepland. Los van Layer 1-7, hangt enkel af van Layer 0-data. Volledig uitgewerkt in: intent_classifier_roadmap.md.
7. 🟢 **Activity Awareness (activiteiten herkennen, correleren, proactief reageren)** — concept uitgewerkt (6 juli 2026), nog niet ingepland. Kern: generiek `"ik ga <activiteit>"`-patroon in intent_router.py publiceert `activity_started`-events die Layer 2 al generiek meetelt; daarnaast co-occurrence tussen activiteiten (bv. koffie + coderen) en duur-detectie met drempelwaarde voor proactieve pauze-suggesties — beide pure statistiek/timer-logica, geen ML. Optioneel scherm-detectie (psutil, geen ML) en camera-detectie (vereist extern vision-model als sensor, met privacy-ontwerp vooraf). Ook: mogelijke uitbreiding naar per-woord-timing voor Layer 4 (zie Layer 4-sectie). Volledig uitgewerkt in: **activity_awareness_roadmap.md**.
8. 🟡 **emotion_engine.py decay/recovery-mechanisme** — `overstimulation.level` lijkt structureel hoog te blijven staan zonder ooit te dalen (zie identity_state.json-regel hierboven en Layer 4-sectie). Nog niet onderzocht — vermoedelijk hoort dit bij Layer 6.

---

## 📚 Roadmap documenten (in project)

| Document | Beschrijft |
| --- | --- |
| Nova_Roadmap.md | Overkoepelende/algemene roadmap van het project |
| memory_layer0_roadmap.md | Layer 0: memory.py v2.0 (SQLite, tiering, query API) |
| memory_24-7_daemon_addendum.md | 24/7 daemon aanpassingen voor memory.py |
| memory_layer1_roadmap.md | Layer 1: Word Associations Learner (PMI scoring) |
| memory_layer2_roadmap.md | Layer 2: Pattern Matcher (gedragspatronen) |
| memory_layer4_roadmap.md | Layer 4: Response Generation Engine |
| memory_layer5_roadmap.md | Layer 5: Context Manager (interruption logic) |
| memory_layer7_roadmap.md | Layer 7: Emergence Engine (zelfbewustzijn) |
| semantic_roadmap.md | Semantic Fases 1-7 (KLAAR — referentie bewaren) |
| semantic_extension_roadmap.md | Semantic Fases 8-13 (toekomstige uitbreidingen) |
| semantic_architecture.md | Architectuurdocument semantic.py: engines (ConceptStore, SenseEngine, RelationEngine, TeachEngine, RelationParser, RelationFlowEngine) en hoe ze samenwerken |
| semantic_api.md | API-referentie voor semantic.py (beschikbare functies/aanroepen) |
| semantic_teachengine.md | Detail-documentatie van de TeachEngine binnen semantic.py |
| reboot_hotreload_roadmap.md | Reboot + Hot Reload (3 fases) |
| memory_user_preferences_roadmap.md | User Preferences: wat Nova over Kevin onthoudt (voorkeuren/afkeuren) |
| topic_events_roadmap.md | `topic_detected`-events: hoe Layer 2 specifieke onderwerpen (schaak, Plex, ...) op tijdstip leert koppelen, en hoe Layer 4 dat later in vaste sjabloonzinnen gebruikt |
| identity_ROADMAP.md | Identity-opbouw in 6 fases: Blueprint → Personality Engine → Emotion Engine → Expression Engine → Integration Layer → Adaptive Learning (later) |
| math_roadmap.md | Roadmap voor math.py-uitbreidingen |
| intent_classifier_roadmap.md | ML-specialist naast intent_router.py: klein lokaal classificatiemodel (scikit-learn) dat nieuwe, onbekende zinnen naar een bekende intent-categorie voorspelt. Concept, nog niet ingepland in bouwvolgorde. |
| activity_awareness_roadmap.md | Activiteiten herkennen via intent/scherm/camera, co-occurrence tussen activiteiten, duur-detectie + proactieve pauze-suggestie. Concept, nog niet ingepland in bouwvolgorde. |
| ml_components_overview.md | Overzicht per laag (1/2/3/4) van mogelijke bounded ML-toevoegingen — referentiedocument, geen bouwvolgorde. Layer 3 (GNN voor concepts.json) is Kevin's belangrijkste "achterhoofd"-optie, grootste ingreep van de lijst. |

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
