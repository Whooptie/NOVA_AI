# test_weerwaarschuwing.py
"""
Los testscript voor weerwaarschuwing() — GEEN onderdeel van Nova zelf,
enkel om de logica te controleren zonder op echt slecht weer te wachten.

Roept de echte weerwaarschuwing()-methode uit modules/weather/weather.py
rechtstreeks aan met verzonnen scenario's. Geen echte API-call nodig.

Uitvoeren: python test_weerwaarschuwing.py
"""

import sys
from pathlib import Path

# Zorgt dat "modules.weather.weather" gevonden wordt, ongeacht vanuit
# welke map je dit script start (zolang het in de Nova-projectroot staat).
sys.path.insert(0, str(Path(__file__).parent))

from modules.weather.weather import WeatherModule


class DummyEventBus:
    """Nep-EventBus — WeatherModule heeft er één nodig om te construeren,
    maar we gebruiken hem hier niet echt (geen publish/subscribe nodig)."""
    def subscribe(self, *args, **kwargs):
        pass

    def publish(self, *args, **kwargs):
        pass


def run_tests():
    wm = WeatherModule(DummyEventBus(), api_key="dummy")

    # (naam, main_categorie, weather_id, windsnelheid, temperatuur, heeft_neerslag, verwachte_uitkomst)
    # verwachte_uitkomst = None betekent "geen waarschuwing verwacht"
    # verwachte_uitkomst = "bevat:..." betekent "moet deze tekst bevatten"
    scenarios = [
        ("Helder weer, lichte wind",              "Clear",        None, 3.0,  20.0, False, None),
        ("Onweer, normale wind",                  "Thunderstorm", None, 5.0,  20.0, False, "onweer"),
        ("Sneeuw",                                 "Snow",         None, 2.0,  0.0,  True,  "sneeuw"),
        ("Mist",                                   "Mist",         None, 1.0,  15.0, False, "mist"),
        ("Harde wind, verder helder",             "Clear",        None, 18.0, 20.0, False, "harde wind"),
        ("Net onder de winddrempel (14.9 m/s)",   "Clear",        None, 14.9, 20.0, False, None),
        ("Precies op de winddrempel (15.0 m/s)",  "Clear",        None, 15.0, 20.0, False, "harde wind"),
        ("Hagel via specifieke weather-ID 906",   "Clouds",       906,  4.0,  15.0, False, "hagel"),
        ("Onweer + hagel + harde wind samen",     "Thunderstorm", 906,  20.0, 20.0, False, "onweer"),
        ("Hitte op de drempel (27.0\u00b0C)",         "Clear",        None, 3.0,  27.0, False, "warm"),
        ("Net onder de hittedrempel (26.9\u00b0C)",   "Clear",        None, 3.0,  26.9, False, None),
        ("Hitte ver boven de drempel (32.0\u00b0C)",  "Clear",        None, 3.0,  32.0, False, "warm"),
        ("Gladheid: 1.0\u00b0C met neerslag",         "Rain",         None, 3.0,  1.0,  True,  "gladheid"),
        ("Gladheid-grens: 0.0\u00b0C met neerslag",   "Rain",         None, 3.0,  0.0,  True,  "gladheid"),
        ("Gladheid-grens: 2.0\u00b0C met neerslag",   "Snow",         None, 3.0,  2.0,  True,  "gladheid"),
        ("Net boven gladheidsgrens: 2.1\u00b0C",      "Rain",         None, 3.0,  2.1,  True,  None),
        ("Net onder gladheidsgrens: -0.1\u00b0C",     "Rain",         None, 3.0,  -0.1, True,  None),
        ("1.0\u00b0C maar GEEN neerslag (droge kou)", "Clear",        None, 3.0,  1.0,  False, None),
    ]

    print("=" * 70)
    print("TEST: weerwaarschuwing()")
    print("=" * 70)

    aantal_ok = 0
    aantal_fout = 0

    for naam, categorie, weather_id, wind, temp, neerslag, verwacht in scenarios:
        resultaat = wm.weerwaarschuwing(categorie, weather_id=weather_id, windsnelheid=wind, temperatuur=temp, heeft_neerslag=neerslag)

        if verwacht is None:
            geslaagd = resultaat is None
        else:
            geslaagd = resultaat is not None and verwacht in resultaat

        status = "✅ OK  " if geslaagd else "❌ FOUT"
        if geslaagd:
            aantal_ok += 1
        else:
            aantal_fout += 1

        print(f"{status} | {naam}")
        print(f"        Resultaat: {resultaat}")
        print()

    print("=" * 70)
    print(f"Resultaat: {aantal_ok} geslaagd, {aantal_fout} gefaald (van {len(scenarios)} testen)")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()