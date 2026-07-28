# Response Variant Learning Roadmap: welke sjabloonvariant "landt" het best bij Kevin

**Status:** Concept — nog niet ingepland in bouwvolgorde
**Depends on:** Layer 4 (`response_engine.py`, Fase 5 — meerdere varianten per sjabloon, `_kies_variant()`), Layer 6 (`personality_engine.py`, `microlearning.py` als referentie-classifier)
**Gebruikt door:** Layer 4 (`_kies_variant()`) — vervangt op termijn de **gelijk verdeelde** `random.choice()` door een **gewogen** keuze
**Datum:** 28 juli 2026

---

## OVERZICHT: TWEE FASEN, BEWUST GESCHEIDEN

| Fase | Vraag die het beantwoordt | Vereist een classifier? |
|---|---|---|
| 1. Logging (zonder oordeel) | Welke variant koos Nova, in welke context? | Nee |
| 2. Gewogen keuze (Kevin's reactie als proxy-signaal) | Welke variant "landt" beter dan een andere? | Ja — klassiek, geen LLM |

Fase 1 kan **nu al** gebouwd worden, los van of Fase 2 ooit gebeurt. Fase 2 hangt af van Fase 1's data en is pas zinvol met genoeg verzamelde voorbeelden.

---

## INHOUDSOPGAVE

1. [Wat lost dit op?](#wat-lost-dit-op)
2. [Waarom niet meteen een duimpjes-systeem?](#waarom-niet-duimpjes)
3. [Fase 1: logging](#fase-1)
4. [Data structure — voorbeeld-JSONL](#data-structure)
5. [Fase 2: gewogen keuze](#fase-2)
6. [Eerlijkheid: wat dit wel/niet is](#eerlijkheid)
7. [Open vragen voor later](#open-vragen)

---

## WAT LOST DIT OP? {#wat-lost-dit-op}

Vandaag kiest `_kies_variant()` in `response_engine.py` (en de vergelijkbare `random.choice()`'s in `response_pipeline.py`'s fallback-sjablonen en `conversation_engine.py`'s observatie-openingen/afsluitingen) **gelijk verdeeld** tussen alle geschreven varianten. Elke variant heeft dus altijd exact dezelfde kans, ongeacht of die ene variant in de praktijk beter "landt" bij Kevin dan een andere.

Dit systeem wil die kansverdeling **bijsturen, niet vervangen**: nog steeds toeval, maar minder blind toeval — varianten die historisch beter ontvangen werden krijgen een iets hogere kans, zonder dat er ooit maar 1 vaste "beste" variant overblijft.

**Concreet doel:** als blijkt dat Kevin merkbaar positiever reageert na `"Ik ken '{entity}' als: {definition}"` dan na `"{entity}, dat is: {definition}"`, mag de eerste iets vaker gekozen worden — zonder de tweede ooit helemaal uit te sluiten.

---

## WAAROM NIET METEEN EEN DUIMPJES-SYSTEEM? {#waarom-niet-duimpjes}

Overwogen, bewust niet als eerste stap gekozen:

| | Kevin's reactie (microlearning-stijl) | Expliciete duim omhoog/omlaag |
|---|---|---|
| Vereist nieuwe UI/interactie? | Nee — hergebruikt bestaand sentiment-signaal | Ja — Nova draait via chat/terminal, geen duim-knop vandaag |
| Hergebruikt bestaande code? | Ja, `microlearning.py`'s classifier-aanpak | Nee, volledig nieuw mechanisme |
| Zuiverheid van het signaal | Ruizig (zie Eerlijkheid) | Zuiver, ondubbelzinnig |
| Moeite om te bouwen | Klein — vooral Fase 1's logging | Groter — nieuw invoerkanaal nodig |

Gekozen: eerst Fase 1 (logging) bouwen, ongeacht welk signaal later gebruikt wordt — dan pas Kevin's reactie als proxy (Fase 2), niet het duimpjes-systeem. Dat laatste blijft een mogelijke latere uitbreiding, geen vervanging.

---

## FASE 1: LOGGING (ZONDER OORDEEL) {#fase-1}

Elke keer `_kies_variant()` een keuze maakt, loggen we die keuze + de context waarin ze gemaakt werd — **zonder** meteen te beoordelen of het een goede keuze was. Zelfde soort append-only JSONL-bestand als `unmatched_intents.jsonl` en `insight_feedback.json` elders in Nova.

```python
event_bus.publish("variant_gekozen", {
    "sjabloon_naam": "definitie",
    "gekozen_variant_index": 2,
    "entity": "python",
    "personality_style": {"pace": "normaal", "tone": "warm", "interrupts": False, "dramatic": False},
    "response_style": "normaal",
    "moment": "2026-07-28T14:32:00"
})
```

Dit event wordt (net als `identity_state:updated`) automatisch opgepikt door `memory.py`'s wildcard-subscribe — **geen wijziging nodig in `memory.py` zelf**, enkel dit ene nieuwe event publiceren vanuit `_kies_variant()`.

**Belangrijk:** dit verandert niets aan het gedrag van Nova. `random.choice()` blijft exact zoals nu — dit is puur een observatie-laag ernaast, geen ingreep.

---

## DATA STRUCTURE — VOORBEELD-JSONL {#data-structure}

Ter referentie, zodat je meteen ziet hoe dit er in de praktijk uitziet zodra Fase 1 gebouwd is en een tijdje gedraaid heeft. Dit is **fictieve, illustratieve data** — geen echte Kevin-gegevens — puur om het formaat te tonen.

`data/variant_feedback.jsonl`:

```jsonl
{"sjabloon_naam": "definitie", "gekozen_variant_index": 0, "variant_tekst": "{entity} betekent: {definition}", "entity": "python", "personality_style": {"pace": "normaal", "tone": "warm", "interrupts": false, "dramatic": false}, "response_style": "normaal", "moment": "2026-07-28T09:12:03", "reactie_sentiment": null}
{"sjabloon_naam": "definitie", "gekozen_variant_index": 2, "variant_tekst": "Ik ken '{entity}' als: {definition}", "entity": "schaken", "personality_style": {"pace": "snel", "tone": "enthousiast", "interrupts": false, "dramatic": true}, "response_style": "uitgebreid", "moment": "2026-07-28T09:14:51", "reactie_sentiment": "positief"}
{"sjabloon_naam": "met_associatie", "gekozen_variant_index": 4, "variant_tekst": "Wat ik weet over '{entity}': {definition} Bij jou hoort daar meestal ook '{associatie}' bij.", "entity": "koffie", "personality_style": {"pace": "normaal", "tone": "warm", "interrupts": false, "dramatic": false}, "response_style": "normaal", "moment": "2026-07-28T09:20:17", "reactie_sentiment": "neutraal"}
{"sjabloon_naam": "onbekend", "gekozen_variant_index": 1, "variant_tekst": "Hmm, '{entity}' ken ik nog niet.", "entity": "kwantumfysica", "personality_style": {"pace": "normaal", "tone": "warm", "interrupts": false, "dramatic": false}, "response_style": "kort", "moment": "2026-07-28T09:25:40", "reactie_sentiment": null}
{"sjabloon_naam": "interruption_vraag", "gekozen_variant_index": 3, "variant_tekst": "Even een momentje?", "entity": null, "personality_style": {"pace": "normaal", "tone": "warm", "interrupts": true, "dramatic": false}, "response_style": "normaal", "moment": "2026-07-28T09:31:12", "reactie_sentiment": "negatief"}
```

**Toelichting bij de velden:**
- `gekozen_variant_index` — index in `self.templates[sjabloon_naam]`, zodat je later exact kan herleiden welke variant het was, ook als de tekst zelf ooit licht wijzigt.
- `variant_tekst` — de ongevulde sjabloon-string zelf, ter leesbaarheid (zodat je niet telkens in `response_engine.py` moet gaan opzoeken wat index 4 ook alweer was).
- `reactie_sentiment` — **bewust `null` in Fase 1**. Dit veld bestaat al in de structuur, maar wordt pas gevuld zodra Fase 2 gebouwd wordt en `microlearning.py`'s sentiment-signaal gekoppeld wordt aan het eerstvolgende Kevin-bericht na deze variant. Door het veld nu al te voorzien (ook al blijft het `null`), moet het JSONL-formaat later niet migreren — Fase 2 vult gewoon een bestaand veld in plaats van het schema te wijzigen.
- `entity: null` bij `interruption_vraag` — niet elk sjabloon-type gaat over een woord/definitie, dus dit veld is niet altijd van toepassing.

---

## FASE 2: GEWOGEN KEUZE {#fase-2}

Zodra Fase 1 een tijdje gedraaid heeft en er genoeg voorbeelden zijn (net als bij Layer 7's `_effectieve_drempel()` — pas zinvol na een minimum aantal observaties, geen vast getal vooraf, af te spreken met Kevin):

1. **Koppel Kevin's eerstvolgende reactie** (via `microlearning.py`'s bestaande sentiment-classifier) aan de laatst gelogde `variant_gekozen`-entry, en vul `reactie_sentiment` in (`"positief"` / `"neutraal"` / `"negatief"`).
2. **Klassiek classificatiemodel** (zelfde stijl als `microlearning.py` — TF-IDF + Logistic Regression, of eenvoudiger: een simpele gewogen-gemiddelde-score per variant-index) berekent per `(sjabloon_naam, variant_index)`-combinatie een score op basis van de verzamelde `reactie_sentiment`-waarden.
3. `_kies_variant()` gebruikt die scores als **gewichten** in `random.choices(varianten, weights=scores)` in plaats van gelijke kansen — nooit een gewicht van 0 (elke variant blijft altijd mogelijk, hoe klein de kans ook).

---

## EERLIJKHEID: WAT DIT WEL/NIET IS {#eerlijkheid}

**Wel:**
- 100% klassieke, uitlegbare statistiek/ML — zelfde soort model als `microlearning.py` al gebruikt, geen LLM, geen tekstgeneratie.
- Blijft **altijd toeval bevatten** — dit vervangt `random.choice()` door een gewogen variant ervan, nooit door een deterministische "altijd de beste variant"-keuze. Dat zou net het "geen woordenboek-gevoel"-doel van Fase 5 ongedaan maken.
- Kiest enkel tussen **al bestaande, door Kevin/Claude geschreven** varianten — er wordt nooit een nieuwe zin gegenereerd of samengesteld.

**Niet:**
- Geen garantie op een zuiver signaal. Kevin's reactie na een variant kan net zo goed door het onderwerp zelf komen (bv. blij omdat het over schaken gaat) als door de specifieke formulering — het label is een **proxy**, geen directe waarheid. Verwacht ruis, vooral bij weinig data.
- Geen vervanging voor Fase 5's variatie-doel — als de gewichten ooit te scheef zouden worden (bv. 1 variant met 90% kans), is dat een signaal om de spreiding te begrenzen (bv. een minimum-gewicht per variant instellen), niet om het systeem zijn gang te laten gaan.

---

## OPEN VRAGEN VOOR LATER {#open-vragen}

- Hoeveel voorbeelden per `(sjabloon_naam, variant_index)` zijn "genoeg" vóór Fase 2 een gewicht mag laten meespelen? (Vergelijkbaar met Layer 7's confidence-gates — af te spreken, geen vast getal hier al ingevuld.)
- Hoe voorkomen we dat een vroege toevalstreffer (bv. 1x toevallig positief) een variant al te veel bevoordeelt bij weinig data? Mogelijk: een minimum-aantal-observaties-drempel per variant, zelfde patroon als Layer 2's `MIN_OBSERVATIES_VOOR_ANOMALIE`.
- Moet `reactie_sentiment` het eerstvolgende Kevin-bericht nemen, of een venster van bv. de eerste 2 berichten erna? (Kevin kan soms pas in een tweede reactie iets laten blijken.)
- Dit document beschrijft dit enkel voor Layer 4's `_kies_variant()`. Zou hetzelfde ooit ook toegepast worden op `response_pipeline.py`'s fallback-sjablonen en `conversation_engine.py`'s observatie-varianten (consistentie, zie eerdere gespreksnotitie)? Nog niet beslist — apart te bespreken zodra Fase 1 hier werkt.
