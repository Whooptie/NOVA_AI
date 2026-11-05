# modules/preferences/kandidaat_suggesties.py
"""
User Preferences: kandidaat-suggesties via Layer 1 (word_associations_
learner.py).

Wat dit is
----------
Losse, kleine module die luistert op 'preference_learned' (gepubliceerd
door kevin_profile.py, zie add_preference()). Telkens Kevin een woord
met een DUIDELIJK sentiment (positief of negatief -- niet
neutraal_gemengd, te onzeker als basis) vastlegt, vraagt deze module
aan Layer 1 (word_associations_learner.find_related()) welk ander woord
daar sterk mee geassocieerd is, en stelt dat -- als het nog niet in het
profiel staat -- terloops voor als mogelijke nieuwe voorkeur.

Waarom een aparte module (ontwerpgesprek 26 juli 2026):
- kevin_profile.py hoort Layer 1 niet te kennen (single responsibility:
  kevin_profile.py is pure opslag, niet coördinatie tussen modules).
- intent_router.py is al een groot bestand; dit is een eigen, kleine
  verantwoordelijkheid die net als sentiment_classifier.py beter apart
  staat.

Waarom dit GEEN sentiment-schatter is (belangrijk onderscheid t.o.v.
Layer 1's eigen get_word_sentiment()): word_associations_learner.py
heeft al een get_word_sentiment()-methode, maar die is zelf expliciet
gemarkeerd als "GEEN sentiment-AI/ML-model", een ruwe woordenlijst-
gok. Nu er een echt getraind model bestaat (sentiment_classifier.py),
zou het gebruiken van Layer 1's oudere sentiment-gok ernaast enkel
verwarring geven (twee verschillende, mogelijk tegenstrijdige
sentiment-inschattingen). Deze module gebruikt Layer 1 daarom NOOIT om
sentiment te schatten -- enkel om KANDIDAAT-WOORDEN te vinden via
find_related() (co-occurrence/PMI), een heel ander soort taak.

Autonomie-principe: Nova SUGGEREERT enkel, ze slaat nooit automatisch
iets op namens Kevin. Bevestiging gebeurt gewoon via het al bestaande
'onthoud:'-commando (Fase 2) -- geen nieuwe pending_question-flow
nodig, Kevin kan de suggestie ook gewoon negeren.
"""

import os
import json

# Gedeelde stopwoordenlijst (core/nl_stopwoorden.py): Layer 1 filtert die al,
# maar we controleren de kandidaat hier nog eens, voor het geval een woord
# via een andere route (bv. een sense-sleutel) toch binnenkomt.
from core.nl_stopwoorden import STOPWOORDEN


class KandidaatSuggesties:
    # Minimale PMI-score (zie word_associations_learner.get_associations())
    # om een kandidaat de moeite waard te maken om te tonen. Onder deze
    # drempel is de associatie te zwak/toevallig om als suggestie te
    # tonen -- bewust conservatief gekozen, liever te weinig suggesties
    # dan ruis.
    MIN_PMI_DREMPEL = 0.4

    # Punt 67 (5 november 2026): woorden waarmee Kevin een VOORKEUR of een
    # COMMANDO uitspreekt, maar die zelf nooit een voorkeur-onderwerp zijn.
    # Layer 1 leert van alles wat Kevin typt, dus na "onthoud: ik hou van
    # thee" stonden "thee" en "hou(den)" samen in dezelfde zin en stelde
    # Nova "houden" voor. Idem "wis" uit "wis definitief: thee".
    # Bewust hier en NIET in core/nl_stopwoorden.py: "houden" is in andere
    # zinnen een zinvol woord voor Layer 1 en response_pipeline.py.
    NEGEER_KANDIDATEN = frozenset({
        "hou", "houd", "houden", "houdt",
        "haat", "haten", "haatte",
        "lust", "lusten",
        "vind", "vinden", "vindt",
        "wis", "wissen", "wist",
        "onthouden", "vergeten", "verwijderen", "definitief",
        "leuk", "favoriet", "favoriete", "liefst", "graag",
    })

    def __init__(self, event_bus, kevin_profile=None, word_associations=None,
                 semantic=None):
        self.event_bus = event_bus
        self.kevin_profile = kevin_profile
        self.word_associations = word_associations
        # Punt 67: alleen woorden die al een concept zijn worden voorgesteld.
        # Zonder semantic (None) staat dit filter UIT, zodat de module dan
        # werkt zoals voorheen.
        self.semantic = semantic

        base = os.path.dirname(__file__)
        self._gesuggereerd_pad = os.path.join(base, "kandidaat_suggesties_gedaan.json")
        self._al_gesuggereerd = self._laad_gesuggereerd()

        if event_bus:
            event_bus.subscribe("preference_learned", self._on_preference_learned)

    # ---------------------------------------------------------
    # Cooldown-bijhouden (welke bron->kandidaat-paren al gesuggereerd zijn)
    # ---------------------------------------------------------
    def _laad_gesuggereerd(self):
        """
        Leest welke (bron_woord, kandidaat_woord)-paren al ooit
        gesuggereerd zijn, zodat Nova niet blijft herhalen. Simpel
        platte lijst van "bron|kandidaat"-strings i.p.v. een geneste
        structuur -- makkelijker te lezen/debuggen voor Kevin.
        """
        if not os.path.exists(self._gesuggereerd_pad):
            return set()

        try:
            with open(self._gesuggereerd_pad, "r", encoding="utf-8") as f:
                lijst = json.load(f)
            return set(tuple(item.split("|", 1)) for item in lijst)
        except Exception:
            return set()

    def _sla_gesuggereerd_op(self):
        try:
            lijst = [f"{bron}|{kandidaat}" for bron, kandidaat in self._al_gesuggereerd]
            with open(self._gesuggereerd_pad, "w", encoding="utf-8") as f:
                json.dump(lijst, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[KANDIDAAT_SUGGESTIES] Kon gesuggereerd-bestand niet opslaan: {e}")

    # ---------------------------------------------------------
    # Kernlogica
    # ---------------------------------------------------------
    def _on_preference_learned(self, data):
        """
        Subscriber op 'preference_learned' (kevin_profile.py). Enkel
        een duidelijk positief/negatief sentiment triggert een
        suggestie -- neutraal_gemengd is zelf al een onzekere/genuanceerde
        inschatting, en zou een te wankele basis zijn om weer een NIEUWE
        suggestie op te bouwen.
        """
        actief_sentiment = data.get("actief_sentiment")
        if actief_sentiment not in ("positief", "negatief"):
            return

        if not self.word_associations or not self.kevin_profile:
            return

        bron_woord = data["woord"]
        kandidaat, score = self._vind_kandidaat(bron_woord)

        if kandidaat is None:
            return

        self._al_gesuggereerd.add((bron_woord, kandidaat))
        self._sla_gesuggereerd_op()

        tekst = self._formuleer_suggestie(bron_woord, kandidaat)
        self.event_bus.publish("layer4_response", {"text": tekst})
        print(
            f"[KANDIDAAT_SUGGESTIES] Suggestie voor '{kandidaat}' "
            f"(via associatie met '{bron_woord}', score {score})."
        )

    def _vind_kandidaat(self, bron_woord):
        """
        Zoekt het sterkste kandidaat-woord voor bron_woord via Layer 1,
        dat (a) boven MIN_PMI_DREMPEL scoort, (b) nog niet in het
        profiel staat, en (c) nog niet eerder gesuggereerd is voor DIT
        bron_woord.

        Geeft terug: (kandidaat_woord, score) van de eerste match, of
        (None, None) als er niets geschikts is. find_related() geeft
        resultaten al gesorteerd van sterk naar zwak, dus de eerste
        match die door de filters komt is meteen de beste beschikbare.
        """
        try:
            gerelateerd = self.word_associations.find_related(
                bron_woord, top_k=5, min_confidence=self.MIN_PMI_DREMPEL
            )
        except Exception as e:
            print(f"[KANDIDAAT_SUGGESTIES] Fout bij find_related(): {e}")
            return None, None

        for kandidaat, score in gerelateerd:
            if not self._is_geschikte_kandidaat(kandidaat):
                continue
            if self.kevin_profile.get_preference(kandidaat) is not None:
                continue
            if (bron_woord, kandidaat) in self._al_gesuggereerd:
                continue
            return kandidaat, score

        return None, None

    def _is_geschikte_kandidaat(self, kandidaat):
        """
        Punt 67: filtert kandidaten die nooit een voorkeur-onderwerp kunnen
        zijn. Twee lagen, puur opzoeking (geen ML):

        1. Negeerlijst: stopwoorden en voorkeur-/commandowoorden
           (NEGEER_KANDIDATEN), bv. "houden" en "wis".
        2. Concept-filter: het woord moet al een concept zijn in
           concepts.json. Werkwoorden en losse woorden staan daar normaal
           niet in (response_pipeline.py laat enkel zelfstandige
           naamwoorden als 'unknown'-concept toe). Staat er geen semantic-
           module ingeprikt, dan slaan we deze laag over.

        Layer 1 kan een sense-sleutel teruggeven ("python#2"); we toetsen
        dan op het kale woord ("python").
        """
        woord = str(kandidaat).split("#", 1)[0].strip().lower()
        if not woord:
            return False
        if woord in self.NEGEER_KANDIDATEN or woord in STOPWOORDEN:
            return False

        if self.semantic is not None:
            try:
                if not self.semantic.store.has_concept(woord):
                    return False
            except Exception:
                return False

        return True

    def _formuleer_suggestie(self, bron_woord, kandidaat):
        """
        Bouwt de suggestie-zin. Bewust kort en terloops, geen dwingende
        vraag -- Kevin kan dit negeren zonder dat er iets moet
        "afgehandeld" worden (geen pending_question).
        """
        return (
            f"Trouwens, je noemde '{bron_woord}' -- hoort '{kandidaat}' "
            f"daar ook een beetje bij? Zeg maar 'onthoud: ik hou van "
            f"{kandidaat}' als dat klopt."
        )


def init_module(event_bus, semantic_module=None):
    """
    Standaard module_loader.py-conventie. 'semantic_module' wordt hier
    niet gebruikt maar moet aanwezig zijn voor de dynamische scan.
    kevin_profile en word_associations worden NIET hier meegegeven
    (net als bij intent_router/session_watcher) -- deze module wordt
    dynamisch geladen (stap 3), VOOR beide afhankelijkheden gegarandeerd
    bestaan. module_loader.py prikt ze na de laadfase apart in, zie het
    zoek/vervang-blok daarvoor.
    """
    instance = KandidaatSuggesties(event_bus)
    event_bus.publish("module_loaded", {"name": "kandidaat_suggesties"})
    return instance