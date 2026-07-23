# core/intent_router.py
import re

C_RESET = "\033[0m"
C_GREEN = "\033[92m"
C_BLUE = "\033[94m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_CYAN = "\033[96m"
C_MAGENTA = "\033[95m"

def dbg(label, text=""):
    print(f"{C_CYAN}[ROUTER]{C_RESET} {label} {text}")

class IntentRouter:
    def __init__(self, event_bus, semantic_module=None):
        self.event_bus = event_bus
        self.semantic = semantic_module
        self.awaiting_confirmation = None

        event_bus.subscribe("chat_message", self.route)
        dbg(f"{C_GREEN}IntentRouter geladen{C_RESET}")

    # ---------------------------------------------------------
    # Reboot-commando
    # ---------------------------------------------------------
    def detect_reboot(self, text):
        if text.strip().lower() != "/reboot":
            return False

        dbg(f"{C_RED}→ reboot commando ontvangen{C_RESET}")
        # Let op: GEEN chat_response event hier — dat zou pas later
        # in main.py opgehaald worden, maar tegen die tijd bestaat dit
        # proces al niet meer (os.execv heeft het dan al vervangen).
        # De afscheidsboodschap gebeurt daarom rechtstreeks via print()
        # in reboot_manager.py, want dat verschijnt wél meteen.
        self.event_bus.publish("system:reboot", {})
        return True
    
    # ---------------------------------------------------------
    # Teach-flow
    # ---------------------------------------------------------
    def handle_teach(self, text):
        if not text.startswith("teach "):
            return False

        parts = text.split(maxsplit=2)
        if len(parts) != 3:
            return False

        # 1. teach <woord> noun/verb/adj
        if parts[2] in ("noun", "verb", "adj"):
            self.event_bus.publish("teach_pos", {
                "word": parts[1],
                "pos": parts[2]
            })
            return True

        # 2. teach <woord> <betekenis>
        self.event_bus.publish("teach_concept", {
            "word": parts[1],
            "meaning": parts[2]
        })
        return True

    # ---------------------------------------------------------
    # Example-flow (voorbeeldzin toevoegen)
    # ---------------------------------------------------------
    def handle_example(self, text):
        if not text.startswith("example "):
            return False

        parts = text.split(maxsplit=2)
        if len(parts) != 3:
            self.event_bus.publish("chat_response", {
                "text": "Gebruik: example <woord> <voorbeeldzin>"
            })
            return True

        word = parts[1]
        sentence = parts[2]

        self.event_bus.publish("teach_example", {
            "word": word,
            "sentence": sentence
        })
        return True

    # ---------------------------------------------------------
    # Confirm-flow (teach)
    # ---------------------------------------------------------
    def handle_confirmation(self, text):
        if not self.awaiting_confirmation:
            return False
        return False

    # ---------------------------------------------------------
    # Definition
    # ---------------------------------------------------------
    def detect_definition(self, text):
        t = text.lower().strip()

        # Synoniemen
        for p in ["wat zijn synoniemen van ", "wat is een synoniem van ", "synoniemen van "]:
            if t.startswith(p):
                word = t[len(p):].strip().rstrip("?.")
                self.event_bus.publish("intent_synonym", {"word": word})
                return True

        # Antoniemen
        for p in ["wat is het tegenovergestelde van ", "wat zijn antoniemen van ", "tegendeel van "]:
            if t.startswith(p):
                word = t[len(p):].strip().rstrip("?.")
                self.event_bus.publish("intent_antonym", {"word": word})
                return True

        # Waarvoor gebruik je X
        for p in ["waarvoor gebruik je ", "waarvoor is ", "waarvoor dient "]:
            if t.startswith(p):
                word = t[len(p):].strip().rstrip("?.")
                for art in ["de ", "het ", "een "]:
                    if word.startswith(art):
                        word = word[len(art):].strip()
                        break
                self.event_bus.publish("intent_used_for", {"word": word})
                return True

        # Wat veroorzaakt X
        for p in ["wat veroorzaakt ", "wat zorgt voor "]:
            if t.startswith(p):
                word = t[len(p):].strip().rstrip("?.")
                self.event_bus.publish("intent_causes", {"word": word})
                return True

        # Wat zijn eigenschappen van X
        for p in ["wat zijn eigenschappen van ", "wat zijn kenmerken van "]:
            if t.startswith(p):
                word = t[len(p):].strip().rstrip("?.")
                self.event_bus.publish("intent_properties", {"word": word})
                return True
            
        # Waarop lijkt X (related_to)
        for p in ["waarop lijkt ", "waar lijkt ", "wat lijkt op "]:
            if t.startswith(p):
                word = t[len(p):].strip().rstrip("?.")
                for art in ["de ", "het ", "een "]:
                    if word.startswith(art):
                        word = word[len(art):].strip()
                        break
                self.event_bus.publish("intent_related_to", {"word": word})
                return True

        # Wikipedia opzoeken
        for p in ["wiki ", "leer wikipedia ", "zoek op "]:
            if t.startswith(p):
                word = t[len(p):].strip().rstrip("?.")
                for art in ["de ", "het ", "een "]:
                    if word.startswith(art):
                        word = word[len(art):].strip()
                        break
                self.event_bus.publish("intent_wiki", {"word": word})
                return True
                
        # Definitievragen (crashfix: woord veilig ophalen)
        prefixes = [
            "wat is ",
            "wat zijn ",
            "wat betekent ",
            "wat betekend ",
            "betekent ",
            "betekend ",
            "definieer ",
            "definieer: ",
            "definitie van "
        ]
        for p in prefixes:
            if t.startswith(p):
                word = t[len(p):].strip().rstrip("?.")
                if not word:
                    return False
                # Lidwoorden strippen
                for art in ["de ", "het ", "een "]:
                    if word.startswith(art):
                        word = word[len(art):].strip()
                        break

                # Per-woord-timing (Layer 2-koppeling, uitbreiding op de
                # bewust generieke "definitie"-topic uit Fase 7): het
                # herkende woord hier bewaren als instance-attribuut,
                # zodat route() straks (na deze aanroep) een woord-
                # specifiek topic kan publiceren i.p.v. het vaste
                # "definitie". Alleen HIER, in de definitie-tak, gezet --
                # blijft None/ongewijzigd voor alle andere intents.
                self._laatste_definitie_woord = word

                # Layer 4 (response_engine) EERST proberen: die combineert
                # semantic + word_associations + pattern_matcher tot één
                # antwoord. Alleen als Layer 4 zelf geen definitie/relatie
                # vond (confidence <= 0.2, dat is zijn "weet ik niet"-geval,
                # zie response_engine.py), vallen we terug op de oude route
                # via chat.py's intent_definition — want DIE heeft nog de
                # automatische Wikipedia-fallback die Layer 4 niet heeft.
                # LET OP (Fase 7): we publiceren "layer4_response" i.p.v.
                # rechtstreeks "chat_response" — zo loopt de tekst nog
                # door response_pipeline.py's tone-keten (emotie/tone/
                # expression_injector), net als greeting/fallback al
                # deden. response_pipeline.py verzint daarbij GEEN nieuwe
                # tekst, het voegt enkel Nova's stemming/expressie toe.
                response_engine = self.event_bus.modules.get("response_engine")

                if response_engine is not None:
                    resultaat = response_engine.generate(word)

                    if resultaat.get("confidence", 0.0) > 0.2:
                        self.event_bus.publish("layer4_response", {
                            "text": resultaat["text"]
                        })
                        return True
                    # confidence <= 0.2 -> Layer 4 wist het niet, val
                    # door naar de oude route hieronder (met Wikipedia).

                self.event_bus.publish("intent_definition", {
                    "text": text,
                    "word": word
                })
                return True

        return False

    # ---------------------------------------------------------
    # Greeting
    # ---------------------------------------------------------
    def detect_greeting(self, text):
        greetings = {"hallo", "hoi", "hey", "hello", "dag", "yo"}
        if text in greetings:
            dbg(f"{C_GREEN}→ greeting{C_RESET}")
            self.event_bus.publish("intent_greeting", {"sender": self._get_sender_name()})
            return True
        return False

    def _get_sender_name(self):
        """
        Layer 6, stap 5 (17 juli 2026): haalt de naam van de huidige
        spreker op via presence_detector.get_current_speaker() (Layer
        5), i.p.v. de vroegere hardcoded "user"-placeholder.

        Via event_bus.modules i.p.v. een directe import, dezelfde
        aanpak als response_pipeline.py's _get_response_style() eerder
        deze sessie — voorkomt een harde afhankelijkheid tussen
        intent_router.py en presence_detector.py, en blijft werken
        ongeacht laadvolgorde.

        Valt terug op "Kevin" als presence_detector (nog) niet
        beschikbaar is — nooit een crash, en nooit terug naar de oude,
        onpersoonlijke "user"-placeholder.
        """
        try:
            presence = self.event_bus.modules.get("presence_detector")
            if presence is not None and hasattr(presence, "get_current_speaker"):
                return presence.get_current_speaker()
        except Exception:
            pass
        return "Kevin"

    # ---------------------------------------------------------
    # Weather
    # ---------------------------------------------------------
    def detect_weather(self, text):
        t = text.lower()
        woorden = [w.strip(".,!?;:") for w in t.split()]

        # Los woord "weer", "weerbericht" of "temperatuur" ergens in de zin
        weerwoorden = {"weer", "weerbericht", "temperatuur"}
        if any(w in weerwoorden for w in woorden):
            dbg(f"{C_BLUE}→ weather{C_RESET}")
            self.event_bus.publish("intent_weather", {"text": text})
            return True

        # Zinnen zonder het letterlijke woord "weer"
        extra_triggers = ["is het koud", "is het warm"]
        if any(trig in t for trig in extra_triggers):
            dbg(f"{C_BLUE}→ weather{C_RESET}")
            self.event_bus.publish("intent_weather", {"text": text})
            return True

        return False
    # ---------------------------------------------------------
    # Time
    # ---------------------------------------------------------
    def detect_time(self, text):
        t = text.lower().strip()
        
        # Exacte zinnen eerst
        time_phrases = [
            "hoe laat is het",
            "wat is de tijd",
            "wat is het uur",
            "hoeveel tijd",
            "hoe laat"
        ]
        if any(phrase in t for phrase in time_phrases):
            dbg(f"{C_YELLOW}→ time_query{C_RESET}")
            self.event_bus.publish("intent_time_query", {"text": text})
            return True

        # Losse woorden — alleen als heel woord, niet als deel van een ander woord
        time_words = ["tijd", "klok"]
        words_in_text = t.split()
        if any(w in words_in_text for w in time_words):
            dbg(f"{C_YELLOW}→ time_query{C_RESET}")
            self.event_bus.publish("intent_time_query", {"text": text})
            return True

        return False

    # ---------------------------------------------------------
    # Chess
    # ---------------------------------------------------------
    def detect_chess(self, text):
        t = text.lower().strip().rstrip("?.")

        # Nieuwe partij
        new_game_phrases = [
            "nieuwe partij", "nieuw potje", "nieuw spel schaak",
            "start schaken", "begin schaken", "nieuwe schaakpartij"
        ]
        if t in new_game_phrases or any(t.startswith(p) for p in new_game_phrases):
            dbg(f"{C_GREEN}→ chess_new{C_RESET}")
            self.event_bus.publish("intent_chess_new", {})
            return True

        # Bord tonen
        board_phrases = [
            "toon bord", "laat bord zien", "huidige stand",
            "schaakbord", "wat is de stand", "bord"
        ]
        if t in board_phrases:
            dbg(f"{C_GREEN}→ chess_board{C_RESET}")
            self.event_bus.publish("intent_chess_board", {})
            return True

        # Zet in UCI-notatie: bv "e2e4", "g1f3", "e7e8q" (promotie)
        if re.fullmatch(r"[a-h][1-8][a-h][1-8][qrbn]?", t):
            dbg(f"{C_GREEN}→ chess_move{C_RESET}")
            self.event_bus.publish("intent_chess_move", {"move": t})
            return True

        # Zet in natuurlijke taal: stuksnaam + veld (bv. "paard naar f3", "pion e4")
        stukken = ["pion", "paard", "loper", "toren", "dame", "koning"]
        heeft_stuk = any(s in t for s in stukken)
        heeft_veld = bool(re.search(r'[a-h][1-8]', t))
        if heeft_stuk and heeft_veld:
            dbg(f"{C_GREEN}→ chess_move (natuurlijke taal){C_RESET}")
            self.event_bus.publish("intent_chess_move", {"move": t})
            return True

        # Alleen een veld (bv. "e4") — pion wordt aangenomen
        if re.fullmatch(r"[a-h][1-8]", t):
            dbg(f"{C_GREEN}→ chess_move (veld alleen){C_RESET}")
            self.event_bus.publish("intent_chess_move", {"move": t})
            return True

        # Moeilijkheidsgraad (bv. "moeilijkheid 5", "niveau 15")
        m = re.match(r"(?:moeilijkheid|niveau|level)\s+(\d+)", t)
        if m:
            dbg(f"{C_GREEN}→ chess_difficulty{C_RESET}")
            self.event_bus.publish("intent_chess_difficulty", {"niveau": m.group(1)})
            return True

        # Denktijd (bv. "denktijd 3", "denktijd 0.5")
        m = re.match(r"denktijd\s+(\d+(?:\.\d+)?)", t)
        if m:
            dbg(f"{C_GREEN}→ chess_think_time{C_RESET}")
            self.event_bus.publish("intent_chess_think_time", {"seconden": m.group(1)})
            return True

        # Statistieken opvragen
        if t in ["statistieken", "stats", "score", "mijn score"]:
            dbg(f"{C_GREEN}→ chess_stats{C_RESET}")
            self.event_bus.publish("intent_chess_stats", {})
            return True

        # Rokade
        if t in ["rokeer kort", "korte rokade", "rokade kort"]:
            dbg(f"{C_GREEN}→ chess_move (rokade kort){C_RESET}")
            self.event_bus.publish("intent_chess_move", {"move": "O-O"})
            return True

        if t in ["rokeer lang", "lange rokade", "rokade lang"]:
            dbg(f"{C_GREEN}→ chess_move (rokade lang){C_RESET}")
            self.event_bus.publish("intent_chess_move", {"move": "O-O-O"})
            return True

        return False

    # ---------------------------------------------------------
    # Math
    # ---------------------------------------------------------
    def detect_math(self, text):
        t = text.strip()
        if any(op in t for op in ["+", "-", "*", "/", "^"]):
            self.event_bus.publish("intent_math", {"expr": text})
            return True
        import re
        if re.search(r'\d\s*[x×]\s*\d', t):
            self.event_bus.publish("intent_math", {"expr": text})
            return True
        if re.fullmatch(r"\d+(\.\d+)?\s*°[CF]", t):
            self.event_bus.publish("intent_math", {"expr": text})
            return True
        # BUGFIX (11 juli 2026): "tan" (en andere korte math_keywords)
        # zaten voorheen als kale substring-check, waardoor gewone
        # woorden die deze letters toevallig bevatten (bv. "toestand"
        # bevat "tan") foutief als wiskunde-expressie werden herkend.
        # We gebruiken nu woordgrenzen (\b) zodat enkel het EXACTE
        # keyword als apart woord matcht, niet als deel van een ander
        # woord.
        math_keywords = ["sqrt", "sin", "cos", "tan", "log", "ln", "exp", "abs", "round"]
        if any(re.search(rf"\b{k}\b", t) for k in math_keywords):
            self.event_bus.publish("intent_math", {"expr": text})
            return True
        return False

    # ---------------------------------------------------------
    # Relation-check ("is een hond een dier")
    # ---------------------------------------------------------
    def detect_relation_check(self, text):
        t = text.lower().strip().rstrip("?.")

        # 1. "is een X een Y"
        m = re.match(r"is\s+een\s+(\w+)\s+een\s+([\w\s]+)", t)
        if m:
            self.event_bus.publish("intent_relation_check", {
                "source": m.group(1).strip(),
                "target": m.group(2).strip()
            })
            return True

        # 2. "X is een Y"
        m = re.match(r"(\w+)\s+is\s+een\s+([\w\s]+)", t)
        if m:
            self.event_bus.publish("intent_relation_check", {
                "source": m.group(1).strip(),
                "target": m.group(2).strip()
            })
            return True

        return False

    # ---------------------------------------------------------
    # Part-of-check ("is een snaar onderdeel van een orkest",
    # "zit een wiel in een fiets") — analoog aan detect_relation_check,
    # maar voor part_of i.p.v. is_a. Nieuw (11 juli 2026).
    # ---------------------------------------------------------
    def detect_part_of_check(self, text):
        t = text.lower().strip().rstrip("?.")

        # 1. "is een X onderdeel van een Y" / "is een X een onderdeel van Y"
        m = re.match(r"is\s+een\s+(\w+)\s+(?:een\s+)?onderdeel\s+van\s+(?:een\s+)?([\w\s]+)", t)
        if m:
            self.event_bus.publish("intent_part_of_check", {
                "source": m.group(1).strip(),
                "target": m.group(2).strip()
            })
            return True

        # 2. "zit een X in een Y"
        m = re.match(r"zit\s+een\s+(\w+)\s+in\s+(?:een\s+)?([\w\s]+)", t)
        if m:
            self.event_bus.publish("intent_part_of_check", {
                "source": m.group(1).strip(),
                "target": m.group(2).strip()
            })
            return True

        return False
    
    # ---------------------------------------------------------
    # Subtypes-vraag ("welke soorten dier ken je", "noem soorten
    # van dier", "wat zijn allemaal dieren") — omgekeerde is_a-
    # lookup. Nieuw (12 juli 2026).
    # ---------------------------------------------------------
    def detect_subtypes_query(self, text):
        t = text.lower().strip().rstrip("?.")

        # 1. "welke soorten X ken je" / "welke soorten van X ken je"
        m = re.match(r"welke\s+soorten\s+(?:van\s+)?(\w+)\s+ken\s+je", t)
        if m:
            self.event_bus.publish("intent_subtypes_query", {
                "target": m.group(1).strip()
            })
            return True

        # 2. "noem soorten van X" / "noem soorten X"
        m = re.match(r"noem\s+soorten\s+(?:van\s+)?(\w+)", t)
        if m:
            self.event_bus.publish("intent_subtypes_query", {
                "target": m.group(1).strip()
            })
            return True

        # 3. "wat zijn allemaal X" (bv. "wat zijn allemaal dieren")
        m = re.match(r"wat\s+zijn\s+allemaal\s+([\w\s]+)", t)
        if m:
            self.event_bus.publish("intent_subtypes_query", {
                "target": m.group(1).strip()
            })
            return True

        return False

    # ---------------------------------------------------------
    # Identiteitsvragen (Kevin vraagt iets over Nova zelf)
    # ---------------------------------------------------------
    def detect_identity_question(self, text):
        t = text.lower().strip().rstrip("?.")

        identity_patronen = {
            "who": [
                "wie ben je", "wie ben jij", "wie is nova", "wie ben jij eigenlijk",
                "vertel over jezelf", "vertel eens over jezelf", "stel jezelf voor"
            ],
            "age": [
                "hoe oud ben je", "hoe oud ben jij", "wat is je leeftijd"
            ],
            "is_ai": [
                "ben je een ai", "ben jij een ai", "ben je ai", "ben jij ai",
                "ben je een robot", "ben jij een robot", "ben je robot", "ben jij robot",
                "ben je kunstmatige intelligentie", "ben jij kunstmatige intelligentie",
                "ben je een computer", "ben jij een computer",
            ],
            "is_human": [
                "ben je een mens", "ben jij een mens", "ben je mens", "ben jij mens",
                "ben je echt", "ben jij echt",
            ],
            "what_are_you": [
                "besef je dat je een programma bent", "besef jij dat je een programma bent",
                "wat ben je eigenlijk", "wat ben jij eigenlijk",
                "wat voor soort programma ben je", "wat voor soort programma ben jij",
            ],
            "character": [
                "wat is je karakter", "hoe zou je jezelf omschrijven",
                "hoe zou jij jezelf omschrijven", "hoe ben je", "hoe ben jij",
                "beschrijf jezelf"
            ],
            "likes": [
                "wat vind je leuk", "wat vind jij leuk", "waar hou je van",
                "waar hou jij van", "wat vind je fijn"
            ],
            "hobbies": [
                "wat zijn je hobby", "wat zijn jouw hobby", "waar hou je je mee bezig",
                "wat doe je graag"
            ],
            "values": [
                "wat zijn je waarden", "wat zijn jouw waarden", "wat vind je belangrijk",
                "wat vind jij belangrijk"
            ],
            "boundaries": [
                "wat zijn je grenzen", "wat zijn jouw grenzen", "wat doe je nooit",
                "wat wil je niet"
            ],
            "current_mood": [
                "hoe voel je je", "hoe voel jij je", "hoe gaat het met je",
                "hoe gaat het met jou", "hoe is het met je", "wat is je stemming"
            ],
            "excitement": [
                "wat maakt je enthousiast", "waar word je blij van", "waar word jij blij van"
            ],
            "uncertainty": [
                "waar word je onzeker van", "wat maakt je onzeker"
            ],
            "motivation": [
                "waarom doe je dit", "waarom doe jij dit", "wat is je doel",
                "wat drijft je", "wat motiveert je"
            ],
            "long_term_goals": [
                "wat wil je bereiken", "wat wil jij bereiken",
                "wat zijn je doelen op lange termijn"
            ],
            "strengths": [
                "waar ben je goed in", "waar ben jij goed in", "wat zijn je sterktes"
            ],
            "growth": [
                "waar wil je nog in groeien", "waar wil jij nog in groeien",
                "wat zijn je groeipunten"
            ],
            "communication_style": [
                "hoe communiceer je het liefst", "heb je gevoel voor humor",
                "heb jij gevoel voor humor"
            ],
            "bond_with_kevin": [
                "wat vind je van mij", "wat vind jij van mij", "hoe is onze band"
            ],
            "self_awareness": [
                "ken je je eigen grenzen", "ken jij je eigen grenzen", "besef je je grenzen"
            ],
            "can_grow": [
                "kan je groeien", "kan jij groeien", "kan jij nog veranderen",
                "kan je nog veranderen"
            ],
        }

        for sub_intent, zinnen in identity_patronen.items():
            for zin in zinnen:
                if zin in t:
                    self.event_bus.publish("intent_identity", {"sub_intent": sub_intent})
                    return True

        return False
    
    # ---------------------------------------------------------
    # Memory test-commando's
    # ---------------------------------------------------------
    def detect_memory(self, text):
        t = text.strip()

        # "memory stats"
        if t.lower() == "memory stats":
            mem = self.event_bus.modules.get("memory")
            if not mem:
                self.event_bus.publish("chat_response", {"text": "Memory-module niet gevonden."})
                return True
            stats = mem.get_stats()
            msg = (
                f"Memory statistieken:\n"
                f"  Totaal events: {stats.get('totaal_events', 0)}\n"
                f"  Periode: {stats.get('periode', 'onbekend')}\n"
                f"  Events in RAM: {stats.get('events_in_ram', 0)}\n"
                f"  Database grootte: {stats.get('database_grootte_mb', 0)} MB"
            )
            self.event_bus.publish("chat_response", {"text": msg})
            return True

        # "memory search <woord>"
        if t.lower().startswith("memory search "):
            keyword = t[len("memory search "):].strip()
            mem = self.event_bus.modules.get("memory")
            if not mem:
                self.event_bus.publish("chat_response", {"text": "Memory-module niet gevonden."})
                return True
            resultaten = mem.search(keyword, limit=5)
            if not resultaten:
                self.event_bus.publish("chat_response", {
                    "text": f"Geen events gevonden met '{keyword}'."
                })
            else:
                regels = [f"  [{r['event_type']}] {r['data'][:80]}" for r in resultaten]
                msg = f"Gevonden ({len(resultaten)} resultaten voor '{keyword}'):\n" + "\n".join(regels)
                self.event_bus.publish("chat_response", {"text": msg})
            return True

        # "memory similar <woord>"
        if t.lower().startswith("memory similar "):
            woord = t[len("memory similar "):].strip()
            mem = self.event_bus.modules.get("memory")
            if not mem:
                self.event_bus.publish("chat_response", {"text": "Memory-module niet gevonden."})
                return True
            resultaten = mem.find_similar(woord, top_k=3)
            if not resultaten:
                self.event_bus.publish("chat_response", {
                    "text": f"Niets gevonden dat lijkt op '{woord}'."
                })
            else:
                regels = [
                    f"  (score {r['similarity']}) [{r['event_type']}] {r['data'][:60]}"
                    for r in resultaten
                ]
                msg = f"Meest gelijkende events op '{woord}':\n" + "\n".join(regels)
                self.event_bus.publish("chat_response", {"text": msg})
            return True

        return False

    # ---------------------------------------------------------
    # Help
    # ---------------------------------------------------------
    def detect_help(self, text):
        t = text.lower().strip().rstrip("?.")

        if t == "help":
            self.event_bus.publish("intent_help", {"topic": ""})
            return True

        if t.startswith("help "):
            topic = t[5:].strip()
            self.event_bus.publish("intent_help", {"topic": topic})
            return True

        return False

    # ---------------------------------------------------------
    # Activity Awareness (Deel A) — "ik ga <activiteit>"
    # ---------------------------------------------------------
    # Generiek patroon: werkt voor ONBEPERKT veel activiteiten, geen
    # aparte code nodig per nieuwe activiteit. Publiceert een
    # "activity_started"-event dat Layer 2 (pattern_matcher.py) en
    # later Layer 5/Activity-Aware Interaction gebruiken.
    # 100% symbolisch: puur patroonherkenning + een klein
    # synoniemen-tabelletje, geen ML/generatie.

    # Klein, uitbreidbaar tabelletje: spreektaal-variant -> vaste,
    # genormaliseerde activiteitsnaam. Puur onderhoud van een lijst,
    # geen nieuwe logica. Nieuwe activiteiten die hier niet in staan
    # werken nog steeds -- ze krijgen dan gewoon hun eigen letterlijke
    # naam als sleutel.
    ACTIVITEIT_SYNONIEMEN = {
        "koffiezetten": "koffie",
        "koffie zetten": "koffie",
        "koffie drinken": "koffie",
        "netflixen": "netflix",
        "netflix kijken": "netflix",
        "gamen": "gamen",
        "games spelen": "gamen",
        "coderen": "coderen",
        "programmeren": "coderen",
        "code schrijven": "coderen",
    }

    def detect_activity(self, text):
        t = text.lower().strip().rstrip("?.")

        prefixes = ["ik ga ", "ik ga nu ", "ik begin met ", "ik start met "]
        for p in prefixes:
            if t.startswith(p):
                activiteit = t[len(p):].strip()
                if not activiteit:
                    return False

                # Zelfde patroon als topic_detected:<naam> (zie
                # _emit_topic()): de activiteitsnaam zit IN de
                # event-type-string zelf, niet enkel in de data-dict.
                # Zo kan pattern_matcher.py (Layer 2) dit generiek
                # herkennen via dezelfde prefix-check die het al
                # gebruikt voor topic_detected, zonder aparte logica
                # per event-soort.
                dbg(f"{C_MAGENTA}→ activity_started:{activiteit}{C_RESET}")
                self.event_bus.publish(f"activity_started:{activiteit}", {
                    "naam": activiteit,
                    "tijd": self._huidige_tijd_iso()
                })
                return True

        return False

    def _huidige_tijd_iso(self):
        """Kleine helper zodat detect_activity() niet zelf datetime
        hoeft te importeren bovenaan het bestand -- lokale import,
        enkel gebruikt wanneer een activiteit ook echt herkend wordt."""
        from datetime import datetime
        return datetime.now().isoformat()

    # ---------------------------------------------------------
    # Pending Question — antwoord op Nova's eigen vraag verwerken
    # ---------------------------------------------------------
    # Bewust EEN EIGEN, losstaande woordenlijst hier -- NIET de
    # signal_classifier uit microlearning.py, want die herkent iets
    # anders (frustratie/waardering/interesse/verwarring/focus/kilte,
    # bedoeld om traits.json langzaam bij te sturen), geen bevestiging/
    # ontkenning. Een apart model zou hier overkill zijn: dit is een
    # kleine, gesloten set korte woorden zonder de taalkundige
    # dubbelzinnigheid die een classifier zou rechtvaardigen. 100%
    # symbolisch: woordenlijst-matching, geen ML, geen toon/sentiment-
    # interpretatie (zie interruption_learning_roadmap.md's
    # eerlijkheids-sectie: Nova mag DAT iets bevestigd/geweigerd werd
    # zien, nooit HOE geïrriteerd of enthousiast dat klonk).
    BEVESTIGING_WOORDEN = {
        "ja", "jup", "jep", "yep", "yes", "joa", "jow",
        "oke", "oké", "ok", "okay", "okee", "okeej",
        "zeker", "zeker weten", "zeker wel",
        "tuurlijk", "natuurlijk", "vanzelfsprekend",
        "prima", "goed", "prima hoor", "goed hoor",
        "graag", "graag gedaan", "graag wel",
        "yolo", "toch wel", "waarom niet",
        "kom maar", "ga je gang", "zeg het maar",
        "mag", "mag wel", "is goed", "is oke", "is oké",
    }

    ONTKENNING_WOORDEN = {
        "nee", "neu", "nope", "no", "non",
        "nee hoor", "neu hoor", "liever niet",
        "nu niet", "niet nu", "later", "straks liever",
        "niet nodig", "hoeft niet", "laat maar",
        "niet storen", "wacht liever", "wacht nog even",
        "nog niet", "een andere keer", "niet echt",
    }

    def _interpreteer_ja_nee(self, text):
        """
        Geeft "bevestiging", "ontkenning" of None terug (bij twijfel/
        onherkend) op basis van woordenlijst-matching. Geen ML, geen
        confidence-score -- gewoon een letterlijke match tegen een
        vaste set, zoals hierboven beschreven.
        """
        t = text.lower().strip().rstrip("?.!")

        if t in self.BEVESTIGING_WOORDEN:
            return "bevestiging"
        if t in self.ONTKENNING_WOORDEN:
            return "ontkenning"

        # Ook een korte zin die MET zo'n woord begint accepteren
        # (bv. "ja hoor, ga je gang" -- niet enkel exacte matches),
        # zolang de zin kort blijft. Een lange, inhoudelijke zin die
        # toevallig met "ja" begint ("ja, ik denk dat het weer...")
        # willen we NIET als kort bevestigingsantwoord meepikken --
        # vandaar de lengte-grens.
        if len(t.split()) <= 4:
            for woord in self.BEVESTIGING_WOORDEN:
                if t.startswith(woord):
                    return "bevestiging"
            for woord in self.ONTKENNING_WOORDEN:
                if t.startswith(woord):
                    return "ontkenning"

        return None

    def _verwerk_pending_antwoord(self, text):
        """
        Wordt aangeroepen VOORDAT de normale intent-routing draait,
        enkel als pending_question.is_open() True is. Interpreteert
        het antwoord en publiceert "pending_question:answered" -- de
        module die de vraag stelde (bv. straks de interruption-
        tracker) luistert daarop en weet zelf wat ermee te doen op
        basis van "vraag_type". Dit mechanisme zelf beslist nooit wat
        het antwoord BETEKENT voor de rest van Nova, het levert enkel
        het geïnterpreteerde signaal af.

        Geeft True terug als het bericht als antwoord behandeld is
        (dus de normale routing NIET meer moet draaien), anders False.
        """
        pending = self.event_bus.modules.get("pending_question")
        if pending is None or not pending.is_open():
            return False

        vraag_type = pending.get_type()
        signaal = self._interpreteer_ja_nee(text)

        if signaal is None:
            # Onherkend antwoord -- de vraag blijft open staan (mag
            # nog steeds verlopen via de verval-tijd), Kevin krijgt
            # een kans om het nog eens duidelijker te zeggen. We
            # sturen HIER niets door naar de normale routing, want een
            # onduidelijk antwoord op een net gestelde vraag moet niet
            # als een volledig los, nieuw bericht behandeld worden.
            dbg(f"{C_YELLOW}→ pending_question: onherkend antwoord op '{vraag_type}'{C_RESET}")
            return True

        dbg(f"{C_YELLOW}→ pending_question:answered ({vraag_type} → {signaal}){C_RESET}")
        self.event_bus.publish("pending_question:answered", {
            "vraag_type": vraag_type,
            "signaal": signaal
        })
        pending.clear()
        return True

    # ---------------------------------------------------------
    # Topic events (Layer 2 topic-bewustzijn)
    # ---------------------------------------------------------
    def _emit_topic(self, naam):
        """
        Stuurt een 'topic_detected:<naam>' event de EventBus op.
        Layer 2 (pattern_matcher.py) telt dit generiek mee op uur/dag,
        zodat er per onderwerp (schaken, weer, ...) patronen kunnen
        ontstaan. Geen nieuwe logica hier — enkel doorgeven.
        """
        self.event_bus.publish(f"topic_detected:{naam}", {})

    # ---------------------------------------------------------
    # Fallback
    # ---------------------------------------------------------
    def fallback(self, text):
        dbg(f"{C_RED}→ fallback{C_RESET}")
        self.event_bus.publish("intent_fallback", {"text": text})

    # ---------------------------------------------------------
    # MAIN ROUTER
    # ---------------------------------------------------------
    def route(self, data, event_type=None):
        text = data.get("text", "").strip()
        superscripts = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789-")
        text = text.translate(superscripts)
        text = text.replace("×", "*")
        dbg(f"{C_RESET}Ontvangen: '{text}'")

        # Layer 6, Fase 6 (Adaptive Learning, 17 juli 2026): elk ruw
        # bericht van Kevin publiceren als apart, algemeen event, VOOR
        # de eigenlijke intent-routing begint. Nodig omdat er tot nu
        # toe geen centraal "elk bericht"-event bestond — enkel
        # intent_fallback bevatte de ruwe tekst, en dat mist elk
        # bericht dat WEL een herkende intent triggert (bv. "dank je
        # Nova" zou als greeting/fallback gerouteerd worden, maar
        # microlearning.py moet ALLE berichten kunnen zien om
        # frustratie/waardering/interesse/kilte te herkennen, niet
        # enkel de onherkende). Puur een extra publicatie, verandert
        # niets aan de bestaande routing hieronder.
        if text:
            self.event_bus.publish("raw_user_message", {"text": text})

        # -1 Pending question (nieuw) -- MOET voor ALLES anders
        # gecontroleerd worden, zelfs voor reboot: als Nova net een
        # vraag stelde en Kevin antwoordt "ja", mag dat nooit als een
        # gewoon, los bericht door de rest van de routing lopen.
        if self._verwerk_pending_antwoord(text):
            return

        # 0 Reboot (altijd als allereerste gecontroleerd, voorrang op alles)
        if self.detect_reboot(text):
            return
        
        # 1 Teach
        if self.handle_teach(text):
            return

        # 1B Example
        if self.handle_example(text):
            return

        # 2 Confirm
        if self.handle_confirmation(text):
            return

        # 3 Greeting
        if self.detect_greeting(text):
            self._emit_topic("greeting")
            return

        # 4 Time
        if self.detect_time(text):
            self._emit_topic("time")
            return

        # 5 Weather
        if self.detect_weather(text):
            self._emit_topic("weather")
            return

        # 6 Chess (vóór math, want zetten zoals "e2e4" mogen niet als math gezien worden)
        if self.detect_chess(text):
            self._emit_topic("chess")
            return

        # 6b Help
        if self.detect_help(text):
            self._emit_topic("help")
            return

        # 6c Memory test-commando's
        if self.detect_memory(text):
            self._emit_topic("memory")
            return

        # 6d Identiteitsvragen (Kevin vraagt iets over Nova zelf)
        if self.detect_identity_question(text):
            self._emit_topic("identity")
            return

        # 7 Math
        if self.detect_math(text):
            self._emit_topic("math")
            return

        # 8 Definition
        if self.detect_definition(text):
            # Per-woord-timing: gebruik het specifieke woord als het
            # beschikbaar is (gezet in detect_definition() hierboven),
            # met het oude, generieke "definitie" als veilige terugval
            # -- zo kan dit nooit stil breken als _laatste_definitie_woord
            # om een onverwachte reden leeg zou zijn.
            woord = getattr(self, "_laatste_definitie_woord", None)
            self._emit_topic(f"definitie_{woord}" if woord else "definitie")
            return

        # 9 Relation-flow (eerst! anders pikt relation-check het op)
        if self.semantic and self.semantic._detect_relation(text):
            return

        # 10 Relation-check
        if self.detect_relation_check(text):
            self._emit_topic("relatie")
            return

        # 10b Part-of-check (nieuw, 11 juli 2026)
        if self.detect_part_of_check(text):
            self._emit_topic("part_of")
            return

        # 10c Subtypes-vraag (nieuw, 12 juli 2026)
        if self.detect_subtypes_query(text):
            self._emit_topic("subtypes")
            return

        # 10d Activity Awareness Deel A (nieuw) — "ik ga <activiteit>"
        # Bewust hier, NA alle specifieke intents (weer, schaken, math,
        # definities...) en VOOR de fallback: een zin als "ik ga
        # slapen" mag nooit een specifiekere, al bestaande intent
        # overschrijven, maar moet wel vóór de kale fallback gevangen
        # worden.
        if self.detect_activity(text):
            self._emit_topic("activity")
            return
        
        # Sense-choice (antwoord met nummer)
        if text.isdigit():
            if self.semantic:
                self.semantic.handle_sense_choice(text)
            return

        # Confirm-flow voor semantic. LET OP: als er een pending
        # question open stond, is dit bericht al hierboven (stap -1)
        # afgehandeld en heeft return al plaatsgevonden -- deze regel
        # wordt dus enkel bereikt als er GEEN pending question actief
        # was, bv. een "ja"/"nee" als antwoord op een semantic-vraag
        # ("bedoel je zin A of B?").
        if text in ("ja", "nee"):
            if self.semantic:
                self.semantic.handle_confirm(text)
            return

        # 11 Fallback
        self.fallback(text)

def init_module(event_bus, semantic_module=None):
    router = IntentRouter(event_bus, semantic_module)
    event_bus.publish("module_loaded", {"name": "intent_router"})
    return router