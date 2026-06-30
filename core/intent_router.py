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
            self.event_bus.publish("intent_greeting", {"sender": "user"})
            return True
        return False

    # ---------------------------------------------------------
    # Weather
    # ---------------------------------------------------------
    def detect_weather(self, text):
        triggers = [
            "hoe is het weer",
            "wat is het weer",
            "weerbericht",
            "temperatuur",
            "is het koud",
            "is het warm"
        ]
        if "weer" not in text:
            return False
        if any(t in text for t in triggers):
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
        math_keywords = ["sqrt", "sin", "cos", "tan", "log", "ln", "exp", "abs", "round"]
        if any(k in t for k in math_keywords):
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

        # 1 Teach
        if self.handle_teach(text):
            return

        # 2 Confirm
        if self.handle_confirmation(text):
            return

        # 3 Greeting
        if self.detect_greeting(text):
            return

        # 4 Time
        if self.detect_time(text):
            return

        # 5 Weather
        if self.detect_weather(text):
            return

        # 6 Chess (vóór math, want zetten zoals "e2e4" mogen niet als math gezien worden)
        if self.detect_chess(text):
            return

        # 6b Help
        if self.detect_help(text):
            return

        # 7 Math
        if self.detect_math(text):
            return

        # 8 Definition
        if self.detect_definition(text):
            return

        # 9 Relation-flow (eerst! anders pikt relation-check het op)
        if self.semantic and self.semantic._detect_relation(text):
            return

        # 10 Relation-check
        if self.detect_relation_check(text):
            return

        # Sense-choice (antwoord met nummer)
        if text.isdigit():
            if self.semantic:
                self.semantic.handle_sense_choice(text)
            return

        # Confirm-flow voor semantic
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