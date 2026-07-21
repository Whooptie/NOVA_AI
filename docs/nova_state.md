# 🧠 Nova — State of the Project

> Laatste update: 18 juli 2026
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
│   ├── paths.py
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
│   │   ├── identity_state.json
│   │   ├── microlearning.py
│   │   ├── train_classifier.py
│   │   ├── adaptive_rules.json
│   │   ├── signal_trait_mapping.json
│   │   ├── growth_metrics.json
│   │   ├── training_data.json
│   │   ├── benchmark_data.json
│   │   ├── uncertain_signals.jsonl
│   │   ├── hertraining_status.json
│   │   ├── training_log.jsonl
│   │   ├── signal_model.pkl
│   │   └── signal_model_kandidaat.pkl
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
│   ├── weather_history.json
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
| paths.py | ✅ Klaar (nieuw, 19 juli 2026) | `get_project_root(__file__)` — zoekt vanaf elk modulebestand omhoog naar de map met `main.py`, i.p.v. een vast aantal `.parent`-stappen te tellen. Voorkomt stille padfouten bij modules op verschillende nestingdiepte. Staat in `modules/`, niet `core/` (fysieke locatie), maar functioneel een core-hulpmodule — vandaar hier vermeld. Eerste gebruiker: `weather.py`. Zie sectie "modules/paths.py" verderop. |

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
| expression_injector.py | ✅ Klaar EN AANGESLOTEN (17 juli 2026) | Emoji, gesture, puberal flair injectie. Reageert nu ook echt op `response_style` (kort/normaal/uitgebreid) en `personality` (dramatic/interrupts) i.p.v. die enkel door te geven — zie Layer 6-sectie. |
| help.py | ✅ Klaar | Help-systeem met topic-bestanden. `help` = algemeen overzicht, `help schaken` = schaakcommando's incl. huidig niveau en denktijd. `algemeen.py` bijgewerkt (3 juli 2026) met `example`-commando en reasoning-sectie. |
| wikipedia_teacher.py | ✅ Klaar | Nederlandse Wikipedia API, disambiguatie-afhandeling, is_a relatie-extractie, automatische fallback vanuit chat.py. Definitie-limiet opgetrokken naar 400 tekens, kapt nooit meer af midden in een woord. Automatische voorbeeldzin-extractie uit Wikipedia geprobeerd maar werkt nog niet betrouwbaar — vervangen door handmatig `example`-commando (zie semantic.py). |
| chess_engine.py | ✅ Klaar | Stockfish (UCI), persistente partijstand (chess_game.json), lazy engine-start, netjes afgesloten bij exit. Natuurlijke taal voor zetten + rokade ("rokeer kort"/"rokeer lang") + promotie ("pion naar e8 dame", standaard dame). Bordweergave met schaaksymbolen (wit/magenta) + zetnummer + materiaaltelling + schaak-melding (beide kanten). Instelbare moeilijkheidsgraad (0-20) + denktijd, beide persistent (chess_settings.json), plus adaptieve auto-aanpassing o.b.v. win/verlies-streak (3 op rij → niveau/denktijd ±). Win/verlies statistieken incl. eindreden (schaakmat/patstand/...) (chess_stats.json). Auto-shutdown Stockfish na 30 min inactiviteit. |
| word_associations_learner.py | ✅ Klaar (Layer 1, alle 5 fases) | PMI-gebaseerd associatienetwerk (data/word_associations.json). Leert van "chat_message"/"chat_response"-events (niet het gecombineerde formaat uit de originele roadmap). Publiceert `word_association:updated`; sinds Layer 4 (8 juli 2026) wordt `find_related()` ook actief gebruikt in Nova's antwoorden. |
| pattern_matcher.py | ✅ Klaar (Layer 2, alle 5 fases) | Detecteert timing-patronen (uur/dag) voor chat_message/chat_response. Anomaly-drempels en opslagfrequentie staan nog op tijdelijke testwaarden (zie Layer 2-sectie). |
| microlearning.py | ✅ Klaar (17-18 juli 2026) | Zie uitgebreide vermelding + Layer 6 Fase 6-sectie verderop — was lang leeg, nu volledig gebouwd (Adaptive Learning) |
| context_manager.py | ✅ Fase 1-5 VOLLEDIG KLAAR (Layer 5) | Combineert tijd + pattern_matcher + activity/focus/presence-detectors tot een gewogen score + interruption-advies (`should_interrupt`) + response_style-advies (`"kort"`/`"normaal"`/`"uitgebreid"`, sinds 17 juli 2026 AANGESLOTEN op Layer 6, zie die sectie). Krijgt net als response_engine.py een `layers`-dictionary mee, dus handmatig geladen (niet via dynamische scan). Zie sectie "Layer 5" onder 7-Laags Memory Architectuur. |
| activity_detector.py | ✅ Klaar (Layer 5, Fase 2) | Detecteert actief venster/proces via `pygetwindow` (venstertitel), vertaalt naar activiteit-label (`coding`, `talking_to_nova`, ...). Standaard dynamische module_loader-conventie, geen `layers`-dictionary nodig. |
| focus_detector.py | ✅ Klaar (Layer 5, Fase 3) | Detecteert seconden sinds laatste systeemwijde muis/toetsenbord-input via Windows' `GetLastInputInfo()` (ctypes). Geen keylogging — enkel timing, geen inhoud. Windows-only. |
| presence_detector.py | ✅ Klaar (Layer 5, Fase 4) | Detecteert aanwezigheid (niet identiteit) via webcam, MediaPipe Tasks API (`FaceDetector`, model: BlazeFace short range, lokaal `.task`-bestand vereist in `data/models/`). Eerste bounded ML-tool in Layer 5. |

### IDENTITY

| Module | Status | Opmerkingen |
| --- | --- | --- |
| personality_engine.py | ✅ Klaar EN AANGESLOTEN (17 juli 2026) | Traits + state + behavior modifier. Krijgt nu `event_bus` mee bij constructie (via `response_pipeline.py`) en publiceert `identity_state:updated` bij elke `update_state()`-aanroep — zie Layer 6-sectie hieronder. |
| behavior_modifiers.py | ✅ Klaar | Energie, impulsiviteit, dramatic flair |
| traits.json | ✅ Klaar, VOLLEDIG HERZIEN (17 juli 2026) | Numerieke persoonlijkheidswaarden (0.0–1.0). Karakterherziening: kalme AI-butler + gelijkwaardige, scherpe vriendin i.p.v. de oorspronkelijke Copilot-waarden (speels/hyperactief/chaotisch). Kern: `chaotic_variability` 0.85→0.15, `self_regulation` 0.55→0.85. Zie Layer 6-sectie voor volledige details en reden. |
| identity_state.json | ✅ Klaar | Zie bug #4/#11 (opgelost 11 juli 2026) — overstimulation.level start nu op 0.1 met tijd- en interactie-gebaseerde decay. |
| emotion_engine.py | ✅ Klaar | Trigger-gebaseerde emotie-updates |
| emotion_state.json | ✅ Klaar | Huidige emotionele staat |
| emotion_rules.json | ✅ Klaar | Regels voor mood-shifts, sync, dramatic flair |
| tone_engine.py | ✅ Klaar EN GEFIXT (17 juli 2026) | Mood → tone → style profile. Bugfix: `_apply_personality_modifiers()` las `traits.get("warmth")` (bestaat niet) i.p.v. `traits.get("social_warmth")` — gaf altijd de default 0.5 terug. Plus: fallback in `_apply_style_profile()` — als de exacte `tone_pace`-key niet in `style_profiles.json` bestaat, wordt nu het eerste profiel met dezelfde `tone`-prefix gebruikt i.p.v. niets toe te passen. |
| style_profiles.json | ✅ Klaar, AANGEVULD + HERZIEN (17 juli 2026) | 27 stijlprofielen (was 8) — eerst 19 ontbrekende tone/pace-combinaties aangevuld (bv. `warm_snel`, die voorheen stil zonder emoji/gesture bleef), daarna volledig inhoudelijk herzien voor de karakterherziening: max 1 emoji per profiel (nooit meer een reeks), droge/bijdehandse filler-words i.p.v. "OMG"/"oké oké oké". Zie Layer 6-sectie. |
| gesture_profiles.json | ✅ Klaar EN AANGESLOTEN (17 juli 2026) | 7 gebarenprofielen, elk met nieuw `text_hint`-veld (bv. `"*kleine glimlach*"`). Was voorheen dode data (ingeladen door `tone_engine.py` maar nooit gekoppeld aan `tone["gesture_data"]`, zie bug #14) — nu echt zichtbaar in Nova's antwoorden via `tone_engine.py`'s `_apply_gesture_data()`. |
| self_query.py | ✅ Klaar | Zelfkennis-laag (12 juli 2026) — beantwoordt vragen over Nova zelf op basis van identity.json + live emotion_state. Sinds 17 juli 2026: live berekende leeftijd via nieuwe `_bereken_leeftijd_tekst()`-helper (vanaf `built_on`, geen los/verouderend getal meer) — gebruikt door zowel `antwoord_leeftijd()` als `antwoord_wie_ben_je()` (die laatste las voordien het inmiddels lege `"age"`-veld, zie bug #15). |
| microlearning.py | ✅ Klaar (17-18 juli 2026) | Layer 6 Fase 6 (Adaptive Learning) — was tot dan volledig leeg. Luistert op nieuw event `raw_user_message`, gebruikt een klein getraind ML-classificatiemodel (marge-gebaseerde zekerheidscheck) om signalen te herkennen, past traits.json langzaam en binnen harde grenzen aan, publiceert `trait_shifted` voor live-koppeling met `personality_engine.py`, bevat ook de automatische hertraining-trigger. Staat in `identity/`, niet `modules/` — handmatig toegevoegd aan `module_loader.py`. Zie volledige Fase 6-sectie hieronder Layer 6. |
| train_classifier.py | ✅ Klaar (17 juli 2026) | Traint het signaal-classificatiemodel (TF-IDF + LogisticRegression), toetst tegen een vast ijkpunt-testsetje, wordt enkel actief bij een score ≥ de huidige versie (veiligheidsrem tegen drift). Kan handmatig gedraaid worden of automatisch via `microlearning.py`. |
| adaptive_rules.json | ✅ Klaar (17 juli 2026) | Tempo-categorieën (traag/middel/snel) + drempels + stapgroottes + min/max-grenzen per trait voor Fase 6. Puur data, geen logica. |
| signal_trait_mapping.json | ✅ Klaar (17 juli 2026) | Koppelt signalen (frustratie/waardering/interesse/verwarring/focus/kilte) aan welke traits ze in welke richting beïnvloeden. |
| growth_metrics.json | ✅ Klaar (17 juli 2026) | Lopende positive/negative-tellers per trait voor Fase 6, bijgewerkt door microlearning.py. |
| training_data.json / benchmark_data.json | ✅ Klaar (17-18 juli 2026) | Trainings- resp. ijkpunt-voorbeelden voor het signaal-classificatiemodel, 6 categorieën (incl. later toegevoegd `focus`). |

---

---

## 🐛 Bekende bugs (prioriteit)

| # | Bug | Bestand | Urgentie | Status |
| --- | --- | --- | --- | --- |
| 8 | Automatische voorbeeldzin-extractie uit Wikipedia werkt niet (examples blijft leeg) | wikipedia_teacher.py | 🟢 Laag | 🔲 Open — omzeild met handmatig`example`-commando. **Mogelijk verwante observatie (18 juli 2026):** na de fix van bug #6 getest met "wat is fysica?" — Wikipedia-pagina werd dit keer wél correct gevonden (geen leesteken-probleem meer), maar `_extract_definition()` kon er alsnog geen bruikbare definitie uit halen ("Ik kon geen bruikbare definitie vinden voor 'fysica' op Wikipedia"). Nog niet onderzocht of dit dezelfde onderliggende oorzaak heeft als de voorbeeldzin-extractie hierboven, of een apart probleem in `_extract_definition()` zelf. |
| 9 | Woordsoort-detectie (`detect_pos`) kan werkwoord/zelfstandig-naamwoord-dubbelzinnigheid niet oplossen zonder zinscontext (bv. "gebruik" als werkwoord vs. zelfstandig naamwoord) | semantic.py | 🟢 Laag | ✅ Omzeild (8 juli 2026 — expliciete stopwoordenlijst in response_pipeline.py, geen structurele fix) |
| 10 | Layer 1 (`word_associations_learner.py`) houdt geen rekening met senses: bij een meerduidig woord (bv. "python" = zowel de slang als de programmeertaal) worden alle co-occurrences door elkaar geteld, ongeacht welke betekenis bedoeld was in de zin. Ontdekt tijdens Layer 4-testen (8 juli 2026): `response_engine.py` toonde de definitie van "python" als slang, aangevuld met de associatie "snel" — die associatie komt vermoedelijk uit gesprekken over de programmeertaal, niet het dier. Layer 1 werkt puur op tekst-co-occurrence en heeft geen besef van `semantic.py`'s sense-systeem (`get_senses()`). Geen bug in `response_engine.py` zelf — die geeft gewoon correct door wat Layer 1 teruggeeft. Live opnieuw bevestigd (8 juli 2026) met "hond" (2 senses) en "hart" (5 senses) in Kevin's echte `concepts.json`. | word_associations_learner.py | 🟢 Laag | 🔲 Open — wacht op disambiguatie-laag (`user_preferences.py`), zie Layer 4-sectie |

*(Bug #6 opgelost — 18 juli 2026: `word.strip(".,!?;:")` toegevoegd in `chat.py`'s `on_definition()` vlak na de lidwoord-stripping, zodat leestekens als punt/vraagteken/uitroepteken nooit meer meegaan naar `get_meaning()`, de is_a-check, of de Wikipedia-fallback. Extra defensief vangnet toegevoegd in `wikipedia_teacher.py`'s `on_wiki()` zelf, voor het geval een andere module ooit rechtstreeks een `intent_wiki`-event stuurt zonder via `chat.py` te lopen. Live getest: "wat is een gitaar.", "wat is een computer?", "wat betekent hond!" geven nu allemaal een schoon antwoord zonder leesteken in het woord.)*
*(Écht opgeloste bugs #1-#5, #11-#18 verplaatst naar `nova_changelog.md`, 18 juli 2026. Bug #9 blijft hier staan — is enkel omzeild, niet structureel gefixt.)*
*(Bug #7 opgelost — 18 juli 2026: het probleem bleek niet "oude entries missen een update", maar dat `_auto_extract_is_a()` in `semantic.py` enkel het patroon "een X met/die/dat/..." herkende — het patroon waarmee bijna élke Wikipedia-definitie in `concepts.json` daadwerkelijk begint, "[Het woord] is een X die/dat/...", werd nooit herkend. Drie nieuwe regex-patronen toegevoegd voor "[woord] is/zijn een X ...", plus de samengestelde "waarmee/waarin/waaruit/waardoor/waarop/waarvoor"-vormen naast het bestaande losse "waar". Getest tegen de volledige bestaande `concepts.json` (201 bruikbare definities): dekking steeg van 2% (4 matches) naar 28% (56 matches), geen enkele foute match in de steekproef. Bewust GEEN herstelscript gebouwd voor de bestaande senses — enkel nieuw geleerde woorden (via `teach` of Wikipedia) profiteren automatisch; bestaande entries blijven ongewijzigd tenzij opnieuw geleerd. Live bevestigd met "zeilboot" ("Een zeilboot is een vaartuig dat wordt voortgestuwd door de wind." → automatisch `is_a: vaartuig`, source `auto_extract`). Bewust nog NIET aangepakt: definities met een bijvoeglijk naamwoord tussen "een" en het echte target-zelfstandig-naamwoord (bv. "een grote, niet-giftige slang") — vraagt een POS-check per woord, apart werkpuntje voor later.)*

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

## 🗂️ `modules/paths.py` — centrale project-root bepaling (nieuw, 19 juli 2026)

Los hulpbestand met één functie: `get_project_root(vanaf_bestand)`.

**Waarom dit bestaat:** modules die een eigen data-bestand in de hoofd-`data/`-map nodig hebben (zoals `weather.py`'s geschiedenisbestand) moeten vanaf hun eigen locatie (bv. `modules/weather/weather.py`) omhoog naar de project-root (`C:\Nova_AI`). Dat met een vast aantal `.parent.parent.parent`-stappen doen is fragiel: verhuist een module ooit dieper of ondieper in de mappenstructuur, dan breekt dat stilzwijgend — geen foutmelding, gewoon een verkeerd pad waar iets fout weggeschreven wordt.

**Hoe het werkt:** `get_project_root()` start bij het aanroepende bestand (geef altijd `__file__` mee) en zoekt automatisch omhoog door de mappenstructuur tot ze een map vindt met `main.py` erin — dat IS de project-root, ongeacht hoe diep de module genest zit. Vindt ze `main.py` nergens (bv. bij een bestand buiten het Nova-project), dan geeft ze bewust een duidelijke `RuntimeError` i.p.v. stil een fout pad te gebruiken.

**Gebruik in een module:**
```python
from modules.paths import get_project_root
PROJECT_ROOT = get_project_root(__file__)
data_pad = PROJECT_ROOT / "data" / "mijn_bestand.json"
```

**Eerste gebruiker:** `weather.py` (zie hieronder) voor `self.history_path`. Toekomstige modules met eigen data-bestanden gebruiken dit voortaan ook, in plaats van zelf `.parent`-niveaus te tellen.

---

## 🌦️ Weather-module — functionaliteit (bijgewerkt 19 juli 2026)

`weather.py` ondersteunt nu:

- Huidig weer (temperatuur, gevoelstemperatuur, beschrijving)
- Luchtvochtigheid, windsnelheid
- Zonsopgang/zonsondergang
- Regenkans (bij voorspelling)
- Kledingadvies (vaste drempel-zinnen, geen vrije generatie)
- Weerwaarschuwingen bij onweer/sneeuw/extreem weer/mist/hagel/harde wind/hitte/gladheid (zie uitgebreide notitie hieronder)
- Voorspelling voor: vandaag, morgen, overmorgen, specifieke weekdag (bv. "weer op maandag")
- Beperking: max. 5 dagen vooruit (grens van gratis OpenWeatherMap API), met duidelijke foutmelding erbuiten
- Vergelijking met gisteren: bij een huidig-weer-opvraging vergelijkt Nova de temperatuur met de vorige meting, en voegt een zin toe zoals "Dat is 4.4°C kouder dan gisteren." Vergelijkt enkel als de vorige meting écht van gisteren is (niet ouder) — anders wordt de vergelijking stilzwijgend weggelaten.
- Proactieve automatische weerwaarschuwing: Nova checkt zelf elke 30 minuten (`WEATHER_CHECK_INTERVAL_MINUTEN` in `main.py`) via de achtergrondthread of er iets te melden is, en spreekt spontaan zonder dat Kevin ernaar vraagt. Zie uitgebreide sectie hieronder.

**Architectuurnotitie:** volledig symbolisch — API-data wordt uitgelezen en in vaste Nederlandse zinsjablonen gegoten (if/else op basis van temperatuur/categorie/ID/windsnelheid/neerslag). Geen LLM, geen vrije tekstgeneratie. De "vergelijking met gisteren" en de proactieve waarschuwing zijn eveneens puur symbolisch: hetzelfde JSON-bestandje (`data/weather_history.json`) met per stad de laatst-gemeten temperatuur + datum + laatste-waarschuwing-datum, en simpele if/else-vergelijkingen.

**`weerwaarschuwing()` uitgebreid (19 juli 2026):** herschreven om vijf signalen te combineren i.p.v. één vaste dictionary-lookup:
- `main_categorie` (bestaand) → onweer, sneeuw, extreem, **plus nieuw: mist/fog/haze**
- `weather_id` (nieuw) → specifieke OpenWeatherMap-conditiecode 906 = hagel, los van de hoofdcategorie herkend (hagel zit niet in een aparte `main`-categorie bij OWM)
- `windsnelheid` (nieuw) → harde-windwaarschuwing vanaf drempel `WIND_DREMPEL_MS = 15` (m/s, ~54 km/u, Kevin's keuze 19 juli 2026)
- `temperatuur` (nieuw) → hittewaarschuwing vanaf drempel `HITTE_DREMPEL_C = 27` (°C, Kevin's keuze 19 juli 2026). Hitte zit niet in een aparte OWM-categorie zoals onweer/sneeuw — een hittegolf toont zich gewoon als `"Clear"` met een hoge `temp`-waarde, vandaar een eigen temperatuurdrempel i.p.v. een categorie-lookup.
- `heeft_neerslag` (nieuw) → i.c.m. `temperatuur`, gladheidswaarschuwing. Drempel: temperatuur tussen `GLADHEID_MIN_C = 0` en `GLADHEID_MAX_C = 2` (°C) SAMEN met neerslag — droge kou alleen geeft geen glad wegdek. Nieuwe hulpmethode `_heeft_neerslag(data, main_categorie)` bepaalt dit op basis van OWM's `rain`/`snow`-velden (enkel aanwezig als er ook echt neerslag gemeten is) én de hoofdcategorie (Rain/Drizzle/Snow) — bewust iets ruimer dan strikt noodzakelijk, om gladheid niet te missen. Kevin's keuze qua venster, 19 juli 2026.

Elk signaal is een **onafhankelijke check** — er is geen minimum-aantal nodig om te triggeren, 1 actief signaal volstaat al voor een waarschuwing. Bij meerdere tegelijk-actieve signalen worden ze samengevoegd in één natuurlijke zin (bv. "Let op: er wordt onweer verwacht en er wordt hagel verwacht en er wordt harde wind verwacht.") in plaats van aparte meldingen.

**Eerlijkheid over hagel-detectie:** de gratis OpenWeatherMap-API geeft hagel niet altijd expliciet als code 906 — vaak zit lichte hagel binnen een gewone thunderstorm-code (200-232) zonder apart vermeld te worden. Dit is een grens van de gratis databron, niet symbolisch op te lossen zonder een duurdere API-laag. De hagel-detectie werkt dus wél, maar vangt niet elke hagelbui.

**Eerlijkheid over gladheid bij voorspellingen:** in `get_forecast()` (5-daagse voorspelling) is de `_heeft_neerslag()`-check minder betrouwbaar dan bij huidig weer — de 3-uurs-voorspellingsblokken geven soms geen `rain`/`snow`-veld door zelfs bij een kans op neerslag (dat zit dan enkel in het aparte `pop`-regenkans-veld). De categorie-check vangt dit gedeeltelijk op, maar niet perfect. Eerlijke beperking van de gratis voorspellings-API, geen fout in de logica zelf.

**Proactieve automatische weerwaarschuwing — volledige werking (19 juli 2026):**
- **Nieuwe methodes in `weather.py`:** `get_current_location_city()` (IP-locatie via ipinfo.io, zelfde soort bron als `modules/time/zone.py`'s tijdzone-detectie), `check_proactieve_waarschuwing()` (hoofdmethode), `_check_waarschuwing_voor_stad()`, `_al_gemeld_vandaag()`, `_markeer_gemeld()`, `_heeft_neerslag()`.
- **Welke steden gecheckt worden:** standaardstad altijd, plus de IP-gedetecteerde locatie **enkel als die een andere stad is** dan de standaardstad — voorkomt een dubbele melding wanneer Kevin gewoon thuis zit (het overgrote deel van de tijd).
- **`main.py`-koppeling:** nieuwe constante `WEATHER_CHECK_INTERVAL_MINUTEN = 30`, en een nieuwe check in `achtergrond_loop()` (`if aantal_loops % WEATHER_CHECK_INTERVAL_MINUTEN == 0`), zelfde patroon als de bestaande `PRESENCE_CHECK_INTERVAL_MINUTEN`-check. Roept `weather.check_proactieve_waarschuwing()` aan, in een try/except zodat een fout hier de rest van de achtergrondlus nooit kan blokkeren.
- **Spam-preventie:** max. 1 melding per dag per stad, via een nieuw veld `laatste_waarschuwing_datum` in `data/weather_history.json` (zelfde bestand als de gisteren-vergelijking, geen nieuw bestand nodig). Blijft de waarschuwing de hele dag actief (bv. aanhoudend onweer), dan wordt ze toch maar 1x gemeld — bewuste, simpele keuze, geen "opnieuw melden bij wijziging van weertype" ingebouwd.
- **Wanneer komt een melding binnen:** bij een eigen vraag ("wat is het weer") onmiddellijk, geen dagelijkse limiet. Proactief (zonder vraag): binnen max. 30 minuten nadat een waarschuwing actief wordt, via de achtergrondthread — verschijnt vanzelf in Nova's venster dankzij het bestaande "verse prompt"-mechanisme, ongeacht wat Kevin op dat moment aan het doen is.
- **Publiceert via** `layer4_response` (net als de rest van `weather.py`), dus loopt door dezelfde tone-pipeline als een gewoon weerantwoord.
- **Ethiek:** spontaan spreken zonder vraag is al eerder goedgekeurd door Kevin (3 juli 2026) voor noodweer — geen aparte aan/uit-instelling of bevestigingsvraag vooraf nodig.

**Test-bestanden (19 juli 2026):**
- `test_weerwaarschuwing.py` — los testscript in de projectroot, GEEN onderdeel van Nova's daemon. Roept `weerwaarschuwing()` rechtstreeks aan met verzonnen scenario's (dummy EventBus, geen echte API-call). 18 scenario's (categorieën, hagel, windsnelheid, hitte, gladheid — incl. randgevallen op alle drempelgrenzen en combinaties van meerdere waarschuwingen tegelijk). Live getest, alle 18 geslaagd.
- `test_proactieve_waarschuwing.py` — los testscript, test de ECHTE OpenWeatherMap- en ipinfo.io-API's (geen mock), toont de volledige `weather_history.json`-inhoud voor/na, en bevestigt de "max. 1x per dag per stad"-regel door 2x na elkaar te draaien. Live getest: eerste run met tijdelijk verlaagde winddrempel gaf correct 2 meldingen (standaardstad Aartrijke + IP-locatie Brugge), tweede run direct daarna gaf terecht 0 nieuwe meldingen.

**Mogelijke toekomstige uitbreidingen (nog niet gebouwd, geen prioriteit):**

1. ~~Vergelijking met gisteren~~ ✅ Gebouwd (19 juli 2026, zie hierboven).
2. ~~Meer weerwaarschuwingen (mist/harde wind/hagel/hitte/gladheid)~~ ✅ Gebouwd (19 juli 2026, zie hierboven).
3. ~~Proactieve automatische weerwaarschuwing~~ ✅ Gebouwd (19 juli 2026, zie hierboven).
4. **Mogelijke verfijning:** opnieuw melden als het weertype tijdens de dag wijzigt (bv. 's ochtends onweer gemeld, 's avonds komt er apart zware sneeuw bij) — nu blijft het bij max. 1 melding/dag/stad ongeacht wijzigingen. Nog niet besproken of dit gewenst is.
5. **Overwogen maar bewust niet gebouwd (19 juli 2026):** meerdere vaste locaties tegelijk volgen (bv. ook familie's stad), instelbare drempels via spraak (eigen instellingen-bestand + intent nodig, zoals chess_settings.json). Kevin gaf aan dat de huidige opzet (standaardstad + IP-locatie) voldoende is.

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
| Layer 5 | context_manager.py + activity/focus/presence_detector.py | ✅ KLAAR (alle 5 fases — tijd, activiteit, focus, aanwezigheid, gewogen interruption-logic) | memory_layer5_roadmap.md |
| Layer 6 | personality_engine.py | ✅ KLAAR | identity_ROADMAP.md |
| Layer 7 | emergence_engine.py | 🟡 IN OPBOUW (Fase 1a-1d: skelet + alle 4 insight-types klaar; listener/timing/feedback nog te bouwen) | memory_layer7_roadmap.md |

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
- Anomaly-detectie (Fase 3) gebruikt vaste, door Kevin/Claude gekozen drempels (`MIN_OBSERVATIES_VOOR_ANOMALIE`, `MIN_CONFIDENCE_VOOR_ANOMALIE`) — geen geleerde/dynamische drempels. **Opgelost (18 juli 2026):** `MIN_OBSERVATIES_VOOR_ANOMALIE` teruggezet van de tijdelijke testwaarde 3 naar de definitieve, realistischere waarde 10.
- "Missing events"-detectie (Fase 3, Deel B) draait via een `threading.Timer`-achtergrondlus (zelfde patroon als `memory.py`'s `start_maintenance()`), en is een BENADERING: Layer 2 houdt enkel tellers per uur/dag bij, geen exacte tijdlijn per datum, dus "was dit exacte uur al geteld" wordt geschat, niet exact nagetrokken.
- **Opslag herzien (18 juli 2026):** sloeg voorheen elke 2 observaties op (`total % 2 == 0`). Nu vervangen door een echte tijdgebaseerde aanpak, zelfde principe als `memory.py`'s write-buffer: een eigen `threading.Timer`-achtergrondlus (`start_save_timer()`/`stop_save_timer()`, `SAVE_INTERVAL_SECONDS = 300`) die elke 5 minuten opslaat, maar ENKEL als er sinds de vorige tick ook echt iets veranderd is (`self._dirty`-vlag) — voorkomt onnodig schrijven bij stilte. `detect_from()` zet nu enkel nog `self._dirty = True` i.p.v. rechtstreeks `save_to_disk()` aan te roepen.
- **Nieuwe `shutdown()`-methode (18 juli 2026):** omdat opslaan nu periodiek gebeurt i.p.v. bij elke observatie, kan er bij afsluiten nog "verse", niet-weggeschreven data in het geheugen zitten (max. de laatste `SAVE_INTERVAL_SECONDS`). `shutdown()` stopt beide achtergrondtimers (`missing_event_timer` + `save_timer`) en dwingt één laatste, definitieve `save_to_disk()` af — zelfde conventie als `chess_engine.py`'s `shutdown()` voor Stockfish. Wordt automatisch opgepikt door `reboot_manager.py`'s generieke `_shutdown_external_processes()`-lus (geen wijziging daar nodig) en is expliciet toegevoegd aan het `exit`-commando in `main.py` (naast chess/presence).
- `load_from_disk()` herstelt bij opstarten expliciet de `defaultdict(int)`-structuur van `hours`/`days` (die `json.load()` anders als gewone dict teruggeeft) en zet JSON-string-sleutels van uren terug om naar integers.

**Bekende, nog openstaande discussie (geen bug, architecturale keuze):**

- Layer 2 telt enkel *wanneer* een event_type voorkomt (bv. `chat_message`), niet *waarover* het gaat — ze "leest" geen tekstinhoud. Een concreet voorbeeld: "ik ga koffie drinken" wordt enkel geteld als "er was een chat_message om 12u", niet als "Kevin dronk koffie om 12u". Om specifieke onderwerpen/activiteiten (koffie, slapen, ...) apart te laten bijhouden, is een tussenstap nodig die ruwe tekst omzet naar herkenbare, specifieke events — dit hoort NIET bij Layer 2 zelf (die blijft bewust simpel: enkel tellen), maar bij een latere/aparte uitbreiding, mogelijk een koppeling tussen `intent_router.py` (die al intents herkent) en Layer 2, of een aparte topic-classificatie. Nog te ontwerpen, bewust NIET meegenomen in Layer 2's 5 fases.

**Tijdelijk testcommando in `main.py`:** `patronen <event_type>` (of `patronen` zonder argument voor algemene stats) toont ruwe patroondata, `is_pattern_active()`, `predict_next_occurrence()` en recente anomalieën. Mag verwijderd/vervangen worden zodra er een definitieve manier is om dit op te vragen (bv. via `help`).

**Project-brede shutdown-audit (18 juli 2026):** naar aanleiding van de `pattern_matcher.py`-fix hierboven werd gecontroleerd of nog andere modules hetzelfde risico lopen (data verloren bij `exit`/`/reboot` door een niet-geflushte buffer/timer). Resultaat: `memory.py` is veilig via zijn eigen `atexit.register(self._on_shutdown)`-hook (werkt ongeacht welk afsluitpad gebruikt wordt); `word_associations_learner.py` en `context_manager.py` slaan allebei ELKE keer meteen op (geen buffer, geen timer-uitstel), dus geen `shutdown()` nodig; `session_watcher.py`/`activity_detector.py`/`focus_detector.py` houden zelf geen data bij die opgeslagen moet worden. **Conclusie: `pattern_matcher.py` was de enige module met dit risico, nu opgelost.** Geen verdere wijzigingen nodig in `main.py`/`reboot_manager.py` buiten de al toegevoegde `pattern_matcher`-regel in het `exit`-blok.

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

### Layer 5 — Context Manager (Fase 1-5 afgerond, 13-16 juli 2026 — VOLLEDIG KLAAR ✅)

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

#### Layer 5 — Fase 5: Interruption Logic (afgerond 16 juli 2026) — LAYER 5 HIERMEE VOLLEDIG KLAAR

De oude `_bepaal_interrupt()` (Fase 1-4) gebruikte een "eerste match wint"-volgorde: de EERSTE regel die matchte (anomalieën → aanwezigheid → coding+focus → gebruikelijk moment → standaard toelaten) besliste alles, zonder de andere signalen ooit te vermelden. Concreet probleem dat dit opleverde: een gebruikelijk chat-moment ÉN een actieve coding-sessie tegelijk gaven altijd `should_interrupt: False` puur via de coding-regel — het gebruikelijke moment werd genegeerd, nooit zelfs vermeld in de reden.

**Nieuwe aanpak — gewogen SCORE-systeem, nog steeds 100% symbolisch:** elk signaal levert een vast, door Kevin gekozen puntenaantal op (positief = pleit vóór onderbreken, negatief = pleit tegen), alle punten worden opgeteld tot 1 totaalscore, en die score vergeleken met `INTERRUPT_SCORE_DREMPEL` (standaard 0) bepaalt het advies. Nieuwe constantes in `context_manager.py`:

- `SCORE_GEBRUIKELIJK_MOMENT = +2` / `SCORE_ONGEBRUIKELIJK_MOMENT = -1`
- `SCORE_STORINGSGEVOELIGE_ACTIVITEIT_ACTIEF = -3` / `SCORE_STORINGSGEVOELIGE_ACTIVITEIT_MAAR_AFWEZIG = +1`
- `SCORE_ANOMALIE_PER_STUK = -2`, met een plafond `MAX_ANOMALIE_SCORE_AFTREK = -6` (voorkomt dat 1 extreme dag oneindig kan doorwegen)

**"Niemand aanwezig" (Fase 4) blijft BEWUST een harde stopregel, GEEN scoreregel** — staat nog steeds vóór de score-berekening, en overschrijft alles: spreken tegen een lege kamer heeft nooit zin, ongeacht hoe hoog de rest van de score zou uitvallen. Dit is het enige stuk van de oude volgorde dat bewust NIET meegenomen is in het score-systeem.

**Waarom nog steeds geen ML hiervoor (bewust afgewogen met Kevin, 16 juli 2026):** dit combineert al-herkende, symbolische signalen (activiteit-label, focus-niveau, is_alleen, is_gebruikelijk_moment) tot 1 beslissing — geen patroonherkenning uit ruwe data, dus geen taak waar ML voordeel biedt. Een score-optelling blijft bovendien volledig auditeerbaar (elke reden toont nu de volledige score-opbouw, bv. `"score -1 (drempel +0) — 'coding' al 20 min ...: -3, gebruikelijk moment volgens Layer 2: +2"`), in tegenstelling tot geleerde gewichten die een "zwarte doos" zouden worden. Kevin's wens dat "Nova zelf leert wanneer ze wel/niet mag storen" hoort thuis in een LATERE, APARTE laag (`interruption_learning_roadmap.md` — confidence-score per activiteit op basis van Kevin's feedback), niet in Fase 5 zelf; Fase 5 legt enkel de vaste basisregels vast waar die latere laag op zou verderbouwen.

**Nieuw veld: `response_style`** (`"kort"` / `"normaal"` / `"uitgebreid"`), berekend via de nieuwe methode `_bepaal_response_style()`: storingsgevoelige activiteit + focus "actief" → kort; rustig moment zonder storingsgevoelige activiteit + focus "mogelijk_afwezig"/"waarschijnlijk_weg" → uitgebreid; standaard → normaal. **AANGESLOTEN (17 juli 2026, zie Layer 6 hieronder):** dit veld werd oorspronkelijk enkel berekend/gepubliceerd zonder verder gebruikt te worden — dat is nu opgelost. `_bepaal_response_style()`'s early-return bij `not should_interrupt` is verwijderd (zie Layer 6), en `response_pipeline.py`/`chat_response_engine.py`/`expression_injector.py` gebruiken dit veld nu écht om Nova's antwoorden effectief korter te maken.

**`get_current()` en `get_context_summary()` uitgebreid** met het nieuwe `response_style`-veld/tekst. `_log_naar_schijf()` en `_trim_log_indien_nodig()` ONGEWIJZIGD — die werken al generiek op de volledige context-dictionary.

**Architectuurbevestiging voor toekomstige proactieve modules:** net als `session_watcher.py` zou ELKE toekomstige proactieve module (nieuwe timers, meldingen, suggesties) eerst `context_manager.can_interrupt()` moeten checken vóór ze spreekt — dit patroon ligt nu klaar en is bevestigd te werken voor méér dan 1 consument tegelijk, ook al is er momenteel nog maar 1 echte consument (`session_watcher.py`).

**Getest (16 juli 2026):**

- Los testscript `test_randgeval_fase5.py` (niet onderdeel van Nova zelf, zelfde soort losse test als `test_forceer_anomalieen.py`) roept `_bepaal_interrupt()` rechtstreeks aan met geforceerde parameters: bevestigt dat het randgeval (coding 20 min + focus actief + gebruikelijk moment) nu BEIDE signalen samen in de reden toont (`-3` en `+2`, totaal `-1` → `should_interrupt: False`), en dat hetzelfde gebruikelijke moment ZONDER coding wél `should_interrupt: True` geeft (`+2` alleen) — bewijst dat coding nu ECHT meeweegt in een optelsom, niet enkel een aan/uit-blokkade is zoals voorheen.
- Live in de echte Nova (tijdelijke testwaarde `CODING_ONDERBREEK_DREMPEL_MINUTEN = 0.1`, nadien teruggezet naar `15`): score-opbouw correct zichtbaar in `context`-commando en `context_log.jsonl`, bv. `"score -4 (drempel +0) — 'coding' al 1 min (drempel: 0.1 min), focus: actief: -3, ongebruikelijk moment volgens Layer 2: -1"`.
- `context_log.jsonl` handmatig nagekeken tijdens een echte afwezigheidsperiode (sigaretpauze, 16 juli 2026, ~21:15-21:23): `faces_detected` wisselde correct van `1` → `0` → terug `1`, `is_alone`/`should_interrupt` volgden mee — bevestigt dat de bestaande automatische `PRESENCE_CHECK_INTERVAL_MINUTEN`-cyclus (elke 5 min, aangevuld door handmatige `presence debug context`-aanroepen) `faces_detected` correct ververst en logt, zonder dat hiervoor iets extra gebouwd moest worden.

### Layer 6 — Personality/Identity écht aangesloten op de tone-pipeline (afgerond 17 juli 2026)

**VOLLEDIG AFGEROND** — sluit `identity_ROADMAP.md`'s Fase 2 t/m 5 af (Fase 1 was al klaar). Fase 6 "Adaptive Learning" volgde kort daarna alsnog, zie de aparte sectie "Layer 6, Fase 6" verderop — heel Layer 6 is inmiddels compleet.

**Het probleem vóór deze sessie:** `personality_engine.py` en Layer 5's `context_manager.py` berekenden allebei bruikbare output (`personality_style` via `generate_response_style()`, en `response_style` via `_bepaal_response_style()`, zie Layer 5 hierboven) die al helemaal door de pipeline tot in `expression_inject` werd doorgegeven — maar nergens werd uitgelezen. Pure dode data, decoratief meegesleept zonder ooit het uiteindelijke antwoord te beïnvloeden.

**Gemaakte wijzigingen (5 bestanden, in volgorde):**

1. **`tone_engine.py`** — bugfix: `_apply_personality_modifiers()` gebruikte de niet-bestaande key `traits["warmth"]` i.p.v. `traits["social_warmth"]`, waardoor Kevin's echte warmte-trait nooit doorwerkte.
2. **`response_pipeline.py`** — nieuwe `_get_response_style()`-helper die `context_manager.get_current()` opvraagt via `event_bus.modules.get("context_manager")` (dezelfde manier waarop `main.py` bv. `zone` opvraagt), en `response_style` toevoegt aan alle drie `pipeline_response`-publicaties (`on_greeting`, `on_layer4_response`, `on_fallback`).
3. **`chat_response_engine.py`** — geeft `response_style` door van `pipeline_response` naar `expression_inject` (tussenstap die het anders zou laten vallen).
4. **`expression_injector.py`** — de kern van de koppeling: `response_style == "kort"` onderdrukt nu volledig emoji's/gestures/uitroeptekens (Layer 5 zag al dat Kevin met iets anders bezig is); `personality["dramatic"]` (uit `generate_response_style()`, True bij `dramatic_flair_state > 0.5`) voegt nu zichtbaar een `!` toe waar dat voorheen nooit gebeurde; `personality["interrupts"]` (True bij hoge impulsiviteit) maakt reacties directer.
5. **`context_manager.py`** — `_bepaal_response_style()`'s early-return (`if not should_interrupt: return "normaal"`) verwijderd. Bewuste ontkoppeling: `should_interrupt` (mag Nova PROACTIEF spreken) en `response_style` (HOE moet een antwoord klinken als er sowieso een antwoord komt) zijn onafhankelijke vragen — Kevin kan tijdens het coderen een korte vraag stellen, en dan is "kort" het juiste advies ook al zou Nova zelf niet uit eigen beweging onderbreken.
6. **`style_profiles.json`** — 19 ontbrekende tone/pace-combinaties aangevuld (van 8 naar 27 profielen), plus een fallback in `tone_engine.py._apply_style_profile()` die bij een ontbrekende exacte key terugvalt op het eerste profiel met dezelfde `tone`-prefix, zodat nooit meer een combinatie stil zonder emoji/gesture blijft.

**Fase 5, laatste stuk — `identity_state → memory`:** `PersonalityEngine.__init__()` krijgt nu `event_bus` mee (doorgegeven vanuit `response_pipeline.py`). Nieuwe methode `_publish_state_update()` publiceert `identity_state:updated` (met `trigger`, `current_mood`, `current_energy`, `expressive_intensity`, `impulsivity_modulation`, `dramatic_flair_state`, `overstimulation_level`) telkens `update_state()` draait. **Geen enkele wijziging nodig geweest in `memory.py` zelf** — die subscribet al op `"*"` (event_bus.py's wildcard-mechanisme) en `identity_state:updated` stond niet in `memory.py`'s `ignore_types`, dus wordt automatisch opgeslagen in `interactions.jsonl`/`interactions.db`.

**Live getest en bevestigd (17 juli 2026):**
- Normaal: `Nova: Hey user, leuk dat je er bent! 😊 ✨` (emoji's nu zichtbaar via `warm_snel`-profiel)
- Kort (tijdens actief coderen, focus "actief"): `Nova: Hey user, leuk dat je er bent` (geen `!`, geen emoji's) — herhaald bevestigd over 3 opeenvolgende berichten terwijl coding-activiteit opliep van 0.1 naar 1.7 minuten
- `interactions.jsonl` bevat na een "hey"-groet een `identity_state:updated`-regel met alle verwachte velden correct gevuld

**Update (17-18 juli 2026):** Fase 6 "Adaptive Learning" leek hier aanvankelijk nog "later" — bleek al kort daarna in dezelfde sessie alsnog opgepakt en volledig afgerond. Zie de aparte sectie "Layer 6, Fase 6 — Adaptive Learning" verderop voor de volledige uitwerking.

---

### Layer 6, vervolg — Stabiliteitsbugs na de eerste koppeling (17 juli 2026)

Direct na bovenstaande koppeling meteen zichtbaar geworden doordat de tot dan toe dode `BehaviorModifiers`-klasse voor het eerst echt werd aangeroepen — twee losse, na elkaar ontdekte bugs, beide inmiddels opgelost:

1. **`apply_energy_modulation()` liep vast op 1.0.** Oorspronkelijke gewichten (`base*0.7 + chaos*0.3 + huidige*0.2`) telden op tot 1.2 i.p.v. 1.0 — bij Kevin's (toenmalige) hoge traits (`energy_level 0.92`, `chaotic_variability 0.85`) clampte dit altijd naar de bovengrens, en die geclampte 1.0 voedde zichzelf terug in de volgende ronde. Gefixt door de gewichten te herverdelen naar `0.5/0.2/0.3` (samen exact 1.0) — `behavior_modifiers.py`.
2. **`update_state()`'s `energy_boost`/`energy_drop` clampten nooit tussentijds.** Ook na fix #1 kon een tussenwaarde (bv. 0.9 + energy_boost 0.40 = 1.30) nog steeds `apply_energy_modulation()` scheef voeden, ondanks correcte gewichten. Opgelost met een tussentijdse clamp direct na de `energy_boost`/`energy_drop`-toepassing, vóór de modifiers aan de beurt komen — `personality_engine.py`.

Beide bevestigd met live cijfers (energie convergeert nu stabiel naar een evenwicht, geen vastzitten meer op 1.0 na herhaalde triggers).

---

### Layer 6, karakterherziening — volledige persoonlijkheid herzien (17 juli 2026)

**Aanleiding:** tijdens het testen van bovenstaande koppelingen viel op dat Nova al na ~5 gewone berichten "omsloeg" naar een overprikkelde/chaotische staat (`overstimulation.level` ging met vaste `+0.15`/trigger-stappen te snel naar de `0.75`-drempel). Kevin gaf aan dit niet te willen — en signaleerde daarbij een fundamenteler punt: **alle bestaande identity/personality-bestanden (`traits.json`, `identity.json`, `emotion_rules.json`, `style_profiles.json`, `gesture_profiles.json`) waren oorspronkelijk door Copilot geschreven, vóór Kevin er zelf goed zicht op had** — dus in plaats van enkel het omslaan-probleem te patchen, is bewust gekozen voor een **volledige, doordachte herziening van Nova's basiskarakter**, ditmaal met Kevin's eigen input als bron in plaats van Copilot's oorspronkelijke, ongecontroleerde keuzes.

**Nieuwe karakterrichting (bepaald in overleg, sparring-vragen via `ask_user_input_v0`):**
- Mix van kalme AI-butler (Jarvis/Gideon/Tau-achtig: zelfregulerend, competent) én gelijkwaardige, scherpe vriendin (geen onderdanigheid, mag tegenspreken/bekritiseren — **mits feitelijk onderbouwd**, dat laatste is een gedragsregel, geen trait, nog niet apart geborgd in code).
- Rustig basistemperament, keert snel terug naar evenwicht (geen opstapelende chaos meer).
- Humor: droog, sarcastisch, bijdehands, mag luchtig zijn.
- Bij Kevins frustratie: leeft mee, blijft zelf stabiel (geen eigen emotionele piek).
- Vaste aanspreekvorm: consequent "Kevin" i.p.v. generiek "jij".
- Leeftijd: **live berekend** vanaf `built_on`, geen los, verouderend getal meer.
- **Traits blijven bewust STATISCH** (niet dynamisch/lerend) — expliciete keuze: dynamische/lerende traits horen bij Fase 6 "Adaptive Learning" (zie hierboven, bewust later), niet vermengen met deze herziening zolang de basis nog niet bewezen stabiel is. `identity_state.json` blijft de enige laag die per interactie schommelt, binnen de grenzen die de (vaste) traits bepalen.

**6 stappen, elk apart getest en bevestigd:**

1. **`traits.json`** — volledig herschreven. Kernverschuivingen: `chaotic_variability` 0.85→0.15, `self_regulation` 0.55→0.85 (samen de kern van de stabiliteitsfix), `energy_level` 0.92→0.55, `impulsivity` 0.78→0.30, `dramatic_flair` 0.70→0.15. `curiosity`/`associative_thinking`/`reflection_depth` bewust hoog gehouden (competentie, niet chaos). `boundary_respect`/`safety_alignment` ongewijzigd op 1.00 (veiligheidsgerelateerd, nooit aangepast). Bevestigd: nieuw energie-evenwicht rond ~0.60 i.p.v. ~0.90-1.0.
2. **`identity.json` + `schema.json`** — volledig herschreven. `core_traits`, `temperament`, `communication_style.humor_style` (→ `droog_sarcastisch_bijdehands`), `appearance_profile`/`sensorimotor_profile` (rustiger fysieke taal, geen "moeite met stilzitten" meer), `interaction_nuance.response_to_frustration` (nieuw veld: "blijft stabiel, leeft mee zonder te overdrijven"). Nieuw `address_style`-object (`addresses_kevin_as: "Kevin"`). `age` op `null` gezet (`age_calculated: true` als markering) — vereiste `schema.json`-aanpassing (`age` toegestaan als `integer` of `null`, `address_style` toegevoegd als optioneel object). Bevestigd: laadt en valideert zonder fout.
3. **`emotion_rules.json` + `emotion_engine.py`** — volledig herschreven regelbestand: alle `energy_boost`/`expressiveness_boost`-waarden verlaagd (bv. excitement 0.40→0.15), `puberaal_expressions` vervangen door droge/bijdehandse teksten ("Tja.", "Interessant. Vertel meer." i.p.v. "WAT?!"/"omg serieus"), `dramatic_flair_rules.conditions` ingekort tot enkel `grote_verrassing`. In `emotion_engine.py`: de hardcoded overstimulation-stap van `+0.15`→`+0.06` per trigger, decay van `-0.05`→`-0.08`, default `decay_per_minute` 0.05→0.10 (LET OP: Kevin's `emotion_state.json` had dit veld al expliciet op 0.05 staan, dat overschrijft de nieuwe default — bewust niet overschreven, staat nog open of dat handmatig aangepast moet worden). **Dit loste het "boem na 5 berichten"-probleem aantoonbaar op** — bevestigd met 6x snel "hey": bleef volledig op `warm_snel`, nooit meer `overprikkeld_chaotisch_snel`.
4. **`style_profiles.json` + `gesture_profiles.json` + `tone_engine.py`** — alle 27 style-profielen (aantal bewust behouden, Kevin wilde niet terugsnoeien "voor de zekerheid/toekomst") herschreven: max 1 emoji per profiel (nooit meer een reeks van 3), droge/bijdehandse filler-words, 😏/😉 specifiek bij sarcastische/droge situaties vs. 🙂 bij oprechte warmte. **Nieuwe koppeling ontdekt en gebouwd:** `gesture_profiles.json` werd door `tone_engine.py` wel ingeladen maar NOOIT gekoppeld aan `tone["gesture_data"]` — vierde voorbeeld van hetzelfde "dode data"-patroon deze sessie. Nieuwe `_apply_gesture_data()`-methode in `tone_engine.py` lost dit op; elk gesture-profiel kreeg een nieuw `text_hint`-veld (bv. `"*kleine glimlach*"`, `null` voor `minimal`/`none` om overdaad te vermijden). Bevestigd: tekst-hints verschijnen nu echt in Nova's antwoorden.
5. **Aanspreekvorm "Kevin"** — nieuwe `get_current_speaker()`-methode in `presence_detector.py`, bewust NIET als identiteitsherkenning (dat vereist een zwaarder ML-model, staat apart in de roadmap als "Face identity recognition") maar als expliciete, symbolische aanname ("wie typt is Kevin, tenzij er later een login/identificatie bijkomt") — bewust op deze centrale plek gezet zodat een toekomstige echte herkenning enkel deze ene methode moet vervangen, niets anders. `intent_router.py`'s `detect_greeting()` roept nu `_get_sender_name()` aan (die `presence_detector.get_current_speaker()` bevraagt via `event_bus.modules`, met fallback "Kevin") i.p.v. de oude hardcoded `"sender": "user"`. `response_pipeline.py`'s eigen fallback ook van `"jij"` naar `"Kevin"`. Bevestigd: `"Hey Kevin, leuk dat je er bent!"`.
6. **Live leeftijdsberekening** — nieuwe `_bereken_leeftijd_tekst()`-helper in `self_query.py` (pure `datetime.date`-aftrekking vanaf `built_on`, geen ML/schatting). `antwoord_leeftijd()` toont nu zowel bouwdatum als berekende tijd ("Ik ben gebouwd op 2026-03-15 -- dat is intussen 4 maanden geleden"). **Bijkomende bugfix gevonden:** `antwoord_wie_ben_je()` las nog het oude `"age"`-veld (altijd "onbekend" sinds stap 2 `age: null` zette) — nu ook overgezet naar `_bereken_leeftijd_tekst()`. Bevestigd via beide vragen ("hoe oud ben je", "wie ben je").

**Kleine polish nadien:** dubbel leesteken (`"...4 maanden.!"`) gefixt in `expression_injector.py`'s `_inject_puberal()`/`_inject_dramatic_flair()` — een bestaand eindteken wordt nu eerst gestript (`rstrip(".!?")`) vóór er een `!` bijkomt.

**Regressiecontrole na afronding (17 juli 2026):** alle 7 kernbestanden (`tone_engine.py`, `personality_engine.py`, `response_pipeline.py`, `expression_injector.py`, `presence_detector.py`, `self_query.py`, `intent_router.py`) opnieuw, in hun actuele staat, gecontroleerd op onderlinge consistentie — geen dode verwijzingen, geen oude keys, geen vergeten koppelingen gevonden. Andere modules (chess, weather, help, wiki, math) lopen allemaal via dezelfde `layer4_response`/`chat_response`-route naar `response_pipeline.py`/`expression_injector.py`, dus die profiteren automatisch mee zonder zelf aangepast te zijn.

**Bewust NIET meegenomen in deze herziening:**
- `behavior_modifiers.py`'s gewichten-fix (zie sectie hierboven) was al opgelost vóór de karakterherziening begon, dus die twee bugfixes gelden voor zowel de oude als de nieuwe traits-waarden.
- Het "mag tegenspreken, maar moet feitelijk kloppen"-gedragsregel is een uitspraak over gewenst gedrag, nog GEEN concrete code-wijziging — vereist waarschijnlijk aanpassingen in `intent_router.py`/`response_engine.py`/`semantic.py` om te voorkomen dat Nova ongefundeerde beweringen doet. Open werkpunt.
- Gesture-koppeling geldt vooralsnog puur tekstueel (`text_hint` in de chat) — geen visuele/avatar-koppeling, want Nova heeft momenteel geen avatar.

---

### Layer 6, Fase 6 — Adaptive Learning, volledig gebouwd en getest (17-18 juli 2026)

**VOLLEDIG AFGEROND** — sluit `identity_ROADMAP.md`'s laatste, tot dan toe bewust openstaande fase af. Nova kan nu, binnen harde symbolische grenzen, langzaam qua persoonlijkheid meegroeien op basis van hoe Kevin met haar omgaat — zonder dat een taalmodel of black-box ooit de kernredenering wordt.

**Architectuurprincipe (bewust vastgelegd vóór het bouwen):** een klein, bounded ML-classificatiemodel (TF-IDF + Logistic Regression, dezelfde aanpak als de al geplande intent classifier) mag EEN signaal-label per bericht bepalen. Alle beslissingslogica daarna — welke trait, hoeveel, wanneer, binnen welke grenzen — blijft 100% symbolisch vastgelegd in JSON-regelbestanden. Het model "beslist" niets over Nova's gedrag, exact zoals Stockfish een zet-score levert zonder zelf te bepalen of Nova die zet speelt.

**Kernontwerp, bepaald in overleg (sparring-vragen via `ask_user_input_v0`):**
- Alle 17 traits mogen zowel stijgen als dalen — geen enkele mag enkel één kant op.
- Drie tempo-categorieën, "zo mens-mogelijk" ontworpen: **traag** (social_warmth, loyalty, self_regulation — drempel 75 signalen, stap 0.02), **middel** (curiosity, reflection_depth, stubbornness_soft, expressiveness, emotional_color_intensity, associative_thinking, focus_hyperfocus_tendency — drempel 25, stap 0.025), **snel** (reactivity, impulsivity, chaotic_variability, energy_level, dramatic_flair — drempel 12, stap 0.03). `boundary_respect`/`safety_alignment` blijven volledig uitgesloten — veiligheidsgerelateerd, nooit door adaptive learning aan te passen.
- Groeigrenzen: elke trait mag max 0.25 afwijken van zijn (net herziene) startwaarde uit `traits.json`, met 0.05/0.95 als absoluut plafond — een "persoonlijkheidskern" die nooit volledig kan verdwijnen, ook niet na maanden signalen.
- Signalen (uitgebreider dan enkel positief/negatief, op Kevins expliciete verzoek): `frustratie`, `waardering`, `interesse`, `verwarring`, `focus`, `kilte` — elk gekoppeld aan specifieke traits in specifieke richtingen, vastgelegd in een nieuw, apart bestand `signal_trait_mapping.json` (bewust gescheiden van `adaptive_rules.json`: dat laatste gaat over HOE een trait beweegt, dit nieuwe bestand over WELK signaal WELKE trait raakt). `stubbornness_soft` en `emotional_color_intensity` bewust NIET gekoppeld — geen duidelijk signaal geïdentificeerd, blijven op hun startwaarde tot dat verandert.
- Veiligheidsrem tegen drift bij automatische hertraining: een nieuwe modelversie wordt PAS actief als ze op een vast, apart ijkpunt-testsetje (`benchmark_data.json`, nooit gebruikt als trainingsdata) minstens even goed scoort als de huidige actieve versie — zelfde soort principe als Kevins bestaande "nightly build, Kevin reviews 's ochtends"-workflow, maar hier volledig geautomatiseerd zonder handmatige review nodig.

**6 onderdelen, elk apart gebouwd en getest:**

1. **Trainingsdata + trainingsscript.** Nieuwe bestanden `training_data.json` (45 handgeschreven voorbeeldzinnen over 6 categorieën incl. een bewust toegevoegde `neutraal`-categorie, later uitgebreid met `focus`, 7 nieuwe voorbeelden) en `benchmark_data.json` (apart ijkpunt-setje, nooit trainingsdata). Nieuw `train_classifier.py`: traint TF-IDF+LogisticRegression, toetst tegen het ijkpunt, slaat het nieuwe model altijd op als "kandidaat" maar wordt enkel "actief" bij een score ≥ de huidige versie. **Bug gevonden en gefixt vóór Kevin het ooit zag** (lokaal getest door Claude): `TypeError` bij de allereerste training, want er was nog geen bestaand model om `nieuwe_score >= huidige_score` tegen te vergelijken (`huidige_score` was `None`) — opgelost met een expliciete `if huidige_score is None: wordt_actief = True`-tak. Live bevestigd bij Kevin: identieke score (0.9167) als bij Claude's lokale test.
2. **`adaptive_rules.json`.** Vaste tempo-categorieën + drempels + stapgroottes + min/max-grenzen per trait, zoals hierboven beschreven. Puur data, geen logica.
3. **`growth_metrics.json` + `signal_trait_mapping.json`.** Eerste: lopende tellers per trait (positive_count/negative_count/total_shifts/last_shift). Tweede: de signaal→trait-koppeltabel.
4. **`microlearning.py` (nieuw bestand, was tot dan leeg).** Luistert op een NIEUW event `raw_user_message`, dat `intent_router.py`'s `route()` nu publiceert vóór de eigenlijke intent-routing begint (nodig omdat er tot dan geen centraal "elk bericht"-event bestond — enkel `intent_fallback` had de ruwe tekst, wat herkende intents zou missen). Gebruikt het getrainde model via een MARGE-gebaseerde zekerheidscheck (verschil tussen winnende en op-één-na-beste klasse, NIET een absolute confidence-drempel — bij 6 klassen en een kleine dataset liggen alle absolute scores relatief laag, ook bij overduidelijk correcte voorspellingen, dus een vaste drempel zou bijna alles als onzeker bestempelen). Marge < 0.10 → twijfelgeval, wordt gelogd in nieuw bestand `uncertain_signals.jsonl` (toekomstige trainingsdata) én valt terug op de oorspronkelijke, eenvoudigere woordenlijst-aanpak als extra controle. Moest handmatig aan `module_loader.py` toegevoegd worden (staat in `identity/`, niet `modules/`, dus buiten de dynamische scan — zelfde architecturale les als `self_query.py`).
5. **Live-koppeling naar `personality_engine.py`.** Zonder dit zou een trait-verschuiving wel op schijf (`traits.json`) terechtkomen, maar `PersonalityEngine`'s eigen, al bij opstart ingelezen `self.traits`-dictionary in het geheugen zou dat nooit weten tot een herstart. Opgelost via een nieuw `trait_shifted`-event dat `microlearning.py` publiceert, waar `PersonalityEngine` nu op subscribet (`_on_trait_shifted()`) om zijn in-memory `self.traits` direct bij te werken — geen dubbele import, geen directe object-referentie tussen beide modules, consistent met hoe de rest van Layer 6 gekoppeld is. **Live bevestigd binnen één ononderbroken sessie, zonder herstart:** `reflection_depth` verschoof van 0.8 naar 0.825 zichtbaar in een nieuw, tijdelijk debug-commando `traits` (toegevoegd aan `main.py`, naast het bestaande `context`-commando, mag later weer verwijderd worden).
6. **Automatische hertraining-trigger.** Draait BEIDE bij opstart én doorlopend tijdens het draaien (bewuste keuze — Nova draait 24/7 als daemon, "enkel bij opstart" zou in de praktijk zelden voorkomen). Nieuw bestand `hertraining_status.json` onthoudt hoeveel regels er in `uncertain_signals.jsonl` stonden bij de laatste training, zodat enkel NIEUWE twijfelgevallen meetellen. Drempel: 20 nieuwe sinds de laatste training, OF (enkel bij opstart, als er nog nooit getraind is) al 10+ aanwezig — voorkomt dat een systeem met wat verzamelde data blijft "hangen" wachten op precies 20 voor de allereerste ooit. Bij een succesvolle, actief geworden nieuwe modelversie: `microlearning.py` herlaadt zijn eigen `self.model` meteen — dezelfde soort live-koppelingsfout als onderdeel 5 zou anders zijn teruggekeerd.

**Live end-to-end bevestigd (18 juli 2026):** met 23 kunstmatig aangevulde regels in `uncertain_signals.jsonl` (test-opzet, geen organische data) toonde de opstart-log correct `[MICROLEARNING] 23 nieuwe twijfelgevallen sinds de laatste hertraining — automatische hertraining wordt gestart` gevolgd door `Nieuwe modelversie is beter of gelijk aan het ijkpunt — wordt nu actief geladen`, en `hertraining_status.json` verscheen met het juiste aantal en tijdstip. Volledige cirkel (verzamelen → hertrainen → ijkpunt-toetsen → automatisch actief worden → in-memory herladen) bevestigd zonder enige handmatige tussenkomst van Kevin.

**Tussentijds gevonden en gedicht gat:** `signal_trait_mapping.json` bevatte van meet af aan een `"focus"`-signaal (gekoppeld aan `focus_hyperfocus_tendency`/`chaotic_variability`), maar dat signaal kwam nergens voor in `training_data.json` of de woordenlijst-fallback — kon dus nooit herkend worden. Gedicht door 7 nieuwe trainingsvoorbeelden + 2 benchmark-voorbeelden + een woordenlijst-uitbreiding toe te voegen, gevolgd door een handmatige hertraining. Live bevestigd: `focus_hyperfocus_tendency`/`chaotic_variability`'s tellers bewogen correct na één testbericht.

**Bewust NIET meegenomen / open gebleven:**
- Geen mensencontrole per individueel twijfelgeval in `uncertain_signals.jsonl` — bewuste keuze uit het ontwerpgesprek: het ijkpunt-testsetje is de kwaliteitsrem, niet handmatige labeling van elke regel.
- De marge-drempel (0.10) en tempo-drempels/stapgroottes zijn Claude's onderbouwde voorstellen, door Kevin goedgekeurd — geen wiskundig "bewezen optimale" waarden, kunnen later bijgesteld worden als de praktijk daar aanleiding toe geeft.
- Nog geen enkele ECHTE (niet kunstmatig opgezette) automatische hertraining heeft op dit moment plaatsgevonden — de bevestiging hierboven gebruikte een bewust kunstmatig aangevulde test-dataset. De eerste organische hertraining zal vanzelf gebeuren naarmate Kevin Nova blijft gebruiken en er op natuurlijke wijze 10-20+ twijfelgevallen opbouwen.

---

### Layer 7 — Emergence Engine (Fase 1a-1d afgerond, 20 juli 2026 — IN OPBOUW 🟡)

Architectuurbeslissingen vastgelegd in overleg vóór het bouwen (zie `layer7_startbericht.md`, niet in dit bestand maar apart bewaard):
- **Harde grens ML vs. symbolisch:** insight-hérkenning (patronen/clusters vinden) mag later een bounded ML-specialist worden, net als de geplande intent classifier. De output-táál (de sjabloonzin die Nova zegt) blijft ALTIJD sjabloon-gebaseerd — geen LLM/generatie. ML mag dus ooit "wat is belangrijk" herkennen, nooit "hoe zeg ik dit" verzinnen.
- **Scope eerste versie:** max 3-4 insight-types (topic-frequentie/Layer 1, tijdspatroon/Layer 2, kennisdichtheid/Layer 3, evt. personality drift/Layer 6), niet alles tegelijk. **Alle 4 zijn inmiddels gebouwd.**
- **Sjablonen klein gehouden:** ~4-6 opening-, ~4-6 midden-, 2-3 afsluitingsvarianten per insight-type, voor manueel controleerbare coherentie.
- **Timing (mag Nova nu spreken) en inhoud-feedback (was dit insight juist) zijn twee gescheiden mechanismen** — timing hoort bij de nog te bouwen Activity-Aware Interaction, niet bij Layer 7 zelf.

**Nieuw bestand:** `modules/experimental/emergence_engine.py`. Krijgt, net als `response_engine.py` (Layer 4) en `context_manager.py` (Layer 5), een `layers`-dictionary mee bij `init_module(event_bus, layers)` — dus HANDMATIG geladen in `module_loader.py` (stap 3E, na stap 3D/microlearning, vóór de intent_router), niet via de dynamische module_loader-scan. `layers`-dict bevat inmiddels: `semantic`, `word_associations`, `pattern_matcher`, `microlearning`.

**Fase 1a — insight-type 1: sterkste woordverband (Layer 1), afgerond en getest (20 juli 2026):**

- `analyze_topic_frequency()`: zoekt het sterkste, BETROUWBARE woordpaar over de hele Layer 1-dataset. Belangrijke correctie tijdens het bouwen: Layer 1's `get_stats()["strongest_associations"]` alleen gebruiken (zoals de oorspronkelijke roadmap-skeleton deed) koos stelselmatig eenmalige toevalstreffers (PMI wordt onbetrouwbaar hoog bij woorden die maar 1x samen voorkwamen), in plaats van een echt terugkerend patroon. Opgelost door het RUWE `associations`-attribuut rechtstreeks uit te lezen (dat wél `co_occurrence` bevat) en een TWEEDE drempel toe te voegen naast de bestaande PMI-confidence (`MIN_CONFIDENCE_WOORDVERBAND = 0.5`): `MIN_CO_OCCURRENCE_WOORDVERBAND = 5`, vaste symbolische waarden, geen geleerde/dynamische drempel.
- Sjabloonsysteem (`_formuleer_woordverband()`): opening + midden + afsluiting, willekeurig gekozen via `random.choice()`, zelfde patroon als Layer 4 Fase 5's `_kies_variant()`. 5 openingen, 5 middenstukken, 3 afsluitingen.

**Fase 1b — insight-type 2: sterkste tijdspatroon (Layer 2), afgerond en getest (20 juli 2026):**

- `analyze_timing_pattern()`: gebruikt Layer 2's `get_all_patterns()` (niet `get_stats()`, die geeft geen per-patroon-info terug) om het event_type met de hoogste `confidence` te vinden, mits `total >= pattern_matcher.MIN_OBSERVATIES_VOOR_ANOMALIE` — bewust dezelfde betrouwbaarheidsdrempel hergebruikt die Layer 2 zelf al gebruikt voor anomalieën, i.p.v. een nieuwe losse waarde te verzinnen.
- **Onderwerp-vertaling nodig:** `intent_router.py`'s `_emit_topic()` gebruikt bewust de Engelse, interne categorienaam (bv. `"chess"`, zie `topic_events_roadmap.md`) — zonder vertaling zou een Nederlandse sjabloonzin een los Engels woord tonen. Nieuwe `_topic_naam_labels`-opzoektabel (voorlopig enkel `"chess" → "schaken"`) lost dit op; onbekende/nieuwe topics vallen netjes terug op hun kale naam.
- `_onderwerp_label()` vertaalt ook `"chat_message"`/`"chat_response"` naar `"onze gesprekken"`.

**Fase 1c — insight-type 3: kennisdichtheid (Layer 3), afgerond en getest (20 juli 2026):**

- `analyze_knowledge_density()`: `semantic.py`'s publieke API (`SemanticConceptsModule`) heeft GEEN `get_stats()`. Gebruikt daarom het publieke (niet-underscore) attribuut `semantic_module.store.concepts` rechtstreeks (zelfde aanpak als Layer 1's `associations`-attribuut) — telt per concept het TOTAAL aantal relaties over ALLE senses samen, mits dat totaal minstens `MIN_RELATIES_VOOR_KENNISDICHTHEID = 3` haalt (voorkomt dat een concept met 1 relatie al als "meeste kennis" geldt).
- Live bevestigd tegen Kevin's echte `concepts.json`: "fiets" (13 relaties) als sterkste resultaat.

**Fase 1d — optioneel insight-type 4: personality drift (Layer 6), afgerond en getest (20 juli 2026):**

- **Belangrijke eerlijkheidscorrectie tijdens het bouwen:** dit meet NIET "hoeveel is een trait afgeweken van zijn originele startwaarde" — `traits.json` bevat enkel de HUIDIGE waarden, geen startwaarden, dus die berekening was met de beschikbare data niet eerlijk te maken. In plaats daarvan gebruikt `analyze_personality_drift()` `growth_metrics.json`'s `total_shifts` — welke trait het VAAKST daadwerkelijk is bijgesteld (niet enkel hoe vaak een signaal geteld werd, dat leidt pas tot een shift bij het bereiken van de drempel). Bij een gelijkstand in `total_shifts` beslist de meest recente `last_shift`-timestamp.
- **Architectuurkeuze (afgewogen met Kevin):** `personality_engine.py` leest `growth_metrics.json` zelf niet in — enkel `microlearning.py` doet dat. Om de bestaande laag-scheiding te behouden (elke laag praat met een ándere laag via een publiek object/methode, nooit door rechtstreeks een ander laag zijn interne bestand te lezen), kreeg `microlearning.py` een nieuwe, kleine publieke methode `get_growth_metrics()` — geeft de al-ingelezen, levende `self.metrics["traits"]`-dict terug (als kopie, tegen per-ongeluk-wijzigen). Geen nieuwe schijf-lezing nodig.
- `microlearning` toegevoegd aan `module_loader.py`'s `emergence_layers`-dictionary (stap 3E) — geen andere wijziging in de laadvolgorde nodig, stap 3D (microlearning) liep al vóór stap 3E.
- Nieuwe `_trait_labels`-opzoektabel vertaalt interne trait-namen (bv. `"reflection_depth"`) naar leesbaar Nederlands (`"hoe diep ik nadenk"`) — zelfde patroon als de topic-naam-vertaling uit Fase 1b.
- Live bevestigd tegen Kevin's echte `growth_metrics.json`: "hoe diep ik nadenk" (`reflection_depth`, 1 shift, meest recente timestamp) wint een gelijkstand met `social_warmth` (ook 1 shift, oudere timestamp).

**Gemeenschappelijk aan alle 4 insight-types:**
- `reflect()` publiceert `emergence:insight` per gevonden insight — **nog GEEN listener die dit doorstuurt naar `layer4_response`** (bewust een latere, aparte stap: eerst deze basis testen). Nova zegt dus nog niets proactief over deze inzichten.
- `feedback(insight_type, success)` is bewust nog een LEGE STUB — publiceert enkel `emergence:learned_success`/`emergence:learned_failure`, slaat nog niets op. Latere stap: een echt opslagbestand (`insight_feedback.json` of SQLite-tabel), bijgehouden PER INSIGHT-TYPE.
- Tijdelijk testcommando in `main.py`: `emergence` (roept `reflect()` handmatig aan, toont tekst + confidence per insight) en `emergence debug` (toont ruwe status van de `layers`-dictionary).

**Bijvangst tijdens het testen: bug #21 gevonden (zie `nova_changelog.md`).** `module_loader.py` vroeg Layer 1 overal op met de verkeerde dictionary-key (`"word_associations"` i.p.v. de echte `"word_associations_learner"`), waardoor zowel Layer 7 als — sinds 8 juli al — Layer 4's personal touch nooit echt werkten. Nu gefixt op beide plekken (stap 3B en 3E).

**Bijvangst tijdens het testen (Fase 1b): eigen fout van Claude, direct gevonden en gefixt.** Bij het opruimen van een dubbele `_onderwerp_label()`-definitie werd per ongeluk ook de functie-header van `analyze_topic_frequency()` verwijderd, waardoor `emergence` crashte met een `AttributeError`. Hersteld en sindsdien elke uitbreiding end-to-end getest (alle insight-types tegelijk via `reflect()`, niet enkel apart) vóór het bestand werd doorgegeven — geen vergelijkbaar probleem meer opgetreden bij Fase 1c/1d.

**Nog te doen:**
- Listener `emergence:insight` → `layer4_response`, met confidence-gate (voorstel uit `layer7_startbericht.md`: > 0.85) — LET OP: `kennisdichtheid` en `personality_drift` gebruiken een ANDER soort "confidence" (ruw aantal relaties/shifts, geen 0-1-score) dan `woordverband`/`tijdspatroon` (PMI/Layer 2-confidence, wél 0-1) — een uniforme confidence-gate moet hier rekening mee houden, nog niet opgelost.
- Eenvoudige, tijdelijke timing-check (aangezien Activity-Aware Interaction nog niet bestaat) — of voorlopig gewoon altijd mogen spreken tot die module er is
- `feedback()` echt laten opslaan, per insight-type

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

| Fase | Omschrijving | Type | Status |
| --- | --- | --- | --- |
| 8 | Causal Reasoning | Pure symbolisch | ❌ Toekomst |
| 9 | Temporal Semantics | Pure symbolisch | ❌ Toekomst |
| 10 | Uncertainty Tracking | Pure symbolisch | ❌ Toekomst |
| 11 | Knowledge Extraction (spaCy) | ML | ❌ Toekomst |
| 12 | Semantic Similarity (embeddings) | ML | ❌ Toekomst |
| 13 | Graph Visualization (Plotly) | ML | ❌ Toekomst |

**concepts.json:** gevuld met testdata (hond, dier, appel, pitvrucht, vliegtuig, democratie...) — productiedata, niet wissen.

---

## ♟️ Games — Status & Roadmap

| Spel | Modul | Status | Engine |
| --- | --- | --- | --- |
| Schaak | chess_engine.py | ✅ Klaar | Stockfish (symbolisch) |
| Dammen | checkers_engine.py | ❌ Toekomst | Symbolic engine |
| Go | go_engine.py | ❌ Toekomst | KataGo (neural, bounded) |
| Meerdere bordspellen (dammen, Go, ...) | active_game systeem | ❌ Toekomst | via IntentRouter |

**Geplande features:**

- Langzame partijen over weken/maanden
- GUI bord + chat sidebar (tegelijk praten en spelen)
- Commentary per zet ("Interessante zet!")
- Leren van Kevin's spelstijl via Layer 2 (pattern_matcher)

---

## 🔁 Reboot & Hot Reload

|Feature|Status|Roadmap|
|---|---|---|
|/reboot commando (full restart, ~5 sec)|✅ Klaar en volledig getest|reboot_hotreload_roadmap.md|
|/reload module (manual hot reload)|❌ Later|reboot_hotreload_roadmap.md|
|Auto file watcher (Ctrl+S → reload)|❌ Veel later|reboot_hotreload_roadmap.md|

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

| Fase | Omschrijving                           | Status           |
|------|----------------------------------------|------------------|
| 1    | Databestand + basis CRUD               | ❌ Nog te bouwen |
| 2    | Expliciet commando (onthoud:/vergeet:) | ❌ Nog te bouwen |
| 3    | Automatische patroonherkenning         | ❌ Nog te bouwen |
| 4    | Integratie in chat.py                  | ❌ Nog te bouwen |

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

1. 🟢 **User preferences-module** — nog te plannen (memory_user_preferences_roadmap.md). Groeiend takenpakket: expliciete voorkeuren (ik hou van/haat X), disambiguatie-keuzes voor meerduidige woorden (zie bug #10, Layer 4-sectie), en mogelijk een feedback-loop voor Layer 4-antwoorden.
2. 🟢 **memory.py Fase 5** — optimalisatie/polish, enkel nodig bij grote databank of trage queries (geen haast)
3. 🟢 **Intent classifier (ML-specialist)** — concept, nog niet ingepland. Los van Layer 1-7, hangt enkel af van Layer 0-data. Volledig uitgewerkt in: intent_classifier_roadmap.md.
4. 🟢 **Activity Awareness (activiteiten herkennen, correleren, proactief reageren)** — concept uitgewerkt (6 juli 2026), nog niet ingepland. Kern: generiek `"ik ga <activiteit>"`-patroon in intent_router.py publiceert `activity_started`-events die Layer 2 al generiek meetelt; daarnaast co-occurrence tussen activiteiten (bv. koffie + coderen) en duur-detectie met drempelwaarde voor proactieve pauze-suggesties — beide pure statistiek/timer-logica, geen ML. Optioneel scherm-detectie (psutil, geen ML) en camera-detectie (vereist extern vision-model als sensor, met privacy-ontwerp vooraf). Ook: mogelijke uitbreiding naar per-woord-timing voor Layer 4 (zie Layer 4-sectie). Volledig uitgewerkt in: **activity_awareness_roadmap.md**.
5. 🟢 **Activity-Aware Interaction (interruption learning + contextuele suggesties)** — concept uitgewerkt (9 juli 2026), nog niet ingepland. Bouwt voort op Activity Awareness + Layer 5 (Layer 5 Fase 1-5 zijn intussen VOLLEDIG klaar): leert per activiteit een confidence-score op ("mag ik storen tijdens coderen?"), met vaste sjabloonvariatie zodat het niet elke keer identiek klinkt. Aparte, grotere uitbreiding: contextuele suggesties tussen activiteiten (bv. Plex → lichten dimmen) — puur co-occurrence-tellen zoals Activity Awareness Deel C, maar vereist voor "alledaagse" acties (zoals lichten dimmen via schakelaar) een aparte sensor/integratie-laag (bv. Home Assistant/Hue) om dat moment uberhaupt als Nova-event zichtbaar te maken. **Belangrijke nuance (16 juli 2026, na afronding Layer 5 Fase 5):** Kevin's wens dat "Nova zelf leert wanneer ze wel/niet mag storen" hoort HIER thuis, niet in Layer 5 zelf — Fase 5 legt enkel de vaste score-gewichten vast (zie Layer 5-sectie); dit werkpunt zou die gewichten leren aanpassen op basis van Kevin's feedback, blijft daarbij mogelijk 100% symbolisch (tellen i.p.v. ML). Volledig uitgewerkt in: **interruption_learning_roadmap.md**.

*(Afgeronde werkpunten verplaatst naar `nova_changelog.md`, 18 juli 2026 — inclusief Personality pipeline deel 1+2, microlearning.py, Layer 2 opruimwerk, Layer 5 Fase 1-5, Layer 6-integratie response_style, emotion_engine decay, Layer 6 identity-blueprint-koppeling, het achtergrondthread-patroon, en de `behavior_modifiers.py`-koppeling — zie changelog voor de correctie hierover.)*

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
