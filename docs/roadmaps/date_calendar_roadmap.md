# Datum & Kalender Roadmap: feestdagen, vakanties, datumrekenen, historische datums

**Status:** Concept — nog niet gepland in bouwvolgorde
**Depends on:** intent_router.py ✅, modules/paths.py ✅
**Aansluiting:** publiceert via `layer4_response` (zelfde patroon als weather.py/time.py/math.py — spreektalige tekst, gaat door de tone-pipeline)
**Datum:** 25 juli 2026

---

## INHOUDSOPGAVE

1. [Wat lost dit op?](#wat-lost-dit-op)
2. [Overzicht: wat is puur symbolisch, wat niet](#overzicht)
3. [Onderdeel 1: datumrekenen (100% symbolisch)](#datumrekenen)
4. [Onderdeel 2: feestdagen (100% symbolisch)](#feestdagen)
5. [Onderdeel 3: schoolvakanties (100% symbolisch, met een kanttekening)](#vakanties)
6. [Onderdeel 4: historische datums via Wikipedia On This Day API](#historische-datums)
7. [Onderdeel 5: "wil je erover lezen?" + automatisch openen in browser](#lees-flow)
8. [Data structure](#data-structure)
9. [API design](#api-design)
10. [Fase-roadmap](#fase-roadmap)
11. [Eerlijkheid: samenvatting](#eerlijkheid)

---

## WAT LOST DIT OP? {#wat-lost-dit-op}

```
Kevin: "Hoeveel dagen tot kerst?"
Kevin: "Wanneer is Pasen dit jaar?"
Kevin: "Is het morgen een feestdag?"
Kevin: "Wat gebeurde er op deze dag in de geschiedenis?"
         ↓
intent_router.py heeft hier geen detect_*() voor
         ↓
Valt terug op fallback
         ↓
= Nova kan momenteel geen enkele datum-gerelateerde
  vraag beantwoorden, ook al heeft ze al wel time.py
  (huidige datum/tijd) en math.py (rekenkundige basis)
```

---

## OVERZICHT: WAT IS PUUR SYMBOLISCH, WAT NIET {#overzicht}

Dit is, in tegenstelling tot het nieuws-onderwerp van hiervoor, **grotendeels een goed-nieuws-verhaal**:

```
✅ Datumrekenen (dagen tussen data, dag van de week, ...)
   → PURE WISKUNDE — Python's ingebouwde datetime-module
   
✅ Feestdagen (Kerst, Pasen, Nieuwjaar, ...)
   → VASTE REGELS/FORMULES — geen interpretatie nodig,
     zelfs bewegende feestdagen zoals Pasen volgen een
     exacte, wiskundige formule (bekend sinds eeuwen)

✅ Schoolvakanties (België)
   → VASTE, JAARLIJKS GEPUBLICEERDE DATA — een tabel,
     geen berekening, maar wel 100% symbolisch (opzoeken,
     niet interpreteren)

✅ Historische datums / "wat gebeurde er op deze dag"
   → OOK HAALBAAR — via Wikipedia's officiële "On This
     Day" REST API (gratis, geen API-key), hetzelfde
     principe als de bestaande wikipedia_teacher.py:
     een externe bron RAADPLEGEN en TONEN, geen eigen
     redenering. Zie sectie 4 hieronder voor de details
     en de ene praktische kanttekening die hierbij hoort.
```

---

## ONDERDEEL 1: DATUMREKENEN {#datumrekenen}

100% haalbaar, met Python's ingebouwde `datetime`-module — geen externe bron nodig.

```python
Kevin: "Hoeveel dagen tot kerst?"
Kevin: "Welke dag van de week is 15 augustus?"
Kevin: "Hoeveel weken geleden was 1 januari?"
Kevin: "Wat is de datum over 100 dagen?"
```

```
Alles hierboven is PURE REKENKUNDE op datums:
├── datetime.date.today() → vandaag
├── (doeldatum - vandaag).days → aantal dagen
├── .weekday() / .strftime("%A") → dag van de week
├── timedelta(days=N) → datum optellen/aftrekken
└── = Geen enkele ML/interpretatie nodig, dit is
      exact hetzelfde soort taak als math.py al doet
```

Sluit qua stijl perfect aan bij `math.py` (dat al temperatuurconversies en eenheden doet) — dit is in essentie "eenheden-conversie", maar dan voor datums.

---

## ONDERDEEL 2: FEESTDAGEN {#feestdagen}

Ook 100% symbolisch, in twee soorten:

```
VASTE feestdagen (elk jaar dezelfde datum):
├── Nieuwjaar (1 januari)
├── Kerst (25 december)
├── Nationale feestdag België (21 juli)
├── Sinterklaas (6 december, niet officieel maar
│   wel cultureel relevant)
└── = Simpele opzoektabel, geen berekening nodig

BEWEGENDE feestdagen (datum verschilt per jaar,
maar volgt een EXACTE, gekende formule):
├── Pasen — berekend via het "computus"-algoritme
│   (een eeuwenoude, wiskundige formule, geen
│   interpretatie, gewoon een reeks berekeningen)
├── Hemelvaart = Pasen + 39 dagen
├── Pinksteren = Pasen + 49 dagen
├── Carnaval = Pasen - 47 dagen
└── = Ook dit is 100% deterministisch — dezelfde
      input (jaartal) geeft altijd exact dezelfde,
      correcte uitkomst
```

**Belangrijk:** dit is geen "voorspelling" of "schatting" — de Paasformule is exact en wiskundig bewezen correct voor elk jaar. Dit hoort dus volledig thuis in de categorie "berekenen", niet "interpreteren".

---

## ONDERDEEL 3: SCHOOLVAKANTIES {#vakanties}

100% symbolisch, met één praktische kanttekening.

```
✅ WAT SYMBOLISCH KAN:
Belgische schoolvakanties volgen een vaste STRUCTUUR
(herfstvakantie, kerstvakantie, krokusvakantie,
paasvakantie, zomervakantie) met exacte data die
jaarlijks door de overheid gepubliceerd worden

⚠️ PRAKTISCHE KANTTEKENING:
In tegenstelling tot Pasen (een formule) zijn
schoolvakantie-data GEEN berekening — het zijn
politieke/administratieve BESLISSINGEN die elk
jaar opnieuw vastgelegd worden. Dit vereist dus:
├── OFWEL een jaarlijkse, handmatige update van
│   een tabel (Kevin vult 1x per jaar de nieuwe
│   data in, net zoals je nu al bij weather.py's
│   instellingen doet)
├── OFWEL het ophalen van een officiële bron
│   (bv. de Vlaamse overheid publiceert dit als
│   open data) — dit zou puur data ophalen zijn,
│   geen interpretatie, dus nog steeds symbolisch,
│   maar wel een externe afhankelijkheid (zoals
│   weather.py's API)
└── Beide opties zijn 100% symbolisch — het verschil
    is enkel WAAR de data vandaan komt, niet HOE
    Nova ermee omgaat
```

**Aanbeveling:** start met een handmatig bij te werken tabel (simpelst, geen externe afhankelijkheid), met de optie om dit later te automatiseren via een officiële bron zodra dat de moeite waard blijkt.

---

## ONDERDEEL 4: HISTORISCHE DATUMS VIA WIKIPEDIA ON THIS DAY API {#historische-datums}

**Bijgewerkt 25 juli 2026** — dit onderdeel gebruikte oorspronkelijk het idee van een eenmalige, door Claude samengestelde statische lijst (zoals bij het termenlijst-idee voor wiskunde/fysica/AI-definities). Bij nader opzoeken bleek er een betere, officiële bron te bestaan die dat overbodig maakt.

```
✅ ER BESTAAT EEN GRATIS, OFFICIËLE API HIERVOOR:

Wikipedia's "On This Day" REST API
(en.wikipedia.org/api/rest_v1/feed/onthisday)

├── Gratis, geen API-key nodig
├── Onderhouden door duizenden Wikipedia-vrijwilligers,
│   continu bijgewerkt en geverifieerd — geen eenmalige,
│   "bevroren" lijst zoals het oorspronkelijke idee
├── Geeft voor elke kalenderdag (maand+dag): gebeurtenissen,
│   geboortes, sterfgevallen, gegroepeerd per jaar
├── Elke gebeurtenis bevat een LINK naar het bijhorende
│   Wikipedia-artikel — direct bruikbaar voor Onderdeel 5
│   hieronder
└── = Exact hetzelfde principe als de al bestaande
      wikipedia_teacher.py: een externe bron RAADPLEGEN
      en het antwoord TONEN, geen eigen redenering
      over wat "interessant" is — dat oordeel ligt al
      besloten in wat Wikipedia's vrijwilligers ooit
      aan de lijst toevoegden, Nova voegt daar zelf
      niets aan toe of af (behalve eventueel de eerste
      N resultaten selecteren, zie Fase-roadmap)
```

**Waarom dit beter is dan de oorspronkelijke statische-lijst-aanpak:**

```
OUD IDEE (eenmalige lijst door Claude samengesteld):
├── Beperkt tot wat ik op één moment kon verzinnen
├── "Bevriest" — wordt nooit vanzelf up-to-date
├── Foutgevoeliger (uit geheugen, niet geverifieerd)
└── Extra werk: een JSON-bestand met ~365 dagen invullen

NIEUW (Wikipedia On This Day API):
├── Levend, continu bijgewerkt door de Wikipedia-
│   gemeenschap zelf
├── Geen eenmalig invulwerk nodig
├── Bevat automatisch links naar volledige artikelen
└── Zelfde architecturale patroon als de al bestaande,
    bewezen wikipedia_teacher.py
```

**Eén praktische kanttekening, eerlijk vermeld:**

```
⚠️ De API is primair Engelstalig van aard
   (en.wikipedia.org). Er bestaat ook een Nederlandse
   Wikipedia-variant, maar die heeft historisch gezien
   minder complete "on this day"-data dan de Engelse.
   
   Praktisch gevolg: de gebeurtenissen die Nova toont
   zullen doorgaans in het Engels zijn (de titel/omschrijving
   komt rechtstreeks uit de API), tenzij er gekozen wordt
   voor de Nederlandse feed met het risico op minder of
   soms lege resultaten voor bepaalde dagen.
   
   Dit is een eerlijke, praktische databron-beperking —
   geen architecturaal probleem, vergelijkbaar met de
   al gedocumenteerde hagel-detectie-beperking in
   weather.py (grens van de gratis databron, niet
   symbolisch op te lossen).
```

---

## ONDERDEEL 5: "WIL JE ERVER LEZEN?" + AUTOMATISCH OPENEN IN BROWSER {#lees-flow}

Na het tonen van een historische gebeurtenis (of feestdag-uitleg) kan Nova aanbieden om de volledige Wikipedia-pagina te openen — met **keuze-ondersteuning** als er meerdere gebeurtenissen getoond zijn, niet enkel een simpele ja/nee.

```
Kevin: "Wat gebeurde er op 25 juli in de geschiedenis?"
         ↓
Nova roept de Wikipedia On This Day API aan, toont
bijvoorbeeld de top 3 gebeurtenissen:
         ↓
Nova: "In 1978 werd Louise Brown geboren, de eerste
       'reageerbuisbaby'. In 1943 viel Mussolini in
       Italië. In 2000 stortte een Concorde neer bij
       Parijs. Wil je over één hiervan lezen? Zeg
       'de eerste', 'de tweede', 'de derde', of 'nee'."
         ↓
pending_question.set("open_wiki_pagina", 
                      opties=[url1, url2, url3],
                      verval_seconden=120)
         ↓
Kevin: "de eerste"  (of: "ja", "de tweede", "nee", ...)
         ↓
intent_router checkt: is er een pending_question?
   → JA → signal_classifier / een kleine, uitgebreide
     keuzeherkenning bepaalt WELKE optie bedoeld is
     (of een simpele "nee")
         ↓
pending_question:answered event, met de gekozen index
(of geen keuze bij "nee")
         ↓
Een listener in de datum-module opent de bijhorende URL:
   webbrowser.open(gekozen_url)
         ↓
Nova: "Geopend!" (korte, symbolische bevestiging)
```

**Waarom dit een uitbreiding van `pending_question_roadmap.md` is, geen vervanging:**

```
pending_question_roadmap.md beschrijft oorspronkelijk
een BINAIRE afhandeling (bevestiging/irritatie/neutraal,
via de bestaande signal_classifier — gericht op korte
ja/nee-achtige reacties).

Dit scenario (Optie 3, "direct de robuuste variant")
vraagt om een KEUZE UIT MEERDERE opties, niet enkel
ja/nee. Dat betekent:
├── Het `vraag_type`-veld blijft hetzelfde generieke
│   mechanisme (geen nieuwe architectuur)
├── MAAR de afhandeling bij een openstaande vraag van
│   dit type moet, naast de signal_classifier, ook
│   kunnen herkennen: "de eerste" / "optie 2" / "die
│   laatste" / een uitgesproken jaartal uit de lijst
├── Dit is een KLEINE, aanvullende, symbolische
│   patroonherkenning (ordinaal-woorden + eventueel
│   het genoemde jaartal matchen tegen de opties-lijst
│   die in de pending_question zelf is opgeslagen) —
│   geen nieuw ML-model nodig, wel een uitbreiding van
│   pending_question.py's databronveld (een `opties`-lijst
│   naast het bestaande `vraag_type`/`verval_seconden`)
└── Bij geen duidelijke match: Nova vraagt kort door
    ("Welke bedoel je precies?") in plaats van te gokken
```

**Wat er wél 100% symbolisch en direct haalbaar is, zonder verdere twijfel:**

```
✅ webbrowser.open(url) — Python's ingebouwde module,
   geen extra package nodig, werkt cross-platform
   (Windows/Mac/Linux)
✅ De URL komt rechtstreeks uit de Wikipedia On This Day
   API-respons — geen aparte zoekactie nodig
✅ Dit raakt rechtstreeks het bestaande toestemmings-
   principe uit nova_state.md ("nooit handelen zonder
   toestemming van Kevin") — een browser openen is een
   systeemactie, Nova vraagt dus altijd eerst, precies
   zoals het hoort
```

**Belangrijke kanttekening — dit is een aanname vanuit de HUIDIGE, lokale situatie:**

```
⚠️ webbrowser.open(url) opent de browser op de machine
   waar Nova's eigen Python-proces draait — niet op
   "een" apparaat in het algemeen, maar specifiek DIE
   machine.

   NU (Nova draait lokaal op Kevin's laptop):
   ├── Nova's proces = Kevin's laptop = waar hij zit
   └── = Werkt vanzelf correct, geen extra stap nodig

   LATER (mocht Nova ooit headless draaien, zoals
   client_server_control_roadmap.md beschrijft):
   ├── Nova's brein zou dan op een APARTE server draaien
   ├── webbrowser.open() zou dan een browser proberen
   │   te openen OP DIE SERVER — niet op Kevin's laptop
   │   waar hij feitelijk naar kijkt
   └── = Zou dan NIET meer werken zoals bedoeld

Dit is exact dezelfde soort aanname als bij "Plex
openen" of "Spotify starten" (zie client_server_
control_roadmap.md, Deel A: laptop bedienen) — mocht
de client-server-architectuur ooit gebouwd worden,
hoort deze actie daar dan ook door te lopen: via
event_bus.publish("laptop:open_url", {"url": ...}),
afgehandeld door de laptop-client, in plaats van
rechtstreeks vanuit Nova's kern-proces. Geen
architecturaal probleem nu, wel iets om NIET te
vergeten als die stap ooit gezet wordt.
```

---

## DATA STRUCTURE

### data/feestdagen.json

```json
{
  "vaste_feestdagen": [
    {"datum": "01-01", "naam": "Nieuwjaar"},
    {"datum": "07-21", "naam": "Nationale feestdag"},
    {"datum": "12-25", "naam": "Kerstmis"}
  ],
  "beweeglijke_feestdagen_formules": [
    {"naam": "Pasen", "berekening": "computus"},
    {"naam": "Hemelvaart", "offset_dagen_na_pasen": 39},
    {"naam": "Pinksteren", "offset_dagen_na_pasen": 49}
  ]
}
```

### data/schoolvakanties.json

```json
{
  "schooljaar_2026_2027": {
    "herfstvakantie": {"start": "2026-10-31", "einde": "2026-11-08"},
    "kerstvakantie": {"start": "2026-12-26", "einde": "2027-01-10"},
    "krokusvakantie": {"start": "2027-02-13", "einde": "2027-02-21"}
  }
}
```

### data/onthisday_cache.json (optioneel, geen bron-bestand)

Geen statische bron meer nodig — de data komt live van de Wikipedia On This Day API. Een lichte, optionele cache (zelfde soort idee als `weather_history.json`) kan wel zinnig zijn om herhaalde vragen op dezelfde dag niet telkens opnieuw te hoeven ophalen:

```json
{
  "07-25": {
    "opgehaald_op": "2026-07-25T09:03:12",
    "gebeurtenissen": [
      {"jaar": 1978, "tekst": "Louise Brown, the first 'test-tube baby', is born", "url": "https://en.wikipedia.org/wiki/Louise_Brown"}
    ]
  }
}
```

De pending_question die hierbij hoort (Onderdeel 5) slaat de aangeboden `opties` (lijst van URL's) tijdelijk, in-memory op — zelfde principe als `pending_question_roadmap.md` al beschrijft, hier enkel uitgebreid met een `opties`-veld naast het bestaande `vraag_type`.

Alle bestanden via `modules/paths.py`'s `get_project_root()`, zelfde patroon als `weather_history.json`.

---

## API DESIGN

```python
kalender = KalenderModule(event_bus, sem)

kalender.dagen_tot("2026-12-25")
# → 153

kalender.dag_van_de_week("2027-08-15")
# → "zondag"

kalender.is_feestdag("2026-12-25")
# → {"is_feestdag": True, "naam": "Kerstmis"}

kalender.bereken_pasen(2027)
# → date(2027, 3, 28)

kalender.huidige_vakantie()
# → {"in_vakantie": True, "naam": "krokusvakantie", "einde": "..."}

kalender.historische_gebeurtenissen("07-25")
# → live opgehaald via Wikipedia On This Day API
#   [{"jaar": 1978, "tekst": "...", "url": "https://..."}]
#   (optioneel eerst gecached resultaat van vandaag herbruikt)

kalender.open_pagina_voor_optie(gekozen_index, opties_lijst)
# → webbrowser.open(opties_lijst[gekozen_index]["url"])
```

---

## FASE-ROADMAP {#fase-roadmap}

| Fase | Omschrijving | ML nodig? | Nieuw t.o.v. bestaand patroon? |
|---|---|---|---|
| 1 | Basaal datumrekenen (dagen tussen data, dag van de week, optellen/aftrekken) — puur `datetime` | ❌ Nee | Sluit aan bij math.py's stijl |
| 2 | Vaste feestdagen (opzoektabel) + `detect_feestdag_query()` in intent_router.py | ❌ Nee | Nieuw, klein |
| 3 | Bewegende feestdagen (Pasen-formule + afgeleiden) | ❌ Nee | Nieuw, wiskundige formule |
| 4 | Schoolvakanties — handmatige jaarlijkse tabel | ❌ Nee | Zelfde onderhoudspatroon als een instelbaar voorkeursveld |
| 5 | Publiceren via `layer4_response` (tone-pipeline) | ❌ Nee | Hergebruikt exact het bestaande, gevestigde patroon van weather/time/math |
| 6 | Historische datums — live via Wikipedia On This Day API (`en.wikipedia.org/api/rest_v1/feed/onthisday`) | ❌ Nee (puur data ophalen) | Hergebruikt exact het bestaande patroon van `wikipedia_teacher.py` |
| 7 (optioneel, later) | Schoolvakanties automatisch verversen via een officiële open-databron i.p.v. handmatige tabel | ❌ Nee (puur data ophalen) | Zelfde patroon als weather.py's API-aanroep |
| 8 | "Wil je erover lezen?" — keuze-ondersteunende pending_question (Onderdeel 5) + `webbrowser.open()` bij bevestiging | ❌ Nee | Uitbreiding van `pending_question_roadmap.md` met een `opties`-veld; browser openen is een directe, symbolische systeemactie |

**Afhankelijkheden:** geen van de nog te bouwen memory-lagen nodig — volledig op zichzelf staand, zoals `math.py` en `weather.py`.

---

## EERLIJKHEID: SAMENVATTING {#eerlijkheid}

- ✅ **Datumrekenen** — 100% wiskunde, geen enkele beperking
- ✅ **Feestdagen (vast én bewegend)** — 100% deterministische formules, geen interpretatie
- ✅ **Schoolvakanties** — 100% symbolisch, met de praktische kanttekening dat de brondata jaarlijks bijgewerkt moet worden (handmatig of via een externe bron), net zoals bij elk ander "vaste tabel"-gegeven
- ✅ **Historische datums via de Wikipedia On This Day API** — puur een externe, gratis, community-onderhouden bron raadplegen en tonen, exact hetzelfde principe als de al bestaande `wikipedia_teacher.py`
- ✅ **Aanbieden om een pagina te openen + dit ook echt doen na bevestiging** — `webbrowser.open()` is een directe, symbolische systeemactie; de vraag vooraf sluit aan bij het bestaande toestemmingsprincipe
- ❌ **Nova die zelf, buiten wat de API teruggeeft, oordeelt welke gebeurtenissen "interessant genoeg" zijn** — de selectie van wélke gebeurtenissen ooit aan Wikipedia's lijst zijn toegevoegd, is door de Wikipedia-gemeenschap gedaan, niet door Nova; Nova kiest hooguit de eerste N resultaten uit die al bestaande lijst
- ❌ **Garanderen dat de Engelstalige feed altijd een Nederlandstalig, volledig antwoord geeft** — een eerlijke, praktische databron-beperking (zie Onderdeel 4), geen architecturaal probleem

**Status in de bouwvolgorde:** onafhankelijk, kan op elk moment gebouwd worden. Fase 1-6 (datumrekenen + feestdagen + vakanties + historische datums via de API) vereisen geen van de nog te bouwen memory-lagen. Fase 8 (de vraag+browser-flow) hergebruikt en breidt `pending_question_roadmap.md` licht uit — logisch te bouwen ná dat mechanisme, of samen ermee.

---

## RELATIE TOT ANDERE DOCUMENTEN

```
Datum & kalender (dit document)
├── Hergebruikt de architectuur van: math.py (rekenstijl)
│   en weather.py (layer4_response, geschiedenis-bestand,
│   modules/paths.py)
├── Fase 6 (historische datums) hergebruikt exact het
│   patroon van: wikipedia_teacher.py — een gratis,
│   community-onderhouden externe bron raadplegen en
│   tonen, geen eenmalige statische data meer nodig
├── Fase 8 (vraag + browser openen) breidt uit op:
│   pending_question_roadmap.md — hetzelfde generieke
│   mechanisme, met een extra `opties`-veld voor
│   keuze-uit-meerdere i.p.v. enkel ja/nee
├── Deelt dezelfde "lokale situatie"-aanname als:
│   client_server_control_roadmap.md's Deel A (laptop
│   bedienen) — webbrowser.open() gaat er, net als
│   "Plex openen", van uit dat Nova's proces en Kevin's
│   scherm hetzelfde apparaat zijn; zou bij een
│   toekomstige headless/client-server-opzet via de
│   laptop-client moeten lopen in plaats van rechtstreeks
└── Deelt hetzelfde eerlijkheidsprincipe als news_roadmap.md:
    opzoeken/berekenen mag altijd, een "oordeel over
    relevantie" moet ofwel vooraf door een mens/gemeenschap
    vastgelegd zijn (zoals bij Wikipedia's vrijwilligers),
    ofwel via een symbolische heuristiek benaderd worden
```

---

**Status:** PLANNING — nog niet gebouwd
**Auteur:** Claude + Kevin
