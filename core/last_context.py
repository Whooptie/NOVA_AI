# core/last_context.py
"""
Laatst-besproken-concept-geheugen (Taal & Redeneerlimieten, idee 1+2 uit
taal_en_redeneerlimieten_roadmap.md).

BEWUST GEEN uitbreiding van pending_question.py: dat mechanisme is
vraag-gedreven (Nova stelt een vraag, verwacht een DIRECT antwoord,
wordt na 1 reactie gewist). Dit hier is doorlopend-gesprek-gedreven --
geen vraag, geen verwachte-antwoord-vorm, blijft gewoon "actueel" tot
het te oud wordt of een nieuw, expliciet onderwerp het overschrijft.

Puur symbolisch: een dictionary + een timestamp + een vaste
vervaltermijn. Geen NLP, geen coreference-model, geen classificatie --
zie taal_en_redeneerlimieten_roadmap.md voor de volledige onderbouwing
waarom dit bewust GEEN NLP-library gebruikt.

Twee onafhankelijke manieren waarop de inhoud "leeg raakt":
1. Tijd verstreken (vangnet, VERVAL_SECONDEN) -- stilte/geen nieuw
   onderwerp gedurende een tijdje.
2. Een nieuw, EXPLICIET genoemd onderwerp (veiligheidsklep) --
   overschrijft onmiddellijk, ongeacht de klok.

Een verwijzing die zelf via dit mechanisme werd opgelost (bv. "die
zet" -> "de zet met paard") ververst enkel de timestamp een beetje
(ververs_timestamp()) -- vervangt de INHOUD niet. Zo valt een reeks
vervolgvragen ("die?" -> "en dat?" -> "ook die?") niet na de volledige
VERVAL_SECONDEN stil, maar telt een dergelijke reeks ook nooit als een
"vers", nieuw onderwerp.
"""

import time


class LastContext:

    # Vangnet-vervaltijd: langer dan pending_question.py's 120 sec,
    # want dit dient een ander doel (doorlopend gespreksgeheugen,
    # geen direct-verwacht-antwoord). Zie taal_en_redeneerlimieten_
    # roadmap.md voor de volledige afweging.
    VERVAL_SECONDEN = 300

    # Hoeveel een "verwijzing was oplosbaar"-hit de timestamp mag
    # verlengen -- bewust HETZELFDE als VERVAL_SECONDEN (de klok wordt
    # gewoon opnieuw gestart), maar als APARTE constante genoteerd
    # zodat een toekomstige aanpassing (bv. een kortere verlenging dan
    # de volle vervaltijd) hier één plek heeft om te wijzigen zonder
    # VERVAL_SECONDEN zelf aan te raken.
    VERVERS_SECONDEN = VERVAL_SECONDEN

    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self._concept = None
        self._antwoord_type = None
        self._opties = None
        self._laatste_update = None

    # ------------------------------------------------------------
    # Interne helper
    # ------------------------------------------------------------
    def _is_verlopen(self):
        if self._laatste_update is None:
            return True
        return (time.time() - self._laatste_update) > self.VERVAL_SECONDEN

    # ------------------------------------------------------------
    # Schrijven -- nieuw, EXPLICIET onderwerp (veiligheidsklep)
    # ------------------------------------------------------------
    def set_concept(self, concept, antwoord_type=None):
        """
        Legt een nieuw, expliciet besproken concept vast. Overschrijft
        ALTIJD de vorige inhoud, ongeacht hoe lang die nog geldig was --
        dit is de veiligheidsklep uit het ontwerp: een nieuw onderwerp
        wint altijd van de klok.

        Wist ook automatisch de laatst-aangeboden-opties-lijst: een
        nieuw hoofdonderwerp betekent dat een eerder aangeboden
        keuzelijst niet meer het "actuele" is om op te reageren.
        """
        if not concept:
            return
        self._concept = concept
        self._antwoord_type = antwoord_type
        self._opties = None
        self._laatste_update = time.time()

    def set_opties(self, opties):
        """
        Legt de laatst aangeboden keuzelijst vast (ellipsis, idee 2),
        bv. bij een meerkeuze-achtig antwoord ("wil je schaken of
        dammen?"). Raakt het onthouden concept/antwoord_type NIET aan
        -- een opties-lijst kan naast een lopend gespreksonderwerp
        bestaan.
        """
        if not opties:
            return
        self._opties = list(opties)
        self._laatste_update = time.time()

    # ------------------------------------------------------------
    # Verversen -- verwijzing was oplosbaar, GEEN nieuwe inhoud
    # ------------------------------------------------------------
    def ververs_timestamp(self):
        """
        Verlengt enkel de geldigheidsduur, zonder de inhoud te
        wijzigen. Aan te roepen NA een geslaagde referentie-resolutie
        (bv. "die?" correct opgelost naar het bestaande concept) --
        zodat een lopend gesprek van louter vervolgvragen niet na
        VERVAL_SECONDEN wegvalt, maar zonder dat dit als een "vers"
        nieuw onderwerp telt (zie set_concept() voor dat onderscheid).
        """
        if self._concept is None and self._opties is None:
            return
        self._laatste_update = time.time()

    # ------------------------------------------------------------
    # Lezen
    # ------------------------------------------------------------
    def is_geldig(self):
        """True als er een niet-verlopen concept ÉN/OF opties-lijst is."""
        if self._is_verlopen():
            return False
        return self._concept is not None or self._opties is not None

    def get_concept(self):
        """Geeft het laatst besproken concept terug, of None als er
        niets is of het verlopen is."""
        if self._is_verlopen():
            return None
        return self._concept

    def get_antwoord_type(self):
        if self._is_verlopen():
            return None
        return self._antwoord_type

    def get_opties(self):
        """Geeft de laatst aangeboden opties-lijst terug (of None)."""
        if self._is_verlopen():
            return None
        return self._opties

    def clear(self):
        self._concept = None
        self._antwoord_type = None
        self._opties = None
        self._laatste_update = None


def init_module(event_bus=None):
    return LastContext(event_bus)