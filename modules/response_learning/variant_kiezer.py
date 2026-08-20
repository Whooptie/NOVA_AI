# modules/response_learning/variant_kiezer.py
"""
Gedeelde, herbruikbare "kies een variant"-functie voor Response
Variant Learning (response_variant_learning_roadmap.md).

WAAROM DIT EEN APARTE, LOSSTAANDE MODULE IS (in plaats van deze
logica te dupliceren in response_engine.py, response_pipeline.py EN
conversation_engine.py, of ze rechtstreeks in variant_feedback_
logger.py te stoppen):

1. response_engine.py's _kies_variant() bevatte deze logica al
   (gewicht ophalen bij variant_feedback_logger, gewogen of gelijke
   keuze, "variant_gekozen"-event publiceren). response_pipeline.py
   en conversation_engine.py hebben dezelfde behoefte -- dupliceren
   zou betekenen dat een toekomstige bugfix (zoals de twee bugs die
   hier onderweg al gevonden zijn: dubbele module-registratie,
   timing_hint-vermenging) op 3 plekken apart doorgevoerd moet
   worden, met het risico dat er ergens een verschil insluipt.

2. variant_feedback_logger.py blijft bewust een PASSIEVE luisteraar
   (abonneert op "variant_gekozen"/"raw_user_message", bemoeit zich
   nooit met HOE of WAAR een keuze gemaakt wordt). Deze functie hier
   HAALT enkel gewichten op via get_gewichten() (een read-only
   opvraging) en PUBLICEERT een event -- ze roept nooit iets anders
   op variant_feedback_logger aan. Zo blijft de bestaande scheiding
   (kiezer vs. toeschouwer) intact, en blijft variant_feedback_logger
   volledig optioneel voor elke aanroeper (geen harde afhankelijkheid
   -- ontbreekt hij, dan werkt dit gewoon als random.choice() zoals
   voorheen).

3. Puur functioneel (geen klasse, geen eigen state) -- elk bestand
   dat dit gebruikt blijft zelf verantwoordelijk voor ZIJN EIGEN
   sjabloon-dictionary/lijst en context (entity, response_style, ...),
   deze functie bemoeit zich daar niet mee.

GEBRUIK (vervangt een losse random.choice(lijst)-aanroep):

    from modules.response_learning.variant_kiezer import kies_variant

    tekst = kies_variant(
        varianten=self._sjablonen_fallback,
        sjabloon_naam="fallback_algemeen",
        event_bus=self.event_bus,
        variant_feedback_logger=self.event_bus.modules.get("variant_feedback_logger"),
        entity=None,
        response_style=response_style,
    )

Geeft de GEKOZEN TEKST terug (nog NIET geformatteerd met .format() --
dat blijft de verantwoordelijkheid van de aanroeper, want niet elke
aanroeper gebruikt dezelfde invulwaarden-conventie als response_
engine.py's sjablonen). Voor sjablonen zonder invulplekken (zoals
response_pipeline.py's fallback-zinnen) is dat verschil onzichtbaar --
je gebruikt de tekst gewoon direct.
"""

import random
from datetime import datetime
from typing import List, Optional


def kies_variant(
    varianten: List[str],
    sjabloon_naam: str,
    event_bus,
    variant_feedback_logger=None,
    entity: Optional[str] = None,
    response_style: Optional[str] = None,
    uitsluiten_indices: Optional[List[int]] = None,
) -> str:
    """
    Kiest een variant uit 'varianten' -- gewogen via variant_feedback_
    logger.get_gewichten() als die beschikbaar is EN genoeg observaties
    heeft voor dit sjabloon_naam, anders gewoon gelijke kansen
    (random.choice()-gedrag, exact zoals voorheen).

    Publiceert altijd een "variant_gekozen"-event (Fase 1-logging),
    ongeacht of variant_feedback_logger nu al meeluistert -- zelfde
    principe als response_engine.py's _kies_variant(): dit bestand
    weet niet en hoeft niet te weten OF er iets luistert.

    uitsluiten_indices (optioneel): indices die voor DEZE aanroep niet
    gekozen mogen worden (bv. een variant met "{duur}" als er geen
    duur-tekst beschikbaar is, zie conversation_engine.py). BELANGRIJK:
    'varianten' blijft hierbij de VOLLEDIGE, vaste lijst -- we filteren
    de lijst zelf NIET vooraf, want dat zou de index-betekenis laten
    verschuiven tussen aanroepen (index 0 zou dan soms iets anders
    betekenen dan een andere keer), wat get_gewichten()'s scores door
    elkaar zou husselen. In plaats daarvan wordt het gewicht van een
    uitgesloten index simpelweg op 0 gezet VOOR het kiezen, zodat de
    lijst en de indices altijd stabiel blijven.

    BLIJFT 100% VAST/SYMBOLISCH, exact zoals response_engine.py's
    _kies_variant(): er wordt nooit een nieuwe tekst gegenereerd of
    samengesteld die niet al letterlijk in 'varianten' stond.
    """
    gewichten = None
    if variant_feedback_logger is not None:
        try:
            gewichten = variant_feedback_logger.get_gewichten(sjabloon_naam, len(varianten))
        except Exception:
            # Een fout in een ondersteunende laag mag Nova's antwoord
            # nooit laten crashen -- gewoon terugvallen op gelijke
            # kansen, zelfde principe als overal elders in Nova.
            gewichten = None

    if uitsluiten_indices:
        if gewichten is None:
            # Geen gewogen data -> toch een gelijke-kansen-gewichtenlijst
            # opbouwen, puur om de uitsluiting te kunnen toepassen.
            gewichten = [1.0] * len(varianten)
        else:
            gewichten = list(gewichten)  # niet de originele lijst muteren
        for index in uitsluiten_indices:
            if 0 <= index < len(gewichten):
                gewichten[index] = 0.0

    if gewichten is not None:
        gekozen_index = random.choices(range(len(varianten)), weights=gewichten, k=1)[0]
    else:
        gekozen_index = random.randrange(len(varianten))

    gekozen = varianten[gekozen_index]

    if event_bus is not None:
        try:
            event_bus.publish("variant_gekozen", {
                "sjabloon_naam": sjabloon_naam,
                "gekozen_variant_index": gekozen_index,
                "variant_tekst": gekozen,
                "entity": entity,
                "response_style": response_style,
                "moment": datetime.now().isoformat(),
            })
        except Exception:
            # Loggen mag Nova's eigenlijke antwoord nooit blokkeren.
            pass

    return gekozen