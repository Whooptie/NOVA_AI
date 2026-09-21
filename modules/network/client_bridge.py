# modules/network/client_bridge.py

"""
Layer 5-uitbreiding: Client Bridge (Windows-companion-client, Fase 1)

WAT LOST DIT OP?
Nova draait sinds de verhuizing naar battleserver op een headless
Linux-Docker-container. activity_detector.py (venster-detectie),
focus_detector.py (muis/toetsenbord-input) en presence_detector.py
(webcam) hebben stuk voor stuk iets nodig dat ENKEL op Kevin's eigen
Windows-laptop bestaat: een scherm, een venster, een webcam. Dat kan
onmogelijk op de server berekend worden — de data ontstaat nergens
anders dan op het apparaat waar Kevin fysiek zit.

DE OPLOSSING (client-server, zie client_server_control_roadmap.md):
Kevin's laptop draait een apart programma (nova_client.py, NIET
onderdeel van deze Nova-daemon) dat:
1. Lokaal dezelfde metingen doet die activity_detector.py/
   focus_detector.py/presence_detector.py vroeger al deden
2. Het resultaat via een WebSocket-verbinding naar DIT bestand stuurt

Dit bestand (client_bridge.py) is de ONTVANGER op battleserver:
- Start een WebSocket-server die luistert op alle netwerkinterfaces
  (0.0.0.0), zodat de laptop 'm kan bereiken via Tailscale, ook van
  buiten het thuisnetwerk
- Bewaart de laatst-ontvangen data per soort (activity/focus/presence)
  in het geheugen — GEEN eigen meting, enkel een postbus
- Doet verder NIETS met de data — geen beslissingen, geen logica.
  Dat blijft, zoals altijd, de taak van context_manager.py (Layer 5)

BELANGRIJK — waarom dit 100% symbolisch blijft: dit bestand voert geen
enkele vorm van classificatie of "begrip" uit. Het ontvangt een kant-
en-klaar label (bv. "coding", "actief", 1 gezicht) dat de laptop-client
zelf al bepaald heeft met exact dezelfde symbolische logica die eerst
op deze server stond. Er gaat GEEN schermafbeelding of cameraframe
over het netwerk — enkel het reeds-berekende resultaat, precies zoals
activity_detector.py vroeger ook al enkel een label doorgaf aan
context_manager.py binnen hetzelfde proces.

VERVANGT NIET, MAAR VULT AAN: de klassen ActivityDetector,
FocusDetector en PresenceDetector die vroeger in dit bestand stonden
(en nu op de laptop draaien in nova_client.py) zijn hier vervangen
door "Remote"-varianten met EXACT dezelfde methodenamen
(detect_activity(), get_focus_info(), detect_presence()) — zodat
context_manager.py en module_loader.py GEEN ENKELE aanpassing nodig
hebben. Voor de rest van Nova verandert er niets aan de interface,
enkel aan waar de data vandaan komt.

BERICHTFORMAAT (JSON, over de WebSocket):
    {
        "type": "activity_status",
        "activity": "coding",
        "duration_minutes": 3.2,
        "raw_window_title": "context_manager.py - Nova_AI - Visual Studio Code",
        "is_working_on_nova": true,
        "time": "2026-09-13T14:32:00"
    }
    {
        "type": "focus_status",
        "focus_level": "actief",
        "seconds_since_input": 12.4
    }
    {
        "type": "presence_status",
        "faces_detected": 1,
        "is_alone": false
    }

Nog NIET gebouwd in deze eerste versie (bewust, stap voor stap):
- Commando's TERUGSTUREN naar de laptop (Deel A: app_controller.py
  e.d.) — dat komt in een latere fase
- Automatisch herverbinden bij verbroken verbinding — als de laptop
  even offline gaat, geeft dit bestand gewoon "geen info" terug
  (zelfde eerlijke fallback-gedrag als de originele detectors altijd
  al hadden bij een ontbrekend pakket), geen crash
- Authenticatie op de WebSocket — voldoende voor nu omdat de
  verbinding alleen via Tailscale's eigen private netwerk loopt, niet
  publiek toegankelijk is
"""

import asyncio
import json
import threading
import time

try:
    import websockets
    WEBSOCKETS_BESCHIKBAAR = True
except ImportError:
    WEBSOCKETS_BESCHIKBAAR = False


# Op welke poort luistert de WebSocket-server? Moet overeenkomen met
# NOVA_SERVER_URI in nova_client.py op de laptop.
LUISTER_POORT = 8765

# Hoe oud mag de laatst-ontvangen data zijn voor we hem nog vertrouwen?
# Boven deze grens geven de Remote-detectors "geen info" terug in
# plaats van stokoude data door te geven alsof het nu net gemeten is
# (bv. omdat de laptop-client gecrasht is of de laptop uit staat).
DATA_VERVAL_SECONDEN = 180  # 3 minuten


class ClientBridge:
    """
    Ontvangt status-berichten van de Windows-companion-client
    (nova_client.py) via WebSocket, en houdt de laatst-ontvangen
    waarde per soort bij. Doet zelf GEEN enkele interpretatie —
    dat blijft context_manager.py's taak, via de Remote*-klassen
    hieronder.
    """

    def __init__(self, event_bus):
        self.event_bus = event_bus

        # Laatst-ontvangen data per soort, telkens samen met het
        # tijdstip van ontvangst (voor de veroudering-check hierboven).
        self._laatste_activity = None
        self._laatste_activity_tijd = 0.0

        self._laatste_focus = None
        self._laatste_focus_tijd = 0.0

        self._laatste_presence = None
        self._laatste_presence_tijd = 0.0

        # Lock, want de WebSocket-server draait in een eigen thread
        # (asyncio-event-loop) terwijl context_manager.py vanuit de
        # hoofdthread leest — zonder lock zou dat een race condition
        # kunnen geven bij gelijktijdige lees/schrijf-toegang.
        self._lock = threading.Lock()

        self._server_thread = None
        self._verbonden_clients = 0

        # --- NIEUW: server → laptop (commando's terugsturen) ---
        # De actieve websocket-verbinding zelf (niet enkel de data die
        # ze doorgeeft) — nodig om vanuit de hoofdthread iets NAAR de
        # laptop te kunnen sturen. None zolang er geen laptop verbonden
        # is; als er ooit meerdere clients tegelijk verbinden, houden
        # we bewust enkel de LAATST verbonden client bij (er is maar
        # één laptop van Kevin, geen multi-client-ondersteuning nodig).
        self._actieve_websocket = None

        # De asyncio-event-loop waarin de WebSocket-server draait.
        # Nodig voor run_coroutine_threadsafe() hieronder — dezelfde
        # truc die nova_client.py al gebruikt, nu in omgekeerde
        # richting (server-hoofdthread → WebSocket-thread, in plaats
        # van laptop-workerthread → laptop-event-loop).
        self._event_loop = None

        # Wachtende commando's: command_id -> threading.Event, plus
        # het resultaat zodra het binnenkomt. Hiermee kan de
        # aanroepende code (intent_router.py, in de hoofdthread) na
        # het versturen van een commando WACHTEN op het antwoord van
        # de laptop, in plaats van blind te hopen dat het lukte.
        self._wachtende_commandos = {}
        self._volgend_commando_id = 0

        if not WEBSOCKETS_BESCHIKBAAR:
            print(
                "[CLIENT_BRIDGE] WAARSCHUWING: 'websockets' is niet "
                "geïnstalleerd. De Windows-companion-client kan zich "
                "niet verbinden. Installeer met: pip install websockets"
            )
            return

        self._start_server_in_achtergrond()

    # ------------------------------------------------------------
    # WebSocket-server opstarten (eigen achtergrondthread)
    # ------------------------------------------------------------

    def _start_server_in_achtergrond(self):
        """
        Start de WebSocket-server in een aparte thread met een eigen
        asyncio-event-loop. NODIG omdat Nova's hoofdthread (main.py's
        chat-loop) gewoon synchrone Python is — de asyncio-server mag
        die niet blokkeren.
        """
        self._server_thread = threading.Thread(
            target=self._run_asyncio_loop,
            daemon=True,  # stopt automatisch mee als Nova zelf stopt
        )
        self._server_thread.start()
        print(f"[CLIENT_BRIDGE] WebSocket-server wordt gestart op poort {LUISTER_POORT}...")

    def _run_asyncio_loop(self):
        """Draait in de aparte thread: start en onderhoudt de asyncio-loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._start_websocket_server())
            loop.run_forever()
        except Exception as e:
            print(f"[CLIENT_BRIDGE] WebSocket-server gestopt met fout: {e}")

    async def _start_websocket_server(self):
        """
        Start de effectieve WebSocket-server, luisterend op ALLE
        netwerkinterfaces (0.0.0.0) — NIET enkel 127.0.0.1 — zodat
        de laptop 'm via Tailscale kan bereiken, ook van buiten het
        thuisnetwerk. Zie de uitleg hierover in
        client_server_control_roadmap.md.

        NIEUW: bewaart ook de event-loop waarin dit draait, zodat
        stuur_commando_naar_laptop() hieronder — aangeroepen vanuit
        de hoofdthread — hier veilig iets kan inplannen.
        """
        self._event_loop = asyncio.get_running_loop()

        async with websockets.serve(self._verwerk_client, "0.0.0.0", LUISTER_POORT):
            print(f"[CLIENT_BRIDGE] WebSocket-server actief op 0.0.0.0:{LUISTER_POORT}")
            await asyncio.Future()  # blijft eeuwig draaien

    # ------------------------------------------------------------
    # Eén verbonden client (de laptop) afhandelen
    # ------------------------------------------------------------

    async def _verwerk_client(self, websocket):
        """
        Wordt aangeroepen zolang de laptop-client verbonden blijft.
        Verwerkt elk binnenkomend bericht en slaat het op naar type.

        NIEUW: bewaart ook 'websocket' zelf in self._actieve_websocket,
        zodat stuur_commando_naar_laptop() hieronder weet WAARHEEN te
        sturen. Bij het verbreken van de verbinding wordt dit weer
        teruggezet naar None — een commando versturen terwijl er geen
        laptop verbonden is, moet een duidelijke, eerlijke fout geven,
        geen stille mislukking.
        """
        self._verbonden_clients += 1
        with self._lock:
            self._actieve_websocket = websocket
        print(f"[CLIENT_BRIDGE] Laptop-client verbonden (totaal actief: {self._verbonden_clients})")

        if self.event_bus is not None:
            self.event_bus.publish("client_bridge:verbonden", {"time": time.time()})

        try:
            async for ruwe_boodschap in websocket:
                self._verwerk_bericht(ruwe_boodschap)
        except Exception as e:
            print(f"[CLIENT_BRIDGE] Verbinding met laptop-client verbroken: {e}")
        finally:
            self._verbonden_clients -= 1
            with self._lock:
                if self._actieve_websocket is websocket:
                    self._actieve_websocket = None
            if self.event_bus is not None:
                self.event_bus.publish("client_bridge:verbroken", {"time": time.time()})

    def _verwerk_bericht(self, ruwe_boodschap):
        """
        Parseert 1 JSON-bericht en slaat het op in de juiste
        "laatste_..."-variabele, afhankelijk van het "type"-veld.
        Onbekende of kapotte berichten worden genegeerd (geen crash) —
        zelfde eerlijke, defensieve stijl als de rest van Nova.
        """

        try:
            data = json.loads(ruwe_boodschap)
        except json.JSONDecodeError:
            print("[CLIENT_BRIDGE] Ontving geen geldige JSON, genegeerd.")
            return

        bericht_type = data.get("type")
        nu = time.time()

        onbekende_melding_data = None

        with self._lock:
            if bericht_type == "activity_status":
                self._laatste_activity = data
                self._laatste_activity_tijd = nu
            elif bericht_type == "focus_status":
                self._laatste_focus = data
                self._laatste_focus_tijd = nu
            elif bericht_type == "presence_status":
                self._laatste_presence = data
                self._laatste_presence_tijd = nu
            elif bericht_type == "command_result":
                # NIEUW: resultaat van een eerder verstuurd commando
                # (bv. "open_app"). Wordt hier apart afgehandeld, niet
                # met de drie types hierboven, want dit hoort niet bij
                # de laptop→server-sensordata, maar bij het antwoord
                # op een server→laptop-commando (zie
                # stuur_commando_naar_laptop() hieronder).
                self._verwerk_commando_resultaat(data)
            elif bericht_type == "onbekende_activiteit_melding":
                # NIEUW (19 september 2026): ActivityDetector op de
                # laptop meldt dat een onbekende venstertitel de
                # ONBEKEND_MELD_DREMPEL bereikt heeft. Enkel de RUWE
                # DATA hier binnen de lock overnemen — de effectieve
                # event_bus.publish() gebeurt HIERONDER, BUITEN de
                # lock.
                #
                # BUGFIX (19 september 2026, live ontdekt: Nova bleef
                # hangen op elk bericht na zo'n melding): publish()
                # hier binnen de lock aanroepen gaf een ZELF-DEADLOCK.
                # event_bus.publish("layer4_response", ...) triggert
                # uiteindelijk (via response_pipeline.py ->
                # context_manager.py -> RemoteActivityDetector ->
                # self.bridge.get_laatste_activity()) een AANROEP TERUG
                # naar get_laatste_activity() HIERONDER — die zelf ook
                # "with self._lock:" gebruikt. self._lock is een
                # threading.Lock() (NIET herbetreedbaar), dus die
                # tweede aanroep, vanuit DEZELFDE thread die de lock al
                # vasthoudt, blokkeert voor altijd. Vandaar dat de
                # EERSTE "hey" na een herstart nog gewoon werkte (geen
                # onbekende_activiteit_melding ertussen), maar elk
                # bericht NA zo'n melding stil bleef hangen.
                if self.event_bus is not None:
                    onbekende_melding_data = {
                        "titel": data.get("titel", "een onbekend venster"),
                        "aantal": data.get("aantal", "meerdere"),
                    }
            else:
                print(f"[CLIENT_BRIDGE] Onbekend berichttype genegeerd: {bericht_type!r}")

        # BUITEN de lock — hier mag event_bus.publish() zonder risico
        # op een deadlock aanroepen, ook al leidt dat intern weer tot
        # get_laatste_activity()/get_laatste_focus()/enz.
        if onbekende_melding_data is not None:
            titel = onbekende_melding_data["titel"]
            aantal = onbekende_melding_data["aantal"]
            self.event_bus.publish("layer4_response", {
                "text": (
                    f"Ik zie dat het venster '{titel}' al {aantal} keer "
                    "voorkwam zonder dat ik weet wat voor activiteit dat is. "
                    "Wil je dat toevoegen aan mijn activiteitenlijst?"
                )
            })

    # ------------------------------------------------------------
    # Interne helper: is de laatst-ontvangen data nog vers genoeg?
    # ------------------------------------------------------------

    def _is_vers(self, tijdstip):
        if tijdstip == 0.0:
            return False  # nog nooit iets ontvangen
        return (time.time() - tijdstip) <= DATA_VERVAL_SECONDEN

    # ------------------------------------------------------------
    # Publieke, thread-safe lees-API voor de Remote*-klassen hieronder
    # ------------------------------------------------------------

    def get_laatste_activity(self):
        with self._lock:
            if self._is_vers(self._laatste_activity_tijd):
                return self._laatste_activity
            return None

    def get_laatste_focus(self):
        with self._lock:
            if self._is_vers(self._laatste_focus_tijd):
                return self._laatste_focus
            return None

    def get_laatste_presence(self):
        with self._lock:
            leeftijd = time.time() - self._laatste_presence_tijd if self._laatste_presence_tijd else None
            if self._is_vers(self._laatste_presence_tijd):
                return self._laatste_presence
            return None

    # ------------------------------------------------------------
    # NIEUW: server → laptop — commando's versturen en op resultaat
    # wachten (Deel A van client_server_control_roadmap.md)
    # ------------------------------------------------------------

    def is_laptop_verbonden(self):
        """
        Simpele check, vooral bedoeld zodat aanroepende code (bv.
        intent_router.py) meteen een eerlijke melding kan geven
        ("je laptop is niet verbonden") in plaats van blind te
        proberen versturen en pas nadien een fout te zien.
        """
        with self._lock:
            return self._actieve_websocket is not None

    def stuur_commando_naar_laptop(self, commando_type, payload, timeout_seconden=10):
        """
        Stuurt een commando naar de laptop-client en WACHT op het
        resultaat (blokkerend, want dit wordt aangeroepen vanuit
        intent_router.py's synchrone route()-hoofdpad — Nova moet
        weten of "open chrome" lukte VOORDAT ze erop antwoordt).

        commando_type: bv. "open_app" — komt terecht in het "type"-
        veld van het JSON-bericht dat nova_client.py ontvangt.
        payload: dict met de rest van de gegevens, bv. {"app": "chrome"}.

        Geeft een dict terug:
            {"ok": True, ...}   bij een geslaagd resultaat
            {"ok": False, "reden": "..."} bij mislukking of timeout

        Gooit NOOIT een exception naar de aanroeper — elke fout
        (geen laptop verbonden, timeout, verzendfout) komt netjes
        terug als {"ok": False, "reden": ...}, want intent_router.py
        moet hier gewoon een chat-antwoord van kunnen maken, geen
        stacktrace hoeven vangen.
        """
        with self._lock:
            websocket = self._actieve_websocket
            event_loop = self._event_loop

        if websocket is None or event_loop is None:
            return {"ok": False, "reden": "Je laptop is momenteel niet verbonden."}

        # Elk commando krijgt een uniek ID, zodat het resultaat dat
        # later terugkomt (via _verwerk_commando_resultaat hieronder)
        # gekoppeld kan worden aan de JUISTE wachtende aanroep — nodig
        # zodra er ooit twee commando's kort na elkaar verstuurd worden.
        with self._lock:
            self._volgend_commando_id += 1
            commando_id = self._volgend_commando_id
            wacht_event = threading.Event()
            self._wachtende_commandos[commando_id] = {
                "event": wacht_event,
                "resultaat": None,
            }

        bericht = dict(payload)
        bericht["type"] = commando_type
        bericht["command_id"] = commando_id

        try:
            future = asyncio.run_coroutine_threadsafe(
                websocket.send(json.dumps(bericht, default=str)), event_loop
            )
            # Wachten tot de VERZENDING zelf lukt (niet het resultaat) —
            # dezelfde .result() zoals nova_client.py's publish() al
            # deed, in omgekeerde richting.
            future.result(timeout=5)
        except Exception as e:
            with self._lock:
                self._wachtende_commandos.pop(commando_id, None)
            return {"ok": False, "reden": f"Versturen naar laptop mislukt: {e}"}

        # Wachten op het antwoord van de laptop (of een timeout).
        kreeg_antwoord = wacht_event.wait(timeout=timeout_seconden)

        with self._lock:
            info = self._wachtende_commandos.pop(commando_id, None)

        if not kreeg_antwoord or info is None:
            return {"ok": False, "reden": "Geen antwoord van de laptop binnen de tijd."}

        return info["resultaat"]

    def _verwerk_commando_resultaat(self, data):
        """
        Wordt aangeroepen vanuit _verwerk_bericht() zodra er een
        "command_result"-bericht binnenkomt van de laptop. Koppelt het
        resultaat via "command_id" aan de juiste wachtende aanroep in
        stuur_commando_naar_laptop() hierboven, en maakt die wakker.

        Wordt zelf al binnen de self._lock van _verwerk_bericht()
        aangeroepen — GEEN eigen lock hier nemen (zou een deadlock
        geven, want threading.Lock is hier niet-herbetreedbaar).
        """
        commando_id = data.get("command_id")
        info = self._wachtende_commandos.get(commando_id)

        if info is None:
            # Te laat binnengekomen (timeout al verstreken en
            # opgeruimd) of een onbekend ID — negeren, geen crash.
            print(f"[CLIENT_BRIDGE] Commando-resultaat voor onbekend/verlopen ID genegeerd: {commando_id!r}")
            return

        info["resultaat"] = {
            "ok": data.get("ok", False),
            "reden": data.get("reden"),
            "app": data.get("app"),
        }
        info["event"].set()

    def shutdown(self):
        """Nette opruiming bij /reboot — de daemon-thread stopt vanzelf mee."""
        pass


# ----------------------------------------------------------------
# Remote-varianten: zelfde interface als de originele detectors
# ----------------------------------------------------------------
# Deze drie klassen vervangen activity_detector.py/focus_detector.py/
# presence_detector.py in module_loader.py's context_layers-dictionary.
# Ze hebben EXACT dezelfde publieke methodenamen als de originelen
# (detect_activity(), get_focus_info(), detect_presence()) zodat
# context_manager.py — dat deze methodes aanroept via
# self.layers.get("activity_detector") — HELEMAAL NIETS hoeft te weten
# over het feit dat de data van een laptop via WebSocket komt in
# plaats van lokaal gemeten te worden.

class RemoteActivityDetector:
    """Vervangt ActivityDetector — leest laatst-ontvangen data van de laptop."""

    def __init__(self, bridge, event_bus=None):
        self.bridge = bridge
        self.event_bus = event_bus

        # BUGFIX (19 september 2026, gevonden tijdens het uitpluizen
        # van waarom "werken_aan_uurrooster" niet in patterns_layer2.json
        # verscheen): het origineel (activity_detector.py, de klasse
        # die vóór de Windows-companion-client hier stond) publiceerde
        # zelf "activity_started:<label>_gedetecteerd" bij ELKE
        # detect_activity()-aanroep (zie dat bestand, regel 208) —
        # zonder dat, telt Layer 2 (pattern_matcher.py) GEEN ENKELE
        # activiteit meer mee, voor GEEN ENKEL label, sinds deze
        # RemoteActivityDetector het origineel verving (13 sept 2026).
        # De bestaande "coding_gedetecteerd: 683"-tellingen in
        # patterns_layer2.json zijn dus HISTORISCH, van vóór die
        # overstap -- er kwam sindsdien NIETS meer bij, voor geen
        # enkel activiteit-label, niet enkel voor nieuwe labels.
        #
        # Om exact hetzelfde gedrag als het origineel te herstellen
        # (incl. de "alleen bij een ECHTE wissel opnieuw publiceren"
        # -logica, zie _vorig_label hieronder), houden we hier ONS
        # EIGEN laatst-geziene label bij -- de laptop-kant
        # (nova_client.py) doet dat OOK al voor zijn eigen
        # duration_minutes-berekening, maar dat is een aparte,
        # onafhankelijke teller; wij hebben hier onze eigen nodig om
        # te weten WANNEER we opnieuw moeten publiceren.
        self._vorig_label = None

    def detect_activity(self):
        data = self.bridge.get_laatste_activity()

        if data is None:
            # Zelfde eerlijke fallback als het origineel gaf wanneer
            # pygetwindow ontbrak: "unknown", geen crash.
            resultaat = {
                "activity": "unknown",
                "duration_minutes": 0.0,
                "raw_window_title": None,
                "raw_process_name": None,
                "is_working_on_nova": False,
                "time": None,
            }
        else:
            resultaat = {
                "activity": data.get("activity", "unknown"),
                "duration_minutes": data.get("duration_minutes", 0.0),
                "raw_window_title": data.get("raw_window_title"),
                "raw_process_name": data.get("raw_process_name"),
                "is_working_on_nova": data.get("is_working_on_nova", False),
                "time": data.get("time"),
            }

        label = resultaat["activity"]

        # Enkel publiceren bij een ECHTE wissel van activiteit, niet
        # bij ELKE detect_activity()-aanroep (die gebeurt elke paar
        # seconden via main.py's achtergrond_loop()) — anders zou
        # Layer 2 "coding" honderden keren per minuut tellen zolang je
        # gewoon in VS Code blijft zitten, wat de tellingen zinloos
        # zou opblazen. Zelfde bedoeling als het origineel had via
        # zijn "if label != self._huidige_activiteit"-check
        # (activity_detector.py) — hier op onze eigen, aparte
        # _vorig_label herbouwd, want DIE detectie/duur-berekening
        # gebeurt nu op de laptop (nova_client.py), niet hier.
        if self.event_bus is not None and label != self._vorig_label:
            self.event_bus.publish(f"activity_started:{label}_gedetecteerd", resultaat)

            if resultaat.get("is_working_on_nova"):
                self.event_bus.publish("activity_started:werken_aan_nova_gedetecteerd", resultaat)

            self.event_bus.publish("activity_detected", resultaat)

        self._vorig_label = label

        return resultaat

class RemoteFocusDetector:
    """Vervangt FocusDetector — leest laatst-ontvangen data van de laptop."""

    def __init__(self, bridge):
        self.bridge = bridge

    def get_focus_info(self):
        data = self.bridge.get_laatste_focus()

        if data is None:
            # Zelfde eerlijke fallback als het origineel gaf op een
            # niet-Windows-systeem: "onbekend", geen crash.
            return {
                "seconds_since_input": None,
                "focus_level": "onbekend",
            }

        return {
            "seconds_since_input": data.get("seconds_since_input"),
            "focus_level": data.get("focus_level", "onbekend"),
        }


class RemotePresenceDetector:
    """Vervangt PresenceDetector — leest laatst-ontvangen data van de laptop."""

    def __init__(self, bridge):
        self.bridge = bridge

    def detect_presence(self):
        data = self.bridge.get_laatste_presence()

        if data is None:
            # Zelfde eerlijke fallback als het origineel gaf bij een
            # ontbrekend pakket/modelbestand: "geen info", geen crash.
            return {
                "faces_detected": None,
                "is_alone": None,
                "time": None,
            }

        return {
            "faces_detected": data.get("faces_detected"),
            "is_alone": data.get("is_alone"),
            "time": data.get("time"),
        }

    def get_current_speaker(self):
        """
        Zelfde symbolische aanname als het origineel: Nova draait voor
        Kevin, dus wie er "aanwezig" is IS Kevin, tenzij er later een
        apart identificatie-mechanisme bijkomt.
        """
        return "Kevin"

    def shutdown(self):
        pass


def init_module(event_bus, sem=None):
    """
    Standaard module_loader-conventie: init_module(event_bus, sem).
    'sem' wordt hier niet gebruikt, net als bij de originele
    activity_detector.py/focus_detector.py — enkel aanwezig zodat de
    dynamische pkgutil-scan in module_loader.py deze module net als
    de andere kan initialiseren.

    Geeft de ClientBridge-instance terug (niet een Remote*-detector),
    want module_loader.py heeft de bridge zelf nodig om de drie
    Remote*-detectors mee te bouwen in context_layers — zie het
    zoek/vervang-blok in module_loader.py hieronder.
    """
    instance = ClientBridge(event_bus)
    event_bus.publish("module_loaded", {"name": "client_bridge"})
    return instance