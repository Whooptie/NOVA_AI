import json
from datetime import datetime

OLD_FILE = "data/concepts.json"
NEW_FILE = "data/concepts.json"

def migrate():
    with open(OLD_FILE, "r", encoding="utf-8") as f:
        old_concepts = json.load(f)

    new_concepts = {}
    for word, meaning in old_concepts.items():
        # Als het nog een string is → omzetten naar nieuw formaat
        if isinstance(meaning, str):
            new_concepts[word] = {
                "senses": [
                    {
                        "sense_id": f"{word}#1",
                        "definition": meaning,
                        "relations": [],
                        "examples": []
                    }
                ],
                "audit_log": [
                    {
                        "timestamp": datetime.utcnow().isoformat(),
                        "status": "migrated",
                        "by": "migration_script"
                    }
                ]
            }
        else:
            # Als het al in nieuw formaat zit → gewoon meenemen
            new_concepts[word] = meaning

    with open(NEW_FILE, "w", encoding="utf-8") as f:
        json.dump(new_concepts, f, indent=2, ensure_ascii=False)

    print(f"Migratie voltooid. Bestand opgeslagen naar {NEW_FILE}")

if __name__ == "__main__":
    migrate()
