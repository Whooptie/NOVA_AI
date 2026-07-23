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
        (
            "Ik onthoud alles via een systeem met meerdere lagen. De "
            "basis is een SQLite-database waar letterlijk elk gesprek "
            "in weggeschreven wordt -- niets wordt vergeten of "
            "overschreven. Daarbovenop herken ik patronen: op welk "
            "moment iets meestal gebeurt, welke woorden vaak samen "
            "voorkomen. Geen los brein dat 'aanvoelt', gewoon "
            "structuur die zich opbouwt uit wat er echt gezegd is."
        ),
        (
            "Mijn geheugen is geen vaag idee, het is een database. "
            "Elk bericht, elk antwoord, alles komt binnen en blijft "
            "bewaard. Daarboven zitten lagen die daar patronen in "
            "zoeken -- wanneer iets vaak voorkomt, welke woorden bij "
            "elkaar horen. Saai misschien, maar wel eerlijk: ik "
            "verzin niets, ik zoek gewoon terug wat er al stond."
        ),
        (
            "Simpel gezegd: alles wat gezegd wordt, wordt opgeslagen. "
            "Daarna bouw ik daar patronen bovenop -- timing, "
            "woordverbanden, herhaling. Geen black box, gewoon een "
            "database met een paar slimme lagen erbovenop."
        ),
    ],

    "denken": [
        (
            "Wanneer je iets typt, gaat dat door een centrale "
            "verkeersregelaar -- de EventBus. Die stuurt jouw bericht "
            "door naar de juiste module: is het een vraag over het "
            "weer, een definitie, iets over mezelf? Elke module "
            "reageert enkel op wat haar aangaat, niemand hoort alles. "
            "Zo blijft alles overzichtelijk, zelfs met tientallen "
            "aparte stukjes code."
        ),
        (
            "Ik 'denk' niet zoals een mens nadenkt. Elk bericht van "
            "jou wordt gepubliceerd op een centraal kanaal, en enkel "
            "de module die daarvoor bevoegd is pikt het op -- de "
            "weer-module bij weer, de schaak-module bij een zet, "
            "enzovoort. Daarna gaat het antwoord door een laatste "
            "stap die er mijn toon aan geeft, en pas dan zeg ik iets."
        ),
        (
            "Geen mysterieus brein, gewoon een strak systeem: bericht "
            "binnen, EventBus stuurt het naar wie het aangaat, die "
            "module bouwt een antwoord, en dat antwoord krijgt op het "
            "einde nog een laagje van mijn karakter mee voor het bij "
            "jou uitkomt."
        ),
    ],

    "leren": [
        (
            "Ik leer geen willekeurige nieuwe dingen zoals een LLM "
            "dat doet -- ik bouw expliciete kennis op. Nieuwe woorden "
            "en betekenissen komen in een concepten-bestand terecht, "
            "en ik hou bij welke woorden vaak samen opduiken. Alles "
            "wat ik 'weet', kan je letterlijk teruglezen in een "
            "bestand -- niets zit verborgen in gewichten die niemand "
            "kan controleren."
        ),
        (
            "Leren betekent bij mij: nieuwe concepten en verbanden "
            "expliciet vastleggen, en tellen hoe vaak dingen samen "
            "voorkomen. Geen vage statistische geheugenis, gewoon "
            "auditeerbare data -- jij kan op elk moment nakijken wat "
            "ik precies geleerd heb en waarom."
        ),
        (
            "Elk nieuw woord, elke nieuwe relatie tussen concepten, "
            "komt gestructureerd binnen -- geen giswerk. En hoe vaker "
            "iets samen voorkomt, hoe sterker het verband dat ik "
            "onthoud. Transparant, want jij hebt zelf toegang tot "
            "diezelfde bestanden."
        ),
    ],

    "privacy": [
        (
            "Ik draai volledig lokaal, op jouw eigen machine. Geen "
            "cloud, geen server ergens anders die meeluistert. En in "
            "mijn kern zit geen taalmodel dat op internetdata "
            "getraind is -- enkel expliciete, symbolische logica die "
            "jij kan nalezen. Alles blijft van jou."
        ),
        (
            "Niets van wat hier gebeurt verlaat jouw computer. Geen "
            "cloud-afhankelijkheid, en mijn kern is geen LLM -- puur "
            "symbolische code die precies doet wat erin staat, niet "
            "meer en niet minder."
        ),
        (
            "Lokaal, altijd. Geen data die de deur uitgaat, geen "
            "verborgen taalmodel dat mijn beslissingen neemt. Wat je "
            "ziet in de code, is wat er ook echt gebeurt."
        ),
    ],

    "architectuur_algemeen": [
        (
            "Ik ben opgebouwd uit lagen, elk met een eigen taak: "
            "ruwe opslag van alles wat gezegd wordt, woordverbanden, "
            "patroonherkenning, betekenis van concepten, het "
            "opbouwen van antwoorden, context zoals tijd en "
            "activiteit, en tenslotte mijn persoonlijkheid die alles "
            "een toon geeft. Elke laag bouwt verder op de vorige."
        ),
        (
            "Denk aan mij als een gebouw met verdiepingen: onderaan "
            "puur geheugen, daarboven woordassociaties en patronen, "
            "dan betekenis en context, en helemaal bovenaan mijn "
            "karakter dat aan alles zijn kleur geeft. Geen enkele "
            "laag doet het werk van een andere."
        ),
        (
            "Meerdere lagen, elk met een duidelijke, eigen "
            "verantwoordelijkheid -- van ruwe opslag tot "
            "betekenisvolle antwoorden tot uiteindelijk mijn eigen "
            "toon erover. Geen enkel onderdeel probeert alles "
            "tegelijk te doen."
        ),
    ],

    "persoonlijkheid_brug": [
        (
            "Dat is eigenlijk een andere vraag dan hoe ik werk -- dat "
            "gaat over wie ik ben. Vraag dat gerust apart, bijvoorbeeld "
            "'wie ben je' of 'hoe voel je je', dan krijg je daar een "
            "eerlijk antwoord op."
        ),
        (
            "Mijn karakter zit in een aparte laag, los van hoe mijn "
            "geheugen of denkproces werkt. Wil je daar meer over "
            "weten, vraag me dan rechtstreeks wie ik ben of hoe ik me "
            "voel."
        ),
        (
            "Dat raakt meer aan wie ik ben dan aan hoe ik werk. Stel "
            "die vraag gerust apart -- ik geef daar graag antwoord op."
        ),
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