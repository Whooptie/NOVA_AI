# modules/context/context_manager.py

"""
Layer 5: Context Manager

Bepaalt WAT NU BELANGRIJK IS en WANNEER NOVA MAG SPREKEN.

Fase 1 (afgerond): tijd + Layer 2 (pattern_matcher.py) combineren tot
een simpele "mag ik nu spreken"-beslissing.

Fase 2 (afgerond): activiteit (activity_detector.py) erbij betrekken —
WELK PROGRAMMA nu open staat, en hoe lang al.

Fase 3 (afgerond): focus (focus_detector.py) erbij betrekken — HOELANG
GELEDEN was er systeemwijde muis/toetsenbord-input. Verfijnt Fase 2:
"coding" telt enkel als storingsgevoelig als er OOK recent input was.

Fase 4 (dit bestand, nieuw): aanwezigheid (presence_detector.py) erbij
betrekken — via de webcam (MediaPipe Face Detection) wordt gecheckt of
er IEMAND aanwezig is, niet WIE. Dit is de EERSTE Layer 5-fase die een
extern ML-model gebruikt (bounded, external specialist tool — Nova's
symbolische kern beslist nog steeds zelf wat ze met het resultaat
doet). Regel (besproken met Kevin, 16 juli 2026): is er NIEMAND
aanwezig, dan mag Nova NIET onderbreken — spreken heeft geen zin als
er niemand is om het te zien/horen op dat moment; dat zou enkel een
opgestapelde, misplaatste melding worden tegen de tijd dat Kevin
terugkomt.

GEEN identiteitsherkenning (wie is dit specifiek) — dat blijft een
latere, aparte uitbreiding (Kevin's presence/identiteits-roadmap, nog
te schrijven), net als Windows Hello-koppeling en stemherkenning.

Fase 5 (dit bestand, nieuw): interruption logic afgerond — Layer 5 is
hiermee VOLLEDIG. De oude "eerste match wint"-volgorde in
_bepaal_interrupt() is vervangen door een gewogen SCORE-systeem: elk
signaal (anomalieën, storingsgevoelige activiteit + focus, gebruikelijk
moment) levert vaste, symbolische punten op, die samen opgeteld worden
tot 1 totaalscore t.o.v. INTERRUPT_SCORE_DREMPEL. "Niemand aanwezig"
(Fase 4) blijft BEWUST een harde stopregel, GEEN scoreregel — spreken
tegen een lege kamer heeft nooit zin, ongeacht de score. Daarnaast is
een nieuw advies-veld "response_style" toegevoegd ("kort"/"normaal"/
"uitgebreid") — puur berekend/gepubliceerd, nog NIET aangesloten op
response_engine.py/expression_injector.py (zie _bepaal_response_style()
voor de volledige, eerlijke toelichting). Dit blijft 100% symbolisch:
vaste, door Kevin gekozen getallen die simpelweg opgeteld worden — GEEN
ML, geen geleerde gewichten. Dat "leren" (bv. via Kevin's feedback op
onderbrekingen) is een bewuste, latere, aparte stap, zie
interruption_learning_roadmap.md.

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
    Layer 5: Context Manager (Fase 1 + Fase 2 + Fase 3 + Fase 4 + Fase 5
    — VOLLEDIG AFGEROND)

    Verzamelt op elk moment:
    - het huidige tijdstip
    - of dit een "gebruikelijk" moment is volgens Layer 2 (patronen)
    - recente anomalieën (Layer 2)
    - de huidige activiteit + duur (Fase 2, via activity_detector.py)
    - het focus-niveau (Fase 3, via focus_detector.py)
    - aanwezigheid (Fase 4, via presence_detector.py)

    En berekent daaruit (Fase 5) een gewogen score-gebaseerde context +
    interruption-advies + response_style-advies. Elke beslissing wordt
    ook gelogd naar schijf (context_log.jsonl), inclusief de volledige
    score-opbouw in het "reden"-veld voor nazicht/debug door Kevin.
    """

    # Welk event_type gebruiken we als basis om te bepalen of NU een
    # "normaal actieve" periode is? We kiezen "chat_message" omdat dat
    # het meest rechtstreekse signaal is van "Kevin is aan het praten
    # met Nova" — pattern_matcher.py houdt hier al patronen van bij.
    REFERENTIE_EVENT_TYPE = "chat_message"

    # Vanaf hoeveel minuten ononderbroken "coding"-activiteit gaan we
    # onderbreken extra afraden? Dit is een bewust simpele, vaste
    # drempel — geen geleerde/dynamische waarde.
    CODING_ONDERBREEK_DREMPEL_MINUTEN = 0.1

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

    # ------------------------------------------------------------
    # Fase 5: gewogen score-systeem voor de interruption-beslissing
    # ------------------------------------------------------------
    # In plaats van de oude "eerste match wint"-volgorde (Fase 1-4)
    # telt Fase 5 punten op: elk signaal draagt een vast gewicht bij
    # aan een totaalscore. Positief = pleit VOOR onderbreken, negatief
    # = pleit TEGEN onderbreken. Aan het einde bepaalt de totaalscore,
    # vergeleken met INTERRUPT_SCORE_DREMPEL, het uiteindelijke advies.
    #
    # BELANGRIJK: dit blijft 100% symbolisch — vaste, door Kevin zelf
    # gekozen getallen die gewoon opgeteld worden. Geen ML, geen
    # geleerde gewichten. Dat is een BEWUSTE latere, aparte stap (zie
    # interruption_learning_roadmap.md), niet iets wat Fase 5 zelf doet.
    #
    # "Niemand aanwezig" (Fase 4) blijft hier BEWUST BUITEN: dat is
    # geen scoreregel maar een harde stopregel (zie _bepaal_interrupt),
    # want spreken tegen een lege kamer heeft nooit zin, ongeacht hoe
    # hoog de rest van de score zou uitvallen.
    SCORE_GEBRUIKELIJK_MOMENT = +2
    SCORE_ONGEBRUIKELIJK_MOMENT = -1
    SCORE_STORINGSGEVOELIGE_ACTIVITEIT_ACTIEF = -3
    SCORE_STORINGSGEVOELIGE_ACTIVITEIT_MAAR_AFWEZIG = +1
    SCORE_ANOMALIE_PER_STUK = -2
    MAX_ANOMALIE_SCORE_AFTREK = -6  # nooit meer dan dit aftrekken

    # Vanaf welke totaalscore mag Nova onderbreken? Lager dan dit
    # (strikt kleiner) betekent should_interrupt = False.
    INTERRUPT_SCORE_DREMPEL = 0

    # Fase 5: response_style — HOE zou Nova best antwoorden, los van
    # OF ze mag onderbreken? Dit is puur een advies-veld dat Fase 5
    # berekent en publiceert; het effectief GEBRUIKEN om antwoorden
    # in te korten is nog niet aangesloten (zie toelichting bij
    # _bepaal_response_style() hieronder).
    RESPONSE_STYLE_KORT = "kort"
    RESPONSE_STYLE_NORMAAL = "normaal"
    RESPONSE_STYLE_UITGEBREID = "uitgebreid"

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

        # Fase 4: laatst bekende presence-info wordt lokaal onthouden.
        # NODIG omdat presence_detector.py enkel elke paar minuten
        # (PRESENCE_CHECK_INTERVAL_MINUTEN in main.py) een nieuwe
        # meting doet, terwijl get_current() elke minuut draait. Dit
        # bewaart dus de LAATST BEKENDE waarde tussen twee webcam-
        # metingen door, i.p.v. bij elke get_current()-aanroep zelf
        # de webcam te openen (dat zou het lampje veel te vaak laten
        # flikkeren — precies wat Kevin niet wilde).
        self._laatst_bekende_presence = {
            "faces_detected": None,
            "is_alone": None,
        }

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
        presence_detector = self.layers.get("presence_detector")

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

        # --- Fase 4: aanwezigheid ophalen ---
        # BELANGRIJK: we roepen presence_detector.detect_presence() HIER
        # NIET rechtstreeks aan — dat zou de webcam bij ELKE
        # get_current()-aanroep openen (elke minuut, via de
        # achtergrondthread), wat het lampje veel te vaak zou laten
        # flikkeren. In plaats daarvan gebruiken we de LAATST BEKENDE
        # waarde, die main.py's achtergrond_loop() apart en spaarzamer
        # (elke PRESENCE_CHECK_INTERVAL_MINUTEN) bijwerkt via
        # update_presence_info().
        aantal_gezichten = self._laatst_bekende_presence.get("faces_detected")
        is_alleen = self._laatst_bekende_presence.get("is_alone")

        should_interrupt, reden = self._bepaal_interrupt(
            is_gebruikelijk_moment,
            anomalieen_vandaag,
            activiteit_label,
            activiteit_duur_minuten,
            focus_niveau,
            is_alleen,
        )

        # Fase 5, NIEUW: response_style — zie _bepaal_response_style()
        # voor de volledige uitleg (incl. de eerlijke kanttekening dat
        # dit nog NIET effectief gebruikt wordt om antwoorden aan te
        # passen, enkel berekend/gepubliceerd wordt).
        response_style = self._bepaal_response_style(
            should_interrupt,
            activiteit_label,
            activiteit_duur_minuten,
            focus_niveau,
            is_alleen,
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
            "faces_detected": aantal_gezichten,
            "is_alone": is_alleen,
            "should_interrupt": should_interrupt,
            "response_style": response_style,
            "reden": reden,
        }

        self.context = context

        if self.event_bus is not None:
            self.event_bus.publish("context:updated", context)

        self._log_naar_schijf(context)

        return context

    def update_presence_info(self):
        """
        Fase 4: vraagt presence_detector.py EENMALIG een nieuwe webcam-
        meting, en onthoudt het resultaat als "laatst bekend" tot de
        volgende aanroep. Wordt AANGEROEPEN VANUIT main.py's
        achtergrond_loop(), spaarzaam (elke
        PRESENCE_CHECK_INTERVAL_MINUTEN minuten), NIET vanuit
        get_current() zelf — zie toelichting daar.

        Als presence_detector niet beschikbaar is (ontbrekend pakket,
        webcam-fout), blijft de vorige "laatst bekende" waarde gewoon
        staan (of None als er nog nooit een geslaagde meting was) —
        we overschrijven NOOIT een goede laatste meting met "onbekend"
        enkel omdat 1 volgende poging toevallig faalde.
        """
        presence_detector = self.layers.get("presence_detector")
        if presence_detector is None:
            return

        try:
            info = presence_detector.detect_presence()
        except Exception as e:
            print(f"[CONTEXT_MANAGER] Fout bij update_presence_info(): {e}")
            return

        aantal_gezichten = info.get("faces_detected")
        is_alleen = info.get("is_alone")

        # Enkel bijwerken als de meting ECHT iets opleverde (niet None)
        # — anders zou een tijdelijke webcam-hik de laatst betrouwbare
        # waarde overschrijven met "onbekend".
        if aantal_gezichten is not None:
            self._laatst_bekende_presence["faces_detected"] = aantal_gezichten
            self._laatst_bekende_presence["is_alone"] = is_alleen

    def _bepaal_interrupt(
        self,
        is_gebruikelijk_moment,
        anomalieen_vandaag,
        activiteit_label,
        activiteit_duur_minuten,
        focus_niveau,
        is_alleen,
    ):
        """
        Fase 5: gewogen score-systeem (vervangt de oude "eerste match
        wint"-volgorde uit Fase 1-4).

        WERKING: elk signaal levert een vast, symbolisch puntenaantal
        op (zie de SCORE_*-constantes hierboven), positief of negatief.
        Alle punten worden opgeteld tot 1 totaalscore. Ligt die score
        op of boven INTERRUPT_SCORE_DREMPEL, dan mag Nova onderbreken;
        eronder niet. Dit vervangt de vroegere aanpak waarbij de EERSTE
        regel die matchte meteen alles besliste — nu wegen meerdere
        signalen tegelijk mee (bv. "wel een gebruikelijk moment, MAAR
        ook al een tijdje aan het coderen" geeft nu een eerlijke
        combinatie van beide, in plaats van dat de coding-regel alles
        overschaduwt).

        UITZONDERING — "niemand aanwezig" blijft een HARDE STOPREGEL,
        GEEN scoreregel: als is_alleen is True, wordt er NOOIT
        onderbroken, ongeacht hoe hoog de rest van de score zou zijn.
        Reden: spreken tegen een lege kamer heeft simpelweg geen nut,
        dat is geen kwestie van "een beetje minder overtuigend" maar
        van "compleet zinloos op dit moment". Dit blijft daarom, net
        als in Fase 4, VOOR de score-berekening gecheckt.

        BELANGRIJK: is_alleen kan None zijn (nog geen enkele geslaagde
        webcam-meting gehad, of presence_detector niet beschikbaar).
        We behandelen None BEWUST als "geen info", niet als "iemand
        is aanwezig" — vandaar `is_alleen is True`, niet `if is_alleen`.

        Geeft een tuple terug: (should_interrupt: bool, reden: str).
        De reden bevat nu ook de volledige score-opbouw, zodat Kevin
        in context_log.jsonl exact kan navertellen HOE een beslissing
        tot stand kwam — dit is precies waarom dit systeem symbolisch
        blijft i.p.v. ML: elke beslissing is stap voor stap leesbaar,
        in tegenstelling tot de "zwarte doos" van geleerde gewichten.
        """
        # --- Harde stopregel: niemand aanwezig (blijft VOOR de score) ---
        if is_alleen is True:
            return False, "niemand aanwezig volgens webcam (Fase 4) — harde stopregel, geen score"

        # --- Score opbouwen: elke regel voegt een (label, punten)-paar toe ---
        score_onderdelen = []

        # 1) Anomalieën vandaag — hoe meer, hoe negatiever, met een plafond
        #    (MAX_ANOMALIE_SCORE_AFTREK) zodat 1 extreme dag niet oneindig
        #    kan doorwegen.
        aantal_anomalieen = len(anomalieen_vandaag)
        if aantal_anomalieen > 0:
            aftrek = max(
                self.SCORE_ANOMALIE_PER_STUK * aantal_anomalieen,
                self.MAX_ANOMALIE_SCORE_AFTREK,
            )
            score_onderdelen.append(
                (f"{aantal_anomalieen} anomalie(ën) vandaag", aftrek)
            )

        # 2) Storingsgevoelige activiteit (bv. coding) + duur + focus
        is_storingsgevoelige_activiteit = (
            activiteit_label in self.STORINGSGEVOELIGE_ACTIVITEITEN
            and activiteit_duur_minuten >= self.CODING_ONDERBREEK_DREMPEL_MINUTEN
        )

        if is_storingsgevoelige_activiteit:
            if focus_niveau in self.FOCUS_NIVEAUS_ZONDER_ACTIEVE_AANWEZIGHEID:
                # Venster staat open, maar geen recente input — Kevin
                # is er waarschijnlijk niet meer actief mee bezig. Dit
                # telt dus juist LICHT POSITIEF mee (venster open, maar
                # afwezig is geen reden meer om terughoudend te zijn).
                score_onderdelen.append(
                    (
                        f"'{activiteit_label}' al {activiteit_duur_minuten:.0f} min, "
                        f"maar focus: {focus_niveau} (waarschijnlijk afwezig)",
                        self.SCORE_STORINGSGEVOELIGE_ACTIVITEIT_MAAR_AFWEZIG,
                    )
                )
            else:
                # focus_niveau is "actief" of "onbekend" — bij "onbekend"
                # (bv. geen Windows, API-fout) kiezen we bewust de
                # voorzichtige kant: dit telt gewoon mee als storend.
                score_onderdelen.append(
                    (
                        f"'{activiteit_label}' al {activiteit_duur_minuten:.0f} min "
                        f"(drempel: {self.CODING_ONDERBREEK_DREMPEL_MINUTEN} min), "
                        f"focus: {focus_niveau}",
                        self.SCORE_STORINGSGEVOELIGE_ACTIVITEIT_ACTIEF,
                    )
                )

        # 3) Gebruikelijk moment volgens Layer 2
        if is_gebruikelijk_moment:
            score_onderdelen.append(
                ("gebruikelijk moment volgens Layer 2", self.SCORE_GEBRUIKELIJK_MOMENT)
            )
        else:
            score_onderdelen.append(
                ("ongebruikelijk moment volgens Layer 2", self.SCORE_ONGEBRUIKELIJK_MOMENT)
            )

        # --- Totaalscore optellen ---
        totaalscore = sum(punten for _, punten in score_onderdelen)

        should_interrupt = totaalscore >= self.INTERRUPT_SCORE_DREMPEL

        # Leesbare reden: score-opbouw + eindresultaat, voor
        # nazicht/debug door Kevin (context_log.jsonl / "context"-commando).
        opbouw_tekst = ", ".join(
            f"{label}: {punten:+d}" for label, punten in score_onderdelen
        )
        reden = (
            f"score {totaalscore:+d} (drempel {self.INTERRUPT_SCORE_DREMPEL:+d}) — "
            f"{opbouw_tekst}"
        )

        return should_interrupt, reden

    def _bepaal_response_style(
        self,
        should_interrupt,
        activiteit_label,
        activiteit_duur_minuten,
        focus_niveau,
        is_alleen,
    ):
        """
        Fase 5, NIEUW: response_style — een advies over HOE Nova best
        zou antwoorden, los van OF ze mag onderbreken. Puur symbolisch,
        zelfde soort vaste regels als _bepaal_interrupt().

        BELANGRIJK, EERLIJKHEID OVER WAT DIT (NOG NIET) IS: dit veld
        wordt hier enkel BEREKEND en gepubliceerd in "context:updated"
        — het daadwerkelijk GEBRUIKEN ervan om Nova's antwoorden echt
        korter/uitgebreider te maken vereist een aparte integratiestap
        in response_engine.py/expression_injector.py (Layer 4/6), die
        dit NIET automatisch oppikt enkel omdat dit veld nu bestaat.
        Dit is bewust dezelfde situatie als personality_engine.py's
        output nu: klaar om op aan te sluiten, nog niet aangesloten.

        Regels (simpel, uitbreidbaar):
        - Mag Nova sowieso niet onderbreken? Dan is de vraag "hoe"
          niet relevant — "normaal" als neutrale standaardwaarde.
        - Storingsgevoelige activiteit (coding) met actieve focus?
          Dan kort, want Kevin is duidelijk met iets anders bezig.
        - Rustig moment, geen storingsgevoelige activiteit, focus
          "mogelijk_afwezig"/"waarschijnlijk_weg" (Kevin heeft dus
          tijd, geen druk venster open)? Dan uitgebreid mag.
        - Standaard: normaal.
        """
        if not should_interrupt:
            return self.RESPONSE_STYLE_NORMAAL

        is_storingsgevoelige_activiteit = (
            activiteit_label in self.STORINGSGEVOELIGE_ACTIVITEITEN
            and activiteit_duur_minuten >= self.CODING_ONDERBREEK_DREMPEL_MINUTEN
        )

        if is_storingsgevoelige_activiteit and focus_niveau == "actief":
            return self.RESPONSE_STYLE_KORT

        if (
            not is_storingsgevoelige_activiteit
            and focus_niveau in self.FOCUS_NIVEAUS_ZONDER_ACTIEVE_AANWEZIGHEID
        ):
            return self.RESPONSE_STYLE_UITGEBREID

        return self.RESPONSE_STYLE_NORMAAL

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

        gezichten = ctx.get("faces_detected")
        gezichten_tekst = str(gezichten) if gezichten is not None else "onbekend"

        return (
            f"Tijd: {ctx['hour']}u — "
            f"Gebruikelijk moment: {ctx['is_gebruikelijk_moment']} — "
            f"Anomalieën vandaag: {ctx['aantal_anomalieen_vandaag']} — "
            f"Activiteit: {ctx['activity']} "
            f"({ctx['activity_duration_minutes']:.1f} min) — "
            f"Focus: {ctx['focus_level']} (laatste input: {seconden_tekst}) — "
            f"Gezichten: {gezichten_tekst} — "
            f"Mag onderbreken: {ctx['should_interrupt']} — "
            f"Response-stijl: {ctx.get('response_style', '?')} "
            f"(reden: {ctx['reden']})"
        )


def init_module(event_bus, layers=None):
    """
    LET OP — dit bestand volgt NIET de standaard dynamische
    module_loader-conventie (init_module(event_bus, sem)), net zoals
    response_engine.py dat ook niet doet. De reden is dezelfde: Layer 5
    heeft een "layers"-dictionary nodig (met pattern_matcher,
    activity_detector, focus_detector EN presence_detector erin), geen
    losse "sem"-parameter.

    Daarom moet dit bestand, net als response_engine.py, HANDMATIG
    geladen worden in module_loader.py — NIET via de automatische
    pkgutil-scan in stap 3. Concreet: dit hoort in module_loader.py
    op een plek NA het laden van pattern_matcher.py, activity_detector.py,
    focus_detector.py EN presence_detector.py (alle vier dynamische
    modules-stap), zodat self.loaded_modules.get(...) al bestaat op het
    moment dat context_manager geladen wordt.
    """
    instance = ContextManager(event_bus, layers=layers)
    if event_bus is not None:
        event_bus.publish("module_loaded", {"name": "context_manager"})
    return instance