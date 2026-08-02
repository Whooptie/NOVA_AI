# core/intent_router.py
import re

C_RESET = "\033[0m"
C_GREEN = "\033[92m"
C_BLUE = "\033[94m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_CYAN = "\033[96m"
C_MAGENTA = "\033[95m"

def dbg(label, text=""):
    print(f"{C_CYAN}[ROUTER]{C_RESET} {label} {text}")

class IntentRouter:
    def __init__(self, event_bus, semantic_module=None, kevin_profile=None, sentiment_classifier=None, intent_classifier=None):
        self.event_bus = event_bus
        self.semantic = semantic_module
        self.kevin_profile = kevin_profile
        # User Preferences, sentiment-nuance (26 juli 2026): verfijnt
        # het grove positief/negatief-resultaat van _ontleed_voorkeur_
        # zin() naar 3 categorieën (positief/neutraal_gemengd/negatief).
        # Kan None zijn als het model nog niet geladen is -- altijd
        # voorzichtig checken met "if self.sentiment_classifier".
        self.sentiment_classifier = sentiment_classifier
        # Intent Classifier (Fase 3, 28 juli 2026): ML-fallback als
        # GEEN enkele bestaande detect_*() een match vindt. Kan None
        # zijn als het model nog niet geladen is -- altijd voorzichtig
        # checken met "if self.intent_classifier". Zie
        # intent_classifier_roadmap.md voor de volledige onderbouwing
        # waarom dit een begrensde ML-specialist is, geen LLM.
        self.intent_classifier = intent_classifier
        # Fase 4 (correcties): kortstondig geheugen van de laatst
        # gestelde classifier-vraag (originele tekst + gegokt label),
        # puur in RAM. Zie _probeer_intent_classifier() en
        # _verwerk_correctie().
        self._laatste_classifier_vraag = None
        # 29 juli 2026: vlag die een detect_*()-methode zelf kan zetten
        # als ze AL een specifieker topic emit heeft dan de generieke
        # naam uit de intent-tabel (bv. detect_chess()'s evaluatie
        # -tak emit "chess_evaluation" i.p.v. het algemene "chess").
        # Wordt door route()'s centrale lus gecheckt vlak vóór ze haar
        # eigen, generieke _emit_topic() zou aanroepen -- en telkens
        # weer op False gezet na elk bericht, zodat dit nooit per
        # ongeluk "aanblijft" voor een volgend, ongerelateerd bericht.
        self._topic_al_ge_emit = False
        # Bug #10-fix, stap 7: houdt bij of Kevin net gevraagd is een
        # nummer te kiezen na "onthoud sense <woord>". Volledig los van
        # pending_question.py (dat mechanisme is gebouwd voor ja/nee-
        # vragen, niet voor een keuze uit een genummerde lijst) --
        # zelfde soort lokale, eigen state als semantic.py's
        # RelationFlowEngine.pending_relation.
        self._pending_sense_voorkeur = None
        self._intent_tabel_deel1 = self._build_intent_tabel_deel1()
        self._intent_tabel_deel2 = self._build_intent_tabel_deel2()

        event_bus.subscribe("chat_message", self.route)
        event_bus.subscribe("intent_preference_detected", self._on_preference_detected)
        # Intent Classifier (Fase 3): luistert naar het antwoord op een
        # classifier-gestelde vraag (bv. "Bedoel je dat je wil
        # schaken?"). Dezelfde soort listener als
        # session_watcher.py/interruption_tracker.py gebruiken voor
        # "mag_ik_storen" -- hergebruikt het bestaande
        # pending_question-mechanisme, geen nieuwe infrastructuur.
        event_bus.subscribe("pending_question:answered", self._on_classifier_pending_answered)
        dbg(f"{C_GREEN}IntentRouter geladen{C_RESET}")

    # ---------------------------------------------------------
    # Reboot-commando
    # ---------------------------------------------------------
    def detect_reboot(self, text):
        if text.strip().lower() != "/reboot":
            return False

        dbg(f"{C_RED}→ reboot commando ontvangen{C_RESET}")
        # Let op: GEEN chat_response event hier — dat zou pas later
        # in main.py opgehaald worden, maar tegen die tijd bestaat dit
        # proces al niet meer (os.execv heeft het dan al vervangen).
        # De afscheidsboodschap gebeurt daarom rechtstreeks via print()
        # in reboot_manager.py, want dat verschijnt wél meteen.
        self.event_bus.publish("system:reboot", {})
        return True
    
    # ---------------------------------------------------------
    # Teach-flow
    # ---------------------------------------------------------
    def handle_teach(self, text):
        if not text.startswith("teach "):
            return False

        parts = text.split(maxsplit=2)
        if len(parts) != 3:
            return False

        # 1. teach <woord> noun/verb/adj
        if parts[2] in ("noun", "verb", "adj"):
            self.event_bus.publish("teach_pos", {
                "word": parts[1],
                "pos": parts[2]
            })
            return True

        # 2. teach <woord> <betekenis>
        self.event_bus.publish("teach_concept", {
            "word": parts[1],
            "meaning": parts[2]
        })
        return True

    # ---------------------------------------------------------
    # Example-flow (voorbeeldzin toevoegen)
    # ---------------------------------------------------------
    def handle_example(self, text):
        if not text.startswith("example "):
            return False

        parts = text.split(maxsplit=2)
        if len(parts) != 3:
            self.event_bus.publish("chat_response", {
                "text": "Gebruik: example <woord> <voorbeeldzin>"
            })
            return True

        word = parts[1]
        sentence = parts[2]

        self.event_bus.publish("teach_example", {
            "word": word,
            "sentence": sentence
        })
        return True

    # ---------------------------------------------------------
    # Preferences-flow (Fase 2: expliciet commando)
    # ---------------------------------------------------------
    def handle_preference(self, text):
        """
        Herkent 'onthoud: ...' en 'vergeet: ...'. Dit is bewust dezelfde
        stijl als handle_teach() hierboven: een vaste prefix, splitsen,
        en rechtstreeks doorsturen -- geen patroonherkenning hier (dat
        is Fase 3, detect_preference()). Dit is de voorspelbare,
        expliciete route: wat Kevin letterlijk typt, wordt letterlijk
        opgeslagen.

        Voorbeelden:
            onthoud: ik drink graag koffie   -> positief, "koffie"
            onthoud: ik hou niet van kou     -> negatief, "kou"
            vergeet: kou                     -> verwijderd
        """
        t = text.strip()
        tl = t.lower()

        # --- vergeet: <woord> ---
        if tl.startswith("vergeet:") or tl.startswith("vergeet "):
            woord = t.split(":", 1)[1].strip() if ":" in t else t.split(maxsplit=1)[1].strip()
            if not woord:
                self.event_bus.publish("chat_response", {
                    "text": "Gebruik: vergeet: <woord>"
                })
                return True

            if self.kevin_profile:
                verwijderd = self.kevin_profile.remove_preference(woord)
                if not verwijderd:
                    self.event_bus.publish("chat_response", {
                        "text": f"Ik had niets onthouden over '{woord}'."
                    })
            return True

        # --- onthoud: <zin> ---
        if tl.startswith("onthoud:") or tl.startswith("onthoud "):
            zin = t.split(":", 1)[1].strip() if ":" in t else t.split(maxsplit=1)[1].strip()
            if not zin:
                self.event_bus.publish("chat_response", {
                    "text": "Gebruik: onthoud: ik hou van <woord> / ik hou niet van <woord>"
                })
                return True

            grof_sentiment, woord = self._ontleed_voorkeur_zin(zin)
            if not woord:
                self.event_bus.publish("chat_response", {
                    "text": (
                        "Ik snap niet goed wat ik moet onthouden. Probeer bv.: "
                        "'onthoud: ik hou van koffie'"
                    )
                })
                return True

            sentiment = self._verfijn_sentiment(zin, grof_sentiment)

            if self.kevin_profile:
                self.kevin_profile.add_preference(woord, sentiment, bron="expliciet")
            return True

        return False

    def _ontleed_voorkeur_zin(self, zin):
        """
        Zeer eenvoudige, pure regex/string-herkenning van sentiment +
        onderwerp in een zin na 'onthoud:'. Bewust beperkt tot een
        handvol vaste patronen -- dit is 100% symbolisch (geen ML/LLM),
        maar heeft daardoor ook een eerlijke grens: een creatief
        geformuleerde zin die niet in een van deze patronen past, wordt
        gewoon niet herkend (geeft dan woord=None terug).

        Geeft terug: (sentiment, woord) -- sentiment is "positief" of
        "negatief", woord is None als niets herkend werd.
        """
        z = zin.strip().lower().rstrip(".!")

        negatieve_patronen = [
            "ik hou niet van ", "ik haat ", "ik lust geen ", "ik lust niet van ",
        ]
        for p in negatieve_patronen:
            if p in z:
                woord = z.split(p, 1)[1].strip()
                return "negatief", woord or None

        positieve_patronen = [
            "ik hou van ", "ik drink graag ", "ik eet graag ",
            "mijn favoriete ", "ik vind leuk ",
        ]
        for p in positieve_patronen:
            if p in z:
                woord = z.split(p, 1)[1].strip()
                # "mijn favoriete X is Y" -> we willen Y, niet "X is Y".
                # BUGFIX (26 juli 2026): deze "is"-check moet ENKEL bij
                # het "mijn favoriete "-patroon gebeuren, niet bij de
                # andere patronen. Was voorheen onvoorwaardelijk, waardoor
                # een zin als "ik hou van koffie maar het is niet mijn
                # favoriet" verkeerd afgekapt werd: de losse " is " in
                # "...maar het IS niet..." (een heel andere zins-
                # constructie dan "mijn favoriete X is Y") werd toch als
                # splitpunt gebruikt, en gooide daarbij "koffie" zelf weg
                # nog vóór _kap_woord_af() de kans kreeg iets te doen.
                if p == "mijn favoriete " and " is " in woord:
                    woord = woord.split(" is ", 1)[1].strip()
                woord = self._kap_woord_af(woord)
                return "positief", woord or None

        return "positief", None

    # Signaalwoorden die typisch een nuance-bijzin inleiden (bugfix
    # 26 juli 2026): zonder dit werd bv. "ik hou van koffie maar het
    # is niet mijn favoriet" opgeslagen met het VOLLEDIGE restant van
    # de zin als "woord" ("koffie maar het is niet mijn favoriet")
    # i.p.v. enkel "koffie". Zodra een van deze signalen in de rest
    # van de zin voorkomt, snijden we het woord daar af. Bewust een
    # vaste, korte lijst -- 100% symbolisch, geen taalbegrip -- dus
    # zal niet elke mogelijke nuance-constructie vangen, maar dekt de
    # meest voorkomende gevallen.
    _AFKAP_SIGNALEN = [
        " maar ", " hoewel ", " al is ", " ook al ", " ondanks ",
        " toch niet ", " echter ", " niet altijd ", " niet mijn favoriet",
    ]

    def _kap_woord_af(self, woord):
        """
        Snijdt 'woord' af zodra een nuance-signaalwoord verschijnt (zie
        _AFKAP_SIGNALEN hierboven). Geeft het woord ongewijzigd terug
        als geen enkel signaal voorkomt.
        """
        laagste_index = len(woord)
        for signaal in self._AFKAP_SIGNALEN:
            idx = woord.find(signaal)
            if idx != -1 and idx < laagste_index:
                laagste_index = idx
        return woord[:laagste_index].strip()

    def _verfijn_sentiment(self, volledige_zin, grof_sentiment):
        """
        User Preferences, sentiment-nuance (26 juli 2026): geeft de
        VOLLEDIGE zin (niet enkel het losse woord) door aan
        sentiment_classifier.py, dat het grove positief/negatief-
        resultaat van _ontleed_voorkeur_zin() kan verfijnen naar
        "neutraal_gemengd" als de zin daarop wijst (bv. "koffie is wel
        oké maar niet mijn favoriet" -- de regex-patronen hierboven
        herkennen enkel WELK woord het onderwerp is en een grof
        sentiment, geen nuance).

        Geeft gewoon grof_sentiment terug als er geen classifier
        beschikbaar is (bv. nog geen model getraind) -- de nuance-
        verfijning is een bonus bovenop de werkende Fase 2/3-flow,
        nooit een vereiste ervoor.
        """
        if not self.sentiment_classifier:
            return grof_sentiment

        return self.sentiment_classifier.classificeer(
            volledige_zin, grof_sentiment=grof_sentiment
        )

    # ---------------------------------------------------------
    # Sense-voorkeur commando (Bug #10-fix, stap 7)
    # ---------------------------------------------------------
    def handle_sense_voorkeur(self, text):
        """
        Herkent 'onthoud sense <woord>'. Start een korte, lokale
        vraag-flow (net als RelationFlowEngine in semantic.py, maar
        hier volledig binnen intent_router.py): Nova toont de
        genummerde lijst van senses voor dat woord, en wacht op een
        nummer als antwoord (afgehandeld door
        _verwerk_pending_sense_voorkeur()).

        Bewust een NUMMER laten kiezen i.p.v. te proberen vrije tekst
        ("de slang") te matchen met een definitie -- dat laatste zou
        een eigen stuk tekstherkenning vergen en is foutgevoeliger.
        Zelfde soort keuze als _ask_sense_choice() in semantic.py al
        maakt voor de relatie-flow.

        Voorbeeld:
            onthoud sense python
            -> "Welke betekenis van 'python' bedoel je meestal?
                1. een programmeertaal
                2. Een python is een grote, niet-giftige slang..."
            Kevin antwoordt: 2
            -> voorkeur opgeslagen, python -> python#2
        """
        t = text.strip()
        tl = t.lower()

        if not (tl.startswith("onthoud sense ") or tl.startswith("onthoud betekenis ")):
            return False

        prefix_lengte = len("onthoud sense ") if tl.startswith("onthoud sense ") else len("onthoud betekenis ")
        woord = t[prefix_lengte:].strip().rstrip(".!?")

        if not woord:
            self.event_bus.publish("chat_response", {
                "text": "Gebruik: onthoud sense <woord>, bv. 'onthoud sense python'"
            })
            return True

        if not self.semantic:
            self.event_bus.publish("chat_response", {
                "text": "Ik kan nu geen betekenissen opzoeken, probeer later opnieuw."
            })
            return True

        senses = self.semantic.get_senses(woord)
        echte_senses = [s for s in senses if s.get("definition") != "unknown"]

        if len(echte_senses) < 2:
            self.event_bus.publish("chat_response", {
                "text": f"Ik ken '{woord}' niet met meerdere betekenissen, dus er is niets om te kiezen."
            })
            return True

        lines = [f"Welke betekenis van '{woord}' bedoel je meestal?"]
        for i, s in enumerate(echte_senses, start=1):
            lines.append(f"{i}. {s.get('definition')}")
        lines.append("Antwoord met het nummer.")

        self._pending_sense_voorkeur = {
            "woord": woord,
            "senses": echte_senses,
        }

        self.event_bus.publish("chat_response", {"text": "\n".join(lines)})
        return True

    def _verwerk_pending_sense_voorkeur(self, text):
        """
        Wordt aangeroepen VOORDAT de normale intent-routing draait,
        enkel als self._pending_sense_voorkeur niet None is (dus vlak
        na handle_sense_voorkeur() de vraag stelde). Verwacht een kaal
        nummer als antwoord.

        Geeft True terug als het bericht als antwoord behandeld is
        (normale routing dus NIET meer draait), anders False.
        """
        if self._pending_sense_voorkeur is None:
            return False

        t = text.strip()

        if not t.isdigit():
            self.event_bus.publish("chat_response", {
                "text": "Antwoord met enkel het nummer van de betekenis die je bedoelt."
            })
            return True  # Vraag blijft open staan, geen normale routing

        nummer = int(t)
        senses = self._pending_sense_voorkeur["senses"]
        woord = self._pending_sense_voorkeur["woord"]

        if nummer < 1 or nummer > len(senses):
            self.event_bus.publish("chat_response", {
                "text": f"Kies een nummer tussen 1 en {len(senses)}."
            })
            return True  # Vraag blijft open staan

        gekozen_sense_id = senses[nummer - 1]["sense_id"]

        if self.kevin_profile:
            self.kevin_profile.set_sense_voorkeur(woord, gekozen_sense_id)
            self.event_bus.publish("chat_response", {
                "text": f"Oké, ik onthoud dat je met '{woord}' meestal betekenis {nummer} bedoelt."
            })
        else:
            self.event_bus.publish("chat_response", {
                "text": "Ik kan dit nu niet opslaan (kevin_profile niet beschikbaar)."
            })

        self._pending_sense_voorkeur = None
        return True

    # ---------------------------------------------------------
    # Preferences-flow (Fase 3: automatische patroonherkenning)
    # ---------------------------------------------------------
    def detect_preference(self, text):
        """
        Automatische tegenhanger van handle_preference() hierboven --
        zelfde patroonlijst (via _ontleed_voorkeur_zin), maar zonder dat
        Kevin het expliciete 'onthoud:'-commando hoeft te typen. Volgt
        exact de conventie van detect_weather()/detect_math() hierboven:
        herkent een patroon, publiceert een event, geeft True terug.
        Geeft False terug (of valt stil door) als niets herkend wordt --
        _emit_topic() gebeurt dan NIET, dat doet route() zelf al via de
        intent-tabel.

        Bewuste symbolische grens (zie ook memory_user_preferences_
        roadmap.md, sectie EERLIJKHEID): dit is dezelfde beperkte
        patroonlijst als de expliciete route, dus dezelfde kans dat een
        creatief geformuleerde zin gemist wordt. Dat is de bewuste prijs
        van 100% symbolisch werken zonder taalmodel -- beter een patroon
        missen dan een verkeerd sentiment vastleggen.

        LET OP: dit publiceert 'intent_preference_detected' i.p.v.
        rechtstreeks kevin_profile.add_preference() aan te roepen, in
        tegenstelling tot handle_preference(). Reden: bij een impliciete
        (niet-expliciete) uitspraak wil je typisch een lagere
        confidence/andere bron ("automatisch" i.p.v. "expliciet") EN wil
        je response_engine.py de kans geven om dit natuurlijk te
        bevestigen in de tone-pipeline, i.p.v. hier al stilzwijgend op
        te slaan. Het opslaan zelf gebeurt in _on_preference_detected()
        verderop, die op dit event subscribet.
        """
        t = text.strip()
        tl = t.lower()

        # Vermijd dubbel werk: zinnen die al met 'onthoud:'/'vergeet:'
        # beginnen zijn al door handle_preference() afgehandeld (die
        # stap staat vóór de intent-tabel in route()), dus komen hier
        # normaal nooit aan -- deze check is een extra vangnet.
        if tl.startswith("onthoud") or tl.startswith("vergeet"):
            return False

        grof_sentiment, woord = self._ontleed_voorkeur_zin(t)
        if not woord:
            return False

        dbg(f"{C_GREEN}→ preference (automatisch): '{woord}' = {grof_sentiment}{C_RESET}")
        self.event_bus.publish("intent_preference_detected", {
            "woord": woord,
            "sentiment": grof_sentiment,
            "volledige_zin": t,
        })
        return True

    def _on_preference_detected(self, data):
        """
        Subscriber op 'intent_preference_detected' (zie detect_preference()
        hierboven). Slaat de gevonden voorkeur effectief op met
        bron="automatisch" -- lagere confidence dan het expliciete
        'onthoud:'-commando (bron="expliciet"), conform de data-structuur
        in memory_user_preferences_roadmap.md.

        Verfijnt eerst het grove sentiment via sentiment_classifier.py
        (zie _verfijn_sentiment()) -- zelfde nuance-stap als
        handle_preference() voor het expliciete commando.
        """
        if not self.kevin_profile:
            return

        sentiment = self._verfijn_sentiment(data["volledige_zin"], data["sentiment"])
        self.kevin_profile.add_preference(
            data["woord"], sentiment, bron="automatisch"
        )

    # ---------------------------------------------------------
    # Preferences-flow (Fase 4: voorkeuren OPVRAGEN in gesprek)
    # ---------------------------------------------------------
    # Vaste woordenlijsten voor categorie-specifieke vragen. Bewust
    # klein en plat gehouden (geen semantic.py-koppeling) -- dit is
    # een eenvoudige lookup-tabel, geen taalbegrip. Uitbreidbaar door
    # gewoon woorden toe te voegen aan de sets.
    _DRANK_WOORDEN = {"koffie", "thee", "water", "cola", "melk", "sap", "wijn", "bier"}
    _ETEN_WOORDEN = {"pizza", "pasta", "salade", "friet", "soep", "brood"}

    def detect_preference_query(self, text):
        """
        Herkent vragen die het profiel OPVRAGEN, in twee smaken:

        1. Categorie-specifiek: "wat kan ik drinken?" / "wat zou ik
           kunnen eten?" -- kijkt enkel naar voorkeuren die in de
           _DRANK_WOORDEN/_ETEN_WOORDEN-lijst voorkomen.
        2. Breed profiel-overzicht: "wat weet je over mij?" / "wat
           vind ik leuk?" -- dumpt het volledige voorkeuren/afkeuren-
           profiel in één zin.

        100% symbolisch: vaste triggerzinnen + een vaste woordenlijst-
        lookup, geen vrije tekstinterpretatie. Net als detect_weather()
        hierboven, geen _emit_topic() hier -- dat doet de intent-tabel
        zelf al (zie _build_intent_tabel_deel2()).

        Publiceert 'layer4_response' i.p.v. rechtstreeks 'chat_response',
        zodat het antwoord nog door de volledige tone-pipeline gaat
        (emotie/personality/expressie) -- zelfde route als weather.py/
        math.py/time.py, zie nova_state.md sectie over layer4_response.
        """
        if not self.kevin_profile:
            return False

        t = text.lower().strip().rstrip("?.")

        drink_triggers = [
            "wat kan ik drinken", "wat zou ik kunnen drinken",
            "wat kan ik best drinken", "wat drink ik graag",
        ]
        eet_triggers = [
            "wat kan ik eten", "wat zou ik kunnen eten",
            "wat kan ik best eten", "wat eet ik graag",
        ]
        breed_triggers = [
            "wat weet je over mij", "wat weet je van mij",
            "wat vind ik leuk", "wat hou ik van", "wat zijn mijn voorkeuren",
            "wat weet je over kevin",
        ]

        if any(trig in t for trig in drink_triggers):
            tekst = self._antwoord_categorie_vraag(self._DRANK_WOORDEN, "drinkt")
            self.event_bus.publish("layer4_response", {"text": tekst})
            return True

        if any(trig in t for trig in eet_triggers):
            tekst = self._antwoord_categorie_vraag(self._ETEN_WOORDEN, "eet")
            self.event_bus.publish("layer4_response", {"text": tekst})
            return True

        if any(trig in t for trig in breed_triggers):
            tekst = self._antwoord_volledig_profiel()
            self.event_bus.publish("layer4_response", {"text": tekst})
            return True

        return False

    def _antwoord_categorie_vraag(self, categorie_woorden, werkwoord):
        """
        Bouwt een antwoord voor een categorie-specifieke vraag (drinken/
        eten). Kiest willekeurig tussen alle matches als er meerdere
        zijn -- geen voorkeur voor expliciet/automatisch of hoogste
        aantal_keer_genoemd, dat is bewust simpel gehouden voor deze
        eerste versie.
        """
        import random
        alles = self.kevin_profile.get_all_preferences()
        matches = [w for w in alles["voorkeuren"] if w in categorie_woorden]

        if not matches:
            return f"Ik weet nog niet wat je graag {werkwoord}, je hebt me dat nog niet verteld."

        gekozen = random.choice(matches)
        return f"{gekozen.capitalize()} misschien? Je gaf eerder aan dat je dat graag {werkwoord}."

    def _antwoord_volledig_profiel(self):
        """
        Bouwt een antwoord dat het volledige profiel samenvat in één
        zin. Toont enkel de woorden zelf (geen bron/aantal-details --
        dat zou de zin onleesbaar maken), gescheiden door komma's.
        """
        alles = self.kevin_profile.get_all_preferences()
        voorkeuren = list(alles["voorkeuren"].keys())
        afkeuren = list(alles["afkeuren"].keys())

        if not voorkeuren and not afkeuren:
            return "Ik weet eigenlijk nog niet zoveel over je voorkeuren -- vertel gerust iets!"

        delen = []
        if voorkeuren:
            delen.append("je houdt van " + ", ".join(voorkeuren))
        if afkeuren:
            delen.append("je houdt niet van " + ", ".join(afkeuren))

        return "Voor zover ik weet: " + " en ".join(delen) + "."

    # ---------------------------------------------------------
    # Definition
    # ---------------------------------------------------------
    def detect_definition(self, text):
        t = text.lower().strip()

        # Synoniemen
        for p in ["wat zijn synoniemen van ", "wat is een synoniem van ", "synoniemen van "]:
            if t.startswith(p):
                word = t[len(p):].strip().rstrip("?.")
                self.event_bus.publish("intent_synonym", {"word": word})
                return True

        # Antoniemen
        for p in ["wat is het tegenovergestelde van ", "wat zijn antoniemen van ", "tegendeel van "]:
            if t.startswith(p):
                word = t[len(p):].strip().rstrip("?.")
                self.event_bus.publish("intent_antonym", {"word": word})
                return True

        # Waarvoor gebruik je X
        for p in ["waarvoor gebruik je ", "waarvoor is ", "waarvoor dient "]:
            if t.startswith(p):
                word = t[len(p):].strip().rstrip("?.")
                for art in ["de ", "het ", "een "]:
                    if word.startswith(art):
                        word = word[len(art):].strip()
                        break
                self.event_bus.publish("intent_used_for", {"word": word})
                return True

        # Wat veroorzaakt X
        for p in ["wat veroorzaakt ", "wat zorgt voor "]:
            if t.startswith(p):
                word = t[len(p):].strip().rstrip("?.")
                self.event_bus.publish("intent_causes", {"word": word})
                return True

        # Wat zijn eigenschappen van X
        for p in ["wat zijn eigenschappen van ", "wat zijn kenmerken van "]:
            if t.startswith(p):
                word = t[len(p):].strip().rstrip("?.")
                self.event_bus.publish("intent_properties", {"word": word})
                return True
            
        # Waarop lijkt X (related_to)
        for p in ["waarop lijkt ", "waar lijkt ", "wat lijkt op "]:
            if t.startswith(p):
                word = t[len(p):].strip().rstrip("?.")
                for art in ["de ", "het ", "een "]:
                    if word.startswith(art):
                        word = word[len(art):].strip()
                        break
                self.event_bus.publish("intent_related_to", {"word": word})
                return True

        # Wikipedia opzoeken
        for p in ["wiki ", "leer wikipedia ", "zoek op "]:
            if t.startswith(p):
                word = t[len(p):].strip().rstrip("?.")
                for art in ["de ", "het ", "een "]:
                    if word.startswith(art):
                        word = word[len(art):].strip()
                        break
                self.event_bus.publish("intent_wiki", {"word": word})
                return True

        # Andere/aanvullende betekenis opvragen (vervolgpunt uit bug #27,
        # 31 juli 2026): een natuurlijke vervolgzin op een eerdere "wat
        # is X"-vraag, geen los commando.
        #
        # Bugfix bij live-testen (31 juli 2026): de eerste versie
        # gebruikte EXACTE zin-gelijkheid (t in [...]), waardoor zelfs
        # een kleine, heel natuurlijke variatie als "zijn er nog andere
        # betekenissen VAN FYSICA" al niet matchte en gewoon in de
        # fallback-intent belandde. Nu: STARTSWITH-matching op een
        # kernzin, met het woord ERNA optioneel (na "van "/"voor ").
        # Als het woord expliciet genoemd wordt, heeft dat voorrang op
        # _laatste_definitie_woord (bv. als iemand na een tijdje toch
        # nog een ANDER woord noemt dan het laatst opgezochte).
        andere_betekenis_kernzinnen = [
            "zijn er nog andere betekenissen",
            "zijn er andere betekenissen",
            "heeft dat nog andere betekenissen",
            "heeft het nog andere betekenissen",
            "andere betekenissen",
            "nog andere betekenissen",
            "wat betekent het nog meer",
            "wat betekent dat nog meer",
            "wat betekent het nog",
            "wat betekend het nog",
        ]
        for kernzin in andere_betekenis_kernzinnen:
            if t == kernzin or t.startswith(kernzin):
                rest = t[len(kernzin):].strip().rstrip("?.")
                woord = None
                for koppel in [" van ", " voor "]:
                    if rest.startswith(koppel):
                        woord = rest[len(koppel):].strip()
                        break
                if not woord:
                    woord = getattr(self, "_laatste_definitie_woord", None)

                if not woord:
                    self.event_bus.publish("chat_response", {
                        "text": "Waarvan wil je andere betekenissen weten? "
                                "Vraag eerst even 'wat is <woord>'."
                    })
                    return True

                # Eigen, herkenbaar Layer 2-topic (1 augustus 2026), i.p.v.
                # mee te liften op het topic van de vorige, gewone
                # definitievraag -- "zijn er nog andere betekenissen" is
                # een ANDER, onderscheiden gedragspatroon (bv. Kevin die
                # 's avonds graag dieper op een woord doorvraagt), dat
                # zonder eigen topic onzichtbaar zou blijven voor Layer 2.
                # Zelfde vlag-patroon als detect_chess()'s
                # chess_evaluation-tak hierboven: voorkomt dat route()'s
                # stap 8 hierna ALSNOG het generieke "definitie_<woord>"
                # emit (zie ook de bijbehorende aanpassing daar).
                self._emit_topic(f"andere_betekenis_{woord}", bron="detect")
                self._topic_al_ge_emit = True
                self.event_bus.publish("intent_wiki_andere_betekenis", {"word": woord})
                return True

        # "Wat weet je allemaal over X" -- nieuwe module concept_overview.py
        # (1 augustus 2026): toont een kort overzicht van ALLE bestaande
        # kennis over een woord (alle senses, relaties, voorbeelden),
        # met een pending-vervolgvraag voor wie meer detail wil. In
        # tegenstelling tot de andere detecties hierboven werkt dit
        # woord ALTIJD expliciet genoemd (geen zinvolle "vorig woord"-
        # fallback hier, want dit gaat niet per se over het laatst
        # opgezochte woord).
        overview_prefixes = [
            "wat weet je allemaal over ",
            "wat weet je over ",
            "vertel me alles over ",
            "vertel alles over ",
        ]
        for p in overview_prefixes:
            if t.startswith(p):
                woord = t[len(p):].strip().rstrip("?.")
                for art in ["de ", "het ", "een "]:
                    if woord.startswith(art):
                        woord = woord[len(art):].strip()
                        break
                # Eigen Layer 2-topic (1 augustus 2026), zelfde redenering
                # als bij de andere-betekenis-tak hierboven -- "wat weet
                # je allemaal over X" is een apart, herkenbaar
                # gedragspatroon, geen gewone definitievraag.
                self._emit_topic(f"concept_overview_{woord}" if woord else "concept_overview", bron="detect")
                self._topic_al_ge_emit = True
                self.event_bus.publish("intent_concept_overview", {"word": woord})
                return True

        # Definitievragen (crashfix: woord veilig ophalen)
        prefixes = [
            "wat is ",
            "wat zijn ",
            "wat betekent ",
            "wat betekend ",
            "betekent ",
            "betekend ",
            "definieer ",
            "definieer: ",
            "definitie van "
        ]
        for p in prefixes:
            if t.startswith(p):
                word = t[len(p):].strip().rstrip("?.")
                if not word:
                    return False
                # Lidwoorden strippen
                for art in ["de ", "het ", "een "]:
                    if word.startswith(art):
                        word = word[len(art):].strip()
                        break

                # Per-woord-timing (Layer 2-koppeling, uitbreiding op de
                # bewust generieke "definitie"-topic uit Fase 7): het
                # herkende woord hier bewaren als instance-attribuut,
                # zodat route() straks (na deze aanroep) een woord-
                # specifiek topic kan publiceren i.p.v. het vaste
                # "definitie". Alleen HIER, in de definitie-tak, gezet --
                # blijft None/ongewijzigd voor alle andere intents.
                self._laatste_definitie_woord = word

                # Layer 4 (response_engine) EERST proberen: die combineert
                # semantic + word_associations + pattern_matcher tot één
                # antwoord. Alleen als Layer 4 zelf geen definitie/relatie
                # vond (confidence <= 0.2, dat is zijn "weet ik niet"-geval,
                # zie response_engine.py), vallen we terug op de oude route
                # via chat.py's intent_definition — want DIE heeft nog de
                # automatische Wikipedia-fallback die Layer 4 niet heeft.
                # LET OP (Fase 7): we publiceren "layer4_response" i.p.v.
                # rechtstreeks "chat_response" — zo loopt de tekst nog
                # door response_pipeline.py's tone-keten (emotie/tone/
                # expression_injector), net als greeting/fallback al
                # deden. response_pipeline.py verzint daarbij GEEN nieuwe
                # tekst, het voegt enkel Nova's stemming/expressie toe.
                response_engine = self.event_bus.modules.get("response_engine")

                if response_engine is not None:
                    # Bug #10-fix: de volledige vraagzin (t) meegeven als
                    # context, zodat response_engine (via semantic.
                    # detect_sense()) bij meerduidige woorden (python,
                    # hart, ...) de juiste sense kan herkennen i.p.v.
                    # altijd de sense met hoogste confidence te tonen.
                    context_words = t.split()

                    # Werkpunt 9.5 (27 juli 2026): response_style
                    # opvragen bij Layer 5 (context_manager) en
                    # doorgeven aan generate(), zodat "kort" nu ook
                    # de INHOUD verkort (Layer 1-associatie + Layer 2-
                    # timing-hint overslaan), niet enkel de toon
                    # achteraf (dat laatste deed expression_injector.py
                    # al). Zelfde try/except-veiligheid en dezelfde
                    # manier van opvragen als response_pipeline.py's
                    # _get_response_style() — context_manager wordt
                    # nooit als argument doorgegeven aan IntentRouter,
                    # dus we halen het op via event_bus.modules, met
                    # "normaal" als veilige standaardwaarde als Layer 5
                    # nog niet geladen is of er iets misgaat.
                    response_style = "normaal"
                    try:
                        ctx_mgr = self.event_bus.modules.get("context_manager")
                        if ctx_mgr is not None:
                            ctx = ctx_mgr.get_current()
                            response_style = ctx.get("response_style", "normaal")
                    except Exception:
                        response_style = "normaal"

                    resultaat = response_engine.generate(
                        word, context_words, response_style=response_style
                    )

                    if resultaat.get("confidence", 0.0) > 0.2:
                        self.event_bus.publish("layer4_response", {
                            "text": resultaat["text"]
                        })
                        return True
                    # confidence <= 0.2 -> Layer 4 wist het niet, val
                    # door naar de oude route hieronder (met Wikipedia).

                self.event_bus.publish("intent_definition", {
                    "text": text,
                    "word": word
                })
                return True

        return False

    # ---------------------------------------------------------
    # Greeting
    # ---------------------------------------------------------
    def detect_greeting(self, text):
        greetings = {"hallo", "hoi", "hey", "hello", "dag", "yo"}
        if text in greetings:
            dbg(f"{C_GREEN}→ greeting{C_RESET}")
            self.event_bus.publish("intent_greeting", {"sender": self._get_sender_name()})
            return True
        return False

    def _get_sender_name(self):
        """
        Layer 6, stap 5 (17 juli 2026): haalt de naam van de huidige
        spreker op via presence_detector.get_current_speaker() (Layer
        5), i.p.v. de vroegere hardcoded "user"-placeholder.

        Via event_bus.modules i.p.v. een directe import, dezelfde
        aanpak als response_pipeline.py's _get_response_style() eerder
        deze sessie — voorkomt een harde afhankelijkheid tussen
        intent_router.py en presence_detector.py, en blijft werken
        ongeacht laadvolgorde.

        Valt terug op "Kevin" als presence_detector (nog) niet
        beschikbaar is — nooit een crash, en nooit terug naar de oude,
        onpersoonlijke "user"-placeholder.
        """
        try:
            presence = self.event_bus.modules.get("presence_detector")
            if presence is not None and hasattr(presence, "get_current_speaker"):
                return presence.get_current_speaker()
        except Exception:
            pass
        return "Kevin"

    # ---------------------------------------------------------
    # Weather
    # ---------------------------------------------------------
    def detect_weather(self, text):
        t = text.lower()
        woorden = [w.strip(".,!?;:") for w in t.split()]

        # Los woord "weer", "weerbericht" of "temperatuur" ergens in de zin
        weerwoorden = {"weer", "weerbericht", "temperatuur"}
        if any(w in weerwoorden for w in woorden):
            dbg(f"{C_BLUE}→ weather{C_RESET}")
            self.event_bus.publish("intent_weather", {"text": text})
            return True

        # Zinnen zonder het letterlijke woord "weer"
        extra_triggers = ["is het koud", "is het warm"]
        if any(trig in t for trig in extra_triggers):
            dbg(f"{C_BLUE}→ weather{C_RESET}")
            self.event_bus.publish("intent_weather", {"text": text})
            return True

        return False
    # ---------------------------------------------------------
    # Time
    # ---------------------------------------------------------
    def detect_time(self, text):
        t = text.lower().strip()
        
        # Exacte zinnen eerst
        time_phrases = [
            "hoe laat is het",
            "wat is de tijd",
            "wat is het uur",
            "hoeveel tijd",
            "hoe laat"
        ]
        if any(phrase in t for phrase in time_phrases):
            dbg(f"{C_YELLOW}→ time_query{C_RESET}")
            self.event_bus.publish("intent_time_query", {"text": text})
            return True

        # Losse woorden — alleen als heel woord, niet als deel van een ander woord
        time_words = ["tijd", "klok"]
        words_in_text = t.split()
        if any(w in words_in_text for w in time_words):
            dbg(f"{C_YELLOW}→ time_query{C_RESET}")
            self.event_bus.publish("intent_time_query", {"text": text})
            return True

        return False

    # ---------------------------------------------------------
    # Chess
    # ---------------------------------------------------------
    def detect_chess(self, text):
        t = text.lower().strip().rstrip("?.")

        # Vraag naar detail van de laatste zet-evaluatie (nieuw).
        # Herhaalt enkel wat al berekend werd bij de zet zelf --
        # verzint GEEN nieuwe uitleg (zie chess_engine.py's
        # handle_evaluation_query()).
        eval_vraag_phrases = [
            "waarom was dat een blunder", "wat ging er mis",
            "wat had ik beter kunnen doen", "wat was de betere zet",
            "waarom was die zet slecht", "leg die zet uit",
            "wat had ik moeten spelen",
        ]
        if any(p in t for p in eval_vraag_phrases):
            dbg(f"{C_GREEN}→ chess_evaluation_query{C_RESET}")
            self.event_bus.publish("intent_chess_evaluation_query", {})
            # Deze tak van detect_chess() hoort eigenlijk bij een
            # SPECIFIEKERE categorie dan het generieke "chess" dat de
            # centrale lus (route()) anders zou emitten via de vaste
            # (topic_naam, detect_functie)-koppeling in de intent
            # -tabel. We emitten hier zelf het juiste, specifieke
            # topic, en zetten een vlag zodat route() zijn eigen,
            # generieke _emit_topic("chess", ...) hierna NIET nogmaals
            # aanroept (anders zou dit bericht dubbel -- en onder het
            # verkeerde label "chess" -- meetellen voor Fase 6's
            # Layer 0-koppeling).
            self._emit_topic("chess_evaluation", bron="detect")
            self._topic_al_ge_emit = True
            return True

        # Nieuwe partij
        new_game_phrases = [
            "nieuwe partij", "nieuw potje", "nieuw spel schaak",
            "start schaken", "begin schaken", "nieuwe schaakpartij"
        ]
        if t in new_game_phrases or any(t.startswith(p) for p in new_game_phrases):
            dbg(f"{C_GREEN}→ chess_new{C_RESET}")
            self.event_bus.publish("intent_chess_new", {})
            return True

        # Bord tonen
        board_phrases = [
            "toon bord", "laat bord zien", "huidige stand",
            "schaakbord", "wat is de stand", "bord"
        ]
        if t in board_phrases:
            dbg(f"{C_GREEN}→ chess_board{C_RESET}")
            self.event_bus.publish("intent_chess_board", {})
            return True

        # Zet in UCI-notatie: bv "e2e4", "g1f3", "e7e8q" (promotie)
        if re.fullmatch(r"[a-h][1-8][a-h][1-8][qrbn]?", t):
            dbg(f"{C_GREEN}→ chess_move{C_RESET}")
            self.event_bus.publish("intent_chess_move", {"move": t})
            return True

        # Zet in natuurlijke taal: stuksnaam + veld (bv. "paard naar f3", "pion e4")
        stukken = ["pion", "paard", "loper", "toren", "dame", "koning"]
        heeft_stuk = any(s in t for s in stukken)
        heeft_veld = bool(re.search(r'[a-h][1-8]', t))
        if heeft_stuk and heeft_veld:
            dbg(f"{C_GREEN}→ chess_move (natuurlijke taal){C_RESET}")
            self.event_bus.publish("intent_chess_move", {"move": t})
            return True

        # Alleen een veld (bv. "e4") — pion wordt aangenomen
        if re.fullmatch(r"[a-h][1-8]", t):
            dbg(f"{C_GREEN}→ chess_move (veld alleen){C_RESET}")
            self.event_bus.publish("intent_chess_move", {"move": t})
            return True

        # Moeilijkheidsgraad (bv. "moeilijkheid 5", "niveau 15")
        m = re.match(r"(?:moeilijkheid|niveau|level)\s+(\d+)", t)
        if m:
            dbg(f"{C_GREEN}→ chess_difficulty{C_RESET}")
            self.event_bus.publish("intent_chess_difficulty", {"niveau": m.group(1)})
            return True

        # Denktijd (bv. "denktijd 3", "denktijd 0.5")
        m = re.match(r"denktijd\s+(\d+(?:\.\d+)?)", t)
        if m:
            dbg(f"{C_GREEN}→ chess_think_time{C_RESET}")
            self.event_bus.publish("intent_chess_think_time", {"seconden": m.group(1)})
            return True

        # Statistieken opvragen
        if t in ["statistieken", "stats", "score", "mijn score"]:
            dbg(f"{C_GREEN}→ chess_stats{C_RESET}")
            self.event_bus.publish("intent_chess_stats", {})
            return True

        # Rokade
        if t in ["rokeer kort", "korte rokade", "rokade kort"]:
            dbg(f"{C_GREEN}→ chess_move (rokade kort){C_RESET}")
            self.event_bus.publish("intent_chess_move", {"move": "O-O"})
            return True

        if t in ["rokeer lang", "lange rokade", "rokade lang"]:
            dbg(f"{C_GREEN}→ chess_move (rokade lang){C_RESET}")
            self.event_bus.publish("intent_chess_move", {"move": "O-O-O"})
            return True

        return False

    # ---------------------------------------------------------
    # Eenhedenconversie in natuurlijke taal
    # ---------------------------------------------------------
    # NIEUW (1 aug 2026): vertaalt natuurlijke zinnen ("hoeveel ml is
    # 250 cl?", "1 kg in gram") naar math.py's .to(...)-syntax. Puur
    # symbolisch (regex + woordenboek), geen ML nodig. Beperkt tot een
    # praktische lijst veelgebruikte Nederlandse eenheidswoorden — code-
    # afkortingen (kg, cl, ...) werken via detect_math() al vanzelf.
    NL_EENHEDEN = {
        "meter": "m", "meters": "m", "centimeter": "cm", "centimeters": "cm",
        "millimeter": "mm", "millimeters": "mm", "kilometer": "km", "kilometers": "km",
        "mijl": "mile", "mijlen": "mile", "voet": "ft", "yard": "yard",
        "gram": "g", "kilo": "kg", "kilogram": "kg", "milligram": "mg",
        "pond": "lb", "ons": "oz",
        "liter": "L", "liters": "L", "milliliter": "ml", "milliliters": "ml",
        "centiliter": "cl", "centiliters": "cl", "deciliter": "dl", "deciliters": "dl",
        "gallon": "gal",
        "seconde": "s", "seconden": "s", "minuut": "min", "minuten": "min",
        "uur": "h", "uren": "h", "dag": "day", "dagen": "day", "week": "week", "weken": "week",
        "celsius": "degC", "fahrenheit": "degF", "kelvin": "K",
        "graden": "deg", "graad": "deg", "radialen": "rad", "radiaal": "rad",
        "calorie": "cal", "calorieën": "cal", "kilocalorie": "kcal", "kilocalorieën": "kcal",
        "byte": "byte", "bytes": "byte", "kilobyte": "kB", "megabyte": "MB", "gigabyte": "GB",
    }

    def _eenheid_naar_code(self, woord):
        w = woord.strip().lower()
        return self.NL_EENHEDEN.get(w, woord.strip())

    def detect_conversie(self, text):
        t = text.strip()

        # patroon A: "hoeveel <doel> is <getal> <bron>"
        m = re.search(
            r'hoeveel\s+([a-zA-Zµ°éë]+)\s+is\s+(\d+(?:[.,]\d+)?)\s*([a-zA-Zµ°]+)',
            t, re.IGNORECASE
        )
        if m:
            doel_woord, getal, bron_woord = m.groups()
            bron = self._eenheid_naar_code(bron_woord)
            doel = self._eenheid_naar_code(doel_woord)
            getal = getal.replace(",", ".")
            expr = f"{getal}{bron}.to({doel})"
            self.event_bus.publish("intent_math", {"expr": expr})
            return True

        # patroon B: "<getal> <bron> in <doel>"
        m = re.search(
            r'(\d+(?:[.,]\d+)?)\s*([a-zA-Zµ°]+)\s+in\s+([a-zA-Zµ°éë]+)',
            t, re.IGNORECASE
        )
        if m:
            getal, bron_woord, doel_woord = m.groups()
            bron = self._eenheid_naar_code(bron_woord)
            doel = self._eenheid_naar_code(doel_woord)
            getal = getal.replace(",", ".")
            expr = f"{getal}{bron}.to({doel})"
            self.event_bus.publish("intent_math", {"expr": expr})
            return True

        return False

    # ---------------------------------------------------------
    # Math
    # ---------------------------------------------------------
    def detect_math(self, text):
        t = text.strip()
        if any(op in t for op in ["+", "-", "*", "/", "^"]):
            self.event_bus.publish("intent_math", {"expr": text})
            return True
        import re
        if re.search(r'\d\s*[x×]\s*\d', t):
            self.event_bus.publish("intent_math", {"expr": text})
            return True
        if re.fullmatch(r"\d+(\.\d+)?\s*°[CF]", t):
            self.event_bus.publish("intent_math", {"expr": text})
            return True

        # UITBREIDING (1 aug 2026): eenhedenconversie via .to(...) (bv.
        # "5m.to(cm)") bevat geen operator/keyword en werd daardoor nooit
        # herkend als math-intent. Het patroon ".to(" is heel specifiek
        # voor conversie-syntax en komt niet voor in gewone zinnen.
        if re.search(r'\.to\(', t):
            self.event_bus.publish("intent_math", {"expr": text})
            return True

        # UITBREIDING (1 aug 2026): getal direct gevolgd door een kale
        # eenheid-letter (bv. "0C", "20C", "5m", "10kg") werd nooit
        # herkend, omdat er geen operator/keyword/gradenteken in zit.
        # Nodig zodat bv. "0C" wél naar math.py gaat — daar geeft de
        # dubbelzinnigheid-check een duidelijke foutmelding i.p.v. dat
        # de zin in de fallback verdwijnt.
        if re.fullmatch(r"\d+(\.\d+)?\s*[A-Za-zµ]+", t):
            self.event_bus.publish("intent_math", {"expr": text})
            return True

        # BUGFIX (11 juli 2026): "tan" (en andere korte math_keywords)
        # zaten voorheen als kale substring-check, waardoor gewone
        # woorden die deze letters toevallig bevatten (bv. "toestand"
        # bevat "tan") foutief als wiskunde-expressie werden herkend.
        # We gebruiken nu woordgrenzen (\b) zodat enkel het EXACTE
        # keyword als apart woord matcht, niet als deel van een ander
        # woord.
        # UITBREIDING (1 aug 2026): math_keywords bevatte enkel de basis
        # wiskundige functies, niet de vector/matrix/rotatie-functienamen
        # uit math.py's self.funcs. Daardoor werden aanroepen als
        # "det(...)", "dot(...)", "rotX(...)" nooit herkend.
        math_keywords = [
            "sqrt", "sin", "cos", "tan", "log", "ln", "exp", "abs", "round",
            "dot", "norm", "cross", "unit", "proj", "transpose", "det", "inverse",
            "identity", "rotX", "rotx", "rotY", "roty", "rotZ", "rotz",
            "rotAxis", "rotaxis", "solve", "solveGauss", "solvegauss",
            # UITBREIDING (Fase 3, Algebra-module): zonder deze namen werd
            # bv. "extremum(x2, 0, 5)" (geen +/-/*/^ in de tekst) nooit
            # herkend als math-intent en verdween hij stil in de fallback.
            # LET OP: "wortel" en "bereken" bewust NIET in deze lijst —
            # dat zijn gewone Nederlandse woorden (vgl. "de wortel van het
            # probleem", "ik moet nog berekenen wat...") die als kale
            # substring-match veel te breed zouden triggeren. Zie de
            # aparte, strengere check hieronder die enkel matcht als er
            # ook een openingshaakje op volgt (dus echt een functie-
            # aanroep is, bv. "wortel(1,-5,6)").
            "solveQuadratic", "solvequadratic",
            "newton", "nulpunt", "polyeval", "extremum", "minmax",
            # UITBREIDING (Fase 3, punt 8 — Calculus-module): "dv_euler"
            # en "dv_rk4" zijn technische namen die niemand toevallig in
            # een gewone zin gebruikt, dus die mogen breed matchen. "dv"
            # alleen is te kort/generiek (net als "pi"/"e" hierboven) en
            # staat daarom bij de haakje-vereiste check verderop. Ook
            # "afgeleide", "integraal" en "limiet" zijn gewone
            # Nederlandse woorden (vgl. "een integraal onderdeel van...",
            # "de limiet van mijn geduld", "de afgeleide betekenis van
            # dit woord") — die staan daarom NIET hier.
            "dv_euler", "dv_rk4",
            # UITBREIDING (Fase 3, punt 9 — Statistiek-module):
            # "stdafwijking", "variantie", "faculteit", "combinaties" en
            # "permutaties" zijn specifieke technische termen die niemand
            # toevallig in een gewone zin gebruikt, dus die mogen breed
            # matchen. "mediaan" staat voor de zekerheid ook hier (komt
            # zelden voor buiten wiskunde-context). "gemiddelde", "modus",
            # "regressie", "correlatie" en "normaal" zijn wél gewone
            # Nederlandse woorden (vgl. "dat is normaal gesproken zo",
            # "in het gemiddelde geval", "wat is jouw modus vandaag",
            # "de correlatie is duidelijk") — die staan daarom NIET hier,
            # zie de haakje-vereiste check verderop.
            "stdafwijking", "variantie", "faculteit", "combinaties",
            "permutaties", "mediaan",
            # UITBREIDING (Fase 4, punt 10 — Symbolische algebra, via
            # SymPy): allemaal Engelse, technische functienamen die
            # niemand toevallig in een gewone Nederlandse zin gebruikt
            # (in tegenstelling tot "wortel"/"bereken"/"gemiddelde"/
            # "normaal" hierboven), dus die mogen gewoon breed matchen.
            "differentiate", "integrate_sym", "simplify_sym",
            "expand_sym", "factor_sym", "solve_sym",
            # UITBREIDING (Fase 4, punt 11 — Fysica-engine):
            # "energie_kinetisch", "energie_potentieel", "snelheid_na",
            # "afstand_na" en "val_met_weerstand" bevatten underscores en
            # zijn technisch genoeg om breed te mogen matchen. "projectiel"
            # is ook technisch genoeg (komt zelden voor in gewone zinnen).
            # "kracht" en "arbeid" zijn wél gewone Nederlandse woorden
            # (vgl. "de kracht van je woorden", "ik ga naar mijn arbeid")
            # — die staan daarom NIET hier, zie de haakje-vereiste check
            # verderop.
            "energie_kinetisch", "energie_potentieel", "snelheid_na",
            "afstand_na", "val_met_weerstand", "projectiel",
        ]
        if any(re.search(rf"\b{k}\b", t) for k in math_keywords):
            self.event_bus.publish("intent_math", {"expr": text})
            return True

        # "wortel", "bereken", "afgeleide", "integraal", "limiet", "dv",
        # "gemiddelde", "modus", "regressie", "correlatie", "binomiaal",
        # "normaal", "kracht" en "arbeid" enkel herkennen als ECHTE
        # functie-aanroep (naam direct gevolgd door een openingshaakje) —
        # zie toelichting hierboven waarom deze niet in de brede
        # math_keywords-lijst staan.
        if re.search(r'\b(wortel|bereken|afgeleide|integraal|limiet|dv|gemiddelde|modus|regressie|correlatie|binomiaal|normaal|kracht|arbeid)\s*\(', t):
            self.event_bus.publish("intent_math", {"expr": text})
            return True

        # LET OP — bewust apart gehouden van math_keywords hierboven:
        # "pi" en "e" zijn losse, korte woorden die ook buiten wiskunde-
        # context kunnen voorkomen. Enkel toevoegen als je dit risico
        # aanvaardt.
        math_constants = ["pi", "e"]
        if any(re.search(rf"\b{k}\b", t) for k in math_constants):
            self.event_bus.publish("intent_math", {"expr": text})
            return True

        return False

    # ---------------------------------------------------------
    # Relation-check ("is een hond een dier")
    # ---------------------------------------------------------
    def detect_relation_check(self, text):
        t = text.lower().strip().rstrip("?.")

        # 1. "is een X een Y"
        m = re.match(r"is\s+een\s+(\w+)\s+een\s+([\w\s]+)", t)
        if m:
            self.event_bus.publish("intent_relation_check", {
                "source": m.group(1).strip(),
                "target": m.group(2).strip()
            })
            return True

        # 2. "X is een Y"
        m = re.match(r"(\w+)\s+is\s+een\s+([\w\s]+)", t)
        if m:
            self.event_bus.publish("intent_relation_check", {
                "source": m.group(1).strip(),
                "target": m.group(2).strip()
            })
            return True

        return False

    # ---------------------------------------------------------
    # Part-of-check ("is een snaar onderdeel van een orkest",
    # "zit een wiel in een fiets") — analoog aan detect_relation_check,
    # maar voor part_of i.p.v. is_a. Nieuw (11 juli 2026).
    # ---------------------------------------------------------
    def detect_part_of_check(self, text):
        t = text.lower().strip().rstrip("?.")

        # 1. "is een X onderdeel van een Y" / "is een X een onderdeel van Y"
        m = re.match(r"is\s+een\s+(\w+)\s+(?:een\s+)?onderdeel\s+van\s+(?:een\s+)?([\w\s]+)", t)
        if m:
            self.event_bus.publish("intent_part_of_check", {
                "source": m.group(1).strip(),
                "target": m.group(2).strip()
            })
            return True

        # 2. "zit een X in een Y"
        m = re.match(r"zit\s+een\s+(\w+)\s+in\s+(?:een\s+)?([\w\s]+)", t)
        if m:
            self.event_bus.publish("intent_part_of_check", {
                "source": m.group(1).strip(),
                "target": m.group(2).strip()
            })
            return True

        return False
    
    # ---------------------------------------------------------
    # Subtypes-vraag ("welke soorten dier ken je", "noem soorten
    # van dier", "wat zijn allemaal dieren") — omgekeerde is_a-
    # lookup. Nieuw (12 juli 2026).
    # ---------------------------------------------------------
    def detect_subtypes_query(self, text):
        t = text.lower().strip().rstrip("?.")

        # 1. "welke soorten X ken je" / "welke soorten van X ken je"
        m = re.match(r"welke\s+soorten\s+(?:van\s+)?(\w+)\s+ken\s+je", t)
        if m:
            self.event_bus.publish("intent_subtypes_query", {
                "target": m.group(1).strip()
            })
            return True

        # 2. "noem soorten van X" / "noem soorten X"
        m = re.match(r"noem\s+soorten\s+(?:van\s+)?(\w+)", t)
        if m:
            self.event_bus.publish("intent_subtypes_query", {
                "target": m.group(1).strip()
            })
            return True

        # 3. "wat zijn allemaal X" (bv. "wat zijn allemaal dieren")
        m = re.match(r"wat\s+zijn\s+allemaal\s+([\w\s]+)", t)
        if m:
            self.event_bus.publish("intent_subtypes_query", {
                "target": m.group(1).strip()
            })
            return True

        return False

    # ---------------------------------------------------------
    # Identiteitsvragen (Kevin vraagt iets over Nova zelf)
    # ---------------------------------------------------------
    def detect_identity_question(self, text):
        t = text.lower().strip().rstrip("?.")

        identity_patronen = {
            "who": [
                "wie ben je", "wie ben jij", "wie is nova", "wie ben jij eigenlijk",
                "vertel over jezelf", "vertel eens over jezelf", "stel jezelf voor"
            ],
            "age": [
                "hoe oud ben je", "hoe oud ben jij", "wat is je leeftijd"
            ],
            "is_ai": [
                "ben je een ai", "ben jij een ai", "ben je ai", "ben jij ai",
                "ben je een robot", "ben jij een robot", "ben je robot", "ben jij robot",
                "ben je kunstmatige intelligentie", "ben jij kunstmatige intelligentie",
                "ben je een computer", "ben jij een computer",
            ],
            "is_human": [
                "ben je een mens", "ben jij een mens", "ben je mens", "ben jij mens",
                "ben je echt", "ben jij echt",
            ],
            "what_are_you": [
                "besef je dat je een programma bent", "besef jij dat je een programma bent",
                "wat ben je eigenlijk", "wat ben jij eigenlijk",
                "wat voor soort programma ben je", "wat voor soort programma ben jij",
            ],
            "character": [
                "wat is je karakter", "hoe zou je jezelf omschrijven",
                "hoe zou jij jezelf omschrijven", "hoe ben je", "hoe ben jij",
                "beschrijf jezelf"
            ],
            "likes": [
                "wat vind je leuk", "wat vind jij leuk", "waar hou je van",
                "waar hou jij van", "wat vind je fijn"
            ],
            "hobbies": [
                "wat zijn je hobby", "wat zijn jouw hobby", "waar hou je je mee bezig",
                "wat doe je graag"
            ],
            "values": [
                "wat zijn je waarden", "wat zijn jouw waarden", "wat vind je belangrijk",
                "wat vind jij belangrijk"
            ],
            "boundaries": [
                "wat zijn je grenzen", "wat zijn jouw grenzen", "wat doe je nooit",
                "wat wil je niet"
            ],
            "current_mood": [
                "hoe voel je je", "hoe voel jij je", "hoe gaat het met je",
                "hoe gaat het met jou", "hoe is het met je", "wat is je stemming"
            ],
            "excitement": [
                "wat maakt je enthousiast", "waar word je blij van", "waar word jij blij van"
            ],
            "uncertainty": [
                "waar word je onzeker van", "wat maakt je onzeker"
            ],
            "motivation": [
                "waarom doe je dit", "waarom doe jij dit", "wat is je doel",
                "wat drijft je", "wat motiveert je"
            ],
            "long_term_goals": [
                "wat wil je bereiken", "wat wil jij bereiken",
                "wat zijn je doelen op lange termijn"
            ],
            "strengths": [
                "waar ben je goed in", "waar ben jij goed in", "wat zijn je sterktes"
            ],
            "growth": [
                "waar wil je nog in groeien", "waar wil jij nog in groeien",
                "wat zijn je groeipunten"
            ],
            "communication_style": [
                "hoe communiceer je het liefst", "heb je gevoel voor humor",
                "heb jij gevoel voor humor"
            ],
            "bond_with_kevin": [
                "wat vind je van mij", "wat vind jij van mij", "hoe is onze band"
            ],
            "self_awareness": [
                "ken je je eigen grenzen", "ken jij je eigen grenzen", "besef je je grenzen"
            ],
            "can_grow": [
                "kan je groeien", "kan jij groeien", "kan jij nog veranderen",
                "kan je nog veranderen"
            ],
        }

        for sub_intent, zinnen in identity_patronen.items():
            for zin in zinnen:
                if zin in t:
                    self.event_bus.publish("intent_identity", {"sub_intent": sub_intent})
                    return True

        return False

    # ---------------------------------------------------------
    # Self-architecture (nieuw, 23 juli 2026) -- HOE Nova werkt
    # (geheugen, denken, leren, privacy, architectuur), in
    # tegenstelling tot detect_identity_question hierboven, dat WIE
    # Nova is beantwoordt (persoonlijkheid/gevoel via identity.json).
    #
    # BEWUST via 'layer4_response' i.p.v. rechtstreeks 'chat_response'
    # (anders dan intent_identity!) -- zo krijgt de uitleg automatisch
    # Nova's toon mee via de tone-pipeline (response_pipeline.py ->
    # chat_response_engine.py -> expression_injector.py), net als
    # weer/tijd/definities. Kevin wil expliciet dat haar identiteit
    # ook hier doorschemert, i.p.v. een kale technische uitleg.
    # ---------------------------------------------------------
    def detect_self_architecture(self, text):
        t = text.lower().strip().rstrip("?.")

        architectuur_patronen = {
            "geheugen": [
                "hoe onthoud je dingen", "hoe onthoud jij dingen",
                "hoe werkt je geheugen", "hoe werkt jouw geheugen",
                "hoe slaan je dingen op", "hoe sla jij dingen op",
                "waar onthoud je dingen", "vergeet je dingen",
                "vergeet jij dingen",
            ],
            "denken": [
                "hoe denk je na", "hoe denk jij na", "hoe werk je van binnen",
                "hoe werkt jij van binnen", "hoe verwerk je een bericht",
                "wat gebeurt er als ik iets tegen je zeg",
                "wat gebeurt er als ik iets tegen jou zeg",
                "wat is een eventbus", "wat is de eventbus",
                "hoe beslis je wat je antwoordt",
            ],
            "leren": [
                "hoe leer je nieuwe woorden", "hoe leer jij nieuwe woorden",
                "hoe leer je bij", "hoe leer jij bij",
                "hoe leer je dingen", "hoe leer jij dingen",
            ],
            "privacy": [
                "draai je in de cloud", "draai jij in de cloud",
                "ben je lokaal", "ben jij lokaal",
                "gebruik je een taalmodel", "gebruik jij een taalmodel",
                "gebruik je een llm", "gebruik jij een llm",
                "stuur je data door", "stuur jij data door",
            ],
            "architectuur_algemeen": [
                "hoe ben je opgebouwd", "hoe ben jij opgebouwd",
                "hoe zit je in elkaar", "hoe zit jij in elkaar",
                "leg je architectuur uit", "leg jouw architectuur uit",
                "wat zijn je lagen", "wat zijn jouw lagen",
                "hoe werk je", "hoe werk jij",
            ],
        }

        for topic, zinnen in architectuur_patronen.items():
            for zin in zinnen:
                if zin in t:
                    self.event_bus.publish("intent_self_architecture", {"topic": topic})
                    return True

        return False
    
    # ---------------------------------------------------------
    # Memory test-commando's
    # ---------------------------------------------------------
    def detect_memory(self, text):
        t = text.strip()

        # "memory stats"
        if t.lower() == "memory stats":
            mem = self.event_bus.modules.get("memory")
            if not mem:
                self.event_bus.publish("chat_response", {"text": "Memory-module niet gevonden."})
                return True
            stats = mem.get_stats()
            msg = (
                f"Memory statistieken:\n"
                f"  Totaal events: {stats.get('totaal_events', 0)}\n"
                f"  Periode: {stats.get('periode', 'onbekend')}\n"
                f"  Events in RAM: {stats.get('events_in_ram', 0)}\n"
                f"  Database grootte: {stats.get('database_grootte_mb', 0)} MB"
            )
            self.event_bus.publish("chat_response", {"text": msg})
            return True

        # "memory search <woord>"
        if t.lower().startswith("memory search "):
            keyword = t[len("memory search "):].strip()
            mem = self.event_bus.modules.get("memory")
            if not mem:
                self.event_bus.publish("chat_response", {"text": "Memory-module niet gevonden."})
                return True
            resultaten = mem.search(keyword, limit=5)
            if not resultaten:
                self.event_bus.publish("chat_response", {
                    "text": f"Geen events gevonden met '{keyword}'."
                })
            else:
                regels = [f"  [{r['event_type']}] {r['data'][:80]}" for r in resultaten]
                msg = f"Gevonden ({len(resultaten)} resultaten voor '{keyword}'):\n" + "\n".join(regels)
                self.event_bus.publish("chat_response", {"text": msg})
            return True

        # "memory similar <woord>"
        if t.lower().startswith("memory similar "):
            woord = t[len("memory similar "):].strip()
            mem = self.event_bus.modules.get("memory")
            if not mem:
                self.event_bus.publish("chat_response", {"text": "Memory-module niet gevonden."})
                return True
            resultaten = mem.find_similar(woord, top_k=3)
            if not resultaten:
                self.event_bus.publish("chat_response", {
                    "text": f"Niets gevonden dat lijkt op '{woord}'."
                })
            else:
                regels = [
                    f"  (score {r['similarity']}) [{r['event_type']}] {r['data'][:60]}"
                    for r in resultaten
                ]
                msg = f"Meest gelijkende events op '{woord}':\n" + "\n".join(regels)
                self.event_bus.publish("chat_response", {"text": msg})
            return True

        return False

    # ---------------------------------------------------------
    # Help
    # ---------------------------------------------------------
    def detect_help(self, text):
        t = text.lower().strip().rstrip("?.")

        if t == "help":
            self.event_bus.publish("intent_help", {"topic": ""})
            return True

        if t.startswith("help "):
            topic = t[5:].strip()
            self.event_bus.publish("intent_help", {"topic": topic})
            return True

        return False

    # ---------------------------------------------------------
    # Activity Awareness (Deel A) — "ik ga <activiteit>"
    # ---------------------------------------------------------
    # Generiek patroon: werkt voor ONBEPERKT veel activiteiten, geen
    # aparte code nodig per nieuwe activiteit. Publiceert een
    # "activity_started"-event dat Layer 2 (pattern_matcher.py) en
    # later Layer 5/Activity-Aware Interaction gebruiken.
    # 100% symbolisch: puur patroonherkenning + een klein
    # synoniemen-tabelletje, geen ML/generatie.

    # Klein, uitbreidbaar tabelletje: spreektaal-variant -> vaste,
    # genormaliseerde activiteitsnaam. Puur onderhoud van een lijst,
    # geen nieuwe logica. Nieuwe activiteiten die hier niet in staan
    # werken nog steeds -- ze krijgen dan gewoon hun eigen letterlijke
    # naam als sleutel.
    ACTIVITEIT_SYNONIEMEN = {
        "koffiezetten": "koffie",
        "koffie zetten": "koffie",
        "koffie drinken": "koffie",
        "netflixen": "netflix",
        "netflix kijken": "netflix",
        "gamen": "gamen",
        "games spelen": "gamen",
        "coderen": "coderen",
        "programmeren": "coderen",
        "code schrijven": "coderen",
    }

    def detect_activity(self, text):
        t = text.lower().strip().rstrip("?.")

        prefixes = ["ik ga ", "ik ga nu ", "ik begin met ", "ik start met "]
        for p in prefixes:
            if t.startswith(p):
                activiteit = t[len(p):].strip()
                if not activiteit:
                    return False

                # Zelfde patroon als topic_detected:<naam> (zie
                # _emit_topic()): de activiteitsnaam zit IN de
                # event-type-string zelf, niet enkel in de data-dict.
                # Zo kan pattern_matcher.py (Layer 2) dit generiek
                # herkennen via dezelfde prefix-check die het al
                # gebruikt voor topic_detected, zonder aparte logica
                # per event-soort.
                dbg(f"{C_MAGENTA}→ activity_started:{activiteit}{C_RESET}")
                self.event_bus.publish(f"activity_started:{activiteit}", {
                    "naam": activiteit,
                    "tijd": self._huidige_tijd_iso()
                })
                return True

        return False

    def _huidige_tijd_iso(self):
        """Kleine helper zodat detect_activity() niet zelf datetime
        hoeft te importeren bovenaan het bestand -- lokale import,
        enkel gebruikt wanneer een activiteit ook echt herkend wordt."""
        from datetime import datetime
        return datetime.now().isoformat()

    # ---------------------------------------------------------
    # Pending Question — antwoord op Nova's eigen vraag verwerken
    # ---------------------------------------------------------
    # Bewust EEN EIGEN, losstaande woordenlijst hier -- NIET de
    # signal_classifier uit microlearning.py, want die herkent iets
    # anders (frustratie/waardering/interesse/verwarring/focus/kilte,
    # bedoeld om traits.json langzaam bij te sturen), geen bevestiging/
    # ontkenning. Een apart model zou hier overkill zijn: dit is een
    # kleine, gesloten set korte woorden zonder de taalkundige
    # dubbelzinnigheid die een classifier zou rechtvaardigen. 100%
    # symbolisch: woordenlijst-matching, geen ML, geen toon/sentiment-
    # interpretatie (zie interruption_learning_roadmap.md's
    # eerlijkheids-sectie: Nova mag DAT iets bevestigd/geweigerd werd
    # zien, nooit HOE geïrriteerd of enthousiast dat klonk).
    BEVESTIGING_WOORDEN = {
        "ja", "jup", "jep", "yep", "yes", "joa", "jow",
        "oke", "oké", "ok", "okay", "okee", "okeej",
        "zeker", "zeker weten", "zeker wel",
        "tuurlijk", "natuurlijk", "vanzelfsprekend",
        "prima", "goed", "prima hoor", "goed hoor",
        "graag", "graag gedaan", "graag wel",
        "yolo", "toch wel", "waarom niet",
        "kom maar", "ga je gang", "zeg het maar",
        "mag", "mag wel", "is goed", "is oke", "is oké",
    }

    ONTKENNING_WOORDEN = {
        "nee", "neu", "nope", "no", "non",
        "nee hoor", "neu hoor", "liever niet",
        "nu niet", "niet nu", "later", "straks liever",
        "niet nodig", "hoeft niet", "laat maar",
        "niet storen", "wacht liever", "wacht nog even",
        "nog niet", "een andere keer", "niet echt",
    }

    def _interpreteer_ja_nee(self, text):
        """
        Geeft "bevestiging", "ontkenning" of None terug (bij twijfel/
        onherkend) op basis van woordenlijst-matching. Geen ML, geen
        confidence-score -- gewoon een letterlijke match tegen een
        vaste set, zoals hierboven beschreven.
        """
        t = text.lower().strip().rstrip("?.!")

        if t in self.BEVESTIGING_WOORDEN:
            return "bevestiging"
        if t in self.ONTKENNING_WOORDEN:
            return "ontkenning"

        # Ook een korte zin die MET zo'n woord begint accepteren
        # (bv. "ja hoor, ga je gang" -- niet enkel exacte matches),
        # zolang de zin kort blijft. Een lange, inhoudelijke zin die
        # toevallig met "ja" begint ("ja, ik denk dat het weer...")
        # willen we NIET als kort bevestigingsantwoord meepikken --
        # vandaar de lengte-grens.
        if len(t.split()) <= 4:
            for woord in self.BEVESTIGING_WOORDEN:
                if t.startswith(woord):
                    return "bevestiging"
            for woord in self.ONTKENNING_WOORDEN:
                if t.startswith(woord):
                    return "ontkenning"

        return None

    def _verwerk_pending_antwoord(self, text):
        """
        Wordt aangeroepen VOORDAT de normale intent-routing draait,
        enkel als pending_question.is_open() True is. Interpreteert
        het antwoord en publiceert "pending_question:answered" -- de
        module die de vraag stelde (bv. straks de interruption-
        tracker) luistert daarop en weet zelf wat ermee te doen op
        basis van "vraag_type". Dit mechanisme zelf beslist nooit wat
        het antwoord BETEKENT voor de rest van Nova, het levert enkel
        het geïnterpreteerde signaal af.

        Geeft True terug als het bericht als antwoord behandeld is
        (dus de normale routing NIET meer moet draaien), anders False.
        """
        pending = self.event_bus.modules.get("pending_question")
        if pending is None or not pending.is_open():
            return False

        vraag_type = pending.get_type()

        # Fase 4 (correcties, 28 juli 2026): EERST checken of dit een
        # correctie is ("nee ik bedoelde X"), VOORDAT de gewone ja/nee
        # -interpretatie draait. Dat is bewust, want
        # _interpreteer_ja_nee() heeft een lengte-limiet van 4 woorden
        # -- een langere correctiezin zoals "nee dat is het niet, ik
        # bedoel weer" zou daar anders NIET als ontkenning herkend
        # worden en gewoon "onherkend" opleveren.
        if self._verwerk_correctie(text, vraag_type):
            return True

        signaal = self._interpreteer_ja_nee(text)

        if signaal is None:
            # Onherkend antwoord -- de vraag blijft open staan (mag
            # nog steeds verlopen via de verval-tijd), Kevin krijgt
            # een kans om het nog eens duidelijker te zeggen. We
            # sturen HIER niets door naar de normale routing, want een
            # onduidelijk antwoord op een net gestelde vraag moet niet
            # als een volledig los, nieuw bericht behandeld worden.
            dbg(f"{C_YELLOW}→ pending_question: onherkend antwoord op '{vraag_type}'{C_RESET}")
            return True

        dbg(f"{C_YELLOW}→ pending_question:answered ({vraag_type} → {signaal}){C_RESET}")
        self.event_bus.publish("pending_question:answered", {
            "vraag_type": vraag_type,
            "signaal": signaal
        })
        pending.clear()
        return True

    # ---------------------------------------------------------
    # Intent-tabel (i.p.v. losse if-keten in route())
    # ---------------------------------------------------------
    # Elke regel = (topic_naam, detect_functie). De VOLGORDE van deze
    # lijst = de prioriteit, exact zoals voorheen de volgorde van de
    # if-blokken in route() dat bepaalde. Wordt als instance-attribuut
    # opgebouwd in __init__ (self._build_intent_tabel()), niet als
    # class-attribuut, omdat de functies aan 'self' gebonden methoden
    # zijn die pas bestaan nadat de instance is aangemaakt.
    #
    # Let op: dit is GEEN vervanging van alle stappen in route(). Een
    # aantal stappen (pending question, reboot, teach, example,
    # confirm, relation-flow via semantic, sense-choice, ja/nee-
    # confirm, fallback) passen niet in dit (topic, detect)-patroon
    # en blijven bewust als aparte, expliciete stappen in route()
    # staan -- zie de commentaren daar voor waarom.
    def _build_intent_tabel_deel1(self):
        """
        Stappen 3 t/m 7 (zie route()) -- alles VOOR de definition-
        check, want die heeft een dynamische topic-naam en past niet
        in dit (topic, detect)-patroon.
        """
        return [
            ("greeting",         self.detect_greeting),
            ("time",             self.detect_time),
            ("weather",          self.detect_weather),
            # chess vóór math: zetten zoals "e2e4" mogen niet als
            # math gezien worden
            ("chess",            self.detect_chess),
            ("help",             self.detect_help),
            ("memory",           self.detect_memory),
            # self_architecture vóór identity: "hoe werk je" gaat over
            # architectuur, niet over persoonlijkheid, en moet niet
            # per ongeluk door de identity-patronen opgepikt worden
            ("self_architecture", self.detect_self_architecture),
            ("identity",         self.detect_identity_question),
            # conversie vóór math: een conversiezin ("hoeveel ml is
            # 250 cl?") moet eerst als conversie herkend en vertaald
            # worden naar .to(...)-syntax, vóór detect_math() de zin
            # eventueel al op een andere manier oppikt
            ("conversie",        self.detect_conversie),
            ("math",             self.detect_math),
        ]

    def _build_intent_tabel_deel2(self):
        """
        Stappen 10 t/m 10d (zie route()) -- alles NA de relation-flow
        via semantic._detect_relation(), die zelf geen vaste topic-
        naam heeft en dus apart in route() blijft staan.
        """
        return [
            ("relatie",          self.detect_relation_check),
            ("part_of",          self.detect_part_of_check),
            ("subtypes",         self.detect_subtypes_query),
            ("activity",         self.detect_activity),
            # preference_query VOOR preference (Fase 4 vóór Fase 3):
            # een VRAAG ("wat kan ik drinken?") moet niet per ongeluk
            # door detect_preference() als een NIEUWE uitspraak gelezen
            # worden. detect_preference_query() herkent vraag-vormen,
            # detect_preference() herkent uitspraak-vormen -- ze
            # overlappen normaal niet qua triggerzinnen, maar de
            # volgorde hier is een extra vangnet.
            ("preference_query", self.detect_preference_query),
            # preference bewust als ALLERLAATSTE (na activity): een
            # zin als "ik ga slapen" of "ik speel graag schaak" moet
            # eerst de kans krijgen om als activity/chess herkend te
            # worden -- pas als niets specifieker matcht, proberen we
            # de generieke voorkeur-patronen (Fase 3, zie detect_
            # preference() hierboven).
            ("preference",       self.detect_preference),
        ]

    # ---------------------------------------------------------
    # Intent Classifier (Fase 3, 28 juli 2026) — ML-fallback wanneer
    # GEEN enkele bestaande detect_*() een match vond. Zie
    # intent_classifier_roadmap.md voor de volledige onderbouwing.
    #
    # Drempels (Kevin's keuze, 28 juli 2026):
    #   >= 0.70            -> direct de categorie afhandelen, geen vraag
    #   0.35 t/m 0.70 (excl)-> pending_question stellen, wacht op ja/nee
    #   < 0.35              -> loggen naar unmatched_intents.jsonl,
    #                          daarna gewoon door naar fallback()
    # ---------------------------------------------------------
    DREMPEL_DIRECT = 0.70
    DREMPEL_VRAAG = 0.35

    # Nederlandse, spreektalige labels per categorie -- gebruikt in de
    # bevestigingsvraag ("Bedoel je dat je wil <label>?"). Los van de
    # interne Engelse categorienamen zelf, puur voor leesbare zinnen.
    # 29 juli 2026: TWEE aparte mappings i.p.v. één -- een eerdere
    # versie hergebruikte dezelfde tekst in "Bedoel je dat je
    # {label_nl}?" EN "Oké, dus je wil {label_nl}.", maar Nederlandse
    # werkwoordsvervoeging verschilt tussen die twee zinsconstructies
    # ("je WEET" vs "je wil WETEN"). Bleek concreet fout te lopen bij
    # chess_evaluation ("Bedoel je dat je weten..." klonk krom). Nu
    # heeft elke categorie een losse, grammaticaal juiste tekst per
    # zinsvorm, zodat toekomstige nieuwe categorieën dit meteen goed
    # kunnen instellen zonder dezelfde valkuil.
    _CLASSIFIER_LABEL_NL_VRAAG = {
        "greeting": "even gedag wil zeggen",
        "time": "weet hoe laat het is",
        "weather": "het weer wil weten",
        "chess": "wil schaken",
        "self_architecture": "wil weten hoe ik in elkaar zit",
        "identity": "iets over mij wil weten",
        "math": "een berekening wil laten maken",
        "activity": "een activiteit wil starten",
        "preference": "een voorkeur wil delen",
        "chess_evaluation": "wil weten wat er mis ging met een zet",
    }

    _CLASSIFIER_LABEL_NL_BEVESTIGING = {
        "greeting": "gedag zeggen",
        "time": "weten hoe laat het is",
        "weather": "het weer weten",
        "chess": "schaken",
        "self_architecture": "weten hoe ik in elkaar zit",
        "identity": "iets over mij weten",
        "math": "een berekening laten maken",
        "activity": "een activiteit starten",
        "preference": "een voorkeur delen",
        "chess_evaluation": "weten wat er mis ging met een zet",
    }

    # Generieke actie-koppeling per Intent Classifier-categorie (30
    # juli 2026): label -> functie die de ECHTE actie uitvoert i.p.v.
    # enkel een neutrale bevestigende tekst. Elke functie krijgt de
    # ORIGINELE tekst mee (nodig voor bv. weather/time, die de tekst
    # zelf doorgeven in hun payload) en publiceert zelf het juiste
    # event -- exact zoals de bestaande detect_*()-tegenhangers dat al
    # deden.
    #
    # BEWUST NIET in dit dictionary (blijven op de neutrale
    # bevestigingstekst hieronder, "Oké, dus je wil X..."):
    #   - identity / self_architecture: vereisen een sub_intent uit
    #     een lijst van ~20 opties (who/age/is_ai/geheugen/denken/...)
    #     die uit de brede classifier-categorie niet af te leiden is
    #     -- een gok hier zou een verzonnen sub_intent betekenen.
    #     Mogelijk vervolgpunt (Kevin, 30 juli 2026), nog niet gebouwd.
    #   - activity: vereist de letterlijke activiteitsnaam UIT de
    #     tekst gehaald ("ik ga koken" -> "koken") -- bij een
    #     classifier-gok is niet zeker dat die naam er überhaupt
    #     herkenbaar in staat.
    #   - math: module zelf nog niet af (Kevin, 30 juli 2026).
    #   - preference: heeft al een eigen gespecialiseerde classifier
    #     (sentiment_classifier.py) voor de nuance -- koppeling met
    #     dit register is een apart te bekijken vraagstuk, geen
    #     "kan niet", gewoon nog niet beslist (Kevin, 30 juli 2026).
    def _actie_chess_classifier(self, text):
        """
        Zelfde sub-actie-keuze als de oude, hardcoded if-tak in
        _voer_classifier_intent_uit() hierboven -- enkel verplaatst
        naar het generieke register, gedrag ongewijzigd.
        """
        chess_engine = self.event_bus.modules.get("chess_engine")
        partij_voorbij = (
            chess_engine is None
            or not hasattr(chess_engine, "board")
            or chess_engine.board.is_game_over()
        )
        if partij_voorbij:
            self.event_bus.publish("intent_chess_new", {})
        else:
            self.event_bus.publish("intent_chess_board", {})

    def _actie_greeting_classifier(self, text):
        self.event_bus.publish("intent_greeting", {"sender": self._get_sender_name()})

    _CLASSIFIER_ACTIE_REGISTER = {
        "chess": _actie_chess_classifier,
        "chess_evaluation": lambda self, text: self.event_bus.publish(
            "intent_chess_evaluation_query", {}
        ),
        "weather": lambda self, text: self.event_bus.publish(
            "intent_weather", {"text": text}
        ),
        "time": lambda self, text: self.event_bus.publish(
            "intent_time_query", {"text": text}
        ),
        "greeting": _actie_greeting_classifier,
    }

    # Fase 4 (correcties, 28 juli 2026): omgekeerde mapping -- welk
    # Nederlands woord dat Kevin typt na "ik bedoelde ..." hoort bij
    # welk intern label. Bewust een VASTE, expliciete lijst (geen ML)
    # als eerste, betrouwbare poging -- enkel als een woord hier NIET
    # in staat, valt _herken_correctie_label() terug op de classifier
    # zelf als vangnet (zie die methode voor de reden).
    _CORRECTIE_WOORDEN_NL = {
        "schaken": "chess", "schaak": "chess",
        "weer": "weather", "het weer": "weather",
        "tijd": "time", "hoe laat": "time",
        "rekenen": "math", "wiskunde": "math", "berekening": "math",
        "identiteit": "identity", "jezelf": "identity",
        "wie je bent": "identity",
        "architectuur": "self_architecture", "je brein": "self_architecture",
        "hoe je werkt": "self_architecture",
        "activiteit": "activity", "iets doen": "activity",
        "voorkeur": "preference", "wat ik leuk vind": "preference",
        "begroeten": "greeting", "gedag zeggen": "greeting",
    }

    # Woorden waarmee een ontkenning/correctie kan beginnen -- los van
    # ONTKENNING_WOORDEN hierboven, want DIE lijst is beperkt tot max.
    # 4 woorden (regel _interpreteer_ja_nee) en zou dus een langere
    # correctiezin zoals "nee dat is het niet, ik bedoel weer" missen.
    _CORRECTIE_START_WOORDEN = ("nee", "neen", "nope", "non")

    def _detecteer_correctie(self, text):
        """
        Herkent of 'text' een correctie op een classifier-vraag is,
        zoals "nee ik bedoelde weer" of "neen, weer" of "nee dat is
        het niet, ik bedoel weer". Geeft het RUWE correctie-woord terug
        (bv. "weer"), of None als er geen correctiepatroon herkend
        wordt.

        Volgorde (eerste match wint):
          1. bevat "bedoel" of "bedoelde"? -> alles NA dat woord
          2. bevat een komma? -> alles NA de LAATSTE komma
          3. anders: geen correctie herkend (val terug op de gewone
             _interpreteer_ja_nee() ontkenning-detectie)

        Bewust GEEN lengte-limiet hier (in tegenstelling tot
        _interpreteer_ja_nee) -- een correctiezin mag zo lang zijn als
        nodig, zolang ze met een ontkenningswoord begint.
        """
        t = text.lower().strip().rstrip("?.!")

        begint_met_ontkenning = any(
            t.startswith(woord) for woord in self._CORRECTIE_START_WOORDEN
        )
        if not begint_met_ontkenning:
            return None

        for sleutelwoord in ("bedoelde", "bedoel"):
            if sleutelwoord in t:
                _, _, rest = t.partition(sleutelwoord)
                rest = rest.strip(" ,.")
                if rest:
                    return rest

        if "," in t:
            rest = t.rsplit(",", 1)[-1].strip(" .")
            if rest:
                return rest

        return None

    # Fase 4 (correcties, 28 juli 2026): minimale confidence die de
    # classifier moet halen op een LOS correctiewoord (bv. enkel
    # "koken") vooraleer we dat vertrouwen als vangnet. Een los woord
    # scoort doorgaans lager/onbetrouwbaarder dan een volledige zin,
    # dus bewust STRENGER dan de gewone DREMPEL_VRAAG (0.35) -- anders
    # zou een woord dat bij GEEN van de 9 categorieën hoort (zoals
    # "koken") toch een willekeurig, fout label toegewezen krijgen en
    # als "gecorrigeerd" (dus MET ZEKERHEID juist) worden opgeslagen.
    DREMPEL_CORRECTIE_VANGNET = 0.40

    def _herken_correctie_label(self, correctie_woord):
        """
        Zet het ruwe correctie-woord (bv. "weer") om naar een intern
        label (bv. "weather").

        Eerst de vaste, expliciete _CORRECTIE_WOORDEN_NL-lijst
        proberen (betrouwbaar, voorspelbaar). Staat het woord daar
        niet in, dan de classifier zelf als vangnet gebruiken -- maar
        ENKEL als de score boven DREMPEL_CORRECTIE_VANGNET ligt. Onder
        die drempel geven we liever eerlijk "onbekend" terug (zie
        _verwerk_correctie(), die dit dan naar
        onbekende_correcties.jsonl logt) dan een gegokt label blind
        als "gecorrigeerd, met zekerheid juist" te bewaren.
        """
        if correctie_woord in self._CORRECTIE_WOORDEN_NL:
            return self._CORRECTIE_WOORDEN_NL[correctie_woord]

        if self.intent_classifier:
            resultaat = self.intent_classifier.predict(correctie_woord)
            if resultaat and resultaat["confidence"] >= self.DREMPEL_CORRECTIE_VANGNET:
                dbg(f"{C_YELLOW}→ correctiewoord '{correctie_woord}' niet in "
                    f"vaste lijst, classifier gokt: {resultaat['label']} "
                    f"(confidence {resultaat['confidence']}){C_RESET}")
                return resultaat["label"]
            elif resultaat:
                dbg(f"{C_YELLOW}→ correctiewoord '{correctie_woord}' -- "
                    f"classifier te onzeker ({resultaat['confidence']} < "
                    f"{self.DREMPEL_CORRECTIE_VANGNET}), niet vertrouwd"
                    f"{C_RESET}")

        return None

    def _log_gecorrigeerd_voorbeeld(self, tekst, label):
        """
        Slaat een DOOR KEVIN BEVESTIGDE correctie op in
        data/gecorrigeerde_voorbeelden.jsonl -- bewust een apart
        bestand, LOS van training_data.json (dat blijft Kevin's eigen,
        handmatig beheerde bestand) en los van unmatched_intents.jsonl
        (dat bevat ONZEKERE gokken zonder bevestigd label, dit hier
        bevat enkel MET ZEKERHEID correct gelabelde voorbeelden).

        Een toekomstige Fase 5 (periodieke hertraining, elke nacht/4
        uur -- Kevin's keuze, 28 juli 2026) leest training_data.json
        EN dit bestand samen om te trainen, zodat niets verloren gaat
        zonder dat Kevin zelf iets hoeft te kopiëren.
        """
        import json
        import os
        from datetime import datetime

        pad = os.path.join("data", "gecorrigeerde_voorbeelden.jsonl")
        regel = {
            "tekst": tekst,
            "label": label,
            "bron": "gecorrigeerd",
            "tijdstip": datetime.now().isoformat()
        }
        try:
            os.makedirs("data", exist_ok=True)
            with open(pad, "a", encoding="utf-8") as f:
                f.write(json.dumps(regel, ensure_ascii=False) + "\n")
        except Exception as e:
            dbg(f"{C_RED}kon gecorrigeerde_voorbeelden.jsonl niet "
                f"schrijven: {e}{C_RESET}")

    def _log_onbekende_correctie(self, origineel, correctie_woord):
        """
        Slaat een correctiewoord op dat bij GEEN van de 9 bestaande
        categorieën goed paste (niet in _CORRECTIE_WOORDEN_NL, en de
        classifier was er ook niet zeker genoeg van). Dit is Kevin's
        hint-lijst voor mogelijke NIEUWE categorieën/modules die nog
        niet bestaan (bv. "koken" zou hier een paar keer kunnen
        opduiken en dan blijkt dat een eigen intent te verdienen) --
        bewust LOS van gecorrigeerde_voorbeelden.jsonl (dat bevat enkel
        MET ZEKERHEID juiste labels voor bestaande categorieën) en van
        unmatched_intents.jsonl (dat bevat classifier-onzekerheid over
        HELE zinnen, niet over een specifiek correctiewoord).
        """
        import json
        import os
        from datetime import datetime

        pad = os.path.join("data", "onbekende_correcties.jsonl")
        regel = {
            "originele_zin": origineel,
            "correctie_woord": correctie_woord,
            "tijdstip": datetime.now().isoformat()
        }
        try:
            os.makedirs("data", exist_ok=True)
            with open(pad, "a", encoding="utf-8") as f:
                f.write(json.dumps(regel, ensure_ascii=False) + "\n")
        except Exception as e:
            dbg(f"{C_RED}kon onbekende_correcties.jsonl niet "
                f"schrijven: {e}{C_RESET}")

    def _verwerk_correctie(self, text, vraag_type):
        """
        Wordt aangeroepen vanuit _verwerk_pending_antwoord() ZODRA een
        correctiepatroon herkend is ("nee ik bedoelde X") op een
        classifier-vraag. Handelt het VOLLEDIGE correctie-scenario af:
        label herkennen, opslaan als trainingsvoorbeeld, de juiste
        actie alsnog uitvoeren, en de pending question sluiten.

        Geeft True terug als de correctie volledig verwerkt is,
        anders False (dan valt de aanroeper terug op de normale
        ja/nee-afhandeling).
        """
        pending = self.event_bus.modules.get("pending_question")

        if not vraag_type.startswith("classifier_intent_") or \
           self._laatste_classifier_vraag is None:
            return False

        correctie_woord = self._detecteer_correctie(text)
        if correctie_woord is None:
            return False

        nieuw_label = self._herken_correctie_label(correctie_woord)
        if nieuw_label is None:
            dbg(f"{C_YELLOW}→ correctie herkend maar label onbekend: "
                f"'{correctie_woord}'{C_RESET}")
            # Hint-lijst voor mogelijke nieuwe categorieën (Kevin's
            # keuze, 28 juli 2026) -- LOS van gecorrigeerde_
            # voorbeelden.jsonl, want we weten hier NIET welk label
            # correct is, enkel dat geen van de 9 bestaande paste.
            originele_tekst = self._laatste_classifier_vraag["tekst"]
            self._log_onbekende_correctie(originele_tekst, correctie_woord)
            self.event_bus.publish("chat_response", {
                "text": f"Sorry, ik ken '{correctie_woord}' niet als "
                        f"onderwerp. Kan je het anders formuleren?"
            })
            if pending:
                pending.clear()
            self._laatste_classifier_vraag = None
            return True

        originele_tekst = self._laatste_classifier_vraag["tekst"]
        oud_label = self._laatste_classifier_vraag["label"]

        dbg(f"{C_GREEN}→ correctie: '{originele_tekst}' was gegokt als "
            f"'{oud_label}', Kevin corrigeert naar '{nieuw_label}'{C_RESET}")
        self._log_gecorrigeerd_voorbeeld(originele_tekst, nieuw_label)

        if pending:
            pending.clear()
        self._laatste_classifier_vraag = None

        # Meteen de juiste actie alsnog proberen uit te voeren (Kevin's
        # keuze, 28 juli 2026) -- hergebruikt dezelfde methode als bij
        # een gewone bevestiging, dus chess toont het bord/start een
        # nieuwe partij, de rest geeft de neutrale bevestigende tekst.
        # 30 juli 2026: originele_tekst meegegeven, nodig voor de
        # nieuw ondersteunde acties (weather/time geven de tekst door).
        self._voer_classifier_intent_uit(nieuw_label, originele_tekst)
        return True

    def _probeer_intent_classifier(self, text):
        """
        Wordt aangeroepen als LAATSTE stap in route(), enkel als geen
        enkele bestaande detect_*() iets herkende. Retourneert True als
        dit bericht hierdoor afgehandeld is (vraag gesteld OF direct
        uitgevoerd), anders False (dan gaat route() gewoon door naar
        de normale fallback()).

        BELANGRIJK (eerlijkheid): de classifier kiest ALTIJD het minst
        -slechte label uit haar lijst, ook bij een compleet onbekende
        zin -- ze heeft geen "ik weet het niet"-status. Daarom wordt
        hier NOOIT enkel op confidence vertrouwd zonder drempel, en
        wordt alles onder DREMPEL_VRAAG apart gelogd voor toekomstig
        bijtrainen i.p.v. genegeerd.
        """
        if not self.intent_classifier:
            return False

        resultaat = self.intent_classifier.predict(text)
        if resultaat is None:
            # Nog geen getraind model beschikbaar (bv. te weinig data)
            return False

        label = resultaat["label"]
        confidence = resultaat["confidence"]

        if confidence >= self.DREMPEL_DIRECT:
            dbg(f"{C_GREEN}→ classifier direct: '{label}' "
                f"(confidence {confidence}){C_RESET}")
            self._voer_classifier_intent_uit(label, text)
            return True

        if confidence >= self.DREMPEL_VRAAG:
            pending = self.event_bus.modules.get("pending_question")
            if pending is None:
                # Geen pending_question-module geladen -- kan niet
                # netjes vragen, dus behandel dit dan maar als
                # onzeker genoeg om te loggen i.p.v. te gokken.
                self._log_unmatched_intent(text, resultaat)
                return False

            label_nl = self._CLASSIFIER_LABEL_NL_VRAAG.get(label, label)
            dbg(f"{C_YELLOW}→ classifier twijfel: '{label}' "
                f"(confidence {confidence}) -- vraag bevestiging{C_RESET}")
            pending.set(f"classifier_intent_{label}", verval_seconden=60)
            # Fase 4 (correcties, 28 juli 2026): bewaar de ORIGINELE
            # zin kortstondig in RAM, puur voor de duur tussen vraag en
            # antwoord -- verdwijnt vanzelf zodra het antwoord verwerkt
            # is (zie _verwerk_correctie()) of de vraag verloopt.
            self._laatste_classifier_vraag = {
                "tekst": text,
                "label": label
            }
            self.event_bus.publish("chat_response", {
                "text": f"Bedoel je dat je {label_nl}?"
            })
            return True

        # confidence < DREMPEL_VRAAG -- te onzeker om zelfs te vragen.
        # Loggen voor toekomstig bijtrainen, dan gewoon door naar de
        # normale fallback() (geen True hier -- retourneer False zodat
        # route() zelf fallback(text) nog aanroept).
        self._log_unmatched_intent(text, resultaat)
        return False

    def _log_unmatched_intent(self, text, resultaat):
        """
        Slaat een onherkende/onzekere zin op in data/unmatched_intents
        .jsonl -- één JSON-object per regel, zodat Kevin dit later
        rustig kan doorlopen als hint-lijst voor mogelijke nieuwe
        trainingsvoorbeelden of nieuwe modules. Puur toevoegen, nooit
        overschrijven.
        """
        import json
        import os
        from datetime import datetime

        pad = os.path.join("data", "unmatched_intents.jsonl")
        regel = {
            "tekst": text,
            "hoogste_gok": resultaat["label"],
            "confidence": resultaat["confidence"],
            "tijdstip": datetime.now().isoformat()
        }
        try:
            os.makedirs("data", exist_ok=True)
            with open(pad, "a", encoding="utf-8") as f:
                f.write(json.dumps(regel, ensure_ascii=False) + "\n")
        except Exception as e:
            dbg(f"{C_RED}kon unmatched_intents.jsonl niet schrijven: {e}{C_RESET}")

    def _voer_classifier_intent_uit(self, label, text=""):
        """
        Voert de daadwerkelijke actie uit voor een categorie die de
        classifier herkende -- ofwel direct (confidence >= 0.70), ofwel
        na een bevestigde pending_question (zie
        _on_classifier_pending_answered() hieronder).

        30 juli 2026: gebruikt nu _CLASSIFIER_ACTIE_REGISTER i.p.v.
        een hardcoded "if label == 'chess':". Staat het label in het
        register, dan voert de bijhorende functie de ECHTE actie uit
        (chess, chess_evaluation, weather, time, greeting -- zie de
        uitleg bij _CLASSIFIER_ACTIE_REGISTER hierboven voor welke
        categorieën BEWUST nog niet in dit register zitten en waarom).
        Staat het label er niet in, dan blijft het oude gedrag gewoon
        bestaan: een neutrale bevestigende chat_response.

        'text' is de ORIGINELE, ruwe tekst van Kevin's bericht -- nodig
        voor categorieën als weather/time die de tekst zelf doorgeven
        aan hun event-payload. Heeft een veilige lege-string-default,
        zodat een eventuele oude aanroep zonder dit argument niet
        meteen crasht (al geven alle drie de aanroeppunten hieronder
        het nu netjes door).
        """
        actie = self._CLASSIFIER_ACTIE_REGISTER.get(label)
        if actie is not None:
            actie(self, text)
            self._emit_topic(label, bron="classifier")
            return

        # Overige categorieën (identity, self_architecture, activity,
        # math, preference, en elk toekomstig onbekend label): neutrale
        # bevestigende tekst, gewoon het onderwerp benoemen. Geen
        # concrete sub-actie mogelijk -- zie roadmap-eerlijkheid: de
        # classifier kent enkel het label, geen sub-informatie.
        label_nl = self._CLASSIFIER_LABEL_NL_BEVESTIGING.get(label, label)
        self.event_bus.publish("chat_response", {
            "text": f"Oké, dus je wil {label_nl}. Zeg maar wat je precies bedoelt!"
        })
        self._emit_topic(label, bron="classifier")

    def _on_classifier_pending_answered(self, data):
        """
        Subscriber op 'pending_question:answered'. Dit event wordt
        gepubliceerd door ELKE module die met pending_question.py
        werkt (bv. ook interruption_tracker.py voor "mag_ik_storen"),
        dus we filteren hier expliciet op onze eigen vraag_type-prefix
        ("classifier_intent_") om niet op andermans vragen te
        reageren.
        """
        vraag_type = data.get("vraag_type", "")
        if not vraag_type.startswith("classifier_intent_"):
            return

        label = vraag_type[len("classifier_intent_"):]
        signaal = data.get("signaal")

        if signaal == "bevestiging":
            dbg(f"{C_GREEN}→ classifier-vraag bevestigd: {label}{C_RESET}")
            # 30 juli 2026: originele tekst nodig voor de nieuw
            # ondersteunde acties (weather/time). Deze komt niet mee
            # via 'data' (dat is pending_question.py's eigen payload),
            # maar staat nog in _laatste_classifier_vraag -- gezet in
            # _probeer_intent_classifier() bij het stellen van de
            # vraag, en nog niet gewist op dit punt. Veilige fallback
            # naar lege string als die er onverwacht toch niet is.
            originele_tekst = ""
            if self._laatste_classifier_vraag:
                originele_tekst = self._laatste_classifier_vraag.get("tekst", "")
            self._voer_classifier_intent_uit(label, originele_tekst)
        else:
            dbg(f"{C_YELLOW}→ classifier-vraag ontkend: {label}{C_RESET}")
            # Bewust GEEN unmatched_intents-logging hier: Kevin heeft
            # actief "nee" gezegd op de classifier's gok, dus we weten
            # dat dit specifieke label fout was -- maar we weten nog
            # niet wat het WEL had moeten zijn (zie roadmap, "geval 1").
            # Een toekomstige uitbreiding (Fase 4) kan Kevin hier de
            # kans geven het zelf te zeggen ("nee ik bedoelde X").

    # ---------------------------------------------------------
    # Topic events (Layer 2 topic-bewustzijn)
    # ---------------------------------------------------------
    def _emit_topic(self, naam, bron="detect"):
        """
        Stuurt een 'topic_detected:<naam>' event de EventBus op.
        Layer 2 (pattern_matcher.py) telt dit generiek mee op uur/dag,
        zodat er per onderwerp (schaken, weer, ...) patronen kunnen
        ontstaan. Geen nieuwe logica hier -- enkel doorgeven.

        Fase 6 (leren uit Layer 0, 28 juli 2026): 'bron' onderscheidt
        WAAR dit topic vandaan kwam -- "detect" (een bestaande,
        betrouwbare detect_*()-match, de default) versus "classifier"
        (de Intent Classifier gokte dit, Fase 3/4). Dit veld belandt
        mee in Layer 0 (memory.py slaat elk event + z'n volledige data
        op), en een latere hertrainings-uitbreiding gebruikt dit om
        ENKEL "detect"-topics als nieuw trainingsvoorbeeld te
        vertrouwen -- classifier-gokken opnieuw laten meetrainen zou
        een zelfbevestigend risico zijn (Kevin's keuze, 28 juli 2026).
        """
        self.event_bus.publish(f"topic_detected:{naam}", {"bron": bron})

    # ---------------------------------------------------------
    # Fallback
    # ---------------------------------------------------------
    def fallback(self, text):
        dbg(f"{C_RED}→ fallback{C_RESET}")
        self.event_bus.publish("intent_fallback", {"text": text})

    # ---------------------------------------------------------
    # MAIN ROUTER
    # ---------------------------------------------------------
    def route(self, data, event_type=None):
        text = data.get("text", "").strip()
        superscripts = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789-")
        text = text.translate(superscripts)
        text = text.replace("×", "*")
        dbg(f"{C_RESET}Ontvangen: '{text}'")

        # Layer 6, Fase 6 (Adaptive Learning, 17 juli 2026): elk ruw
        # bericht van Kevin publiceren als apart, algemeen event, VOOR
        # de eigenlijke intent-routing begint. Nodig omdat er tot nu
        # toe geen centraal "elk bericht"-event bestond — enkel
        # intent_fallback bevatte de ruwe tekst, en dat mist elk
        # bericht dat WEL een herkende intent triggert (bv. "dank je
        # Nova" zou als greeting/fallback gerouteerd worden, maar
        # microlearning.py moet ALLE berichten kunnen zien om
        # frustratie/waardering/interesse/kilte te herkennen, niet
        # enkel de onherkende). Puur een extra publicatie, verandert
        # niets aan de bestaande routing hieronder.
        if text:
            self.event_bus.publish("raw_user_message", {"text": text})

        # -1 Pending question (nieuw) -- MOET voor ALLES anders
        # gecontroleerd worden, zelfs voor reboot: als Nova net een
        # vraag stelde en Kevin antwoordt "ja", mag dat nooit als een
        # gewoon, los bericht door de rest van de routing lopen.
        if self._verwerk_pending_antwoord(text):
            return

        # -1C Pending Wikipedia-disambiguatie-keuze (31 juli 2026, Bug
        # #8-vervolg) -- zelfde voorrang-redenering als hierboven en als
        # de sense-voorkeur-check: als Nova net een genummerde
        # Wikipedia-keuzevraag stelde ("1. Mercurius (planeet) / 2. ..."),
        # mag dat nummer nooit doorlopen naar de bestaande, generieke
        # "text.isdigit()"-sense-choice-afhandeling verderop in deze
        # functie (die is bedoeld voor concepts.json-sense-keuzes, niet
        # voor Wikipedia-disambiguatie) -- vandaar VÓÓR die check.
        wiki_teacher = self.event_bus.modules.get("wikipedia_teacher")
        if wiki_teacher is not None and wiki_teacher.verwerk_wiki_keuze(text):
            return

        # -1D Pending "wat weet je over X"-vervolgantwoord (1 augustus
        # 2026, nieuwe module concept_overview.py) -- zelfde voorrang-
        # redenering als -1C hierboven: als Nova net het korte overzicht
        # toonde en vroeg "typ 'ja' of een nummer", mag dat antwoord
        # nooit door de generieke sense-choice-check hieronder opgevangen
        # worden.
        concept_overview = self.event_bus.modules.get("concept_overview")
        if concept_overview is not None and concept_overview.verwerk_overview_antwoord(text):
            return

        # -1B Pending sense-voorkeur (Bug #10-fix, stap 7) -- zelfde
        # voorrang-redenering als hierboven: als Kevin net gevraagd is
        # een nummer te kiezen na "onthoud sense <woord>", mag dat
        # nummer nooit als een los, nieuw bericht door de rest van de
        # routing lopen (bv. per ongeluk als math-expressie "2"
        # herkend worden).
        if self._verwerk_pending_sense_voorkeur(text):
            return

        # 0 Reboot (altijd als allereerste gecontroleerd, voorrang op alles)
        if self.detect_reboot(text):
            return
        
        # 1 Teach
        if self.handle_teach(text):
            return

        # 1B Example
        if self.handle_example(text):
            return

        # 2A Sense-voorkeur commando (Bug #10-fix, stap 7) -- MOET voor
        # handle_preference() gecontroleerd worden: "onthoud sense X"
        # begint met "onthoud " en zou anders door
        # _ontleed_voorkeur_zin() als een onherkend voorkeur-patroon
        # worden afgevangen (met een verwarrende foutmelding), nog
        # vóór dit commando de kans krijgt.
        if self.handle_sense_voorkeur(text):
            return

        # 2B Preferences (Fase 2: expliciet 'onthoud:'/'vergeet:'-commando)
        if self.handle_preference(text):
            return

        # 3 t/m 7 -- via de intent-tabel (zie _build_intent_tabel_deel1()).
        # Zelfde volgorde, zelfde detect_*()-functies als voorheen --
        # enkel de manier waarop ze doorlopen worden is veranderd.
        for topic_naam, detect_functie in self._intent_tabel_deel1:
            if detect_functie(text):
                # 29 juli 2026: als de detect_*()-methode zelf al een
                # specifieker topic emit heeft (zie _topic_al_ge_emit
                # -uitleg in __init__), dan NIET nogmaals het generieke
                # topic_naam uit de tabel emitten -- anders zou
                # bv. een chess_evaluation-vraag dubbel (en onder het
                # verkeerde label "chess") meetellen voor Fase 6's
                # Layer 0-koppeling.
                if self._topic_al_ge_emit:
                    self._topic_al_ge_emit = False
                    return
                # Fase 6: expliciet bron="detect" -- dit is een
                # betrouwbare match van een bestaande detect_*(),
                # geschikt als toekomstig trainingsvoorbeeld.
                self._emit_topic(topic_naam, bron="detect")
                return

        # 8 Definition
        if self.detect_definition(text):
            # Bugfix (1 augustus 2026): detect_definition() dekt sinds
            # bug #27 ook de "andere betekenissen"- en "concept
            # overview"-vragen, die nu ZELF al hun eigen, specifiekere
            # topic emitten (zie de _topic_al_ge_emit-vlag daar, zelfde
            # patroon als detect_chess()'s chess_evaluation-tak). Zonder
            # deze check zou zo'n bericht DUBBEL meetellen: eenmaal
            # correct onder zijn eigen topic, en eenmaal hier onder het
            # verkeerde, misleidende "definitie_<woord>" (het topic van
            # de VORIGE, gewone definitievraag, want deze takken laten
            # _laatste_definitie_woord ongewijzigd).
            if self._topic_al_ge_emit:
                self._topic_al_ge_emit = False
                return

            # Per-woord-timing: gebruik het specifieke woord als het
            # beschikbaar is (gezet in detect_definition() hierboven),
            # met het oude, generieke "definitie" als veilige terugval
            # -- zo kan dit nooit stil breken als _laatste_definitie_woord
            # om een onverwachte reden leeg zou zijn.
            woord = getattr(self, "_laatste_definitie_woord", None)
            self._emit_topic(f"definitie_{woord}" if woord else "definitie")
            return

        # 9 Relation-flow (eerst! anders pikt relation-check het op
        # dat via de tabel hieronder loopt) -- geen _emit_topic hier,
        # geen vaste topic-vorm, dus past niet in de tabel.
        if self.semantic and self.semantic._detect_relation(text):
            return

        # 10 t/m 10d -- via de intent-tabel (zie
        # _build_intent_tabel_deel2()). Zelfde volgorde als voorheen.
        for topic_naam, detect_functie in self._intent_tabel_deel2:
            if detect_functie(text):
                # 29 juli 2026: zelfde vlag-check als bij
                # _intent_tabel_deel1 hierboven (zie die commentaar
                # voor de volledige uitleg).
                if self._topic_al_ge_emit:
                    self._topic_al_ge_emit = False
                    return
                # Fase 6: expliciet bron="detect", zelfde reden als
                # bij _intent_tabel_deel1 hierboven.
                self._emit_topic(topic_naam, bron="detect")
                return

        # Sense-choice (antwoord met nummer)
        if text.isdigit():
            if self.semantic:
                self.semantic.handle_sense_choice(text)
            return

        # Confirm-flow voor semantic. LET OP: als er een pending
        # question open stond, is dit bericht al hierboven (stap -1)
        # afgehandeld en heeft return al plaatsgevonden -- deze regel
        # wordt dus enkel bereikt als er GEEN pending question actief
        # was, bv. een "ja"/"nee" als antwoord op een semantic-vraag
        # ("bedoel je zin A of B?").
        if text in ("ja", "nee"):
            if self.semantic:
                self.semantic.handle_confirm(text)
            return

        # 10e Intent Classifier (Fase 3, 28 juli 2026) -- ML-fallback,
        # ENKEL geprobeerd als GEEN enkele bestaande detect_*()
        # hierboven al iets herkende. Kan het bericht zelf afhandelen
        # (vraag stellen OF direct uitvoeren bij hoge confidence) --
        # geeft dan True terug en we stoppen hier. Bij lage confidence
        # wordt enkel gelogd en gaat de routing gewoon door naar de
        # normale fallback() hieronder.
        if self._probeer_intent_classifier(text):
            return

        # 11 Fallback
        self.fallback(text)

def init_module(event_bus, semantic_module=None, kevin_profile=None, sentiment_classifier=None, intent_classifier=None):
    router = IntentRouter(event_bus, semantic_module, kevin_profile, sentiment_classifier, intent_classifier)
    event_bus.publish("module_loaded", {"name": "intent_router"})
    return router