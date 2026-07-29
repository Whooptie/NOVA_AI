# modules/chess/chess_engine.py

import chess
import chess.engine
import json
import random
import threading
import time
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
        self.laatste_zet = None  # Voor highlighting op het bord

        # Stockfish-engine (wordt pas gestart als nodig)
        self.engine = None
        # skill_level en think_time worden geladen via load_settings()
        self.last_move_time = None        # Tijdstip van laatste zet
        self.inactivity_timeout = 1800   # 30 minuten in seconden

        # Inactiviteitscheck starten in achtergrond
        self._start_inactivity_watcher()

        # Instellingen
        self.settings_path = Path(r"C:\Nova_AI\data") / "chess_settings.json"
        self.skill_level, self.think_time = self.load_settings()

        # Statistieken
        self.stats_path = Path(r"C:\Nova_AI\data") / "chess_stats.json"
        self.stats = self.load_stats()
        if "streak" not in self.stats:
            self.stats["streak"] = 0  # positief = jij wint op rij, negatief = jij verliest op rij

        # Bestaande partij terugladen indien aanwezig
        self.load_game()

        # Luisteren naar schaak-events
        event_bus.subscribe("intent_chess_move", self.handle_move)
        event_bus.subscribe("intent_chess_new", self.handle_new_game)
        event_bus.subscribe("intent_chess_board", self.handle_show_board)
        event_bus.subscribe("intent_chess_difficulty", self.handle_difficulty)
        event_bus.subscribe("intent_chess_think_time", self.handle_think_time)
        event_bus.subscribe("intent_chess_stats", self.handle_stats)
        event_bus.subscribe("intent_chess_evaluation_query", self.handle_evaluation_query)

        # Sjablonen voor de meest terugkerende, tot nu toe vaste zinnen
        # (schaak-melding, zet-melding, spelverloop), nu ook opgebouwd
        # als OPENING + MIDDEN + AFSLUITING (zelfde patroon als de
        # zet-evaluatie-sjablonen verderop) i.p.v. volledig vaste
        # zinnen -- meer variatie, nog steeds puur string-combinatie
        # via _bouw_zin(), geen generatie. Echte zet-inhoudelijke
        # commentaar (bv. "sterke opening") zit apart in de
        # evaluatie-sjablonen hieronder.
        self._schaak_melding_opening = [
            "Schaak!", "Schaak gezet,", "Dat is schaak!", "Schaak!", "Schaak gezet --",
        ]
        self._schaak_melding_midden = [
            "Goede zet", "Knap gedaan", "Mooie zet",
            "Dat zag ik niet aankomen", "Goed gespeeld",
        ]
        self._schaak_melding_afsluiting = [
            ".", ".", "!",
        ]

        # zet_melding bestaat inhoudelijk uit twee vaste helften (wat
        # JIJ deed + wat IK doe) -- het middendeel hieronder is daarom
        # zelf al de volledige combinatie van beide placeholders i.p.v.
        # een losse keuze, de variatie zit in opening/afsluiting.
        self._zet_melding_opening = [
            "Jij speelde", "Je zette", "Jij koos", "Na jouw", "Zonet speelde je",
        ]
        self._zet_melding_midden = [
            "{move_text}. Ik speel {nova_zet}",
            "{move_text}, ik antwoord met {nova_zet}",
            "{move_text}, ik doe {nova_zet}",
            "{move_text}, ik kies {nova_zet}",
            "{move_text} -- ik speel {nova_zet}",
        ]
        self._zet_melding_afsluiting = [
            ".", ".",
        ]

        self._winst_opening = [
            "🎉 Jij wint", "🎉 Winst voor jou", "🎉 Jij haalt het",
            "🎉 Overwinning", "🎉 Jij wint deze partij",
        ]
        self._winst_midden = [
            "door {reden}",
        ]
        self._winst_afsluiting = [
            "! Goed gespeeld!", "! Sterk gespeeld!", "! Proficiat!", "! Goed gedaan!",
        ]

        self._verlies_opening = [
            "💀 Ik win", "💀 Deze ga ik winnen", "💀 Ik haal het",
            "💀 Winst voor mij", "💀 Ik trek aan het langste eind",
        ]
        self._verlies_midden = [
            "door {reden}",
        ]
        self._verlies_afsluiting = [
            ". Probeer het opnieuw!", ". Nieuwe kans?",
            ". Volgende keer beter!", ". Nog een partij?", ". Opnieuw proberen?",
        ]

        self._gelijkspel_opening = [
            "🤝 Gelijkspel", "🤝 We eindigen gelijk", "🤝 Remise",
            "🤝 Niemand wint", "🤝 Een gelijkspel",
        ]
        self._gelijkspel_midden = [
            "door {reden}",
        ]
        self._gelijkspel_afsluiting = [
            "!", ".", ", helaas voor ons allebei.",
        ]

        # ------------------------------------------------------------
        # Zet-evaluatie (nieuw) — 100% symbolisch via Stockfish' eigen
        # centipawn-score, GEEN ML/LLM. Stockfish geeft voor/na elke
        # speler-zet een evaluatie terug; het verschil (vanuit jouw
        # perspectief, in centipawns) bepaalt de categorie hieronder.
        # Enkel Stockfish' BESTE-ZET-SUGGESTIE wordt getoond bij
        # twijfelachtig/blunder — WAAROM die zet beter is, wordt
        # bewust niet uitgelegd (vereist stelling-redenering die
        # Stockfish niet teruggeeft; apart, later werkpunt, zie
        # nova_state.md).
        self.EVAL_DREMPEL_UITSTEKEND = 150   # cp verbetering
        self.EVAL_DREMPEL_TWIJFELACHTIG = 50  # cp verlies
        self.EVAL_DREMPEL_BLUNDER = 150       # cp verlies
        self.EVAL_KANS_NEUTRAAL_TOCH_SPREKEN = 0.15  # "soms" bij gewone zet

        # Vaste analysetijd voor de zet-evaluatie, BEWUST los van
        # self.think_time. think_time wordt automatisch door
        # _pas_niveau_aan() opgeschroefd/verlaagd o.b.v. jouw
        # winst/verlies-streak -- dat zegt iets over hoe sterk Nova's
        # EIGEN zet moet zijn, niets over hoe lang de evaluatie van
        # JOUW zet zou moeten duren. Zonder deze aparte waarde zou een
        # hoge think_time (bv. 10s bij skill 20) de evaluatie 2x zo
        # traag maken (voor- en na-analyse), wat de partij onnodig
        # zou vertragen naarmate je beter speelt.
        self.EVAL_ANALYSE_TIJD = 0.3

        # Onthoudt de laatste evaluatie zodat een latere vraag
        # ("waarom was dat een blunder?") ze kan herhalen zonder
        # opnieuw te moeten berekenen.
        self.laatste_zet_evaluatie = None

        # ------------------------------------------------------------
        # Sjablonen als OPENING + MIDDEN + AFSLUITING, zelfde patroon
        # als conversation_engine.py's OPENINGEN/AFSLUITINGEN-aanpak,
        # hier met een extra middendeel voor meer variatie. Nova
        # combineert per categorie willekeurig 1 opening + 1 midden +
        # 1 afsluiting tot een volledige zin -- puur string-combinatie
        # via random.choice(), geen generatie.

        self._eval_uitstekend_opening = [
            "Wow,", "Sterk gespeeld,", "Daar had ik niet van terug --",
            "Chapeau,", "Knap gedaan,",
        ]
        self._eval_uitstekend_midden = [
            "dat was een uitstekende zet", "dat is echt een topzet",
            "dat had ik niet meteen zien aankomen",
            "dat is precies de beste zet hier", "dat was heel scherp gezien",
        ]
        self._eval_uitstekend_afsluiting = [
            "!", ", goed gezien!", ", knap gespeeld!",
        ]

        self._eval_sterk_opening = [
            "Sterke zet --", "Mooi gespeeld,", "Goede keuze,",
            "Prima gedaan,", "Dat is degelijk --",
        ]
        self._eval_sterk_midden = [
            "dat zet me onder druk", "dat had ik niet meteen zien aankomen",
            "dat houdt de stelling gezond", "dat is een verstandige zet",
            "dat brengt je stelling vooruit",
        ]
        self._eval_sterk_afsluiting = [
            ".", ", goed bezig.", ".",
        ]

        self._eval_neutraal_opening = [
            "Oké,", "Prima,", "Nu goed,", "Alright,", "Tja,",
        ]
        self._eval_neutraal_midden = [
            "logische zet", "een rustige, degelijke zet",
            "dat houdt het spel in balans", "een gewone, veilige zet",
            "een redelijke keuze hier",
        ]
        self._eval_neutraal_afsluiting = [
            ".", ".", ".",
        ]

        self._eval_twijfelachtig_opening = [
            "Hmm,", "Kon,", "Tja,", "Nou,", "Eerlijk gezegd,",
        ]
        self._eval_twijfelachtig_midden = [
            "dat had misschien sterker gekund",
            "dat is niet de sterkste keuze hier",
            "er stond volgens mij iets beters klaar",
            "dat is een beetje twijfelachtig",
            "dat had scherper gemogen",
        ]
        self._eval_twijfelachtig_afsluiting = [
            ".", ", denk ik.", ", vind ik.",
        ]

        self._eval_blunder_opening = [
            "Au --", "Oei,", "Dat ging niet goed --", "Pas op --", "Hmm, dat is niet best --",
        ]
        self._eval_blunder_midden = [
            "dat kost je nogal wat", "dat was een blunder",
            "die zet doet best pijn voor je stelling",
            "daar verlies je flink materiaal of stelling mee",
            "dat is een dure vergissing",
        ]
        self._eval_blunder_afsluiting = [
            ", vrees ik.", ", let goed op.", ".",
        ]

        self._eval_mat_dreigt_opening = [
            "Pas op,", "Let op --", "Voorzichtig,", "Kijk uit,", "Opgelet,",
        ]
        self._eval_mat_dreigt_midden = [
            "ik zie een mataanval aankomen als je niet oppast",
            "dat kan uitdraaien op mat binnen enkele zetten",
            "er dreigt hier een matnet",
            "dit kan gevaarlijk aflopen voor je koning",
            "je koning staat hier niet veilig meer",
        ]
        self._eval_mat_dreigt_afsluiting = [
            ".", "!", ".",
        ]

        self._betere_zet_opening = [
            "Sterker was volgens mij", "Ik had zelf", "Overweeg volgende keer",
            "Beter was", "Ik zou eerder gekozen hebben voor",
        ]
        self._betere_zet_midden = [
            "{betere_zet}",
        ]
        self._betere_zet_afsluiting = [
            " geweest.", " overwogen.", ".", ", denk ik.",
        ]

        self._redding_nu_opening = [
            "Als je nu nog wil redden,", "Je kan dit nog pareren met",
            "Overweeg", "Probeer misschien", "Nu kan je nog",
        ]
        self._redding_nu_midden = [
            "{redding_zet}",
        ]
        self._redding_nu_afsluiting = [
            ".", ", denk ik.", " om dit nog recht te trekken.",
        ]

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
        # instant=True: bevat ANSI-kleurcodes + meerdere regels. Het
        # typewriter-effect zou elke escape-code letter voor letter
        # printen — traag én zichtbaar rommelig (rare tekens i.p.v.
        # kleur). Net als bij help.py: in één keer tonen.
        self.event_bus.publish("chat_response", {
            "text": f"Huidige stand:\n\n{self.bord_als_tekst()}",
            "instant": True
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

        # Promotiestuk zoeken (bv. "pion naar e8 dame")
        promotie_stuk = None
        promotie_namen = {
            "dame": chess.QUEEN, "toren": chess.ROOK,
            "loper": chess.BISHOP, "paard": chess.KNIGHT
        }
        for naam, ptype in promotie_namen.items():
            # Het laatste stukwoord in de zin (na "naar veld") is het promotiestuk
            if t.rstrip().endswith(naam):
                promotie_stuk = ptype
                break

        # Zoek in legale zetten
        candidates = []
        for move in self.board.legal_moves:
            if move.to_square != target_square:
                continue
            if piece_type is None or self.board.piece_type_at(move.from_square) == piece_type:
                # Bij promotiezetten: alleen de zet met het juiste promotiestuk nemen
                if move.promotion is not None:
                    gewenst = promotie_stuk if promotie_stuk else chess.QUEEN  # standaard: dame
                    if move.promotion == gewenst:
                        candidates.append(move)
                else:
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
        GRIJS = "\033[37m"
        HIGHLIGHT_BG = "\033[43m"  # Gele achtergrond voor laatste zet

        zetnummer = self.board.fullmove_number
        header = f"{GRIJS}Zet {zetnummer}{RESET}\n"

        gemarkeerde_velden = set()
        if self.laatste_zet:
            gemarkeerde_velden = {self.laatste_zet.from_square, self.laatste_zet.to_square}

        symbolen = {
            (chess.PAWN,   True):  "♙", (chess.PAWN,   False): "♟",
            (chess.KNIGHT, True):  "♘", (chess.KNIGHT, False): "♞",
            (chess.BISHOP, True):  "♗", (chess.BISHOP, False): "♝",
            (chess.ROOK,   True):  "♖", (chess.ROOK,   False): "♜",
            (chess.QUEEN,  True):  "♕", (chess.QUEEN,  False): "♛",
            (chess.KING,   True):  "♔", (chess.KING,   False): "♚",
        }
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
        return header + "\n".join(regels)

    # ----------------------------------------------------
    # Materiaaltelling
    # ----------------------------------------------------
    def materiaal_balans(self):
        waarden = {
            chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
            chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0
        }
        wit_punten = 0
        zwart_punten = 0
        for stuk_type in waarden:
            wit_punten += len(self.board.pieces(stuk_type, chess.WHITE)) * waarden[stuk_type]
            zwart_punten += len(self.board.pieces(stuk_type, chess.BLACK)) * waarden[stuk_type]

        verschil = wit_punten - zwart_punten
        if verschil > 0:
            return f"Jij staat {verschil} punt(en) voor."
        elif verschil < 0:
            return f"Ik sta {abs(verschil)} punt(en) voor."
        else:
            return "Materiaal is gelijk."
        
    # ----------------------------------------------------
    # UCI-zet omzetten naar leesbare tekst (bv. b8c6 → "paard naar c6")
    # ----------------------------------------------------
    def uci_to_leesbaar(self, move, bord=None):
        """
        Zet een Move-object om naar leesbare tekst (bv. "paard naar d5
        (f6d5)"). BELANGRIJK: optioneel `bord`-argument toegevoegd --
        zonder dit gebruikt de methode self.board (huidige stelling),
        zoals voorheen. Dit is nodig omdat de zet-evaluatie soms een
        zet op een ANDERE stelling moet vertalen dan de huidige (bv.
        de betere-zet-suggestie hoort bij de stelling VOOR jouw zet,
        niet bij het bord van nu).

        Werkt zowel voor een zet die op `bord` AL gespeeld is (het
        stuk staat dan op to_square, from_square is leeg -- dit is
        het geval bij Nova's net gespeelde result.move) als voor een
        zet die er NOG NIET op gespeeld is (het stuk staat dan nog op
        from_square -- dit is het geval bij betere_zet_voor/
        redding_zet, die enkel een SUGGESTIE zijn en nooit echt
        gepusht worden op dat bord).
        """
        werkbord = bord if bord is not None else self.board

        stuk_namen = {
            chess.PAWN:   "pion",
            chess.KNIGHT: "paard",
            chess.BISHOP: "loper",
            chess.ROOK:   "toren",
            chess.QUEEN:  "dame",
            chess.KING:   "koning",
        }
        # Eerst from_square proberen (zet nog niet gespeeld), anders
        # to_square (zet al gespeeld op dit bord).
        stuk = werkbord.piece_type_at(move.from_square)
        zet_al_gespeeld = stuk is None
        if zet_al_gespeeld:
            stuk = werkbord.piece_type_at(move.to_square)
        naam = stuk_namen.get(stuk, "stuk")
        veld = chess.square_name(move.to_square)

        # Tussen haakjes altijd de VOLLEDIGE UCI-notatie (bv. "c2c4"),
        # niet de korte SAN ("c4"). SAN is voor een schaakbord correct
        # en gangbaar, maar als los tekstfragment zonder bord erbij
        # (bv. "Beter was pion naar c4 (c4) geweest") oogt het
        # onvolledig/verwarrend -- welke pion, van waar? De volledige
        # UCI (van-veld + naar-veld) is voor Kevin ondubbelzinnig,
        # ook zonder het bord erbij te zien.
        uci_notatie = move.uci()

        # Slagzet expliciet benoemen (nieuw). Zonder dit klinkt een
        # zin als "ik speel paard naar c7" alsof het naar een leeg
        # veld gaat -- terwijl het in werkelijkheid een stuk (soms
        # zelfs precies datzelfde veld waar JIJ net naartoe speelde)
        # wegneemt. Detectie moet gebeuren op het bord VAN VOOR de
        # zet: als de zet al gespeeld is op `werkbord` (zie
        # zet_al_gespeeld hierboven), gebruiken we daarom move_stack
        # om tijdelijk terug te gaan; anders werkt is_capture() al
        # direct correct op het huidige (nog-niet-gespeelde) bord.
        if zet_al_gespeeld and werkbord.move_stack and werkbord.move_stack[-1] == move:
            werkbord.pop()
            is_slagzet = werkbord.is_capture(move)
            werkbord.push(move)
        elif not zet_al_gespeeld:
            is_slagzet = werkbord.is_capture(move)
        else:
            is_slagzet = False  # kan niet betrouwbaar bepaald worden

        werkwoord = "slaat op" if is_slagzet else "naar"

        if move.promotion:
            promotie_naam = stuk_namen.get(move.promotion, "dame")
            return f"pion {werkwoord} {veld}, gepromoveerd tot {promotie_naam} ({uci_notatie})"

        return f"{naam} {werkwoord} {veld} ({uci_notatie})"

    # ----------------------------------------------------
    # Zet-evaluatie -- 100% symbolisch via Stockfish' centipawn-score
    # ----------------------------------------------------
    def _score_naar_cp(self, info_score, speler_kleur):
        """
        Zet een python-chess PovScore om naar een centipawn-getal
        VANUIT HET PERSPECTIEF VAN speler_kleur (jij, meestal WIT).
        Geeft None terug bij een mat-score (die wordt apart
        afgehandeld door _mate_in()).
        """
        pov_score = info_score.pov(speler_kleur)
        if pov_score.is_mate():
            return None
        return pov_score.score()

    def _mate_in(self, info_score, speler_kleur):
        """
        Geeft het aantal zetten tot mat terug (positief = jij zet mat,
        negatief = jij wordt mat gezet), of None als er geen mat
        gezien wordt in deze analyse.
        """
        pov_score = info_score.pov(speler_kleur)
        if pov_score.is_mate():
            return pov_score.mate()
        return None

    # ----------------------------------------------------
    # Bouwt een zin uit opening + midden + afsluiting-lijsten
    # (zelfde variatie-patroon als conversation_engine.py's
    # OPENINGEN/AFSLUITINGEN, hier met een extra middendeel).
    # format_kwargs wordt enkel gebruikt bij midden-lijsten die een
    # placeholder bevatten (bv. {betere_zet}, {redding_zet}).
    # ----------------------------------------------------
    def _bouw_zin(self, opening_lijst, midden_lijst, afsluiting_lijst, **format_kwargs):
        opening = random.choice(opening_lijst)
        midden = random.choice(midden_lijst)
        afsluiting = random.choice(afsluiting_lijst)
        if format_kwargs:
            midden = midden.format(**format_kwargs)
        return f"{opening} {midden}{afsluiting}"

    def evalueer_speler_zet(self, move, speler_kleur):
        """
        Vergelijkt Stockfish' evaluatie van de stelling VOOR en NA
        jouw zet (vanuit jouw perspectief, in centipawns). Geeft een
        dict terug met categorie + kant-en-klare tekst, of None als
        Stockfish niet beschikbaar is (dan wordt er gewoon niets
        gezegd -- geen crash, de zet zelf gaat wel gewoon door).

        BELANGRIJK: dit is analyse VOOR Nova's eigen antwoordzet --
        het bord staat op dit moment nog net na jouw zet, dus we
        moeten de stelling van ERVOOR apart vasthouden (zie
        handle_move() waar dit aangeroepen wordt).
        """
        if not self.ensure_engine():
            return None

        try:
            stelling_voor = self.board.copy()
            stelling_voor.pop()  # jouw zet ongedaan maken voor de "voor"-analyse
        except IndexError:
            return None

        try:
            info_voor = self.engine.analyse(stelling_voor, chess.engine.Limit(time=self.EVAL_ANALYSE_TIJD))
            info_na = self.engine.analyse(self.board, chess.engine.Limit(time=self.EVAL_ANALYSE_TIJD))
        except Exception as e:
            dbg(f"{C_RED}Kon zet niet evalueren: {e}{C_RESET}")
            return None

        beste_zet_voor = info_voor.get("pv", [None])[0]

        mate_na = self._mate_in(info_na["score"], speler_kleur)
        if mate_na is not None and mate_na < 0:
            # Jij wordt binnenkort mat gezet
            categorie = "mat_dreigt"
            tekst = self._bouw_zin(
                self._eval_mat_dreigt_opening,
                self._eval_mat_dreigt_midden,
                self._eval_mat_dreigt_afsluiting,
            )
            return self._bouw_evaluatie(categorie, tekst, beste_zet_voor, stelling_voor)

        cp_voor = self._score_naar_cp(info_voor["score"], speler_kleur)
        cp_na = self._score_naar_cp(info_na["score"], speler_kleur)

        if cp_voor is None or cp_na is None:
            # Eén van beide kanten zag al een mat -- niet vergelijkbaar
            # als gewoon centipawn-verschil, laat dit gewoon stil.
            return None

        verschil = cp_na - cp_voor  # negatief = jij verloor terrein

        if verschil >= 0 or verschil > -self.EVAL_DREMPEL_TWIJFELACHTIG:
            # Zet bleef gelijk of verbeterde: sterk of uitstekend
            if verschil >= self.EVAL_DREMPEL_UITSTEKEND:
                categorie = "uitstekend"
                tekst = self._bouw_zin(
                    self._eval_uitstekend_opening,
                    self._eval_uitstekend_midden,
                    self._eval_uitstekend_afsluiting,
                )
            elif verschil >= 0:
                categorie = "sterk"
                tekst = self._bouw_zin(
                    self._eval_sterk_opening,
                    self._eval_sterk_midden,
                    self._eval_sterk_afsluiting,
                )
            else:
                categorie = "neutraal"
                tekst = self._bouw_zin(
                    self._eval_neutraal_opening,
                    self._eval_neutraal_midden,
                    self._eval_neutraal_afsluiting,
                )
            return self._bouw_evaluatie(categorie, tekst, None, stelling_voor)

        verlies = -verschil
        if verlies >= self.EVAL_DREMPEL_BLUNDER:
            categorie = "blunder"
            tekst = self._bouw_zin(
                self._eval_blunder_opening,
                self._eval_blunder_midden,
                self._eval_blunder_afsluiting,
            )
            return self._bouw_evaluatie(categorie, tekst, beste_zet_voor, stelling_voor)
        else:
            categorie = "twijfelachtig"
            tekst = self._bouw_zin(
                self._eval_twijfelachtig_opening,
                self._eval_twijfelachtig_midden,
                self._eval_twijfelachtig_afsluiting,
            )
            return self._bouw_evaluatie(categorie, tekst, beste_zet_voor, stelling_voor)

    def _bouw_evaluatie(self, categorie, tekst, beste_zet_voor, stelling_voor):
        """
        Voegt, indien van toepassing, Stockfish' beste-zet-suggestie
        toe in leesbare tekst. Geeft nooit een UITLEG waarom die zet
        beter was -- bewust weggelaten, zie toelichting bovenaan dit
        blok.
        """
        volledige_tekst = tekst
        if beste_zet_voor is not None and categorie in ("twijfelachtig", "blunder"):
            try:
                # BELANGRIJK: uci_to_leesbaar() krijgt hier expliciet
                # stelling_voor mee -- dat is het bord VOOR jouw zet,
                # niet self.board (dat staat op dit moment al na jouw
                # zet én zelfs na Nova's tegenzet). Zonder dit
                # argument zou san()/piece_type_at() het verkeerde
                # stuk of een foutieve notatie teruggeven.
                betere_zet_tekst = self.uci_to_leesbaar(beste_zet_voor, bord=stelling_voor)
                aanvulling = self._bouw_zin(
                    self._betere_zet_opening,
                    self._betere_zet_midden,
                    self._betere_zet_afsluiting,
                    betere_zet=betere_zet_tekst,
                )
                volledige_tekst += f" {aanvulling}"
            except Exception:
                pass

        return {
            "categorie": categorie,
            "tekst": volledige_tekst,
        }

    # ----------------------------------------------------
    # Zet verwerken
    # ----------------------------------------------------
    def handle_move(self, data, event_type=None):
        move_text = data.get("move", "").strip()
        move = None

        # Rokade (O-O = kort, O-O-O = lang)
        if move_text in ("O-O", "O-O-O"):
            try:
                move = self.board.parse_san(move_text)
                if move not in self.board.legal_moves:
                    move = None
            except Exception:
                move = None

            if move is None:
                self.event_bus.publish("chat_response", {
                    "text": "Rokade is nu niet mogelijk (koning of toren al bewogen, of velden niet vrij/veilig)."
                })
                return

        # Eerst proberen als UCI-notatie (bv. e2e4)
        if move is None:
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
                if self.board.is_check():
                    self.event_bus.publish("chat_response", {
                        "text": f"Je staat schaak! Die zet lost dat niet op. Je moet je koning redden.\n\n{self.bord_als_tekst()}",
                        "instant": True
                    })
                else:
                    self.event_bus.publish("chat_response", {
                        "text": f"Die zet is niet mogelijk in deze stand. Probeer een andere zet."
                    })
                return

        # Speler zet uitvoeren
        self.board.push(move)
        self.laatste_zet = move
        self.save_game()
        self.last_move_time = time.time()

        # Leesbare vorm van JOUW zet vastleggen, direct na het spelen
        # ervan -- move_text is enkel de rauwe tekst die jij typte
        # (bv. "d5c7", of een natuurlijke-taal-zin), niet noodzakelijk
        # een correcte/consistente beschrijving van wat er gebeurde.
        # Door dit hier via uci_to_leesbaar() te doen (self.board
        # staat nu net na jouw zet, dus zet_al_gespeeld-pad wordt
        # gebruikt) krijgt Nova's melding hieronder altijd een
        # correcte, consistente beschrijving -- inclusief "slaat op"
        # als jouw zet een stuk wegnam.
        move_leesbaar = self.uci_to_leesbaar(move)

        # --------------------------------------------------------
        # Zet-evaluatie (nieuw) -- MOET gebeuren vóór Nova's eigen
        # tegenzet hieronder, want evalueer_speler_zet() vergelijkt
        # de stelling voor/na JOUW zet en gebruikt daarvoor tijdelijk
        # self.board.pop() om terug te gaan naar "voor jouw zet".
        # Dat werkt alleen zolang Nova's zet er nog niet bovenop ligt.
        # Bewust via layer4_response (warme tone-pipeline) i.p.v.
        # rechtstreeks chat_response -- de bordweergave verderop
        # blijft wél apart op chat_response, net als voorheen.
        speler_kleur = not self.board.turn  # de kleur die zonet zette
        evaluatie = self.evalueer_speler_zet(move, speler_kleur)
        if evaluatie is not None:
            self.laatste_zet_evaluatie = evaluatie
            categorie = evaluatie["categorie"]

            # mat_dreigt wordt BEWUST niet hier al gepubliceerd -- die
            # wordt hieronder, na Nova's tegenzet, samengevoegd met de
            # "redding nu"-suggestie tot ÉÉN bericht. Twee losse
            # meldingen ("had moeten"/"kan nu nog") vlak na elkaar zou
            # in een gespannen moment als ruis aanvoelen; kies daarom
            # voor natuurlijkheid boven volledigheid.
            mag_spreken = categorie not in ("neutraal", "mat_dreigt")
            if categorie == "neutraal" and random.random() < self.EVAL_KANS_NEUTRAAL_TOCH_SPREKEN:
                mag_spreken = True

            if mag_spreken:
                self.event_bus.publish("layer4_response", {
                    "text": evaluatie["tekst"]
                })

        if self.board.is_game_over():
            self.announce_game_over()
            return

        # Als jouw zet Nova schaak zet, dat direct melden
        if self.board.is_check():
            self.event_bus.publish("chat_response", {
                "text": self._bouw_zin(
                    self._schaak_melding_opening,
                    self._schaak_melding_midden,
                    self._schaak_melding_afsluiting,
                )
            })

        # Nova's beurt (Stockfish)
        if not self.ensure_engine():
            return

        self.engine.configure({"Skill Level": self.skill_level})
        result = self.engine.play(self.board, chess.engine.Limit(time=self.think_time))
        self.board.push(result.move)
        self.laatste_zet = result.move
        self.save_game()

        nova_zet = self.uci_to_leesbaar(result.move)
        schaak_melding = "\n\n⚠️ Je staat schaak!" if self.board.is_check() else ""
        materiaal = self.materiaal_balans()
        zet_tekst = self._bouw_zin(
            self._zet_melding_opening,
            self._zet_melding_midden,
            self._zet_melding_afsluiting,
            move_text=move_leesbaar, nova_zet=nova_zet,
        )
        self.event_bus.publish("chat_response", {
            "text": f"{zet_tekst}\n\n{self.bord_als_tekst()}\n{materiaal}{schaak_melding}",
            "instant": True
        })

        # --------------------------------------------------------
        # "Redding nu" (nieuw) -- ENKEL bij mat_dreigt, en enkel als
        # de partij nog niet voorbij is. Aparte, DERDE Stockfish-
        # analyse op de stelling NA Nova's tegenzet (dus de stelling
        # waarin jij zo meteen weer aan zet bent). De mat_dreigt-
        # waarschuwing zelf (evaluatie["tekst"]) werd hierboven bewust
        # NIET al gepubliceerd -- ze wordt hier samengevoegd met de
        # redding-suggestie tot ÉÉN natuurlijk bericht, i.p.v. twee
        # losse meldingen na elkaar.
        # Bewust nog steeds 100% symbolisch -- gewoon Stockfish' eigen
        # beste-zet-suggestie op het huidige bord, geen ML/LLM.
        if (
            evaluatie is not None
            and evaluatie["categorie"] == "mat_dreigt"
            and not self.board.is_game_over()
        ):
            try:
                info_redding = self.engine.analyse(
                    self.board, chess.engine.Limit(time=self.EVAL_ANALYSE_TIJD)
                )
                redding_zet = info_redding.get("pv", [None])[0]
                if redding_zet is not None:
                    # Hier GEEN apart bord-argument nodig -- self.board
                    # staat op dit moment al op de juiste stelling
                    # (na Nova's tegenzet, vóór redding_zet gespeeld
                    # is), exact zoals uci_to_leesbaar() standaard
                    # verwacht.
                    redding_zet_tekst = self.uci_to_leesbaar(redding_zet)
                    redding_tekst = self._bouw_zin(
                        self._redding_nu_opening,
                        self._redding_nu_midden,
                        self._redding_nu_afsluiting,
                        redding_zet=redding_zet_tekst,
                    )
                    volledig_bericht = f"{evaluatie['tekst']} {redding_tekst}"
                else:
                    volledig_bericht = evaluatie["tekst"]
                self.event_bus.publish("layer4_response", {
                    "text": volledig_bericht
                })
            except Exception as e:
                dbg(f"{C_RED}Kon redding-nu niet berekenen: {e}{C_RESET}")
                # Nog steeds de kale waarschuwing tonen, beter dan
                # volledig stilzwijgen bij een echte mat-dreiging.
                self.event_bus.publish("layer4_response", {
                    "text": evaluatie["tekst"]
                })

        if self.board.is_game_over():
            self.announce_game_over()

    # ----------------------------------------------------
    # Game-over melding
    # ----------------------------------------------------
    def announce_game_over(self):
        result = self.board.result()

        # Reden van einde bepalen
        if self.board.is_checkmate():
            reden = "schaakmat"
        elif self.board.is_stalemate():
            reden = "patstand"
        elif self.board.is_insufficient_material():
            reden = "onvoldoende materiaal om mat te zetten"
        elif self.board.is_seventyfive_moves():
            reden = "75-zettenregel"
        elif self.board.is_fivefold_repetition():
            reden = "5x dezelfde stelling herhaald"
        else:
            reden = "onbekende reden"

        if result == "1-0":
            self.stats["gewonnen"] += 1
            self.stats["streak"] = max(1, self.stats["streak"] + 1)
            bericht = self._bouw_zin(
                self._winst_opening, self._winst_midden, self._winst_afsluiting,
                reden=reden,
            )
        elif result == "0-1":
            self.stats["verloren"] += 1
            self.stats["streak"] = min(-1, self.stats["streak"] - 1)
            bericht = self._bouw_zin(
                self._verlies_opening, self._verlies_midden, self._verlies_afsluiting,
                reden=reden,
            )
        else:
            self.stats["gelijkspel"] += 1
            self.stats["streak"] = 0
            bericht = self._bouw_zin(
                self._gelijkspel_opening, self._gelijkspel_midden, self._gelijkspel_afsluiting,
                reden=reden,
            )

        aanpassing = self._pas_niveau_aan()
        self.save_stats()

        self.event_bus.publish("chat_response", {
            "text": f"{bericht}\n\n{self.bord_als_tekst()}{aanpassing}",
            "instant": True
        })

    # ----------------------------------------------------
    # Automatisch niveau/denktijd aanpassen o.b.v. streak
    # ----------------------------------------------------
    def _pas_niveau_aan(self):
        streak = self.stats["streak"]

        # Elke 3 overwinningen/verliezen op rij → aanpassing, daarna streak resetten
        if streak >= 3:
            oud_niveau = self.skill_level
            self.skill_level = min(20, self.skill_level + 2)
            self.think_time = min(10.0, round(self.think_time + 0.5, 1))
            self.stats["streak"] = 0
            self.save_settings()
            if self.skill_level != oud_niveau:
                return f"\n\n📈 Je wint vaak — ik verhoog mijn niveau naar {self.skill_level}/20 en denktijd naar {self.think_time}s."
        elif streak <= -3:
            oud_niveau = self.skill_level
            self.skill_level = max(0, self.skill_level - 2)
            self.think_time = max(0.1, round(self.think_time - 0.5, 1))
            self.stats["streak"] = 0
            self.save_settings()
            if self.skill_level != oud_niveau:
                return f"\n\n📉 Ik verlaag mijn niveau naar {self.skill_level}/20 en denktijd naar {self.think_time}s, succes!"

        return ""

    # ----------------------------------------------------
    # Instellingen laden en opslaan
    # ----------------------------------------------------
    def load_settings(self):
        if self.settings_path.exists():
            with open(self.settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("skill_level", 10), data.get("think_time", 1.0)
        return 10, 1.0  # standaardwaarden

    def save_settings(self):
        with open(self.settings_path, "w", encoding="utf-8") as f:
            json.dump({
                "skill_level": self.skill_level,
                "think_time": self.think_time
            }, f, indent=2)

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

    # ----------------------------------------------------
    # Detail op vraag: laatste zet-evaluatie herhalen
    # ----------------------------------------------------
    def handle_evaluation_query(self, data, event_type=None):
        """
        Reageert op een vraag als "waarom was dat een blunder?" of
        "wat had ik beter kunnen doen?". Herhaalt gewoon de laatst
        opgeslagen evaluatie (incl. betere-zet-suggestie indien
        aanwezig) -- verzint GEEN nieuwe uitleg, dat is bewust
        (nog) niet gebouwd, zie toelichting bij evalueer_speler_zet().
        """
        if self.laatste_zet_evaluatie is None:
            self.event_bus.publish("chat_response", {
                "text": "Ik heb nog geen zet-evaluatie klaarstaan -- speel eerst een zet."
            })
            return

        self.event_bus.publish("layer4_response", {
            "text": self.laatste_zet_evaluatie["tekst"]
        })

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
        self.save_settings()
        self.event_bus.publish("chat_response", {
            "text": f"Moeilijkheidsgraad ingesteld op {self.skill_level}/20."
        })

    def handle_think_time(self, data, event_type=None):
        seconden = float(data.get("seconden", 1.0))
        self.think_time = max(0.1, min(10.0, seconden))
        self.save_settings()
        self.event_bus.publish("chat_response", {
            "text": f"Denktijd ingesteld op {self.think_time} seconden per zet."
        })

    # ----------------------------------------------------
    # Inactiviteitswatcher — sluit Stockfish na X seconden stilte
    # ----------------------------------------------------
    def _start_inactivity_watcher(self):
        def watcher():
            while True:
                time.sleep(60)  # Check elke minuut
                if self.engine is None:
                    continue
                if self.last_move_time is None:
                    continue
                inactief = time.time() - self.last_move_time
                if inactief >= self.inactivity_timeout:
                    dbg(f"{C_RED}Stockfish afgesloten na inactiviteit ({int(inactief//60)} min){C_RESET}")
                    self.engine.quit()
                    self.engine = None

        thread = threading.Thread(target=watcher, daemon=True)
        thread.start()

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