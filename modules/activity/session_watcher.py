# modules/activity/session_watcher.py
import time


class SessionWatcher:
    """
    Houdt bij hoe lang Kevin al aan het chatten is met Nova, en stuurt
    na een ingestelde tijd één keer een korte pauze-melding.

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

    # Na hoeveel MINUTEN sinds het starten van een activiteit vraagt
    # Nova voor het eerst "mag ik storen?" -- vaste waarde, besproken
    # met Kevin (22 juli 2026): uiteindelijk 15 minuten.
    #
    # TIJDELIJK VERLAAGD NAAR 1 OM TE TESTEN (22 juli 2026) -- zet dit
    # terug naar 15 zodra het testen achter de rug is. Zelfde aanpak
    # als PAUZE_DREMPEL_SECONDEN hierboven, dat ook al een "zet dit
    # tijdelijk lager om te testen"-opmerking had.
    INTERRUPTION_VRAAG_DREMPEL_MINUTEN = 15

    def __init__(self, event_bus, context_manager=None):
        self.event_bus = event_bus
        self.start_time = time.time()
        self.laatste_melding_time = None
        # Layer 5 — bepaalt of dit een goed moment is om te onderbreken.
        # Kan None zijn (bv. als context_manager nog niet geladen is),
        # daarom altijd voorzichtig checken met "if self.context_manager".
        self.context_manager = context_manager

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

        event_bus.subscribe("*", self._on_any_event)

        # Antwoord op de "mag ik storen?"-vraag opvangen. Dit event
        # komt van intent_router.py's _verwerk_pending_antwoord(), dus
        # GEEN wildcard nodig -- een exacte event-naam volstaat hier.
        event_bus.subscribe("pending_question:answered", self._on_pending_answered)

    def _on_any_event(self, data, event_type=None):
        """
        Vangt ALLE events op (wildcard), en filtert zelf op het
        "activity_started:<naam>"-voorvoegsel -- zelfde patroon als
        pattern_matcher.py's is_topic_event/is_activity_event-check,
        hier toegepast om de ACTIEVE activiteit (niet de statistiek
        erover) bij te houden.
        """
        if not event_type or not event_type.startswith("activity_started:"):
            return

        naam = data.get("naam") or event_type.split(":", 1)[1]

        # Nieuwe activiteit gestart (of dezelfde opnieuw benoemd) --
        # start_tijd + "al gevraagd"-vlag altijd resetten, ook als het
        # dezelfde naam is als daarvoor (Kevin is opnieuw begonnen).
        self.actieve_activiteit = naam
        self.activiteit_start_tijd = time.time()
        self._al_gevraagd_voor_activiteit = None

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

        try:
            beslissing = resp_engine.beslis_interruption_gedrag(self.actieve_activiteit)
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

    def check_pauze(self):
        """
        Wordt periodiek aangeroepen door de achtergrondthread in main.py.
        Kijkt of de sessie al lang genoeg loopt sinds de start (of sinds
        de vorige melding) om een pauze voor te stellen.
        """
        nu = time.time()

        # Referentiepunt: sinds de laatste melding, of sinds de start
        # als er nog nooit gemeld is.
        referentie = self.laatste_melding_time or self.start_time

        verstreken = nu - referentie

        if verstreken >= self.PAUZE_DREMPEL_SECONDEN:
            # Layer 5 vragen: is dit een goed moment om te onderbreken?
            # Als context_manager niet beschikbaar is (bv. door een
            # laadvolgorde-probleem), gaan we voorzichtig gewoon door —
            # Layer 5 ontbreken mag nooit de pauze-melding blokkeren,
            # want dat zou de bestaande functionaliteit stiller maken
            # dan voorheen. We proberen het WEL opnieuw bij de
            # eerstvolgende check (verstreken blijft oplopen), in
            # plaats van laatste_melding_time hier al bij te werken.
            if self.context_manager is not None:
                try:
                    mag_onderbreken = self.context_manager.can_interrupt()
                except Exception:
                    mag_onderbreken = True
            else:
                mag_onderbreken = True

            if not mag_onderbreken:
                # Nog niet melden — probeer het over 60 seconden
                # opnieuw (achtergrond_loop() roept dit sowieso elke
                # minuut aan). laatste_melding_time NIET bijwerken,
                # anders "verliest" de sessie deze wachttijd stilletjes.
                #
                # Enkel een console-print voor Kevin (debug), GEEN
                # chat_response — Nova "zegt" dit niet tegen zichzelf,
                # dit is puur zichtbaar voor wie main.py's terminal leest.
                print("[SESSION_WATCHER] Pauze-melding uitgesteld door Layer 5 (context_manager.can_interrupt() == False)")
                return

            self.laatste_melding_time = nu
            minuten = int(self.PAUZE_DREMPEL_SECONDEN / 60)

            self.event_bus.publish("chat_response", {
                "text": f"We zijn nu al {minuten} minuten bezig — misschien even pauzeren?"
            })


def init_module(event_bus, sem=None):
    """
    Standaard module_loader-conventie: init_module(event_bus, sem).
    'sem' wordt hier niet gebruikt maar moet aanwezig zijn zodat
    module_loader.py deze module net als de andere kan initialiseren.

    LET OP: session_watcher wordt geladen via de DYNAMISCHE modules-
    scan in module_loader.py (stap 3) — dat gebeurt VOOR context_manager
    geladen wordt (stap 3C, na response_engine). Op dit moment bestaat
    loaded_modules["context_manager"] dus nog NIET. We geven hier dus
    (nog) geen context_manager mee — die wordt vlak na het laden
    apart ingeprikt door module_loader.py. Zie het zoek/vervang-blok
    voor module_loader.py hieronder.
    """
    instance = SessionWatcher(event_bus)
    event_bus.publish("module_loaded", {"name": "session_watcher"})
    return instance