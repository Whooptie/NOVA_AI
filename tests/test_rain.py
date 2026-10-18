# tests/test_rain.py
"""
pytest-tests voor modules/weather/rain.py (regenradar: "gaat het regenen?" /
"wanneer stopt het met regenen?").

Risico-afweging: rain.py geeft zelf antwoorden op basis van een onofficiële
externe bron (Buienradar). Als die bron van formaat verandert, of de reserve
(Open-Meteo) niet meer werkt, merk je dat anders pas als Nova op een regenachtige
dag iets raars zegt. Daarom dekken deze tests ook de terugval-logica en het
parseren af, met de ECHTE uitvoer van 18 oktober 2026 als testdata.

Geen netwerk nodig: requests.get wordt vervangen door een nep-versie.
Geen echte data/-bestanden: rain.py schrijft niets weg.
"""

from datetime import datetime, timedelta

import pytest

from modules.weather import rain
from modules.weather.rain import (
    RainModule,
    Slot,
    analyseer,
    beslis_proactief,
    bepaal_vraagtype,
    duur_tekst,
    formuleer_begin,
    formuleer_stop,
    horizon_tekst,
    intensiteit_tekst,
    minuten_tekst,
    parse_buienradar,
    parse_open_meteo,
    waarde_naar_mm_u,
)

# ---------------------------------------------------------------
# Testdata
# ---------------------------------------------------------------

# Echte Buienradar-uitvoer van zondag 18 oktober 2026, 12:56 (Aartrijke).
ECHTE_BUIENRADAR = (
    "077|13:00\n109|13:05\n102|13:10\n104|13:15\n087|13:20\n077|13:25\n"
    + "".join(
        f"000|{u:02d}:{m:02d}\n"
        for u, m in [
            (13, 30), (13, 35), (13, 40), (13, 45), (13, 50), (13, 55),
            (14, 0), (14, 5), (14, 10), (14, 15), (14, 20), (14, 25),
            (14, 30), (14, 35), (14, 40), (14, 45), (14, 50), (14, 55),
        ]
    )
)

# Echte Open-Meteo-uitvoer van hetzelfde moment.
ECHTE_OPEN_METEO = {
    "minutely_15": {
        "time": [
            "2026-10-18T12:45", "2026-10-18T13:00", "2026-10-18T13:15",
            "2026-10-18T13:30", "2026-10-18T13:45", "2026-10-18T14:00",
            "2026-10-18T14:15", "2026-10-18T14:30", "2026-10-18T14:45",
            "2026-10-18T15:00", "2026-10-18T15:15", "2026-10-18T15:30",
        ],
        "precipitation": [0.4, 0.4, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    }
}

NU_ECHT = datetime(2026, 10, 18, 12, 56)
NU = datetime(2026, 10, 18, 13, 0)

R = 1.0  # regen (mm/u)
D = 0.0  # droog


def maak_slots(eerste_start, waarden, stap=5):
    """Eén Slot per waarde, elk 'stap' minuten lang."""
    slots = []
    for i, mm_u in enumerate(waarden):
        start = eerste_start + timedelta(minutes=stap * i)
        slots.append(Slot(start, start + timedelta(minutes=stap), mm_u))
    return slots


class FakeResponse:
    """Nep-antwoord van requests.get()."""

    def __init__(self, status_code=200, text="", json_data=None):
        self.status_code = status_code
        self.text = text
        self._json = json_data

    def json(self):
        return self._json


class DummyEventBus:
    def __init__(self):
        self.gepubliceerd = []

    def subscribe(self, *args, **kwargs):
        pass

    def publish(self, event, data):
        self.gepubliceerd.append((event, data))


@pytest.fixture
def bus():
    return DummyEventBus()


@pytest.fixture
def rm(bus):
    # Geen API-sleutel: onbekende steden kunnen dan niet opgezocht worden,
    # en Aartrijke zit al in BEKENDE_LOCATIES.
    return RainModule(bus, api_key=None)


def nep_requests(monkeypatch, buienradar, open_meteo):
    """Vervangt requests.get in rain.py. 'buienradar' en 'open_meteo' zijn
    FakeResponse-objecten, of een Exception-instantie om een
    verbindingsfout na te bootsen."""

    def nep_get(url, timeout=None):
        antwoord = buienradar if "buienradar" in url else open_meteo
        if isinstance(antwoord, Exception):
            raise antwoord
        return antwoord

    monkeypatch.setattr(rain.requests, "get", nep_get)


# ---------------------------------------------------------------
# Analyse: begint / stopt de regen?
# ---------------------------------------------------------------

@pytest.mark.parametrize(
    "waarden, verwacht",
    [
        pytest.param([R, R, R] + [D] * 21,
                     {"regent_nu": True, "stop_min": 15, "daarna_min": None},
                     id="regent nu, stopt over 15 min"),
        pytest.param([D] * 5 + [R, R] + [D] * 17,
                     {"regent_nu": False, "begin_min": 25},
                     id="droog nu, begint over 25 min"),
        pytest.param([D] * 24,
                     {"regent_nu": False, "begin_min": None, "horizon_min": 120},
                     id="helemaal droog"),
        pytest.param([R] * 24,
                     {"regent_nu": True, "stop_min": None},
                     id="regent tot het einde van de data"),
        pytest.param([R, R, D, R, R] + [D] * 19,
                     {"regent_nu": True, "stop_min": 25},
                     id="kort droog blokje (5 min) tussen de regen telt niet als gestopt"),
        pytest.param([R, R, D, D, R] + [D] * 19,
                     {"regent_nu": True, "stop_min": 10},
                     id="droog stuk van 10 min telt wel als gestopt"),
        pytest.param([R, R, R, D, D, D, D, R, R] + [D] * 15,
                     {"stop_min": 15, "daarna_min": 35},
                     id="stopt, maar komt later terug"),
        pytest.param([D, D, R, R] + [D] * 20,
                     {"regent_nu": False, "begin_min": 10},
                     id="regen begint over 10 min"),
        pytest.param([R] + [D] * 23,
                     {"regent_nu": True, "stop_min": 5},
                     id="stopt na het eerste blok"),
    ],
)
def test_analyseer_scenarios(waarden, verwacht):
    analyse = analyseer(maak_slots(NU, waarden), NU)
    for sleutel, waarde in verwacht.items():
        assert analyse[sleutel] == waarde, f"{sleutel}: {analyse}"


def test_analyseer_zonder_bruikbare_blokken_geeft_none():
    assert analyseer([], NU) is None
    # Alle blokken liggen in het verleden:
    verleden = maak_slots(NU - timedelta(hours=2), [R, R, R])
    assert analyseer(verleden, NU) is None


def test_analyseer_negeert_blokken_in_het_verleden():
    # Eerste twee blokken zijn voorbij, de regen in blok 3 is wat telt.
    slots = maak_slots(NU - timedelta(minutes=10), [R, R, D, D, D, D, D])
    analyse = analyseer(slots, NU)
    assert analyse["regent_nu"] is False
    assert analyse["begin_min"] is None


def test_analyseer_intensiteit_is_de_piek_van_de_regenreeks():
    analyse = analyseer(maak_slots(NU, [0.5, 3.0, 8.0, 1.0] + [D] * 20), NU)
    assert analyse["intensiteit"] == 8.0


def test_analyseer_kwartierblokken_kort_droog_stuk():
    # Bij kwartierblokken is 1 droog blok al 15 min -> telt wel als gestopt.
    slots = maak_slots(NU, [R, R, D, R, R, D, D, D], stap=15)
    analyse = analyseer(slots, NU)
    assert analyse["stop_min"] == 30


# ---------------------------------------------------------------
# Echte data inlezen
# ---------------------------------------------------------------

def test_buienradar_echte_tekst_wordt_ingelezen():
    slots = parse_buienradar(ECHTE_BUIENRADAR, NU_ECHT)
    assert len(slots) == 24
    assert slots[0].start == datetime(2026, 10, 18, 13, 0)
    assert slots[-1].start == datetime(2026, 10, 18, 14, 55)
    assert slots[0].einde - slots[0].start == timedelta(minutes=5)


def test_buienradar_echte_data_regent_nu_en_stopt_over_34_minuten():
    analyse = analyseer(parse_buienradar(ECHTE_BUIENRADAR, NU_ECHT), NU_ECHT)
    assert analyse["regent_nu"] is True
    assert analyse["stop_min"] == 34  # 13:30 min 12:56
    assert analyse["daarna_min"] is None


def test_buienradar_over_middernacht():
    nu = datetime(2026, 10, 18, 23, 58)
    slots = parse_buienradar("109|00:00\n109|00:05\n000|00:10\n000|00:15\n", nu)
    assert slots[0].start == datetime(2026, 10, 19, 0, 0)
    assert analyseer(slots, nu)["stop_min"] == 12


def test_buienradar_middernacht_midden_in_de_reeks():
    nu = datetime(2026, 10, 18, 23, 50)
    tekst = "000|23:50\n000|23:55\n109|00:00\n109|00:05\n"
    slots = parse_buienradar(tekst, nu)
    assert slots[2].start == datetime(2026, 10, 19, 0, 0)
    assert analyseer(slots, nu)["begin_min"] == 10


@pytest.mark.parametrize("rommel", ["", "geen data", "abc|def\nxyz", "109|25:99"])
def test_buienradar_onbruikbare_tekst_geeft_lege_lijst(rommel):
    assert parse_buienradar(rommel, NU_ECHT) == []


def test_buienradar_waarde_omrekening():
    assert waarde_naar_mm_u(0) == 0.0
    assert waarde_naar_mm_u(109) == pytest.approx(1.0)
    assert waarde_naar_mm_u(77) == pytest.approx(0.1)


def test_open_meteo_echte_data_regent_nu_en_stopt():
    slots = parse_open_meteo(ECHTE_OPEN_METEO)
    assert len(slots) == 12
    assert slots[0].mm_u == pytest.approx(1.6)  # 0.4 mm per kwartier x 4
    analyse = analyseer(slots, NU_ECHT)
    assert analyse["regent_nu"] is True
    assert analyse["stop_min"] == 19  # 13:15 min 12:56


@pytest.mark.parametrize("rommel", [{}, None, {"minutely_15": {}}, {"andere": 1}])
def test_open_meteo_onbruikbaar_antwoord_geeft_lege_lijst(rommel):
    assert parse_open_meteo(rommel) == []


def test_open_meteo_slaat_lege_waarden_over():
    data = {"minutely_15": {
        "time": ["2026-10-18T13:00", "2026-10-18T13:15"],
        "precipitation": [None, 0.4],
    }}
    assert len(parse_open_meteo(data)) == 1


# ---------------------------------------------------------------
# Zinnen
# ---------------------------------------------------------------

@pytest.mark.parametrize(
    "minuten, verwacht",
    [
        (0, "zo meteen"),
        (1, "zo meteen"),
        (2, "zo meteen"),
        (3, "over ongeveer 3 minuten"),
        (7, "over ongeveer 7 minuten"),
        (34, "over ongeveer 35 minuten"),
        (59, "over ongeveer 1 uur"),
        (60, "over ongeveer 1 uur"),
        (80, "over ongeveer 1 uur en 20 minuten"),
        (120, "over ongeveer 2 uur"),
    ],
)
def test_minuten_tekst(minuten, verwacht):
    assert minuten_tekst(minuten) == verwacht


@pytest.mark.parametrize(
    "minuten, verwacht",
    [(45, "45 minuten"), (59, "1 uur"), (124, "2 uur"), (140, "2 uur en 30 minuten"), (169, "3 uur")],
)
def test_horizon_tekst(minuten, verwacht):
    assert horizon_tekst(minuten) == verwacht


def test_duur_tekst_enkelvoud():
    assert duur_tekst(1) == "1 minuut"


@pytest.mark.parametrize(
    "mm_u, verwacht",
    [
        (0.1, "lichte motregen"),
        (1.0, "lichte regen"),
        (3.0, "matige regen"),
        (8.0, "zware regen"),
    ],
)
def test_intensiteit_tekst(mm_u, verwacht):
    assert intensiteit_tekst(mm_u) == verwacht


def test_zinnen_regent_nu_en_stopt_straks():
    analyse = analyseer(maak_slots(NU, [R, R, R] + [D] * 21), NU)
    zin = formuleer_begin(analyse)
    assert "regent nu al" in zin
    assert "over ongeveer 15 minuten" in zin
    assert "Daarna blijft het droog" in zin


def test_zinnen_stopt_en_komt_terug():
    analyse = analyseer(maak_slots(NU, [R, R, R, D, D, D, D, R, R] + [D] * 15), NU)
    zin = formuleer_stop(analyse)
    assert "stopt over ongeveer 15 minuten" in zin
    assert "over ongeveer 35 minuten begint het opnieuw te regenen" in zin


def test_zinnen_blijft_regenen_verwijst_naar_de_grens_van_de_radar():
    analyse = analyseer(maak_slots(NU, [R] * 24), NU)
    assert "tot minstens 2 uur" in formuleer_stop(analyse)
    assert "Verder kijk ik niet" in formuleer_begin(analyse)


def test_zinnen_droog_nu_regen_straks():
    analyse = analyseer(maak_slots(NU, [D] * 5 + [R, R] + [D] * 17), NU)
    assert "Het begint over ongeveer 25 minuten te regenen" in formuleer_begin(analyse)
    assert "Het regent nu niet. Wel begint het" in formuleer_stop(analyse)


def test_zinnen_helemaal_droog():
    analyse = analyseer(maak_slots(NU, [D] * 24), NU)
    assert "Het blijft droog" in formuleer_begin(analyse)
    assert "blijft het droog" in formuleer_stop(analyse)


# ---------------------------------------------------------------
# Vraagtype en stad
# ---------------------------------------------------------------

@pytest.mark.parametrize(
    "tekst, verwacht",
    [
        ("gaat het regenen", "begin"),
        ("regent het straks", "begin"),
        ("gaat het regenen in gent", "begin"),
        ("wanneer stopt het met regenen", "stop"),
        ("wanneer stopt de regen", "stop"),
        ("wanneer houdt het op met regenen", "stop"),
        ("wanneer houdt de regen op", "stop"),
        ("wanneer klaart het op", "stop"),
        ("wanneer is het gedaan met regenen", "stop"),
        ("wanneer is het weer droog", "stop"),
        ("is de regen straks voorbij", "stop"),
        ("WANNEER STOPT HET", "stop"),
    ],
)
def test_bepaal_vraagtype(tekst, verwacht):
    assert bepaal_vraagtype(tekst) == verwacht


@pytest.mark.parametrize(
    "tekst, verwacht",
    [
        ("gaat het regenen", "Aartrijke"),
        ("gaat het regenen in gent", "gent"),
        ("gaat het regenen in gent?", "gent"),
        ("regent het in brugge vandaag", "brugge"),
        ("gaat het regenen in ", "Aartrijke"),
    ],
)
def test_extract_city(rm, tekst, verwacht):
    assert rm.extract_city(tekst) == verwacht


# ---------------------------------------------------------------
# Bronnen en terugval (netwerk vervangen door nep-antwoorden)
# ---------------------------------------------------------------

def test_haal_slots_gebruikt_buienradar_als_die_werkt(rm, monkeypatch):
    nep_requests(monkeypatch,
                 buienradar=FakeResponse(200, text=ECHTE_BUIENRADAR),
                 open_meteo=FakeResponse(200, json_data=ECHTE_OPEN_METEO))
    slots, grof = rm.haal_slots(51.12, 3.09, NU_ECHT)
    assert grof is False
    assert len(slots) == 24


@pytest.mark.parametrize(
    "buienradar",
    [
        ConnectionError("geen verbinding"),
        FakeResponse(503, text="Service Unavailable"),
        FakeResponse(404, text="Not Found"),
        FakeResponse(200, text="Dit adres bestaat niet meer"),
        FakeResponse(200, text=""),
    ],
    ids=["verbindingsfout", "http 503", "http 404", "ander formaat", "leeg antwoord"],
)
def test_haal_slots_valt_terug_op_open_meteo(rm, monkeypatch, buienradar):
    nep_requests(monkeypatch,
                 buienradar=buienradar,
                 open_meteo=FakeResponse(200, json_data=ECHTE_OPEN_METEO))
    slots, grof = rm.haal_slots(51.12, 3.09, NU_ECHT)
    assert grof is True
    assert len(slots) == 12


def test_haal_slots_geeft_lege_lijst_als_beide_bronnen_falen(rm, monkeypatch):
    nep_requests(monkeypatch,
                 buienradar=ConnectionError("weg"),
                 open_meteo=FakeResponse(500))
    slots, grof = rm.haal_slots(51.12, 3.09, NU_ECHT)
    assert slots == []


# ---------------------------------------------------------------
# Hele keten: vraag -> antwoord
# ---------------------------------------------------------------

def test_maak_antwoord_echte_data_stop_vraag(rm, monkeypatch):
    nep_requests(monkeypatch,
                 buienradar=FakeResponse(200, text=ECHTE_BUIENRADAR),
                 open_meteo=FakeResponse(500))
    antwoord = rm.maak_antwoord("Aartrijke", "stop", nu=NU_ECHT)
    assert antwoord.startswith("Het stopt over ongeveer 35 minuten met regenen.")
    assert "grovere schatting" not in antwoord


def test_maak_antwoord_echte_data_begin_vraag(rm, monkeypatch):
    nep_requests(monkeypatch,
                 buienradar=FakeResponse(200, text=ECHTE_BUIENRADAR),
                 open_meteo=FakeResponse(500))
    antwoord = rm.maak_antwoord("Aartrijke", "begin", nu=NU_ECHT)
    assert antwoord.startswith("Het regent nu al (lichte regen).")


def test_maak_antwoord_meldt_grove_bron(rm, monkeypatch):
    nep_requests(monkeypatch,
                 buienradar=ConnectionError("weg"),
                 open_meteo=FakeResponse(200, json_data=ECHTE_OPEN_METEO))
    antwoord = rm.maak_antwoord("Aartrijke", "stop", nu=NU_ECHT)
    assert "grovere schatting per kwartier" in antwoord


def test_maak_antwoord_radar_onbereikbaar(rm, monkeypatch):
    nep_requests(monkeypatch,
                 buienradar=ConnectionError("weg"),
                 open_meteo=ConnectionError("ook weg"))
    antwoord = rm.maak_antwoord("Aartrijke", "begin", nu=NU_ECHT)
    assert antwoord == "Ik kon de regenradar nu niet bereiken."


def test_maak_antwoord_onbekende_stad_zonder_api_sleutel(rm):
    antwoord = rm.maak_antwoord("gent", "begin", nu=NU_ECHT)
    assert antwoord.startswith("Ik weet niet waar Gent ligt")


def test_maak_antwoord_andere_stad_krijgt_stadsnaam_voorop(rm, monkeypatch):
    monkeypatch.setattr(rm, "get_coordinates", lambda city: (51.05, 3.72))
    nep_requests(monkeypatch,
                 buienradar=FakeResponse(200, text=ECHTE_BUIENRADAR),
                 open_meteo=FakeResponse(500))
    antwoord = rm.maak_antwoord("gent", "stop", nu=NU_ECHT)
    assert antwoord.startswith("In Gent: Het stopt")


def test_on_rain_publiceert_layer4_response(rm, bus, monkeypatch):
    nep_requests(monkeypatch,
                 buienradar=FakeResponse(200, text=ECHTE_BUIENRADAR),
                 open_meteo=FakeResponse(500))
    monkeypatch.setattr(rain, "nu_lokaal", lambda: NU_ECHT)
    rm.on_rain({"text": "wanneer stopt het met regenen"})
    assert len(bus.gepubliceerd) == 1
    event, data = bus.gepubliceerd[0]
    assert event == "layer4_response"
    assert "stopt over ongeveer 35 minuten" in data["text"]


def test_on_rain_zonder_tekst_crasht_niet(rm, bus, monkeypatch):
    nep_requests(monkeypatch,
                 buienradar=FakeResponse(200, text=ECHTE_BUIENRADAR),
                 open_meteo=FakeResponse(500))
    rm.on_rain({})
    assert bus.gepubliceerd[0][0] == "layer4_response"


def test_module_abonneert_zich_op_intent_rain():
    geabonneerd = []

    class Bus:
        def subscribe(self, event, handler):
            geabonneerd.append(event)

        def publish(self, *args, **kwargs):
            pass

    RainModule(Bus(), api_key=None)
    assert geabonneerd == ["intent_rain"]


def test_init_module_meldt_zich_aan(monkeypatch):
    gepubliceerd = []

    class Bus:
        def subscribe(self, *args, **kwargs):
            pass

        def publish(self, event, data):
            gepubliceerd.append((event, data))

    instance = rain.init_module(Bus())
    assert isinstance(instance, RainModule)
    assert ("module_loaded", {"name": "rain"}) in gepubliceerd


# ---------------------------------------------------------------
# Tijd
# ---------------------------------------------------------------

def test_nu_lokaal_geeft_naieve_datetime():
    nu = rain.nu_lokaal()
    assert isinstance(nu, datetime)
    assert nu.tzinfo is None

# ---------------------------------------------------------------
# Proactieve melding ("over 15 minuten begint het te regenen")
# ---------------------------------------------------------------

LEEG = {"gemeld": False, "laatste": None}
DAG = datetime(2026, 10, 18, 14, 0)   # overdag


def analyse_van(waarden, nu=DAG):
    return analyseer(maak_slots(nu, waarden), nu)


def test_proactief_meldt_regen_die_binnenkort_begint():
    analyse = analyse_van([D] * 3 + [R, R] + [D] * 19)  # begint over 15 min
    zin, staat = beslis_proactief(analyse, DAG, LEEG)
    assert zin == "Let op: het begint over ongeveer 15 minuten te regenen (lichte regen)."
    assert staat["gemeld"] is True
    assert staat["laatste"] == DAG


def test_proactief_zwijgt_als_regen_nog_te_ver_weg_is():
    analyse = analyse_van([D] * 6 + [R, R] + [D] * 16)  # over 30 min
    zin, staat = beslis_proactief(analyse, DAG, LEEG)
    assert zin is None and staat["gemeld"] is False


def test_proactief_zwijgt_bij_motregen():
    analyse = analyse_van([D] * 3 + [0.2, 0.2] + [D] * 19)
    assert beslis_proactief(analyse, DAG, LEEG)[0] is None


def test_proactief_zwijgt_als_het_al_regent():
    analyse = analyse_van([R, R, R] + [D] * 21)
    assert beslis_proactief(analyse, DAG, LEEG)[0] is None


def test_proactief_zwijgt_zonder_analyse():
    assert beslis_proactief(None, DAG, LEEG) == (None, LEEG)


@pytest.mark.parametrize("uur", [23, 0, 3, 6])
def test_proactief_zwijgt_s_nachts(uur):
    nu = datetime(2026, 10, 18, uur, 0)
    analyse = analyse_van([D] * 3 + [R, R] + [D] * 19, nu)
    assert beslis_proactief(analyse, nu, LEEG)[0] is None


def test_proactief_meldt_overdag_vanaf_7_uur():
    nu = datetime(2026, 10, 18, 7, 0)
    analyse = analyse_van([D] * 3 + [R, R] + [D] * 19, nu)
    assert beslis_proactief(analyse, nu, LEEG)[0] is not None


def test_proactief_meldt_dezelfde_bui_maar_een_keer():
    # Voorspelling schommelt: 15 min, dan 20 min, dan weer 10 min.
    staat = LEEG
    zin1, staat = beslis_proactief(analyse_van([D] * 3 + [R] * 2 + [D] * 19), DAG, staat)
    zin2, staat = beslis_proactief(analyse_van([D] * 4 + [R] * 2 + [D] * 18), DAG, staat)
    zin3, staat = beslis_proactief(analyse_van([D] * 2 + [R] * 2 + [D] * 20), DAG, staat)
    assert zin1 is not None
    assert zin2 is None and zin3 is None


def test_proactief_volgende_bui_wordt_wel_gemeld():
    staat = LEEG
    _, staat = beslis_proactief(analyse_van([D] * 3 + [R] * 2 + [D] * 19), DAG, staat)
    # De bui is er: het regent nu -> 'gemeld' wordt gewist.
    _, staat = beslis_proactief(analyse_van([R] * 2 + [D] * 22), DAG, staat)
    assert staat["gemeld"] is False
    # Twee uur later komt er weer een bui aan.
    later = DAG + timedelta(hours=2)
    zin, _ = beslis_proactief(analyse_van([D] * 3 + [R] * 2 + [D] * 19, later), later, staat)
    assert zin is not None


def test_proactief_wist_melding_als_regen_uit_de_voorspelling_verdwijnt():
    staat = {"gemeld": True, "laatste": DAG}
    _, staat = beslis_proactief(analyse_van([D] * 24), DAG, staat)
    assert staat["gemeld"] is False


def test_proactief_maximaal_een_melding_per_uur():
    staat = {"gemeld": False, "laatste": DAG - timedelta(minutes=30)}
    analyse = analyse_van([D] * 3 + [R, R] + [D] * 19)
    assert beslis_proactief(analyse, DAG, staat)[0] is None


def test_check_proactief_publiceert_een_keer(rm, bus, monkeypatch):
    # Radar: droog nu, regen over 15 minuten.
    tekst = "".join(
        f"{'109' if 3 <= i < 5 else '000'}|{(14 * 60 + 5 * i) // 60:02d}:{(14 * 60 + 5 * i) % 60:02d}\n"
        for i in range(24)
    )
    nep_requests(monkeypatch,
                 buienradar=FakeResponse(200, text=tekst),
                 open_meteo=FakeResponse(500))
    eerste = rm.check_proactief(nu=DAG)
    tweede = rm.check_proactief(nu=DAG + timedelta(minutes=5))
    assert eerste is not None and tweede is None
    assert [e for e, _ in bus.gepubliceerd] == ["layer4_response"]


def test_check_proactief_crasht_niet_als_radar_weg_is(rm, bus, monkeypatch):
    nep_requests(monkeypatch,
                 buienradar=ConnectionError("weg"),
                 open_meteo=ConnectionError("ook weg"))
    assert rm.check_proactief(nu=DAG) is None
    assert bus.gepubliceerd == []