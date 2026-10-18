# tests/test_forecast.py
"""
pytest-tests voor modules/weather/forecast.py (18 oktober 2026): de
dagvoorspelling tot 16 dagen vooruit en de ochtendsamenvatting.

Risico-afweging: dit bestand zet getallen van een weermodel om in zinnen die
Nova hardop zegt, en bepaalt wanneer ze "let op" zegt. Een verkeerde
afronding, een verkeerde drempel (15/20 m/s, 27 graden) of een foute
onzekerheidsopmerking vallen niet vanzelf op. De URL's worden ook getest:
Open-Meteo weigert de HELE aanvraag bij één verkeerde veldnaam, en dat merk
je anders pas als de ochtendsamenvatting nooit meer komt.

Geen netwerk, geen bestanden: alles hier zijn pure functies.
"""

from datetime import date, datetime, timedelta

import pytest

from modules.weather import forecast
from modules.weather.forecast import (
    Dag,
    Uur,
    beschrijving,
    dag_label,
    dag_waarschuwing,
    formuleer_dag,
    formuleer_ochtend,
    graden,
    is_ochtend,
    kleding_temperatuur,
    onzekerheid_tekst,
    parse_dagen,
    parse_uren,
    regen_piek,
)

VANDAAG = date(2026, 10, 18)  # een zondag


def maak_dag(**kw):
    """Een rustige dag; geef alleen op wat afwijkt."""
    waarden = dict(
        datum=VANDAAG, code=3, tmax=12.0, tmin=6.0,
        regenkans=20, neerslag=0.0, wind=4.0, vlagen=7.0,
    )
    waarden.update(kw)
    return Dag(**waarden)


# Echte Open-Meteo-uitvoer van 18 oktober 2026 (Kevin's controle in de container,
# de eerste drie dagen van de 16).
ECHT_DAILY = {"daily": {
    "time": ["2026-10-18", "2026-10-19", "2026-10-20"],
    "weather_code": [53, 45, 3],
    "temperature_2m_max": [11.4, 13.0, 13.2],
    "temperature_2m_min": [6.3, 5.5, 7.2],
    "precipitation_probability_max": [29, 20, 63],
    "precipitation_sum": [0.5, 0.0, 0.3],
    "wind_speed_10m_max": [3.7, 4.3, 6.3],
    "wind_gusts_10m_max": [5.7, 6.8, 11.0],
}}


# ---------------------------------------------------------------
# Inlezen
# ---------------------------------------------------------------

def test_parse_dagen_echte_data():
    dagen = parse_dagen(ECHT_DAILY)
    assert len(dagen) == 3
    d = dagen[0]
    assert d.datum == date(2026, 10, 18)
    assert (d.code, d.tmax, d.tmin) == (53, 11.4, 6.3)
    assert (d.regenkans, d.neerslag, d.wind, d.vlagen) == (29, 0.5, 3.7, 5.7)
    assert dagen[2].regenkans == 63


@pytest.mark.parametrize("rommel", [{}, None, {"daily": {}}, {"daily": []},
                                    {"daily": {"time": "kapot"}}])
def test_parse_dagen_rommel_geeft_lege_lijst(rommel):
    assert parse_dagen(rommel) == []


def test_parse_dagen_ontbrekende_velden_worden_none():
    dagen = parse_dagen({"daily": {"time": ["2026-10-18"], "temperature_2m_max": [10.0]}})
    assert dagen[0].tmax == 10.0
    assert dagen[0].tmin is None and dagen[0].regenkans is None and dagen[0].code is None


def test_parse_dagen_slaat_kapotte_datum_over():
    dagen = parse_dagen({"daily": {"time": ["geen-datum", "2026-10-18"],
                                   "temperature_2m_max": [1.0, 2.0]}})
    assert len(dagen) == 1 and dagen[0].tmax == 2.0


def test_parse_dagen_ver_weg_regenkans_kan_none_zijn():
    # Open-Meteo kan voor dagen ver weg een lege regenkans geven.
    data = {"daily": {"time": ["2026-11-02"], "temperature_2m_max": [9.0],
                      "temperature_2m_min": [4.0], "precipitation_probability_max": [None]}}
    assert parse_dagen(data)[0].regenkans is None


def test_parse_uren():
    data = {"hourly": {
        "time": ["2026-10-18T07:00", "2026-10-18T08:00"],
        "temperature_2m": [8.0, 9.0],
        "apparent_temperature": [6.0, 7.5],
        "precipitation_probability": [10, 55],
        "weather_code": [3, 61],
    }}
    uren = parse_uren(data)
    assert len(uren) == 2
    assert uren[1].tijd == datetime(2026, 10, 18, 8, 0)
    assert (uren[1].temp, uren[1].gevoel, uren[1].regenkans, uren[1].code) == (9.0, 7.5, 55, 61)


@pytest.mark.parametrize("rommel", [{}, None, {"hourly": {}}, {"hourly": {"time": "kapot"}}])
def test_parse_uren_rommel_geeft_lege_lijst(rommel):
    assert parse_uren(rommel) == []


# ---------------------------------------------------------------
# Zinnen
# ---------------------------------------------------------------

@pytest.mark.parametrize("waarde,verwacht", [
    (12.6, "13°C"), (12.4, "12°C"), (0.0, "0°C"), (-0.4, "0°C"), (-3.6, "-4°C"),
])
def test_graden(waarde, verwacht):
    assert graden(waarde) == verwacht


def test_beschrijving():
    assert beschrijving(61) == "lichte regen"
    assert beschrijving(95) == "onweer"
    assert beschrijving(12345) is None
    assert beschrijving(None) is None


def test_alle_codes_uit_open_meteo_hebben_een_beschrijving():
    # De WMO-codes die Open-Meteo kan geven (zonder de ongebruikte 4 t/m 44).
    for code in (0, 1, 2, 3, 45, 48, 51, 53, 55, 56, 57, 61, 63, 65, 66, 67,
                 71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99):
        assert beschrijving(code), code


def test_formuleer_dag_echte_data():
    dag = parse_dagen(ECHT_DAILY)[0]
    assert formuleer_dag(dag, "Aartrijke", "Vandaag") == (
        "Vandaag wordt het in Aartrijke tussen 6°C en 11°C met motregen. "
        "Regenkans: 29%. Wind: tot 4 m/s (windstoten tot 6 m/s)."
    )


def test_formuleer_dag_zonder_regenkans_en_wind_laat_die_zinnen_weg():
    dag = maak_dag(regenkans=None, wind=None, vlagen=None)
    zin = formuleer_dag(dag, "Gent", "Morgen")
    assert zin == "Morgen wordt het in Gent tussen 6°C en 12°C met een bewolkte lucht."


def test_formuleer_dag_wind_zonder_windstoten():
    zin = formuleer_dag(maak_dag(vlagen=None), "Gent", "Morgen")
    assert "Wind: tot 4 m/s." in zin and "windstoten" not in zin


def test_formuleer_dag_regenkans_nul_wordt_gewoon_genoemd():
    assert "Regenkans: 0%." in formuleer_dag(maak_dag(regenkans=0), "Gent", "Morgen")


def test_formuleer_dag_onbekende_code_laat_het_weertype_weg():
    zin = formuleer_dag(maak_dag(code=None), "Gent", "Morgen")
    assert zin.startswith("Morgen wordt het in Gent tussen 6°C en 12°C.")


def test_formuleer_dag_gelijke_min_en_max_zegt_rond():
    zin = formuleer_dag(maak_dag(tmax=9.2, tmin=8.8), "Gent", "Morgen")
    assert "rond 9°C" in zin and "tussen" not in zin


def test_formuleer_dag_alleen_een_maximum():
    zin = formuleer_dag(maak_dag(tmin=None), "Gent", "Morgen")
    assert "rond 12°C" in zin


def test_formuleer_dag_zonder_temperatuur_geeft_none():
    assert formuleer_dag(maak_dag(tmax=None, tmin=None), "Gent", "Morgen") is None


# ---------------------------------------------------------------
# Labels en onzekerheid
# ---------------------------------------------------------------

@pytest.mark.parametrize("dagen,verwacht", [
    (0, "Vandaag"),
    (1, "Morgen"),
    (2, "Overmorgen"),
    (5, "Op vrijdag 23/10"),   # 18 oktober 2026 is een zondag
    (15, "Op maandag 02/11"),
])
def test_dag_label(dagen, verwacht):
    assert dag_label(VANDAAG + timedelta(days=dagen), VANDAAG) == verwacht


@pytest.mark.parametrize("dagen", [0, 1, 2, 3, 4])
def test_onzekerheid_tot_4_dagen_niets(dagen):
    assert onzekerheid_tekst(dagen) is None


@pytest.mark.parametrize("dagen,begin", [
    (5, "Kanttekening: dit is een verwachting van een weermodel"),
    (7, "Kanttekening: dit is een verwachting van een weermodel"),
    (8, "Kanttekening: dit ligt al ver weg"),
    (10, "Kanttekening: dit ligt al ver weg"),
    (11, "Kanttekening: dit ligt heel ver weg"),
    (15, "Kanttekening: dit ligt heel ver weg"),
])
def test_onzekerheid_wordt_groter_met_de_afstand(dagen, begin):
    assert onzekerheid_tekst(dagen).startswith(begin)


def test_onzekerheid_noemt_geen_verzonnen_percentages():
    for dagen in range(5, 16):
        assert "%" not in onzekerheid_tekst(dagen)


# ---------------------------------------------------------------
# Waarschuwingen
# ---------------------------------------------------------------

def test_waarschuwing_rustige_dag_geeft_none():
    assert dag_waarschuwing(maak_dag()) is None


@pytest.mark.parametrize("code,tekst", [
    (95, "onweer"), (96, "onweer"), (99, "onweer"),
    (96, "hagel"), (99, "hagel"),
    (71, "sneeuw"), (73, "sneeuw"), (75, "sneeuw"), (77, "sneeuw"), (85, "sneeuw"), (86, "sneeuw"),
    (45, "mist"), (48, "mist"),
    (56, "ijzel"), (57, "ijzel"), (66, "ijzel"), (67, "ijzel"),
])
def test_waarschuwing_per_weercode(code, tekst):
    w = dag_waarschuwing(maak_dag(code=code))
    assert w.startswith("Let op: ") and tekst in w


@pytest.mark.parametrize("code", [0, 1, 2, 3, 51, 61, 63, 80, 81])
def test_waarschuwing_gewone_regen_en_wolken_geven_niets(code):
    assert dag_waarschuwing(maak_dag(code=code)) is None


@pytest.mark.parametrize("wind,vlagen,verwacht", [
    (14.9, 19.9, False), (15.0, 7.0, True), (4.0, 20.0, True), (4.0, 19.9, False),
])
def test_waarschuwing_wind_drempels(wind, vlagen, verwacht):
    w = dag_waarschuwing(maak_dag(wind=wind, vlagen=vlagen))
    assert (w is not None and "harde wind" in w) is verwacht


@pytest.mark.parametrize("tmax,verwacht", [(26.9, False), (27.0, True), (31.0, True)])
def test_waarschuwing_hitte_drempel(tmax, verwacht):
    w = dag_waarschuwing(maak_dag(tmax=tmax, tmin=15.0))
    assert (w is not None and "erg warm" in w) is verwacht


def test_waarschuwing_meerdere_signalen_in_een_zin():
    w = dag_waarschuwing(maak_dag(code=95, wind=18.0))
    assert w == "Let op: er wordt onweer verwacht en er wordt harde wind verwacht."


def test_waarschuwing_vorst_met_regen_geeft_voor_een_hele_dag_geen_gladheid():
    # Bewust: voor een hele dag te grof (zie docstring). Alleen ijzel-codes tellen.
    assert dag_waarschuwing(maak_dag(code=61, tmin=-1.0, tmax=1.0, neerslag=3.0)) is None


def test_waarschuwing_overleeft_ontbrekende_waarden():
    leeg = maak_dag(code=None, tmax=None, tmin=None, wind=None, vlagen=None, regenkans=None)
    assert dag_waarschuwing(leeg) is None


# ---------------------------------------------------------------
# Ochtendsamenvatting
# ---------------------------------------------------------------

@pytest.mark.parametrize("uur,minuut,verwacht", [
    (5, 59, False), (6, 0, True), (9, 30, True), (11, 59, True), (12, 0, False), (23, 0, False),
])
def test_is_ochtend(uur, minuut, verwacht):
    assert is_ochtend(datetime(2026, 10, 18, uur, minuut)) is verwacht


def maak_uren(gevoel=7.0, kansen=None):
    """24 uren van vandaag. kansen = {uur: regenkans}."""
    kansen = kansen or {}
    return [
        Uur(datetime(2026, 10, 18, u), 8.0, gevoel, kansen.get(u, 10), 3)
        for u in range(24)
    ]


def test_kleding_temperatuur_gemiddelde_gevoelstemperatuur_overdag():
    uren = [
        Uur(datetime(2026, 10, 18, 3), 2.0, -5.0, 0, 3),   # 's nachts: telt niet mee
        Uur(datetime(2026, 10, 18, 8), 8.0, 4.0, 0, 3),
        Uur(datetime(2026, 10, 18, 18), 8.0, 8.0, 0, 3),   # 18:00 telt nog mee
        Uur(datetime(2026, 10, 18, 19), 8.0, 20.0, 0, 3),  # 19:00 niet meer
    ]
    assert kleding_temperatuur(maak_dag(), uren) == 6.0


def test_kleding_temperatuur_zonder_uren_gemiddelde_van_min_en_max():
    assert kleding_temperatuur(maak_dag(tmax=12.0, tmin=6.0), []) == 9.0


def test_kleding_temperatuur_uren_zonder_gevoel_vallen_terug_op_dag():
    uren = [Uur(datetime(2026, 10, 18, 9), 8.0, None, 0, 3)]
    assert kleding_temperatuur(maak_dag(tmax=12.0, tmin=6.0), uren) == 9.0


def test_kleding_temperatuur_alleen_maximum():
    assert kleding_temperatuur(maak_dag(tmax=12.0, tmin=None), []) == 12.0


def test_kleding_temperatuur_niets_geeft_none():
    assert kleding_temperatuur(maak_dag(tmax=None, tmin=None), []) is None


NU_OCHTEND = datetime(2026, 10, 18, 8, 0)


def test_regen_piek_kiest_het_uur_met_de_grootste_kans():
    uren = maak_uren(kansen={13: 45, 15: 70, 17: 60})
    assert regen_piek(uren, NU_OCHTEND) == (15, 70)


def test_regen_piek_onder_de_drempel_geeft_none():
    assert regen_piek(maak_uren(kansen={15: 39}), NU_OCHTEND) is None


def test_regen_piek_precies_op_de_drempel_telt():
    assert regen_piek(maak_uren(kansen={15: 40}), NU_OCHTEND) == (15, 40)


def test_regen_piek_bij_gelijke_kans_wint_het_vroegste_uur():
    assert regen_piek(maak_uren(kansen={12: 60, 16: 60}), NU_OCHTEND) == (12, 60)


def test_regen_piek_kijkt_niet_naar_uren_die_voorbij_zijn():
    uren = maak_uren(kansen={7: 90, 9: 50})
    assert regen_piek(uren, datetime(2026, 10, 18, 9, 0)) == (9, 50)
    assert regen_piek(maak_uren(kansen={8: 90}), datetime(2026, 10, 18, 9, 0)) is None


def test_regen_piek_kijkt_niet_naar_de_nacht():
    # Voor 07:00 en na 22:59 zegt Nova niets over regen.
    assert regen_piek(maak_uren(kansen={3: 95, 23: 95}), datetime(2026, 10, 18, 6, 0)) is None


def test_regen_piek_negeert_ontbrekende_kansen():
    uren = [Uur(datetime(2026, 10, 18, 15), 8.0, 7.0, None, 3)]
    assert regen_piek(uren, NU_OCHTEND) is None


def test_formuleer_ochtend_met_regenpiek():
    dag = parse_dagen(ECHT_DAILY)[0]
    uren = maak_uren(kansen={15: 70})
    zin = formuleer_ochtend(dag, uren, "Aartrijke", "Goedemorgen Kevin!", NU_OCHTEND)
    assert zin == (
        "Goedemorgen Kevin! Vandaag wordt het in Aartrijke tussen 6°C en 11°C met motregen. "
        "Regenkans: 29%. De kans op regen is het grootst rond 15 uur (70%)."
    )


def test_formuleer_ochtend_zonder_piek_noemt_geen_uur():
    dag = maak_dag(regenkans=10)
    zin = formuleer_ochtend(dag, maak_uren(), "Aartrijke", "Goedemorgen Kevin!", NU_OCHTEND)
    assert "Regenkans: 10%." in zin and "het grootst" not in zin


def test_formuleer_ochtend_zonder_uurgegevens_werkt_nog():
    zin = formuleer_ochtend(maak_dag(), [], "Aartrijke", "Goedemorgen Kevin!", NU_OCHTEND)
    assert zin.startswith("Goedemorgen Kevin! Vandaag wordt het in Aartrijke")


def test_formuleer_ochtend_noemt_wind_niet():
    # De windzin hoort bij de dagvoorspelling, niet bij de korte ochtendzin
    # (harde wind komt via dag_waarschuwing()).
    zin = formuleer_ochtend(maak_dag(), maak_uren(), "Aartrijke", "Goedemorgen Kevin!", NU_OCHTEND)
    assert "Wind:" not in zin


def test_formuleer_ochtend_zonder_temperatuur_geeft_none():
    dag = maak_dag(tmax=None, tmin=None)
    assert formuleer_ochtend(dag, [], "Aartrijke", "Goedemorgen Kevin!", NU_OCHTEND) is None


def test_alle_openingen_zijn_bruikbaar():
    assert len(forecast.OCHTEND_OPENINGEN) >= 2
    for opening in forecast.OCHTEND_OPENINGEN:
        zin = formuleer_ochtend(maak_dag(), [], "Aartrijke", opening, NU_OCHTEND)
        assert zin.startswith(opening)


# ---------------------------------------------------------------
# Instellingen en URL's
# ---------------------------------------------------------------

def test_max_dagen_past_bij_de_aanvraag_van_16_dagen():
    # Open-Meteo geeft vandaag + 15 dagen = 16. Verander je het ene getal,
    # dan moet je het andere ook aanpassen.
    assert forecast.MAX_DAGEN_VOORUIT == 15
    assert "forecast_days=16" in forecast.OPEN_METEO_DAG_URL


@pytest.mark.parametrize("url", [forecast.OPEN_METEO_DAG_URL, forecast.OPEN_METEO_OCHTEND_URL])
def test_urls_zijn_invulbaar_en_vragen_ms_en_brusselse_tijd(url):
    ingevuld = url.format(lat=51.1192, lon=3.0903)
    assert "latitude=51.1192" in ingevuld and "longitude=3.0903" in ingevuld
    assert "wind_speed_unit=ms" in ingevuld
    assert "timezone=Europe%2FBrussels" in ingevuld


def test_dag_url_vraagt_alle_velden_die_parse_dagen_leest():
    for veld in ("weather_code", "temperature_2m_max", "temperature_2m_min",
                 "precipitation_probability_max", "precipitation_sum",
                 "wind_speed_10m_max", "wind_gusts_10m_max"):
        assert veld in forecast.OPEN_METEO_DAG_URL
        assert veld in forecast.OPEN_METEO_OCHTEND_URL


def test_ochtend_url_vraagt_vandaag_per_uur():
    assert "forecast_days=1" in forecast.OPEN_METEO_OCHTEND_URL
    for veld in ("temperature_2m", "apparent_temperature",
                 "precipitation_probability", "weather_code"):
        assert veld in forecast.OPEN_METEO_OCHTEND_URL.split("&hourly=")[1]


def test_getalwoorden_dekken_1_tot_15():
    assert sorted(forecast.GETALWOORDEN.values()) == list(range(1, 16))


def test_weekdagnamen():
    assert forecast.WEEKDAG_NAMEN[0] == "maandag" and forecast.WEEKDAG_NAMEN[6] == "zondag"
    assert len(forecast.WEEKDAG_NAMEN) == 7


def test_ochtendvenster_is_logisch():
    assert 0 <= forecast.OCHTEND_VAN_UUR < forecast.OCHTEND_TOT_UUR <= 12