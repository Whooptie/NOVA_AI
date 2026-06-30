import json

FILE = "data/concepts.json"

def test():
    with open(FILE, "r", encoding="utf-8") as f:
        concepts = json.load(f)

    # Check of 'moeder' nu netjes een sense heeft
    if "moeder" in concepts:
        moeder = concepts["moeder"]
        if "senses" in moeder and len(moeder["senses"]) > 0:
            print("✅ Migratie geslaagd voor 'moeder'")
            for s in moeder["senses"]:
                print(f" - {s['sense_id']}: {s['definition']}")
        else:
            print("❌ 'moeder' heeft geen senses, migratie mislukt")
    else:
        print("⚠️ 'moeder' niet gevonden in concepts.json")

if __name__ == "__main__":
    test()
