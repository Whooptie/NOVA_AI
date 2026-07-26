# modules/preferences/sentiment_classifier.py
"""
User Preferences: sentiment-nuance-classificatie (positief/neutraal_
gemengd/negatief).

Zelfde patroon als identity/personality/microlearning.py (Layer 6,
Fase 6, onderdeel 1+6) -- bewust hergebruikt i.p.v. iets nieuws
verzonnen: model laden, marge-detectie bij twijfel, twijfelgevallen
loggen als toekomstige trainingsdata, en automatische hertraining
zowel bij opstart als doorlopend na elk nieuw twijfelgeval.

Waarom dit een APARTE module is, en geen code binnenin intent_
router.py (ontwerpgesprek 26 juli 2026): intent_router.py is al een
groot bestand met veel routing-verantwoordelijkheid. Een heel ML-
subsysteem (model laden, marge-logica, uncertain-logging, hertrain-
trigger) hoort daar niet rechtstreeks in thuis -- zelfde reden waarom
microlearning.py ook een eigen bestand is naast intent_router.py,
niet erin verweven.

Bounded ML-tool, geen brein: dit classificeert ENKEL een sentiment-
nuance-categorie voor een already-matched voorkeur-zin (het regex-
patroon in intent_router.py's _ontleed_voorkeur_zin() bepaalt eerst
OF een zin een voorkeur-uitspraak is en WELK woord het onderwerp is;
deze classifier verfijnt enkel het grove positief/negatief-sentiment
dat daaruit komt naar 3 nuance-categorieën). Geen taalbegrip, geen
beslissing over opslag/conflictregels -- dat blijft in kevin_profile.py.
"""

import json
import os
import pickle
from datetime import datetime


class SentimentClassifier:
    # Zelfde marge-drempel-principe als microlearning.py: hoe klein
    # het verschil tussen de winnende en de op-één-na-beste categorie,
    # hoe onzekerder het model -- onder deze drempel loggen we het
    # geval als twijfelgeval voor toekomstige hertraining.
    MARGE_DREMPEL = 0.10

    # Aantal NIEUWE twijfelgevallen sinds de laatste training dat een
    # automatische hertraining rechtvaardigt. Zelfde als microlearning.py's
    # HERTRAINING_DREMPEL, hier iets lager omdat deze module een pas
    # gestarte, kleinere dataset heeft -- eerder bijleren is hier
    # waardevoller. Kevin kan dit later optrekken als de dataset groeit.
    HERTRAINING_DREMPEL = 15

    def __init__(self, event_bus=None):
        self.event_bus = event_bus

        base = os.path.dirname(__file__)
        self._model_pad = os.path.join(base, "sentiment_model.pkl")
        self._uncertain_pad = os.path.join(base, "sentiment_uncertain.jsonl")
        self._hertraining_status_pad = os.path.join(base, "sentiment_hertraining_status.json")

        self.model = self._laad_model()

        # Layer 6-achtige automatische hertraining (zie train_sentiment_
        # classifier.py voor de veiligheidsrem): één check meteen bij
        # opstart, én een doorlopende check na elk nieuw gelogd
        # twijfelgeval (zie _log_uncertain()).
        self._check_hertraining(bij_opstart=True)

    def _laad_model(self):
        """
        Laadt het getrainde sentiment-classificatiemodel (train_
        sentiment_classifier.py). Geeft None terug als het nog niet
        bestaat (Kevin heeft train_sentiment_classifier.py nog niet
        gedraaid) -- classificeer() valt dan terug op een neutrale
        default, geen crash.
        """
        if not os.path.exists(self._model_pad):
            print(
                "[SENTIMENT_CLASSIFIER] Geen getraind model gevonden "
                f"({self._model_pad}). Draai train_sentiment_classifier.py "
                "eerst -- voorlopig wordt elke voorkeur als grof "
                "positief/negatief behandeld, zonder nuance-verfijning."
            )
            return None

        try:
            with open(self._model_pad, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            print(f"[SENTIMENT_CLASSIFIER] Kon model niet laden: {e}")
            return None

    # ---------------------------------------------------------
    # Publieke API
    # ---------------------------------------------------------
    def classificeer(self, tekst, grof_sentiment=None):
        """
        Geeft de sentiment-nuance-categorie terug voor een zin:
        "positief", "neutraal_gemengd", of "negatief".

        Argumenten:
            tekst: de VOLLEDIGE zin (niet enkel het losse woord) --
                   de nuance zit in de context/formulering rond het
                   woord, niet in het woord zelf.
            grof_sentiment: optioneel, het bestaande regex-resultaat
                   ("positief"/"negatief") uit intent_router.py's
                   _ontleed_voorkeur_zin(). Gebruikt als terugval-
                   waarde als er geen model geladen is, EN als extra
                   controle bij een lage marge (zie hieronder) --
                   zelfde aanpak als microlearning.py's woordenlijst-
                   fallback bij twijfel.

        Geeft terug: "positief", "neutraal_gemengd", of "negatief".
        Valt terug op grof_sentiment (of "positief" als die ook
        ontbreekt) als er geen model beschikbaar is -- classificatie
        mag nooit een crash veroorzaken in de preference-flow.
        """
        if self.model is None:
            return grof_sentiment or "positief"

        try:
            proba = self.model.predict_proba([tekst])[0]
            klassen = self.model.classes_
            gesorteerd = sorted(zip(klassen, proba), key=lambda x: -x[1])
            top_klasse, top_score = gesorteerd[0]
            _, tweede_score = gesorteerd[1]
            marge = top_score - tweede_score
        except Exception as e:
            print(f"[SENTIMENT_CLASSIFIER] Fout bij classificeren: {e}")
            return grof_sentiment or "positief"

        if marge < self.MARGE_DREMPEL:
            # Model twijfelt -- loggen als toekomstige trainingsdata.
            # Het EFFECTIEF gebruikte resultaat blijft hier gewoon de
            # top-klasse van het model (in tegenstelling tot
            # microlearning.py, dat bij twijfel de woordenlijst-
            # fallback voorrang geeft): deze classifier heeft geen
            # even betrouwbare "woordenlijst"-tegenhanger, dus het
            # model-resultaat blijft leidend, enkel het logging-gedrag
            # verandert.
            self._log_uncertain(tekst, top_klasse, marge, grof_sentiment)

        return top_klasse

    # ---------------------------------------------------------
    # Twijfelgevallen loggen (toekomstige trainingsdata)
    # ---------------------------------------------------------
    def _log_uncertain(self, tekst, model_categorie, marge, grof_sentiment):
        """
        Logt een twijfelgeval -- een zin waar het model geen duidelijke
        marge tussen de winnende en tweede categorie had. Dit is de
        groeiende trainingsdata voor toekomstige, automatische
        hertraining (zie train_sentiment_classifier.py's gebruik van
        deze data).

        Het model-resultaat wordt gelogd als het "categorie"-veld --
        dat is wat train_sentiment_classifier.py later als label zal
        gebruiken bij hertraining. GEEN mensencontrole op dit moment --
        bewust zo ontworpen, zelfde als microlearning.py: het ijkpunt-
        testsetje (sentiment_benchmark_data.json) is de kwaliteitsrem,
        niet elke individuele log-regel.
        """
        try:
            with open(self._uncertain_pad, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "text": tekst,
                    "categorie": model_categorie,
                    "marge": round(marge, 4),
                    "grof_sentiment_regex": grof_sentiment,
                    "tijdstip": datetime.now().isoformat(),
                }, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[SENTIMENT_CLASSIFIER] Kon twijfelgeval niet loggen: {e}")
            return

        self._check_hertraining(bij_opstart=False)

    # ---------------------------------------------------------
    # Automatische hertraining
    # ---------------------------------------------------------
    def _tel_huidige_uncertain_regels(self):
        if not os.path.exists(self._uncertain_pad):
            return 0
        with open(self._uncertain_pad, "r", encoding="utf-8") as f:
            return sum(1 for regel in f if regel.strip())

    def _laad_hertraining_status(self):
        """
        Onthoudt hoeveel regels er in sentiment_uncertain.jsonl stonden
        bij de LAATSTE hertraining -- nodig om te bepalen hoeveel
        NIEUWE twijfelgevallen er sindsdien zijn bijgekomen, zonder
        steeds dezelfde oude regels opnieuw te tellen.
        """
        if not os.path.exists(self._hertraining_status_pad):
            return {"aantal_bij_laatste_training": 0, "laatste_training": None}

        try:
            with open(self._hertraining_status_pad, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"aantal_bij_laatste_training": 0, "laatste_training": None}

    def _save_hertraining_status(self, aantal_regels):
        status = {
            "aantal_bij_laatste_training": aantal_regels,
            "laatste_training": datetime.now().isoformat(),
        }
        with open(self._hertraining_status_pad, "w", encoding="utf-8") as f:
            json.dump(status, f, indent=2, ensure_ascii=False)

    def _check_hertraining(self, bij_opstart: bool):
        """
        Checkt of er genoeg NIEUWE twijfelgevallen zijn sinds de
        laatste hertraining om een nieuwe trainingsronde te
        rechtvaardigen. Roept train_sentiment_classifier.train_model()
        aan als dat zo is -- dat script bevat zelf al de volledige
        veiligheidsrem (ijkpunt-vergelijking, nieuwe versie wordt enkel
        actief bij minstens gelijke score). Deze methode moet dus ZELF
        geen kwaliteitsoordeel vellen -- enkel bepalen WANNEER een
        nieuwe trainingspoging de moeite waard is.

        Combineert BEIDE triggers (ontwerpgesprek 26 juli 2026, zelfde
        als microlearning.py): één check bij opstart (dekt Nova's 24/7-
        daemon-karakter, waarbij "opnieuw opstarten" zelden gebeurt),
        én een doorlopende check na elk nieuw gelogd twijfelgeval.

        Na een succesvolle trainingspoging (ongeacht of de nieuwe
        versie uiteindelijk actief werd): als de nieuwe versie ECHT
        actief werd, moet deze instantie zijn eigen self.model herladen
        -- anders blijft deze lopende instantie het OUDE model
        gebruiken tot de volgende herstart.
        """
        huidig_aantal = self._tel_huidige_uncertain_regels()
        status = self._laad_hertraining_status()
        nieuwe_sinds_laatste = huidig_aantal - status["aantal_bij_laatste_training"]

        moet_hertrainen = (
            nieuwe_sinds_laatste >= self.HERTRAINING_DREMPEL
            or (bij_opstart and status["laatste_training"] is None and huidig_aantal >= 10)
        )

        if not moet_hertrainen:
            return

        try:
            # Late import: train_sentiment_classifier.py importeert
            # zelf scikit-learn, wat we liever niet onnodig belasten
            # als er toch niets te hertrainen valt.
            from modules.preferences import train_sentiment_classifier

            print(
                f"[SENTIMENT_CLASSIFIER] {nieuwe_sinds_laatste} nieuwe twijfelgevallen "
                f"sinds de laatste hertraining -- automatische hertraining wordt gestart."
            )
            resultaat = train_sentiment_classifier.train_model()

            if resultaat.get("succes"):
                self._save_hertraining_status(huidig_aantal)

                if resultaat.get("wordt_actief"):
                    print(
                        "[SENTIMENT_CLASSIFIER] Nieuwe modelversie is beter of gelijk "
                        "aan het ijkpunt -- wordt nu actief geladen."
                    )
                    self.model = self._laad_model()
                else:
                    print(
                        "[SENTIMENT_CLASSIFIER] Nieuwe modelversie scoorde lager op "
                        "het ijkpunt -- huidige, actieve versie blijft in gebruik."
                    )
            else:
                print(f"[SENTIMENT_CLASSIFIER] Hertraining niet gelukt: {resultaat.get('reden')}")
        except Exception as e:
            print(f"[SENTIMENT_CLASSIFIER] Fout tijdens automatische hertraining: {e}")


def init_module(event_bus, semantic_module=None):
    """
    Standaard module_loader.py-conventie. 'semantic_module' wordt hier
    niet gebruikt maar moet aanwezig zijn zodat module_loader.py deze
    module net als de andere kan initialiseren via de dynamische scan.
    """
    classifier = SentimentClassifier(event_bus)
    if event_bus:
        event_bus.publish("module_loaded", {"name": "sentiment_classifier"})
    return classifier
