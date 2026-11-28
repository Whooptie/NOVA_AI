# modules/network/brein_stream.py
#
# Live brein-weergave (nova_state.md, punt 79): het kanaal naar de pagina.
#
# WAT DOET DIT?
#   Start een klein webservertje in Nova (alleen Python-standaardbibliotheek, geen extra
#   pakketten). Een browser (laptop, telefoon, tablet, fotolijst met kiosk-browser) opent de
#   pagina en krijgt via een "stream" (Server-Sent Events) live te horen welke module en
#   functie net iets deed. De pagina laat dat als flitsen zien. De metingen komen uit de
#   tracer (core/tracer.py).
#
# WAT STUURT HET UIT?
#   Alleen namen van modules en functies, tijden, aantallen en eventnamen. NOOIT wat Kevin
#   typt en NOOIT de inhoud van een event: de tracer bewaart dat al niet, en hier worden alleen
#   de velden uit PAGINA_VELDEN doorgegeven (een lijst, geen "alles behalve").
#
# TRACER AAN/UIT:
#   Zodra de eerste browser verbindt, zet deze module de tracer aan; als de laatste weggaat,
#   zet hij hem weer uit (tenzij jij hem zelf met "trace aan" aanzette). Kijkt niemand, dan
#   kost dit dus niets.
#
# BEVEILIGING (lees dit voor je poort 8770 openzet):
#   - Het token staat in de .env als NOVA_BREIN_TOKEN (aparte sleutel dan NOVA_CLIENT_TOKEN).
#     Staat er geen token, dan START de server niet (fail closed).
#   - Pagina en stream zijn alleen bruikbaar met ?token=... in de link. Wie de link heeft, ziet
#     welke modules actief zijn en wanneer (maar nooit wat je typt).
#   - Het is gewoon HTTP, niet versleuteld. Gebruik het alleen op je thuisnetwerk of via
#     Tailscale. Zet poort 8770 NOOIT door op je router naar het internet.
#   - Het token wordt nergens in een log geprint. Alleen "brein link" toont de volledige link,
#     op jouw verzoek, in jouw console.
#   - Maximaal MAX_CLIENTS gelijktijdige kijkers; een foute poging wacht even met antwoorden.
#
# PUUR SYMBOLISCH: tellen, namen doorgeven, tijd. Geen ML.

import hmac
import json
import os
import select
import socket
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

try:                                              # zelfde aanpak als client_bridge.py
    from dotenv import load_dotenv
except Exception:                                 # pragma: no cover
    load_dotenv = None

LUISTER_POORT = 8770
TOKEN_NAAM = "NOVA_BREIN_TOKEN"
HOST_NAAM = "NOVA_BREIN_HOST"                     # optioneel: alleen voor de tekst van "brein link"
MAX_CLIENTS = 8
BATCH_SECONDEN = 0.08                             # hoe vaak een kijker een pakketje krijgt
HARTSLAG_SECONDEN = 15                            # een lege regel om de verbinding open te houden
ACHTERGROND_MIN_INTERVAL = 0.25                   # dezelfde achtergrondfunctie hooguit 4x per seconde
WACHTRIJ_MAX = 1500                               # per kijker; bij traagheid vallen oudste records weg
PAGINA_BESTAND = Path(__file__).with_name("brein_pagina.html")

# Exact deze velden gaan naar de pagina (kort, om de stream klein te houden):
#   s soort (h handler, t trace, k0 begin antwoord, k1 einde antwoord)
#   m module   f functie/handler   ev event   d duur ms   e eigen ms
#   k keten (nummer van het antwoord, of None)   tr treffer   w wildcard-luisteraar
PAGINA_VELDEN = ("s", "m", "f", "ev", "d", "e", "k", "tr", "w")


# ----------------------------------------------------------------------
# Losse hulpfuncties (zonder netwerk, makkelijk te testen)
# ----------------------------------------------------------------------

def haal_token():
    """Het token uit .env, of None. Geen token = de server start niet."""
    if load_dotenv is not None:
        try:
            load_dotenv()
        except Exception:
            pass
    token = (os.getenv(TOKEN_NAAM) or "").strip()
    return token or None


def token_klopt(gegeven, verwacht):
    """Vergelijking in constante tijd (zodat niemand het token via tijdsverschillen kan raden)."""
    if not gegeven or not verwacht:
        return False
    try:
        return hmac.compare_digest(str(gegeven).encode("utf-8"), str(verwacht).encode("utf-8"))
    except Exception:
        return False


def _korte_naam(pad):
    naam = str(pad or "?").rsplit(".", 1)[-1]
    return "main" if naam == "__main__" else naam


def wildcard_namen(event_bus):
    """Namen (qualname) van de handlers die op ALLE events luisteren (memory, logger, ...)."""
    namen = set()
    for handler in list(getattr(event_bus, "_subscribers", {}).get("*", [])):
        naam = getattr(handler, "__qualname__", None)
        if naam:
            namen.add(naam)
    return namen


def maak_record_voor_pagina(record, wildcards=()):
    """
    Zet een tracer-record om naar het kleine formaat voor de pagina. Geeft None als het record
    niet getoond hoeft te worden. Neemt ALLEEN velden uit PAGINA_VELDEN over.
    """
    soort = record.get("soort")
    if soort == "keten_start":
        uit = {"s": "k0", "k": record.get("keten")}
    elif soort == "keten_eind":
        uit = {"s": "k1", "k": record.get("keten")}
    elif soort in ("handler", "trace"):
        handler = str(record.get("handler") or "?")
        uit = {
            "s": "h" if soort == "handler" else "t",
            "m": _korte_naam(record.get("module")),
            "f": handler,
            "ev": record.get("event"),
            "d": record.get("duur_ms"),
            "e": record.get("eigen_ms"),
            "k": record.get("keten"),
            "tr": record.get("treffer"),
            "w": soort == "handler" and handler in wildcards,
        }
    else:
        return None
    return {veld: uit[veld] for veld in PAGINA_VELDEN if veld in uit}


def groep_van(instantie):
    """'modules.network.client_bridge' -> 'network'; 'core.memory' -> 'core'; anders 'overig'."""
    pad = str(getattr(type(instantie), "__module__", "") or "")
    delen = pad.split(".")
    if delen[0] == "core":
        return "core"
    if delen[0] == "modules" and len(delen) >= 3:
        return delen[1]
    return "overig"


def bouw_topologie(event_bus):
    """
    Welke modules zijn er en op welke events luistert elke module? Alleen namen.
    {"modules": [{"n": naam, "a": bestandsnaam, "g": groep, "l": [events]}], "wildcard": [namen]}
    """
    modules = dict(getattr(event_bus, "modules", {}) or {})
    op_id = {id(inst): naam for naam, inst in modules.items()}
    alias = {naam: _korte_naam(getattr(type(inst), "__module__", naam)) for naam, inst in modules.items()}
    op_alias = {}
    for naam, a in alias.items():
        op_alias.setdefault(a, naam)

    luistert = {naam: set() for naam in modules}
    for event, handlers in list(getattr(event_bus, "_subscribers", {}).items()):
        for handler in list(handlers):
            eigenaar = getattr(handler, "__self__", None)
            naam = op_id.get(id(eigenaar)) if eigenaar is not None else None
            if naam is None:
                naam = op_alias.get(_korte_naam(getattr(handler, "__module__", None)))
            if naam is not None:
                luistert[naam].add(str(event))

    return {
        "modules": [
            {"n": naam, "a": alias[naam], "g": groep_van(inst), "l": sorted(luistert[naam])}
            for naam, inst in sorted(modules.items())
        ],
        "wildcard": sorted(wildcard_namen(event_bus)),
    }


# ----------------------------------------------------------------------
# De module
# ----------------------------------------------------------------------

class _Kijker:
    """Een verbonden browser: een wachtrij met records en een seintje als er iets bij komt."""

    def __init__(self):
        self.wachtrij = deque(maxlen=WACHTRIJ_MAX)
        self.seintje = threading.Condition()
        self.open = True

    def zet(self, item):
        with self.seintje:
            self.wachtrij.append(item)
            self.seintje.notify()

    def sluit(self):
        with self.seintje:
            self.open = False
            self.seintje.notify_all()

    def haal(self, timeout):
        """Wacht tot er iets is (of timeout), geeft alle wachtende items terug."""
        with self.seintje:
            if not self.wachtrij and self.open:
                self.seintje.wait(timeout)
            items = list(self.wachtrij)
            self.wachtrij.clear()
            return items


class BreinStream:
    def __init__(self, event_bus, poort=LUISTER_POORT, token="__uit_env__", start=True, host="0.0.0.0"):
        self.event_bus = event_bus
        self.poort = poort
        self._host = host
        self._token = haal_token() if token == "__uit_env__" else token
        self._slot = threading.Lock()
        self._kijkers = []
        self._we_zetten_aan = False
        self._laatst = {}                         # (module, functie) -> tijd laatste doorgestuurd
        self._wildcards = set()
        self._server = None
        self._thread = None
        if start:
            self._start()

    # ---------- starten en stoppen ----------
    def _start(self):
        if not self._token:
            print(f"[BREIN] {TOKEN_NAAM} staat niet in .env: de breinpagina staat UIT. "
                  f"Maak een token met: python -c \"import secrets; print(secrets.token_urlsafe(32))\"")
            return
        if getattr(self.event_bus, "tracer", None) is None:
            print("[BREIN] Deze EventBus heeft geen tracer: de breinpagina staat UIT.")
            return
        try:
            self._server = ThreadingHTTPServer((self._host, self.poort), self._maak_handler())
            self._server.daemon_threads = True
            self.poort = self._server.server_address[1]
        except OSError as e:
            print(f"[BREIN] Kon poort {self.poort} niet openen ({e}). De breinpagina staat UIT.")
            self._server = None
            return
        self._thread = threading.Thread(target=self._server.serve_forever, name="brein_stream", daemon=True)
        self._thread.start()
        print(f"[BREIN] Breinpagina actief op poort {self.poort} (link met: brein link).")

    def shutdown(self):
        """Wordt automatisch aangeroepen bij afsluiten en /reboot (zie sluit_modules_netjes_af)."""
        server, self._server = self._server, None
        for kijker in list(self._kijkers):
            kijker.sluit()
        if server is not None:
            try:
                server.shutdown()
                server.server_close()
            except Exception:
                pass
        self._zet_tracer_terug()

    # ---------- tekst voor de debug-commando's ----------
    def status_tekst(self):
        if self._server is None:
            reden = ("geen token in .env" if not self._token else "poort niet beschikbaar of niet gestart")
            return f"Breinpagina: UIT ({reden})."
        tracer = getattr(self.event_bus, "tracer", None)
        return (f"Breinpagina: AAN op poort {self.poort}. Kijkers nu: {len(self._kijkers)}. "
                f"Tracer: {'aan' if tracer is not None and tracer.aan else 'uit'}.")

    def link_tekst(self):
        if self._server is None or not self._token:
            return self.status_tekst()
        host = (os.getenv(HOST_NAAM) or "").strip() or "<adres-van-battleserver>"
        return (f"http://{host}:{self.poort}/?token={self._token}\n"
                f"(Deel deze link met niemand. Alleen thuisnetwerk of Tailscale; poort niet doorzetten naar internet.)")

    # ---------- kijkers aan- en afmelden ----------
    def _meld_aan(self, kijker):
        with self._slot:
            if len(self._kijkers) >= MAX_CLIENTS:
                return False
            self._kijkers.append(kijker)
            eerste = len(self._kijkers) == 1
        self._wildcards = wildcard_namen(self.event_bus)
        if eerste:
            tracer = self.event_bus.tracer
            self._we_zetten_aan = not tracer.aan
            tracer.zet(True)
            tracer.voeg_toe(self._op_record)
        return True

    def _meld_af(self, kijker):
        with self._slot:
            if kijker in self._kijkers:
                self._kijkers.remove(kijker)
            laatste = not self._kijkers
        kijker.sluit()
        if laatste:
            self._zet_tracer_terug()

    def _zet_tracer_terug(self):
        tracer = getattr(self.event_bus, "tracer", None)
        if tracer is None:
            return
        try:
            tracer.verwijder(self._op_record)
        except Exception:
            pass
        if self._we_zetten_aan:
            tracer.zet(False)
            self._we_zetten_aan = False

    # ---------- records van de tracer naar de kijkers ----------
    def _op_record(self, record):
        """Luisteraar van de tracer. Snel en foutbestendig: de tracer mag hier nooit last van hebben."""
        try:
            item = maak_record_voor_pagina(record, self._wildcards)
            if item is None:
                return
            if item["s"] in ("h", "t") and item.get("k") is None:
                nu = time.time()
                sleutel = (item["m"], item["f"])
                if nu - self._laatst.get(sleutel, 0.0) < ACHTERGROND_MIN_INTERVAL:
                    return                        # achtergrond-getter die continu tikt: afremmen
                if len(self._laatst) > 5000:
                    self._laatst.clear()
                self._laatst[sleutel] = nu
            for kijker in list(self._kijkers):
                kijker.zet(item)
        except Exception:
            pass

    # ---------- de webserver ----------
    def _maak_handler(self):
        stream = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            server_version = "NovaBrein"
            sys_version = ""

            def log_message(self, *args):         # nooit loggen: in de URL staat het token
                pass

            def _stuur(self, code, soort, body, extra=None):
                self.send_response(code)
                self.send_header("Content-Type", soort)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                for naam, waarde in (extra or {}).items():
                    self.send_header(naam, waarde)
                self.end_headers()
                self.wfile.write(body)

            def _token_ok(self, query):
                gegeven = (query.get("token") or [""])[0]
                if token_klopt(gegeven, stream._token):
                    return True
                time.sleep(0.5)                   # een foute poging krijgt even geen snel antwoord
                self._stuur(403, "text/plain; charset=utf-8", b"Geen toegang.\n")
                return False

            def do_GET(self):
                try:
                    url = urlparse(self.path)
                    query = parse_qs(url.query)
                    if url.path == "/":
                        try:
                            body = PAGINA_BESTAND.read_bytes()
                        except OSError:
                            self._stuur(500, "text/plain; charset=utf-8", b"Pagina ontbreekt.\n")
                            return
                        self._stuur(200, "text/html; charset=utf-8", body)
                    elif url.path == "/topologie":
                        if self._token_ok(query):
                            body = json.dumps(bouw_topologie(stream.event_bus)).encode("utf-8")
                            self._stuur(200, "application/json; charset=utf-8", body)
                    elif url.path == "/stream":
                        if self._token_ok(query):
                            self._stream()
                    else:
                        self._stuur(404, "text/plain; charset=utf-8", b"Niet gevonden.\n")
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass
                except Exception:
                    try:
                        self._stuur(500, "text/plain; charset=utf-8", b"Fout.\n")
                    except Exception:
                        pass

            def _verbinding_weg(self):
                """True als de browser de verbinding al gesloten heeft (dan is de socket leesbaar met EOF)."""
                try:
                    leesbaar, _, _ = select.select([self.connection], [], [], 0)
                    if leesbaar:
                        return self.connection.recv(1, socket.MSG_PEEK) == b""
                except (OSError, ValueError):
                    return True
                return False

            def _schrijf(self, tekst):
                self.wfile.write(tekst.encode("utf-8"))
                self.wfile.flush()

            def _stream(self):
                kijker = _Kijker()
                if not stream._meld_aan(kijker):
                    self._stuur(503, "text/plain; charset=utf-8", b"Te veel kijkers.\n")
                    return
                self.close_connection = True
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Connection", "close")
                    self.send_header("X-Accel-Buffering", "no")
                    self.end_headers()
                    self._schrijf("retry: 2000\n"
                                  "event: topologie\ndata: "
                                  + json.dumps(bouw_topologie(stream.event_bus)) + "\n\n")
                    laatste_teken = time.time()
                    while kijker.open and stream._server is not None:
                        if self._verbinding_weg():
                            break
                        items = kijker.haal(BATCH_SECONDEN)
                        if items:
                            self._schrijf("event: batch\ndata: " + json.dumps(items) + "\n\n")
                            laatste_teken = time.time()
                            time.sleep(BATCH_SECONDEN)        # bundelen: niet vaker dan ~12 pakketjes/s
                        elif time.time() - laatste_teken > HARTSLAG_SECONDEN:
                            self._schrijf(": hartslag\n\n")
                            laatste_teken = time.time()
                            tracer = stream.event_bus.tracer
                            if stream._we_zetten_aan and not tracer.aan:
                                tracer.zet(True)              # iemand typte "trace uit": weer aan
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                    pass
                finally:
                    stream._meld_af(kijker)

        return Handler


def init_module(event_bus, sem=None):
    return BreinStream(event_bus)