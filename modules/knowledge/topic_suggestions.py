# modules/knowledge/topic_suggestions.py
"""
Topic Suggestions — Fase 5 van topic_events_roadmap.md, punt 7 van
nova_state.md's "Volgende stappen" (13 augustus 2026).

Nova die ONGEVRAAGD een sjabloonzin uitspreekt op basis van een
topic-tijdspatroon, bv. "Het is 19u, wil je een potje schaken?" omdat
dat het gebruikelijke moment is. Zelfde soort periodieke achtergrond-
check als contradiction_checker.py (punt 2, 6 augustus 2026) en
emergence_engine.reflect() -- geroepen vanuit main.py's
achtergrond_loop(), niet vanuit het gesprek zelf.

Puur symbolisch: leest enkel bestaande, al-getelde data
(pattern_matcher.is_pattern_active()) en context_manager.can_interrupt(),
formatteert een vast sjabloon. Geen ML, geen generatie -- elk woord in
de uiteindelijke zin komt letterlijk uit een whitelist of een vaste
sjabloonstring (zelfde "eerlijkheid"-principe als topic_events_
roadmap.md zelf voorschrijft).

BEWUST NIET hetzelfde als het nieuwe punt 25 ("ik weet niet wat te
doen" -> suggestie): dit hier triggert op TIJDSTIP (is_pattern_active()),
punt 25 zou triggeren op een HERKENDE, vrije uitspraak van Kevin. Twee
verschillende triggers, bewust niet in dezelfde module vermengd.

Whitelist-principe (zelfde reden als emergence_engine.py's
INSIGHT_WAARDIGE_ACTIVITEITEN, 30 juli 2026): niet elk topic_detected:-
onderwerp is geschikt om ONGEVRAAGD als "wil je een potje X?"
voorgesteld te worden -- "wil je een potje het weer?" zou raar klinken.
Nieuwe topics zijn dus standaard stil totdat Kevin ze hier expliciet
toevoegt. Voorlopig enkel "chess" (Kevin's akkoord, 13 augustus 2026).

Tweede trigger (15 september 2026, nova_state.md punt 18): naast de
bestaande TIJD-trigger (is_pattern_active()) telt nu ook een
ACTIVITEIT-trigger mee, via context_manager.get_relevant_topics()
(Layer 5-restje van 13 sept 2026, tot nu toe zonder aanroeper). Puur
symbolisch: get_relevant_topics() is zelf enkel een vaste lookup in
ACTIVITEIT_NAAR_TOPICS, geen classifier/embedder. Beide triggers delen
dezelfde TOPIC_WHITELIST/spam-preventie/can_interrupt()-gate hieronder
-- enkel de MANIER waarop een topic als "kandidaat" gevonden wordt is
verschillend (klok vs. huidige activiteit).

Eerlijke kanttekening: ACTIVITEIT_NAAR_TOPICS (context_manager.py)
bevat vandaag geen enkele activiteit die naar "chess" wijst -- deze
koppeling verandert dus nog NIETS zichtbaars totdat Kevin ooit een
activiteit expliciet aan "chess" koppelt in die tabel. Bewust toch nu
al gebouwd (Kevin's akkoord, 15 september 2026), zelfde "klaarzetten
voor later"-aanpak als get_relevant_topics() zelf destijds.
"""

import json
from datetime import datetime

from modules.paths import get_project_root


class TopicSuggestions:

    STATE_BESTAND = "data/topic_suggestion_state.json"

    # Welke topic_detected:<naam>-onderwerpen mogen ooit als "wil je
    # een potje X?"-suggestie voorgesteld worden. Whitelist i.p.v.
    # blacklist: nieuwe topics (Plex, dammen, Go, ...) zijn standaard
    # UITGESLOTEN totdat Kevin ze hier bewust toevoegt, samen met het
    # bijhorende sjabloon in _sjabloon_voor().
    TOPIC_WHITELIST = {"chess"}

    # Vertaalt de interne topic-naam naar het woord dat in de
    # sjabloonzin moet komen. Bewust een KLEINE, eigen tabel i.p.v.
    # emergence_engine.py's _topic_naam_labels hergebruiken: die tabel
    # bevat ook topics (weer, rekenen, definities) waarvoor dit
    # sjabloon nooit gebruikt mag worden -- een eigen, kleinere tabel
    # voorkomt dat een toekomstige toevoeging aan de ANDERE tabel hier
    # per ongeluk ook een ongepaste suggestie triggert.
    _topic_naam_labels = {
        "chess": "schaken",
    }

    def __init__(self, event_bus, pattern_matcher=None, context_manager=None):
        self.event_bus = event_bus
        self.pattern_matcher = pattern_matcher
        self.context_manager = context_manager
        self.project_root = get_project_root(__file__)
        self.state_pad = self.project_root / self.STATE_BESTAND

        # Spam-preventie: onthoudt het uur (0-23) waarop een topic
        # voor het laatst voorgesteld is, per topic-naam. Zonder dit
        # zou Nova elke minuut opnieuw "wil je schaken?" zeggen zolang
        # is_pattern_active() True blijft binnen hetzelfde uur.
        self._laatst_voorgesteld = self._laad_state()

        print("[TopicSuggestions] module geladen")

    # ------------------------------------------------------------------
    def _laad_state(self):
        if self.state_pad.exists():
            try:
                with open(self.state_pad, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _sla_state_op(self):
        self.state_pad.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.state_pad, "w", encoding="utf-8") as f:
                json.dump(self._laatst_voorgesteld, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    # ------------------------------------------------------------------
    def _sjabloon_voor(self, topic_naam: str, uur: int) -> str:
        """
        Bouwt de sjabloonzin voor 1 topic. Vaste string, geen
        generatie -- {uur} en {onderwerp} komen letterlijk uit
        opgeslagen data (huidig uur, TOPIC_WHITELIST/_topic_naam_labels).
        """
        onderwerp = self._topic_naam_labels.get(topic_naam, topic_naam)
        return f"Het is {uur}u — wil je een potje {onderwerp}?"

    # ------------------------------------------------------------------
    def status_nu(self) -> list[dict]:
        """
        Read-only variant voor het debug-commando 'topic suggesties':
        toont per gewhitelist topic of het patroon NU actief is en of
        can_interrupt() het toelaat, ZONDER de spam-preventie-state te
        wijzigen of daadwerkelijk een layer4_response te publiceren.
        Analoog aan contradiction_checker.alle_contradicties_nu().
        """
        resultaat = []
        nu = datetime.now()
        huidig_uur = nu.hour
        vandaag = nu.strftime("%Y-%m-%d")

        for topic_naam in self.TOPIC_WHITELIST:
            event_type = f"topic_detected:{topic_naam}"
            actief = False
            if self.pattern_matcher:
                try:
                    actief = self.pattern_matcher.is_pattern_active(event_type)
                except Exception:
                    actief = False

            mag_onderbreken = True
            if self.context_manager:
                mag_onderbreken = self.context_manager.can_interrupt()

            sleutel = f"{vandaag}:{huidig_uur}"
            al_voorgesteld = self._laatst_voorgesteld.get(topic_naam) == sleutel

            resultaat.append({
                "topic": topic_naam,
                "event_type": event_type,
                "patroon_actief": actief,
                "mag_onderbreken": mag_onderbreken,
                "al_voorgesteld_dit_uur": al_voorgesteld,
                "zou_nu_spreken": actief and mag_onderbreken and not al_voorgesteld,
            })
        return resultaat

    # ------------------------------------------------------------------
    # Kandidaat-bepaling -- twee onafhankelijke triggers, zelfde
    # whitelist/gates erna (punt 18, 15 september 2026)
    # ------------------------------------------------------------------
    def _tijd_kandidaten(self) -> set[str]:
        """
        Trigger 1 (bestaand): topics waarvoor NU het gebruikelijke
        moment is, volgens Layer 2 (pattern_matcher.is_pattern_active()
        op "topic_detected:<naam>"). Enkel topics uit TOPIC_WHITELIST.
        """
        if not self.pattern_matcher:
            return set()

        kandidaten = set()
        for topic_naam in self.TOPIC_WHITELIST:
            event_type = f"topic_detected:{topic_naam}"
            try:
                actief = self.pattern_matcher.is_pattern_active(event_type)
            except Exception as e:
                print(f"[TopicSuggestions] Fout bij is_pattern_active('{event_type}'): {e}")
                continue
            if actief:
                kandidaten.add(topic_naam)
        return kandidaten

    def _activiteit_kandidaten(self) -> set[str]:
        """
        Trigger 2 (nieuw, punt 18): topics die horen bij de HUIDIGE
        activiteit, via context_manager.get_relevant_topics() (Layer 5-
        restje, 13 sept 2026). Puur een vaste lookup in
        ACTIVITEIT_NAAR_TOPICS aan de kant van context_manager.py --
        hier enkel doorgefilterd tegen TOPIC_WHITELIST, zelfde principe
        als bij _tijd_kandidaten hierboven: een topic dat relevant is
        voor de activiteit, mag nog steeds niet ongevraagd voorgesteld
        worden als het niet expliciet gewhitelist is.

        Ontbrekende context_manager, of een fout in get_relevant_topics()
        zelf -- geeft gewoon een lege set terug, nooit een crash (zelfde
        defensieve stijl als de rest van deze module).
        """
        if not self.context_manager:
            return set()

        try:
            relevante_topics = self.context_manager.get_relevant_topics()
        except Exception as e:
            print(f"[TopicSuggestions] Fout bij get_relevant_topics(): {e}")
            return set()

        return {t for t in relevante_topics if t in self.TOPIC_WHITELIST}

    # ------------------------------------------------------------------
    # Kernmethode -- wordt aangeroepen vanuit main.py's achtergrond_loop(),
    # zelfde patroon als contradiction_checker.check_contradictions() en
    # emergence.reflect().
    # ------------------------------------------------------------------
    def check_suggesties(self):
        """
        Verzamelt kandidaat-topics uit TWEE onafhankelijke triggers
        (_tijd_kandidaten: gebruikelijk moment volgens Layer 2;
        _activiteit_kandidaten: relevant voor de huidige activiteit,
        via context_manager.get_relevant_topics()) en checkt per
        kandidaat of context_manager.can_interrupt() het toelaat. Bij
        een match: publiceert de sjabloonzin naar layer4_response, en
        onthoudt dat dit topic dit uur al voorgesteld is (spam-preventie)
        -- ongeacht via welke trigger het gevonden werd.

        Stopt na de EERSTE geschikte suggestie in deze cyclus -- twee
        losse "wil je een potje X?"-vragen na elkaar zou raar aanvoelen,
        en de whitelist is momenteel toch nog klein (1 topic).
        """
        kandidaten = self._tijd_kandidaten() | self._activiteit_kandidaten()
        if not kandidaten:
            return

        nu = datetime.now()
        huidig_uur = nu.hour
        vandaag = nu.strftime("%Y-%m-%d")

        for topic_naam in kandidaten:
            # Spam-preventie: dit exacte topic is dit exacte uur, op
            # deze exacte dag, al eens voorgesteld -- niet opnieuw.
            sleutel = f"{vandaag}:{huidig_uur}"
            if self._laatst_voorgesteld.get(topic_naam) == sleutel:
                continue

            # Timing-gate, zelfde check als session_watcher.py en
            # emergence_engine.py's _mag_nu_spreken() -- ontbrekende
            # context_manager mag de suggestie nooit blokkeren (zelfde
            # "nooit stiller dan voorheen"-principe als bij Layer 5).
            if self.context_manager and not self.context_manager.can_interrupt():
                continue

            tekst = self._sjabloon_voor(topic_naam, huidig_uur)
            self._laatst_voorgesteld[topic_naam] = sleutel
            self._sla_state_op()

            self.event_bus.publish("layer4_response", {"text": tekst})
            return  # 1 suggestie per cyclus is genoeg


def init_module(event_bus, pattern_matcher=None, context_manager=None):
    suggesties = TopicSuggestions(event_bus, pattern_matcher, context_manager)
    event_bus.publish("module_loaded", {"name": "topic_suggestions"})
    return suggesties