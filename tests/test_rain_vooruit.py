# tests/test_rain_vooruit.py
"""
pytest-tests voor de uitbreiding van modules/weather/rain.py van 18 oktober 2026:

  1. de korte radarzin voor in "wat is het weer"  (formuleer_kort, weer_vooruit_zin)
  2. gladheid en harde wind in de komende uren     (parse_gevaar, analyseer_gevaar,
                                                    beslis_gevaar, check_proactief)

Risico-afweging: dit zijn nieuwe, spontane meldingen ("Let op: kans op
gladheid over ongeveer 1 uur"). Een fout in de drempels of in de
"niet dubbel melden"-regels merk je anders pas als Nova 's nachts of bij
elke controle opnieuw begint te praten. Daarom worden de grenswaarden
(0/2 graden, 15/20 m/s), de stille uren en de "al gemeld"-vlag expliciet
getest, en ook dat een kapotte bron nooit het gewone weerbericht of de
regenmelding tegenhoudt.

Geen netwerk nodig: requests.get wordt vervangen door een nep-versie.
"""

from datetime import datetime, timedelta

import pytest

from modules.weather import rain
from modules.weather.rain import (
    RainModule,
    Slot,
    Weerpunt,
    analyseer,
    analyseer_gevaar,
    beslis_gevaar,
    formuleer_kort,
    gevaar_fragment,
    haal_gevaar,
    is_glad,
    is_harde_wind,
    parse_gevaar,
    weer_vooruit_zin,
)

NU = datetime(2026, 1, 15, 14, 0)


# ---------------------------------------------------------------
# Hulpjes
# ---------------------------------------------------------------

class FakeResponse:
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


def maak_slots(eerste_start, waarden, stap=5):
    slots = []
    for i, mm_u in enumerate(waarden):
        start = eerste_start + timedelta(minutes=stap * i)
        slots.append(Slot(start, start + timedelta(minutes=stap), mm_u))
    return slots


def analyse_van(waarden, nu=NU):
    return analyseer(maak_slots(nu, waarden), nu)


def maak_gevaar_json(eerste_start, rijen):
    """rijen = lijst van (temp, neerslag_mm, wind, vlagen) per kwartier."""
    return {"minutely_15": {
        "time": [(eerste_start + timedelta(minutes=15 * i)).strftime("%Y-%m-%dT%H:%M")
                 for i in range(len(rijen))],
        "temperature_2m": [r[0] for r in rijen],
        "precipitation": [r[1] for r in rijen],
        "wind_speed_10m": [r[2] for r in rijen],
        "wind_gusts_10m": [r[3] for r in rijen],
    }}


def punten_van(rijen, start=NU):
    return parse_gevaar(maak_gevaar_json(start, rijen))


# Kwartieren: (temp, neerslag, wind, vlagen)
RUSTIG = (8.0, 0.0, 3.0, 5.0)
GLAD = (1.0, 0.3, 3.0, 5.0)         # 1 graad + neerslag
KOUD_DROOG = (1.0, 0.0, 3.0, 5.0)   # droge kou: geen gladheid
WARM_NAT = (6.0, 0.5, 3.0, 5.0)     # regen, maar geen vorst
STORM = (8.0, 0.0, 16.0, 24.0)      # harde wind


@pytest.fixture
def bus():
    return DummyEventBus()


@pytest.fixture
def rm(bus):
    return RainModule(bus, api_key=None)


def nep_alles(monkeypatch, buienradar=None, typeinfo=None, gevaar=None):
    """Vervangt requests.get in rain.py. Elke bron is een FakeResponse of een
    Exception-instantie (verbindingsfout). None = FakeResponse(404)."""
    standaard = FakeResponse(status_code=404)

    def nep_get(url, timeout=None):
        if "buienradar" in url:
            antwoord = buienradar
        elif "wind_gusts_10m" in url:
            antwoord = gevaar
        elif "weather_code" in url:
            antwoord = typeinfo
        else:
            antwoord = None
        antwoord = antwoord if antwoord is not None else standaard
        if isinstance(antwoord, Exception):
            raise antwoord
        return antwoord

    monkeypatch.setattr(rain.requests, "get", nep_get)


def buienradar_tekst(waarden, nu=NU):
    """'000|14:00' per 5 minuten, vanaf nu."""
    regels = []
    for i, w in enumerate(waarden):
        t = nu + timedelta(minutes=5 * i)
        regels.append(f"{w:03d}|{t:%H:%M}")
    return "\n".join(regels) + "\n"


# ---------------------------------------------------------------
# 1. Korte radarzin
# ---------------------------------------------------------------

R, D = 1.0, 0.0  # regen / droog (mm/u)


def test_kort_regen_begint_straks():
    # 4 droge blokken van 5 min, dan regen: begint over 20 minuten
    zin = formuleer_kort(analyse_van([D, D, D, D, R, R, R, R]))
    assert zin == "Over ongeveer 20 minuten begint het te regenen (lichte regen)."


def test_kort_regen_begint_zo_meteen():
    # Het droge blok loopt nog 2 minuten, daarna regen: "zo meteen".
    slots = maak_slots(NU - timedelta(minutes=3), [D, R, R, R])
    zin = formuleer_kort(analyseer(slots, NU))
    assert zin.startswith("Zo meteen begint het te regenen")


def test_kort_regent_nu_en_stopt():
    zin = formuleer_kort(analyse_van([R, R, R, D, D, D, D]))
    assert zin == "De regen stopt over ongeveer 15 minuten."


def test_kort_regent_nu_stopt_en_komt_terug():
    zin = formuleer_kort(analyse_van([R, R, D, D, D, D, R, R]))
    assert zin.startswith("De regen stopt over ongeveer 10 minuten.")
    assert "begint het opnieuw te regenen" in zin


def test_kort_regent_nu_en_blijft_regenen():
    zin = formuleer_kort(analyse_van([R] * 24))
    assert zin.startswith("De regen houdt voorlopig aan, minstens de komende")


def test_kort_droog_en_blijft_droog_geeft_niets():
    # Het weerbericht hoeft niet elke keer 'het blijft droog' te zeggen.
    assert formuleer_kort(analyse_van([D] * 24)) is None


def test_kort_zonder_analyse_geeft_niets():
    assert formuleer_kort(None) is None


def test_kort_sneeuw_gebruikt_sneeuwwoorden():
    zin = formuleer_kort(analyse_van([D, D, D, D, R, R]), soort="sneeuw")
    assert zin == "Over ongeveer 20 minuten begint het te sneeuwen (lichte sneeuw)."


def test_kort_sneeuw_stopt_gebruikt_sneeuwwoorden():
    zin = formuleer_kort(analyse_van([R, R, D, D, D, D]), soort="sneeuw")
    assert "sneeuw" in zin and "regen" not in zin


# ---------------------------------------------------------------
# 2a. Inlezen
# ---------------------------------------------------------------

# Echte Open-Meteo-uitvoer van 18 oktober 2026 (Kevin's controle in de container).
ECHT_GEVAAR = {"minutely_15": {
    "time": ["2026-10-18T17:45", "2026-10-18T18:00", "2026-10-18T18:15"],
    "wind_gusts_10m": [3.1, 3.0, 2.8],
    "wind_speed_10m": [1.4, 1.4, 1.4],
    "temperature_2m": [10.7, 10.5, 10.4],
    "precipitation": [0.0, 0.0, 0.0],
}}


def test_parse_gevaar_echte_data():
    punten = parse_gevaar(ECHT_GEVAAR)
    assert len(punten) == 3
    p = punten[0]
    assert p.start == datetime(2026, 10, 18, 17, 45)
    assert p.einde == datetime(2026, 10, 18, 18, 0)
    assert (p.temp, p.neerslag, p.wind, p.vlagen) == (10.7, 0.0, 1.4, 3.1)
    assert not is_glad(p) and not is_harde_wind(p)


@pytest.mark.parametrize("rommel", [{}, None, {"minutely_15": {}}, {"minutely_15": []},
                                    {"minutely_15": {"time": "kapot"}}])
def test_parse_gevaar_rommel_geeft_lege_lijst(rommel):
    assert parse_gevaar(rommel) == []


def test_parse_gevaar_ontbrekende_velden_worden_none_en_geven_geen_alarm():
    # De gewone regen-terugval stuurt alleen 'precipitation': mag niet crashen
    # en mag nooit een gladheids- of windmelding opleveren.
    data = {"minutely_15": {"time": ["2026-10-18T12:45"], "precipitation": [0.4]}}
    p = parse_gevaar(data)[0]
    assert (p.temp, p.wind, p.vlagen) == (None, None, None)
    assert not is_glad(p) and not is_harde_wind(p)


def test_parse_gevaar_slaat_kapotte_tijd_over():
    data = {"minutely_15": {"time": ["geen-tijd", "2026-10-18T12:45"],
                            "temperature_2m": [1.0, 2.0]}}
    punten = parse_gevaar(data)
    assert len(punten) == 1 and punten[0].temp == 2.0


def test_parse_gevaar_lege_waarden_blijven_none():
    data = {"minutely_15": {"time": ["2026-10-18T12:45"], "temperature_2m": [None],
                            "precipitation": [None], "wind_speed_10m": [None],
                            "wind_gusts_10m": [None]}}
    p = parse_gevaar(data)[0]
    assert not is_glad(p) and not is_harde_wind(p)


# ---------------------------------------------------------------
# 2b. De drempels
# ---------------------------------------------------------------

def punt(temp=8.0, neerslag=0.0, wind=3.0, vlagen=5.0):
    return Weerpunt(NU, NU + timedelta(minutes=15), temp, neerslag, wind, vlagen)


@pytest.mark.parametrize("temp,neerslag,verwacht", [
    (0.0, 0.3, True),     # precies op de ondergrens
    (2.0, 0.3, True),     # precies op de bovengrens
    (1.0, 0.3, True),
    (-0.1, 0.3, True),    # net onder 0: telt sinds punt 48 ook als glad
    (-5.0, 0.3, True),    # stevige vorst met neerslag: glad
    (-5.0, 0.0, False),   # droge vorst: niet glad
    (2.1, 0.3, False),    # net boven 2
    (1.0, 0.0, False),    # droge kou
    (1.0, 0.1, True),     # 0.1 mm in een kwartier = 0.4 mm/u: telt als neerslag
    (None, 0.3, False),
    (1.0, None, False),
])
def test_is_glad(temp, neerslag, verwacht):
    assert is_glad(punt(temp=temp, neerslag=neerslag)) is verwacht


@pytest.mark.parametrize("wind,vlagen,verwacht", [
    (14.9, 19.9, False),
    (15.0, 5.0, True),     # gemiddelde wind op de drempel (zoals weather.py)
    (3.0, 20.0, True),     # windstoten op de drempel
    (3.0, 19.9, False),
    (None, None, False),
    (None, 25.0, True),
    (16.0, None, True),
])
def test_is_harde_wind(wind, vlagen, verwacht):
    assert is_harde_wind(punt(wind=wind, vlagen=vlagen)) is verwacht


# ---------------------------------------------------------------
# 2c. Analyse
# ---------------------------------------------------------------

def test_analyse_alles_rustig():
    info = analyseer_gevaar(punten_van([RUSTIG] * 12), NU)
    assert info["gladheid"] is None and info["wind"] is None
    assert info["horizon_min"] == 180


def test_analyse_zonder_gegevens_geeft_none():
    assert analyseer_gevaar([], NU) is None


def test_analyse_negeert_kwartieren_in_het_verleden():
    # Kwartieren vanaf 13:00. Het gladde kwartier van 13:00 is voorbij en telt
    # niet meer; het gladde kwartier van 14:15 wel (over 15 minuten).
    rijen = [GLAD, RUSTIG, RUSTIG, RUSTIG, RUSTIG, GLAD]
    info = analyseer_gevaar(punten_van(rijen, start=NU - timedelta(hours=1)), NU)
    assert info["gladheid"]["begin_min"] == 15
    assert info["gladheid"]["nu"] is False


def test_analyse_alleen_kwartieren_in_het_verleden_geeft_none():
    punten = punten_van([GLAD, GLAD], start=NU - timedelta(hours=2))
    assert analyseer_gevaar(punten, NU) is None


def test_analyse_gladheid_begint_over_een_uur():
    rijen = [RUSTIG] * 4 + [GLAD, GLAD, GLAD] + [RUSTIG] * 5
    info = analyseer_gevaar(punten_van(rijen), NU)
    glad = info["gladheid"]
    assert glad["nu"] is False
    assert glad["begin_min"] == 60
    assert glad["einde_min"] == 105
    assert glad["temp"] == 1.0
    assert info["wind"] is None


def test_analyse_gladheid_neemt_de_laagste_temperatuur_van_de_reeks():
    rijen = [RUSTIG, (2.0, 0.3, 3, 5), (0.5, 0.3, 3, 5), (1.5, 0.3, 3, 5), RUSTIG]
    glad = analyseer_gevaar(punten_van(rijen), NU)["gladheid"]
    assert glad["temp"] == 0.5


def test_analyse_gladheid_loopt_tot_het_einde_van_de_data():
    rijen = [RUSTIG] * 8 + [GLAD] * 4
    glad = analyseer_gevaar(punten_van(rijen), NU)["gladheid"]
    assert glad["begin_min"] == 120
    assert glad["einde_min"] is None


def test_analyse_gladheid_is_er_al():
    # Het kwartier van 14:00 loopt nog: gladheid is er dus al.
    info = analyseer_gevaar(punten_van([GLAD, GLAD, RUSTIG]), NU + timedelta(minutes=5))
    assert info["gladheid"]["nu"] is True
    assert info["gladheid"]["begin_min"] == 0


def test_analyse_droge_kou_en_natte_warmte_zijn_geen_gladheid():
    info = analyseer_gevaar(punten_van([KOUD_DROOG, WARM_NAT] * 4), NU)
    assert info["gladheid"] is None


def test_analyse_harde_wind_met_piekwaarden():
    rijen = [RUSTIG] * 2 + [STORM, (8.0, 0.0, 17.0, 26.0), STORM] + [RUSTIG] * 3
    wind = analyseer_gevaar(punten_van(rijen), NU)["wind"]
    assert wind["begin_min"] == 30
    assert wind["einde_min"] == 75
    assert wind["wind"] == 17.0
    assert wind["vlagen"] == 26.0
    assert wind["nu"] is False


def test_analyse_gladheid_en_wind_tegelijk():
    rijen = [RUSTIG, GLAD, STORM, RUSTIG]
    info = analyseer_gevaar(punten_van(rijen), NU)
    assert info["gladheid"]["begin_min"] == 15
    assert info["wind"]["begin_min"] == 30


# ---------------------------------------------------------------
# 2d. Zinnen
# ---------------------------------------------------------------

def test_fragment_gladheid():
    item = {"begin_min": 60, "temp": 1.2}
    assert gevaar_fragment("gladheid", item) == (
        "kans op gladheid over ongeveer 1 uur (rond 1°C met neerslag)"
    )


def test_fragment_gladheid_zonder_temperatuur():
    assert gevaar_fragment("gladheid", {"begin_min": 20, "temp": None}) == (
        "kans op gladheid over ongeveer 20 minuten"
    )


def test_fragment_gladheid_nul_graden_wordt_geen_min_nul():
    item = {"begin_min": 30, "temp": -0.0}
    assert "rond 0°C" in gevaar_fragment("gladheid", item)


def test_fragment_gladheid_zo_meteen():
    assert gevaar_fragment("gladheid", {"begin_min": 1, "temp": 1.0}).startswith(
        "kans op gladheid zo meteen"
    )


def test_fragment_wind_met_wind_en_vlagen():
    item = {"begin_min": 30, "wind": 16.4, "vlagen": 24.0}
    assert gevaar_fragment("wind", item) == (
        "kans op harde wind over ongeveer 30 minuten "
        "(wind tot 16 m/s en windstoten tot 24 m/s)"
    )


def test_fragment_wind_alleen_windstoten():
    item = {"begin_min": 30, "wind": 8.0, "vlagen": 22.0}
    tekst = gevaar_fragment("wind", item)
    assert "windstoten tot 22 m/s" in tekst and "wind tot" not in tekst


def test_fragment_wind_alleen_gemiddelde_wind():
    item = {"begin_min": 30, "wind": 15.0, "vlagen": 18.0}
    tekst = gevaar_fragment("wind", item)
    assert "wind tot 15 m/s" in tekst and "windstoten" not in tekst


def test_fragment_gladheid_die_er_al_is():
    item = {"nu": True, "begin_min": 0, "einde_min": 45, "temp": 1.0}
    assert gevaar_fragment("gladheid", item) == (
        "kans op gladheid nu, nog ongeveer 45 minuten (rond 1°C met neerslag)"
    )


def test_fragment_gladheid_die_er_al_is_en_blijft():
    item = {"nu": True, "begin_min": 0, "einde_min": None, "temp": 1.0}
    assert gevaar_fragment("gladheid", item) == "kans op gladheid nu (rond 1°C met neerslag)"


def test_fragment_wind_die_er_al_is():
    item = {"nu": True, "begin_min": 0, "einde_min": 90, "wind": 8.0, "vlagen": 22.0}
    assert gevaar_fragment("wind", item) == (
        "kans op harde wind nu, nog ongeveer 1 uur en 30 minuten (windstoten tot 22 m/s)"
    )


# ---------------------------------------------------------------
# 2e. Beslissen: wanneer praat Nova spontaan?
# ---------------------------------------------------------------

LEEG = {
    "gladheid": {"gemeld": False, "laatste": None},
    "wind": {"gemeld": False, "laatste": None},
}


def info_van(rijen, nu=NU):
    return analyseer_gevaar(punten_van(rijen, start=nu), nu)


def test_beslis_zonder_info_doet_niets():
    zinnen, staat = beslis_gevaar(None, NU, LEEG)
    assert zinnen == [] and staat == LEEG


def test_beslis_meldt_gladheid_binnen_het_venster():
    info = info_van([RUSTIG, RUSTIG, RUSTIG, RUSTIG, GLAD, GLAD])
    zinnen, staat = beslis_gevaar(info, NU, LEEG)
    assert zinnen == ["Let op: kans op gladheid over ongeveer 1 uur (rond 1°C met neerslag)."]
    assert staat["gladheid"]["gemeld"] is True
    assert staat["gladheid"]["laatste"] == NU
    assert staat["wind"]["gemeld"] is False


def test_beslis_meldt_harde_wind():
    info = info_van([RUSTIG, STORM, STORM])
    zinnen, staat = beslis_gevaar(info, NU, LEEG)
    assert len(zinnen) == 1 and zinnen[0].startswith("Let op: kans op harde wind")
    assert staat["wind"]["gemeld"] is True


def test_beslis_meldt_gladheid_en_wind_apart():
    info = info_van([RUSTIG, GLAD, STORM])
    zinnen, staat = beslis_gevaar(info, NU, LEEG)
    assert len(zinnen) == 2
    assert "gladheid" in zinnen[0] and "harde wind" in zinnen[1]


def test_beslis_zwijgt_als_het_te_ver_weg_is():
    # Gladheid pas over 2 uur en 15 minuten: buiten GEVAAR_VOORUIT_MINUTEN (120)
    info = info_van([RUSTIG] * 9 + [GLAD])
    assert info["gladheid"]["begin_min"] == 135
    zinnen, staat = beslis_gevaar(info, NU, LEEG)
    assert zinnen == [] and staat["gladheid"]["gemeld"] is False


def test_beslis_meldt_precies_op_de_grens():
    info = info_van([RUSTIG] * 8 + [GLAD])
    assert info["gladheid"]["begin_min"] == 120
    zinnen, _ = beslis_gevaar(info, NU, LEEG)
    assert len(zinnen) == 1


def test_beslis_zwijgt_als_het_al_gebeurt():
    # Gebeurt het nu al, dan meldt weather.py dat (huidig weer).
    nu = NU + timedelta(minutes=5)
    info = analyseer_gevaar(punten_van([GLAD, GLAD, STORM]), nu)
    assert info["gladheid"]["nu"] is True
    zinnen, _ = beslis_gevaar(info, nu, LEEG)
    assert not any("gladheid" in z for z in zinnen)


@pytest.mark.parametrize("uur", [23, 0, 3, 6])
def test_beslis_zwijgt_s_nachts(uur):
    nu = NU.replace(hour=uur)
    info = info_van([RUSTIG, GLAD, GLAD], nu=nu)
    zinnen, staat = beslis_gevaar(info, nu, LEEG)
    assert zinnen == [] and staat["gladheid"]["gemeld"] is False


def test_beslis_meldt_overdag_vanaf_7_uur():
    nu = NU.replace(hour=7, minute=0)
    info = info_van([RUSTIG, GLAD, GLAD], nu=nu)
    zinnen, _ = beslis_gevaar(info, nu, LEEG)
    assert len(zinnen) == 1


def test_beslis_meldt_dezelfde_episode_maar_een_keer():
    info = info_van([RUSTIG, GLAD, GLAD])
    zinnen, staat = beslis_gevaar(info, NU, LEEG)
    assert len(zinnen) == 1
    # 5 minuten later, voorspelling schuift iets op: niet nog eens
    nu2 = NU + timedelta(minutes=5)
    info2 = info_van([RUSTIG, RUSTIG, GLAD, GLAD], nu=nu2)
    zinnen2, staat = beslis_gevaar(info2, nu2, staat)
    assert zinnen2 == [] and staat["gladheid"]["gemeld"] is True


def test_beslis_gemeld_vlag_blokkeert_ook_na_een_uur_zolang_het_nog_niet_begonnen_is():
    # Gemeld op het uiterste moment van het venster (gladheid over 2 uur).
    # Ruim een uur later begint het nog niet (nog 59 minuten): de "een uur
    # tussen meldingen"-regel is dan voorbij, maar het is dezelfde episode.
    info = info_van([RUSTIG] * 8 + [GLAD])
    zinnen, staat = beslis_gevaar(info, NU, LEEG)
    assert len(zinnen) == 1
    nu2 = NU + timedelta(minutes=61)
    info2 = info_van([RUSTIG] * 3 + [GLAD], nu=nu2)
    assert info2["gladheid"]["begin_min"] == 45
    zinnen2, _ = beslis_gevaar(info2, nu2, staat)
    assert zinnen2 == []


def test_beslis_wist_de_vlag_als_het_uit_de_verwachting_verdwijnt():
    info = info_van([RUSTIG, GLAD, GLAD])
    _, staat = beslis_gevaar(info, NU, LEEG)
    assert staat["gladheid"]["gemeld"] is True
    nu2 = NU + timedelta(minutes=30)
    _, staat = beslis_gevaar(info_van([RUSTIG] * 8, nu=nu2), nu2, staat)
    assert staat["gladheid"]["gemeld"] is False


def test_beslis_volgende_episode_na_wissen_maximaal_een_per_uur():
    info = info_van([RUSTIG, GLAD, GLAD])
    _, staat = beslis_gevaar(info, NU, LEEG)
    nu2 = NU + timedelta(minutes=30)
    _, staat = beslis_gevaar(info_van([RUSTIG] * 8, nu=nu2), nu2, staat)  # vlag gewist
    # Nog geen uur na de eerste melding: zwijgen, ook al is er weer gladheid
    zinnen, staat = beslis_gevaar(info_van([RUSTIG, GLAD, GLAD], nu=nu2), nu2, staat)
    assert zinnen == []
    # Ruim een uur na de eerste melding: wel
    nu3 = NU + timedelta(minutes=61)
    zinnen, _ = beslis_gevaar(info_van([RUSTIG, GLAD, GLAD], nu=nu3), nu3, staat)
    assert len(zinnen) == 1


def test_beslis_gladheid_en_wind_hebben_elk_hun_eigen_staat():
    info = info_van([RUSTIG, GLAD, GLAD])
    zinnen, staat = beslis_gevaar(info, NU, LEEG)
    assert staat["wind"]["laatste"] is None
    # Wind komt erbij: wordt wel gemeld, gladheid niet nog eens
    nu2 = NU + timedelta(minutes=5)
    info2 = info_van([RUSTIG, GLAD, STORM], nu=nu2)
    zinnen2, _ = beslis_gevaar(info2, nu2, staat)
    assert len(zinnen2) == 1 and "harde wind" in zinnen2[0]


def test_beslis_verandert_de_oude_staat_niet():
    info = info_van([RUSTIG, GLAD, GLAD])
    oud = {"gladheid": {"gemeld": False, "laatste": None},
           "wind": {"gemeld": False, "laatste": None}}
    beslis_gevaar(info, NU, oud)
    assert oud["gladheid"]["gemeld"] is False


def test_beslis_werkt_met_een_lege_staat():
    # Voor de zekerheid: een ontbrekende of lege staat mag niet crashen.
    info = info_van([RUSTIG, GLAD, GLAD])
    zinnen, _ = beslis_gevaar(info, NU, {})
    assert len(zinnen) == 1


# ---------------------------------------------------------------
# Ophalen
# ---------------------------------------------------------------

def test_haal_gevaar_leest_open_meteo(monkeypatch):
    nep_alles(monkeypatch, gevaar=FakeResponse(json_data=ECHT_GEVAAR))
    assert len(haal_gevaar(51.12, 3.09)) == 3


def test_haal_gevaar_vraagt_alle_vier_de_velden_op(monkeypatch):
    gezien = []

    def nep_get(url, timeout=None):
        gezien.append(url)
        return FakeResponse(json_data=ECHT_GEVAAR)

    monkeypatch.setattr(rain.requests, "get", nep_get)
    haal_gevaar(51.12, 3.09)
    url = gezien[0]
    for veld in ("temperature_2m", "precipitation", "wind_speed_10m", "wind_gusts_10m"):
        assert veld in url
    assert "wind_speed_unit=ms" in url  # m/s, want de drempels staan in m/s


@pytest.mark.parametrize("antwoord", [
    ConnectionError("geen verbinding"),
    FakeResponse(status_code=500),
    FakeResponse(json_data="rommel"),
])
def test_haal_gevaar_geeft_lege_lijst_bij_elke_fout(monkeypatch, antwoord):
    nep_alles(monkeypatch, gevaar=antwoord)
    assert haal_gevaar(51.12, 3.09) == []


# ---------------------------------------------------------------
# weer_vooruit_zin (voor weather.py)
# ---------------------------------------------------------------

def test_vooruit_zin_radar_en_gladheid(monkeypatch):
    # Regen over 20 minuten, en een uur later gladheid
    nep_alles(
        monkeypatch,
        buienradar=FakeResponse(text=buienradar_tekst([0, 0, 0, 0, 100, 100, 100, 100])),
        gevaar=FakeResponse(json_data=maak_gevaar_json(NU, [RUSTIG] * 4 + [GLAD, GLAD])),
    )
    zin = weer_vooruit_zin(51.12, 3.09, NU)
    assert zin.startswith("Over ongeveer 20 minuten begint het te regenen")
    assert "Straks: kans op gladheid over ongeveer 1 uur" in zin


def test_vooruit_zin_droog_en_rustig_geeft_none(monkeypatch):
    nep_alles(
        monkeypatch,
        buienradar=FakeResponse(text=buienradar_tekst([0] * 24)),
        gevaar=FakeResponse(json_data=maak_gevaar_json(NU, [RUSTIG] * 12)),
    )
    assert weer_vooruit_zin(51.12, 3.09, NU) is None


def test_vooruit_zin_sneeuw_krijgt_sneeuwwoorden(monkeypatch):
    typeinfo = {"minutely_15": {
        "time": [(NU + timedelta(minutes=15 * i)).strftime("%Y-%m-%dT%H:%M") for i in range(4)],
        "rain": [0.0] * 4, "snowfall": [0.4] * 4, "weather_code": [71] * 4,
    }}
    nep_alles(
        monkeypatch,
        buienradar=FakeResponse(text=buienradar_tekst([0, 0, 0, 0, 100, 100])),
        typeinfo=FakeResponse(json_data=typeinfo),
        gevaar=FakeResponse(json_data=maak_gevaar_json(NU, [RUSTIG] * 12)),
    )
    zin = weer_vooruit_zin(51.12, 3.09, NU)
    assert "sneeuwen" in zin and "regenen" not in zin


def test_vooruit_zin_radar_kapot_gladheid_blijft_werken(monkeypatch):
    nep_alles(
        monkeypatch,
        buienradar=ConnectionError("weg"),
        gevaar=FakeResponse(json_data=maak_gevaar_json(NU, [RUSTIG, GLAD, GLAD])),
    )
    zin = weer_vooruit_zin(51.12, 3.09, NU)
    assert zin.startswith("Straks: kans op gladheid")


def test_vooruit_zin_gladheid_kapot_radar_blijft_werken(monkeypatch):
    nep_alles(
        monkeypatch,
        buienradar=FakeResponse(text=buienradar_tekst([0, 0, 0, 0, 100, 100])),
        gevaar=ConnectionError("weg"),
    )
    zin = weer_vooruit_zin(51.12, 3.09, NU)
    assert zin.startswith("Over ongeveer 20 minuten begint het te regenen")


def test_vooruit_zin_alles_kapot_geeft_none_en_crasht_niet(monkeypatch):
    nep_alles(monkeypatch, buienradar=ConnectionError("weg"), gevaar=ConnectionError("weg"))
    assert weer_vooruit_zin(51.12, 3.09, NU) is None


def test_vooruit_zin_noemt_gladheid_niet_als_het_al_glad_is(monkeypatch):
    # weather.py meldt gladheid van nu zelf al ("Let op: kans op gladheid.")
    nep_alles(
        monkeypatch,
        buienradar=FakeResponse(text=buienradar_tekst([0] * 24)),
        gevaar=FakeResponse(json_data=maak_gevaar_json(NU - timedelta(minutes=5), [GLAD, GLAD, RUSTIG])),
    )
    assert weer_vooruit_zin(51.12, 3.09, NU) is None


def test_vooruit_zin_inclusief_nu_noemt_gladheid_die_er_al_is(monkeypatch):
    nep_alles(
        monkeypatch,
        buienradar=FakeResponse(text=buienradar_tekst([0] * 24)),
        gevaar=FakeResponse(json_data=maak_gevaar_json(NU - timedelta(minutes=5), [GLAD, GLAD, RUSTIG])),
    )
    zin = weer_vooruit_zin(51.12, 3.09, NU, inclusief_nu=True)
    assert zin == "Let op: kans op gladheid nu, nog ongeveer 25 minuten (rond 1°C met neerslag)."


def test_vooruit_zin_inclusief_nu_noemt_straks_nog_steeds_als_straks(monkeypatch):
    nep_alles(
        monkeypatch,
        buienradar=FakeResponse(text=buienradar_tekst([0] * 24)),
        gevaar=FakeResponse(json_data=maak_gevaar_json(NU, [RUSTIG, RUSTIG, GLAD, GLAD])),
    )
    zin = weer_vooruit_zin(51.12, 3.09, NU, inclusief_nu=True)
    assert zin.startswith("Straks: kans op gladheid over ongeveer 30 minuten")


def test_vooruit_zin_standaard_noemt_wat_er_al_is_niet(monkeypatch):
    nep_alles(
        monkeypatch,
        buienradar=FakeResponse(text=buienradar_tekst([0] * 24)),
        gevaar=FakeResponse(json_data=maak_gevaar_json(NU - timedelta(minutes=5), [GLAD, GLAD, RUSTIG])),
    )
    assert weer_vooruit_zin(51.12, 3.09, NU) is None


def test_vooruit_zin_meldt_grove_bron(monkeypatch):
    open_meteo_regen = {"minutely_15": {
        "time": [(NU + timedelta(minutes=15 * i)).strftime("%Y-%m-%dT%H:%M") for i in range(6)],
        "precipitation": [0.0, 0.0, 0.5, 0.5, 0.0, 0.0],
    }}

    def nep_get(url, timeout=None):
        if "buienradar" in url:
            raise ConnectionError("weg")
        if "wind_gusts_10m" in url or "weather_code" in url:
            return FakeResponse(status_code=404)
        return FakeResponse(json_data=open_meteo_regen)

    monkeypatch.setattr(rain.requests, "get", nep_get)
    zin = weer_vooruit_zin(51.12, 3.09, NU)
    assert "grovere schatting" in zin


# ---------------------------------------------------------------
# Regressie: haal_slots / haal_typeinfo zijn nu staticmethods
# ---------------------------------------------------------------

def test_haal_slots_werkt_zowel_met_als_zonder_object(rm, monkeypatch):
    nep_alles(monkeypatch, buienradar=FakeResponse(text=buienradar_tekst([0, 100, 100])))
    via_object, grof1 = rm.haal_slots(51.12, 3.09, NU)
    via_klasse, grof2 = RainModule.haal_slots(51.12, 3.09, NU)
    assert via_object == via_klasse and grof1 is grof2 is False
    assert len(via_object) == 3


def test_haal_typeinfo_werkt_zowel_met_als_zonder_object(rm, monkeypatch):
    typeinfo = {"minutely_15": {"time": ["2026-01-15T14:00"], "rain": [0.0],
                                "snowfall": [0.0], "weather_code": [3]}}
    nep_alles(monkeypatch, typeinfo=FakeResponse(json_data=typeinfo))
    assert rm.haal_typeinfo(51.12, 3.09) == RainModule.haal_typeinfo(51.12, 3.09)
    assert len(rm.haal_typeinfo(51.12, 3.09)) == 1


# ---------------------------------------------------------------
# check_proactief(): de derde controle
# ---------------------------------------------------------------

def test_check_proactief_meldt_gladheid(rm, bus, monkeypatch):
    nep_alles(
        monkeypatch,
        buienradar=FakeResponse(text=buienradar_tekst([0] * 24)),
        gevaar=FakeResponse(json_data=maak_gevaar_json(NU, [RUSTIG, RUSTIG, GLAD, GLAD])),
    )
    resultaat = rm.check_proactief(nu=NU)
    assert "kans op gladheid over ongeveer 30 minuten" in resultaat
    assert len(bus.gepubliceerd) == 1
    assert bus.gepubliceerd[0][0] == "layer4_response"


def test_check_proactief_meldt_dezelfde_gladheid_niet_twee_keer(rm, bus, monkeypatch):
    nep_alles(
        monkeypatch,
        buienradar=FakeResponse(text=buienradar_tekst([0] * 24)),
        gevaar=FakeResponse(json_data=maak_gevaar_json(NU, [RUSTIG, RUSTIG, GLAD, GLAD])),
    )
    rm.check_proactief(nu=NU)
    assert rm.check_proactief(nu=NU + timedelta(minutes=5)) is None
    assert len(bus.gepubliceerd) == 1


def test_check_proactief_gladheid_bron_kapot_regenmelding_blijft_werken(rm, bus, monkeypatch):
    nep_alles(
        monkeypatch,
        buienradar=FakeResponse(text=buienradar_tekst([0, 0, 0, 0, 100, 100, 100, 100])),
        gevaar=ConnectionError("weg"),
    )
    resultaat = rm.check_proactief(nu=NU)
    assert "begint over ongeveer 20 minuten te regenen" in resultaat or "regenen" in resultaat
    assert len(bus.gepubliceerd) == 1


def test_check_proactief_fout_in_gladheid_houdt_regenmelding_niet_tegen(rm, bus, monkeypatch, capsys):
    nep_alles(
        monkeypatch,
        buienradar=FakeResponse(text=buienradar_tekst([0, 0, 0, 0, 100, 100, 100, 100])),
        gevaar=FakeResponse(json_data=maak_gevaar_json(NU, [RUSTIG] * 4)),
    )

    def kapot(*args, **kwargs):
        raise RuntimeError("kunstmatige testfout")

    monkeypatch.setattr(rain, "analyseer_gevaar", kapot)
    resultaat = rm.check_proactief(nu=NU)
    assert resultaat is not None and "regenen" in resultaat
    assert "gladheid/wind-check mislukt" in capsys.readouterr().out
    assert len(bus.gepubliceerd) == 1


def test_check_proactief_regen_en_gladheid_samen_twee_aparte_berichten(rm, bus, monkeypatch):
    nep_alles(
        monkeypatch,
        buienradar=FakeResponse(text=buienradar_tekst([0, 0, 0, 0, 100, 100, 100, 100])),
        gevaar=FakeResponse(json_data=maak_gevaar_json(NU, [RUSTIG, GLAD, GLAD, GLAD])),
    )
    rm.check_proactief(nu=NU)
    assert len(bus.gepubliceerd) == 2