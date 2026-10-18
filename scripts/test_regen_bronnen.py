# test_regen_bronnen.py
"""
Los testscript om twee regenradar-bronnen uit te proberen voor Aartrijke —
GEEN onderdeel van Nova zelf. Doel: zien welke bron betrouwbaar data geeft
voor de komende uren, zodat we daarna een regenmodule (modules/weather/rain.py)
kunnen bouwen op de bron die echt werkt.

Bron 1: Buienradar (5-minuten-resolutie, ~2 uur vooruit, onofficieel endpoint)
Bron 2: Open-Meteo  (15-minuten-resolutie, gedocumenteerde gratis API)

Het script print ALLES ruw, zodat we het formaat kunnen controleren.

Uitvoeren: python test_regen_bronnen.py
"""

import os
import requests
from dotenv import load_dotenv

# Terugval-coördinaten (ongeveer Aartrijke) als OpenWeatherMap niet bereikbaar is
FALLBACK_LAT = 51.12
FALLBACK_LON = 3.07
STAD = "Aartrijke"
LAND = "BE"


def haal_coordinaten():
    """Vraagt de coördinaten van de stad op via OpenWeatherMap (zelfde sleutel
    als weather.py). Geeft (lat, lon, bron_uitleg) terug."""
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        return FALLBACK_LAT, FALLBACK_LON, "terugval (geen API-sleutel in .env)"

    url = (
        f"https://api.openweathermap.org/data/2.5/weather?"
        f"q={STAD},{LAND}&appid={api_key}"
    )
    try:
        data = requests.get(url, timeout=5).json()
        lat = data["coord"]["lat"]
        lon = data["coord"]["lon"]
        return lat, lon, "OpenWeatherMap"
    except Exception as e:
        return FALLBACK_LAT, FALLBACK_LON, f"terugval (OWM mislukt: {e})"


def waarde_naar_mm_per_uur(waarde):
    """Buienradar geeft een getal 0-255. 0 = droog. Voor de rest geldt de
    formule mm/u = 10 ** ((waarde - 109) / 32). (Formule uit mijn geheugen —
    controleer of de uitkomst logisch is: 77 ~ 0.1 mm/u, 109 ~ 1 mm/u.)"""
    if waarde <= 0:
        return 0.0
    return 10 ** ((waarde - 109) / 32)


def test_buienradar(lat, lon):
    print("=" * 70)
    print("BRON 1: Buienradar")
    print("=" * 70)

    url = f"https://gpsgadget.buienradar.nl/data/raintext?lat={lat:.2f}&lon={lon:.2f}"
    print(f"URL: {url}")

    try:
        r = requests.get(url, timeout=6)
    except Exception as e:
        print(f"❌ Verbinding mislukt: {e}")
        return False

    print(f"HTTP-status: {r.status_code}")
    if r.status_code != 200:
        print("❌ Geen bruikbaar antwoord.")
        print(r.text[:300])
        return False

    ruw = r.text.strip()
    regels = [l.strip() for l in ruw.splitlines() if l.strip()]
    print(f"Aantal regels ontvangen: {len(regels)}")
    print("\nRUWE TEKST (eerste 6 regels):")
    for l in regels[:6]:
        print(f"   {l}")

    print("\nGEPARST (tijd -> ruwe waarde -> mm/u):")
    geparst = 0
    for l in regels:
        if "|" not in l:
            continue
        waarde_txt, tijd = l.split("|", 1)
        try:
            waarde = int(waarde_txt)
        except ValueError:
            continue
        mm = waarde_naar_mm_per_uur(waarde)
        print(f"   {tijd}  waarde={waarde:3d}  ->  {mm:.2f} mm/u")
        geparst += 1

    if geparst == 0:
        print("❌ Geen enkele regel kon geparst worden — formaat klopt niet met mijn verwachting.")
        return False

    print(f"\n✅ {geparst} regels geparst.")
    return True


def test_open_meteo(lat, lon):
    print()
    print("=" * 70)
    print("BRON 2: Open-Meteo (15-minuten neerslag)")
    print("=" * 70)

    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat:.4f}&longitude={lon:.4f}"
        "&minutely_15=precipitation"
        "&forecast_minutely_15=12"
        "&timezone=Europe%2FBrussels"
    )
    print(f"URL: {url}")

    try:
        r = requests.get(url, timeout=6)
    except Exception as e:
        print(f"❌ Verbinding mislukt: {e}")
        return False

    print(f"HTTP-status: {r.status_code}")
    if r.status_code != 200:
        print("❌ Geen bruikbaar antwoord.")
        print(r.text[:300])
        return False

    try:
        data = r.json()
        tijden = data["minutely_15"]["time"]
        neerslag = data["minutely_15"]["precipitation"]
    except Exception as e:
        print(f"❌ Antwoord heeft niet de verwachte vorm: {e}")
        print(r.text[:300])
        return False

    print("\nGEPARST (tijd -> mm in dat kwartier):")
    for t, mm in zip(tijden, neerslag):
        print(f"   {t}  ->  {mm} mm")

    print(f"\n✅ {len(tijden)} kwartieren ontvangen.")
    return True


def run():
    load_dotenv()

    lat, lon, bron = haal_coordinaten()
    print(f"Locatie: {STAD} ({lat:.4f}, {lon:.4f}) — coördinaten via: {bron}\n")

    ok_buien = test_buienradar(lat, lon)
    ok_meteo = test_open_meteo(lat, lon)

    print()
    print("=" * 70)
    print("SAMENVATTING")
    print("=" * 70)
    print(f"Buienradar : {'✅ werkt' if ok_buien else '❌ werkt niet'}")
    print(f"Open-Meteo : {'✅ werkt' if ok_meteo else '❌ werkt niet'}")
    print()
    print("Tip: draai dit nog eens als het écht regent (of net gestopt is),")
    print("dan zien we ook of de waarden niet overal 0 zijn.")


if __name__ == "__main__":
    run()