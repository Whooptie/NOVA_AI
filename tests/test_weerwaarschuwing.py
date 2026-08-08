# test_weerwaarschuwing.py
#
# Echte pytest-test voor weerwaarschuwing() uit modules/weather/weather.py.
#
# Dit is de pytest-versie van het oude, print-gebaseerde script. De
# scenario's en verwachte uitkomsten zijn ONGEWIJZIGD overgenomen --
# enkel de manier waarop we ze controleren is veranderd: in plaats van
# zelf "OK"/"FOUT" te tellen en printen, laten we pytest per scenario
# een eigen, apart zichtbaar testresultaat geven (via parametrize).
#
# Geen netwerk nodig, geen echte data/-bestanden -- WeatherModule wordt
# hier enkel gebruikt om zijn interne weerwaarschuwing()-logica te
# testen, met een nep-EventBus en een nep-API-key die nooit echt
# gebruikt wordt (er wordt geen enkele API-call gedaan in deze test).
#
# Uitvoeren: pytest tests/test_weerwaarschuwing.py -v

import pytest

from modules.weather.weather import WeatherModule


class DummyEventBus:
    """Nep-EventBus -- WeatherModule heeft er één nodig om te construeren,
    maar we gebruiken hem hier niet echt (geen publish/subscribe nodig)."""
    def subscribe(self, *args, **kwargs):
        pass

    def publish(self, *args, **kwargs):
        pass


@pytest.fixture
def weather_module():
    """Bouwt één WeatherModule op, herbruikt door elk scenario hieronder.

    api_key="dummy" is veilig hier: weerwaarschuwing() doet geen
    enkele netwerkcall, het is pure if/else-logica op basis van de
    parameters die je er rechtstreeks aan meegeeft.
    """
    return WeatherModule(DummyEventBus(), api_key="dummy")


# (naam, main_categorie, weather_id, windsnelheid, temperatuur, heeft_neerslag, verwacht)
# verwacht = None betekent "geen waarschuwing verwacht"
# verwacht = "..." betekent "resultaat moet deze tekst bevatten"
SCENARIOS = [
    ("helder_lichte_wind",         "Clear",        None, 3.0,  20.0, False, None),
    ("onweer_normale_wind",        "Thunderstorm", None, 5.0,  20.0, False, "onweer"),
    ("sneeuw",                     "Snow",         None, 2.0,  0.0,  True,  "sneeuw"),
    ("mist",                       "Mist",         None, 1.0,  15.0, False, "mist"),
    ("harde_wind_verder_helder",   "Clear",        None, 18.0, 20.0, False, "harde wind"),
    ("net_onder_winddrempel",      "Clear",        None, 14.9, 20.0, False, None),
    ("precies_op_winddrempel",     "Clear",        None, 15.0, 20.0, False, "harde wind"),
    ("hagel_specifieke_id_906",    "Clouds",       906,  4.0,  15.0, False, "hagel"),
    ("onweer_hagel_wind_samen",    "Thunderstorm", 906,  20.0, 20.0, False, "onweer"),
    ("hitte_op_drempel_27",        "Clear",        None, 3.0,  27.0, False, "warm"),
    ("net_onder_hittedrempel",     "Clear",        None, 3.0,  26.9, False, None),
    ("hitte_ver_boven_drempel",    "Clear",        None, 3.0,  32.0, False, "warm"),
    ("gladheid_1graad_neerslag",   "Rain",         None, 3.0,  1.0,  True,  "gladheid"),
    ("gladheid_grens_0graad",      "Rain",         None, 3.0,  0.0,  True,  "gladheid"),
    ("gladheid_grens_2graad",      "Snow",         None, 3.0,  2.0,  True,  "gladheid"),
    ("net_boven_gladheidsgrens",   "Rain",         None, 3.0,  2.1,  True,  None),
    ("net_onder_gladheidsgrens",   "Rain",         None, 3.0,  -0.1, True,  None),
    ("droge_kou_geen_neerslag",    "Clear",        None, 3.0,  1.0,  False, None),
]


@pytest.mark.parametrize(
    "categorie, weather_id, wind, temp, neerslag, verwacht",
    [s[1:] for s in SCENARIOS],
    ids=[s[0] for s in SCENARIOS],
)
def test_weerwaarschuwing_scenario(weather_module, categorie, weather_id, wind, temp, neerslag, verwacht):
    resultaat = weather_module.weerwaarschuwing(
        categorie,
        weather_id=weather_id,
        windsnelheid=wind,
        temperatuur=temp,
        heeft_neerslag=neerslag,
    )

    if verwacht is None:
        assert resultaat is None, (
            f"Verwachtte GEEN waarschuwing, maar kreeg: {resultaat!r}"
        )
    else:
        assert resultaat is not None and verwacht in resultaat, (
            f"Verwachtte dat resultaat '{verwacht}' zou bevatten, "
            f"maar kreeg: {resultaat!r}"
        )