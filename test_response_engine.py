# test_response_engine.py
"""
Testscript voor Layer 4 (response_engine.py) — Fase 2.

WAT DOET DIT SCRIPT?
Het laadt je ECHTE semantic.py + data/concepts.json ÉN je ECHTE
word_associations_learner.py + data/word_associations.json in (geen
van beide is een nep-versie), en laat je woorden intypen om te zien
wat response_engine.py daarmee antwoordt.

Sinds Fase 2 kan het antwoord er dus ook zo uitzien (als Layer 1 al
een sterk genoege associatie kent voor dat woord):
    "python betekent: een programmeertaal. Je associeert dat
     trouwens vaak met 'snel'."

Heeft Layer 1 nog te weinig/geen data voor dat woord (heel normaal
als je nog niet veel met Nova gechat hebt), dan krijg je gewoon de
kale definitie terug zoals in Fase 1 — dat is verwacht gedrag, geen
bug.

WAAROM EEN NEP-EVENTBUS?
semantic.py verwacht een event_bus met minstens een subscribe() en
publish() methode (want SemanticConceptsModule roept die aan in zijn
__init__). We hebben hier de volledige EventBus uit core/event_bus.py
niet per se nodig — een piepklein "neposbord" dat gewoon niets doet
is voldoende om semantic.py zonder klachten te laten opstarten.
word_associations_learner.py accepteert event_bus=None probleemloos,
dus daarvoor is geen nepbus nodig.

HOE GEBRUIK JE DIT?
1. Zet dit bestand in de hoofdmap van je project: C:\\Nova_AI\\test_response_engine.py
   (dus NAAST main.py, niet in een submap — anders kloppen de imports niet)
2. Zorg dat response_engine.py al in C:\\Nova_AI\\core\\ staat
3. Open een terminal in C:\\Nova_AI en typ: python test_response_engine.py
4. Typ een woord (bv. "python", of een woord waar je al vaak met Nova
   over gechat hebt) en druk op Enter
5. Typ "stop" om te stoppen
"""

import sys
import os

# Zorg dat "core" en "modules" gevonden worden, ongeacht vanuit welke
# map je dit script toevallig start.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.semantic import SemanticConceptsModule
from core.response_engine import ResponseEngine
from modules.learning.word_associations_learner import WordAssociationsLearner


class NepEventBus:
    """
    Piepklein "neposbord": doet niets, maar heeft wel de methodes
    die semantic.py nodig heeft om zonder fouten op te starten
    (subscribe/publish). We testen hier alleen response_engine.py,
    dus we hebben geen échte EventBus-werking nodig.
    """

    def subscribe(self, event_type, handler):
        pass

    def publish(self, event_type, data):
        # Als semantic.py iets probeert te publiceren (bv. bij
        # module_loaded), printen we het gewoon even mee zodat je
        # ziet dat er niets stuk is — puur informatief.
        print(f"[NEPBUS] event gepubliceerd: {event_type} -> {data}")


def main():
    print("=" * 60)
    print(" TEST: Layer 4 — response_engine.py (Fase 2)")
    print("=" * 60)
    print("Dit gebruikt je ECHTE data/concepts.json EN")
    print("je ECHTE data/word_associations.json.")
    print("Typ een woord om te testen, of 'stop' om te stoppen.\n")

    # 1. Nep-EventBus + echte semantic.py opstarten
    nepbus = NepEventBus()
    sem = SemanticConceptsModule(nepbus)

    # 2. Echte word_associations_learner.py opstarten (Layer 1).
    #    event_bus=None mag hier gewoon — deze klasse checkt zelf
    #    "if self.event_bus is not None" voor hij iets abonneert.
    #    Hij laadt automatisch data/word_associations.json in, als
    #    dat bestand al bestaat.
    word_assoc = WordAssociationsLearner(event_bus=None, semantic_module=sem)

    # 3. response_engine.py opstarten met beide lagen erin gestoken
    layers = {
        "semantic": sem,
        "word_associations": word_assoc,
    }
    engine = ResponseEngine(event_bus=None, layers=layers)

    # 3. Interactieve testlus
    while True:
        woord = input("\nWoord om te testen: ").strip()

        if woord.lower() == "stop":
            print("Testscript gestopt.")
            break

        if not woord:
            continue

        resultaat = engine.generate(woord)

        print("-" * 40)
        print(f"Tekst:       {resultaat['text']}")
        print(f"Confidence:  {resultaat['confidence']}")
        print(f"Bronnen:     {resultaat['sources']}")
        print("-" * 40)


if __name__ == "__main__":
    main()
