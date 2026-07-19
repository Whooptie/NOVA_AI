# test_proactieve_waarschuwing.py
"""
Los testscript voor check_proactieve_waarschuwing() — GEEN onderdeel
van Nova zelf. Test de ECHTE OpenWeatherMap-API (met je .env-sleutel)
en de ECHTE ipinfo.io-locatiecheck, zonder dat Nova zelf hoeft te draaien.

Handig om te zien of een proactieve melding zou verschijnen, zonder
30 minuten te wachten op de achtergrondthread.

BELANGRIJK: dit gebruikt je echte API-sleutel en doet echte netwerk-
calls (OpenWeatherMap + ipinfo.io). Draai dit dus niet te vaak achter
elkaar (gratis API's hebben een limiet per dag).

Uitvoeren: python test_proactieve_waarschuwing.py
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))

from modules.weather.weather import WeatherModule


class DummyEventBus:
    """Nep-EventBus die publicaties opvangt in een lijst, zodat we
    achteraf kunnen tonen wat Nova zou gezegd hebben."""
    def __init__(self):
        self.gepubliceerd = []

    def subscribe(self, *args, **kwargs):
        pass

    def publish(self, event, data):
        self.gepubliceerd.append((event, data))


def toon_huidige_geschiedenis(wm):
    """Print de huidige inhoud van weather_history.json, zodat je ziet
    wat er al opgeslagen staat (incl. eventuele 'al gemeld vandaag'-vlag)."""
    print("-" * 70)
    print("Huidige inhoud van weather_history.json:")
    if wm.history_path.exists():
        with open(wm.history_path, "r", encoding="utf-8") as f:
            print(json.dumps(json.load(f), indent=2, ensure_ascii=False))
    else:
        print("(bestand bestaat nog niet — wordt aangemaakt bij eerste run)")
    print("-" * 70)


def run_test():
    load_dotenv()
    api_key = os.getenv("OPENWEATHER_API_KEY")

    if not api_key:
        print("❌ Geen OPENWEATHER_API_KEY gevonden in .env — kan niet testen.")
        return

    bus = DummyEventBus()
    wm = WeatherModule(bus, api_key=api_key)

    print("=" * 70)
    print("TEST: check_proactieve_waarschuwing()")
    print(f"Standaardstad: {wm.default_city}")
    print("=" * 70)

    toon_huidige_geschiedenis(wm)

    print("\nIP-locatie ophalen...")
    ip_stad = wm.get_current_location_city()
    print(f"IP-locatie gevonden: {ip_stad}")
    if ip_stad and ip_stad.lower() == wm.default_city.lower():
        print("-> Zelfde als standaardstad, wordt dus NIET apart gecheckt.")
    elif ip_stad:
        print("-> Andere stad dan standaard, wordt DUS OOK gecheckt.")
    else:
        print("-> Kon geen IP-locatie bepalen, enkel standaardstad wordt gecheckt.")

    print("\nProactieve check uitvoeren...")
    wm.check_proactieve_waarschuwing()

    print("\n" + "=" * 70)
    if bus.gepubliceerd:
        print(f"✅ Er werd {len(bus.gepubliceerd)} melding(en) gepubliceerd:")
        for event, data in bus.gepubliceerd:
            print(f"   [{event}] {data['text']}")
    else:
        print("ℹ️  Geen melding gepubliceerd. Dit is NORMAAL als:")
        print("   - Het weer nu geen onweer/sneeuw/extreem/mist/hagel/harde wind heeft")
        print("   - OF er vandaag al een melding was voor deze stad (zie geschiedenis hieronder)")
    print("=" * 70)

    toon_huidige_geschiedenis(wm)

    print("\nTip: draai dit script 2x na elkaar. De 2e keer zou GEEN nieuwe")
    print("melding meer mogen geven voor dezelfde stad, ook al is er nog")
    print("steeds een waarschuwing actief (max. 1x per dag per stad).")


if __name__ == "__main__":
    run_test()