# User Preferences Roadmap: Wat Nova over Kevin onthoudt

**Status:** Concept — nog niet gepland in bouwvolgorde
**Depends on:** memory.py (Layer 0) ✅ Fase 1-3 klaar
**Gebruikt door:** Layer 4 (Response generation), toekomstige proactieve suggesties
**Datum:** 2 juli 2026

---

## INHOUDSOPGAVE

1. [Wat is dit?](#wat-is-dit)
2. [Waarom een aparte module, en geen Layer 1?](#waarom-apart)
3. [Hoe werkt het?](#hoe-werkt-het)
4. [Data structure](#data-structure)
5. [API design](#api-design)
6. [Fase-roadmap](#fase-roadmap)
7. [Eerlijkheid: wat kan wel/niet symbolisch](#eerlijkheid)

---

## WAT IS DIT?

Een module die **expliciete feiten over Kevin** bijhoudt — dingen zoals voorkeuren, gewoontes, afkeuren. Niet "welke woorden vaak samen voorkomen" (dat is Layer 1), maar een concreet, doorzoekbaar profiel:

```
kevin_profile.json
{
  "voorkeuren": {
    "koffie": {"sentiment": "positief", "bron": "expliciet", "datum": "2026-07-02"},
    "python": {"sentiment": "positief", "bron": "automatisch", "datum": "2026-07-01"}
  },
  "afkeuren": {
    "kou": {"sentiment": "negatief", "bron": "automatisch", "datum": "2026-06-15"}
  }
}
```

### Waarom nodig?

```
Zonder deze module:
Kevin: "Wat kan ik vanavond drinken?"
Nova: Heeft geen idee wat je lekker vindt.

Met deze module:
Kevin: "Wat kan ik vanavond drinken?"
Nova: Kijkt in kevin_profile.json → vindt "koffie: positief"
      → "Koffie misschien? Je gaf eerder aan dat je dat graag drinkt."
```

---

## WAAROM APART, EN GEEN LAYER 1? {#waarom-apart}

Dit is een bewuste architectuurkeuze, geen toeval:

| | Layer 1 (word associations) | Deze module |
|---|---|---|
| Wat het opslaat | statistisch verband tussen willekeurige woorden | expliciete, benoemde feiten over Kevin specifiek |
| Precisie | vaag ("python" hangt samen met "snel") | concreet ("Kevin drinkt graag koffie") |
| Bevraagbaar met zekerheid? | nee, het is een gewicht/score | ja, het is een simpele ja/nee-lookup |
| Herkomst | puur automatisch, uit alle tekst | automatisch én expliciet commando |

Layer 1 leert *taal*. Deze module leert *Kevin*. Ze kunnen naast elkaar bestaan en elkaar aanvullen — Layer 1 kan zelfs als extra signaal dienen om kandidaat-voorkeuren te vinden die deze module dan expliciet vastlegt.

---

## HOE WERKT HET?

### Twee ingangen

**1. Automatisch — patroonherkenning in de IntentRouter**

Net zoals `detect_weather()` of `detect_math()` nu al patronen herkennen, komt er een `detect_preference()` methode die zinnen zoals deze herkent:

- "ik hou van X" / "ik hou niet van X"
- "mijn favoriete X is Y"
- "ik drink graag X" / "ik eet graag X"
- "ik haat X"

Dit is **pure patroonherkenning**, dezelfde aanpak als de rest van `intent_router.py` — geen ML, geen LLM. Wel een eerlijke beperking: alleen zinnen die in een herkend patroon passen worden opgepikt. Zeg je het op een creatieve, onvoorziene manier, dan mist Nova het — dat is de prijs van symbolisch werken zonder taalmodel.

**2. Expliciet — commando**

```
onthoud: ik drink graag koffie
vergeet: kou
```

Dit gaat via dezelfde route als je huidige `teach`-commando's in `intent_router.py` — voorspelbaar, geen twijfel over wat wordt opgeslagen.

### Verwerking

```
Event binnenkomt (automatisch óf expliciet)
   ↓
Woord + sentiment (positief/negatief) + bron bepalen
   ↓
Opslaan in kevin_profile.json
   ↓
event_bus.publish("preference_learned", {...})
   (chat.py kan dit oppikken voor bevestiging: "Genoteerd, je houdt van koffie!")
```

---

## DATA STRUCTURE

```json
{
  "voorkeuren": {
    "<woord>": {
      "sentiment": "positief",
      "bron": "expliciet",
      "datum": "2026-07-02",
      "aantal_keer_genoemd": 1
    }
  },
  "afkeuren": {
    "<woord>": { "...zelfde structuur..." }
  }
}
```

Bewust simpel gehouden — een plat JSON-bestand, geen database nodig. Dit groeit traag (hooguit een paar honderd items ooit), dus SQLite zoals bij Layer 0 is hier overkill.

---

## API DESIGN

```python
prefs.add_preference(woord, sentiment, bron="automatisch")
prefs.remove_preference(woord)
prefs.get_preference(woord)          # → dict of None
prefs.get_all_preferences()          # → volledige profiel
prefs.get_by_sentiment("positief")   # → lijst van alles wat Kevin leuk vindt
```

---

## FASE-ROADMAP

| Fase | Omschrijving | Geschat werk |
|---|---|---|
| 1 | Databestand + basis CRUD (`add/remove/get_preference`) | Klein — vergelijkbaar met een simpele JSON-module |
| 2 | Expliciet commando (`onthoud: ...` / `vergeet: ...`) via IntentRouter | Klein — zelfde patroon als `teach` |
| 3 | Automatische patroonherkenning (`detect_preference()`) | Middel — een handvol regex-patronen, testen kost tijd |
| 4 | Integratie in `chat.py` — voorkeuren gebruiken in antwoorden | Middel — hangt af van hoeveel plekken je dit wil laten meespelen |

Geen daemon-complexiteit nodig hier (geen write buffer, geen WAL) — dit schrijft zelden, dus een simpele directe JSON-write per wijziging volstaat.

---

## EERLIJKHEID: WAT KAN WEL/NIET SYMBOLISCH {#eerlijkheid}

- ✅ **Patroon-detectie van expliciete uitspraken** ("ik hou van X") — 100% symbolisch, regex-gebaseerd, past perfect bij Nova's filosofie
- ✅ **Sentiment simpel classificeren** (positief/negatief op basis van het patroon zelf, bv. "hou van" = positief, "haat" = negatief) — symbolisch, een woordenlijstje van signaalwoorden volstaat
- ❌ **Impliciete/subtiele voorkeuren begrijpen** (bv. uit de toon van een heel gesprek afleiden dat je iets stiekem niet leuk vindt) — dat vereist taalbegrip op een niveau dat symbolisch niet haalbaar is zonder een LLM. Dit bouwen we dus niet.
- ❌ **Nuance in sentiment** (bv. "koffie is oké maar niet mijn favoriet" correct als "neutraal-licht-positief" classificeren) — te subtiel voor patroonmatching, zou een verkeerd beeld geven als we het zouden proberen. Beter een expliciet patroon missen dan een verkeerd sentiment vastleggen.

**Status in de bouwvolgorde:** nog niet ingepland. Logisch punt om te starten is na Layer 0 Fase 4, als los, klein project ernaast — het heeft geen afhankelijkheid van Layer 1 of 2, dus kan op elk moment.
