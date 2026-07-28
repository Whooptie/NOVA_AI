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
        # Fase 5 (periodieke hertraining, 28 juli 2026): pad naar de
        # correcties die intent_router.py's _log_gecorrigeerd_
        # voorbeeld() wegschrijft. Los bestand, wordt NIET aangepast
        # door deze module -- enkel gelezen bij
        # retrain_vanuit_bestanden().
        self.gecorrigeerd_path = self.data_dir / "gecorrigeerde_voorbeelden.jsonl"

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

    def _laad_gecorrigeerde_voorbeelden(self):
        """
        Leest data/gecorrigeerde_voorbeelden.jsonl in (indien
        aanwezig) -- de MET ZEKERHEID juist gelabelde correcties die
        intent_router.py's "nee ik bedoelde X"-mechanisme daar
        wegschrijft (Fase 4). Bewust ENKEL lezen, dit bestand wordt
        hier nooit aangepast of leeggemaakt (Kevin's keuze, 28 juli
        2026: het mag gewoon blijven groeien, dubbels bij een volgende
        hertraining zijn onschadelijk).

        Geeft een lijst terug in hetzelfde formaat als
        self.voorbeelden (elk item heeft minstens "tekst" en "label"),
        of een lege lijst als het bestand nog niet bestaat of leeg is.
        """
        if not self.gecorrigeerd_path.exists():
            return []

        voorbeelden = []
        try:
            with open(self.gecorrigeerd_path, "r", encoding="utf-8") as f:
                for regel in f:
                    regel = regel.strip()
                    if not regel:
                        continue
                    item = json.loads(regel)
                    voorbeelden.append({
                        "tekst": item["tekst"],
                        "label": item["label"],
                        "bron": item.get("bron", "gecorrigeerd")
                    })
        except (OSError, json.JSONDecodeError, KeyError) as e:
            dbg(f"{C_RED}kon gecorrigeerde_voorbeelden.jsonl niet volledig "
                f"lezen: {e}{C_RESET}")

        return voorbeelden

    def retrain_vanuit_bestanden(self):
        """
        Fase 5+6 (periodieke hertraining, 28 juli 2026): wordt
        periodiek aangeroepen door main.py's achtergrond_loop() (elke
        4 uur, Kevin's keuze). Combineert DRIE bronnen:
          1. training_data.json (Kevin's eigen, handmatig beheerde
             basisset)
          2. data/gecorrigeerde_voorbeelden.jsonl (Fase 4's bevestigde
             "nee ik bedoelde X"-correcties)
          3. Layer 0 / memory.py (Fase 6: berichten die een bestaande,
             betrouwbare detect_*() al zelf correct herkende -- ZONDER
             classifier-gokken, zie _haal_layer0_voorbeelden_op())
        en traint daarop.

        BELANGRIJK: dit schrijft GEEN van de twee aanvullende bronnen
        terug naar training_data.json zelf -- dat bestand blijft
        Kevin's eigen, schone basisset. De combinatie gebeurt enkel
        TIJDELIJK, in het geheugen, vlak vóór het trainen. Na afloop
        staat self.voorbeelden weer op enkel de training_data.json
        -inhoud (retrain() hieronder schrijft immers self.voorbeelden
        terug naar schijf via _sla_training_data_op() -- vandaar dat
        we hier bewust een LOKALE kopie combineren i.p.v.
        self.voorbeelden zelf uit te breiden).
        """
        gecorrigeerd = self._laad_gecorrigeerde_voorbeelden()
        layer0 = self._haal_layer0_voorbeelden_op()
        aanvullend = gecorrigeerd + layer0

        # Layer 0-scan-tijdstip bijwerken, OOK als er niets nieuws
        # gevonden werd -- anders zou een lege scan de volgende keer
        # gewoon dezelfde (nog altijd niets-nieuws) periode herhalen.
        # Dit gebeurt HIER (voor het eventuele vroege return hieronder)
        # zodat het altijd bijgewerkt wordt, ongeacht of retrain() zelf
        # slaagt.
        import time as _time
        self.metadata["laatste_layer0_scan"] = _time.time()

        if not aanvullend:
            dbg(f"{C_CYAN}geen aanvullende voorbeelden gevonden, "
                f"hertrain gewoon op de basisset{C_RESET}")
            self._sla_training_data_op()
            return self.retrain()

        # Combineer LOKAAL (niet self.voorbeelden zelf aanpassen) --
        # zie docstring hierboven waarom dat belangrijk is.
        oorspronkelijke_voorbeelden = self.voorbeelden
        try:
            self.voorbeelden = oorspronkelijke_voorbeelden + aanvullend
            dbg(f"{C_CYAN}hertraining met {len(oorspronkelijke_voorbeelden)} "
                f"basisvoorbeelden + {len(gecorrigeerd)} gecorrigeerde + "
                f"{len(layer0)} Layer 0-voorbeelden{C_RESET}")
            gelukt = self.retrain()
        finally:
            # ALTIJD terugzetten naar de schone basisset, ongeacht of
            # retrain() slaagde of niet -- self.voorbeelden mag nooit
            # blijvend de aanvullende voorbeelden bevatten (die horen
            # niet thuis in training_data.json zelf).
            self.voorbeelden = oorspronkelijke_voorbeelden
            # metadata/training_data.json opnieuw correct wegschrijven
            # met de schone set, want retrain() heeft hierboven net de
            # GECOMBINEERDE set naar schijf geschreven via
            # _sla_training_data_op().
            self.metadata["aantal_voorbeelden"] = len(self.voorbeelden)
            self.metadata["categorieën"] = self._categorieen()
            self._sla_training_data_op()

        return gelukt

    # ---------------------------------------------------------
    # Fase 6 (28 juli 2026): leren uit Layer 0 (memory.py)
    # ---------------------------------------------------------

    # Hoeveel recente events (van elk type) maximaal ophalen per scan.
    # Ruim genoeg voor een 4-uur-interval bij normaal chatgebruik,
    # zonder de hele geschiedenis te moeten doorzoeken (zie
    # retrain_vanuit_bestanden()'s docstring "optie 1 vs 2"-afweging,
    # 28 juli 2026: bewust de eenvoudige, bestaande query()-API
    # gebruiken i.p.v. memory.py zelf uit te breiden).
    LAYER0_QUERY_LIMIT = 500

    def _haal_layer0_voorbeelden_op(self):
        """
        Doorzoekt Layer 0 (memory.py) op berichten die door een
        BESTAANDE, betrouwbare detect_*()-match werden afgehandeld
        (topic_detected:<naam> met bron="detect" -- zie
        intent_router.py's _emit_topic()). Classifier-eigen gokken
        (bron="classifier") worden BEWUST NOOIT meegenomen -- Kevin's
        keuze, 28 juli 2026: dat zou een zelfbevestigend leerrisico
        zijn (de classifier zou haar eigen, mogelijk foute gokken als
        nieuwe "waarheid" gaan hertrainen).

        KOPPELING IS VOLGORDE-GEBASEERD, NIET TIJD-GEBASEERD (herzien
        28 juli 2026, na een praktijktest waarbij de achtergrondthread
        -- vermoedelijk de webcam-gebonden presence-check -- de
        hoofdthread tijdelijk vertraagde via Python's GIL, waardoor er
        ruim 2 seconden tussen een bericht en zijn eigen topic_detected
        -event zat). Een vaste tijdsmarge zou daardoor ofwel voorbeelden
        missen (marge te krap) ofwel bij toekomstige, nog zwaardere
        achtergrondtaken een VERKEERD bericht kunnen koppelen (marge te
        ruim).

        In plaats daarvan: een chronologische tijdlijn van ALLE
        raw_user_message- en topic_detected-events samen. Een bericht
        wordt ENKEL gekoppeld als het ALLEREERSTVOLGENDE event in die
        tijdlijn precies zijn eigen topic_detected-event is -- zonder
        dat er nog een ANDER raw_user_message tussenin kwam. Komen er
        2+ berichten na elkaar voor er een topic-event verschijnt, dan
        wordt GEEN van die berichten gekoppeld (Kevin's keuze, 28 juli
        2026: liever een voorbeeld missen dan het aan het verkeerde
        bericht toeschrijven). Dit werkt correct ongeacht hoeveel tijd
        er tussen bericht en topic-event verstrijkt.

        Onthoudt zelf tot waar al gescand is (self.metadata
        ["laatste_layer0_scan"]) zodat dezelfde oude berichten niet
        bij elke hertraining opnieuw meegeteld worden.

        Geeft een lijst terug in hetzelfde formaat als
        self.voorbeelden, of een lege lijst als memory niet beschikbaar
        is of er niets nieuws gevonden werd.
        """
        if not self.event_bus:
            return []

        memory = self.event_bus.modules.get("memory")
        if memory is None:
            dbg(f"{C_YELLOW}geen memory-module beschikbaar, sla Layer 0 "
                f"over{C_RESET}")
            return []

        laatste_scan = self.metadata.get("laatste_layer0_scan", 0) or 0

        # We kunnen query()'s event_type-filter niet gebruiken (dat is
        # een exacte match, geen prefix/wildcard), dus halen we een
        # ruime, ongefilterde set recente events op en filteren zelf
        # in Python op event_type-prefix + timestamp.
        alle_recente = memory.query({
            "sort": "recent_first",
            "limit": self.LAYER0_QUERY_LIMIT
        })

        raw_messages = []
        topic_events = []
        for row in alle_recente:
            etype = row.get("event_type", "")
            ts = row.get("timestamp", 0)
            if ts <= laatste_scan:
                continue
            if etype == "raw_user_message":
                raw_messages.append(row)
            elif etype.startswith("topic_detected:"):
                topic_events.append(row)

        if not topic_events:
            dbg(f"{C_CYAN}geen nieuwe topic_detected-events sinds laatste "
                f"Layer 0-scan{C_RESET}")
            return []

        # Gezamenlijke, chronologische tijdlijn van ALLE relevante
        # events (berichten + topic-events door elkaar) -- nodig om
        # per bericht te kunnen zeggen "wat was het ALLEREERSTE dat
        # hierna gebeurde". Enkel als dat het bijhorende topic-event
        # is (en niet een ander raw_user_message), is de koppeling
        # zeker genoeg.
        tijdlijn = sorted(
            raw_messages + topic_events,
            key=lambda r: r["timestamp"]
        )

        nieuwe_voorbeelden = []
        for i, row in enumerate(tijdlijn):
            if row["event_type"] != "raw_user_message":
                continue

            # Als het VORIGE event in de tijdlijn ook al een
            # raw_user_message was, dan behoorde DIT bericht zelf al
            # tot een "2+ berichten na elkaar"-groep -- Kevin's keuze
            # (28 juli 2026): GEEN van de berichten in zo'n groep is
            # betrouwbaar te koppelen, dus ook dit bericht niet, ook al
            # zou het eerstvolgende event toevallig wel een geldig
            # topic-event zijn.
            if i > 0 and tijdlijn[i - 1]["event_type"] == "raw_user_message":
                continue

            # Zoek het EERSTVOLGENDE event in de tijdlijn na dit bericht.
            if i + 1 >= len(tijdlijn):
                # Dit was het allerlaatste event -- nog geen opvolger
                # bekend, kan dus nog niets betrouwbaars zeggen.
                continue
            volgende = tijdlijn[i + 1]

            if volgende["event_type"] == "raw_user_message":
                # Er kwam een ANDER bericht vóór er ooit een topic
                # -event verscheen -- niet zeker of hier ooit een
                # detect_*() matchte, en zo ja voor welk van de twee
                # berichten. Kevin's keuze (28 juli 2026): het HELE
                # eerste bericht verwerpen i.p.v. gokken.
                continue

            if not volgende["event_type"].startswith("topic_detected:"):
                continue

            try:
                topic_data = json.loads(volgende["data"])
            except (json.JSONDecodeError, KeyError):
                continue

            if topic_data.get("bron") != "detect":
                # Classifier-gok -- bewust NIET vertrouwen, zie
                # docstring hierboven.
                continue

            label = volgende["event_type"].split(":", 1)[1]

            try:
                msg_data = json.loads(row["data"])
                tekst = msg_data.get("text", "").strip()
            except (json.JSONDecodeError, KeyError):
                continue

            if not tekst:
                continue

            nieuwe_voorbeelden.append({
                "tekst": tekst,
                "label": label,
                "bron": "layer0"
            })

        dbg(f"{C_GREEN}{len(nieuwe_voorbeelden)} nieuwe voorbeelden "
            f"gevonden via Layer 0{C_RESET}")

        # Debug-logbestand (Kevin's keuze, 28 juli 2026): elk Layer 0
        # -voorbeeld dat effectief gevonden werd, ook wegschrijven naar
        # een los, leesbaar bestand -- puur zodat je achteraf kan
        # nakijken wat er precies uit interactions.jsonl gehaald werd,
        # zonder daar zelf in te moeten zoeken. Dit bestand wordt NOOIT
        # ingelezen door Nova zelf (in tegenstelling tot training_data
        # .json/gecorrigeerde_voorbeelden.jsonl) -- puur ter inzage.
        self._log_layer0_gebruikt(nieuwe_voorbeelden)

        return nieuwe_voorbeelden

    def _log_layer0_gebruikt(self, voorbeelden):
        """
        Schrijft elk Layer 0-voorbeeld dat net gevonden werd weg naar
        data/layer0_gebruikt.jsonl -- puur ter inzage/debug voor Kevin,
        wordt door Nova zelf nooit terug ingelezen. Doet niets als de
        lijst leeg is (geen lege regel/ruis in het bestand).
        """
        if not voorbeelden:
            return

        import json
        import os
        from datetime import datetime

        pad = os.path.join("data", "layer0_gebruikt.jsonl")
        tijdstip = datetime.now().isoformat()
        try:
            os.makedirs("data", exist_ok=True)
            with open(pad, "a", encoding="utf-8") as f:
                for v in voorbeelden:
                    regel = {
                        "tekst": v["tekst"],
                        "label": v["label"],
                        "gebruikt_bij_hertraining": tijdstip
                    }
                    f.write(json.dumps(regel, ensure_ascii=False) + "\n")
        except Exception as e:
            dbg(f"{C_RED}kon layer0_gebruikt.jsonl niet schrijven: "
                f"{e}{C_RESET}")

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