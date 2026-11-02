"""
core/concept_hint.py  --  Fase 13: semantic als routing-hint.

Doel: als de intent classifier te onzeker is (confidence < 0.30), kijken
of een sleutelwoord uit de zin in concepts.json een korte verbinding
heeft met een "anker-concept" van een categorie (bv. 'nat' -> 'regen').

100% symbolisch: alleen opzoeken en relaties volgen. Geen ML, geen gokken
op onbekende woorden: kent Nova het woord niet, dan komt er geen hint.
"""

import re

# De ENIGE koppeling die in code staat: categorie -> anker-woorden.
# De kennis zelf (welke woorden bij 'weer' horen) staat in concepts.json.
CATEGORIE_ANKERS = {
    "weather": ["weer"],
    "rain": ["regen"],
    "time": ["klok"],
    "chess": ["schaken", "schaak"],
}

# 0 = het woord zelf is een anker, 1 = direct verbonden,
# 2 = via 1 tussenwoord. Bewust klein: bij 3-4 stappen is bijna
# alles met alles verbonden.
MAX_AFSTAND = 1

RELATIE_TYPES = {"related_to", "is_a", "part_of", "has_part",
                 "synonym", "used_for", "causes", "property_of"}

try:
    from core.nl_stopwoorden import STOPWOORDEN
except Exception:
    STOPWOORDEN = set()

try:
    import simplemma
except Exception:
    simplemma = None


def _is_bruikbaar(relatie):
    """Rejected relaties worden genegeerd (trust state van Nova)."""
    return (relatie.get("type") in RELATIE_TYPES
            and relatie.get("status") != "rejected")


def bouw_graaf(concepts):
    """
    Maakt van concepts.json een buurlijst: woord -> set(buurwoorden).
    Relaties tellen in BEIDE richtingen: staat er 'nat related_to
    regen', dan is regen ook verbonden met nat.
    """
    graaf = {}
    for woord, data in concepts.items():
        graaf.setdefault(woord, set())
        for sense in data.get("senses", []):
            if sense.get("status") == "rejected":
                continue
            for rel in sense.get("relations", []):
                if not _is_bruikbaar(rel):
                    continue
                doel = rel.get("target")
                if not doel or doel == woord:
                    continue
                graaf[woord].add(doel)
                graaf.setdefault(doel, set()).add(woord)
    return graaf


def haal_sleutelwoorden(tekst, concepts):
    """Woorden uit de zin die Nova KENT, zonder stopwoorden (ook lemma)."""
    resultaat = []
    for woord in re.findall(r"[a-zà-ÿ]+", tekst.lower()):
        if woord in STOPWOORDEN or len(woord) < 2:
            continue
        kandidaten = [woord]
        if simplemma is not None:
            try:
                lemma = simplemma.lemmatize(woord, lang="nl")
                if lemma and lemma != woord:
                    kandidaten.append(lemma)
            except Exception:
                pass
        for kandidaat in kandidaten:
            if kandidaat in concepts and kandidaat not in resultaat:
                resultaat.append(kandidaat)
                break
    return resultaat


def _afstanden_vanaf(graaf, start, max_afstand):
    """Breadth-first: {woord: aantal stappen vanaf start}."""
    afstanden = {start: 0}
    rij = [start]
    while rij:
        huidig = rij.pop(0)
        if afstanden[huidig] >= max_afstand:
            continue
        for buur in graaf.get(huidig, ()):
            if buur not in afstanden:
                afstanden[buur] = afstanden[huidig] + 1
                rij.append(buur)
    return afstanden


def zoek_hint(tekst, concepts, graaf=None, ankers=None, max_afstand=MAX_AFSTAND):
    """
    Geeft {"label", "sleutelwoord", "anker", "afstand"} of None.
    None = geen woord gekend, geen verbinding, OF twee categorieen even
    sterk (dan liever niets zeggen dan gokken).
    """
    ankers = ankers or CATEGORIE_ANKERS
    graaf = graaf if graaf is not None else bouw_graaf(concepts)

    beste = {}  # label -> (afstand, sleutelwoord, anker)
    for sleutel in haal_sleutelwoorden(tekst, concepts):
        afstanden = _afstanden_vanaf(graaf, sleutel, max_afstand)
        for label, anker_woorden in ankers.items():
            for anker in anker_woorden:
                if anker in afstanden:
                    kandidaat = (afstanden[anker], sleutel, anker)
                    if label not in beste or kandidaat[0] < beste[label][0]:
                        beste[label] = kandidaat

    if not beste:
        return None

    gesorteerd = sorted(beste.items(), key=lambda kv: kv[1][0])
    if len(gesorteerd) > 1 and gesorteerd[0][1][0] == gesorteerd[1][1][0]:
        return None  # gelijkspel tussen categorieen: niet gokken

    label, (afstand, sleutel, anker) = gesorteerd[0]
    return {"label": label, "sleutelwoord": sleutel,
            "anker": anker, "afstand": afstand}


# Ingang voor intent_router: leest concepts.json zelf en herbouwt de
# graaf alleen als het bestand veranderd is.
_cache = {"pad": None, "mtime": None, "concepts": None, "graaf": None}


def hint_voor_zin(tekst, pad="data/concepts.json"):
    """Retourneert een hint-dict of None. Gooit nooit een fout."""
    import json
    import os
    try:
        mtime = os.path.getmtime(pad)
        if _cache["pad"] != pad or _cache["mtime"] != mtime:
            with open(pad, encoding="utf-8") as f:
                concepts = json.load(f)
            _cache.update(pad=pad, mtime=mtime, concepts=concepts,
                          graaf=bouw_graaf(concepts))
        return zoek_hint(tekst, _cache["concepts"], _cache["graaf"])
    except Exception:
        return None