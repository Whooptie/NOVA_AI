# modules/weather/weather.py
import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Laadt de variabelen uit het .env bestand in het project
load_dotenv()

WEEKDAGEN = {
    "maandag": 0, "dinsdag": 1, "woensdag": 2, "donderdag": 3,
    "vrijdag": 4, "zaterdag": 5, "zondag": 6
}


class WeatherModule:
    def __init__(self, event_bus, api_key, default_city="Aartrijke", default_country="BE"):
        self.event_bus = event_bus
        self.api_key = api_key
        self.default_city = default_city
        self.default_country = default_country

        # Luistert enkel naar intent_weather (IntentRouter doet detectie)
        event_bus.subscribe("intent_weather", self.on_weather)

    # -----------------------------------------------------
    # Tekst → stad
    # -----------------------------------------------------
    def extract_city(self, text):
        text = text.lower()
        if " in " not in text:
            return self.default_city

        # Neem enkel het eerste woord na "in"
        city = text.split(" in ", 1)[1].strip()
        city = city.split()[0]  # verwijder "vandaag", "morgen", etc.

        # Verwijder leestekens die per ongeluk meegepakt worden
        city = city.strip(".,!?;:")

        return city

    # -----------------------------------------------------
    # Tekst → dag-offset (0 = vandaag, 1 = morgen, ...)
    # -----------------------------------------------------
    def extract_day_offset(self, text):
        t = text.lower()

        if "overmorgen" in t:
            return 2
        if "morgen" in t:
            return 1
        if "vandaag" in t:
            return 0

        # Specifieke weekdag, bv. "weer op maandag"
        for naam, weekday_nr in WEEKDAGEN.items():
            if naam in t:
                vandaag = datetime.now().weekday()
                offset = (weekday_nr - vandaag) % 7
                if offset == 0:
                    offset = 0  # zelfde dag = vandaag bedoeld
                return offset

        return 0  # standaard: vandaag

    # -----------------------------------------------------
    # Event-handler
    # -----------------------------------------------------
    def on_weather(self, data, event_type=None):
        text = (data.get("text") or "").lower()
        city = self.extract_city(text)
        offset = self.extract_day_offset(text)

        if offset == 0:
            antwoord = self.get_weather(city)
        else:
            antwoord = self.get_forecast(city, offset)

        if antwoord:
            self.event_bus.publish("layer4_response", {"text": antwoord})
        else:
            self.event_bus.publish("layer4_response", {
                "text": f"Ik kon het weer voor {city} niet ophalen."
            })

    # -----------------------------------------------------
    # Huidig weer
    # -----------------------------------------------------
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
            humidity = data["main"]["humidity"]
            wind = data["wind"]["speed"]
            main_categorie = data["weather"][0]["main"]

            sunrise = datetime.fromtimestamp(data["sys"]["sunrise"]).strftime("%H:%M")
            sunset = datetime.fromtimestamp(data["sys"]["sunset"]).strftime("%H:%M")
        except Exception:
            return None

        zin = (
            f"In {city} is het momenteel {temp}°C met {desc}. "
            f"Gevoelstemperatuur: {feels}°C. "
            f"Luchtvochtigheid: {humidity}%, wind: {wind} m/s. "
            f"Zon op: {sunrise}, zon onder: {sunset}."
        )

        kledingadvies = self.kledingadvies(temp)
        if kledingadvies:
            zin += f" {kledingadvies}"

        waarschuwing = self.weerwaarschuwing(main_categorie)
        if waarschuwing:
            zin += f" {waarschuwing}"

        return zin

    # -----------------------------------------------------
    # Voorspelling (morgen / overmorgen / specifieke dag)
    # -----------------------------------------------------
    def get_forecast(self, city, offset_dagen):
        if not self.api_key:
            return "Geen API-sleutel ingesteld voor weerinformatie."

        if offset_dagen > 4:
            return (
                "Ik kan maximaal 5 dagen vooruit voorspellen "
                "(dat is de grens van de gratis weerdienst)."
            )

        url = (
            f"https://api.openweathermap.org/data/2.5/forecast?"
            f"q={city},{self.default_country}&appid={self.api_key}&units=metric&lang=nl"
        )

        try:
            r = requests.get(url, timeout=5)
            data = r.json()
        except Exception:
            return None

        if data.get("cod") != "200":
            return None

        doel_datum = (datetime.now() + timedelta(days=offset_dagen)).strftime("%Y-%m-%d")

        # Zoek het voorspellingsblok van die dag dat het dichtst bij 12:00 ligt
        beste_blok = None
        beste_verschil = None

        for blok in data.get("list", []):
            dt_txt = blok.get("dt_txt", "")  # bv. "2026-07-04 12:00:00"
            if not dt_txt.startswith(doel_datum):
                continue

            blok_uur = int(dt_txt.split(" ")[1].split(":")[0])
            verschil = abs(blok_uur - 12)

            if beste_verschil is None or verschil < beste_verschil:
                beste_verschil = verschil
                beste_blok = blok

        if not beste_blok:
            return f"Ik heb geen voorspelling gevonden voor {city} op die dag."

        try:
            temp = beste_blok["main"]["temp"]
            desc = beste_blok["weather"][0]["description"]
            humidity = beste_blok["main"]["humidity"]
            wind = beste_blok["wind"]["speed"]
            regenkans = round(beste_blok.get("pop", 0) * 100)  # pop = 0.0–1.0
            main_categorie = beste_blok["weather"][0]["main"]
        except Exception:
            return None

        dag_label = self.dag_label(offset_dagen)

        zin = (
            f"{dag_label} wordt het in {city} rond de {temp}°C met {desc}. "
            f"Regenkans: {regenkans}%. Luchtvochtigheid: {humidity}%, wind: {wind} m/s."
        )

        kledingadvies = self.kledingadvies(temp)
        if kledingadvies:
            zin += f" {kledingadvies}"

        waarschuwing = self.weerwaarschuwing(main_categorie)
        if waarschuwing:
            zin += f" {waarschuwing}"

        return zin

    # -----------------------------------------------------
    # Hulpfuncties
    # -----------------------------------------------------
    def dag_label(self, offset_dagen):
        if offset_dagen == 1:
            return "Morgen"
        if offset_dagen == 2:
            return "Overmorgen"

        datum = datetime.now() + timedelta(days=offset_dagen)
        weekdag_namen = [
            "maandag", "dinsdag", "woensdag", "donderdag",
            "vrijdag", "zaterdag", "zondag"
        ]
        naam = weekdag_namen[datum.weekday()]
        return f"Op {naam} {datum.strftime('%d/%m')}"

    def kledingadvies(self, temp):
        if temp < 0:
            return "Trek een dikke jas aan, het vriest!"
        if temp < 8:
            return "Trek een warme jas aan."
        if temp < 15:
            return "Een jas is aan te raden."
        if temp > 25:
            return "Het wordt warm, lichte kleding is een goed idee."
        return None

    def weerwaarschuwing(self, main_categorie):
        waarschuwingen = {
            "Thunderstorm": "Let op: er wordt onweer verwacht.",
            "Snow": "Let op: er wordt sneeuw verwacht.",
            "Extreme": "Let op: extreme weersomstandigheden verwacht."
        }
        return waarschuwingen.get(main_categorie)


def init_module(event_bus):
    API_KEY = os.getenv("OPENWEATHER_API_KEY")
    instance = WeatherModule(event_bus, API_KEY)
    event_bus.publish("module_loaded", {"name": "weather"})
    return instance