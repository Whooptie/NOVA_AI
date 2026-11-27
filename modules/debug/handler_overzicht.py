# modules/debug/handler_overzicht.py
#
# Telt hoeveel handlers (functies die op een event luisteren) Nova heeft.
# Gebruikt door het debug-commando "handlers debug".
#
# Waarom? De EventBus onthoudt in _subscribers per event welke functies erop
# luisteren. Dat is de enige plek die het ECHTE aantal kent (een telling met
# grep in de code mist abonnementen in lussen). Dit overzicht leest alleen:
# het verandert niets aan de bus.
#
# Begrippen:
#   abonnement : een functie die op 1 event luistert (dezelfde functie op
#                3 events = 3 abonnementen)
#   handler    : een unieke functie (dezelfde functie op 3 events telt 1x)
#   wildcard   : een handler op "*", dus op elk event
#
# PUUR SYMBOLISCH: tellen en sorteren. Geen ML.


def _sleutel(handler):
    """Zelfde functie van hetzelfde object = dezelfde handler."""
    zelf = getattr(handler, "__self__", None)
    func = getattr(handler, "__func__", None)
    if zelf is not None and func is not None:
        return ("methode", id(zelf), id(func))
    return ("functie", id(handler))


def _modulenaam(handler):
    naam = getattr(handler, "__module__", None)
    return naam if naam else "(onbekend)"


def tel_handlers(subscribers):
    """
    subscribers: dict {eventnaam: [handler, ...]} (zoals EventBus._subscribers).

    Geeft een dict:
      handlers      aantal unieke handlers
      abonnementen  aantal (event, handler)-koppelingen
      events        aantal events met minstens 1 luisteraar
      wildcard      aantal unieke handlers op "*"
      per_module    lijst van (modulenaam, handlers, abonnementen), grootste eerst
    """
    uniek = {}                 # sleutel -> modulenaam
    per_module = {}            # modulenaam -> {"handlers": set, "abonnementen": int}
    abonnementen = 0
    events = 0
    wildcard = set()

    for event, lijst in (subscribers or {}).items():
        if not lijst:
            continue
        events += 1
        for handler in lijst:
            sleutel = _sleutel(handler)
            module = _modulenaam(handler)
            uniek[sleutel] = module
            abonnementen += 1
            info = per_module.setdefault(module, {"handlers": set(), "abonnementen": 0})
            info["handlers"].add(sleutel)
            info["abonnementen"] += 1
            if event == "*":
                wildcard.add(sleutel)

    rijen = [(naam, len(i["handlers"]), i["abonnementen"]) for naam, i in per_module.items()]
    rijen.sort(key=lambda r: (-r[1], -r[2], r[0]))
    return {
        "handlers": len(uniek),
        "abonnementen": abonnementen,
        "events": events,
        "wildcard": len(wildcard),
        "per_module": rijen,
    }


def maak_tekst(subscribers, aantal_geladen=None, top=15):
    """Leesbare tekst voor in de console."""
    t = tel_handlers(subscribers)
    regels = [
        f"Unieke handlers: {t['handlers']}",
        f"Abonnementen (functie op een event): {t['abonnementen']}",
        f"Events met minstens 1 luisteraar: {t['events']}",
        f"Handlers op '*' (luisteren naar alles): {t['wildcard']}",
    ]
    if aantal_geladen is not None:
        regels.append(f"Geladen modules: {aantal_geladen}")
    regels.append(f"Bestanden met minstens 1 handler: {len(t['per_module'])}")
    if t["per_module"]:
        regels.append("")
        regels.append(f"Meeste handlers (top {min(top, len(t['per_module']))}):")
        for naam, h, a in t["per_module"][:top]:
            regels.append(f"  {h:>3} handlers, {a:>3} abonnementen  {naam}")
    return "\n".join(regels)