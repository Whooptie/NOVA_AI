# Topic Events Roadmap: onderwerp-herkenning koppelen aan Layer 2

**Status:** Ontwerp uitgewerkt, nog te bouwen
**Depends on:** intent_router.py ✅, pattern_matcher.py (Layer 2) ✅
**Gebruikt door:** Layer 4 (response_engine.py, nog te bouwen)
**Datum:** 5 juli 2026

---

## INHOUDSOPGAVE

1. [Wat lost dit op?](#wat-lost-dit-op)
2. [Waarom Layer 2 dit nu niet kan](#waarom-niet)
3. [Het ontwerp: topic_detected-events](#ontwerp)
4. [Hoe dit samenspeelt met Layer 1](#layer-1)
5. [Hoe dit samenspeelt met Layer 4](#layer-4)
6. [Fase-roadmap](#fase-roadmap)
7. [Eerlijkheid: wat kan wel/niet](#eerlijkheid)

---

## WAT LOST DIT OP? {#wat-lost-dit-op}

Layer 2 (`pattern_matcher.py`) telt nu enkel **generieke event-types** (`chat_message`, `chat_response`) op uur/dag. Ze weet dus dat er om 19u vaak gechat wordt, maar niet **waarover**.

Doel: Layer 2 laten weten dat er specifiek over **schaken**, **Plex**, **dammen**, enz. gepraat/gehandeld wordt op bepaalde tijdstippen — zodat er straks concrete, onderwerp-specifieke patronen ontstaan zoals:

```
"topic_detected:chess" → 92% van de dagen rond 19u-20u
"topic_detected:plex"  → vaak op vrijdagavond 21u
```

---

## WAAROM LAYER 2 DIT NU NIET KAN {#waarom-niet}

Layer 2 is bewust **inhouds-blind** gebouwd (zie `nova_state.md`, Layer 2-sectie): ze telt enkel *dat* een event_type voorkomt, nooit *wat* er inhoudelijk gezegd is. Dat is een architecturale keuze, geen beperking om op te lossen door Layer 2 zelf tekst te laten lezen — dat zou immers taalbegrip vereisen, precies wat symbolische telling wil vermijden.

De oplossing zit dus niet in Layer 2 "slimmer" maken, maar in het **al herkende onderwerp expliciet doorgeven** vanuit een module die dat al weet.

---

## HET ONTWERP: TOPIC_DETECTED-EVENTS {#ontwerp}

```
intent_router.py herkent een intent (bv. schaken) — dit gebeurt al
       ↓
publiceert EXTRA event: event_bus.publish("topic_detected:chess", {"timestamp": ...})
       ↓
Layer 2 luistert al naar de EventBus — voegt "topic_detected:chess"
toe aan haar relevante-events-filter (RELEVANTE_EVENT_TYPES)
       ↓
Layer 2 telt dit net als elk ander event_type op uur/dag — GEEN nieuwe logica nodig
```

**Belangrijk:** dit wordt geen aparte oplossing per onderwerp. Layer 2's tel-mechanisme blijft volledig generiek — ze telt gewoon elk event dat begint met `topic_detected:`, ongeacht welk woord daarachter staat. Per nieuwe module (Plex, dammen, Go, ...) komt er telkens maar **1 kleine toevoeging** bij: de regel die het event verstuurt op het moment dat de intent al herkend wordt. Dit wordt een vaste stap in het bouwproces van elke nieuwe module, geen apart project.

---

## HOE DIT SAMENSPEELT MET LAYER 1 {#layer-1}

Layer 2 geeft enkel **wanneer** (tijdstip/frequentie van een onderwerp). Layer 1 (woordassociaties) geeft **welke woorden erbij horen**, opgebouwd uit Kevin's eigen taalgebruik via PMI-scores — volledig onafhankelijk van timing.

```
Layer 2 weet: "topic_detected:plex" komt vaak voor op vrijdag 21u
Layer 1 weet: "plex" ↔ "actiefilm" (0.88), "plex" ↔ "ontspannen" (0.81)
```

Beide lagen blijven apart en onafhankelijk — Layer 2 hoeft Layer 1 niet te "horen" en andersom. Pas Layer 4 combineert beide (zie hieronder).

---

## HOE DIT SAMENSPEELT MET LAYER 4 {#layer-4}

Layer 4 (response_engine.py, nog te bouwen) luistert naar `pattern:detected`-events van Layer 2, en combineert dit met Layer 1's woordverbanden en Layer 3's semantische kennis, in een **vast sjabloon** — geen vrije tekstgeneratie:

```
sjabloon: "Het is {uur}u — wil je een potje {onderwerp}?"
→ "Het is 19u, wil je een potje schaken?"

sjabloon met Layer 1-verrijking: "Het is {uur}u — tijd om te {top_associatie}?"
→ "Het is 21u — tijd om te ontspannen met een actiefilm?"
```

De variabelen (`{uur}`, `{onderwerp}`, `{top_associatie}`) komen altijd **letterlijk uit opgeslagen, natelbare data** (Layer 2's confidence-score, Layer 1's PMI-score) — Layer 4 verzint nooit zelf een verband dat nergens geteld is.

---

## FASE-ROADMAP {#fase-roadmap}


| Fase | Omschrijving                                                                                                       | Geschat werk                                                  |
| ------ | -------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| 1    | `intent_router.py` uitbreiden: bij elke herkende intent ook `topic_detected:<naam>` publiceren                     | Klein — 1 regel per bestaande intent                         |
| 2    | `pattern_matcher.py` (Layer 2): `topic_detected:*`-events toevoegen aan relevante-events-filter                    | Klein — uitbreiding van bestaande`RELEVANTE_EVENT_TYPES`-set |
| 3    | Testen met minstens 2 onderwerpen (bv. schaken + weer) om te bevestigen dat losse patronen per onderwerp ontstaan  | Klein                                                         |
| 4    | Vast "recept": bij elke nieuwe module (Plex, dammen, Go...) voortaan standaard een`topic_detected`-event toevoegen | Doorlopend, geen apart project                                |
| 5    | Koppeling met Layer 4 (sjabloon-antwoorden + proactief spreken via achtergrondtimer)                               | Later — afhankelijk van Layer 4-bouw                         |

---

## EERLIJKHEID: WAT KAN WEL/NIET {#eerlijkheid}

- ✅ **Event per herkende intent publiceren** — 100% symbolisch, intent_router.py weet dit al, enkel doorgeven
- ✅ **Layer 2 telt dit generiek op tijdstip** — zelfde bestaande mechanisme, geen nieuwe logica
- ✅ **Sjabloonzinnen met ingevulde variabelen (Layer 4)** — symbolische templating, geen generatie
- ❌ **Layer 2 zelf tekstinhoud laten interpreteren om onderwerpen te "ontdekken"** — dat zou taalbegrip vereisen, wordt bewust niet gebouwd
- ❌ **Verwachten dat dit voor élk denkbaar onderwerp werkt** — enkel voor intents die `intent_router.py` al herkent; nieuwe onderwerpen vereisen altijd eerst een eigen module/intent, dit systeem volgt daarna vanzelf mee
- ❌ **Nova zelf vrij laten formuleren welk verband ze ziet** — elk woord/verband in de uiteindelijke zin moet herleidbaar zijn tot een opgeslagen, natelbare score (confidence uit Layer 2, PMI uit Layer 1)

**Status in de bouwvolgorde:** logische vervolgstap zodra Layer 2 verder getest is met haar huidige, generieke event-types. Kan onafhankelijk van Layer 4 al gebouwd en getest worden (Layer 2 kan de topic-patronen al opslaan, ook al gebruikt niemand ze nog).
