# modules/context/focus_detector.py

"""
Layer 5, Fase 3: Focus Detector

Detecteert HOELANG GELEDEN de laatste muis- of toetsenbordactiviteit
was, systeemwijd (niet gekoppeld aan één specifiek venster). Puur
symbolisch: gebruikt Windows' eigen GetLastInputInfo()-API via ctypes
— dit VRAAGT gewoon aan Windows wanneer de laatste input was, er wordt
niets gemeten, gelogd of geclassificeerd met ML.

WAAROM dit nodig is (het gat dat Fase 2 liet liggen): activity_detector
.py (Fase 2) zegt enkel WELK VENSTER open staat, niet of Kevin er ook
actief mee bezig is. Iemand kan 20 minuten "coding" staan volgens
Fase 2 terwijl hij allang weg is van zijn bureau en VS Code toevallig
nog open staat. Fase 3 lost dat op door de output van Fase 2 te
temperen: enkel als er OOK recente input is, telt een activiteit als
"actief bezig", niet enkel als "venster staat open".

BELANGRIJK — wat dit NIET is:
- Geen keylogger: er wordt NOOIT gelezen WAT er getypt/geklikt wordt,
  enkel WANNEER de laatste input was (1 timestamp, geen inhoud).
- Geen per-programma input-tracking — dit is systeemwijd (Windows kent
  geen ingebouwde manier om input per venster te meten zonder een veel
  ingrijpendere hook). Dat is een bewuste, aanvaarde beperking: iemand
  die leest zonder te typen/klikken telt na een tijdje als "inactief",
  ook al is hij wel degelijk aan het lezen. Zie de eerlijke afweging
  in het gesprek met Kevin (13 juli 2026) — dit is de reden waarom
  focus-detectie apart staat van activity-detectie, niet gecombineerd
  in 1 "zekere" waarheid.
- Windows-only: GetLastInputInfo() is een Win32-API. Op andere
  platformen geeft dit bestand altijd "geen info" terug (geen crash).
"""

import ctypes
from ctypes import wintypes
import platform


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("dwTime", wintypes.DWORD),
    ]


class FocusDetector:
    """
    Layer 5, Fase 3: detecteert hoelang geleden de laatste systeemwijde
    input (muis/toetsenbord) was.
    """

    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.is_windows = platform.system() == "Windows"

        if not self.is_windows:
            print(
                "[FOCUS_DETECTOR] WAARSCHUWING: dit systeem is geen "
                "Windows — focus-detectie geeft altijd 'geen info' "
                "terug (GetLastInputInfo is een Win32-API)."
            )

    # ------------------------------------------------------------
    # Kern: seconden sinds laatste input
    # ------------------------------------------------------------

    def seconds_since_last_input(self):
        """
        Geeft het aantal seconden sinds de laatste muis- of
        toetsenbordactiviteit terug, systeemwijd. Geeft None terug
        als dit niet te bepalen is (bv. niet-Windows, of een
        onverwachte API-fout) — NOOIT een crash.
        """
        if not self.is_windows:
            return None

        try:
            info = LASTINPUTINFO()
            info.cbSize = ctypes.sizeof(LASTINPUTINFO)

            if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
                return None

            millis_sinds_boot_laatste_input = info.dwTime
            millis_sinds_boot_nu = ctypes.windll.kernel32.GetTickCount()

            millis_inactief = millis_sinds_boot_nu - millis_sinds_boot_laatste_input

            # GetTickCount() loopt na ~49.7 dagen ononderbroken uptime
            # over (32-bit teller). Bij een negatieve uitkomst weten we
            # dat dit gebeurd is — dan geven we voorzichtig None terug
            # in plaats van een onzinnig groot/negatief getal.
            if millis_inactief < 0:
                return None

            return millis_inactief / 1000.0
        except Exception:
            return None

    def get_focus_info(self):
        """
        Geeft een dictionary terug met de ruwe seconden sinds laatste
        input, plus een simpel, symbolisch focus-niveau-label.

        Publiceert ook een "focus_detected"-event, zodat andere
        modules (of Layer 2) dit later kunnen gebruiken zonder zelf
        te moeten pollen.
        """
        seconden = self.seconds_since_last_input()

        niveau = self._bepaal_focus_niveau(seconden)

        resultaat = {
            "seconds_since_input": seconden,
            "focus_level": niveau,
        }

        if self.event_bus is not None:
            self.event_bus.publish("focus_detected", resultaat)

        return resultaat

    def _bepaal_focus_niveau(self, seconden):
        """
        Simpele, vaste drempels (Fase 3) — geen geleerde/dynamische
        waarden:
        - < 120s (2 min) sinds laatste input  -> "actief"
        - 120s - 600s (2-10 min)              -> "mogelijk_afwezig"
        - > 600s (10+ min)                    -> "waarschijnlijk_weg"
        - geen info beschikbaar                -> "onbekend"
        """
        if seconden is None:
            return "onbekend"

        if seconden < 120:
            return "actief"
        elif seconden < 600:
            return "mogelijk_afwezig"
        else:
            return "waarschijnlijk_weg"


def init_module(event_bus, sem=None):
    """
    Standaard module_loader-conventie: init_module(event_bus, sem).
    'sem' wordt hier niet gebruikt maar moet aanwezig zijn zodat
    module_loader.py deze module net als de andere kan initialiseren
    via de automatische dynamische scan (geen "layers"-dictionary
    nodig, net als activity_detector.py).
    """
    instance = FocusDetector(event_bus)
    event_bus.publish("module_loaded", {"name": "focus_detector"})
    return instance
