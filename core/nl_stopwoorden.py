# core/nl_stopwoorden.py
"""
Gedeelde Nederlandse stopwoordenlijst (5 oktober 2026).

Woorden die zo vaak voorkomen dat ze niets zeggen over het onderwerp
van een zin: lidwoorden, voorzetsels, voegwoorden, voornaamwoorden,
hulpwerkwoorden, vraagwoorden, groeten, tussenwerpsels, en Nova's eigen
commandowoorden.

Gebruikt door:
  - modules/learning/word_associations_learner.py (Layer 1): welke
    woorden tellen mee voor woordassociaties en get_trending().
  - modules/chat/response_pipeline.py: welke woorden uit een fallback-
    zin NOOIT als "unknown"-concept in concepts.json mogen belanden.

Waarom één gedeelde lijst: voorheen hadden beide modules een eigen
lijst, die uit elkaar groeiden (Layer 1 kreeg op 3 oktober 2026 een
uitgebreide lijst, het auto-learn-filter bleef op ~60 woorden staan en
liet o.a. wat/hoe/over/omdat/hey als concept door).

Bewust NIET in deze lijst: woorden die in Layer 1 wél moeten meetellen
maar als concept rommel zijn (bv. "beter" -- in Layer 1 een beschermd
woord). Die staan enkel in response_pipeline.py's eigen extra lijst.

Pure data, geen klasse, geen init_module(). Bewust in core/: de
dynamische scan van module_loader.py kijkt daar niet.
"""

STOPWOORDEN = frozenset({
    # Lidwoorden
    "de", "het", "een",

    # Voorzetsels
    "in", "op", "van", "voor", "naar", "over", "onder", "boven",
    "tussen", "bij", "met", "zonder", "door", "tegen", "tot",
    "uit", "aan", "om", "sinds", "binnen", "buiten", "langs",
    "rond", "per", "via", "richting", "vanaf", "tijdens",

    # Voegwoorden
    "en", "of", "maar", "want", "dus", "als", "toen", "omdat",
    "doordat", "hoewel", "terwijl", "zodat", "tenzij", "mits",
    "noch", "dan", "nadat", "voordat",

    # Persoonlijke voornaamwoorden
    "ik", "jij", "je", "u", "hij", "zij", "ze", "wij", "we",
    "jullie", "hen", "hun", "mij", "me", "jou", "haar", "hem",

    # Bezittelijke voornaamwoorden
    "mijn", "jouw", "zijn", "ons", "onze", "uw",

    # Aanwijzende / betrekkelijke / vragende voornaamwoorden
    "deze", "dit", "die", "dat", "zulke", "zo'n", "welke", "welk",
    "wat", "wie", "wiens", "waar", "wanneer", "waarom", "hoe",
    "hoeveel", "waarover",

    # Onbepaalde voornaamwoorden
    "iets", "niets", "iemand", "niemand", "alles", "alle",
    "sommige", "elke", "elk", "ieder", "iedere", "geen", "veel",
    "weinig", "meer", "meest", "andere", "ander",

    # Hulpwerkwoorden / koppelwerkwoorden (courante vervoegingen)
    "is", "ben", "bent", "was", "waren", "wordt",
    "worden", "werd", "werden", "heeft", "heb", "hebt", "hebben",
    "had", "hadden", "kan", "kunt", "kunnen", "kon",
    "konden", "zal", "zult", "zullen", "zou", "zouden", "moet",
    "moeten", "moest", "moesten", "mag", "mogen", "mocht",
    "mochten", "wil", "wilt", "willen", "wilde", "wilden",

    # Ontkenning en versterkers
    "niet", "wel", "toch", "juist", "erg", "heel",
    "zeer", "best", "nogal", "vrij", "tamelijk", "echt", "zeker",

    # Overige zeer frequente functiewoorden
    "er", "hier", "daar", "ook", "nog", "al", "nu",
    "even", "gewoon", "eigenlijk", "misschien", "waarschijnlijk",
    "natuurlijk", "trouwens", "namelijk", "bijvoorbeeld", "zo",
    "eens", "graag", "alweer", "meestal", "vaak",

    # Groeten en tussenwerpsels
    "hey", "hoi", "hallo", "goeiedag", "goedemorgen", "goeiemorgen",
    "goedenavond", "oké", "oke", "okay", "pff", "hmm", "nee", "jawel",

    # Nova's eigen commandowoorden (debug-commando's komen nooit tot
    # hier, main.py vangt die op vóór het publiceren -- gewone
    # commando's zoals teach/wiki/onthoud wel)
    "teach", "example", "wiki", "onthoud", "vergeet", "weerleg",
    "verwijder", "definitief", "help", "debug",

    # Engelse stopwoorden (Kevin mengt soms Engelse termen)
    "the", "a", "an", "and", "or", "but", "be", "are",
    "were", "have", "has", "do", "does", "did",
    "would", "could", "should", "will", "shall", "to",
    "at", "for", "with", "as", "by", "this",
})