import chess
import chess.engine

# PAS DIT PAD AAN naar jouw exacte bestandsnaam!
STOCKFISH_PATH = r"C:\Nova_AI\engines\stockfish\stockfish-windows-x86-64-avx2.exe"

# Stockfish opstarten
engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)

# Een leeg bord (startpositie)
board = chess.Board()

print("Startpositie:")
print(board)
print()

# Stockfish laten denken over de beste zet (1 seconde)
result = engine.play(board, chess.engine.Limit(time=1.0))

print(f"Stockfish speelt: {result.move}")

# Netjes afsluiten
engine.quit()