# modules/activity/session_watcher.py
import time


class SessionWatcher:
    """
    Houdt bij hoe lang Kevin al aan het chatten is met Nova, en stuurt
    na een ingestelde tijd één keer een korte pauze-melding.

    Puur symbolisch: enkel tijd bijhouden en vergelijken (time.time()),
    geen ML, geen kansberekening. Dit is een eerste, ruwe versie van
    wat later verder uitgebouwd wordt in activity_awareness_roadmap.md.
    """

    # Na hoeveel seconden zonder pauze stuurt Nova een melding?
    # 1800 seconden = 30 minuten. Zet dit tijdelijk lager (bv. 60) om te testen.
    PAUZE_DREMPEL_SECONDEN = 1800

    def __init__(self, event_bus, context_manager=None):
        self.event_bus = event_bus
        self.start_time = time.time()
        self.laatste_melding_time = None
        # Layer 5 — bepaalt of dit een goed moment is om te onderbreken.
        # Kan None zijn (bv. als context_manager nog niet geladen is),
        # daarom altijd voorzichtig checken met "if self.context_manager".
        self.context_manager = context_manager

    def check_pauze(self):
        """
        Wordt periodiek aangeroepen door de achtergrondthread in main.py.
        Kijkt of de sessie al lang genoeg loopt sinds de start (of sinds
        de vorige melding) om een pauze voor te stellen.
        """
        nu = time.time()

        # Referentiepunt: sinds de laatste melding, of sinds de start
        # als er nog nooit gemeld is.
        referentie = self.laatste_melding_time or self.start_time

        verstreken = nu - referentie

        if verstreken >= self.PAUZE_DREMPEL_SECONDEN:
            # Layer 5 vragen: is dit een goed moment om te onderbreken?
            # Als context_manager niet beschikbaar is (bv. door een
            # laadvolgorde-probleem), gaan we voorzichtig gewoon door —
            # Layer 5 ontbreken mag nooit de pauze-melding blokkeren,
            # want dat zou de bestaande functionaliteit stiller maken
            # dan voorheen. We proberen het WEL opnieuw bij de
            # eerstvolgende check (verstreken blijft oplopen), in
            # plaats van laatste_melding_time hier al bij te werken.
            if self.context_manager is not None:
                try:
                    mag_onderbreken = self.context_manager.can_interrupt()
                except Exception:
                    mag_onderbreken = True
            else:
                mag_onderbreken = True

            if not mag_onderbreken:
                # Nog niet melden — probeer het over 60 seconden
                # opnieuw (achtergrond_loop() roept dit sowieso elke
                # minuut aan). laatste_melding_time NIET bijwerken,
                # anders "verliest" de sessie deze wachttijd stilletjes.
                #
                # Enkel een console-print voor Kevin (debug), GEEN
                # chat_response — Nova "zegt" dit niet tegen zichzelf,
                # dit is puur zichtbaar voor wie main.py's terminal leest.
                print("[SESSION_WATCHER] Pauze-melding uitgesteld door Layer 5 (context_manager.can_interrupt() == False)")
                return

            self.laatste_melding_time = nu
            minuten = int(self.PAUZE_DREMPEL_SECONDEN / 60)

            self.event_bus.publish("chat_response", {
                "text": f"We zijn nu al {minuten} minuten bezig — misschien even pauzeren?"
            })


def init_module(event_bus, sem=None):
    """
    Standaard module_loader-conventie: init_module(event_bus, sem).
    'sem' wordt hier niet gebruikt maar moet aanwezig zijn zodat
    module_loader.py deze module net als de andere kan initialiseren.

    LET OP: session_watcher wordt geladen via de DYNAMISCHE modules-
    scan in module_loader.py (stap 3) — dat gebeurt VOOR context_manager
    geladen wordt (stap 3C, na response_engine). Op dit moment bestaat
    loaded_modules["context_manager"] dus nog NIET. We geven hier dus
    (nog) geen context_manager mee — die wordt vlak na het laden
    apart ingeprikt door module_loader.py. Zie het zoek/vervang-blok
    voor module_loader.py hieronder.
    """
    instance = SessionWatcher(event_bus)
    event_bus.publish("module_loaded", {"name": "session_watcher"})
    return instance