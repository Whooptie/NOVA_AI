# modules/time/on_this_day.py

# ============================================================
# OnThisDayModule
# ------------------------------------------------------------
# Historische datums via Wikipedia's "On This Day" REST API
# (date_calendar_roadmap.md, Onderdeel 4): "wat is er gebeurd op
# [datum]", "wie is er geboren op [datum]", "wie is er overleden
# op [datum]".
#
# Puur een externe, gratis, community-onderhouden bron RAADPLEGEN
# en het antwoord TONEN -- geen eigen redenering over wat
# "interessant" is (dat oordeel ligt al besloten in wat Wikipedia's
# vrijwilligers ooit aan de lijst toevoegden). Zelfde architecturale
# patroon als de al bestaande wikipedia_teacher.py: urllib.request
# (geen extra dependency), zelfde User-Agent-header, zelfde
# timeout/foutafhandelingsstijl.
#
# TAALKEUZE, HERZIEN 18 september 2026 (de ENGELSE feed hieronder
# als ON_THIS_DAY_API, niet Nederlands -- zie de volledige
# geschiedenis van deze beslissing hieronder).
#
# Oorspronkelijk gekozen: de Nederlandse feed (nl.wikipedia.org),
# om precies dezelfde reden als hieronder nog steeds geldt voor de
# afweging zelf -- vertalen zou stiekem ML/generatie onder een
# symbolisch jasje verbergen. MAAR: live getest op battleserver
# tegen de ECHTE API bleek de Nederlandse "On This Day"-feed
# structureel LEEG te zijn -- niet incidenteel mager, maar
# consistent leeg, zelfs voor de best-gedocumenteerde dagen die
# er zijn (11 september, 25 december kregen alle vijf categorieën
# als lege dict/lijst terug). De Engelse feed gaf voor exact
# dezelfde datum (25 december) 70 events, 229 geboortes, 133
# sterfgevallen. Dit is een bekend, gedocumenteerd Wikimedia-
# patroon (bevestigd via een vergelijkbaar gemeld probleem voor de
# Zweedse feed): de "On This Day"-feed wordt per taalversie zeer
# ongelijk onderhouden, los van hoe uitgebreid de gewone
# Wikipedia in die taal verder is.
#
# BESLISSING (Kevin, 18 september 2026): nu overschakelen naar de
# ENGELSE feed (rijke, betrouwbare data), de tekst zelf blijft dus
# in het Engels -- eerlijk zo vermeld, geen vertaling. Op termijn,
# als APART, bewust project: een LOKAAL draaiend vertaalmodel
# overwegen (bv. Argos Translate of een klein Marian/NLLB-model via
# transformers) om de Engelse tekst naar het Nederlands om te
# zetten. Dat zou, in tegenstelling tot een cloud-LLM-aanroep, wél
# lokaal en zonder externe afhankelijkheid draaien -- maar blijft
# niettemin een ML-model, geen symbolische berekening. Als dat ooit
# gebouwd wordt, hoort het expliciet benoemd te worden als "extern
# gespecialiseerd tool" (toegestaan, zoals vastgelegd in Nova's
# kernprincipes), nooit stilzwijgend voorgesteld als symbolisch.
#
# SCOPE: enkel de datum -> namen/gebeurtenissen richting. "Wanneer
# is [persoon] geboren/overleden" (naam -> datum) is bewust NIET
# gebouwd -- de On This Day API werkt alleen andersom, dat zou een
# heel ander soort Wikipedia-opzoeking vereisen (dichter bij
# wikipedia_teacher.py's aanpak). Apart werkpunt voor later.
#
# Apart bestand t.o.v. calendar.py/holidays.py/vakanties.py: dit is
# de enige van de vier die een externe netwerkaanroep doet (de
# andere drie zijn pure berekeningen) -- een fundamenteel andere
# soort taak, met een eigen faalmodus (geen internet/Wikipedia
# onbereikbaar) die de andere drie niet hebben.
#
# ------------------------------------------------------------
# ONDERDEEL 5 -- VERVOLGVRAGEN (26 september 2026)
# ------------------------------------------------------------
# date_calendar_roadmap.md Onderdeel 5 + het vervolgontwerp uit
# nova_state.md (punt 22). Na elk antwoord toont Nova de feiten nu
# als GENUMMERDE lijst, en kan Kevin verder vragen:
#
#   "meer" / "nog meer" / "is er nog meer gebeurd"
#       -> de volgende 3 feiten van DEZELFDE datum en categorie
#          (4-6, dan 7-9, ...). De nummering loopt door, zodat
#          elk nummer altijd naar hetzelfde feit blijft wijzen.
#   een nummer ("2")
#       -> een korte Wikipedia-samenvatting van dat feit. GEEN extra
#          netwerkaanroep: de On This Day-respons bevat per feit al
#          een "pages"-lijst met kant-en-klare samenvattingen
#          ("extract") en de link naar de volledige pagina.
#   "ja" (na "Wil je de volledige pagina openen op je laptop?")
#       -> de pagina wordt geopend in de browser op Kevins LAPTOP,
#          via client_bridge.py's stuur_commando_naar_laptop()
#          ("open_url"). NIET via webbrowser.open() hier: Nova draait
#          op battleserver (headless Docker) -- daar is geen scherm
#          en geen browser.
#
# BEWUST GEEN pending_question.py (zelfde keuze als nova_state.md
# vastlegt, en als wikipedia_teacher.py's _pending_wiki_choice):
# dat systeem is gereserveerd voor ja/nee-vragen, dit is een keuze
# uit een genummerde lijst. Eigen, lichte state in self._vervolg,
# gecheckt door intent_router.py's route() via verwerk_vervolg()
# (stap -1C2, vlak na de Wikipedia-keuzevraag, VÓÓR de generieke
# "text.isdigit()"-sense-keuze).
#
# De state vervalt zodra Kevin iets ANDERS typt (net als bij
# _pending_wiki_choice), én sowieso na VERVOLG_VERVAL_SECONDEN --
# Nova draait 24/7, een losse "2" de volgende ochtend mag niet
# alsnog naar een lijst van gisteren verwijzen.
#
# EERLIJKE GRENS -- welke pagina bij een feit hoort: een feit linkt
# vaak naar MEERDERE Wikipedia-pagina's (de gebeurtenis zelf, maar
# ook bv. een land of een persoon). Nova neemt de EERSTE bruikbare
# pagina uit Wikipedia's eigen lijst (en slaat pure jaartal-pagina's
# zoals "1978" over). Dat is een simpele, structurele keuze -- GEEN
# inhoudelijk begrip van welke pagina "de juiste" is. Nova toont
# daarom altijd de paginatitel erbij, zodat Kevin ziet waarover de
# samenvatting gaat.
# ============================================================

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

ON_THIS_DAY_API = "https://en.wikipedia.org/api/rest_v1/feed/onthisday/all/"

MAX_FEITEN_PER_ANTWOORD = 3

# Onderdeel 5: hoe lang blijft een getoonde lijst "actief" voor
# vervolgvragen ("meer", een nummer, "ja")? 10 minuten.
VERVOLG_VERVAL_SECONDEN = 10 * 60

# Onderdeel 5: maximale lengte van een samenvatting -- zelfde grens
# als wikipedia_teacher.py's _extract_definition() (MAX_LENGTH = 400).
MAX_SAMENVATTING_LENGTE = 400

# Onderdeel 5: woorden/zinnen die "toon de volgende reeks" betekenen.
# Vaste lijst, zelfde aanpak als detect_trending_query()'s vaste zinnen.
MEER_TRIGGERS = {
    "meer", "nog meer", "en nog meer", "volgende", "verder", "ga verder",
    "is er nog meer gebeurd", "wat is er nog meer gebeurd",
    "wat is er nog gebeurd", "wie nog", "wie is er nog meer geboren",
    "wie is er nog meer overleden", "wie is er nog meer gestorven",
    "toon meer", "laat meer zien",
}

JA_WOORDEN = {
    "ja", "jaa", "ja graag", "graag", "ok", "oké", "oke", "okay", "yes",
    "doe maar", "ja doe maar", "open maar", "ja open maar", "open",
    "zeker", "ja zeker", "goed",
}
NEE_WOORDEN = {
    "nee", "neen", "nee dank je", "nee bedankt", "no", "nope",
    "laat maar", "niet nodig", "hoeft niet",
}


class OnThisDayModule:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.zone = event_bus.get_module("zone")  # optioneel, zelfde als calendar.py

        # Onderdeel 5: state voor vervolgvragen. None = geen actieve
        # lijst. Anders een dict met:
        #   "categorie":  "events" / "births" / "deaths"
        #   "kop":        "Op deze dag" / "Geboren op deze dag" / ...
        #   "entries":    ALLE ruwe entries van die categorie (niet
        #                 enkel de getoonde)
        #   "getoond":    hoeveel entries er al getoond zijn
        #   "tijd":       time.time() van het laatste gebruik
        #   "open_url":   URL die op een "ja" wacht, of None
        #   "open_titel": paginatitel bij die URL, of None
        self._vervolg = None

        event_bus.subscribe("intent_on_this_day_query", self.on_this_day_intent)

    # --------------------------------------------------------
    # Lokale datum ophalen (zelfde aanpak als calendar.py/
    # holidays.py/vakanties.py's today())
    # --------------------------------------------------------
    def today(self):
        if self.zone:
            return self.zone.now_local().date()
        return datetime.now().date()

    # --------------------------------------------------------
    # De ruwe API-aanroep. Zelfde patroon als wikipedia_teacher.py:
    # urllib.request met dezelfde User-Agent, timeout=5,
    # HTTPError apart van een generieke Exception afgevangen.
    # Geeft None terug bij eender welke fout (geen internet, geen
    # Wikipedia-respons, corrupte JSON, ...) -- nooit een crash,
    # nooit een gok naar de aanroeper toe over WAAROM het faalde;
    # dat wordt in on_this_day_intent()/de antwoord_*()-methodes
    # netjes en eerlijk gemeld.
    # --------------------------------------------------------
    def _fetch_dag_data(self, maand, dag):
        url = f"{ON_THIS_DAY_API}{maand:02d}/{dag:02d}"

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Nova-AI/1.0 (educational project)"},
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data
        except urllib.error.HTTPError:
            return None
        except Exception:
            return None

    # --------------------------------------------------------
    # Eén categorie (events/births/deaths) uit de ruwe data
    # halen, met de eerste MAX_FEITEN_PER_ANTWOORD entries.
    # Geeft een lege lijst terug als de categorie ontbreekt of
    # leeg is -- dat is precies het "mager/leeg voor deze dag"-
    # geval dat we eerlijk willen kunnen melden, geen crash.
    #
    # BUG GEVONDEN TIJDENS LIVE TESTEN (18 september 2026, Kevin):
    # de ECHTE Wikipedia-API geeft voor een lege categorie een LEGE
    # DICT ({}) terug, niet een lege lijst ([]), zoals bevestigd met
    # curl tegen de nl.wikipedia.org-API zelf. entries[:N] op een
    # dict geeft "TypeError: unhashable type: 'slice'" (slicen werkt
    # niet op een dict). Dit kon niet vooraf getest worden -- geen
    # netwerktoegang tot wikipedia.org vanuit de ontwikkelomgeving
    # waarin deze module gebouwd is; enkel gesimuleerde/nagebouwde
    # responses waren beschikbaar, en die simuleerden per ongeluk
    # het EN-gedrag (waar de bronnen wél consistent leken te zeggen
    # dat een lege categorie [] geeft), niet het feitelijke NL-gedrag.
    # Fix: expliciet checken of entries een lijst is vóór het slicen.
    # --------------------------------------------------------
    def _haal_feiten_op(self, data, categorie):
        return self._alle_feiten(data, categorie)[:MAX_FEITEN_PER_ANTWOORD]

    # --------------------------------------------------------
    # Onderdeel 5: ALLE entries van een categorie (niet enkel de
    # eerste 3), zodat "meer" kan doorschuiven zonder een nieuwe
    # API-aanroep. Zelfde lege-dict-bescherming als hierboven.
    # --------------------------------------------------------
    def _alle_feiten(self, data, categorie):
        if data is None:
            return []
        entries = data.get(categorie, [])
        if not isinstance(entries, list):
            return []
        return entries

    # --------------------------------------------------------
    # Eén entry (uit events/births/deaths) formatteren tot een
    # leesbare regel: "<jaar>: <tekst>". Geeft None terug als de
    # entry geen bruikbare tekst/jaar heeft (defensief, voor het
    # geval Wikipedia een onvolledige entry teruggeeft).
    # --------------------------------------------------------
    def _formatteer_entry(self, entry):
        jaar = entry.get("year")
        tekst = entry.get("text", "").strip()
        if not tekst:
            return None
        if jaar is not None:
            return f"{jaar}: {tekst}"
        return tekst

    # --------------------------------------------------------
    # Event-handler
    # --------------------------------------------------------
    def on_this_day_intent(self, data, event_type=None):
        vraag_type = data.get("type", "events")
        text = data.get("text", "")

        if vraag_type == "geboren":
            self.antwoord_geboren(text)
        elif vraag_type == "overleden":
            self.antwoord_overleden(text)
        else:
            self.antwoord_events(text)

    # --------------------------------------------------------
    # Datum uit tekst halen, met dezelfde parsing als calendar.py
    # (lazy import, om geen harde afhankelijkheid/circulaire
    # import te creëren -- zelfde patroon als holidays.py's
    # eigen lazy imports van calendar.py). Zonder herkenbare
    # datum in de tekst: gewoon vandaag.
    # --------------------------------------------------------
    def _bepaal_maand_dag(self, text):
        vandaag = self.today()

        try:
            from modules.time.calendar import CalendarModule
        except ImportError:
            return vandaag.month, vandaag.day, vandaag

        tijdelijke_calendar = CalendarModule.__new__(CalendarModule)
        # _parse_datum() heeft geen event_bus/zone nodig zolang de
        # tekst geen "vandaag"/"morgen"-achtig relatief patroon
        # bevat dat today() aanroept zonder dat self.zone bestaat --
        # om dat risico te vermijden, zetten we hier toch een
        # bruikbare today() op de tijdelijke instantie.
        tijdelijke_calendar.today = lambda: vandaag

        gevonden_datum = tijdelijke_calendar._parse_datum(text.lower())
        if gevonden_datum is None:
            return vandaag.month, vandaag.day, vandaag
        return gevonden_datum.month, gevonden_datum.day, gevonden_datum

    # --------------------------------------------------------
    # Nette boodschap bij geen internet/Wikipedia onbereikbaar.
    # --------------------------------------------------------
    def _geen_data_beschikbaar(self):
        msg = (
            "Ik kon Wikipedia niet bereiken om dat op te zoeken. "
            "Probeer het straks nog eens."
        )
        self.event_bus.publish("layer4_response", {"text": msg})

    # --------------------------------------------------------
    # Nette boodschap bij een lege/magere feed voor die specifieke
    # dag -- eerlijk, geen gok, geen aanvulling. Zeldzaam bij de
    # Engelse feed (in tegenstelling tot de eerder geprobeerde
    # Nederlandse feed, die structureel leeg bleek), maar
    # theoretisch nog steeds mogelijk voor een obscure datum.
    # --------------------------------------------------------
    def _weinig_gevonden(self, categorie_label):
        msg = f"Ik heb weinig {categorie_label} gevonden voor deze dag op Wikipedia."
        self.event_bus.publish("layer4_response", {"text": msg})

    # --------------------------------------------------------
    # Gedeelde kern van de drie antwoord_*()-methodes hieronder
    # (Onderdeel 5): ophalen, eerste reeks tonen, en de volledige
    # lijst onthouden voor vervolgvragen.
    # --------------------------------------------------------
    def _beantwoord_categorie(self, text, categorie, kop, leeg_label):
        # Een nieuwe vraag vervangt altijd een eventuele oude lijst.
        self._vervolg = None

        maand, dag, datum = self._bepaal_maand_dag(text)
        data = self._fetch_dag_data(maand, dag)

        if data is None:
            self._geen_data_beschikbaar()
            return

        # Enkel entries met bruikbare tekst meenemen -- zo klopt de
        # nummering altijd met wat Kevin effectief te zien krijgt.
        entries = [e for e in self._alle_feiten(data, categorie)
                   if isinstance(e, dict) and self._formatteer_entry(e)]

        if not entries:
            self._weinig_gevonden(leeg_label)
            return

        self._vervolg = {
            "categorie": categorie,
            "kop": kop,
            "entries": entries,
            "getoond": 0,
            "tijd": time.time(),
            "open_url": None,
            "open_titel": None,
        }
        self._toon_volgende_reeks()

    # --------------------------------------------------------
    # Toont de volgende MAX_FEITEN_PER_ANTWOORD entries uit de
    # actieve lijst, genummerd (doorlopende nummering: 1-3, dan
    # 4-6, ...), met een korte uitleg wat Kevin nu kan typen.
    # --------------------------------------------------------
    def _toon_volgende_reeks(self):
        v = self._vervolg
        start = v["getoond"]
        reeks = v["entries"][start:start + MAX_FEITEN_PER_ANTWOORD]

        regels = []
        for i, entry in enumerate(reeks, start=start + 1):
            regels.append(f"  {i}. {self._formatteer_entry(entry)}")

        v["getoond"] = start + len(reeks)
        v["tijd"] = time.time()
        v["open_url"] = None
        v["open_titel"] = None

        nog_meer = v["getoond"] < len(v["entries"])
        if nog_meer:
            uitleg = "Typ een nummer voor meer uitleg, of 'meer' voor de volgende."
        else:
            uitleg = "Typ een nummer voor meer uitleg."

        kop = v["kop"] if start == 0 else f"{v['kop']} (vervolg)"
        msg = f"{kop}:\n" + "\n".join(regels) + "\n" + uitleg
        self.event_bus.publish("layer4_response", {"text": msg})

    # --------------------------------------------------------
    # "Wat is er gebeurd op [datum]?"
    # --------------------------------------------------------
    def antwoord_events(self, text):
        self._beantwoord_categorie(text, "events", "Op deze dag", "gebeurtenissen")

    # --------------------------------------------------------
    # "Wie is er geboren op [datum]?"
    # --------------------------------------------------------
    def antwoord_geboren(self, text):
        self._beantwoord_categorie(text, "births", "Geboren op deze dag", "geboortes")

    # --------------------------------------------------------
    # "Wie is er overleden op [datum]?"
    # --------------------------------------------------------
    def antwoord_overleden(self, text):
        self._beantwoord_categorie(text, "deaths", "Overleden op deze dag", "sterfgevallen")

    # ========================================================
    # ONDERDEEL 5 -- vervolgvragen
    # ========================================================

    # --------------------------------------------------------
    # Wordt door intent_router.py's route() aangeroepen voor ELK
    # bericht (stap -1C2), zelfde contract als wikipedia_teacher.py's
    # verwerk_wiki_keuze():
    #   True  -> dit bericht was een vervolgvraag en is afgehandeld,
    #            route() moet stoppen
    #   False -> geen actieve lijst, of het bericht hoort er niet
    #            bij; route() gaat gewoon verder. In dat laatste
    #            geval vervalt de lijst (Kevin is over iets anders
    #            begonnen).
    # --------------------------------------------------------
    def verwerk_vervolg(self, text):
        if self._vervolg is None:
            return False

        if time.time() - self._vervolg["tijd"] > VERVOLG_VERVAL_SECONDEN:
            self._vervolg = None
            return False

        t = (text or "").lower().strip().rstrip("?.!")
        t = re.sub(r"\s+", " ", t)

        # 1. Staat er een "open de pagina?"-vraag open? Dan eerst ja/nee.
        if self._vervolg["open_url"] is not None:
            if t in JA_WOORDEN:
                self._open_op_laptop()
                return True
            if t in NEE_WOORDEN:
                self._vervolg["open_url"] = None
                self._vervolg["open_titel"] = None
                self._vervolg["tijd"] = time.time()
                self.event_bus.publish("layer4_response", {
                    "text": "Oké, geen probleem."
                })
                return True
            # Iets anders: de open-vraag vervalt, maar een nummer of
            # "meer" hieronder blijft gewoon geldig.
            self._vervolg["open_url"] = None
            self._vervolg["open_titel"] = None

        # 2. Een nummer uit de lijst?
        if t.isdigit():
            nummer = int(t)
            if 1 <= nummer <= self._vervolg["getoond"]:
                self._toon_samenvatting(nummer)
            else:
                self.event_bus.publish("layer4_response", {
                    "text": (
                        f"Dat nummer staat niet in de lijst -- kies een "
                        f"nummer van 1 tot {self._vervolg['getoond']}."
                    )
                })
                self._vervolg["tijd"] = time.time()
            return True

        # 3. "meer" / "is er nog meer gebeurd" / ...
        if t in MEER_TRIGGERS:
            if self._vervolg["getoond"] >= len(self._vervolg["entries"]):
                self.event_bus.publish("layer4_response", {
                    "text": "Dat waren ze allemaal voor deze dag."
                })
                self._vervolg["tijd"] = time.time()
            else:
                self._toon_volgende_reeks()
            return True

        # 4. Iets anders: Kevin is over iets nieuws begonnen.
        self._vervolg = None
        return False

    # --------------------------------------------------------
    # Kiest de eerste bruikbare Wikipedia-pagina uit de "pages"-lijst
    # van een entry. Geeft een dict {"titel", "samenvatting", "url"}
    # terug, of None als er geen bruikbare pagina met samenvatting
    # is. Pure jaartal-pagina's ("1978") worden overgeslagen -- die
    # zeggen niets over het feit zelf. Zie "EERLIJKE GRENS" bovenaan.
    #
    # Defensief geschreven: de exacte veldnamen komen uit Wikimedia's
    # "page summary"-formaat (titles.normalized / normalizedtitle /
    # title, extract, content_urls.desktop.page). Ontbreekt de link,
    # dan wordt hij opgebouwd uit de titel.
    # --------------------------------------------------------
    def _kies_pagina(self, entry):
        pages = entry.get("pages")
        if not isinstance(pages, list):
            return None

        for page in pages:
            if not isinstance(page, dict):
                continue

            titels = page.get("titles") if isinstance(page.get("titles"), dict) else {}
            titel = (
                titels.get("normalized")
                or page.get("normalizedtitle")
                or (page.get("title") or "").replace("_", " ")
            ).strip()
            samenvatting = (page.get("extract") or "").strip()

            if not titel or not samenvatting:
                continue
            if titel.isdigit():
                continue

            url = None
            content_urls = page.get("content_urls")
            if isinstance(content_urls, dict):
                desktop = content_urls.get("desktop")
                if isinstance(desktop, dict):
                    url = desktop.get("page")
            if not url:
                url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(
                    titel.replace(" ", "_")
                )

            return {"titel": titel, "samenvatting": samenvatting, "url": url}

        return None

    # --------------------------------------------------------
    # Kort een samenvatting in tot max. MAX_SAMENVATTING_LENGTE
    # tekens, afgekapt op een volledige zin (of anders een heel
    # woord) -- zelfde regels als wikipedia_teacher.py's
    # _extract_definition(): nooit midden in een woord.
    # --------------------------------------------------------
    def _kort_in(self, tekst):
        tekst = " ".join(tekst.split())
        if len(tekst) <= MAX_SAMENVATTING_LENGTE:
            return tekst

        afgekapt = tekst[:MAX_SAMENVATTING_LENGTE]
        laatste_punt = afgekapt.rfind(". ")
        if laatste_punt > 0:
            return afgekapt[:laatste_punt + 1]
        laatste_spatie = afgekapt.rfind(" ")
        if laatste_spatie > 0:
            return afgekapt[:laatste_spatie] + "..."
        return afgekapt

    # --------------------------------------------------------
    # Toont de samenvatting van feit <nummer>, en biedt aan de
    # volledige pagina te openen -- ENKEL als de laptop op dit moment
    # verbonden is (anders zou Nova iets aanbieden wat ze niet kan).
    # --------------------------------------------------------
    def _toon_samenvatting(self, nummer):
        v = self._vervolg
        entry = v["entries"][nummer - 1]
        v["tijd"] = time.time()

        pagina = self._kies_pagina(entry)
        if pagina is None:
            self.event_bus.publish("layer4_response", {
                "text": (
                    f"Wikipedia gaf bij feit {nummer} geen samenvatting mee, "
                    "dus daar kan ik je niet meer over vertellen."
                )
            })
            return

        msg = f"{pagina['titel']}: {self._kort_in(pagina['samenvatting'])}"

        if self._laptop_verbonden():
            v["open_url"] = pagina["url"]
            v["open_titel"] = pagina["titel"]
            msg += "\nWil je de volledige pagina openen op je laptop? (ja/nee)"

        self.event_bus.publish("layer4_response", {"text": msg})

    def _client_bridge(self):
        modules = getattr(self.event_bus, "modules", None) or {}
        return modules.get("client_bridge")

    def _laptop_verbonden(self):
        bridge = self._client_bridge()
        if bridge is None:
            return False
        try:
            return bool(bridge.is_laptop_verbonden())
        except Exception:
            return False

    # --------------------------------------------------------
    # Stuurt het "open_url"-commando naar nova_client.py op de
    # laptop. Zelfde patroon als intent_router.py's
    # detect_open_app(): stuur_commando_naar_laptop() wacht zelf op
    # het resultaat en gooit nooit een exception.
    #
    # VEILIGHEID: nova_client.py controleert ZELF nog eens dat de URL
    # een https-link naar wikipedia.org is (zie _open_url() daar) --
    # de laptop vertrouwt dus niet blind wat battleserver stuurt.
    # --------------------------------------------------------
    def _open_op_laptop(self):
        v = self._vervolg
        url = v["open_url"]
        titel = v["open_titel"]
        v["open_url"] = None
        v["open_titel"] = None
        v["tijd"] = time.time()

        bridge = self._client_bridge()
        if bridge is None:
            self.event_bus.publish("layer4_response", {
                "text": "Ik kan niets openen — de laptop-verbinding is niet geladen."
            })
            return

        resultaat = bridge.stuur_commando_naar_laptop("open_url", {"url": url})

        if resultaat.get("ok"):
            self.event_bus.publish("layer4_response", {
                "text": f"De pagina over {titel} staat open op je laptop."
            })
        else:
            reden = resultaat.get("reden") or "onbekende fout"
            self.event_bus.publish("layer4_response", {
                "text": f"Dat lukte niet: {reden}"
            })


def init_module(event_bus):
    mod = OnThisDayModule(event_bus)
    event_bus.publish("module_loaded", {"name": "on_this_day"})
    return mod