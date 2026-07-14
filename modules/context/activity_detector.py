# modules/context/activity_detector.py

"""
Layer 5, Fase 2: Activity Detector

Detecteert WELK PROGRAMMA nu actief is (op de voorgrond) en vertaalt
dat naar een leesbaar activiteit-label (bv. "coding", "gaming",
"browsing"). Puur symbolisch: dit VRAAGT gewoon aan Windows welk
venster bovenaan staat via psutil — geen classificatie, geen ML, geen
gok. Het besturingssysteem WEET dit gewoon, wij lezen het enkel af.

BELANGRIJK — wat dit NIET is:
- Geen focus-detectie (mouse/keyboard-activiteit) — dat is Fase 3.
- Geen aanwezigheidsdetectie via webcam — dat is Fase 4, en dat
  VEREIST wél bounded ML (gezichtsherkenning). Hier niet van
  toepassing.
- Geen "raden" wat je aan het doen bent op basis van gedrag — enkel
  een directe, harde koppeling proces-naam -> activiteit-label.

Vereist het pakket 'psutil' (pip install psutil). Op Windows is er
geen ingebouwde manier om het ACTIEVE (voorgrond-)venster te bepalen
zonder een extra pakket; psutil geeft ons wel de lijst van draaiende
processen. Voor het ECHTE voorgrond-venster (welk venster heeft
"focus", niet enkel "draait") is op Windows het pakket 'pygetwindow'
of de win32-API nodig. Dit bestand gebruikt daarom EEN VAN BEIDE,
afhankelijk van wat beschikbaar is — zie _detecteer_actief_venster().
"""

from datetime import datetime

try:
    import psutil
    PSUTIL_BESCHIKBAAR = True
except ImportError:
    PSUTIL_BESCHIKBAAR = False

try:
    import pygetwindow as gw
    PYGETWINDOW_BESCHIKBAAR = True
except ImportError:
    PYGETWINDOW_BESCHIKBAAR = False


class ActivityDetector:
    """
    Layer 5, Fase 2: detecteert de huidige activiteit op basis van
    het actieve voorgrond-venster/proces.
    """

    # ------------------------------------------------------------
    # MAPPING: proces- of venstertitel-fragment -> activiteit-label
    # ------------------------------------------------------------
    # Dit is de plek waar JIJ (Kevin) dit verder aanvult naar jouw
    # eigen gewoontes. De KEY is een stukje tekst dat moet voorkomen
    # in de venstertitel OF procesnaam (kleine letters, we zoeken
    # case-insensitive), de VALUE is het activiteit-label dat Layer 5
    # ermee associeert.
    #
    # Volgorde maakt uit: de EERSTE match in deze dictionary wint.
    # Zet dus specifiekere/belangrijkere matches bovenaan als er
    # overlap zou kunnen zijn.
    ACTIVITEIT_MAPPING = {
        # --- Coderen (echte code-editors, VS Code/PyCharm) ---
        "code.exe": "coding",           # VS Code
        "visual studio code": "coding",
        "pycharm": "coding",

        # --- Praten met Nova zelf (apart label, GEEN "coding") ---
        # Nova's eigen consolevenster toont "python.exe" (of soms de
        # projectmap) als titel, ongeacht of dit het originele venster
        # is of een nieuw venster geopend via /reboot
        # (reboot_manager.py, subprocess.Popen + CREATE_NEW_CONSOLE).
        # Dit venster ALTIJD als "talking_to_nova" bestempelen, nooit
        # als "coding" — praten met Nova is geen storingsgevoelige
        # activiteit zoals VS Code-werk, ook al draait er letterlijk
        # Python in dat venster.
        "python.exe": "talking_to_nova",
        "nova_ai": "talking_to_nova",

        # --- Overige terminals (PowerShell/cmd zonder Nova erin) ---
        "powershell": "coding",
        "cmd.exe": "coding",
        "windows terminal": "coding",

        # --- Gamen (voorbeelden, pas aan naar jouw eigen games) ---
        "steam.exe": "gaming",

        # --- Communicatie ---
        "discord.exe": "communicating",
        "outlook.exe": "communicating",

        # Voeg hier gerust meer toe, bv.:
        # "photoshop": "editing",
        # "spotify.exe": "music",
    }

    # Als geen enkele match gevonden wordt, dit label gebruiken.
    ONBEKEND_LABEL = "unknown"

    def __init__(self, event_bus):
        self.event_bus = event_bus

        # Voor duur-tracking: welke activiteit waren we vorige keer
        # aan het doen, en sinds wanneer?
        self._huidige_activiteit = None
        self._activiteit_sinds = None

        if not PSUTIL_BESCHIKBAAR:
            print(
                "[ACTIVITY_DETECTOR] WAARSCHUWING: 'psutil' is niet "
                "geïnstalleerd. Activity-detectie geeft altijd "
                "'unknown' terug. Installeer met: pip install psutil"
            )

    # ------------------------------------------------------------
    # Kern: activiteit detecteren
    # ------------------------------------------------------------

    def detect_activity(self):
        """
        Detecteert de huidige activiteit en geeft een dictionary
        terug met het label, sinds wanneer deze activiteit loopt
        (in minuten), en de ruwe venster/proces-info (voor debug).

        Publiceert ook een "activity_detected"-event, zodat
        pattern_matcher.py (Layer 2) dit automatisch kan meetellen
        net als elk ander event_type — en zodat context_manager.py
        (Layer 5) hier straks op kan subscriben i.p.v. zelf te pollen.
        """
        raw_titel, raw_proces = self._detecteer_actief_venster()

        label = self._match_activiteit(raw_titel, raw_proces)

        nu = datetime.now()

        if label != self._huidige_activiteit:
            # Activiteit is veranderd — teller herstarten.
            self._huidige_activiteit = label
            self._activiteit_sinds = nu

        duur_minuten = 0.0
        if self._activiteit_sinds is not None:
            duur_minuten = (nu - self._activiteit_sinds).total_seconds() / 60

        resultaat = {
            "activity": label,
            "duration_minutes": round(duur_minuten, 1),
            "raw_window_title": raw_titel,
            "raw_process_name": raw_proces,
            "time": nu.isoformat(),
        }

        if self.event_bus is not None:
            # Layer 2 (pattern_matcher.py) telt dit automatisch mee
            # zoals elk ander event_type, zonder dat pattern_matcher.py
            # zelf iets hoeft te weten over "activiteiten" — het ziet
            # gewoon een event_type "activity_detected" langskomen.
            self.event_bus.publish("activity_detected", resultaat)

        return resultaat

    # ------------------------------------------------------------
    # Intern: welk venster staat op de voorgrond?
    # ------------------------------------------------------------

    def _detecteer_actief_venster(self):
        """
        Geeft een tuple (venstertitel, procesnaam) terug van het
        venster dat nu op de voorgrond staat (focus heeft).

        Probeert eerst pygetwindow (geeft de ECHTE voorgrond-titel),
        valt terug op "geen info" als dat niet beschikbaar is. We
        gebruiken BEWUST geen psutil om het voorgrond-venster te
        bepalen — psutil kent enkel DRAAIENDE processen, niet welke
        daarvan op dit moment focus heeft. Dat onderscheid is precies
        het verschil tussen "Chrome staat open ergens" en "Chrome is
        NU het venster waar Kevin in werkt".
        """
        if not PYGETWINDOW_BESCHIKBAAR:
            return None, None

        try:
            actief = gw.getActiveWindow()
        except Exception:
            # pygetwindow kan op sommige systemen/momenten falen
            # (bv. geen enkel venster heeft focus) — dan geen crash,
            # gewoon "geen info".
            return None, None

        if actief is None:
            return None, None

        titel = actief.title or ""
        return titel, None

    # ------------------------------------------------------------
    # Intern: titel/proces matchen tegen de mapping
    # ------------------------------------------------------------

    def _match_activiteit(self, raw_titel, raw_proces):
        """
        Zoekt de eerste mapping-key die voorkomt in de venstertitel
        OF procesnaam (case-insensitive substring-match). Geeft
        ONBEKEND_LABEL terug als niets matcht, of als er geen
        titel/proces-info beschikbaar was.
        """
        if not raw_titel and not raw_proces:
            return self.ONBEKEND_LABEL

        titel_lower = (raw_titel or "").lower()
        proces_lower = (raw_proces or "").lower()

        for sleutel, label in self.ACTIVITEIT_MAPPING.items():
            sleutel_lower = sleutel.lower()
            if sleutel_lower in titel_lower or sleutel_lower in proces_lower:
                return label

        return self.ONBEKEND_LABEL


def init_module(event_bus, sem=None):
    """
    Standaard module_loader-conventie: init_module(event_bus, sem).
    'sem' wordt hier niet gebruikt maar moet aanwezig zijn zodat
    module_loader.py deze module net als de andere kan initialiseren
    via de automatische dynamische scan (dit bestand heeft, in
    tegenstelling tot context_manager.py, GEEN "layers"-dictionary
    nodig — het publiceert enkel events, het leest geen andere lagen).
    """
    instance = ActivityDetector(event_bus)
    event_bus.publish("module_loaded", {"name": "activity_detector"})
    return instance