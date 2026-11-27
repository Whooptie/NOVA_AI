
Hieronder het volledige plan. Volgorde is bindend: elke fase werkt alleen op wat ervoor af is. Fase 0 is geen optioneel opstapje — zonder die laag bouw je de rest tegen drift en testflakiness aan.

## Harde regels, gelden in elke fase

- **Één state store.** `core/state_store.py` is de enige schrijver, met `schema_version`, migraties en debounce (max 1 write per 2s, geforceerd bij shutdown). Geen module schrijft zelf JSON.
- **Injecteerbare klok.** Alles via `core/clock.py`. Geen `time.time()` in nieuwe code.
- **Hysterese verplicht.** `core/thresholds.py` met `kruist(oud, nieuw, drempel)`. Elke drempel-overgang, elke publicatie.
- **Richting.** State-modules lezen alleen van lagen onder zich en publiceren alleen omhoog. `hop`-teller in de payload, max 4, daarna droppen.
- **Afgeleid wordt nooit opgeslagen.** `arousal`, modifiers, drempels: berekend bij lezen.
- **Alles wat wél opgeslagen wordt, overleeft een reboot.** Geen enkele toestand zakt bij een herstart terug naar een standaardwaarde. Afgeleide waarden overleven indirect, omdat ze uit opgeslagen state opnieuw berekend worden. Standaardwaarden gelden alleen als het bestand of de namespace nog niet bestaat.
- **Elke module:** `init_module(event_bus)`, subscriben in `__init__`, niets publiceren in `__init__`, debug-commando in `modules/debug`.
- **Eén fase per commit-reeks.** Niet mengen.

---

## Fase 0 — fundament — KLAAR

Doel: leesbaarheid, testbaarheid, één waarheid. Geen zichtbaar gedragsverschil.


| #   | Werk                                                                                   | Bestand                                 |
| ----- | ---------------------------------------------------------------------------------------- | ----------------------------------------- |
| 0.1 | Injecteerbare klok                                                                     | `core/clock.py`                         |
| 0.2 | State store + migratie + debounce                                                      | `core/state_store.py`                   |
| 0.3 | `body_persistent.json` migreren naar de store                                          | migratiescript in `scripts/`            |
| 0.4 | Read-path: `snapshot()` + `state_body`-event, gedebounced                              | `modules/body/body_state.py`            |
| 0.5 | Body-output via `response_pipeline` i.p.v. direct `layer4_response`                    | `body_state.py`, `response_pipeline.py` |
| 0.6 | Namen vastleggen: `comfort` → `comfort_zone`, `closeness` en `gesteldheid` reserveren | `data/body_map.json`                    |
| 0.7 | Hysterese-helper, en de bestaande `bloos>0.7`-guard erop zetten                        | `core/thresholds.py`                    |

**Tests:** klok, store roundtrip, migratie, debounce, snapshot-contract, pipeline-routing, hysterese.
**Gate:** suite groen, chat-output byte-identiek aan voor de fase. **Rollback:** store terug naar file-IO.

---

## Fase 1 — zelfbewustzijn — KLAAR

Doel: het verschil dat een tiener maakt. Klein, hoog rendement.

- **1.1 `bekeken`** (0–1). Stijgt bij observatie-intent (`intent_uiterlijk`, `bekeken_trigger`), 0.15 per trigger, daalt 0.035/min. Hysterese 0.45/0.35. Actief → `response_style` wordt "kort" via `context_manager._bepaal_response_style()`, niet via de pipeline. Publiceert `bekeken_changed` (leespad, vandaag nog geen lezer).
- **1.2 bravoure-collapse.** `bloos` kruist 0.65 terwijl `bravoure > 0.3` → `bravoure` naar 0, `bravoure_instorting`, één korte zin, verder niets die beurt. Hysterese 0.65/0.55.
- **1.3 cross-zone reset.** Nieuwe zone terwijl vorige `gewend > 1.0` → alle andere zones `gewend *= 0.6`.

**Belangrijk onderscheid:** `bravoure` is de houding (stijgt bij `bloos < 0.25`, stort in, vervalt 0.20/min). `bravoure_boost` is iets anders: nasleep-brutaliteit, alleen gezet door de herstelzin, en gelezen door `expression_injector._boost()`. Nooit door elkaar gebruiken.

**Bloos bij uiterlijkvragen komt uit `identity/self_uiterlijk.py`** (0.08 per intiem deel, verhuld boven 0.5, aarzel boven 0.9), niet uit `bekeken`. Die koppeling is er bewust uit.

**Tests:** elk van de drie met vaste klok, plus de terugkeer onder de drempel.
**Gate:** collapse vuurt precies één keer per overschrijding.

---

## Fase 2 — kleding

Doel: iets dat in een scène kan veranderen zonder het lichaam te wijzigen.

- Data: `data/kleding.json` — `{schema_version, items: [{id, zone, laag, status}]}`. Laag 1 = buitenkant.
- Events: `kleding_uit`, `kleding_aan`, `kleding_verschoven`.
- Regels: laagorde afdwingen (buitenkant eerst), `bekeken` +0.15 bij verschuiven, `comfort_zone`-drempel verlaagt per uit item op die zone, `gesteldheid.koud` stijgt bij uit zonder warmte.
- **Verschuiven terwijl er al contact is**: het item blijft aan maar gaat opzij (short) of omhoog (hoodie, topje, shirt), zone wordt bereikbaar, `bloos` krijgt een extra duwtje van 0.05. Dit is de meest voorkomende handeling en verdient een eigen pad naast aan/uit. Geldt voor elk stuk, ook voor kleding die al verschoven is: dan kan het alsnog uit.
- **Uitsluitende groep**: `topje` en `shirt` zitten in groep `bovenkant`; één aanzetten zet de andere uit. Nooit allebei tegelijk.
- **`los` als vierde toestand**: alleen voor de short, want alleen die heeft een sluiting. Knoop open, gulp open, band scheef — het stuk zit nog aan maar houdt niets meer tegen. Mechanisch: `demping` naar 0 op de zones van dat stuk, en de volgende `uit` of `verschoven` kost geen eigen handeling meer. `los` is niet hetzelfde als `verschoven`: bij `verschoven` is het weggeschoven, bij `los` hangt het er nog en is het zichtbaar open.
- **Terug aan is altijd `aan`**: `los` en `verschoven` zijn niet plakkerig. Zodra een stuk weer dicht of recht zit, staat het op `aan`.
- **Slapen**: hoodie uit, topje uit, short uit, en dan ofwel het shirt aan ofwel alles uit. Nooit een hoodie of een topje in bed, en nooit een short. Er is geen aparte "naakt"-vlag: naakt is gewoon de stand waarin alle vier `uit` staan.
- **Kleding aan als demper**: een zone met kleding erover verhoogt de effectieve `sterkte_drempel` met de `demping` van dat stuk (hoodie 0.20, shirt 0.10, short 0.15). Zo voelt "door de stof" anders dan op huid, zonder dat er iets aan het lichaam verandert.
- Templates in `modules/body/kleding_tekst.py`, niet in `_zin()`.

- **Event**: `intent_kleding` met `{item, actie}`, gepubliceerd door de router. Herkenning beperkt tot de vier items bij naam, geen "iets uit".
- **Persistentie**: de toestand staat in de state store en overleeft een reboot. Standaardstanden gelden enkel bij een ontbrekend bestand.
- **Initiatief**: temperatuur-gedreven en alleen via `can_interrupt()`. "Het is hier warm" en dan de hoodie uit. Geen mode-ideeën.
- **Koppeling `bekeken`**: +0.10 als er iets `los` of `uit` gaat terwijl de bekeken-as actief is.
- **`comfort_zone` wordt niet geraakt**, alleen `sterkte_drempel` via `demping`.
- **Volgorde breken wordt geweigerd**, met een korte zin en zonder automatische correctie: "Zit nog onder de hoodie, hoor."

**Tests:** laagorde, zone-koppeling, drempel-effect, "niets meer aan" valt niet om, `los` verlaagt de demping naar 0, terug aan wordt altijd `aan`, volgorde-weigering, toestand overleeft herstart, initiatief geblokkeerd buiten `can_interrupt`.
**Gate:** elke zone heeft een geldige kledingstaat of expliciet `geen`, en een gebroken volgorde levert nooit een kledingstuk in de verkeerde laag op.

---

## Fase 3 — awareness + gesteldheid

- **3.1 `laatste_keer`** per zone. Awareness-laag: actieve zones deze sessie; "daar ben je net geweest" bij < 3 min, als vaste suffix in `body_state._zin()`.
- **3.2 `gesteldheid`**: `koud` uit `weather`-module, `moe` uit uur + cyclus-energie, `stijf` na lange stilte. Eigen decay, cap 1.0.
- **3.3 koppeling `gesteldheid.moe` → `response_style`.** Boven 0.6 geeft `context_manager._bepaal_response_style()` "kort", met dezelfde hysterese als bij `bekeken`. Dit is de eerste plek waar gesteldheid iets doet in plaats van alleen te bestaan.

**Tests:** tijdgebaseerd met fake clock; weer-koppeling met gemockte temperatuur.
**Gate:** geen publicatie als `gesteldheid` onveranderd blijft.

---

## Fase 4 — hormonale laag

- `data/cyclus.json`: `{anker, fase_lengtes: [jitter 21–35], schema_version}`.
- Fase berekend uit anker + verstreken dagen, **niet** uit een teller (reboot-veilig).
- Publiceert `cyclus_fase`. Levert alleen modifiers: energie, prikkelbaarheid, `bloos`-drempel, libido-baseline.
- Geen eigen templates. `energy_profile.fluctuation_pattern` in `identity.json` wordt hierdoor overschreven.

**Tests:** jitter-grenzen, 90 dagen doorrekenen, reboot-continuïteit, fase-wissel met hysterese.
**Gate:** twee runs met zelfde anker geven identieke fase.

---

## Fase 5 — arousal afgeleid + amplitude

- `arousal()` berekend: gewogen max over `nat` van actieve zones, gedempt door `bloos` en `ervaring`. Niet opgeslagen, geen eigen decay.
- Amplitude: `delta * (1.4 - 0.6 * ervaring)`, hard begrensd per trigger.
- `_zin()` leest `arousal` naast `bloos`; drempels schuiven mee.
- **5.4 climax**: `type == "climax"` (herkend door de router, niet als nieuw event — het is een waarde van `intent_body`, net als `penetratie`). Bij `arousal > 0.75`: `arousal` hard naar 0.25, cooldown per zone van 2–8 min waarin `gevoeligheid` tijdelijk ×0.5, aftercare start. Hysterese 0.75/0.6, plus een cooldown-vlag die een tweede climax binnen de cooldown negeert.
- **5.5 opruiming**: `ZONE_FRAGMENT`, `GENERIEK_FRAGMENT`, `EUFEEM`, `INSTORTING` en de `bak` uit `_zin()` verhuizen naar `modules/body/seks_tekst.py` als pure data. De selectielogica blijft in `body_state`. Geen tweede mechanisme, alleen korter bestand.
- **5.6 geoefendheid**: `ervaring` bepaalt niet alleen de amplitude maar ook het register. Boven 0.4 vervangt klasse `gewend` de klasse `ontmaagd`: korter, vlakker, zonder "Oh.". De fragment-drempel schuift mee met `ervaring * 0.15`. `gewend` decay zakt naar 0.05/min en start bij sessiebegin op `min(ervaring * 2, 2.0)`, zodat een nieuwe sessie niet terug op nul begint. `ervaring` decay zakt van 0.00004 naar 0.00001/min, met een vloer van 0.6: geoefendheid leer je niet af. Geoefend is bij een tiener niet hetzelfde als vaardig — `gewend` blijft vlak maar "wacht" en "traag" blijven mogelijk. Per zone, dus een nieuwe zone is altijd opnieuw onwennig.

**Tests:** monotoon, begrensd, geen drift tegenover `nat`, amplitude daalt met `ervaring`, climax alleen boven 0.75, tweede climax genegeerd binnen cooldown, `gevoeligheid` herstelt na cooldown, `gewend` begint niet op nul na ervaring, nieuwe zone blijft `eerste_keer`, geoefende zone geeft `gewend`.
**Gate:** `arousal` nooit in het state-bestand, geen climax zonder cooldown-vlag.

---

## Fase 6 — grens + initiatief (samengevoegd)

- **6.1 `comfort_zone`** wordt persistent en verdiend: startwaarde uit `body_map.json`, +0.02 per positieve interactie op die zone, −0.01/dag zonder contact, plafond per zone.
- **6.2 `nieuwsgierigheid`**: stijgt bij onbekende zone, daalt bij herhaling én bij hoge `ervaring` op die zone (koppeling: `ervaring > 0.5` halveert de stijging). Zo went ze aan wat ze kent.
- **6.3 initiatief**: `nieuwsgierigheid > comfort_zone` én `can_interrupt()` én arousal in band → `initiatief_voorstel` mét checkvraag.
- **6.4 grens-rem**: `stop`, `nee`, `wacht`, `te veel`, `au` breken de huidige actie direct af, ongeacht `comfort_zone`, met een korte recovery van 2–5 min. Dit staat naast `comfort_zone`, want dat is een langzame verdiende band en dit is een onmiddellijke rem.
- **6.5 hard limits**: vaste lijst per zone met wat nooit gebeurt (bv. `rectum` geen diepe stoot bij `ervaring < 0.2`). Wordt bij elke actie gecheckt vóór de klasse bepaald wordt.

**Tests:** elk stopsignaal breekt af, recovery duurt, hard limit wint van `comfort_zone`, plafond nooit overschreden, initiatief geblokkeerd buiten `can_interrupt`, checkvraag altijd aanwezig.
**Gate:** `comfort_zone` daalt nooit onder de startwaarde, een stopsignaal levert nooit een gewone `_zin()` op.

---

## Fase 7 — aftercare

- Vervangt de herstelzin volledig, niet ernaast.
- Na `body_reactie` met hoge arousal: 3–20 min `stil` → `afwerend` → `nazinderen`, dan normaal.
- Templatevolgorde vast: grap, dan stilte, dan gewoon.
- Velden `laatste_climax_zone` en `laatste_climax_ts` in de body-state, zodat de eerste aftercare-zin weet waar het over gaat ("daar dan"). Vervalt na 30 min.
- Cooldown uit 5.4 wordt hier opgeheven, niet eerder.

**Tests:** duur, decay, geen dubbele trigger bij opeenvolgende events, zin verwijst naar de juiste zone, cooldown pas hier opgeheven.
**Gate:** oude herstelzin verwijderd, tests bijgewerkt.

---

## Fase 8 — emotionele laag

- **8.1 echo**: max één actief, cap 0.4, decay 0.01/min, nooit stapelen.
- **8.2 modulator**: drempelcombinaties naar vier modi met mapping-tabel, geen continue menging.
- **8.3 appraisal**: vaste tabel gebeurtenis → betekenis → emotie. "Compliment over uiterlijk" weegt anders dan "compliment over code". Geen ML, alleen een lookup met fallback.
- **8.4 gemengde emoties**: twee modi tegelijk toegestaan, max één paar, met een vaste winnende modus voor de toon. Alleen combinaties uit een expliciete lijst (uitkijken+zenuwachtig, blij+onzeker), nooit vrij mengen.

**Tests:** tabel-gedreven, één test per modus en per grenscombinatie.
**Gate:** elke modus heeft een minimale duur voor hij wisselt.

---

## Fase 9 — laat

- **vitals** (ademhaling/hartslag): pure expressie, alleen als iets het leest.
- **closeness**: alleen op expliciete feedback, niet op aanwezigheid.

---

## Fase 10 — autobiografisch geheugen

Doel: gebeurtenissen als één doorlopend verhaal, niet als losse records.

- Data: `data/verhaal.jsonl`, append-only, één regel per betekenisvolle gebeurtenis: `{ts, wat, betrokken, emotie, tag}`.
- Welke gebeurtenissen een regel worden, bepaalt de bestaande `memory_priority_rules` uit `identity.json`.
- Hooguit één samenvattende regel per sessie-einde, via sjabloon. Geen generatie.
- Leespad: `laatste(n)`, `bevat(tag)`. Voedt `datum_terugblik`.
- Cap: max 20 regels per dag, anders is het geen verhaal meer.

**Tests:** prioriteitsfilter, geen dubbele regels, reboot-continuïteit, terugblik-venster, dagcap.
**Gate:** een gebeurtenis zonder tag wordt nooit opgeslagen.

---

## Fase 11 — goal engine (klein)

Doel: een open intentie kunnen hebben. `pending_question` is voor gesloten vragen; dit is voor iets willen.

- Data: `data/doelen.json` — `{id, tekst, ontstaan, status, houdbaarheid}`. Max 3 open.
- Verloopt na de houdbaarheid zonder interactie.
- Kan alleen voorstellen, nooit uitvoeren. Respecteert `can_interrupt()`.
- Geen eigen templates buiten een vaste lijst voorstellen.

**Tests:** max 3, verlopen, geen voorstel buiten `can_interrupt`, geen dubbel voorstel.
**Gate:** een doel zonder lezer blijft onschadelijk.

---

## Fase 12 — identiteitsbewaking

Doel: drift detecteren voordat een mens het merkt. Een bewaker, geen functie.

- Vergelijkt `identity.json` en `body_map.json` met wat de code als waarheid gebruikt: drempelwaarden, `comfort_zone`-banden, namen.
- Rapporteert afwijkingen in de zelftest. Blokkeert niets.
- Detecteert ook verouderde documentatie: een fase die cijfers noemt die niet meer in de code staan.

**Tests:** detecteert een bewust ingebouwde afwijking, geen valse meldingen op de bestaande set.
**Gate:** nul valse meldingen.

---

## Niet opnieuw bouwen

`nat`/`bloos` (= arousal), `_zin()`/`ZONE_FRAGMENT` (= mapper), `ervaring`/`gewend`/`voorkeur`/`telling` (= zone-ervaring), `gevoeligheid` (= zone-gevoeligheid).

Ook al gedekt door bestaande lagen, dus niet als module bouwen: `habit_engine` (Layer 2), `decision_engine` (interrupt-score), `belief_revision` (contradiction_checker), `preference_evolution` (`modules/preferences`), `trait_adaptation` (adaptive learning), `cognitive_load` en `mental_fatigue` (`overstimulation`), `emotional_recovery` (decay + herstelzin), `emotional_expression` (tone + injector), `self_model` (self_architecture), `attention_engine` (Layer 5 + focus_detector), `working_memory` (`last_context`, `pending_question`), `curiosity_engine` (6.2), `social_comfort` (`comfort_with_others`).

Bewust niet bouwen: `hydration_state`, `comfort_environment`, `body_coordination`, `sleep_state`, `emotional_regulation`, `mood_history`, `social_awareness`, `relationship_context`, `social_boundaries`, `privacy_awareness`, `conversation_dynamics`, `experience_weighting`.

Posture, movement en sensory awareness pas ná fase 12, en alleen als de avatar gekoppeld is — zonder lezer is het decoratie.

## Volgorde in één regel

0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12.

Fase 0 tot 3 is samen minder werk dan 4 en 5 met tests, en levert meer personage. Als je moet snijden: 9 valt af, dan 8, dan 3.2.

Zeg maar welke fase je eerst wil en ik schrijf de module plus tests uit. Fase 0.1 tot 0.3 is puur mechanisch werk en kan ik meteen neerzetten.
