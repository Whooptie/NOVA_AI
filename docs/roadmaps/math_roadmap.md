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

### ➤ 7. **Algebra‑module (numeriek)**  
- wortels zoeken (Newton‑Raphson)  
- kwadratische vergelijkingen  
- polynoom‑evaluatie  
- minima/maxima zoeken  

### ➤ 8. **Calculus‑module (numeriek)**  
- numerieke afgeleiden  
- numerieke integralen  
- limieten benaderen  
- differentiaalvergelijkingen (Euler, RK4)  

### ➤ 9. **Statistiek‑module**  
- gemiddelden  
- variantie  
- regressie  
- correlatie  
- kansberekeningen  

---

## **FASE 4 — High‑level engines**

### ➤ 10. **Symbolische algebra (optioneel)**  
- `solve("x^2 - 4 = 0")`  
- `differentiate("x^3 + 2x")`  

### ➤ 11. **Fysica‑engine**  
Gebaseerd op vectoren + calculus + units:  
- krachten  
- energie  
- beweging  
- projectielbanen  
- simulaties

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