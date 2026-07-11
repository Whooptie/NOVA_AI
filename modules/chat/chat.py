# modules/chat/chat.py

class ChatModule:
    def __init__(self, event_bus, semantic_module=None):
        self.event_bus = event_bus
        self.semantic = semantic_module

        # Luister naar intents, niet naar chat_message
        event_bus.subscribe("intent_definition", self.on_definition)
        event_bus.subscribe("intent_relation_check", self.on_relation_check)
        event_bus.subscribe("intent_related_to", self.on_related_to)
        event_bus.subscribe("intent_synonym", self.on_synonym)
        event_bus.subscribe("intent_antonym", self.on_antonym)
        event_bus.subscribe("intent_used_for", self.on_used_for)
        event_bus.subscribe("intent_causes", self.on_causes)
        event_bus.subscribe("intent_properties", self.on_properties)
        event_bus.subscribe("intent_meaning", self.on_meaning)
        event_bus.subscribe("concept_learned", self.on_concept_learned)
        event_bus.subscribe("weather_response", self.on_weather_response)
        event_bus.subscribe("intent_wiki", self.on_wiki_response)

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

        meaning = None
        if self.semantic and hasattr(self.semantic, "get_meaning"):
            try:
                meaning = self.semantic.get_meaning(word)
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
            self.event_bus.publish("chat_response", {
                "text": "Ik begrijp de relatie niet helemaal."
            })
            return

        if self.semantic and hasattr(self.semantic, "explain_is_a"):
            msg = self.semantic.explain_is_a(source, target)
        elif self.semantic and hasattr(self.semantic, "is_a") and self.semantic.is_a(source, target):
            msg = f"Ja, een {source} is een {target}."
        else:
            msg = f"Nee, een {source} is geen {target}."

        self.event_bus.publish("chat_response", {"text": msg})

    # -------------------------
    # 4. Related-to vragen
    # -------------------------
    def on_related_to(self, data, event_type=None):
        word = data.get("word")

        if not word:
            self.event_bus.publish("chat_response", {
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

        self.event_bus.publish("chat_response", {"text": msg})

    # -------------------------
    # Synoniemen
    # -------------------------
    def on_synonym(self, data, event_type=None):
        word = (data.get("word") or "").strip()
        if not word:
            self.event_bus.publish("chat_response", {"text": "Welk woord bedoel je?"})
            return
        results = self.semantic.get_synonyms(word) if self.semantic else []
        if results:
            self.event_bus.publish("chat_response", {
                "text": f"Synoniemen van '{word}': {', '.join(results)}."
            })
        else:
            self.event_bus.publish("chat_response", {
                "text": f"Ik ken geen synoniemen van '{word}'."
            })

    # -------------------------
    # Antoniemen
    # -------------------------
    def on_antonym(self, data, event_type=None):
        word = (data.get("word") or "").strip()
        if not word:
            self.event_bus.publish("chat_response", {"text": "Welk woord bedoel je?"})
            return
        results = self.semantic.get_antonyms(word) if self.semantic else []
        if results:
            self.event_bus.publish("chat_response", {
                "text": f"Het tegenovergestelde van '{word}': {', '.join(results)}."
            })
        else:
            self.event_bus.publish("chat_response", {
                "text": f"Ik ken geen tegendeel van '{word}'."
            })

    # -------------------------
    # Gebruikt voor
    # -------------------------
    def on_used_for(self, data, event_type=None):
        word = (data.get("word") or "").strip()
        if not word:
            self.event_bus.publish("chat_response", {"text": "Welk woord bedoel je?"})
            return
        results = self.semantic.get_used_for(word) if self.semantic else []
        if results:
            self.event_bus.publish("chat_response", {
                "text": f"'{word}' gebruik je voor: {', '.join(results)}."
            })
        else:
            self.event_bus.publish("chat_response", {
                "text": f"Ik weet nog niet waarvoor '{word}' gebruikt wordt."
            })

    # -------------------------
    # Veroorzaakt
    # -------------------------
    def on_causes(self, data, event_type=None):
        word = (data.get("word") or "").strip()
        if not word:
            self.event_bus.publish("chat_response", {"text": "Welk woord bedoel je?"})
            return
        results = self.semantic.get_causes(word) if self.semantic else []
        if results:
            self.event_bus.publish("chat_response", {
                "text": f"'{word}' veroorzaakt: {', '.join(results)}."
            })
        else:
            self.event_bus.publish("chat_response", {
                "text": f"Ik weet niet wat '{word}' veroorzaakt."
            })

    # -------------------------
    # Eigenschappen
    # -------------------------
    def on_properties(self, data, event_type=None):
        word = (data.get("word") or "").strip()
        if not word:
            self.event_bus.publish("chat_response", {"text": "Welk woord bedoel je?"})
            return
        results = self.semantic.get_properties(word) if self.semantic else []
        if results:
            self.event_bus.publish("chat_response", {
                "text": f"Eigenschappen van '{word}': {', '.join(results)}."
            })
        else:
            self.event_bus.publish("chat_response", {
                "text": f"Ik ken geen eigenschappen van '{word}'."
            })

    # -------------------------
    # 5. Betekenisvragen via parser
    # -------------------------
    def on_meaning(self, data, event_type=None):
        word = data.get("word")

        if not word:
            self.event_bus.publish("chat_response", {
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
            self.event_bus.publish("chat_response", {
                "text": f"{word} betekent: {meaning}"
            })
        else:
            self.event_bus.publish("chat_response", {
                "text": f"Dat woord ken ik nog niet. Je kan het me leren met: teach {word} <betekenis>"
            })

    # -------------------------
    # 6. Concept learned (logging / feedback)
    # -------------------------
    def on_concept_learned(self, data, event_type=None):
        word = data.get("word")
        definition = data.get("definition")
        # Console logging is ok; geen chat_response hier nodig
        print(f"Nova leerde een nieuw woord: {word} → {definition}")

    def on_weather_response(self, data, event_type=None):
        text = data.get("text", "")
        print(f"Nova: {text}")

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
