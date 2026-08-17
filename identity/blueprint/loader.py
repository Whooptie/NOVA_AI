# identity/blueprint/loader.py
import json
import os
from jsonschema import validate, ValidationError

# Module-niveau cache (16 augustus 2026): load_identity_blueprint()
# wordt onafhankelijk van elkaar aangeroepen door zowel self_query.py
# (bij import, module-niveau) als personality_engine.py (binnen
# PersonalityEngine.__init__()) -- allebei op zich terecht en
# gedocumenteerd, maar niemand had gemerkt dat ze dezelfde bron dubbel
# inlazen. Gevolg: identity.json werd 2x gelezen/gevalideerd bij elke
# opstart (onnodig dubbel werk, zichtbaar als de dubbele "Identity
# blueprint succesvol geladen"-print), EN self_query.py/
# PersonalityEngine hielden elk hun EIGEN, aparte in-memory kopie bij
# i.p.v. gegarandeerd dezelfde data te zien.
#
# Deze cache lost beide op zonder dat er iets hoeft te veranderen bij
# de aanroepers zelf: de eerste aanroep laadt/valideert/print zoals
# voorheen, elke latere aanroep (ongeacht vanuit welke module) krijgt
# dezelfde, al-geladen dict terug.
_cached_blueprint = None


def load_identity_blueprint():
    """
    Laadt identity.json, valideert het tegen schema.json
    en geeft de blueprint terug als Python-dict.

    Wordt maar 1x echt van schijf gelezen/gevalideerd per proces (zie
    de module-niveau cache hierboven) -- identity.json verandert
    praktisch nooit tijdens een sessie, dus latere aanroepen hergebruiken
    gewoon dezelfde, al-gevalideerde dict.
    """
    global _cached_blueprint

    if _cached_blueprint is not None:
        return _cached_blueprint

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

    _cached_blueprint = identity
    return _cached_blueprint
