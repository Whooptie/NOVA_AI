# modules/learning/word_associations_learner.py
"""
Layer 1: Word Associations Learner
====================================

FASE 1: Tokenization & Filtering ✅
FASE 2: Co-occurrence tellen ✅ (nieuw in dit bestand)

Doel van Fase 1 (preprocessing):
- Tekst (wat Kevin typt + wat Nova antwoordt) omzetten naar een lijst
  van "bruikbare" woorden.
- Stopwoorden (lidwoorden, voegwoorden, ...) eruit filteren, want die
  zeggen niets over betekenis/interesse.
- Woorden een beetje normaliseren (lemmatization-benadering), zodat
  "auto's" en "auto" bijvoorbeeld als hetzelfde woord tellen.

Doel van Fase 2 (co-occurrence):
- Bijhouden hoe vaak elk woord voorkomt (word_stats).
- Bijhouden welke woorden samen voorkomen binnen een "venster" van
  woorden in dezelfde zin/interactie (associations).
- Dit is nog GEEN sterkte-score (dat komt in Fase 3 met PMI) — hier
  tellen we gewoon hoe vaak twee woorden samen opduiken.
- learn_from() luistert naar echte interacties via de EventBus
  (event "memory:interaction_added", gepubliceerd door memory.py).

Wat dit bestand NOG NIET doet (komt in latere fases):
- PMI berekenen / sterkte-score (Fase 3)
- Opvragen/queries zoals get_associations(), find_related() (Fase 4)
- Opslaan naar schijf + publiceren van updates op de EventBus (Fase 5)

Alles hier is pure telling/wiskunde in Python — geen ML, geen LLM.
"""

import json
import math
import re
import time
from pathlib import Path
from typing import Dict, List


class WordAssociationsLearner:
    """
    Layer 1: Word Associations Learner (wordt fase per fase uitgebreid).

    Deze klasse leert welke woorden vaak samen voorkomen in Kevin's
    gesprekken met Nova, zodat Nova later context/persoonlijkheid kan
    tonen (bv. weten dat Kevin "snel" en "Python" met elkaar associeert).
    """

    def __init__(self, event_bus=None, semantic_module=None, save_path=None):
        self.event_bus = event_bus
        self.semantic = semantic_module
        self.config = {}

        # ─────────────────────────────────
        # Opslag (Fase 2 — nog enkel in het geheugen, niet op schijf)
        # ─────────────────────────────────
        # associations: word1 -> {word2: {"co_occurrence": int,
        #                                  "first_seen": timestamp,
        #                                  "last_seen": timestamp}}
        self.associations: Dict[str, Dict[str, dict]] = {}
        # word_stats: word -> {"frequency": int,
        #                       "first_seen": timestamp,
        #                       "last_seen": timestamp}
        self.word_stats: Dict[str, dict] = {}

        # ─────────────────────────────────
        # Uitgebreide Nederlandse stopwoordenlijst
        # ─────────────────────────────────
        # Dit zijn woorden die zo vaak voorkomen dat ze niets zeggen
        # over de inhoud/betekenis van een zin (lidwoorden, voorzetsels,
        # voegwoorden, voornaamwoorden, hulpwerkwoorden, ...).
        # We houden ook een kleine set Engelse stopwoorden, omdat Kevin
        # soms Engelse termen door het Nederlands mengt (bv. "Python is
        # cool").
        self.stopwords = set([
            # Lidwoorden
            "de", "het", "een",

            # Voorzetsels
            "in", "op", "van", "voor", "naar", "over", "onder", "boven",
            "tussen", "bij", "met", "zonder", "door", "tegen", "tot",
            "uit", "aan", "om", "sinds", "binnen", "buiten", "langs",
            "rond", "per", "via", "richting", "vanaf", "tijdens",

            # Voegwoorden
            "en", "of", "maar", "want", "dus", "als", "toen", "omdat",
            "doordat", "hoewel", "terwijl", "zodat", "tenzij", "mits",
            "noch", "dan", "nadat", "voordat",

            # Persoonlijke voornaamwoorden
            "ik", "jij", "je", "u", "hij", "zij", "ze", "wij", "we",
            "jullie", "hen", "hun", "mij", "me", "jou", "haar", "hem",

            # Bezittelijke voornaamwoorden
            "mijn", "jouw", "zijn", "haar", "ons", "onze", "hun", "uw",

            # Aanwijzende / betrekkelijke voornaamwoorden
            "deze", "dit", "die", "dat", "zulke", "zo'n", "welke", "wat",
            "wie", "wiens",

            # Vragende voornaamwoorden (let op: "wat"/"wie" hierboven ook)
            "waar", "wanneer", "waarom", "hoe",

            # Onbepaalde voornaamwoorden
            "iets", "niets", "iemand", "niemand", "alles", "alle",
            "sommige", "elke", "elk", "ieder", "iedere", "geen", "veel",
            "weinig", "meer", "meest", "andere", "ander",

            # Hulpwerkwoorden / koppelwerkwoorden (courante vervoegingen)
            "is", "ben", "bent", "zijn", "was", "waren", "wordt",
            "worden", "werd", "werden", "heeft", "heb", "hebt", "hebben",
            "had", "hadden", "kan", "kan", "kunt", "kunnen", "kon",
            "konden", "zal", "zult", "zullen", "zou", "zouden", "moet",
            "moeten", "moest", "moesten", "mag", "mogen", "mocht",
            "mochten", "wil", "wilt", "willen", "wilde", "wilden",

            # Ontkenning en versterkers
            "niet", "geen", "wel", "toch", "juist", "erg", "heel",
            "zeer", "best", "nogal", "vrij", "tamelijk", "echt",

            # Overige zeer frequente functiewoorden
            "er", "hier", "daar", "ook", "nog", "al", "nu", "dan",
            "even", "gewoon", "eigenlijk", "misschien", "waarschijnlijk",
            "natuurlijk", "trouwens", "namelijk", "bijvoorbeeld", "zo",

            # Engelse stopwoorden (Kevin mengt soms Engelse termen)
            "the", "a", "an", "and", "or", "but", "be", "is", "are",
            "was", "were", "have", "has", "had", "do", "does", "did",
            "would", "could", "should", "will", "shall", "to", "of",
            "in", "on", "at", "for", "with", "as", "by", "this", "that",
        ])

        # Config-opties (vaste standaardwaarden, geen config-systeem nodig)
        self.min_word_length = 3
        self.window_size = 5

        # ─────────────────────────────────
        # Opslag-pad (Fase 5)
        # ─────────────────────────────────
        default_path = (
            Path(__file__).resolve().parent.parent.parent
            / "data" / "word_associations.json"
        )
        self.save_path = Path(save_path) if save_path else default_path

        # Bestaande data inladen (indien aanwezig)
        self.load_from_disk()

        # ─────────────────────────────────
        # Abonneren op de EventBus (Fase 2)
        # ─────────────────────────────────
        # memory.py publiceert dit event telkens er een nieuwe
        # interactie (Kevin's bericht + Nova's antwoord) is opgeslagen.
        # Layer 1 luistert mee en leert er automatisch van.
        if self.event_bus is not None:
            self.event_bus.subscribe(
                "memory:interaction_added", self.learn_from
            )
    # ─────────────────────────────────
    # Tokenization & Preprocessing
    # ─────────────────────────────────

    def tokenize(self, text: str) -> List[str]:
        """
        Splitst tekst op in losse woorden.

        Stappen:
        1. Alles omzetten naar kleine letters (zodat "Python" en
           "python" als hetzelfde woord tellen).
        2. Met een regex enkel letter-reeksen eruit halen (dus geen
           leestekens, cijfers, of losse underscores).

        Voorbeeld:
            "Python is mijn favoriet!"
            -> ["python", "is", "mijn", "favoriet"]
        """
        text = text.lower()
        # \b[a-zà-ÿ]+\b -> haalt woorden eruit, inclusief NL-accenten
        # (bv. "café", "één"). Cijfers en leestekens vallen eruit.
        words = re.findall(r"\b[a-zà-ÿ]+\b", text)
        return words

    def filter_stopwords(self, words: List[str]) -> List[str]:
        """
        Verwijdert stopwoorden en woorden die te kort zijn om
        betekenisvol te zijn (standaard: korter dan 3 letters).
        """
        return [
            w for w in words
            if w not in self.stopwords and len(w) >= self.min_word_length
        ]

    def lemmatize_nl(self, word: str) -> str:
        """
        Eenvoudige, symbolische normalisatie van Nederlandse woorden
        (BENADERING — geen volledige taalkundige lemmatizer).

        Wat dit wel afvangt:
        - Verkleinwoorden: "autootje" -> "auto", "boekje" -> "boek"
        - Regelmatig meervoud: "auto's" -> "auto" (al gebeurt dit vaak
          al in tokenize doordat de apostrof wegvalt), "honden" -> "hond"
        - Bijvoeglijke vorm met -e: "snelle" -> "snel"

        Wat dit NIET afvangt (bewuste beperking, zie uitleg in de chat):
        - Onregelmatige werkwoordsvervoegingen ("liep" -> "lopen")
        - Onregelmatig meervoud ("kind" -> "kinderen" andersom)
        - Homoniemen en context-afhankelijke gevallen

        Dit blijft 100% regel-gebaseerd Python (geen ML/LLM).
        """
        # Verkleinwoord op "-tje" (bv. "kopje" -> "kop")
        if word.endswith("tje") and len(word) > 5:
            return word[:-3]
        # Verkleinwoord op "-je" (bv. "boekje" -> "boek")
        if word.endswith("je") and len(word) > 4:
            return word[:-2]
        # Bijvoeglijke vorm op "-e" (bv. "snelle" -> "snel")
        # Let op: dit is een benadering en kan soms fout normaliseren
        # bij korte woorden, vandaar de lengte-check.
        if word.endswith("e") and len(word) > 4 and not word.endswith("ie"):
            stam = word[:-1]
            # NL-spellingsregel: bij een dubbele medeklinker aan het
            # einde (ontstaan door de extra lettergreep) valt er één
            # letter weg, bv. "snelle" -> stam "snell" -> "snel".
            if len(stam) > 2 and stam[-1] == stam[-2] and stam[-1] not in "aeiou":
                stam = stam[:-1]
            return stam
        # Regelmatig meervoud op "-en" (bv. "honden" -> "hond")
        if word.endswith("en") and len(word) > 5:
            return word[:-2]
        return word

    def preprocess(self, text: str) -> List[str]:
        """
        Volledige pijplijn: tokenize -> stopwoorden filteren ->
        lemmatizen -> duplicaten verwijderen (eerste voorkomen behouden).

        Voorbeeld:
            "Python is mijn favoriete taal, want Python is snel"
            -> ["python", "favoriet", "taal", "want" (gefilterd als
                stopwoord), "snel"]
            (volgorde blijft behouden, duplicaten zoals 2e "python"
            worden verwijderd)
        """
        tokens = self.tokenize(text)
        tokens = self.filter_stopwords(tokens)
        tokens = [self.lemmatize_nl(t) for t in tokens]

        # Duplicaten verwijderen, volgorde behouden
        seen = set()
        result = []
        for t in tokens:
            if t not in seen:
                result.append(t)
                seen.add(t)
        return result

    # ─────────────────────────────────
    # Leren (Fase 2)
    # ─────────────────────────────────

    def learn_from(self, interaction: Dict, event_type: str = None):
        """
        Wordt aangeroepen telkens memory.py een event doorstuurt via
        "memory:interaction_added".

        LET OP: memory.py luistert met "*" naar ALLE events, dus dit
        event komt binnen per los event ("chat_message" met Kevin's
        tekst, of "chat_response" met Nova's tekst) — niet als één
        gecombineerd paar. We filteren hier op event_type en gebruiken
        de "text"-sleutel, zoals Nova die overal gebruikt.

        De 2e parameter "event_type" vangen we hier bewust mee op
        (ook al gebruiken we hem niet), omdat Nova's EventBus elke
        handler standaard aanroept als handler(data, event_type) — zie
        core/event_bus.py. Zonder deze parameter zou elke aanroep eerst
        op een TypeError stuiten (die daar wel opgevangen wordt met een
        fallback, maar dat is nodeloze overhead bij elk bericht).
        """
        data = interaction.get("data", {})
        interaction_event_type = interaction.get("event_type", "")

        if interaction_event_type not in ("chat_message", "chat_response"):
            return

        text = data.get("text", "")
        if not text:
            return

        words = self.preprocess(text)

        if len(words) < 2:
            return  # Te weinig bruikbare woorden voor een associatie

        ts = interaction.get("timestamp", 0)

        # ── Stap 1: woordfrequentie bijwerken ──
        for word in words:
            if word not in self.word_stats:
                self.word_stats[word] = {
                    "frequency": 0,
                    "first_seen": ts,
                    "last_seen": ts,
                }
            self.word_stats[word]["frequency"] += 1
            self.word_stats[word]["last_seen"] = ts

        # ── Stap 2: co-occurrence bijwerken (sliding window) ──
        for i, word in enumerate(words):
            window_start = max(0, i - self.window_size)
            window_end = min(len(words), i + self.window_size + 1)

            for j in range(window_start, window_end):
                if i == j:
                    continue  # Een woord telt niet als associatie met zichzelf

                other_word = words[j]

                if word not in self.associations:
                    self.associations[word] = {}

                if other_word not in self.associations[word]:
                    self.associations[word][other_word] = {
                        "co_occurrence": 0,
                        "first_seen": ts,
                        "last_seen": ts,
                    }

                self.associations[word][other_word]["co_occurrence"] += 1
                self.associations[word][other_word]["last_seen"] = ts

        # ── Stap 3: PMI herberekenen ──
        # Elke keer als we bijleren, herberekenen we de sterkte-scores.
        self.calculate_pmi()

        # ── Stap 4: opslaan + event publiceren (Fase 5) ──
        # We slaan telkens meteen op naar schijf. Bij een grote
        # hoeveelheid data/interacties kan dit later een optimalisatie
        # nodig hebben (bv. enkel elke N interacties opslaan), maar
        # voor nu is "altijd opslaan" het veiligst: geen dataverlies
        # bij een crash van de 24/7 daemon.
        self.save_to_disk()

        # We publiceren een update-event per nieuw/bijgewerkt woordpaar
        # in DEZE interactie, zodat Layer 3 (semantic.py) hiervan op de
        # hoogte kan blijven zonder zelf steeds de hele dataset te
        # moeten doorzoeken.
        for i, word in enumerate(words):
            window_start = max(0, i - self.window_size)
            window_end = min(len(words), i + self.window_size + 1)
            for j in range(window_start, window_end):
                if i != j:
                    self.publish_update(word, words[j])

    # ─────────────────────────────────
    # Persistentie (Fase 5)
    # ─────────────────────────────────

    def save_to_disk(self):
        """
        Slaat associations + word_stats op naar data/word_associations.json.

        Als het bestand of de map nog niet bestaat, wordt de map eerst
        aangemaakt (parents=True) zodat dit ook bij een verse install
        van Nova werkt.
        """
        data = {
            "metadata": {
                "version": "1.0",
                "last_updated": time.time(),
                "total_words": len(self.word_stats),
                "total_associations": sum(
                    len(v) for v in self.associations.values()
                ),
            },
            "associations": self.associations,
            "word_stats": self.word_stats,
        }

        try:
            self.save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            # We laten Nova hierop NIET crashen — een mislukte save
            # mag het gesprek niet onderbreken. We loggen het enkel.
            print(f"[word_associations] Fout bij opslaan: {e}")

    def load_from_disk(self):
        """
        Laadt associations + word_stats terug in vanaf
        data/word_associations.json, als dat bestand bestaat.

        Bestaat het bestand nog niet (bv. eerste keer opstarten), dan
        doen we gewoon niets — we starten dan met lege data, wat
        normaal is.
        """
        if not self.save_path.exists():
            return

        try:
            with open(self.save_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.associations = data.get("associations", {})
            self.word_stats = data.get("word_stats", {})
        except Exception as e:
            # Corrupt of onleesbaar bestand: niet laten crashen, gewoon
            # met lege data verdergaan en het probleem melden.
            print(f"[word_associations] Fout bij laden: {e}")

    # ─────────────────────────────────
    # Publiceren (Fase 5)
    # ─────────────────────────────────

    def publish_update(self, word1: str, word2: str):
        """
        Publiceert een event op de EventBus wanneer een associatie
        bijgewerkt is, zodat andere modules (vooral Layer 3/semantic.py
        later) hierop kunnen inspelen zonder zelf te moeten pollen.
        """
        if self.event_bus is None:
            return

        if word1 in self.associations and word2 in self.associations[word1]:
            pmi = self.associations[word1][word2].get("pmi", 0)
            self.event_bus.publish("word_association:updated", {
                "word1": word1,
                "word2": word2,
                "pmi": float(pmi),
                "timestamp": time.time(),
            })
    
    # ─────────────────────────────────
    # (Fase 3)
    # ─────────────────────────────────
    
    def calculate_pmi(self):
        """
        Berekent voor elk woordpaar een sterkte-score tussen 0 en 1,
        gebaseerd op PMI (Pointwise Mutual Information).

        Wat is PMI?
        -----------
        PMI meet: "komen deze twee woorden vaker samen voor dan je puur
        toevallig zou verwachten?"

            PMI(x, y) = log( P(x, y) / (P(x) * P(y)) )

        Waarbij:
            P(x, y) = kans dat woord x en y samen voorkomen
                      = (co_occurrence van x en y) / (totaal aantal paren)
            P(x)    = kans dat woord x sowieso voorkomt
                      = (frequentie van x) / (totaal aantal woorden)
            P(y)    = idem voor y

        Interpretatie van de ruwe PMI-waarde:
            PMI > 0  -> x en y komen vaker samen voor dan toeval (interessant!)
            PMI = 0  -> x en y zijn onafhankelijk van elkaar
            PMI < 0  -> x en y vermijden elkaar juist

        Een ruwe PMI-waarde is echter lastig te lezen (kan van -5 tot +10
        lopen). Daarom persen we het resultaat door een sigmoid-functie,
        zodat het altijd netjes tussen 0 en 1 valt:

            genormaliseerd = 1 / (1 + e^(-PMI / 2))

        Dit geeft ons dan de uiteindelijke "confidence"/sterkte-score
        die we opslaan bij elk woordpaar.

        Dit is pure wiskunde (logaritmes en een sigmoid) — geen ML/LLM.
        """
        if not self.associations:
            return  # Nog niets geleerd, niets te berekenen

        # Totaal aantal woordparen (som van alle co_occurrence-tellingen)
        total_pairs = sum(
            sum(pair.get("co_occurrence", 0) for pair in assoc.values())
            for assoc in self.associations.values()
        )
        if total_pairs == 0:
            return

        # Totaal aantal woord-voorkomens (som van alle frequenties)
        total_words = sum(
            stats.get("frequency", 0) for stats in self.word_stats.values()
        )
        if total_words == 0:
            return

        for word1, assoc in self.associations.items():
            if word1 not in self.word_stats:
                continue  # Zou niet mogen gebeuren, maar veiligheidscheck

            p_x = self.word_stats[word1]["frequency"] / total_words

            for word2, pair_data in assoc.items():
                if word2 not in self.word_stats:
                    continue

                p_y = self.word_stats[word2]["frequency"] / total_words
                p_xy = pair_data.get("co_occurrence", 0) / total_pairs

                if p_xy <= 0 or p_x <= 0 or p_y <= 0:
                    continue  # Kan niet gebeuren bij een geldige telling, maar veilig

                pmi = math.log(p_xy / (p_x * p_y))

                # Sigmoid-normalisatie naar het bereik 0-1
                genormaliseerd = 1.0 / (1.0 + math.exp(-pmi / 2.0))

                pair_data["pmi"] = genormaliseerd
                pair_data["confidence"] = genormaliseerd

    # ─────────────────────────────────
    # Opvragen (Fase 4)
    # ─────────────────────────────────

    def get_associations(self, word: str, min_confidence: float = 0.0) -> Dict[str, float]:
        """
        Geeft alle associaties van een woord terug, gesorteerd van
        sterk naar zwak (op basis van de PMI-score).

        Voorbeeld:
            get_associations("python")
            -> {"snel": 0.61, "favoriet": 0.55, ...}

        min_confidence: enkel associaties met minstens deze score
        tonen. Standaard 0.0 = alles tonen. Zet dit bv. op 0.5 om
        alleen de echt sterke verbanden te zien.
        """
        if word not in self.associations:
            return {}

        gefilterd = {
            ander_woord: data.get("pmi", 0)
            for ander_woord, data in self.associations[word].items()
            if data.get("pmi", 0) >= min_confidence
        }

        # Sorteren van sterk naar zwak
        gesorteerd = dict(
            sorted(gefilterd.items(), key=lambda x: x[1], reverse=True)
        )
        return gesorteerd

    def find_related(self, word: str, top_k: int = 5,
                      min_confidence: float = 0.0) -> List[tuple]:
        """
        Geeft de top-K sterkst gerelateerde woorden terug als lijst
        van (woord, score)-paren.

        Voorbeeld:
            find_related("python", top_k=3)
            -> [("snel", 0.61), ("favoriet", 0.55), ("elegant", 0.52)]
        """
        associaties = self.get_associations(word, min_confidence)
        return list(associaties.items())[:top_k]

    def word_distance(self, word1: str, word2: str) -> float:
        """
        Geeft een afstandsscore tussen twee woorden (0-1, hoger =
        sterker verbonden).

        Als de woorden direct met elkaar geassocieerd zijn, gebruiken
        we die PMI-score direct. Zijn ze niet direct verbonden, dan
        kijken we naar gedeelde associaties (bv. "rust" en "python"
        zijn geen directe buren, maar delen mogelijk "snel" als
        associatie) en middelen we die — met een korting, omdat een
        indirecte link altijd zwakker is dan een directe.
        """
        assoc1 = self.get_associations(word1)

        if word2 in assoc1:
            return assoc1[word2]

        assoc2 = self.get_associations(word2)
        gemeenschappelijk = set(assoc1.keys()) & set(assoc2.keys())

        if not gemeenschappelijk:
            return 0.0

        gemiddelde = sum(
            (assoc1[w] + assoc2[w]) / 2 for w in gemeenschappelijk
        ) / len(gemeenschappelijk)

        return gemiddelde * 0.5  # Indirecte link telt voor de helft

    def get_word_sentiment(self, word: str) -> Dict[str, float]:
        """
        Schat in of een woord positief, negatief, of neutraal aanvoelt.

        BELANGRIJK — eerlijkheid over hoe dit werkt:
        Dit is GEEN sentiment-AI/ML-model. Het is een simpele,
        symbolische aanpak met twee vaste woordenlijsten (hardcoded
        positief/negatief). Onbekende woorden krijgen een score
        gebaseerd op hun associaties met die vaste lijsten. Dit werkt
        dus enkel zo goed als de woordenlijst hieronder is, en is geen
        vervanging voor een echt sentiment-classificatiemodel. Wil je
        dat later nauwkeuriger, dan is een ML-sentiment-tool (bounded
        specialist-tool, zoals eerder afgesproken) de juiste aanpak —
        niet iets dat we hier stiekem symbolisch "namaken".
        """
        positieve_woorden = [
            "favoriet", "snel", "elegant", "mooi", "goed", "leuk",
            "interessant", "cool", "geweldig", "perfect", "lekker",
            "fijn", "heerlijk", "top", "super", "fantastisch",
        ]
        negatieve_woorden = [
            "traag", "saai", "slecht", "lelijk", "dom", "vervelend",
            "stom", "verschrikkelijk", "afschuwelijk", "waardeloos",
            "irritant", "vies",
        ]

        if word in positieve_woorden:
            return {"positive": 0.9, "negative": 0.05, "neutral": 0.05}
        if word in negatieve_woorden:
            return {"positive": 0.05, "negative": 0.9, "neutral": 0.05}

        # Onbekend woord: afleiden uit associaties
        associaties = self.get_associations(word)
        if not associaties:
            return {"positive": 0.33, "negative": 0.33, "neutral": 0.34}

        pos_score = sum(
            score for w, score in associaties.items()
            if w in positieve_woorden
        ) / len(associaties)
        neg_score = sum(
            score for w, score in associaties.items()
            if w in negatieve_woorden
        ) / len(associaties)
        neutraal_score = max(0.0, 1.0 - pos_score - neg_score)

        return {
            "positive": pos_score,
            "negative": neg_score,
            "neutral": neutraal_score,
        }

    def get_stats(self) -> Dict:
        """
        Geeft algemene statistieken terug: hoeveel woorden/associaties
        er zijn, en de sterkste associaties over de hele dataset.

        Voorbeeld output:
            {
                "total_words": 42,
                "total_associations": 130,
                "strongest_associations": [
                    ("python", "snel", 0.61),
                    ("rust", "veilig", 0.58),
                    ...
                ]
            }
        """
        totaal_associaties = sum(
            len(v) for v in self.associations.values()
        )

        # Per woord de top-3 sterkste associaties verzamelen,
        # daarna over alles heen de globale top-20 nemen.
        alle_top_per_woord = [
            (word1, word2, score)
            for word1, assoc in self.associations.items()
            for word2, score in sorted(
                [(w, d.get("pmi", 0)) for w, d in assoc.items()],
                key=lambda x: x[1],
                reverse=True,
            )[:3]
        ]
        sterkste_overall = sorted(
            alle_top_per_woord, key=lambda x: x[2], reverse=True
        )[:20]

        return {
            "total_words": len(self.word_stats),
            "total_associations": totaal_associaties,
            "strongest_associations": sterkste_overall,
        }
    
    def get_debug_snapshot(self) -> Dict:
        """
        Hulpfunctie enkel voor testen/debuggen in Fase 2.

        Geeft een leesbaar overzicht van wat er tot nu toe geleerd is,
        zodat Kevin kan controleren of learn_from() goed werkt zonder
        dat er al een echte query-API (Fase 4) bestaat.

        Dit blijft in de klasse staan (het is onschadelijk en handig),
        maar wordt in latere fases minder relevant naarmate get_stats()
        en get_associations() er zijn.
        """
        return {
            "aantal_woorden": len(self.word_stats),
            "aantal_woorden_met_associaties": len(self.associations),
            "word_stats": self.word_stats,
            "associations": self.associations,
        }


def init_module(event_bus, semantic_module=None):
    """
    Wordt aangeroepen door module_loader.py bij het opstarten van Nova.

    Let op: module_loader.py roept dynamische modules aan als
    init_module(event_bus, sem), waarbij "sem" de semantic-module
    (Layer 3) is. Vandaar de "semantic_module"-parameter, net als bij
    chat.py en response_pipeline.py.
    """
    instance = WordAssociationsLearner(event_bus, semantic_module=semantic_module)
    if event_bus is not None:
        event_bus.publish("module_loaded", {"name": "word_associations"})
    return instance
