# modules/learning/pattern_matcher.py

"""
Layer 2: Pattern Matcher

Detecteert gedragspatronen in Nova's interacties: op welk uur en welke
dag komt een bepaald event (bv. "coffee:mentioned") meestal voor, en
hoe zeker is dat patroon?

Dit is 100% symbolisch: enkel tellen en rekenen op timestamps.
Geen ML, geen taalverwerking.

Fase 1: Event grouping (per uur, per dag, per event_type)
Fase 2: Pattern detection (frequentie + confidence-score)
Fase 3: Anomaly detection (timing-afwijkingen + gemiste events)
Fase 4 (later): Query & predictie
Fase 5 (later): Volledige integratie met Layer 5/7
"""

from collections import defaultdict
from datetime import datetime
import json
import threading
from pathlib import Path


# Nederlandse dagnamen, index volgens datetime.weekday() (0 = maandag)
# LET OP: we gebruiken bewust NIET dt.strftime("%A"), want dat geeft op
# Windows Engelse dagnamen terug (bekende bug, ook al opgelost in
# weather.py op dezelfde manier).
DAGEN_NL = [
    "maandag", "dinsdag", "woensdag", "donderdag",
    "vrijdag", "zaterdag", "zondag"
]


class PatternMatcher:
    """
    Layer 2: Pattern Matcher

    Houdt van élk event_type bij op welk uur en welke dag het meestal
    voorkomt, en berekent hoe betrouwbaar (confidence) dat patroon is.
    Detecteert daarnaast anomalieën: momenten die sterk afwijken van
    het geleerde patroon, en momenten waarop een verwacht event uitbleef.
    """

    # Welke ORIGINELE event_types willen we analyseren op gedragspatronen?
    # Dit voorkomt dat we interne pipeline-events (pipeline_response,
    # expression_inject, module_loaded, ...) meetellen als "gedrag" —
    # die zijn geen directe actie van Kevin, maar interne verwerkingsstappen.
    RELEVANTE_EVENT_TYPES = {
        "chat_message",
        "chat_response",
    }

    # Vanaf hoeveel observaties vinden we een patroon betrouwbaar genoeg
    # om anomalieën op te baseren? Met te weinig data is bijna alles
    # "normaal", puur omdat er nog geen historiek is.
    # TIJDELIJK verlaagd naar 3 om makkelijk te kunnen testen — later
    # (als alles werkt) zetten we dit terug naar een realistischere
    # waarde zoals 10 of hoger.
    MIN_OBSERVATIES_VOOR_ANOMALIE = 3

    # Onder welke confidence-drempel beschouwen we een patroon als
    # "sterk genoeg" om afwijkingen tegen te toetsen?
    MIN_CONFIDENCE_VOOR_ANOMALIE = 0.6

    def __init__(self, event_bus=None, semantic_module=None):
        self.event_bus = event_bus
        # Nog niet gebruikt in Fase 1-3, maar we houden de parameter
        # aan zodat module_loader.py (die altijd init_module(event_bus, sem)
        # aanroept) niet crasht. Zelfde conventie als word_associations_learner.py.
        self.semantic = semantic_module

        # patterns structuur, per event_type:
        # {
        #   "hours": {0: aantal, 1: aantal, ...},   # int -> int
        #   "days": {"maandag": aantal, ...},        # str -> int
        #   "total": aantal
        # }
        self.patterns = {}

        # Lijst met gedetecteerde anomalieën (Fase 3), meest recente eerst.
        # Elke anomalie is een dict met: event_type, type ("ongewone_timing"
        # of "gemist_event"), timestamp, en een korte omschrijving.
        self.anomalies = []
        self.max_anomalies = 200  # voorkomt onbeperkte groei in RAM

        # Houdt bij wanneer we voor het laatst een "missing event"-check
        # deden per event_type, zodat we niet dubbel dezelfde gemiste
        # observatie melden.
        self._laatst_gecheckte_uur_per_type = {}

        # Portable pad, zelfde principe als memory.py: nooit hardcoded
        # Windows-pad, altijd relatief t.o.v. dit bestand.
        self.save_path = Path(__file__).resolve().parent.parent.parent / "data" / "patterns_layer2.json"

        # FASE 5: bestaande patronen herladen bij opstarten, zodat een
        # herstart van Nova niet alles terug op 0 zet. Dit MOET gebeuren
        # vóór we naar de EventBus subscriben, anders zou een binnenkomend
        # event tijdens het laden een gedeeltelijke/inconsistente staat
        # kunnen zien.
        self.load_from_disk()

        # Achtergrond-timer voor "missing events"-detectie (Fase 3, Deel B)
        self.missing_event_check_interval_seconds = 3600  # elk uur
        self.missing_event_timer = None

        if self.event_bus is not None:
            self.event_bus.subscribe("memory:interaction_added", self.detect_from)

        # Start de achtergrondtimer meteen bij het opstarten van Nova.
        self.start_missing_event_checks()

    # ------------------------------------------------------------------
    # FASE 1: Event grouping
    # ------------------------------------------------------------------

    def detect_from(self, interaction, event_type=None):
        """
        Wordt aangeroepen bij élke 'memory:interaction_added'-event.

        LET OP: memory.py publiceert élk event opnieuw, en geeft de
        ORIGINELE event_type door in interaction["event_type"] (niet als
        losse parameter — dat "event_type"-argument hier is altijd
        letterlijk de string 'memory:interaction_added', want dat is wat
        memory.py zelf publiceert).
        """

        if not isinstance(interaction, dict):
            return

        # Het ECHTE, originele event_type zit genest in interaction,
        # niet in het functie-argument 'event_type'.
        origineel_type = interaction.get("event_type")

        if origineel_type not in self.RELEVANTE_EVENT_TYPES:
            return

        timestamp = interaction.get("timestamp")
        if timestamp is None:
            return

        # We gebruiken origineel_type als sleutel, niet het functie-argument
        event_type = origineel_type

        dt = datetime.fromtimestamp(timestamp)
        hour = dt.hour
        day_name = DAGEN_NL[dt.weekday()]

        # Nieuw event_type? Structuur aanmaken.
        if event_type not in self.patterns:
            self.patterns[event_type] = {
                "hours": defaultdict(int),
                "days": defaultdict(int),
                "total": 0
            }

        # FASE 3, Deel A: check VOOR we deze observatie meetellen of het
        # huidige moment afwijkt van het al gekende patroon. Zo vergelijken
        # we "wat Nova al wist" met "wat er nu binnenkomt", in plaats van
        # de nieuwe observatie met zichzelf te vergelijken.
        self._check_ongewone_timing(event_type, hour, day_name, timestamp)

        self.patterns[event_type]["hours"][hour] += 1
        self.patterns[event_type]["days"][day_name] += 1
        self.patterns[event_type]["total"] += 1

        # Na elke nieuwe observatie meteen de statistieken herberekenen
        # (Fase 2).
        self._update_pattern_stats(event_type)

        # FASE 5: laat andere modules (bv. straks Layer 5, de Context
        # Manager) weten dat er een patroon-update is, zonder dat ze zelf
        # in pattern_matcher.py's interne structuur moeten graven.
        if self.event_bus is not None:
            self.event_bus.publish("pattern:detected", {
                "event_type": event_type,
                "pattern": self.patterns[event_type]
            })

        # Tijdelijk: elke 2 observaties opslaan, zodat je tijdens het
        # testen snel resultaat ziet. Later vervangen we dit
        # door iets efficiënter (tijdgebaseerd, zoals memory.py doet).
        if self.patterns[event_type]["total"] % 2 == 0:
            self.save_to_disk()

    # ------------------------------------------------------------------
    # FASE 2: Pattern detection (frequentie + confidence)
    # ------------------------------------------------------------------

    def _update_pattern_stats(self, event_type):
        """
        Berekent voor één event_type:
        - most_common_hour: het uur waarop dit event het vaakst voorkomt
        - confidence: hoe vaak het exact op dat uur is (0.0 - 1.0)
        - day_frequency: per dag, hoe vaak dit event relatief voorkomt
        """

        data = self.patterns[event_type]
        total = data["total"]

        if total == 0:
            return

        # Meest voorkomende uur
        hours = data["hours"]
        most_common_hour = max(hours, key=hours.get)
        occurrences_at_hour = hours[most_common_hour]

        # Confidence: hoe groot is het aandeel van dat ene uur t.o.v. alle
        # keren dat dit event ooit voorkwam?
        confidence = occurrences_at_hour / total

        self.patterns[event_type]["most_common_hour"] = most_common_hour
        self.patterns[event_type]["confidence"] = round(confidence, 3)

        # Dagfrequentie: voor elke dag, hoeveel aandeel heeft die dag in
        # het totaal aantal observaties?
        days = data["days"]
        total_days_observed = sum(days.values())

        day_frequency = {}
        for dag in DAGEN_NL:
            aantal_op_die_dag = days.get(dag, 0)
            if total_days_observed > 0:
                # Aandeel van deze dag t.o.v. alle observaties, genormaliseerd
                # zodat een dag die "elke keer" voorkomt naar 1.0 neigt.
                verwacht_per_dag = total_days_observed / 7
                freq = aantal_op_die_dag / verwacht_per_dag if verwacht_per_dag > 0 else 0
                day_frequency[dag] = round(min(1.0, freq), 3)
            else:
                day_frequency[dag] = 0.0

        self.patterns[event_type]["day_frequency"] = day_frequency

    # ------------------------------------------------------------------
    # FASE 3, Deel A: Ongewone timing detecteren
    # ------------------------------------------------------------------

    def _check_ongewone_timing(self, event_type, hour, day_name, timestamp):
        """
        Vergelijkt het HUIDIGE moment met het patroon dat Nova tot nu toe
        heeft opgebouwd voor dit event_type. Als het huidige uur sterk
        afwijkt van het meest voorkomende uur, EN het patroon al
        betrouwbaar genoeg is (genoeg observaties + hoge confidence),
        wordt dit als anomalie gelogd.

        Dit zegt NOOIT "waarom" iets afwijkt (bv. "Kevin is ziek") — dat
        weet Nova niet en verzinnen we niet. Enkel DAT het afwijkt.
        """

        bestaand_patroon = self.patterns.get(event_type)
        if not bestaand_patroon:
            return  # eerste keer dat we dit event_type zien, niks om mee te vergelijken

        total = bestaand_patroon.get("total", 0)
        confidence = bestaand_patroon.get("confidence")
        most_common_hour = bestaand_patroon.get("most_common_hour")

        if total < self.MIN_OBSERVATIES_VOOR_ANOMALIE:
            return  # nog te weinig data, alles is "normaal" bij gebrek aan historiek

        if confidence is None or confidence < self.MIN_CONFIDENCE_VOOR_ANOMALIE:
            return  # patroon zelf is niet sterk genoeg om afwijkingen op te baseren

        if most_common_hour is None:
            return

        # Hoeveel uur zit het huidige moment van het meest gebruikelijke uur?
        # We houden rekening met "rond middernacht" (bv. 23u vs 1u is maar
        # 2 uur verschil, niet 22u).
        verschil = min(
            abs(hour - most_common_hour),
            24 - abs(hour - most_common_hour)
        )

        # Drempel: meer dan 4 uur afwijking van het gebruikelijke moment
        # beschouwen we als "ongewoon". Dit is een eenvoudige, symbolische
        # vaste drempel — geen ML, geen leren van de drempel zelf.
        if verschil > 4:
            self._log_anomalie(
                event_type=event_type,
                anomalie_type="ongewone_timing",
                timestamp=timestamp,
                omschrijving=(
                    f"'{event_type}' kwam voor om {hour}u, terwijl dit "
                    f"normaal rond {most_common_hour}u gebeurt "
                    f"(confidence {confidence})."
                )
            )

    def _log_anomalie(self, event_type, anomalie_type, timestamp, omschrijving):
        """Voegt een anomalie toe aan de lijst, met een maximum-grootte."""
        anomalie = {
            "event_type": event_type,
            "type": anomalie_type,
            "timestamp": timestamp,
            "omschrijving": omschrijving
        }
        self.anomalies.insert(0, anomalie)  # meest recente eerst

        if len(self.anomalies) > self.max_anomalies:
            self.anomalies = self.anomalies[:self.max_anomalies]

        print(f"[PATTERN_MATCHER] Anomalie gedetecteerd: {omschrijving}")

    # ------------------------------------------------------------------
    # FASE 3, Deel B: Gemiste events detecteren (achtergrondtimer)
    # ------------------------------------------------------------------

    def _check_missing_events(self):
        """
        Wordt periodiek aangeroepen (elk uur, via de achtergrondtimer).
        Checkt voor elk gekend event_type: was dit uur normaal een
        "actief" uur volgens het patroon, en is er toch niks gebeurd?

        LET OP: dit is een eenvoudige, symbolische heuristiek. Ze werkt
        per KALENDERUUR (bv. 12:00-13:00), niet per exact tijdstip.
        """

        nu = datetime.now()
        huidig_uur = nu.hour
        huidige_dag = DAGEN_NL[nu.weekday()]

        for event_type, data in self.patterns.items():
            total = data.get("total", 0)
            confidence = data.get("confidence")
            most_common_hour = data.get("most_common_hour")
            day_frequency = data.get("day_frequency", {})

            if total < self.MIN_OBSERVATIES_VOOR_ANOMALIE:
                continue

            if confidence is None or confidence < self.MIN_CONFIDENCE_VOOR_ANOMALIE:
                continue

            if most_common_hour != huidig_uur:
                continue  # dit is sowieso geen "verwacht" uur voor dit event

            dag_freq = day_frequency.get(huidige_dag, 0)
            if dag_freq < 0.5:
                continue  # op deze dag komt het event normaal niet vaak voor

            # Was er in het HUIDIGE kalenderuur al een observatie?
            # We gebruiken hier een simpele vlag per (event_type, uur, dag)
            # combinatie, zodat we niet elk uur opnieuw dezelfde melding maken.
            check_key = (event_type, nu.date().isoformat(), huidig_uur)
            if self._laatst_gecheckte_uur_per_type.get(event_type) == check_key:
                continue  # dit uur al gecheckt

            self._laatst_gecheckte_uur_per_type[event_type] = check_key

            # Was dit uur, op deze datum, effectief al geteld?
            # We benaderen dit door te kijken of het TOTAAL voor dit uur
            # is toegenomen sinds de vorige check. Eenvoudige aanpak:
            # als er sinds het begin van dit kalenderuur geen nieuwe
            # observatie is bijgekomen, loggen we een gemist event.
            #
            # LET OP: dit is een benadering, geen exacte "was er nu een
            # observatie ja/nee"-check, omdat we niet per event een
            # volledige geschiedenis met exacte datums bijhouden (enkel
            # tellers per uur/dag, zoals gepland in Fase 1-2).
            aantal_op_dit_uur = data.get("hours", {}).get(huidig_uur, 0)
            verwacht_minimum = max(1, int(total * (dag_freq / 7)))

            if aantal_op_dit_uur < verwacht_minimum:
                self._log_anomalie(
                    event_type=event_type,
                    anomalie_type="gemist_event",
                    timestamp=nu.timestamp(),
                    omschrijving=(
                        f"'{event_type}' werd verwacht rond {huidig_uur}u "
                        f"op een {huidige_dag}, maar bleef dit uur uit."
                    )
                )

    def start_missing_event_checks(self):
        """
        Start de achtergrond-timer die elk uur checkt op gemiste events.
        Werkt op dezelfde manier als memory.py's start_maintenance():
        een herhalende threading.Timer die zichzelf telkens opnieuw plant.
        """
        def _tick():
            try:
                self._check_missing_events()
            except Exception as e:
                print(f"[PATTERN_MATCHER] Fout bij missing-event-check: {e}")
            self.start_missing_event_checks()  # volgende ronde inplannen

        self.missing_event_timer = threading.Timer(
            self.missing_event_check_interval_seconds, _tick
        )
        self.missing_event_timer.daemon = True  # stopt automatisch als Nova stopt
        self.missing_event_timer.start()

    def stop_missing_event_checks(self):
        """Zet de achtergrond-timer stil (bij netjes afsluiten)."""
        if self.missing_event_timer:
            self.missing_event_timer.cancel()
            self.missing_event_timer = None

    # ------------------------------------------------------------------
    # FASE 4: Query & predictie
    # ------------------------------------------------------------------

    def is_pattern_active(self, event_type):
        """
        Checkt of dit event_type NU, op dit exacte moment, "normaal
        actief" is — dus: komt dit event gewoonlijk voor op dit uur,
        op deze dag?

        Geeft False terug als:
        - het event_type nog niet gekend is
        - er nog te weinig observaties zijn om iets zinnigs te zeggen
        - het huidige uur niet overeenkomt met het gebruikelijke uur
        - deze dag normaal niet vaak voorkomt voor dit event
        """
        pattern = self.patterns.get(event_type)
        if not pattern:
            return False

        total = pattern.get("total", 0)
        if total < self.MIN_OBSERVATIES_VOOR_ANOMALIE:
            return False  # te weinig data om iets zinnigs te zeggen

        most_common_hour = pattern.get("most_common_hour")
        if most_common_hour is None:
            return False

        nu = datetime.now()
        huidig_uur = nu.hour
        huidige_dag = DAGEN_NL[nu.weekday()]

        dag_freq = pattern.get("day_frequency", {}).get(huidige_dag, 0)

        return (
            huidig_uur == most_common_hour and
            dag_freq > 0.5
        )

    def predict_next_occurrence(self, event_type):
        """
        Voorspelt WANNEER (welk eerstvolgend moment) dit event_type
        weer verwacht wordt, gebaseerd op het meest voorkomende uur.

        Dit is een EENVOUDIGE, symbolische voorspelling: gewoon het
        eerstvolgende tijdstip berekenen waarop most_common_hour weer
        voorkomt. Geen rekening met specifieke dagen (dat zou de
        voorspelling ingewikkelder maken dan nu nodig is) — enkel het uur.

        Geeft None terug als er nog te weinig data is om iets te
        voorspellen.
        """
        pattern = self.patterns.get(event_type)
        if not pattern:
            return None

        total = pattern.get("total", 0)
        if total < self.MIN_OBSERVATIES_VOOR_ANOMALIE:
            return None

        most_common_hour = pattern.get("most_common_hour")
        if most_common_hour is None:
            return None

        nu = datetime.now()

        # Bouw een datetime voor VANDAAG op het verwachte uur
        verwacht_moment = nu.replace(
            hour=most_common_hour, minute=0, second=0, microsecond=0
        )

        # Als dat moment vandaag al voorbij is, dan is het morgen
        if verwacht_moment <= nu:
            from datetime import timedelta
            verwacht_moment += timedelta(days=1)

        return verwacht_moment

    def get_pattern(self, event_type):
        """Geeft alle patroongegevens terug voor een bepaald event_type."""
        return self.patterns.get(event_type)

    def get_all_patterns(self):
        """Geeft alle gedetecteerde patronen terug (voor alle event_types)."""
        return self.patterns

    def get_anomalies(self, days=7):
        """
        Geeft de anomalieën terug van de laatste 'days' dagen,
        meest recente eerst.
        """
        cutoff = datetime.now().timestamp() - (days * 24 * 3600)
        return [a for a in self.anomalies if a["timestamp"] >= cutoff]

    def get_stats(self):
        """Kort overzicht: hoeveel event_types worden er bijgehouden en met hoeveel observaties totaal."""
        return {
            "aantal_event_types": len(self.patterns),
            "totaal_observaties": sum(p["total"] for p in self.patterns.values()),
            "aantal_anomalieen": len(self.anomalies)
        }

    # ------------------------------------------------------------------
    # FASE 5: Opslag + herladen bij opstarten
    # ------------------------------------------------------------------

    def load_from_disk(self):
        """
        Leest patterns_layer2.json in (indien aanwezig) en herstelt
        self.patterns en self.anomalies daaruit. Wordt aangeroepen bij
        het opstarten van PatternMatcher, zodat een herstart van Nova
        niet alles terug op 0 zet.

        Als het bestand nog niet bestaat (bv. allereerste keer dat Nova
        met Layer 2 opstart), gebeurt er gewoon niks — self.patterns en
        self.anomalies blijven dan leeg, zoals verwacht.
        """
        if not self.save_path.exists():
            return

        try:
            with open(self.save_path, "r", encoding="utf-8") as f:
                opgeslagen_data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[PATTERN_MATCHER] Kon patterns_layer2.json niet lezen, start leeg: {e}")
            return

        opgeslagen_patterns = opgeslagen_data.get("patterns", {})

        for event_type, data in opgeslagen_patterns.items():
            # "hours" en "days" moeten terug defaultdict(int) worden,
            # anders crasht _update_pattern_stats() straks bij het
            # optellen van nieuwe observaties. json.load() geeft altijd
            # gewone dicts terug, dus dit moeten we expliciet herstellen.
            #
            # LET OP: JSON-sleutels zijn altijd strings, dus de uren
            # ("hours") moeten we terug omzetten naar integers (12 i.p.v. "12").
            hours_ruw = data.get("hours", {})
            hours = defaultdict(int, {int(u): aantal for u, aantal in hours_ruw.items()})

            days_ruw = data.get("days", {})
            days = defaultdict(int, days_ruw)

            self.patterns[event_type] = {
                "hours": hours,
                "days": days,
                "total": data.get("total", 0),
                "most_common_hour": data.get("most_common_hour"),
                "confidence": data.get("confidence"),
                "day_frequency": data.get("day_frequency", {})
            }

        self.anomalies = opgeslagen_data.get("anomalies", [])

        print(
            f"[PATTERN_MATCHER] {len(self.patterns)} patroon(en) en "
            f"{len(self.anomalies)} anomalie(ën) hersteld uit "
            f"patterns_layer2.json."
        )


    def save_to_disk(self):
        """Slaat de huidige patronen én anomalieën op als JSON."""
        self.save_path.parent.mkdir(parents=True, exist_ok=True)

        # defaultdict kan niet direct naar JSON, dus zetten we alles om
        # naar gewone dicts voor het opslaan.
        serializable_patterns = {}
        for event_type, data in self.patterns.items():
            serializable_patterns[event_type] = {
                "hours": dict(data["hours"]),
                "days": dict(data["days"]),
                "total": data["total"],
                "most_common_hour": data.get("most_common_hour"),
                "confidence": data.get("confidence"),
                "day_frequency": data.get("day_frequency", {})
            }

        output = {
            "patterns": serializable_patterns,
            "anomalies": self.anomalies
        }

        with open(self.save_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)


def init_module(event_bus, semantic_module=None):
    """
    Wordt aangeroepen door module_loader.py bij het opstarten van Nova.

    Let op: module_loader.py roept dynamische modules altijd aan als
    init_module(event_bus, sem) — waarbij "sem" de semantic-module
    (Layer 3) is. Daarom accepteert deze functie een
    "semantic_module"-parameter, net zoals word_associations_learner.py
    dat ook al doet. We gebruiken semantic_module hier momenteel nog
    niet.

    LET OP: dit is Fase 1-3 van 5. Er wordt nog geen definitieve,
    efficiënte opslagstrategie gebruikt (dat komt in Fase 5). Herstart je
    Nova, dan is alles wat tot dan toe geleerd is, weer weg. Dat is
    verwacht gedrag voor deze fase.
    """
    instance = PatternMatcher(event_bus, semantic_module=semantic_module)
    if event_bus is not None:
        event_bus.publish("module_loaded", {"name": "pattern_matcher"})
    return instance
    """
    Wordt aangeroepen door module_loader.py bij het opstarten van Nova.

    Let op: module_loader.py roept dynamische modules altijd aan als
    init_module(event_bus, sem) — waarbij "sem" de semantic-module
    (Layer 3) is. Daarom accepteert deze functie een
    "semantic_module"-parameter, net zoals word_associations_learner.py
    dat ook al doet. We gebruiken semantic_module hier momenteel nog
    niet.

    LET OP: dit is Fase 1-2 van 5. Er wordt nog NIETS automatisch
    opgeslagen naar schijf bij elk event — dat komt pas in Fase 5.
    Herstart je Nova, dan is alles wat tot dan toe geleerd is, weer weg.
    Dat is verwacht gedrag voor deze fase. Je kan wel manueel
    save_to_disk() aanroepen om tussentijds te kijken wat er verzameld is.
    """
    instance = PatternMatcher(event_bus, semantic_module=semantic_module)
    if event_bus is not None:
        event_bus.publish("module_loaded", {"name": "pattern_matcher"})
    return instance