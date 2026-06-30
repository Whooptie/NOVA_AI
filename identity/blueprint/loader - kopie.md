# identity/blueprint/loader.py
import json
import os
from jsonschema import validate, ValidationError

def load_identity_blueprint():
    """
    Laadt identity.json, valideert het tegen schema.json
    en geeft de blueprint terug als Python-dict.
    """

    base = os.path.dirname(__file__)
    identity_path = os.path.join(base, "identity.json")
    schema_path = os.path.join(base, "schema.json")

    # 1. Identity inladen
    with open(identity_path, "r", encoding="utf-8") as f:
        identity = json.load(f)

    # 2. Schema inladen
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    # 3. Validatie
    try:
        validate(instance=identity, schema=schema)
    except ValidationError as e:
        raise ValueError(
            f"❌ Identity blueprint is ongeldig!\n"
            f"Fout: {e.message}\n"
            f"Locatie: {'/'.join(str(x) for x in e.path)}"
        )

    # 4. Alles oké
    print("✅ Identity blueprint succesvol geladen en gevalideerd.")
    return identity
