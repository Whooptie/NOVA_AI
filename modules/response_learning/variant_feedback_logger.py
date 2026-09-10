# modules/response_learning/variant_feedback_logger.py
"""
Response Variant Learning (response_variant_learning_roadmap.md).

Fase 1 (altijd actief, geen classifier nodig):
Logt élke keuze die response_engine.py's _kies_variant() maakt naar
data/variant_feedback.jsonl -- puur observatie, verandert niets aan
WELKE variant gekozen wordt. Luistert op het "variant_gekozen"-event
dat _kies_variant() al publiceert.

Fase 2 (enkel effectief zodra er genoeg data is):
Koppelt Kevins EERSTVOLGENDE bericht na een variant-keuze aan die
keuze, via de ECHTE sentiment-nuance-classifier (modules/preferences/
sentiment_classifier.py -- positief/neutraal_gemengd/negatief), en
berekent daaruit per (sjabloon_naam, variant_index) een score. Die
score wordt via get_gewichten() aan response_engine.py aangeboden,
die er -- ENKEL als er genoeg observaties zijn -- random.choices()
mee doet i.p.v. gelijke kansen. Blijft ALTIJD toeval bevatten: er
wordt hier nooit een gewicht van 0 teruggegeven.

BELANGRIJKE, BEWUSTE KEUZES (afgesproken met Kevin, 20 augustus 2026):

1. GEEN personality_style-veld. response_engine.py's _kies_variant()
   heeft dat vandaag niet beschikbaar (dat is Fase 7 van response_
   engine.py's eigen roadmap, "tone_engine.py/personality_engine.py
   laten meespelen in variant-keuze" -- nog niet gebouwd). Dit
   bestand verzint dat veld niet -- als Fase 7 ooit gebouwd wordt,
   komt er dan een aparte uitbreiding, geen gok nu al.

2. APART TRAININGSBESTAND (data/variant_feedback.jsonl), NIET via
   memory.py's automatische wildcard-subscribe (event_bus.subscribe
   ("*", ...) in memory.py sla ALLE events al op in interactions.
   jsonl/interactions.db). Bewuste keuze van Kevin: een apart,
   overzichtelijk bestand maakt het makkelijker om later te bepalen
   hoeveel observaties "genoeg" zijn per variant.

3. GEEN "grof_sentiment" doorgeven aan sentiment_classifier.
   classificeer(). Dat argument is bedoeld voor voorkeur-zinnen met
   een al bekend regex-resultaat (intent_router.py's _ontleed_
   voorkeur_zin()) -- gewone reactie-zinnen op een Nova-antwoord
   hebben dat niet. Zonder model valt classificeer() anders terug op
   een hardcoded "positief" -- dat zou stilzwijgend valse "positief"-
   data in dit logbestand plaatsen zolang er nog geen model getraind
   is. Daarom: als sentiment_classifier.model nog None is, loggen we
   reactie_sentiment als None (eerlijk "geen data"), we gokken nooit.

4. "EERSTVOLGENDE REACTIE" = precies ÉÉN open koppeling tegelijk, per
   sjabloon_naam. Zodra een NIEUWE variant_gekozen-event voor
   hetzelfde sjabloon binnenkomt terwijl de vorige nog geen sentiment
   gekregen heeft, wordt die vorige koppeling losgelaten (blijft
   permanent None/ongekoppeld) -- NOOIT met terugwerkende kracht een
   verkeerd bericht koppelen. Dit voorkomt dat Kevins TWEEDE vraag
   (zonder eerst op het eerste antwoord te reageren) ten onrechte als
   "reactie" op het eerste antwoord gelabeld wordt.

5. DREMPEL: MIN_OBSERVATIES_PER_VARIANT = 8 (zie klasse-attribuut
   hieronder voor de volledige onderbouwing). Dit is een STARTWAARDE,
   geen definitieve keuze -- makkelijk aan te passen zodra er meer
   inzicht is in hoe snel variant_feedback.jsonl vult.

6. RUIS-BEWUSTZIN: dit werkt PER sjabloon_naam, niet in één globale
   pot. Sjablonen als "onbekend"/"interruption_vraag" zullen van
   nature trager (of nooit) de drempel halen, omdat Kevins reactie
   daar meer over het ONDERWERP (teleurstelling dat Nova iets niet
   weet, wel/niet gestoord willen worden) gaat dan over de specifieke
   FORMULERING -- dat is verwacht en gewenst gedrag, geen bug. Geen
   apart uitsluitingsmechanisme nodig: de drempel + het neutrale
   gewicht voor te-weinig-data vangen dit vanzelf op.
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional


class VariantFeedbackLogger:
    # Zie punt 5 in de docstring hierboven voor de volledige
    # onderbouwing van dit getal. Klasse-attribuut i.p.v. hardcoded
    # in de methode zelf, zodat Kevin dit later met 1 regel kan
    # aanpassen (bv. "logger.MIN_OBSERVATIES_PER_VARIANT = 15") zonder
    # in de logica zelf te moeten zoeken.
    MIN_OBSERVATIES_PER_VARIANT = 8

    # Sentiment-categorieën van sentiment_classifier.py omgezet naar
    # een score. "neutraal_gemengd" krijgt bewust 0.5 (het midden),
    # niet 0.0 -- een gemengde reactie is geen straf, gewoon geen
    # duidelijk signaal in beide richtingen.
    SENTIMENT_NAAR_SCORE = {
        "positief": 1.0,
        "neutraal_gemengd": 0.5,
        "negatief": 0.0,
    }

    # Ondergrens voor een gewicht in get_gewichten() -- GEEN gewicht
    # wordt ooit kleiner dan dit, ongeacht hoe slecht een variant
    # scoort. Zie response_variant_learning_roadmap.md, sectie
    # "Eerlijkheid": dit systeem vervangt random.choice() door een
    # GEWOGEN random.choices(), nooit door een deterministische
    # keuze -- elke variant moet altijd mogelijk blijven.
    MIN_GEWICHT = 0.05

    def __init__(self, event_bus, sentiment_classifier=None, data_dir=None):
        self.event_bus = event_bus
        self.sentiment_classifier = sentiment_classifier

        if data_dir is None:
            project_root = Path(__file__).resolve().parent.parent.parent
            data_dir = project_root / "data"
        else:
            data_dir = Path(data_dir)

        data_dir.mkdir(parents=True, exist_ok=True)
        self._pad = data_dir / "variant_feedback.jsonl"

        # In-memory scores, opgebouwd bij opstart uit het bestaande
        # bestand (zie _herbouw_scores_uit_bestand()) EN bijgewerkt
        # bij elke nieuwe sentiment-koppeling. get_gewichten() gebruikt
        # ENKEL deze in-memory structuur -- geen bestand-IO bij elke
        # variant-keuze, dat zou Nova's antwoordsnelheid onnodig
        # vertragen.
        #
        # Structuur: self._scores[sjabloon_naam][variant_index] =
        #     {"totaal_score": float, "aantal": int}
        self._scores: Dict[str, Dict[int, Dict[str, float]]] = {}

        # Precies 1 open koppeling per sjabloon_naam tegelijk (zie
        # punt 4 in de docstring). Structuur:
        # self._open_koppeling[sjabloon_naam] = {
        #     "gekozen_variant_index": int,
        #     "moment": float (time.time()),
        # }
        self._open_koppeling: Dict[str, Dict] = {}

        self._herbouw_scores_uit_bestand()

        event_bus.subscribe("variant_gekozen", self.on_variant_gekozen)
        event_bus.subscribe("raw_user_message", self.on_raw_user_message)

    # ------------------------------------------------------------
    # Opstart: bestaande data inlezen
    # ------------------------------------------------------------
    def _herbouw_scores_uit_bestand(self):
        """
        Leest data/variant_feedback.jsonl volledig in bij opstart, en
        bouwt de in-memory self._scores-structuur op uit alle regels
        die al een reactie_sentiment hebben (regels met None worden
        overgeslagen -- die hebben nog geen bruikbaar signaal).

        Nova draait 24/7 als daemon (zie nova_state.md) -- dit gebeurt
        dus normaal maar 1x per (zeldzame) herstart, niet vaak.
        """
        if not self._pad.exists():
            return

        try:
            with open(self._pad, "r", encoding="utf-8") as f:
                for regel in f:
                    regel = regel.strip()
                    if not regel:
                        continue
                    try:
                        entry = json.loads(regel)
                    except Exception:
                        # Eén beschadigde regel mag het inlezen van de
                        # rest van het bestand nooit blokkeren.
                        continue

                    sentiment = entry.get("reactie_sentiment")
                    if sentiment is None:
                        continue

                    score = self.SENTIMENT_NAAR_SCORE.get(sentiment)
                    if score is None:
                        continue

                    self._voeg_score_toe(
                        entry.get("sjabloon_naam"),
                        entry.get("gekozen_variant_index"),
                        score,
                    )
        except Exception as e:
            print(f"[VARIANT_FEEDBACK_LOGGER] Kon bestaand bestand niet volledig inlezen: {e}")

    def _voeg_score_toe(self, sjabloon_naam, variant_index, score):
        if sjabloon_naam is None or variant_index is None:
            return

        per_sjabloon = self._scores.setdefault(sjabloon_naam, {})
        huidig = per_sjabloon.setdefault(variant_index, {"totaal_score": 0.0, "aantal": 0})
        huidig["totaal_score"] += score
        huidig["aantal"] += 1

    # ------------------------------------------------------------
    # Fase 1: elke variant-keuze loggen
    # ------------------------------------------------------------
    def on_variant_gekozen(self, data, event_type=None):
        """
        Wordt aangeroepen bij elke "variant_gekozen"-event vanuit
        response_engine.py's _kies_variant(). Schrijft een nieuwe
        regel naar data/variant_feedback.jsonl (reactie_sentiment nog
        None -- wordt evt. later aangevuld, zie punt 4 in de
        docstring: als NIEUWE regel, niet als wijziging van de oude
        regel, want JSONL is append-only).

        Opent meteen ook een nieuwe "wacht op reactie"-koppeling voor
        dit sjabloon_naam -- vervangt een eventuele vorige, nog open
        koppeling voor HETZELFDE sjabloon (die blijft dan permanent
        ongekoppeld, zie punt 4).
        """
        sjabloon_naam = data.get("sjabloon_naam")
        variant_index = data.get("gekozen_variant_index")

        entry = {
            "sjabloon_naam": sjabloon_naam,
            "gekozen_variant_index": variant_index,
            "variant_tekst": data.get("variant_tekst"),
            "entity": data.get("entity"),
            "response_style": data.get("response_style"),
            "moment": data.get("moment"),
            "reactie_sentiment": None,
        }

        self._schrijf_regel(entry)

        if sjabloon_naam is not None:
            self._open_koppeling[sjabloon_naam] = {
                "gekozen_variant_index": variant_index,
                "moment": time.time(),
            }

    def _schrijf_regel(self, entry, max_retries=3, retry_delay=0.2):
        """
        Zelfde soort retry-aanpak als memory.py's append_to_disk() --
        een bestandsschrijving mag Nova's gedrag niet laten crashen,
        maar we proberen wel een paar keer bij een tijdelijke fout.
        """
        regel = json.dumps(entry, ensure_ascii=False) + "\n"
        for poging in range(1, max_retries + 1):
            try:
                with open(self._pad, "a", encoding="utf-8") as f:
                    f.write(regel)
                return
            except Exception as e:
                print(f"[VARIANT_FEEDBACK_LOGGER] Schrijffout (poging {poging}/{max_retries}): {e}")
                if poging < max_retries:
                    time.sleep(retry_delay)

    # ------------------------------------------------------------
    # Fase 2: sentiment van Kevins eerstvolgende reactie koppelen
    # ------------------------------------------------------------
    def on_raw_user_message(self, data, event_type=None):
        """
        Wordt aangeroepen bij ELK bericht van Kevin (intent_router.py
        publiceert dit al voor elk bericht, zie route()). Controleert
        voor elk sjabloon_naam met een open koppeling of dit bericht
        de eerstvolgende reactie is, en koppelt zo ja het sentiment.

        Zie punt 3 in de docstring: classificeer() wordt AANGEROEPEN
        zonder grof_sentiment, maar het resultaat wordt genegeerd
        (blijft None gelogd) zolang sentiment_classifier.model nog
        None is -- anders zou classificeer() zelf stilzwijgend
        "positief" teruggeven als terugvalwaarde, wat valse data zou
        loggen.
        """
        if not self._open_koppeling:
            return

        text = data.get("text", "")
        if not text:
            return

        sentiment = self._classificeer_veilig(text)

        # Alle op dit moment open koppelingen (1 per sjabloon_naam)
        # krijgen dit bericht als hun "eerstvolgende reactie" -- ze
        # worden daarna meteen gesloten (punt 4: precies 1 koppeling
        # per sjabloon tegelijk).
        for sjabloon_naam, koppeling in list(self._open_koppeling.items()):
            self._koppel_sentiment(sjabloon_naam, koppeling, sentiment)
            del self._open_koppeling[sjabloon_naam]

    def _classificeer_veilig(self, text) -> Optional[str]:
        if self.sentiment_classifier is None:
            return None

        # Punt 3: geen model geladen -> classificeer() zou hier zelf
        # "positief" gokken als terugvalwaarde. Dat willen we NIET
        # loggen als een echt signaal -- liever eerlijk None.
        if getattr(self.sentiment_classifier, "model", None) is None:
            return None

        try:
            return self.sentiment_classifier.classificeer(text)
        except Exception as e:
            print(f"[VARIANT_FEEDBACK_LOGGER] Kon sentiment niet classificeren: {e}")
            return None

    def _koppel_sentiment(self, sjabloon_naam, koppeling, sentiment):
        """
        Schrijft een NIEUWE regel (append-only, zie punt 4) die
        verwijst naar de oorspronkelijke variant-keuze, met het
        gekoppelde sentiment. Werkt meteen ook de in-memory
        self._scores bij, zodat get_gewichten() dit onmiddellijk kan
        gebruiken -- geen wachten op een herstart.
        """
        variant_index = koppeling["gekozen_variant_index"]

        entry = {
            "sjabloon_naam": sjabloon_naam,
            "gekozen_variant_index": variant_index,
            "reactie_sentiment": sentiment,
            "moment": koppeling["moment"],
            "type": "sentiment_koppeling",
        }
        self._schrijf_regel(entry)

        if sentiment is None:
            return

        score = self.SENTIMENT_NAAR_SCORE.get(sentiment)
        if score is None:
            return

        self._voeg_score_toe(sjabloon_naam, variant_index, score)

    # ------------------------------------------------------------
    # Publieke API voor response_engine.py
    # ------------------------------------------------------------
    def get_gewichten(self, sjabloon_naam: str, aantal_varianten: int) -> Optional[List[float]]:
        """
        Geeft een lijst gewichten terug (lengte == aantal_varianten),
        te gebruiken in random.choices(varianten, weights=...).

        Geeft None terug als er voor DIT sjabloon nog GEEN ENKELE
        variant de drempel (MIN_OBSERVATIES_PER_VARIANT) gehaald
        heeft -- response_engine.py valt dan terug op zijn eigen
        gelijke-kansen-gedrag (random.choice()). Dit voorkomt dat een
        sjabloon met nauwelijks data toch al "gewogen" lijkt te
        worden op basis van 1-2 toevalstreffers.

        Zodra minstens 1 variant genoeg observaties heeft, geeft dit
        WEL al gewichten terug voor ALLE varianten van dit sjabloon --
        varianten met te weinig eigen data krijgen dan het NEUTRALE
        gewicht (0.5, het midden van de score-schaal), niet 0 en niet
        een gok. Zo blijft een variant met weinig observaties normaal
        meedraaien i.p.v. onterecht bestraft te worden puur omdat hij
        toevallig minder vaak gekozen werd.

        Gewicht = MIN_GEWICHT + gemiddelde_score (dus tussen
        MIN_GEWICHT en 1.0 + MIN_GEWICHT) -- garandeert dat geen
        gewicht ooit 0 wordt, zelfs een variant met een gemiddelde
        score van exact 0.0 (enkel negatieve reacties) blijft dus nog
        altijd een kleine kans houden.
        """
        per_sjabloon = self._scores.get(sjabloon_naam)
        if not per_sjabloon:
            return None

        heeft_genoeg_data = any(
            info["aantal"] >= self.MIN_OBSERVATIES_PER_VARIANT
            for info in per_sjabloon.values()
        )
        if not heeft_genoeg_data:
            return None

        gewichten = []
        for index in range(aantal_varianten):
            info = per_sjabloon.get(index)
            if info is None or info["aantal"] == 0:
                gemiddelde_score = 0.5  # neutraal, geen data
            else:
                gemiddelde_score = info["totaal_score"] / info["aantal"]

            gewichten.append(self.MIN_GEWICHT + gemiddelde_score)

        return gewichten


def init_module(event_bus, sentiment_classifier=None):
    """
    LET OP voor module_loader.py: dit volgt NIET het generieke
    "init_module(event_bus, sem)"-patroon -- deze module heeft
    sentiment_classifier nodig, geen semantic. Moet dus, net als
    response_engine.py/context_manager.py, HANDMATIG geladen worden
    (niet via de dynamische modules-scan), NA sentiment_classifier
    zelf (die zit in modules/preferences/ en wordt al via de
    dynamische scan geladen, dus staat op dat moment al in
    loaded_modules).
    """
    instance = VariantFeedbackLogger(event_bus, sentiment_classifier=sentiment_classifier)
    if event_bus is not None:
        event_bus.publish("module_loaded", {"name": "variant_feedback_logger"})
    return instance