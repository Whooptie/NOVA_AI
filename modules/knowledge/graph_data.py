#modules/knowledge/graph_data.py

"""
graph_data.py -- Semantic Fase 13.1: data voor de kennisgraaf.

Pure hulpfuncties (geen klasse, geen init_module, geen EventBus, geen externe
bibliotheek). Ze lezen een concepts-dictionary (zoals ConceptStore.concepts of
json.load(concepts.json)) en geven gewone lijsten/dictionaries terug.

100% symbolisch: tellen, doorlopen en vergelijken. Geen ML, geen generatie.

Wat zit erin:
  - bouw_graaf()       nodes + edges rond 1 concept (breadth-first, met diepte en maximum)
  - vind_pad()         kortste pad tussen 2 concepten over ALLE relatietypes
  - statistieken()     hoe dicht/dun is de graaf (punt 50a)
  - statistieken_tekst() leesbare Nederlandse tekst van die cijfers

Afspraken (zelfde als de rest van Nova):
  - sense of relatie met status == "rejected" telt NIET mee (tenzij toon_afgewezen=True)
  - de richting van een relatie blijft bewaard (van -> naar), maar bij het zoeken van
    buren en paden wordt in beide richtingen gelopen
  - HTML-veiligheid is NIET hier maar in de tekenlaag (13.2): deze module geeft ruwe tekst
"""

from collections import deque

STANDAARD_DIEPTE = 2
STANDAARD_MAX_NODES = 60
MAX_DIEPTE_TOEGESTAAN = 4          # grens voor de gebruiker, anders wordt het een kluwen
MAX_PAD_DIEPTE = 6                 # zelfde als ReasoningEngine.MAX_DEPTH

# relaties die van beide kanten even waar zijn: A related_to B is hetzelfde als B related_to A
SYMMETRISCHE_TYPES = {"related_to", "synonym", "antonym"}


# ---------------------------------------------------------------------------
# Intern: alle bruikbare relaties verzamelen
# ---------------------------------------------------------------------------

def _kaal_woord(tekst):
    """'Hond#2' -> 'hond'. Doelen in concepts.json zijn gewone woorden, dit is een vangnet."""
    return str(tekst).strip().lower().split("#")[0]


def _verzamel_relaties(concepten, relatietypes=None, toon_afgewezen=False):
    """
    Geeft een lijst relaties terug, elk een dict:
      {"van", "type", "naar", "status", "bron", "confidence", "sense_id"}
    Een relatie staat op een sense. Is de sense afgewezen, dan vallen al zijn relaties weg.
    """
    resultaat = []
    for woord, concept in concepten.items():
        if not isinstance(concept, dict):
            continue
        for sense in concept.get("senses", []):
            if not isinstance(sense, dict):
                continue
            if sense.get("status") == "rejected" and not toon_afgewezen:
                continue
            for rel in sense.get("relations", []):
                if not isinstance(rel, dict):
                    continue
                rel_type = rel.get("type")
                doel = rel.get("target")
                if not rel_type or not doel:
                    continue
                status = rel.get("status", "confirmed")
                if status == "rejected" and not toon_afgewezen:
                    continue
                if relatietypes and rel_type not in relatietypes:
                    continue
                resultaat.append({
                    "van": _kaal_woord(woord),
                    "type": rel_type,
                    "naar": _kaal_woord(doel),
                    "status": status,
                    "bron": rel.get("source", ""),
                    "confidence": rel.get("confidence", 1.0),
                    "sense_id": sense.get("sense_id", ""),
                })
    return resultaat


def _canoniek(van, rel_type, naar):
    """
    Zet een relatie in 1 vaste vorm, zodat dezelfde waarheid maar 1 keer geteld/getekend wordt:
      - 'A has_part B' wordt 'B part_of A'
      - symmetrische types worden alfabetisch gesorteerd (A related_to B == B related_to A)
    Geeft (van, type, naar, gericht) terug; gericht=False betekent: geen pijlpunt nodig.
    """
    if rel_type == "has_part":
        return naar, "part_of", van, True
    if rel_type in SYMMETRISCHE_TYPES:
        eerste, tweede = sorted((van, naar))
        return eerste, rel_type, tweede, False
    return van, rel_type, naar, True


def _ontdubbel(relaties):
    """
    Voegt gelijke relaties samen (zie _canoniek). Verschillen de statussen, dan wint de
    zwakste: is 1 van de twee 'unverified', dan toont de graaf 'unverified' (eerlijker).
    """
    uniek = {}
    for rel in relaties:
        van, rel_type, naar, gericht = _canoniek(rel["van"], rel["type"], rel["naar"])
        sleutel = (van, rel_type, naar)
        if sleutel not in uniek:
            uniek[sleutel] = {**rel, "van": van, "type": rel_type, "naar": naar, "gericht": gericht}
        elif rel["status"] != "confirmed":
            uniek[sleutel]["status"] = rel["status"]
    return list(uniek.values())


def _bouw_buren(relaties):
    """woord -> lijst van (buur, relatie). Beide richtingen, zodat BFS overal kan lopen."""
    buren = {}
    for rel in relaties:
        if rel["van"] == rel["naar"]:
            continue
        buren.setdefault(rel["van"], []).append((rel["naar"], rel))
        buren.setdefault(rel["naar"], []).append((rel["van"], rel))
    return buren


def _eerste_zichtbare_sense(concept):
    """Eerste sense die niet afgewezen is (voor de definitie in de pop-up)."""
    for sense in concept.get("senses", []):
        if isinstance(sense, dict) and sense.get("status") != "rejected":
            return sense
    return None


def _sleutel_opzoeken(concepten, woord):
    """Zoekt een woord case-insensitief op. Geeft de echte sleutel of None."""
    gezocht = _kaal_woord(woord)
    if gezocht in concepten:
        return gezocht
    for sleutel in concepten:
        if _kaal_woord(sleutel) == gezocht:
            return sleutel
    return None


# ---------------------------------------------------------------------------
# 13.1a  De graaf rond 1 concept
# ---------------------------------------------------------------------------

def bouw_graaf(concepten, centrum, diepte=STANDAARD_DIEPTE, max_nodes=STANDAARD_MAX_NODES,
               relatietypes=None, toon_afgewezen=False):
    """
    Bouwt nodes en edges rond `centrum`.

    Breadth-first: eerst alle directe buren (afstand 1), dan hun buren (afstand 2), enzovoort,
    tot `diepte`. Bij `max_nodes` stopt het toevoegen; dan staat "afgekapt" op True.

    Terug:
      {
        "centrum": "fiets",
        "diepte": 2,
        "afgekapt": False,
        "nodes": [{"id","label","afstand","aantal_relaties","bestaat","definitie","ontstaan"}],
        "edges": [{"van","naar","type","status","bron","confidence"}],
        "fout": None            # of een korte tekst als er niets te tekenen valt
      }
    """
    leeg = {"centrum": _kaal_woord(centrum), "diepte": diepte, "afgekapt": False,
            "nodes": [], "edges": [], "fout": None}

    sleutel = _sleutel_opzoeken(concepten, centrum)
    if sleutel is None:
        leeg["fout"] = "onbekend"
        return leeg

    diepte = max(1, min(int(diepte), MAX_DIEPTE_TOEGESTAAN))
    max_nodes = max(2, int(max_nodes))
    start = _kaal_woord(sleutel)
    leeg["centrum"] = start
    leeg["diepte"] = diepte

    relaties = _verzamel_relaties(concepten, relatietypes, toon_afgewezen)
    buren = _bouw_buren(relaties)

    if start not in buren:
        # concept bestaat wel, maar heeft geen (bruikbare) relaties
        leeg["nodes"] = [_maak_node(concepten, start, 0, 0)]
        leeg["fout"] = "geen_relaties"
        return leeg

    afstanden = {start: 0}
    wachtrij = deque([start])
    afgekapt = False

    while wachtrij:
        huidig = wachtrij.popleft()
        if afstanden[huidig] >= diepte:
            continue
        # vaste volgorde, zodat dezelfde vraag altijd dezelfde graaf geeft
        for buur, _rel in sorted(buren.get(huidig, []), key=lambda t: t[0]):
            if buur in afstanden:
                continue
            if len(afstanden) >= max_nodes:
                afgekapt = True
                continue
            afstanden[buur] = afstanden[huidig] + 1
            wachtrij.append(buur)

    graad = {woord: len(lijst) for woord, lijst in buren.items()}
    nodes = [_maak_node(concepten, woord, afstand, graad.get(woord, 0))
             for woord, afstand in sorted(afstanden.items(), key=lambda t: (t[1], t[0]))]

    # alle relaties tussen opgenomen nodes, ontdubbeld (has_part/part_of en A<->B samengevoegd)
    edges = []
    for rel in _ontdubbel(relaties):
        if rel["van"] in afstanden and rel["naar"] in afstanden and rel["van"] != rel["naar"]:
            edges.append({
                "van": rel["van"], "naar": rel["naar"], "type": rel["type"],
                "status": rel["status"], "bron": rel["bron"], "confidence": rel["confidence"],
                "gericht": rel["gericht"],
            })
    edges.sort(key=lambda e: (e["van"], e["type"], e["naar"]))

    leeg["nodes"] = nodes
    leeg["edges"] = edges
    leeg["afgekapt"] = afgekapt
    return leeg


def _maak_node(concepten, woord, afstand, aantal_relaties):
    sleutel = _sleutel_opzoeken(concepten, woord)
    node = {"id": woord, "label": woord, "afstand": afstand,
            "aantal_relaties": aantal_relaties,
            "bestaat": sleutel is not None, "definitie": "", "ontstaan": None}
    if sleutel is not None:
        sense = _eerste_zichtbare_sense(concepten[sleutel])
        if sense:
            definitie = sense.get("definition", "")
            node["definitie"] = "" if definitie == "unknown" else definitie
            node["ontstaan"] = sense.get("ontstaan")
    return node


# ---------------------------------------------------------------------------
# 13.1a-2  De volledige graaf (voor de interactieve 3D-pagina)
# ---------------------------------------------------------------------------

def volledige_graaf(concepten, toon_afgewezen=False):
    """
    ALLE nodes en edges (ontdubbeld), zodat de pagina zelf kan uitbreiden als je op een
    woord klikt, zonder dat Nova er nog iets voor hoeft te doen.

    Terug: {"nodes": [...], "edges": [...]} in dezelfde vorm als bouw_graaf().
    """
    relaties = [r for r in _ontdubbel(_verzamel_relaties(concepten, None, toon_afgewezen))
                if r["van"] != r["naar"]]
    graad = {}
    for rel in relaties:
        graad[rel["van"]] = graad.get(rel["van"], 0) + 1
        graad[rel["naar"]] = graad.get(rel["naar"], 0) + 1

    ids = set(graad) | {_kaal_woord(w) for w in concepten}
    nodes = [_maak_node(concepten, woord, 0, graad.get(woord, 0)) for woord in sorted(ids)]
    edges = [{"van": r["van"], "naar": r["naar"], "type": r["type"], "status": r["status"],
              "bron": r["bron"], "confidence": r["confidence"], "gericht": r["gericht"]}
             for r in relaties]
    edges.sort(key=lambda e: (e["van"], e["type"], e["naar"]))
    return {"nodes": nodes, "edges": edges}


# ---------------------------------------------------------------------------
# 13.1a-3  Groepen van woorden die bij elkaar horen (voor de kleuren in de 3D-pagina)
# ---------------------------------------------------------------------------

def gemeenschappen(nodes, edges, resolutie=1.5, seed=1, max_groepen=16, min_grootte=8):
    """
    Zoekt groepen woorden die onderling veel verbonden zijn (bv. alles rond lichaam, rond
    voertuigen, rond tijd). Dit is een gewoon grafenalgoritme (Louvain uit NetworkX), geen
    ML en geen taalmodel: het telt alleen hoeveel verbindingen er binnen en tussen groepen zijn.
    Met een vaste `seed` geeft dezelfde graaf altijd dezelfde groepen.

    Terug: (toewijzing, groepen)
      toewijzing: {woord_id: groepnummer}   (-1 = hoort bij geen grote groep)
      groepen   : [{"naam": "voertuig", "grootte": 59}, ...]  groep 0 is de grootste
    De naam van een groep is het best verbonden woord erin.
    Zonder NetworkX (niet geinstalleerd) geeft dit ({}, []): de pagina werkt dan gewoon, zonder kleuren.
    """
    try:
        import networkx as nx
    except ImportError:
        return {}, []

    graaf = nx.Graph()
    graaf.add_nodes_from(n["id"] for n in nodes)
    for e in edges:
        if e["van"] != e["naar"]:
            graaf.add_edge(e["van"], e["naar"])
    if graaf.number_of_edges() == 0:
        return {}, []

    graad = dict(graaf.degree())
    stukken = nx.community.louvain_communities(graaf, seed=seed, resolution=resolutie)
    stukken = sorted(stukken, key=lambda groep: (-len(groep), min(groep)))

    toewijzing = {n["id"]: -1 for n in nodes}
    groepen = []
    for stuk in stukken:
        if len(groepen) >= max_groepen or len(stuk) < min_grootte:
            break
        naam = sorted(stuk, key=lambda w: (-graad[w], w))[0]
        for woord in stuk:
            toewijzing[woord] = len(groepen)
        groepen.append({"naam": naam, "grootte": len(stuk)})
    return toewijzing, groepen


# ---------------------------------------------------------------------------
# 13.1b  Kortste pad tussen twee concepten
# ---------------------------------------------------------------------------

def vind_pad(concepten, woord_a, woord_b, max_diepte=MAX_PAD_DIEPTE,
             relatietypes=None, toon_afgewezen=False):
    """
    Kortste pad van a naar b over alle relatietypes (in beide richtingen).

    Terug: lijst stappen, elk {"van","type","naar","omgekeerd"}.
      "omgekeerd" is True als de opgeslagen relatie de andere kant op wijst
      (bv. pad hond -> dier via 'dier has_part ...' zou omgekeerd zijn).
    Lege lijst = a en b zijn hetzelfde woord. None = geen pad (of onbekend woord).
    """
    sleutel_a = _sleutel_opzoeken(concepten, woord_a)
    sleutel_b = _sleutel_opzoeken(concepten, woord_b)
    if sleutel_a is None or sleutel_b is None:
        return None

    start, doel = _kaal_woord(sleutel_a), _kaal_woord(sleutel_b)
    if start == doel:
        return []

    buren = _bouw_buren(_verzamel_relaties(concepten, relatietypes, toon_afgewezen))
    vorige = {start: None}           # woord -> (vorig woord, relatie)
    wachtrij = deque([(start, 0)])

    while wachtrij:
        huidig, afstand = wachtrij.popleft()
        if afstand >= max_diepte:
            continue
        for buur, rel in sorted(buren.get(huidig, []), key=lambda t: t[0]):
            if buur in vorige:
                continue
            vorige[buur] = (huidig, rel)
            if buur == doel:
                return _pad_terugbouwen(vorige, doel)
            wachtrij.append((buur, afstand + 1))
    return None


def _pad_terugbouwen(vorige, doel):
    stappen = []
    huidig = doel
    while vorige[huidig] is not None:
        vorig_woord, rel = vorige[huidig]
        stappen.append({"van": vorig_woord, "type": rel["type"], "naar": huidig,
                        "omgekeerd": rel["van"] != vorig_woord})
        huidig = vorig_woord
    stappen.reverse()
    return stappen


# ---------------------------------------------------------------------------
# 13.1c  Statistieken (punt 50a: hoe dicht is de graaf?)
# ---------------------------------------------------------------------------

def statistieken(concepten):
    """
    Cijfers over de hele graaf. Afgewezen senses/relaties tellen niet mee in de graaf
    zelf, maar worden wel apart geteld ("afgewezen_relaties").
    """
    actief = _verzamel_relaties(concepten)
    alles = _verzamel_relaties(concepten, toon_afgewezen=True)
    buren = _bouw_buren(actief)

    sleutels = [_kaal_woord(w) for w in concepten]
    sleutelset = set(sleutels)
    aantal_senses = 0
    zonder_definitie = 0
    for concept in concepten.values():
        if not isinstance(concept, dict):
            continue
        for sense in concept.get("senses", []):
            if isinstance(sense, dict) and sense.get("status") != "rejected":
                aantal_senses += 1
                if sense.get("definition", "unknown") == "unknown":
                    zonder_definitie += 1

    per_type, per_status = {}, {}
    for rel in actief:
        per_type[rel["type"]] = per_type.get(rel["type"], 0) + 1
        per_status[rel["status"]] = per_status.get(rel["status"], 0) + 1

    ontbrekend = sorted({r["naar"] for r in actief if r["naar"] not in sleutelset})
    losse = sorted(w for w in sleutelset if w not in buren)

    # eilanden = aaneengesloten stukken (alle nodes: concepten + ontbrekende doelen)
    alle_nodes = sleutelset | set(buren.keys())
    bezocht = set()
    groottes = []
    for begin in sorted(alle_nodes):
        if begin in bezocht:
            continue
        grootte = 0
        wachtrij = deque([begin])
        bezocht.add(begin)
        while wachtrij:
            huidig = wachtrij.popleft()
            grootte += 1
            for buur, _ in buren.get(huidig, []):
                if buur not in bezocht:
                    bezocht.add(buur)
                    wachtrij.append(buur)
        groottes.append(grootte)
    groottes.sort(reverse=True)
    verbonden_stukken = [g for g in groottes if g > 1]

    top = sorted(((w, len(l)) for w, l in buren.items() if w in sleutelset),
                 key=lambda t: (-t[1], t[0]))[:5]

    aantal_concepten = len(sleutelset)
    return {
        "concepten": aantal_concepten,
        "senses": aantal_senses,
        "relaties": len(actief),
        "unieke_relaties": len(_ontdubbel(actief)),
        "afgewezen_relaties": len(alles) - len(actief),
        "type_ontbreekt": sum(1 for r in actief if str(r["type"]).strip().lower() in ("none", "null")),
        "gem_relaties_per_concept": round(len(actief) / aantal_concepten, 2) if aantal_concepten else 0.0,
        "per_type": dict(sorted(per_type.items(), key=lambda t: -t[1])),
        "per_status": per_status,
        "losse_concepten": losse,
        "ontbrekende_doelen": ontbrekend,
        "zonder_definitie": zonder_definitie,
        "stukken": len(verbonden_stukken),
        "grootste_stuk": verbonden_stukken[0] if verbonden_stukken else 0,
        "top_verbonden": top,
    }


def statistieken_tekst(stats):
    """Korte, leesbare samenvatting voor in de chat of het debug-commando."""
    if not stats or not stats.get("concepten"):
        return "De kennisgraaf is nog leeg."

    regels = [
        f"Graaf: {stats['concepten']} concepten, {stats['senses']} betekenissen, "
        f"{stats['relaties']} relaties opgeslagen, waarvan {stats['unieke_relaties']} unieke verbindingen "
        f"(gemiddeld {stats['gem_relaties_per_concept']} opgeslagen per concept).",
    ]
    if stats["per_type"]:
        delen = [f"{t} {n}" for t, n in list(stats["per_type"].items())[:6]]
        regels.append("Per type: " + ", ".join(delen) + ".")
    bevestigd = stats["per_status"].get("confirmed", 0)
    onzeker = stats["per_status"].get("unverified", 0)
    regels.append(f"Zekerheid: {bevestigd} bevestigd, {onzeker} niet bevestigd.")

    regels.append(f"Losse concepten zonder enige relatie: {len(stats['losse_concepten'])}.")
    regels.append(f"Aaneengesloten stukken: {stats['stukken']} "
                  f"(het grootste heeft {stats['grootste_stuk']} woorden).")
    if stats["ontbrekende_doelen"]:
        regels.append(f"Relaties wijzen naar {len(stats['ontbrekende_doelen'])} woorden "
                      f"die zelf geen concept zijn: {', '.join(stats['ontbrekende_doelen'][:5])}"
                      f"{' ...' if len(stats['ontbrekende_doelen']) > 5 else ''}.")
    if stats.get("type_ontbreekt"):
        regels.append(f"LET OP: {stats['type_ontbreekt']} relaties hebben als type de tekst 'None' "
                      f"(een fout in concepts.json).")
    if stats["zonder_definitie"]:
        regels.append(f"Betekenissen zonder echte definitie ('unknown'): {stats['zonder_definitie']}.")
    if stats["top_verbonden"]:
        regels.append("Best verbonden: " + ", ".join(f"{w} ({n})" for w, n in stats["top_verbonden"]) + ".")
    return "\n".join(regels)