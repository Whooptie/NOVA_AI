# Smart Home Roadmap: X-Sense, Dreame, Samsung Smart TV

**Status:** Concept/idee, verre toekomst — geen prioriteit, niet ingepland in bouwvolgorde
**Depends on:** event_bus.py ✅ (verder losstaand van bestaande architectuur)
**Gebruikt door:** eventueel response_engine.py (Layer 4) voor meldingen/waarschuwingen aan Kevin
**Datum:** 10 juli 2026

---

## INHOUDSOPGAVE

1. [Wat lost dit op?](#wat-lost-dit-op)
2. [Waarom geen Home Assistant](#waarom-geen-ha)
3. [Deel A: X-Sense (SBS50 rookmelders)](#deel-a)
4. [Deel B: Dreame (robotstofzuiger)](#deel-b)
5. [Deel C: Samsung Smart TV](#deel-c)
6. [Gemeenschappelijk patroon: hoe zo'n module in Nova past](#patroon)
7. [Verhuizing naar 24/7-pc](#verhuizing)
8. [Fase-roadmap](#fase-roadmap)
9. [Eerlijkheid: wat kan wel/niet](#eerlijkheid)

---

## WAT LOST DIT OP? {#wat-lost-dit-op}

Kevin heeft thuis drie smart-apparaten die hij graag met Nova wil koppelen:
- **X-Sense rookmelders** (met SBS50-basisstation) — Nova moet kunnen waarschuwen bij rook-/CO-alarm
- **Dreame robotstofzuiger** — status/voortgang, eventueel starten/stoppen
- **Samsung Smart TV** — status opvragen, eventueel bediening

Geen van deze drie vereist een LLM of generatief model. Het is in essentie hetzelfde patroon als `weather.py`: een externe API/protocol aanspreken, het antwoord vertalen naar een EventBus-event, en Nova laten reageren volgens vaste logica.

---

## WAAROM GEEN HOME ASSISTANT {#waarom-ha}

Home Assistant is vooral krachtig omdat het **honderden kant-en-klare protocol-vertalers** meelevert voor alle mogelijke merken. Dat zelf nabouwen voor "alle apparaten die ooit zouden kunnen bestaan" is geen AI-probleem — het is gewoon massaal herhaald vertaalwerk per merk, en dat is een project van jaren.

Kevin heeft dat niet nodig: hij heeft precies **drie** merken in huis. Daarvoor is geen tussenlaag nodig — elk apparaat wordt gewoon een eigen, kleine Nova-module die rechtstreeks met dát ene apparaat praat. Geen Home Assistant, geen extra laag om te onderhouden.

---

## DEEL A: X-SENSE (SBS50 ROOKMELDERS) {#deel-a}

**100% symbolisch, geen ML.**

**Aard van de API:** X-Sense heeft **geen officiële, publieke developer-API**. Toegang loopt via:
- de onofficiële/gereverse-engineerde app-cloud-API, of
- een door de community geschreven Home-Assistant-component (bv. het `ha-xsense-component`-project op GitHub) die dat werk al heeft uitgezocht

**Belangrijke eerlijkheidsnoot:** omdat dit geen officiële, gedocumenteerde API is, kan X-Sense dit op elk moment laten breken bij een firmware- of app-update, zonder aankondiging. Dit is dus **brozer** dan bijvoorbeeld `weather.py` (dat een stabiele, officiële API gebruikt).

```
X-Sense SBS50-basisstation (rook/CO-alarm)
       ↓ (onofficiële cloud-API of community-component)
xsense.py polling/luistert op alarmstatus
       ↓
event_bus.publish("smoke_alarm_detected", {"locatie": "...", "type": "rook/CO", "tijd": ...})
       ↓
response_engine.py kiest vast, hoge-prioriteit sjabloon:
  "🚨 Rookmelder in de keuken geeft alarm!"
```

**Twee toegangsroutes, in volgorde van voorkeur:**
1. Zelf de bestaande community-component (Elwinmage/ha-xsense-component of vergelijkbaar) als referentie gebruiken om te zien welke endpoints/protocollen werken, en dat rechtstreeks in een eigen `xsense.py` overnemen — geen Home Assistant nodig als draaiende dependency.
2. Als dat te broos/onduidelijk blijkt: alsnog een kleine, headless Home Assistant-instantie enkel voor X-Sense laten draaien, en Nova daarmee laten praten via HA's eigen lokale REST/WebSocket-API (die wél stabiel en gedocumenteerd is). Dit is een fallback, geen eerste keuze.

---

## DEEL B: DREAME (ROBOTSTOFZUIGER) {#deel-b}

**100% symbolisch, geen ML.**

Vergelijkbaar verhaal als X-Sense: geen officiële developer-API, maar wel al uitgezocht door de community (bestaande Home Assistant-integraties voor Dreame-toestellen bestaan en zijn een goed startpunt om te zien welke velden/commando's beschikbaar zijn).

```
Dreame-cloud-API (onofficieel, community-uitgezocht)
       ↓
dreame_vacuum.py haalt status op (schoonmaken/leeg/vol/vastgelopen) of stuurt commando
       ↓
event_bus.publish("vacuum_status_changed", {"status": "...", "tijd": ...})
       ↓
Nova kan op vraag status geven, of proactief melden bij "vastgelopen"
```

**Eerlijkheidsnoot:** zelfde kwetsbaarheid als X-Sense — onofficiële API, kan breken bij updates. Verder puur EventBus-werk, geen andere complexiteit.

---

## DEEL C: SAMSUNG SMART TV {#deel-c}

**100% symbolisch, geen ML. Dit is de gunstigste van de drie.**

Samsung Smart TV's (2016 en later) bieden een **lokale WebSocket-API**, rechtstreeks op het thuisnetwerk — geen cloud-afhankelijkheid, geen reverse-engineering nodig. Er bestaan stabiele, onderhouden Python-libraries hiervoor (bv. `samsungtvws`).

```
Samsung Smart TV (lokaal WebSocket-endpoint op eigen netwerk)
       ↓
samsung_tv.py (via samsungtvws-library)
       ↓
event_bus.publish("tv_status_changed", {"status": "aan/uit", "app": "...", "tijd": ...})
       ↓
Nova kan status opvragen of (met toestemming) commando's sturen (aan/uit, volume, app starten)
```

**Waarom dit makkelijker is:** geen cloud, geen onofficiële API, geen risico dat een externe partij de toegang morgen dichttimmert — het draait allemaal lokaal op Kevin's eigen netwerk.

---

## GEMEENSCHAPPELIJK PATROON: HOE ZO'N MODULE IN NOVA PAST {#patroon}

Alle drie volgen exact hetzelfde patroon als bestaande modules zoals `weather.py`:

```
modules/
└── smart_home/
    ├── xsense.py
    ├── dreame_vacuum.py
    └── samsung_tv.py
```

- Elke module is verantwoordelijk voor **communicatie met precies één apparaat/merk**
- Elke module vertaalt externe status naar een EventBus-event — nooit directe logica in andere modules
- `intent_router.py` krijgt eventueel nieuwe `detect_*`-methodes (bv. "is de rookmelder oké?", "hoe ver staat de stofzuiger?") — **vergeet niet** de vaste stap `self._emit_topic("<naam>")` toe te voegen vlak voor `return True`, anders telt Layer 2 dit onderwerp niet mee (zie architectuurprincipes in `nova_state.md`)
- API-keys/tokens altijd via `.env` + `python-dotenv`, nooit hardcoded (zie bug #1 in `nova_state.md` — dezelfde fout niet herhalen)
- Geen enkele architecturale wijziging aan Layer 0-7 nodig — dit zijn losstaande, aanvullende modules

---

## VERHUIZING NAAR 24/7-PC {#verhuizing}

Dit sluit aan bij Kevin's plan om Nova ooit van laptop naar een altijd-aan pc te verhuizen (zie `nova_state.md`, bug #2 — portable pad al opgelost via `Path(__file__)`).

Als deze smart-home-modules er ooit komen, is de verhuizing het logische moment om ze meteen daar te laten draaien:
- Rookmelder-, stofzuiger- en tv-monitoring hebben sowieso een **altijd-actieve daemon** nodig om events op tijd te kunnen opvangen — een laptop die soms dicht gaat is daar ongeschikt voor
- Geen aparte planning nodig: dit volgt vanzelf uit "Nova draait 24/7 op de nieuwe machine", geen extra stap

---

## FASE-ROADMAP {#fase-roadmap}

| Fase | Omschrijving | ML nodig? | API-stabiliteit | Geschat werk |
|---|---|---|---|---|
| 1 | Samsung Smart TV module (lokale WebSocket-API) | ❌ Nee | 🟢 Stabiel, lokaal | Klein-Middel |
| 2 | X-Sense module (via community-component als referentie) | ❌ Nee | 🟡 Onofficieel, kan breken | Middel |
| 3 | Dreame-module (via community-integraties als referentie) | ❌ Nee | 🟡 Onofficieel, kan breken | Middel |
| 4 | `intent_router.py` uitbreiden met status-vragen per apparaat + `_emit_topic()` | ❌ Nee | — | Klein |
| 5 | Proactieve meldingen (bv. rookalarm → direct melden, ongevraagd) via response_engine.py | ❌ Nee | — | Klein — hangt af van Layer 4-personality-pipeline voor nette formulering |

**Aanbevolen volgorde:** Samsung TV eerst (makkelijkst, stabielste API, goede leeroefening voor het patroon), dan X-Sense (hoogste veiligheidswaarde — rookmelder), dan Dreame (laagste urgentie).

---

## EERLIJKHEID: WAT KAN WEL/NIET {#eerlijkheid}

- ✅ **Alle drie volledig haalbaar met pure symbolische Python** — geen ML/LLM nodig, gewoon API's aanspreken en events vertalen
- ✅ **Samsung TV: stabiele, lokale, officieel ondersteunde library** — laagste risico van de drie
- ✅ **Geen Home Assistant nodig** — voor drie specifieke merken is een eigen module per apparaat eenvoudiger dan een hele HA-installatie onderhouden
- ✅ **Past zonder wijziging in bestaande architectuur** — gewoon nieuwe modules + EventBus-events, geen impact op Layer 0-7
- ⚠️ **X-Sense en Dreame leunen op onofficiële/community-uitgezochte API's** — geen garantie dat dit blijft werken bij toekomstige firmware-updates van die fabrikanten; dit is een risico dat inherent bij het apparaat hoort, niet iets wat Nova's code kan oplossen
- ⚠️ **Als de onofficiële routes te onstabiel blijken:** een headless Home Assistant-instantie enkel voor X-Sense/Dreame is een geldige fallback — dan praat Nova met HA's stabiele lokale API in plaats van rechtstreeks met de fabrikant
- ❌ **Dit "vanzelf" laten meegroeien naar andere merken/apparaten** — elk nieuw apparaat vereist een eigen, apart uitgezochte module; er is geen generiek "smart home"-patroon dat automatisch nieuwe merken oppikt

**Status in de bouwvolgorde:** concept voor de verre toekomst, geen prioriteit. Losstaand van Layer 5/6/7-werk en van de huidige bugtabel — kan op eender welk moment als zij-project opgepakt worden zonder iets bestaands te breken.
