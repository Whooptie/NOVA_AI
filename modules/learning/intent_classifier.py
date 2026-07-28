# modules/learning/intent_classifier.py
"""
IntentClassifier — ML-specialist naast intent_router.py.

BELANGRIJK (eerlijkheid, zie intent_classifier_roadmap.md):
Dit IS een ML-model (scikit-learn: TF-IDF + Logistic Regression),
géén LLM. Het genereert nooit tekst, het kiest enkel een label uit een
vaste, gesloten lijst categorieën (net zoals microlearning.py's
signal_classifier dat al doet voor Layer 6). Puur symbolisch is dit
probleem niet oplosbaar zonder elke zinsvariant handmatig als patroon
toe te voegen -- zie de roadmap voor de volledige onderbouwing.

Dit bestand is BEWUST een losse, in-memory/bestand-gebaseerde module,
GEEN daemon-achtige klasse. Hertrainen gebeurt enkel wanneer expliciet
retrain() aangeroepen wordt (bv. via een debug-commando of periodieke
achtergrondtaak) -- nooit automatisch bij elke zin.

Volgt dezelfde init_module(event_bus, ...)-conventie als andere Nova-
modules, zodat module_loader.py deze automatisch oppikt.
"""

import json
import os
from pathlib import Path

C_RESET = "\033[0m"
C_CYAN = "\033[96m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"


def dbg(label, text=""):
    print(f"{C_CYAN}[INTENT_CLASSIFIER]{C_RESET} {label} {text}")


class IntentClassifier:
    """
    Klein, begrensd ML-classificatiemodel dat een zin voorspelt naar
    één van een vaste lijst intent-categorieën.

    Bestandslocaties (relatief t.o.v. data_dir, standaard 'data/'):
        training_data.json              -- alle gelabelde voorbeelden
        intent_classifier_model.pkl     -- getraind scikit-learn model
        intent_classifier_vectorizer.pkl -- TF-IDF vectorizer

    Belangrijk: dit model heeft GEEN ingebouwde "ik ken dit niet"-
    status -- het kiest altijd het minst-slechte label uit zijn lijst.
    Het onderscheid tussen "twijfel tussen bekende opties" en "dit is
    waarschijnlijk compleet onbekend" wordt daarom NIET door predict()
    zelf gemaakt, maar hoort symbolisch bovenop gebouwd te worden door
    de aanroeper (intent_router.py), door niet enkel naar confidence
    te kijken maar naar de volledige score-verdeling. predict() geeft
    daarom desgewenst ook alle scores mee terug (all_scores), zodat
    die beslissing elders genomen kan worden.
    """

    def __init__(self, event_bus=None, data_dir="data"):
        self.event_bus = event_bus
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.training_path = self.data_dir / "training_data.json"
        self.model_path = self.data_dir / "intent_classifier_model.pkl"
        self.vectorizer_path = self.data_dir / "intent_classifier_vectorizer.pkl"

        self.model = None
        self.vectorizer = None
        self.voorbeelden = []
        self.metadata = {}

        self._laad_training_data()
        self._laad_of_train_model()

        if event_bus:
            dbg(f"{C_GREEN}geladen — {len(self.voorbeelden)} voorbeelden, "
                f"{len(self._categorieen())} categorieën{C_RESET}")

    # ---------------------------------------------------------
    # Training data laden/opslaan
    # ---------------------------------------------------------
    def _laad_training_data(self):
        if not self.training_path.exists():
            dbg(f"{C_YELLOW}geen training_data.json gevonden op "
                f"{self.training_path} — start leeg{C_RESET}")
            self.voorbeelden = []
            self.metadata = {
                "laatst_getraind": None,
                "aantal_voorbeelden": 0,
                "categorieën": []
            }
            return

        with open(self.training_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.voorbeelden = data.get("voorbeelden", [])
        self.metadata = data.get("metadata", {})

    def _sla_training_data_op(self):
        data = {
            "voorbeelden": self.voorbeelden,
            "metadata": self.metadata
        }
        with open(self.training_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _categorieen(self):
        return sorted(set(v["label"] for v in self.voorbeelden))

    # ---------------------------------------------------------
    # Model laden of trainen
    # ---------------------------------------------------------
    def _laad_of_train_model(self):
        if self.model_path.exists() and self.vectorizer_path.exists():
            try:
                import pickle
                with open(self.model_path, "rb") as f:
                    self.model = pickle.load(f)
                with open(self.vectorizer_path, "rb") as f:
                    self.vectorizer = pickle.load(f)
                dbg(f"{C_GREEN}bestaand model geladen van schijf{C_RESET}")
                return
            except Exception as e:
                dbg(f"{C_RED}kon opgeslagen model niet laden ({e}), "
                    f"train opnieuw{C_RESET}")

        if self.voorbeelden:
            self.retrain()
        else:
            dbg(f"{C_YELLOW}geen trainingsdata — model blijft leeg tot "
                f"retrain() met voorbeelden aangeroepen wordt{C_RESET}")

    def retrain(self):
        """
        Traint het model opnieuw met ALLE huidige voorbeelden in
        self.voorbeelden. Slaat model + vectorizer op naar schijf.

        Retourneert True bij succes, False als er te weinig data is
        (bv. minder dan 2 categorieën, of een categorie met te weinig
        voorbeelden om te splitsen).
        """
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        import pickle

        categorieen = self._categorieen()
        if len(categorieen) < 2:
            dbg(f"{C_RED}te weinig categorieën ({len(categorieen)}) om te "
                f"trainen — minstens 2 nodig{C_RESET}")
            return False

        teksten = [v["tekst"] for v in self.voorbeelden]
        labels = [v["label"] for v in self.voorbeelden]

        self.vectorizer = TfidfVectorizer(lowercase=True, ngram_range=(1, 2))
        X = self.vectorizer.fit_transform(teksten)

        self.model = LogisticRegression(max_iter=1000)
        self.model.fit(X, labels)

        with open(self.model_path, "wb") as f:
            pickle.dump(self.model, f)
        with open(self.vectorizer_path, "wb") as f:
            pickle.dump(self.vectorizer, f)

        from datetime import date
        self.metadata["laatst_getraind"] = str(date.today())
        self.metadata["aantal_voorbeelden"] = len(self.voorbeelden)
        self.metadata["categorieën"] = categorieen
        self._sla_training_data_op()

        dbg(f"{C_GREEN}model getraind op {len(self.voorbeelden)} "
            f"voorbeelden, {len(categorieen)} categorieën{C_RESET}")
        return True

    # ---------------------------------------------------------
    # Voorspellen
    # ---------------------------------------------------------
    def predict(self, tekst):
        """
        Voorspelt de intent-categorie van een nieuwe, onbekende zin.

        Retourneert:
            {
                "label": "chess",
                "confidence": 0.87,
                "all_scores": {"chess": 0.87, "weather": 0.05, ...}
            }
        of None als er nog geen getraind model is.

        LET OP (eerlijkheid): dit model kiest ALTIJD het minst-slechte
        label uit zijn lijst, ook bij een compleet onbekende zin. Het
        heeft geen "ik weet het niet"-antwoord. De aanroeper moet zelf
        beslissen (via confidence + all_scores) of dit resultaat
        vertrouwd wordt -- zie roadmap, sectie "Onbekende/niet-
        passende intents zichtbaar maken".
        """
        if self.model is None or self.vectorizer is None:
            dbg(f"{C_RED}geen getraind model beschikbaar — retrain() eerst "
                f"aanroepen{C_RESET}")
            return None

        X = self.vectorizer.transform([tekst])
        proba = self.model.predict_proba(X)[0]
        klassen = self.model.classes_

        scores = {klasse: round(float(p), 4) for klasse, p in zip(klassen, proba)}
        beste_label = max(scores, key=scores.get)
        beste_score = scores[beste_label]

        return {
            "label": beste_label,
            "confidence": beste_score,
            "all_scores": scores
        }

    # ---------------------------------------------------------
    # Trainingsdata uitbreiden
    # ---------------------------------------------------------
    def add_training_example(self, tekst, label, bron="gecorrigeerd"):
        """
        Voegt een nieuw gelabeld voorbeeld toe aan de trainingsset.
        Traint het model NIET automatisch opnieuw -- retrain() moet
        apart aangeroepen worden (bv. periodiek, of na een batch
        nieuwe correcties). Dit voorkomt dat elke losse correctie
        meteen een (relatief trage) hertraining triggert.
        """
        self.voorbeelden.append({
            "tekst": tekst,
            "label": label,
            "bron": bron
        })
        self._sla_training_data_op()
        dbg(f"{C_GREEN}voorbeeld toegevoegd: '{tekst}' → {label} "
            f"(bron: {bron}){C_RESET}")

    # ---------------------------------------------------------
    # Statistieken
    # ---------------------------------------------------------
    def get_stats(self):
        return {
            "aantal_voorbeelden": len(self.voorbeelden),
            "categorieën": self._categorieen(),
            "laatst_getraind": self.metadata.get("laatst_getraind"),
            "model_geladen": self.model is not None
        }


def init_module(event_bus, semantic_module=None, data_dir="data"):
    """
    LET OP: module_loader.py's dynamische scan (stap 3) roept ELKE
    module aan als init_module(event_bus, sem) -- dus deze functie
    MOET een tweede positioneel argument accepteren, anders vangt de
    loader's TypeError-fallback dit niet op en zou "sem" per ongeluk
    als data_dir doorgegeven worden. We nemen semantic_module hier
    daarom gewoon aan (en negeren 'm, deze module heeft er niets aan)
    net zoals pattern_matcher.py/word_associations_learner.py al
    doen.
    """
    classifier = IntentClassifier(event_bus, data_dir=data_dir)
    event_bus.publish("module_loaded", {"name": "intent_classifier"})
    return classifier