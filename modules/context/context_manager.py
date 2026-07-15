# modules/context/context_manager.py

"""
Layer 5: Context Manager

Bepaalt WAT NU BELANGRIJK IS en WANNEER NOVA MAG SPREKEN.

Fase 1 (afgerond): tijd + Layer 2 (pattern_matcher.py) combineren tot
een simpele "mag ik nu spreken"-beslissing.

Fase 2 (afgerond): activiteit (activity_detector.py) erbij betrekken —
WELK PROGRAMMA nu open staat, en hoe lang al.

Fase 3 (dit bestand, nieuw): focus (focus_detector.py) erbij betrekken
— HOELANG GELEDEN was er systeemwijde muis/toetsenbord-input. Dit
verfijnt Fase 2: "coding" telt nu enkel als storingsgevoelig als er
OOK recent input was — staat VS Code enkel nog open terwijl Kevin al
weg is van zijn bureau, dan mag Nova gewoon weer onderbreken.

Nog steeds 100% symbolisch: focus_detector.py gebruikt Windows' eigen
GetLastInputInfo()-API (via ctypes) om enkel WANNEER de laatste input
was op te vragen — geen keylogging, geen inhoud, geen ML.

GEEN webcam/presence-detectie (Fase 4, en dát VEREIST wél bounded ML),
GEEN identiteitsherkenning — dat blijven latere, aparte fases.

Opslag: elke berekende context wordt weggeschreven naar
data/context_log.jsonl — een append-only GESCHIEDENIS, geen "state"
die bij opstarten opnieuw ingeladen wordt. Layer 5 herberekent zijn
context altijd live; enkel de geschiedenis van beslissingen wordt
bewaard.
"""

from datetime import datetime
from pathlib import Path
import json


class ContextManager:
    """
    Layer 5: Context Manager (Fase 1 + Fase 2 + Fase 3)

    Verzamelt op elk moment:
    - het huidige tijdstip
    - of dit een "gebruikelijk" moment is volgens Layer 2 (patronen)
    - recente anomalieën (Layer 2)
    - de huidige activiteit + duur (Fase 2, via activity_detector.py)
    - het focus-niveau (Fase 3, via focus_detector.py)

    En berekent daaruit een simpele context + interruption-advies.
    Elke beslissing wordt ook gelogd naar schijf (context_log.jsonl).
    """

    # Welk event_type gebruiken we als basis om te bepalen of NU een
    # "normaal actieve" periode is? We kiezen "chat_message" omdat dat
    # het meest rechtstreekse signaal is van "Kevin is aan het praten
    # met Nova" — pattern_matcher.py houdt hier al patronen van bij.
    REFERENTIE_EVENT_TYPE = "chat_message"

    # Vanaf hoeveel minuten ononderbroken "coding"-activiteit gaan we
    # onderbreken extra afraden? Dit is een bewust simpele, vaste
    # drempel — geen geleerde/dynamische waarde.
    CODING_ONDERBREEK_DREMPEL_MINUTEN = 15

    # Activiteiten waarbij we extra terughoudend zijn met onderbreken.
    # Uitbreidbaar: voeg hier gerust "gaming" of andere labels aan toe
    # zodra je dat wil, telkens gekoppeld aan de mapping in
    # activity_detector.py's ACTIVITEIT_MAPPING.
    STORINGSGEVOELIGE_ACTIVITEITEN = {"coding"}

    # Fase 3: welke focus-niveaus tellen als "Kevin is er echt niet
    # meer actief mee bezig"? Bij deze niveaus mag Nova gewoon weer
    # onderbreken, ZELFS tijdens een storingsgevoelige activiteit —
    # het venster staat wel open, maar er is te lang geen input geweest.
    FOCUS_NIVEAUS_ZONDER_ACTIEVE_AANWEZIGHEID = {
        "mogelijk_afwezig",
        "waarschijnlijk_weg",
    }

    # Hoeveel regels mag context_log.jsonl maximaal bevatten? Ouder dan
    # dit wordt afgekapt (oudste eerst weg), zodat het bestand niet
    # onbeperkt groeit bij een 24/7-daemon.
    MAX_LOG_REGELS = 2000

    def __init__(self, event_bus, layers=None):
        self.event_bus = event_bus
        # "layers" volgt dezelfde conventie als response_engine.py:
        # een dictionary met de andere lagen die Layer 5 nodig heeft.
        self.layers = layers or {}

        # Laatst berekende context, zodat andere modules (of debug-
        # commando's in main.py) die ook kunnen opvragen zonder meteen
        # opnieuw te moeten herberekenen.
        self.context = {}

        # Portable pad, zelfde principe als pattern_matcher.py/memory.py:
        # nooit hardcoded Windows-pad, altijd relatief t.o.v. dit bestand.
        # modules/context/context_manager.py -> ../../data/context_log.jsonl
        self.log_path = Path(__file__).resolve().parent.parent.parent / "data" / "context_log.jsonl"

        # Layer 5 spreekt zelf nooit rechtstreeks (geen chat_response
        # hier) — dit bestand berekent enkel CONTEXT en publiceert die.
        # Andere modules (bv. session_watcher, of nieuwe proactieve
        # modules) kunnen op "context:updated" subscriben om hun
        # beslissingen (moet ik nu spreken?) erop te baseren.

    # ------------------------------------------------------------------
    # Kern: context berekenen
    # ------------------------------------------------------------------

    def get_current(self):
        """
        Berekent de huidige context, publiceert die als
        "context:updated", logt de beslissing naar schijf, en geeft
        de context-dictionary ook terug.
        """
        nu = datetime.now()

        pattern_matcher = self.layers.get("pattern_matcher")
        activity_detector = self.layers.get("activity_detector")
        focus_detector = self.layers.get("focus_detector")

        is_gebruikelijk_moment = False
        anomalieen_vandaag = []

        if pattern_matcher is not None:
            try:
                is_gebruikelijk_moment = pattern_matcher.is_pattern_active(
                    self.REFERENTIE_EVENT_TYPE
                )
            except Exception:
                # Layer 2 nog niet klaar met genoeg data, of onverwachte
                # fout — dan behandelen we dit voorzichtig als "geen
                # betrouwbaar patroon", nooit als crash voor Layer 5.
                is_gebruikelijk_moment = False

            try:
                anomalieen_vandaag = pattern_matcher.get_anomalies(days=1)
            except Exception:
                anomalieen_vandaag = []

        # --- Fase 2: activiteit ophalen ---
        activiteit_label = "unknown"
        activiteit_duur_minuten = 0.0

        if activity_detector is not None:
            try:
                activiteit_info = activity_detector.detect_activity()
                activiteit_label = activiteit_info.get("activity", "unknown")
                activiteit_duur_minuten = activiteit_info.get("duration_minutes", 0.0)
            except Exception:
                # activity_detector.py ontbreekt pygetwindow, of
                # een ander onverwacht probleem — nooit Layer 5 laten
                # crashen, gewoon terugvallen op "unknown".
                activiteit_label = "unknown"
                activiteit_duur_minuten = 0.0

        # --- Fase 3: focus ophalen ---
        focus_niveau = "onbekend"
        seconden_sinds_input = None

        if focus_detector is not None:
            try:
                focus_info = focus_detector.get_focus_info()
                focus_niveau = focus_info.get("focus_level", "onbekend")
                seconden_sinds_input = focus_info.get("seconds_since_input")
            except Exception:
                # focus_detector.py niet op Windows, of onverwachte
                # fout — nooit Layer 5 laten crashen, terugvallen op
                # "onbekend" (wat _bepaal_interrupt() als "geen sterke
                # aanwijzing" behandelt, niet als "zeker afwezig").
                focus_niveau = "onbekend"
                seconden_sinds_input = None

        should_interrupt, reden = self._bepaal_interrupt(
            is_gebruikelijk_moment,
            anomalieen_vandaag,
            activiteit_label,
            activiteit_duur_minuten,
            focus_niveau,
        )

        context = {
            "time": nu.isoformat(),
            "hour": nu.hour,
            "is_gebruikelijk_moment": is_gebruikelijk_moment,
            "aantal_anomalieen_vandaag": len(anomalieen_vandaag),
            "activity": activiteit_label,
            "activity_duration_minutes": activiteit_duur_minuten,
            "focus_level": focus_niveau,
            "seconds_since_input": seconden_sinds_input,
            "should_interrupt": should_interrupt,
            "reden": reden,
        }

        self.context = context

        if self.event_bus is not None:
            self.event_bus.publish("context:updated", context)

        self._log_naar_schijf(context)

        return context

    def _bepaal_interrupt(
        self,
        is_gebruikelijk_moment,
        anomalieen_vandaag,
        activiteit_label,
        activiteit_duur_minuten,
        focus_niveau,
    ):
        """
        Simpele, symbolische regel (Fase 1 + Fase 2 + Fase 3):

        - Zijn er vandaag al veel anomalieën geweest (bv. 3 of meer)?
          Dan wordt Nova voorzichtiger. Dit heeft ALTIJD voorrang.
        - Zit je al een tijdje (>= drempel) in een storingsgevoelige
          activiteit (bv. "coding")? Dan raadt Layer 5 onderbreken af
          — MAAR (Fase 3, NIEUW) enkel als er ook nog recente input
          was. Is het focus-niveau "mogelijk_afwezig" of
          "waarschijnlijk_weg" (te lang geen muis/toetsenbord-input),
          dan mag Nova alsnog onderbreken: het venster staat wel open,
          maar Kevin is er waarschijnlijk niet meer echt mee bezig.
        - Is dit een gebruikelijk moment (bv. Kevin chat hier meestal
          op dit uur)? Dan mag Nova gewoon spreken.
        - Standaard: gewoon toelaten.

        Geeft een tuple terug: (should_interrupt: bool, reden: str).

        Dit blijft een EENVOUDIGE regel — geen gewogen score, geen ML.
        Fase 4 (aanwezigheid via webcam) kan dit verder verfijnen, maar
        dat vereist wel bounded ML (gezichtsherkenning).
        """
        if len(anomalieen_vandaag) >= 3:
            return False, "te veel anomalieën vandaag (>=3)"

        is_storingsgevoelige_activiteit = (
            activiteit_label in self.STORINGSGEVOELIGE_ACTIVITEITEN
            and activiteit_duur_minuten >= self.CODING_ONDERBREEK_DREMPEL_MINUTEN
        )

        if is_storingsgevoelige_activiteit:
            if focus_niveau in self.FOCUS_NIVEAUS_ZONDER_ACTIEVE_AANWEZIGHEID:
                # Venster staat open, maar geen recente input — Kevin
                # is er waarschijnlijk niet meer actief mee bezig.
                # Val NIET terug op de coding-blokkade; ga gewoon door
                # naar de normale gebruikelijk-moment-check hieronder.
                pass
            else:
                # focus_niveau is "actief" of "onbekend" — bij
                # "onbekend" (bv. geen Windows, of API-fout) kiezen we
                # BEWUST de voorzichtige kant: liever niet onderbreken
                # dan een gok wagen, zelfde filosofie als de rest van
                # Layer 5 (nooit een crash/onzekerheid laten leiden tot
                # onbedoeld gedrag).
                return (
                    False,
                    f"al {activiteit_duur_minuten:.0f} min bezig met "
                    f"'{activiteit_label}' (drempel: "
                    f"{self.CODING_ONDERBREEK_DREMPEL_MINUTEN} min), "
                    f"focus: {focus_niveau}",
                )

        if is_gebruikelijk_moment:
            return True, "gebruikelijk moment volgens Layer 2"

        # Geen sterke aanwijzing in beide richtingen: standaard toelaten.
        return True, "geen sterke aanwijzing, standaard toegelaten"

    # ------------------------------------------------------------------
    # Opslag: geschiedenis van beslissingen (append-only logboek)
    # ------------------------------------------------------------------

    def _log_naar_schijf(self, context):
        """
        Voegt de huidige context toe als 1 regel aan
        data/context_log.jsonl (JSON Lines: 1 JSON-object per regel).

        Dit is bewust een append-only GESCHIEDENIS, geen "state" die
        bij opstarten opnieuw ingeladen wordt. Layer 5 herberekent
        zijn context altijd live; enkel de geschiedenis van
        beslissingen wordt bewaard, puur voor nazicht/debug door Kevin.

        Fouten hierbij (bv. schijf tijdelijk niet beschikbaar) mogen
        NOOIT de rest van Layer 5 laten crashen — vandaar de brede
        try/except.
        """
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(context, ensure_ascii=False) + "\n")

            self._trim_log_indien_nodig()
        except Exception as e:
            print(f"[CONTEXT_MANAGER] Kon context_log.jsonl niet wegschrijven: {e}")

    def _trim_log_indien_nodig(self):
        """
        Houdt het logbestand begrensd op MAX_LOG_REGELS regels, door
        bij overschrijding de OUDSTE regels weg te knippen.
        """
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                regels = f.readlines()
        except OSError:
            return

        aantal = len(regels)

        if aantal <= self.MAX_LOG_REGELS:
            return

        overschot = aantal - self.MAX_LOG_REGELS
        resterende_regels = regels[overschot:]

        with open(self.log_path, "w", encoding="utf-8") as f:
            f.writelines(resterende_regels)

    def get_recent_log(self, aantal=10):
        """
        Leest de laatste 'aantal' regels uit context_log.jsonl terug,
        meest recente eerst. Puur voor debug/nazicht.

        Geeft een lege lijst terug als het bestand nog niet bestaat
        of niet leesbaar is — geen crash.
        """
        if not self.log_path.exists():
            return []

        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                regels = f.readlines()
        except OSError:
            return []

        laatste_regels = regels[-aantal:]
        laatste_regels.reverse()  # meest recente eerst

        resultaat = []
        for regel in laatste_regels:
            regel = regel.strip()
            if not regel:
                continue
            try:
                resultaat.append(json.loads(regel))
            except json.JSONDecodeError:
                continue

        return resultaat

    # ------------------------------------------------------------------
    # Publieke, korte API — zelfde stijl als roadmap-voorbeeld
    # ------------------------------------------------------------------

    def can_interrupt(self):
        """Kort en bondig: mag Nova nu spreken?"""
        ctx = self.get_current()
        return ctx.get("should_interrupt", True)

    def get_context_summary(self):
        """
        Leesbare samenvatting voor debug-doeleinden (bv. een
        'context'-testcommando in main.py).
        """
        ctx = self.get_current()
        seconden = ctx.get("seconds_since_input")
        seconden_tekst = f"{seconden:.0f}s" if seconden is not None else "onbekend"
        return (
            f"Tijd: {ctx['hour']}u — "
            f"Gebruikelijk moment: {ctx['is_gebruikelijk_moment']} — "
            f"Anomalieën vandaag: {ctx['aantal_anomalieen_vandaag']} — "
            f"Activiteit: {ctx['activity']} "
            f"({ctx['activity_duration_minutes']:.1f} min) — "
            f"Focus: {ctx['focus_level']} (laatste input: {seconden_tekst}) — "
            f"Mag onderbreken: {ctx['should_interrupt']} "
            f"(reden: {ctx['reden']})"
        )


def init_module(event_bus, layers=None):
    """
    LET OP — dit bestand volgt NIET de standaard dynamische
    module_loader-conventie (init_module(event_bus, sem)), net zoals
    response_engine.py dat ook niet doet. De reden is dezelfde: Layer 5
    heeft een "layers"-dictionary nodig (met pattern_matcher,
    activity_detector EN focus_detector erin), geen losse
    "sem"-parameter.

    Daarom moet dit bestand, net als response_engine.py, HANDMATIG
    geladen worden in module_loader.py — NIET via de automatische
    pkgutil-scan in stap 3. Concreet: dit hoort in module_loader.py
    op een plek NA het laden van pattern_matcher.py, activity_detector.py
    EN focus_detector.py (alle drie dynamische modules-stap), zodat
    self.loaded_modules.get(...) al bestaat op het moment dat
    context_manager geladen wordt.
    """
    instance = ContextManager(event_bus, layers=layers)
    if event_bus is not None:
        event_bus.publish("module_loaded", {"name": "context_manager"})
    return instance
