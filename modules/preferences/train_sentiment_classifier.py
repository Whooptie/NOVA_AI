# modules/preferences/train_sentiment_classifier.py
"""
User Preferences: traint het sentiment-nuance-classificatiemodel.

Zelfde patroon en veiligheidsrem als identity/personality/train_
classifier.py (Layer 6, Fase 6) -- bewust hergebruikt i.p.v. iets
nieuws verzonnen, zodat Kevin dit al herkent uit dat systeem.

Kan op TWEE manieren aangeroepen worden:
1. Handmatig: `python train_sentiment_classifier.py` (Kevin roept dit
   zelf aan na het aanvullen van sentiment_training_data.json)
2. Automatisch: aangeroepen door sentiment_classifier.py's
   check_en_hertrain() zodra er genoeg nieuwe twijfelgevallen
   verzameld zijn in sentiment_uncertain.jsonl.

BELANGRIJK -- de veiligheidsrem tegen drift: dit script overschrijft
NOOIT zomaar het actieve model. Een nieuw getraind model wordt eerst
getoetst tegen sentiment_benchmark_data.json (het vaste ijkpunt-
testsetje). Het nieuwe model wordt alleen actief als het daar
minstens even goed scoort als het huidige model. Zo niet: het nieuwe
model wordt WEL opgeslagen (als "kandidaat", voor eventuele latere
handmatige inspectie door Kevin), maar het huidige, actieve model
blijft in gebruik.

Bounded ML-tool, geen brein: dit model classificeert enkel EEN
sentiment-nuance-categorie per zin (positief/neutraal_gemengd/
negatief). Alle beslissingslogica over WAT er met die categorie
gebeurt (opslag, conflictregel expliciet/automatisch, antwoord-
formulering) zit volledig in kevin_profile.py/intent_router.py --
puur symbolisch, dit script en zijn model bemoeien zich daar niet mee.
"""

import json
import os
import pickle
from datetime import datetime

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score


BASE = os.path.dirname(__file__)
TRAINING_PAD = os.path.join(BASE, "sentiment_training_data.json")
BENCHMARK_PAD = os.path.join(BASE, "sentiment_benchmark_data.json")
UNCERTAIN_PAD = os.path.join(BASE, "sentiment_uncertain.jsonl")
MODEL_ACTIEF_PAD = os.path.join(BASE, "sentiment_model.pkl")
MODEL_KANDIDAAT_PAD = os.path.join(BASE, "sentiment_model_kandidaat.pkl")
TRAINING_LOG_PAD = os.path.join(BASE, "sentiment_training_log.jsonl")


def _laad_json(pad, fallback=None):
    if not os.path.exists(pad):
        return fallback
    with open(pad, "r", encoding="utf-8") as f:
        return json.load(f)


def _laad_uncertain_voorbeelden():
    """
    Leest sentiment_uncertain.jsonl (twijfelgevallen die sentiment_
    classifier.py tijdens normaal gebruik verzameld heeft). Geeft een
    lege lijst terug als het bestand nog niet bestaat -- heel normaal
    bij de allereerste training.
    """
    if not os.path.exists(UNCERTAIN_PAD):
        return []

    voorbeelden = []
    with open(UNCERTAIN_PAD, "r", encoding="utf-8") as f:
        for regel in f:
            regel = regel.strip()
            if not regel:
                continue
            try:
                item = json.loads(regel)
                if "text" in item and "categorie" in item:
                    voorbeelden.append(item)
            except json.JSONDecodeError:
                continue
    return voorbeelden


def train_model(gebruik_uncertain=True):
    """
    Traint een nieuw model op sentiment_training_data.json (+
    optioneel de verzamelde sentiment_uncertain.jsonl), toetst het
    tegen sentiment_benchmark_data.json, en beslist of het de actieve
    versie wordt.

    Geeft een dictionary terug met het resultaat -- handig zowel voor
    het handmatige gebruik (print een duidelijk verslag) als voor het
    automatische gebruik vanuit sentiment_classifier.py (kan dit
    resultaat gebruiken om te beslissen of Kevin een melding moet
    krijgen).
    """
    training_data = _laad_json(TRAINING_PAD)
    benchmark_data = _laad_json(BENCHMARK_PAD)

    if not training_data or not benchmark_data:
        return {
            "succes": False,
            "reden": "sentiment_training_data.json of sentiment_benchmark_data.json ontbreekt of is leeg.",
        }

    voorbeelden = list(training_data.get("voorbeelden", []))

    aantal_extra = 0
    if gebruik_uncertain:
        extra = _laad_uncertain_voorbeelden()
        voorbeelden.extend(extra)
        aantal_extra = len(extra)

    if len(voorbeelden) < 10:
        return {
            "succes": False,
            "reden": f"Te weinig trainingsvoorbeelden ({len(voorbeelden)}) om zinvol te trainen.",
        }

    teksten = [v["text"] for v in voorbeelden]
    labels = [v["categorie"] for v in voorbeelden]

    # Klein, bounded model -- TF-IDF + Logistic Regression, exact
    # dezelfde aanpak als identity/personality/train_classifier.py.
    # Geen diep netwerk, geen taalmodel -- een simpele, verklaarbare
    # classifier.
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
        ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
    ])
    pipeline.fit(teksten, labels)

    # ---------------------------------------------------------
    # Toetsen tegen het vaste ijkpunt
    # ---------------------------------------------------------
    benchmark_voorbeelden = benchmark_data.get("voorbeelden", [])
    benchmark_teksten = [v["text"] for v in benchmark_voorbeelden]
    benchmark_labels = [v["categorie"] for v in benchmark_voorbeelden]

    voorspellingen = pipeline.predict(benchmark_teksten)
    nieuwe_score = accuracy_score(benchmark_labels, voorspellingen)

    huidige_score = _evalueer_huidig_model(benchmark_teksten, benchmark_labels)

    # Kandidaat ALTIJD opslaan, ongeacht of hij goed genoeg is -- zodat
    # Kevin desgewenst zelf kan inspecteren wat er getraind werd.
    with open(MODEL_KANDIDAAT_PAD, "wb") as f:
        pickle.dump(pipeline, f)

    # Bugfix (overgenomen uit train_classifier.py): bij de ALLEREERSTE
    # training bestaat er nog geen actief model, dus huidige_score is
    # None -- er is dan niets om mee te vergelijken, dus de nieuwe
    # versie wordt sowieso actief.
    if huidige_score is None:
        wordt_actief = True
    else:
        wordt_actief = nieuwe_score >= huidige_score

    if wordt_actief:
        with open(MODEL_ACTIEF_PAD, "wb") as f:
            pickle.dump(pipeline, f)

    resultaat = {
        "succes": True,
        "aantal_training_voorbeelden": len(voorbeelden),
        "aantal_extra_uit_uncertain": aantal_extra,
        "nieuwe_score": round(nieuwe_score, 4),
        "huidige_score": round(huidige_score, 4) if huidige_score is not None else None,
        "wordt_actief": wordt_actief,
        "tijdstip": datetime.now().isoformat(),
    }

    _log_training(resultaat)
    return resultaat


def _evalueer_huidig_model(benchmark_teksten, benchmark_labels):
    """
    Geeft de accuracy van het HUIDIGE, actieve model terug op het
    ijkpunt-testsetje -- nodig om te vergelijken met de nieuwe
    kandidaat. Geeft None terug als er nog geen actief model bestaat
    (allereerste training ooit) -- dan wordt de nieuwe versie sowieso
    actief, want er is niets om mee te vergelijken.
    """
    if not os.path.exists(MODEL_ACTIEF_PAD):
        return None

    with open(MODEL_ACTIEF_PAD, "rb") as f:
        huidig_model = pickle.load(f)

    voorspellingen = huidig_model.predict(benchmark_teksten)
    return accuracy_score(benchmark_labels, voorspellingen)


def _log_training(resultaat: dict):
    """
    Append-only log van elke trainingspoging -- zodat Kevin desgewenst
    kan teruglezen hoe het model zich over tijd ontwikkelde, zelfde
    principe als train_classifier.py's training_log.jsonl.
    """
    with open(TRAINING_LOG_PAD, "a", encoding="utf-8") as f:
        f.write(json.dumps(resultaat, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    print("Training van het sentiment-nuance-classificatiemodel gestart...")
    resultaat = train_model()

    if not resultaat["succes"]:
        print(f"❌ Training mislukt: {resultaat['reden']}")
    else:
        print(f"✅ Training voltooid.")
        print(f"   Trainingsvoorbeelden: {resultaat['aantal_training_voorbeelden']} "
              f"(waarvan {resultaat['aantal_extra_uit_uncertain']} uit eerder verzamelde twijfelgevallen)")
        print(f"   Score nieuwe versie op ijkpunt: {resultaat['nieuwe_score']}")
        if resultaat["huidige_score"] is not None:
            print(f"   Score huidige actieve versie: {resultaat['huidige_score']}")
        else:
            print(f"   Geen eerder actief model -- dit wordt de allereerste versie.")

        if resultaat["wordt_actief"]:
            print("   → Nieuwe versie is minstens even goed: WORDT ACTIEF.")
        else:
            print("   → Nieuwe versie scoort slechter: NIET actief geworden, "
                  "huidige versie blijft in gebruik. Kandidaat wel opgeslagen "
                  "als sentiment_model_kandidaat.pkl voor eventuele inspectie.")
