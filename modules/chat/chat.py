# modules/chat/chat.py

from identity import self_query
from identity import self_architecture

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
        event_bus.subscribe("intent_properties", self.on_properties)
        event_bus.subscribe("intent_meaning", self.on_meaning)
        event_bus.subscribe("concept_learned", self.on_concept_learned)
        event_bus.subscribe("intent_wiki", self.on_wiki_response)
        event_bus.subscribe("intent_identity", self.on_identity_question)
        event_bus.subscribe("intent_self_architecture", self.on_self_architecture_question)

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

        if self.semantic and hasattr(self.semantic, "explain_is_a"):
            msg = self.semantic.explain_is_a(source, target)
        elif self.semantic and hasattr(self.semantic, "is_a") and self.semantic.is_a(source, target):
            msg = f"Ja, een {source} is een {target}."
        else:
            msg = f"Nee, een {source} is geen {target}."

        self.event_bus.publish("layer4_response", {"text": msg})

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
        results = self.semantic.get_causes(word) if self.semantic else []
        if results:
            self.event_bus.publish("layer4_response", {
                "text": f"'{word}' veroorzaakt: {', '.join(results)}."
            })
        else:
            self.event_bus.publish("layer4_response", {
                "text": f"Ik weet niet wat '{word}' veroorzaakt."
            })

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
    # 6. Concept learned (logging / feedback)
    # -------------------------
    def on_concept_learned(self, data, event_type=None):
        word = data.get("word")
        definition = data.get("definition")
        # Console logging is ok; geen chat_response hier nodig
        print(f"Nova leerde een nieuw woord: {word} → {definition}")

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
