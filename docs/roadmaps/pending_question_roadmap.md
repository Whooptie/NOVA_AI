# Pending Question Roadmap: generiek "Nova wacht op antwoord"-mechanisme

**Status:** Concept — nog niet gepland in bouwvolgorde
**Depends on:** intent_router.py ✅, signal_classifier (Layer 6) ✅ reeds gebouwd
**Vult aan:** `handle_confirmation()` (al jaren als "nog leeg" genoteerd), en generaliseert het scenario uit `interruption_learning_roadmap.md`
**Datum:** 19 juli 2026

---

## INHOUDSOPGAVE

1. [Het gat dat dit oplost](#het-gat)
2. [Waarom dit apart van interruption_learning_roadmap.md staat](#waarom-apart)
3. [Hoe werkt het?](#hoe-werkt-het)
4. [Data structure](#data-structure)
5. [API design](#api-design)
6. [Fase-roadmap](#fase-roadmap)
7. [Eerlijkheid: wat kan wel/niet](#eerlijkheid)

---

## HET GAT DAT DIT OPLOST {#het-gat}

Nova heeft al een klein, lokaal ML-model gebouwd dat KORTE signaalwoorden ("oké", "tuurlijk", "prima") correct interpreteert als bevestiging vs. irritatie vs. neutraal (Layer 6, `train_classifier.py` / `signal_model.pkl`). Dat model werkt technisch — maar mist op dit moment een aanroep-moment.

```
Kevin: "oké" (zomaar getypt, niet als reactie op iets)
         ↓
intent_router.py heeft GEEN patroon dat dit herkent
als "een reactie op een eerdere vraag van Nova"
         ↓
Valt terug op de gewone fallback
         ↓
De signal_classifier wordt NOOIT geraadpleegd,
want niets vertelt intent_router dat dit een
moment is waarop hij dat zou moeten doen
```

**De kern van het probleem:** er bestaat geen enkele plek in Nova die onthoudt *"ik heb net een vraag gesteld waar ik een antwoord op verwacht"*. Zonder die staat kan `intent_router.py` een kort woord als "oké" nooit onderscheiden van een willekeurige, losse uitspraak.

Dit document beschrijft een **generiek** mechanisme daarvoor — niet gebonden aan één specifieke vraag (zoals "mag ik storen?"), maar herbruikbaar voor élke toekomstige situatie waarin Nova iets vraagt en een antwoord verwacht.

---

## WAAROM DIT APART VAN interruption_learning_roadmap.md STAAT {#waarom-apart}

`interruption_learning_roadmap.md` beschrijft al een vergelijkbaar scenario:

```
Nova: "Mag ik storen?"
Kevin: "Ja"
Nova: ...
       ↓ wordt geregistreerd als interruption_feedback
```

Dat document lost dit **specifiek** op voor het interruption-scenario: het `interruption_feedback`-event, met vaste velden (`activiteit`, `toegestaan`, `tijd_sinds_start`), gericht op het opbouwen van een confidence-score per activiteit.

Dit huidige document behandelt een **onderliggend, generieker probleem**: hoe weet Nova *sowieso al* dat "ja"/"nee"/"oké" een antwoord ís op wat ze net vroeg, ongeacht welke vraag dat was? Zonder dit generieke mechanisme zou elke nieuwe soort vraag die Nova ooit stelt (niet alleen "mag ik storen") opnieuw zijn eigen ad-hoc oplossing nodig hebben.

```
interruption_learning_roadmap.md:
├── Specifiek voor: "mag ik storen?"
├── Registreert: toestemming per activiteit
└── Doel: leren WANNEER storen oké is

Dit document (pending_question):
├── Generiek voor: ELKE vraag die Nova ooit stelt
├── Registreert: dat er een vraag open staat + welk type
└── Doel: Nova's EIGEN kortetermijngeheugen van
    "ik verwacht nu een antwoord" — een voorwaarde
    waar interruption_learning_roadmap.md op leunt,
    maar zelf niet bouwt
```

**Relatie tussen beide:** zodra dit generieke mechanisme bestaat, wordt `interruption_learning_roadmap.md`'s eigen scenario er een van de mogelijke *toepassingen* van, in plaats van een aparte, losstaande oplossing.

---

## HOE WERKT HET? {#hoe-werkt-het}

### Stap 1 — Nova registreert dat ze een vraag stelt

Wanneer eender welke module (session_watcher.py, straks interruption-logic, of een toekomstige module) een vraag stelt waar ze een kort antwoord op verwacht, publiceert ze dat expliciet:

```python
event_bus.publish("pending_question:set", {
    "vraag_type": "mag_ik_storen",   # vrije, herkenbare naam per situatie
    "gesteld_op": time.time(),
    "verval_seconden": 120           # hoelang de vraag "open" blijft
})
```

Dit is bewust een **generiek event** — de naam van `vraag_type` is vrij te kiezen per situatie (net zoals `topic_detected:<naam>` en `activity_started:<naam>` elders al werken), zodat er geen nieuwe code nodig is per nieuw soort vraag.

### Stap 2 — intent_router checkt EERST op een openstaande vraag

Vóór de bestaande patroonmatching (of de eventuele toekomstige `intent_classifier`, zie `intent_classifier_roadmap.md`) een zin verwerkt, wordt eerst gecheckt:

```
Kevin typt iets
       ↓
is er een pending_question die nog niet verlopen is?
       ├── JA → stuur de tekst naar de signal_classifier
       │        (Layer 6), interpreteer als reactie
       │        op die specifieke vraag_type
       │
       └── NEE → normale flow: bestaande patroonmatching,
                 eventueel later intent_classifier-fallback
```

### Stap 3 — signal_classifier bepaalt de aard van het antwoord

De classifier die al gebouwd is (getraind op korte signaalwoorden) wordt hier voor het eerst op een zinvol moment aangeroepen:

```python
resultaat = signal_classifier.predict("oké")
# → {"label": "bevestiging", "confidence": 0.91}
```

### Stap 4 — resultaat + vraag_type gaan naar de juiste bestemming

```python
event_bus.publish("pending_question:answered", {
    "vraag_type": "mag_ik_storen",
    "signaal": "bevestiging",
    "confidence": 0.91
})
```

Welke module hierop luistert, hangt af van `vraag_type` — voor `"mag_ik_storen"` zou dat bijvoorbeeld `interruption_learning_roadmap.md`'s teller zijn (`interruption_feedback`). Voor een toekomstige, andere vraag zou een andere module luisteren. Dit mechanisme bepaalt zelf nooit wat er met het antwoord gebeurt — het levert enkel het geïnterpreteerde signaal af bij de juiste plek.

### Stap 5 — de pending_question wordt gewist

Na een antwoord (of na het verval-tijdstip) wordt de openstaande vraag verwijderd, zodat een later, ongerelateerd "oké" niet per ongeluk nog aan een oude vraag gekoppeld wordt.

---

## DATA STRUCTURE

Geen apart bestand nodig — dit is bewust **in-memory, kortlevende staat**, geen permanente opslag (in tegenstelling tot Layer 0-2, die juist wél alles blijvend bijhouden). Een openstaande vraag is per definitie tijdelijk en irrelevant zodra ze beantwoord of verlopen is.

```python
# In intent_router.py of een klein, apart state-object:
self._pending_question = {
    "vraag_type": "mag_ik_storen",
    "gesteld_op": 1721380335.0,
    "verval_seconden": 120
}
# of None als er niets openstaat
```

---

## API DESIGN

```python
# Een module stelt een vraag en meldt dit:
pending.set("mag_ik_storen", verval_seconden=120)

# intent_router checkt bij elk bericht:
if pending.is_open():
    vraag_type = pending.get_type()
    signaal = signal_classifier.predict(tekst)
    event_bus.publish("pending_question:answered", {
        "vraag_type": vraag_type,
        "signaal": signaal["label"],
        "confidence": signaal["confidence"]
    })
    pending.clear()
else:
    # normale flow

# Automatisch verlopen (geen antwoord binnen verval_seconden):
pending.is_open()  # → False zodra verval_seconden overschreden,
                    # ruimt zichzelf op bij die check
```

---

## FASE-ROADMAP {#fase-roadmap}

| Fase | Omschrijving | ML nodig? | Geschat werk |
|---|---|---|---|
| 1 | Klein `PendingQuestion`-state-object (set/is_open/clear, met verval) | ❌ Nee | Klein |
| 2 | `intent_router.py`: check op openstaande vraag vóór normale patroonmatching | ❌ Nee | Klein — 1 vroege check bovenaan de bestaande routing |
| 3 | Koppeling met de al gebouwde signal_classifier (Layer 6) bij een openstaande vraag | ❌ Nee (model bestaat al) | Klein — enkel de aanroep zelf |
| 4 | `pending_question:answered`-event, per `vraag_type` opgepikt door de juiste luisteraar | ❌ Nee | Klein — vergelijkbaar met bestaande generieke event-patronen (`topic_detected:<naam>`) |
| 5 | Eerste echte toepassing: `session_watcher.py`'s toekomstige "mag ik storen?"-vraag hierop aansluiten, i.p.v. een eigen ad-hoc afhandeling (zie `interruption_learning_roadmap.md`) | ❌ Nee | Klein — hergebruik, geen nieuwe logica |

**Afhankelijkheden:** vereist geen van de nog te bouwen lagen (Layer 7 niet nodig). Kan volledig los gebouwd en getest worden — de signal_classifier (Layer 6) bestaat al, intent_router.py bestaat al. Dit is dus een klein, op zichzelf staand project, geen wachten op iets anders.

---

## EERLIJKHEID: WAT KAN WEL/NIET {#eerlijkheid}

- ✅ **Onthouden dat er een vraag open staat, met verval-tijd** — pure state, geen ML, geen interpretatie
- ✅ **Bij een openstaand antwoord de bestaande signal_classifier raadplegen** — hergebruik van een al gebouwd, begrensd model, geen nieuwe ML-taak
- ✅ **Generiek `vraag_type`-veld, herbruikbaar voor onbeperkt veel toekomstige situaties** — zelfde patroon als `topic_detected:<naam>`, geen aparte code per vraag
- ✅ **Automatisch laten vervallen na een tijdslimiet** — voorkomt dat een oud, niet-gerelateerd antwoord per ongeluk aan een allang vergeten vraag gekoppeld wordt
- ❌ **Dit systeem laten "raden" of iets een antwoord is zonder dat er expliciet een pending_question is ingesteld** — zonder die expliciete `set()`-stap blijft alles gewoon via de normale flow lopen; er is geen impliciete detectie van "dit klinkt als een antwoord"
- ❌ **De signal_classifier hierdoor laten heraantrainen op basis van dit mechanisme** — dit document voegt enkel een aanroep-moment toe, het traint het model niet opnieuw en verandert niets aan hoe het model zelf leert (zie `intent_classifier_roadmap.md` voor hoe hertraining wél zou werken bij die andere classifier)
- ❌ **Dit gebruiken voor open, vrije vervolgvragen** ("wat bedoel je daarmee?") — dit mechanisme is uitsluitend bedoeld voor korte, verwachte reacties (ja/nee/bevestiging-achtig), niet voor het voortzetten van een open gesprek

**Status in de bouwvolgorde:** klein, onafhankelijk project. Logisch om te bouwen vlak vóór of samen met de eerste echte toepassing ervan (`interruption_learning_roadmap.md`'s Fase 1), aangezien die roadmap er stilzwijgend van uitgaat dat Nova al weet wanneer "ja"/"nee" een reactie is op haar eigen vraag.

---

## RELATIE TOT ANDERE DOCUMENTEN

```
pending_question (dit document)
├── Vult aan: handle_confirmation() in intent_router.py
│   (al jaren als "nog leeg" genoteerd in nova_state.md)
├── Is een voorwaarde voor: interruption_learning_roadmap.md
│   (die roadmap kan pas werken zodra dit bestaat)
├── Gebruikt: de al gebouwde signal_classifier (Layer 6)
│   op een moment dat nu nog ontbreekt
└── Is GEEN vervanging van: intent_classifier_roadmap.md
    (dat lost een ander probleem op — nieuwe zinsvormen
    voor MODULE-activatie herkennen, niet korte reacties
    op een eigen vraag interpreteren)
```

---

**Status:** PLANNING — nog niet gebouwd
**Auteur:** Claude + Kevin
