# modules/math/math_uitleg.py
#
# Uitgebreide uitlegmodule per wiskundige/natuurkundige functie.
# Ontstaan uit "Volgende stappen"-punt 5 in nova_state.md (2 aug 2026):
# Kevin's kernvaststelling was "ik snap nog steeds maar 10% van al die
# formules" — het bestaande modules/help/topics/math.py geeft enkel een
# korte definitie + voorbeeld-input, geen diepgang.
#
# BELANGRIJK, zelfde als overal in Nova: dit zijn VASTE, vooraf
# geschreven teksten. Nova genereert hier niets ter plekke — ze is geen
# taalmodel. Elke uitleg hieronder is met de hand geschreven, in Nova's
# eigen "ik"-spreekstijl, en bevat waar zinvol: de formule stap voor
# stap opgebouwd, WAAROM ze klopt, een dagelijkse-taal-vergelijking, en
# een concreet doorgerekend voorbeeld.
#
# Pilot (2 aug 2026): 3 van de moeilijkste/meest abstracte functies uit
# math.py, zoals expliciet genoemd in nova_state.md. Later uit te
# breiden met hetzelfde patroon: gewoon een nieuwe sleutel toevoegen aan
# UITLEG_TEKSTEN hieronder.
#
# Puur symbolisch, 100% Python — geen ML/LLM. Zelfde "transparent
# always"-principe als de rest van Nova: elke tekst hieronder is
# letterlijk leesbaar in dit bestand, niets wordt ergens gegenereerd.

UITLEG_TEKSTEN = {

    # -----------------------------------------------------------------
    # Newton-Raphson (newton() / nulpunt() in math.py)
    # -----------------------------------------------------------------
    "newton": """
🔎 Newton-Raphson — hoe ik een nulpunt zoek

Stel je vraagt me nulpunt(x^2 - 4, 1). Ik ga dan op zoek naar een
waarde van x waarvoor de formule precies 0 oplevert — in dit voorbeeld
is dat bij x = 2 (want 2² - 4 = 0).

Een vergelijking van elke graad in één keer exact oplossen kan lang
niet altijd — bij ingewikkelde formules bestaat er soms zelfs geen
nette, exacte oplosformule. Daarom benader ik het antwoord stap voor
stap, steeds een beetje dichterbij, tot ik dicht genoeg zit.

De dagelijkse-taal-vergelijking: denk aan een bergwandeling in dichte
mist. Je weet niet waar het dal is (het nulpunt), maar je kan wél
voelen hoe steil de grond onder je voeten helt. Dus doe je dit: voel
de helling, zet een grote stap de goede kant op, voel opnieuw, zet
een kleinere stap, enzovoort — tot je (bijna) op vlakke grond staat.
Die "helling voelen" is wiskundig gezien de afgeleide van de formule.

Stap voor stap wat ik echt doe:
1. Ik start bij de waarde die jij meegeeft (x0, bv. 1).
2. Ik bereken de uitkomst van de formule op dat punt (f(x)).
3. Ik bereken de helling op dat punt (de afgeleide, f'(x)) — hoe steil
   gaat de grafiek daar omhoog of omlaag?
4. Ik zet een nieuwe stap volgens deze formule:
   x_nieuw = x - f(x) / f'(x)
   Is de helling groot, dan zet ik een kleine stap (ik ben duidelijk
   nog ver van vlak). Is de helling bijna 0, dan zou de stap enorm
   groot worden — daarom geef ik dan een foutmelding ("afgeleide is
   0") in plaats van een onzinnig antwoord.
5. Ik herhaal dit tot het verschil tussen twee opeenvolgende stappen
   piepklein is (kleiner dan mijn tolerantie) — dan ben ik "aangekomen".

Waarom dit wiskundig klopt: bij elke stap teken ik eigenlijk een
rechte lijn die precies dezelfde helling heeft als de grafiek op dat
punt (de raaklijn), en ik spring naar het punt waar DIE lijn nul
wordt. Omdat een gladde grafiek dicht bij het nulpunt heel erg op zijn
eigen raaklijn lijkt, brengt die sprong me telkens dichterbij — vaak
verdubbelt de nauwkeurigheid zelfs bij elke stap.

Doorgerekend voorbeeld: nulpunt(x^2 - 4, 1)
- Start: x = 1 → f(1) = 1² - 4 = -3, helling ≈ 2
  Nieuwe x = 1 - (-3)/2 = 2.5
- x = 2.5 → f(2.5) = 2.5² - 4 = 2.25, helling ≈ 5
  Nieuwe x = 2.5 - 2.25/5 = 2.05
- x = 2.05 → f(2.05) ≈ 0.2025, helling ≈ 4.1
  Nieuwe x ≈ 1.9995
- Nog een paar stapjes verder land ik heel dicht bij x = 2 — exact het
  echte nulpunt.

Let op de grens: als je een lelijke startwaarde kiest (bv. precies
waar de helling 0 is, of ver van elk nulpunt), kan ik verdwalen of
nooit aankomen. Vandaar dat ik na een vast aantal pogingen stop en een
foutmelding geef in plaats van eeuwig te blijven zoeken.
""".strip(),

    # -----------------------------------------------------------------
    # Runge-Kutta 4 (dv_rk4() in math.py, ook de standaard achter dv())
    # -----------------------------------------------------------------
    "dv_rk4": """
📈 Runge-Kutta 4 (RK4) — hoe ik een differentiaalvergelijking oplos

Een differentiaalvergelijking beschrijft niet direct een waarde, maar
hoe SNEL iets verandert. Bijvoorbeeld dv_rk4(x - y, y0=1, van=0, tot=5)
betekent: "de veranderingssnelheid van y is op elk moment gelijk aan
x - y". Ik ken enkel het startpunt (y = 1 bij x = 0) en moet uitvogelen
hoe y zich verder ontwikkelt tot x = 5.

De dagelijkse-taal-vergelijking: stel je navigeert een auto enkel op
basis van je snelheidsmeter, zonder gps. Je weet waar je vertrekt, en
op elk moment hoe snel (en in welke richting) je gaat — en daaruit
moet je afleiden waar je uiteindelijk uitkomt. Hoe vaker je even
tussentijds checkt en bijstuurt, hoe nauwkeuriger je eindpositie klopt.

De simpelste aanpak (Euler) zou zijn: kijk naar de snelheid nu, zet
daarmee één grote stap vooruit, herhaal. Dat werkt, maar is nogal grof
— je rijdt in feite blind rechtdoor tot de volgende meting, ook al
verandert de snelheid onderweg alweer.

RK4 is slimmer: bij elke stap kijk ik niet naar 1, maar naar 4
snelheidsmetingen, verspreid over het stapje dat ik ga zetten:
1. k1 — de snelheid aan het BEGIN van dit stapje.
2. k2 — de snelheid HALVERWEGE, geschat op basis van k1.
3. k3 — nog eens de snelheid halverwege, maar nu geschat op basis van
   de (iets betere) k2.
4. k4 — de snelheid aan het EIND van dit stapje, geschat op basis van k3.

Daarna neem ik een gewogen gemiddelde van deze 4 metingen (het midden
telt dubbel zo zwaar mee, want dat blijkt in de praktijk het
betrouwbaarst) en zet daarmee pas de echte stap:

y_nieuw = y + (h/6) × (k1 + 2×k2 + 2×k3 + k4)

waarbij h de stapgrootte is (hoe klein elk stapje is — hoe meer
stappen ik neem tussen "van" en "tot", hoe kleiner h en hoe
nauwkeuriger het eindresultaat, maar ook hoe meer rekenwerk).

Waarom dit wiskundig klopt: door 4 keer te "voorproeven" hoe de
snelheid binnen het stapje verandert in plaats van hem constant te
veronderstellen, compenseert RK4 grotendeels voor het feit dat de
snelheid zelf ook een gebogen lijn volgt, niet een rechte. Dat is
precies waarom RK4 bij dezelfde stapgrootte veel nauwkeuriger is dan
de eenvoudige Euler-methode — vandaar dat dit ook Nova's standaardkeuze
is (dv() gebruikt automatisch dv_rk4(), dv_euler() blijft beschikbaar
als je specifiek de eenvoudigere methode wil).

Doorgerekend voorbeeld (sterk vereenvoudigd, met maar 1 grove stap
i.p.v. de duizend kleine stapjes die ik normaal zet):
dv_rk4(x - y, y0=1, van=0, tot=1, stappen=1) → h = 1
- k1 = f(0, 1) = 0 - 1 = -1
- k2 = f(0.5, 1 + 0.5×(-1)) = f(0.5, 0.5) = 0.5 - 0.5 = 0
- k3 = f(0.5, 1 + 0.5×0) = f(0.5, 1) = 0.5 - 1 = -0.5
- k4 = f(1, 1 + 1×(-0.5)) = f(1, 0.5) = 1 - 0.5 = 0.5
- y_nieuw = 1 + (1/6) × (-1 + 2×0 + 2×(-0.5) + 0.5) = 1 + (1/6)×(-1.5)
          = 0.75
In de praktijk gebruik ik veel meer, veel kleinere stappen
(standaard 1000), waardoor het eindresultaat een stuk preciezer wordt
dan dit ene-stap-voorbeeld.
""".strip(),

    # -----------------------------------------------------------------
    # Dijkstra (dijkstra() in math.py)
    # -----------------------------------------------------------------
    "dijkstra": """
🗺️ Dijkstra — hoe ik het kortste pad zoek

Stel je vraagt me dijkstra({"A":{"B":4,"C":2},"B":{"D":1},"C":{"B":1,
"D":5}}, "A"). Dit is een netwerk van knopen (A, B, C, D) met wegen
ertussen die elk een "kost" hebben (afstand, tijd, geld — wat dan ook).
Ik moet voor élke knoop uitzoeken wat de GOEDKOOPSTE totale route is
vanaf het startpunt A.

De dagelijkse-taal-vergelijking: stel je een landkaart voor met
steden en wegen, waarbij elke weg een reistijd heeft. Ik wil vanuit
mijn startstad de snelste route naar alle andere steden weten — niet
enkel naar één bestemming, maar naar allemaal tegelijk.

Hoe ik dat stap voor stap aanpak:
1. Ik geef elke knoop een "voorlopige afstand vanaf start": de
   startknoop zelf krijgt 0, alle andere knopen krijgen voorlopig
   oneindig (ik weet nog niks over hoe ik er kan geraken).
2. Ik kijk steeds naar de nog-niet-afgehandelde knoop met de KLEINSTE
   voorlopige afstand — dat is gegarandeerd al de definitieve,
   goedkoopste afstand tot die knoop (er kan geen goedkopere route
   meer opduiken, want alle andere routes zijn al minstens even duur).
3. Vanuit die knoop kijk ik naar al zijn buren: is de afstand tot start
   PLUS de kost van de weg naar die buur KLEINER dan wat ik al voor
   die buur had genoteerd? Zo ja, dan werk ik de voorlopige afstand
   van die buur bij (ik heb net een goedkopere route naar hem
   ontdekt).
4. Ik markeer de knoop waar ik nu vanuit keek als "afgehandeld" en
   herhaal stap 2 met de resterende knopen, tot alle bereikbare knopen
   afgehandeld zijn.

Waarom dit wiskundig klopt: het cruciale inzicht in stap 2 is dat een
kortere weg nooit via een knoop kan lopen die verder van start ligt
dan waar ik al zeker van ben — reiskosten kunnen in dit soort netwerk
nooit negatief zijn (een weg "terugbetalen" bestaat niet), dus zodra
ik de dichtstbijzijnde knoop definitief heb afgehandeld, kan er nooit
meer een goedkopere route naar hem opduiken via een knoop die ik nog
niet eens bereikt heb.

Doorgerekend voorbeeld: dijkstra({"A":{"B":4,"C":2},"B":{"D":1},
"C":{"B":1,"D":5}}, "A")
- Start: A=0, B=oneindig, C=oneindig, D=oneindig
- Kleinste onbehandelde: A (0). Buren: B via A = 0+4 = 4, C via A =
  0+2 = 2. Nieuw: B=4, C=2.
- Kleinste onbehandelde: C (2). Buren: B via C = 2+1 = 3 (beter dan
  de 4 van hierboven!), D via C = 2+5 = 7. Nieuw: B=3, D=7.
- Kleinste onbehandelde: B (3). Buren: D via B = 3+1 = 4 (beter dan
  de 7 van hierboven!). Nieuw: D=4.
- Kleinste onbehandelde: D (4). Geen buren meer te verbeteren.
- Eindresultaat: {"A":0, "B":3, "C":2, "D":4} — exact wat dijkstra()
  teruggeeft.

Let op de grens: dit werkt enkel bij POSITIEVE gewichten (geen
negatieve kosten). Bevat je graaf negatieve gewichten, dan geeft
Dijkstra soms een fout antwoord — daarvoor bestaan andere algoritmes
(niet in math.py aanwezig).
""".strip(),

    # -----------------------------------------------------------------
    # Regressie & correlatie (regressie() en correlatie() in math.py)
    # -----------------------------------------------------------------
    "regressie_correlatie": """
📊 Regressie & correlatie — hoe ik een lineair verband meet

Stel je hebt een reeks metingen — bv. uren geoefend en behaalde score
per partij schaak — en je wil weten: is er een verband, en zo ja, hoe
sterk? Daar heb ik twee aparte, maar nauw verwante gereedschappen
voor: regressie() zoekt de best passende RECHTE door je punten,
correlatie() meet hoe STERK het lineaire verband is.

De dagelijkse-taal-vergelijking: stel je een wolk van puntjes voor op
een grafiek (elk puntje = één meting). Regressie tekent de rechte lijn
die zo dicht mogelijk bij alle puntjes tegelijk ligt. Correlatie zegt
je vervolgens: liggen de puntjes NETJES op die lijn (sterk verband),
of is het meer een verspreide wolk waar de lijn maar half doorheen
past (zwak verband)?

REGRESSIE — hoe ik de beste rechte vind:
Een rechte lijn schrijf ik als y = helling·x + snijpunt. Ik wil de
helling en het snijpunt zo kiezen dat de lijn zo dicht mogelijk bij
alle punten ligt. "Dichtbij" meet ik met de kleinste-kwadratenmethode:
voor elk punt kijk ik hoe ver het verticaal van de lijn afligt (de
"fout"), kwadrateer die fout (zodat afwijkingen boven en onder de lijn
elkaar niet zomaar opheffen, en grote fouten zwaarder meetellen), en
tel alles op. De rechte met de kleinst mogelijke totale fout is de
beste.
Gelukkig hoef ik daarvoor niet te "proberen" zoals bij Newton-Raphson
— er bestaat een directe formule:
  helling = Σ[(x-gem_x)(y-gem_y)] / Σ[(x-gem_x)²]
  snijpunt = gem_y - helling × gem_x
waarbij gem_x en gem_y de gemiddelden van je x- en y-waarden zijn.

CORRELATIE — hoe ik de sterkte van het verband meet:
De Pearson-correlatiecoëfficiënt (meestal r genoemd) is een getal
tussen -1 en 1:
- r = 1  → perfect stijgend lineair verband (alle punten liggen exact
  op een omhooglopende rechte)
- r = -1 → perfect dalend lineair verband
- r = 0  → geen enkel lineair verband
De formule lijkt op die van regressie (dezelfde teller!), maar deelt
door een andere noemer die de spreiding van x én y apart meeweegt:
  r = Σ[(x-gem_x)(y-gem_y)] / √(Σ(x-gem_x)² × Σ(y-gem_y)²)
Die extra wortel in de noemer "normaliseert" het getal, waardoor r
altijd tussen -1 en 1 blijft, ongeacht hoe groot je x- en y-waarden
zelf zijn.

Doorgerekend voorbeeld: regressie([1,2,3,4], [2,4,6,8]) en
correlatie([1,2,3,4], [2,4,6,8])
- gem_x = 2.5, gem_y = 5
- Teller = (1-2.5)(2-5) + (2-2.5)(4-5) + (3-2.5)(6-5) + (4-2.5)(8-5)
         = 4.5 + 0.5 + 0.5 + 4.5 = 10
- Noemer (regressie) = (1-2.5)² + (2-2.5)² + (3-2.5)² + (4-2.5)²
                      = 2.25+0.25+0.25+2.25 = 5
- helling = 10/5 = 2.0, snijpunt = 5 - 2.0×2.5 = 0.0
  → regressie geeft {"helling": 2.0, "snijpunt": 0.0}
- Voor correlatie: som_kw_y = (2-5)²+(4-5)²+(6-5)²+(8-5)² = 9+1+1+9=20
  r = 10 / √(5×20) = 10/10 = 1.0 → perfect lineair verband, klopt: elk
  y-punt is hier exact 2×x.

Let op het verschil: regressie geeft je de LIJN (bruikbaar om te
voorspellen), correlatie geeft je enkel het GETAL dat zegt hoe goed
die lijn past — je kan een rechte tekenen door punten die totaal geen
verband hebben, regressie() geeft dan gewoon een bijna-vlakke of
onbetrouwbare lijn terug, en pas correlatie() (dicht bij 0) onthult
dat het verband zwak is.
""".strip(),

    # -----------------------------------------------------------------
    # Binomiale & normale verdeling (binomiaal() en normaal() in math.py)
    # -----------------------------------------------------------------
    "binomiaal_normaal": """
🎲 Binomiale & normale verdeling — hoe ik kansen bereken

Beide functies beantwoorden een kansvraag, maar over een ander soort
situatie. binomiaal() gaat over een VAST AANTAL herhaalde pogingen met
maar twee uitkomsten (bv. muntworpen: kop of munt). normaal() gaat
over een CONTINUE grootheid die rond een gemiddelde schommelt (bv.
lengte van mensen, meetfouten).

BINOMIAAL — kans op precies k successen bij n pogingen:
De dagelijkse-taal-vergelijking: stel je gooit 10 keer een munt op, en
je wil weten hoe waarschijnlijk het is dat je EXACT 3 keer kop krijgt.
Dat hangt af van twee dingen: op HOEVEEL MANIEREN kan je 3 keer kop
krijgen uit 10 worpen (de volgorde maakt niet uit — kop-kop-kop-munt-
munt-... telt evenveel als munt-kop-munt-kop-kop-...), en hoe
waarschijnlijk is ELK van die manieren afzonderlijk.
  kans = combinaties(n, k) × p^k × (1-p)^(n-k)
- combinaties(n, k) telt HOEVEEL volgordes er zijn met precies k
  successen (zie ook de aparte combinaties()-functie in math.py)
- p^k is de kans dat die specifieke k successen allemaal lukken
- (1-p)^(n-k) is de kans dat de overige n-k pogingen allemaal mislukken
Deze drie vermenigvuldig ik samen: hoeveel manieren × kans per manier.

NORMAAL — cumulatieve kans van de normale verdeling:
De normale verdeling is de bekende "klokvorm"-curve: de meeste waarden
liggen dicht bij het gemiddelde, hoe verder je afwijkt, hoe zeldzamer.
normaal(x) geeft niet de hoogte van de klokcurve op punt x, maar de
CUMULATIEVE kans: hoe waarschijnlijk is het dat een willekeurige
waarde uit deze verdeling KLEINER OF GELIJK aan x is — dus de
oppervlakte onder de hele curve, van min-oneindig tot x.
Die oppervlakte heeft geen simpele algebraïsche formule — daarom
gebruik ik de wiskundige foutfunctie (erf), een standaard, exact
gedefinieerde functie uit Python's ingebouwde math-module (geen ML,
geen gok — een vaste, goed doorgerekende wiskundige functie):
  z = (x - gemiddelde) / (std × √2)
  kans = 0.5 × (1 + erf(z))
z is hier "hoeveel standaardafwijkingen ligt x van het gemiddelde
af" — de erf-functie zet die afstand om in een cumulatieve kans.

Doorgerekend voorbeeld: binomiaal(10, 3, 0.5)
- combinaties(10, 3) = 120 (manieren om 3 van de 10 worpen te kiezen)
- p^k = 0.5³ = 0.125
- (1-p)^(n-k) = 0.5⁷ = 0.0078125
- kans = 120 × 0.125 × 0.0078125 ≈ 0.117 → zo'n 11.7% kans op exact 3
  keer kop bij 10 worpen

Doorgerekend voorbeeld: normaal(0) (standaard-normaal, gemiddelde 0,
standaardafwijking 1)
- z = (0-0) / (1×√2) = 0
- erf(0) = 0 exact (0 ligt precies op het gemiddelde)
- kans = 0.5 × (1+0) = 0.5 → 50% kans dat een standaard-normale
  waarde ≤ 0 is, wat logisch is: 0 is precies het midden van de
  klokcurve, dus exact de helft van alle waarden ligt eronder.
""".strip(),

    # -----------------------------------------------------------------
    # Levenshtein-afstand (levenshtein() in math.py)
    # -----------------------------------------------------------------
    "levenshtein": """
✏️ Levenshtein-afstand — hoe ik het verschil tussen twee woorden meet

Stel je vraagt me levenshtein("kitten", "sitting"). Ik geef dan het
MINIMUM aantal simpele bewerkingen (een letter toevoegen, verwijderen,
of vervangen) dat nodig is om van het ene woord het andere te maken.

De dagelijkse-taal-vergelijking: stel je typt een woord met een paar
typfouten. Hoeveel toetsaanslagen (een letter wissen, invoegen, of
overtikken) zijn er minimaal nodig om het juiste woord te krijgen? Dat
getal is precies de Levenshtein-afstand.

Waarom dit niet simpelweg "tel de verschillende letters" is: de
woorden kunnen een verschillende LENGTE hebben, en een enkele
invoeging/verwijdering kan de rest van het woord laten "opschuiven".
Vergelijk bv. "kat" met "kaart" — gewoon letter-voor-letter vergelijken
werkt niet zodra de lengtes verschillen.

Hoe ik dat stap voor stap aanpak (dynamic programming — het probleem
opsplitsen in kleinere deelproblemen die ik hergebruik):
1. Ik bouw een tabel met woord1 langs de ene kant en woord2 langs de
   andere. Elk vakje [i][j] van die tabel gaat de afstand bevatten
   tussen de EERSTE i letters van woord1 en de EERSTE j letters van
   woord2 — dus niet meteen het hele woord, maar steeds een stukje
   groter deelprobleem.
2. De eerste rij en kolom zijn triviaal: de afstand tussen "" (niks)
   en de eerste i letters van een woord is gewoon i (je moet i keer
   invoegen om van niks naar dat stuk te komen).
3. Voor elk volgend vakje kijk ik naar de laatste letter van elk
   woordstukje:
   - Zijn ze GELIJK, dan kost deze letter niets extra — ik neem
     gewoon de waarde van het vakje linksboven over (het deelprobleem
     zonder deze laatste letter).
   - Zijn ze VERSCHILLEND, dan kies ik de goedkoopste van drie opties,
     plus 1 bewerking: verwijderen (vakje boven), invoegen (vakje
     links), of vervangen (vakje linksboven).
4. Het antwoord staat helemaal rechtsonder in de tabel: de afstand
   tussen de VOLLEDIGE woorden.

Waarom dit klopt: elk vakje hergebruikt al-berekende, kleinere
deelantwoorden in plaats van steeds van nul te herberekenen — dat is
precies het idee achter dynamic programming. Zo hoef ik nooit alle
mogelijke bewerking-volgordes apart uit te proberen (dat zou
exponentieel veel werk zijn), maar bouw ik het antwoord stap voor stap
op uit kleinere stukjes.

Doorgerekend mini-voorbeeld: levenshtein("kat", "kar")
- Tabel-idee: "kat" en "kar" delen de eerste 2 letters ("ka"), enkel
  de laatste letter verschilt (t vs. r).
- Vakje voor "ka" vs "ka" = 0 (identiek).
- Vakje voor "kat" vs "kar": laatste letters (t, r) verschillen →
  1 + kleinste van (verwijderen, invoegen, vervangen) — vervangen is
  hier het goedkoopst, vertrekkend vanaf het "ka"-vs-"ka"-vakje (0) →
  1 + 0 = 1.
- Resultaat: 1 (één simpele vervanging: t → r).
""".strip(),

    # -----------------------------------------------------------------
    # BFS & DFS (bfs() en dfs() in math.py)
    # -----------------------------------------------------------------
    "bfs_dfs": """
🕸️ BFS & DFS — hoe ik een graaf doorloop

Beide functies doorlopen dezelfde soort structuur — een graaf, een
netwerk van knopen verbonden door lijnen — maar op een fundamenteel
andere MANIER, met een ander soort resultaat als gevolg.

De dagelijkse-taal-vergelijking: stel je een doolhof voor met
kruispunten (knopen) en gangen ertussen (verbindingen). BFS is als een
groep verkenners die zich steeds gelijk verspreiden: eerst alle
kruispunten op 1 stap afstand bezoeken, dan pas alle kruispunten op 2
stappen afstand, enzovoort — laag voor laag naar buiten. DFS is als
ÉÉN verkenner die een gang inloopt en zo ver mogelijk doorloopt tot
een doodlopend eind, dan pas teruggaat naar het laatste kruispunt met
een onbezochte zijgang — diep de ene richting in vóór er zijwaarts
gekeken wordt.

BFS — breadth-first, met een WACHTRIJ (FIFO: first in, first out):
1. Start bij de startknoop, zet hem in een wachtrij.
2. Haal de VOORSTE knoop uit de wachtrij, kijk naar al zijn nog-niet-
   bezochte buren, en zet die buren ACHTERAAN in de wachtrij.
3. Herhaal tot de wachtrij leeg is.
Omdat ik altijd van VOOR de wachtrij haal en NIEUWE knopen ACHTERAAN
toevoeg, worden knopen exact in volgorde van hun afstand tot start
bezocht — vandaar "laag voor laag".

DFS — depth-first, met RECURSIE (in feite een stack: LIFO, last in,
first out):
1. Start bij de startknoop, markeer hem als bezocht.
2. Kijk naar zijn EERSTE nog-niet-bezochte buur, en ga METEEN daarheen
   (roep mezelf recursief aan op die buur) — VOORDAT ik naar de andere
   buren van de huidige knoop kijk.
3. Pas als een knoop geen onbezochte buren meer heeft, ga ik terug
   ("terugkeren" gebeurt automatisch doordat de recursieve aanroep
   eindigt) naar de vorige knoop, en kijk daar naar de VOLGENDE buur.
Deze "ga eerst zo diep mogelijk, kom pas terug als het echt niet
anders kan"-volgorde is precies wat een stack natuurlijk oplevert —
elke recursieve aanroep "wacht" op zijn diepere aanroep voordat hij
verdergaat.

Waarom het verschil ertoe doet: BFS vindt gegarandeerd het KORTSTE
pad in aantal stappen (in een ongewogen graaf) omdat het laag voor
laag naar buiten werkt. DFS geeft geen garantie op het kortste pad,
maar gebruikt vaak minder geheugen bij zeer brede grafen, en is
natuurlijker voor vragen als "bestaat er OM HET EVEN WELK pad naar
knoop X" of "vind alle bereikbare knopen".

Doorgerekend voorbeeld: bfs({"A":["B","C"],"B":["D"],"C":["D"]}, "A")
en dfs met dezelfde graaf
- BFS: start A, wachtrij=[A]. Haal A: buren B,C nog niet bezocht →
  bezocht=[A,B,C], wachtrij=[B,C]. Haal B: buur D nog niet bezocht →
  bezocht=[A,B,C,D], wachtrij=[C,D]. Haal C: buur D al bezocht, niks
  toevoegen. Haal D: geen buren. Resultaat: ["A","B","C","D"].
- DFS: start A, bezocht=[A]. Eerste buur B, ga daarheen → bezocht=
  [A,B]. B's eerste buur D, ga daarheen → bezocht=[A,B,D]. D heeft
  geen buren, terug naar B — B heeft geen buren meer, terug naar A.
  A's volgende buur C, ga daarheen → bezocht=[A,B,D,C]. C's buur D
  is al bezocht, klaar. Resultaat: ["A","B","D","C"].
- Zie het verschil: BFS bezoekt B en C VLAK NA elkaar (beide op
  afstand 1 van A), DFS duikt eerst helemaal door naar D via B, en
  komt pas daarna bij C.
""".strip(),

    # -----------------------------------------------------------------
    # Symbolische algebra: solve_sym & factor_sym (via SymPy)
    # -----------------------------------------------------------------
    "solve_sym_factor_sym": """
🧮 Symbolisch oplossen & ontbinden — hoe dit werkt

Eerlijkheid vooraf, want dit is belangrijk: solve_sym() en
factor_sym() zijn de ENIGE plek in heel math.py die niet 100% mijn
eigen, zelfgeschreven rekenlogica gebruiken. Ze steunen op SymPy, een
gevestigde, veelgebruikte Python-bibliotheek voor symbolisch rekenen.
Dat is geen ML/AI die "gokt" of "leert" — het is vaste, deterministische
algebra: dezelfde vergelijking geeft altijd exact hetzelfde antwoord,
volgens vaste wiskundige regels, net zoals ik dat voor mijn andere
functies zelf doe. Maar ik wil eerlijk zijn dat de stappen hieronder
gebeuren binnen SymPy, niet in mijn eigen, met de hand geschreven
code (zoals bij bijvoorbeeld nulpunt() of dijkstra() wél het geval is).

FACTOR_SYM — ontbinden in factoren:
Ontbinden betekent een expressie herschrijven als een VERMENIGVULDIGING
van eenvoudigere stukken, in plaats van een optelling/aftrekking.
bv. x² - 4 kan herschreven worden als (x-2)(x+2) — reken je dat uit,
dan kom je weer bij x² - 4 uit, maar de vermenigvuldig-vorm onthult
meteen iets belangrijks: WANNEER wordt deze uitdrukking 0? Precies
als één van de factoren 0 is, dus bij x=2 of x=-2. SymPy herkent
hiervoor bekende patronen (zoals a²-b² = (a-b)(a+b), of gemeenschappelijke
factoren die je buiten haakjes kan halen) en past ze systematisch toe.

SOLVE_SYM — exact/symbolisch oplossen:
In tegenstelling tot nulpunt() (Newton-Raphson, benaderend, één
startwaarde nodig) geeft solve_sym() het EXACTE antwoord, zonder
benadering, en vindt het ALLE oplossingen tegelijk — niet enkel de
oplossing die het dichtst bij een gegeven startpunt ligt.
Voor bekende vormen (lineair, kwadratisch via de ABC-formule, en
bepaalde hogere-graads patronen) bestaan er vaste, exacte oplosmethodes
die SymPy toepast. Voor kwadratische vergelijkingen (ax²+bx+c=0) is
dat bijvoorbeeld de bekende ABC-formule:
  x = (-b ± √(b²-4ac)) / 2a

Waarom "soms lukt exact oplossen niet": niet elke vergelijking heeft
een nette, algebraïsche oplosformule. Voor de meeste vergelijkingen
van graad 5 en hoger bestaat er WISKUNDIG BEWEZEN geen algemene
formule meer (dit heet de Abel-Ruffini-stelling) — dat is geen
beperking van SymPy of van mij, maar een fundamentele eigenschap van
de wiskunde zelf. In dat geval geeft solve_sym() een duidelijke
foutmelding, en verwijs ik je door naar nulpunt() voor een numerieke
BENADERING in plaats van een exact antwoord.

Doorgerekend voorbeeld: solve_sym(x^2 - 5x + 6 = 0)
- Dit is een kwadratische vergelijking: a=1, b=-5, c=6
- Via de ABC-formule: x = (5 ± √(25-24)) / 2 = (5 ± 1) / 2
- x = 3 of x = 2
- Controle via factor_sym(x^2 - 5x + 6): dit ontbindt tot (x-2)(x-3)
  — exact dezelfde twee oplossingen, nu zichtbaar als de twee factoren
  die 0 kunnen worden.

Let op een schrijfwijze-valkuil: de VOLGORDE van letter en cijfer
maakt hier echt uit. "4x" (cijfer eerst) lees ik als 4·x
(vermenigvuldiging) — dat is waarschijnlijk wat je meestal bedoelt.
Maar "x4" (letter eerst) lees ik als x⁴ (x tot de vierde macht), om
dezelfde reden waarom ik "m2" als m² lees (de eenheden-notatie
"letter+cijfer=macht" geldt namelijk overal, ook bij x/y). Bedoel je
dus "4 keer x", schrijf dan "4x" of "4*x" — nooit "x4". Bedoel je
expliciet een macht, kan "x^4" ook altijd, ongeacht de volgorde.
""".strip(),

    # -----------------------------------------------------------------
    # Projectielbeweging & val met luchtweerstand
    # (projectiel() en val_met_weerstand() in math.py)
    # -----------------------------------------------------------------
    "projectiel_valweerstand": """
🚀 Projectielbeweging & val met luchtweerstand

Beide functies gaan over een object dat door de lucht beweegt onder
invloed van de zwaartekracht, maar met een cruciaal verschil:
projectiel() negeert luchtweerstand volledig (een nette, exacte
formule), val_met_weerstand() houdt er wél rekening mee (en heeft
daarom een simulatie nodig, geen nette formule meer).

PROJECTIEL — worp onder een hoek, ZONDER luchtweerstand:
De dagelijkse-taal-vergelijking: schiet een bal onder een hoek weg.
Zonder wind of luchtweerstand blijft de bal een perfecte, symmetrische
boog volgen — precies zo'n boog als in een schoolboek-tekening.
De truc is de snelheid in TWEE onafhankelijke richtingen op te
splitsen: een horizontale component (vx) en een verticale component
(vy), via gewone driehoeksmeetkunde:
  vx = snelheid × cos(hoek)
  vy = snelheid × sin(hoek)
Deze twee bewegen volledig ONAFHANKELIJK van elkaar: horizontaal blijft
de snelheid constant (geen weerstand die afremt), verticaal remt enkel
de zwaartekracht af (net als een rechte worp omhoog). Daaruit volgen
drie dingen direct:
- vluchttijd = (2 × vy) / g — de tijd tot de bal weer op dezelfde
  hoogte terug is (symmetrisch: even lang omhoog als omlaag)
- max_hoogte = vy² / (2×g) — hoe hoog de bal komt op het hoogste punt
- bereik = vx × vluchttijd — hoe ver de bal horizontal komt, want
  horizontaal is snelheid × tijd gewoon afstand

VAL_MET_WEERSTAND — vrije val MET luchtweerstand:
Zodra luchtweerstand meespeelt, verandert alles: de weerstandskracht
hangt af van hoe SNEL je valt, maar hoe snel je valt hangt weer af van
hoeveel weerstand je al ondervond — de twee grootheden beïnvloeden
elkaar voortdurend. Daardoor bestaat er GEEN nette, kant-en-klare
formule meer (zoals hierboven bij projectiel() wel het geval was) —
dit moet stap voor stap gesimuleerd worden.
Het model: versnelling = g - (weerstandscoëfficiënt/massa) × snelheid²
— hoe sneller je valt, hoe groter die tweede term wordt, tot hij
uiteindelijk (bijna) even groot wordt als g, en de versnelling naar 0
gaat: de "eindsnelheid" (denk aan een parachutist die niet oneindig
blijft versnellen).
Ik simuleer dit in hele kleine stapjes (elke stap 0.01 seconde): op
elk moment bereken ik de huidige versnelling, gebruik die om de
snelheid een klein beetje bij te werken, en de snelheid om de hoogte
een klein beetje te verlagen — dat herhaal ik duizenden keren tot de
hoogte 0 bereikt. Zodra dat gebeurt, reken ik de exacte landingstijd
nauwkeuriger uit door lineair te interpoleren binnen dat laatste
stapje, in plaats van simpelweg de laatste hele stap te gebruiken.

Doorgerekend voorbeeld: projectiel(20, 45) — een bal met 20 m/s onder
45°
- vx = 20×cos(45°) ≈ 14.14 m/s, vy = 20×sin(45°) ≈ 14.14 m/s
- vluchttijd = (2×14.14)/9.81 ≈ 2.88 s
- max_hoogte = 14.14² / (2×9.81) ≈ 10.19 m
- bereik = 14.14 × 2.88 ≈ 40.77 m

Let op de grens: val_met_weerstand() is een SIMULATIE, geen exacte
formule — het antwoord is een zeer nauwkeurige benadering (duizenden
kleine stapjes), niet een wiskundig exact getal zoals bij projectiel().
""".strip(),

    # -----------------------------------------------------------------
    # Numerieke afgeleide & integraal (afgeleide() en integraal())
    # -----------------------------------------------------------------
    "afgeleide_integraal": """
📐 Numerieke afgeleide & integraal — hoe ik dit benader

Beide functies beantwoorden een klassieke calculus-vraag, maar dan
NUMERIEK: geen symbolische formule zoals bij differentiate()/
integrate_sym() (die letterlijk een nieuwe formule teruggeven), maar
een concreet GETAL op een specifiek punt of tussen twee specifieke
grenzen — berekend via een slimme benadering, zonder de onderliggende
formule ooit symbolisch te hoeven kennen.

AFGELEIDE — de helling in één punt, via centraal verschil:
De dagelijkse-taal-vergelijking: wil je weten hoe steil een berghelling
is op een bepaald punt, zonder de wiskundige vorm van de berg te
kennen? Zet dan twee meetpalen vlak naast elkaar, aan weerszijden van
dat punt, en meet het hoogteverschil gedeeld door de afstand ertussen
— dat geeft je een heel goede schatting van de helling ter plekke.
Precies dat doe ik: ik neem een MINUSCULE stap (h = 0.000001) naar
links en naar rechts van je punt x, en bereken:
  f'(x) ≈ (f(x+h) - f(x-h)) / (2h)
Waarom TWEE kanten (centraal verschil) in plaats van slechts één kant
("f(x+h) - f(x)")? Omdat het gemiddelde van de helling net links en
net rechts van x veel nauwkeuriger blijkt te zijn dan de helling naar
slechts één kant — de fouten aan weerszijden heffen elkaar grotendeels
op.

INTEGRAAL — de oppervlakte tussen twee punten, via Simpson's regel:
De dagelijkse-taal-vergelijking: wil je de oppervlakte onder een
kromme grafiek weten, zonder een wiskundige formule voor die
oppervlakte te hebben? Verdeel het gebied in een heel groot aantal
smalle stroken, en tel de oppervlakte van elke strook bij elkaar op —
hoe smaller de stroken, hoe nauwkeuriger.
Een simpele aanpak zou rechthoekige stroken gebruiken, maar ik gebruik
iets slimmers: Simpson's regel, die elke strook benadert met een
lichtgebogen (parabolische) top in plaats van een platte rechte top —
dat past veel beter bij de meeste kromme grafieken, en levert daardoor
een veel nauwkeuriger antwoord op bij hetzelfde aantal stroken.
Simpson's regel weegt de tussenpunten NIET allemaal even zwaar: de
even-genummerde tussenpunten tellen dubbel (×2), de oneven-genummerde
tellen vier keer zo zwaar (×4), en enkel de twee uiterste randpunten
tellen enkelvoudig — dat specifieke wegingspatroon is precies wat een
parabolische (in plaats van rechte) top wiskundig oplevert:
  oppervlakte ≈ (h/3) × [f(a) + 4×f(x1) + 2×f(x2) + 4×f(x3) + ... + f(b)]
waarbij h de breedte van elke kleine strook is.

Doorgerekend voorbeeld: afgeleide(x^2, 3) — de helling van x² bij x=3
- f(3+h) ≈ (3.000001)² ≈ 9.000006, f(3-h) ≈ (2.999999)² ≈ 8.999994
- f'(3) ≈ (9.000006 - 8.999994) / 0.000002 = 6.0 — exact de bekende
  afgeleide van x² (namelijk 2x, bij x=3 dus 6), al is dit hier een
  benadering, geen symbolisch exacte berekening.

Doorgerekend mini-voorbeeld: integraal(x^2, 0, 3) met slechts 2 stappen
(math.py gebruikt standaard 1000 stappen voor veel meer nauwkeurigheid
dan dit vereenvoudigde voorbeeld)
- h = (3-0)/2 = 1.5, tussenpunt x1 = 1.5
- oppervlakte ≈ (1.5/3) × [f(0) + 4×f(1.5) + f(3)]
             = 0.5 × [0 + 4×2.25 + 9] = 0.5 × 18 = 9.0
- Dit klopt al exact met de werkelijke oppervlakte onder x² tussen 0
  en 3 (namelijk x³/3, dus 27/3 = 9) — Simpson's regel is voor een
  gladde curve als x² zelfs met weinig stappen al erg nauwkeurig.
""".strip(),

    # -----------------------------------------------------------------
    # Kwadratische vergelijking oplossen (wortel()/solveQuadratic() in math.py)
    # -----------------------------------------------------------------
    "wortel": """
➗ Wortel (kwadratische vergelijking) — de ABC-formule

Stel je vraagt me wortel(1, -5, 6). Dit is de Nederlandse naam voor
solveQuadratic() — ik los dan de vergelijking a·x² + b·x + c = 0 op,
hier dus x² - 5x + 6 = 0, en zoek ALLE waarden van x waarvoor dat
klopt.

De dagelijkse-taal-vergelijking: een kwadratische vergelijking
tekent, als je hem als grafiek zou uitzetten, een dalparabool of
bergparabool. Ik zoek de punten waar die kromme de x-as SNIJDT —
meestal twee punten, soms één (de kromme raakt de as maar net), en
soms geen enkel reëel punt (de hele kromme blijft boven of onder de
as).

De formule (de bekende "ABC-formule") komt rechtstreeks uit het
"kwadraat afmaken"-idee (elke ax²+bx+c herschrijven tot een volledig
kwadraat plus een rest), en levert:
  x = (-b ± √(b²-4ac)) / (2a)
Dat ± teken is de kern: er zijn typisch TWEE oplossingen, één met +
en één met -.

Het stuk ONDER de wortel (b²-4ac) heet de DISCRIMINANT, en die bepaalt
meteen hoeveel (en wat voor soort) oplossingen er zijn — ik hoef de
rest van de formule niet eens uit te rekenen om dat al te weten:
- Discriminant > 0 → twee verschillende, reële oplossingen (de
  kromme snijdt de x-as op twee plekken)
- Discriminant = 0 → precies één oplossing (de kromme raakt de x-as
  op exact één punt, het toppunt van de parabool ligt daar)
- Discriminant < 0 → geen reële oplossingen, maar wel twee COMPLEXE
  oplossingen (de kromme komt de x-as nooit aan) — sinds Fase 5 van
  math.py toon ik die complexe oplossingen ook gewoon, in plaats van
  enkel een foutmelding te geven.

Bijzonder geval: is a = 0, dan is het eigenlijk geen kwadratische
maar een LINEAIRE vergelijking (bx+c=0) — de ABC-formule zou dan door
0 delen, dus reken ik in dat geval gewoon de simpele oplossing uit:
x = -c/b.

Doorgerekend voorbeeld: wortel(1, -5, 6), dus x² - 5x + 6 = 0
- discriminant = (-5)² - 4×1×6 = 25 - 24 = 1
- discriminant > 0, dus twee reële oplossingen
- x = (5 ± √1) / 2 = (5 ± 1) / 2
- x₁ = (5+1)/2 = 3, x₂ = (5-1)/2 = 2
- Resultaat: [2, 3] — controle: 2×3=6 (=c/a) en 2+3=5 (=-b/a), klopt.

Doorgerekend voorbeeld met complexe oplossing: wortel(1, 0, 1), dus
x² + 1 = 0
- discriminant = 0² - 4×1×1 = -4 (negatief!)
- x = (0 ± √(-4)) / 2 = (0 ± 2i) / 2 = ±i
- Resultaat: [-i, i] — er is geen enkel reëel getal waarvan het
  kwadraat -1 is, vandaar de imaginaire eenheid i.
""".strip(),

    # -----------------------------------------------------------------
    # Determinant & inverse matrix (det() en inverse() in math.py)
    # -----------------------------------------------------------------
    "det_inverse": """
🔲 Determinant & inverse matrix — hoe ik dit bereken

Beide functies werken op een vierkante matrix (evenveel rijen als
kolommen), en zijn nauw verbonden: ik kan namelijk pas een inverse
matrix berekenen als ik eerst de determinant ken.

DETERMINANT — één enkel getal dat veel over een matrix zegt:
De dagelijkse-taal-vergelijking: stel je een matrix voor als een
manier om een vlak (of hogere-dimensionale ruimte) te vervormen — te
schalen, roteren, of scheeftrekken. De determinant vertelt je met
welke FACTOR de oppervlakte (of, in 3D, het volume) verandert door die
vervorming. Is de determinant bijvoorbeeld 2, dan verdubbelt elk
gebied door deze matrix. Is de determinant 0, dan wordt alles
PLATGEDRUKT tot een lijn of punt — er gaat dimensie-informatie
onherstelbaar verloren, en dat is precies waarom een matrix met
determinant 0 geen inverse kan hebben (zie hieronder).
Hoe ik het bereken hangt af van de grootte:
- 1×1 matrix: gewoon het enige getal zelf.
- 2×2 matrix: een simpele, directe formule — voor [[a,b],[c,d]] is
  de determinant a×d - b×c.
- Grotere matrices (n×n): ik gebruik Laplace-expansie — ik "ontvouw"
  de matrix langs de eerste rij, en voor elk element in die rij
  bereken ik de determinant van de kleinere SUBMATRIX die overblijft
  als je die rij en kolom weghaalt (recursief, tot ik bij 2×2 of 1×1
  matrices uitkom), met afwisselend + en - teken per kolom.

INVERSE — de matrix die de vervorming ONGEDAAN maakt:
De dagelijkse-taal-vergelijking: als een matrix een vervorming
beschrijft (schalen, roteren, ...), dan is de inverse matrix precies
de vervorming die dat weer terugdraait — vermenigvuldig een matrix
met zijn inverse, en je krijgt de eenheidsmatrix (het "doe niets"-
resultaat) terug, net zoals een getal maal zijn omgekeerde altijd 1
geeft (bv. 4 × 0.25 = 1).
Hoe ik dat bereken (de cofactor/adjoint-methode):
1. Bereken eerst de determinant. Is die 0, dan bestaat er GEEN inverse
   (de matrix "drukt alles plat", zoals hierboven uitgelegd — zo'n
   vervorming kan onmogelijk teruggedraaid worden, want de info is al
   verloren).
2. Bouw de COFACTOR-matrix: voor elk element bereken ik de determinant
   van de submatrix zonder die rij/kolom, met een afwisselend +/-
   teken (een "dambord"-patroon van tekens).
3. Transponeer die cofactor-matrix (rijen en kolommen omwisselen) —
   dat resultaat heet de adjoint.
4. Deel tenslotte elk element van de adjoint door de determinant.

Doorgerekend voorbeeld: det([[1,2],[3,4]]) en inverse([[1,2],[3,4]])
- determinant = 1×4 - 2×3 = 4 - 6 = -2
- Cofactor-matrix: voor elk element de "tegenoverliggende" waarde met
  wisselend teken → [[4,-3],[-2,1]]
- Adjoint (getransponeerd) → [[4,-2],[-3,1]]
- Inverse = adjoint / determinant = [[4/-2, -2/-2], [-3/-2, 1/-2]]
          = [[-2.0, 1.0], [1.5, -0.5]]
- Controle: [[1,2],[3,4]] × [[-2.0,1.0],[1.5,-0.5]] geeft inderdaad de
  eenheidsmatrix [[1,0],[0,1]] terug.

Let op de grens: is de determinant 0 (bv. bij [[1,2],[2,4]], waar de
tweede rij simpelweg 2× de eerste is), dan geeft inverse() een
foutmelding — zo'n matrix heet "singulier", en heeft principieel geen
inverse, hoe je ook rekent.
""".strip(),

    # -----------------------------------------------------------------
    # Kansrekening: dobbelstenen & kaarten
    # (kans_dobbelsteen() en kans_kaart() in math.py)
    # -----------------------------------------------------------------
    "kans_dobbelsteen_kaart": """
🎲 Kans op dobbelstenen & kaarten — twee verschillende technieken

Beide functies berekenen een kans bij een kansspel, maar gebruiken
BEWUST twee verschillende technieken — niet omdat de ene beter is dan
de andere, maar omdat ze allebei het beste passen bij hun eigen soort
probleem.

KANS_DOBBELSTEEN — via volledige enumeratie (brute-force, maar exact):
De dagelijkse-taal-vergelijking: met een klein aantal dobbelstenen kan
ik gewoon ALLE mogelijke worpen stuk voor stuk natellen — net zoals je
met 2 dobbelstenen makkelijk alle 36 combinaties (6×6) op een blaadje
kan uitschrijven en aankruisen welke som 7 geeft.
Dat is precies wat ik doe: ik loop RECURSIEF door elke mogelijke worp
van elke dobbelsteen (1 tot 6), tel bij elke volledige combinatie de
som op, en hou bij hoe vaak die som exact overeenkomt met wat je
zoekt. De kans is dan simpelweg:
  kans = (aantal gunstige worpen) / (totaal aantal mogelijke worpen)
waarbij het totaal aantal mogelijke worpen 6^aantal_dobbelstenen is
(elke dobbelsteen heeft 6 onafhankelijke uitkomsten).
Waarom dit enkel werkt voor een KLEIN aantal dobbelstenen: bij 8
dobbelstenen zijn er al 6⁸ ≈ 1.68 miljoen combinaties om te
doorlopen — nog net haalbaar, maar bij bv. 20 dobbelstenen zou dit
economisch onhaalbaar traag worden. Vandaar de harde grens van 8 in
math.py.

KANS_KAART — via de combinatie-formule (hypergeometrische verdeling):
Bij een kaartspel van 52 kaarten is volledige enumeratie volstrekt
onhaalbaar (véél te veel mogelijke combinaties van 5 kaarten uit 52).
In plaats daarvan gebruik ik een elegante WISKUNDIGE TRUC: in plaats
van rechtstreeks te berekenen "kans op MINSTENS 1 gewenste kaart" (wat
ingewikkeld is, want dat kan op veel manieren — 1 gewenste, 2
gewenste, 3, ...), bereken ik het TEGENOVERGESTELDE: de kans dat je
GEEN ENKELE gewenste kaart trekt (wat maar op één manier kan: alle
getrokken kaarten komen uit de ongewenste kaarten), en trek dat af
van 1:
  kans(minstens 1 gewenst) = 1 - kans(helemaal geen gewenste)
Die kans op "geen enkele gewenste" bereken ik met de bekende
combinatie-formule (zie ook de aparte combinaties()-functie in
math.py): hoeveel manieren zijn er om je trek-aantal kaarten te kiezen
UIT ENKEL de ongewenste kaarten, gedeeld door het totaal aantal
manieren om je trek-aantal kaarten te kiezen uit het HELE spel:
  kans(geen gewenste) = combinaties(ongewenst, trek_aantal) /
                        combinaties(totaal_kaarten, trek_aantal)

Doorgerekend voorbeeld: kans_dobbelsteen(2, 7) — kans op som=7 met 2
dobbelstenen
- Totaal mogelijkheden = 6² = 36
- Gunstige combinaties die som 7 geven: (1,6),(2,5),(3,4),(4,3),(5,2),
  (6,1) → 6 combinaties
- kans = 6/36 ≈ 0.1667 → zo'n 16.7% kans op som 7 (de meest
  waarschijnlijke som bij 2 dobbelstenen, want er zijn hier de meeste
  combinaties voor)

Doorgerekend voorbeeld: kans_kaart(4, 52, 5) — kans op minstens 1 aas
bij 5 kaarten trekken uit een spel van 52 (met 4 azen)
- ongewenst = 52 - 4 = 48 (niet-azen)
- kans(geen aas) = combinaties(48,5) / combinaties(52,5)
                 = 1.712.304 / 2.598.960 ≈ 0.6588
- kans(minstens 1 aas) = 1 - 0.6588 ≈ 0.3412 → zo'n 34.1% kans om
  minstens 1 aas te trekken bij 5 kaarten.
""".strip(),
}

# Alias-tabel: verschillende manieren waarop Kevin naar dezelfde
# functie kan verwijzen, wijzen allemaal naar dezelfde sleutel in
# UITLEG_TEKSTEN. Analoog aan math.py's eigen alias
# ("nulpunt": self._newton).
UITLEG_ALIASSEN = {
    "newton": "newton",
    "nulpunt": "newton",
    "newton-raphson": "newton",
    "newton raphson": "newton",

    "dv_rk4": "dv_rk4",
    "rk4": "dv_rk4",
    "runge-kutta": "dv_rk4",
    "runge kutta": "dv_rk4",
    "differentiaalvergelijking": "dv_rk4",

    "dijkstra": "dijkstra",
    "kortste pad": "dijkstra",
    "kortstepad": "dijkstra",

    "regressie": "regressie_correlatie",
    "correlatie": "regressie_correlatie",
    "lineaire regressie": "regressie_correlatie",
    "pearson": "regressie_correlatie",

    "binomiaal": "binomiaal_normaal",
    "normaal": "binomiaal_normaal",
    "binomiale verdeling": "binomiaal_normaal",
    "normale verdeling": "binomiaal_normaal",

    "levenshtein": "levenshtein",
    "levenshtein-afstand": "levenshtein",
    "edit distance": "levenshtein",

    "bfs": "bfs_dfs",
    "dfs": "bfs_dfs",
    "breadth-first search": "bfs_dfs",
    "depth-first search": "bfs_dfs",
    "breadth first search": "bfs_dfs",
    "depth first search": "bfs_dfs",

    "solve_sym": "solve_sym_factor_sym",
    "factor_sym": "solve_sym_factor_sym",
    "symbolisch oplossen": "solve_sym_factor_sym",
    "ontbinden in factoren": "solve_sym_factor_sym",

    "projectiel": "projectiel_valweerstand",
    "val_met_weerstand": "projectiel_valweerstand",
    "projectielbeweging": "projectiel_valweerstand",
    "val met weerstand": "projectiel_valweerstand",

    "afgeleide": "afgeleide_integraal",
    "integraal": "afgeleide_integraal",
    "numerieke afgeleide": "afgeleide_integraal",
    "numerieke integraal": "afgeleide_integraal",

    "wortel": "wortel",
    "solvequadratic": "wortel",
    "kwadratische vergelijking": "wortel",
    "abc-formule": "wortel",
    "abc formule": "wortel",

    "det": "det_inverse",
    "inverse": "det_inverse",
    "determinant": "det_inverse",
    "inverse matrix": "det_inverse",

    "kans_dobbelsteen": "kans_dobbelsteen_kaart",
    "kans_kaart": "kans_dobbelsteen_kaart",
    "kans dobbelsteen": "kans_dobbelsteen_kaart",
    "kans kaart": "kans_dobbelsteen_kaart",
}


def get_uitleg(naam: str):
    """
    Geeft de uitgebreide uitlegtekst voor een functienaam terug, of
    None als er (nog) geen uitleg voor bestaat. 'naam' wordt eerst
    genormaliseerd (kleine letters, spaties gestript) en dan door de
    aliassen-tabel gehaald, zodat "Newton-Raphson", "nulpunt" en
    "newton" allemaal bij dezelfde tekst uitkomen.
    """
    sleutel = UITLEG_ALIASSEN.get(naam.lower().strip())
    if sleutel is None:
        return None
    return UITLEG_TEKSTEN.get(sleutel)


def canonieke_naam(naam: str):
    """
    Vertaalt een (mogelijk alias-)naam naar zijn CANONIEKE sleutel uit
    UITLEG_TEKSTEN (bv. "nulpunt" en "Newton-Raphson" geven allebei
    "newton" terug), of None als de naam nergens matcht.

    Nodig voor Layer 2 (5 aug 2026, nova_state.md/nova_changelog.md):
    intent_router.py gebruikt dit om een dynamische topic-naam te
    bouwen (bv. "uitleg_newton") die NIET verschilt naargelang welke
    alias Kevin toevallig typte -- zonder dit zouden "leg uit nulpunt"
    en "wat is newton-raphson" als twee aparte, losse patronen gaan
    tellen in patterns_layer2.json, terwijl het inhoudelijk dezelfde
    vraag is.
    """
    return UITLEG_ALIASSEN.get(naam.lower().strip())


def beschikbare_functies():
    """
    Geeft de lijst van functienamen terug waar momenteel een
    uitgebreide uitleg voor bestaat (de "canonieke" namen, niet elke
    alias apart) — handig voor een nette foutmelding als Kevin om een
    functie vraagt die nog niet is uitgeschreven.
    """
    return sorted(UITLEG_TEKSTEN.keys())


# =======================================================================
# Contextuele oplos-suggestie (nova_state.md, "Volgende stappen" punt 24,
# 5 augustus 2026) -- als Kevin net "leg uit X" gebruikte en daarna een
# bewerking typt, checken of die bewerking QUA VORM bij functie X past,
# en zo ja voorstellen om hem meteen op te lossen.
#
# BEWUSTE SCOPE-BEPERKING (vastgelegd tijdens het ontwerpgesprek): dit
# werkt ALLEEN voor functies met een UNIEKE, ondubbelzinnige invoervorm
# -- niet voor alle 13 canonieke uitlegteksten. Van de 13 zijn er 7
# waarvoor de vorm alleen al genoeg zegt om ze te onderscheiden van elke
# andere math.py-functie:
#   - newton            : expressie met 1 variabele + los startgetal
#   - dv_rk4             : expressie + y0=/van=/tot=-syntax
#   - bfs_dfs            : {...}-graafstructuur + startknoop-string
#   - regressie_correlatie: twee losse [...]-lijsten
#   - levenshtein        : twee tekst-strings
#   - det_inverse        : matrix (geneste [[...],[...]]-lijst)
#   - afgeleide_integraal: expressie + 1 getal (afgeleide) of 2 getallen
#                          (integraal) -- onderling te onderscheiden via
#                          het AANTAL getallen na de expressie
#
# BEWUST NIET IN DEZE LIJST (gedeelde/ambigue vorm, zou vaker fout dan
# goed raden -- expliciet besproken en verworpen):
#   - dijkstra           : deelt exact dezelfde graaf-vorm als bfs_dfs
#     (dijkstra zelf blijft een normale, werkende functie/uitlegtekst,
#     enkel deze automatische-suggestie-feature dekt hem niet)
#   - solve_sym_factor_sym: een "="-teken alleen is GEEN betrouwbaar
#     signaal -- "x4=6*7" heeft ook een "=" maar is eerder een simpele
#     berekening dan een vergelijking-om-op-te-lossen (zie het
#     ontwerpgesprek, 5 aug 2026)
#   - wortel, binomiaal_normaal, kans_dobbelsteen_kaart,
#     projectiel_valweerstand: delen allemaal de vorm "2-3 losse
#     getallen" met elkaar EN met tientallen andere math.py-functies
#     (ggd, kgv, modulo, kracht, energie_kinetisch, ...) -- op vorm
#     alleen niet betrouwbaar te onderscheiden
# =======================================================================

import re as _re


def _functienaam_in(tekst: str, namen: set) -> bool:
    """Checkt of de tekst begint met één van de gegeven functienamen
    gevolgd door een "(" (met optionele spatie ertussen), ongeacht
    hoofd-/kleine letters. Dit is de meest betrouwbare vorm-check die
    er is: als Kevin de functienaam zelf al typt, hoeft er niets
    geraden te worden op basis van losse structuurkenmerken."""
    t = tekst.strip().lower()
    for naam in namen:
        if _re.match(rf'{_re.escape(naam)}\s*\(', t):
            return True
    return False


def _is_newton_vorm(tekst: str) -> bool:
    """newton(expressie, startwaarde) / nulpunt(expressie, startwaarde).
    Betrouwbaarst via de functienaam zelf; als fallback (kale expressie
    zonder functienaam) een STRIKTE check: moet de letter x bevatten
    (de enige variabele die newton/nulpunt ondersteunt) gevolgd door een
    los getal, en GEEN y0=/van=/tot=-syntax (dat is dv_rk4's vorm)."""
    if _functienaam_in(tekst, {"newton", "nulpunt"}):
        return True
    if "y0" in tekst or "van=" in tekst or "tot=" in tekst:
        return False
    # Strikt: minstens één "x" als op-zichzelf-staande variabele
    # (woordgrens, geen deel van een functienaam als "kracht" of
    # "kgv" -- vandaar \bx\b, niet zomaar "x" als losse letter overal)
    return bool(_re.search(r'\bx\b', tekst)) and bool(
        _re.search(r',\s*-?\d+(\.\d+)?\s*\)?\s*$', tekst.strip())
    )


def _is_dv_vorm(tekst: str) -> bool:
    """dv_rk4(...)/dv_euler(...)/dv(...). Betrouwbaarst via de
    functienaam zelf; als fallback de karakteristieke y0=/van=/tot=
    -syntax, of x EN y allebei als op-zichzelf-staande variabelen."""
    if _functienaam_in(tekst, {"dv_rk4", "dv_euler", "dv"}):
        return True
    if "y0" in tekst or "van=" in tekst or "tot=" in tekst:
        return True
    return bool(_re.search(r'\bx\b', tekst)) and bool(_re.search(r'\by\b', tekst))


def _is_graaf_vorm(tekst: str) -> bool:
    """bfs(...)/dfs(...) (dijkstra bewust uitgesloten, zie module-
    docstring). Betrouwbaarst via de functienaam zelf; als fallback een
    {...}-graafstructuur gevolgd door een aparte, aangehaalde
    startknoop-string -- MAAR expliciet niet als de tekst met
    "dijkstra(" begint, want die deelt exact dezelfde structuurvorm en
    zou anders per ongeluk als bfs/dfs herkend worden."""
    if _functienaam_in(tekst, {"bfs", "dfs"}):
        return True
    if _functienaam_in(tekst, {"dijkstra"}):
        return False
    return bool(_re.search(r'\{.*\}\s*,\s*["\'][^"\']+["\']', tekst, _re.DOTALL))


def _is_twee_lijsten_vorm(tekst: str) -> bool:
    """regressie(...)/correlatie(...). Betrouwbaarst via de
    functienaam zelf; als fallback twee losse, NIET-geneste
    [...]-lijsten na elkaar (sluit matrices bewust uit)."""
    if _functienaam_in(tekst, {"regressie", "correlatie"}):
        return True
    if _re.search(r'\[\s*\[', tekst):
        return False  # geneste lijst = matrix, niet twee data-reeksen
    matches = _re.findall(r'\[[^\[\]]*\]', tekst)
    return len(matches) == 2


def _is_twee_strings_vorm(tekst: str) -> bool:
    """levenshtein(...). Betrouwbaarst via de functienaam zelf; als
    fallback twee losse, aangehaalde tekst-strings, zonder een
    {...}-graafstructuur erbij (anders zou dit een graaf-startknoop
    kunnen zijn, geen levenshtein-woordpaar)."""
    if _functienaam_in(tekst, {"levenshtein"}):
        return True
    if "{" in tekst:
        return False
    matches = _re.findall(r'["\'][^"\']*["\']', tekst)
    return len(matches) == 2


def _is_matrix_vorm(tekst: str) -> bool:
    """det(...)/inverse(...). Betrouwbaarst via de functienaam zelf;
    als fallback een geneste lijst-van-lijsten ([[...],[...]])."""
    if _functienaam_in(tekst, {"det", "inverse"}):
        return True
    return bool(_re.search(r'\[\s*\[', tekst))


def _is_afgeleide_integraal_vorm(tekst: str):
    """afgeleide(...)/integraal(...). ENKEL via de functienaam zelf
    betrouwbaar te herkennen -- een kale expressie+getal(len) zonder
    functienaam deelt exact dezelfde vorm met newton (expressie + 1
    getal) en met tientallen andere functies (2 getallen), en is dus
    NIET via structuur alleen te onderscheiden. Geeft "afgeleide",
    "integraal" of None terug (niet enkel True/False, want dit
    onderscheidt twee functies binnen dezelfde canonieke tekst)."""
    if _functienaam_in(tekst, {"afgeleide"}):
        return "afgeleide"
    if _functienaam_in(tekst, {"integraal"}):
        return "integraal"
    return None


# Volgorde: de functienaam-check zelf (binnen elke detector) is altijd
# betrouwbaar en botst nergens mee -- verschillende functienamen kunnen
# nooit tegelijk matchen. Enkel de STRUCTUUR-fallback (voor kale
# expressies zonder herkenbare functienaam) kan in theorie overlappen
# tussen newton en dv_rk4 (beide "expressie + getal(len)"), vandaar
# newton pas NA dv_rk4 in deze lijst: een dv_rk4-fallback-match (x EN y
# samen) is specifieker dan newton's fallback (enkel x), dus die moet
# eerst de kans krijgen.
_VORM_DETECTOREN = [
    ("bfs_dfs", _is_graaf_vorm),
    ("levenshtein", _is_twee_strings_vorm),
    ("det_inverse", _is_matrix_vorm),
    ("regressie_correlatie", _is_twee_lijsten_vorm),
    ("dv_rk4", _is_dv_vorm),
    ("newton", _is_newton_vorm),
]


def herken_vorm(tekst: str):
    """
    Kijkt naar de VORM (niet de betekenis) van een stuk ingegeven
    tekst, en geeft de canonieke functienaam terug waar die vorm het
    best bij past, of None als er geen enkele match is.

    Dit is GEEN vrije-taal-begrip en GEEN garantie -- puur syntactische
    pattern-matching op functienamen/komma's/haakjes/aanhalingstekens,
    exact zoals de rest van Nova werkt (zie module-docstring hierboven
    voor de volledige scope-afbakening: slechts 7 van de 13 canonieke
    functies hebben een vorm die uniek genoeg is om hier betrouwbaar op
    te gokken). Het betrouwbaarst is als Kevin de functienaam zelf al
    typt (bv. "afgeleide(x^2, 3)") -- de structuur-only fallback (voor
    een kale expressie zonder functienaam) werkt enkel voor newton en
    dv_rk4, de overige 5 vereisen de functienaam zelf.
    """
    tekst = tekst.strip()
    if not tekst:
        return None

    afg_int = _is_afgeleide_integraal_vorm(tekst)
    if afg_int is not None:
        return "afgeleide_integraal"

    for canonieke_naam_kandidaat, detector in _VORM_DETECTOREN:
        if detector(tekst):
            return canonieke_naam_kandidaat

    return None


def check_vorm_tegen_verwachting(tekst: str, verwachte_naam: str):
    """
    Kijkt of 'tekst' qua vorm bij 'verwachte_naam' past (de functie
    waarover Kevin net een uitleg kreeg), of beter bij een ANDERE
    canonieke functie past, of bij geen enkele.

    Geeft een van drie resultaten terug:
    - ("match", verwachte_naam)     : de vorm past bij wat verwacht werd
    - ("mismatch", andere_naam)     : de vorm past beter bij een andere
                                       functie dan verwacht
    - (None, None)                  : geen enkele match, geen suggestie
    """
    gevonden = herken_vorm(tekst)
    if gevonden is None:
        return (None, None)
    if gevonden == verwachte_naam:
        return ("match", gevonden)
    return ("mismatch", gevonden)


# Vriendelijke weergavenaam per canonieke sleutel, voor gebruik in
# gesproken suggesties ("wil je dat ik dit oplos met...") -- de rauwe
# interne sleutel (bv. "bfs_dfs", "regressie_correlatie") is prima als
# dict-key maar niet als iets wat Nova hardop "zegt".
WEERGAVENAAM = {
    "newton": "newton/nulpunt",
    "dv_rk4": "dv_rk4",
    "dijkstra": "dijkstra",
    "regressie_correlatie": "regressie/correlatie",
    "binomiaal_normaal": "binomiaal/normaal",
    "levenshtein": "levenshtein",
    "bfs_dfs": "bfs/dfs",
    "solve_sym_factor_sym": "solve_sym/factor_sym",
    "projectiel_valweerstand": "projectiel/val_met_weerstand",
    "afgeleide_integraal": "afgeleide/integraal",
    "wortel": "wortel",
    "det_inverse": "det/inverse",
    "kans_dobbelsteen_kaart": "kans_dobbelsteen/kans_kaart",
}


def weergavenaam(canonieke_naam_: str) -> str:
    """Geeft de vriendelijke weergavenaam terug voor gebruik in
    gesproken suggesties, of de canonieke naam zelf als fallback
    (bv. voor een toekomstige canonieke naam die nog niet in de
    tabel hierboven is opgenomen)."""
    return WEERGAVENAAM.get(canonieke_naam_, canonieke_naam_)


class MathUitlegModule:
    """
    Dunne wrapper zodat deze module via module_loader.py's normale,
    dynamische scan (pkgutil.walk_packages over modules/) gevonden en
    geregistreerd wordt — net als elke andere module in Nova, i.p.v.
    een losse, rechtstreekse cross-module import vanuit
    intent_router.py.

    Bewust GEEN EventBus-subscripties hier: deze module bevat enkel
    vaste, statische tekst (geen eigen gedrag/state), dus er is niets
    om op te reageren. intent_router.py's detect_uitleg() haalt de
    module op via event_bus.modules.get("math_uitleg") en roept de
    functies hieronder rechtstreeks aan — zelfde ophaal-patroon als
    bv. wikipedia_teacher/concept_overview, enkel zonder events terug.
    """

    def __init__(self, event_bus):
        self.event_bus = event_bus

    def get_uitleg(self, naam: str):
        return get_uitleg(naam)

    def canonieke_naam(self, naam: str):
        return canonieke_naam(naam)

    def beschikbare_functies(self):
        return beschikbare_functies()

    def herken_vorm(self, tekst: str):
        return herken_vorm(tekst)

    def check_vorm_tegen_verwachting(self, tekst: str, verwachte_naam: str):
        return check_vorm_tegen_verwachting(tekst, verwachte_naam)

    def weergavenaam(self, canonieke_naam_: str) -> str:
        return weergavenaam(canonieke_naam_)


def init_module(event_bus, sem=None):
    """
    Volgt de standaard init_module(event_bus, sem=None)-conventie
    (zelfde signatuur als bv. session_watcher.py) zodat module_loader
    hem automatisch oppikt: geen "sem" nodig, maar de parameter moet
    er staan omdat de loader bij de dynamische scan altijd eerst
    init_module(event_bus, sem) probeert (zie module_loader.py, stap
    3) en pas bij een TypeError terugvalt op init_module(event_bus).
    """
    mod = MathUitlegModule(event_bus)
    event_bus.publish("module_loaded", {"name": "math_uitleg"})
    return mod