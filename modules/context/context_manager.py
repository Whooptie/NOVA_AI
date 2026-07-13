# modules/context/context_manager.py

"""
Layer 5: Context Manager

Bepaalt WAT NU BELANGRIJK IS en WANNEER NOVA MAG SPREKEN.

Dit is Fase 1 van memory_layer5_roadmap.md: enkel tijd + Layer 2
(pattern_matcher.py) combineren tot een simpele "mag ik nu spreken"-
beslissing. GEEN mouse/keyboard-tracking, GEEN webcam/presence-
detectie, GEEN identiteitsherkenning — dat zijn latere, aparte fases
(en sommige daarvan vereisen bounded ML, zoals gezichtsherkenning,
wat expliciet NIET in dit bestand zit).

100% symbolisch: enkel if/else-logica op basis van tijd en de
patronen die pattern_matcher.py (Layer 2) al bijhoudt. Geen ML,
geen generatie.

NIEUW (sinds de opslag-uitbreiding): elke berekende context wordt ook
weggeschreven naar data/context_log.jsonl, zodat je achteraf kan
nakijken WANNEER Layer 5 een onderbreking afraadde en WAAROM. Dit is
puur een logboek (append-only, met een grens op het aantal regels),
geen "state" die opnieuw ingeladen wordt bij opstarten — in
tegenstelling tot pattern_matcher.py's patterns_layer2.json, dat WEL
de working state is. Layer 5's "brain" blijft dus stateless/herberekend
bij elke get_current()-aanroep; enkel de geschiedenis wordt bewaard.
"""

from datetime import datetime
from pathlib import Path
import json


class ContextManager:
    """
    Layer 5: Context Manager (Fase 1 — symbolische basis)

    Verzamelt op elk moment:
    - het huidige tijdstip
    - of dit een "gebruikelijk" moment is volgens Layer 2 (patronen)
    - recente anomalieën (Layer 2)

    En berekent daaruit een simpele context + interruption-advies.
    Elke beslissing wordt ook gelogd naar schijf (context_log.jsonl).
    """

    # Welk event_type gebruiken we als basis om te bepalen of NU een
    # "normaal actieve" periode is? We kiezen "chat_message" omdat dat
    # het meest rechtstreekse signaal is van "Kevin is aan het praten
    # met Nova" — pattern_matcher.py houdt hier al patronen van bij.
    REFERENTIE_EVENT_TYPE = "chat_message"

    # Hoeveel regels mag context_log.jsonl maximaal bevatten? Ouder dan
    # dit wordt afgekapt (oudste eerst weg), zodat het bestand niet
    # onbeperkt groeit bij een 24/7-daemon. Analoog aan
    # pattern_matcher.py's max_anomalies-aanpak, maar dan op schijf
    # i.p.v. in RAM, omdat dit een append-only logboek is, geen
    # actieve state.
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

        should_interrupt, reden = self._bepaal_interrupt(
            is_gebruikelijk_moment, anomalieen_vandaag
        )

        context = {
            "time": nu.isoformat(),
            "hour": nu.hour,
            "is_gebruikelijk_moment": is_gebruikelijk_moment,
            "aantal_anomalieen_vandaag": len(anomalieen_vandaag),
            "should_interrupt": should_interrupt,
            "reden": reden,
        }

        self.context = context

        if self.event_bus is not None:
            self.event_bus.publish("context:updated", context)

        self._log_naar_schijf(context)

        return context

    def _bepaal_interrupt(self, is_gebruikelijk_moment, anomalieen_vandaag):
        """
        Simpele, symbolische regel (Fase 1):

        - Zijn er vandaag al veel anomalieën geweest (bv. 3 of meer)?
          Dan wordt Nova voorzichtiger — iets ongewoons is aan de gang,
          dus we onderbreken liever niet zonder duidelijke reden.
        - Is dit een gebruikelijk moment (bv. Kevin chat hier meestal
          op dit uur)? Dan mag Nova gewoon spreken.
        - Standaard (geen patroon-data, geen anomalieën): gewoon
          toelaten, want er is nog geen reden om terughoudend te zijn.

        Geeft een tuple terug: (should_interrupt: bool, reden: str) —
        de reden wordt puur gebruikt voor de log/debug-samenvatting,
        NIET voorgelezen aan Kevin door Nova zelf.

        Dit is bewust een EENVOUDIGE eerste regel — geen gewogen score,
        geen ML. Latere fases (focus-detectie, aanwezigheid) kunnen dit
        verfijnen, maar Fase 1 houdt het bij dit simpele niveau.
        """
        if len(anomalieen_vandaag) >= 3:
            return False, "te veel anomalieën vandaag (>=3)"

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
        bij opstarten opnieuw ingeladen wordt — in tegenstelling tot
        pattern_matcher.py's patterns_layer2.json. Layer 5 herberekent
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
        bij overschrijding de OUDSTE regels weg te knippen. We doen dit
        niet bij elke schrijfactie (dat zou traag zijn bij een groot
        bestand), maar met een eenvoudige periodieke check: enkel
        uitvoeren als het bestand toevallig een rond veelvoud van 100
        regels bevat. Dit is een bewuste, simpele benadering — geen
        exacte "elke keer opnieuw tellen"-aanpak, om overhead op een
        24/7-daemon te beperken.
        """
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                regels = f.readlines()
        except OSError:
            return

        aantal = len(regels)

        # Enkel trimmen bij ruime overschrijding, en niet bij elke
        # schrijfbeurt herberekenen — anders lezen we bij elke
        # get_current()-aanroep het hele bestand in, wat op termijn
        # onnodig zwaar wordt.
        if aantal <= self.MAX_LOG_REGELS:
            return

        overschot = aantal - self.MAX_LOG_REGELS
        resterende_regels = regels[overschot:]

        with open(self.log_path, "w", encoding="utf-8") as f:
            f.writelines(resterende_regels)

    def get_recent_log(self, aantal=10):
        """
        Leest de laatste 'aantal' regels uit context_log.jsonl terug,
        meest recente eerst. Puur voor debug/nazicht (bv. een
        toekomstig 'context geschiedenis'-commando in main.py).

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
        'context'-testcommando in main.py, analoog aan het bestaande
        'patronen'-commando).
        """
        ctx = self.get_current()
        return (
            f"Tijd: {ctx['hour']}u — "
            f"Gebruikelijk moment: {ctx['is_gebruikelijk_moment']} — "
            f"Anomalieën vandaag: {ctx['aantal_anomalieen_vandaag']} — "
            f"Mag onderbreken: {ctx['should_interrupt']} "
            f"(reden: {ctx['reden']})"
        )


def init_module(event_bus, layers=None):
    """
    LET OP — dit bestand volgt NIET de standaard dynamische
    module_loader-conventie (init_module(event_bus, sem)), net zoals
    response_engine.py dat ook niet doet. De reden is dezelfde: Layer 5
    heeft een "layers"-dictionary nodig (met pattern_matcher erin),
    geen losse "sem"-parameter.

    Daarom moet dit bestand, net als response_engine.py, HANDMATIG
    geladen worden in module_loader.py — NIET via de automatische
    pkgutil-scan in stap 3. Concreet: dit hoort in module_loader.py
    op een plek NA het laden van pattern_matcher.py (dynamische
    modules-stap), zodat self.loaded_modules.get("pattern_matcher")
    al bestaat op het moment dat context_manager geladen wordt.

    Zie de toelichting die als code-comment is meegegeven bij het
    zoek/vervang-blok voor module_loader.py.
    """
    instance = ContextManager(event_bus, layers=layers)
    if event_bus is not None:
        event_bus.publish("module_loaded", {"name": "context_manager"})
    return instance