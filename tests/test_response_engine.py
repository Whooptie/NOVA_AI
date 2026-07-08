# test_response_engine.py
"""
Testscript voor Layer 4 (response_engine.py) — Fase 1.

WAT DOET DIT SCRIPT?
Het laadt je ECHTE semantic.py en je ECHTE data/concepts.json in
(niet een nep-versie), en laat je woorden intypen om te zien wat
response_engine.py daarmee antwoordt. Zo test je meteen met je eigen,
al geleerde concepten (hond, appel, pitvrucht, democratie, ...).

WAAROM EEN NEP-EVENTBUS?
semantic.py verwacht een event_bus met minstens een subscribe() en
publish() methode (want SemanticConceptsModule roept die aan in zijn
__init__). We hebben hier de volledige EventBus uit core/event_bus.py
niet per se nodig — een piepklein "neposbord" dat gewoon niets doet
is voldoende om semantic.py zonder klachten te laten opstarten.

HOE GEBRUIK JE DIT?
1. Zet dit bestand in de hoofdmap van je project: C:\\Nova_AI\\test_response_engine.py
   (dus NAAST main.py, niet in een submap — anders kloppen de imports niet)
2. Zorg dat response_engine.py al in C:\\Nova_AI\\core\\ staat
3. Open een terminal in C:\\Nova_AI en typ: python test_response_engine.py
4. Typ een woord (bv. "hond") en druk op Enter
5. Typ "stop" om te stoppen
"""

import sys
import os

# Zorg dat "core" en "modules" gevonden worden, ongeacht vanuit welke
# map je dit script toevallig start.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.semantic import SemanticConceptsModule
from core.response_engine import ResponseEngine


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
    print(" TEST: Layer 4 — response_engine.py (Fase 1)")
    print("=" * 60)
    print("Dit gebruikt je ECHTE data/concepts.json.")
    print("Typ een woord om te testen, of 'stop' om te stoppen.\n")

    # 1. Nep-EventBus + echte semantic.py opstarten
    nepbus = NepEventBus()
    sem = SemanticConceptsModule(nepbus)

    # 2. response_engine.py opstarten met semantic erin gestoken
    layers = {"semantic": sem}
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