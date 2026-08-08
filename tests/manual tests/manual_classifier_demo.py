from modules.learning.intent_classifier import IntentClassifier

clf = IntentClassifier(event_bus=None, data_dir="data")

# Belangrijk: forceer een hertraining zodra training_data.json nieuwe
# voorbeelden bevat. __init__ laadt anders gewoon het oude opgeslagen
# model van schijf (intent_classifier_model.pkl), dat nog niets weet
# van de net toegevoegde/verwijderde zinnen.
clf.retrain()

print(clf.get_stats())
print()

# Vaste testzinnen per verwachte categorie, zodat we niet elke keer
# handmatig hoeven te typen. "verwacht" is puur ter referentie in de
# print -- de classifier gebruikt dit niet, het is enkel om zelf snel
# te kunnen zien of het klopt.
testzinnen = [
    ("laten we verder schaken", "chess"),
    ("zin om te gaan schaken", "chess"),
    ("speel je een potje mee", "chess"),
    ("wil je nog schaken", "chess"),

    ("moet ik een paraplu meenemen", "weather"),
    ("is het lekker weer buiten", "weather"),
    ("wordt het nog warm vandaag", "weather"),

    ("heb je de tijd voor me", "time"),
    ("hoe laat zou het nu zijn", "time"),

    ("ik ga zo aan het programmeren", "activity"),
    ("ik ben aan het gamen nu", "activity"),
    ("tijd om te gaan douchen", "activity"),

    ("ik ben echt weg van pizza", "preference"),
    ("koffie drink ik heel graag", "preference"),
    ("ik heb een hekel aan lawaai", "preference"),

    ("werk je met een taalmodel", "self_architecture"),
    ("hoe zit jouw brein in elkaar", "self_architecture"),

    ("wat voor iemand ben jij", "identity"),
    ("waar geniet je van", "identity"),

    ("tel 15 en 27 op", "math"),
    ("wat is de wortel van 81", "math"),

    ("kan je mijn planten water geven", "onbekend / geen goede match"),
    ("hoe laat begint de film vanavond", "dubbelzinnig (time?)"),
]

print("=== Testresultaten ===\n")
for zin, verwacht in testzinnen:
    r = clf.predict(zin)
    top3 = sorted(r["all_scores"].items(), key=lambda x: -x[1])[:3]
    goed = "OK" if r["label"] == verwacht else "?"
    print(f"[{goed}] '{zin}'  (verwacht: {verwacht})")
    print(f"      -> {r['label']} (confidence: {r['confidence']})")
    print(f"      top3: {top3}")
    print()

print("\nKlaar. Typ hieronder gerust nog eigen losse zinnen, of Ctrl+C om te stoppen.\n")

while True:
    zin = input("Test zin (of 'stop'): ")
    if zin == "stop":
        break
    resultaat = clf.predict(zin)
    print(f"-> {resultaat['label']} (confidence: {resultaat['confidence']})")
    top3 = sorted(resultaat["all_scores"].items(), key=lambda x: -x[1])[:3]
    print(f"  top 3: {top3}")