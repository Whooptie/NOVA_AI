# modules/knowledge/temporal_semantics.py
#
# Semantic Fase 9.1 -- Temporal Semantics: het ontstaansjaar van een woord.
#
# Puur symbolisch: Kevin leert Nova een jaartal ("python bestaat sinds 1991"),
# Nova bewaart het bij de sense van het woord (zie SenseEngine.set_ontstaan)
# en geeft het terug op "wanneer ontstond python" / "hoe lang bestaat python al".
# Geen voorspellingen, geen schattingen.
#
# Luistert op de events die intent_router.detect_temporal() publiceert:
#   intent_temporal_leer  {"word", "jaar"}
#   intent_temporal_query {"word", "vorm"}   (vorm = "wanneer" of "hoelang")
# Antwoordt via layer4_response (dus door de tone-pipeline).

from datetime import datetime


def _huidig_jaar():
    return datetime.now().year


class TemporalSemantics:
    def __init__(self, event_bus, sem):
        self.event_bus = event_bus
        self.sem = sem
        event_bus.subscribe("intent_temporal_leer", self.on_leer)
        event_bus.subscribe("intent_temporal_query", self.on_query)
        event_bus.publish("module_loaded", {"name": "temporal_semantics"})

    def _zeg(self, tekst):
        self.event_bus.publish("layer4_response", {"text": tekst})

    @staticmethod
    def _hoofdletter(woord):
        return woord[:1].upper() + woord[1:]

    def on_leer(self, data, event_type=None):
        woord = data.get("word", "").strip()
        jaar = data.get("jaar")
        if not woord or jaar is None:
            return

        resultaat = self.sem.set_ontstaan(woord, jaar, source="user")
        if resultaat.get("blocked"):
            self._zeg(f"Dat kan ik niet opslaan: alle betekenissen van '{woord}' zijn afgewezen.")
            return

        naam = self._hoofdletter(woord)
        oud = resultaat.get("oud")
        if oud is None:
            self._zeg(f"Genoteerd: {naam} bestaat sinds {jaar}.")
        elif oud == jaar:
            self._zeg(f"Dat wist ik al: {naam} bestaat sinds {jaar}.")
        else:
            self._zeg(f"Aangepast: ik had {oud} genoteerd, nu staat {naam} op {jaar}.")

    def on_query(self, data, event_type=None):
        woord = data.get("word", "").strip()
        vorm = data.get("vorm", "wanneer")
        if not woord:
            return

        info = self.sem.get_ontstaan(woord)
        naam = self._hoofdletter(woord)
        if not info:
            self._zeg(
                f"Ik weet nog niet wanneer {woord} ontstond. "
                f"Je kunt het me leren, bijvoorbeeld: '{woord} bestaat sinds 1991'."
            )
            return

        jaar = info["jaar"]
        extra = "" if info.get("status") == "confirmed" else " (nog niet bevestigd)"

        if vorm == "hoelang":
            verschil = _huidig_jaar() - jaar
            if verschil <= 0:
                tekst = f"{naam} bestaat sinds dit jaar ({jaar})."
            elif verschil == 1:
                tekst = f"{naam} bestaat al 1 jaar (sinds {jaar})."
            else:
                tekst = f"{naam} bestaat al {verschil} jaar (sinds {jaar})."
        else:
            tekst = f"{naam} bestaat sinds {jaar}."
        self._zeg(tekst + extra)


def init_module(event_bus, sem):
    return TemporalSemantics(event_bus, sem)