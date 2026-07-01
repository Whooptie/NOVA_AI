# Reboot & Hot Reload Roadmap

**Status:** Planning document  
**Depends on:** memory.py daemon (24/7 addendum) ✅  
**Timeline:** Fase 1 nu, Fase 3 later  
**Date:** June 29, 2026  

---

## INHOUDSOPGAVE

1. [Waarom nodig?](#waarom-nodig)
2. [Drie fases](#drie-fases)
3. [Fase 1: Full reboot](#fase-1-full-reboot)
4. [Fase 2: Manual hot reload](#fase-2-manual-hot-reload)
5. [Fase 3: Auto hot reload](#fase-3-auto-hot-reload)
6. [Module cleanup standaard](#module-cleanup-standaard)

---

## WAAROM NODIG?

Nova draait 24/7. Maar Kevin ontwikkelt ook actief modules.

```
PROBLEEM ZONDER REBOOT/RELOAD:

Kevin wijzigt chess_engine.py
→ Nova draait nog met OUDE versie
→ Kevin moet Nova handmatig stoppen
→ Kevin start Nova opnieuw
→ Memory volledig herladen
→ Context verloren
= Irritant bij actieve development!

OPLOSSING:

Fase 1: /reboot commando
→ Graceful stop + herstart
→ Memory herladen van disk
→ Alle wijzigingen actief
= Simpel, altijd werkend ✅

Fase 3: Auto hot reload
→ Kevin slaat chess_engine.py op
→ Nova herlaadt automatisch
→ Zero downtime
→ Memory intact
= Professioneel ✅
```

---

## DRIE FASES

```
FASE 1 (NU - Week 1):
├── /reboot commando
├── ~10 regels code
├── Downtime: ~5 seconden
├── Moeilijkheid: ⭐
└── = DIRECT BRUIKBAAR

FASE 2 (LATER - Maand 2-3):
├── /reload <module> commando
├── ~50 regels code
├── Downtime: ZERO
├── Moeilijkheid: ⭐⭐⭐
└── = Targeted reload

FASE 3 (VEEL LATER - Maand 6+):
├── Auto file watcher
├── Ctrl+S → herlaadt vanzelf
├── ~150 regels code
├── Downtime: ZERO
├── Moeilijkheid: ⭐⭐⭐⭐
└── = Volledige hot reload
```

---

## FASE 1: FULL REBOOT

**Doel:** Nova herstart zichzelf volledig via commando

**Hoe het werkt:**

```
Kevin: "/reboot"
Nova: "Even herstarten..."
      [graceful shutdown]
      [~3-5 seconden]
      [herstart via os.execv]
Nova: "Ik ben terug! Alle wijzigingen geladen."
= Klaar!
```

**Implementation:**

```python
# core/reboot_manager.py

import os
import sys
import time

class RebootManager:
    """
    Fase 1: Full reboot van Nova via commando.
    Herstart het volledige process, laadt alle *.py opnieuw.
    """
    
    def __init__(self, event_bus, memory=None):
        self.event_bus = event_bus
        self.memory = memory
        
        # Luister naar /reboot commando
        event_bus.subscribe("system:reboot", self.reboot)
    
    def reboot(self, data=None):
        """Graceful shutdown + herstart"""
        
        print("[Reboot] Nova herstart...")
        
        # STAP 1: Memory graceful flushen
        if self.memory:
            self.memory._flush_buffer()
            if hasattr(self.memory, 'conn') and self.memory.conn:
                self.memory.conn.commit()
                self.memory.conn.close()
        
        # STAP 2: Publiceer shutdown event
        self.event_bus.publish("system:shutdown", {
            "reason": "reboot",
            "graceful": True
        })
        
        # STAP 3: Kleine pauze (modules krijgen tijd om op te ruimen)
        time.sleep(1)
        
        # STAP 4: Herstart zelfde script
        # os.execv vervangt het huidige process
        # = Alle *.py bestanden opnieuw ingeladen
        os.execv(sys.executable, [sys.executable] + sys.argv)


def init_module(event_bus, memory=None):
    instance = RebootManager(event_bus, memory)
    event_bus.publish("module_loaded", {"name": "reboot_manager"})
    return instance
```

**Integratie in intent_router.py:**

```python
def handle_system_command(self, user_input):
    if "/reboot" in user_input.lower():
        self.event_bus.publish("system:reboot", {})
        return "Even herstarten..."
    return None
```

**Testing:**
- [ ] /reboot commando herkend
- [ ] Memory buffer geflushed voor herstart
- [ ] Nova herstart correct
- [ ] Alle gewijzigde modules actief na herstart
- [ ] Geen data verlies

---

## FASE 2: MANUAL HOT RELOAD

**Doel:** 1 specifieke module herladen zonder Nova te stoppen

**Hoe het werkt:**

```
Kevin: "/reload chess_engine"
Nova: "Chess module herladen..."
      [unload oude versie]
      [importlib.reload()]
      [init nieuwe versie]
Nova: "Chess module herladen! ✅"
= Zero downtime!
```

**Implementation:**

```python
# core/hot_reloader.py (Fase 2)

import importlib
import importlib.util
import sys
from pathlib import Path

class HotReloader:
    """
    Fase 2: Manueel herladen van specifieke modules.
    Geen downtime, memory intact.
    """
    
    def __init__(self, event_bus, module_loader):
        self.event_bus = event_bus
        self.module_loader = module_loader
        
        event_bus.subscribe("system:reload", self.on_reload_command)
    
    def on_reload_command(self, data):
        """Kevin typt: /reload chess_engine"""
        
        module_name = data.get("module")
        
        if not module_name:
            self._reload_all()
            return
        
        path = self._find_module_path(module_name)
        
        if not path:
            self.event_bus.publish("nova:response", {
                "text": f"Module '{module_name}' niet gevonden."
            })
            return
        
        self._reload_module(module_name, path)
    
    def _reload_module(self, module_name, path):
        """Herlaad 1 module"""
        
        try:
            # STAP 1: Cleanup oude module
            old_instance = self.module_loader.get_module(module_name)
            if old_instance and hasattr(old_instance, 'cleanup'):
                old_instance.cleanup()
            
            # STAP 2: Verwijder uit Python's module cache
            for key in list(sys.modules.keys()):
                if module_name in key:
                    del sys.modules[key]
            
            # STAP 3: Importeer opnieuw
            spec = importlib.util.spec_from_file_location(module_name, str(path))
            new_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(new_module)
            
            # STAP 4: Init nieuwe versie
            if hasattr(new_module, 'init_module'):
                new_instance = new_module.init_module(self.event_bus)
                self.module_loader.register(module_name, new_instance)
            
            # STAP 5: Publiceer succes
            self.event_bus.publish("nova:response", {
                "text": f"{module_name} herladen! ✅"
            })
            
            print(f"[HotReloader] ✅ {module_name} herladen!")
            
        except Exception as e:
            # FOUT: Oude module blijft draaien (veilig!)
            print(f"[HotReloader] ❌ Fout bij herladen {module_name}: {e}")
            self.event_bus.publish("nova:response", {
                "text": f"Fout bij herladen {module_name}: {e}"
            })
    
    def _reload_all(self):
        """Herlaad alle modules"""
        modules = self.module_loader.get_all_modules()
        for name, path in modules.items():
            self._reload_module(name, path)
    
    def _find_module_path(self, module_name):
        """Zoek *.py bestand voor module"""
        for base in [Path("modules/"), Path("core/")]:
            for path in base.rglob(f"{module_name}.py"):
                return path
        return None


def init_module(event_bus, module_loader=None):
    instance = HotReloader(event_bus, module_loader)
    event_bus.publish("module_loaded", {"name": "hot_reloader"})
    return instance
```

**Testing:**
- [ ] /reload chess_engine herlaadt correct
- [ ] /reload all herlaadt alles
- [ ] Fout in module = Nova blijft draaien
- [ ] Memory intact na reload

---

## FASE 3: AUTO HOT RELOAD

**Doel:** Nova detecteert automatisch gewijzigde *.py bestanden

**Extra library:**

```bash
pip install watchdog
```

**Hoe het werkt:**

```
Kevin: (wijzigt chess_engine.py in VSCode)
Kevin: Ctrl+S
Nova: (detecteert wijziging via file watcher)
Nova: "Chess module automatisch herladen ✅"
= Zero downtime, zero commando's!
```

**Implementation:**

```python
# core/hot_reloader.py (Fase 3 uitbreiding)

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time

class FileChangeHandler(FileSystemEventHandler):
    """Detecteert wijzigingen in *.py bestanden"""
    
    def __init__(self, hot_reloader):
        self.hot_reloader = hot_reloader
        self.last_reload = {}
        self.cooldown = 2.0  # Seconden tussen reloads
    
    def on_modified(self, event):
        """Bestand gewijzigd!"""
        
        if event.is_directory:
            return
        if not event.src_path.endswith(".py"):
            return
        
        path = Path(event.src_path)
        module_name = path.stem
        
        # Skip interne bestanden
        if module_name.startswith("__"):
            return
        
        # Anti-dubbele reload (cooldown)
        now = time.time()
        if now - self.last_reload.get(module_name, 0) < self.cooldown:
            return
        self.last_reload[module_name] = now
        
        print(f"[AutoReload] Wijziging gedetecteerd: {module_name}")
        self.hot_reloader._reload_module(module_name, path)


class HotReloader:
    """
    Fase 3: Auto hot reload via file watcher.
    Bouwt verder op Fase 2.
    """
    
    def __init__(self, event_bus, module_loader, auto_reload=False):
        self.event_bus = event_bus
        self.module_loader = module_loader
        self.observer = None
        
        event_bus.subscribe("system:reload", self.on_reload_command)
        
        if auto_reload:
            self._start_file_watcher()
    
    def _start_file_watcher(self):
        """Start file watcher"""
        handler = FileChangeHandler(self)
        self.observer = Observer()
        
        for watch_path in [Path("modules/"), Path("core/")]:
            if watch_path.exists():
                self.observer.schedule(handler, str(watch_path), recursive=True)
        
        self.observer.start()
        print("[HotReloader] Auto reload actief!")
    
    def _stop_file_watcher(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
    
    def cleanup(self):
        """Cleanup bij unload"""
        self._stop_file_watcher()
    
    # ... (rest Fase 2 code blijft hetzelfde)
```

**Config:**

```yaml
# nova_config.yaml
hot_reload:
  enabled: true
  auto_reload: true       # Fase 3 aan/uit
  cooldown_seconds: 2
  watch_paths:
    - "modules/"
    - "core/"
  ignore_patterns:
    - "__pycache__"
    - "*.pyc"
    - "__init__.py"
```

**Testing:**
- [ ] Wijziging in VSCode → automatisch herladen
- [ ] Cooldown werkt (geen dubbele reloads)
- [ ] Fout in bestand = Nova blijft draaien
- [ ] Cleanup bij Nova stop

---

## MODULE CLEANUP STANDAARD

Elke module moet een `cleanup()` functie hebben voor hot reload:

```python
# TEMPLATE voor elke module:

class MijnModule:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.subscriptions = []
        self.subscriptions.append(
            event_bus.subscribe("event:naam", self.handler)
        )
    
    def cleanup(self):
        """
        Ruim op voor hot reload.
        ALTIJD implementeren!
        """
        # Unsubscribe van alle events
        for sub in self.subscriptions:
            self.event_bus.unsubscribe(sub)
        
        # Sla state op indien nodig
        self._save_state()
        
        print(f"[{self.__class__.__name__}] Cleanup klaar")
    
    def _save_state(self):
        """Optioneel: sla module state op"""
        pass
```

---

## MODULE LOADER UITBREIDING

```python
# core/module_loader.py uitbreidingen:

class ModuleLoader:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.modules = {}  # naam → instance
        self.paths = {}    # naam → path
    
    def get_module(self, name):
        return self.modules.get(name)
    
    def get_all_modules(self):
        return self.paths.copy()
    
    def register(self, name, instance, path=None):
        self.modules[name] = instance
        if path:
            self.paths[name] = path
    
    def unload(self, name):
        if name in self.modules:
            instance = self.modules[name]
            if hasattr(instance, 'cleanup'):
                instance.cleanup()
            del self.modules[name]
```

---

## COMMANDO OVERZICHT

```
/reboot
├── Full herstart Nova
├── ~5 seconden downtime
├── Alle modules herladen
└── Memory herladen van disk

/reload chess_engine
├── Herlaad 1 module
├── Zero downtime
└── Memory intact

/reload all
├── Herlaad alle modules
├── Zero downtime
└── Memory intact

(Auto - Fase 3):
├── Ctrl+S in VSCode
├── Nova herlaadt vanzelf
└── Zero downtime
```

---

## IMPLEMENTATIE VOLGORDE

```
STAP 1 (NU):
└── reboot_manager.py
    = /reboot commando
    = 10 minuten werk ⭐

STAP 2 (LATER):
└── hot_reloader.py Fase 2
    = /reload <module>
    = paar uur werk ⭐⭐⭐

STAP 3 (VEEL LATER):
└── hot_reloader.py Fase 3
    = Auto file watcher
    = pip install watchdog
    = halve dag werk ⭐⭐⭐⭐
```

---

**Status:** PLANNING  
**Fase 1:** Direct uitvoerbaar  
**Fase 3:** Wanneer klaar voor development workflow  
**Author:** Claude + Kevin
