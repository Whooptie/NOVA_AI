# core/pending_question.py

"""
Pending Question — kortlevend "wacht ik op een antwoord?"-geheugen

Dit lost een specifiek probleem op: wanneer Nova zelf een vraag stelt
("Mag ik storen?"), moet een kort antwoord van Kevin ("ja"/"nee"/"oké")
herkend worden als reactie op DIE vraag, niet als een los, nieuw
bericht dat de gewone intent-routing zou doorlopen.

BEWUST GEEN permanente opslag (in tegenstelling tot Layer 0-2, die
alles blijvend bijhouden): een openstaande vraag is per definitie
tijdelijk. Ze bestaat enkel in het geheugen (RAM), verdwijnt bij een
herstart, en dat is precies de bedoeling — er is niets om na een
herstart nog "open" te laten staan.

100% symbolisch: dit bestand doet geen enkele interpretatie van TEKST.
Het houdt enkel bij (1) is er een vraag open, (2) welk vraag_type was
het, en (3) is de verval-tijd al voorbij. Wélk antwoord Kevin gaf en
wat dat betekent, wordt elders bepaald (bv. door de signal_classifier,
zie pending_question_roadmap.md) — dit bestand levert enkel het kale
"is er iets open, en zo ja wat"-signaal.

Gebruik (via event_bus.modules.get("pending_question"), net als bij
andere gedeelde modules zoals presence_detector/context_manager):

    pending = event_bus.modules.get("pending_question")

    # Een module stelt een vraag en meldt dit:
    pending.set("mag_ik_storen", verval_seconden=120)

    # intent_router.py checkt bij elk bericht:
    if pending.is_open():
        vraag_type = pending.get_type()
        ... verwerk het antwoord ...
        pending.clear()
"""

import time


class PendingQuestion:
    """
    Houdt bij of Nova op dit moment op een antwoord "wacht", en op
    welke vraag. Slechts ÉÉN openstaande vraag tegelijk mogelijk —
    een nieuwe .set()-aanroep overschrijft altijd een eventuele oude,
    nog niet beantwoorde vraag (dat kan in de praktijk bijna niet
    gebeuren, aangezien Nova maar 1 ding tegelijk vraagt, maar zo is
    het gedrag bij zo'n zeldzaam geval tenminste voorspelbaar).
    """

    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self._vraag_type = None
        self._gesteld_op = None
        self._verval_seconden = None

    # ------------------------------------------------------------------
    # Een vraag aankondigen
    # ------------------------------------------------------------------

    def set(self, vraag_type, verval_seconden=120):
        """
        Meldt dat Nova zonet een vraag heeft gesteld, en dat een
        volgend kort antwoord daaraan gekoppeld moet worden.

        vraag_type: een korte, vaste string die aangeeft WELKE vraag
        het was (bv. "mag_ik_storen") — de module die deze vraag
        stelde, herkent dit type later terug als het antwoord
        binnenkomt en weet dan zelf wat ermee te doen.

        verval_seconden: hoelang de vraag "open" blijft staan als er
        geen antwoord komt. Na deze tijd telt is_open() vanzelf weer
        als False, zonder dat iemand clear() hoeft aan te roepen.
        """
        self._vraag_type = vraag_type
        self._gesteld_op = time.time()
        self._verval_seconden = verval_seconden

    # ------------------------------------------------------------------
    # Opvragen
    # ------------------------------------------------------------------

    def is_open(self):
        """
        Staat er nu een onbeantwoorde vraag open?

        Ruimt zichzelf automatisch op als de verval-tijd overschreden
        is — een later, ongerelateerd "ja"/"oké" wordt dan niet per
        ongeluk nog aan een oude vraag gekoppeld.
        """
        if self._vraag_type is None:
            return False

        verstreken = time.time() - self._gesteld_op
        if verstreken > self._verval_seconden:
            self.clear()
            return False

        return True

    def get_type(self):
        """
        Geeft het vraag_type terug van de huidige openstaande vraag,
        of None als er niets openstaat. Roep is_open() typisch eerst
        aan om te checken of er überhaupt iets is.
        """
        if not self.is_open():
            return None
        return self._vraag_type

    # ------------------------------------------------------------------
    # Wissen
    # ------------------------------------------------------------------

    def clear(self):
        """Wist de huidige openstaande vraag (na antwoord of verval)."""
        self._vraag_type = None
        self._gesteld_op = None
        self._verval_seconden = None


def init_module(event_bus, semantic_module=None):
    """
    Wordt aangeroepen door module_loader.py bij het opstarten van Nova.

    Volgt de standaard dynamische module-conventie (init_module(event_bus,
    sem)), ook al gebruikt deze module semantic_module niet — zelfde
    reden als bij pattern_matcher.py/word_associations_learner.py: de
    dynamische pkgutil-scan roept altijd deze signatuur aan.
    """
    instance = PendingQuestion(event_bus)
    if event_bus is not None:
        event_bus.publish("module_loaded", {"name": "pending_question"})
    return instance