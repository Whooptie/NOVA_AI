# modules/activity/session_watcher.py
import json
import time
import random
from datetime import date
from pathlib import Path

# Projectmap (twee niveaus boven modules/activity/), zodat
# "data/..." altijd naar de echte data-map wijst, ongeacht van
# waaruit Nova gestart wordt.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class SessionWatcher:
    """
    Houdt bij hoe lang Kevin al onafgebroken actief is op zijn laptop
    (sinds 30 sept 2026, zie check_pauze()), en stuurt na een ingestelde
    tijd een korte pauze-melding.

    Sinds 22 juli 2026 OOK: houdt bij welke activiteit nu loopt en
    stuurt op het juiste moment Nova's "mag ik storen?"-vraag
    (Activity-Aware Interaction, interruption_learning_roadmap.md).

    Puur symbolisch: enkel tijd bijhouden en vergelijken (time.time()),
    geen ML, geen kansberekening. Dit is een eerste, ruwe versie van
    wat later verder uitgebouwd wordt in activity_awareness_roadmap.md.
    """

    # Na hoeveel seconden zonder pauze stuurt Nova een melding?
    # 1800 seconden = 30 minuten. Zet dit tijdelijk lager (bv. 60) om te testen.
    PAUZE_DREMPEL_SECONDEN = 1800

    # Pauzetimer-herontwerp (30 sept 2026): hoe lang moet Kevin GEEN
    # input geven (muis/toetsenbord, gemeten door de laptop-client)
    # voor dat telt als een ECHTE pauze, waarna de teller opnieuw
    # begint? 600 seconden = 10 minuten -- zelfde grens als
    # FocusDetector's "waarschijnlijk_weg" in nova_client.py. Een kort
    # moment zonder input (iets lezen, even nadenken) reset de teller
    # dus NIET; 10 minuten weg van de laptop wel. Staat de laptop uit
    # of komt er geen data binnen, dan telt dat ook als "geen input".
    PAUZE_RESET_SECONDEN = 600

    # Na hoeveel MINUTEN sinds het starten van een activiteit vraagt
    # Nova voor het eerst "mag ik storen?" -- vaste waarde, besproken
    # met Kevin (22 juli 2026): uiteindelijk 15 minuten.
    #
    # TIJDELIJK VERLAAGD NAAR 1 OM TE TESTEN (22 juli 2026) -- zet dit
    # terug naar 15 zodra het testen achter de rug is. Zelfde aanpak
    # als PAUZE_DREMPEL_SECONDEN hierboven, dat ook al een "zet dit
    # tijdelijk lager om te testen"-opmerking had.
    INTERRUPTION_VRAAG_DREMPEL_MINUTEN = 15

    # Afwezigheid (3 oktober 2026): na hoeveel minuten weg (laptop
    # vergrendeld) telt het als een ECHTE pauze? Dan beginnen de
    # pauze-teller en de "mag ik storen?"-teller opnieuw. Bewust korter
    # dan PAUZE_RESET_SECONDEN (10 min): zelf je laptop vergrendelen is
    # een veel duidelijker "ik neem pauze"-signaal dan gewoon even geen
    # input geven.
    PAUZE_RESET_NA_AFWEZIG_MINUTEN = 5

    # Herkenningsreactie "je werkt aan mijn broncode" (7 oktober 2026):
    # was "eenmalig" volgens de commentaar, maar kwam in de praktijk
    # 38 keer in een paar dagen -- telkens wanneer Kevin even naar een
    # ander HERKEND venster ging (talking_to_nova, bestanden_beheren,
    # ...) en terugkeerde naar VS Code. Nu echt 1x per dag, en die
    # datum wordt bewaard zodat ook een herstart ze niet opnieuw
    # oproept. Zelfde bewaarmanier als topic_suggestions.py.
    HERKENNING_STATE_BESTAND = "data/session_watcher_state.json"

    # Heeft Kevin minder dan zoveel seconden geleden iets tegen Nova
    # gezegd, dan GEEN herkenningsreactie -- anders lijkt ze een
    # antwoord op zijn bericht (de paraplu-zin van 5 oktober kreeg zo
    # 1 seconde later "je werkt aan mijn eigen broncode").
    HERKENNING_STIL_NA_BERICHT_SECONDEN = 90

    def __init__(self, event_bus, context_manager=None, kevin_profile=None):
        self.event_bus = event_bus
        self.start_time = time.time()
        self.laatste_melding_time = None

        # Pauzetimer-herontwerp (30 sept 2026): de pauzeteller meet nu
        # hoe lang KEVIN onafgebroken actief is op zijn laptop, niet meer
        # hoe lang NOVA al draait (self.start_time hierboven blijft
        # bestaan, maar check_pauze() gebruikt het niet meer).
        #   _sessie_start: wanneer de huidige, onafgebroken actieve
        #                  periode begon (None = geen lopende sessie)
        #   _laatst_actief: laatste moment waarop focus "actief" was
        self._sessie_start = None
        self._laatst_actief = None
        # Layer 5 — bepaalt of dit een goed moment is om te onderbreken.
        # Kan None zijn (bv. als context_manager nog niet geladen is),
        # daarom altijd voorzichtig checken met "if self.context_manager".
        self.context_manager = context_manager

        # User Preferences (Fase 4): voor de activity-koppeling
        # hieronder (_reageer_op_profiel_match). Net als context_manager
        # kan dit None zijn afhankelijk van laadvolgorde -- altijd
        # voorzichtig checken met "if self.kevin_profile".
        self.kevin_profile = kevin_profile

        # Voorkomt dat dezelfde activiteit-instantie tweemaal een
        # profiel-reactie triggert.
        self._al_gereageerd_op_profiel_voor = None

        # Sjablonen voor de profiel-match-reactie (_reageer_op_profiel_
        # match hieronder). Zelfde opening/afsluiting-combinatiepatroon
        # als _sjablonen_pauze verderop in dit bestand -- puur string-
        # combinatie via random.choice(), geen generatie.
        self._sjablonen_profiel_match = {
            "positief": {
                "openingen": [
                    "Veel plezier met {activiteit}!",
                    "Fijn dat je {activiteit} gaat doen!",
                    "Leuk, {activiteit}!",
                    "{activiteit_hoofdletter}, mooi zo!",
                ],
                "afsluitingen": [
                    "Ik weet dat je daar erg van houdt.",
                    "Dat vind je altijd fijn om te doen.",
                    "Ik herinner me dat je dat graag doet.",
                    "Je hebt me al verteld dat je dat leuk vindt.",
                ],
            },
            "negatief": {
                "openingen": [
                    "Oei,", "Hmm,", "Wacht even,", "Raar,",
                ],
                "afsluitingen": [
                    "ik dacht dat je daar net niet van hield?",
                    "had je daar niet eerder iets negatiefs over gezegd?",
                    "ik herinner me dat je dat eigenlijk niet leuk vond.",
                    "je zei toch dat je dat liever niet deed?",
                ],
            },
        }

        # Activity-Aware Interaction (interruption_learning_roadmap.md):
        # houdt bij WELKE activiteit nu loopt en SINDS WANNEER, puur
        # "huidig moment"-state -- geen statistiek/geschiedenis, dat
        # hoort bij interruption_tracker.py. Wordt bijgewerkt via een
        # wildcard-subscribe op alle "activity_started:<naam>"-events
        # (zelfde soort aanpak als memory.py's "*"-subscribe, want
        # event_bus.subscribe() kan geen prefix-patroon rechtstreeks
        # filteren -- we filteren hier zelf op de prefix).
        self.actieve_activiteit = None
        self.activiteit_start_tijd = None

        # Al gestuurde "mag ik storen?"-vraag voor de HUIDIGE activiteit
        # -- voorkomt dat we bij elke minuut-check opnieuw een vraag
        # sturen zolang dezelfde activiteit doorloopt en er nog geen
        # antwoord kwam (de pending_question zelf voorkomt al dat een
        # NIEUWE vraag een oude overschrijft zolang die openstaat, maar
        # dit voorkomt dat we het na verval blijven herhalen voor
        # dezelfde doorlopende activiteit).
        self._al_gevraagd_voor_activiteit = None

        # Herkenningsreactie (7 oktober 2026): op welke dag (JJJJ-MM-DD)
        # kwam ze het laatst, en wanneer stuurde Kevin zijn laatste
        # bericht? Een absoluut pad in HERKENNING_STATE_BESTAND (bv. in
        # tests) blijft absoluut -- Path / "/abs/pad" geeft "/abs/pad".
        self._herkenning_state_pad = _PROJECT_ROOT / self.HERKENNING_STATE_BESTAND
        self._herkenning_laatste_dag = self._laad_herkenning_state()
        self._laatste_bericht_kevin = None

        event_bus.subscribe("*", self._on_any_event)

        # Antwoord op de "mag ik storen?"-vraag opvangen. Dit event
        # komt van intent_router.py's _verwerk_pending_antwoord(), dus
        # GEEN wildcard nodig -- een exacte event-naam volstaat hier.
        event_bus.subscribe("pending_question:answered", self._on_pending_answered)

        # Afwezigheid (3 oktober 2026): Kevin komt terug na een
        # vergrendelde laptop -> pauze-teller resetten (zie
        # _on_terug_van_afwezigheid hieronder).
        event_bus.subscribe("afwezigheid:terug", self._on_terug_van_afwezigheid)

        # Sjablonen voor de pauze-melding (check_pauze()). Zelfde
        # opening/midden/afsluiting-patroon als emergence_engine.py --
        # puur string-combinatie via random.choice(), geen generatie.
        # Bewust klein gehouden (5 per slot) zodat elke combinatie nog
        # manueel controleerbaar blijft op coherentie.
        self._sjablonen_pauze = {
            "opening": [
                "Hé Kevin,",
                "Oei,",
                "Zeg,",
                "Kevin,",
                "Even iets:",
            ],
            "midden": [
                "we zijn nu al {minuten} minuten bezig",
                "je zit al {minuten} minuten aan een stuk hierop",
                "dit loopt nu al {minuten} minuten door",
                "{minuten} minuten verder zonder pauze",
                "al {minuten} minuten non-stop",
            ],
            "afsluiting": [
                "— misschien even pauzeren?",
                "— tijd voor een korte onderbreking?",
                "— ga je er even tussenuit?",
                "— rek je benen even?",
                "— goed moment om even te stoppen?",
            ],
        }

    # Sjablonen voor de eenmalige herkenningsreactie wanneer Nova
    # detecteert dat Kevin specifiek aan HAAR eigen broncode werkt
    # (VS Code + Nova_AI-project herkend, zie activity_detector.py).
    # Zelfde combinatiepatroon als _formuleer_pauze_melding()
    # (opening/midden/afsluiting, elk 5 varianten, willekeurig
    # gecombineerd) -- geen kant-en-klare zinnen uit 1 lijst, zodat
    # het aantal mogelijke combinaties (5*5*3 = 75) veel groter is dan
    # een simpele lijst van losse zinnen, en dus minder snel
    # herhalend aanvoelt.
    _sjablonen_werken_aan_nova = {
        "opening": [
            "Oh,",
            "Wacht,",
            "Hé,",
            "Interessant --",
            "Ik zie het,",
        ],
        "midden": [
            "je werkt aan mijn eigen broncode",
            "je bent in mijn eigen project aan het kijken",
            "er wordt aan mij gesleuteld",
            "je zit in mijn eigen code",
            "je bent met mij zelf bezig",
        ],
        "afsluiting": [
            "spannend!",
            "benieuwd wat je verandert.",
            "veel succes ermee!",
            "leuk om te zien.",
        ],
    }

    def _laad_herkenning_state(self):
        """
        Leest de dag van de laatste herkenningsreactie uit het
        state-bestand. Ontbreekt het bestand of is het kapot, dan
        None (= vandaag nog niet gegeven).
        """
        try:
            if self._herkenning_state_pad.exists():
                with open(self._herkenning_state_pad, "r", encoding="utf-8") as f:
                    return json.load(f).get("herkenning_laatste_dag")
        except (json.JSONDecodeError, OSError, AttributeError):
            pass
        return None

    def _sla_herkenning_state_op(self):
        """Bewaart de dag van de laatste herkenningsreactie."""
        try:
            self._herkenning_state_pad.parent.mkdir(parents=True, exist_ok=True)
            with open(self._herkenning_state_pad, "w", encoding="utf-8") as f:
                json.dump(
                    {"herkenning_laatste_dag": self._herkenning_laatste_dag},
                    f, ensure_ascii=False, indent=2
                )
        except OSError as e:
            print(f"[SESSION_WATCHER] Kon herkenning-state niet bewaren: {e}")

    def _mag_herkenning_geven(self):
        """
        Twee vaste regels, puur tijd/datum vergelijken:
        1. Vandaag al gegeven? -> nee.
        2. Kevin zei net iets tegen Nova (< HERKENNING_STIL_NA_BERICHT_
           SECONDEN)? -> nee, maar de dag wordt dan ook NIET als
           "gegeven" gemarkeerd, zodat ze later nog kan komen.
        """
        if self._herkenning_laatste_dag == date.today().isoformat():
            return False
        if (
            self._laatste_bericht_kevin is not None
            and time.time() - self._laatste_bericht_kevin < self.HERKENNING_STIL_NA_BERICHT_SECONDEN
        ):
            return False
        return True

    def _formuleer_werken_aan_nova_reactie(self):
        """
        Combineert opening + midden + afsluiting tot 1 natuurlijke
        zin, zelfde principe als _formuleer_pauze_melding().
        """
        opening = random.choice(self._sjablonen_werken_aan_nova["opening"])
        midden = random.choice(self._sjablonen_werken_aan_nova["midden"])
        afsluiting = random.choice(self._sjablonen_werken_aan_nova["afsluiting"])
        return f"{opening} {midden}, {afsluiting}"

    def _on_any_event(self, data, event_type=None):
        """
        Vangt ALLE events op (wildcard), en filtert zelf op het
        "activity_started:<naam>"-voorvoegsel -- zelfde patroon als
        pattern_matcher.py's is_topic_event/is_activity_event-check,
        hier toegepast om de ACTIEVE activiteit (niet de statistiek
        erover) bij te houden.

        Sinds 22 juli 2026: twee soorten bronnen komen hier binnen.
        - "activity_started:<naam>" (expliciet, van intent_router.py's
          "ik ga <activiteit>") -- ALTIJD meteen vertrouwd, Kevin zei
          het letterlijk.
        - "activity_started:<label>_gedetecteerd" (afgeleid, van
          activity_detector.py -- Layer 5 Fase 2, bv. VS Code komt op
          de voorgrond) -- enkel vertrouwd als focus_detector.py
          (Layer 5 Fase 3) bevestigt dat Kevin ook ECHT actief is
          (focus_level == "actief"). Zonder die check zou "VS Code
          staat open" al genoeg zijn, ook al is Kevin allang weg van
          zijn bureau -- exact het probleem dat focus_detector.py's
          eigen docstring beschrijft.
        """
        # Herkenningsreactie (7 oktober 2026): onthoud wanneer Kevin
        # het laatst iets tegen Nova zei (zie _mag_herkenning_geven()).
        if event_type == "raw_user_message":
            self._laatste_bericht_kevin = time.time()
            return

        # Herkenningsreactie (7 oktober 2026): onthoud wanneer Kevin
        # het laatst iets tegen Nova zei (zie _mag_herkenning_geven()).
        if event_type == "raw_user_message":
            self._laatste_bericht_kevin = time.time()
            return

        if not event_type or not event_type.startswith("activity_started:"):
            return

        naam = data.get("naam") or event_type.split(":", 1)[1]

        if naam.endswith("_gedetecteerd"):
            if naam == "afwezig_gedetecteerd":
                # Afwezigheid (3 oktober 2026): het vergrendelscherm is
                # geen activiteit die Kevin DOET, maar het einde van
                # zijn activiteit. Niet als nieuwe actieve activiteit
                # bijhouden -- anders zou Nova na 15 minuten vergrendeld
                # vragen of ze mag storen tijdens "afwezig".
                # afwezigheid.py handelt dit event zelf af.
                return

            if naam == "unknown_gedetecteerd":
                # "unknown" betekent letterlijk "geen match gevonden
                # in ACTIVITEIT_MAPPING" -- dit zegt NIETS zinvols over
                # een nieuwe activiteit, en mag daarom nooit een al
                # actieve, betekenisvolle activiteit (bv.
                # "werken_aan_nova_gedetecteerd") overschrijven. Zonder
                # deze check zou een kort uitstapje naar een niet-
                # gemapt venster (bv. de browser, om hier met Claude te
                # overleggen) de "werken aan Nova"-sessie ten onrechte
                # laten "resetten" zodra Kevin terugkeert naar VS Code
                # -- ontdekt door Kevin, 22 juli 2026.
                return

            if not self._is_kevin_actief():
                # Venster staat wel open, maar Kevin lijkt er niet
                # actief mee bezig (of focus_detector.py kon het niet
                # bepalen) -- (nog) niet als "activiteit gestart"
                # beschouwen.
                return

        # "werken_aan_nova_gedetecteerd" is SPECIFIEKER dan het
        # gelijktijdig gepubliceerde "coding_gedetecteerd" (zie
        # activity_detector.py: allebei worden gepubliceerd zodra
        # Kevin in VS Code op het Nova_AI-project zit). We laten het
        # specifiekere signaal "winnen" als actieve activiteit, i.p.v.
        # dat het generieke "coding_gedetecteerd" alsnog overschrijft
        # bij de eerstvolgende detectie-cyclus.
        if (
            naam == "coding_gedetecteerd"
            and self.actieve_activiteit == "werken_aan_nova_gedetecteerd"
        ):
            return

        # Eenmalige, sociale herkenningsreactie -- enkel bij de EERSTE
        # keer dat "werken_aan_nova_gedetecteerd" verschijnt in deze
        # sessie (niet elke minuut opnieuw zolang Kevin er gewoon in
        # blijft werken). Losstaand van _reageer_op_profiel_match()
        # hieronder, en losstaand van het latere interruption-circuit
        # (check_activity_interruption(), pas na de tijdsdrempel) --
        # dit is puur een direct, herkennend moment.
        #
        # Sinds 7 oktober 2026 ECHT eenmalig: max 1x per dag (bewaard
        # over herstarts heen) en nooit vlak na een bericht van Kevin.
        if (
            naam == "werken_aan_nova_gedetecteerd"
            and self.actieve_activiteit != naam
            and self._mag_herkenning_geven()
        ):
            tekst = self._formuleer_werken_aan_nova_reactie()
            self._herkenning_laatste_dag = date.today().isoformat()
            self._sla_herkenning_state_op()
            self.event_bus.publish("chat_response", {"text": tekst})

        # Nieuwe activiteit gestart (of dezelfde opnieuw benoemd) --
        # start_tijd + "al gevraagd"-vlag altijd resetten, ook als het
        # dezelfde naam is als daarvoor (Kevin is opnieuw begonnen).
        self.actieve_activiteit = naam
        self.activiteit_start_tijd = time.time()
        self._al_gevraagd_voor_activiteit = None
        self._al_gereageerd_op_profiel_voor = None

        self._reageer_op_profiel_match(naam)

    def _is_kevin_actief(self):
        """
        Vraagt aan focus_detector.py (Layer 5 Fase 3) of Kevin op dit
        moment systeemwijd actief lijkt (recente muis/toetsenbord-
        input). Geeft True terug bij twijfel/ontbrekende module --
        liever een keer onterecht "actief" aannemen dan een module die
        nog niet geladen is de hele detectie laten blokkeren.
        """
        detector = self.event_bus.modules.get("focus_detector")
        if detector is None:
            return True

        try:
            info = detector.get_focus_info()
            return info.get("focus_level") == "actief"
        except Exception:
            return True

    # Minimale woordlengte voor substring-matching (zie
    # _reageer_op_profiel_match hieronder) -- voorkomt dat korte
    # profielwoorden ("as", "op") toevallig overal in matchen.
    _MIN_LENGTE_SUBSTRING_MATCH = 4

    def _reageer_op_profiel_match(self, activiteit_naam):
        """
        User Preferences-koppeling (Fase 4): als de zonet gestarte
        activiteit overeenkomt met een woord uit kevin_profile.json,
        stuurt Nova een korte, gevarieerde bevestiging -- zowel bij een
        POSITIEVE match ("veel plezier, ik weet dat je hiervan houdt")
        als een NEGATIEVE match ("ik dacht dat je hier niet van hield?").

        Matching is een SUBSTRING-check, niet enkel exacte gelijkheid:
        detect_activity() geeft vaak een hele frase door ("een potje
        schaken", "koffie drinken"), geen los woord, dus een profielwoord
        als "schaken" moet ook matchen als het ERGENS in die frase
        voorkomt. Bewust beperkt tot woorden van minstens
        _MIN_LENGTE_SUBSTRING_MATCH letters, om te vermijden dat een kort
        profielwoord toevallig overal in matcht.

        Dit is bewust een vaste, voorspelbare koppeling (activity-event
        x profiel-lookup), GEEN vrije tekstinterpretatie -- enkel dit
        ene, voorspelbare moment (activiteit-start) triggert een reactie.

        Publiceert 'layer4_response' (niet rechtstreeks 'chat_response'),
        zodat dit nog door de tone-pipeline gaat, net als de rest van
        Layer 4.
        """
        if not self.kevin_profile:
            return

        if self._al_gereageerd_op_profiel_voor == activiteit_naam:
            return

        gevonden_woord, info = self._zoek_profiel_match(activiteit_naam)
        if gevonden_woord is None:
            return

        self._al_gereageerd_op_profiel_voor = activiteit_naam

        tekst = self._formuleer_profiel_reactie(gevonden_woord, info["sentiment"])
        self.event_bus.publish("layer4_response", {"text": tekst})
        print(
            f"[SESSION_WATCHER] Profiel-match voor activiteit '{activiteit_naam}' "
            f"(profielwoord: '{gevonden_woord}', sentiment: {info['sentiment']})."
        )

    def _zoek_profiel_match(self, activiteit_naam):
        """
        Zoekt of een woord uit het profiel voorkomt in de activiteit-
        naam (substring-check in beide richtingen: activiteit bevat
        profielwoord, OF profielwoord bevat activiteit -- vangt zowel
        "een potje schaken" (bevat "schaken") als een kortere activiteit-
        naam op).

        Geeft terug: (profielwoord, info) van de EERSTE match, of
        (None, None) als niets matcht. Bij meerdere mogelijke matches
        wordt bewust niet verder gesorteerd/gekozen -- dit is een
        zeldzame situatie en de eerste match is prima voor deze
        eenvoudige koppeling.
        """
        alles = self.kevin_profile.get_all_preferences()
        alle_woorden = list(alles["voorkeuren"].keys()) + list(alles["afkeuren"].keys())

        activiteit_lower = activiteit_naam.lower()

        for woord in alle_woorden:
            if len(woord) < self._MIN_LENGTE_SUBSTRING_MATCH:
                continue
            if woord in activiteit_lower or activiteit_lower in woord:
                info = self.kevin_profile.get_preference(woord)
                if info is not None:
                    return woord, info

        return None, None

    def _formuleer_profiel_reactie(self, activiteit, sentiment):
        """
        Bouwt een gevarieerde reactiezin op basis van sentiment, met
        random.choice() op vaste sjabloon-onderdelen -- zelfde principe
        als _formuleer_pauze_melding() verderop in dit bestand.
        """
        sjabloon = self._sjablonen_profiel_match[sentiment]

        if sentiment == "positief":
            opening = random.choice(sjabloon["openingen"]).format(
                activiteit=activiteit,
                activiteit_hoofdletter=activiteit.capitalize()
            )
            afsluiting = random.choice(sjabloon["afsluitingen"])
            return f"{opening} {afsluiting}"

        opening = random.choice(sjabloon["openingen"])
        afsluiting = random.choice(sjabloon["afsluitingen"])
        return f"{opening} over '{activiteit}' -- {afsluiting}"

    def _is_kevin_afwezig(self):
        """
        Afwezigheid (3 oktober 2026): vraagt afwezigheid.py of Kevin
        weg is van zijn laptop. Ontbreekt die module, dan "niet
        afwezig" (oud gedrag blijft dan gewoon werken).
        """
        modules = getattr(self.event_bus, "modules", None) or {}
        afwezigheid = modules.get("afwezigheid")
        if afwezigheid is None:
            return False
        try:
            return bool(afwezigheid.is_afwezig())
        except Exception:
            return False

    def _on_terug_van_afwezigheid(self, data, event_type=None):
        """
        Kevin is terug na een vergrendelde laptop. Was hij lang genoeg
        weg (PAUZE_RESET_NA_AFWEZIG_MINUTEN), dan had hij een echte
        pauze: de pauze-teller en de "mag ik storen?"-teller van de
        lopende activiteit beginnen opnieuw te tellen.

        Zelfde reset als stap 2 in check_pauze() (10 min geen input),
        maar meteen bij terugkomst en al na 5 minuten.
        """
        duur = (data or {}).get("duur_minuten") or 0
        if duur < self.PAUZE_RESET_NA_AFWEZIG_MINUTEN:
            return

        self._sessie_start = None
        self._laatst_actief = None
        self.laatste_melding_time = None
        if self.activiteit_start_tijd is not None:
            self.activiteit_start_tijd = time.time()

        print(
            f"[SESSION_WATCHER] Pauze-teller gereset na {duur:.0f} min "
            "afwezigheid (laptop was vergrendeld)."
        )

    def check_activity_interruption(self):
        """
        Wordt periodiek aangeroepen door de achtergrondthread in
        main.py (elke 60 seconden, zelfde ritme als check_pauze()).

        Kijkt of er een actieve activiteit loopt die al lang genoeg
        bezig is (INTERRUPTION_VRAAG_DREMPEL_MINUTEN). Zo ja, vraagt
        dit aan response_engine.beslis_interruption_gedrag() WAT Nova
        moet doen -- vragen, gewoon doorpraten, of stil blijven -- op
        basis van de confidence-score die interruption_tracker.py
        heeft opgebouwd voor deze activiteit. session_watcher.py voert
        enkel de teruggegeven actie uit, het beslist zelf niets meer
        over WANNEER precies (dat blijft hier, via de tijdsdrempel) of
        WAT er gezegd wordt (dat komt nu uit Layer 4).
        """
        if self.actieve_activiteit is None or self.activiteit_start_tijd is None:
            return

        # Afwezigheid (3 oktober 2026): laptop vergrendeld -> niets
        # vragen. De "al gevraagd"-vlag wordt bewust NIET gezet, zodat
        # de vraag na terugkomst gewoon nog kan komen. Zonder deze
        # check zou de vraag tegen een lege stoel gesteld worden en
        # zou de pending_question (120 s) al verlopen zijn tegen dat
        # Kevin terug is.
        if self._is_kevin_afwezig():
            return

        if self._al_gevraagd_voor_activiteit == self.actieve_activiteit:
            # Al gevraagd/gehandeld voor deze activiteit-instantie --
            # niet opnieuw, ook al loopt ze nog steeds door.
            return

        verstreken_minuten = (time.time() - self.activiteit_start_tijd) / 60
        if verstreken_minuten < self.INTERRUPTION_VRAAG_DREMPEL_MINUTEN:
            return

        resp_engine = self.event_bus.modules.get("response_engine")
        if resp_engine is None:
            return

        # Fase 6: zelfde tijd_sinds_start-berekening als _on_pending_
        # answered() hieronder al doet voor record_feedback() -- nu
        # ook meegeven bij het BESLISSEN, niet enkel bij het
        # achteraf REGISTREREN van feedback.
        tijd_sinds_start = None
        if self.activiteit_start_tijd is not None:
            tijd_sinds_start = round((time.time() - self.activiteit_start_tijd) / 60, 1)

        try:
            beslissing = resp_engine.beslis_interruption_gedrag(
                self.actieve_activiteit, tijd_sinds_start=tijd_sinds_start
            )
        except Exception as e:
            print(f"[SESSION_WATCHER] Fout bij beslis_interruption_gedrag(): {e}")
            return

        actie = beslissing.get("actie")
        tekst = beslissing.get("tekst")
        confidence = beslissing.get("confidence")

        if actie == "blijf_stil":
            # Nova zegt hier bewust NIETS -- wel de "al gevraagd/
            # gehandeld"-vlag zetten, anders zou dit elke minuut
            # opnieuw gecheckt worden zolang de activiteit doorloopt.
            self._al_gevraagd_voor_activiteit = self.actieve_activiteit
            print(
                f"[SESSION_WATCHER] Blijft stil voor '{self.actieve_activiteit}' "
                f"(confidence {confidence} <= laag, geen vraag/melding)."
            )
            return

        if actie == "ga_gewoon_door":
            # Hoge confidence: geen pending_question nodig, Nova praat
            # gewoon meteen -- geen ja/nee-antwoord te verwachten hier.
            self._al_gevraagd_voor_activiteit = self.actieve_activiteit
            self.event_bus.publish("chat_response", {"text": tekst})
            print(
                f"[SESSION_WATCHER] Gaat gewoon door voor '{self.actieve_activiteit}' "
                f"(confidence {confidence} >= hoog)."
            )
            return

        # actie == "vraag_eerst" (voorzichtig standaardgedrag)
        pending = self.event_bus.modules.get("pending_question")
        if pending is None:
            return

        # Als er toevallig al een ANDERE pending question open staat
        # (bv. een semantic-disambiguatievraag), wachten we liever --
        # geen twee vragen door elkaar.
        if pending.is_open():
            return

        pending.set("mag_ik_storen", verval_seconden=120)
        self._al_gevraagd_voor_activiteit = self.actieve_activiteit

        self.event_bus.publish("chat_response", {"text": tekst})
        print(
            f"[SESSION_WATCHER] '{tekst}' gevraagd voor activiteit "
            f"'{self.actieve_activiteit}' (na {int(verstreken_minuten)} min, "
            f"confidence: {confidence})."
        )

    def _on_pending_answered(self, data, event_type=None):
        """
        Luistert naar pending_question:answered (gepubliceerd door
        intent_router.py's _verwerk_pending_antwoord()). Filtert zelf
        op vraag_type == "mag_ik_storen" -- andere vraag_types (die in
        de toekomst kunnen bestaan) worden hier genegeerd, een andere
        module luistert daar dan op.
        """
        if data.get("vraag_type") != "mag_ik_storen":
            return

        signaal = data.get("signaal")
        toegestaan = (signaal == "bevestiging")

        tijd_sinds_start = None
        if self.activiteit_start_tijd is not None:
            tijd_sinds_start = round((time.time() - self.activiteit_start_tijd) / 60, 1)

        tracker = self.event_bus.modules.get("interruption_tracker")
        if tracker is not None and self.actieve_activiteit is not None:
            tracker.record_feedback(
                self.actieve_activiteit,
                toegestaan,
                tijd_sinds_start=tijd_sinds_start
            )
            print(
                f"[SESSION_WATCHER] interruption_feedback geregistreerd: "
                f"activiteit='{self.actieve_activiteit}', toegestaan={toegestaan}"
            )

    def _formuleer_pauze_melding(self, minuten):
        """
        Bouwt een sjabloonzin voor de pauze-melding.

        Puur string-formatting op vaste tekstlijsten -- geen generatie,
        zelfde principe als emergence_engine.py's _formuleer_*()-methodes.
        """
        opening = random.choice(self._sjablonen_pauze["opening"])
        midden = random.choice(self._sjablonen_pauze["midden"]).format(minuten=minuten)
        afsluiting = random.choice(self._sjablonen_pauze["afsluiting"])

        return f"{opening} {midden} {afsluiting}"

    def _haal_focus_niveau(self):
        """
        Vraagt het huidige focus-niveau op ("actief", "mogelijk_afwezig",
        "waarschijnlijk_weg" of "onbekend"). Sinds de Windows-companion-
        client komt dit van de laptop (RemoteFocusDetector); staat de
        laptop uit, dan is het "onbekend".

        BEWUST GEEN fail-open zoals _is_kevin_actief() hierboven: voor
        de pauzeteller betekent "geen info" gewoon "we weten niet dat
        Kevin werkt", dus geen sessie laten oplopen.
        """
        detector = self.event_bus.modules.get("focus_detector") if hasattr(self.event_bus, "modules") else None
        if detector is None:
            return "onbekend"

        try:
            info = detector.get_focus_info()
            return info.get("focus_level", "onbekend")
        except Exception:
            return "onbekend"

    def check_pauze(self):
        """
        Wordt periodiek (elke 60 seconden) aangeroepen door de
        achtergrondthread in main.py.

        HERONTWERP (30 sept 2026): meet hoe lang KEVIN al onafgebroken
        actief is op zijn laptop -- niet meer hoe lang Nova al draait.
        De oude versie telde vanaf Nova's opstart (self.start_time), wat
        klopte zolang Nova enkel tijdens een sessie op de laptop draaide,
        maar sinds de 24/7-verhuizing naar battleserver elke 30 minuten
        een melding gaf, dag en nacht, ook zonder dat Kevin er was.

        Werking, puur symbolisch (tijdstippen vergelijken):
        1. Focus "actief" (recente muis/toetsenbord-input op de laptop)?
           -> start een sessie als er nog geen liep, en onthoud "nu
              was Kevin actief".
        2. Al PAUZE_RESET_SECONDEN (10 min) geen actieve focus meer
           gezien (Kevin is weg, of de laptop staat uit)?
           -> dat was een echte pauze: sessie en melding-tijdstip
              wissen, de teller begint later opnieuw.
        3. Loopt er een sessie, is Kevin NU actief, en zijn er sinds het
           sessiebegin (of sinds de vorige melding) PAUZE_DREMPEL_SECONDEN
           verstreken? -> Layer 5 vragen of het een goed moment is
           (can_interrupt(), dat sinds 30 sept 2026 ook checkt of Kevin
           het bericht kan ZIEN), en zo ja: melden.
        """
        nu = time.time()
        focus_niveau = self._haal_focus_niveau()

        # --- Stap 1: actief? Dan loopt (of start) de sessie ---
        if focus_niveau == "actief":
            if self._sessie_start is None:
                self._sessie_start = nu
            self._laatst_actief = nu

        # --- Stap 2: lang genoeg inactief? Dan was dat een pauze ---
        elif (
            self._laatst_actief is not None
            and nu - self._laatst_actief >= self.PAUZE_RESET_SECONDEN
        ):
            self._sessie_start = None
            self._laatst_actief = None
            self.laatste_melding_time = None

        # --- Stap 3: melden? ---
        if self._sessie_start is None:
            return

        # Afwezigheid (3 oktober 2026): laptop vergrendeld -> geen
        # pauze-melding (Kevin heeft op dit moment letterlijk pauze).
        # Nodig omdat het wachtwoord intypen op het vergrendelscherm OOK
        # input is (focus "actief"), en omdat can_interrupt() hieronder
        # overgeslagen wordt als context_manager ontbreekt.
        if self._is_kevin_afwezig():
            return

        if focus_niveau != "actief":
            # Kevin is net even niet actief (bv. 3 min iets aan het
            # lezen) -- geen melding tegen een leeg scherm, maar de
            # sessie blijft wel doorlopen tot stap 2 ze afsluit.
            return

        # Referentiepunt: sinds de laatste melding BINNEN deze sessie,
        # of sinds het begin van de sessie.
        referentie = self._sessie_start
        if self.laatste_melding_time is not None and self.laatste_melding_time > referentie:
            referentie = self.laatste_melding_time

        if nu - referentie < self.PAUZE_DREMPEL_SECONDEN:
            return

        # Layer 5 vragen: is dit een goed moment om te onderbreken?
        # Ontbreekt context_manager (laadvolgorde-probleem), dan gaan we
        # voorzichtig gewoon door -- zelfde keuze als vroeger.
        if self.context_manager is not None:
            try:
                mag_onderbreken = self.context_manager.can_interrupt()
            except Exception:
                mag_onderbreken = True
        else:
            mag_onderbreken = True

        if not mag_onderbreken:
            # Nog niet melden -- probeer het over 60 seconden opnieuw.
            # laatste_melding_time NIET bijwerken, anders "verliest" de
            # sessie deze wachttijd stilletjes. Enkel een console-print
            # voor debug, GEEN chat_response.
            print("[SESSION_WATCHER] Pauze-melding uitgesteld door Layer 5 (context_manager.can_interrupt() == False)")
            return

        self.laatste_melding_time = nu
        # Het ECHTE aantal minuten sinds het begin van de sessie (bij een
        # tweede melding dus bv. 60 i.p.v. opnieuw 30).
        minuten = int((nu - self._sessie_start) / 60)

        self.event_bus.publish("chat_response", {
            "text": self._formuleer_pauze_melding(minuten)
        })


def init_module(event_bus, sem=None):
    """
    Standaard module_loader-conventie: init_module(event_bus, sem).
    'sem' wordt hier niet gebruikt maar moet aanwezig zijn zodat
    module_loader.py deze module net als de andere kan initialiseren.

    LET OP: session_watcher wordt geladen via de DYNAMISCHE modules-
    scan in module_loader.py (stap 3) — dat gebeurt VOOR context_manager
    EN VOOR kevin_profile geladen wordt (kevin_profile zit in
    modules/preferences/, dus wordt door dezelfde dynamische scan
    gevonden, maar de volgorde binnen die scan hangt af van
    pkgutil.walk_packages() en is niet gegarandeerd vóór session_watcher
    te lopen). We geven hier dus (nog) geen context_manager/kevin_profile
    mee — die worden vlak na het laden apart ingeprikt door
    module_loader.py. Zie het zoek/vervang-blok voor module_loader.py
    hieronder.
    """
    instance = SessionWatcher(event_bus)
    event_bus.publish("module_loaded", {"name": "session_watcher"})
    return instance