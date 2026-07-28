#modules/chat/conversation_engine.py
"""
Laag: fallback-conversatie (geen LLM, puur symbolisch).

Wordt NIET zelf op "intent_fallback" geabonneerd -- dat zou naast
response_pipeline.py's on_fallback() een TWEEDE, apart antwoord
publiceren. In plaats daarvan roept response_pipeline.py's
on_fallback() de methode probeer_activiteit_observatie() hier
rechtstreeks aan, VOOR het zijn eigen standaard sjabloon kiest --
zelfde patroon als intent_router.py dat al doet met
response_engine.generate() vs. de Wikipedia-fallback.

Onthoudt de laatst gebruikte praatvorm in data/conversation_state.json,
zodat dezelfde vorm niet 2x na elkaar gekozen wordt (blijft ook bestaan
over een /reboot heen, want elke keuze wordt meteen weggeschreven).

Fase 1: enkel de praatvorm "activiteit_observatie".
Latere fases voegen mood_observatie / topic_terugkoppeling /
kennisdichtheid_terugkoppeling / bodemzin toe, volgens hetzelfde patroon.
"""

import json
import random
import time

from modules.paths import get_project_root


class ConversationEngine:

    STATE_BESTAND = "data/conversation_state.json"

    # Hoeveel minuten moeten voorbij zijn voor dezelfde praatvorm
    # opnieuw mag -- voorkomt dat Nova elke keer opnieuw "je bent al
    # een tijdje bezig" zegt bij elk los bericht, maar laat haar wel
    # blijven reageren op een langere coderen-sessie i.p.v. na 1 keer
    # voorgoed stil te vallen op dit vlak.
    HERHALING_DREMPEL_MINUTEN = 10

    ACTIVITEIT_OPENINGEN = [
        "Ik zie dat je al een tijdje met {activiteit} bezig bent.",
        "Je bent nu al {duur} met {activiteit} bezig.",
        "Nog steeds aan het {activiteit}?",
        "Je zit al een poosje in de {activiteit}-modus.",
    ]

    ACTIVITEIT_AFSLUITINGEN = [
        "Hoe gaat het ermee?",
        "Alles nog onder controle?",
        "Nog lang mee bezig?",
    ]

    ACTIVITEIT_LABELS = {
        "coding": "coderen",
        "talking_to_nova": "praten met mij",
    }

    # --- Drempels voor mood_observatie (Layer 6) ---
    # Consistent met generate_response_style()'s bestaande 0.8-drempel
    # voor "snel" tempo, iets ruimer gezet zodat mood_observatie ook
    # echt kans krijgt om te triggeren in de praktijk.
    ENERGIE_HOOG_DREMPEL = 0.7
    ENERGIE_LAAG_DREMPEL = 0.3
    # Bewust lager dan de bestaande 0.75-crisisdrempel elders in Nova
    # (zie emotion_rules.json/overstimulation-decay) -- dit is een
    # vroeger, zachter signaal, geen alarmsituatie.
    OVERSTIMULATION_DREMPEL = 0.5

    MOOD_ENERGIEK_OPENINGEN = [
        "Ik voel me best energiek vandaag, eerlijk gezegd.",
        "Ik zit boordevol energie op dit moment.",
        "Ik voel me nu best levendig, moet ik zeggen.",
    ]

    MOOD_RUSTIG_OPENINGEN = [
        "Ik voel me nu wat rustiger aan.",
        "Ik ben op dit moment in een kalmere modus.",
        "Het is nu wat stiller vanbinnen bij mij, zeg maar.",
    ]

    MOOD_OVERPRIKKELD_OPENINGEN = [
        "Ik voel me nu een beetje overprikkeld, eerlijk gezegd.",
        "Er komt nu best veel tegelijk binnen bij mij.",
        "Ik heb nu wat meer moeite om alles rustig te verwerken.",
    ]

    MOOD_AFSLUITINGEN = [
        "Hoe is het met jou?",
        "En bij jou, hoe voel jij je?",
        "Hoe zit het bij jou?",
    ]

    def __init__(self, event_bus, semantic_module=None):
        self.event_bus = event_bus
        self.project_root = get_project_root(__file__)
        self.state_pad = self.project_root / self.STATE_BESTAND
        self.laatste_praatvorm, self.laatste_observatie_tijdstip = self._laad_state()

    # ------------------------------------------------------------------
    def _laad_state(self):
        if self.state_pad.exists():
            try:
                with open(self.state_pad, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data.get("laatste_praatvorm"), data.get("laatste_observatie_tijdstip")
            except (json.JSONDecodeError, OSError):
                return None, None
        return None, None

    def _sla_state_op(self):
        self.state_pad.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.state_pad, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "laatste_praatvorm": self.laatste_praatvorm,
                        "laatste_observatie_tijdstip": self.laatste_observatie_tijdstip,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except OSError:
            pass

    def _mag_opnieuw_observeren(self):
        """
        True als er nog nooit een observatie was, OF als de laatste
        observatie langer dan HERHALING_DREMPEL_MINUTEN geleden is.
        Vervangt het oude "nooit 2x na elkaar"-hard-slot: dat liet
        Nova bij een lange coderen-sessie voorgoed stil vallen op dit
        vlak, ook al bleef Kevin gewoon doorpraten.
        """
        if self.laatste_observatie_tijdstip is None:
            return True
        verstreken_minuten = (time.time() - self.laatste_observatie_tijdstip) / 60
        return verstreken_minuten >= self.HERHALING_DREMPEL_MINUTEN
    
    # ------------------------------------------------------------------
    def _formatteer_duur(self, minuten):
        if minuten is None:
            return None

        if minuten < 5:
            return "een paar minuten"

        gebruik_rond = random.random() < 0.65

        if gebruik_rond:
            if minuten < 20:
                return "een kwartiertje"
            elif minuten < 40:
                return "een half uurtje"
            elif minuten < 75:
                return "meer dan een uur"
            else:
                uren = round(minuten / 60)
                return f"zo'n {uren} uur"
        else:
            return f"{int(minuten)} minuten"

    # ------------------------------------------------------------------
    # Publieke methode -- wordt aangeroepen door response_pipeline.py's
    # on_fallback(), NIET via een eigen event-subscribe. Geeft een
    # kant-en-klare tekst terug, of None als er niets bruikbaars is
    # (dan valt on_fallback() terug op zijn eigen standaard sjabloon).
    # ------------------------------------------------------------------
    def probeer_mood_observatie(self):
        """
        Kijkt naar Layer 6's actuele emotionele state (via
        event_bus.modules.get("personality"), zie response_pipeline.py's
        registratie) en geeft een observatie terug ALLEEN als er iets
        noemenswaardigs is (hoge/lage energie, of overprikkeling).
        Bij een gewone, gemiddelde staat geeft dit bewust None terug --
        we forceren geen sjabloon als er niets bijzonders te melden is,
        dat zou net zo nietszeggend zijn als de oude kale fallback.

        Gebruikt hetzelfde tijdvenster-mechanisme als
        probeer_activiteit_observatie() (_mag_opnieuw_observeren()),
        zodat de twee praatvormen elkaar niet direct na elkaar
        overlappen.
        """
        personality = self.event_bus.modules.get("personality")
        if personality is None:
            return None

        state = personality.state
        energie = state.get("current_energy")
        overstimulation = state.get("overstimulation_level")

        if energie is None or overstimulation is None:
            return None

        if not self._mag_opnieuw_observeren():
            return None

        # Overprikkeling heeft voorrang -- het is het meest
        # betekenisvolle signaal van de drie categorieën.
        if overstimulation > self.OVERSTIMULATION_DREMPEL:
            opening = random.choice(self.MOOD_OVERPRIKKELD_OPENINGEN)
        elif energie > self.ENERGIE_HOOG_DREMPEL:
            opening = random.choice(self.MOOD_ENERGIEK_OPENINGEN)
        elif energie < self.ENERGIE_LAAG_DREMPEL:
            opening = random.choice(self.MOOD_RUSTIG_OPENINGEN)
        else:
            return None  # gemiddelde staat, niets noemenswaardigs

        afsluiting = random.choice(self.MOOD_AFSLUITINGEN)
        volledige_tekst = f"{opening} {afsluiting}"

        self.laatste_praatvorm = "mood_observatie"
        self.laatste_observatie_tijdstip = time.time()
        self._sla_state_op()

        return volledige_tekst

    def probeer_activiteit_observatie(self):
        context_manager = self.event_bus.modules.get("context_manager")
        if context_manager is None:
            return None

        context = context_manager.get_current()
        activiteit_raw = context.get("activity")
        duur_minuten = context.get("activity_duration_minutes")

        if not activiteit_raw or activiteit_raw not in self.ACTIVITEIT_LABELS:
            return None

        vorm_naam = "activiteit_observatie"
        if not self._mag_opnieuw_observeren():
            return None

        activiteit_tekst = self.ACTIVITEIT_LABELS[activiteit_raw]
        duur_tekst = self._formatteer_duur(duur_minuten)

        opening = random.choice(self.ACTIVITEIT_OPENINGEN)
        if "{duur}" in opening and duur_tekst is None:
            opening = random.choice(
                [o for o in self.ACTIVITEIT_OPENINGEN if "{duur}" not in o]
            )

        afsluiting = random.choice(self.ACTIVITEIT_AFSLUITINGEN)

        zin = opening.format(activiteit=activiteit_tekst, duur=duur_tekst)
        volledige_tekst = f"{zin} {afsluiting}"

        self.laatste_praatvorm = vorm_naam
        self.laatste_observatie_tijdstip = time.time()
        self._sla_state_op()

        return volledige_tekst


def init_module(event_bus, semantic_module=None):
    return ConversationEngine(event_bus, semantic_module)