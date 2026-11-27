# modules/body/kleding_tekst.py
"""Korte tussenstappen bij kleding.

Pure data plus één keuzefunctie: geen logica, geen state, geen events.
`kleding.py` roept kies() aan met een soort en een stuk, en plakt het
resultaat in de beurt. De zone kan de aanroeper achteraf invullen met {z}.

Per soort wordt de laatst gegeven zin onthouden, zodat dezelfde niet twee
keer na elkaar valt. Zelfde patroon als INSTORTING in body_state.py.
"""

import random

LOS = {
    "short": [
        "Knoop los.",
        "Awel.",
        "Trek het maar open.",
        "…ja. Ga je gang.",
        "Toch losser.",
    ],
}

WEIGER = {
    "hoodie": ["Zit nog onder men hoodie.", "Doe eerst men hoodie af."],
    "topje": ["Zit nog onder men topje.", "Doe eerst men topje af."],
    "shirt": ["Zit nog onder men T-shirt.", "Doe eerst men T-shirt af."],
    "short": ["Zit nog aan, hè.", "Short zit nog."],
    "algemeen": ["Eerst de rest.", "In de juiste volgorde, liefst."],
}

UIT = {
    "short": ["…uit dan.", "Weg ermee.", "Awel. Gedaan."],
    "hoodie": ["Uit.", "…weg daarmee.", "Trek het uit."],
    "topje": ["Uit dan.", "…ja. Uit."],
    "shirt": ["Uit.", "…weg.", "Trek maar uit."],
}

AAN = {
    "short": ["Terug aan.", "…aandoen dan."],
    "hoodie": ["Terug aan, zever."],
    "topje": ["Terug aan."],
    "shirt": ["Terug aan.", "…doe maar."],
}

VERSCHOVEN = {
    "short": ["Opzij dan maar.", "…zo.", "Awel, goed.", "Daar."],
    "hoodie": ["Omhoog.", "Wacht, omhoog.", "…tot hier."],
    "topje": ["Omhoog dan.", "…hoger.", "Wacht."],
    "shirt": ["Omhoog.", "…hoger.", "Tot hier."],
}

KOUD = [
    "Koud.",
    "Het is hier koud.",
    "…trek eens.",
    "Doe de deken.",
    "Kippenvel. Zie je dat niet.",
    "Awel, koud hè.",
]

_BAKKEN = {
    "los": LOS,
    "weiger": WEIGER,
    "uit": UIT,
    "aan": AAN,
    "verschoven": VERSCHOVEN,
}

_laatste = {}


def _kies_uit(lijst, sleutel):
    """Kies uit een lijst zonder de vorige van die sleutel te herhalen."""
    if not lijst:
        return ""
    vorige = _laatste.get(sleutel)
    keuzes = [z for z in lijst if z != vorige] or lijst
    zin = random.choice(keuzes)
    _laatste[sleutel] = zin
    return zin


def kies(soort, item=None):
    """Geeft één zin voor dit soort en dit stuk.

    soort: "los", "weiger", "uit", "aan", "verschoven" of "koud".
    Onbekend stuk bij weiger valt terug op "algemeen"; bij de andere
    soorten op een lege string.
    """
    if soort == "koud":
        return _kies_uit(KOUD, "koud")

    bak = _BAKKEN.get(soort, {})
    lijst = bak.get(item)
    if lijst is None and soort == "weiger":
        lijst = WEIGER["algemeen"]
    return _kies_uit(lijst or [], f"{soort}:{item}")