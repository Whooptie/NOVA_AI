# core/rekenwoorden.py
#
# Bug #31 + het kleine deel van punt 10 (25 oktober 2026):
# vertaalt een eenvoudige Nederlandse rekenzin naar een kale expressie die
# modules/math/math.py begrijpt.
#
#   "wat is drie plus vijf"           -> "3 + 5"
#   "hoeveel is twintig gedeeld door vier" -> "20 / 4"
#   "bereken 3+5"                     -> "3 + 5"
#   "wat is 9/11"                     -> "9 / 11"
#
# PUUR SYMBOLISCH: een opzoektabel voor getalwoorden en operatiewoorden plus
# een strikte grammatica. Geen ML, geen SymPy, geen gokwerk: lukt het niet
# 100% om de HELE zin te lezen, dan geeft vertaal_rekenzin() None terug en
# loopt de zin gewoon door de normale routing.
#
# Bewust NIET ondersteund (zie nova_state.md, punt 10 "vergelijkingen"):
# haakjes, komma-getallen in woorden ("twee komma vijf"), vergelijkingen
# oplossen, "de som van drie en vijf", wortels in woorden.

import re

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
_INLEIDINGEN = (
    "wat is dan", "wat is", "hoeveel is dan", "hoeveel is", "wat geeft",
    "wat levert", "bereken", "reken uit", "reken eens uit", "rekenen",
)

# Woord-operaties (meerwoordige eerst, anders pakt "gedeeld" het te vroeg).
_WOORD_OPERATIES = (
    ("gedeeld door", "/"),
    ("te delen door", "/"),
    ("delen door", "/"),
    ("tot de macht", "^"),
    ("minus", "-"),
    ("plus", "+"),
    ("maal", "*"),
    ("keer", "*"),
    ("min", "-"),
)

_SYMBOLEN = "+-*/^×÷"


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
    for inl in _INLEIDINGEN:
        if t == inl:
            return "", True
        if t.startswith(inl + " "):
            return t[len(inl) + 1:].strip(), True
    return t, False


def vertaal_rekenzin(tekst):
    """
    Geeft een kale expressie zoals '3 + 5' terug, of None.

    Regels (alles of niets):
      - de HELE zin moet een rekensom zijn: [inleiding] term (operatie term)+
      - een term is een getal in cijfers ('3', '2,5') of in woorden ('drie')
      - minstens één operatie
      - zonder inleiding en met enkel symbolen ('3+5') geven we None: dat
        pad werkt al en blijft ongewijzigd
    """
    if not isinstance(tekst, str):
        return None
    t = tekst.lower().strip().rstrip("?!. ").strip()
    if not t:
        return None

    t, had_inleiding = _strip_inleiding(t)
    if not t:
        return None

    # "3 x 4" / "3×4" met cijfers aan beide kanten -> maal
    t = re.sub(r"(?<=\d)\s*[x×]\s*(?=\d)", " * ", t)
    t = t.replace("÷", " / ")

    heeft_woordoperatie = False
    for woord, symbool in _WOORD_OPERATIES:
        patroon = rf"(?<![a-zà-ÿ]){re.escape(woord)}(?![a-zà-ÿ])"
        if re.search(patroon, t):
            heeft_woordoperatie = True
            t = re.sub(patroon, f" {symbool} ", t)

    if not heeft_woordoperatie and not had_inleiding:
        return None   # kale '3+5': bestaand pad, niet aanraken

    # spaties rond symbolen, zodat '3+5' en '9/11' ook tokens worden
    t = re.sub(r"([+\-*/^])", r" \1 ", t)
    tokens = t.split()
    if not tokens:
        return None

    termen = []        # lijst van strings ('3', '2.5')
    operaties = []
    wacht_woorden = []  # opeenvolgende getalwoorden, samen één getal

    def sluit_woorden():
        if not wacht_woorden:
            return True
        waarde = getalwoord_naar_int("".join(wacht_woorden))
        wacht_woorden.clear()
        if waarde is None:
            return False
        termen.append(str(waarde))
        return True

    verwacht_term = True
    for tok in tokens:
        if tok in _SYMBOLEN and len(tok) == 1:
            if verwacht_term and not wacht_woorden:
                return None            # twee operaties na elkaar / begint met operatie
            if not sluit_woorden():
                return None
            operaties.append("*" if tok == "×" else tok)
            verwacht_term = True
        elif re.fullmatch(r"\d+([.,]\d+)?", tok):
            if wacht_woorden or not verwacht_term:
                return None
            termen.append(tok.replace(",", "."))
            verwacht_term = False
        elif tok.isalpha():
            if not verwacht_term and not wacht_woorden:
                return None
            wacht_woorden.append(tok)
            verwacht_term = False
        else:
            return None

    if not sluit_woorden():
        return None
    if verwacht_term:                    # eindigt op een operatie
        return None
    if not operaties or len(termen) != len(operaties) + 1:
        return None

    delen = [termen[0]]
    for op, term in zip(operaties, termen[1:]):
        delen.extend([op, term])
    return " ".join(delen)