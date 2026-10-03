# modules/context/afwezigheid.py

"""
Layer 5-uitbreiding: Afwezigheid (laptop vergrendeld)

WAT LOST DIT OP?
Als Kevin zijn laptop vergrendelt, zit hij er gegarandeerd niet achter.
Dat is een veel sterker signaal dan "al een tijdje geen muis/toetsenbord"
(focus_detector), want dat kan ook betekenen dat hij iets leest of een
film kijkt. Tot nu toe werd dit signaal enkel geteld in Layer 2
(activity_started:afwezig_gedetecteerd), maar niemand deed er iets mee:
Nova bleef gewoon proactief praten tegen een lege stoel.

WAT DEZE MODULE DOET:
1. Houdt bij OF en SINDS WANNEER Kevin weg is.
   - Begin: het event "activity_started:afwezig_gedetecteerd" (de
     laptop-client zag het Windows-vergrendelscherm, zie
     ACTIVITEIT_MAPPING in nova_client.py: "vergrendelingsscherm").
   - Einde: het eerstvolgende ANDERE "activity_started:<label>
     _gedetecteerd"-event (de laptop is ontgrendeld en er staat weer
     een gewoon venster op de voorgrond).
2. Bewaart proactieve berichten die Nova tijdens de afwezigheid wilde
   sturen (weerwaarschuwing, onbekend-venster-melding, ...), in plaats
   van ze tegen een lege kamer te zeggen. main.py vraagt dit aan via
   onderschep_bericht() voor elk bericht dat NIET van de hoofdthread
   komt (= niet een antwoord op iets wat Kevin net typte).
3. Geeft bij terugkomst een "welkom terug"-bericht, met de bewaarde
   berichten erin.
4. Toont de bewaarde berichten ook meteen als Kevin tijdens zijn
   afwezigheid toch met Nova praat (bv. via zijn gsm over SSH): hij
   leest op dat moment duidelijk mee.
5. Publiceert "afwezigheid:vertrokken" en "afwezigheid:terug", zodat
   andere modules (session_watcher.py) erop kunnen reageren, bv. door
   de pauze-teller te resetten na een echte pauze.

100% SYMBOLISCH: enkel tijd bijhouden, events filteren op naam en
berichten in een lijst bewaren. Geen ML, geen gok.

BELANGRIJK — DEADLOCK-LES (zie client_bridge.py, 19 sept 2026):
event_bus.publish() wordt in dit bestand NOOIT binnen self._lock
aangeroepen. Een publish("chat_response") komt namelijk uit bij
main.py's on_chat_response(), die op zijn beurt onderschep_bericht()
hieronder aanroept, en die neemt dezelfde lock. Binnen de lock zou dat
een zelf-deadlock geven (threading.Lock is niet herbetreedbaar).
"""

import random
import threading
import time
from datetime import datetime


class AfwezigheidModule:

    # Het event dat de laptop-client (via client_bridge.py's
    # RemoteActivityDetector) publiceert zodra het vergrendelscherm op
    # de voorgrond staat.
    AFWEZIG_EVENT = "activity_started:afwezig_gedetecteerd"

    # Vanaf hoeveel minuten weg zegt Nova "welkom terug", ook als er
    # niets bewaard werd? Korter dan dit (bv. even het scherm vergrendeld
    # om koffie te halen) is geen begroeting waard, tenzij er berichten
    # klaarliggen.
    MIN_MINUTEN_VOOR_WELKOM = 5

    # Hoeveel bewaarde berichten maximaal? Bij meer valt het OUDSTE weg,
    # zodat een lange afwezigheid (bv. een hele nacht) geen muur van
    # meldingen oplevert bij terugkomst.
    MAX_BEWAARDE_BERICHTEN = 10

    # Berichten ouder dan dit worden bij terugkomst niet meer getoond
    # (een weerwaarschuwing van gisterochtend is niet meer nuttig), enkel
    # nog geteld in een korte "en nog X oudere"-regel.
    MAX_BERICHT_LEEFTIJD_UUR = 12

    _WELKOM_OPENINGEN = [
        "Welkom terug!",
        "Hé, daar ben je weer!",
        "Fijn dat je terug bent!",
    ]

    def __init__(self, event_bus, klok=None):
        self.event_bus = event_bus

        # Injecteerbare klok (enkel voor tests, zelfde idee als
        # last_context.py's NepKlok) -- in Nova zelf altijd time.time.
        self._klok = klok or time.time

        # Lock: events komen binnen vanuit de achtergrondthread (main.py's
        # achtergrond_loop) en de WebSocket-thread (client_bridge.py),
        # terwijl de hoofdthread (input-lus) tegelijk berichten kan laten
        # onderscheppen. Zie de deadlock-les in de module-docstring.
        self._lock = threading.Lock()

        # None = Kevin is er (of we weten niets anders). Anders: het
        # tijdstip (time.time()) waarop het vergrendelscherm verscheen.
        self.afwezig_sinds = None

        # Bewaarde proactieve berichten: lijst van {"tekst", "tijd"}.
        self._bewaarde_berichten = []

        # Hoeveel berichten vielen weg door MAX_BEWAARDE_BERICHTEN?
        self._aantal_weggevallen = 0

        # Wildcard, want event_bus.subscribe() kan niet op een prefix
        # filteren -- zelfde aanpak als session_watcher.py.
        event_bus.subscribe("*", self._on_any_event)
        event_bus.subscribe("raw_user_message", self._on_user_message)

    # ------------------------------------------------------------
    # Publieke API
    # ------------------------------------------------------------

    def is_afwezig(self):
        with self._lock:
            return self.afwezig_sinds is not None

    def afwezig_minuten(self):
        """Hoe lang is Kevin al weg, in minuten? None als hij er is."""
        with self._lock:
            if self.afwezig_sinds is None:
                return None
            return (self._klok() - self.afwezig_sinds) / 60

    def aantal_bewaarde_berichten(self):
        with self._lock:
            return len(self._bewaarde_berichten)

    def onderschep_bericht(self, data, is_hoofdthread):
        """
        Wordt door main.py's on_chat_response() aangeroepen voor ELK
        bericht dat Nova wil tonen. Geeft True terug als het bericht
        BEWAARD werd (main.py toont het dan niet), anders False.

        Enkel berichten van een ANDERE thread dan de hoofdthread worden
        ooit bewaard: dat zijn de proactieve berichten (achtergrond_loop,
        WebSocket-thread). Een bericht van de hoofdthread is altijd een
        antwoord op iets wat Kevin zelf net typte, en dat moet hij
        uiteraard meteen zien.
        """
        if is_hoofdthread:
            return False

        tekst = (data.get("text") or data.get("msg") or "").strip()
        if not tekst:
            return False

        with self._lock:
            if self.afwezig_sinds is None:
                return False

            # Exact dezelfde tekst al bewaard? Niet dubbel opslaan, maar
            # wel onderscheppen (anders zou de tweede kopie alsnog
            # tegen de lege kamer gezegd worden).
            if any(b["tekst"] == tekst for b in self._bewaarde_berichten):
                return True

            self._bewaarde_berichten.append({"tekst": tekst, "tijd": self._klok()})

            if len(self._bewaarde_berichten) > self.MAX_BEWAARDE_BERICHTEN:
                self._bewaarde_berichten.pop(0)
                self._aantal_weggevallen += 1

        print("[AFWEZIGHEID] Proactief bericht bewaard tot Kevin terug is.")
        return True

    def status_tekst(self):
        """Korte, leesbare status (voor debug)."""
        minuten = self.afwezig_minuten()
        if minuten is None:
            return "Kevin is aanwezig (laptop niet vergrendeld)."
        return (
            f"Kevin is weg sinds {self._duur_tekst(minuten)} "
            f"({self.aantal_bewaarde_berichten()} bericht(en) bewaard)."
        )

    # ------------------------------------------------------------
    # Event-afhandeling
    # ------------------------------------------------------------

    def _on_any_event(self, data, event_type=None):
        """
        Filtert zelf op afgeleide activiteit-events van de laptop
        ("activity_started:<label>_gedetecteerd"). Expliciete uitspraken
        zoals "ik ga slapen" (zonder _gedetecteerd) zeggen niets over
        de laptop zelf en worden hier genegeerd.
        """
        if not event_type or not event_type.startswith("activity_started:"):
            return
        if not event_type.endswith("_gedetecteerd"):
            return

        if event_type == self.AFWEZIG_EVENT:
            self._markeer_vertrokken()
        else:
            self._markeer_terug()

    def _markeer_vertrokken(self):
        nu = self._klok()
        with self._lock:
            if self.afwezig_sinds is not None:
                return  # was al weg, niets nieuws
            self.afwezig_sinds = nu

        print("[AFWEZIGHEID] Laptop vergrendeld — Kevin is weg.")
        self.event_bus.publish("afwezigheid:vertrokken", {"tijd": nu})

    def _markeer_terug(self):
        nu = self._klok()
        with self._lock:
            if self.afwezig_sinds is None:
                return  # was niet weg, gewone activiteitswissel
            duur_minuten = (nu - self.afwezig_sinds) / 60
            berichten = self._bewaarde_berichten
            weggevallen = self._aantal_weggevallen
            self.afwezig_sinds = None
            self._bewaarde_berichten = []
            self._aantal_weggevallen = 0

        print(
            f"[AFWEZIGHEID] Kevin is terug na {duur_minuten:.1f} min "
            f"({len(berichten)} bewaard bericht(en))."
        )

        # Eerst het event (zodat bv. session_watcher.py zijn pauze-teller
        # al kan resetten), daarna pas de begroeting.
        self.event_bus.publish("afwezigheid:terug", {
            "duur_minuten": round(duur_minuten, 1),
            "aantal_berichten": len(berichten),
        })

        tekst = self._formuleer_welkom(duur_minuten, berichten, weggevallen, nu)
        if tekst:
            self.event_bus.publish("chat_response", {"text": tekst})

    def _on_user_message(self, data, event_type=None):
        """
        Kevin typt iets naar Nova terwijl zijn laptop nog vergrendeld is
        (bv. via zijn gsm). Hij leest dus mee: de bewaarde berichten
        meteen tonen in plaats van te wachten tot hij ontgrendelt. De
        afwezigheid zelf blijft lopen (de laptop is nog steeds
        vergrendeld).
        """
        nu = self._klok()
        with self._lock:
            if self.afwezig_sinds is None or not self._bewaarde_berichten:
                return
            berichten = self._bewaarde_berichten
            weggevallen = self._aantal_weggevallen
            self._bewaarde_berichten = []
            self._aantal_weggevallen = 0

        lijst = self._formuleer_lijst(berichten, weggevallen, nu)
        if lijst:
            self.event_bus.publish("chat_response", {
                "text": "Terwijl je laptop vergrendeld is, had ik nog dit voor je:" + lijst
            })

    # ------------------------------------------------------------
    # Tekst opbouwen (vaste sjablonen, geen generatie)
    # ------------------------------------------------------------

    def _formuleer_welkom(self, duur_minuten, berichten, weggevallen, nu):
        lijst = self._formuleer_lijst(berichten, weggevallen, nu)

        if not lijst and duur_minuten < self.MIN_MINUTEN_VOOR_WELKOM:
            return None

        delen = [random.choice(self._WELKOM_OPENINGEN)]

        if duur_minuten >= self.MIN_MINUTEN_VOOR_WELKOM:
            delen.append(f"Je was {self._duur_tekst(duur_minuten)} weg.")

        tekst = " ".join(delen)

        if lijst:
            tekst += " Terwijl je weg was:" + lijst

        return tekst

    def _formuleer_lijst(self, berichten, weggevallen, nu):
        """
        Bouwt de opsomming van bewaarde berichten (elk op een eigen
        regel, met het tijdstip erbij). Te oude berichten worden niet
        getoond maar wel meegeteld in de slotregel. Geeft "" terug als
        er niets te tonen valt.
        """
        max_leeftijd = self.MAX_BERICHT_LEEFTIJD_UUR * 3600
        recent = [b for b in berichten if nu - b["tijd"] <= max_leeftijd]
        te_oud = len(berichten) - len(recent) + weggevallen

        if not recent and not te_oud:
            return ""

        regels = [
            f"\n- [{datetime.fromtimestamp(b['tijd']).strftime('%H:%M')}] {b['tekst']}"
            for b in recent
        ]

        if te_oud:
            meervoud = "melding" if te_oud == 1 else "meldingen"
            regels.append(f"\n(en nog {te_oud} oudere {meervoud} die ik heb laten vallen)")

        return "".join(regels)

    @staticmethod
    def _duur_tekst(minuten):
        if minuten < 1:
            return "minder dan een minuut"
        if minuten < 60:
            m = int(minuten)
            return "1 minuut" if m == 1 else f"{m} minuten"
        uren = int(minuten // 60)
        rest = int(minuten % 60)
        tekst = f"{uren} uur"
        if rest:
            tekst += " en 1 minuut" if rest == 1 else f" en {rest} minuten"
        return tekst


def init_module(event_bus, sem=None):
    """
    Standaard module_loader-conventie: init_module(event_bus, sem).
    'sem' wordt niet gebruikt. Wordt automatisch gevonden door de
    dynamische scan in module_loader.py (modules/context/), geen
    handmatige registratie nodig. Beschikbaar als
    event_bus.modules["afwezigheid"].
    """
    instance = AfwezigheidModule(event_bus)
    event_bus.publish("module_loaded", {"name": "afwezigheid"})
    return instance