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