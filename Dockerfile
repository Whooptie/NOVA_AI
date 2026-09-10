# ============================================================
# Nova AI — Dockerfile
# ============================================================
# Basis: Python 3.11 (zelfde versie als Kevin's Windows-omgeving,
# om verrassingen door versieverschillen te vermijden).
#
# BELANGRIJK: dit image bevat enkel de Python-omgeving + system-
# dependencies (Stockfish, build-tools voor mediapipe/scikit-learn).
# Nova's eigen code + data komen NIET in dit image te zitten —
# die worden via een volume mount gekoppeld (zie de -v vlag in de
# docker run / Unraid-container-instellingen). Zo hoeft dit image
# nooit herbouwd te worden als je gewoon code wijzigt.
# ============================================================

FROM python:3.11.9-slim

# --- Stockfish (schaak-engine, extern proces, geen pip-package) ---
# apt-get install haalt de Linux-binary op; deze komt automatisch
# in PATH terecht (meestal op /usr/games/stockfish), dus de fallback-
# waarde "stockfish" in chess_engine.py (via STOCKFISH_PATH env var)
# vindt hem vanzelf zonder extra configuratie.
#
# We installeren hier ook build-essential + andere basis-tools,
# omdat sommige Python-packages (mediapipe, scikit-learn) tijdens
# de pip-install C/C++-code compileren als er geen kant-en-klare
# Linux-wheel beschikbaar is voor deze exacte Python-versie.
RUN apt-get update && apt-get install -y --no-install-recommends \
    stockfish \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# --- Werkmap in de container ---
# Dit pad wordt straks gekoppeld aan de nova_ai-share op Unraid
# via een volume mount, dus alles wat hier "staat" is in werkelijkheid
# Kevin's eigen bestanden op de server.
WORKDIR /app

# --- Python-dependencies ---
# We kopiëren ENKEL requirements.txt eerst (nog niet de rest van de
# code) zodat Docker deze installatiestap kan hergebruiken (cachen)
# zolang requirements.txt niet wijzigt -- scheelt tijd bij een
# eventuele herbouw van dit image later.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Poort (indien Nova ooit een webserver/API blootgeeft) ---
# Nog niet gebruikt vandaag, maar alvast voorzien voor een
# toekomstige client-server-opzet (zie client_server_control_roadmap.md).
# EXPOSE 8000

# --- Opstartcommando ---
# main.py verwacht interactieve stdin (chat-invoer). Voor nu draaien
# we dit gewoon door -- Fase 1 van de daemon-opzet. Als dit straks
# een non-interactieve daemon wordt (zonder losse terminal-invoer),
# passen we dit commando aan.
CMD ["python", "main.py"]
