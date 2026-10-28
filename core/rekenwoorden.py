# core/rekenwoorden.py
#
# Bug #31 + punt 10 (25 oktober 2026), uitgebreid op 28 oktober 2026:
# vertaalt een Nederlandse rekenzin naar een kale expressie die
# modules/math/math.py begrijpt.
#
#   "wat is drie plus vijf"                  -> "3 + 5"
#   "hoeveel is twintig gedeeld door vier"   -> "20 / 4"
#   "wat is de som van drie en vijf"         -> "3 + 5"
#   "wat is twee maal de som van drie en vijf" -> "2 * (3 + 5)"
#   "wat is twee komma vijf plus een"        -> "2.5 + 1"
#   "wat is twintig procent van tachtig"     -> "20 * 80 / 100"
#   "bereken (3+5)*2"                        -> "(3 + 5) * 2"
#
# PUUR SYMBOLISCH: opzoektabellen + een kleine, handgeschreven grammatica
# (tokenizer + parser). Geen ML, geen SymPy, geen gokwerk. Lukt het niet
# 100% om de HELE zin te lezen, of is de zin dubbelzinnig, dan geeft
# vertaal_rekenzin() None terug en loopt de zin gewoon door de normale
# routing.
#
# Bewust NIET ondersteund (nog):
#   - negatieve getallen / een minteken vooraan ("-3 plus 5")
#   - vergelijkingen oplossen ("zoek x als ...")
#   - een mix van cijfers en woorden in een komma-getal ("twee komma 5")
#   - dubbelzinnige zinnen zoals "de helft van twintig plus vier": gebruik
#     haakjes, dan is het wel duidelijk.

import re

# Naam van de wortelfunctie in math.py. Staat de wortel bij jou onder een
# andere naam, pas dan enkel deze ene regel aan.
WORTEL_FUNCTIE = "sqrt"

_MAX_LENGTE = 200

_EENHEDEN = {
    "nul": 0, "een": 1, "twee": 2, "drie": 3, "vier": 4,
    "vijf": 5, "zes": 6, "zeven": 7, "acht": 8, "negen": 9,
}
_TIENTALLEN_TOT_20 = {
    "tien": 10, "elf": 11, "twaalf": 12, "dertien": 13, "veertien": 14,
    "vijftien": 15, "zestien": 16, "zeventien": 17, "achttien": 18,
    "negentien": 19,
}
_TIENTALLEN = {
    "twintig": 20, "dertig": 30, "veertig": 40, "vijftig": 50,
    "zestig": 60, "zeventig": 70, "tachtig": 80, "negentig": 90,
}

# Inleidingen die een rekenvraag kan hebben (alleen aan het BEGIN van de zin).
# De langste worden eerst geprobeerd (zie _strip_inleiding).
_INLEIDINGEN = (
    "wat is de uitkomst van", "wat is het resultaat van",
    "wat is dan", "wat is", "hoeveel is dan", "hoeveel is", "wat geeft",
    "wat levert", "bereken", "reken uit", "reken eens uit", "rekenen",
)


def _normaliseer(woord):
    return (woord.replace("ë", "e").replace("é", "e").replace("ï", "i")
                 .replace("ö", "o").replace("ü", "u"))


def _tot_100(s):
    """Getalwoord tot 99, bv. 'zeventien', 'dertig', 'tweeentwintig'."""
    if s in _EENHEDEN:
        return _EENHEDEN[s]
    if s in _TIENTALLEN_TOT_20:
        return _TIENTALLEN_TOT_20[s]
    if s in _TIENTALLEN:
        return _TIENTALLEN[s]
    # samengesteld: eenheid + "en" + tiental (tweeentwintig, eenendertig)
    for tiental, waarde in _TIENTALLEN.items():
        if s.endswith(tiental):
            voor = s[: -len(tiental)]
            if voor.endswith("en"):
                eenheid = voor[:-2]
                if eenheid in _EENHEDEN and _EENHEDEN[eenheid] > 0:
                    return waarde + _EENHEDEN[eenheid]
    return None


def _tot_1000(s):
    if s == "":
        return 0
    if "honderd" in s:
        links, rechts = s.split("honderd", 1)
        if links == "":
            honderdtallen = 1
        else:
            honderdtallen = _EENHEDEN.get(links)
            if not honderdtallen:      # None of 0
                return None
        rest = _tot_100(rechts) if rechts else 0
        if rest is None:
            return None
        return honderdtallen * 100 + rest
    return _tot_100(s)


def getalwoord_naar_int(woord):
    """'drie' -> 3, 'tweeëntwintig' -> 22, 'honderdvijf' -> 105,
    'tweeduizend vijfhonderd' (aan elkaar geschreven) -> 2500.
    None als het geen (geldig) getalwoord is. Bereik: 0 t/m 999.999."""
    s = _normaliseer((woord or "").lower().strip())
    if not s or not s.isalpha():
        return None
    if "duizend" in s:
        links, rechts = s.split("duizend", 1)
        if links == "":
            duizendtallen = 1
        else:
            duizendtallen = _tot_1000(links)
            if not duizendtallen:
                return None
        rest = _tot_1000(rechts) if rechts else 0
        if rest is None:
            return None
        return duizendtallen * 1000 + rest
    return _tot_1000(s)


def _strip_inleiding(t):
    """(zonder_inleiding, had_inleiding)."""
    for inl in sorted(_INLEIDINGEN, key=len, reverse=True):
        if t == inl:
            return "", True
        if t.startswith(inl + " "):
            return t[len(inl) + 1:].strip(), True
    return t, False


# ---------------------------------------------------------------------
# Stap 1: de zin in stukjes knippen (tokenizer)
# ---------------------------------------------------------------------
# Een stukje is ("NUM"|"WORD"|"SYM", tekst, komt_uit_woord).
# De letterklasse sluit het deelteken (U+00F7) bewust uit.
_TOKEN_RE = re.compile(r"\d+(?:[.,]\d+)?|[a-zà-öø-ÿ]+|[+\-*/^()%,]")


def _tokeniseer(t):
    """Knipt de zin in stukjes. None als er een onbekend teken in zit."""
    tokens = []
    pos = 0
    for m in _TOKEN_RE.finditer(t):
        if t[pos:m.start()].strip():
            return None                       # onbekend teken ertussen
        stuk = m.group(0)
        if stuk[0].isdigit():
            tokens.append(("NUM", stuk.replace(",", "."), False))
        elif stuk[0].isalpha():
            tokens.append(("WORD", _normaliseer(stuk), True))
        else:
            tokens.append(("SYM", stuk, False))
        pos = m.end()
    if t[pos:].strip():
        return None
    return tokens


def _voeg_komma_getallen_samen(tokens):
    """'2 komma 5' (cijfers) -> 2.5."""
    uit = []
    i = 0
    while i < len(tokens):
        if (i + 2 < len(tokens)
                and tokens[i][0] == "NUM" and "." not in tokens[i][1]
                and tokens[i + 1][:2] == ("WORD", "komma")
                and tokens[i + 2][0] == "NUM" and "." not in tokens[i + 2][1]):
            uit.append(("NUM", tokens[i][1] + "." + tokens[i + 2][1], True))
            i += 3
        else:
            uit.append(tokens[i])
            i += 1
    return uit


# ---------------------------------------------------------------------
# Stap 2: woorden en woordgroepen omzetten naar vaste bouwstenen
# ---------------------------------------------------------------------
_FRASEN = {
    # bewerkingen
    ("plus",): ("PLUS", None),
    ("min",): ("MIN", None),
    ("minus",): ("MIN", None),
    ("maal",): ("MUL", None),
    ("keer",): ("MUL", None),
    ("gedeeld", "door"): ("DIV", None),
    ("te", "delen", "door"): ("DIV", None),
    ("delen", "door"): ("DIV", None),
    ("tot", "de", "macht"): ("POW", None),
    # machten die achter een getal komen
    ("kwadraat",): ("POST", 2),
    ("tot", "de", "tweede", "macht"): ("POST", 2),
    ("tot", "de", "derde", "macht"): ("POST", 3),
    ("tot", "de", "vierde", "macht"): ("POST", 4),
    # structuurwoorden
    ("en",): ("EN", None),
    ("procent", "van"): ("PERCENT", None),
    ("%", "van"): ("PERCENT", None),
    ("de", "som", "van"): ("SOM", None),
    ("som", "van"): ("SOM", None),
    ("het", "product", "van"): ("PRODUCT", None),
    ("product", "van"): ("PRODUCT", None),
    ("het", "verschil", "tussen"): ("VERSCHIL", None),
    ("het", "verschil", "van"): ("VERSCHIL", None),
    ("verschil", "tussen"): ("VERSCHIL", None),
    ("het", "quotient", "van"): ("QUOTIENT", None),
    ("quotient", "van"): ("QUOTIENT", None),
    ("het", "kwadraat", "van"): ("SQOF", 2),
    ("kwadraat", "van"): ("SQOF", 2),
    ("de", "tweede", "macht", "van"): ("SQOF", 2),
    ("de", "derde", "macht", "van"): ("SQOF", 3),
    ("de", "helft", "van"): ("HALF", None),
    ("helft", "van"): ("HALF", None),
    ("het", "dubbele", "van"): ("DOUBLE", None),
    ("dubbele", "van"): ("DOUBLE", None),
    ("de", "wortel", "van"): ("ROOT", None),
    ("wortel", "van"): ("ROOT", None),
    # haakjes in woorden
    ("haakje", "openen"): ("LP", None),
    ("haakjes", "openen"): ("LP", None),
    ("haakje", "sluiten"): ("RP", None),
    ("haakjes", "sluiten"): ("RP", None),
}
_MAX_FRAAS = max(len(k) for k in _FRASEN)

_SYMBOLEN = {
    "+": "PLUS", "-": "MIN", "*": "MUL", "/": "DIV", "^": "POW",
    "(": "LP", ")": "RP", ",": "COMMA",
}

_CIJFERWOORDEN = {
    "nul": "0", "een": "1", "twee": "2", "drie": "3", "vier": "4",
    "vijf": "5", "zes": "6", "zeven": "7", "acht": "8", "negen": "9",
}


def _zoek_frase(raw, i):
    """(lengte, (soort, waarde)) van de langste woordgroep op plek i, of None."""
    for lengte in range(_MAX_FRAAS, 0, -1):
        stuk = raw[i:i + lengte]
        if len(stuk) < lengte:
            continue
        if any(soort == "NUM" for soort, _, _ in stuk):
            continue
        sleutel = tuple(tekst for _, tekst, _ in stuk)
        if sleutel in _FRASEN:
            return lengte, _FRASEN[sleutel]
    return None


def _run_naar_getal(woorden):
    """['tweeentwintig'] -> '22', ['twee','komma','vijf'] -> '2.5'. None bij fout."""
    if "komma" in woorden:
        if woorden.count("komma") != 1:
            return None
        k = woorden.index("komma")
        links, rechts = woorden[:k], woorden[k + 1:]
        if not links or not rechts:
            return None
        hele = getalwoord_naar_int("".join(links))
        if hele is None:
            return None
        cijfers = ""
        for w in rechts:
            if w not in _CIJFERWOORDEN:
                return None
            cijfers += _CIJFERWOORDEN[w]
        return f"{hele}.{cijfers}"
    waarde = getalwoord_naar_int("".join(woorden))
    return None if waarde is None else str(waarde)


def _bouw_tokens(raw):
    """Zet de ruwe stukjes om naar (soort, waarde, uit_woord). None bij fout."""
    uit = []
    i = 0
    while i < len(raw):
        soort, tekst, uit_woord = raw[i]
        if soort == "NUM":
            uit.append(("NUM", tekst, uit_woord))
            i += 1
            continue

        gevonden = _zoek_frase(raw, i)
        if gevonden:
            lengte, (naam, waarde) = gevonden
            uit.append((naam, waarde, soort == "WORD" or lengte > 1))
            i += lengte
            continue

        if soort == "SYM":
            naam = _SYMBOLEN.get(tekst)
            if naam is None:
                return None                   # bv. een los %-teken
            uit.append((naam, None, False))
            i += 1
            continue

        # losse woorden bij elkaar nemen: samen vormen ze één getal
        j = i
        while j < len(raw) and raw[j][0] == "WORD" and _zoek_frase(raw, j) is None:
            j += 1
        getal = _run_naar_getal([raw[x][1] for x in range(i, j)])
        if getal is None:
            return None
        uit.append(("NUM", getal, True))
        i = j
    return uit


# ---------------------------------------------------------------------
# Stap 3: de parser (leest de bouwstenen en maakt er een boom van)
# ---------------------------------------------------------------------
class _Fout(Exception):
    """De zin past niet in de grammatica, of is dubbelzinnig."""


class _Parser:
    # Staat een van deze achter een "simpel" onderdeel, dan is de zin
    # dubbelzinnig ("de helft van twintig plus vier"): liever niets doen.
    _OPERATOREN = ("PLUS", "MIN", "MUL", "DIV", "POW", "POST", "PERCENT")

    def __init__(self, tokens):
        self.t = tokens
        self.i = 0

    def kijk(self):
        return self.t[self.i][0] if self.i < len(self.t) else "EIND"

    def neem(self):
        tok = self.t[self.i]
        self.i += 1
        return tok

    def verwacht(self, soort):
        if self.kijk() != soort:
            raise _Fout(f"verwachtte {soort}")
        return self.neem()

    # optellen en aftrekken (zwakste binding)
    def expr(self):
        links = self.term()
        while self.kijk() in ("PLUS", "MIN"):
            op = "+" if self.neem()[0] == "PLUS" else "-"
            rechts = self.term()
            links = ("BIN", op, links, rechts)
        return links

    # maal en delen
    def term(self):
        links = self.macht()
        while self.kijk() in ("MUL", "DIV"):
            op = "*" if self.neem()[0] == "MUL" else "/"
            rechts = self.macht()
            links = ("BIN", op, links, rechts)
        return links

    # machten (sterkste binding, rechts-associatief)
    def macht(self):
        basis = self.atoom()
        while self.kijk() == "POST":
            basis = ("BIN", "^", basis, ("NUM", str(self.neem()[1])))
        if self.kijk() == "POW":
            self.neem()
            exponent = self.macht()
            return ("BIN", "^", basis, exponent)
        return basis

    def atoom(self):
        knoop = self.kern()
        if self.kijk() == "PERCENT":
            self.neem()
            deel = self.enkelvoudig()
            knoop = ("BIN", "/", ("BIN", "*", knoop, deel), ("NUM", "100"))
        return knoop

    def enkelvoudig(self):
        """Eén onderdeel zonder bewerking erachter (anders: dubbelzinnig)."""
        knoop = self.kern()
        if self.kijk() in self._OPERATOREN:
            raise _Fout("dubbelzinnig")
        return knoop

    def lijst(self, exact=None):
        """'A en B (en C)': minstens 2 onderdelen, gescheiden door 'en' of komma."""
        onderdelen = [self.enkelvoudig()]
        while self.kijk() in ("EN", "COMMA"):
            self.neem()
            onderdelen.append(self.enkelvoudig())
        if len(onderdelen) < 2:
            raise _Fout("te weinig onderdelen")
        if exact is not None and len(onderdelen) != exact:
            raise _Fout("verkeerd aantal onderdelen")
        return onderdelen

    def kern(self):
        soort = self.kijk()
        if soort == "NUM":
            return ("NUM", self.neem()[1])
        if soort == "LP":
            self.neem()
            knoop = self.expr()
            self.verwacht("RP")
            return knoop
        if soort in ("SOM", "PRODUCT"):
            self.neem()
            op = "+" if soort == "SOM" else "*"
            onderdelen = self.lijst()
            knoop = onderdelen[0]
            for volgend in onderdelen[1:]:
                knoop = ("BIN", op, knoop, volgend)
            return knoop
        if soort == "VERSCHIL":
            self.neem()
            a, b = self.lijst(exact=2)
            return ("FUNC", "abs", ("BIN", "-", a, b))
        if soort == "QUOTIENT":
            self.neem()
            a, b = self.lijst(exact=2)
            return ("BIN", "/", a, b)
        if soort == "HALF":
            self.neem()
            return ("BIN", "/", self.enkelvoudig(), ("NUM", "2"))
        if soort == "DOUBLE":
            self.neem()
            return ("BIN", "*", self.enkelvoudig(), ("NUM", "2"))
        if soort == "ROOT":
            self.neem()
            return ("FUNC", WORTEL_FUNCTIE, self.enkelvoudig())
        if soort == "SQOF":
            macht = self.neem()[1]
            return ("BIN", "^", self.enkelvoudig(), ("NUM", str(macht)))
        raise _Fout(f"onverwacht: {soort}")


# ---------------------------------------------------------------------
# Stap 4: de boom weer als tekst opschrijven (met haakjes waar nodig)
# ---------------------------------------------------------------------
_PREC = {"+": 1, "-": 1, "*": 2, "/": 2, "^": 3}


def _prec(knoop):
    return _PREC[knoop[1]] if knoop[0] == "BIN" else 9


def _zet_om(knoop):
    soort = knoop[0]
    if soort == "NUM":
        return knoop[1]
    if soort == "FUNC":
        return f"{knoop[1]}({_zet_om(knoop[2])})"
    _, op, links, rechts = knoop
    p = _PREC[op]
    ls = _zet_om(links)
    rs = _zet_om(rechts)
    if _prec(links) < p or (op == "^" and _prec(links) == p):
        ls = f"({ls})"
    if _prec(rechts) < p or (_prec(rechts) == p and op in ("-", "/")):
        rs = f"({rs})"
    return f"{ls} {op} {rs}"


# ---------------------------------------------------------------------
# De functie die de rest van Nova gebruikt
# ---------------------------------------------------------------------
def vertaal_rekenzin(tekst):
    """
    Geeft een kale expressie zoals '3 + 5' terug, of None.

    Regels (alles of niets):
      - de HELE zin moet een rekensom zijn: [inleiding] som
      - minstens één bewerking (een los getal is geen som)
      - zonder inleiding en zonder woorden ('3+5', '(3+5)*2') geven we None:
        dat pad werkt al en blijft ongewijzigd
      - dubbelzinnige zinnen geven None
    """
    if not isinstance(tekst, str):
        return None
    t = tekst.lower().strip().rstrip("?!. ").strip()
    if not t or len(t) > _MAX_LENGTE:
        return None

    t, had_inleiding = _strip_inleiding(t)
    if not t:
        return None

    t = t.replace("÷", " / ").replace("×", " * ")
    # "3 x 4" met cijfers aan beide kanten -> maal
    t = re.sub(r"(?<=\d)\s*x\s*(?=\d)", " * ", t)

    raw = _tokeniseer(t)
    if raw is None:
        return None
    raw = _voeg_komma_getallen_samen(raw)
    tokens = _bouw_tokens(raw)
    if not tokens:
        return None

    if not had_inleiding and not any(uit_woord for _, _, uit_woord in tokens):
        return None   # kale '3+5': bestaand pad, niet aanraken

    try:
        parser = _Parser(tokens)
        knoop = parser.expr()
        if parser.i != len(tokens):
            return None
    except (_Fout, IndexError, RecursionError):
        return None

    if knoop[0] == "NUM":
        return None
    return _zet_om(knoop)