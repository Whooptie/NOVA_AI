# modules/time/vakanties.py

# ============================================================
# VakantiesModule
# ------------------------------------------------------------
# Vlaamse schoolvakanties (date_calendar_roadmap.md, Onderdeel 3):
# herfst-, kerst-, krokus-, paas- en zomervakantie.
#
# BELANGRIJKE CORRECTIE T.O.V. DE OORSPRONKELIJKE ROADMAP-AANNAME:
# de roadmap zelf stelde dat schoolvakantiedata GEEN berekening
# zijn, maar jaarlijkse politieke/administratieve beslissingen die
# een handmatige tabel zouden vereisen. Bij navraag (Kevin, 18
# september 2026, met bronverwijzingen naar de officiële regelgeving)
# bleek dit gedeeltelijk onjuist: alle 5 vakanties volgen in
# werkelijkheid een VASTE, officieel vastgelegde regel (Besluit van
# de Vlaamse Regering betreffende de vakantieregeling). Dit is dus
# WEL 100% symbolisch berekenbaar, voor onbeperkt veel jaren vooruit
# -- geen tabel-onderhoud nodig, in tegenstelling tot de oorspronkelijke
# aanname. Elke regel hieronder is geverifieerd tegen de officiële
# Vlaamse overheidsbron (vlaanderen.be/schoolvakanties) voor de
# schooljaren 2023-2024 t/m 2029-2030 -- zie test_vakanties.py.
#
# SCOPE: uitsluitend Vlaamse schoolvakanties (Kevins uitdrukkelijke
# keuze) -- niet de Franstalige of Duitstalige gemeenschap, die een
# eigen, afwijkende kalender hanteren.
#
# BEREKENING PER KALENDERJAAR (bewust zo gekozen i.p.v. per school-
# jaar): elke vakantie hoort bij het kalenderjaar waarin ze grotendeels
# ligt of start -- zelfde stijl als holidays.py's bewegende_feestdagen
# (jaar), dat ook een "jaar_van_pasen"-parameter gebruikt. Krokus- en
# paasvakantie van kalenderjaar X gebruiken Pasen VAN dat jaar X zelf.
#
# Apart bestand t.o.v. holidays.py: schoolvakanties zijn een andere
# soort kennis dan feestdagen (onderwijsregelgeving i.p.v. religieuze/
# nationale feestdagen), ook al gebruiken ze wel dezelfde Pasen-
# berekening. Hergebruikt holidays.py's bereken_pasen() (lazy import)
# i.p.v. het computus-algoritme een derde keer te dupliceren
# (calendar.py, holidays.py, en nu hier).
# ============================================================

from datetime import date, timedelta


# --------------------------------------------------------
# Officiële regelnamen, in de volgorde waarin het schooljaar
# ze doorloopt. Gebruikt voor "volgende vakantie"-sortering en
# voor het herkennen van vakantienamen in tekst.
# --------------------------------------------------------
VAKANTIE_NAMEN = [
    "Herfstvakantie",
    "Kerstvakantie",
    "Krokusvakantie",
    "Paasvakantie",
    "Zomervakantie",
]

# Alledaagse alternatieve benamingen -> officiële naam.
VAKANTIE_ALIASSEN = {
    "herfstvakantie": "Herfstvakantie",
    "allerheiligenvakantie": "Herfstvakantie",
    "kerstvakantie": "Kerstvakantie",
    "wintervakantie": "Kerstvakantie",
    "krokusvakantie": "Krokusvakantie",
    "carnavalsvakantie": "Krokusvakantie",
    "voorjaarsvakantie": "Krokusvakantie",
    "paasvakantie": "Paasvakantie",
    "lentevakantie": "Paasvakantie",
    "zomervakantie": "Zomervakantie",
    "grote vakantie": "Zomervakantie",
}


def _eerstvolgende_maandag_op_of_na(datum):
    """Geeft de eerstvolgende maandag terug, of datum zelf als het
    al een maandag is."""
    offset = (7 - datum.weekday()) % 7
    return datum + timedelta(days=offset)


def bereken_herfstvakantie(jaar):
    """Officiële regel: begint op de maandag van de week waarin
    1 november valt, en duurt 1 week. Uitzondering: als 1 november
    op een zondag valt, begint de vakantie pas op 2 november.
    Geverifieerd tegen vlaanderen.be voor 2023-2029 (7/7 correct)."""
    allerheiligen = date(jaar, 11, 1)
    if allerheiligen.weekday() == 6:  # zondag
        start = date(jaar, 11, 2)
    else:
        start = allerheiligen - timedelta(days=allerheiligen.weekday())
    einde = start + timedelta(days=6)
    return start, einde


def bereken_kerstvakantie(jaar):
    """Officiële regel: begint op de maandag van de week waarin
    25 december valt, en duurt 2 weken. Als 25 december op een
    zaterdag of zondag valt, begint de vakantie de maandag NA
    25 december. Geverifieerd tegen vlaanderen.be voor 2023-2028
    (6/6 correct). Let op: loopt door tot in het volgende
    kalenderjaar."""
    kerst = date(jaar, 12, 25)
    if kerst.weekday() in (5, 6):  # zaterdag of zondag
        start = kerst + timedelta(days=(7 - kerst.weekday()))
    else:
        start = kerst - timedelta(days=kerst.weekday())
    einde = start + timedelta(days=13)
    return start, einde


def bereken_krokusvakantie(jaar_van_pasen):
    """Officiële regel: begint op de 7e maandag vóór Pasen, en duurt
    1 week. De maandag van de paasweek zelf telt daarbij als de "1e
    maandag terug". Geverifieerd tegen vlaanderen.be voor Pasen-jaren
    2024-2028 (5/5 correct)."""
    from modules.time.holidays import bereken_pasen

    pasen = bereken_pasen(jaar_van_pasen)
    maandag_paasweek = pasen - timedelta(days=6)
    start = maandag_paasweek - timedelta(weeks=6)
    einde = start + timedelta(days=6)
    return start, einde


def bereken_paasvakantie(jaar_van_pasen):
    """Officiële regel (Besluit van de Vlaamse Regering), drie
    gevallen:
    - Als Pasen in maart valt: de vakantie begint de maandag NA
      Pasen, duurt 2 weken (14 dagen).
    - Als Pasen na 15 april valt: de vakantie begint de 2e maandag
      VOOR Pasen. Pasen zelf valt dan binnen de vakantie (aan het
      einde), en de vakantie loopt door tot en met Paasmaandag zelf
      (15 dagen totaal, één dag langer dan het normale geval).
    - Anders (het gangbare geval): de vakantie begint op de eerste
      maandag van april, duurt 2 weken (14 dagen).
    Geverifieerd tegen vlaanderen.be/otheo.be voor Pasen-jaren
    2024-2030 (7/7 correct, alle drie de gevallen gedekt)."""
    from modules.time.holidays import bereken_pasen

    pasen = bereken_pasen(jaar_van_pasen)

    if pasen.month == 3:
        start = pasen + timedelta(days=1)
        einde = start + timedelta(days=13)
    elif pasen > date(jaar_van_pasen, 4, 15):
        maandag_paasweek = pasen - timedelta(days=6)
        start = maandag_paasweek - timedelta(weeks=1)
        einde = start + timedelta(days=14)
    else:
        eerste_april = date(jaar_van_pasen, 4, 1)
        start = _eerstvolgende_maandag_op_of_na(eerste_april)
        einde = start + timedelta(days=13)

    return start, einde


def bereken_zomervakantie(jaar):
    """Officiële regel: altijd van 1 juli tot en met 31 augustus,
    ongeacht op welke dag van de week die vallen (bevestigd door
    Kevin: de exacte weekdag-verschuivingen die vlaanderen.be er nog
    bovenop vermeldt zijn beschrijvend, niet functioneel relevant
    voor "zit ik in de zomervakantie")."""
    start = date(jaar, 7, 1)
    einde = date(jaar, 8, 31)
    return start, einde


class VakantiesModule:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.zone = event_bus.get_module("zone")  # optioneel, zelfde als calendar.py

        event_bus.subscribe("intent_vakantie_query", self.on_vakantie_intent)

    # --------------------------------------------------------
    # Lokale datum ophalen (zelfde aanpak als calendar.py/
    # holidays.py's today())
    # --------------------------------------------------------
    def today(self):
        if self.zone:
            return self.zone.now_local().date()
        from datetime import datetime
        return datetime.now().date()

    # --------------------------------------------------------
    # Alle 5 vakanties voor een kalenderjaar, in één keer
    # opgebouwd. Krokus/Paas gebruiken Pasen VAN dat kalenderjaar
    # zelf (zie module-docstring).
    # --------------------------------------------------------
    def alle_vakanties_van_jaar(self, jaar):
        """Geeft een dict {officiële naam: (start_date, eind_date)}
        terug voor het gegeven kalenderjaar."""
        return {
            "Herfstvakantie": bereken_herfstvakantie(jaar),
            "Kerstvakantie": bereken_kerstvakantie(jaar),
            "Krokusvakantie": bereken_krokusvakantie(jaar),
            "Paasvakantie": bereken_paasvakantie(jaar),
            "Zomervakantie": bereken_zomervakantie(jaar),
        }

    # --------------------------------------------------------
    # Eén vakantie opzoeken op naam (of alias), voor een gegeven
    # kalenderjaar. Case-insensitive. Geeft None terug als de
    # naam niet gekend is.
    # --------------------------------------------------------
    def datum_van_vakantie(self, naam, jaar):
        naam_lower = naam.lower().strip()
        officiele_naam = VAKANTIE_ALIASSEN.get(naam_lower)
        if officiele_naam is None:
            # Ook de officiële naam zelf accepteren, hoofdletter-
            # ongevoelig, mocht die niet letterlijk in de aliassen
            # staan.
            for n in VAKANTIE_NAMEN:
                if n.lower() == naam_lower:
                    officiele_naam = n
                    break
        if officiele_naam is None:
            return None

        alle = self.alle_vakanties_van_jaar(jaar)
        return alle.get(officiele_naam)

    # --------------------------------------------------------
    # Is een gegeven datum onderdeel van een schoolvakantie?
    # Geeft (True, naam) of (False, None) terug. Kijkt in het
    # eigen kalenderjaar EN het vorige (voor de kerstvakantie die
    # doorloopt in januari), om geen vakantie te missen die over
    # de jaarwisseling heen loopt.
    # --------------------------------------------------------
    def is_vakantie(self, datum):
        for jaar in (datum.year, datum.year - 1):
            for naam, (start, einde) in self.alle_vakanties_van_jaar(jaar).items():
                if start <= datum <= einde:
                    return True, naam
        return False, None

    # --------------------------------------------------------
    # Alle vakanties die (gedeeltelijk) zichtbaar zijn rond een
    # gegeven datum, gesorteerd op startdatum -- gebruikt door
    # volgende_vakantie() om over de jaargrens heen te kunnen
    # zoeken zonder een vakantie te missen of dubbel te tellen.
    # --------------------------------------------------------
    def _kandidaten_rond(self, jaar):
        resultaat = []
        for naam, (start, einde) in self.alle_vakanties_van_jaar(jaar).items():
            resultaat.append((start, einde, naam))
        return sorted(resultaat, key=lambda tup: tup[0])

    # --------------------------------------------------------
    # Eerstvolgende vakantie vanaf een gegeven datum (exclusief
    # een vakantie waar je al middenin zit -- "volgende" betekent
    # de eerstvolgende die nog moet BEGINNEN).
    # --------------------------------------------------------
    def volgende_vakantie(self, vanaf_datum):
        """Geeft (start_date, eind_date, naam) terug van de
        eerstvolgende vakantie die na vanaf_datum begint. Zoekt
        door naar het jaar erna als er dit jaar geen meer over
        zijn."""
        kandidaten = [
            (start, einde, naam)
            for start, einde, naam in self._kandidaten_rond(vanaf_datum.year)
            if start > vanaf_datum
        ]
        if kandidaten:
            return kandidaten[0]

        volgend_jaar = self._kandidaten_rond(vanaf_datum.year + 1)
        return volgend_jaar[0]

    # --------------------------------------------------------
    # Event-handler
    # --------------------------------------------------------
    def on_vakantie_intent(self, data, event_type=None):
        vraag_type = data.get("type", "")
        text = data.get("text", "")

        if vraag_type == "wanneer_is":
            self.antwoord_wanneer_is(text)
        elif vraag_type == "is_nu_vakantie":
            self.antwoord_is_nu_vakantie()
        elif vraag_type == "volgende_vakantie":
            self.antwoord_volgende_vakantie()
        elif vraag_type == "dagen_tot_vakantie":
            self.antwoord_dagen_tot_vakantie()
        else:
            self._geen_vakantie_herkend()

    # --------------------------------------------------------
    # Nette "dat ken ik niet"-boodschap
    # --------------------------------------------------------
    def _geen_vakantie_herkend(self):
        msg = (
            "Welke vakantie bedoel je precies? Ik ken de herfst-, "
            "kerst-, krokus-, paas- en zomervakantie."
        )
        self.event_bus.publish("layer4_response", {"text": msg})

    # --------------------------------------------------------
    # Hulpmethode: consistente datumformattering, lazy import
    # van calendar.py's DAGNAMEN/MAANDNAMEN (zelfde aanpak als
    # holidays.py, om een circulaire import te vermijden).
    # --------------------------------------------------------
    def _formatteer_datum(self, datum):
        from modules.time.calendar import DAGNAMEN, MAANDNAMEN

        dagnaam = DAGNAMEN[datum.weekday()]
        maandnaam = MAANDNAMEN[datum.month]
        return f"{dagnaam} {datum.day} {maandnaam} {datum.year}"

    # --------------------------------------------------------
    # "Wanneer is de paasvakantie?"
    # --------------------------------------------------------
    def antwoord_wanneer_is(self, text):
        t = text.lower().strip().rstrip("?.!")

        # Langste namen eerst (geen bekende prefix-botsingen zoals
        # bij pinksteren/pinkstermaandag, maar dezelfde voorzichtige
        # aanpak als holidays.py voor consistentie).
        zoek_paren = [(naam.lower(), naam) for naam in VAKANTIE_NAMEN]
        zoek_paren += list(VAKANTIE_ALIASSEN.items())
        zoek_paren_gesorteerd = sorted(
            zoek_paren, key=lambda paar: len(paar[0]), reverse=True
        )

        gevonden_naam = None
        for gezochte_tekst, officiele_naam in zoek_paren_gesorteerd:
            if gezochte_tekst in t:
                gevonden_naam = officiele_naam
                break

        if gevonden_naam is None:
            self._geen_vakantie_herkend()
            return

        vandaag = self.today()
        jaar = vandaag.year
        start, einde = self.datum_van_vakantie(gevonden_naam, jaar)

        # Als de vakantie dit jaar al helemaal voorbij is, toon
        # volgend jaar -- zelfde automatische-jaarsprong-regel als
        # calendar.py/holidays.py.
        if einde < vandaag:
            jaar += 1
            start, einde = self.datum_van_vakantie(gevonden_naam, jaar)

        msg = (
            f"{gevonden_naam} loopt van {self._formatteer_datum(start)} "
            f"tot en met {self._formatteer_datum(einde)}."
        )
        self.event_bus.publish("layer4_response", {"text": msg})

    # --------------------------------------------------------
    # "Zijn we nu in vakantie?"
    # --------------------------------------------------------
    def antwoord_is_nu_vakantie(self):
        vandaag = self.today()
        in_vakantie, naam = self.is_vakantie(vandaag)

        if in_vakantie:
            msg = f"Ja, het is nu {naam}!"
        else:
            msg = "Nee, momenteel is er geen schoolvakantie."
        self.event_bus.publish("layer4_response", {"text": msg})

    # --------------------------------------------------------
    # "Wat is de volgende vakantie?"
    # --------------------------------------------------------
    def antwoord_volgende_vakantie(self):
        vandaag = self.today()
        start, einde, naam = self.volgende_vakantie(vandaag)
        aantal_dagen = (start - vandaag).days

        if aantal_dagen == 1:
            msg = f"De volgende vakantie is {naam}, die morgen begint ({self._formatteer_datum(start)})."
        else:
            msg = (
                f"De volgende vakantie is {naam}, over {aantal_dagen} dagen "
                f"({self._formatteer_datum(start)})."
            )
        self.event_bus.publish("layer4_response", {"text": msg})

    # --------------------------------------------------------
    # "Hoeveel dagen tot de vakantie?" -- zelfde info als
    # antwoord_volgende_vakantie(), maar met de nadruk op het
    # aantal dagen i.p.v. de naam als opener.
    # --------------------------------------------------------
    def antwoord_dagen_tot_vakantie(self):
        vandaag = self.today()
        start, einde, naam = self.volgende_vakantie(vandaag)
        aantal_dagen = (start - vandaag).days

        # Geen aantal_dagen==0-geval nodig: volgende_vakantie() filtert
        # strikt op start > vandaag, dus start == vandaag komt hier
        # nooit voor (zie test_al_middenin_een_vakantie_springt_bewust_
        # door_naar_de_volgende in test_vakanties.py voor de bewuste
        # keuze achter dat gedrag).
        if aantal_dagen == 1:
            msg = f"Nog 1 dag tot {naam}, die morgen begint."
        else:
            msg = f"Nog {aantal_dagen} dagen tot {naam} ({self._formatteer_datum(start)})."
        self.event_bus.publish("layer4_response", {"text": msg})


def init_module(event_bus):
    mod = VakantiesModule(event_bus)
    event_bus.publish("module_loaded", {"name": "vakanties"})
    return mod