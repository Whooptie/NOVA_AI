# Layer 1 Word Embeddings Roadmap: word2vec als externe specialist naast PMI

**Status:** Concept — nog niet ingepland in bouwvolgorde
**Depends on:** Layer 1 (`word_associations_learner.py`, PMI/co-occurrence — draait al ✅)
**Gebruikt door:** Layer 1 zelf (als aanvullend signaal), Layer 4 (`response_engine.py`'s `_sterkste_associatie()`), mogelijk Layer 3 (`semantic.py`, zie kanttekening onderaan)
**Datum:** 28 juli 2026

---

## INHOUDSOPGAVE

1. [Wat lost dit op?](#wat-lost-dit-op)
2. [Eerlijkheid vooraf: dit is GEEN symbolische berekening](#eerlijkheid-vooraf)
3. [PMI vs. embeddings: aanvulling, geen vervanging](#pmi-vs-embeddings)
4. [Architectuur: embeddings als bounded specialist](#architectuur)
5. [Twee opties: getraind vs. voorgetraind model](#twee-opties)
6. [Fase-roadmap](#fase-roadmap)
7. [Data structure — uitbreiding van word_associations.json](#data-structure)
8. [Wat dit niet oplost](#wat-dit-niet-oplost)
9. [Open vragen voor later](#open-vragen)

---

## WAT LOST DIT OP? {#wat-lost-dit-op}

Layer 1's huidige PMI/co-occurrence-systeem ziet **alleen** woorden die letterlijk samen in een zin voorkwamen. Twee woorden die Kevin nooit samen typt, krijgen nooit een associatie — ook niet als ze inhoudelijk sterk verwant zijn.

```
Kevin typt ooit: "ik speel graag schaken, leuk bordspel"
Kevin typt ooit: "backgammon is ook een leuk bordspel"

PMI/co-occurrence ziet:
  schaken ↔ bordspel  (co-occurrence: 1)
  backgammon ↔ bordspel  (co-occurrence: 1)
  schaken ↔ backgammon  → NOOIT gezien, dus GEEN associatie

Embeddings zouden kunnen zien:
  schaken en backgammon komen allebei vaak voor náást "bordspel",
  "zet", "partij" → vergelijkbare CONTEXT → hoge similarity,
  ook al stonden ze zelf nooit in dezelfde zin.
```

Dat is de kloof die word2vec (of een vergelijkbaar embeddings-model) zou dichten.

---

## EERLIJKHEID VOORAF: DIT IS GEEN SYMBOLISCHE BEREKENING {#eerlijkheid-vooraf}

**Dit moet keihard vooraf gezegd worden, want het is precies waar dit spoor van spoor 2 (Jaccard) verschilt.**

Word2vec (en elk ander embeddings-model, zoals `sentence-transformers`) is **een klein neuraal netwerk** dat vectoren traint op basis van een tekstcorpus. Het is geen telling, geen if/else, geen formule die je met de hand kan naspeuren zoals PMI. Dat betekent:

- Dit valt in dezelfde categorie als Stockfish/KataGo/MediaPipe in jouw architectuur: **toegestaan als externe, begrensde specialist — nooit als Nova's kern.**
- Het contract moet strikt blijven: **woord(en) in → vector/similarity-score uit.** Nova's symbolische kern (Layer 1's opslag, Layer 4's `_kies_variant()`/`_sterkste_associatie()`) beslist zelf wat ze met die score doet. Het model "begrijpt" niets, "denkt" niets — het is een reken-blackbox die gewoon een getal teruggeeft.
- Training/gebruik van dit model gebeurt **buiten** de live daemon-loop (apart script, of eenmalig ingeladen model), niet iets dat elke chat-beurt opnieuw hoeft te draaien.

Als dit ooit gebouwd wordt, moet dat in `nova_state.md` net zo expliciet gelabeld staan als de `llm_bridge.py`-vermelding: "gebruikt ML, geen symbolische Python" — geen twijfel daarover laten bestaan.

---

## PMI VS. EMBEDDINGS: AANVULLING, GEEN VERVANGING {#pmi-vs-embeddings}

| | PMI/co-occurrence (huidig, Layer 1) | Word2vec/embeddings (dit voorstel) |
|---|---|---|
| Techniek | Telling + logaritme-formule | Getraind neuraal netwerk |
| Symbolisch of ML? | 100% symbolisch/statistisch | ML — externe specialist |
| Ziet verband tussen... | woorden die **letterlijk samen** voorkwamen | woorden met **vergelijkbare context**, ook nooit-samen-gezien |
| Herkomst van de data | Kevin's eigen chatgeschiedenis, exclusief | Ofwel Kevin's chatgeschiedenis (klein corpus), ofwel een extern voorgetraind model |
| Uitlegbaarheid | Volledig — elk getal is herleidbaar | Black box — een vector "betekent" niets herleidbaars voor een mens |
| Nu al gebouwd? | ✅ Ja | ❌ Nee, dit document |

**Belangrijk:** dit vervangt PMI niet. Layer 1 blijft PMI gebruiken als primair, uitlegbaar signaal. Embeddings komen er **naast** te staan als een tweede, aparte score — Layer 4 (of Layer 1 zelf) kan dan beslissen om embeddings-similarity enkel te raadplegen als PMI niets vindt (zie Fase-roadmap).

---

## ARCHITECTUUR: EMBEDDINGS ALS BOUNDED SPECIALIST {#architectuur}

```
                    ┌─────────────────────────┐
                    │  word_associations_      │
                    │  learner.py (Layer 1)     │
                    │  - PMI/co-occurrence      │
                    │  - blijft primair signaal │
                    └───────────┬───────────────┘
                                │ als PMI niets vindt
                                ▼
                    ┌─────────────────────────┐
                    │  embedding_specialist.py  │  <-- NIEUW, apart bestand
                    │  - laadt extern model     │
                    │  - woord(en) in            │
                    │  - similarity-score uit     │
                    │  - GEEN eigen beslissingen │
                    └───────────┬───────────────┘
                                │ score
                                ▼
                    Layer 1/Layer 4 beslist zelf
                    of/hoe die score gebruikt wordt
```

`embedding_specialist.py` is een dun, apart module-bestand — precies zoals `chess_engine.py` een dunne laag is rond Stockfish. Het bevat geen eigen taalkundige logica, enkel: model laden, vector opvragen, cosine similarity berekenen, getal teruggeven.

---

## TWEE OPTIES: GETRAIND VS. VOORGETRAIND MODEL {#twee-opties}

**Optie A — zelf trainen op Kevin's eigen chatgeschiedenis (`interactions.jsonl`)**
- Voordeel: 100% "eigen" aan Kevin en Nova, geen externe afhankelijkheid qua inhoud.
- Nadeel, eerlijk: Kevin's corpus is klein (zie `word_associations.json` — een handvol woorden, enkele tientallen associaties). Word2vec heeft doorgaans **tienduizenden tot miljoenen** zinnen nodig om bruikbare vectoren te leren. Met een corpus deze grootte zal de kwaliteit waarschijnlijk zwak/onbetrouwbaar zijn — dit moet je vooraf weten, niet achteraf ontdekken.

**Optie B — voorgetraind Nederlands model gebruiken (bv. via `gensim`, of een Nederlands `sentence-transformers`-model)**
- Voordeel: direct bruikbare kwaliteit, geen trainingsdata-probleem.
- Nadeel, eerlijk: dit is dan **geen "Nova leert zelf"** meer — het is een kant-en-klaar extern taalmodel dat je inhuurt, getraind op een corpus dat niets met Kevin te maken heeft. Moet in `nova_state.md` expliciet zo benoemd worden: "extern voorgetraind model, geen eigen leerproces."

**Advies (te bespreken, geen beslissing hier):** optie B is realistischer gezien de kleine omvang van Kevin's eigen data vandaag. Optie A zou pas overweegbaar worden als `word_associations.json`/`interactions.jsonl` na maanden/jaren véél groter is.

---

## FASE-ROADMAP {#fase-roadmap}

### FASE 1: Losstaand testen (geen koppeling met Nova)
- `embedding_specialist.py` bouwen als losse, apart testbare klasse (net zoals `response_engine.py` in Fase 1-3 ook eerst losstaand was).
- Kiezen tussen optie A/B (zie hierboven), model laden, en gewoon een paar woordparen testen: geeft het zinvolle similarity-scores voor Nederlandse woorden?
- Geen enkele wijziging aan `word_associations_learner.py` of `response_engine.py` in deze fase.

### FASE 2: Koppeling als fallback-signaal in Layer 1
- `word_associations_learner.py` (of `response_engine.py`'s `_sterkste_associatie()`) raadpleegt `embedding_specialist.py` **alleen** als PMI niets/te weinig vindt voor een woord.
- Resultaat wordt duidelijk gelabeld als `"bron": "embedding"` in `word_associations.json` (zie Data structure), zodat het nooit verward wordt met een PMI-gevonden associatie.

### FASE 3: Confidence-drempel en eerlijke weergave
- Net als PMI zijn `MIN_ASSOCIATIE_SCORE`-drempel: embeddings-scores krijgen een eigen, apart te bepalen drempel (cosine similarity zit meestal tussen -1 en 1, PMI-scores in Layer 1 zijn al genormaliseerd 0-1 — deze twee schalen zijn NIET rechtstreeks vergelijkbaar, dus geen gedeelde drempelwaarde).
- Als een sjabloon in `response_engine.py` ooit een embedding-gevonden associatie toont, zou de formulering eerlijk kunnen blijven zoals ze nu al is (het onderscheid PMI/embedding hoeft niet zichtbaar te zijn voor Kevin in de chat zelf) — maar moet wel intern gelabeld blijven voor debug-doeleinden.

---

## DATA STRUCTURE — UITBREIDING VAN WORD_ASSOCIATIONS.JSON {#data-structure}

Ter referentie: hoe een embedding-gevonden associatie eruit zou zien naast de bestaande PMI-associaties, met een duidelijk `"bron"`-veld om de twee nooit te verwarren.

```json
{
  "associations": {
    "schaken": {
      "bordspel": {
        "co_occurrence": 1,
        "pmi": 0.86,
        "confidence": 0.86,
        "bron": "pmi"
      },
      "backgammon": {
        "similarity": 0.74,
        "confidence": 0.74,
        "bron": "embedding",
        "model": "voorgetraind_nl_v1"
      }
    }
  }
}
```

**Toelichting:**
- `"bron": "pmi"` vs. `"bron": "embedding"` — expliciet onderscheid, zodat je in `word_associations.json` altijd meteen ziet welk mechanisme een associatie vond. Dit is het eerlijkheidsprincipe uit je architectuur letterlijk teruggebracht in de datastructuur zelf.
- `"model"`-veld bij embedding-associaties — welk extern model verantwoordelijk was, nuttig als je ooit van model wisselt en oude/nieuwe associaties wil onderscheiden.
- Geen `"co_occurrence"`-veld bij embedding-associaties — dat concept bestaat daar niet, embeddings tellen geen letterlijke co-occurrence.

---

## WAT DIT NIET OPLOST {#wat-dit-niet-oplost}

Belangrijke kanttekening, aansluitend bij het eerdere gesprek over "kan Nova hierdoor beter praten": **nee.** Dit verrijkt enkel Layer 1's **geheugen/associatiedata** — het heeft geen enkel effect op hoe Nova een zin formuleert. Dat blijft, zoals eerder besproken, het domein van Layer 4's sjablonen (`response_engine.py`) en eventueel de aparte "response variant learning"-roadmap.

---

## OPEN VRAGEN VOOR LATER {#open-vragen}

- Optie A of B (zelf trainen vs. voorgetraind)? Voorlopig advies: B, gezien corpusgrootte — definitief te beslissen vóór Fase 1 start.
- Welk concreet voorgetraind Nederlands model (als optie B)? Vereist een aparte, korte vergelijking (bv. beschikbare `gensim`-modellen, of een Nederlandse `sentence-transformers`-variant) — nog niet onderzocht in dit document.
- Waar leeft `embedding_specialist.py` qua geheugengebruik/laadtijd? Een voorgetraind model kan honderden MB's groot zijn — moet gecheckt worden of dat past binnen de resources van Kevin's Intel Arc iGPU-opstelling, of dat dit puur CPU-gebonden moet blijven.
- Relevantie voor Layer 3 (`semantic.py`): Fase 12 in `semantic_extension_roadmap.md` beschrijft een vergelijkbaar idee maar dan toegepast op *concepten* (met `sentence-transformers`) in plaats van losse woorden. Als dit Layer 1-spoor ooit gebouwd wordt, is het de moeite waard om te bekijken of hetzelfde externe model voor beide doeleinden hergebruikt kan worden, in plaats van twee aparte modellen te laden.
