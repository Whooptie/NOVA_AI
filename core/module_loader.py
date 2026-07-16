# core/module_loader.py
import importlib
import pkgutil
import modules
import time

class ModuleLoader:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.loaded_modules = {}

    def discover_and_load(self):
        
        # ----------------------------------------------------
        # 1. CORE MODULES
        # ----------------------------------------------------
        from core import memory, semantic, patterns, logger, intent_router, reboot_manager

        # Memory
        start = time.time()
        mem = memory.init_module(self.event_bus)
        mem.__load_time_ms__ = int((time.time() - start) * 1000)
        self.loaded_modules["memory"] = mem
        self.event_bus.register_module("memory", mem)

        # Semantic
        start = time.time()
        sem = semantic.init_module(self.event_bus, mem)
        sem.__load_time_ms__ = int((time.time() - start) * 1000)
        self.loaded_modules["semantic"] = sem
        self.event_bus.register_module("semantic", sem)

        # Patterns
        start = time.time()
        pat = patterns.init_module(self.event_bus)
        pat.__load_time_ms__ = int((time.time() - start) * 1000)
        self.loaded_modules["patterns"] = pat
        self.event_bus.register_module("patterns", pat)

        # Logger
        start = time.time()
        log = logger.init_module(self.event_bus)
        log.__load_time_ms__ = int((time.time() - start) * 1000)
        self.loaded_modules["logger"] = log
        self.event_bus.register_module("logger", log)

        # Reboot manager (krijgt memory mee voor de buffer/database,
        # en de volledige loaded_modules-dictionary zodat hij bij /reboot
        # ELKE module met een shutdown()-methode netjes kan afsluiten —
        # bv. chess_engine.py, die Stockfish als apart extern proces
        # draaiend houdt. Zonder dit blijft Stockfish (en dus het oude
        # console-venster) na een reboot gewoon actief hangen.
        # LET OP: reboot_manager staat zelf nog niet in loaded_modules
        # op dit moment (komt er pas na deze regels bij), dus dit geeft
        # hem een LEVENDE referentie naar de dictionary — modules die
        # daarna nog geladen worden (chess_engine, etc.) staan er dus
        # automatisch ook in tegen de tijd dat /reboot ooit gebruikt wordt.
        start = time.time()
        reboot_mgr = reboot_manager.init_module(
            self.event_bus,
            memory=mem,
            loaded_modules=self.loaded_modules
        )
        reboot_mgr.__load_time_ms__ = int((time.time() - start) * 1000)
        self.loaded_modules["reboot_manager"] = reboot_mgr
        self.event_bus.register_module("reboot_manager", reboot_mgr)

        # ----------------------------------------------------
        # 2. ZONE + TIME ENGINE (altijd eerst)
        # ----------------------------------------------------
        import modules.time.zone as zone_module
        start = time.time()
        zone = zone_module.init_module(self.event_bus)
        zone.__load_time_ms__ = int((time.time() - start) * 1000)
        self.loaded_modules["zone"] = zone
        self.event_bus.register_module("zone", zone)

        # ----------------------------------------------------
        # 3. DYNAMISCHE MODULES
        # ----------------------------------------------------
        module_paths = [
            name for _, name, _ in pkgutil.walk_packages(
                modules.__path__, prefix="modules."
            )
        ]

        print("DEBUG module_paths:", module_paths)

        for full_name in module_paths:
            parts = full_name.split(".")
            if len(parts) != 3:
                continue

            pkg, group, mod = parts

            module = importlib.import_module(full_name)

            # Sla over als er geen init_module is (bv. subpackages zoals topics)
            if not hasattr(module, "init_module"):
                continue

            # Chat krijgt semantic mee
            if group == "chat":
                start = time.time()
                instance = module.init_module(self.event_bus, sem)
                instance.__load_time_ms__ = int((time.time() - start) * 1000)
            else:
                start = time.time()
                try:
                    instance = module.init_module(self.event_bus, sem)
                except TypeError:
                    instance = module.init_module(self.event_bus)
            instance.__load_time_ms__ = int((time.time() - start) * 1000)
            self.loaded_modules[mod] = instance
            self.event_bus.register_module(mod, instance)

        # ----------------------------------------------------
        # 3B. RESPONSE ENGINE (Layer 4)
        # ----------------------------------------------------
        # Krijgt een aparte "layers"-dictionary mee in plaats van het
        # gebruikelijke "sem"-argument dat de andere modules krijgen,
        # want Layer 4 heeft meerdere lagen tegelijk nodig (semantic,
        # word_associations, pattern_matcher). Daarom kan dit niet
        # via de generieke dynamische lus hierboven geladen worden —
        # dat roept altijd module.init_module(event_bus, sem) aan.
        #
        # LET OP: dit MOET na de dynamische modules-lus staan, want
        # word_associations_learner.py en pattern_matcher.py zitten
        # zelf ook in "modules/" (modules/learning/) en worden dus
        # pas hierboven, in stap 3, geladen. Zonder deze volgorde
        # zouden loaded_modules["word_associations"] en
        # loaded_modules["pattern_matcher"] hier nog niet bestaan.
        from core import response_engine

        start = time.time()
        response_layers = {
            "semantic": sem,
            "word_associations": self.loaded_modules.get("word_associations"),
            "pattern_matcher": self.loaded_modules.get("pattern_matcher"),
        }
        resp_engine = response_engine.init_module(self.event_bus, layers=response_layers)
        resp_engine.__load_time_ms__ = int((time.time() - start) * 1000)
        self.loaded_modules["response_engine"] = resp_engine
        self.event_bus.register_module("response_engine", resp_engine)

        # ----------------------------------------------------
        # 3C. CONTEXT MANAGER (Layer 5)
        # ----------------------------------------------------
        # Zelfde reden als response_engine hierboven: krijgt een
        # "layers"-dictionary mee i.p.v. de standaard "sem"-parameter,
        # dus niet via de automatische dynamische scan (stap 3) te
        # laden. Moet hier staan, NA pattern_matcher EN activity_detector
        # (beide dynamische modules-stap), zodat loaded_modules[...]
        # al bestaat op het moment dat context_manager ze nodig heeft.
        from modules.context import context_manager

        start = time.time()
        context_layers = {
            "pattern_matcher": self.loaded_modules.get("pattern_matcher"),
            "activity_detector": self.loaded_modules.get("activity_detector"),
            "focus_detector": self.loaded_modules.get("focus_detector"),
            "presence_detector": self.loaded_modules.get("presence_detector"),
        }
        ctx_mgr = context_manager.init_module(self.event_bus, layers=context_layers)
        ctx_mgr.__load_time_ms__ = int((time.time() - start) * 1000)
        self.loaded_modules["context_manager"] = ctx_mgr
        self.event_bus.register_module("context_manager", ctx_mgr)

        # session_watcher (Layer 5-consument): werd hierboven al geladen
        # via de dynamische modules-scan (stap 3), VOOR context_manager
        # bestond. We prikken de referentie hier alsnog handmatig in,
        # zodat session_watcher.check_pauze() Layer 5 kan raadplegen
        # vóór hij een pauze-melding stuurt. Geen aparte
        # init_module()-aanroep nodig — enkel het attribuut bijwerken
        # op de instance die al bestaat.
        watcher = self.loaded_modules.get("session_watcher")
        if watcher is not None:
            watcher.context_manager = ctx_mgr
        
        # ----------------------------------------------------
        # 4. INTENT ROUTER ALS LAATSTE
        # ----------------------------------------------------
        start = time.time()
        ir = intent_router.init_module(self.event_bus, semantic_module=sem)
        ir.__load_time_ms__ = int((time.time() - start) * 1000)
        self.loaded_modules["intent_router"] = ir
        self.event_bus.register_module("intent_router", ir)

        # ----------------------------------------------------
        # 5. SYSTEEM GEREED
        # ----------------------------------------------------
        self.event_bus.publish("system_ready", {"msg": "Alle modules zijn geladen"})
