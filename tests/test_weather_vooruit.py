# tests/test_weather_vooruit.py
"""
pytest-tests voor de uitbreidingen van modules/weather/weather.py
(18 oktober 2026):

  1. "wat is het weer" noemt ook de regenradar en gladheid/wind straks
  3. voorspelling tot 15 dagen vooruit (Open-Meteo), met een eerlijke
     opmerking over de onzekerheid, plus nieuwe tijdsuitdrukkingen
     ("over 10 dagen", "over twee weken", "volgende week woensdag")
  4. de ochtendsamenvatting (check_ochtend_samenvatting)

Risico-afweging: het gewone weerbericht is wat Kevin het vaakst gebruikt. Een
nieuwe bron mag dat nooit kapot maken (alle fouten worden afgevangen en de
oude zin blijft gewoon werken), en de ochtendsamenvatting mag nooit twee keer
op één dag komen, nooit buiten de ochtend, en nooit als Kevin er niet is.
Dat is precies wat hier getest wordt, naast de tijdsuitdrukkingen waar een
verkeerd getal stilletjes het weer van de verkeerde dag oplevert.

Geen netwerk, geen echte data/-bestanden: requests.get is vervangen door een
nep-versie en alle bestanden gaan naar tmp_path.
"""

import json
from datetime import date, datetime, timedelta

import pytest

from modules.weather import forecast, rain, weather
from modules.weather.weather import WeatherModule

# 18 oktober 2026 is een zondag.
ZONDAG = datetime(2026, 10, 18, 12, 0)
MAANDAG = datetime(2026, 10, 19, 12, 0)
NU = datetime(2026, 10, 19, 8, 30)  # maandagochtend, voor de ochtendtests


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


def vaste_datum(monkeypatch, nu):
    """Laat weather.py denken dat het 'nu' is (voor de weekdag-berekening)."""
    class VasteTijd(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(nu.year, nu.month, nu.day, nu.hour, nu.minute)

    monkeypatch.setattr(weather, "datetime", VasteTijd)
    monkeypatch.setattr(forecast, "vandaag_lokaal", lambda: nu.date())


@pytest.fixture
def bus():
    return DummyEventBus()


@pytest.fixture
def wm(bus, tmp_path):
    w = WeatherModule(bus, api_key="dummy")
    # Nooit naar de echte data/-map schrijven.
    w.history_path = tmp_path / "data" / "weather_history.json"
    return w


def maak_daily(eerste_dag=date(2026, 10, 18), aantal=16, afwijkend=None):
    """Open-Meteo 'daily'-antwoord met rustig weer. afwijkend = {dag_index: {veld: waarde}}."""
    afwijkend = afwijkend or {}
    velden = {
        "weather_code": 3, "temperature_2m_max": 12.0, "temperature_2m_min": 6.0,
        "precipitation_probability_max": 20, "precipitation_sum": 0.0,
        "wind_speed_10m_max": 4.0, "wind_gusts_10m_max": 7.0,
    }
    daily = {"time": [(eerste_dag + timedelta(days=i)).isoformat() for i in range(aantal)]}
    for veld, standaard in velden.items():
        daily[veld] = [afwijkend.get(i, {}).get(veld, standaard) for i in range(aantal)]
    return {"daily": daily}


def maak_hourly(dag=date(2026, 10, 19), gevoel=7.0, kansen=None):
    kansen = kansen or {}
    return {"hourly": {
        "time": [datetime(dag.year, dag.month, dag.day, u).strftime("%Y-%m-%dT%H:%M") for u in range(24)],
        "temperature_2m": [8.0] * 24,
        "apparent_temperature": [gevoel] * 24,
        "precipitation_probability": [kansen.get(u, 10) for u in range(24)],
        "weather_code": [3] * 24,
    }}


def maak_ochtend_json(dag=date(2026, 10, 19), gevoel=7.0, kansen=None, afwijkend=None):
    data = maak_daily(eerste_dag=dag, aantal=1, afwijkend={0: (afwijkend or {})})
    data.update(maak_hourly(dag, gevoel=gevoel, kansen=kansen))
    return data


OWM_NU = {
    "cod": 200,
    "coord": {"lon": 3.0903, "lat": 51.1192},
    "main": {"temp": 9.0, "feels_like": 7.0, "humidity": 80},
    "weather": [{"id": 500, "main": "Rain", "description": "lichte regen"}],
    "wind": {"speed": 4.0},
    "sys": {"sunrise": 1781000000, "sunset": 1781040000},
}


class NepNet:
    """Vervangt requests.get (voor weather.py ÉN rain.py: het is hetzelfde
    requests-pakket). Elke bron is een FakeResponse of een Exception.
    Niet ingestelde bronnen geven een 404. 'urls' onthoudt wat er gevraagd is."""

    def __init__(self):
        self.urls = []
        self.bronnen = {}

    def zet(self, naam, antwoord):
        self.bronnen[naam] = antwoord
        return self

    def installeer(self, monkeypatch):
        monkeypatch.setattr(weather.requests, "get", self._get)
        return self

    def _soort(self, url):
        if "buienradar" in url:
            return "buienradar"
        if "minutely_15=temperature_2m" in url:
            return "gevaar"
        if "minutely_15=rain,snowfall,weather_code" in url:
            return "type"
        if "minutely_15=precipitation&" in url:
            return "open_meteo_regen"
        if "hourly=" in url:
            return "ochtend"
        if "daily=" in url:
            return "dag"
        if "geo/1.0/direct" in url:
            return "geocode"
        if "data/2.5/weather" in url:
            return "owm_nu"
        if "data/2.5/forecast" in url:
            return "owm_voorspelling"
        return "onbekend"

    def _get(self, url, timeout=None):
        self.urls.append(url)
        antwoord = self.bronnen.get(self._soort(url), FakeResponse(status_code=404))
        if isinstance(antwoord, Exception):
            raise antwoord
        return antwoord

    def vroeg_om(self, naam):
        return any(self._soort(u) == naam for u in self.urls)


def droge_radar():
    return FakeResponse(text="\n".join(f"000|{(NU + timedelta(minutes=5 * i)):%H:%M}" for i in range(24)))


def regen_radar_over_20_min():
    waarden = [0, 0, 0, 0, 100, 100, 100, 100] + [0] * 16
    return FakeResponse(text="\n".join(
        f"{w:03d}|{(NU + timedelta(minutes=5 * i)):%H:%M}" for i, w in enumerate(waarden)
    ))


def rustig_gevaar(start=NU):
    return FakeResponse(json_data={"minutely_15": {
        "time": [(start + timedelta(minutes=15 * i)).strftime("%Y-%m-%dT%H:%M") for i in range(12)],
        "temperature_2m": [8.0] * 12, "precipitation": [0.0] * 12,
        "wind_speed_10m": [3.0] * 12, "wind_gusts_10m": [5.0] * 12,
    }})


# ---------------------------------------------------------------
# Tijdsuitdrukkingen
# ---------------------------------------------------------------

@pytest.mark.parametrize("tekst,verwacht", [
    ("wat is het weer over 10 dagen", 10),
    ("weer over 3 dagen", 3),
    ("weer over 1 dag", 1),
    ("weer over drie dagen", 3),
    ("weer over een dag", 1),
    ("weer over een week", 7),
    ("weer over 2 weken", 14),
    ("wat is het weer over twee weken in gent", 14),
    ("weer over vijftien dagen", 15),
    ("weer over 20 dagen", 20),
    ("weer volgende week", 7),
])
def test_relatieve_dagen(wm, tekst, verwacht):
    assert wm.extract_day_offset(tekst) == verwacht


@pytest.mark.parametrize("tekst,verwacht", [
    # vandaag is zondag
    ("weer volgende week maandag", 1),
    ("weer volgende week woensdag", 3),
    ("weer volgende week zondag", 7),
])
def test_volgende_week_op_een_zondag(wm, monkeypatch, tekst, verwacht):
    vaste_datum(monkeypatch, ZONDAG)
    assert wm.extract_day_offset(tekst) == verwacht


@pytest.mark.parametrize("tekst,verwacht", [
    # vandaag is maandag
    ("weer volgende week maandag", 7),
    ("weer volgende week dinsdag", 8),
    ("weer volgende week zondag", 13),
])
def test_volgende_week_op_een_maandag(wm, monkeypatch, tekst, verwacht):
    vaste_datum(monkeypatch, MAANDAG)
    assert wm.extract_day_offset(tekst) == verwacht


def test_volgende_week_is_nooit_vandaag_of_deze_week(wm, monkeypatch):
    # Op elke dag van de week moet "volgende week <dag>" tussen 1 en 13 vallen.
    for dag in range(7):
        vaste_datum(monkeypatch, datetime(2026, 10, 19 + dag, 12, 0))
        for naam in forecast.WEEKDAG_NAMEN:
            assert 1 <= wm.extract_day_offset(f"weer volgende week {naam}") <= 13


@pytest.mark.parametrize("tekst,verwacht", [
    ("hoe is het weer", 0),
    ("weer vandaag", 0),
    ("weer morgen", 1),
    ("weer overmorgen", 2),
    ("over mijn dagen praten", 0),
    ("weer over blabla dagen", 0),
])
def test_bestaande_uitdrukkingen_blijven_werken(wm, tekst, verwacht):
    assert wm.extract_day_offset(tekst) == verwacht


def test_weekdag_blijft_de_eerstvolgende_en_nooit_vandaag(wm, monkeypatch):
    vaste_datum(monkeypatch, ZONDAG)
    assert wm.extract_day_offset("weer op zaterdag") == 6
    assert wm.extract_day_offset("weer op zondag") == 7


# ---------------------------------------------------------------
# get_forecast(): routering naar de lange voorspelling
# ---------------------------------------------------------------

def test_vier_dagen_vooruit_gebruikt_nog_openweathermap(wm, monkeypatch):
    net = NepNet().zet("owm_voorspelling", FakeResponse(json_data={"cod": "404"})).installeer(monkeypatch)
    assert wm.get_forecast("aartrijke", 4) is None
    assert net.vroeg_om("owm_voorspelling") and not net.vroeg_om("dag")


def test_vijf_dagen_vooruit_gebruikt_open_meteo(wm, monkeypatch):
    vaste_datum(monkeypatch, ZONDAG)
    net = NepNet().zet("dag", FakeResponse(json_data=maak_daily())).installeer(monkeypatch)
    zin = wm.get_forecast("aartrijke", 5)
    assert zin.startswith("Op vrijdag 23/10 wordt het in Aartrijke")
    assert net.vroeg_om("dag") and not net.vroeg_om("owm_voorspelling")


def test_oude_grens_van_5_dagen_bestaat_niet_meer(wm, monkeypatch):
    vaste_datum(monkeypatch, ZONDAG)
    NepNet().zet("dag", FakeResponse(json_data=maak_daily())).installeer(monkeypatch)
    assert "maximaal 5 dagen" not in wm.get_forecast("aartrijke", 6)


def test_lange_voorspelling_werkt_zonder_api_sleutel_voor_aartrijke(bus, tmp_path, monkeypatch):
    # Open-Meteo heeft geen sleutel nodig, en Aartrijke kent zijn coördinaten.
    vaste_datum(monkeypatch, ZONDAG)
    w = WeatherModule(bus, api_key=None)
    w.history_path = tmp_path / "h.json"
    NepNet().zet("dag", FakeResponse(json_data=maak_daily())).installeer(monkeypatch)
    zin = w.get_forecast("aartrijke", 6)
    assert "Geen API-sleutel" not in zin and "wordt het in Aartrijke" in zin


# ---------------------------------------------------------------
# get_forecast_lang()
# ---------------------------------------------------------------

def test_lang_inhoud_van_de_zin(wm, monkeypatch):
    vaste_datum(monkeypatch, ZONDAG)
    daily = maak_daily(afwijkend={6: {"weather_code": 61, "temperature_2m_max": 14.0,
                                      "temperature_2m_min": 9.0,
                                      "precipitation_probability_max": 80}})
    NepNet().zet("dag", FakeResponse(json_data=daily)).installeer(monkeypatch)
    zin = wm.get_forecast_lang("aartrijke", 6)
    assert zin.startswith("Op zaterdag 24/10 wordt het in Aartrijke tussen 9°C en 14°C met lichte regen.")
    assert "Regenkans: 80%." in zin
    assert "Wind: tot 4 m/s (windstoten tot 7 m/s)." in zin


def test_lang_kledingadvies_komt_uit_de_bestaande_sjablonen(wm, monkeypatch):
    vaste_datum(monkeypatch, ZONDAG)
    # min 6 en max 12: gemiddelde 9 = "fris"
    NepNet().zet("dag", FakeResponse(json_data=maak_daily())).installeer(monkeypatch)
    zin = wm.get_forecast_lang("aartrijke", 6)
    assert any(s in zin for s in wm._sjablonen_kledingadvies["fris"])


def test_lang_kledingadvies_warm(wm, monkeypatch):
    vaste_datum(monkeypatch, ZONDAG)
    daily = maak_daily(afwijkend={6: {"temperature_2m_max": 31.0, "temperature_2m_min": 22.0}})
    NepNet().zet("dag", FakeResponse(json_data=daily)).installeer(monkeypatch)
    zin = wm.get_forecast_lang("aartrijke", 6)
    assert any(s in zin for s in wm._sjablonen_kledingadvies["warm"])
    assert "Let op: het wordt erg warm." in zin


def test_lang_waarschuwing_bij_onweer(wm, monkeypatch):
    vaste_datum(monkeypatch, ZONDAG)
    NepNet().zet("dag", FakeResponse(json_data=maak_daily(afwijkend={7: {"weather_code": 95}}))).installeer(monkeypatch)
    assert "Let op: er wordt onweer verwacht." in wm.get_forecast_lang("aartrijke", 7)


@pytest.mark.parametrize("dagen,tekst", [
    (5, "De grote lijn klopt meestal"),
    (7, "De grote lijn klopt meestal"),
    (8, "Zie het als een trend"),
    (10, "Zie het als een trend"),
    (11, "De onzekerheid is groot"),
    (15, "De onzekerheid is groot"),
])
def test_lang_zegt_er_eerlijk_bij_dat_het_onzekerder_wordt(wm, monkeypatch, dagen, tekst):
    vaste_datum(monkeypatch, ZONDAG)
    NepNet().zet("dag", FakeResponse(json_data=maak_daily())).installeer(monkeypatch)
    assert tekst in wm.get_forecast_lang("aartrijke", dagen)


def test_lang_verder_dan_15_dagen_vraagt_niets_op(wm, monkeypatch):
    net = NepNet().installeer(monkeypatch)
    zin = wm.get_forecast_lang("aartrijke", 16)
    assert zin.startswith("Verder dan 15 dagen vooruit kan ik niet kijken")
    assert net.urls == []


def test_lang_precies_15_dagen_is_nog_toegestaan(wm, monkeypatch):
    vaste_datum(monkeypatch, ZONDAG)
    NepNet().zet("dag", FakeResponse(json_data=maak_daily())).installeer(monkeypatch)
    zin = wm.get_forecast_lang("aartrijke", 15)
    assert "Op maandag 02/11 wordt het" in zin


@pytest.mark.parametrize("antwoord", [
    ConnectionError("geen verbinding"),
    FakeResponse(status_code=500),
    FakeResponse(json_data={"error": True, "reason": "kapot"}),
])
def test_lang_bron_onbereikbaar_of_kapot(wm, monkeypatch, antwoord):
    vaste_datum(monkeypatch, ZONDAG)
    NepNet().zet("dag", antwoord).installeer(monkeypatch)
    zin = wm.get_forecast_lang("aartrijke", 6)
    # Bron weg = None (on_weather zegt dan "Ik kon het weer niet ophalen");
    # leeg antwoord = nette melding. Nooit een crash.
    assert zin is None or "geen voorspelling" in zin


def test_lang_dag_ontbreekt_in_het_antwoord(wm, monkeypatch):
    vaste_datum(monkeypatch, ZONDAG)
    NepNet().zet("dag", FakeResponse(json_data=maak_daily(aantal=3))).installeer(monkeypatch)
    assert "geen voorspelling gevonden voor Aartrijke" in wm.get_forecast_lang("aartrijke", 6)


def test_lang_dag_zonder_temperatuur(wm, monkeypatch):
    vaste_datum(monkeypatch, ZONDAG)
    daily = maak_daily(afwijkend={6: {"temperature_2m_max": None, "temperature_2m_min": None}})
    NepNet().zet("dag", FakeResponse(json_data=daily)).installeer(monkeypatch)
    assert "geen voorspelling gevonden" in wm.get_forecast_lang("aartrijke", 6)


def test_lang_regenkans_ontbreekt_ver_weg(wm, monkeypatch):
    vaste_datum(monkeypatch, ZONDAG)
    daily = maak_daily(afwijkend={14: {"precipitation_probability_max": None}})
    NepNet().zet("dag", FakeResponse(json_data=daily)).installeer(monkeypatch)
    zin = wm.get_forecast_lang("aartrijke", 14)
    assert "Regenkans" not in zin and "wordt het in Aartrijke" in zin


def test_lang_andere_stad_zoekt_coordinaten_op(wm, monkeypatch):
    vaste_datum(monkeypatch, ZONDAG)
    net = (NepNet()
           .zet("geocode", FakeResponse(json_data=[{"lat": 51.05, "lon": 3.72}]))
           .zet("dag", FakeResponse(json_data=maak_daily()))
           .installeer(monkeypatch))
    zin = wm.get_forecast_lang("gent", 6)
    assert "wordt het in Gent" in zin
    dag_url = [u for u in net.urls if "daily=" in u][0]
    assert "latitude=51.0500" in dag_url and "longitude=3.7200" in dag_url


def test_lang_onbekende_stad_geeft_none(wm, monkeypatch):
    vaste_datum(monkeypatch, ZONDAG)
    net = NepNet().zet("geocode", FakeResponse(json_data=[])).installeer(monkeypatch)
    assert wm.get_forecast_lang("nergensdorp", 6) is None
    assert not net.vroeg_om("dag")


def test_lang_onbekende_stad_zonder_api_sleutel_geeft_none(bus, tmp_path, monkeypatch):
    w = WeatherModule(bus, api_key=None)
    w.history_path = tmp_path / "h.json"
    net = NepNet().installeer(monkeypatch)
    assert w.get_forecast_lang("gent", 6) is None
    assert net.urls == []


def test_on_weather_over_10_dagen_volledige_keten(wm, bus, monkeypatch):
    vaste_datum(monkeypatch, ZONDAG)
    NepNet().zet("dag", FakeResponse(json_data=maak_daily())).installeer(monkeypatch)
    wm.on_weather({"text": "wat is het weer over 10 dagen"})
    event, data = bus.gepubliceerd[0]
    assert event == "layer4_response"
    assert data["text"].startswith("Op woensdag 28/10 wordt het in Aartrijke")
    assert "Zie het als een trend" in data["text"]


def test_on_weather_lange_voorspelling_kapot_geeft_nette_melding(wm, bus, monkeypatch):
    vaste_datum(monkeypatch, ZONDAG)
    NepNet().zet("dag", ConnectionError("weg")).installeer(monkeypatch)
    wm.on_weather({"text": "weer over 10 dagen"})
    assert bus.gepubliceerd[0][1]["text"] == "Ik kon het weer voor Aartrijke niet ophalen."


# ---------------------------------------------------------------
# get_weather(): radarzin erbij
# ---------------------------------------------------------------

def test_weer_noemt_de_regen_die_eraan_komt(wm, monkeypatch):
    monkeypatch.setattr(rain, "nu_lokaal", lambda: NU)
    NepNet().zet("owm_nu", FakeResponse(json_data=OWM_NU)) \
            .zet("buienradar", regen_radar_over_20_min()) \
            .zet("gevaar", rustig_gevaar()).installeer(monkeypatch)
    zin = wm.get_weather("aartrijke")
    assert zin.startswith("In aartrijke is het momenteel 9.0°C met lichte regen.")
    assert "Over ongeveer 20 minuten begint het te regenen (lichte regen)." in zin


def test_weer_radarzin_staat_na_de_waarschuwing_en_voor_de_vergelijking_met_gisteren(wm, monkeypatch):
    monkeypatch.setattr(rain, "nu_lokaal", lambda: NU)
    # gisteren was het 5 graden: "4°C warmer dan gisteren"
    gisteren = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    wm.history_path.parent.mkdir(parents=True)
    wm.history_path.write_text(json.dumps({"aartrijke": {"datum": gisteren, "temp": 5.0}}))
    owm = dict(OWM_NU, weather=[{"id": 211, "main": "Thunderstorm", "description": "onweer"}])
    NepNet().zet("owm_nu", FakeResponse(json_data=owm)) \
            .zet("buienradar", regen_radar_over_20_min()) \
            .zet("gevaar", rustig_gevaar()).installeer(monkeypatch)
    zin = wm.get_weather("aartrijke")
    i_waarschuwing = zin.index("Let op: er wordt onweer verwacht.")
    i_radar = zin.index("Over ongeveer 20 minuten")
    i_gisteren = zin.index("warmer dan gisteren")
    assert i_waarschuwing < i_radar < i_gisteren


def test_weer_droog_en_rustig_voegt_niets_toe(wm, monkeypatch):
    monkeypatch.setattr(rain, "nu_lokaal", lambda: NU)
    owm = dict(OWM_NU, weather=[{"id": 800, "main": "Clear", "description": "onbewolkt"}])
    NepNet().zet("owm_nu", FakeResponse(json_data=owm)) \
            .zet("buienradar", droge_radar()) \
            .zet("gevaar", rustig_gevaar()).installeer(monkeypatch)
    zin = wm.get_weather("aartrijke")
    assert "regenen" not in zin and "Straks" not in zin
    assert zin.startswith("In aartrijke is het momenteel 9.0°C met onbewolkt.")


def test_weer_zonder_coordinaten_vraagt_de_radar_niet_op(wm, monkeypatch):
    zonder = {k: v for k, v in OWM_NU.items() if k != "coord"}
    net = NepNet().zet("owm_nu", FakeResponse(json_data=zonder)).installeer(monkeypatch)
    zin = wm.get_weather("aartrijke")
    assert zin.startswith("In aartrijke is het momenteel")
    assert not net.vroeg_om("buienradar") and not net.vroeg_om("gevaar")


def test_weer_radar_en_gladheid_kapot_gewoon_weerbericht_blijft(wm, monkeypatch):
    NepNet().zet("owm_nu", FakeResponse(json_data=OWM_NU)) \
            .zet("buienradar", ConnectionError("weg")) \
            .zet("gevaar", ConnectionError("weg")).installeer(monkeypatch)
    zin = wm.get_weather("aartrijke")
    assert zin.startswith("In aartrijke is het momenteel 9.0°C met lichte regen.")
    assert "Over ongeveer" not in zin


def test_weer_fout_in_de_vooruitblik_breekt_het_weerbericht_niet(wm, monkeypatch):
    def kapot(*args, **kwargs):
        raise RuntimeError("kunstmatige testfout")

    monkeypatch.setattr(rain, "weer_vooruit_zin", kapot)
    NepNet().zet("owm_nu", FakeResponse(json_data=OWM_NU)).installeer(monkeypatch)
    assert wm.get_weather("aartrijke").startswith("In aartrijke is het momenteel")


def test_weer_noemt_gladheid_straks(wm, monkeypatch):
    monkeypatch.setattr(rain, "nu_lokaal", lambda: NU)
    owm = dict(OWM_NU, weather=[{"id": 800, "main": "Clear", "description": "onbewolkt"}])
    glad = FakeResponse(json_data={"minutely_15": {
        "time": [(NU + timedelta(minutes=15 * i)).strftime("%Y-%m-%dT%H:%M") for i in range(8)],
        "temperature_2m": [6.0, 6.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
        "precipitation": [0.0, 0.0, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3],
        "wind_speed_10m": [3.0] * 8, "wind_gusts_10m": [5.0] * 8,
    }})
    NepNet().zet("owm_nu", FakeResponse(json_data=owm)) \
            .zet("buienradar", droge_radar()).zet("gevaar", glad).installeer(monkeypatch)
    zin = wm.get_weather("aartrijke")
    assert "Straks: kans op gladheid over ongeveer 30 minuten (rond 1°C met neerslag)." in zin


def test_weer_bewaart_nog_steeds_de_temperatuur_voor_morgen(wm, monkeypatch):
    NepNet().zet("owm_nu", FakeResponse(json_data=OWM_NU)).installeer(monkeypatch)
    wm.get_weather("aartrijke")
    opgeslagen = json.loads(wm.history_path.read_text())
    assert opgeslagen["aartrijke"]["temp"] == 9.0


# ---------------------------------------------------------------
# Ochtendsamenvatting
# ---------------------------------------------------------------

def net_voor_ochtend(monkeypatch, **bronnen):
    """Standaard: rustige dag, droge radar, rustig gevaar."""
    net = NepNet()
    net.zet("ochtend", FakeResponse(json_data=maak_ochtend_json()))
    net.zet("buienradar", droge_radar())
    net.zet("gevaar", rustig_gevaar())
    for naam, antwoord in bronnen.items():
        net.zet(naam, antwoord)
    return net.installeer(monkeypatch)


def test_ochtend_publiceert_een_samenvatting(wm, bus, monkeypatch):
    net_voor_ochtend(monkeypatch)
    tekst = wm.check_ochtend_samenvatting(nu=NU)
    assert tekst is not None
    assert bus.gepubliceerd == [("layer4_response", {"text": tekst})]
    assert any(tekst.startswith(o) for o in forecast.OCHTEND_OPENINGEN)
    assert "Vandaag wordt het in Aartrijke tussen 6°C en 12°C met een bewolkte lucht." in tekst
    assert "Regenkans: 20%." in tekst
    # gevoelstemperatuur 7 graden = "koud"
    assert any(s in tekst for s in wm._sjablonen_kledingadvies["koud"])


def test_ochtend_noemt_regen_die_eraan_komt(wm, monkeypatch):
    monkeypatch.setattr(rain, "nu_lokaal", lambda: NU)
    net_voor_ochtend(monkeypatch, buienradar=regen_radar_over_20_min())
    tekst = wm.check_ochtend_samenvatting(nu=NU)
    assert "Over ongeveer 20 minuten begint het te regenen" in tekst


def test_ochtend_noemt_het_piekuur_van_de_regen(wm, monkeypatch):
    net_voor_ochtend(monkeypatch, ochtend=FakeResponse(json_data=maak_ochtend_json(kansen={15: 70})))
    assert "De kans op regen is het grootst rond 15 uur (70%)." in wm.check_ochtend_samenvatting(nu=NU)


def test_ochtend_noemt_gladheid_die_er_nu_al_is(wm, monkeypatch):
    # De ochtendsamenvatting haalt het huidige weer niet apart op, dus
    # gladheid van dit moment moet er uit de kwartierdata in komen.
    monkeypatch.setattr(rain, "nu_lokaal", lambda: NU)
    glad_nu = FakeResponse(json_data={"minutely_15": {
        "time": [(NU - timedelta(minutes=15) + timedelta(minutes=15 * i)).strftime("%Y-%m-%dT%H:%M") for i in range(6)],
        "temperature_2m": [1.0] * 6, "precipitation": [0.3] * 6,
        "wind_speed_10m": [3.0] * 6, "wind_gusts_10m": [5.0] * 6,
    }})
    net_voor_ochtend(monkeypatch, gevaar=glad_nu)
    tekst = wm.check_ochtend_samenvatting(nu=NU)
    assert "Let op: kans op gladheid nu" in tekst


def test_ochtend_waarschuwing_bij_onweer(wm, monkeypatch):
    data = maak_ochtend_json(afwijkend={"weather_code": 95})
    net_voor_ochtend(monkeypatch, ochtend=FakeResponse(json_data=data))
    assert "Let op: er wordt onweer verwacht." in wm.check_ochtend_samenvatting(nu=NU)


def test_ochtend_kledingadvies_volgt_de_gevoelstemperatuur(wm, monkeypatch):
    data = maak_ochtend_json(gevoel=-2.0)
    net_voor_ochtend(monkeypatch, ochtend=FakeResponse(json_data=data))
    tekst = wm.check_ochtend_samenvatting(nu=NU)
    assert any(s in tekst for s in wm._sjablonen_kledingadvies["vriezend"])


def test_ochtend_komt_maar_een_keer_per_dag(wm, bus, monkeypatch):
    net_voor_ochtend(monkeypatch)
    assert wm.check_ochtend_samenvatting(nu=NU) is not None
    assert wm.check_ochtend_samenvatting(nu=NU + timedelta(minutes=5)) is None
    assert wm.check_ochtend_samenvatting(nu=NU + timedelta(hours=2)) is None
    assert len(bus.gepubliceerd) == 1


def test_ochtend_onthoudt_het_ook_na_een_herstart(wm, bus, tmp_path, monkeypatch):
    net_voor_ochtend(monkeypatch)
    wm.check_ochtend_samenvatting(nu=NU)

    nieuw = WeatherModule(bus, api_key="dummy")  # Nova herstart
    nieuw.history_path = wm.history_path
    assert nieuw.check_ochtend_samenvatting(nu=NU + timedelta(minutes=30)) is None
    assert len(bus.gepubliceerd) == 1


def test_ochtend_bewaart_de_datum_in_een_apart_bestand(wm, monkeypatch):
    net_voor_ochtend(monkeypatch)
    wm.check_ochtend_samenvatting(nu=NU)
    pad = wm.history_path.parent / "weather_ochtend.json"
    assert json.loads(pad.read_text()) == {"laatste_datum": "2026-10-19"}
    # De bestaande geschiedenis (temperaturen, waarschuwingen) blijft ongemoeid.
    assert not wm.history_path.exists()


def test_ochtend_volgende_dag_komt_weer(wm, bus, monkeypatch):
    net_voor_ochtend(monkeypatch)
    wm.check_ochtend_samenvatting(nu=NU)
    net_voor_ochtend(monkeypatch, ochtend=FakeResponse(json_data=maak_ochtend_json(dag=date(2026, 10, 20))))
    assert wm.check_ochtend_samenvatting(nu=NU + timedelta(days=1)) is not None
    assert len(bus.gepubliceerd) == 2


@pytest.mark.parametrize("uur,minuut", [(5, 59), (12, 0), (14, 30), (23, 0), (0, 0)])
def test_ochtend_buiten_het_ochtendvenster_gebeurt_niets(wm, bus, monkeypatch, uur, minuut):
    net = net_voor_ochtend(monkeypatch)
    nu = NU.replace(hour=uur, minute=minuut)
    assert wm.check_ochtend_samenvatting(nu=nu) is None
    assert net.urls == [] and bus.gepubliceerd == []


@pytest.mark.parametrize("uur,minuut", [(6, 0), (9, 15), (11, 59)])
def test_ochtend_binnen_het_ochtendvenster_komt_ze(wm, monkeypatch, uur, minuut):
    net_voor_ochtend(monkeypatch)
    assert wm.check_ochtend_samenvatting(nu=NU.replace(hour=uur, minute=minuut)) is not None


def test_ochtend_wacht_tot_kevin_er_is(wm, bus, monkeypatch):
    net = net_voor_ochtend(monkeypatch)
    aanwezig = {"ja": False}
    assert wm.check_ochtend_samenvatting(mag_spreken=lambda: aanwezig["ja"], nu=NU) is None
    assert net.urls == [] and bus.gepubliceerd == []  # niets opgehaald, niets gezegd
    # Een uur later is Kevin er wel: nu komt ze alsnog (nog binnen de ochtend)
    aanwezig["ja"] = True
    assert wm.check_ochtend_samenvatting(mag_spreken=lambda: aanwezig["ja"], nu=NU + timedelta(hours=1)) is not None
    assert len(bus.gepubliceerd) == 1


def test_ochtend_vraagt_aan_layer5_pas_als_de_rest_klopt(wm, monkeypatch):
    # Buiten de ochtend en na een geslaagde samenvatting mag mag_spreken()
    # niet eens meer aangeroepen worden (Layer 5 is er niet gratis voor).
    net_voor_ochtend(monkeypatch)
    aanroepen = []

    def mag():
        aanroepen.append(1)
        return True

    wm.check_ochtend_samenvatting(mag_spreken=mag, nu=NU.replace(hour=15))
    assert aanroepen == []
    wm.check_ochtend_samenvatting(mag_spreken=mag, nu=NU)
    assert len(aanroepen) == 1
    wm.check_ochtend_samenvatting(mag_spreken=mag, nu=NU + timedelta(minutes=10))
    assert len(aanroepen) == 1  # vandaag al gedaan


def test_ochtend_zonder_mag_spreken_functie_mag_gewoon(wm, monkeypatch):
    net_voor_ochtend(monkeypatch)
    assert wm.check_ochtend_samenvatting(mag_spreken=None, nu=NU) is not None


def test_ochtend_fout_in_mag_spreken_zwijgt_en_crasht_niet(wm, bus, monkeypatch, capsys):
    net_voor_ochtend(monkeypatch)

    def kapot():
        raise RuntimeError("kunstmatige testfout")

    assert wm.check_ochtend_samenvatting(mag_spreken=kapot, nu=NU) is None
    assert bus.gepubliceerd == []
    assert "ochtendsamenvatting mislukt" in capsys.readouterr().out
    # En het mag later gewoon opnieuw
    assert wm.check_ochtend_samenvatting(mag_spreken=lambda: True, nu=NU + timedelta(minutes=5)) is not None


def test_ochtend_bron_onbereikbaar_probeert_het_later_opnieuw(wm, bus, monkeypatch):
    net_voor_ochtend(monkeypatch, ochtend=ConnectionError("weg"))
    assert wm.check_ochtend_samenvatting(nu=NU) is None
    assert bus.gepubliceerd == []
    assert not (wm.history_path.parent / "weather_ochtend.json").exists()

    # Binnen 15 minuten opnieuw proberen? Nee: niet bij elke controle bellen.
    net = net_voor_ochtend(monkeypatch)
    assert wm.check_ochtend_samenvatting(nu=NU + timedelta(minutes=10)) is None
    assert net.urls == []

    # Na 15 minuten wel, en nu lukt het
    assert wm.check_ochtend_samenvatting(nu=NU + timedelta(minutes=15)) is not None
    assert len(bus.gepubliceerd) == 1


@pytest.mark.parametrize("kapot", [
    FakeResponse(status_code=500),
    FakeResponse(json_data={}),
    FakeResponse(json_data={"daily": {"time": []}}),
])
def test_ochtend_onbruikbaar_antwoord_zegt_niets(wm, bus, monkeypatch, kapot):
    net_voor_ochtend(monkeypatch, ochtend=kapot)
    assert wm.check_ochtend_samenvatting(nu=NU) is None
    assert bus.gepubliceerd == []


def test_ochtend_dag_zonder_temperatuur_zegt_niets(wm, bus, monkeypatch):
    data = maak_ochtend_json(afwijkend={"temperature_2m_max": None, "temperature_2m_min": None})
    net_voor_ochtend(monkeypatch, ochtend=FakeResponse(json_data=data))
    assert wm.check_ochtend_samenvatting(nu=NU) is None
    assert bus.gepubliceerd == []


def test_ochtend_radar_kapot_samenvatting_komt_toch(wm, monkeypatch):
    net_voor_ochtend(monkeypatch, buienradar=ConnectionError("weg"), gevaar=ConnectionError("weg"))
    tekst = wm.check_ochtend_samenvatting(nu=NU)
    assert tekst is not None and "Vandaag wordt het" in tekst


def test_ochtend_onbekende_standaardstad_zegt_niets(bus, tmp_path, monkeypatch):
    w = WeatherModule(bus, api_key=None, default_city="Nergensdorp")
    w.history_path = tmp_path / "h.json"
    net = net_voor_ochtend(monkeypatch)
    assert w.check_ochtend_samenvatting(nu=NU) is None
    assert net.urls == [] and bus.gepubliceerd == []


def test_ochtend_opslaan_mislukt_dan_toch_maar_een_keer_per_proces(wm, bus, tmp_path, monkeypatch):
    # De map waar het bestandje heen moet bestaat niet en kan niet gemaakt
    # worden (er staat een gewoon bestand op die plek).
    blokkade = tmp_path / "blokkade"
    blokkade.write_text("ik ben een bestand, geen map")
    wm.history_path = blokkade / "data" / "weather_history.json"
    net_voor_ochtend(monkeypatch)
    assert wm.check_ochtend_samenvatting(nu=NU) is not None
    # Meer dan 15 minuten later, zodat enkel het "vandaag al gedaan"-geheugen
    # in het proces (en niet de wachttijd tussen pogingen) het tegenhoudt.
    assert wm.check_ochtend_samenvatting(nu=NU + timedelta(minutes=20)) is None
    assert len(bus.gepubliceerd) == 1


def test_ochtend_kapot_statusbestand_wordt_genegeerd(wm, bus, monkeypatch):
    wm.history_path.parent.mkdir(parents=True)
    (wm.history_path.parent / "weather_ochtend.json").write_text("{kapot")
    net_voor_ochtend(monkeypatch)
    assert wm.check_ochtend_samenvatting(nu=NU) is not None


def test_ochtend_gebruikt_de_vaste_standaardstad_coordinaten(wm, monkeypatch):
    net = net_voor_ochtend(monkeypatch)
    wm.check_ochtend_samenvatting(nu=NU)
    ochtend_url = [u for u in net.urls if "hourly=" in u][0]
    assert "latitude=51.1192" in ochtend_url and "longitude=3.0903" in ochtend_url
    assert not net.vroeg_om("geocode")  # Aartrijke is bekend: geen opzoeking nodig


# ---------------------------------------------------------------
# Het oude gedrag blijft werken
# ---------------------------------------------------------------

def test_weerwaarschuwing_ongewijzigd(wm):
    assert wm.weerwaarschuwing("Clear", windsnelheid=15.0) == "Let op: er wordt harde wind verwacht."
    assert wm.weerwaarschuwing("Clear", windsnelheid=14.9) is None
    assert wm.weerwaarschuwing("Clear", temperatuur=1.0, heeft_neerslag=True) == "Let op: kans op gladheid."


def test_drempels_in_rain_en_weather_zijn_hetzelfde(wm):
    # rain.py en weather.py hebben elk hun eigen kopie van de drempels. Als
    # iemand er één aanpast, moeten de twee gelijk blijven: "nu" en "straks"
    # horen op dezelfde manier te meten.
    assert wm.weerwaarschuwing("Clear", windsnelheid=rain.WIND_DREMPEL_MS) is not None
    assert wm.weerwaarschuwing("Clear", windsnelheid=rain.WIND_DREMPEL_MS - 0.1) is None
    for temp, verwacht in ((rain.GLADHEID_MIN_C, True), (rain.GLADHEID_MAX_C, True),
                           (rain.GLADHEID_MIN_C - 0.1, False), (rain.GLADHEID_MAX_C + 0.1, False)):
        w = wm.weerwaarschuwing("Clear", temperatuur=temp, heeft_neerslag=True)
        assert (w is not None) is verwacht
    assert forecast.HITTE_DREMPEL_C == 27
    assert wm.weerwaarschuwing("Clear", temperatuur=forecast.HITTE_DREMPEL_C) is not None
    assert wm.weerwaarschuwing("Clear", temperatuur=forecast.HITTE_DREMPEL_C - 0.1) is None