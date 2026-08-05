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