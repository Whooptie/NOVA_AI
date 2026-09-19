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
# ============================================================

import json
import urllib.error
import urllib.request
from datetime import datetime

ON_THIS_DAY_API = "https://en.wikipedia.org/api/rest_v1/feed/onthisday/all/"

MAX_FEITEN_PER_ANTWOORD = 3


class OnThisDayModule:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.zone = event_bus.get_module("zone")  # optioneel, zelfde als calendar.py

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
        if data is None:
            return []
        entries = data.get(categorie, [])
        if not isinstance(entries, list):
            return []
        return entries[:MAX_FEITEN_PER_ANTWOORD]

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
    # "Wat is er gebeurd op [datum]?"
    # --------------------------------------------------------
    def antwoord_events(self, text):
        maand, dag, datum = self._bepaal_maand_dag(text)
        data = self._fetch_dag_data(maand, dag)

        if data is None:
            self._geen_data_beschikbaar()
            return

        feiten = self._haal_feiten_op(data, "events")
        regels = [r for r in (self._formatteer_entry(f) for f in feiten) if r]

        if not regels:
            self._weinig_gevonden("gebeurtenissen")
            return

        msg = "Op deze dag: " + " / ".join(regels)
        self.event_bus.publish("layer4_response", {"text": msg})

    # --------------------------------------------------------
    # "Wie is er geboren op [datum]?"
    # --------------------------------------------------------
    def antwoord_geboren(self, text):
        maand, dag, datum = self._bepaal_maand_dag(text)
        data = self._fetch_dag_data(maand, dag)

        if data is None:
            self._geen_data_beschikbaar()
            return

        feiten = self._haal_feiten_op(data, "births")
        regels = [r for r in (self._formatteer_entry(f) for f in feiten) if r]

        if not regels:
            self._weinig_gevonden("geboortes")
            return

        msg = "Geboren op deze dag: " + " / ".join(regels)
        self.event_bus.publish("layer4_response", {"text": msg})

    # --------------------------------------------------------
    # "Wie is er overleden op [datum]?"
    # --------------------------------------------------------
    def antwoord_overleden(self, text):
        maand, dag, datum = self._bepaal_maand_dag(text)
        data = self._fetch_dag_data(maand, dag)

        if data is None:
            self._geen_data_beschikbaar()
            return

        feiten = self._haal_feiten_op(data, "deaths")
        regels = [r for r in (self._formatteer_entry(f) for f in feiten) if r]

        if not regels:
            self._weinig_gevonden("sterfgevallen")
            return

        msg = "Overleden op deze dag: " + " / ".join(regels)
        self.event_bus.publish("layer4_response", {"text": msg})


def init_module(event_bus):
    mod = OnThisDayModule(event_bus)
    event_bus.publish("module_loaded", {"name": "on_this_day"})
    return mod