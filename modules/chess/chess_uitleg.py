# modules/chess/chess_uitleg.py
"""
Schaak-doorvragen (punt 79, 10 november 2026): uitleg over zetten, puur symbolisch.

Dit bestand bevat ALLEEN pure functies zonder Stockfish, zonder EventBus en zonder
bestanden: ze krijgen een python-chess bord (of een score) en geven een Nederlandse zin
terug. Daardoor zijn ze zonder engine te testen. chess_engine.py (ChessModule) bewaart de
zetten en roept deze functies aan.

WAT HET IS (eerlijk):
- Feiten uit het bord (slaat een stuk, geeft schaak, rokade, promotie, ontwikkelt een stuk,
  dreigt een stuk te slaan, kon geslagen worden, staat niet gedekt) komen uit python-chess.
- De beste zet, de verwachte reactie en de score komen uit Stockfish (externe, gespecialiseerde
  tool die je al gebruikt; nooit de kern van Nova).
- De zinnen zijn vaste sjablonen. Nova VERZINT geen uitleg: vindt ze geen feit, dan zegt ze
  dat eerlijk (zie de terugvalzinnen in chess_engine.py).
"""
import re

import chess

STUK_NAAM = {
    chess.PAWN: "pion",
    chess.KNIGHT: "paard",
    chess.BISHOP: "loper",
    chess.ROOK: "toren",
    chess.QUEEN: "dame",
    chess.KING: "koning",
}
NAAM_NAAR_STUK = {naam: stuk for stuk, naam in STUK_NAAM.items()}

# Voor "wie wordt er voordeliger geslagen": een koning telt als onbetaalbaar.
STUK_WAARDE = {
    chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
    chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100,
}

# Grenzen (centipawns) voor de stand-beoordeling.
STAND_GELIJK = 30
STAND_IETS = 100
STAND_DUIDELIJK = 300


def _naam(bord, veld):
    return STUK_NAAM.get(bord.piece_type_at(veld), "stuk")


def _lijst_nl(delen):
    """['a'] -> 'a'; ['a','b'] -> 'a en b'; ['a','b','c'] -> 'a, b en c'."""
    delen = [d for d in delen if d]
    if not delen:
        return ""
    if len(delen) == 1:
        return delen[0]
    return ", ".join(delen[:-1]) + " en " + delen[-1]


def _geslagen_veld_en_stuk(bord, zet):
    """(veld, stuktype) van het stuk dat 'zet' wegneemt, of None als het geen slag is.
    Let op en passant: het geslagen pion staat dan niet op het doelveld."""
    if bord.is_en_passant(zet):
        return chess.square(chess.square_file(zet.to_square), chess.square_rank(zet.from_square)), chess.PAWN
    if bord.is_capture(zet):
        return zet.to_square, bord.piece_type_at(zet.to_square)
    return None


# ---------------------------------------------------------------------------
# 1. Feiten over een gespeelde zet (waarom speelde je dat?)
# ---------------------------------------------------------------------------
def feiten_van_zet(bord_voor, zet, door_nova):
    """Geeft een lijst korte werkwoordsdelen over 'zet', gespeeld op 'bord_voor' (de stelling
    VOOR de zet). 'door_nova' bepaalt wie "mijn" en wie "jouw" is.

    Voorbeeld: ["slaat jouw pion op e5", "geeft schaak"].
    Een lege lijst betekent: geen herkenbaar feit gevonden.
    """
    feiten = []
    stuk = bord_voor.piece_at(zet.from_square)
    if stuk is None:
        return feiten
    kleur = stuk.color
    van_tegenstander = "jouw" if door_nova else "mijn"
    eigen = "mijn" if door_nova else "jouw"

    if bord_voor.is_castling(zet):
        feiten.append("is een korte rokade" if bord_voor.is_kingside_castling(zet) else "is een lange rokade")
    else:
        slag = _geslagen_veld_en_stuk(bord_voor, zet)
        if slag is not None:
            veld, soort = slag
            feiten.append(f"slaat {van_tegenstander} {STUK_NAAM.get(soort, 'stuk')} op {chess.square_name(veld)}")

    bord_na = bord_voor.copy(stack=False)
    bord_na.push(zet)

    if zet.promotion:
        feiten.append(f"promoveert tot {STUK_NAAM.get(zet.promotion, 'dame')}")

    if bord_na.is_checkmate():
        feiten.append("zet mat")
    elif bord_na.is_check():
        feiten.append("geeft schaak")

    achterste_rij = 0 if kleur == chess.WHITE else 7
    if (
        stuk.piece_type in (chess.KNIGHT, chess.BISHOP)
        and chess.square_rank(zet.from_square) == achterste_rij
        and chess.square_rank(zet.to_square) != achterste_rij
    ):
        feiten.append(f"ontwikkelt {eigen} {STUK_NAAM[stuk.piece_type]}")

    # Dreiging: het verplaatste stuk valt nu een stuk aan dat niet gedekt staat of meer waard is.
    verplaatst = bord_na.piece_at(zet.to_square)
    if verplaatst is not None and verplaatst.piece_type != chess.KING and not bord_voor.is_castling(zet):
        beste = None
        for veld in bord_na.attacks(zet.to_square):
            doel = bord_na.piece_at(veld)
            if doel is None or doel.color == kleur or doel.piece_type == chess.KING:
                continue
            gedekt = bool(bord_na.attackers(doel.color, veld))
            if (not gedekt) or STUK_WAARDE[doel.piece_type] > STUK_WAARDE[verplaatst.piece_type]:
                if beste is None or STUK_WAARDE[doel.piece_type] > beste[0]:
                    beste = (STUK_WAARDE[doel.piece_type], veld, doel.piece_type)
        if beste is not None:
            feiten.append(f"dreigt {van_tegenstander} {STUK_NAAM[beste[2]]} op {chess.square_name(beste[1])} te slaan")

    return feiten


def zin_over_zet(feiten):
    """['slaat jouw pion op e5', 'geeft schaak'] -> 'Die zet slaat jouw pion op e5 en geeft schaak.'"""
    if not feiten:
        return ""
    return "Die zet " + _lijst_nl(feiten) + "."


# ---------------------------------------------------------------------------
# 2. Wat ging er mis na Kevins zet? (waarom was dat een blunder?)
# ---------------------------------------------------------------------------
def gevaren_na_zet(bord_na, zet, reactie, mat_dreigt=False):
    """Concrete, controleerbare redenen waarom Kevins zet slecht was.

    bord_na   = de stelling direct NA Kevins zet (nog vóór Nova's reactie).
    zet       = Kevins zet.
    reactie   = Stockfish' verwachte beste reactie van Nova op bord_na (of None).
    mat_dreigt = True als Stockfish een mat tegen Kevin ziet.

    Geeft een lijst zinnen. Leeg = geen herkenbaar feit gevonden.
    """
    zinnen = []
    if mat_dreigt:
        zinnen.append("Na die zet kon ik je mat zetten.")

    gebruikt = set()
    stuk = bord_na.piece_at(zet.to_square)
    if stuk is not None and stuk.piece_type != chess.KING:
        aanvallers = bord_na.attackers(not stuk.color, zet.to_square)
        verdedigers = bord_na.attackers(stuk.color, zet.to_square)
        if aanvallers:
            goedkoopste = min(STUK_WAARDE[bord_na.piece_type_at(v)] for v in aanvallers)
            if not verdedigers or goedkoopste < STUK_WAARDE[stuk.piece_type]:
                tekst = f"Je {STUK_NAAM[stuk.piece_type]} op {chess.square_name(zet.to_square)} kon geslagen worden"
                if not verdedigers:
                    tekst += " en stond niet gedekt"
                zinnen.append(tekst + ".")
                gebruikt.add(zet.to_square)

    if reactie is not None:
        try:
            slag = _geslagen_veld_en_stuk(bord_na, reactie)
            if slag is not None and slag[0] not in gebruikt:
                zinnen.append(f"Daarna kon ik je {STUK_NAAM.get(slag[1], 'stuk')} op {chess.square_name(slag[0])} slaan.")
            if bord_na.gives_check(reactie) and not mat_dreigt:
                zinnen.append("Daarna kon ik schaak zetten.")
        except Exception:
            pass

    return zinnen


# ---------------------------------------------------------------------------
# 3. Welke zetten kan ik doen?
# ---------------------------------------------------------------------------
def mogelijke_zetten_tekst(bord, stuk_type=None):
    """Alle legale zetten voor de speler die aan de beurt is, per stuk gegroepeerd.
    Met 'stuk_type' alleen de zetten van dat soort stuk."""
    per_stuk = {}
    for zet in bord.legal_moves:
        stuk = bord.piece_at(zet.from_square)
        if stuk is None:
            continue
        if stuk_type is not None and stuk.piece_type != stuk_type:
            continue
        doel = chess.square_name(zet.to_square)
        if bord.is_capture(zet):
            doel += " (slaat)"
        doelen = per_stuk.setdefault((stuk.piece_type, zet.from_square), [])
        if doel not in doelen:
            doelen.append(doel)

    if not per_stuk:
        if stuk_type is not None:
            return f"Met je {STUK_NAAM[stuk_type]} kun je nu niets doen."
        return "Je hebt geen zetten meer."

    regels = []
    for (soort, van), doelen in sorted(per_stuk.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        regels.append(f"{STUK_NAAM[soort]} {chess.square_name(van)}: {', '.join(doelen)}")

    kop = f"Met je {STUK_NAAM[stuk_type]} kun je:" if stuk_type is not None else "Dit zijn je mogelijke zetten:"
    return kop + "\n" + "\n".join(regels)


# ---------------------------------------------------------------------------
# 4. Wie staat er beter?
# ---------------------------------------------------------------------------
def beoordeel_stand(cp, mat_in=None):
    """cp = centipawns vanuit Kevin (positief = Kevin staat beter). mat_in = aantal zetten tot
    mat (positief: Kevin zet mat, negatief: Nova zet mat), of None."""
    if mat_in is not None:
        n = abs(mat_in)
        zetten = "1 zet" if n == 1 else f"{n} zetten"
        if mat_in > 0:
            return f"Volgens Stockfish zet jij me mat in {zetten}."
        return f"Volgens Stockfish zet ik jou mat in {zetten}."
    if cp is None:
        return ""
    a = abs(cp)
    if a <= STAND_GELIJK:
        return "Het staat ongeveer gelijk."
    wie = "Jij staat" if cp > 0 else "Ik sta"
    if a <= STAND_IETS:
        return f"{wie} iets beter."
    if a <= STAND_DUIDELIJK:
        return f"{wie} duidelijk beter."
    return f"{wie} veel beter."


# ---------------------------------------------------------------------------
# 5. Herkennen van de doorvragen (zinsvormen, geen ML)
# ---------------------------------------------------------------------------
_BESTE_VORIGE = [
    re.compile(r"^wat (was|had) (de|mijn|een) (beste|betere) zet( daar| toen)?$"),
    re.compile(r"^wat had ik (beter )?(moeten|kunnen) (spelen|doen)$"),
]
_BESTE_NU = re.compile(r"^wat is (de|mijn) beste zet( nu)?$")
_BESTE_NU_VAST = {
    "wat zou je spelen", "wat zou jij spelen", "wat zou jij doen", "geef me een tip", "geef een tip",
    "geef me een hint", "geef een hint", "wat raad je aan",
}
_WAAROM_NOVA = re.compile(r"^waarom (speelde|speel|deed|koos) (je|jij) (dat|die zet|dit|die)( dan)?$")
_WAAROM_NOVA_VAST = {"wat was je idee", "wat was jouw idee"}
_MOGELIJK_STUK = re.compile(
    r"^wat kan ik (nu )?(doen|spelen) met (mijn |de |m'n )?(pion|paard|loper|toren|dame|koning)$"
)
_MOGELIJK_VAST = {"mogelijke zetten", "wat kan ik spelen", "wat zijn mijn opties"}
_STAND_VAST = {
    "wie staat er beter", "wie staat beter", "wie heeft de overhand", "wie staat er voor",
    "sta ik voor", "sta ik achter", "hoe sta ik ervoor", "hoe staan we ervoor", "hoe staat het ervoor",
    "wie gaat er winnen", "wie wint er", "wie is er aan de winnende hand",
}
_TERUG_VAST = {
    "en daarvoor", "en daarvoor dan", "en de zet daarvoor", "en de zet ervoor", "en de vorige zet",
    "en de vorige", "en die ervoor", "en die daarvoor",
}
_MIJN_VAST = {"en mijn zet", "en mijn vorige zet", "en die van mij"}
_JOUW_VAST = {"en jouw zet", "en je zet", "en die van jou", "en jouw vorige zet"}


def stuk_uit_tekst(t):
    """Geeft het stuktype dat in de tekst genoemd wordt ("met mijn paard"), of None."""
    for naam, soort in NAAM_NAAR_STUK.items():
        if re.search(rf"\b{naam}\b", t):
            return soort
    return None


def herken_doorvraag(tekst, partij_bezig, cursor_actief):
    """Herkent een schaak-doorvraag. Geeft (soort, extra) of None.

    soort: "beste_zet_vorige", "beste_zet_nu", "waarom_nova", "mogelijke_zetten", "stand",
           "terug", "mijn_zet", "jouw_zet".
    partij_bezig: True als er een partij loopt (anders geen enkele zin hier oppakken, zodat
                  "wie wint er" in gewoon gesprek niet bij schaken terechtkomt).
    cursor_actief: True als Nova net een zet uitlegde (nodig voor "en daarvoor").
    """
    if not partij_bezig:
        return None
    t = re.sub(r"\s+", " ", (tekst or "").lower().strip().rstrip("?.! "))

    if any(p.match(t) for p in _BESTE_VORIGE):
        return "beste_zet_vorige", {}
    if _BESTE_NU.match(t) or t in _BESTE_NU_VAST:
        return "beste_zet_nu", {}
    if _WAAROM_NOVA.match(t) or t in _WAAROM_NOVA_VAST:
        return "waarom_nova", {}
    if t in _STAND_VAST:
        return "stand", {}

    woorden = set(t.split())
    if _MOGELIJK_STUK.match(t):
        return "mogelijke_zetten", {"stuk": stuk_uit_tekst(t)}
    if t in _MOGELIJK_VAST or (
        "zetten" in woorden
        and woorden & {"welke", "mogelijke", "mogelijkheden"}
        and not woorden & {"waarom", "wie", "hoeveel"}
    ):
        return "mogelijke_zetten", {"stuk": stuk_uit_tekst(t)}

    # Ook zonder actieve cursor herkennen: Nova vraagt dan zelf over welke zet het gaat
    # (handle_followup), in plaats van de zin naar de algemene fallback te laten vallen.
    if t in _TERUG_VAST:
        return "terug", {}
    if t in _MIJN_VAST:
        return "mijn_zet", {}
    if t in _JOUW_VAST:
        return "jouw_zet", {}
    return None