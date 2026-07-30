# 🗣️ Taal & Redeneerlimieten — losse uitbreidingsideeën (niet in officiële roadmap)

> Aangemaakt: 30 juli 2026
> Status: PLANNING — losse ideeën, géén onderdeel van een bestaande Layer- of semantic-roadmap
> Context: ontstaan uit een extern AI-advies over hoe ver Nova's taal en vrij redeneren op te rekken zijn zonder een LLM in de kern te zetten, en de daaropvolgende controle welke punten daarvan al gedekt waren door bestaande roadmaps

---

## Waarom dit document?

Het externe advies noemde een reeks mogelijke uitbreidingsrichtingen voor taal en redeneren. Bij controle tegen `nova_state.md` en de bestaande roadmaps bleek het merendeel al gedekt:

- Diepere symbolische chaining, causaal redeneren, analogie op structuur → zit al in `semantic_extension_roadmap.md` (Fase 8+) en `reasoning_engine_ideeen_roadmap.md`
- Synoniemen/parafrase/output-variatie → zit al in `response_variant_learning_roadmap.md`

Vier punten bleven over die **nergens** een thuis hadden — niet in een bestaande roadmap, niet als bijvangst tijdens een bouwsessie. Die staan hier, zodat ze niet verloren gaan.

**Belangrijk:** dit is geen bouwvolgorde, geen toezegging — puur een ideeënlijst om later uit te kiezen, zelfde opzet als `reasoning_engine_ideeen_roadmap.md`.

---

## De 4 ideeën

### 1. Contextuele referentie-resolutie
**Type:** pure symbolisch, middelgrote opzet
**Wat:** verwijswoorden oplossen naar het concept/event waar ze op slaan — "die zet", "dat", "hetzelfde als net", "gisteren" — zodat Nova een vervolgzin kan koppelen aan wat er net besproken werd, zonder dat Kevin het onderwerp herhaalt.
**Waar zou dit thuishoren:** Layer 5 (`context_manager.py`), niet Layer 3/4 — het gaat over "wat is het meest recente relevante ding om naar te verwijzen", niet over kennis of respons-opbouw zelf. Staat NIET in `memory_layer5_roadmap.md` (die roadmap gaat over tijd/activiteit/focus/aanwezigheid/interruption, niet over taalkundige verwijzingen).
**Implementatie, ruw:** een kortlevend "laatst besproken concept/event"-geheugen (vergelijkbaar qua levensduur met `pending_question.py`'s in-memory aanpak), bijgewerkt na elk succesvol antwoord, geraadpleegd door `intent_router.py` zodra een zin een verwijswoord bevat zonder eigen zelfstandig naamwoord.
**Relatie tot officiële roadmap:** niet vermeld — eigen, nieuw gat.

### 2. Ellipsis / korte antwoorden
**Type:** pure symbolisch, kleine tot middelgrote opzet
**Wat:** korte, onvolledige vervolgzinnen zoals "ja die", "nee de andere", "nog eens" correct interpreteren als reactie op wat Nova net aanbood (bv. een lijst met opties, of een laatst gegeven antwoord).
**Hoe dit verschilt van wat al bestaat:** `pending_question.py` lost al een deel van dit probleem op, maar uitsluitend voor korte ja/nee/bevestiging-achtige reacties op een vraag die Nova zelf net stelde. Ellipsis is breder: het gaat ook over verwijzen naar één item uit een zojuist gegeven lijst of alternatievenset, niet enkel bevestigen/ontkennen.
**Relatie tot officiële roadmap:** niet vermeld — hangt inhoudelijk samen met idee #1 (referentie-resolutie) en zou grotendeels dezelfde onderliggende "wat is er net gezegd"-laag kunnen hergebruiken.

### 3. Case-based reasoning
**Type:** pure symbolisch, middelgrote opzet
**Wat:** bij een nieuwe vraag/situatie actief op zoek gaan naar een vergelijkbare eerdere situatie uit Layer 0 (`memory.py`) of Layer 2 (`pattern_matcher.py`), en die als referentiepunt gebruiken in het antwoord (bv. "vorige keer toen je dit vroeg, ging het over X").
**Waarom interessant:** Nova slaat al enorm veel op (Layer 0's volledige interactiegeschiedenis, Layer 2's patronen), maar haalt dit nooit actief op als vergelijkingsmateriaal voor een NIEUWE vraag — enkel voor statistiek/timing.
**Relatie tot officiële roadmap:** niet vermeld in bestaande roadmap-documenten. Zou een nieuwe query-laag op Layer 0 vereisen (vergelijkbaar met `memory.find_similar()`, die al bestaat maar tot nu toe niet voor dit doel ingezet wordt).

### 4. Hypothetisch redeneren binnen de kennisgraaf
**Type:** pure symbolisch, grotere opzet
**Wat:** tijdelijke aannames kunnen verwerken die niet (nog) in `concepts.json` staan — bv. "stel dat een octopus wél een zoogdier is, wat zou dat betekenen?" — door een tijdelijke, niet-opgeslagen relatie toe te voegen en daar vervolgvragen op te beantwoorden binnen dezelfde gespreksbeurt, zonder dat dit ooit permanent in de kennisgraaf terechtkomt.
**Waarom lastiger dan de andere drie:** vereist een aparte, tijdelijke "wat-als"-laag boven de bestaande `ReasoningEngine`, die duidelijk gescheiden blijft van de echte, opgeslagen kennis — een reëel risico op vervuiling van `concepts.json` als dit niet zorgvuldig geïsoleerd wordt.
**Relatie tot officiële roadmap:** niet vermeld — wel expliciet genoemd in het externe AI-advies als "technisch mogelijk, maar complexer" dan de andere symbolische redeneeruitbreidingen.

---

## Kort overzicht: overlap met bestaande roadmap

| Idee | Zit in officiële roadmap? |
| --- | --- |
| 1. Contextuele referentie-resolutie | ❌ Niet vermeld — hoort bij Layer 5, staat er niet in |
| 2. Ellipsis / korte antwoorden | ❌ Niet vermeld — deels aanpalend aan `pending_question.py`, maar breder |
| 3. Case-based reasoning | ❌ Niet vermeld — zou `memory.find_similar()` een nieuw doel geven |
| 4. Hypothetisch redeneren | ❌ Niet vermeld — grootste/lastigste van de vier |

**Advies (30 juli 2026):** geen van deze vier is ingepland of geprioriteerd. Idee #1 en #2 hangen inhoudelijk samen (beide leunen op "wat is er net gezegd/aangeboden") en zijn vermoedelijk het efficiëntst om samen als één klein project op te pakken, mocht Kevin hier ooit tussendoor iets van willen bouwen. Idee #3 kan volledig los gebouwd worden (hergebruikt bestaande Layer 0-data). Idee #4 is het grootst en heeft de meeste zorgvuldigheid nodig (isolatie van de echte kennisgraaf) — laatste keuze als hier ooit aan begonnen wordt.

---

## Context: herkomst van dit document

Ontstaan uit een gesprek waarin een extern AI-advies werd voorgelegd over de haalbare grenzen van Nova's taal en vrij redeneren zonder LLM-kern. Van de daarin genoemde richtingen bleken causaal/analogisch redeneren en output-variatie al gedekt door `semantic_extension_roadmap.md`, `reasoning_engine_ideeen_roadmap.md` en `response_variant_learning_roadmap.md`. Deze 4 punten waren de enige die nergens een thuis hadden.
