# modules/debug/debug_commands.py
#
# Verzamelt alle tijdelijke debug-/testcommando's die voorheen los in
# main.py's invoerlus stonden (14 stuks, verspreid, ~320 regels).
# Doel: main.py overzichtelijk houden — main.py checkt nu enkel nog
# "is dit een debug-commando?" en stuurt het door naar hier via het
# 'debug_command'-event, i.p.v. zelf 14 aparte if-blokken te bevatten.
#
# BELANGRIJK: dit is GEEN los EventBus-subscriber-only module zoals
# de meeste andere modules. DebugCommands heeft rechtstreeks toegang
# nodig tot loader.loaded_modules (net zoals main.py dat voorheen
# deed), dus die wordt bij het opstarten meegegeven i.p.v. via de
# EventBus opgevraagd. Dat is bewust simpeler voor iets dat toch enkel
# door Kevin als developer gebruikt wordt, nooit door "Nova zelf".
#
# Puur symbolisch: string-matching + dictionary-dispatch, exact
# dezelfde logica als voorheen in main.py, enkel verplaatst en
# gebundeld. Geen ML/AI bij betrokken.

C_RESET = "\033[0m"
C_RED = "\033[91m"
C_CYAN = "\033[96m"


class DebugCommands:
    def __init__(self, event_bus, loader):
        self.event_bus = event_bus
        self.loader = loader

        # Elke entry: (herken_functie, verwerk_functie)
        # herken_functie(tekst) -> True/False
        # verwerk_functie(tekst) -> None (print zelf alles)
        self._commands = [
            (lambda t: t == "emergence debug", self._emergence_debug),
            (lambda t: t == "emergence", self._emergence),
            (lambda t: t.startswith("emergence feedback"), self._emergence_feedback),
            (lambda t: t.startswith("emergence drempel"), self._emergence_drempel),
            (lambda t: t == "onderhoud", self._onderhoud),
            (lambda t: t in ("geheugen stats", "geheugen stats vers"), self._geheugen_stats),
            (lambda t: t == "geheugen gezondheid", self._geheugen_gezondheid),
            (lambda t: t == "activiteit debug", self._activiteit_debug),
            (lambda t: t == "focus debug", self._focus_debug),
            (lambda t: t == "presence debug context", self._presence_debug_context),
            (lambda t: t == "presence debug", self._presence_debug),
            (lambda t: t == "context", self._context),
            (lambda t: t == "traits", self._traits),
            (lambda t: t.startswith("context geschiedenis"), self._context_geschiedenis),
            (lambda t: t.startswith("interruption test"), self._interruption_test),
            (lambda t: t.startswith("interruption gedrag"), self._interruption_gedrag),
            (lambda t: t.startswith("patronen"), self._patronen),
            (lambda t: t == "preferences debug", self._preferences_debug),
            (lambda t: t.startswith("associaties"), self._associaties),
            (lambda t: t == "intent debug", self._intent_debug),
            (lambda t: t.startswith("intent test"), self._intent_test),
            (lambda t: t == "intent retrain", self._intent_retrain),
        ]

        event_bus.subscribe("debug_command", self.handle_debug_command)

    def is_debug_command(self, user_input):
        """
        Checkt of user_input een bekend debug-commando is. main.py
        roept dit aan VOORDAT het bericht als gewone chat wordt
        gepubliceerd, zodat debug-commando's nooit als 'onbekend
        woord' bij Nova's leerproces terechtkomen.
        """
        tekst = user_input.lower().strip()
        return any(herken(tekst) for herken, _ in self._commands)

    def handle_debug_command(self, data, event_type=None):
        """
        Wordt aangeroepen via event_bus.publish('debug_command', {"text": user_input}).
        Zoekt het eerste passende commando en voert het uit.
        """
        user_input = data.get("text", "")
        tekst = user_input.lower().strip()

        for herken, verwerk in self._commands:
            if herken(tekst):
                verwerk(user_input)
                return

        print(f"{C_RED}Onbekend debug-commando.{C_RESET}")

    # ------------------------------------------------------------------
    # Layer 7 — Emergence Engine
    # ------------------------------------------------------------------

    def _emergence_debug(self, user_input):
        emergence = self.loader.loaded_modules.get("emergence_engine")
        if not emergence:
            print(f"{C_RED}emergence_engine-module niet gevonden.{C_RESET}")
            return
        print(f"{C_CYAN}{emergence.debug_layers_status()}{C_RESET}")

    def _emergence(self, user_input):
        emergence = self.loader.loaded_modules.get("emergence_engine")
        if not emergence:
            print(f"{C_RED}emergence_engine-module niet gevonden.{C_RESET}")
            return

        resultaten = emergence.reflect()
        if not resultaten:
            print(f"{C_CYAN}Nog geen insight — waarschijnlijk te weinig data "
                  f"(bv. nog geen woordassociatie boven de confidence-drempel).{C_RESET}")
            return

        print(f"{C_CYAN}--- Layer 7: {len(resultaten)} insight(en) ---{C_RESET}")
        for r in resultaten:
            print(f"{C_CYAN}  type: {r['insight_type']} — confidence: {r['confidence']:.2f}{C_RESET}")
            print(f"{C_CYAN}  tekst: {r['text']}{C_RESET}")

    def _emergence_feedback(self, user_input):
        emergence = self.loader.loaded_modules.get("emergence_engine")
        if not emergence:
            print(f"{C_RED}emergence_engine-module niet gevonden.{C_RESET}")
            return

        delen = user_input.split()
        # delen[0] = "emergence", delen[1] = "feedback", delen[2:] = rest

        if len(delen) == 2:
            # "emergence feedback" zonder verder argument: alles tonen
            if not emergence.feedback_data:
                print(f"{C_CYAN}Nog geen feedback opgeslagen.{C_RESET}")
            else:
                print(f"{C_CYAN}--- Feedback per insight-type ---{C_RESET}")
                for insight_type, stats in emergence.feedback_data.items():
                    print(f"{C_CYAN}  {insight_type}: {stats}{C_RESET}")
            return

        if len(delen) == 4 and delen[3].lower() in ("ok", "slecht"):
            # "emergence feedback <type> <ok|slecht>": feedback geven
            insight_type = delen[2]
            success = delen[3].lower() == "ok"
            emergence.feedback(insight_type, success=success)
            print(f"{C_CYAN}Feedback opgeslagen voor '{insight_type}': "
                  f"{'success' if success else 'failure'}.{C_RESET}")
            return

        print(f"{C_RED}Gebruik: 'emergence feedback' (overzicht) of "
              f"'emergence feedback <type> <ok|slecht>' (feedback geven).{C_RESET}")

    def _emergence_drempel(self, user_input):
        emergence = self.loader.loaded_modules.get("emergence_engine")
        if not emergence:
            print(f"{C_RED}emergence_engine-module niet gevonden.{C_RESET}")
            return

        delen = user_input.split()
        if len(delen) != 3:
            print(f"{C_RED}Gebruik: 'emergence drempel <type>' "
                  f"(bv. 'emergence drempel woordverband').{C_RESET}")
            return

        insight_type = delen[2]
        origineel = emergence.LAYER4_DREMPELS.get(insight_type)
        if origineel is None:
            print(f"{C_RED}Onbekend insight-type: '{insight_type}'.{C_RESET}")
            return

        effectief = emergence._effectieve_drempel(insight_type)
        stats = emergence.feedback_data.get(insight_type)

        print(f"{C_CYAN}Insight-type: {insight_type}{C_RESET}")
        print(f"{C_CYAN}  Originele drempel: {origineel}{C_RESET}")
        print(f"{C_CYAN}  Effectieve drempel: {effectief}{C_RESET}")
        print(f"{C_CYAN}  Feedback-stats: {stats}{C_RESET}")

    # ------------------------------------------------------------------
    # Layer 0 — Memory
    # ------------------------------------------------------------------

    def _onderhoud(self, user_input):
        mem = self.loader.loaded_modules.get("memory")
        if mem:
            print(f"{C_CYAN}Onderhoudsronde wordt gestart...{C_RESET}")
            mem.run_maintenance()
        else:
            print(f"{C_RED}Memory-module niet gevonden.{C_RESET}")

    def _geheugen_stats(self, user_input):
        mem = self.loader.loaded_modules.get("memory")
        if mem:
            vers = user_input.lower() == "geheugen stats vers"
            stats = mem.get_stats(force_refresh=vers)
            print(f"{C_CYAN}Memory stats: {stats}{C_RESET}")
        else:
            print(f"{C_RED}Memory-module niet gevonden.{C_RESET}")

    def _geheugen_gezondheid(self, user_input):
        mem = self.loader.loaded_modules.get("memory")
        if mem:
            resultaat = mem.health_check()
            if resultaat["status"] == "ok":
                print(f"{C_CYAN}Memory gezondheid: OK — geen problemen gevonden.{C_RESET}")
            else:
                print(f"{C_RED}Memory gezondheid: PROBLEMEN{C_RESET}")
                for probleem in resultaat["problemen"]:
                    print(f"{C_RED}  - {probleem}{C_RESET}")
            print(f"{C_CYAN}Details: {resultaat['details']}{C_RESET}")
        else:
            print(f"{C_RED}Memory-module niet gevonden.{C_RESET}")

    # ------------------------------------------------------------------
    # Layer 5 — Context Manager (activiteit, focus, presence)
    # ------------------------------------------------------------------

    def _activiteit_debug(self, user_input):
        ad = self.loader.loaded_modules.get("activity_detector")
        if not ad:
            print(f"{C_RED}activity_detector-module niet gevonden.{C_RESET}")
            return
        info = ad.detect_activity()
        print(f"{C_CYAN}Ruwe venstertitel: {info.get('raw_window_title')!r}{C_RESET}")
        print(f"{C_CYAN}Ruwe procesnaam: {info.get('raw_process_name')!r}{C_RESET}")
        print(f"{C_CYAN}Herkend als: {info.get('activity')}{C_RESET}")
        print(f"{C_CYAN}Werkt aan Nova zelf: {info.get('is_working_on_nova')}{C_RESET}")

    def _focus_debug(self, user_input):
        fd = self.loader.loaded_modules.get("focus_detector")
        if not fd:
            print(f"{C_RED}focus_detector-module niet gevonden.{C_RESET}")
            return
        info = fd.get_focus_info()
        print(f"{C_CYAN}Seconden sinds laatste input: {info.get('seconds_since_input')}{C_RESET}")
        print(f"{C_CYAN}Focus-niveau: {info.get('focus_level')}{C_RESET}")

    def _presence_debug(self, user_input):
        pd = self.loader.loaded_modules.get("presence_detector")
        if not pd:
            print(f"{C_RED}presence_detector-module niet gevonden.{C_RESET}")
            return
        print(f"{C_CYAN}Webcam wordt gecheckt (lampje kan even flikkeren)...{C_RESET}")
        info = pd.detect_presence()
        print(f"{C_CYAN}Aantal gezichten: {info.get('faces_detected')}{C_RESET}")
        print(f"{C_CYAN}Alleen: {info.get('is_alone')}{C_RESET}")

    def _presence_debug_context(self, user_input):
        ctx_mgr = self.loader.loaded_modules.get("context_manager")
        if not ctx_mgr:
            print(f"{C_RED}context_manager-module niet gevonden.{C_RESET}")
            return
        print(f"{C_CYAN}Webcam wordt gecheckt EN doorgegeven aan context_manager...{C_RESET}")
        ctx_mgr.update_presence_info()
        print(f"{C_CYAN}{ctx_mgr.get_context_summary()}{C_RESET}")

    def _context(self, user_input):
        ctx_mgr = self.loader.loaded_modules.get("context_manager")
        if not ctx_mgr:
            print(f"{C_RED}context_manager-module niet gevonden.{C_RESET}")
            return
        print(f"{C_CYAN}{ctx_mgr.get_context_summary()}{C_RESET}")

    def _context_geschiedenis(self, user_input):
        ctx_mgr = self.loader.loaded_modules.get("context_manager")
        if not ctx_mgr:
            print(f"{C_RED}context_manager-module niet gevonden.{C_RESET}")
            return

        delen = user_input.split()
        aantal = 10
        if len(delen) >= 3 and delen[2].isdigit():
            aantal = int(delen[2])

        regels = ctx_mgr.get_recent_log(aantal=aantal)
        if not regels:
            print(f"{C_CYAN}Nog geen geschiedenis beschikbaar.{C_RESET}")
            return

        print(f"{C_CYAN}--- Laatste {len(regels)} Layer 5-beslissing(en) ---{C_RESET}")
        for regel in regels:
            tijd = regel.get("time", "?")
            should_interrupt = regel.get("should_interrupt")
            reden = regel.get("reden", "?")
            print(f"  {tijd} — mag onderbreken: {should_interrupt} — reden: {reden}")

    # ------------------------------------------------------------------
    # Layer 6 — Personality
    # ------------------------------------------------------------------

    def _traits(self, user_input):
        resp_pipeline = self.loader.loaded_modules.get("response_pipeline")
        if not resp_pipeline:
            print(f"{C_RED}response_pipeline-module niet gevonden.{C_RESET}")
            return
        print(f"{C_CYAN}--- Live traits (in-memory, personality_engine.traits) ---{C_RESET}")
        for naam, waarde in resp_pipeline.personality.traits.items():
            print(f"{C_CYAN}  {naam}: {waarde}{C_RESET}")

    # ------------------------------------------------------------------
    # Activity-Aware Interaction
    # ------------------------------------------------------------------

    def _interruption_test(self, user_input):
        tracker = self.loader.loaded_modules.get("interruption_tracker")
        if not tracker:
            print(f"{C_RED}interruption_tracker-module niet gevonden.{C_RESET}")
            return

        delen = user_input.split()
        if len(delen) < 4:
            print(f"{C_RED}Gebruik: interruption test <activiteit> <ja|nee> <aantal>{C_RESET}")
            return

        activiteit = delen[2]
        antwoord = delen[3].lower()
        aantal = int(delen[4]) if len(delen) >= 5 and delen[4].isdigit() else 1
        toegestaan = antwoord in ("ja", "yes", "true")

        for _ in range(aantal):
            tracker.record_feedback(activiteit, toegestaan)

        print(
            f"{C_CYAN}{aantal}x geregistreerd: activiteit='{activiteit}', "
            f"toegestaan={toegestaan}{C_RESET}"
        )
        print(f"{C_CYAN}Huidig patroon: {tracker.get_pattern(activiteit)}{C_RESET}")

    def _interruption_gedrag(self, user_input):
        resp_engine = self.loader.loaded_modules.get("response_engine")
        if not resp_engine:
            print(f"{C_RED}response_engine-module niet gevonden.{C_RESET}")
            return

        delen = user_input.split()
        if len(delen) < 3:
            print(f"{C_RED}Gebruik: interruption gedrag <activiteit>{C_RESET}")
            return

        activiteit = delen[2]
        beslissing = resp_engine.beslis_interruption_gedrag(activiteit)
        print(f"{C_CYAN}Beslissing voor '{activiteit}': {beslissing}{C_RESET}")

    # ------------------------------------------------------------------
    # Layer 2 — Pattern Matcher
    # ------------------------------------------------------------------

    def _patronen(self, user_input):
        pm = self.loader.loaded_modules.get("pattern_matcher")
        if not pm:
            print(f"{C_RED}pattern_matcher-module niet gevonden.{C_RESET}")
            return

        delen = user_input.split()
        if len(delen) < 2:
            # Geen event_type opgegeven: toon algemene stats
            print(f"{C_CYAN}Layer 2 stats: {pm.get_stats()}{C_RESET}")
            return

        event_type = delen[1]

        print(f"{C_CYAN}--- Patroon voor '{event_type}' ---{C_RESET}")
        print("Ruwe data:", pm.get_pattern(event_type))
        print("Is nu actief?:", pm.is_pattern_active(event_type))
        print("Volgende verwachte moment:", pm.predict_next_occurrence(event_type))
        print("Anomalieën (laatste 7 dagen):", pm.get_anomalies(days=7))

    # ------------------------------------------------------------------
    # Layer 1 — Word Associations Learner
    # ------------------------------------------------------------------

    def _associaties(self, user_input):
        """
        Toont Layer 1's opgeslagen woordassociaties -- rechtstreeks
        uit word_associations_learner.py, buiten elke sjabloon/
        response_engine.py om. Puur om na te kijken OF en HOEVEEL
        Layer 1 effectief leert, los van of dat ooit zichtbaar wordt
        in een antwoord (dat hangt af van detect_definition() +
        een sterk genoeg PMI-verband, zie nova_state.md).

        Zonder woord: algemene stats (get_stats()).
        Met woord: alle associaties voor dat woord (get_associations()).
        """
        # Let op: de dynamische module-scan (module_loader.py) gebruikt
        # de BESTANDSNAAM als key in loaded_modules, niet het label uit
        # het "module_loaded"-event (dat blijft "word_associations",
        # puur een event-naam-keuze in word_associations_learner.py
        # zelf). Vandaar hier een fallback op beide mogelijke keys.
        wa = self.loader.loaded_modules.get("word_associations_learner")
        if not wa:
            wa = self.loader.loaded_modules.get("word_associations")
        if not wa:
            print(f"{C_RED}word_associations(_learner)-module niet gevonden.{C_RESET}")
            return

        delen = user_input.split()
        if len(delen) < 2:
            # Geen woord opgegeven: toon algemene stats
            print(f"{C_CYAN}Layer 1 stats: {wa.get_stats()}{C_RESET}")
            return

        woord = delen[1].lower()

        print(f"{C_CYAN}--- Associaties voor '{woord}' ---{C_RESET}")
        associaties = wa.get_associations(woord)
        if not associaties:
            print(f"(nog geen associaties opgeslagen voor '{woord}')")
            return
        print(associaties)
        print("Sentiment:", wa.get_word_sentiment(woord))

    # ------------------------------------------------------------------
    # User Preferences (kevin_profile.py / sentiment_classifier.py /
    # kandidaat_suggesties.py) -- 26 juli 2026
    # ------------------------------------------------------------------

    def _preferences_debug(self, user_input):
        """
        Toont in één oogopslag de status van de volledige User
        Preferences-module: aantal voorkeuren/afkeuren, sentiment-
        classifier-status (getraind of niet, laatste hertraining,
        aantal openstaande twijfelgevallen), en kandidaat-suggesties-
        status (aantal al gedaan). Puur uitlezen, geen wijzigingen.
        """
        profiel = self.loader.loaded_modules.get("kevin_profile")
        classifier = self.loader.loaded_modules.get("sentiment_classifier")
        kandidaten = self.loader.loaded_modules.get("kandidaat_suggesties")

        print(f"{C_CYAN}--- User Preferences: status ---{C_RESET}")

        if not profiel:
            print(f"{C_RED}kevin_profile-module niet gevonden.{C_RESET}")
        else:
            # get_by_sentiment() is de publieke, stabiele API -- gebruikt
            # bewust NIET _bepaal_actief_sentiment() (privé-methode)
            # rechtstreeks, zodat deze debug-code niet afhankelijk is
            # van kevin_profile.py's interne opslagstructuur.
            n_positief = len(profiel.get_by_sentiment("positief"))
            n_gemengd = len(profiel.get_by_sentiment("neutraal_gemengd"))
            n_negatief = len(profiel.get_by_sentiment("negatief"))

            print(f"{C_CYAN}Profiel: {n_positief} positief, {n_gemengd} neutraal_gemengd, "
                  f"{n_negatief} negatief (totaal {n_positief + n_gemengd + n_negatief} woorden).{C_RESET}")

        if not classifier:
            print(f"{C_RED}sentiment_classifier-module niet gevonden.{C_RESET}")
        else:
            model_status = "geladen" if classifier.model is not None else "NIET geladen (train_sentiment_classifier.py nog niet gedraaid)"
            status = classifier._laad_hertraining_status()
            n_twijfel = classifier._tel_huidige_uncertain_regels()
            n_sinds_laatste = n_twijfel - status["aantal_bij_laatste_training"]

            print(f"{C_CYAN}Sentiment-classifier: model {model_status}.{C_RESET}")
            print(f"{C_CYAN}Laatste hertraining: {status['laatste_training'] or 'nog nooit'}.{C_RESET}")
            print(f"{C_CYAN}Twijfelgevallen: {n_twijfel} totaal, {n_sinds_laatste} nieuw sinds "
                  f"laatste hertraining (drempel: {classifier.HERTRAINING_DREMPEL}).{C_RESET}")

        if not kandidaten:
            print(f"{C_RED}kandidaat_suggesties-module niet gevonden.{C_RESET}")
        else:
            n_gesuggereerd = len(kandidaten._al_gesuggereerd)
            print(f"{C_CYAN}Kandidaat-suggesties: {n_gesuggereerd} suggestie(s) ooit gedaan "
                  f"(PMI-drempel: {kandidaten.MIN_PMI_DREMPEL}).{C_RESET}")

    # ------------------------------------------------------------------
    # Intent Classifier (Fase 1-6, 28 juli 2026)
    # ------------------------------------------------------------------

    def _intent_debug(self, user_input):
        """
        Toont de status van de Intent Classifier: hoeveel voorbeelden,
        welke categorieën, wanneer voor het laatst getraind. Puur
        uitlezen, geen wijzigingen.
        """
        clf = self.loader.loaded_modules.get("intent_classifier")
        if not clf:
            print(f"{C_RED}intent_classifier-module niet gevonden.{C_RESET}")
            return

        stats = clf.get_stats()
        print(f"{C_CYAN}--- Intent Classifier: status ---{C_RESET}")
        print(f"{C_CYAN}Aantal voorbeelden: {stats['aantal_voorbeelden']}{C_RESET}")
        print(f"{C_CYAN}Categorieën: {', '.join(stats['categorieën'])}{C_RESET}")
        print(f"{C_CYAN}Laatst getraind: {stats['laatst_getraind'] or 'nog nooit'}{C_RESET}")
        print(f"{C_CYAN}Model geladen: {stats['model_geladen']}{C_RESET}")
        print(f"{C_CYAN}Laatste Layer 0-scan: "
              f"{clf.metadata.get('laatste_layer0_scan') or 'nog nooit'}{C_RESET}")

    def _intent_test(self, user_input):
        """
        Test een zin rechtstreeks tegen de Intent Classifier, buiten
        de normale intent_router.py-flow om (dus GEEN pending_question,
        GEEN drempel-logica, GEEN logging naar unmatched_intents.jsonl
        -- puur het kale predict()-resultaat, ter inspectie).

        Gebruik: intent test <zin>
        """
        clf = self.loader.loaded_modules.get("intent_classifier")
        if not clf:
            print(f"{C_RED}intent_classifier-module niet gevonden.{C_RESET}")
            return

        # "intent test" is 2 woorden, de rest is de te testen zin.
        delen = user_input.split(maxsplit=2)
        if len(delen) < 3:
            print(f"{C_RED}Gebruik: intent test <zin>{C_RESET}")
            return

        zin = delen[2]
        resultaat = clf.predict(zin)
        if resultaat is None:
            print(f"{C_RED}Geen getraind model beschikbaar.{C_RESET}")
            return

        print(f"{C_CYAN}--- Intent test: '{zin}' ---{C_RESET}")
        print(f"{C_CYAN}Label: {resultaat['label']} "
              f"(confidence: {resultaat['confidence']}){C_RESET}")
        top3 = sorted(resultaat["all_scores"].items(), key=lambda x: -x[1])[:3]
        print(f"{C_CYAN}Top 3: {top3}{C_RESET}")

    def _intent_retrain(self, user_input):
        """
        Forceert retrain_vanuit_bestanden() handmatig, i.p.v. te
        wachten op de periodieke 4-uur-cyclus in main.py's
        achtergrond_loop(). Handig om meteen te zien of een correctie/
        Layer 0-voorbeeld al effect heeft, zonder uren te moeten
        wachten tijdens het testen.
        """
        clf = self.loader.loaded_modules.get("intent_classifier")
        if not clf:
            print(f"{C_RED}intent_classifier-module niet gevonden.{C_RESET}")
            return

        print(f"{C_CYAN}Hertraining wordt gestart...{C_RESET}")
        gelukt = clf.retrain_vanuit_bestanden()
        if gelukt:
            print(f"{C_CYAN}Hertraining geslaagd. {clf.get_stats()}{C_RESET}")
        else:
            print(f"{C_RED}Hertraining mislukt (zie logs hierboven).{C_RESET}")


def init_module(event_bus, loader=None):
    """
    LET OP: afwijkende signature t.o.v. de meeste modules
    (init_module(event_bus, sem)) — DebugCommands heeft de loader
    zelf nodig, niet de semantic_module. Wordt daarom, net als
    pending_question.py en interruption_tracker.py, handmatig geladen
    in module_loader.py (niet via de dynamische pkgutil-scan) met de
    loader zelf als tweede argument.
    """
    instance = DebugCommands(event_bus, loader)
    event_bus.publish("module_loaded", {"name": "debug_commands"})
    return instance