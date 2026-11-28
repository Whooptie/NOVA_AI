# core/trace_punten.py
#
# Live brein-weergave (nova_state.md, punt 79): de aanroepen die NIET via de EventBus
# lopen laten zich toch zien.
#
# WAAROM?
#   De EventBus-tracer (core/tracer.py) ziet alleen functies die de bus zelf aanroept.
#   De achtergrondlussen in main.py, de threads van een paar modules en de router
#   (die response_engine rechtstreeks aanroept) lopen niet via de bus. Hier staat in
#   EEN lijst welke functies we willen zien. Bij het opstarten wordt elke functie uit de
#   lijst omhuld: eerst meldt hij zich bij de tracer (naam en duur), daarna doet hij
#   precies wat hij deed. Aan de modules zelf verandert niets.
#
# NIEUWE FUNCTIE TOEVOEGEN: zet de modulenaam (zoals in loader.loaded_modules) en de
# functienaam in TRACE_PUNTEN. De test tests/test_trace_punten.py controleert dat elke
# aanroep in de lussen van main.py in deze lijst staat; vergeet je er een, dan wordt
# die test rood.
#
# VEILIGHEID:
#   - Een module of functie die niet bestaat wordt overgeslagen (met een melding in het
#     resultaat), nooit een crash.
#   - Elke functie wordt maar 1x omhuld, ook bij een tweede aanroep van installeer().
#   - Staat de tracer uit, dan roept de omhulling direct de echte functie aan.
#   - De omhulling geeft de uitkomst en fouten van de echte functie ongewijzigd door.
#
# PUUR SYMBOLISCH: namen en tijd. Geen ML.

import functools

# modulenaam (loader.loaded_modules) -> functies die we willen zien
TRACE_PUNTEN = {
    # achtergrond_loop en snelle_activiteit_loop in main.py
    "session_watcher": ["check_pauze", "check_activity_interruption"],
    "activity_detector": ["detect_activity"],
    "focus_detector": ["get_focus_info"],
    "context_manager": ["update_presence_info", "get_current"],
    "weather": ["check_proactieve_waarschuwing", "check_ochtend_samenvatting"],
    "rain": ["check_proactief"],
    "emergence_engine": ["reflect"],
    "handler_fouten": ["check_nieuwe_fouten"],
    "intent_classifier": ["retrain_vanuit_bestanden"],
    "contradiction_checker": ["check_contradictions"],
    "topic_suggestions": ["check_suggesties"],
    # eigen threads van modules (de functie die elke ronde draait)
    "watchdog": ["tik"],
    "datum_terugblik": ["check_nu"],
    "zelftest": ["controleer_nacht"],
    "naam_onderhoud": ["check_nieuwe_namen"],
    # rechtstreeks aangeroepen door de router (niet via de EventBus)
    "response_engine": ["generate"],
}


def _maak_omhulling(tracer, label, origineel):
    @functools.wraps(origineel)
    def omhulling(*args, **kwargs):
        if not tracer.aan:
            return origineel(*args, **kwargs)
        start = tracer.begin()
        try:
            return origineel(*args, **kwargs)
        finally:
            tracer.trace(label, start)
    omhulling._getraceerd = True
    return omhulling


def installeer(event_bus, modules, punten=None):
    """
    Omhult de functies uit `punten` (standaard TRACE_PUNTEN) van de geladen modules.
    Geeft {"omhuld": [labels], "overgeslagen": [(label, reden)]}.
    """
    punten = TRACE_PUNTEN if punten is None else punten
    resultaat = {"omhuld": [], "overgeslagen": []}
    tracer = getattr(event_bus, "tracer", None)
    for modulenaam, functies in punten.items():
        for functie in functies:
            label = f"{modulenaam}.{functie}"
            if tracer is None:
                resultaat["overgeslagen"].append((label, "bus heeft geen tracer"))
                continue
            instantie = (modules or {}).get(modulenaam)
            if instantie is None:
                resultaat["overgeslagen"].append((label, "module niet geladen"))
                continue
            huidig = getattr(instantie, functie, None)
            if huidig is None or not callable(huidig):
                resultaat["overgeslagen"].append((label, "functie bestaat niet"))
                continue
            if getattr(huidig, "_getraceerd", False):
                continue                      # al omhuld
            try:
                setattr(instantie, functie, _maak_omhulling(tracer, label, huidig))
            except Exception as e:            # bv. een object zonder eigen attributen
                resultaat["overgeslagen"].append((label, f"kon niet omhullen: {type(e).__name__}"))
                continue
            resultaat["omhuld"].append(label)
    return resultaat