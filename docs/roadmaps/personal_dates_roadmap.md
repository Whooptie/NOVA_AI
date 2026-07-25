# Persoonlijke Datums Roadmap: verjaardagen onthouden en herinneren

**Status:** Concept — nog niet gepland in bouwvolgorde
**Depends on:** intent_router.py ✅, modules/paths.py ✅
**Bouwt voort op:** date_calendar_roadmap.md (datumrekenen), weather.py's proactieve-melding-patroon, memory_user_preferences_roadmap.md (persoonlijke opslag)
**Datum:** 25 juli 2026

---

## INHOUDSOPGAVE

1. [Wat lost dit op?](#wat-lost-dit-op)
2. [Waarom dit apart van date_calendar_roadmap.md staat](#waarom-apart)
3. [Hoe werkt het?](#hoe-werkt-het)
4. [Proactief herinneren](#proactief)
5. [Data structure](#data-structure)
6. [API design](#api-design)
7. [Fase-roadmap](#fase-roadmap)
8. [Toekomstpad: echte agenda/kalender-integratie](#toekomstpad)
9. [Eerlijkheid: wat kan wel/niet](#eerlijkheid)

---

## WAT LOST DIT OP? {#wat-lost-dit-op}

```
Kevin: "Onthoud dat Jan zijn verjaardag op 14 maart is"
         ↓
intent_router.py heeft hier geen detect_*() voor
         ↓
Valt terug op fallback — Nova onthoudt dit niet
gestructureerd (hooguit ergens los in interactions.jsonl,
niet doorzoekbaar of bruikbaar voor een herinnering)
```

Dit document beschrijft een klein, eigen mechanisme waarmee Kevin persoonlijke, belangrijke datums aan Nova kan doorgeven — die ze vervolgens kan **opzoeken op vraag** én **proactief kan herinneren** wanneer de datum nadert.

---

## WAAROM DIT APART VAN date_calendar_roadmap.md STAAT {#waarom-apart}

Op het eerste gezicht lijkt dit een simpele uitbreiding van de kalender-roadmap (die gaat immers ook over datums). Toch is er een fundamenteel verschil dat een eigen document rechtvaardigt:

| | `date_calendar_roadmap.md` | Dit document |
|---|---|---|
| **Bron van de data** | Externe, algemeen geldige bronnen (Wikipedia, wiskundige formules, officiële feestdagen) | Kevin zelf, over zijn eigen leven/relaties |
| **Aard van de data** | Wereldkennis, voor iedereen hetzelfde | Persoonlijke, private informatie |
| **Waar hoort de opslag thuis?** | Algemene datastructuren (feestdagen.json, e.d.) | Persoonlijk, vergelijkbaar met een toekomstig `kevin_profile.json` (zie `memory_user_preferences_roadmap.md`) |
| **Toekomstperspectief** | Blijft standalone, symbolisch | Kan ooit gekoppeld worden aan een ECHTE externe agenda (Google Calendar e.d.) — dat is een heel ander soort integratie (authenticatie, sync, externe API) dan wat `date_calendar_roadmap.md` ooit nodig heeft |

**De doorslaggevende reden om dit apart te houden:** zodra je ooit een echte agenda/kalender wil koppelen (zie sectie 8), wordt dit document de plek waar die integratie thuishoort — niet de kalenderrekenkunde-roadmap, die puur symbolisch en zonder externe authenticatie blijft. Door nu al te scheiden, hoeft er later niets herschreven te worden, enkel uitgebreid.

---

## HOE WERKT HET? {#hoe-werkt-het}

### Opslaan

```
Kevin: "Onthoud dat Jan zijn verjaardag op 14 maart is"
         ↓
Nieuwe detect_persoonlijke_datum() in intent_router.py
herkent dit vaste patroon
         ↓
Slaat op in data/persoonlijke_datums.json:
   {"naam": "Jan", "type": "verjaardag", "datum": "03-14",
    "toegevoegd_op": "2026-07-25"}
         ↓
Nova: "Genoteerd! Jan is jarig op 14 maart."
```

### Opvragen (on-demand)

```
Kevin: "Wanneer is Jan zijn verjaardag?"
         ↓
detect_persoonlijke_datum_vraag() zoekt op in
persoonlijke_datums.json
         ↓
Nova: "14 maart" — of, met de datumrekenkunde uit
       date_calendar_roadmap.md gecombineerd:
       "14 maart, dat is over 42 dagen"
```

**Bewuste hergebruik-koppeling:** de "hoeveel dagen tot..."-berekening hoeft hier niet opnieuw gebouwd te worden — dit roept gewoon dezelfde `dagen_tot()`-functie aan die al in `date_calendar_roadmap.md` gepland staat, met de opgeslagen datum als input.

---

## PROACTIEF HERINNEREN {#proactief}

Dit is het onderdeel dat het meeste waarde toevoegt, en hergebruikt een patroon dat al **twee keer bewezen werkt** in Nova (`weather.py`'s proactieve weerwaarschuwing, `session_watcher.py`'s pauze-melding):

```
Een nieuwe check_verjaardagen() methode, aangeroepen
vanuit main.py's achtergrond_loop() (zelfde ritme-
patroon als de bestaande PRESENCE_CHECK_INTERVAL/
WEATHER_CHECK_INTERVAL-constantes, bv. 1x per dag)

├── Doorloopt persoonlijke_datums.json
├── Vergelijkt elke opgeslagen datum met vandaag
├── Bij een match binnen een instelbare marge
│   (bv. "vandaag" of "over 3 dagen"):
│   publiceert een `layer4_response`-event
│   ("Vergeet niet: Jan is over 3 dagen jarig!")
├── Zelfde spam-preventie-principe als weather.py's
│   "max 1x per dag"-check (een `laatst_herinnerd`-
│   veld per datum-entry, net als weather_history.json)
└── = Puur symbolisch: datum vergelijken, geen
      interpretatie nodig
```

```
Kevin: (typt niets, Nova neemt zelf het initiatief)
         ↓
Nova: "Vergeet niet: Jan is over 3 dagen jarig
       (14 maart)!"
```

**Instelbare herinnerings-marge:** net zoals bij weerwaarschuwingen kan dit configureerbaar zijn (bv. standaard 3 dagen vooraf + op de dag zelf), zodat Kevin niet overspoeld wordt maar ook niet vergeet.

---

## DATA STRUCTURE

### data/persoonlijke_datums.json

```json
{
  "datums": [
    {
      "id": "jan-verjaardag",
      "naam": "Jan",
      "type": "verjaardag",
      "datum": "03-14",
      "toegevoegd_op": "2026-07-25",
      "laatst_herinnerd": null
    },
    {
      "id": "trouwdag-ouders",
      "naam": "mama en papa",
      "type": "trouwdag",
      "datum": "06-02",
      "toegevoegd_op": "2026-07-25",
      "laatst_herinnerd": "2027-05-30"
    }
  ],
  "instellingen": {
    "herinner_dagen_vooraf": 3,
    "herinner_op_de_dag_zelf": true
  }
}
```

Via `modules/paths.py`'s `get_project_root()`, zelfde patroon als `weather_history.json`. Bewust een **eigen bestand**, niet `concepts.json` (dat is voor algemene wereldkennis) en niet `interactions.jsonl` (dat is ruwe, ongestructureerde logging — hier is een doorzoekbare, gestructureerde lijst nodig).

**Waarom een `type`-veld (verjaardag/trouwdag/andere) in plaats van enkel verjaardagen:** dit houdt de structuur meteen generiek genoeg voor andere terugkerende, persoonlijke datums (jubilea, gedenkdagen) zonder dat de architectuur later aangepast moet worden — dezelfde soort generieke aanpak als het `vraag_type`-veld in `pending_question_roadmap.md`.

---

## API DESIGN

```python
persoonlijke_datums = PersoonlijkeDatumsModule(event_bus, sem)

# Opslaan
persoonlijke_datums.voeg_toe("Jan", "verjaardag", "03-14")

# Opvragen
persoonlijke_datums.zoek("Jan")
# → {"datum": "03-14", "type": "verjaardag"}

# Alle datums binnen een venster (voor de proactieve check)
persoonlijke_datums.komende_datums(dagen_vooruit=3)
# → [{"naam": "Jan", "datum": "03-14", "dagen_tot": 3}]

# Proactieve achtergrondcheck (aangeroepen vanuit main.py)
persoonlijke_datums.check_verjaardagen()
```

---

## FASE-ROADMAP {#fase-roadmap}

| Fase | Omschrijving | Nieuw t.o.v. bestaand patroon? |
|---|---|---|
| 1 | `persoonlijke_datums.json` opzetten + basale opslag/opvraag-functies | Nieuw, klein — vergelijkbaar met elk ander eigen data-bestand |
| 2 | `detect_persoonlijke_datum()` + `detect_persoonlijke_datum_vraag()` in intent_router.py (vaste zinsvormen) | Nieuw, klein |
| 3 | Koppeling met `date_calendar_roadmap.md`'s `dagen_tot()`-functie voor "over hoeveel dagen"-antwoorden | Hergebruik, geen nieuwe rekenlogica |
| 4 | Proactieve `check_verjaardagen()`, aangeroepen vanuit `achtergrond_loop()` | Hergebruikt exact het bewezen patroon van `weather.py`/`session_watcher.py` |
| 5 | Publiceren via `layer4_response` (tone-pipeline) | Hergebruikt het bestaande, gevestigde patroon |
| 6 (optioneel, later) | Uitbreiding met meer zinsvarianten voor het toevoegen/opvragen, eventueel via de geplande `intent_classifier` | Optioneel — zelfde beperking als overal elders: vaste zinsvormen werken meteen, varianten vereisen uitbreiding |

**Afhankelijkheden:** geen van de nog te bouwen memory-lagen nodig. Fase 3 leunt op `date_calendar_roadmap.md`'s rekenfuncties, maar kan ook zonder (dan toont Nova gewoon de datum zelf, zonder "over hoeveel dagen"-berekening).

---

## TOEKOMSTPAD: ECHTE AGENDA/KALENDER-INTEGRATIE {#toekomstpad}

Kevin noemde expliciet de wens om Nova later toegang te geven tot een echte, externe agenda (bv. Google Calendar). Dit is **een fundamenteel ander soort project** dan wat hierboven beschreven staat, en verdient een eerlijke vooruitblik zodat de verwachting correct blijft.

```
WAT DIT DOCUMENT NU BESCHRIJFT:
├── Een eigen, lokaal JSON-bestand
├── Kevin voert handmatig datums in via een zin
├── Geen externe authenticatie, geen sync
└── = Volledig binnen Nova's bestaande, lokale,
      privacy-first architectuur

WAT ECHTE AGENDA-INTEGRATIE ZOU VEREISEN:
├── OAuth-authenticatie met een externe dienst
│   (Google/Microsoft/...) — een heel nieuw soort
│   "vertrouwde toegang" dat Nova nu nergens anders
│   heeft
├── Een sync-mechanisme (wat als Kevin iets in de
│   ECHTE agenda wijzigt — hoe/wanneer merkt Nova dat?)
├── Leesrechten vs. schrijfrechten — mag Nova ZELF
│   afspraken toevoegen? Dat raakt weer het
│   toestemmingsprincipe: elke schrijf-actie zou
│   altijd eerst bevestiging moeten vragen, nooit
│   automatisch een externe agenda wijzigen
├── Privacy-overweging: een externe agenda-koppeling
│   is de EERSTE plek waar Nova's "local first"-
│   principe een bewuste uitzondering zou moeten
│   maken (data verlaat, voor het ophalen, wel
│   Kevin's eigen machine — richting Google's servers,
│   niet omgekeerd)
└── = Dit is GEEN kleine uitbreiding van dit document,
      maar een eigen, toekomstig project met een eigen
      roadmap, wanneer Kevin dat wil oppakken
```

**Aanbeveling:** bouw eerst dit document (lokaal, simpel, 100% symbolisch, geen externe afhankelijkheid) — dat is meteen bruikbaar en oefent het juiste patroon (opslaan + proactief herinneren). Een echte agenda-koppeling kan daar later, als apart project, bovenop komen — de `persoonlijke_datums.json`-structuur zou dan zelfs kunnen dienen als lokale "cache" van wat er uit de externe agenda gehaald is, zodat de proactieve-herinnering-logica (Fase 4) niet opnieuw gebouwd hoeft te worden.

---

## EERLIJKHEID: WAT KAN WEL/NIET {#eerlijkheid}

- ✅ **Een datum onthouden die Kevin expliciet doorgeeft** — pure opslag, geen interpretatie
- ✅ **Op vraag die datum teruggeven, eventueel met dagen-tot-berekening** — hergebruik van bestaande, symbolische datumrekenkunde
- ✅ **Proactief herinneren op vaste, ingestelde momenten** — hergebruikt het bewezen `weather.py`/`session_watcher.py`-patroon, puur datumvergelijking
- ❌ **Elke mogelijke manier herkennen waarop Kevin een datum zou kunnen doorgeven** — net als overal elders werken vaste, voorziene zinsvormen het beste; nieuwe varianten vereisen uitbreiding van `intent_router.py` of, later, de geplande intent-classifier
- ❌ **Een echte externe agenda lezen/schrijven** — dat is bewust buiten de scope van dit document; zie sectie 8 voor waarom dat een eigen, toekomstig project is
- ❌ **Zelf beslissen om iets aan een externe agenda toe te voegen zonder bevestiging** — mocht Fase 8+ (agenda-integratie) er ooit komen, blijft het toestemmingsprincipe onverkort gelden: Nova stelt voor, Kevin bevestigt, pas dan wordt er geschreven

**Status in de bouwvolgorde:** onafhankelijk, kan op elk moment gebouwd worden — vereist geen van de nog te bouwen memory-lagen. Logisch te combineren met `date_calendar_roadmap.md` (Fase 1, datumrekenen) voor de "over hoeveel dagen"-functionaliteit, maar niet strikt afhankelijk daarvan.

---

## RELATIE TOT ANDERE DOCUMENTEN

```
persoonlijke_datums (dit document)
├── Hergebruikt datumrekenkunde van: date_calendar_roadmap.md
│   (Fase 1, dagen_tot()) — geen dubbele logica
├── Hergebruikt het proactieve-melding-patroon van:
│   weather.py (achtergrond_loop-check + spam-preventie)
│   en session_watcher.py
├── Sluit qua persoonlijke-opslag-filosofie aan bij:
│   memory_user_preferences_roadmap.md (Kevin's eigen
│   gegevens, apart van concepts.json/wereldkennis)
└── Is de aangewezen plek voor een toekomstig, apart
    project: echte agenda/kalender-integratie (OAuth,
    sync, lees/schrijfrechten) — zie sectie 8
```

---

**Status:** PLANNING — nog niet gebouwd
**Auteur:** Claude + Kevin
