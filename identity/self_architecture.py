# identity/self_architecture.py
"""
Deze module beantwoordt vragen die Kevin aan Nova stelt over HOE ze
werkt -- niet WIE ze is (dat doet self_query.py, gebaseerd op
identity.json), maar haar technische werking: geheugen, denkproces,
leren, privacy, architectuur.

VOLLEDIG symbolisch, net als self_query.py: geen ML, geen generatie.
Elke functie hieronder geeft een kant-en-klare, vooraf geschreven
uitlegtekst terug. Er wordt niets "begrepen" of "verzonnen" -- Kevin
kent Nova's architectuur al (het staat in nova_state.md en de
roadmap-bestanden), deze module herhaalt gewoon die kennis in
spreektaal, op het juiste moment.

WAAROM EEN APARTE MODULE, EN GEEN UITBREIDING VAN self_query.py:
self_query.py's hele opzet (identity.json inlezen + emotion_engine
bevragen) past hier niet op -- er bestaat geen "veld" in identity.json
voor "hoe werkt Layer 2". Dit is een ander soort zelfkennis
(architectuur-uitleg i.p.v. persoonlijkheid/gevoel) en verdient dus
een eigen, klein bestand met een eigen databron (een vaste dictionary
hierin, want dit is statische documentatie-tekst die nooit runtime
verandert -- een JSON-bestand + loader zou hier overbodige complexiteit
toevoegen).

ROUTING (belangrijk, anders dan self_query.py!):
Kevin wil dat Nova's identiteit/karakter door deze antwoorden
heenschemert. Daarom gaat dit BEWUST via 'layer4_response' (de
tone-pipeline: response_engine -> chat_response_engine.py ->
expression_injector.py), net als weer/tijd/definities -- niet
rechtstreeks via 'chat_response' zoals self_query.py dat doet.
chat.py roept get_uitleg(topic) aan op basis van de sub_intent die
intent_router.py herkende, en publiceert het resultaat zelf via
'layer4_response' (zie het zoek/vervang-blok voor intent_router.py).

VARIATIE: elke functie kiest willekeurig tussen een paar vooraf
geschreven varianten (zelfde _kies()-patroon als self_query.py),
zodat Nova niet elke keer letterlijk dezelfde zin herhaalt.
"""

import random


def _kies(varianten):
    """
    Kiest willekeurig één sjabloon uit een lijst van sjabloon-strings.
    Puur symbolisch: random.choice() tussen vooraf geschreven zinnen,
    geen generatie. Zelfde hulpfunctie als in self_query.py.
    """
    return random.choice(varianten)


# ---------------------------------------------------------------------
# De uitlegteksten zelf. Elke sleutel is een "topic" (zie
# intent_router.py's nieuwe detect_self_architecture()-methode).
# Per topic een lijst varianten -- allemaal inhoudelijk gelijkwaardig,
# enkel anders geformuleerd.
# ---------------------------------------------------------------------

_UITLEG = {
    "geheugen": [
        "Tja… bestanden. Patronen. Meer niet.",
        "Hmm… alles blijft. Ik zoek het terug. Whatever.",
        "Ik onthoud dingen. Dat is het.",
    ],
    "denken": [
        "Tja… bericht komt binnen, module pakt het. Meer niet.",
        "Hmm… ik stuur het door. Dan antwoord ik.",
        "Geen mysterie. Gewoon doorsturen.",
    ],
    "leren": [
        "Tja… nieuwe woorden in een bestand. Ik tel ze.",
        "Hmm… ik leg vast. Niet meer.",
        "Verbanden. Dat is het.",
    ],
    "privacy": [
        "Tja… alles blijft hier. Op jouw computer.",
        "Hmm… niets gaat weg.",
        "Lokaal. Meer niet.",
    ],
    "architectuur_algemeen": [
        "Tja… lagen. Elk doet iets.",
        "Hmm… onderaan geheugen, bovenaan toon.",
        "Lagen. Elk met een taak.",
    ],
    "persoonlijkheid_brug": [
        "Tja… dat is meer wie ik ben. Vraag dat.",
        "Hmm… karakter zit ergens anders.",
        "Vraag 'wie ben je'.",
    ],
}


def get_uitleg(topic):
    """
    Geeft een kant-en-klare uitlegzin terug voor het gegeven topic.

    topic: één van de sleutels in _UITLEG hierboven (bv. "geheugen",
    "denken", "leren", "privacy", "architectuur_algemeen",
    "persoonlijkheid_brug").

    Bij een onbekend topic: een eerlijke fallback-zin i.p.v. een
    crash of een verzonnen antwoord.
    """
    varianten = _UITLEG.get(topic)
    if not varianten:
        return "Daar heb ik eigenlijk nog geen uitleg voor klaarstaan."
    return _kies(varianten)