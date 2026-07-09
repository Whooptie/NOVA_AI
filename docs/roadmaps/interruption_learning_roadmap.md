# Activity-Aware Interaction Roadmap: leren wanneer/hoe/wat Nova rond een activiteit mag zeggen

**Status:** Concept — nog niet ingepland in bouwvolgorde
**Depends on:** Activity Awareness Deel A (activity_started-events), Layer 2 (pattern_matcher.py, tel-mechanisme), Layer 5 (Context Manager, gebruikt de uitkomst). Deel 4 (contextuele suggesties) hangt bovendien af van Activity Awareness Deel C en, voor "alledaagse" acties, van een aparte sensor/integratie-laag (zie Deel 4).
**Gebruikt door:** Layer 4 (response_engine.py) — kiest sjabloon op basis van confidence
**Datum:** 9 juli 2026

---

## OVERZICHT: VIER APARTE STUKKEN

Dit document behandelt vier vragen die elk apart opgelost moeten worden, en die samen bepalen hoe "activiteit-bewust" Nova aanvoelt:

| Deel | Vraag die het beantwoordt |
|---|---|
| 1. Interruption learning | **Of/wanneer** Nova mag spreken tijdens een activiteit |
| 2. Variatie in formulering | **Hoe** ze het formuleert, zodat het niet elke keer identiek klinkt |
| 3. Generiek per activiteit | Werkt dit voor **élke** activiteit, niet enkel "coderen"? |
| 4. Contextuele suggesties tussen activiteiten | **Wélke suggestie** ze doet, gekoppeld aan wat er meestal bij een specifieke activiteit hoort (bv. Plex → lichten dimmen) |

Deel 1-3 kunnen samen gebouwd worden als één samenhangend systeem. Deel 4 is een apart, groter stuk met een eigen afhankelijkheid (zie verderop) en kan later/los ingepland worden.

---

## INHOUDSOPGAVE

1. [Wat lost dit op?](#wat-lost-dit-op)
2. [Waarom geen Layer 1, geen user_preferences.py?](#waarom-apart)
3. [Hoe werkt het?](#hoe-werkt-het)
4. [Data structure](#data-structure)
5. [API design](#api-design)
6. [Fase-roadmap](#fase-roadmap)
7. [Voorbeeldscenario (Kevin, 9 juli 2026)](#voorbeeldscenario)
8. [Eerlijkheid: wat kan wel/niet symbolisch](#eerlijkheid)
9. [Deel 4: contextuele suggesties tussen activiteiten](#deel-4)

---

## WAT LOST DIT OP? {#wat-lost-dit-op}

Kevin wil dat Nova na verloop van tijd zelf aanvoelt — puur op basis van geteld gedrag, niet op basis van een vaste regel — of ze mag storen tijdens een activiteit zoals coderen. Concreet:

```
Eerste keren:
Kevin: "ik ga coderen"
Nova: "Ok, ik laat je focussen."
--10-20 min later--
Nova: "Mag ik storen?"
Kevin: "Ja"
Nova: ...

Na een aantal keren (patroon is duidelijk geworden):
Kevin: "ik ga coderen"
Nova: "Ok, veel plezier!"
Nova: "Lukt het? Kan ik helpen?"
```

Dit is geen feit dat Kevin ooit met zoveel woorden zegt ("ik vind het niet erg als je stoort") — het is een **patroon dat blijkt uit herhaald ja/nee-gedrag**. Dat onderscheidt dit van user_preferences.py (zie verder).

---

## WAAROM APART, EN GEEN LAYER 1 / USER_PREFERENCES.PY? {#waarom-apart}

| | Layer 1 (word associations) | user_preferences.py | Deze module |
|---|---|---|---|
| Wat het opslaat | statistisch verband tussen woorden | expliciet benoemd feit ("ik hou van koffie") | statistisch verband tussen **actie en toestemming** |
| Herkomst | automatisch, uit tekst | expliciet gezegd of `onthoud:`-commando | automatisch, uit herhaald ja/nee-antwoord op Nova's eigen vraag |
| Vorm | gewicht/score tussen woorden | vaste ja/nee-lookup per woord | oplopende ratio/confidence per (activiteit, moment) |
| Zekerheid nodig vóór gebruik | n.v.t., wordt als signaal gebruikt | direct bruikbaar, geen opbouwtijd | pas bruikbaar na genoeg observaties (zie Fase-roadmap) |

Dit is dus qua **techniek** het dichtst verwant aan Layer 2 (`pattern_matcher.py`) — timing/frequentie tellen — maar dan toegepast op een nieuw soort event: niet "wanneer gebeurt X", maar "werd storen tijdens X toegestaan of geweigerd".

**Belangrijk:** user_preferences.py blijft relevant als **shortcut ernaast**. Zegt Kevin ooit expliciet `onthoud: stoor me niet tijdens het coderen`, dan overruled dat meteen de statistische ratio — Nova hoeft dan niet eerst 20 keer te "leren", het feit staat al vast. De twee systemen werken samen, vervangen elkaar niet.

---

## HOE WERKT HET? {#hoe-werkt-het}

### Stap 1: nieuw event bij elke interruption-poging

Wanneer Nova een "mag ik storen?"-vraag stelt (of ongevraagd iets zegt tijdens een lopende activiteit) en Kevin reageert, wordt dat vastgelegd:

```python
event_bus.publish("interruption_feedback", {
    "activiteit": "coderen",
    "toegestaan": True,       # of False
    "tijd_sinds_start": 15,   # minuten sinds activity_started
    "moment": "2026-07-09T14:32:00"
})
```

Dit event bestaat nergens nog — het is de kernuitbreiding die deze roadmap toevoegt.

### Stap 2: tellen (zelfde familie als Layer 2)

```
"interruption_feedback" voor activiteit "coderen"
       ↓
tel per activiteit: totaal_pogingen, aantal_toegestaan
       ↓
confidence = aantal_toegestaan / totaal_pogingen
```

Optioneel verfijnder: apart tellen per tijdsvenster (bv. "binnen 20 min na start" vs. "na 20 min"), zodat Nova ook leert wanneer binnen de activiteit ze beter wacht. Dit is puur additief, geen vereiste voor Fase 1-3.

### Stap 3: sjabloonkeuze in Layer 4

```
confidence(storen_ok, "coderen") = 0.85  (17 van 20 keer ok)
   → "Ok, veel plezier!" + direct: "Lukt het? Kan ik helpen?"

confidence(storen_ok, "coderen") = 0.15  (3 van 20 keer ok)
   → enkel: "Ok, ik laat je focussen."
   → wacht drempelwaarde (bv. 15-20 min) → dan pas: "Mag ik storen?"

onvoldoende observaties (bv. < 5 pogingen)
   → val terug op voorzichtig gedrag: altijd eerst vragen
```

Dit blijft **vaste sjabloonkeuze op basis van een drempelwaarde** — geen generatie, geen LLM. Nova "verzint" niets; ze kiest uit een vooraf bepaalde set zinnen op basis van een geteld getal.

### Stap 4: variatie in formulering

Zonder extra maatregel zou Nova élke keer letterlijk dezelfde zin gebruiken ("Mag ik storen?"), wat mechanisch aanvoelt naarmate het vaker gebeurt. Oplossing: een kleine set vaste varianten per situatie, waaruit willekeurig gekozen wordt — zelfde aanpak als `expression_injector.py` nu al gebruikt voor emoji/gebaren-variatie.

```python
STOOR_VRAGEN = [
    "Mag ik storen?",
    "Heb je even?",
    "Stoor ik als ik nu iets zeg?",
    "Even een momentje?",
]

STOOR_TOEGESTAAN_VERVOLG = [
    "Lukt het? Kan ik helpen?",
    "Hoe gaat het ermee?",
    "Alles onder controle?",
]
```

Dit is nog steeds **100% symbolisch**: `random.choice()` uit een vaste lijst, geen tekstgeneratie. Het lost een ander probleem op dan de confidence-score:
- **Confidence-score** → bepaalt *of* en *wanneer* Nova iets zegt
- **Variatie in formulering** → bepaalt dat het niet elke keer *letterlijk hetzelfde zinnetje* is

Beide zijn nodig om het scenario niet mechanisch te laten aanvoelen.

---

## DATA STRUCTURE

```json
{
  "interruption_patterns": {
    "coderen": {
      "totaal_pogingen": 20,
      "aantal_toegestaan": 17,
      "confidence": 0.85,
      "laatst_bijgewerkt": "2026-07-09T14:32:00"
    },
    "gamen": {
      "totaal_pogingen": 6,
      "aantal_toegestaan": 1,
      "confidence": 0.17,
      "laatst_bijgewerkt": "2026-07-08T20:10:00"
    }
  }
}
```

Bewust plat JSON-bestand, zelfde filosofie als `word_associations.json` en `patterns_layer2.json` — geen SQLite nodig, dit groeit traag en simpel.

### Belangrijk: dit is generiek, niet hardgecodeerd voor "coderen"

De sleutel in `interruption_patterns` is de activiteit-naam zelf (`"coderen"`, `"gamen"`, `"lezen"`, ...) — exact hetzelfde principe als `topic_detected:<naam>` en `activity_started:<naam>` elders in de roadmaps. Er is dus **geen aparte code nodig per nieuwe activiteit**: zodra Activity Awareness Deel A een nieuwe activiteit-naam doorgeeft (via het generieke `"ik ga <activiteit>"`-patroon), begint deze module er automatisch een eigen teller voor bij te houden.

Concreet betekent dit dat Nova per activiteit een **onafhankelijk patroon** kan opbouwen:
- "coderen" → confidence 0.85 → mag meestal storen
- "gamen" → confidence 0.17 → beter niet storen
- "lezen" → nog te weinig observaties → valt terug op voorzichtig altijd-vragen (zie `has_enough_data`)

**Grens:** een gloednieuwe activiteit start altijd op 0 observaties — er is geen "overerving" van hoe het bij andere activiteiten ging. Elke activiteit moet zijn eigen patroon opnieuw opbouwen.

---

## API DESIGN

```python
tracker.record_feedback(activiteit, toegestaan, tijd_sinds_start)
tracker.get_confidence(activiteit)          # → float 0.0-1.0, of None bij te weinig data
tracker.get_pattern(activiteit)              # → volledig dict voor die activiteit
tracker.has_enough_data(activiteit, min_observaties=5)  # → bool
```

---

## FASE-ROADMAP {#fase-roadmap}

| Fase | Omschrijving | ML nodig? | Geschat werk |
|---|---|---|---|
| 1 | Nieuw event `interruption_feedback` publiceren vanuit chat.py (bij ja/nee-antwoord op "mag ik storen?") | ❌ Nee | Klein |
| 2 | Tel-mechanisme + databestand (`interruption_patterns.json`), API zoals hierboven | ❌ Nee | Klein — vergelijkbaar met Layer 2's simpelste teller |
| 3 | Drempelwaarde-logica: vanaf hoeveel observaties mag confidence gebruikt worden (`has_enough_data`) | ❌ Nee | Klein |
| 4 | Integratie in response_engine.py: sjabloonkeuze op basis van confidence (zie Stap 3 hierboven) | ❌ Nee | Middel — hangt af van hoeveel sjabloonvarianten gewenst zijn |
| 5 | Variatie in formulering: sjabloonlijsten per situatie + willekeurige keuze (zie Stap 4) | ❌ Nee | Klein — vergelijkbaar met expression_injector.py |
| 6 (optioneel) | Verfijning: apart tellen per tijdsvenster binnen de activiteit (bv. eerste 20 min vs. daarna) | ❌ Nee | Middel |

**Afhankelijkheden:** vereist dat Activity Awareness Deel A (activity_started-events) en een basisversie van Layer 5 al bestaan, aangezien dit systeem reageert op momenten binnen een lopende activiteit. Kan niet los daarvan gebouwd worden.

---

## VOORBEELDSCENARIO (Kevin, 9 juli 2026) {#voorbeeldscenario}

```
Eerste keren:
Kevin: "ik ga coderen"
Nova: "Ok ik laat je focussen"
Kevin: "ok"
--10-20 min verder--
Nova: "Mag ik storen?"
Kevin: "ja"
Nova: ...
       ↓ elke ja/nee wordt geregistreerd als interruption_feedback

Na een aantal keren (confidence hoog genoeg):
Kevin: "ik ga coderen"
Nova: "Ok veel plezier"
Nova: "Lukt het? Kan ik helpen?"
```

Dit is het scenario dat deze roadmap concreet mogelijk maakt, mits Fase 1-4 gebouwd zijn.

---

## EERLIJKHEID: WAT KAN WEL/NIET SYMBOLISCH {#eerlijkheid}

- ✅ **Tellen hoe vaak storen werd toegestaan vs. geweigerd, per activiteit** — pure statistiek, zelfde familie als Layer 1 (PMI) en Layer 2 (frequentie)
- ✅ **Een confidence-score gebruiken om tussen vaste sjabloonzinnen te kiezen** — if/else op een drempelwaarde, geen generatie
- ✅ **Nova mag zeggen dát een patroon bestaat (impliciet, via haar gedrag), nooit waarom** — zelfde principe als Layer 2's anomaly-detectie: geen verzonnen verklaringen over Kevin's motivatie
- ✅ **Voorzichtig terugvallen bij te weinig data** — een simpele drempelwaarde (`min_observaties`) volstaat, geen ML nodig om "onzekerheid" te herkennen
- ❌ **Nova die zelf aanvoelt of het "een goed moment" is los van een geteld patroon** — dat vereist inschatting/aanvoelen op een niveau dat symbolisch niet haalbaar is zonder LLM
- ❌ **Subtiele signalen in Kevin's toon meewegen** (bv. korte, geïrriteerde "ja" anders wegen dan een enthousiaste "ja") — sentiment/toon-analyse op die schaal is een taalbegrip-taak, niet symbolisch haalbaar met de huidige architectuur
- ❌ **Verklaren waarom Kevin niet gestoord wil worden** — Nova telt enkel dat het patroon bestaat, ze verzint nooit een reden ("je bent vast gestrest") — dat zou een ongefundeerde aanname zijn

**Status in de bouwvolgorde:** concept, nog niet ingepland. Vereist minstens een basisversie van Activity Awareness Deel A en Layer 5 Fase 1-2 vóór dit zinvol gebouwd kan worden — kan dus niet los, zoals user_preferences.py dat wel kan.

---

## DEEL 4: CONTEXTUELE SUGGESTIES TUSSEN ACTIVITEITEN {#deel-4}

### Wat lost dit op?

Kevin's voorbeeld: hij kijkt naar Plex, en Nova stelt op een gegeven moment voor om de lichten te dimmen — niet omdat hij dat ooit heeft gevraagd, maar omdat Nova dat verband zelf heeft leren kennen uit **alledaags gedrag**, niet enkel uit dingen die expliciet tegen haar gezegd worden.

Dit is inhoudelijk **Activity Awareness Deel C** (co-occurrence tussen activiteiten, al beschreven in `activity_awareness_roadmap.md`), maar hier toegepast op een suggestie die Nova zelf doet in plaats van enkel een observatie die ze uitspreekt.

### Hoe zou dit werken, puur symbolisch?

```
Event 1: activity_started("plex_kijken")
Event 2 (binnen X minuten erna): event "lichten_gedimd"

Na voldoende keren dat dit samen voorkomt:
co_occurrence["plex_kijken + lichten_gedimd"] = 14/15 = 0.93

→ Nova kan een vaste suggestie doen: "Zal ik de lichten dimmen?"
```

Net als bij interruption learning: dit blijft tellen + een vaste sjabloonzin kiezen op basis van een confidence-drempel. Geen generatie, geen "begrip" van waarom licht en film bij elkaar horen.

### De harde voorwaarde: het moet al een event zijn

Dit werkt **alleen** als de tweede actie ("lichten dimmen") zelf al een **gemeten event** is binnen Nova's EventBus. Als Kevin het licht zelf dimt via een knop of een aparte app, zonder dat dit ooit bij Nova binnenkomt, dan bestaat dat moment voor Nova simpelweg niet — ze kan niet leren van iets wat ze nooit "ziet" gebeuren.

Dit betekent een concrete, aparte randvoorwaarde: **elke alledaagse actie die Nova moet meeleren, vereist een eigen sensor/integratie** die dat moment naar de EventBus publiceert. Voorbeelden: een Philips Hue-koppeling, Home Assistant, of een andere smart-home-integratie. Dat is zelf geen onderdeel van dit statistiek-systeem — het is een aparte, voorafgaande stap.

### Drie lagen die hiervoor nodig zijn

| Laag | Rol | Bestaat al? |
|---|---|---|
| 1. Sensor/integratie | Maakt een alledaagse actie (bv. "lichten_gedimd") uberhaupt zichtbaar als Nova-event | ❌ Nee, apart te bouwen per integratie |
| 2. Co-occurrence-teller | Telt het verband tussen twee events (Activity Awareness Deel C) | ❌ Nee, wel al beschreven |
| 3. Suggestie-sjabloon | Kiest een vaste zin ("zal ik de lichten dimmen?") op basis van hoge confidence | ❌ Nee, nieuw stukje in Layer 4 |

Zonder laag 1 stopt dit bij: "Nova zou het kunnen leren, als ze het maar kon zien gebeuren." Voor dingen die al wél events zijn (zoals andere activiteiten via het "ik ga X"-patroon), is laag 1 niet nodig — dan volstaan laag 2 en 3.

### Eerlijkheid: wat kan wel/niet

- ✅ **Vast, hardgecodeerd koppel activiteit → suggestie** (bv. altijd "zal ik de lichten dimmen?" bij Plex, ongeacht of het al vaker gebeurde) — 100% symbolisch, triviaal te bouwen, maar leert niets bij
- ✅ **Leren welk koppel het vaakst voorkomt/geaccepteerd wordt, tussen events die al bestaan** — dezelfde confidence-aanpak als interruption learning, toegepast op "suggestie geaccepteerd ja/nee"
- ✅ **Zelf ontdekken van een niet-vooraf-bedacht verband tussen twee activiteiten/events, zolang beide al gemeten worden** — puur co-occurrence tellen, geen ML nodig (Activity Awareness Deel C)
- ⚠️ **Hetzelfde, maar voor een alledaagse actie die nog geen event is** (bv. lichten dimmen via een schakelaar) — vereist eerst een aparte sensor/integratie-laag; zonder die laag is er simpelweg niets om te tellen
- ❌ **Nova die zelf, zonder ooit een voorbeeld gezien te hebben, verzint dat "lichten dimmen" logisch bij "film kijken" hoort** — dat is wereldkennis/redeneren dat verder gaat dan tellen van geziene patronen; dat is een LLM-taak, geen symbolische taak

**Status in de bouwvolgorde:** concept, nog niet ingepland. Groter en met meer losse afhankelijkheden dan Deel 1-3 — met name de sensor/integratie-laag is voor elke nieuwe "alledaagse actie" apart werk, en dus het minst voorspelbare deel qua tijdsinvestering.
