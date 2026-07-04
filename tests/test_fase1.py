# test_fase1.py
"""
Los testscript voor Fase 1 van Layer 1 (Word Associations Learner).

Dit bestand test ENKEL de preprocessing-pijplijn (tokenize, stopwoorden
filteren, lemmatizen). Er wordt nog niets geleerd of opgeslagen.

Hoe te gebruiken:
1. Zet dit bestand in dezelfde map als word_associations_learner.py
   (of pas de import hieronder aan naar het juiste pad).
2. Run: python test_fase1.py
3. Bekijk de output in je terminal.
"""

from modules.learning.word_associations_learner import WordAssociationsLearner


def test(zin, verwacht_commentaar=""):
    print(f"\nInput:  {zin!r}")
    result = leerder.preprocess(zin)
    print(f"Output: {result}")
    if verwacht_commentaar:
        print(f"       ({verwacht_commentaar})")


if __name__ == "__main__":
    # We geven geen event_bus mee (None), want in Fase 1 hebben we die
    # nog niet nodig.
    leerder = WordAssociationsLearner(event_bus=None)

    print("=" * 60)
    print("FASE 1 TEST — Word Associations Learner")
    print("=" * 60)

    test(
        "Python is mijn favoriet",
        "verwacht: ['python', 'favoriet'] (stopwoorden 'is'/'mijn' weg)"
    )

    test(
        "Ik hou van snelle talen",
        "verwacht: iets als ['hou', 'snel', 'taal'] "
        "('ik'/'van' weg, 'snelle'->'snel', 'talen'->'taal')"
    )

    test(
        "Java is traag en dat is jammer",
        "verwacht: ['java', 'traag', 'jammer'] "
        "(stopwoorden 'is', 'en', 'dat' weg)"
    )

    test(
        "Dat kopje koffie was echt lekker!",
        "verwacht: iets als ['kop', 'koffie', 'lekker'] "
        "('kopje'->'kop' via verkleinwoord-regel)"
    )

    test(
        "De auto's van de buren staan er weer",
        "verwacht: ['auto', 'buren'] of gelijkaardig "
        "(let op: 'buren' is geen simpel meervoud op -en van 'buur', "
        "dit toont de beperking van de simpele lemmatizer)"
    )

    print("\n" + "=" * 60)
    print("Klaar. Controleer of de output logisch aanvoelt.")
    print("=" * 60)
