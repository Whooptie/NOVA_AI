# core/trace_router.py
#
# Live brein-weergave (nova_state.md, punt 79): ALLE modules zichtbaar, automatisch.
#
# WAAROM?
#   core/tracer.py ziet alleen wat de EventBus aanroept, en core/trace_punten.py alleen
#   een vaste lijst. Maar de router (intent_router) roept ongeveer 54 detect_*()-functies
#   en de semantic-module rechtstreeks aan, en veel modules praten zo met elkaar.
#   Hier wordt bij het opstarten van ELKE geladen module elke publieke functie omhuld:
#   eerst meldt de functie zich bij de tracer (naam, duur), daarna doet hij precies wat
#   hij deed. Er is geen lijst om bij te houden: een module of functie die je later
#   bijbouwt, doet na de volgende herstart vanzelf mee.
#
# EXTRA VOOR DE ROUTER:
#   - Ook de detect_*()-functies en _route_*()-stappen (privaat) worden omhuld.
#   - Bij een detect_*() onthoudt het record "treffer": True als hij het bericht afhandelde.
#     De detectoren die niets vonden zijn de "zoekende" flitsen, de treffer is de winnaar.
#   - De intent-tabellen van de router houden de originele functies vast; die worden
#     daarom na het omhullen opnieuw opgebouwd.
#
# EIGEN TIJD:
#   Een omhulde functie die andere omhulde functies of EventBus-handlers aanroept, telt hun
#   tijd mee in "duur_ms". "eigen_ms" is de tijd zonder die kinderen, zodat de pagina niet de
#   verkeerde module als traag aanwijst. De stapel daarvoor zit in core/tracer.py.
#
# VEILIGHEID:
#   - Staat de tracer uit, dan roept de omhulling direct de echte functie aan.
#   - Uitkomst en fouten van de echte functie gaan ongewijzigd door.
#   - Alleen gewone functies (def) van een klasse; geen properties, staticmethod,
#     classmethod, async-functies of modules. Dunder-namen en "_"-namen worden
#     overgeslagen (behalve de router-stappen hierboven).
#   - Elke functie wordt maar 1x omhuld; al omhulde functies (trace_punten) blijven zoals ze zijn.
#   - Wat niet omhuld kan worden, wordt overgeslagen, nooit een crash.
#
# PUUR SYMBOLISCH: namen en tijd. Geen ML.

import functools
import inspect

# modules die we bewust NIET omhullen (bv. omdat ze zelf elke regel loggen)
UITGESLOTEN_MODULES = {"logger", "brein_stream"}

# privé-functies van de router die wel meedoen
ROUTER_NAAM = "intent_router"
ROUTER_PREFIXEN = ("detect_", "_route_")


def _maak_omhulling(tracer, label, origineel, met_treffer):
    @functools.wraps(origineel)
    def omhulling(*args, **kwargs):
        if not tracer.aan:
            return origineel(*args, **kwargs)
        start = tracer.begin()
        treffer = None
        try:
            resultaat = origineel(*args, **kwargs)
            if met_treffer:
                try:
                    treffer = bool(resultaat)
                except Exception:
                    treffer = None
            return resultaat
        finally:
            tracer.trace(label, start, treffer=treffer)   # berekent duur en eigen tijd zelf
    omhulling._getraceerd = True
    return omhulling


def _functienamen(instantie, is_router):
    """Namen van gewone functies die op de KLASSE staan (niet via een property e.d.)."""
    namen = []
    for naam in dir(type(instantie)):
        if naam.startswith("__"):
            continue
        privaat = naam.startswith("_")
        if privaat and not (is_router and naam.startswith(ROUTER_PREFIXEN)):
            continue
        try:
            statisch = inspect.getattr_static(type(instantie), naam)
        except AttributeError:
            continue
        if not inspect.isfunction(statisch) or inspect.iscoroutinefunction(statisch):
            continue
        namen.append(naam)
    return namen


def installeer_auto(event_bus, modules, uitgesloten=None):
    """
    Omhult de publieke functies van alle geladen modules (en de detect_*/_route_* van de
    router). Geeft {"omhuld": aantal, "per_module": {naam: aantal}, "overgeslagen": [(label, reden)]}.
    """
    resultaat = {"omhuld": 0, "per_module": {}, "overgeslagen": []}
    tracer = getattr(event_bus, "tracer", None)
    if tracer is None:
        resultaat["overgeslagen"].append(("*", "bus heeft geen tracer"))
        return resultaat
    uitgesloten = UITGESLOTEN_MODULES if uitgesloten is None else uitgesloten

    for modulenaam, instantie in sorted((modules or {}).items()):
        if instantie is None or modulenaam in uitgesloten or inspect.ismodule(instantie):
            continue
        is_router = modulenaam == ROUTER_NAAM
        try:
            namen = _functienamen(instantie, is_router)
        except Exception as e:
            resultaat["overgeslagen"].append((modulenaam, f"kon functies niet lezen: {type(e).__name__}"))
            continue
        aantal = 0
        for naam in namen:
            label = f"{modulenaam}.{naam}"
            try:
                if naam in vars(instantie):          # al een eigen (omhulde) versie op de instantie
                    continue
                huidig = getattr(instantie, naam)
                if not callable(huidig) or getattr(huidig, "_getraceerd", False):
                    continue
                met_treffer = naam.startswith("detect_")
                setattr(instantie, naam, _maak_omhulling(tracer, label, huidig, met_treffer))
                aantal += 1
            except Exception as e:                   # bv. __slots__ of een vergrendeld object
                resultaat["overgeslagen"].append((label, f"kon niet omhullen: {type(e).__name__}"))
        if aantal:
            resultaat["per_module"][modulenaam] = aantal
            resultaat["omhuld"] += aantal
        if is_router and aantal:
            _bouw_tabellen_opnieuw(instantie, resultaat)
    return resultaat


def _bouw_tabellen_opnieuw(router, resultaat):
    """De intent-tabellen bevatten de ORIGINELE detect-functies; bouw ze opnieuw op."""
    for bouwnaam in ("_build_intent_tabel_deel1", "_build_intent_tabel_deel2"):
        doelnaam = bouwnaam.replace("_build", "", 1)         # "_intent_tabel_deel1"
        bouw = getattr(router, bouwnaam, None)
        if not callable(bouw) or not hasattr(router, doelnaam):
            continue
        try:
            setattr(router, doelnaam, bouw())
        except Exception as e:
            resultaat["overgeslagen"].append((bouwnaam, f"tabel niet opnieuw opgebouwd: {type(e).__name__}"))