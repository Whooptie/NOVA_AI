# core/context_resolver.py
"""
Punt 62d (4 november 2026): vervolgvragen die op de LAATSTE kennisvraag voortbouwen.

Wat het oplost (alleen kennisvragen, net als core/language_normalizer.py):

    "wat is een hond"        ->  "en een kat?"        =  "wat is een kat"
    "is een zebra een dier"  ->  "en een kat?"        =  "is een kat een dier"
    "wat is een tijger"      ->  "is dat een dier"    =  "is een tijger een dier"
    "wat is regen"           ->  "wat is het gevolg ervan"  =  "wat zijn de gevolgen van regen"

Hoe het werkt (100% symbolisch, geen ML, geen coreference-model):
1. Elke kennisvraag die in een van de vaste VRAAGVORMEN past, wordt onthouden als
   (sjabloon, onderwerp), bv. ("is {x} een dier", "een zebra"). Dat gebeurt in
   core/last_context.py.
2. Een vervolgzin in een van de vaste VERVOLGVORMEN ("en een kat?", "is dat een
   dier", "wat is het gevolg ervan") wordt herschreven door het onderwerp of het
   verwijswoord in het onthouden sjabloon in te vullen.
3. Past de zin in geen enkele vorm, of is er geen (niet-verlopen) onthouden vraag,
   dan gebeurt er NIETS: de zin blijft precies zoals ze was.

Bewust niet (v1): meerdere eerder besproken onderwerpen onthouden ("En wat eten
die?" kan op hond én kat slaan) en vragen bij twijfel wat Kevin bedoelt. Alleen de
LAATSTE vraag telt. De kale verwijzingen zonder zelfstandig naamwoord ("die?",
"wat is dat?") blijven bij de bestaande code in intent_router.py.
"""

import re

_W = r"[a-zà-ÿ][a-zà-ÿ\-]*"
_LID = r"(?:een|de|het)"
# Een onderwerp: optioneel lidwoord + 1 of 2 woorden. Geen vraag- of functiewoorden.
_NP = rf"(?:{_LID} )?{_W}(?: {_W})?"
_NP_KAAL = rf"{_W}(?: {_W})?"
# Punt 76 (5 november 2026): bij oorzaak- en gevolgvragen is het onderwerp vaak een hele
# gebeurtenis ("te veel koffie drinkt", "te lang in de kou staat"): 1 tot 7 woorden.
_EVENT = rf"{_W}(?: {_W}){{0,6}}"

# Woorden die nooit een onderwerp zijn (anders zou "en dat?" of "en hoe?" een begrip lijken).
_GEEN_ONDERWERP = {
    "dat", "die", "dit", "deze", "het", "er", "ervan", "daarvan", "hiervan", "hij", "zij", "ze",
    "ik", "je", "jij", "u", "we", "wij", "jullie", "mij", "me", "jou", "hem", "haar",
    "wat", "wie", "waar", "wanneer", "waarom", "waardoor", "hoe", "welk", "welke", "hoeveel",
    "is", "zijn", "was", "waren", "een", "de", "ook", "niet", "geen", "nog", "dan", "of", "en",
    "van", "voor", "met", "bij", "op", "in", "aan", "naar", "over", "door", "als", "zo",
    # Ronde 2: bijwoorden en tussenwerpsels ("en nu?", "dan toch?", "ok dan") zijn geen begrip.
    "nu", "nog", "weer", "toch", "wel", "hier", "daar", "misschien", "alweer", "altijd", "nooit",
    "zeker", "ja", "nee", "ok", "oke", "oké", "okee", "nou", "maar", "hallo", "doei", "bedankt",
    "dankje", "dank", "idem", "ervoor", "daarvoor", "hiervoor", "daardoor", "hierdoor",
}

_ARTIKEL = re.compile(rf"^{_LID} ")

# Woorden die in een gebeurtenis nooit voorkomen: dan is het een verwijzing of een vraag aan
# Nova zelf, geen gebeurtenis die we kunnen onthouden.
_GEEN_GEBEURTENIS = frozenset({
    "dat", "dit", "die", "deze", "wat", "wie", "waar", "wanneer", "waarom", "waardoor", "hoe",
    "welk", "welke", "ik", "mij", "me", "u", "jij", "jou", "wij", "we", "nova",
})


def _schoon(tekst):
    t = (tekst or "").lower().strip()
    t = re.sub(r"[?!.]+$", "", t).strip()
    t = re.sub(r"\s+", " ", t)
    return t


# Voorzetsels zijn zonder lidwoord nooit een onderwerp ("en bij?"), maar "bij" met lidwoord
# is een insect ("een bij").
_VOORZETSEL_ALS_NAAMWOORD = frozenset({"bij"})


def _onderwerp_ok(np):
    """True als 'np' (met of zonder lidwoord) echt een onderwerp kan zijn."""
    kaal = _ARTIKEL.sub("", np)
    woorden = kaal.split()
    if not woorden or len(woorden) > 2:
        return False
    heeft_lid = kaal != np
    for w in woorden:
        if w in _GEEN_ONDERWERP and not (heeft_lid and w in _VOORZETSEL_ALS_NAAMWOORD):
            return False
    return True


# --------------------------------------------------------------------------
# 1. Vraagvormen: welke zinnen onthouden we als "laatste kennisvraag"?
#    (naam, patroon, bouwer). De bouwer geeft (sjabloon_met_{x}, onderwerp, soort)
#    "soort" bepaalt of het onderwerp met of zonder lidwoord in het sjabloon komt.
# --------------------------------------------------------------------------
def _bouw_definitie(m):
    return "wat is {x}", m.group("x"), "np"


def _bouw_relatie(m):
    return f"is {{x}} {m.group('y')}", m.group("x"), "np"


def _bouw_oorzaak(m):
    return "wat veroorzaakt {x}", m.group("x"), "kaal"


def _bouw_gevolg(m):
    return "wat zijn de gevolgen van {x}", m.group("x"), "kaal"


def _bouw_synoniem(m):
    return "wat is een synoniem van {x}", m.group("x"), "kaal"


def _gebeurtenis_ok(x):
    """True als 'x' een gebeurtenis van 2 tot 7 woorden is ("te veel koffie drinkt").

    Strenger dan nodig is het niet: alleen verwijzingen en vraagwoorden vallen af, en de
    gebeurtenis mag niet met een verwijswoord of bijwoord uit _GEEN_ONDERWERP beginnen.
    Eén woord valt hier bewust af: dat gaat via _onderwerp_ok().
    """
    woorden = _kaal(x).split()
    if not 2 <= len(woorden) <= 7:
        return False
    if woorden[0] in _GEEN_ONDERWERP:
        return False
    return not any(w in _GEEN_GEBEURTENIS for w in woorden)


VRAAGVORMEN = [
    # Specifieke vormen eerst, de kale definitie als laatste.
    ("synoniem", re.compile(rf"^wat is een synoniem van (?P<x>{_NP_KAAL})$"), _bouw_synoniem),
    ("gevolg", re.compile(rf"^wat zijn de gevolgen van (?P<x>{_EVENT})$"), _bouw_gevolg),
    # Punt 76: de normalizer laat "wat is het gevolg van roken" ongemoeid, dus onthouden we
    # ook die vorm (en zijn varianten) onder hetzelfde sjabloon.
    ("gevolg_enkelvoud",
     re.compile(rf"^wat (?:is|zijn) (?:het gevolg|de gevolgen|het effect|de effecten|het resultaat|"
                rf"de resultaten) van (?P<x>{_EVENT})$"), _bouw_gevolg),
    ("oorzaak", re.compile(rf"^wat veroorzaakt (?P<x>{_EVENT})$"), _bouw_oorzaak),
    ("relatie", re.compile(rf"^is (?P<x>{_NP}) (?P<y>{_LID} {_W}(?: {_W})?)$"), _bouw_relatie),
    ("definitie", re.compile(rf"^wat is (?P<x>{_NP})$"), _bouw_definitie),
]


def herken_vraag(tekst):
    """Geeft (sjabloon, onderwerp, soort) als 'tekst' een onthoudbare kennisvraag is, anders None.

    sjabloon bevat {x} op de plek van het onderwerp, bv. ("is {x} een dier", "een zebra", "np").
    """
    t = _schoon(tekst)
    for _naam, patroon, bouwer in VRAAGVORMEN:
        m = patroon.match(t)
        if not m:
            continue
        sjabloon, onderwerp, soort = bouwer(m)
        # Punt 76: een oorzaak- of gevolgvraag mag ook over een gebeurtenis gaan.
        if not (_onderwerp_ok(onderwerp) or (soort == "kaal" and _gebeurtenis_ok(onderwerp))):
            return None
        # Bij een relatie moet ook het doel (y) een echt begrip zijn, niet "is dat een dier".
        if "y" in m.groupdict() and not _onderwerp_ok(m.group("y")):
            return None
        return sjabloon, onderwerp, soort
    return None


# --------------------------------------------------------------------------
# 2. Vervolgvormen: welke zinnen vullen we aan met de onthouden vraag?
# --------------------------------------------------------------------------
# Een leidend "ok", "nou", "maar" of "ja" wordt eerst weggehaald: "ok en een krant" = "en een krant".
_TUSSENWERPSEL = re.compile(r"^(?:ok|oke|oké|okee|nou|maar|ja)[, ]+")

# Zelfde vraag, nieuw onderwerp. Ronde 2 (4 november 2026) kent meer manieren om het te zeggen:
# "hoe zit dat met een auto", "wat dacht je van een banaan", "idem voor een vis", "en dan een tafel".
_ELLIPS = re.compile(
    r"^(?:en dan|en hoe zit (?:het|dat) (?:dan )?met|hoe zit (?:het|dat) (?:dan )?met|"
    r"en hoe is het met|hoe is het met|en wat dacht je van|wat dacht je van|"
    r"en wat denk je van|wat denk je van|en wat met|wat met|"
    r"idem (?:voor|met)|hetzelfde (?:voor|met|geldt voor)|datzelfde (?:voor|met)|"
    rf"ook (?:voor|met)|en|dan) (?P<k>{_NP})$"
)
# Ronde 3: "een nijlpaard ook?", "en boter dan?", "een mug wel?" = zelfde vraag, nieuw onderwerp.
_W_ZONDER_BIJWOORD = r"(?!(?:ook|dan|wel|nog)\b)[a-zà-ÿ][a-zà-ÿ\-]*"
_NP_ACHTER = rf"(?:{_LID} )?{_W_ZONDER_BIJWOORD}(?: {_W_ZONDER_BIJWOORD})?"
_ELLIPS_ACHTER = re.compile(rf"^(?:en )?(?P<k>{_NP_ACHTER}) (?:ook nog|dan ook|ook|dan|wel|nog)$")
# Vulwoorden aan het eind die niets veranderen: "hoe komt dat eigenlijk".
_VUL_EIND = re.compile(r"\s+(?:eigenlijk|precies|nou|toch|even|trouwens)$")
# Punt 76: ook "zo'n ding", "dat ding" ("hoe ontstaat zo'n ding"). Langste vormen eerst.
_NAAM = r"(?:zo'n ding|dat ding|dit ding|die ding|dat|dit|die|deze|het)"
# Punt 76: het lidwoord van het doel mag ontbreken ("is dat fruit"). Dat is alleen veilig
# als het doel een bekend concept is; zie de controle met 'is_concept' in los_op().
_RELATIE_VERWIJZING = re.compile(
    rf"^(?:en )?is {_NAAM} (?:dan )?(?:ook )?(?P<y>(?:{_LID} )?{_W}(?: {_W})?)$"
)
# Punt 76: "waardoor smelt dat" / "waarom werkt dat": werkwoord + verwijzing. Het onderwerp
# komt uit de laatste vraag ("ijs" -> "wat veroorzaakt ijs smelt").
# Punt 72b: "wat doet zo'n ding" / "wat meet dat ding eigenlijk" / "wat doet dat orgaan" na een
# definitievraag. Bewust een kleine vaste lijst verwijswoorden; het onderwerp is dat van de vorige vraag.
_FUNCTIE_VERWIJZING = re.compile(
    r"^(?:en )?wat (?:doet|meet|is de functie van) "
    r"(?:zo'n ding|dat ding|dit ding|die ding|dat orgaan|dit orgaan|dat gereedschap|dit gereedschap|"
    r"dat instrument|dit instrument|dat apparaat|dit apparaat|dat voorwerp|dit voorwerp|dat|dit|het)$"
)
_WERKWOORD_VERWIJZING = re.compile(rf"^(?:en )?(?:waardoor|waarom) (?P<v>{_W}) {_NAAM}$")
# Koppel-, hulp- en modale werkwoorden zijn geen gebeurtenis ("waarom is dat zo").
_GEEN_GEBEURTENIS_WERKWOORD = frozenset({
    "is", "zijn", "ben", "bent", "was", "waren", "heb", "heeft", "hebt", "hebben", "had",
    "kan", "kun", "kunt", "kunnen", "kon", "wil", "wilt", "willen", "moet", "moeten",
    "mag", "mogen", "zal", "zullen", "zou", "zouden", "doe", "doet", "doen",
})
# "hoort die bij de zoogdieren" (punt 70): klasse in het meervoud, zoals in de normalizer.
_HOORT_VERWIJZING = re.compile(
    rf"^(?:en )?(?:hoort|behoort|valt) {_NAAM} (?:dan )?(?:ook )?(?:bij|tot|onder) de (?P<y>{_W})$"
)
_VERWIJS = r"(?:ervan|daarvan|hiervan|van dat|van dit|van die|van deze)"
_GEVOLG_VERWIJZING = re.compile(
    r"^(?:en )?(?:"
    rf"wat (?:is|zijn) (?:het gevolg|de gevolgen|het effect|de effecten|het resultaat|de resultaten) {_VERWIJS}|"
    r"wat (?:gebeurt|komt|ontstaat|volgt) er (?:dan|daardoor|hierdoor|ervan|daarvan|hiervan|daarop|hierop|vervolgens|daarna)|"
    r"wat (?:komt|gebeurt) er (?:dan )?van|"
    rf"wat heeft {_NAAM} voor (?:gevolgen|effecten)|"
    r"(?:de |het )?(?:gevolgen?|effecten?|resultaten?)(?: daarvan| ervan| hiervan)?"
    r")$"
)
_OORZAAK_VERWIJZING = re.compile(
    r"^(?:en )?(?:"
    rf"(?:wat|waardoor) (?:is|zijn) (?:de oorzaak|de oorzaken) {_VERWIJS}|"
    rf"waardoor (?:ontstaat|komt|is|wordt|ontstond|gebeurt|gaat) {_NAAM}|"
    rf"hoe komt {_NAAM}(?: dan)?|"
    r"(?:de )?oorza(?:ak|ken)(?: daarvan| ervan| hiervan)?|"
    r"wat (?:zorgt|zorgde) (?:er|hier|daar)voor|"
    rf"wat veroorzaakt {_NAAM}|"
    rf"hoe ontstaat {_NAAM}"
    r")$"
)
# "wat is een ander woord voor" (ook afgebroken), "welk woord betekent hetzelfde".
_SYNONIEM_VERWIJZING = re.compile(
    r"^(?:en )?(?:"
    r"(?:wat|welk woord) (?:is|zijn) (?:er )?(?:nog )?(?:een )?(?:ander woord|synoniem|ander woord of synoniem)"
    r"(?: voor| ervoor| daarvoor| hiervoor| voor dat| voor dit)?|"
    r"welk woord (?:betekent|heeft) (?:hetzelfde|dezelfde betekenis)(?: als dat| als dit)?|"
    r"(?:een )?(?:ander woord|synoniem|synoniemen)(?: voor| ervoor| daarvoor| hiervoor)?"
    r")$"
)


def _kaal(np):
    return _ARTIKEL.sub("", np)


def los_op(tekst, sjabloon, onderwerp, soort, is_concept=None):
    """Probeert 'tekst' aan te vullen met de onthouden vraag.

    Geeft (nieuwe_tekst, regelnaam) of None als de zin in geen vervolgvorm past.
    Dit is bewust voorzichtig: een zin die ook maar een beetje afwijkt, blijft ongemoeid.

    is_concept (punt 76): optionele functie woord -> True/False. Zonder die functie wordt
    een doel zonder lidwoord ("is dat fruit") niet opgelost, want "is dat goed" mag nooit
    "is een appel goed" worden. De router geeft hier store.has_concept mee.
    """
    if not sjabloon or not onderwerp:
        return None
    t = _VUL_EIND.sub("", _TUSSENWERPSEL.sub("", _schoon(tekst)))

    # "wat is het gevolg ervan" / "wat is de oorzaak ervan" -> onderwerp van de laatste vraag.
    if _GEVOLG_VERWIJZING.match(t):
        return f"wat zijn de gevolgen van {_kaal(onderwerp)}", "gevolg_verwijzing"
    if _OORZAAK_VERWIJZING.match(t):
        return f"wat veroorzaakt {_kaal(onderwerp)}", "oorzaak_verwijzing"

    if _SYNONIEM_VERWIJZING.match(t):
        return f"wat is een synoniem van {_kaal(onderwerp)}", "synoniem_verwijzing"

    # Punt 72b: "wat doet zo'n ding" na "wat is een tang" -> "wat is een tang" (de definitie
    # bevat meestal wat het ding doet). Alleen na een definitie- of relatievraag met een lidwoord.
    if _FUNCTIE_VERWIJZING.match(t) and soort == "np":
        return f"wat is {onderwerp}", "functie_verwijzing"

    # Punt 76: "waardoor smelt dat" na "wat is ijs" -> "wat veroorzaakt ijs smelt".
    # Zelfde vorm als de normalizer maakt van "waardoor smelt ijs" (onderwerp + werkwoord).
    m = _WERKWOORD_VERWIJZING.match(t)
    if m and soort in ("np", "kaal"):
        v = m.group("v")
        if v not in _GEEN_ONDERWERP and v not in _GEEN_GEBEURTENIS_WERKWOORD:
            return f"wat veroorzaakt {_kaal(onderwerp)} {v}", "oorzaak_werkwoord_verwijzing"

    # "en een kat?" -> zelfde vraag, ander onderwerp.
    m = _ELLIPS.match(t)
    if m and _onderwerp_ok(m.group("k")):
        k = m.group("k")
        invulling = _kaal(k) if soort == "kaal" else k
        return sjabloon.format(x=invulling), "ellips"

    # "een nijlpaard ook?" / "en boter dan?" -> zelfde vraag, ander onderwerp.
    m = _ELLIPS_ACHTER.match(t)
    if m and _onderwerp_ok(m.group("k")):
        k = m.group("k")
        invulling = _kaal(k) if soort == "kaal" else k
        return sjabloon.format(x=invulling), "ellips"

    # "is dat een dier" -> zelfde onderwerp, nieuw doel. Alleen na een definitie- of relatievraag.
    m = _RELATIE_VERWIJZING.match(t)
    if m and soort == "np":
        y = m.group("y")
        if not _onderwerp_ok(y):
            return None
        # Punt 76: zonder lidwoord ("is dat fruit") alleen als het doel een bekend concept is.
        if not _ARTIKEL.match(y) and not (is_concept is not None and is_concept(y)):
            return None
        return f"is {onderwerp} {y}", "relatie_verwijzing"

    m = _HOORT_VERWIJZING.match(t)
    if m and soort == "np":
        y = m.group("y")
        if len(y) >= 4 and re.search(r"(?:en|s)$", y) and _onderwerp_ok(y):
            return f"is {onderwerp} een {y}", "hoort_verwijzing"

    return None


def is_verwijzing_zonder_onderwerp(tekst):
    """True als 'tekst' alleen een verwijzing is die zonder eerdere vraag niets betekent
    ("waardoor ontstaat dat", "wat is een ander woord voor", "wat komt er van").

    De router gebruikt dit om zo'n zin NIET als onderwerp "ander woord voor" naar
    Wikipedia te sturen als er niets onthouden is (punt 74)."""
    t = _VUL_EIND.sub("", _TUSSENWERPSEL.sub("", _schoon(tekst)))
    if _WERKWOORD_VERWIJZING.match(t):
        v = _WERKWOORD_VERWIJZING.match(t).group("v")
        if v not in _GEEN_ONDERWERP and v not in _GEEN_GEBEURTENIS_WERKWOORD:
            return True
    return bool(
        _GEVOLG_VERWIJZING.match(t) or _OORZAAK_VERWIJZING.match(t) or _SYNONIEM_VERWIJZING.match(t)
        or _FUNCTIE_VERWIJZING.match(t)
    )