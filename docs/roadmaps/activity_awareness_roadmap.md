# Activity Awareness Roadmap: activiteiten herkennen, correleren en proactief reageren

**Status:** Concept/idee, nog niet ingepland in bouwvolgorde
**Depends on:** intent_router.py ✅, pattern_matcher.py (Layer 2) ✅, memory_layer1_roadmap.md (PMI-principe, referentie)
**Gebruikt door:** Layer 4 (response_engine.py, nog te bouwen), eventueel health_monitor.py
**Datum:** 6 juli 2026

---

## INHOUDSOPGAVE

1. [Wat lost dit op?](#wat-lost-dit-op)
2. [Deel A: activiteiten herkennen via intent](#deel-a)
3. [Deel B: activiteiten herkennen via camera/scherm (ML als sensor)](#deel-b)
4. [Deel C: co-occurrence tussen activiteiten](#deel-c)
5. [Deel D: duur-detectie en proactieve pauze-suggestie](#deel-d)
6. [Web-lookup module (los onderwerp, zelfde sessie besproken)](#web-lookup)
7. [Fase-roadmap](#fase-roadmap)
8. [Eerlijkheid: wat kan wel/niet](#eerlijkheid)

---

## WAT LOST DIT OP? {#wat-lost-dit-op}

Kevin wil dat Nova op termijn dingen kan zeggen als:
- *"Je drinkt meestal koffie vlak voor het coderen"*
- *"Je bent al 90 minuten aan het coderen, tijd voor een pauze?"*

Dit vereist drie aparte, op zich haalbare bouwstenen: (1) weten dat een activiteit bezig is, (2) verbanden tussen activiteiten tellen, (3) duur bijhouden en drempelwaarden toepassen. Geen van deze drie vereist een LLM. Eén onderdeel (camera-detectie) vereist wel een extern ML-model als sensor.

---

## DEEL A: ACTIVITEITEN HERKENNEN VIA INTENT {#deel-a}

**100% symbolisch, geen ML.**

Kevin zegt: *"ik ga koffie drinken"* / *"ik ga coderen"* / *"ik ga netflix kijken"*

```
intent_router.py herkent GENERIEK patroon: "ik ga <activiteit>"
       ↓
extraheert <activiteit> als variabele (geen aparte module per activiteit nodig)
       ↓
publiceert: event_bus.publish("activity_started", {"naam": "<activiteit>", "tijd": ...})
       ↓
Layer 2 telt dit via haar bestaande generieke tel-mechanisme
```

Eén patroon volstaat voor onbeperkt veel activiteiten — vergelijkbaar met hoe `topic_detected:<naam>` werkt (zie `topic_events_roadmap.md`). Optioneel: een klein synoniemen-tabelletje (bv. "koffiezetten" → "koffie") voor variatie in taalgebruik, puur onderhoud van een lijst, geen nieuwe logica.

**Beperking:** dit werkt alleen voor activiteiten die Kevin **expliciet benoemt**. Activiteiten die hij niet uitspreekt, worden nooit geteld via dit pad.

---

## DEEL B: ACTIVITEITEN HERKENNEN VIA CAMERA/SCHERM (ML ALS SENSOR) {#deel-b}

Twee sub-onderdelen met een andere ML-status:

**Scherm-detectie (welk programma actief is): geen ML nodig**
Systeemaanroep (bv. via `psutil`) die de naam van het actieve venster/proces opvraagt. "VSCode.exe actief" → publiceer `activity_started` met naam "coderen". Puur symbolisch.

**Camera-detectie (wat er visueel te zien is): vereist een extern ML-model**
Objectherkenning ("kop koffie", "laptop") is een computer-vision taak — dit vereist een getraind classificatiemodel/object-detector, ingezet als **externe gespecialiseerde tool**, exact zoals Stockfish dat is voor schaken. Dit model:
- leert zelf niks meer bij tijdens gebruik (het is al elders getraind)
- geeft enkel een label terug ("koffie gedetecteerd")
- de vertaalslag "dit label = dit event-type" blijft door Kevin/de code expliciet vastgelegd, geen automatische betekenisgeving

**Privacy-kanttekening (belangrijk, geen technisch punt maar een ontwerp-punt):** camera/scherm-monitoring valt onder dezelfde zwaardere omkadering als de al geplande security-modules in `nova_modules_overview.md` (logging, consent-principes). Dit moet bewust ontworpen worden, niet als bijkomstigheid toegevoegd.

---

## DEEL C: CO-OCCURRENCE TUSSEN ACTIVITEITEN {#deel-c}

**100% pure statistiek, geen nieuw ML-model — zelfde principe als Layer 1's PMI-scoring, toegepast op events i.p.v. woorden.**

```json
{
  "co_occurrence": {
    "activity_coderen + activity_koffie": {
      "samen_binnen_30min": 47,
      "coderen_totaal": 52,
      "correlatie": 0.90
    }
  }
}
```

Telt hoe vaak twee event-types kort na elkaar voorkomen, gedeeld door hoe vaak het ene event op zich voorkomt. Nova kan dan zeggen "je drinkt meestal koffie vlak voor het coderen" — puur gebaseerd op een geteld getal, geen begrip van waarom.

---

## DEEL D: DUUR-DETECTIE EN PROACTIEVE PAUZE-SUGGESTIE {#deel-d}

**100% puur symbolisch — timer + drempelwaarde, geen statistiek zelfs nodig.**

```
activity_started ("coderen") → start_tijd opslaan
achtergrondtimer checkt elke X minuten: hoelang loopt dit al?
als (huidige_tijd - start_tijd) > drempelwaarde (bv. 90 min)
       → publiceer event: "pauze_suggestie"
       → response_engine.py kiest vast sjabloon:
         "Je bent al {duur} aan het coderen, tijd voor een pauze?"
```

Sluit aan bij het eerder besproken `health_monitor.py`-idee (timing bijhouden, drempelwaarden toepassen op modules) — hier toegepast op Kevin's eigen activiteiten in plaats van op Nova's modules.

---

## WEB-LOOKUP MODULE (LOS ONDERWERP, ZELFDE SESSIE BESPROKEN) {#web-lookup}

Apart concept, maar in dezelfde sessie besproken — hier voor de volledigheid meegenomen:

```
intent: "zoek <term>" / "google <term>" / "zoek regels van <spel>"
       ↓
intent_router.py extraheert <term> (generiek patroon, werkt voor élke term)
       ↓
web_lookup.py bouwt URL: google.com/search?q=<term>
       ↓
webbrowser.open(url) — opent zichtbaar venster op Kevin's scherm
       ↓
Nova antwoordt: "Ik heb het voor je opgezocht, kijk maar mee!"
```

100% symbolisch: geen interpretatie van zoekresultaten, Kevin beoordeelt zelf wat hij ziet. Moet wel **na** specifieke modules (weer, schaken) gecontroleerd worden in de intent-routing, als generiek vangnet — niet als eerste keuze.

---

## FASE-ROADMAP {#fase-roadmap}

| Fase | Omschrijving | ML nodig? | Geschat werk |
|---|---|---|---|
| 1 | Generiek "ik ga \<activiteit>"-patroon in intent_router.py | ❌ Nee | Klein |
| 2 | Layer 2 uitbreiden: `activity_started`-events meetellen (zelfde mechanisme als topic_detected) | ❌ Nee | Klein |
| 3 | web_lookup.py: generieke Google-zoekmodule | ❌ Nee | Klein |
| 4 | Scherm-detectie (actief programma via psutil) | ❌ Nee | Middel |
| 5 | Co-occurrence teller tussen twee event-types | ❌ Nee | Middel |
| 6 | Duur-timer + drempelwaarde + pauze-sjabloon | ❌ Nee | Klein — hangt af van Layer 4 voor het antwoord, kan los al gebouwd worden voor de detectie zelf |
| 7 | Camera-detectie (object/activiteit herkennen) | ✅ Ja — extern vision-model als tool | Groot — inclusief privacy/consent-ontwerp |

---

## EERLIJKHEID: WAT KAN WEL/NIET {#eerlijkheid}

- ✅ **Eén generiek intent-patroon voor onbeperkt veel activiteiten** — geen aparte module per activiteit
- ✅ **Scherm-detectie (welk programma actief is)** — pure systeemaanroep
- ✅ **Co-occurrence tussen activiteiten tellen** — pure statistiek, zelfde familie als Layer 1
- ✅ **Duur bijhouden en drempelwaarden toepassen** — pure timer-logica
- ✅ **web_lookup.py (browser openen op zoekterm)** — pure symbolische actie, geen interpretatie
- ✅ **Nova mag zeggen dát een patroon bestaat, nooit waarom** — zelfde principe als bij Layer 2's anomaly-detectie (geen verzonnen verklaringen)
- ⚠️ **Camera-detectie van objecten/activiteiten** — vereist een extern ML-model (vision classifier) als sensor, nooit als kern; het model "leert" niet meer bij, het levert enkel een label; de vertaling van dat label naar een event-naam blijft expliciet vastgelegde logica
- ❌ **Verwachten dat dit voor élke denkbare activiteit vanzelf werkt zonder dat Kevin het ooit benoemt of een detector ervoor bouwt** — elk nieuw type activiteit vereist ofwel een gesproken intent, ofwel een aparte detector (scherm/camera)
- ❌ **Nova zelf vrij laten interpreteren wat ze ziet/hoort** — elk label/event blijft een vaste, vooraf gedefinieerde categorie, geen open classificatie

**Status in de bouwvolgorde:** idee/concept, geen prioriteit. Fases 1-6 zijn onafhankelijk van elkaar en van Layer 4 al te bouwen/testen. Fase 7 (camera) is het grootste en gevoeligste onderdeel — apart te plannen, met privacy-ontwerp vooraf.
