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

### ✅ 12. **Getaltheorie & combinatoriek** (klaar, getest 2 aug 2026)

- ✔ priemgetallen — `is_priem()` (test), `priemgetallen()` (genereren via Zeef van Eratosthenes)
- ✔ ggd / kgv — `ggd()`, `kgv()` (Euclidisch algoritme)
- ✔ faculteit — `faculteit()` *(al gebouwd in Fase 3, punt 9, hergebruikt hier)*
- ✔ combinaties/permutaties — `combinaties()`, `permutaties()` *(al gebouwd in Fase 3, punt 9, hergebruikt hier)*
- ✔ modulo-rekenen — `modulo()`, als aparte benoemde functie (i.p.v. kaal `%`) om verwarring met de toekomstige percentage-notatie (punt 17) te vermijden

Dat corrigeert de tekstuele checkbox, in lijn met wat we effectief gebouwd hebben. Zullen we

### ✅ 13. **Complexe getallen** (klaar, getest 2 aug 2026)

- ✔ Python's ingebouwde `complex`/`cmath` geïntegreerd — gebruiker typt `i` (wiskundige notatie), vertaald naar Python's `j` via een veilige placeholder-stap in `preprocess()`
- ✔ `solveQuadratic()` en `solve_sym()` tonen nu complexe oplossingen (bv. `x²+1=0` → `x = -i of x = i`) i.p.v. te weigeren zoals voorheen
- ✔ Nette weergave: `3 + 4i` i.p.v. Python's `(3+4j)`, `i`/`-i` i.p.v. `1i`/`-1i`

Onderweg gevonden en opgelost: de `i`→`j`-vertaling botste eerst met de bestaande eenheden-regex (die `4j` als "4 van eenheid j" zag, zelfde soort conflict als de eerdere "3x^2"-bug). Opgelost met een tijdelijke placeholder (`__IMAG__`) die pas na alle andere preprocessing naar `j` wordt omgezet.

**Bewuste voorzichtigheid in de router:** een kale, losstaande `i` wordt niet breed herkend als math-trigger (te generiek risico, vgl. Engelse tekst "I think..."). Enkel `cijfer+i` (bv. `4i`) wordt breed herkend.

### ✅ 14. **Extra eenheden** (klaar, getest 2 aug 2026)

- ✔ imperial-eenheden — grotendeels al aanwezig (mile, ft, inch, yard, lb, oz, gal, mph, enz.), aangevuld met `stone` (Britse gewichtseenheid) en `nmi` (nautische mijl)
- ✔ binair/octaal/decimaal/hexadecimaal — `naar_binair()`, `naar_octaal()`, `naar_hex()` (vanuit decimaal), `vanuit_talstelsel(tekst, grondtal)` voor de omgekeerde richting (grondtal 2 t/m 36)

Onderweg gevonden en opgelost: `nmi` (nautische mijl) botste met het bestaande prefix-systeem (`n`=nano-prefix × `mi`=mile gaf een compleet verkeerd resultaat, `1.6e-6 km` i.p.v. `1852 m`) — zelfde soort naamconflict als eerdere `L`/`mL`-bug. Opgelost met een expliciete herstelregel na het prefix-genererende blok.

### ✅ 15. **Klassieke CS-algoritmes** (klaar, getest 2 aug 2026)

- ✔ zoek-/sorteeralgoritmes — `binary_search()`, `bubble_sort()`, `quick_sort()`
- ✔ graafalgoritmes — `bfs()`, `dfs()` (ongewogen), `dijkstra()` (gewogen kortste pad)
- ✔ string-/pattern-matching — `levenshtein()`, nu ook expliciet oproepbaar (naast het al bestaande impliciete gebruik via `difflib`)

**Architectuur-uitbreiding:** eerste keer dat `_eval()` een `ast.Dict`-node moest verwerken (nodig om een graaf als `{"A": ["B","C"]}` te kunnen intypen voor bfs/dfs/dijkstra).

Onderweg gevonden en opgelost: de bestaande breuknotatie-regel (`:` → `/`, voor `10:4`) botste met dict-syntax — `{"A": [...]}` werd stiekem kapotgemaakt. Gefixt met een gerichte uitzondering (enkel een kale `getal:getal` wordt nog als breuk gelezen).

Bewuste afbakening gerespecteerd: geen graafalgoritmes specifiek voor `concepts.json` — die horen bij de semantic-roadmap.

## **Aanvulling op Fase 3/5 — Precisie, notatie & exacte vormen** (klaar, getest 2 aug 2026)

### ✅ 16. **Afronding & precisie**

- ✔ `significante_cijfers(getal, aantal)` — naast bestaande `round()`
- ✔ `stel_precisie_in(n)` / `reset_precisie()` — instelbare sessie-precisie, toegepast via `_format_value()`

### ✅ 17. **Percentages als eersteklas notatie**

- ✔ `20% * 150` direct parsen → `30` — puur syntactische suiker, vroege preprocess-stap, geen conflict met `modulo()`

### ✅ 18. **Breuken als exact type**

- ✔ `breuk(teller, noemer)` — Python's `Fraction`, `breuk(1,3)+breuk(1,6)` → `1/2` exact. Bewust een aparte, expliciete functie (geen wijziging aan bestaande `/`-deling)

### ✅ 19. **Reeksen/rijen**

- ✔ `som_reeks(van, tot)` (Gauss-formule), `sigma(expr, van, tot)` (hergebruikt het `EXPR_FUNCS`-mechanisme), `meetkundige_reeks(eerste_term, reden, aantal_termen)`

### ✅ 20. **Eenvoudige kansrekening (discreet)**

- ✔ `kans_dobbelsteen(aantal, som)`, `kans_kaart(gewenst, totaal, trek_aantal)` — hergebruikt `combinaties()`/`faculteit()` uit Fase 3, punt 9

**FASE 5 is hiermee volledig afgerond** (punt 12 t/m 20, alle negen onderdelen getest in Nova zelf).

Onderweg gevonden en opgelost: de generieke weergave-tak in `on_math()` gebruikte Python's rauwe `str()` i.p.v. `_format_value()`, waardoor `stel_precisie_in()` genegeerd werd voor gewone berekeningen (bv. `1/3`) — gefixt.

---
