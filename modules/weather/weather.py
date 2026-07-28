# modules/weather/weather.py
import os
import json
import random
import requests
from pathlib import Path
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

        # Pad naar het bestandje dat de laatst-gemeten temperatuur per stad
        # bijhoudt, zodat we "vandaag vs. gisteren" kunnen vergelijken.
        # Ligt naast dit modulebestand, in een data/-submap.
        from modules.paths import get_project_root
        self.history_path = get_project_root(__file__) / "data" / "weather_history.json"

        # Luistert enkel naar intent_weather (IntentRouter doet detectie)
        event_bus.subscribe("intent_weather", self.on_weather)

        # Sjablonen voor de proactieve weerwaarschuwing (zie
        # _check_waarschuwing_voor_stad()). Enkel de INLEIDING varieert
        # -- de eigenlijke waarschuwingstekst zelf (bv. "Let op: er
        # wordt onweer verwacht.") blijft feitelijk en ongewijzigd.
        # Zelfde opening/afsluiting-patroon als emergence_engine.py en
        # session_watcher.py, puur string-combinatie via random.choice().
        self._sjablonen_proactieve_waarschuwing = {
            "opening": [
                "Even een seintje:",
                "Kevin, kort iets:",
                "Zeg, een kleine waarschuwing:",
                "Even laten weten:",
                "Kevin, dit is het weer waard om te melden:",
            ],
            "midden": [
                "het weer in {city} verandert.",
                "er komt iets aan qua weer in {city}.",
                "in {city} slaat het weer om.",
                "voor {city} is er een weersverandering op komst.",
                "het weerbeeld in {city} wijzigt.",
            ],
        }

        # Sjablonen voor kledingadvies (zie kledingadvies()). Vier
        # categorieën (vriezend/koud/fris/warm) x 5 varianten -- zelfde
        # random.choice()-patroon als hierboven, geen generatie.
        self._sjablonen_kledingadvies = {
            "vriezend": [
                "Trek een dikke jas aan, het vriest!",
                "Het vriest -- pak er een dikke jas bij.",
                "Goed inpakken vandaag, het vriest.",
                "Dikke jas nodig, het is vriesweer.",
                "Kleed je warm, er is vorst.",
            ],
            "koud": [
                "Trek een warme jas aan.",
                "Een warme jas is geen overbodige luxe.",
                "Het is koud -- warme jas aanraden.",
                "Kleed je warm aan vandaag.",
                "Een goede jas kan geen kwaad.",
            ],
            "fris": [
                "Een jas is aan te raden.",
                "Best een jas meenemen.",
                "Het is fris -- een jasje doet geen kwaad.",
                "Neem toch maar een jas mee.",
                "Een lichte jas is voldoende, maar wel aanraden.",
            ],
            "warm": [
                "Het wordt warm, lichte kleding is een goed idee.",
                "Het wordt warm -- luchtige kleding aanraden.",
                "Trek iets lichts aan, het wordt warm vandaag.",
                "Het is warm weer, kleed je luchtig.",
                "Warme dag op komst, licht gekleed is fijner.",
            ],
        }

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
    # Geschiedenis (voor "vergelijking met gisteren")
    # -----------------------------------------------------
    def _laad_geschiedenis(self):
        """Leest weather_history.json in. Bestaat het nog niet, of is het
        kapot/leeg, dan geven we gewoon een lege dict terug — geen crash."""
        if not self.history_path.exists():
            return {}

        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _bewaar_temperatuur(self, city, temp):
        """Slaat de temperatuur van vandaag op voor deze stad, en geeft de
        vorige gemeten waarde terug — maar enkel als die écht van gisteren
        is. Is de laatste meting ouder (bv. Nova een week niet gebruikt),
        dan is een vergelijking misleidend en laten we 'm gewoon weg."""
        geschiedenis = self._laad_geschiedenis()
        stad_key = city.lower()
        vandaag_dt = datetime.now()
        vandaag = vandaag_dt.strftime("%Y-%m-%d")
        gisteren = (vandaag_dt - timedelta(days=1)).strftime("%Y-%m-%d")

        vorige_waarde = None
        oude_entry = geschiedenis.get(stad_key)
        if oude_entry and oude_entry.get("datum") == gisteren:
            vorige_waarde = oude_entry.get("temp")

        geschiedenis[stad_key] = {"datum": vandaag, "temp": temp}

        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(geschiedenis, f, ensure_ascii=False, indent=2)
        except Exception:
            # Kon niet opslaan (bv. schrijfrechten) — geen ramp, dan werkt
            # de vergelijking morgen simpelweg nog niet. Geen crash.
            pass

        return vorige_waarde

    def vergelijking_met_gisteren(self, temp_vandaag, temp_gisteren):
        """Zet het verschil met gisteren om in een spreektalige zin.
        Geeft None terug als er geen zinvolle vergelijking is."""
        if temp_gisteren is None:
            return None

        verschil = round(temp_vandaag - temp_gisteren, 1)

        if abs(verschil) < 1:
            return "Dat is ongeveer gelijk aan gisteren."
        if verschil > 0:
            return f"Dat is {verschil}°C warmer dan gisteren."
        return f"Dat is {abs(verschil)}°C kouder dan gisteren."

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
            weather_id = data["weather"][0].get("id")

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

        heeft_neerslag = self._heeft_neerslag(data, main_categorie)
        waarschuwing = self.weerwaarschuwing(main_categorie, weather_id=weather_id, windsnelheid=wind, temperatuur=temp, heeft_neerslag=heeft_neerslag)
        if waarschuwing:
            zin += f" {waarschuwing}"

        # Vergelijk met de vorige gemeten waarde (meestal gisteren) en
        # bewaar meteen de temperatuur van vandaag voor de volgende keer.
        temp_vorige_keer = self._bewaar_temperatuur(city, temp)
        vergelijking = self.vergelijking_met_gisteren(temp, temp_vorige_keer)
        if vergelijking:
            zin += f" {vergelijking}"

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
            weather_id = beste_blok["weather"][0].get("id")
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

        heeft_neerslag = self._heeft_neerslag(beste_blok, main_categorie)
        waarschuwing = self.weerwaarschuwing(main_categorie, weather_id=weather_id, windsnelheid=wind, temperatuur=temp, heeft_neerslag=heeft_neerslag)
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
            return random.choice(self._sjablonen_kledingadvies["vriezend"])
        if temp < 8:
            return random.choice(self._sjablonen_kledingadvies["koud"])
        if temp < 15:
            return random.choice(self._sjablonen_kledingadvies["fris"])
        if temp > 25:
            return random.choice(self._sjablonen_kledingadvies["warm"])
        return None

    def _heeft_neerslag(self, data, main_categorie):
        """Bepaalt of er neerslag is/verwacht wordt, voor de gladheidscheck.
        Kijkt zowel naar de expliciete rain/snow-velden (die OWM enkel
        meestuurt als er ook echt neerslag gemeten is) als naar de
        hoofdcategorie (Rain/Drizzle/Snow) — iets ruimer dan strikt
        noodzakelijk, om gladheid niet per ongeluk te missen."""
        if "rain" in data or "snow" in data:
            return True
        return main_categorie in ("Rain", "Drizzle", "Snow")

    def weerwaarschuwing(self, main_categorie, weather_id=None, windsnelheid=None, temperatuur=None, heeft_neerslag=False):
        """Geeft een waarschuwingszin terug op basis van vijf signalen:
        - main_categorie: het hoofdweertype van OpenWeatherMap (bv. "Thunderstorm")
        - weather_id: de specifieke numerieke conditiecode (bv. 906 = hagel)
        - windsnelheid: windsnelheid in m/s, voor de harde-wind-check
        - temperatuur: temperatuur in °C, voor de hitte- en gladheidscheck
        - heeft_neerslag: bool, of er regen/sneeuw/motregen aanwezig is
          (voor de gladheidscheck — droge kou geeft geen glad wegdek)

        Kan meerdere waarschuwingen tegelijk teruggeven (bv. onweer + harde
        wind), samengevoegd tot één zin. Geeft None als er niets te melden is.
        """
        gevonden_waarschuwingen = []

        categorie_waarschuwingen = {
            "Thunderstorm": "er wordt onweer verwacht",
            "Snow": "er wordt sneeuw verwacht",
            "Extreme": "er worden extreme weersomstandigheden verwacht",
            "Mist": "er wordt mist verwacht",
            "Fog": "er wordt dichte mist verwacht",
            "Haze": "er wordt heiige lucht verwacht",
        }
        if main_categorie in categorie_waarschuwingen:
            gevonden_waarschuwingen.append(categorie_waarschuwingen[main_categorie])

        if weather_id == 906:
            gevonden_waarschuwingen.append("er wordt hagel verwacht")

        WIND_DREMPEL_MS = 15
        if windsnelheid is not None and windsnelheid >= WIND_DREMPEL_MS:
            gevonden_waarschuwingen.append("er wordt harde wind verwacht")

        # Hitte zit niet in een aparte OWM-categorie (in tegenstelling tot
        # onweer/sneeuw/mist) — een hittegolf toont zich gewoon als "Clear"
        # met een hoge temp. Vandaar een eigen temperatuurdrempel, net als
        # bij windsnelheid hierboven. Drempel: Kevin's eigen keuze, 27°C.
        HITTE_DREMPEL_C = 27
        if temperatuur is not None and temperatuur >= HITTE_DREMPEL_C:
            gevonden_waarschuwingen.append("het wordt erg warm")

        # Gladheid: temperatuur rond het vriespunt (0-2°C) SAMEN met
        # neerslag — droge kou alleen geeft geen glad wegdek. Venster
        # bewust iets ruimer dan enkel "< 0°C", want net rond het
        # vriespunt met neerslag is precies wanneer gladheid ontstaat of
        # dreigt. Kevin's keuze, 19 juli 2026.
        GLADHEID_MIN_C = 0
        GLADHEID_MAX_C = 2
        if (
            temperatuur is not None
            and heeft_neerslag
            and GLADHEID_MIN_C <= temperatuur <= GLADHEID_MAX_C
        ):
            gevonden_waarschuwingen.append("kans op gladheid")

        if not gevonden_waarschuwingen:
            return None

        if len(gevonden_waarschuwingen) == 1:
            return f"Let op: {gevonden_waarschuwingen[0]}."
        return f"Let op: {' en '.join(gevonden_waarschuwingen)}."

    # -----------------------------------------------------
    # Proactieve automatische weerwaarschuwing (achtergrond-timer)
    # -----------------------------------------------------
    def get_current_location(self):
        """Vraagt de huidige stad + coördinaten op via IP-locatie
        (ipinfo.io), zelfde soort bron als modules/time/zone.py gebruikt
        voor de tijdzone. Geeft (stad, lat, lon) terug, met None-waarden
        bij falen of ontbrekende velden -- puur symbolisch, geen ML, gewoon
        twee extra velden uit dezelfde soort API-response.

        ipinfo.io geeft coördinaten als 1 string terug in het 'loc'-veld,
        bv. "51.2093,3.2247" (lat,lon) -- die splitsen we hier op."""
        try:
            r = requests.get("https://ipinfo.io/json", timeout=4)
            data = r.json()
            stad = data.get("city")

            lat, lon = None, None
            loc = data.get("loc")
            if loc and "," in loc:
                lat_str, lon_str = loc.split(",", 1)
                lat, lon = float(lat_str), float(lon_str)

            return stad, lat, lon
        except Exception:
            return None, None, None

    def get_current_location_city(self):
        """Backwards-compatible variant die enkel de stadsnaam teruggeeft
        (zonder coördinaten). Gebruikt intern get_current_location()."""
        stad, _lat, _lon = self.get_current_location()
        return stad

    def _get_stad_coordinaten(self, city):
        """Vraagt lat/lon op voor een stadsnaam via OpenWeatherMap's
        Geocoding-API (zelfde api_key als de rest van deze module, geen
        nieuwe dienst nodig). Geeft (lat, lon) terug, of (None, None) bij
        falen -- puur een opzoeking, geen ML."""
        url = (
            f"https://api.openweathermap.org/geo/1.0/direct?"
            f"q={city},{self.default_country}&limit=1&appid={self.api_key}"
        )
        try:
            r = requests.get(url, timeout=4)
            resultaten = r.json()
            if not resultaten:
                return None, None
            return resultaten[0].get("lat"), resultaten[0].get("lon")
        except Exception:
            return None, None

    def _afstand_km(self, lat1, lon1, lat2, lon2):
        """Haversine-afstandsberekening tussen twee coördinaten, in km.
        Standaard wiskunde (bolvormige aarde-benadering) -- geen library,
        geen ML, gewoon een formule."""
        import math

        R = 6371  # gemiddelde straal van de aarde in km
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        a = (
            math.sin(d_lat / 2) ** 2
            + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    # Drempel voor "dit telt als dezelfde plek" -- IP-geolocatie is
    # inherent onnauwkeurig (gebaseerd op internetprovider-routing, niet
    # GPS), dus kleine buurgemeentes van de standaardstad mogen niet als
    # aparte locatie tellen. 20 km dekt bv. Aartrijke <-> Brugge ruim.
    # Gewoon een constante hier bovenaan -- pas gerust aan als 20 km in de
    # praktijk nog te weinig of te veel blijkt.
    ZELFDE_PLEK_DREMPEL_KM = 20

    def check_proactieve_waarschuwing(self):
        """Wordt periodiek aangeroepen vanuit achtergrond_loop() in main.py
        (elke 30 min). Checkt de standaardstad, en indien de IP-locatie een
        ANDERE stad is DIE OOK ECHT VER GENOEG WEG LIGT (> ZELFDE_PLEK_DREMPEL_KM),
        ook die -- om Kevin niet dubbel te melden zodra IP-geolocatie een
        naburige plaats teruggeeft terwijl hij gewoon thuis zit. Meldt
        waarschuwingen per nieuwe episode (zie _is_nieuwe_episode()).
        """
        if not self.api_key:
            return  # geen API-sleutel, stil niets doen (geen spam in de logs)

        steden_om_te_checken = [self.default_city]

        ip_stad, ip_lat, ip_lon = self.get_current_location()
        if ip_stad and ip_stad.lower() != self.default_city.lower():
            # Andere STADSNAAM volgens ipinfo.io -- maar dat kan gewoon een
            # buurgemeente zijn die toevallig anders heet. Enkel als de
            # afstand ook echt groot genoeg is, tellen we dit als een
            # aparte locatie om te checken.
            if ip_lat is not None and ip_lon is not None:
                default_lat, default_lon = self._get_stad_coordinaten(self.default_city)
                if default_lat is not None and default_lon is not None:
                    afstand = self._afstand_km(default_lat, default_lon, ip_lat, ip_lon)
                    if afstand > self.ZELFDE_PLEK_DREMPEL_KM:
                        steden_om_te_checken.append(ip_stad)
                    # Anders: te dichtbij, blijkbaar toch dezelfde plek --
                    # geen tweede stad toevoegen.
                else:
                    # Coördinaten van de standaardstad niet te achterhalen
                    # (bv. Geocoding-API-fout) -- val terug op de oude,
                    # simpele naam-vergelijking om nooit een echte
                    # locatiewissel te missen.
                    steden_om_te_checken.append(ip_stad)
            else:
                # Geen coördinaten van ipinfo.io beschikbaar -- zelfde
                # veilige terugval als hierboven.
                steden_om_te_checken.append(ip_stad)

        for stad in steden_om_te_checken:
            self._check_waarschuwing_voor_stad(stad)

    def _check_waarschuwing_voor_stad(self, city):
        """Haalt het huidige weer op voor 1 stad, en publiceert een
        proactieve melding als er een waarschuwing is EN die vandaag nog
        niet gemeld werd voor deze stad."""
        url = (
            f"https://api.openweathermap.org/data/2.5/weather?"
            f"q={city},{self.default_country}&appid={self.api_key}&units=metric&lang=nl"
        )

        try:
            r = requests.get(url, timeout=4)
            data = r.json()
        except Exception:
            return

        if data.get("cod") != 200:
            return

        try:
            main_categorie = data["weather"][0]["main"]
            weather_id = data["weather"][0].get("id")
            wind = data["wind"]["speed"]
            temp = data["main"]["temp"]
        except Exception:
            return

        heeft_neerslag = self._heeft_neerslag(data, main_categorie)
        waarschuwing = self.weerwaarschuwing(main_categorie, weather_id=weather_id, windsnelheid=wind, temperatuur=temp, heeft_neerslag=heeft_neerslag)

        if not waarschuwing:
            # Geen waarschuwing nu -- toch bijhouden dat de "actieve episode"
            # voorbij is, anders herkennen we een latere terugkeer van
            # dezelfde waarschuwing (bv. 's avonds opnieuw onweer na een
            # rustige middag) niet als nieuwe episode.
            self._markeer_status(city, waarschuwing_tekst=None)
            return

        if not self._is_nieuwe_episode(city, waarschuwing):
            return  # zelfde waarschuwing als de vorige check, nog dezelfde episode

        self._markeer_status(city, waarschuwing_tekst=waarschuwing)
        opening = random.choice(self._sjablonen_proactieve_waarschuwing["opening"])
        midden = random.choice(self._sjablonen_proactieve_waarschuwing["midden"]).format(city=city)
        tekst = f"{opening} {midden} {waarschuwing}"
        self.event_bus.publish("layer4_response", {"text": tekst})

    def _is_nieuwe_episode(self, city, waarschuwing_tekst):
        """Bepaalt of de huidige waarschuwing een NIEUWE episode is t.o.v.
        de vorige check, i.p.v. gewoon 1x per dag te tellen. Een nieuwe
        episode is: de vorige check had GEEN waarschuwing (de waarschuwing
        was dus even weg en komt nu terug -- ook al is het exact hetzelfde
        weertype als eerder vandaag), OF de waarschuwingstekst is nu anders
        dan de vorige keer (bv. onweer -> sneeuw). Blijft dezelfde
        waarschuwing gewoon actief tussen twee checks in, dan is het GEEN
        nieuwe episode en melden we niet opnieuw."""
        geschiedenis = self._laad_geschiedenis()
        stad_key = city.lower()
        entry = geschiedenis.get(stad_key, {})

        vorige_tekst = entry.get("laatste_waarschuwing_tekst")
        return vorige_tekst != waarschuwing_tekst

    def _markeer_status(self, city, waarschuwing_tekst):
        """Slaat de huidige waarschuwingsstatus op voor deze stad: de tekst
        (of None als er nu niets te melden is) plus de datum van de laatste
        melding (enkel bijgewerkt als er ECHT gemeld is). Zonder de
        bestaande temperatuur/datum-gegevens (gisteren-vergelijking) te
        overschrijven."""
        geschiedenis = self._laad_geschiedenis()
        stad_key = city.lower()
        vandaag = datetime.now().strftime("%Y-%m-%d")

        if stad_key not in geschiedenis:
            geschiedenis[stad_key] = {}

        geschiedenis[stad_key]["laatste_waarschuwing_tekst"] = waarschuwing_tekst
        if waarschuwing_tekst is not None:
            geschiedenis[stad_key]["laatste_waarschuwing_datum"] = vandaag

        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(geschiedenis, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


def init_module(event_bus):
    API_KEY = os.getenv("OPENWEATHER_API_KEY")
    instance = WeatherModule(event_bus, API_KEY)
    event_bus.publish("module_loaded", {"name": "weather"})
    return instance