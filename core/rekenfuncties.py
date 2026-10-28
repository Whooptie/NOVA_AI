# core/rekenfuncties.py
#
# Gewone taal -> formule-aanroep voor modules/math/math.py (28 oktober 2026).
#
#   "wat is de afgeleide van x kwadraat in 3"     -> afgeleide(x^2, 3)
#   "ontbind x^2 - 4"                             -> factor_sym(x^2 - 4)
#   "zoek de waarde van x, als 2x + 3 = 11"       -> solve_sym(2x + 3 = 11)
#   "de grootste gemene deler van 48 en 18"       -> ggd(48, 18)
#   "is zeventien een priemgetal"                 -> is_priem(17)
#   "het gemiddelde van 2, 4 en 6"                -> gemiddelde([2, 4, 6])
#   "255 naar binair"                             -> naar_binair(255)
#
# PUUR SYMBOLISCH: een tabel met zinssjablonen (reguliere expressies) die elk
# naar één math.py-functie wijzen, plus een strenge controle van wat er op de
# plaats van de argumenten staat. Geen ML, geen gokwerk.
#
# Alles of niets: past de HELE zin niet op een sjabloon, of is een argument
# geen geldig getal/formule, dan geeft vertaal_functiezin() None terug en loopt
# de zin gewoon door de normale routing.
#
# Gebruik in de router: importeer vertaal_wiskundezin (probeert eerst deze
# sjablonen, daarna de gewone rekenzin-parser uit core/rekenwoorden.py).

import math
import re

from core.rekenwoorden import (
    vertaal_rekenzin,
    _MAX_LENGTE,
    _normaliseer,
    _tokeniseer,
    _voeg_komma_getallen_samen,
    _bouw_tokens,
    _run_naar_getal,
)

# ---------------------------------------------------------------------
# Voorwoorden die we vooraan/achteraan weghalen ("kun je ... alsjeblieft")
# ---------------------------------------------------------------------
_VOORWOORDEN = sorted((
    "kun je mij", "kun je me", "kan je mij", "kan je me", "kun je", "kan je",
    "wil je", "zou je", "wat is dan", "hoeveel is dan", "wat zijn", "wat is",
    "hoeveel is", "hoeveel zijn", "geef mij", "geef me", "geef",
    "bereken eens", "bereken", "reken eens uit", "reken uit", "bepaal",
    "zoek", "vind", "eens", "even",
), key=len, reverse=True)

_STAARTWOORDEN = (" alsjeblieft", " alsjeblief", " graag", " voor me",
                  " voor mij", " even", " eens", " berekenen",
                  " uitrekenen", " bepalen")


def _schoon(tekst):
    t = tekst.lower().strip().rstrip("?!. ").strip()
    t = re.sub(r"\s+", " ", t)
    veranderd = True
    while veranderd:
        veranderd = False
        for woord in _VOORWOORDEN:
            if t.startswith(woord + " "):
                t = t[len(woord) + 1:].strip()
                veranderd = True
                break
        for woord in _STAARTWOORDEN:
            if t.endswith(woord):
                t = t[: -len(woord)].strip()
                veranderd = True
    return t


# ---------------------------------------------------------------------
# Argumenten controleren: getallen en formules
# ---------------------------------------------------------------------
def _getal(s):
    """'3', '2,5', 'drie', 'min vijf', '-4' -> '3', '2.5', '3', '-5', '-4'. None bij fout."""
    s = (s or "").strip()
    neg = False
    m = re.match(r"^(?:min|minus)\s+(.+)$", s)
    if m:
        neg, s = True, m.group(1).strip()
    elif s.startswith("-"):
        neg, s = True, s[1:].strip()
    if re.fullmatch(r"\d+(?:[.,]\d+)?", s):
        w = s.replace(",", ".")
    else:
        woorden = [_normaliseer(x) for x in s.split()]
        if not woorden or not all(x.isalpha() for x in woorden):
            return None
        w = _run_naar_getal(woorden)
        if w is None:
            return None
    if neg and float(w) != 0:
        return "-" + w
    return w


def _int(s):
    w = _getal(s)
    if w is not None and re.fullmatch(r"-?\d+", w):
        return w
    return None


_VARS = frozenset("xyzt")
_FUNCS = frozenset(("sin", "cos", "tan", "log", "ln", "exp", "sqrt", "abs"))
_OPS = {"PLUS": "+", "MIN": "-", "MUL": "*", "DIV": "/", "POW": "^"}


def _formule(s, eis_var=False):
    """
    Leest een formule in cijfers en/of woorden ("x kwadraat min vier",
    "2x + 3", "(x+1)^2") en schrijft hem op zoals math.py hem wil zien
    ("x^2 - 4"). None als er iets niet klopt. Met eis_var=True moet er
    minstens één variabele (x, y, z of t) in staan.
    """
    t = (s or "").lower().strip()
    t = t.replace("÷", " / ").replace("×", " * ")
    t = re.sub(r"(?<=\d)\s*x\s*(?=\d)", " * ", t)   # 3 x 4 = 3 * 4
    raw = _tokeniseer(t)
    if not raw:
        return None
    raw = _voeg_komma_getallen_samen(raw)

    items = []          # (soort, tekst)
    stuk = []

    def leeg_stuk():
        if not stuk:
            return True
        toks = _bouw_tokens(stuk)
        stuk.clear()
        if toks is None:
            return False
        for naam, waarde, _ in toks:
            if naam == "NUM":
                items.append(("NUM", waarde))
            elif naam in _OPS:
                items.append(("OP", _OPS[naam]))
            elif naam == "POST":
                items.append(("OP", "^"))
                items.append(("NUM", str(waarde)))
            elif naam == "LP":
                items.append(("LP", "("))
            elif naam == "RP":
                items.append(("RP", ")"))
            else:
                return False          # bv. 'en', 'komma', 'de som van'
        return True

    for tok in raw:
        soort, tekst, _ = tok
        if soort == "WORD" and tekst in _VARS:
            if not leeg_stuk():
                return None
            items.append(("VAR", tekst))
        elif soort == "WORD" and tekst in _FUNCS:
            if not leeg_stuk():
                return None
            items.append(("FUNC", tekst))
        else:
            stuk.append(tok)
    if not leeg_stuk() or not items:
        return None

    # --- controle van de volgorde ---
    diepte = 0
    vorige = None
    for i, (soort, tekst) in enumerate(items):
        if soort == "LP":
            if vorige in ("NUM", "VAR", "RP"):
                return None
            diepte += 1
        elif soort == "RP":
            diepte -= 1
            if diepte < 0 or vorige in (None, "OP", "UMIN", "LP", "FUNC"):
                return None
        elif soort == "OP":
            if tekst == "-" and vorige in (None, "LP"):
                items[i] = ("UMIN", "-")
                soort = "UMIN"
            elif vorige not in ("NUM", "VAR", "RP"):
                return None
        elif soort == "NUM":
            if vorige in ("NUM", "VAR", "RP"):
                return None
        elif soort == "VAR":
            if vorige in ("VAR", "RP"):
                return None
        elif soort == "FUNC":
            if vorige in ("NUM", "VAR", "RP"):
                return None
            if i + 1 >= len(items) or items[i + 1][0] != "LP":
                return None
        vorige = soort
    if diepte != 0 or vorige not in ("NUM", "VAR", "RP"):
        return None
    if eis_var and not any(soort == "VAR" for soort, _ in items):
        return None

    uit = ""
    for soort, tekst in items:
        if soort == "OP":
            uit += "^" if tekst == "^" else f" {tekst} "
        else:
            uit += tekst
    return uit


def _vergelijking(s):
    """'2x + 3 = 11' (of '... is gelijk aan ...') -> '2x + 3 = 11'. None bij fout."""
    v = re.sub(r"\s+(?:is\s+)?gelijk\s+aan\s+", " = ", (s or "").strip())
    delen = v.split("=")
    if len(delen) != 2:
        return None
    links = _formule(delen[0])
    rechts = _formule(delen[1])
    if links is None or rechts is None:
        return None
    if not re.search(r"[xyzt]", links + rechts):
        return None
    return f"{links} = {rechts}"


# ---------------------------------------------------------------------
# Bouwers: elk sjabloon heeft er één
# ---------------------------------------------------------------------
def _alg(functie):
    """Eén formule met een variabele erin: factor_sym(...), expand_sym(...), ..."""
    def bouw(m):
        f = _formule(m.group("f"), eis_var=True)
        return f"{functie}({f})" if f else None
    return bouw


def _getallen(functie, *namen):
    """Alleen hele getallen als argumenten: ggd(48, 18)."""
    def bouw(m):
        waarden = []
        for n in namen:
            w = _int(m.group(n))
            if w is None:
                return None
            waarden.append(w)
        return f"{functie}({', '.join(waarden)})"
    return bouw


def _vergelijk_bouw(m):
    eq = _vergelijking(m.group("v"))
    return f"solve_sym({eq})" if eq else None


def _stelsel_bouw(m):
    a = _vergelijking(m.group("a"))
    b = _vergelijking(m.group("b"))
    return f"solve_stelsel({a}, {b})" if a and b else None


def _nulpunten_bouw(m):
    f = _formule(m.group("f"), eis_var=True)
    return f"solve_sym({f} = 0)" if f else None


def _afgeleide_punt(m):
    f = _formule(m.group("f"), eis_var=True)
    p = _getal(m.group("p"))
    return f"afgeleide({f}, {p})" if f and p is not None else None


def _integraal_grenzen(m):
    f = _formule(m.group("f"), eis_var=True)
    a = _getal(m.group("a"))
    b = _getal(m.group("b"))
    if f and a is not None and b is not None:
        return f"integraal({f}, {a}, {b})"
    return None


def _limiet_bouw(m):
    f = _formule(m.group("f"), eis_var=True)
    a = _getal(m.group("a"))
    return f"limiet({f}, {a})" if f and a is not None else None


def _abs_bouw(m):
    f = _formule(m.group("f"))
    return f"abs({f})" if f else None


def _afronden_bouw(m):
    n = _getal(m.group("n"))
    d = _int(m.group("d"))
    return f"round({n}, {d})" if n is not None and d is not None else None


_STATISTIEK = {
    "gemiddelde": "gemiddelde", "gemiddeld": "gemiddelde",
    "mediaan": "mediaan", "modus": "modus", "variantie": "variantie",
    "standaardafwijking": "stdafwijking", "standaarddeviatie": "stdafwijking",
}


def _lijst_bouw(m):
    naam = _STATISTIEK[m.group("w")]
    lst = m.group("lst").strip().strip("[]()")
    delen = [d.strip() for d in re.split(r"\s*,\s*|\s+en\s+", lst) if d.strip()]
    waarden = [_getal(d) for d in delen]
    if len(waarden) < 2 or any(w is None for w in waarden):
        return None
    return f"{naam}([{', '.join(waarden)}])"


_NAAR_STELSEL = {"binair": "naar_binair", "octaal": "naar_octaal",
                 "hex": "naar_hex", "hexadecimaal": "naar_hex"}
_STELSEL_BASIS = {"binair": 2, "octaal": 8, "hex": 16, "hexadecimaal": 16}


def _naar_stelsel_bouw(m):
    n = _int(m.group("n"))
    if n is None or n.startswith("-"):
        return None
    return f"{_NAAR_STELSEL[m.group('s')]}({n})"


def _uit_stelsel_bouw(m):
    basis = _STELSEL_BASIS[m.group("s")]
    cijfers = m.group("n")
    try:
        int(cijfers, basis)
    except ValueError:
        return None
    return f'vanuit_talstelsel("{cijfers}", {basis})'


# ---------------------------------------------------------------------
# De sjablonentabel (volgorde telt: specifiek vóór algemeen)
# ---------------------------------------------------------------------
_V = r"[xyzt]"


# =====================================================================
# UITBREIDING (28 oktober 2026, deel 2): vectoren, matrices, fysica,
# kansen, breuken, reeksen, sorteren/zoeken, precisie
# =====================================================================

# --- vectoren en matrices -------------------------------------------
def _vector(s):
    """'[1, 2, 3]' of '(1,2,3)' -> ['1', '2', '3']. None bij fout."""
    s = (s or "").strip()
    if not re.fullmatch(r"[\[(][^\[\]()]*[\])]", s):
        return None
    waarden = [_getal(d.strip()) for d in s[1:-1].split(",")]
    if not waarden or any(w is None for w in waarden):
        return None
    return waarden


def _matrix(s):
    """'[[1,2],[3,4]]' of '[1 2; 3 4]' -> [['1','2'],['3','4']]. None bij fout."""
    s = (s or "").strip()
    if re.fullmatch(r"\[\s*\[[^\[\]]*\](?:\s*,?\s*\[[^\[\]]*\])*\s*\]", s):
        rij_teksten = re.findall(r"\[([^\[\]]*)\]", s[1:-1])
    elif s.startswith("[") and s.endswith("]") and ";" in s and "[" not in s[1:-1]:
        rij_teksten = s[1:-1].split(";")
    else:
        return None
    rijen = []
    for tekst in rij_teksten:
        delen = [d for d in re.split(r"\s*,\s*|\s+", tekst.strip()) if d]
        waarden = [_getal(d) for d in delen]
        if not waarden or any(w is None for w in waarden):
            return None
        rijen.append(waarden)
    if len({len(r) for r in rijen}) != 1:
        return None
    return rijen


def _fmt(waarden):
    return "[" + ", ".join(waarden) + "]"


def _fmt_m(rijen):
    return "[" + ", ".join(_fmt(r) for r in rijen) + "]"


def _vg(naam):
    """Regex-stukje voor één vector, bv. [1,2,3] of (1,2,3)."""
    return rf"(?P<{naam}>[\[(][^\[\]()]*[\])])"


_MG = r"(?P<m>\[\[.*\]\]|\[[^\[\]]*;[^\[\]]*\])"


def _vec1(functie):
    def bouw(m):
        a = _vector(m.group("a"))
        return f"{functie}({_fmt(a)})" if a else None
    return bouw


def _vec2(functie, lengte=None):
    def bouw(m):
        a, b = _vector(m.group("a")), _vector(m.group("b"))
        if a is None or b is None or len(a) != len(b):
            return None
        if lengte is not None and len(a) != lengte:
            return None
        return f"{functie}({_fmt(a)}, {_fmt(b)})"
    return bouw


def _mat1(functie, vierkant=False):
    def bouw(m):
        r = _matrix(m.group("m"))
        if r is None or (vierkant and len(r) != len(r[0])):
            return None
        return f"{functie}({_fmt_m(r)})"
    return bouw


def _stelsel_matrix_bouw(m):
    r = _matrix(m.group("m"))
    v = _vector(m.group("v"))
    if r is None or v is None or len(r) != len(r[0]) or len(v) != len(r):
        return None
    return f"solve({_fmt_m(r)}, {_fmt(v)})"


def _rotatie_bouw(m):
    """rotX/rotY/rotZ in math.py rekenen in RADIALEN. In gewone taal zeggen we
    graden, dus die rekenen we hier om (tenzij er 'radialen' staat)."""
    tekst = m.group("h").strip()
    in_radialen = bool(re.search(r"(?:\s|\d)(?:radialen|radiaal|rad)$", tekst))
    if in_radialen:
        tekst = re.sub(r"\s*(?:radialen|radiaal|rad)$", "", tekst)
    h = _fys(tekst)
    if h is None:
        return None
    waarde = float(h) if in_radialen else math.radians(float(h))
    return f"rot{m.group('as').upper()}({waarde!r})"


# --- fysica ----------------------------------------------------------
_EENHEID = (r"(?:kg|kilogram|kilo|gram|g|m/s²|m/s\^2|m/s2|m/s|meter per seconde|"
            r"meter|m|seconden|seconde|sec|s|newton|n|joule|j|graden|graad|°)")


def _fys(s):
    """'1000 kg', '9,81 m/s²', '45 graden', 'tien' -> getal als tekst. None bij fout."""
    s = (s or "").strip()
    m = re.fullmatch(rf"(.+?)(?:\s+|(?<=\d)){_EENHEID}", s)
    if m:
        s = m.group(1)
    return _getal(s)


def _fys_functie(functie, *namen):
    def bouw(m):
        waarden = []
        for n in namen:
            w = _fys(m.group(n))
            if w is None:
                return None
            waarden.append(w)
        return f"{functie}({', '.join(waarden)})"
    return bouw


# --- kansen en statistiek met twee lijsten --------------------------
def _decimaal_functie(functie, *namen):
    """Getallen (ook decimalen) als argumenten, bv. binomiaal(10, 3, 0.5)."""
    def bouw(m):
        waarden = []
        for n in namen:
            w = _getal(m.group(n))
            if w is None:
                return None
            waarden.append(w)
        return f"{functie}({', '.join(waarden)})"
    return bouw


def _twee_lijsten_bouw(m):
    a, b = _vector(m.group("a")), _vector(m.group("b"))
    if a is None or b is None or len(a) != len(b) or len(a) < 2:
        return None
    naam = "regressie" if m.group("w").endswith("regressie") else "correlatie"
    return f"{naam}({_fmt(a)}, {_fmt(b)})"


# --- breuken, reeksen -------------------------------------------------
def _breuk_bouw(m):
    f = _formule(m.group("e"))
    if f is None or re.search(r"[a-z]", f):
        return None
    uit = re.sub(r"(?<![\d.])(\d+) / (\d+)(?![\d.])", r"breuk(\1, \2)", f)
    rest = re.sub(r"breuk\(\d+, \d+\)", "", uit)
    if "/" in rest or "." in rest or "breuk" not in uit:
        return None
    return uit


def _sigma_bouw(m):
    f = _formule(m.group("f"), eis_var=True)
    a, b = _int(m.group("a")), _int(m.group("b"))
    return f"sigma({f}, {a}, {b})" if f and a is not None and b is not None else None


def _bereken_in_punt(m):
    f = _formule(m.group("f"), eis_var=True)
    p = _getal(m.group("p"))
    return f"bereken({f}, {p})" if f and p is not None else None


def _nulpunt_bouw(m):
    f = _formule(m.group("f"), eis_var=True)
    s = _getal(m.group("s"))
    return f"nulpunt({f}, {s})" if f and s is not None else None


# --- sorteren, zoeken, woorden ----------------------------------------
def _sorteer_bouw(m):
    l = _vector(m.group("l"))
    return f"quick_sort({_fmt(l)})" if l else None


def _zoek_bouw(m):
    l = _vector(m.group("l"))
    n = _getal(m.group("n"))
    if not l or n is None:
        return None
    if [float(x) for x in l] != sorted(float(x) for x in l):
        return None                       # binary_search heeft een gesorteerde lijst nodig
    return f"binary_search({_fmt(l)}, {n})"


def _levenshtein_bouw(m):
    return f'levenshtein("{m.group("a")}", "{m.group("b")}")'


_EXTRA = (
    # --- vectoren ---
    (rf"^(?:het |de )?(?:inproduct|scalair product|dotproduct|dot product) (?:van|tussen) (?:de vectoren )?{_vg('a')} (?:en|met) {_vg('b')}$",
     _vec2("dot")),
    (rf"^(?:het |de )?(?:kruisproduct|uitproduct|vectorproduct) (?:van|tussen) (?:de vectoren )?{_vg('a')} (?:en|met) {_vg('b')}$",
     _vec2("cross", lengte=3)),
    (rf"^(?:de )?(?:lengte|norm|grootte) van (?:de |een )?(?:vector )?{_vg('a')}$", _vec1("norm")),
    (rf"^(?:de )?eenheidsvector van (?:de |een )?(?:vector )?{_vg('a')}$", _vec1("unit")),
    (rf"^(?:de )?projectie van (?:de vector )?{_vg('a')} op (?:de vector )?{_vg('b')}$", _vec2("proj")),
    # --- matrices ---
    (rf"^(?:de )?determinant van (?:de |een )?(?:matrix )?{_MG}$", _mat1("det", vierkant=True)),
    (rf"^(?:de )?inverse (?:matrix )?van (?:de |een )?(?:matrix )?{_MG}$", _mat1("inverse", vierkant=True)),
    (rf"^(?:inverteer|bepaal de inverse van) (?:de |een )?(?:matrix )?{_MG}$", _mat1("inverse", vierkant=True)),
    (rf"^(?:de )?(?:getransponeerde|transpose) (?:matrix )?van (?:de |een )?(?:matrix )?{_MG}$", _mat1("transpose")),
    (rf"^(?:transponeer) (?:de |een )?(?:matrix )?{_MG}$", _mat1("transpose")),
    (r"^(?:de )?(?:eenheidsmatrix|identiteitsmatrix) (?:van|met grootte|van grootte|van orde) (?P<n>.+)$",
     _getallen("identity", "n")),
    (r"^(?:de )?(?P<n>\d+) ?[x×] ?(?P=n) (?:eenheidsmatrix|identiteitsmatrix)$", _getallen("identity", "n")),
    (rf"^los (?:het )?(?:matrix)?stelsel {_MG} (?:met|=|en) {_vg('v')} op$", _stelsel_matrix_bouw),
    (r"^(?:de )?(?:rotatiematrix|rotatie) (?:rond|om) (?:de )?(?P<as>[xyz])[- ]?as (?:met |over |van )?(?P<h>.+)$",
     _rotatie_bouw),
    (r"^roteer (?:rond|om) (?:de )?(?P<as>[xyz])[- ]?as (?:met |over |van )?(?P<h>.+)$", _rotatie_bouw),

    # --- fysica ---
    (r"^(?:de )?kracht (?:bij|met|van|voor) (?:een )?massa (?:van )?(?P<m>.+?) en (?:een )?versnelling (?:van )?(?P<a>.+)$",
     _fys_functie("kracht", "m", "a")),
    (r"^(?:de )?(?:kinetische energie|bewegingsenergie) (?:bij|met|van|voor) (?:een )?massa (?:van )?(?P<m>.+?) en (?:een )?snelheid (?:van )?(?P<v>.+)$",
     _fys_functie("energie_kinetisch", "m", "v")),
    (r"^(?:de )?(?:potenti(?:e|ë)le energie|zwaarte-?energie) (?:bij|met|van|voor) (?:een )?massa (?:van )?(?P<m>.+?) en (?:een )?hoogte (?:van )?(?P<h>.+)$",
     _fys_functie("energie_potentieel", "m", "h")),
    (r"^(?:de )?arbeid (?:bij|met|van|voor) (?:een )?kracht (?:van )?(?P<f>.+?) (?:en|over) (?:een )?(?:afstand|verplaatsing)(?: van)? (?P<d>.+)$",
     _fys_functie("arbeid", "f", "d")),
    (r"^(?:de )?snelheid na (?P<t>.+?)(?: (?:seconden|seconde|sec|s))? (?:bij|met|van) (?:een )?beginsnelheid (?:van )?(?P<v>.+?) en (?:een )?versnelling (?:van )?(?P<a>.+)$",
     _fys_functie("snelheid_na", "v", "a", "t")),
    (r"^(?:de )?afstand na (?P<t>.+?)(?: (?:seconden|seconde|sec|s))? (?:bij|met|van) (?:een )?beginsnelheid (?:van )?(?P<v>.+?) en (?:een )?versnelling (?:van )?(?P<a>.+)$",
     _fys_functie("afstand_na", "v", "a", "t")),
    (r"^(?:(?:het|de) [a-z ]+? van )?(?:een )?(?:projectiel|worp|schot|kogel|bal)(?: met| bij| van)? (?:een )?(?:begin)?snelheid(?: van)? (?P<v>.+?) (?:onder|met|bij) (?:een )?hoek(?: van)? (?P<h>.+)$",
     _fys_functie("projectiel", "v", "h")),

    # --- kansen en statistiek ---
    (r"^(?:de )?kans (?:op )?(?:een )?(?:som|worp) (?:van )?(?P<s>.+?) (?:met|bij) (?P<n>.+?) dobbelstenen?$",
     _getallen("kans_dobbelsteen", "n", "s")),
    (r"^(?:de )?kans (?:om|op) (?P<s>.+?) te gooien met (?P<n>.+?) dobbelstenen?$",
     _getallen("kans_dobbelsteen", "n", "s")),
    (r"^(?:de )?kans (?:op )?minstens (?:een|één|1) (?:kaart )?(?:van de )?(?P<g>.+?) (?:gewenste |goede )?kaarten? (?:als|bij|wanneer) (?:ik )?(?P<n>.+?) kaarten (?:trek|trekt|getrokken)?\s*(?:uit|van) (?P<t>.+)$",
     _getallen("kans_kaart", "g", "t", "n")),
    (r"^(?:de )?kans (?:op )?precies (?P<k>.+?) (?:successen|succes|keer|maal) (?:bij|in|na) (?P<n>.+?) (?:pogingen|poging|worpen|keer) (?:en|met|bij) (?:een )?(?:succes)?kans(?: van| per poging)? (?P<p>.+)$",
     _decimaal_functie("binomiaal", "n", "k", "p")),
    (r"^(?:de )?(?:cumulatieve )?normale (?:kans|verdeling) (?:bij|voor|tot|van) (?:z ?=? ?)?(?P<z>.+)$",
     _decimaal_functie("normaal", "z")),
    (rf"^(?:de )?(?P<w>lineaire regressie|regressie|correlatie) (?:van|tussen) {_vg('a')} (?:en|met|tegen) {_vg('b')}$",
     _twee_lijsten_bouw),

    # --- breuken en reeksen ---
    (r"^(?P<e>.+?) (?:als|in) (?:een |exacte )?(?:exacte )?breuk$", _breuk_bouw),
    (r"^(?:de )?(?:som|sigma) van (?P<f>.+?) (?:voor|met) x (?:van|=|loopt van) (?P<a>.+?) (?:tot en met|tot|t/m) (?P<b>.+)$",
     _sigma_bouw),
    (r"^(?:de )?(?:som van een )?meetkundige reeks (?:met )?(?:beginwaarde|eerste term|start)(?: van)? (?P<a>.+?),? (?:factor|rede|verhouding)(?: van)? (?P<r>.+?),? (?:en )?(?P<n>.+?) termen$",
     _decimaal_functie("meetkundige_reeks", "a", "r", "n")),

    # --- formule op een punt, nulpunt zoeken, precisie ---
    (r"^(?:de waarde van )?(?P<f>.+?) (?:voor|bij) x ?(?:=|gelijk aan) ?(?P<p>.+)$", _bereken_in_punt),
    (r"^(?:een |het )?nulpunt van (?P<f>.+?) (?:vanaf|startend bij|met startwaarde|starten bij) (?P<s>.+)$", _nulpunt_bouw),
    (r"^stel (?:de )?precisie in (?:op|naar) (?P<n>.+?)(?: cijfers)?$", _getallen("stel_precisie_in", "n")),
    (r"^(?:reset|herstel) (?:de )?precisie$", lambda m: "reset_precisie()"),
    (r"^rond (?P<n>.+?) af (?:op|tot) (?P<d>.+?) significante cijfers$", _getallen("significante_cijfers", "n", "d")),

    # --- sorteren, zoeken, woorden ---
    (rf"^(?:sorteer|sorteren|orden) (?:de lijst )?{_vg('l')}$", _sorteer_bouw),
    (rf"^(?:de )?(?:positie|plaats|index) van (?P<n>.+?) in (?:de lijst )?{_vg('l')}$", _zoek_bouw),
    (r"^(?:de )?(?:levenshtein|bewerkingsafstand|editafstand)(?:[- ]?afstand)? (?:tussen|van) (?P<a>[a-zà-ÿ]+) en (?P<b>[a-zà-ÿ]+)$",
     _levenshtein_bouw),
)

_SJABLONEN = [(re.compile(p), b) for p, b in (
    # --- vergelijkingen oplossen ---
    (r"^los (?P<a>.+?) en (?P<b>.+?) op$", _stelsel_bouw),
    (r"^los de vergelijking (?P<v>.+?)(?: op)?$", _vergelijk_bouw),
    (r"^los (?P<v>.+?) op$", _vergelijk_bouw),
    (r"^los op (?P<v>.+)$", _vergelijk_bouw),
    (r"^(?:de )?vergelijking (?P<v>.+?) oplossen$", _vergelijk_bouw),
    (rf"^de waarde van {_V},? (?:als|wanneer|indien|waarbij|voor) (?P<v>.+)$", _vergelijk_bouw),
    (rf"^voor welke {_V} geldt (?P<v>.+)$", _vergelijk_bouw),
    (rf"^{_V},? (?:als|wanneer|indien|waarbij) (?P<v>.+)$", _vergelijk_bouw),
    (r"^(?:de )?(?:nulpunten|wortels|oplossingen) van (?P<f>.+)$", _nulpunten_bouw),

    # --- afgeleide en integraal ---
    (r"^(?:de )?afgeleide van (?P<f>.+?) (?:in|bij|voor|op) (?:het punt )?(?:x ?(?:=|gelijk aan) ?)?(?P<p>.+)$",
     _afgeleide_punt),
    (r"^(?:de )?afgeleide van (?P<f>.+)$", _alg("differentiate")),
    (r"^(?:differentieer|differentieren) (?P<f>.+)$", _alg("differentiate")),
    (r"^leid (?P<f>.+) af$", _alg("differentiate")),
    (r"^(?:de )?integraal van (?P<f>.+?) van (?P<a>.+?) tot(?: en met)? (?P<b>.+)$", _integraal_grenzen),
    (r"^(?:de )?integraal van (?P<f>.+?) tussen (?P<a>.+?) en (?P<b>.+)$", _integraal_grenzen),
    (r"^(?:de )?integraal van (?P<f>.+)$", _alg("integrate_sym")),
    (r"^(?:integreer|integreren) (?P<f>.+)$", _alg("integrate_sym")),
    (rf"^(?:de )?limiet van (?P<f>.+?) (?:als |voor |wanneer )?{_V} (?:naar|nadert|gaat naar) (?P<a>.+?)(?: gaat| nadert)?$",
     _limiet_bouw),

    # --- algebra omvormen ---
    (r"^(?:ontbind|ontbinden|factoriseer) (?P<f>.+?)(?: in factoren)?$", _alg("factor_sym")),
    (r"^werk de haakjes (?:uit|weg) (?:van|in|bij) (?P<f>.+)$", _alg("expand_sym")),
    (r"^werk (?P<f>.+) uit$", _alg("expand_sym")),
    (r"^breid (?P<f>.+) uit$", _alg("expand_sym")),
    (r"^(?:vereenvoudig|vereenvoudigen|versimpel) (?P<f>.+)$", _alg("simplify_sym")),

    # --- getaltheorie en combinatoriek ---
    (r"^(?:de )?(?:ggd|grootste gemene (?:deler|factor)) (?:van|tussen) (?P<a>.+?) en (?P<b>.+)$",
     _getallen("ggd", "a", "b")),
    (r"^(?:het )?(?:kgv|kleinste gemene (?:veelvoud|multiple)) (?:van|tussen) (?P<a>.+?) en (?P<b>.+)$",
     _getallen("kgv", "a", "b")),
    (r"^(?:de )?faculteit van (?P<n>.+)$", _getallen("faculteit", "n")),
    (r"^(?P<n>.+?) faculteit$", _getallen("faculteit", "n")),
    (r"^is (?P<n>.+?) (?:een )?priem(?:getal)?$", _getallen("is_priem", "n")),
    (r"^(?:alle )?priemgetallen (?:tot|onder|tot en met|t/m) (?P<n>.+)$", _getallen("priemgetallen", "n")),
    (r"^(?:de )?rest (?:bij (?:de )?deling )?van (?P<a>.+?) (?:gedeeld door|delen door|door) (?P<b>.+)$",
     _getallen("modulo", "a", "b")),
    (r"^(?P<a>.+?) modulo (?P<b>.+)$", _getallen("modulo", "a", "b")),
    (r"^(?:hoeveel )?combinaties (?:van|met) (?P<k>.+?) (?:uit|van de|van) (?P<n>.+)$",
     _getallen("combinaties", "n", "k")),
    (r"^hoeveel manieren (?:zijn er )?om (?P<k>.+?) uit (?P<n>.+?) te kiezen$",
     _getallen("combinaties", "n", "k")),
    (r"^(?:hoeveel )?permutaties (?:van|met) (?P<k>.+?) (?:uit|van de|van) (?P<n>.+)$",
     _getallen("permutaties", "n", "k")),
    (r"^(?:de )?som van (?P<a>.+?) (?:tot en met|tot|t/m) (?P<b>.+)$", _getallen("som_reeks", "a", "b")),

    # --- statistiek ---
    (r"^(?:het |de )?(?P<w>gemiddelde|gemiddeld|mediaan|modus|variantie|standaardafwijking|standaarddeviatie) "
     r"van (?P<lst>.+)$", _lijst_bouw),

    # --- talstelsels ---
    (r"^(?:zet |reken )?(?P<n>.+?) (?:om )?(?:naar|in) (?P<s>binair|octaal|hexadecimaal|hex)(?: getal)?$",
     _naar_stelsel_bouw),
    (r"^(?P<n>[0-9a-f]+) (?:in )?(?P<s>binair|octaal|hexadecimaal|hex) naar (?:decimaal|tientallig)$",
     _uit_stelsel_bouw),

    # --- netjes afronden en absolute waarde ---
    (r"^rond (?P<n>.+?) af (?:op|tot) (?P<d>.+?) (?:decimalen|decimaal|cijfers na de komma)$", _afronden_bouw),
    (r"^(?:de )?absolute waarde van (?P<f>.+)$", _abs_bouw),
) + _EXTRA]


# ---------------------------------------------------------------------
# De functies die de rest van Nova gebruikt
# ---------------------------------------------------------------------
def vertaal_functiezin(tekst):
    """Gewone taal -> math.py-functie-aanroep zoals 'ggd(48, 18)', of None."""
    if not isinstance(tekst, str):
        return None
    t = tekst.lower().strip()
    if not t or len(t) > _MAX_LENGTE:
        return None
    t = _schoon(t)
    if not t:
        return None
    for patroon, bouw in _SJABLONEN:
        m = patroon.match(t)
        if not m:
            continue
        try:
            uit = bouw(m)
        except Exception:
            uit = None
        if uit:
            return uit
    return None


def vertaal_wiskundezin(tekst):
    """Eerst de functie-sjablonen, daarna de gewone rekenzin-parser."""
    return vertaal_functiezin(tekst) or vertaal_rekenzin(tekst)