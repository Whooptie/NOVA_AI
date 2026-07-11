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

## **FASE 2 — Structuren (volgende grote stap)**

### ✔ 4. **Vector‑module**  
Nova leert:  
✔- `[1,2,3] + [4,5,6]`  
✔- `dot([1,2],[3,4])`  
✔- `cross([1,0,0],[0,1,0])`  
✔- `norm([3,4])`  

### ➤ 5. **Matrix‑module**  
Nova leert:  
✔- matrices optellen  
✔- matrices vermenigvuldigen  
✔- determinant  
✔- inverse  
✔- transponeren
✔- Rotatiematrices 
✔- lineaire systemen oplossen  
✔-Gauss‑eliminatie

### ➤ 6. **Unit‑module** (zonder semantic)  
Nova leert:  
✔- `5m + 30cm` → `5.3m`  
✔- `3m / 2s` → `1.5 m/s`  
✔- `10kg * 2`  

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

