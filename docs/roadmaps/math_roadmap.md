# 🚀 **NOVA MATH ROADMAP — compleet overzicht**

## **FASE 1 — Basis & functies (klaar / bezig)**

### ✔ 1. **Basismodule**

- optellen, aftrekken, vermenigvuldigen, delen
- haakjes
- negatieve getallen
- machtsverheffen
  **Status:** klaar

### ✔ 2. **Functies‑module**

- `sqrt`, `sin`, `cos`, `tan`
- `log`, `ln`, `exp`
- `abs`, `round`
- constanten: `pi`, `e`
  **Status:** klaar

### ✔ 3. **Alias‑operatoren**

- `x` → `*`
- `:` → `/`
- `^` → `**`
- inclusief varianten zonder spaties: `3x5`, `10X10`
  **Status:** bijna klaar (je hebt nog net de regex‑import gefixt)

---

## **FASE 2 — Structuren (VOLLEDIG KLAAR, 19 juli 2026)**

**Status:** Fase 1 én Fase 2 zijn volledig af — bevestigd na code-review van `math.py`. Onderstaande punten stonden nog als "volgende stap"/➤ terwijl de code allang verder is. Unit-module gaat zelfs verder dan hieronder beschreven (temperatuurconversie, honderden afgeleide/prefix-eenheden via SI-tabel).

### ✅ 4. **Vector‑module**

Nova leert:
✔- `[1,2,3] + [4,5,6]`
✔- `dot([1,2],[3,4])`
✔- `cross([1,0,0],[0,1,0])`
✔- `norm([3,4])`

### ✅ 5. **Matrix‑module**

Nova leert:
✔- matrices optellen
✔- matrices vermenigvuldigen
✔- determinant
✔- inverse
✔- transponeren
✔- Rotatiematrices
✔- lineaire systemen oplossen
✔-Gauss‑eliminatie

### ✅ 6. **Unit‑module** (zonder semantic)

Nova leert:
✔- `5m + 30cm` → `5.3m`
✔- `3m / 2s` → `1.5 m/s`
✔- `10kg * 2`
✔- temperatuurconversie (°C/°F/K)
✔- SI-afgeleide eenheden (N, Pa, J, W, V, Ω, ...) + prefixen (k, m, µ, ...)

---

## ⚠️ **Bekend aandachtspunt — `detect_math()` trigger te breed**

`intent_router.py`'s `detect_math()` checkt `any(op in t for op in ["+", "-", "*", "/", "^"])` als kale substring-check, zonder woordgrenzen. Dit is dezelfde soort bug als de al-gefixte `tan`-in-`toestand`-issue (zie werkpunt in `nova_state.md`, 11 juli 2026), maar dan bij de operator-check. Een zin met een gedachtestreepje ("ik ga - denk ik - straks koken") triggert nu math_intent. Nog niet gefixt, geen prioriteit zolang het geen concrete problemen geeft in de praktijk — wel iets om in de gaten te houden.

---

## **FASE 3 — Numerieke intelligentie**

### ✅ 7. **Algebra‑module (numeriek)** (klaar, getest 2 aug 2026)

- ✔ kwadratische vergelijkingen — `solveQuadratic()` / NL-alias `wortel()`, abc-formule
- ✔ wortels zoeken (Newton‑Raphson) — `newton()` / NL-alias `nulpunt()`
- ✔ polynoom‑evaluatie — `polyeval()` / NL-alias `bereken()`
- ✔ minima/maxima zoeken — `extremum()` / NL-alias `minmax()`

Architectuur: `newton`/`polyeval`/`extremum` werken met **vrije expressies**
(bv. `x^2 - 4`), niet met coëfficiënten-lijsten — bewuste keuze zodat Kevin
geen aparte notatie hoeft te onthouden. Dit vroeg een kleine, backward-
compatible uitbreiding van `_eval()` met een optioneel `variables`-dict.

Onderweg gevonden en opgelost, tijdens dezelfde sessie:

- `extremum()` gaf een rauwe Python-dict met floating-point-ruis terug
  (bv. `4.999999999999916` i.p.v. `5`) — nu afgerond en als leesbare
  Nederlandse zin in `on_math()`.
- Bug in bestaande `preprocess()`-regel (1b, getal-exponent zonder ^):
  greep ten onrechte ook in bij `x^2-4` (al een `^` ervoor), en maakte er
  `x**2**-4` van i.p.v. `x**2-4`. Gefixt met een negative lookbehind
  (`(?<!\^)`), getest tegen bestaande units-berekeningen (`m/s^2`,
  `10^-4`) om zeker te zijn dat er geen regressie was.

### ✅ 8. **Calculus‑module (numeriek)** (klaar, getest 2 aug 2026)

- ✔ numerieke afgeleiden — `afgeleide()`, centraal verschil
- ✔ numerieke integralen — `integraal()`, regel van Simpson
- ✔ limieten benaderen — `limiet()`, van links én rechts, geeft eerlijk aan als de limiet niet lijkt te bestaan
- ✔ differentiaalvergelijkingen — `dv()` (standaard RK4), `dv_euler()`, `dv_rk4()` — vorm `f(x,y), y0, van, tot` (wiskundige standaardnotatie voor dy/dx=f(x,y))

Onderweg gevonden en opgelost, tijdens dezelfde sessie:

- Bug in bestaande `preprocess()`-regel (unit+exponent, bv. `m3`→`m^3`):
  greep ten onrechte ook in bij functienamen die op een cijfer eindigen
  (bv. `dv_rk4(...)` → fout omgezet naar `dv_rk^4(...)`). Gefixt met een
  negative lookahead die niet ingrijpt als er een `(` op volgt — getest
  tegen alle bestaande units-berekeningen, geen regressie.
- `_eval()`'s `variables`-mechanisme (gebouwd in punt 7 voor `x`) is nu
  uitgebreid naar twee gelijktijdige variabelen (`x` én `y`) voor de
  DV-functies, zonder de bestaande een-variabele-functies te raken.

### ✅ 9. **Statistiek‑module** (klaar, getest 2 aug 2026)

- ✔ gemiddelden — `gemiddelde()`, `mediaan()`, `modus()`
- ✔ variantie — `variantie()` (steekproefvariantie, deelt door n-1), `stdafwijking()`
- ✔ regressie — `regressie()`, lineaire regressie via kleinste-kwadratenmethode
- ✔ correlatie — `correlatie()`, Pearson-coëfficiënt
- ✔ kansberekeningen — `faculteit()`, `combinaties()`, `permutaties()`,
  `binomiaal()` (binomiale verdeling), `normaal()` (cumulatieve normale
  verdeling via Python's ingebouwde `math.erf()` — exacte formule, geen
  ML/schatting)

**FASE 3 — Numerieke intelligentie is hiermee volledig afgerond** (punt 7 Algebra, punt 8 Calculus, punt 9 Statistiek — alle drie getest in Nova zelf).

Onderweg gevonden en opgelost, tijdens dezelfde sessie:

- Kleine consistentie-bugfix: `_check_getallenlijst()`'s eerste
  foutmelding miste een dubbele punt na de functienaam, waardoor hij
  per ongeluk via het technische "Er ging iets mis:"-voorvoegsel liep
  i.p.v. rechtstreeks als leesbare Nederlandse foutmelding getoond te
  worden.

---

## **FASE 4 — High‑level engines**

### ✅ 10. **Symbolische algebra** (klaar, getest 2 aug 2026)

- ✔ `differentiate()` — symbolisch differentiëren, geeft een formule terug
- ✔ `solve_sym()` — exact oplossen, inclusief hogere-graads vergelijkingen
- ✔ `simplify_sym()`, `expand_sym()`, `factor_sym()`, `integrate_sym()` — als bonus bovenop wat de roadmap oorspronkelijk vroeg

**Architectuurkeuze: SymPy** (externe bibliotheek), niet volledig eigen code — enige uitzondering in heel math.py. Reden: een eigen symbolische differentiator + vereenvoudiger bouwen die ook maar enigszins met Wolfram Alpha-niveau (goniometrische identiteiten, hogere-graads factorisatie) kan meekomen, zou een apart project van weken zijn. SymPy blijft 100% symbolisch/deterministisch — geen ML/LLM, geen "gokken", enkel vaste algebraïsche regels toegepast op een expressieboom, exact zoals de rest van math.py.

**Veiligheidsmaatregel:** SymPy's normale manier om een string in te lezen (`sympify()`) voert intern Python's `eval()` uit — een reëel risico (bevestigd met een test die `__import__('os').system(...)` liet uitvoeren). Opgelost door Nova's eigen, al beveiligde AST-parser te hergebruiken met een strikte functienaam-whitelist, nooit de ruwe tekst rechtstreeks aan SymPy geven.

**Belangrijke bugfix, ontdekt tijdens het testen, raakt bestaande Fase 3-functies:** een bestaande preprocess-regel (getal+letter → eenheid-met-macht, bv. "5m2"→"5m^2") greep ten onrechte ook in bij `3x^2` (bedoeld als 3·x²), en maakte er `(3x)^2` = 9x² van. Trof `afgeleide()`, `newton()`, `polyeval()`, `extremum()`, `integraal()`, `limiet()`, `dv()` — overal waar een coëfficiënt vóór een macht van x staat. Gefixt met een lookahead-uitzondering, volledig geregressietest tegen alle bestaande eenheden- en Fase 3-functionaliteit.

### ✅ 11. **Fysica‑engine** (klaar, getest 2 aug 2026)

Klassieke (Newtoniaanse) mechanica voor één object, 100% eigen Python-code (geen externe bibliotheek nodig), hergebruikt het bestaande eenhedensysteem:

- ✔ krachten — `kracht()` (F=ma)
- ✔ energie — `energie_kinetisch()` (E=½mv²), `energie_potentieel()` (E=mgh), `arbeid()` (W=F·d)
- ✔ beweging — `snelheid_na()`, `afstand_na()` (eenparig versnelde beweging)
- ✔ projectielbanen — `projectiel()`, geeft bereik/max. hoogte/vluchttijd
- ✔ simulaties — `val_met_weerstand()`, numerieke simulatie (val met luchtweerstand heeft geen gesloten-vorm-formule, gekoppeld stelsel hoogte+snelheid stap voor stap doorgerekend)

**FASE 4 — High-level engines is hiermee volledig afgerond** (punt 10 Symbolische algebra via SymPy, punt 11 Fysica-engine — beide getest in Nova zelf).

**Bewuste afbakening:** één object tegelijk, geen botsingen tussen meerdere objecten, geen rotatie/traagheidsmomenten, geen andere vakgebieden (elektromagnetisme, thermodynamica) — dat zou een apart project zijn.

Onderweg gevonden en opgelost, tijdens dezelfde sessie:

- `m/s` bestond niet als losse eenheid-sleutel in het bestaande `self.units`-systeem (enkel als resultaat van een berekening zoals `m/s`) — opgelost door zelf een `UnitValue` met de juiste dimensies te bouwen in `snelheid_na()` en `val_met_weerstand()`.
- Klein afrondingsartefact in `energie_potentieel()` (`196.20000000000002`) opgeschoond met `round()`.

---

## **FASE 5 — Getaltheorie & CS-algoritmes (nog niet gepland)**

Alles hieronder is 100% puur symbolisch/deterministisch — geen ML/LLM nodig.

### ➤ 12. **Getaltheorie & combinatoriek**

- priemgetallen (test + genereren)
- ggd / kgv
- faculteit
- combinaties/permutaties (`nCr`, `nPr`)
- modulo-rekenen

### ➤ 13. **Complexe getallen**

- Python's ingebouwde `complex` type integreren in `_eval()` en de operator-afhandeling

### ➤ 14. **Extra eenheden**

- imperial-eenheden (mijl, pond, ...) naast bestaande SI-set
- basisconversies: binair / octaal / decimaal / hexadecimaal

### ➤ 15. **Klassieke CS-algoritmes (losstaande module, geen wiskunde maar wel symbolisch)**

- zoek-/sorteeralgoritmes (binary search, BFS/DFS, Dijkstra)
- string-/pattern-matching (Levenshtein/edit distance — nu al impliciet via `difflib`, hier pas expliciet als eigen functie)
- **Let op:** graafalgoritmes specifiek gericht op `concepts.json` (kortste pad tussen concepten, cykel-detectie, topologische sortering) horen inhoudelijk beter bij de semantic-roadmap, niet hier — enkel algemene/losstaande CS-algoritmes horen in math.

---

## **Aanvulling op Fase 3/5 — Precisie, notatie & exacte vormen (nog niet gepland)**

Ook hier: alles 100% puur symbolisch, geen ML/LLM nodig.

### ➤ 16. **Afronding & precisie**

- concept van significante cijfers (naast bestaande `round()`)
- instelbare precisie voor een sessie (relevant bij fysica-berekeningen met meetonzekerheid)

### ➤ 17. **Percentages als eersteklas notatie**

- `20% * 150` direct parsen i.p.v. handmatig omzetten naar `0.20 * 150`
- puur syntactische suiker rond bestaande vermenigvuldiging, geen nieuwe rekenlogica

### ➤ 18. **Breuken als exact type**

- Python's ingebouwde `fractions.Fraction` gebruiken i.p.v. float, zodat bv. `1/3 + 1/3` exact `2/3` geeft i.p.v. `0.666...`
- relevant zodra exacte antwoorden gewenst zijn i.p.v. decimale benaderingen

### ➤ 19. **Reeksen/rijen**

- rekenkundige/meetkundige reeksen (som van 1 t/m n, sommaties)
- sigma-notatie evalueren over een bereik
- sluit aan bij Fase 3's calculus-plannen

### ➤ 20. **Eenvoudige kansrekening (discreet)**

- basiskansberekening met combinatoriek (dobbelsteen, kaartspel-achtige modellen)
- nadrukkelijk iets anders dan Fase 3's "Statistiek-module" (die gaat over data/regressie/correlatie)

---
