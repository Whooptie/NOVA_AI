# live_controle.py  -  draaien in de container:  python live_controle.py
# Doet ECHTE internetverzoeken. Wijzigt niets, spreekt niets uit.
import os, sys
sys.path.insert(0, "/app")
from modules.weather.weather import WeatherModule


class NepBus:
    def __init__(self):
        self.berichten = []
    def subscribe(self, *a, **k):
        pass
    def publish(self, naam, data=None):
        if naam == "layer4_response":
            self.berichten.append(data["text"])


bus = NepBus()
wm = WeatherModule(bus, os.getenv("OPENWEATHER_API_KEY"))

vragen = [
    "wat is het weer",
    "wat is het weer morgen",
    "wat is het weer overmorgen",
    "wat is het weer over 6 dagen",
    "wat is het weer over 10 dagen",
    "wat is het weer over twee weken",
    "wat is het weer over 20 dagen",
]
for v in vragen:
    bus.berichten.clear()
    wm.on_weather({"text": v})
    print(f"\n> {v}\n  {bus.berichten[-1] if bus.berichten else '(geen antwoord)'}")

print("\n--- ochtendsamenvatting (zonder iets uit te spreken) ---")
bus.berichten.clear()
tekst = wm.check_ochtend_samenvatting(mag_spreken=lambda: False)
print("mag_spreken=False ->", tekst, "| gepubliceerd:", bus.berichten)