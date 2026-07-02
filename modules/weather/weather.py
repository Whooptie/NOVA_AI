# modules/weather/weather.py
import os
import requests
from dotenv import load_dotenv

# Laadt de variabelen uit het .env bestand in het project
load_dotenv()


class WeatherModule:
    def __init__(self, event_bus, api_key, default_city="Aartrijke", default_country="BE"):
        self.event_bus = event_bus
        self.api_key = api_key
        self.default_city = default_city
        self.default_country = default_country

        # Luistert enkel naar intent_weather (IntentRouter doet detectie)
        event_bus.subscribe("intent_weather", self.on_weather)

    def extract_city(self, text):
        text = text.lower()
        if " in " not in text:
            return self.default_city

        # Neem enkel het eerste woord na "in"
        city = text.split(" in ", 1)[1].strip()
        city = city.split()[0]  # verwijder "vandaag", "morgen", etc.

        # Verwijder leestekens die per ongeluk meegepakt worden
        # (bv. "brugge." of "brugge?" of "brugge!" -> "brugge")
        city = city.strip(".,!?;:")

        return city

    def on_weather(self, data, event_type=None):
        text = (data.get("text") or "").lower()
        city = self.extract_city(text)

        weather = self.get_weather(city)
        if weather:
            self.event_bus.publish("chat_response", {"text": weather})
        else:
            self.event_bus.publish("chat_response", {
                "text": f"Ik kon het weer voor {city} niet ophalen."
            })

    def get_weather(self, city):
        if not self.api_key:
            return "Geen API-sleutel ingesteld voor weerinformatie."

        url = (
            f"https://api.openweathermap.org/data/2.5/weather?"
            f"q={city},{self.default_country}&appid={self.api_key}&units=metric&lang=nl"
        )

        try:
            r = requests.get(url, timeout=4)
            data = r.json()
        except Exception:
            return None

        if data.get("cod") != 200:
            return None

        try:
            temp = data["main"]["temp"]
            desc = data["weather"][0]["description"]
            feels = data["main"]["feels_like"]
        except Exception:
            return None

        return f"In {city} is het momenteel {temp}°C met {desc}. Gevoelstemperatuur: {feels}°C."


def init_module(event_bus):
    API_KEY = os.getenv("OPENWEATHER_API_KEY")
    instance = WeatherModule(event_bus, API_KEY)
    event_bus.publish("module_loaded", {"name": "weather"})
    return instance