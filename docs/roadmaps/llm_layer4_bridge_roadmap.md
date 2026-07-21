# LLM Layer 4 Bridge Roadmap: lokaal model als "stylist" voor Nova's antwoorden

**Status:** Concept/idee, model gekozen en getest, nog niet gebouwd
**Depends on:** `response_engine.py` (Layer 4, ✅ afgerond), Ollama (✅ geïnstalleerd), Qwen2.5 3B (✅ gedownload en getest)
**Gebruikt door:** optionele uitbreiding op `layer4_response`-route, geen vervanging van bestaande sjablonen
**Datum:** 20 juli 2026

---

## INHOUDSOPGAVE

1. [Wat lost dit op?](#wat-lost-dit-op)
2. [Het kernprincipe: Nova blijft de chef](#kernprincipe)
3. [Herkomst van dit idee](#herkomst)
4. [Kostenanalyse: Claude API vs lokaal](#kostenanalyse)
5. [Hardware: geschikt voor Kevin's laptop](#hardware)
6. [Modelkeuze: waarom Qwen2.5 3B](#modelkeuze)
7. [ipex-llm: doodlopend spoor (bewust verlaten)](#ipex-llm)
8. [Testresultaten: prompt-iteraties](#testresultaten)
9. [Architectuur: waar dit aanhaakt](#architectuur)
10. [Welke intents wel/niet door deze route](#intents)
11. [Fase-roadmap](#fase-roadmap)
12. [Eerlijkheid: wat kan wel/niet](#eerlijkheid)

---

## WAT LOST DIT OP? {#wat-lost-dit-op}

Nova's Layer 4 (`response_engine.py`) genereert nu antwoorden via vaste sjablonen — helder en betrouwbaar, maar soms wat houterig ("Ja, een {woord} is een {definitie}."). Het idee: een klein, lokaal taalmodel laten helpen om diezelfde, al-verzamelde feiten in een vloeiendere zin te gieten — zonder dat het model ooit zelf beslist wát er gezegd wordt.

---

## HET KERNPRINCIPE: NOVA BLIJFT DE CHEF {#kernprincipe}

Vergelijkbaar met het kernprincipe uit `llm_codegen_tool_roadmap.md`, maar dan voor *generatie* i.p.v. *codegen*:

> **Het lokale model vervangt alleen de laatste plating-stap. Nova bepaalt nog steeds wélke feiten er zijn, óf er geantwoord mag worden, en in welke toon — het model verwoordt enkel wat al vaststaat.**

Wat blijft ongewijzigd:
- Layer 0-3 (geheugen, associaties, patronen, semantiek) — leveren data zoals altijd
- Layer 5 (context manager) — bepaalt nog steeds of/wanneer Nova mag spreken
- Layer 6 (personality/emotion) — bepaalt nog steeds de tone-pipeline (emoji's, stemming)
- `intent_router.py` — ongewijzigd

Wat verandert: enkel het allerlaatste stukje van `layer4_response` krijgt een **optionele** tussenstap, met de bestaande sjabloon-tekst als **gegarandeerde fallback** bij twijfel of validatiefout.

---

## HERKOMST VAN DIT IDEE {#herkomst}

Kwam voort uit een brainstorm-bericht van een andere AI (20 juli 2026), dat vier scenario's schetste voor "LLM als bounded specialist die op Nova leunt". Dit document werkt enkel **Scenario 1 ("De Vertaler")** verder uit — de andere drie (Lezer, Contextuele Weger, Versneller) blijven pure toekomstvisie, vastgelegd in Claude's geheugen, niet in een aparte roadmap.

---

## KOSTENANALYSE: CLAUDE API VS LOKAAL {#kostenanalyse}

Voor de volledigheid — waarom lokaal boven de Claude API:

| | Claude API (Haiku 4.5) | Lokaal (Ollama, Qwen2.5 3B) |
|---|---|---|
| Kosten | ~$0,33-5/maand, afhankelijk van gebruik | Gratis |
| Snelheid | Netwerk-latency (~0,5-1s) | Zeer snel, lokaal getest |
| Privacy | Verlaat de machine | 100% lokaal — past bij Nova's filosofie |
| Nederlands-kwaliteit | Zeer goed | Wisselend, zie testresultaten hieronder |

Zelfs bij intensief gebruik kost de Claude API-route maar een paar dollar per maand (kleine JSON-input, kort antwoord, geen opbouwende conversatiegeschiedenis). Toch is lokaal gekozen — het is de architecturaal coherentere keuze gezien Nova's "lokaal en privacy-first"-principe.

---

## HARDWARE: GESCHIKT VOOR KEVIN'S LAPTOP {#hardware}

- **Intel Core Ultra 7 155H** (Meteor Lake) — heeft dedicated NPU (Intel AI Boost) én Arc iGPU
- **32GB RAM** — ruim voldoende, een 3-4B model in Q4 is maar ~2-3GB
- **Arc iGPU** — deelt systeem-RAM, "128 MB" in Windows-instellingen is enkel de dedicated-toewijzing, geen echte limiet

**Praktijkresultaat:** Qwen2.5 3B draait via kale Ollama (CPU-only, geen GPU-versnelling) al **zeer snel** op deze hardware — geen noodzaak gebleken om GPU-versnelling meteen te forceren.

---

## MODELKEUZE: WAAROM QWEN2.5 3B {#modelkeuze}

Gebaseerd op het Fietje-onderzoek (Vanroy, KU Leuven, arxiv 2412.15450) — een benchmark van kleine taalmodellen specifiek op Nederlands:

- Nederlands-specifiek getrainde modellen (Fietje, GEITje, Boreas, Tweety) presteerden **slechter** dan gewone multilinguale modellen van vergelijkbare/kleinere omvang
- **Qwen2.5 3B-Instruct scoorde het beste** op de meeste Dutch-benchmarks (Global MMLU, Dutch CoLA, ARC), ondanks kleine omvang
- Phi-3.5-mini-instruct scoorde in het onderzoek op de tweede plaats

**Belangrijke kanttekening uit het onderzoek zelf:** de benchmarks meten vooral *begrip* (classificatie, multiple-choice), niet *vrije taalproductie* — precies het gat dat onze eigen praktijktests moesten opvullen (zie hieronder).

---

## IPEX-LLM: DOODLOPEND SPOOR (BEWUST VERLATEN) {#ipex-llm}

Aanvankelijk overwogen voor Arc iGPU-versnelling, maar tijdens onderzoek bleek: **`intel/ipex-llm` is op 28 januari 2026 gearchiveerd door Intel zelf, om veiligheidsredenen.** De officiële vervanger (`llm-scaler`) richt zich vooral op zwaardere multi-GPU/server-scenario's, niet op individuele laptop-iGPU's.

**Beslissing:** gewoon kale, officiële Ollama gebruikt (CPU-only). Bleek ruim snel genoeg op Kevin's hardware — geen noodzaak voor extra Intel-specifieke tooling.

**Indien later toch GPU-versnelling gewenst:** de actief onderhouden routes zijn dan OpenVINO-backend voor llama.cpp, of native Ollama SYCL-support (sinds v0.17, nog "minder volwassen dan NVIDIA/AMD" volgens community-bronnen). Geen prioriteit zolang CPU-snelheid volstaat.

---

## TESTRESULTATEN: PROMPT-ITERATIES {#testresultaten}

Vier iteraties uitgevoerd op 20 juli 2026, om een realistische Nova-achtige prompt te vinden.

| Poging | Model | Prompt-aanpak | Resultaat |
|---|---|---|---|
| 1 | Qwen2.5 3B | Vrije natuurlijke-taal-vraag | Feitelijk fout, vage/onzinnige zin |
| 2 | Qwen2.5 3B | JSON-input, geen rolinstructie | Feiten correct, maar rolverwarring ("Nova" als aangesprokene) |
| 3 | Qwen2.5 3B | + expliciete derde-persoon-instructie | Feiten correct, maar sprak als het onderwerp zelf ("Ik ben een gitaar...") |
| 4 | Qwen2.5 3B | + "NOOIT als het onderwerp zelf" | **Grammaticaal correct, feiten correct, geen rolverwarring — toon ontbreekt** |
| 4 (herhaald) | Phi-3.5-mini | Zelfde prompt als poging 4 | Grammaticaal duidelijk incorrect, onbegrijpelijke pseudo-poëzie, feiten aanwezig maar onherkenbaar verstopt |

**Winnende prompt-structuur (poging 4):**
```
Beschrijf, in de derde persoon, het volgende onderwerp in ÉÉN vloeiende Nederlandse zin.
Spreek NOOIT als het onderwerp zelf, alsof het onderwerp een "ik" is — beschrijf het van
buitenaf, zoals een verteller. Toon: kalm, droog, licht sarcastisch. Gebruik uitsluitend
de gegeven feiten. Gebruik het woord "[kernwoord]" letterlijk.

Onderwerp: [entity]
is een: [is_a]
eigenschap: [property]
```

**Belangrijkste eerlijke conclusie:** Qwen2.5 3B wint duidelijk van Phi-3.5-mini op grammaticale betrouwbaarheid en feitelijke helderheid. Geen van beide modellen laat de gevraagde toon ("droog, licht sarcastisch") betrouwbaar doorkomen — het model valt terug op neutrale beschrijving zodra feiten + rol + toon tegelijk gevraagd worden.

**Praktische conclusie hieruit:** de LLM hoeft de toon niet zelf te dragen. Nova's bestaande tone-pipeline (`tone_engine.py`/`expression_injector.py`) voegt sowieso al emoji's/stemming toe ná de tekst — de LLM-laag hoeft enkel **correct en feitelijk juist Nederlands** te leveren, niet het karakter zelf te acteren.

---

## ARCHITECTUUR: WAAR DIT AANHAAKT {#architectuur}

```
Layer 3 (semantic) + Layer 1 (associaties) + Layer 2 (timing)
                    ↓
       response_engine.generate() bouwt sjabloon-tekst
                    ↓
       [NIEUW, OPTIONEEL] llm_bridge.py:
         - stuurt kernfeiten (entity, is_a, property) naar Ollama
         - ontvangt kandidaat-zin terug
         - valideert tegen concepts.json (bevat de kernwoorden?)
         - bij twijfel/fout → gebruik het bestaande sjabloon
                    ↓
       layer4_response (ongewijzigd) → tone-pipeline → chat_response
```

**Config-vlag:** een aan/uit-instelling (bv. in een settings-bestand) bepaalt of deze route actief is. Kevin bepaalt dit, niet Nova autonoom — in lijn met het autonomie-principe.

**Nieuwe module:** `llm_bridge.py` — bevat:
1. Eén functie die feiten omzet naar de gekozen prompt-structuur en een HTTP-verzoek stuurt naar `localhost:11434` (Ollama's lokale API)
2. Eén validatiefunctie die het antwoord checkt tegen de kernwoorden uit `concepts.json` vóór het gebruikt wordt

**Model-instelling:** `qwen2.5:3b`, opgeslagen in `C:\Nova_AI\data\models` (Ollama's `OLLAMA_MODELS`-instelling, aangepast via Ollama's eigen Settings-scherm).

---

## WELKE INTENTS WEL/NIET DOOR DEZE ROUTE {#intents}

**Kandidaten (later te bevestigen):**
- Definities (`detect_definition` — Layer 4's hoofdroute)
- Mogelijk andere semantic-intents (synoniemen, eigenschappen) — nog niet besloten of dit de moeite waard is, zie ook openstaand punt in `nova_state.md` over Layer 1/2-verrijking voor deze intents

**Bewust NIET door deze route (blijft op bestaande sjabloon/route):**
- Weer, tijd, math — kort, feitelijk, precies; een LLM voegt hier risico toe zonder meerwaarde
- Schaken, help — blijven bewust op `chat_response`, buiten `layer4_response` om (zie `nova_state.md`)
- Alles met exacte cijfers/waarden — kleinere kans op verhaspeling

---

## FASE-ROADMAP {#fase-roadmap}

| Fase | Omschrijving | Status |
|---|---|---|
| 1 | Ollama installeren, modellen-map ingesteld op `C:\Nova_AI\data\models` | ✅ Afgerond (20 juli 2026) |
| 2 | Model ophalen en los testen (buiten Nova) | ✅ Afgerond — Qwen2.5 3B gekozen |
| 3 | Prompt-structuur vinden die feiten correct + grammaticaal correct oplevert | ✅ Afgerond (zie testresultaten) |
| 4 | `llm_bridge.py` bouwen: functie die feiten → Ollama-verzoek → tekst | 🔲 Nog te doen |
| 5 | Validatiefunctie: check kandidaat-tekst tegen `concepts.json`, fallback bij twijfel | 🔲 Nog te doen |
| 6 | Aanhaken in `response_engine.py` via zoek/vervang-blok, achter config-vlag | 🔲 Nog te doen |
| 7 | Testen in echte Nova-omgeving, meerdere concepten | 🔲 Nog te doen |
| 8 | Beslissen of dit uitgebreid wordt naar andere semantic-intents | 🔲 Nog te doen, geen prioriteit |

**Geschatte moeilijkheid (zoals eerder besproken):** geen remodel van Layer 4 — een module + een haakje. Stap 4-5 zijn het meeste denkwerk (validatielogica), stap 6 is klein en gericht. Realistisch: een paar avonden verspreid over een week of twee, vooral getest via trial-and-error op toon/kwaliteit.

---

## EERLIJKHEID: WAT KAN WEL/NIET {#eerlijkheid}

- ✅ **Qwen2.5 3B kan feiten correct en grammaticaal kloppend verwoorden**, mits de juiste prompt-structuur (derde persoon, expliciet "niet als het onderwerp zelf")
- ✅ **Draait zeer snel op Kevin's Core Ultra 7 155H**, zelfs zonder GPU-versnelling
- ✅ **Volledig lokaal, geen kosten, geen data die de machine verlaat**
- ✅ **Makkelijk terug te draaien of te vervangen** — model draait los van Nova's code, enkel via HTTP-verzoek aangesproken
- ❌ **Qwen2.5 3B (en Phi-3.5-mini) laten de gevraagde toon (droog/sarcastisch) niet betrouwbaar doorkomen** — dit is en blijft Layer 6/tone-pipeline's taak, niet de LLM's
- ❌ **ipex-llm is geen begaanbare weg meer** — gearchiveerd door Intel, bewust verlaten voor deze roadmap
- ❌ **Dit vervangt geen enkele bestaande sjabloon-route** — het is een optionele, valideerbare extra laag, met sjabloon als gegarandeerde fallback
- ❌ **Nova roept dit nooit autonoom aan buiten een normale response-cyclus** — de config-vlag bepaalt of de route actief is, Kevin beslist dat, niet Nova

**Status in de bouwvolgorde:** model gekozen en getest, prompt-structuur gevonden. Bouwen van `llm_bridge.py` (Fase 4) is de volgende stap, wanneer Kevin daar tijd voor wil vrijmaken. Geen harde deadline.

---

**Author:** Claude + Kevin
