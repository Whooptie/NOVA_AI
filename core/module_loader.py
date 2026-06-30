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
        from core import memory, semantic, patterns, logger, intent_router

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
