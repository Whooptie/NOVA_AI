# identity/self_uiterlijk.py
"""
Deze module laat Nova vertellen hoe ze eruitziet ("hoe ziet je haar
eruit", "welke kleur hebben je ogen", "hoe zie je eruit", ...).

VOLLEDIG symbolisch, net als self_query.py en self_architecture.py: geen
ML, geen generatie. Elk antwoord is een DOBBELSTEEN-combinatie van
vooraf geschreven zinsdelen uit data/uiterlijk.json:

    opening  +  midden  +  slot
    (5 opties)  (5 opties)  (5 opties)   ->  125 mogelijke antwoorden per deel

Er wordt nooit iets verzonnen: elke zin die Nova zegt, staat letterlijk
in uiterlijk.json.

WAAROM EEN JSON-BESTAND (anders dan self_architecture.py)?
De uiterlijk-zinnen verhuizen niet mee met de code: Kevin wil ze later
zelf kunnen aanvullen (nieuw lichaamsdeel, nieuwe zinsdelen, ander
kapsel na een nieuw avatar-model). Daarom:
  - een nieuw deel toevoegen = een nieuw blok in uiterlijk.json, GEEN
    Python aanpassen (ook de herkenning van het woord gebruikt de
    'namen' uit de JSON);
  - het bestand wordt opnieuw ingelezen zodra het gewijzigd is, dus ook
    zonder /reboot.

GEEN VASTE VERBODEN-LIJST IN DE CODE: Nova beantwoordt ENKEL de delen
die in uiterlijk.json staan. Vraagt iemand naar een deel dat daar niet
in staat, dan zegt ze neutraal dat ze er niets over te vertellen heeft.
Wat er wel en niet in het JSON-bestand komt, beslist Kevin zelf.

VARIATIE: het kiezen van een zinsdeel gaat via kies_variant() uit
modules/response_learning/variant_kiezer.py (zelfde als de rest van
Nova), zodat Response Variant Learning meeleert. Ontbreekt die module
(bv. tijdens een losse test), dan valt dit terug op random.choice().

ROUTING: intent_router.py's detect_uiterlijk() roept herken_vraag() aan
en publiceert 'intent_uiterlijk' {"deel": <naam of None>}. chat.py roept
get_beschrijving(deel) aan en publiceert het resultaat via
'layer4_response' (zodat Nova's toon er doorheen schemert).
"""

import json
import random
import re
from pathlib import Path

try:
    from modules.response_learning.variant_kiezer import kies_variant
except Exception:  # pragma: no cover - enkel als de module ontbreekt
    kies_variant = None

# identity/self_uiterlijk.py -> projectmap = twee mappen omhoog.
STANDAARD_PAD = Path(__file__).resolve().parent.parent / "data" / "uiterlijk.json"

# Zinsdeel-rijen, in de volgorde waarin ze aan elkaar geplakt worden.
RIJEN = ("opening", "midden", "slot")

# Antwoord als Nova het gevraagde deel niet kent (staat niet in de JSON).
_ONBEKEND = [
    "Daar heb ik niets over te vertellen.",
    "Daar ga ik niet op in. Vraag me gerust iets over mijn ogen of mijn haar.",
    "Dat is niet iets wat ik beschrijf. Over mijn gezicht of mijn haar praat ik wel.",
]

# Korte aarzelzin achter een beschrijving als de verlegenheid hoog staat.
AARZEL = ["…", "Ja.", "Nou ja.", "Kijk niet zo.", "Zeg jij het maar.",
          "Hm.", "Even.", "Niet lachen."]
KORTE_AARZEL = ["…", "Ja.", "Nou ja.", "Hm."]
_laatste_aarzel = ""


def _aarzel(kort=False):
    global _laatste_aarzel
    keuzes = KORTE_AARZEL if kort else AARZEL
    for _ in range(6):
        zin = random.choice(keuzes)
        if zin != _laatste_aarzel:
            _laatste_aarzel = zin
            return zin
    return keuzes[0]

# De router en uiterlijk.json gebruiken soms meervoud/volkstaal;
# die moeten naar de node in body_appearance.json wijzen.
DEEL_ALIAS = {
    "tepels": "tepel_links",
    "tepel": "tepel_links",
    "borsten": "borst_links",
    "borst": "borst_links",
    "anus": "anus_rand",
    "kontgat": "anus_rand",
    "schaamlippen": "vulva",
    "clit": "clitoris",
    "achterwerk": "billen",
}

# Bestand-cache: pad -> (laatste wijzigingstijd, inhoud). Zo lezen we het
# JSON-bestand enkel opnieuw in als het echt veranderd is.
_cache = {}


def _laad(pad=None):
    """
    Geeft de 'delen'-dictionary uit uiterlijk.json terug. Herleest het
    bestand enkel als het gewijzigd is. Bij een ontbrekend of kapot
    bestand: een lege dictionary (Nova zegt dan netjes dat ze er niets
    over weet) in plaats van een crash.
    """
    pad = Path(pad) if pad else STANDAARD_PAD
    try:
        mtime = pad.stat().st_mtime_ns
    except OSError:
        return {}

    ingang = _cache.get(pad)
    if ingang and ingang[0] == mtime:
        return ingang[1]

    try:
        with open(pad, "r", encoding="utf-8") as f:
            data = json.load(f)
        delen = data.get("delen", {})
        if not isinstance(delen, dict):
            delen = {}
    except (OSError, ValueError):
        # Kapotte JSON (bv. halverwege het bewerken opgeslagen): de
        # vorige, werkende versie blijft gebruikt als die er is.
        return ingang[1] if ingang else {}

    _cache[pad] = (mtime, delen)
    return delen


def _schoon(tekst):
    """Kleine letters, zonder leestekens aan de randen en dubbele spaties."""
    t = (tekst or "").lower().strip().strip("?.!,;:")
    return re.sub(r"\s+", " ", t)


_APP_CACHE = {}


def _laad_appearance():
    """Zelfde mtime-cache als _laad(), maar voor body_appearance.json."""
    pad = Path(__file__).resolve().parent.parent / "data" / "body_appearance.json"
    try:
        mtime = pad.stat().st_mtime_ns
    except OSError:
        return {}
    ingang = _APP_CACHE.get(pad)
    if ingang and ingang[0] == mtime:
        return ingang[1]
    try:
        with open(pad, "r", encoding="utf-8") as f:
            data = json.load(f)
        nodes = data.get("nodes", {})
        if not isinstance(nodes, dict):
            nodes = {}
    except (OSError, ValueError):
        return ingang[1] if ingang else {}
    _APP_CACHE[pad] = (mtime, nodes)
    return nodes


def _body_module(event_bus):
    if event_bus is None:
        return None
    modules = getattr(event_bus, "modules", {}) or {}
    return modules.get("body_state") or modules.get("body")


def _ervaring(event_bus, deel):
    body = _body_module(event_bus)
    if body is None:
        return 0.0
    zone = DEEL_ALIAS.get(str(deel).lower(), deel) if deel else None
    if not zone:
        return 0.0
    try:
        return float(body.persistent.get("ervaring", {}).get(zone, 0.0))
    except Exception:
        return 0.0


def _bloos(event_bus):
    body = _body_module(event_bus)
    if body is None:
        return 0.0
    try:
        if hasattr(body, "huidige_bloos"):
            return body.huidige_bloos()
        return float(body.persistent.get("bloos", 0.0))
    except Exception:
        return 0.0


def _bloos_bump(event_bus, factor):
    body = _body_module(event_bus)
    if body is None:
        return
    try:
        if hasattr(body, "verhoog_bloos"):
            body.verhoog_bloos(factor)
            return
        huidig = float(body.persistent.get("bloos", 0.0))
        body.persistent["bloos"] = min(1.0, huidig + (1.0 - huidig) * factor)
        body._opslaan()
    except Exception:
        pass


def _node_voor(deel):
    if not deel:
        return None
    nodes = _laad_appearance()
    for naam in (deel, DEEL_ALIAS.get(str(deel).lower())):
        if naam and isinstance(nodes.get(naam), dict):
            return nodes[naam]
    return None


def vind_deel(tekst, pad=None):
    """
    Zoekt welk lichaamsdeel in 'tekst' genoemd wordt.
    Eerst in uiterlijk.json (namen), daarna in body_appearance.json (node-namen).
    """
    t = _schoon(tekst)
    beste, beste_lengte = None, 0

    # 1) uiterlijk.json
    for deel, blok in _laad(pad).items():
        if not isinstance(blok, dict):
            continue
        for naam in blok.get("namen", []):
            naam = str(naam).lower()
            if len(naam) > beste_lengte and re.search(rf"\b{re.escape(naam)}\b", t):
                beste, beste_lengte = deel, len(naam)

    # 2) body_appearance.json nodes (als nog niets gevonden).
    # Ook het eerste segment ("tepel" uit "tepel_links") telt als naam,
    # anders zijn de suffix-nodes onbereikbaar met hun korte naam.
    if beste is None:
        for node_naam, node in _laad_appearance().items():
            kandidaten = {str(node_naam).lower().replace("_", " ")}
            kandidaten.add(str(node_naam).split("_")[0].lower())
            if isinstance(node, dict):
                kandidaten.update(str(a).lower() for a in node.get("aliassen", []))
            for naam in kandidaten:
                if len(naam) > beste_lengte and re.search(rf"\b{re.escape(naam)}\b", t):
                    beste, beste_lengte = node_naam, len(naam)

    return beste


# Zinsvormen die duidelijk over Nova's uiterlijk gaan. Een lichaamsdeel
# alleen is niet genoeg ("haar" is ook een voornaamwoord: "ik zie haar
# morgen"), er moet een van deze vraagvormen bij staan.
_TRIGGERS = [
    re.compile(r"\bhoe (ziet|zie|zien) (je|jouw|jij)\b"),
    re.compile(r"\bhoe zijn (je|jouw)\b"),
    re.compile(r"\bwat voor \w+( \w+)? heb (je|jij)\b"),
    re.compile(r"\bwelke kleur (heeft|hebben|is|zijn) (je|jouw)\b"),
    re.compile(r"\bwelke kleur \w+ heb (je|jij)\b"),
    re.compile(r"\bbeschrijf (je|jouw) \w+"),
    re.compile(r"\bvertel (eens )?(iets )?over (je|jouw) \w+"),
    re.compile(r"\bwat is (je|jouw) \w*kleur\b"),
]

# "hoe ziet jouw X eruit" -- ook bij een onbekend X duidelijk een
# uiterlijkvraag, dus daar geeft Nova het neutrale 'niets te vertellen'.
_ZIE_ERUIT = re.compile(r"\bhoe (ziet|zie|zien)\b.*\ber ?uit\b")
_JE = re.compile(r"\b(je|jouw|jij)\b")


def herken_vraag(tekst, pad=None):
    """
    Beslist of 'tekst' een uiterlijkvraag is.

    Geeft (gevonden, deel) terug:
      (True,  "ogen")  -- vraag over een deel dat in de JSON staat
      (True,  "algemeen") -- "hoe zie je eruit" e.d.
      (True,  None)    -- "hoe ziet jouw X eruit" met een X die niet in
                          de JSON staat -> neutrale afwijzing
      (False, None)    -- geen uiterlijkvraag, intent_router gaat door
    """
    t = _schoon(tekst)
    delen = _laad(pad)

    # 1) Complete algemene vragen ("hoe zie je eruit").
    for deel, blok in delen.items():
        if not isinstance(blok, dict):
            continue
        for zin in blok.get("zinnen", []):
            if _schoon(zin) and _schoon(zin) in t:
                return True, deel

    # 2) Een bekend lichaamsdeel in een uiterlijk-vraagvorm.
    deel = vind_deel(t, pad)
    if deel and any(p.search(t) for p in _TRIGGERS):
        return True, deel

    # 3) Duidelijke "hoe ziet jouw X eruit"-vraag over een onbekend X.
    if _ZIE_ERUIT.search(t) and _JE.search(t):
        return True, None

    return False, None


def _kies(varianten, sjabloon_naam, event_bus=None, feedback_logger=None):
    """
    Kiest één zinsdeel. Via kies_variant() (Response Variant Learning)
    als die beschikbaar is, anders gewoon random.choice().
    """
    if kies_variant is not None:
        return kies_variant(
            varianten=varianten,
            sjabloon_naam=sjabloon_naam,
            event_bus=event_bus,
            variant_feedback_logger=feedback_logger,
        )
    return random.choice(varianten)


def get_beschrijving(deel, event_bus=None, feedback_logger=None, pad=None):
    """
    Bouwt het antwoord voor een lichaamsdeel.

    Bij een intiem deel (publiek: false) wint de verlegenheid van de
    ingestudeerde beschrijving: boven 0.5 komt de "verhuld"-tekst in
    plaats van de volledige uitleg, boven 0.85 valt de beschrijving
    helemaal weg en blijft er alleen een aarzelzin over.
    Daaronder: uiterlijk.json (5x5x5), dan "zeggen" uit body_appearance.json.
    """
    node = _node_voor(deel)
    intiem = isinstance(node, dict) and not node.get("publiek", True)

    bloos = _bloos(event_bus)
    ervaring = _ervaring(event_bus, deel)
    if intiem:
        _bloos_bump(event_bus, 0.22 * (1.0 - ervaring * 0.5))
        bloos = _bloos(event_bus)

    # extreem verlegen: de voorbereide tekst valt weg
    if intiem and bloos > 0.85 + ervaring * 0.08:
        return _aarzel()

    # verlegen: verhulde tekst in plaats van de volledige beschrijving
    if intiem and bloos > 0.5 + ervaring * 0.1 and node.get("verhuld"):
        return node["verhuld"] + " " + _aarzel(kort=True)

    # normale weg
    blok = _laad(pad).get(deel) if deel else None
    zinsdelen = blok.get("zinsdelen", {}) if isinstance(blok, dict) else {}

    stukken = []
    for rij in RIJEN:
        varianten = zinsdelen.get(rij) or []
        if varianten:
            stukken.append(_kies(varianten, f"uiterlijk_{deel}_{rij}", event_bus, feedback_logger))

    if stukken:
        tekst = " ".join(stukken)
        if intiem and bloos > 0.3:
            tekst += " " + _aarzel(kort=True)
        return tekst

    if isinstance(node, dict):
        zeggen = node.get("zeggen")
        if isinstance(zeggen, list):
            zeggen = [z for z in zeggen if z]
            if zeggen:
                return _kies(zeggen, f"uiterlijk_{deel}_zeggen", event_bus, feedback_logger)
        elif zeggen:
            return zeggen

    return _kies(_ONBEKEND, "uiterlijk_onbekend", event_bus, feedback_logger)