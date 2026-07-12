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

    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.start_time = time.time()
        self.laatste_melding_time = None

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
    """
    instance = SessionWatcher(event_bus)
    event_bus.publish("module_loaded", {"name": "session_watcher"})
    return instance