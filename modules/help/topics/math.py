# modules/help/topics/math.py

def get_help():
    return """
🔢 Wiskunde-commando's — volledig overzicht

Alle notatie hieronder werkt zoals je het al gewend bent: "^" voor machten,
"i" voor de imaginaire eenheid, eenheden gewoon aan een getal plakken (5m,
30cm, 1kg). Waar iets een uitzondering heeft, staat dat er apart bij.

➕ BASISREKENKUNDE
  2 + 3 * 4                       (gewone rekenkunde, +-*/^)
  sqrt(16)  sin(x)  cos(x)  tan(x)  log(x)  ln(x)  exp(x)  abs(x)
  round(3.14159, 2)                (afronden op 2 decimalen)

📏 EENHEDEN & CONVERSIE
  5m + 30cm                       (optellen met verschillende eenheden)
  1kg.to(g)                       (omzetten naar een andere eenheid)
  25°C                            (temperatuur, ook °F)
  5mile.to(km)   1lb.to(kg)   1stone.to(kg)   10nmi.to(km)
                                   (imperial-eenheden + nautische mijl)
  3*m/s^2                         (samengestelde eenheden, bv. versnelling)

📐 VECTOREN & MATRICES
  dot([1,2,3], [4,5,6])           (inproduct)
  cross([1,0,0], [0,1,0])         (kruisproduct, enkel 3D)
  norm([3,4])                     (lengte van een vector)
  unit([3,4])                     (eenheidsvector, lengte 1)
  proj([1,2], [1,0])              (projectie van de ene vector op de andere)
  det([[1,2],[3,4]])              (determinant)
  inverse([[1,2],[3,4]])          (inverse matrix)
  transpose([[1,2],[3,4]])        (getransponeerde matrix)
  identity(3)                     (3x3 eenheidsmatrix)
  solve([[2,1],[1,3]], [5,10])    (stelsel vergelijkingen oplossen)
  rotX(90)   rotY(90)   rotZ(90)  (rotatiematrix rond een as, in graden)

➗ ALGEBRA (numeriek)
  wortel(1, -5, 6)                (kwadratische vergelijking oplossen)
  nulpunt(x^2 - 4, 1)             (wortel zoeken via Newton-Raphson)
  bereken(x^2 + 2x + 1, 3)        (expressie evalueren op een punt)
  minmax(-x^2 + 4x, 0, 5)         (minimum/maximum zoeken in een bereik)

📈 CALCULUS (numeriek)
  afgeleide(x^2, 3)               (helling in één punt)
  integraal(x^2, 0, 3)            (oppervlakte tussen twee punten)
  limiet(sin(x)/x, 0)             (limiet benaderen)
  dv(x - y, 1, 0, 5)              (differentiaalvergelijking oplossen, RK4)
  dv_euler(...)  dv_rk4(...)      (zelfde, met expliciete methode-keuze)

📊 STATISTIEK
  gemiddelde([1,2,3,4])   mediaan([1,3,2])   modus([1,2,2,3])
  variantie([2,4,4,4,5,5,7,9])   stdafwijking(...)
  regressie([1,2,3,4], [2,4,6,8])   (lineaire regressie)
  correlatie([1,2,3,4], [2,4,6,8])  (Pearson-coëfficiënt)
  binomiaal(10, 3, 0.5)           (kans op precies 3 successen bij 10 pogingen)
  normaal(0)                      (cumulatieve kans, standaard-normale verdeling)

🧮 SYMBOLISCHE ALGEBRA (geeft een formule terug, geen getal)
  differentiate(x^3 + 2x)         (symbolisch differentiëren)
  integrate_sym(x^2)              (symbolisch integreren)
  solve_sym(x^2 - 5x + 6 = 0)     (exact oplossen, ook hogere graad)
  solve_stelsel(x+y=10, x-y=2)    (stelsel met x EN y tegelijk oplossen)
  simplify_sym(sin(x)^2 + cos(x)^2)  (vereenvoudigen)
  expand_sym((x+1)^2)             (haakjes uitwerken)
  factor_sym(x^2 - 4)             (ontbinden in factoren)

🚀 FYSICA
  kracht(1000, 3)                 (F = m·a)
  energie_kinetisch(5, 10)        (E = ½mv²)
  energie_potentieel(2, 10)       (E = mgh)
  arbeid(50, 3)                   (W = F·d)
  snelheid_na(0, 9.81, 3)         (v = v0 + a·t)
  afstand_na(20, -5, 4)           (x = v0·t + ½a·t²)
  projectiel(20, 45)              (worp onder een hoek: bereik/hoogte/vluchttijd)
  val_met_weerstand(80, 1000, 0.2) (simulatie: val met luchtweerstand)

🔢 GETALTHEORIE & COMBINATORIEK
  is_priem(17)                    (is dit een priemgetal?)
  priemgetallen(30)               (alle priemgetallen tot een grens)
  ggd(48, 18)   kgv(4, 6)         (grootste gemene deler / kleinste gemene veelvoud)
  faculteit(5)   combinaties(5,2)   permutaties(5,2)
  modulo(17, 5)                   (de rest bij deling)

💫 COMPLEXE GETALLEN
  3 + 4i                          (typ "i" voor de imaginaire eenheid)
  (3+4i) * (1+2i)
  solveQuadratic(1, 0, 1)         (geeft nu ook complexe oplossingen)

🔡 TALSTELSELS
  naar_binair(255)   naar_octaal(255)   naar_hex(255)
  vanuit_talstelsel("ff", 16)      (van een ander talstelsel terug naar decimaal)

🧩 KLASSIEKE CS-ALGORITMES
  binary_search([1,3,5,7,9], 7)   (zoeken in een gesorteerde lijst)
  bubble_sort([5,2,8,1])   quick_sort([5,2,8,1])
  bfs({"A":["B","C"],"B":["D"]}, "A")   (graaf doorlopen, breadth-first)
  dfs({"A":["B","C"],"B":["D"]}, "A")   (graaf doorlopen, depth-first)
  dijkstra({"A":{"B":4,"C":2},"B":{"D":1}}, "A")  (kortste pad met gewichten)
  levenshtein("kitten", "sitting") (hoeveel bewerkingen tussen twee woorden)

🎯 PRECISIE & NOTATIE
  significante_cijfers(123456, 3)  (afronden op significante cijfers)
  stel_precisie_in(3)              (vaste precisie voor de rest van de sessie)
  reset_precisie()                 (precisie terug naar standaard)
  20% * 150                        (percentages direct intypen)
  breuk(1, 3) + breuk(1, 6)        (exacte breuken, geen afgeronde decimalen)

Σ REEKSEN & KANSREKENING
  som_reeks(1, 100)                (som van 1 t/m 100)
  sigma(x^2, 1, 5)                 (sigma-sommatie over een bereik)
  meetkundige_reeks(1, 2, 5)       (meetkundige reeks)
  kans_dobbelsteen(2, 7)           (kans op een bepaalde som met dobbelstenen)
  kans_kaart(4, 52, 5)             (kans op minstens 1 gewenste kaart)

ℹ️ Dit is het volledige overzicht van math.py. Voor de architectuur en
   redenen achter keuzes: zie math_roadmap.md.
""".strip()