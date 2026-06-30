# modules/chess/chess_engine.py

import chess
import chess.engine
import json
from pathlib import Path

C_RESET = "\033[0m"
C_GREEN = "\033[92m"
C_CYAN = "\033[96m"
C_RED = "\033[91m"

def dbg(label, text=""):
    print(f"{C_CYAN}[CHESS]{C_RESET} {label} {text}")

# Nederlandse stuksnamen → schaaktype
STUK_NAMEN = {
    "pion":   chess.PAWN,
    "paard":  chess.KNIGHT,
    "loper":  chess.BISHOP,
    "toren":  chess.ROOK,
    "dame":   chess.QUEEN,
    "koning": chess.KING,
}

class ChessModule:
    def __init__(self, event_bus):
        self.event_bus = event_bus

        # Pad naar Stockfish
        self.stockfish_path = r"C:\Nova_AI\engines\stockfish\stockfish-windows-x86-64-avx2.exe"

        # Pad waar we de partijstand opslaan
        self.save_path = Path(r"C:\Nova_AI\data") / "chess_game.json"
        self.save_path.parent.mkdir(parents=True, exist_ok=True)

        # Het schaakbord (begint leeg = startpositie)
        self.board = chess.Board()

        # Stockfish-engine (wordt pas gestart als nodig)
        self.engine = None
        self.skill_level = 10  # 0 = makkelijkst, 20 = sterkst
        self.think_time = 1.0  # seconden per zet

        # Statistieken
        self.stats_path = Path(r"C:\Nova_AI\data") / "chess_stats.json"
        self.stats = self.load_stats()

        # Bestaande partij terugladen indien aanwezig
        self.load_game()

        # Luisteren naar schaak-events
        event_bus.subscribe("intent_chess_move", self.handle_move)
        event_bus.subscribe("intent_chess_new", self.handle_new_game)
        event_bus.subscribe("intent_chess_board", self.handle_show_board)
        event_bus.subscribe("intent_chess_difficulty", self.handle_difficulty)
        event_bus.subscribe("intent_chess_think_time", self.handle_think_time)
        event_bus.subscribe("intent_chess_stats", self.handle_stats)

        dbg(f"{C_GREEN}ChessModule geladen{C_RESET}")

    # ----------------------------------------------------
    # Stockfish starten (lazy — pas als het echt nodig is)
    # ----------------------------------------------------
    def ensure_engine(self):
        if self.engine is None:
            try:
                self.engine = chess.engine.SimpleEngine.popen_uci(self.stockfish_path)
                dbg(f"{C_GREEN}Stockfish gestart{C_RESET}")
            except Exception as e:
                dbg(f"{C_RED}Kon Stockfish niet starten: {e}{C_RESET}")
                self.event_bus.publish("chat_response", {
                    "text": "Ik kan Stockfish niet vinden. Controleer het pad in chess_engine.py."
                })
                return False
        return True

    # ----------------------------------------------------
    # Partij opslaan naar schijf
    # ----------------------------------------------------
    def save_game(self):
        data = {
            "fen": self.board.fen(),
            "moves": [m.uci() for m in self.board.move_stack]
        }
        with open(self.save_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    # ----------------------------------------------------
    # Partij terugladen van schijf
    # ----------------------------------------------------
    def load_game(self):
        if not self.save_path.exists():
            dbg("Geen opgeslagen partij gevonden, nieuw bord.")
            return

        try:
            with open(self.save_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.board = chess.Board(data["fen"])
            dbg(f"{C_GREEN}Partij teruggeladen ({len(data['moves'])} zetten){C_RESET}")
        except Exception as e:
            dbg(f"{C_RED}Kon partij niet laden: {e}{C_RESET}")

    # ----------------------------------------------------
    # Nieuwe partij starten
    # ----------------------------------------------------
    def handle_new_game(self, data, event_type=None):
        self.board = chess.Board()
        self.save_game()
        self.event_bus.publish("chat_response", {
            "text": "Nieuwe partij gestart. Jij speelt wit, ik speel zwart. Doe je eerste zet!"
        })

    # ----------------------------------------------------
    # Bord tonen (simpele tekstweergave)
    # ----------------------------------------------------
    def handle_show_board(self, data, event_type=None):
        self.event_bus.publish("chat_response", {
            "text": f"Huidige stand:\n\n{self.bord_als_tekst()}"
        })

    # ----------------------------------------------------
    # Natuurlijke taal vertalen naar zet
    # ----------------------------------------------------
    def parse_natural_move(self, text):
        import re
        t = text.lower()

        # Veld zoeken (bv. e4, f3, d7)
        veld_match = re.search(r'[a-h][1-8]', t)
        if not veld_match:
            return None

        target_square = chess.parse_square(veld_match.group())

        # Stuk zoeken
        piece_type = None
        for naam, ptype in STUK_NAMEN.items():
            if naam in t:
                piece_type = ptype
                break

        # Zoek in legale zetten
        candidates = []
        for move in self.board.legal_moves:
            if move.to_square != target_square:
                continue
            if piece_type is None or self.board.piece_type_at(move.from_square) == piece_type:
                candidates.append(move)

        if len(candidates) == 1:
            return candidates[0]  # Gevonden!
        elif len(candidates) > 1:
            return candidates     # Meerdere mogelijkheden
        return None               # Niets gevonden

    # ----------------------------------------------------
    # Bord weergeven met schaaksymbolen
    # ----------------------------------------------------
    def bord_als_tekst(self):
        WIT  = "\033[97m"  # Fel wit
        ZWART = "\033[95m" # Huidig voor zwarte stukken
        RESET = "\033[0m"

        symbolen = {
            (chess.PAWN,   True):  "♙", (chess.PAWN,   False): "♟",
            (chess.KNIGHT, True):  "♘", (chess.KNIGHT, False): "♞",
            (chess.BISHOP, True):  "♗", (chess.BISHOP, False): "♝",
            (chess.ROOK,   True):  "♖", (chess.ROOK,   False): "♜",
            (chess.QUEEN,  True):  "♕", (chess.QUEEN,  False): "♛",
            (chess.KING,   True):  "♔", (chess.KING,   False): "♚",
        }
        GRIJS = "\033[37m"
        regels = [f"{GRIJS}  a b c d e f g h{RESET}"]
        for rij in range(7, -1, -1):
            regel = f"{GRIJS}{rij + 1} {RESET}"
            for kolom in range(8):
                veld = chess.square(kolom, rij)
                stuk = self.board.piece_at(veld)
                if stuk:
                    sym = symbolen.get((stuk.piece_type, stuk.color), "?")
                    kleur = WIT if stuk.color == chess.WHITE else ZWART
                    regel += kleur + sym + RESET + " "
                else:
                    regel += ". "
            regels.append(regel)
        return "\n".join(regels)

    # ----------------------------------------------------
    # UCI-zet omzetten naar leesbare tekst (bv. b8c6 → "paard naar c6")
    # ----------------------------------------------------
    def uci_to_leesbaar(self, move):
        stuk_namen = {
            chess.PAWN:   "pion",
            chess.KNIGHT: "paard",
            chess.BISHOP: "loper",
            chess.ROOK:   "toren",
            chess.QUEEN:  "dame",
            chess.KING:   "koning",
        }
        stuk = self.board.piece_type_at(move.to_square)
        naam = stuk_namen.get(stuk, "stuk")
        veld = chess.square_name(move.to_square)
        return f"{naam} naar {veld}"

    # ----------------------------------------------------
    # Zet verwerken
    # ----------------------------------------------------
    def handle_move(self, data, event_type=None):
        move_text = data.get("move", "").strip()
        move = None

        # Eerst proberen als UCI-notatie (bv. e2e4)
        try:
            move = chess.Move.from_uci(move_text)
            if move not in self.board.legal_moves:
                move = None  # UCI herkend maar niet geldig in deze stand
        except Exception:
            move = None

        # Als UCI niet lukte, probeer natuurlijke taal (bv. "paard naar f3")
        if move is None:
            result = self.parse_natural_move(move_text)
            if isinstance(result, list):
                # Meerdere stukken kunnen naar dat veld
                opties = ", ".join(m.uci() for m in result)
                self.event_bus.publish("chat_response", {
                    "text": f"Meerdere stukken kunnen daar naartoe. Bedoel je: {opties}?"
                })
                return
            elif result is not None:
                move = result
            else:
                self.event_bus.publish("chat_response", {
                    "text": f"Die zet is niet mogelijk in deze stand. Probeer een andere zet."
                })
                return

        # Speler zet uitvoeren
        self.board.push(move)
        self.save_game()

        if self.board.is_game_over():
            self.announce_game_over()
            return

        # Nova's beurt (Stockfish)
        if not self.ensure_engine():
            return

        self.engine.configure({"Skill Level": self.skill_level})
        result = self.engine.play(self.board, chess.engine.Limit(time=self.think_time))
        self.board.push(result.move)
        self.save_game()

        nova_zet = self.uci_to_leesbaar(result.move)
        self.event_bus.publish("chat_response", {
            "text": f"Jij speelde {move_text}. Ik speel {nova_zet}.\n\n{self.bord_als_tekst()}"
        })

        if self.board.is_game_over():
            self.announce_game_over()

    # ----------------------------------------------------
    # Game-over melding
    # ----------------------------------------------------
    def announce_game_over(self):
        result = self.board.result()
        if result == "1-0":
            self.stats["gewonnen"] += 1
            bericht = "🎉 Jij wint! Goed gespeeld!"
        elif result == "0-1":
            self.stats["verloren"] += 1
            bericht = "💀 Ik win deze keer. Probeer het opnieuw!"
        else:
            self.stats["gelijkspel"] += 1
            bericht = "🤝 Gelijkspel!"
        self.save_stats()
        self.event_bus.publish("chat_response", {
            "text": f"{bericht} (Resultaat: {result})"
        })

    # ----------------------------------------------------
    # Statistieken laden en opslaan
    # ----------------------------------------------------
    def load_stats(self):
        if self.stats_path.exists():
            with open(self.stats_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"gewonnen": 0, "verloren": 0, "gelijkspel": 0}

    def save_stats(self):
        with open(self.stats_path, "w", encoding="utf-8") as f:
            json.dump(self.stats, f, indent=2)

    def handle_stats(self, data, event_type=None):
        s = self.stats
        totaal = s["gewonnen"] + s["verloren"] + s["gelijkspel"]
        self.event_bus.publish("chat_response", {
            "text": f"Jouw statistieken:\n✅ Gewonnen: {s['gewonnen']}\n❌ Verloren: {s['verloren']}\n🤝 Gelijkspel: {s['gelijkspel']}\n📊 Totaal: {totaal} partijen"
        })

    # ----------------------------------------------------
    # Moeilijkheidsgraad instellen
    # ----------------------------------------------------
    def handle_difficulty(self, data, event_type=None):
        niveau = data.get("niveau", 10)
        self.skill_level = max(0, min(20, int(niveau)))
        self.event_bus.publish("chat_response", {
            "text": f"Moeilijkheidsgraad ingesteld op {self.skill_level}/20."
        })

    def handle_think_time(self, data, event_type=None):
        seconden = float(data.get("seconden", 1.0))
        self.think_time = max(0.1, min(10.0, seconden))
        self.event_bus.publish("chat_response", {
            "text": f"Denktijd ingesteld op {self.think_time} seconden per zet."
        })

    # ----------------------------------------------------
    # Netjes afsluiten
    # ----------------------------------------------------
    def shutdown(self):
        if self.engine:
            self.engine.quit()


def init_module(event_bus, semantic_module=None):
    instance = ChessModule(event_bus)
    event_bus.publish("module_loaded", {"name": "chess"})
    return instance