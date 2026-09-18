# modules/time/holidays.py

# ============================================================
# HolidaysModule
# ------------------------------------------------------------
# Feestdagen (date_calendar_roadmap.md, Onderdeel 2): vaste
# feestdagen (elk jaar dezelfde datum, simpele opzoektabel) en
# bewegende feestdagen (afhankelijk van Pasen, berekend via het
# "computus"-algoritme -- een eeuwenoude, wiskundige formule).
#
# BELANGRIJK, zoals de roadmap het zelf al stelt: dit is GEEN
# voorspelling of schatting. De Paasformule is exact en
# wiskundig bewezen correct voor elk jaar -- dezelfde input
# (jaartal) geeft altijd exact dezelfde, correcte uitkomst. Dit
# hoort dus volledig thuis in de categorie "berekenen", niet
# "interpreteren". Puur symbolisch, 100% Python's ingebouwde
# datetime, geen enkele externe dependency, geen ML.
#
# Apart bestand t.o.v. calendar.py (bewust zo afgesproken met
# Kevin, 17 september 2026): dit is een andere soort taak dan
# calendar.py's "vergelijk met vandaag" -- hier draait alles om
# een vaste tabel + een formule-algoritme, geen zone/today()-
# afhankelijkheid nodig voor de berekening zelf (wel voor "is
# het nu een feestdag", zie is_vandaag_feestdag() hieronder).
# Zelfde precedent als math.py/math_uitleg.py: aparte taken,
# apart bestand.
#
# SCOPE: enkel de Belgische/Vlaamse feestdagenkalender (Kevin is
# in België gevestigd). Geen ander land, geen internationale
# feestdagen -- dat zou een andere, veel grotere tabel vergen en
# is niet gevraagd.
# ============================================================

from datetime import date, timedelta

# --------------------------------------------------------
# VASTE feestdagen: elk jaar dezelfde datum, geen berekening
# nodig. (maand, dag) -> naam.
# --------------------------------------------------------
VASTE_FEESTDAGEN = {
    (1, 1): "Nieuwjaar",
    (5, 1): "Dag van de Arbeid",
    (7, 11): "Feestdag Vlaamse Gemeenschap",
    (7, 21): "Nationale feestdag België",
    (8, 15): "Onze-Lieve-Vrouw Hemelvaart",
    (10, 31): "Halloween",
    (11, 1): "Allerheiligen",
    (11, 11): "Wapenstilstand",
    (12, 6): "Sinterklaas",
    (12, 25): "Kerstmis",
}

# --------------------------------------------------------
# BEWEGENDE feestdagen: offset in dagen t.o.v. Pasen (kan
# negatief zijn, zoals Carnaval). Naam -> offset.
# --------------------------------------------------------
BEWEGENDE_FEESTDAGEN_OFFSET = {
    "Carnaval": -47,
    "Pasen": 0,
    "Paasmaandag": 1,
    "Hemelvaart": 39,
    "Pinksteren": 49,
    "Pinkstermaandag": 50,
}

# --------------------------------------------------------
# Alledaagse benamingen die niet letterlijk overeenkomen met de
# officiële naam in VASTE_FEESTDAGEN/BEWEGENDE_FEESTDAGEN_OFFSET
# hierboven, bv. "kerst" i.p.v. "Kerstmis". Alias (kleine letters)
# -> officiële naam. Wordt gebruikt in antwoord_wanneer_is() zodat
# Kevin niet de exacte officiële naam hoeft te kennen.
# --------------------------------------------------------
FEESTDAG_ALIASSEN = {
    "kerst": "Kerstmis",
    "kerstdag": "Kerstmis",
    "nieuwjaarsdag": "Nieuwjaar",
    "nieuwjaar": "Nieuwjaar",
    "sint": "Sinterklaas",
}


def bereken_pasen(jaar):
    """Berekent de datum van Pasen voor een gegeven jaar via het
    "computus"-algoritme (Meeus/Jones/Butcher, Gregoriaanse
    kalender). Exact en deterministisch -- geen schatting, geen
    ML, gewoon een vaste reeks berekeningen. Geverifieerd tegen
    officieel bevestigde paasdatums 1900-2030 (zie
    test_holidays.py)."""
    a = jaar % 19
    b = jaar // 100
    c = jaar % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    maand = (h + l - 7 * m + 114) // 31
    dag = ((h + l - 7 * m + 114) % 31) + 1
    return date(jaar, maand, dag)


class HolidaysModule:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.zone = event_bus.get_module("zone")  # optioneel, zelfde als calendar.py

        event_bus.subscribe("intent_holiday_query", self.on_holiday_intent)

    # --------------------------------------------------------
    # Lokale datum ophalen (zelfde aanpak als calendar.py's
    # today())
    # --------------------------------------------------------
    def today(self):
        if self.zone:
            return self.zone.now_local().date()
        from datetime import datetime
        return datetime.now().date()

    # --------------------------------------------------------
    # Alle bewegende feestdagen voor een jaar, in één keer
    # berekend vanuit dezelfde Pasen-datum (voorkomt dat Pasen
    # 6x apart herberekend wordt).
    # --------------------------------------------------------
    def bewegende_feestdagen(self, jaar):
        """Geeft een dict {naam: date} terug met alle bewegende
        feestdagen voor het gegeven jaar."""
        pasen = bereken_pasen(jaar)
        return {
            naam: pasen + timedelta(days=offset)
            for naam, offset in BEWEGENDE_FEESTDAGEN_OFFSET.items()
        }

    # --------------------------------------------------------
    # Eén feestdag opzoeken op naam, voor een gegeven jaar.
    # Case-insensitive. Geeft None terug als de naam niet
    # gekend is -- nooit een gok.
    # --------------------------------------------------------
    def datum_van_feestdag(self, naam, jaar):
        naam_lower = naam.lower().strip()

        for (maand, dag), vaste_naam in VASTE_FEESTDAGEN.items():
            if vaste_naam.lower() == naam_lower:
                return date(jaar, maand, dag)

        for bewegende_naam, datum in self.bewegende_feestdagen(jaar).items():
            if bewegende_naam.lower() == naam_lower:
                return datum

        return None

    # --------------------------------------------------------
    # Is een gegeven datum een feestdag? Geeft (True, naam) of
    # (False, None) terug.
    # --------------------------------------------------------
    def is_feestdag(self, datum):
        vaste_naam = VASTE_FEESTDAGEN.get((datum.month, datum.day))
        if vaste_naam:
            return True, vaste_naam

        for naam, bewegende_datum in self.bewegende_feestdagen(datum.year).items():
            if bewegende_datum == datum:
                return True, naam

        return False, None

    # --------------------------------------------------------
    # Alle feestdagen van een jaar, gesorteerd op datum -- vast
    # en bewegend samen.
    # --------------------------------------------------------
    def alle_feestdagen_van_jaar(self, jaar):
        """Geeft een gesorteerde lijst van (date, naam)-tuples
        terug, vaste en bewegende feestdagen samen."""
        resultaat = []
        for (maand, dag), naam in VASTE_FEESTDAGEN.items():
            resultaat.append((date(jaar, maand, dag), naam))
        for naam, datum in self.bewegende_feestdagen(jaar).items():
            resultaat.append((datum, naam))
        return sorted(resultaat, key=lambda paar: paar[0])

    # --------------------------------------------------------
    # Eerstvolgende feestdag vanaf een gegeven datum (exclusief
    # die datum zelf -- "vanaf morgen"). Kijkt zo nodig in het
    # volgende jaar door (voor eind december).
    # --------------------------------------------------------
    def volgende_feestdag(self, vanaf_datum):
        """Geeft (date, naam) terug van de eerstvolgende feestdag
        na vanaf_datum. Zoekt door naar het jaar erna als er dit
        jaar geen meer over zijn."""
        kandidaten = [
            (d, naam)
            for d, naam in self.alle_feestdagen_van_jaar(vanaf_datum.year)
            if d > vanaf_datum
        ]
        if kandidaten:
            return kandidaten[0]

        volgend_jaar = self.alle_feestdagen_van_jaar(vanaf_datum.year + 1)
        return volgend_jaar[0]

    # --------------------------------------------------------
    # Event-handler
    # --------------------------------------------------------
    def on_holiday_intent(self, data, event_type=None):
        vraag_type = data.get("type", "")
        text = data.get("text", "")

        if vraag_type == "wanneer_is":
            self.antwoord_wanneer_is(text)
        elif vraag_type == "is_vandaag_feestdag":
            self.antwoord_is_vandaag_feestdag()
        elif vraag_type == "volgende_feestdag":
            self.antwoord_volgende_feestdag()
        else:
            self._geen_feestdag_herkend()

    # --------------------------------------------------------
    # Nette "dat ken ik niet"-boodschap, hergebruikt bij een
    # onherkende feestdagnaam.
    # --------------------------------------------------------
    def _geen_feestdag_herkend(self, genoemde_naam=None):
        if genoemde_naam:
            msg = (
                f"Ik ken '{genoemde_naam}' niet als feestdag. Ik weet "
                f"wel wanneer Kerst, Pasen, Nieuwjaar en de andere "
                f"Belgische feestdagen vallen."
            )
        else:
            msg = (
                "Welke feestdag bedoel je precies? Ik kan bijvoorbeeld "
                "zeggen wanneer Kerst of Pasen valt."
            )
        self.event_bus.publish("layer4_response", {"text": msg})

    # --------------------------------------------------------
    # "Wanneer is Pasen (dit jaar)?" / "Wanneer valt Kerst?"
    # --------------------------------------------------------
    def antwoord_wanneer_is(self, text):
        t = text.lower().strip().rstrip("?.!")

        # Zoek welke feestdagnaam genoemd wordt. Combineert de
        # officiële namen MET hun aliassen (bv. "kerst" -> "Kerstmis")
        # in één (gezochte_tekst, officiële_naam)-lijst, en sorteert
        # ALLES samen op lengte, langste eerst -- zodat bv.
        # "pinkstermaandag" niet per ongeluk als "pinksteren" matcht
        # (beide delen "pinkster" als prefix), en "kerstdag" niet als
        # het kortere "kerst" matcht vóór de langere vorm een kans
        # heeft gekregen.
        officiele_namen = list(VASTE_FEESTDAGEN.values()) + list(
            BEWEGENDE_FEESTDAGEN_OFFSET.keys()
        )
        zoek_paren = [(naam.lower(), naam) for naam in officiele_namen]
        zoek_paren += list(FEESTDAG_ALIASSEN.items())
        zoek_paren_gesorteerd = sorted(
            zoek_paren, key=lambda paar: len(paar[0]), reverse=True
        )

        gevonden_naam = None
        for gezochte_tekst, officiele_naam in zoek_paren_gesorteerd:
            if gezochte_tekst in t:
                gevonden_naam = officiele_naam
                break

        if not gevonden_naam:
            self._geen_feestdag_herkend()
            return

        vandaag = self.today()
        jaar = vandaag.year
        datum = self.datum_van_feestdag(gevonden_naam, jaar)

        # Als de feestdag dit jaar al voorbij is, toon volgend
        # jaar (zelfde logica als calendar.py's automatische
        # jaarsprong) -- "wanneer is Kerst" op 27 december moet
        # niet een datum in het verleden teruggeven.
        if datum < vandaag:
            jaar += 1
            datum = self.datum_van_feestdag(gevonden_naam, jaar)

        from modules.time.calendar import DAGNAMEN, MAANDNAMEN

        dagnaam = DAGNAMEN[datum.weekday()]
        maandnaam = MAANDNAMEN[datum.month]
        msg = f"{gevonden_naam} valt dit jaar op {dagnaam} {datum.day} {maandnaam} {datum.year}."
        self.event_bus.publish("layer4_response", {"text": msg})

    # --------------------------------------------------------
    # "Is het vandaag een feestdag?"
    # --------------------------------------------------------
    def antwoord_is_vandaag_feestdag(self):
        vandaag = self.today()
        is_feest, naam = self.is_feestdag(vandaag)

        if is_feest:
            msg = f"Ja, vandaag is het {naam}!"
        else:
            msg = "Nee, vandaag is er geen feestdag."
        self.event_bus.publish("layer4_response", {"text": msg})

    # --------------------------------------------------------
    # "Wat is de volgende feestdag?"
    # --------------------------------------------------------
    def antwoord_volgende_feestdag(self):
        vandaag = self.today()
        datum, naam = self.volgende_feestdag(vandaag)

        from modules.time.calendar import DAGNAMEN, MAANDNAMEN

        dagnaam = DAGNAMEN[datum.weekday()]
        maandnaam = MAANDNAMEN[datum.month]
        aantal_dagen = (datum - vandaag).days

        if aantal_dagen == 1:
            msg = f"De volgende feestdag is {naam}, morgen ({dagnaam} {datum.day} {maandnaam} {datum.year})."
        else:
            msg = (
                f"De volgende feestdag is {naam}, over {aantal_dagen} dagen "
                f"({dagnaam} {datum.day} {maandnaam} {datum.year})."
            )
        self.event_bus.publish("layer4_response", {"text": msg})


def init_module(event_bus):
    mod = HolidaysModule(event_bus)
    event_bus.publish("module_loaded", {"name": "holidays"})
    return mod