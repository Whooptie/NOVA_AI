"""
test_llm_bridge.py

Los testscript om llm_bridge.py te proberen ZONDER Nova zelf op te starten.

Gebruik:
    1. Zorg dat Ollama draait (Ollama-app actief, of `ollama serve` in een terminal)
    2. Zet dit bestand in dezelfde map als llm_bridge.py (bv. core/)
    3. Draai: python test_llm_bridge.py
"""
import logging
logging.basicConfig(level=logging.INFO)
from core import llm_bridge


def print_scheiding(titel: str):
    print("\n" + "=" * 60)
    print(titel)
    print("=" * 60)
 
 
def test_bereikbaarheid():
    print_scheiding("TEST 0: is Ollama bereikbaar?")
    bereikbaar = llm_bridge.is_ollama_bereikbaar()
    print(f"Ollama bereikbaar: {bereikbaar}")
    if not bereikbaar:
        print(
            "\n⚠️  Ollama lijkt niet te draaien op localhost:11434.\n"
            "   Start de Ollama-app of draai 'ollama serve' in een terminal,\n"
            "   en probeer dit script daarna opnieuw."
        )
    return bereikbaar
 
 
def test_generatie(entity: str, is_a: str, property_tekst: str):
    print_scheiding(f"TEST: entity='{entity}', is_a='{is_a}'")
    print(f"Feiten die verstuurd worden:")
    print(f"  onderwerp   : {entity}")
    print(f"  is een      : {is_a}")
    print(f"  eigenschap  : {property_tekst}")
 
    resultaat = llm_bridge.genereer_zin(entity, is_a, property_tekst)
 
    if resultaat is None:
        print("\n❌ Resultaat: None")
        print("   (Ollama niet bereikbaar, timeout, of validatie afgewezen —")
        print("    response_engine.py zou hier gewoon het sjabloon gebruiken)")
    else:
        print(f"\n✅ Gegenereerde zin:\n   \"{resultaat}\"")
        print(f"\n   Lengte: {len(resultaat)} tekens")
 
    return resultaat
 
 
def test_validatie_los():
    """Test de valideer()-functie los, met een paar handmatige voorbeelden."""
    print_scheiding("TEST: valideer() los getest met vaste voorbeelden")
 
    gevallen = [
        ("De gitarist beschikt over een gitaar, die vaak van hout wordt gemaakt en ook een snaarinstrument is.", "gitaar", "snaarinstrument", True),
        ("Deze vaak van hout gemaakte snaarinstrument, de gitarist's zeggen toch dat zij een eigenaardig snaarinstrument zijn?", "gitaar", "snaarinstrument", False),  # mist "gitaar" letterlijk? check hieronder
        ("Iets volledig anders over katten.", "gitaar", "snaarinstrument", False),
        ("", "gitaar", "snaarinstrument", False),
    ]
 
    for tekst, entity, is_a, verwacht in gevallen:
        resultaat = llm_bridge.valideer(tekst, entity, is_a)
        status = "✅" if resultaat == verwacht else "⚠️  (afwijkend van verwachting)"
        print(f"{status} valideer(...) = {resultaat} | verwacht: {verwacht}")
        print(f"   tekst: \"{tekst[:70]}{'...' if len(tekst) > 70 else ''}\"")
 
 
if __name__ == "__main__":
    if not test_bereikbaarheid():
        print("\nStoppen — start eerst Ollama en probeer opnieuw.")
        exit(1)
 
    # 10 representatieve testcases, bewust divers gekozen:
    # - concrete objecten (gitaar, appel)
    # - levende wezens (hond, boom)
    # - abstracte begrippen (democratie, vriendschap)
    # - technische termen (python, wifi)
    # - een woord met meerdere betekenissen (bank)
    # - een wetenschappelijk begrip (zwart gat)
    testcases = [
        ("gitaar", "snaarinstrument", "vaak gemaakt van hout"),
        ("hond", "zoogdier", "wordt vaak als huisdier gehouden"),
        ("python", "programmeertaal", "veel gebruikt voor AI en scripting"),
        ("appel", "vrucht", "groeit aan een boom en is vaak rood of groen"),
        ("boom", "plant", "heeft wortels, een stam en bladeren"),
        ("democratie", "staatsvorm", "burgers kiezen hun vertegenwoordigers"),
        ("vriendschap", "relatie", "gebaseerd op wederzijds vertrouwen en genegenheid"),
        ("wifi", "draadloze technologie", "maakt internetverbinding zonder kabels mogelijk"),
        ("bank", "meubelstuk", "wordt gebruikt om op te zitten"),
        ("zwart gat", "ruimtelijk fenomeen", "heeft een zwaartekracht waar zelfs licht niet aan ontsnapt"),
    ]
 
    resultaten = []
    for entity, is_a, property_tekst in testcases:
        resultaat = test_generatie(entity, is_a, property_tekst)
        resultaten.append((entity, resultaat is not None))
 
    # Los de validatiefunctie zelf testen, onafhankelijk van Ollama
    test_validatie_los()
 
    print_scheiding("SAMENVATTING: SUCCESRATIO OVER 10 ONDERWERPEN")
    geslaagd = sum(1 for _, ok in resultaten if ok)
    for entity, ok in resultaten:
        print(f"  {'✅' if ok else '❌'} {entity}")
    print(f"\nGeslaagd: {geslaagd}/10 ({geslaagd * 10}%)")
 
    print_scheiding("KLAAR")
    print("Bekijk de resultaten hierboven. Let vooral op:")
    print("  - Komen de feiten correct terug in de zin?")
    print("  - Is het grammaticaal correct Nederlands?")
    print("  - Wordt er niet als het onderwerp zelf gesproken (geen 'ik ben...')?")