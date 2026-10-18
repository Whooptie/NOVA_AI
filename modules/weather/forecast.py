# modules/weather/forecast.py
"""
Weer per dag, tot 16 dagen vooruit, en de ochtendsamenvatting.

Dit bestand bevat alleen "pure" hulpfuncties: ze krijgen gegevens binnen
(het antwoord van Open-Meteo) en geven tekst terug. Ze halen zelf niets op
en schrijven niets weg. Het ophalen en het versturen doet weather.py.
Dat maakt alles makkelijk te testen zonder internet.

Er staat bewust GEEN init_module() in: dit is geen module die Nova zelf
laadt, maar een hulpbestand dat weather.py importeert (zelfde idee als
modules/paths.py).

Puur symbolisch: vaste regels en vaste zinsjablonen, geen ML of LLM. De
voorspelling zelf komt van een weermodel (Open-Meteo); wij zetten alleen
getallen om in Nederlandse zinnen.

Eerlijke beperking: hoe verder vooruit, hoe onzekerder een weervoorspelling.
Daarom zegt Nova er vanaf 5 dagen vooruit bij hoe zeker het is
(zie onzekerheid_tekst()).
"""

from collections import namedtuple
from datetime import date, datetime

from modules.weather.rain import (
    ONWEER_CODES,
    SNEEUW_CODES,
    VLAAG_DREMPEL_MS,
    WIND_DREMPEL_MS,
    nu_lokaal,
)

# -----------------------------------------------------
# Instellingen (hier kan je zelf aan draaien)
# -----------------------------------------------------
# Open-Meteo geeft 16 dagen: vandaag + 15 erna.
MAX_DAGEN_VOORUIT = 15

# Zelfde hittedrempel als weather.py (Kevin's keuze: 27 graden).
HITTE_DREMPEL_C = 27

# Ochtendsamenvatting: tussen deze uren (lokale tijd) mag ze komen.
# Komt Kevin pas om 12:00 of later, dan slaat Nova de samenvatting over:
# "goedemorgen" zeggen in de middag klopt niet.
OCHTEND_VAN_UUR = 6
OCHTEND_TOT_UUR = 12
# Lukte het ophalen niet, wacht dan minstens zo lang voor de volgende poging.
OCHTEND_MIN_TUSSENPOGING_MIN = 15
# Pas als de regenkans in een uur minstens zo hoog is, noemt Nova dat uur.
OCHTEND_REGEN_DREMPEL_PCT = 40
# Voor het kledingadvies kijken we naar de gevoelstemperatuur overdag.
OCHTEND_KLEDING_UREN = (8, 18)

OCHTEND_OPENINGEN = [
    "Goedemorgen Kevin!",
    "Goeiemorgen Kevin!",
    "Goedemorgen, Kevin. Even het weer voor vandaag:",
]

# Cijferwoorden voor "over twee weken", "over drie dagen", ...
GETALWOORDEN = {
    "een": 1, "twee": 2, "drie": 3, "vier": 4, "vijf": 5, "zes": 6,
    "zeven": 7, "acht": 8, "negen": 9, "tien": 10, "elf": 11,
    "twaalf": 12, "dertien": 13, "veertien": 14, "vijftien": 15,
}

WEEKDAG_NAMEN = [
    "maandag", "dinsdag", "woensdag", "donderdag",
    "vrijdag", "zaterdag", "zondag",
]

# Eén aanvraag voor 16 dagen. Alle velden zijn op 18 oktober 2026 door Kevin
# getest. Let op: Open-Meteo weigert de HELE aanvraag als er één veldnaam
# niet klopt, dus pas hier niets aan zonder het eerst te testen.
OPEN_METEO_DAG_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={lat:.4f}&longitude={lon:.4f}"
    "&daily=weather_code,temperature_2m_max,temperature_2m_min,"
    "precipitation_probability_max,precipitation_sum,"
    "wind_speed_10m_max,wind_gusts_10m_max"
    "&forecast_days=16&wind_speed_unit=ms&timezone=Europe%2FBrussels"
)

# Voor de ochtendsamenvatting: vandaag per dag én per uur.
OPEN_METEO_OCHTEND_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={lat:.4f}&longitude={lon:.4f}"
    "&daily=weather_code,temperature_2m_max,temperature_2m_min,"
    "precipitation_probability_max,precipitation_sum,"
    "wind_speed_10m_max,wind_gusts_10m_max"
    "&hourly=temperature_2m,apparent_temperature,"
    "precipitation_probability,weather_code"
    "&forecast_days=1&wind_speed_unit=ms&timezone=Europe%2FBrussels"
)

# WMO-weercodes zoals Open-Meteo ze geeft, in woorden die na "met" passen:
# "tussen 6°C en 11°C met matige regen".
WMO_BESCHRIJVING = {
    0: "een heldere hemel",
    1: "overwegend heldere lucht",
    2: "wisselende bewolking",
    3: "een bewolkte lucht",
    45: "mist",
    48: "rijpmist",
    51: "lichte motregen",
    53: "motregen",
    55: "dichte motregen",
    56: "lichte ijzelmotregen",
    57: "ijzelmotregen",
    61: "lichte regen",
    63: "matige regen",
    65: "zware regen",
    66: "lichte ijzelregen",
    67: "zware ijzelregen",
    71: "lichte sneeuw",
    73: "matige sneeuw",
    75: "zware sneeuw",
    77: "sneeuwkorrels",
    80: "lichte regenbuien",
    81: "matige regenbuien",
    82: "hevige regenbuien",
    85: "lichte sneeuwbuien",
    86: "zware sneeuwbuien",
    95: "onweer",
    96: "onweer met lichte hagel",
    99: "onweer met zware hagel",
}

HAGEL_CODES = (96, 99)
MIST_CODES = (45, 48)
IJZEL_CODES = (56, 57, 66, 67)

# Eén dag uit de dagvoorspelling.
Dag = namedtuple(
    "Dag",
    ["datum", "code", "tmax", "tmin", "regenkans", "neerslag", "wind", "vlagen"],
)
# Één uur uit de uurvoorspelling (voor de ochtendsamenvatting).
Uur = namedtuple("Uur", ["tijd", "temp", "gevoel", "regenkans", "code"])


# -----------------------------------------------------
# Tijd
# -----------------------------------------------------
def vandaag_lokaal():
    """De datum van vandaag in Belgische tijd (zie rain.nu_lokaal())."""
    return nu_lokaal().date()


def is_ochtend(nu):
    """True tussen OCHTEND_VAN_UUR en OCHTEND_TOT_UUR."""
    return OCHTEND_VAN_UUR <= nu.hour < OCHTEND_TOT_UUR


# -----------------------------------------------------
# Data inlezen
# -----------------------------------------------------
def _blok(data, naam):
    """Geeft (blok, tijden) uit het Open-Meteo-antwoord, of (None, None)."""
    try:
        blok = data[naam]
        tijden = blok["time"]
    except (KeyError, TypeError):
        return None, None
    if not isinstance(blok, dict) or not isinstance(tijden, list):
        return None, None
    return blok, tijden


def _lijst(blok, naam):
    waarden = blok.get(naam)
    return waarden if isinstance(waarden, list) else []


def _pak(waarden, i):
    return waarden[i] if i < len(waarden) else None


def parse_dagen(data):
    """Zet het 'daily'-deel van het Open-Meteo-antwoord om in Dag-objecten.
    Ontbrekende velden worden None; rommel geeft []."""
    blok, tijden = _blok(data, "daily")
    if blok is None:
        return []

    code = _lijst(blok, "weather_code")
    tmax = _lijst(blok, "temperature_2m_max")
    tmin = _lijst(blok, "temperature_2m_min")
    kans = _lijst(blok, "precipitation_probability_max")
    neerslag = _lijst(blok, "precipitation_sum")
    wind = _lijst(blok, "wind_speed_10m_max")
    vlagen = _lijst(blok, "wind_gusts_10m_max")

    dagen = []
    for i, datum_txt in enumerate(tijden):
        try:
            datum = date.fromisoformat(datum_txt)
        except (ValueError, TypeError):
            continue
        dagen.append(Dag(
            datum, _pak(code, i), _pak(tmax, i), _pak(tmin, i),
            _pak(kans, i), _pak(neerslag, i), _pak(wind, i), _pak(vlagen, i),
        ))
    return dagen


def parse_uren(data):
    """Zet het 'hourly'-deel om in Uur-objecten. Rommel geeft []."""
    blok, tijden = _blok(data, "hourly")
    if blok is None:
        return []

    temp = _lijst(blok, "temperature_2m")
    gevoel = _lijst(blok, "apparent_temperature")
    kans = _lijst(blok, "precipitation_probability")
    code = _lijst(blok, "weather_code")

    uren = []
    for i, tijd_txt in enumerate(tijden):
        try:
            tijd = datetime.fromisoformat(tijd_txt)
        except (ValueError, TypeError):
            continue
        uren.append(Uur(
            tijd, _pak(temp, i), _pak(gevoel, i), _pak(kans, i), _pak(code, i),
        ))
    return uren


# -----------------------------------------------------
# Zinnen
# -----------------------------------------------------
def graden(waarde):
    """12.6 -> '13°C'. (int(round(-0.4)) is 0, dus nooit '-0°C'.)"""
    return f"{int(round(waarde))}°C"


def beschrijving(code):
    """Weercode -> woorden, of None bij een onbekende code."""
    return WMO_BESCHRIJVING.get(code)


def dag_label(datum, vandaag):
    """'Morgen', 'Overmorgen' of 'Op zaterdag 24/10'."""
    verschil = (datum - vandaag).days
    if verschil == 0:
        return "Vandaag"
    if verschil == 1:
        return "Morgen"
    if verschil == 2:
        return "Overmorgen"
    return f"Op {WEEKDAG_NAMEN[datum.weekday()]} {datum.strftime('%d/%m')}"


def onzekerheid_tekst(dagen_vooruit):
    """Hoe verder vooruit, hoe onzekerder. Tot 4 dagen zegt Nova er niets bij
    (daar gebruikt weather.py de gewone voorspelling). Er staan bewust geen
    percentages in: die zou ik moeten verzinnen."""
    if dagen_vooruit <= 4:
        return None
    if dagen_vooruit <= 7:
        return (
            "Kanttekening: dit is een verwachting van een weermodel op meerdere "
            "dagen vooruit. De grote lijn klopt meestal, maar de details kunnen "
            "nog verschuiven."
        )
    if dagen_vooruit <= 10:
        return (
            "Kanttekening: dit ligt al ver weg. Zie het als een trend, "
            "niet als een zekerheid."
        )
    return (
        "Kanttekening: dit ligt heel ver weg. De onzekerheid is groot en de "
        "voorspelling kan nog sterk veranderen."
    )


def _hoofdzin(dag, stad, label):
    """'Morgen wordt het in Aartrijke tussen 6°C en 13°C met matige regen.'
    Geeft None als er helemaal geen temperatuur is."""
    if dag.tmax is None and dag.tmin is None:
        return None

    if dag.tmax is not None and dag.tmin is not None and graden(dag.tmax) != graden(dag.tmin):
        zin = f"{label} wordt het in {stad} tussen {graden(dag.tmin)} en {graden(dag.tmax)}"
    else:
        rond = dag.tmax if dag.tmax is not None else dag.tmin
        zin = f"{label} wordt het in {stad} rond {graden(rond)}"

    tekst = beschrijving(dag.code)
    if tekst:
        zin += f" met {tekst}"
    return zin + "."


def _regenkans_zin(dag):
    if dag.regenkans is None:
        return None
    return f"Regenkans: {int(round(dag.regenkans))}%."


def _wind_zin(dag):
    if dag.wind is None:
        return None
    zin = f"Wind: tot {int(round(dag.wind))} m/s"
    if dag.vlagen is not None:
        zin += f" (windstoten tot {int(round(dag.vlagen))} m/s)"
    return zin + "."


def formuleer_dag(dag, stad, label):
    """De dagvoorspelling als tekst, of None als er geen temperatuur is."""
    hoofd = _hoofdzin(dag, stad, label)
    if hoofd is None:
        return None
    delen = [hoofd, _regenkans_zin(dag), _wind_zin(dag)]
    return " ".join(d for d in delen if d)


def dag_waarschuwing(dag):
    """'Let op: ...' voor een hele dag, of None. Zelfde formaat en drempels
    als weather.py's weerwaarschuwing(), maar dan op basis van de weercode
    en de dagwaarden. Gladheid door lage temperatuur zit hier bewust NIET
    in: voor een hele dag is dat te grof (kou 's nachts, regen 's middags
    geeft geen gladheid). Alleen ijzel (een aparte weercode) komt erin."""
    w = []
    if dag.code in ONWEER_CODES:
        w.append("er wordt onweer verwacht")
    if dag.code in HAGEL_CODES:
        w.append("er wordt hagel verwacht")
    if dag.code in SNEEUW_CODES:
        w.append("er wordt sneeuw verwacht")
    if dag.code in MIST_CODES:
        w.append("er wordt mist verwacht")
    if dag.code in IJZEL_CODES:
        w.append("kans op ijzel en gladheid")
    if (
        (dag.wind is not None and dag.wind >= WIND_DREMPEL_MS)
        or (dag.vlagen is not None and dag.vlagen >= VLAAG_DREMPEL_MS)
    ):
        w.append("er wordt harde wind verwacht")
    if dag.tmax is not None and dag.tmax >= HITTE_DREMPEL_C:
        w.append("het wordt erg warm")

    if not w:
        return None
    return f"Let op: {' en '.join(w)}."


# -----------------------------------------------------
# Ochtendsamenvatting
# -----------------------------------------------------
def kleding_temperatuur(dag, uren):
    """Temperatuur waar het kledingadvies op gebaseerd wordt: het gemiddelde
    van de gevoelstemperatuur overdag. Ontbreken de uurgegevens, dan het
    gemiddelde van minimum en maximum. Geeft None als er niets is."""
    van, tot = OCHTEND_KLEDING_UREN
    gevoel = [
        u.gevoel for u in uren
        if van <= u.tijd.hour <= tot and u.gevoel is not None
    ]
    if gevoel:
        return sum(gevoel) / len(gevoel)

    temps = [t for t in (dag.tmax, dag.tmin) if t is not None]
    if temps:
        return sum(temps) / len(temps)
    return None


def regen_piek(uren, nu):
    """Het uur (vanaf nu, tot 23:00) met de grootste regenkans, als die
    minstens OCHTEND_REGEN_DREMPEL_PCT is. Geeft (uur, kans) of None.
    Bij gelijke kans wint het vroegste uur."""
    beste = None
    for u in uren:
        if u.regenkans is None:
            continue
        if u.tijd.hour < max(nu.hour, 7) or u.tijd.hour > 22:
            continue
        if beste is None or u.regenkans > beste[1]:
            beste = (u.tijd.hour, u.regenkans)

    if beste is None or beste[1] < OCHTEND_REGEN_DREMPEL_PCT:
        return None
    return beste


def formuleer_ochtend(dag, uren, stad, opening, nu):
    """Het hoofddeel van de ochtendsamenvatting: opening, temperatuur en
    weertype, regenkans en (als er een duidelijk piekuur is) wanneer.
    Kledingadvies, waarschuwing en radarzin voegt weather.py erachter toe.
    Geeft None als er geen temperatuur is."""
    hoofd = _hoofdzin(dag, stad, "Vandaag")
    if hoofd is None:
        return None

    delen = [f"{opening} {hoofd}", _regenkans_zin(dag)]

    piek = regen_piek(uren, nu)
    if piek is not None:
        uur, kans = piek
        delen.append(
            f"De kans op regen is het grootst rond {uur} uur ({int(round(kans))}%)."
        )

    return " ".join(d for d in delen if d)