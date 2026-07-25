# News Roadmap: nieuws ophalen, symbolisch filteren op relevantie, duplicaat-detectie

**Status:** Concept — nog niet gepland in bouwvolgorde
**Depends on:** intent_router.py ✅, modules/paths.py ✅ (voor data-bestand-locatie, zelfde patroon als weather.py)
**Geïnspireerd op:** weather.py's on-demand + proactieve architectuur (al gebouwd, bewezen patroon)
**Datum:** 25 juli 2026

---

## INHOUDSOPGAVE

1. [Wat lost dit op?](#wat-lost-dit-op)
2. [Belangrijk: twee totaal verschillende vragen](#twee-vragen)
3. [Waarom "wat doet ertoe" niet symbolisch te begrijpen is](#waarom-niet-symbolisch)
4. [De 4 haalbare heuristieken](#vier-heuristieken)
5. [On-demand, zoals weather.py](#on-demand)
6. [Opgeslagen nieuws + duplicaat-detectie](#duplicaat-detectie)
7. [Data structure](#data-structure)
8. [API design](#api-design)
9. [Fase-roadmap](#fase-roadmap)
10. [Eerlijkheid: wat kan wel/niet](#eerlijkheid)

---

## WAT LOST DIT OP? {#wat-lost-dit-op}

```
Kevin: "Wat is het laatste nieuws?"
         ↓
intent_router.py heeft geen detect_*() hiervoor
         ↓
Valt terug op fallback
         ↓
= Geen enkele nieuwsfunctie bestaat op dit moment
```

Dit document beschrijft een `news.py`-module die, net als `weather.py`, **op vraag** actueel nieuws ophaalt — met een symbolische, eerlijk-begrensde manier om te filteren op wat waarschijnlijk relevant is, en met geheugen zodat een herhaalde vraag zonder nieuwe ontwikkelingen niet gewoon dezelfde lijst opnieuw dumpt.

---

## BELANGRIJK: TWEE TOTAAL VERSCHILLENDE VRAGEN {#twee-vragen}

Bij het bespreken van dit idee bleek er aanvankelijk verwarring mogelijk tussen twee heel verschillende interpretaties van "goed nieuws":

```
❌ NIET dit document:
"Wat was het laatste goede nieuws dat IK je verteld heb?"
(bv. Kevin zei ooit "ik kreeg een promotie!")
→ Dat is een vraag over Nova's EIGEN GEHEUGEN
  (Layer 0, memory.py) — persoonlijke interacties
  terugvinden en tonen, geen externe bron nodig

✅ WEL dit document:
"Wat is het laatste nieuws uit de wereld dat
 ertoe doet?"
→ Dit vereist een EXTERNE bron (nieuws-API/RSS)
  én een manier om te filteren op relevantie
```

Dit document behandelt uitsluitend de tweede interpretatie: **echt, extern wereldnieuws**.

---

## WAAROM "WAT DOET ERTOE" NIET SYMBOLISCH TE BEGRIJPEN IS {#waarom-niet-symbolisch}

Dit is de kern-eerlijkheidsvraag van dit hele document, en verdient het om vooraf helder te staan.

```
❌ WAT NIET HAALBAAR IS:
Nova die ZELF, inhoudelijk, een nieuwsartikel leest
en oordeelt "dit is belangrijk omdat..."
→ Dat vereist begrip van de WERELD, van context,
  van gevolgen — precies het soort interpretatie
  waar een taalmodel voor gemaakt is, en wat
  Nova's symbolische kern bewust niet doet

Symbolische AI kan TELLEN, FILTEREN en MATCHEN.
Ze kan niet WEGEN of een gebeurtenis "ertoe doet"
in de volle, menselijke betekenis van dat woord.
```

Om dit toch bruikbaar te maken, wordt relevantie benaderd via **heuristieken** — telbare, symbolische signalen die vaak (niet altijd) samenvallen met wat mensen belangrijk nieuws noemen. Dat is een **proxy**, geen begrip.

---

## DE 4 HAALBARE HEURISTIEKEN {#vier-heuristieken}

```
OPTIE 1: Categorie-filter (Kevin bepaalt, niet Nova)
├── Kevin geeft expliciet op welke categorieën hem
│   interesseren (bv. technologie, wetenschap, AI)
├── De meeste nieuws-API's/RSS-feeds leveren
│   categorieën standaard mee
├── Nova toont enkel wat binnen die categorieën valt
└── = 100% symbolisch, Kevin's eigen keuze, geen
      oordeel van Nova nodig

OPTIE 2: Plaatsing/positie als proxy
├── Het eerst geplaatste artikel op een nieuwssite/
│   RSS-feed staat daar meestal niet toevallig
├── Puur een TELBAAR gegeven (positie in de lijst),
│   geen interpretatie van de inhoud
└── = Symbolische heuristiek voor "waarschijnlijk
      prominent", geen garantie voor "belangrijk"

OPTIE 3: Frequentie over meerdere bronnen
├── Als hetzelfde onderwerp bij meerdere,
│   onafhankelijke nieuwsbronnen tegelijk
│   opduikt, is dat een signaal van bredere
│   relevantie
├── Simpele matching op gedeelde kernwoorden
│   tussen kopjes van verschillende feeds
└── = Telbaar, wiskundig signaal, geen
      inhoudelijk oordeel

OPTIE 4: Kevin's eigen interessepatroon (Layer 1/7)
├── Layer 1 (word_associations, al gebouwd):
│   welke woorden komen vaak terug in wat Kevin
│   interessant vond?
├── Layer 7 (emergence, nog te bouwen): "Kevin
│   toont vaak interesse in AI-gerelateerd nieuws"
├── Filter nieuwe kopjes op overlap met die
│   bekende interesse-woorden
└── = 100% symbolisch (woord-matching/telling),
      maar vereist dat Layer 1/7 al voldoende
      geschiedenis hebben opgebouwd — pas
      bruikbaar op langere termijn
```

**Praktisch voorstel:** start met Optie 1 (categorie-filter, meteen bruikbaar) + Optie 2/3 (plaatsing/frequentie, ook meteen bruikbaar zonder geschiedenis nodig). Optie 4 kan er later bijkomen zodra Layer 1/7 voldoende data hebben — geen blokkerende afhankelijkheid, wel een logische toekomstige verfijning.

---

## ON-DEMAND, ZOALS weather.py {#on-demand}

Kevin heeft expliciet gevraagd om dit **net als het weer** te laten werken: alleen wanneer erom gevraagd wordt, geen constante achtergrond-polling.

```
Kevin: "Wat is het laatste nieuws?"
         ↓
intent_router.py herkent dit (nieuw detect_news_query())
         ↓
news.py haalt op dat moment de actuele feed op
         ↓
Filtert via de heuristieken hierboven
         ↓
Toont een kort overzicht (bv. top 3, kopjes + bron)
         ↓
Slaat op WAT er getoond is (zie volgende sectie)
```

**Bewust géén proactieve achtergrond-melding** (in tegenstelling tot `weather.py`'s optionele proactieve waarschuwing bij noodweer) — nieuws heeft niet dezelfde "veiligheid, dus mag ongevraagd spreken"-rechtvaardiging die bij weerwaarschuwingen wél gold. Dit blijft dus zuiver on-demand, tenzij je dat later alsnog anders zou willen.

---

## OPGESLAGEN NIEUWS + DUPLICAAT-DETECTIE {#duplicaat-detectie}

Kevins tweede wens: als hij 's middags opnieuw vraagt en er is niets nieuws bijgekomen, moet Nova dat gewoon zeggen in plaats van dezelfde lijst te herhalen — met een aanbod om het oude nieuws opnieuw te horen als hij dat wil.

```
Kevin (9u): "Wat is het laatste nieuws?"
Nova: [haalt op, filtert, toont top 3]
      [slaat de getoonde kopjes op in news_history.json,
       met tijdstip]

Kevin (13u): "Wat is het laatste nieuws?"
         ↓
news.py haalt opnieuw de actuele feed op
         ↓
Vergelijkt de nieuwe kopjes met wat er al in
news_history.json staat (op kopje-tekst of een
unieke ID uit de RSS/API, zelfde soort aanpak
als weather.py's "al gemeld vandaag"-check)
         ↓
GEEN nieuwe kopjes gevonden?
├── Nova: "Geen nieuw nieuws sinds vanmorgen.
│          Wil je de eerdere updates opnieuw horen?"
└── Bij bevestiging: toont de opgeslagen kopjes
    opnieuw (uit news_history.json, geen nieuwe
    API-call nodig)

WEL nieuwe kopjes gevonden?
├── Nova toont enkel de NIEUWE items
└── Update news_history.json
```

**Belangrijke, eerlijke nuance:** dit is puur **string/ID-matching** tussen wat er al opgeslagen stond en wat de feed nu teruggeeft — geen inhoudelijk begrip van "is dit hetzelfde nieuws in andere woorden". Als een nieuwssite een kopje licht herformuleert, zou dat foutief als "nieuw" gezien kunnen worden. Dat is een aanvaardbare, symbolische beperking (zelfde soort beperking als bij de hagel-detectie in `weather.py` — een eerlijke grens van de aanpak, geen bug).

---

## DATA STRUCTURE

### data/news_history.json

```json
{
  "laatste_update": "2026-07-25T09:03:12",
  "getoonde_items": [
    {
      "titel": "Doorbraak in fusietechnologie aangekondigd",
      "bron": "NOS",
      "categorie": "wetenschap",
      "eerste_keer_getoond": "2026-07-25T09:03:12",
      "id": "nos-a83f2c"
    },
    {
      "titel": "Nieuwe AI-verordening treedt in werking",
      "bron": "VRT",
      "categorie": "technologie",
      "eerste_keer_getoond": "2026-07-25T09:03:12",
      "id": "vrt-19d40b"
    }
  ]
}
```

Zelfde soort bestand als `weather_history.json` — via `modules/paths.py`'s `get_project_root()`, geen hardcoded pad.

---

## API DESIGN

```python
news = NewsModule(event_bus, config)

# Haalt op, filtert, vergelijkt met geschiedenis
resultaat = news.get_latest(categorieën=["technologie", "wetenschap"])
# → {
#     "nieuwe_items": [...],
#     "heeft_nieuws": True/False
#   }

# Bij "geen nieuw nieuws" + bevestiging:
eerdere_items = news.get_history_items()
```

---

## FASE-ROADMAP {#fase-roadmap}

| Fase | Omschrijving | Nieuw t.o.v. bestaand patroon? |
|---|---|---|
| 1 | Nieuwsbron kiezen (RSS-feeds NOS/VRT, of een gratis nieuws-API) + basaal ophalen | Nieuw, maar puur data ophalen zoals `weather.py`'s API-call |
| 2 | Categorie-filter (Optie 1) — Kevin geeft voorkeurscategorieën op | Nieuw, klein — vergelijkbaar met een instelbaar voorkeursveld |
| 3 | Plaatsing + frequentie-heuristiek (Optie 2+3) | Nieuw, kleine, symbolische telling |
| 4 | `detect_news_query()` in `intent_router.py`, on-demand afhandeling | Hergebruikt exact het patroon van `weather.py`'s bestaande intent-koppeling |
| 5 | `news_history.json` + duplicaat-detectie + "geen nieuw nieuws sinds..."-antwoord | Hergebruikt `weather_history.json`'s "al gemeld vandaag"-aanpak, en `modules/paths.py` voor het pad |
| 6 | "Wil je de eerdere updates opnieuw horen?" — koppeling met `pending_question_roadmap.md` | Hergebruikt het generieke pending-question-mechanisme (zie dat document) i.p.v. een eigen ad-hoc ja/nee-afhandeling |
| 7 (later, optioneel) | Optie 4 — koppeling met Layer 1 (word_associations) en Layer 7 (emergence) voor persoonlijke relevantie-verfijning | Afhankelijk van voldoende opgebouwde geschiedenis in die lagen |

**Afhankelijkheden:** Fase 1-6 vereisen geen van de nog te bouwen memory-lagen — volledig op zichzelf staand, net als `weather.py`. Fase 7 is een latere, optionele verfijning zodra Layer 1/7 voldoende rijp zijn.

---

## EERLIJKHEID: WAT KAN WEL/NIET {#eerlijkheid}

- ✅ **Nieuws ophalen via RSS/API** — pure data, geen ML, geen interpretatie
- ✅ **Filteren op Kevin's expliciet opgegeven categorieën** — Kevin's keuze, geen oordeel van Nova
- ✅ **Plaatsing/frequentie als symbolische proxy voor "waarschijnlijk prominent"** — telbaar, geen begrip
- ✅ **Onthouden wat al getoond is, en "geen nieuw nieuws" melden bij een herhaalde vraag** — pure opslag + string/ID-matching, zelfde patroon als `weather_history.json`
- ✅ **Op vraag opnieuw de eerder getoonde items tonen** — puur ophalen uit eigen opslag, geen nieuwe interpretatie
- ❌ **Nova die zelf inhoudelijk oordeelt of iets "ertoe doet"** — dit blijft altijd een proxy/heuristiek, nooit een echt begrip van belang
- ❌ **Perfecte duplicaat-detectie bij herformuleerde kopjes** — een eerlijke, symbolische beperking (string-matching, geen semantisch begrip van "hetzelfde nieuws in andere woorden")
- ❌ **Proactief, ongevraagd nieuws melden** — bewust anders dan `weather.py`'s noodweer-uitzondering; dit blijft zuiver on-demand tenzij je dat expliciet zou willen heroverwegen

**Status in de bouwvolgorde:** onafhankelijk, kan op elk moment gebouwd worden — vereist geen van de nog te bouwen lagen voor Fase 1-6. Bouwt voort op twee al bewezen patronen: `weather.py`'s on-demand/geschiedenis-aanpak, en (optioneel, Fase 6) de generieke `pending_question_roadmap.md`.

---

## RELATIE TOT ANDERE DOCUMENTEN

```
news (dit document)
├── Hergebruikt de architectuur van: weather.py
│   (on-demand + geschiedenis-bestand + modules/paths.py)
├── Kan gekoppeld worden aan: pending_question_roadmap.md
│   (voor de "wil je de eerdere updates opnieuw horen?"-vraag)
├── Optionele latere verfijning via: memory_layer1_roadmap.md
│   (word_associations) en memory_layer7_roadmap.md (emergence)
└── Is GEEN vervanging van: een vraag naar Nova's EIGEN
    geheugen ("wat was het laatste goede nieuws dat ik
    je vertelde") — dat zou een aparte, veel eenvoudigere
    Layer 0-opzoeking zijn, geen externe bron nodig
```

---

**Status:** PLANNING — nog niet gebouwd
**Auteur:** Claude + Kevin
