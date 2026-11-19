# modules/chat/chat.py

import re

from identity import self_query
from identity import self_architecture
from identity import self_uiterlijk

class ChatModule:
    def __init__(self, event_bus, semantic_module=None):
        self.event_bus = event_bus
        self.semantic = semantic_module

        # Luister naar intents, niet naar chat_message
        event_bus.subscribe("intent_definition", self.on_definition)
        event_bus.subscribe("intent_relation_check", self.on_relation_check)
        event_bus.subscribe("intent_part_of_check", self.on_part_of_check)
        event_bus.subscribe("intent_subtypes_query", self.on_subtypes_query)
        event_bus.subscribe("intent_parts_query", self.on_parts_query)
        event_bus.subscribe("intent_related_to_check", self.on_related_to_check)
        event_bus.subscribe("intent_compare_concepts", self.on_compare_concepts)
        event_bus.subscribe("intent_bridge_query", self.on_bridge_query)
        event_bus.subscribe("intent_trending_query", self.on_trending_query)
        event_bus.subscribe("intent_memory_query", self.on_memory_query)
        event_bus.subscribe("intent_parts_with_property", self.on_parts_with_property)
        event_bus.subscribe("intent_related_to", self.on_related_to)
        event_bus.subscribe("intent_synonym", self.on_synonym)
        event_bus.subscribe("intent_antonym", self.on_antonym)
        event_bus.subscribe("intent_used_for", self.on_used_for)
        event_bus.subscribe("intent_causes", self.on_causes)
        event_bus.subscribe("intent_effects", self.on_effects)
        event_bus.subscribe("intent_causes_check", self.on_causes_check)
        event_bus.subscribe("intent_properties", self.on_properties)
        event_bus.subscribe("intent_meaning", self.on_meaning)
        # "concept_learned" werd nergens gepubliceerd; de melding "Nova leerde een
        # nieuw woord" komt uit het semantic_update-event (zie main.py).
        event_bus.subscribe("intent_wiki", self.on_wiki_response)
        event_bus.subscribe("intent_identity", self.on_identity_question)
        event_bus.subscribe("intent_self_architecture", self.on_self_architecture_question)
        event_bus.subscribe("intent_uiterlijk", self.on_uiterlijk_question)

    # -------------------------
    # 1. Begroetingen
    # -------------------------
    def on_greeting(self, data, event_type=None):
        sender = data.get("sender", "Onbekend")
        self.event_bus.publish("chat_response", {
            "text": f"Hey {sender}! 😊"
        })

    # -------------------------
    # 2. Definitievragen (ruwe tekst)
    # -------------------------
    # SINDS LAYER 4-INTEGRATIE (8 juli 2026): dit is niet meer de
    # hoofdroute. intent_router.py stuurt definitievragen nu EERST
    # naar response_engine.py (Layer 4, combineert semantic +
    # word_associations + pattern_matcher). Deze methode hier wordt
    # pas nog aangeroepen in twee gevallen:
    #   1) Layer 4 vond zelf niets (confidence <= 0.2) -> val terug
    #      op de automatische Wikipedia-fallback hieronder, die nog
    #      niet in response_engine.py zit.
    #   2) response_engine niet geladen/beschikbaar (bv. tijdens
    #      testen) -> dit blijft dan het volledige vangnet.
    # De logica hieronder is BEWUST ongewijzigd gelaten (nog steeds
    # zijn eigen get_meaning()/is_a-poging), zodat dit een volwaardig
    # vangnet blijft, ook los van Layer 4.
    def on_definition(self, data, event_type=None):
        text = (data.get("text") or "").lower()

        # haal het woord uit verschillende vormen
        for prefix in [
            "wat is",
            "wat zijn",
            "wat betekent",
            "wat betekend",
            "betekent",
            "betekend"
        ]:
            if text.startswith(prefix):
                word = text[len(prefix):].strip()
                break
        else:
            word = text

        # Lidwoorden strippen
        for art in ["de ", "het ", "een "]:
            if word.startswith(art):
                word = word[len(art):].strip()
                break

        # Bugfix #6 (18 juli 2026): losse leestekens aan het einde van
        # het woord verwijderen (punt, vraagteken, uitroepteken, komma,
        # ...). ".strip()" hierboven verwijdert enkel WITRUIMTE, geen
        # leestekens — een zin als "wat is een gitaar." gaf dus tot nu
        # toe het woord "gitaar." door aan get_meaning()/is_a-check/
        # Wikipedia, in plaats van het schone "gitaar". Dit gebeurt
        # bewust hier, VOOR het woord ergens gebruikt wordt (get_meaning,
        # is_a-relaties, en de Wikipedia-fallback verderop) — zo is elke
        # afnemer van dit woord automatisch veilig, zonder dat elk
        # bestand het zelf apart moet stripping.
        word = word.strip(".,!?;:")

        # Meerduidig woord (30 oktober 2026): de router zet "betekenis_keuze"
        # als het woord meerdere betekenissen heeft. Dan stellen we de
        # keuzevraag i.p.v. stil één betekenis te kiezen.
        if data.get("betekenis_keuze") and self.semantic and hasattr(self.semantic, "start_definitie_keuze"):
            try:
                if self.semantic.start_definitie_keuze(word, text.split()):
                    return
            except Exception:
                pass

        meaning = None
        if self.semantic and hasattr(self.semantic, "get_meaning"):
            try:
                # Bug #10-fix: de volledige (al lowercased) tekst
                # meegeven als context, zodat bij meerduidige woorden
                # (python, hart, ...) de juiste sense herkend kan
                # worden i.p.v. altijd de sense met hoogste confidence.
                meaning = self.semantic.get_meaning(word, text.split())
            except Exception:
                meaning = None

        if meaning:
            # FASE 7: via layer4_response i.p.v. rechtstreeks chat_response,
            # zodat dit ook door response_pipeline.py's tone-keten loopt
            # (zelfde behandeling als een antwoord dat wel via Layer 4 zelf
            # gevonden was — consistente "warmte" voor elk definitie-antwoord).
            self.event_bus.publish("layer4_response", {
                "text": f"{word} betekent: {meaning}"
            })
            return

        # FALLBACK: kijk of er een is_a-relatie bestaat
        if self.semantic:
            # normaliseer meervoud → enkelvoud
            pos_guess = self.semantic.sense_engine.detect_pos(word)
            norm = self.semantic.teach_engine._normalize_plural_if_noun(word, pos_guess)

            parents = self.semantic.get_relations(norm, "is_a")

            if parents:
                parent = parents[0]
                self.event_bus.publish("layer4_response", {
                    "text": f"{word} zijn een soort van {parent}."
                })
                return

        # Geen definitie en geen relatie → automatisch Wikipedia proberen
        self.event_bus.publish("intent_wiki", {"word": word, "auto": True})

    # -------------------------
    # 3. Relation check
    # -------------------------
    def _enkelvoud(self, term):
        """
        Zet het LAATSTE woord van een term van meervoud naar enkelvoud, met de
        bestaande TeachEngine._normalize_plural_if_noun (punt 70). Een woord dat
        zelf al een concept is blijft staan ("plaats" wordt nooit "plaat"). Bij
        elke twijfel of fout komt de term ongewijzigd terug.
        """
        try:
            te = self.semantic.teach_engine
            delen = term.split()
            if not delen or te.store.has_concept(delen[-1]):
                return term
            pos_guess = self.semantic.sense_engine.detect_pos(delen[-1])
            delen[-1] = te._normalize_plural_if_noun(delen[-1], pos_guess)
            return " ".join(delen)
        except Exception:
            return term

    def _splits_doel(self, target):
        """
        Splitst een doel als "dier en een zoogdier" in ["dier", "zoogdier"] (punt 72d).
        Blijft heel (een lijst met 1 element) als de hele tekst zelf een bekend
        concept is, of als een deel leeg of niet één woord is -- dan twijfelen we
        liever dan dat we iets verkeerd opsplitsen.
        """
        try:
            if self.semantic.teach_engine.store.has_concept(target):
                return [target]
        except Exception:
            pass
        delen = [d.strip() for d in re.split(r"\s+en\s+(?:een\s+|de\s+|het\s+)?", target.strip())]
        if len(delen) < 2 or any((not d) or (" " in d) for d in delen):
            return [target]
        return delen

    def on_relation_check(self, data, event_type=None):
        # Let op: confirm-flow gebeurt nu in IntentRouter,
        # hier komen alleen definitieve checks terecht.
        source = data.get("source")
        target = data.get("target")

        if not source or not target:
            self.event_bus.publish("layer4_response", {
                "text": "Ik begrijp de relatie niet helemaal."
            })
            return

        # Punt 72c: "is een boek iets om te lezen" -> geen is_a-vraag maar een doelvraag.
        if data.get("relatie") == "doel":
            self.on_doel_check(source, target)
            return

        # 10 oktober 2026: "lidwoord" komt van intent_router.py -- False
        # als Kevin zelf geen "een" vóór X typte ("is wandelen een
        # activiteit"). Ontbreekt het veld (oudere patronen), dan True:
        # exact het gedrag van vóór deze wijziging.
        lidwoord = data.get("lidwoord", True)
        een = "een " if lidwoord else ""

        # Punt 70: "is een hond een dieren" / "hoort een hond bij de dieren" ->
        # het meervoud van source en target eerst naar enkelvoud.
        source = self._enkelvoud(source)

        # Punt 72d: "is een kat een dier en een zoogdier" -> het doel bestaat uit
        # twee delen. Elk deel apart controleren; alleen "Ja" als ALLE delen kloppen.
        delen = self._splits_doel(target)
        if len(delen) > 1 and self.semantic and hasattr(self.semantic, "explain_is_a"):
            antwoorden = [
                self.semantic.explain_is_a(source, self._enkelvoud(deel), lidwoord=lidwoord)
                for deel in delen
            ]
            if all(a.startswith("Ja") for a in antwoorden):
                delen_tekst = " en ".join(f"een {self._enkelvoud(d)}" for d in delen)
                msg = f"Ja, {een}{source} is {delen_tekst}."
            else:
                msg = " ".join(antwoorden)
            self.event_bus.publish("layer4_response", {"text": msg})
            return

        target = self._enkelvoud(target)

        if self.semantic and hasattr(self.semantic, "explain_is_a"):
            msg = self.semantic.explain_is_a(source, target, lidwoord=lidwoord)
        elif self.semantic and hasattr(self.semantic, "is_a") and self.semantic.is_a(source, target):
            msg = f"Ja, {een}{source} is een {target}."
        else:
            msg = f"Nee, {een}{source} is geen {target}."

        self.event_bus.publish("layer4_response", {"text": msg})

    # -------------------------
    # Punt 72c: doelvragen + leren (punt 72c deel 3)
    # -------------------------
    def on_doel_check(self, source, doel_tekst):
        """'is een boek iets om te lezen' / 'is een paraplu bedoeld tegen regen'.

        doel_tekst is 'om te lezen', 'om mee te openen', 'tegen regen' of 'voor ...'.
        Het antwoord komt uit de kennisgraaf of uit de definitie van het woord; er komt nooit
        een stellig 'nee'. Is het een 'ja' op grond van de DEFINITIE en gaat het om een
        werkwoord, dan vraag ik daarna of ik het mag onthouden (ja/nee, via de bestaande
        relatie-bevestiging). Er wordt niets zonder jouw ja opgeslagen."""
        source = self._enkelvoud(source).strip()
        werkwoord = doel_tekst.startswith("om ")
        kern = doel_tekst.split()[-1] if werkwoord else doel_tekst.split(" ", 1)[1]

        if not (self.semantic and hasattr(self.semantic, "explain_used_for")):
            self.event_bus.publish("layer4_response", {"text": "Daar kan ik nu niet over nadenken."})
            return
        tekst, soort = self.semantic.explain_used_for(source, kern)
        self.event_bus.publish("layer4_response", {"text": tekst})

        # Per gesprek hoogstens één keer dezelfde opslagvraag, ook na "nee" (de relatie-bevestiging
        # onthoudt een "nee" niet zelf). Na een herstart kan Nova het dus opnieuw vragen.
        gevraagd = self.__dict__.setdefault("_doel_leervragen", set())
        if soort == "definitie" and werkwoord and (source, kern) not in gevraagd:
            flow = getattr(self.semantic, "flow_engine", None)
            if flow is not None:
                gevraagd.add((source, kern))
                flow.start_relation_flow(source, "used_for", kern)

    # -------------------------
    # 3B. Part-of check (nieuw, 11 juli 2026, analoog aan
    # on_relation_check hierboven maar voor part_of-ketens)
    # -------------------------
    def on_part_of_check(self, data, event_type=None):
        source = data.get("source")
        target = data.get("target")

        if not source or not target:
            self.event_bus.publish("layer4_response", {
                "text": "Ik begrijp de onderdeel-vraag niet helemaal."
            })
            return

        if self.semantic and hasattr(self.semantic, "explain_part_of"):
            msg = self.semantic.explain_part_of(source, target)
        else:
            msg = f"Ik kan nog niet controleren of '{source}' onderdeel is van '{target}'."

        self.event_bus.publish("layer4_response", {"text": msg})

    # -------------------------
    # 3B2. Related-to-check (nieuw, idee #2 uit
    # reasoning_engine_ideeen_roadmap.md, analoog aan on_part_of_check
    # hierboven maar voor related_to-ketens)
    # -------------------------
    def on_related_to_check(self, data, event_type=None):
        source = data.get("source")
        target = data.get("target")

        if not source or not target:
            self.event_bus.publish("layer4_response", {
                "text": "Ik begrijp de related-to-vraag niet helemaal."
            })
            return

        if self.semantic and hasattr(self.semantic, "explain_related_to"):
            msg = self.semantic.explain_related_to(source, target)
        else:
            msg = f"Ik kan nog niet controleren of '{source}' gerelateerd is aan '{target}'."

        self.event_bus.publish("layer4_response", {"text": msg})

    # -------------------------
    # 3B3. Vergelijking tussen 2 concepten (nieuw, idee #6 uit
    # reasoning_engine_ideeen_roadmap.md)
    # -------------------------
    # Nederlandse labels per relatietype, voor een leesbare tekst.
    # Bewust hier als klasse-attribuut i.p.v. in semantic.py: dit is
    # zuiver presentatie (Nederlandse taal), geen kennis-logica --
    # zelfde scheiding als export_concept() (data) vs.
    # concept_overview.py (presentatie) elders in de codebase.
    _COMPARE_LABELS = {
        "is_a": "is een",
        "part_of": "is onderdeel van",
        "has_part": "heeft als onderdeel",
        "related_to": "is gerelateerd aan",
        "causes": "veroorzaakt",
        "used_for": "wordt gebruikt voor",
        "synonym": "is een synoniem van",
        "antonym": "is het tegenovergestelde van",
        "instance_of": "is een voorbeeld van",
        "property": "heeft als eigenschap",
    }

    def on_compare_concepts(self, data, event_type=None):
        word_a = data.get("word_a")
        word_b = data.get("word_b")

        if not word_a or not word_b:
            self.event_bus.publish("layer4_response", {
                "text": "Welke twee dingen wil je dat ik vergelijk?"
            })
            return

        if not self.semantic or not hasattr(self.semantic, "compare_concepts"):
            self.event_bus.publish("layer4_response", {
                "text": "Ik kan nog niet vergelijken."
            })
            return

        try:
            resultaat = self.semantic.compare_concepts(word_a, word_b)
        except Exception:
            resultaat = None

        if not resultaat or not resultaat.get("per_type"):
            self.event_bus.publish("layer4_response", {
                "text": f"Ik weet nog te weinig over '{word_a}' en/of '{word_b}' om ze te vergelijken."
            })
            return

        regels = [f"Vergelijking tussen {word_a} en {word_b}:"]
        for rel_type, groepen in resultaat["per_type"].items():
            label = self._COMPARE_LABELS.get(rel_type, rel_type)

            if groepen["gedeeld"]:
                regels.append(f"  Allebei {label}: {', '.join(groepen['gedeeld'])}")
            if groepen["enkel_a"]:
                regels.append(f"  Enkel {word_a} {label}: {', '.join(groepen['enkel_a'])}")
            if groepen["enkel_b"]:
                regels.append(f"  Enkel {word_b} {label}: {', '.join(groepen['enkel_b'])}")

        msg = "\n".join(regels)
        self.event_bus.publish("layer4_response", {"text": msg})

    # -------------------------
    # 3B3B. Bruggen-woorden tussen 2 concepten (Layer 1, find_bridge(),
    # gekoppeld 9 augustus 2026, nova_state.md punt 6b)
    # -------------------------
    def on_bridge_query(self, data, event_type=None):
        """
        Zelfde structuur als on_compare_concepts() hierboven, maar
        haalt Layer 1 (word_associations_learner) op i.p.v. semantic.
        Bewust een aparte, eigen handler i.p.v. hergebruik van
        on_compare_concepts() — andere databron, andere foutmeldingen,
        en find_bridge() geeft een simpele lijst terug, geen geneste
        per-type-structuur zoals compare_concepts().
        """
        word_a = data.get("word_a")
        word_b = data.get("word_b")

        if not word_a or not word_b:
            self.event_bus.publish("layer4_response", {
                "text": "Welke twee dingen wil je dat ik op gedeelde associaties vergelijk?"
            })
            return

        # Zelfde fallback-patroon als debug_commands.py's _bridge():
        # module_loader.py gebruikt de key "word_associations_learner",
        # maar we checken defensief ook de kortere "word_associations"
        # voor het geval dat ooit verandert.
        word_assoc = self.event_bus.modules.get("word_associations_learner")
        if word_assoc is None:
            word_assoc = self.event_bus.modules.get("word_associations")

        if word_assoc is None or not hasattr(word_assoc, "find_bridge"):
            self.event_bus.publish("layer4_response", {
                "text": "Ik kan nog geen bruggen tussen woorden zoeken."
            })
            return

        try:
            bruggen = word_assoc.find_bridge(word_a, word_b)
        except Exception:
            bruggen = None

        if not bruggen:
            self.event_bus.publish("layer4_response", {
                "text": f"Ik zie bij mij nog geen gedeelde associaties tussen '{word_a}' en '{word_b}'."
            })
            return

        # Enkel het sterkste brugwoord in de hoofdzin, de rest (indien
        # aanwezig) als korte opsomming erachter — zelfde "niet alles
        # tegelijk opdreunen"-principe als idee #5's "waarom niet"-
        # uitleg (nova_changelog.md, enkel eerste alternatief tonen).
        sterkste_woord, sterkste_score = bruggen[0]
        msg = f"'{word_a}' en '{word_b}' worden bij jou vaak samen genoemd met '{sterkste_woord}'."

        overige = [w for w, _ in bruggen[1:]]
        if overige:
            msg += f" (en ook met: {', '.join(overige)})"

        self.event_bus.publish("layer4_response", {"text": msg})

    # -------------------------
    # 3B3B2. Trending woorden (Layer 1, get_trending(), gekoppeld
    # 11 augustus 2026, nova_state.md punt 6b, tweede deel)
    # -------------------------
    def on_trending_query(self, data, event_type=None):
        """
        Zelfde structuur/fallback-patroon als on_bridge_query()
        hierboven. get_trending() heeft geen woord-argumenten nodig
        (data is dus altijd leeg, {}), enkel een venster in dagen --
        vaste 7 dagen hier, geen "trending 14"-achtige varianten in
        het normale gesprek (dat blijft debugcommando-only).
        """
        word_assoc = self.event_bus.modules.get("word_associations_learner")
        if word_assoc is None:
            word_assoc = self.event_bus.modules.get("word_associations")

        if word_assoc is None or not hasattr(word_assoc, "get_trending"):
            self.event_bus.publish("layer4_response", {
                "text": "Ik kan nog niet bijhouden waar je de laatste tijd mee bezig bent."
            })
            return

        try:
            trending = word_assoc.get_trending(window_days=7, top_k=5)
        except Exception:
            trending = None

        if not trending:
            self.event_bus.publish("layer4_response", {
                "text": "Ik zie de laatste tijd nog geen duidelijk terugkerend onderwerp bij jou."
            })
            return

        sterkste_woord, _ = trending[0]
        msg = f"De laatste tijd praat je opvallend veel over '{sterkste_woord}'."

        overige = [w for w, _ in trending[1:]]
        if overige:
            msg += f" (en ook over: {', '.join(overige)})"

        self.event_bus.publish("layer4_response", {"text": msg})

    # -------------------------
    # 3B3b. Memory-vragen in natuurlijke taal (punt 14, nova_state.md)
    # -------------------------
    def on_memory_query(self, data, event_type=None):
        """
        Twee paden, zie detect_memory_query() in intent_router.py voor
        de volledige uitleg:
          - keyword aanwezig -> memory.search(), gefilterd op
            event_type == "raw_user_message" (enkel Kevins eigen
            berichten, geen chat_response-ruis zoals het help-menu).
          - keyword == None -> get_trending() (Layer 1), zelfde bron
            als on_trending_query() hierboven.
        """
        keyword = data.get("keyword")

        if keyword is None:
            word_assoc = self.event_bus.modules.get("word_associations_learner")
            if word_assoc is None:
                word_assoc = self.event_bus.modules.get("word_associations")

            if word_assoc is None or not hasattr(word_assoc, "get_trending"):
                self.event_bus.publish("layer4_response", {
                    "text": "Ik kan nog niet goed bijhouden wat er vaak terugkomt in onze gesprekken."
                })
                return

            try:
                trending = word_assoc.get_trending(window_days=7, top_k=5)
            except Exception:
                trending = None

            if not trending:
                self.event_bus.publish("layer4_response", {
                    "text": "Ik zie nog geen duidelijk terugkerend onderwerp in onze gesprekken."
                })
                return

            sterkste_woord, _ = trending[0]
            msg = f"We hebben het opvallend vaak over '{sterkste_woord}' gehad."
            overige = [w for w, _ in trending[1:]]
            if overige:
                msg += f" (en ook over: {', '.join(overige)})"

            self.event_bus.publish("layer4_response", {"text": msg})
            return

        mem = self.event_bus.modules.get("memory")
        if mem is None:
            self.event_bus.publish("layer4_response", {
                "text": "Ik kan er nu even niet bij, mijn geheugen-module is niet beschikbaar."
            })
            return

        try:
            resultaten = mem.search(keyword, limit=20)
        except Exception:
            resultaten = []

        # Filter: enkel Kevins eigen berichten, geen chat_response-ruis
        # (zoals een help-menu dat toevallig het woord bevat).
        eigen_berichten = [
            r for r in resultaten if r.get("event_type") == "raw_user_message"
        ]

        if not eigen_berichten:
            self.event_bus.publish("layer4_response", {
                "text": f"Ik vind niets terug over '{keyword}' in onze eerdere gesprekken."
            })
            return

        aantal = len(eigen_berichten)
        if aantal == 1:
            msg = f"Je hebt me één keer iets gevraagd over '{keyword}'."
        else:
            msg = f"Je hebt me al {aantal} keer iets gevraagd over '{keyword}'."

        self.event_bus.publish("layer4_response", {"text": msg})

    # -------------------------
    # 3B4. Multi-hop: onderdelen met een eigenschap (nieuw, idee #4
    # uit reasoning_engine_ideeen_roadmap.md)
    # -------------------------
    def on_parts_with_property(self, data, event_type=None):
        target = data.get("target")
        property_value = data.get("property_value")

        if not target or not property_value:
            self.event_bus.publish("layer4_response", {
                "text": "Van welk geheel, en welke eigenschap, wil je de onderdelen weten?"
            })
            return

        gefilterd = []
        if self.semantic and hasattr(self.semantic, "get_all_parts_with_property"):
            try:
                gefilterd = self.semantic.get_all_parts_with_property(target, property_value)
            except Exception:
                gefilterd = []

        if gefilterd:
            msg = f"Onderdelen van {target} die {property_value} zijn: {', '.join(gefilterd)}."
        else:
            msg = f"Ik ken geen onderdelen van {target} die {property_value} zijn."

        self.event_bus.publish("layer4_response", {"text": msg})
        
    # -------------------------
    # 3C. Subtypes-vraag (nieuw, 12 juli 2026, omgekeerde is_a-lookup)
    # -------------------------
    def on_subtypes_query(self, data, event_type=None):
        target = data.get("target")

        if not target:
            self.event_bus.publish("layer4_response", {
                "text": "Van welke categorie wil je de soorten weten?"
            })
            return

        subtypes = []
        if self.semantic and hasattr(self.semantic, "get_all_subtypes"):
            try:
                subtypes = self.semantic.get_all_subtypes(target)
            except Exception:
                subtypes = []

        if subtypes:
            msg = f"Soorten van {target} die ik ken: {', '.join(subtypes)}."
        else:
            msg = f"Ik ken nog geen soorten van {target}."

        self.event_bus.publish("layer4_response", {"text": msg})

    # -------------------------
    # 3D. Parts-vraag (nieuw, idee #1 uit
    # reasoning_engine_ideeen_roadmap.md, analoog aan on_subtypes_query
    # hierboven maar voor part_of i.p.v. is_a)
    # -------------------------
    def on_parts_query(self, data, event_type=None):
        target = data.get("target")

        if not target:
            self.event_bus.publish("layer4_response", {
                "text": "Van welk geheel wil je de onderdelen weten?"
            })
            return

        parts = []
        if self.semantic and hasattr(self.semantic, "get_all_parts"):
            try:
                parts = self.semantic.get_all_parts(target)
            except Exception:
                parts = []

        if parts:
            msg = f"Onderdelen van {target} die ik ken: {', '.join(parts)}."
        else:
            msg = f"Ik ken nog geen onderdelen van {target}."

        self.event_bus.publish("layer4_response", {"text": msg})

    # -------------------------
    # 4. Related-to vragen
    # -------------------------
    def on_related_to(self, data, event_type=None):
        word = data.get("word")

        if not word:
            self.event_bus.publish("layer4_response", {
                "text": "Waarop lijkt wat precies?"
            })
            return

        rels = []
        if self.semantic and hasattr(self.semantic, "get_relations"):
            try:
                rels = self.semantic.get_relations(word, "related_to")
            except Exception:
                rels = []

        # related_to is wederzijds ("verwant aan"): ook relaties die van
        # een ander woord NAAR dit woord wijzen tellen mee (Fase 12: een
        # voorstel wordt maar aan een kant opgeslagen).
        try:
            store = getattr(self.semantic, "store", None)
            doel = word.lower().strip()
            if store is not None:
                for naam, concept in store.concepts.items():
                    if naam == doel or naam in rels:
                        continue
                    for sense in concept.get("senses", []):
                        if sense.get("status") == "rejected":
                            continue
                        if any(r.get("type") == "related_to"
                               and r.get("target") == doel
                               and r.get("status") != "rejected"
                               for r in sense.get("relations", [])):
                            rels.append(naam)
                            break
        except Exception:
            pass

        if rels:
            msg = f"{word} lijkt op: {', '.join(rels)}"
        else:
            msg = f"Ik weet niet waarop {word} lijkt."

        self.event_bus.publish("layer4_response", {"text": msg})

    # -------------------------
    # Synoniemen
    # -------------------------
    def on_synonym(self, data, event_type=None):
        word = (data.get("word") or "").strip()

        if not word:
            self.event_bus.publish("layer4_response", {"text": "Welk woord bedoel je?"})
            return
        results = self.semantic.get_synonyms(word) if self.semantic else []
        if results:
            self.event_bus.publish("layer4_response", {
                "text": f"Synoniemen van '{word}': {', '.join(results)}."
            })
        else:
            self.event_bus.publish("layer4_response", {
                "text": f"Ik ken geen synoniemen van '{word}'."
            })

    # -------------------------
    # Antoniemen
    # -------------------------
    def on_antonym(self, data, event_type=None):
        word = (data.get("word") or "").strip()
        
        if not word:
            self.event_bus.publish("layer4_response", {"text": "Welk woord bedoel je?"})
            return
        results = self.semantic.get_antonyms(word) if self.semantic else []
        if results:
            self.event_bus.publish("layer4_response", {
                "text": f"Het tegenovergestelde van '{word}': {', '.join(results)}."
            })
        else:
            self.event_bus.publish("layer4_response", {
                "text": f"Ik ken geen tegendeel van '{word}'."
            })

    # -------------------------
    # Gebruikt voor
    # -------------------------
    def on_used_for(self, data, event_type=None):
        word = (data.get("word") or "").strip()

        if not word:
            self.event_bus.publish("layer4_response", {"text": "Welk woord bedoel je?"})
            return
        results = self.semantic.get_used_for(word) if self.semantic else []
        if results:
            self.event_bus.publish("layer4_response", {
                "text": f"'{word}' gebruik je voor: {', '.join(results)}."
            })
        else:
            self.event_bus.publish("layer4_response", {
                "text": f"Ik weet nog niet waarvoor '{word}' gebruikt wordt."
            })

    # -------------------------
    # Veroorzaakt
    # -------------------------
    def on_causes(self, data, event_type=None):
        word = (data.get("word") or "").strip()

        if not word:
            self.event_bus.publish("layer4_response", {"text": "Welk woord bedoel je?"})
            return
        # Fase 8.1 (11 oktober 2026): "wat veroorzaakt X" vraagt naar de
        # OORZAKEN van X. Voorheen werd get_causes(word) gebruikt, dat de
        # GEVOLGEN van X teruggeeft (verkeerde richting).
        oorzaken = []
        if self.semantic and hasattr(self.semantic, "get_all_causes"):
            try:
                oorzaken = self.semantic.get_all_causes(word)
            except Exception:
                oorzaken = []

        if oorzaken:
            self.event_bus.publish("layer4_response", {
                "text": f"Oorzaken van '{word}': {self._formatteer_causale_lijst(oorzaken)}."
            })
        else:
            self.event_bus.publish("layer4_response", {
                "text": f"Ik ken geen oorzaken van '{word}'."
            })

    # -------------------------
    # Gevolgen (Fase 8.1, 11 oktober 2026)
    # -------------------------
    def on_effects(self, data, event_type=None):
        word = (data.get("word") or "").strip()

        if not word:
            self.event_bus.publish("layer4_response", {"text": "Welk woord bedoel je?"})
            return

        if data.get("vervolg"):
            self._on_effects_vervolg(word)
            return

        self._en_dan_terugval = None   # nieuwe gevolgvraag: de korte herhaling begint opnieuw
        gevolgen = []
        if self.semantic and hasattr(self.semantic, "get_all_effects"):
            try:
                gevolgen = self.semantic.get_all_effects(word)
            except Exception:
                gevolgen = []

        if gevolgen:
            self.event_bus.publish("layer4_response", {
                "text": f"Gevolgen van '{word}': {self._formatteer_causale_lijst(gevolgen)}."
            })
            # Punt 77: onthoud wat Nova net noemde, zodat "en dan?" kan voortbouwen.
            last_ctx = self.event_bus.modules.get("last_context")
            if last_ctx is not None and hasattr(last_ctx, "set_gevolgen"):
                last_ctx.set_gevolgen(word, gevolgen, self._causale_basisdiepte())
        else:
            self.event_bus.publish("layer4_response", {
                "text": f"Ik ken geen gevolgen van '{word}'."
            })
            # Ook "niets weten" onthouden: "en dan?" krijgt dan een eerlijk antwoord i.p.v. stilte.
            last_ctx = self.event_bus.modules.get("last_context")
            if last_ctx is not None and hasattr(last_ctx, "set_gevolgen"):
                last_ctx.set_gevolgen(word, [], self._causale_basisdiepte())

    # Punt 77 (6 november 2026): "en dan?" na een gevolgvraag.
    # Het eerste antwoord loopt al tot MAX_DEPTH_CAUSAL (4) stappen diep. "En dan?" kijkt
    # daarom een stap-blok verder (nog eens 4), met een harde bovengrens, en noemt ALLEEN wat
    # nog niet gezegd was. Is er niets nieuws, dan zegt Nova dat eerlijk (terugval B).
    EN_DAN_MAX_DIEPTE = 8
    EN_DAN_KORT = "Nee, dat was het. Meer weet ik er niet van."
    _en_dan_terugval = None

    def _causale_basisdiepte(self):
        engine = getattr(self.semantic, "reasoning_engine", None)
        return getattr(engine, "MAX_DEPTH_CAUSAL", 4)

    def _on_effects_vervolg(self, word):
        last_ctx = self.event_bus.modules.get("last_context")
        ctx = last_ctx.get_gevolgen() if last_ctx is not None and hasattr(last_ctx, "get_gevolgen") else None
        if not ctx:
            self.event_bus.publish("layer4_response", {
                "text": "Waar wil je dat ik mee verder ga? Vraag eerst naar de gevolgen van iets."
            })
            return

        bron, getoond, diepte = ctx
        if not getoond:
            if self._en_dan_terugval == (bron, 0):
                self.event_bus.publish("layer4_response", {"text": self.EN_DAN_KORT})
                return
            self._en_dan_terugval = (bron, 0)
            self.event_bus.publish("layer4_response", {
                "text": f"Ik ken geen gevolgen van '{bron}', dus ook niets dat daarna komt."
            })
            return
        al_genoemd = [i["woord"] for i in getoond]
        nieuw = []
        nieuwe_diepte = min(diepte + self._causale_basisdiepte(), self.EN_DAN_MAX_DIEPTE)
        if nieuwe_diepte > diepte and self.semantic and hasattr(self.semantic, "get_all_effects"):
            try:
                alle = self.semantic.get_all_effects(bron, nieuwe_diepte)
            except Exception:
                alle = []
            nieuw = [i for i in alle if i["woord"] not in al_genoemd]

        if nieuw:
            woorden = ", ".join(i["woord"] for i in nieuw)
            self.event_bus.publish("layer4_response", {
                "text": (f"Verder dan wat ik al noemde, volgt er bij '{bron}': {woorden}. "
                         f"Hoe verder weg, hoe minder zeker dat is.")
            })
            last_ctx.set_gevolgen(bron, getoond + nieuw, nieuwe_diepte)
        elif self._en_dan_terugval == (bron, len(al_genoemd)):
            # Zelfde eerlijke antwoord al gegeven: nu kort.
            self.event_bus.publish("layer4_response", {"text": self.EN_DAN_KORT})
        else:
            self._en_dan_terugval = (bron, len(al_genoemd))
            self.event_bus.publish("layer4_response", {
                "text": (f"Verder dan wat ik al noemde ken ik geen gevolgen van '{bron}'. "
                         f"Dit noemde ik al: {', '.join(al_genoemd)}.")
            })

    # -------------------------
    # Causale check (Fase 8.2, 11 oktober 2026) -- analoog aan
    # on_part_of_check()/on_related_to_check()
    # -------------------------
    def on_causes_check(self, data, event_type=None):
        source = data.get("source")
        target = data.get("target")

        if not source or not target:
            self.event_bus.publish("layer4_response", {
                "text": "Ik begrijp de oorzaak-vraag niet helemaal."
            })
            return

        if self.semantic and hasattr(self.semantic, "explain_causes"):
            try:
                msg = self.semantic.explain_causes(source, target)
            except Exception:
                msg = f"Ik kan nu niet controleren of '{source}' leidt tot '{target}'."
        else:
            msg = f"Ik kan nog niet controleren of '{source}' leidt tot '{target}'."

        self.event_bus.publish("layer4_response", {"text": msg})

    @staticmethod
    def _formatteer_causale_lijst(items):
        """
        Directe oorzaken/gevolgen (diepte 1) eerst, de rest kort
        erachter -- zelfde "niet alles even zwaar opsommen"-principe
        als on_bridge_query(). Geeft bv.:
        "modder (verder weg: regen, wolk)"
        """
        direct = [i["woord"] for i in items if i["diepte"] == 1]
        verder = [i["woord"] for i in items if i["diepte"] > 1]

        delen = []
        if direct:
            delen.append(", ".join(direct))
        if verder:
            delen.append(f"(verder weg: {', '.join(verder)})")
        return " ".join(delen)

    # -------------------------
    # Eigenschappen
    # -------------------------
    def on_properties(self, data, event_type=None):
        word = (data.get("word") or "").strip()

        if not word:
            self.event_bus.publish("layer4_response", {"text": "Welk woord bedoel je?"})
            return
        results = self.semantic.get_properties(word) if self.semantic else []
        if results:
            self.event_bus.publish("layer4_response", {
                "text": f"Eigenschappen van '{word}': {', '.join(results)}."
            })
        else:
            self.event_bus.publish("layer4_response", {
                "text": f"Ik ken geen eigenschappen van '{word}'."
            })

    # -------------------------
    # 5. Betekenisvragen via parser
    # -------------------------
    def on_meaning(self, data, event_type=None):
        word = data.get("word")

        if not word:
            self.event_bus.publish("layer4_response", {
                "text": "Welk woord bedoel je precies?"
            })
            return

        meaning = None
        if self.semantic and hasattr(self.semantic, "get_meaning"):
            try:
                meaning = self.semantic.get_meaning(word)
            except Exception:
                meaning = None

        if meaning:
            self.event_bus.publish("layer4_response", {
                "text": f"{word} betekent: {meaning}"
            })
        else:
            self.event_bus.publish("layer4_response", {
                "text": f"Dat woord ken ik nog niet. Je kan het me leren met: teach {word} <betekenis>"
            })

    # -------------------------
    # 5B. Identiteitsvragen (Kevin vraagt iets over Nova zelf)
    # -------------------------
    def on_identity_question(self, data, event_type=None):
        """
        Reageert op een herkende identiteitsvraag (sub_intent uit
        intent_router.py's detect_identity_question) en publiceert het
        antwoord via layer4_response, zodat de tone-pipeline er nog
        warmte/emoji overheen legt -- zelfde behandeling als
        definitie-antwoorden.
        """
        sub_intent = data.get("sub_intent")

        antwoord_functies = {
            "who": self_query.antwoord_wie_ben_je,
            "what_are_you": self_query.antwoord_wat_ben_je,
            "is_ai": self_query.antwoord_is_ai,
            "is_human": self_query.antwoord_is_geen_mens,
            "age": self_query.antwoord_leeftijd,
            "character": self_query.antwoord_karakter,
            "likes": self_query.antwoord_wat_vind_je_leuk,
            "hobbies": self_query.antwoord_hobbies,
            "values": self_query.antwoord_waarden,
            "boundaries": self_query.antwoord_grenzen,
            "excitement": self_query.antwoord_enthousiasme,
            "uncertainty": self_query.antwoord_onzekerheid,
            "motivation": self_query.antwoord_motivatie,
            "long_term_goals": self_query.antwoord_lange_termijn_doelen,
            "strengths": self_query.antwoord_sterktes,
            "growth": self_query.antwoord_groeipunten,
            "communication_style": self_query.antwoord_communicatiestijl,
            "bond_with_kevin": self_query.antwoord_band_met_kevin,
            "self_awareness": self_query.antwoord_eigen_grenzen_kennen,
            "can_grow": self_query.antwoord_kan_groeien,
        }

        if sub_intent == "current_mood":
            # Enige uitzondering: dit leest LIVE emotie-state, niet de
            # vaste blueprint. response_pipeline.py maakt bij zijn eigen
            # init_module() al een EmotionEngine aan (self.emotion) --
            # die halen we hier op via de EventBus-moduleregistratie
            # (module_loader.py registreert elke module onder zijn
            # bestandsnaam, dus "response_pipeline" voor
            # modules/chat/response_pipeline.py).
            pipeline = self.event_bus.modules.get("response_pipeline")
            emotion_engine = getattr(pipeline, "emotion", None) if pipeline else None
            tekst = self_query.antwoord_huidig_gevoel(emotion_engine)
        else:
            functie = antwoord_functies.get(sub_intent)
            tekst = functie() if functie else "Daar heb ik eigenlijk geen goed antwoord op."

        self.event_bus.publish("layer4_response", {"text": tekst})

    # -------------------------
    # 5C. Self-architecture (nieuw, 23 juli 2026) -- Kevin vraagt hoe
    # Nova werkt (geheugen, denken, leren, privacy, architectuur), in
    # tegenstelling tot on_identity_question hierboven (wie ze is).
    # -------------------------
    def on_self_architecture_question(self, data, event_type=None):
        """
        Reageert op een herkende architectuur-vraag (topic uit
        intent_router.py's detect_self_architecture) en publiceert het
        antwoord via layer4_response -- zelfde behandeling als
        on_identity_question hierboven, zodat Nova's toon er ook hier
        doorheen schemert.
        """
        topic = data.get("topic")
        tekst = self_architecture.get_uitleg(topic)
        self.event_bus.publish("layer4_response", {"text": tekst})

    # -------------------------
    # 5D. Uiterlijk (nieuw, 16 oktober 2026) -- Kevin vraagt hoe Nova
    # eruitziet. Antwoord = opening + midden + slot uit
    # data/uiterlijk.json (zie identity/self_uiterlijk.py). Via
    # layer4_response, zodat Nova's toon er doorheen schemert.
    # -------------------------
    def on_uiterlijk_question(self, data, event_type=None):
        deel = data.get("deel")
        logger = self.event_bus.modules.get("variant_feedback_logger")
        tekst = self_uiterlijk.get_beschrijving(
            deel, event_bus=self.event_bus, feedback_logger=logger
        )
        self.event_bus.publish("layer4_response", {"text": tekst})


    # -------------------------
    # Wikipedia
    # -------------------------
    def on_wiki_response(self, data, event_type=None):
        # Wikipedia antwoorden komen rechtstreeks als chat_response
        # via WikipediaTeacher — geen extra handler nodig hier
        pass

    # -------------------------
    # 8. Fallback
    # -------------------------
    def on_fallback(self, data, event_type=None):
        self.event_bus.publish("chat_response", {
            "text": "Ik weet nog niet goed hoe ik daarop moet antwoorden, maar ik leer graag bij."
        })


def init_module(event_bus, semantic_module=None):
    chat = ChatModule(event_bus, semantic_module=semantic_module)
    event_bus.publish("module_loaded", {"name": "chat"})
    return chat
