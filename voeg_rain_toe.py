# voeg_rain_toe.py
"""
Eenmalig script: voegt de categorie "rain" toe aan data/training_data.json.

Wat het doet:
1. Zet 6 regenzinnen die nu onder "weather" staan om naar "rain"
   (anders spreken de voorbeelden elkaar tegen).
2. Voegt nieuwe regen-, sneeuw- en onweervoorbeelden toe, plus een paar
   algemene weervoorbeelden om het evenwicht te bewaren.
3. Past de metadata (aantal + categorieën) aan.

Veilig om meerdere keren te draaien: wat er al staat wordt overgeslagen.
Er wordt eerst een reservekopie gemaakt (training_data.json.voor_rain).

Gebruik (vanuit de projectmap):
    python voeg_rain_toe.py
"""

import json
import shutil
import sys
from pathlib import Path

PAD = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data") / "training_data.json"

# Deze zinnen staan nu onder "weather" maar zijn regenvragen.
VERHUIZEN = [
    "gaat het regenen vandaag",
    "moet ik een paraplu meenemen",
    "gaat het vandaag regenen of niet",
    "is het buiten aan het regenen",
    "wordt het nog droog vandaag",
    "zou ik een paraplu nodig hebben",
]

NIEUW = [
    # regen: begint het?
    "gaat het straks regenen",
    "komt er regen aan",
    "gaat het nog regenen vandaag",
    "regent het al",
    "is het aan het regenen",
    "komt er een bui aan",
    "krijgen we nog regen",
    "valt er regen op komst",
    "is er regen op komst",
    "gaat het hard regenen",
    "zal het regenen vanavond",
    "komen er buien aan",
    "ga ik nat worden onderweg",
    "word ik nat als ik nu buiten ga",
    # paraplu / regenjas
    "heb ik een paraplu nodig",
    "heb ik een regenjas nodig",
    "moet ik mijn regenjas aandoen",
    "is een paraplu nodig vandaag",
    "kan ik zonder paraplu weg",
    # stopt het?
    "wanneer stopt de regen",
    "wanneer houdt het op met regenen",
    "hoe lang blijft het nog regenen",
    "wanneer is de bui voorbij",
    "stopt het snel met regenen",
    "hoe lang duurt de regen nog",
    "klaart het snel op",
    "wanneer wordt het weer droog",
    "blijft het droog vanavond",
    # sneeuw
    "gaat het sneeuwen",
    "komt er sneeuw aan",
    "sneeuwt het al",
    "wanneer stopt de sneeuw",
    # onweer
    "gaat het onweren",
    "komt er onweer aan",
    "is er onweer op komst",
    "wanneer stopt het onweer",
]

# Extra algemene weervoorbeelden, om het evenwicht te bewaren: "rain" heeft nu
# veel voorbeelden en "weather" anders te weinig.
WEER_BIJ = [
    "is het mooi weer buiten",
    "hoe warm is het nu",
    "hoeveel graden is het vandaag",
    "is het zonnig vandaag",
    "moet ik een jas aan vandaag",
    "wordt het warm dit weekend",
    "hoe koud wordt het vannacht",
    "is het fris buiten",
    "wat voor weer wordt het morgen",
    "is het droog en zonnig",
]


def sleutel(v):
    return (v["tekst"].strip().lower(), v["label"])


def main():
    if not PAD.exists():
        print(f"Bestand niet gevonden: {PAD}")
        return 1

    with open(PAD, "r", encoding="utf-8") as f:
        data = json.load(f)
    voorbeelden = data["voorbeelden"]

    reserve = PAD.with_name(PAD.name + ".voor_rain")
    if not reserve.exists():
        shutil.copyfile(PAD, reserve)
        print(f"Reservekopie gemaakt: {reserve}")

    verhuisd = 0
    for v in voorbeelden:
        if v["label"] == "weather" and v["tekst"].strip().lower() in VERHUIZEN:
            v["label"] = "rain"
            verhuisd += 1

    bestaand = {sleutel(v) for v in voorbeelden}
    toegevoegd = 0
    for tekst in NIEUW:
        if (tekst.lower(), "rain") in bestaand:
            continue
        voorbeelden.append({"tekst": tekst, "label": "rain", "bron": "handmatig"})
        toegevoegd += 1

    for tekst in WEER_BIJ:
        if (tekst.lower(), "weather") in bestaand:
            continue
        voorbeelden.append({"tekst": tekst, "label": "weather", "bron": "handmatig"})
        toegevoegd += 1

    meta = data.setdefault("metadata", {})
    meta["aantal_voorbeelden"] = len(voorbeelden)
    meta["categorieën"] = sorted({v["label"] for v in voorbeelden})

    with open(PAD, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Verhuisd van weather naar rain: {verhuisd}")
    print(f"Nieuw toegevoegd: {toegevoegd}")
    print(f"Totaal nu: {len(voorbeelden)} voorbeelden")
    print(f"Categorieën: {', '.join(meta['categorieën'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())