# core/language_normalizer.py
"""
Taalnormalisatie voor kennisvragen (punt 62a, 4 november 2026).

PROBLEEM
    De detectors in intent_router.py kijken naar het BEGIN van een zin:
    "wat is een hond", "is een X een Y", "wat veroorzaakt X". Zodra er iets
    omheen staat ("kun je me vertellen wat een hond is", "klopt het dat een
    kat een zoogdier is", "waardoor ontstaat modder"), herkent Nova de zin
    niet meer en valt ze terug op 'fallback'.

OPLOSSING (100% symbolisch, geen ML)
    normaliseer(tekst) herschrijft zulke omhulsels naar de vorm die Nova al
    kent. Het is een lijst vaste regels (frames). Past de HELE zin in precies
    een regel, dan komt de herschreven zin terug. Past hij nergens, dan komt
    de ORIGINELE tekst ongewijzigd terug. Er wordt nooit half herschreven.

    Wat het NIET doet: vrije taal begrijpen. Een formulering die in geen
    enkele regel past, blijft onbegrepen. De taalbenchmark (--taal en --blind)
    meet hoe groot dat restgat is.

BEREIK EN GRENZEN (stand 4 november 2026, ronde 2)
    Wel: kennisvragen over een woord of een paar woorden (definitie, relatie,
    oorzaak, gevolg, synoniem, antoniem), ook met aanhalingstekens eromheen.
    Bijzinvragen ("waardoor wordt iemand moe", "wat gebeurt er als ijs smelt")
    sinds punt 71 wel als VORM: de gebeurtenis wordt doorgegeven aan "wat zijn de
    gevolgen van X" / "wat veroorzaakt X". De graaf heeft geen concept voor zo'n
    gebeurtenis, dus het antwoord is bijna altijd een eerlijk "Ik ken geen ...".
    Echt begrijpen vraagt zinsontleding en valt buiten vaste regels.
    Ook buiten bereik: meervoud naar enkelvoud ("hoort een hond bij de
    dieren").

VEILIGHEID
    - Alleen vraagvormen. Een stelling ("een hond is een dier") blijft staan.
    - Het onderwerp (X) en het doel (Y) zijn 1 tot 3 woorden, enkel letters,
      zonder persoonlijke voornaamwoorden ("je", "ik", "nova"), vraagwoorden,
      stopwoorden of cijfers. Zo wordt "kun je me vertellen wie jij bent" nooit
      "wat is jij" en blijft rekenwerk ("wat is 5 maal 3") ongemoeid.
    - Idempotent: een al genormaliseerde zin verandert niet meer.
    - Geeft de herschrijving dezelfde zin als de opgeschoonde invoer, dan is
      het geen herschrijving (regel = None).

GEBRUIK
    from core.language_normalizer import normaliseer
    nieuw, regel = normaliseer("weet jij wat een zebra is")
    # nieuw == "wat is een zebra", regel == "definitie_bijzin"
"""

import re

try:
    from core.nl_stopwoorden import STOPWOORDEN as _STOPWOORDEN
except Exception:  # pragma: no cover - defensief, zoals in intent_router.py
    _STOPWOORDEN = frozenset()

# ---------------------------------------------------------------- bouwstenen
_W = r"[a-zà-ÿ][a-zà-ÿ\-]*"
_LID = r"(?:een|de|het)"
# 1 tot 3 woorden (niet-hebzuchtig, zodat "X is een Y" netjes splitst)
_X = rf"{_W}(?: {_W}){{0,2}}?"
_Y = rf"{_W}(?: {_W}){{0,2}}"

# Woorden die nooit (los) onderwerp of doel mogen zijn.
_VERBODEN = frozenset({
    "je", "jij", "jou", "jouw", "u", "ik", "mij", "me", "mijn", "nova",
    "wij", "we", "jullie", "dit", "dat", "deze", "die", "er", "ervan",
    "hier", "daar", "hij", "zij", "ze", "het",
    "wat", "wie", "waar", "wanneer", "waarom", "waardoor", "hoe", "welk", "welke",
    "is", "zijn", "een", "de", "ook", "niet", "geen",
})

# Vulwoorden die zonder betekenisverlies wegvallen.
_VULWOORDEN = re.compile(
    r"\b(?:volgens jou|eigenlijk|nou|toch|precies|trouwens|even|eens|dan|hè)\b"
)
# Aanhalingstekens rond een woord ("regen", «regen», 'regen') vallen weg.
# Een apostrof IN een woord (auto's, zo'n) blijft staan.
_CITAAT = re.compile(r"[\"“”„«»]|(?<!\w)['‘’]|['‘’](?!\w)")
# "een soort fruit", "een vorm van neerslag" -> "een fruit", "een neerslag".
# Bewust NIET "onderdeel van": dat is part_of en geen is_a.
_SOORT = re.compile(r"\b(een|de|het) (?:soort|type|vorm|variant|sort)(?: van)? (?=\w)")
_RELATIE_START = re.compile(
    r"^(?:is|klopt het dat|is het waar dat|is het zo dat|is het juist dat|is het correct dat|"
    r"of|waarom is|hoe komt het dat|hoe kan het dat) ")
_AANHEF = re.compile(r"^(?:(?:hé|hey|hoi|oké|ok|nova)\s+)+")
_STAART = re.compile(r"\s+(?:denk ik|of niet|alsjeblieft|alstublieft|aub|graag|nova)$")

# Inleidingen die voor een kennisvraag mogen staan. Elk patroon wordt aan het
# begin weggehaald. Wat overblijft moet daarna nog in een regel passen.
_INLEIDINGEN = [
    re.compile(r"^(?:kun|kan|zou|wil|wilt)\s+(?:je|jij|u)\s+(?:me\s+|mij\s+)?"
               r"(?:alsjeblieft\s+|alstublieft\s+)?"
               r"(?:vertellen|uitleggen|zeggen|laten\s+weten|uitleg\s+geven(?:\s+over)?)\s+"),
    re.compile(r"^(?:vertel|zeg|leg)\s+(?:me\s+|mij\s+)?(?:uit\s+)?"),
    re.compile(r"^weet\s+(?:je|jij|u)\s+(?=(?:wat|of|waarom|hoe|welk)\b)"),
    re.compile(r"^ik\s+(?:wil|zou)\s+(?:graag\s+)?(?:weten|vragen)\s+"),
    re.compile(r"^ik\s+vraag\s+me\s+af\s+"),
    re.compile(r"^mag\s+ik\s+vragen\s+"),
]


def _schoon(tekst):
    """Kleine letters, geen leestekens aan het eind, komma's weg, spaties samen."""
    t = tekst.lower().strip().replace("’", "'")
    t = re.sub(r"[?!.]+$", "", t).strip()
    t = t.replace(",", " ")
    return re.sub(r"\s+", " ", t).strip()


def _zonder_citaat(t):
    """Haalt aanhalingstekens rond woorden weg en maakt van meerdere spaties een."""
    return re.sub(r"\s+", " ", _CITAAT.sub("", t)).strip()


def _woord_ok(woorden):
    """True als elk woord in de term toegelaten is (zie veiligheid hierboven)."""
    delen = woorden.split()
    if not 1 <= len(delen) <= 3:
        return False
    for w in delen:
        if w in _VERBODEN:
            return False
    # Een enkel stopwoord ("dan", "nu", ...) is nooit een onderwerp.
    if len(delen) == 1 and delen[0] in _STOPWOORDEN:
        return False
    return True


def _term(art, woorden):
    """Zet lidwoord + woord(en) weer in elkaar: 'een zebra' of 'zebra'."""
    return f"{art} {woorden}" if art else woorden


# ---------------------------------------------------------------- de regels
# Elke regel: (naam, patroon, bouwer). De bouwer krijgt de match en geeft de
# nieuwe zin, of None als een controle (bv. _woord_ok) mislukt.

def _b_definitie(m):
    if not _woord_ok(m.group("x")):
        return None
    return "wat is " + _term(m.group("art"), m.group("x"))


def _b_relatie(m):
    if not (_woord_ok(m.group("x")) and _woord_ok(m.group("y"))):
        return None
    return f"is {_term(m.group('artx'), m.group('x'))} {m.group('arty')} {m.group('y')}"


def _b_oorzaak(m):
    if not _woord_ok(m.group("x")):
        return None
    return "wat veroorzaakt " + m.group("x")


def _b_gevolg(m):
    if not _woord_ok(m.group("x")):
        return None
    return "wat zijn de gevolgen van " + m.group("x")


def _b_synoniem(m):
    if not _woord_ok(m.group("x")):
        return None
    return "wat is een synoniem van " + m.group("x")


def _b_antoniem(m):
    if not _woord_ok(m.group("x")):
        return None
    return "wat is het tegenovergestelde van " + m.group("x")

# ---------------------------------------------------------------- bijzinvragen (punt 71)
# "wat gebeurt er als je een ballon loslaat", "waardoor breekt een tak",
# "wat zorgt ervoor dat ijs smelt". De graaf heeft geen concept voor zo'n hele
# gebeurtenis ("een tak breekt"): dit is GEEN begrip van de gebeurtenis. De regel
# herkent alleen de vorm en geeft de gebeurtenis door aan de bestaande vragen
# "wat zijn de gevolgen van X" / "wat veroorzaakt X". Het antwoord is dus bijna
# altijd een eerlijk "Ik ken geen gevolgen van 'tak breekt'".
_GEB = rf"{_W}(?: {_W}){{1,6}}"

# Woorden waaruit blijkt dat de vraag over Nova zelf gaat: die laten we ongemoeid
# ("wat gebeurt er als ik je uitzet", "wat gebeurt er als je een update krijgt").
_ZELF = frozenset({
    "ik", "mij", "me", "mijn", "jij", "jou", "jouw", "jezelf", "mezelf", "u", "uw",
    "nova", "wij", "we", "ons", "onze", "jullie",
    "update", "herstart", "reboot", "opstart", "opstarten", "uitzet", "uitzetten",
    "afsluit", "afsluiten", "uitgezet", "uitschakelt", "uitschakelen", "crasht",
    "geheugen", "batterij", "stroom", "internet", "wifi", "server",
})
_ONBEPAALD_ONDERWERP = frozenset({"iemand", "niemand", "men", "iets", "alles"})
# Werkwoorden die de bestaande oorzaakregels ("waardoor ontstaat X") al dekken.
_OORZAAK_WERKWOORD = frozenset({"ontstaat", "ontstaan", "komt", "komen"})


def _gebeurtenis_ok(woorden):
    """
    De gebeurtenis (2 tot 7 woorden) mag niet over Nova zelf gaan. Een beginnend
    'je' is 'men' ("je een ballon loslaat") en valt weg; dan moeten er nog minstens
    drie woorden volgen (anders is 'je stopt' of 'je gaat dood' waarschijnlijk een
    vraag aan Nova). Geeft de gebeurtenis zonder 'je'/'men', of None.
    """
    w = woorden.split()
    if w and w[0] in ("je", "men"):
        w = w[1:]
        if len(w) < 3:
            return None
    if not 2 <= len(w) <= 7:
        return None
    # "wat gebeurt er als dat gebeurt": een kale verwijzing is geen gebeurtenis.
    if w[0] in ("dat", "dit", "die", "deze", "er", "hier", "daar"):
        return None
    for x in w:
        if x in _ZELF or x in ("je", "wat", "wie", "waar", "waarom", "waardoor", "hoe", "welk", "welke"):
            return None
    return " ".join(w)


def _b_gevolg_zin(m):
    e = _gebeurtenis_ok(m.group("e"))
    return None if e is None else "wat zijn de gevolgen van " + e


def _b_oorzaak_zin(m):
    e = _gebeurtenis_ok(m.group("e"))
    return None if e is None else "wat veroorzaakt " + e


def _b_oorzaak_maakt(m):
    # "wat maakt dat huis zo bijzonder" is geen oorzaakvraag: 'dat' kan ook een
    # aanwijzend woord zijn. Daarom hier enkel een gebeurtenis die met een lidwoord
    # of 'je' begint ("wat maakt dat een kaars brandt").
    if m.group("e").split()[0] not in ("een", "de", "het", "je", "men", "iemand"):
        return None
    return _b_oorzaak_zin(m)


def _b_oorzaak_waardoor_zin(m):
    """'waardoor breekt een tak' -> 'wat veroorzaakt een tak breekt' (werkwoord achteraan)."""
    w = m.group("e").split()
    if len(w) < 2 or w[0] in _OORZAAK_WERKWOORD:
        return None
    v = w[0]
    if w[1] in ("een", "de", "het"):
        if len(w) < 3:
            return None
        onderwerp, rest = w[1:3], w[3:]
        kern = w[2]
    else:
        onderwerp, rest = w[1:2], w[2:]
        kern = w[1]
    if kern in _VERBODEN or kern in _STOPWOORDEN or kern.isdigit():
        if kern not in _ONBEPAALD_ONDERWERP:
            return None
    e = _gebeurtenis_ok(" ".join(onderwerp + [v] + rest))
    return None if e is None else "wat veroorzaakt " + e


_ART = rf"(?:(?P<art>{_LID}) )?"
_ARTX = rf"(?:(?P<artx>{_LID}) )?"

# Bijzin met het werkwoord ACHTERAAN: "(art) X (art) Y is", zoals in
# "klopt het dat een kat een zoogdier is".
_REL_BIJZIN = rf"{_ARTX}(?P<x>{_X}) (?P<arty>{_LID}) (?P<y>{_Y}) is"

REGELS = [
    # A. Definitie
    ("definitie_bijzin",
     re.compile(rf"^wat {_ART}(?P<x>{_X}) is$"), _b_definitie),
    ("definitie_woord",
     re.compile(rf"^wat betekent (?:het woord|de term|het begrip) {_ART}(?P<x>{_X})$"), _b_definitie),
    ("definitie_inhoud",
     re.compile(rf"^wat houdt (?:het woord |de term |het begrip )?{_ART}(?P<x>{_X}) in$"), _b_definitie),
    ("definitie_beschrijven",
     re.compile(rf"^hoe (?:zou|kun|kan|kunt) (?:je|jij|u|men) {_ART}(?P<x>{_X}) "
                rf"(?:beschrijven|omschrijven|definiëren|definieren)$"), _b_definitie),
    ("definitie_hoe",
     re.compile(rf"^hoe (?:beschrijf|omschrijf|definieer|definiëer|beschrijft|omschrijft|definieert) "
                rf"(?:je|jij|u|men) {_ART}(?P<x>{_X})$"), _b_definitie),
    ("definitie_gebod",
     re.compile(rf"^(?:beschrijf|omschrijf|definieer|definiëer) {_ART}(?P<x>{_X})$"), _b_definitie),
    ("definitie_geef",
     re.compile(rf"^geef (?:me |mij )?(?:een )?(?:definitie|omschrijving|beschrijving|uitleg) van "
                rf"{_ART}(?P<x>{_X})$"), _b_definitie),
    ("definitie_wat_voor",
     re.compile(rf"^wat voor (?:iets|ding|een ding|soort ding|soort iets) is {_ART}(?P<x>{_X})$"),
     _b_definitie),

    # B. Relatievragen ("is een X een Y" in andere vormen)
    ("relatie_waarom",
     re.compile(rf"^waarom is {_ARTX}(?P<x>{_X}) (?P<arty>{_LID}) (?P<y>{_Y})$"), _b_relatie),
    ("relatie_waarom_bijzin",
     re.compile(rf"^hoe (?:komt|kan) het dat {_REL_BIJZIN}$"), _b_relatie),
    ("relatie_klopt",
     re.compile(rf"^(?:klopt het dat|is het waar dat|is het zo dat|is het juist dat|is het correct dat) "
                rf"{_REL_BIJZIN}$"), _b_relatie),
    ("relatie_of",
     re.compile(rf"^of {_REL_BIJZIN}$"), _b_relatie),
    ("relatie_is_dat",
     re.compile(rf"^{_ARTX}(?P<x>{_X}) is dat (?:ook )?(?P<arty>{_LID}) (?P<y>{_Y})$"), _b_relatie),
    ("relatie_ook",
     re.compile(rf"^is {_ARTX}(?P<x>{_X}) ook (?P<arty>{_LID}) (?P<y>{_Y})$"), _b_relatie),

    # C. Oorzaak en gevolg
    ("oorzaak_waardoor",
     re.compile(rf"^waardoor (?:ontstaat|ontstaan|komt|komen) {_ART}(?P<x>{_X})$"), _b_oorzaak),
    ("oorzaak_waarom",
     re.compile(rf"^waarom (?:ontstaat|ontstaan) {_ART}(?P<x>{_X})$"), _b_oorzaak),
    ("oorzaak_noemen",
     re.compile(rf"^wat (?:is|zijn) de (?:oorzaak|oorzaken) van {_ART}(?P<x>{_X})$"), _b_oorzaak),
    ("oorzaak_hoe",
     re.compile(rf"^hoe (?:ontstaat|ontstaan) {_ART}(?P<x>{_X})$"), _b_oorzaak),
    ("gevolg_effect",
     re.compile(rf"^wat (?:is|zijn) (?:het|de) (?:effect|effecten) van {_ART}(?P<x>{_X})$"), _b_gevolg),
    ("gevolg_resultaat",
     re.compile(rf"^wat (?:is|zijn) (?:het|de) (?:resultaat|resultaten) van {_ART}(?P<x>{_X})$"),
     _b_gevolg),
    ("gevolg_komt",
     re.compile(rf"^wat komt er (?:van|uit) {_ART}(?P<x>{_X})$"), _b_gevolg),
    ("gevolg_ontstaat",
     re.compile(rf"^wat (?:ontstaat|volgt|gebeurt) er (?:na|bij|op|uit) {_ART}(?P<x>{_X})$"), _b_gevolg),

    # D. Synoniem en antoniem
    ("synoniem_hetzelfde",
     re.compile(rf"^(?:welk woord|wat) betekent (?:ongeveer |bijna )?(?:hetzelfde als|zoveel als|ook) "
                rf"{_ART}(?P<x>{_X})$"), _b_synoniem),
    ("synoniem_betekenis",
     re.compile(rf"^(?:welk woord|wat) heeft (?:ongeveer |bijna )?(?:dezelfde|een gelijke|een vergelijkbare) "
                rf"betekenis als {_ART}(?P<x>{_X})$"), _b_synoniem),
    ("synoniem_is",
     re.compile(rf"^(?:welk woord|wat) is (?:ongeveer |bijna )?(?:hetzelfde als|synoniem (?:aan|met|van|voor)) "
                rf"{_ART}(?P<x>{_X})$"), _b_synoniem),
    ("synoniem_voor",
     re.compile(rf"^wat is (?:een |het )?synoniem voor {_ART}(?P<x>{_X})$"), _b_synoniem),
    ("synoniem_ander_woord",
     re.compile(rf"^wat is een ander woord voor {_ART}(?P<x>{_X})$"),
     lambda m: ("wat is een ander woord voor " + m.group("x")) if _woord_ok(m.group("x")) else None),
    # Ronde 3 (4 november 2026): andere manieren om naar een synoniem te vragen.
    ("synoniem_hoe_noem",
     re.compile(rf"^hoe (?:noem|zeg|schrijf) (?:je|jij|men|u) {_ART}(?P<x>{_X}) (?:anders|ook(?: wel)?)$"),
     _b_synoniem),
    ("synoniem_hoe_heet",
     re.compile(rf"^hoe heet {_ART}(?P<x>{_X}) (?:anders|ook(?: wel)?|nog meer)$"), _b_synoniem),
    ("synoniem_ook_noemen",
     re.compile(rf"^hoe (?:kun|kan|kunnen) (?:je|jij|men|u) {_ART}(?P<x>{_X}) (?:ook|nog) (?:noemen|zeggen)$"),
     _b_synoniem),
    ("synoniem_andere_naam",
     re.compile(rf"^wat is (?:een |de )?(?:andere naam|andere benaming|andere term|alternatief woord) "
                rf"voor {_ART}(?P<x>{_X})$"), _b_synoniem),
    # "wat is dat precies" -> "wat is dat": de vulwoorden zijn al weg, dit laat de kale
    # verwijzing herkennen in plaats van "dat precies" op te zoeken.
    ("definitie_kale_verwijzing",
     re.compile(r"^wat is (?:dat|dit|die|deze|het)$"), lambda m: m.group(0)),
    ("synoniem_meervoud",
     re.compile(rf"^wat zijn synoniemen van {_ART}(?P<x>{_X})$"),
     lambda m: ("wat zijn synoniemen van " + m.group("x")) if _woord_ok(m.group("x")) else None),
    ("antoniem_omgekeerd",
     re.compile(rf"^(?:welk woord betekent het|wat is het) (?:tegenovergestelde|omgekeerde) van "
                rf"{_ART}(?P<x>{_X})$"), _b_antoniem),

    # F. Bijzinvragen (punt 71, 4 november 2026): gebeurtenis als onderwerp.
    ("gevolg_als",
     re.compile(rf"^wat (?:gebeurt|ontstaat|volgt|zou er gebeuren|zou er ontstaan) ?(?:er )?"
                rf"(?:als|wanneer|zodra|nadat|indien) (?P<e>{_GEB})$"), _b_gevolg_zin),
    ("gevolg_komt_zin",
     re.compile(rf"^wat (?:komt|volgt) er (?:van|uit) (?P<e>{_GEB})$"), _b_gevolg_zin),
    ("oorzaak_zorgt",
     re.compile(rf"^wat (?:zorgt|zorgde) (?:ervoor|er voor) dat (?P<e>{_GEB})$"), _b_oorzaak_zin),
    ("oorzaak_maakt",
     re.compile(rf"^wat maakt dat (?P<e>{_GEB})$"), _b_oorzaak_maakt),
    ("oorzaak_waardoor_zin",
     re.compile(rf"^waardoor (?P<e>{_GEB})$"), _b_oorzaak_waardoor_zin),

    # E. De KALE vormen, bewust als LAATSTE: ze vangen alles wat met "wat is" of
    # "is" begint. Staan ze eerder, dan eten ze de specifieke regels hierboven op
    # ("wat is de oorzaak van modder" zou als gewone definitie gelezen worden).
    # Meestal veranderen ze niets (de zin is al in orde); ze halen enkel
    # vulwoorden en een aanhef weg.
    ("definitie_kaal",
     re.compile(rf"^wat is {_ART}(?P<x>{_X})$"), _b_definitie),
    ("relatie_kaal",
     re.compile(rf"^is {_ARTX}(?P<x>{_X}) (?P<arty>{_LID}) (?P<y>{_Y})$"), _b_relatie),
]


# Alleen gebruikt als er aanhalingstekens in de zin stonden: "wat betekent "regen""
# is dan duidelijk een woordvraag. Zonder aanhalingstekens laten we "wat betekent X"
# met rust (het werkt al).
REGELS_CITAAT = [
    ("definitie_citaat",
     re.compile(rf"^wat betekent {_ART}(?P<x>{_X})$"), _b_definitie),
]


def normaliseer(tekst):
    """
    Geeft (nieuwe_tekst, regelnaam).
    - Geen herschrijving nodig of mogelijk: (tekst, None), met de ORIGINELE tekst.
    - Wel herschreven: de genormaliseerde zin (kleine letters, zonder vraagteken)
      en de naam van de regel die paste.
    """
    if not isinstance(tekst, str) or not tekst.strip():
        return tekst, None

    opgeschoond = _schoon(tekst)
    zonder = _zonder_citaat(opgeschoond)
    had_citaat = zonder != opgeschoond

    # Aanhalingstekens, aanhef, vulwoorden en staart weghalen.
    k = re.sub(r"[?!.]+$", "", zonder).strip()
    k = _AANHEF.sub("", k)
    k = _VULWOORDEN.sub(" ", k)
    k = re.sub(r"\s+", " ", k).strip()
    while True:
        nieuw = _STAART.sub("", k).strip()
        if nieuw == k:
            break
        k = nieuw

    # Inleidingen aan het begin (hoogstens drie na elkaar).
    for _ in range(3):
        gewijzigd = False
        for patroon in _INLEIDINGEN:
            nieuw = patroon.sub("", k, count=1).strip()
            if nieuw != k:
                k, gewijzigd = nieuw, True
                break
        if not gewijzigd:
            break

    # "een soort fruit" / "een vorm van neerslag" -> "een fruit" / "een neerslag",
    # maar alleen in vragen over een relatie.
    if _RELATIE_START.match(k):
        k = _SOORT.sub(lambda m: m.group(1) + " ", k)

    # Eerste regel die de HELE zin dekt, wint.
    regels = REGELS + REGELS_CITAAT if had_citaat else REGELS
    for naam, patroon, bouwer in regels:
        m = patroon.match(k)
        if not m:
            continue
        resultaat = bouwer(m)
        if resultaat is None:
            # Regel paste, maar een term is niet toegelaten: niets herschrijven.
            return tekst, None
        if resultaat == opgeschoond:
            return tekst, None
        return resultaat, naam

    return tekst, None