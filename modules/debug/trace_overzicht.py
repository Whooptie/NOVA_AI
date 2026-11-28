# modules/debug/trace_overzicht.py
#
# Tekst voor de debug-commando's "trace aan/uit/status/laatste" en "handlers dekking"
# (punt 79, stap 1). Alleen lezen en opmaken; de tracer zelf staat in core/tracer.py.
#
# PUUR SYMBOLISCH: tellen en sorteren. Geen ML.


def status_tekst(tracer, top=10):
    regels = [
        f"Tracer: {'AAN' if tracer.aan else 'uit'}",
        f"Records sinds het aanzetten: {tracer.totaal} (laatste {len(tracer.log)} bewaard)",
    ]
    alle = tracer.alle_records()
    keten = [r for r in alle if r["soort"] == "handler" and r.get("keten") is not None]
    achtergrond = [r for r in alle if r["soort"] in ("handler", "trace") and r.get("keten") is None]
    regels.append(f"Van de bewaarde records: {len(keten)} binnen een antwoord op Kevin, "
                  f"{len(achtergrond)} achtergrondwerk")
    if tracer.per_module:
        regels.append("")
        regels.append(f"Drukste modules (top {min(top, len(tracer.per_module))}):")
        for naam, aantal in tracer.per_module.most_common(top):
            regels.append(f"  {aantal:>5}  {naam}")
    elif not tracer.aan:
        regels.append("Zet hem aan met: trace aan")
    return "\n".join(regels)


def _ruis_handlers(records, drempel=4):
    """
    Handlers die bij minstens `drempel` VERSCHILLENDE events voorkomen (de wildcard-luisteraars
    zoals memory/logger/session_watcher): die staan bij elk bericht tientallen keren in de lijst
    en verbergen de rest. Alleen gebaseerd op de records zelf.
    """
    events = {}
    for r in records:
        if r["soort"] == "handler":
            events.setdefault(r["handler"], set()).add(r.get("event"))
    return {h for h, e in events.items() if len(e) >= drempel}


def laatste_tekst(tracer, n=15, alles=False):
    """alles=False: detect_*()-functies die NIET aansloegen (treffer False) blijven weg."""
    records = [r for r in tracer.alle_records() if r["soort"] in ("handler", "trace")]
    if not alles:
        ruis = _ruis_handlers(records)
        records = [r for r in records
                   if r.get("treffer") is not False and r["handler"] not in ruis]
    if not records:
        return "Nog geen records. " + ("" if tracer.aan else "Zet de tracer aan met: trace aan")
    regels = []
    for r in records[-n:]:
        duur = "" if r.get("duur_ms") is None else f" {r['duur_ms']:.1f} ms"
        keten = "" if r.get("keten") is None else f" [antwoord #{r['keten']}]"
        soort = "trace" if r["soort"] == "trace" else (r.get("event") or "?")
        raak = " ✓" if r.get("treffer") else ""
        regels.append(f"{r['module']:<28} {r['handler']:<40} {soort}{duur}{raak}{keten}")
    return "\n".join(regels)


def antwoord_tekst(tracer, nummer=None):
    """
    Alles wat binnen EEN antwoord op Kevin gebeurde, in de volgorde van starten.
    Zonder nummer: het laatste antwoord waarin een detect_*() aansloeg (een echte vraag,
    geen debug-commando). Wildcard-luisteraars en niet-aanslaande detectoren blijven weg.
    """
    records = [r for r in tracer.alle_records()
               if r["soort"] in ("handler", "trace") and r.get("keten") is not None]
    if not records:
        return "Nog geen antwoord gezien. " + ("" if tracer.aan else "Zet de tracer aan met: trace aan")
    if nummer is None:
        met_treffer = [r["keten"] for r in records if r.get("treffer")]
        nummer = (met_treffer or [records[-1]["keten"]])[-1]
    keten = [r for r in records if r["keten"] == nummer]
    if not keten:
        return f"Antwoord #{nummer} staat niet (meer) in de bewaarde records."
    ruis = _ruis_handlers([r for r in tracer.alle_records()])
    keten = [r for r in keten if r.get("treffer") is not False and r["handler"] not in ruis]
    keten.sort(key=lambda r: r.get("start_t", r.get("t", 0.0)))
    regels = [f"Antwoord #{nummer}: {len(keten)} stappen (zonder wildcard-ruis en niet-aanslaande detectoren)"]
    for r in keten:
        eigen = r.get("eigen_ms")
        duur = r.get("duur_ms")
        tijd = ""
        if eigen is not None:
            tijd = f" {eigen:.1f} ms eigen"
            if duur is not None and duur - eigen >= 1.0:
                tijd += f" ({duur:.1f} ms totaal)"
        raak = " ✓" if r.get("treffer") else ""
        regels.append(f"  {r['module']:<26} {r['handler']:<44}{tijd}{raak}")
    traagste = sorted((r for r in keten if (r.get("eigen_ms") or 0.0) >= 5.0),
                      key=lambda r: r["eigen_ms"], reverse=True)[:3]
    if traagste:
        regels.append("")
        regels.append("Traagste stappen (eigen tijd):")
        for r in traagste:
            regels.append(f"  {r['eigen_ms']:>8.1f} ms  {r['handler']}")
    return "\n".join(regels)


def dekking_tekst(tracer, geladen_modules):
    gezien, ongezien = tracer.dekking(geladen_modules)
    regels = [f"Geladen modules: {len(gezien) + len(ongezien)}",
              f"Gezien door de tracer: {len(gezien)}",
              f"Nog NIET gezien: {len(ongezien)}"]
    if not tracer.aan and not tracer.totaal:
        regels.append("")
        regels.append("De tracer staat uit en heeft nog niets gezien. Zet hem aan met "
                      "'trace aan', gebruik Nova even en probeer opnieuw.")
        return "\n".join(regels)
    if ongezien:
        regels.append("")
        regels.append("Deze modules deden (nog) niets via de EventBus en hebben geen trace():")
        for naam in ongezien:
            regels.append(f"  {naam}")
        regels.append("")
        regels.append("Dat kan kloppen (een module die nergens op luistert of nog niets te doen kreeg) "
                      "of er mist een trace()-aanroep. Laat Nova eerst een tijdje draaien: "
                      "achtergrondwerk verschijnt pas na een minuut of langer.")
    return "\n".join(regels)