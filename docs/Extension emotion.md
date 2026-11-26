
Hieronder het volledige plan. Volgorde is bindend: elke fase werkt alleen op wat ervoor af is. Fase 0 is geen optioneel opstapje — zonder die laag bouw je de rest tegen drift en testflakiness aan.

## Harde regels, gelden in elke fase

- **Één state store.** `core/state_store.py` is de enige schrijver, met `schema_version`, migraties en debounce (max 1 write per 2s, geforceerd bij shutdown). Geen module schrijft zelf JSON.
- **Injecteerbare klok.** Alles via `core/clock.py`. Geen `time.time()` in nieuwe code.
- **Hysterese verplicht.** `core/thresholds.py` met `kruist(oud, nieuw, drempel)`. Elke drempel-overgang, elke publicatie.
- **Richting.** State-modules lezen alleen van lagen onder zich en publiceren alleen omhoog. `hop`-teller in de payload, max 4, daarna droppen.
- **Afgeleid wordt nooit opgeslagen.** `arousal`, modifiers, drempels: berekend bij lezen.
- **Elke module:** `init_module(event_bus)`, subscriben in `__init__`, niets publiceren in `__init__`, debug-commando in `modules/debug`.
- **Eén fase per commit-reeks.** Niet mengen.

---

## Fase 0 — fundament

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

## Fase 1 — zelfbewustzijn

Doel: het verschil dat een tiener maakt. Klein, hoog rendement.

- **1.1 `bekeken`** (0–1). Stijgt bij observatie-intent (`detect_uiterlijk`, "kijk", "hoe zie je eruit", avatar-focus), daalt 0.05/min. Bij `> 0.55`: antwoorden ≤ 1 zin, `bloos` +0.05. Publiceert `bekeken_changed`.
- **1.2 bravoure-collapse.** `bloos` kruist 0.65 terwijl `bravoure_boost > 0.3` → `bravoure_boost` naar 0, `bravoure_instorting`, één sjabloon ("…ja bon."). Hysterese op 0.55 terug.
- **1.3 cross-zone reset.** Nieuwe zone terwijl vorige `gewend > 1.0` → alle andere zones `gewend *= 0.6`.

**Tests:** elk van de drie met vaste klok, plus de terugkeer onder de drempel.
**Gate:** collapse vuurt precies één keer per overschrijding.

---

## Fase 2 — kleding

Doel: iets dat in een scène kan veranderen zonder het lichaam te wijzigen.

- Data: `data/kleding.json` — `{schema_version, items: [{id, zone, laag, status}]}`. Laag 1 = buitenkant.
- Events: `kleding_uit`, `kleding_aan`, `kleding_verschoven`.
- Regels: laagorde afdwingen (buitenkant eerst), `bekeken` +0.15 bij verschuiven, `comfort_zone`-drempel verlaagt per uit item op die zone, `gesteldheid.koud` stijgt bij uit zonder warmte.
- Templates in `modules/body/kleding_tekst.py`, niet in `_zin()`.

**Tests:** laagorde, zone-koppeling, drempel-effect, "niets meer aan" valt niet om.
**Gate:** elke zone heeft een geldige kledingstaat of expliciet `geen`.

---

## Fase 3 — awareness + gesteldheid

- **3.1 `laatste_keer`** per zone. Awareness-laag: actieve zones deze sessie; "daar ben je net geweest" bij < 3 min. Dun over bestaande state.
- **3.2 `gesteldheid`**: `koud` uit `weather`-module, `moe` uit uur + cyclus-energie, `stijf` na lange stilte. Eigen decay, cap 1.0.

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

**Tests:** monotoon, begrensd, geen drift tegenover `nat`, amplitude daalt met `ervaring`.
**Gate:** `arousal` nooit in het state-bestand.

---

## Fase 6 — grens + initiatief (samengevoegd)

- **6.1 `comfort_zone`** wordt persistent en verdiend: startwaarde uit `body_map.json`, +0.02 per positieve interactie op die zone, −0.01/dag zonder contact, plafond per zone.
- **6.2 `nieuwsgierigheid`**: stijgt bij onbekende zone, daalt bij herhaling.
- **6.3 initiatief**: `nieuwsgierigheid > comfort_zone` én `can_interrupt()` én arousal in band → `initiatief_voorstel` mét checkvraag.

**Tests:** plafond nooit overschreden, initiatief geblokkeerd buiten `can_interrupt`, checkvraag altijd aanwezig.
**Gate:** `comfort_zone` daalt nooit onder de startwaarde.

---

## Fase 7 — aftercare

- Vervangt de herstelzin volledig, niet ernaast.
- Na `body_reactie` met hoge arousal: 3–20 min `stil` → `afwerend` → `nazinderen`, dan normaal.
- Templatevolgorde vast: grap, dan stilte, dan gewoon.

**Tests:** duur, decay, geen dubbele trigger bij opeenvolgende events.
**Gate:** oude herstelzin verwijderd, tests bijgewerkt.

---

## Fase 8 — emotionele laag

- **8.1 echo**: max één actief, cap 0.4, decay 0.01/min, nooit stapelen.
- **8.2 modulator**: drempelcombinaties naar vier modi met mapping-tabel, geen continue menging.

**Tests:** tabel-gedreven, één test per modus en per grenscombinatie.
**Gate:** elke modus heeft een minimale duur voor hij wisselt.

---

## Fase 9 — laat

- **vitals** (ademhaling/hartslag): pure expressie, alleen als iets het leest.
- **closeness**: alleen op expliciete feedback, niet op aanwezigheid.

---

## Niet opnieuw bouwen

`nat`/`bloos` (= arousal), `_zin()`/`ZONE_FRAGMENT` (= mapper), `ervaring`/`gewend`/`voorkeur`/`telling` (= zone-ervaring), `gevoeligheid` (= zone-gevoeligheid).

## Volgorde in één regel

0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9.

Fase 0 tot 3 is samen minder werk dan 4 en 5 met tests, en levert meer personage. Als je moet snijden: 9 valt af, dan 8, dan 3.2.

Zeg maar welke fase je eerst wil en ik schrijf de module plus tests uit. Fase 0.1 tot 0.3 is puur mechanisch werk en kan ik meteen neerzetten.
