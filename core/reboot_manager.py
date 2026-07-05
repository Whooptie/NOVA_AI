# core/reboot_manager.py
#
# RebootManager — Fase 1 van reboot_hotreload_roadmap.md
#
# Doel: Kevin typt "/reboot" en Nova herstart volledig zichzelf.
# Alle *.py bestanden worden opnieuw ingelezen (dus ook wijzigingen die
# Kevin net gemaakt heeft), én alle *.json / *.jsonl / *.db bestanden
# worden opnieuw van schijf geladen omdat elke module gewoon opnieuw
# zijn __init__ doorloopt.
#
# BELANGRIJKE UPDATE (na test door Kevin):
# We gebruiken NIET meer os.execv(). Op Windows bestaat er geen
# echte "exec"-systeemaanroep zoals op Linux/Mac — Python simuleert
# dit door in de praktijk een nieuw kindproces te starten terwijl
# het oude proces nog even blijft hangen. Daardoor vechten twee
# processen kort om dezelfde terminal-invoer (stdin), wat zich uitte
# als: trage input, gemiste toetsaanslagen, Enter die niets deed.
# Dit is een bekend, al sinds 2013 gemeld Python-probleem op Windows
# (bugs.python.org/issue19124), geen fout in Nova's eigen code.
#
# NIEUWE AANPAK (Windows-veilig):
# 1. We starten een VOLLEDIG NIEUW, LOSSTAAND proces via subprocess.Popen
#    met CREATE_NEW_CONSOLE, zodat het zijn eigen, verse terminal-venster
#    en eigen stdin krijgt (geen concurrentie meer met het oude proces).
# 2. Daarna sluiten we het oude proces netjes af via sys.exit(0).
#    Dit is een normale, nette Python-afsluiting (in tegenstelling tot
#    os.execv), dus atexit-handlers en cleanup lopen wel gewoon af.
#
# TWEEDE FIX (na test): we sluiten de SQLite-connectie NIET meer zelf
# in deze module. memory.py heeft zelf al een atexit-hook (_on_shutdown)
# die commit()+close() doet zodra het proces stopt. Deden wij dat hier
# óók, dan probeerde die atexit-hook straks te werken op een al-gesloten
# connectie → "Cannot operate on a closed database". Nu flushen we hier
# enkel de write-buffer, en laten het sluiten volledig over aan memory.py
# zelf via zijn eigen atexit-hook.

import os
import sys
import time
import subprocess


class RebootManager:
    """
    Fase 1: Full reboot van Nova via het "/reboot" commando.
    """

    def __init__(self, event_bus, memory=None, loaded_modules=None):
        self.event_bus = event_bus
        self.memory = memory
        self.loaded_modules = loaded_modules or {}

        # Luister naar het reboot-event
        event_bus.subscribe("system:reboot", self.reboot)

    def _shutdown_external_processes(self):
        """
        Sluit alle modules netjes af die een externe subprocess
        vasthouden (zoals chess_engine.py met Stockfish via UCI).

        Waarom nodig? Zonder dit blijft zo'n extern proces (bv.
        Stockfish) verbonden met het oude Python-proces. Windows
        beschouwt het oude console-venster daardoor als "nog actief"
        en sluit het niet, zelfs niet nadat wij sys.exit(0) aanroepen.

        We doorlopen hier gewoon ALLE geladen modules en roepen
        shutdown() aan als de module die methode heeft — zo hoeft
        deze code niet aangepast te worden telkens er een nieuwe
        module met een extern proces bijkomt (bv. later KataGo voor Go).
        """
        for naam, module in self.loaded_modules.items():
            if hasattr(module, "shutdown"):
                try:
                    print(f"[Reboot] {naam} wordt netjes afgesloten...")
                    module.shutdown()
                except Exception as e:
                    print(f"[Reboot] Waarschuwing: fout bij afsluiten {naam}: {e}")

    def reboot(self, data=None, event_type=None):
        """
        Sluit Nova netjes af en herstart in een vers, apart proces.
        """
        # Dit is een gewone print(), GEEN event over de EventBus.
        # Een event zou pas later door main.py opgehaald en getoond
        # worden, maar we willen dat Kevin dit meteen ziet.
        print("\033[95mNova: Oké, ik herstart even. Ben zo terug!\033[0m")
        print("[Reboot] Nova wordt herstart...")

        # STAP 1: Memory netjes voorbereiden op afsluiten (write-buffer
        # legen + achtergrondtimer stoppen). We sluiten de SQLite-
        # connectie hier BEWUST NIET zelf af.
        if self.memory:
            try:
                # Achtergrond-onderhoudstimer stopzetten, anders blijft
                # die in theorie nog even actief tijdens het afsluiten.
                if hasattr(self.memory, "stop_maintenance"):
                    self.memory.stop_maintenance()

                # Alles wat nog in de write-buffer zit alsnog wegschrijven
                # naar SQLite, zodat we niets kwijtraken.
                if hasattr(self.memory, "_flush_buffer"):
                    self.memory._flush_buffer()

                # LET OP: we roepen hier BEWUST geen conn.commit()/
                # conn.close() meer aan. memory.py registreert namelijk
                # zelf al een atexit-hook (_on_shutdown), die automatisch
                # afgaat zodra STAP 5 hieronder sys.exit() aanroept. Die
                # hook doet zelf al commit() + close(). Deden wij dat
                # hier óók nog eens, dan probeert die atexit-hook straks
                # te werken op een connectie die al gesloten is —
                # exact de fout "Cannot operate on a closed database"
                # die tijdens het testen opdook.
                print("[Reboot] Memory-buffer geflusht (sluiten gebeurt automatisch bij afsluiten).")
            except Exception as e:
                # Zelfs als hier iets misgaat, willen we toch verder
                # kunnen herstarten — maar we melden het duidelijk.
                print(f"[Reboot] Waarschuwing: fout bij flushen memory: {e}")

        # STAP 1B: Alle modules met een extern proces netjes afsluiten
        # (bv. chess_engine.py → Stockfish). Dit MOET gebeuren vóór we
        # het nieuwe proces starten, anders blijft het oude venster
        # hangen zolang dat externe proces nog verbonden is.
        self._shutdown_external_processes()

        # STAP 2: Laat andere modules weten dat Nova gaat herstarten,
        # voor het geval een module zelf nog iets moet opruimen.
        self.event_bus.publish("system:shutdown", {
            "reason": "reboot",
            "graceful": True
        })

        # STAP 3: Kleine pauze zodat bovenstaande shutdown-event
        # nog verwerkt kan worden voor we het nieuwe proces starten.
        time.sleep(0.5)

        # STAP 4: Nieuw, volledig los proces starten met een eigen
        # console-venster (CREATE_NEW_CONSOLE bestaat enkel op Windows).
        print("[Reboot] Nieuw Nova-proces wordt gestart...")

        creationflags = 0
        if os.name == "nt":
            # 0x00000010 = CREATE_NEW_CONSOLE
            creationflags = subprocess.CREATE_NEW_CONSOLE

        subprocess.Popen(
            [sys.executable] + sys.argv,
            creationflags=creationflags,
            close_fds=True
        )

        # STAP 5: Oude proces nu netjes afsluiten. sys.exit() is een
        # NORMALE Python-afsluiting (in tegenstelling tot os.execv),
        # dus atexit-handlers/cleanup lopen hier wel netjes af.
        print("[Reboot] Oud proces sluit af — nieuw venster neemt het over.")
        sys.exit(0)


def init_module(event_bus, memory=None, loaded_modules=None):
    instance = RebootManager(event_bus, memory=memory, loaded_modules=loaded_modules)
    event_bus.publish("module_loaded", {"name": "reboot_manager"})
    return instance