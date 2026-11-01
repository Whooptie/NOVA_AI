# modules/knowledge/datum_terugblik.py
#
# Proactieve datum-terugkoppeling (nova_state.md, idee 8).
#
# Nova kijkt ongevraagd naar wat Kevin 1, 3, 6, 12 en 24 maanden geleden
# (rond dezelfde kalenderdatum) schreef, en meldt het als dat OPVALLEND
# overeenkomt met waar het de laatste dagen over gaat:
#
#   "Een maand geleden (rond 1 oktober) hadden we het ook over 'fietsband'
#    en 'reparatie'. Dat komt deze dagen weer voorbij."
#
# 12 maanden = "vorig jaar op deze datum". Dat levert pas iets op zodra er
# meer dan een jaar aan gesprekken is; tot dan blijft die afstand stil
# (geen fout, er is gewoon nog niets om mee te vergelijken).
#
# 100% SYMBOLISCH. Geen ML, geen embeddings, geen LLM:
#   - woorden tellen, stam nemen (zelfde stam-regel als case_herinnering.py),
#   - "opvallend" = een woord dat op hooguit MAX_DAGFREQ van alle dagen met
#     berichten voorkomt (dus niet "weer", "koffie" of andere vaste woorden),
#   - een terugblik vraagt minstens 2 gedeelde opvallende woorden (of 1 heel
#     zeldzaam woord), zowel toen als de laatste RECENT_DAGEN dagen.
# Nova weet daardoor wel DAT iets toen speelde, nooit WAAROM. De zin is een
# sjabloon.
#
# HOE HET DRAAIT (geen wijziging nodig aan main.py of module_loader.py):
#   - Wordt automatisch gevonden door module_loader.py (modules/knowledge/,
#     standaard init_module(event_bus, sem)).
#   - Heeft een EIGEN achtergrondthread (daemon): 5 minuten na opstarten de
#     eerste check, daarna elke 30 minuten. De zware analyse (database
#     doorzoeken) gebeurt hooguit 1x per dag (of na 3 uur opnieuw als er
#     nog niets gevonden was).
#   - shutdown() stopt de thread; reboot_manager.py roept dat vanzelf aan.
#
# SPAMREGELS (allemaal strenger te zetten via de constanten hieronder):
#   - hoogstens 1 melding per dag;
#   - alleen tussen SPREEK_VANAF_UUR en SPREEK_TOT_UUR;
#   - hetzelfde woord komt pas na HERHALING_DAGEN dagen opnieuw in een melding;
#   - Layer 5 (context_manager.can_interrupt(), dus ook "kan Kevin het zien"
#     en afwezigheid) moet "ja" zeggen. Ontbreekt context_manager, dan
#     zwijgt Nova. Dit is bewust het omgekeerde van sommige andere modules:
#     deze feature is een extraatje, nooit een reden om te storen.
#
# MODUS (omgevingsvariabele DATUM_TERUGBLIK_MODUS in je .env):
#   aan    (standaard) spreekt echt
#   droog  rekent alles uit en print wat Nova ZOU zeggen, maar zegt niets
#   uit    doet niets
#
# TESTEN ZONDER NOVA TE STOREN: scripts/terugblik_status.py leest
# data/interactions.db (alleen lezen) en toont per afstand wat er gevonden
# wordt en waarom iets wel/niet meetelt.

import contextlib
import glob
import gzip
import json
import math
import os
import random
import re
import sqlite3
import threading
from collections import Counter
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("Europe/Brussels")
except Exception:  # geen tzdata (bv. kale Windows): lokale tijd gebruiken
    _TZ = None

# Stam- en stopwoordenlogica hergebruiken van case_herinnering.py, zodat
# "vergelijkbaar" in heel Nova hetzelfde betekent. Zonder die module (bv. in
# een losse test) vallen we terug op een eenvoudige eigen versie.
try:
    from modules.knowledge.case_herinnering import (
        _stam as _basis_stam,
        _EXTRA_FUNCTIEWOORDEN as _FUNCTIEWOORDEN,
        _NEGATIES as _NEGATIE_WOORDEN,
    )
except Exception:  # pragma: no cover
    _basis_stam = None
    _FUNCTIEWOORDEN = frozenset()
    _NEGATIE_WOORDEN = frozenset({"niet", "geen", "nooit", "niets", "niks"})

try:
    from core.nl_stopwoorden import STOPWOORDEN as _GEDEELDE_STOPWOORDEN
except Exception:  # pragma: no cover
    _GEDEELDE_STOPWOORDEN = frozenset()


# ---------------------------------------------------------------
# INSTELLINGEN. Strenger = hogere drempel, kleinere kans op een melding.
# ---------------------------------------------------------------
AFSTANDEN_MAANDEN = (1, 3, 6, 12, 24)  # 12 = "vorig jaar", 24 = "twee jaar geleden"
VENSTER_DAGEN = 3          # kijk +/- 3 dagen rond de doeldatum
RECENT_DAGEN = 7           # "de laatste dagen" = de laatste 7 dagen, vandaag inbegrepen

MIN_ACTIEVE_DAGEN = 14     # minstens zoveel dagen met berichten, anders te weinig basis
MIN_BERICHTEN_VENSTER = 3  # minstens zoveel berichten in het venster van toen
MIN_BERICHTEN_RECENT = 3   # en in de laatste dagen

MAX_DAGFREQ = 0.20         # opvallend = op hooguit 20% van alle dagen gebruikt
MIN_WOORDLENGTE = 4
MIN_GEDEELDE_WOORDEN = 2   # zoveel opvallende woorden moeten toen EN nu voorkomen ...
MIN_SCORE = 4.0            # ... met minstens deze totaalscore (som van ln(1/dagfrequentie))
EEN_WOORD_MIN_SCORE = 4.5  # of 1 uitzonderlijk zeldzaam woord (ook minstens 5 letters)
MAX_WOORDEN_IN_ZIN = 3
MIN_DAGEN_TOEN = 2         # een gedeeld woord moet toen op minstens zoveel VERSCHILLENDE dagen
                           # voorkomen (1 = ook een woord van 1 enkele dag telt; sluit testsessies uit)

SPREEK_VANAF_UUR = 9
SPREEK_TOT_UUR = 21
HERHALING_DAGEN = 30

CHECK_INTERVAL_SEC = 30 * 60
START_VERTRAGING_SEC = 5 * 60
HERBEREKEN_NA_SEC = 3 * 3600

LOOKBACK_DAGEN = 800       # hoe ver terug we berichten inlezen (24 maanden + marge)
MAX_RIJEN = 300000

TOON_VOORBEELD = True      # voeg 1 korte eigen zin van toen toe ("Toen schreef je bijvoorbeeld: ...")
VOORBEELD_MAX_TEKENS = 110

# Woorden die nooit als onderwerp tellen.
# Woorden waarmee je Nova AANSPREEKT of iets laat uitrekenen: geen onderwerp uit je leven.
# Vul gerust aan als je zulke woorden in de status ziet verschijnen.
NEGEER_WOORDEN = frozenset({
    "nova", "kevin",
    "weet", "weten", "wist", "kennen", "ken", "kent",
    "bereken", "berekenen", "berekend", "berekening", "reken", "rekenen", "uitrekenen",
    "vertel", "vertellen", "zeg", "zeggen", "laat", "toon", "toont", "geef", "geven",
    "kun", "kunt", "kan", "kunnen", "wil", "willen", "mag", "moet", "moeten",
    "hoeveel", "welke", "waarom", "wanneer", "bijvoorbeeld", "ongeveer", "eigenlijk",
    "test", "testen", "getest", "debug", "commando",
})

_MAANDEN = ["januari", "februari", "maart", "april", "mei", "juni", "juli",
            "augustus", "september", "oktober", "november", "december"]

_WANNEER = {
    1: "een maand geleden",
    3: "drie maanden geleden",
    6: "een half jaar geleden",
    12: "een jaar geleden",
    24: "twee jaar geleden",
}

_SJABLONEN = [
    "{Wanneer} (rond {datum}) hadden we het ook over {woorden}. Dat komt deze dagen weer voorbij.",
    "Dat doet me ergens aan denken: {wanneer}, rond {datum}, ging het ook over {woorden}, net als de laatste dagen.",
    "Net als de laatste dagen ging het {wanneer} (rond {datum}) over {woorden}.",
    "Grappig: rond {datum}, {wanneer}, kwamen {woorden} ook al voorbij. Nu opnieuw.",
]


# ---------------------------------------------------------------
# Tijd en datums
# ---------------------------------------------------------------
def _nu():
    return datetime.now(_TZ) if _TZ else datetime.now()


def _naar_dt(ts):
    return datetime.fromtimestamp(ts, _TZ) if _TZ else datetime.fromtimestamp(ts)


def _dagen_in_maand(jaar, maand):
    if maand == 12:
        return 31
    return (date(jaar, maand + 1, 1) - date(jaar, maand, 1)).days


def maanden_terug(d, n):
    """De datum n maanden voor d. 31 maart min 1 maand = 28/29 februari (nooit een fout)."""
    totaal = d.year * 12 + (d.month - 1) - n
    jaar, maand0 = divmod(totaal, 12)
    maand = maand0 + 1
    return date(jaar, maand, min(d.day, _dagen_in_maand(jaar, maand)))


def _wanneer_label(n):
    return _WANNEER.get(n, f"{n} maanden geleden")


# ---------------------------------------------------------------
# Woorden
# ---------------------------------------------------------------
@lru_cache(maxsize=50000)
def _stam(token):
    if _basis_stam is not None:
        try:
            return _basis_stam(token)
        except Exception:
            pass
    return token


_CODE_PATROON = re.compile(
    r"[_=<>{}\[\]\\]"            # underscore, =, <, >, accolades, haakjes, backslash
    r"|\w\s*\([^)]*\d"           # functie-aanroep met cijfers: snelheid_na(0, 9.81, 3)
    r"|\d\s*[-+*/^]\s*\d"        # som: 12 * 3
    r"|https?://|\.py\b|\.json\b"  # links en bestandsnamen
)


def lijkt_op_code(tekst):
    """True voor regels die code, een rekenoefening, een link of een bestandsnaam bevatten.
    Die zijn test- of ontwikkelwerk en geen gesprek, dus ze tellen niet mee."""
    return bool(_CODE_PATROON.search(tekst or ""))


def woord_stammen(tekst):
    """
    Geeft {stam: leesbaar woord} van de inhoudswoorden van een bericht.
    Cijfers, korte woorden, stopwoorden, ontkenningen en NEGEER_WOORDEN vallen weg.
    """
    uit = {}
    for token in re.findall(r"[a-zà-ÿ]+", (tekst or "").lower()):
        if len(token) < MIN_WOORDLENGTE:
            continue
        if token in NEGEER_WOORDEN or token in _NEGATIE_WOORDEN:
            continue
        if token in _FUNCTIEWOORDEN or token in _GEDEELDE_STOPWOORDEN:
            continue
        stam = _stam(token)
        if len(stam) < 3:
            continue
        uit.setdefault(stam, token)
    return uit


def _woordenlijst(woorden):
    q = [f"'{w}'" for w in woorden]
    if len(q) <= 1:
        return "".join(q)
    return ", ".join(q[:-1]) + " en " + q[-1]


# ---------------------------------------------------------------
# De analyse (puur: rijen erin, resultaat eruit, geen database nodig)
# ---------------------------------------------------------------
def vind_terugblik(rijen, nu_datum, afstanden=AFSTANDEN_MAANDEN):
    """
    rijen: iterable van (timestamp, tekst) van Kevins berichten.
    Geeft een dict:
      {"actieve_dagen": int, "reden": str|None,
       "kandidaten": [ {afstand_maanden, doel, woorden, stammen, score, voorbeeld} ... ] (beste eerst),
       "afgewezen": [ (afstand_maanden, reden) ... ]}
    """
    dagindex = {}
    for ts, tekst in rijen:
        if lijkt_op_code(tekst):
            continue
        stammen = woord_stammen(tekst)
        if not stammen:
            continue
        dagindex.setdefault(_naar_dt(ts).date(), []).append((ts, tekst, stammen))

    analyse = {"actieve_dagen": len(dagindex), "reden": None, "kandidaten": [], "afgewezen": []}
    n_dagen = len(dagindex)
    if n_dagen < MIN_ACTIEVE_DAGEN:
        analyse["reden"] = (f"te weinig dagen met berichten ({n_dagen}, minimum {MIN_ACTIEVE_DAGEN})")
        return analyse

    dagteller = Counter()
    for lijst in dagindex.values():
        van_die_dag = set()
        for _, _, stammen in lijst:
            van_die_dag.update(stammen)
        dagteller.update(van_die_dag)

    recent_start = nu_datum - timedelta(days=RECENT_DAGEN - 1)
    recent = [m for d, lijst in dagindex.items() if recent_start <= d <= nu_datum for m in lijst]
    if len(recent) < MIN_BERICHTEN_RECENT:
        analyse["reden"] = f"te weinig recente berichten ({len(recent)}, minimum {MIN_BERICHTEN_RECENT})"
        return analyse
    recent_stammen = set()
    for _, _, stammen in recent:
        recent_stammen.update(stammen)

    for n in afstanden:
        doel = maanden_terug(nu_datum, n)
        van = doel - timedelta(days=VENSTER_DAGEN)
        tot = doel + timedelta(days=VENSTER_DAGEN)
        toen = [m for d, lijst in dagindex.items() if van <= d <= tot for m in lijst]
        if len(toen) < MIN_BERICHTEN_VENSTER:
            analyse["afgewezen"].append((n, f"te weinig berichten rond {doel.day} {_MAANDEN[doel.month - 1]} ({len(toen)})"))
            continue

        toen_woorden = {}
        toen_dagen = {}
        for d, lijst in dagindex.items():
            if not (van <= d <= tot):
                continue
            for _, _, stammen in lijst:
                for stam, token in stammen.items():
                    toen_woorden.setdefault(stam, token)
                    toen_dagen.setdefault(stam, set()).add(d)

        gedeeld = []
        for stam in toen_woorden:
            if stam in recent_stammen and len(toen_dagen[stam]) >= MIN_DAGEN_TOEN:
                freq = dagteller[stam] / n_dagen
                if freq <= MAX_DAGFREQ:
                    gedeeld.append((math.log(1.0 / max(freq, 1e-6)), stam))
        gedeeld.sort(reverse=True)
        score = sum(w for w, _ in gedeeld)

        enkel_sterk = (len(gedeeld) == 1 and score >= EEN_WOORD_MIN_SCORE
                       and len(toen_woorden[gedeeld[0][1]]) >= 5)
        meerdere_sterk = len(gedeeld) >= MIN_GEDEELDE_WOORDEN and score >= MIN_SCORE
        if not (enkel_sterk or meerdere_sterk):
            analyse["afgewezen"].append((n, f"{len(gedeeld)} gedeeld opvallend woord(en), score {score:.1f} (te laag)"))
            continue

        top = [s for _, s in gedeeld[:MAX_WOORDEN_IN_ZIN]]
        beste_bericht = max(toen, key=lambda m: (sum(1 for s in top if s in m[2]), -m[0]))
        analyse["kandidaten"].append({
            "afstand_maanden": n,
            "doel": doel,
            "woorden": [toen_woorden[s] for s in top],
            "stammen": [s for _, s in gedeeld],
            "details": [(toen_woorden[st], dagteller[st], len(toen_dagen[st]), w) for w, st in gedeeld],
            "score": score,
            "voorbeeld": " ".join(beste_bericht[1].split()),
        })

    analyse["kandidaten"].sort(key=lambda k: (k["score"], k["afstand_maanden"]), reverse=True)
    if not analyse["kandidaten"] and not analyse["reden"]:
        analyse["reden"] = "geen enkele afstand haalt de drempel"
    return analyse


def formuleer(kandidaat, voorbeeld=TOON_VOORBEELD, kies=random.choice):
    doel = kandidaat["doel"]
    wanneer = _wanneer_label(kandidaat["afstand_maanden"])
    zin = kies(_SJABLONEN).format(
        Wanneer=wanneer[0].upper() + wanneer[1:],
        wanneer=wanneer,
        datum=f"{doel.day} {_MAANDEN[doel.month - 1]}",
        woorden=_woordenlijst(kandidaat["woorden"]),
    )
    if voorbeeld and kandidaat.get("voorbeeld"):
        tekst = kandidaat["voorbeeld"]
        if len(tekst) > VOORBEELD_MAX_TEKENS:
            tekst = tekst[: VOORBEELD_MAX_TEKENS - 1].rstrip() + "…"
        zin += f" Toen schreef je bijvoorbeeld: \"{tekst}\""
    return zin


def formatteer_status(analyse, nu_datum):
    regels = [f"Datum: {nu_datum.day} {_MAANDEN[nu_datum.month - 1]} {nu_datum.year}",
              f"Dagen met berichten: {analyse['actieve_dagen']}"]
    if analyse.get("reden"):
        regels.append(f"Resultaat: geen terugblik ({analyse['reden']})")
    for k in analyse["kandidaten"]:
        regels.append(f"+ {k['afstand_maanden']} maanden geleden (rond {k['doel'].day} "
                      f"{_MAANDEN[k['doel'].month - 1]}): {_woordenlijst(k['woorden'])}, score {k['score']:.1f}")
        for woord, dagen_totaal, dagen_toen, w in k.get("details", []):
            regels.append(f"    {woord}: {dagen_totaal} dag(en) totaal, {dagen_toen} dag(en) toen, score {w:.1f}")
    for n, reden in analyse["afgewezen"]:
        regels.append(f"- {n} maanden geleden: {reden}")
    if analyse["kandidaten"]:
        regels.append("Zou melden: " + formuleer(analyse["kandidaten"][0], kies=lambda lst: lst[0]))
    return "\n".join(regels)


# ---------------------------------------------------------------
# Berichten ophalen (database + gzip-archieven)
# ---------------------------------------------------------------
def _tekst_uit(data):
    try:
        d = json.loads(data) if isinstance(data, str) else data
        return d.get("text", "") if isinstance(d, dict) else ""
    except ValueError:
        return ""


def rijen_uit_conn(conn, lock, ondergrens, limiet=MAX_RIJEN):
    """Kevins berichten (ts, tekst) uit 'interactions' en 'interactions_old'."""
    rijen = []
    ctx = lock if lock is not None else contextlib.nullcontext()
    with ctx:
        for tabel in ("interactions", "interactions_old"):
            try:
                cur = conn.execute(
                    f"SELECT timestamp, data FROM {tabel} "
                    f"WHERE event_type = 'raw_user_message' AND timestamp >= ? "
                    f"ORDER BY timestamp DESC LIMIT ?", (ondergrens, limiet))
                for ts, data in cur.fetchall():
                    tekst = _tekst_uit(data)
                    if tekst:
                        rijen.append((float(ts), tekst))
            except Exception as e:
                print(f"[DATUM_TERUGBLIK] databasefout ({tabel}): {e}")
    return rijen


_GZ_CACHE = {}


def rijen_uit_gz(map_, ondergrens):
    """Berichten uit de gzip-archieven (> 1 jaar oud) in data/archive/."""
    try:
        bestanden = sorted(glob.glob(str(Path(map_) / "*.jsonl.gz")))
        handtekening = tuple((b, os.path.getmtime(b)) for b in bestanden)
    except OSError:
        return []
    if not bestanden:
        return []
    if _GZ_CACHE.get(str(map_), (None, None))[0] != handtekening:
        alles = []
        for b in bestanden:
            try:
                with gzip.open(b, "rt", encoding="utf-8") as f:
                    for regel in f:
                        try:
                            r = json.loads(regel)
                        except ValueError:
                            continue
                        if r.get("event_type") == "raw_user_message":
                            tekst = _tekst_uit(r.get("data", ""))
                            if tekst:
                                alles.append((float(r.get("timestamp", 0)), tekst))
            except (OSError, EOFError):
                continue
        _GZ_CACHE[str(map_)] = (handtekening, alles)
    return [r for r in _GZ_CACHE[str(map_)][1] if r[0] >= ondergrens]


def lees_rijen_uit_db(db_pad, archief_map, ondergrens):
    """Voor scripts/terugblik_status.py: leest de database ALLEEN-LEZEN, los van Nova."""
    conn = sqlite3.connect(f"file:{db_pad}?mode=ro", uri=True)
    try:
        rijen = rijen_uit_conn(conn, None, ondergrens)
    finally:
        conn.close()
    rijen += rijen_uit_gz(archief_map, ondergrens)
    return list({(ts, t): (ts, t) for ts, t in rijen}.values())


# ---------------------------------------------------------------
# De module
# ---------------------------------------------------------------
class DatumTerugblik:

    def __init__(self, event_bus, pad=None, modus=None, klok=None, start_thread=True, kies=None):
        self.event_bus = event_bus
        self.klok = klok or _nu
        self.kies = kies or random.choice
        modus = (modus or os.getenv("DATUM_TERUGBLIK_MODUS", "aan")).strip().lower()
        self.modus = modus if modus in ("aan", "droog", "uit") else "aan"

        if pad is None:
            pad = Path(__file__).resolve().parent.parent.parent / "data" / "datum_terugblik.json"
        self.pad = Path(pad)
        self.staat = {"laatst_gemeld_datum": None, "gemeld": {}, "laatste_analyse": None}
        self._laad()

        self._cache = None            # (datum-tekst, berekend-op-timestamp, analyse)
        self._droog_gelogd = None     # datum waarop de droge run al geprint is
        self._stop = threading.Event()
        self._thread = None
        if start_thread and self.modus != "uit":
            self._thread = threading.Thread(target=self._lus, name="datum_terugblik", daemon=True)
            self._thread.start()
            zelftest = os.getenv("DATUM_TERUGBLIK_ZELFTEST_NA_SECONDEN")
            if zelftest and zelftest.isdigit():
                t = threading.Timer(int(zelftest), self._print_status)
                t.daemon = True
                t.start()

    # --- opslag ---
    def _laad(self):
        try:
            with open(self.pad, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self.staat["laatst_gemeld_datum"] = data.get("laatst_gemeld_datum")
                gemeld = data.get("gemeld", {})
                if isinstance(gemeld, dict):
                    self.staat["gemeld"] = {str(k): str(v) for k, v in gemeld.items()}
                self.staat["laatste_analyse"] = data.get("laatste_analyse")
        except (OSError, ValueError):
            pass

    def _bewaar(self):
        try:
            self.pad.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.pad.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.staat, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.pad)
        except OSError:
            pass

    # --- thread ---
    def _lus(self):
        if self._stop.wait(START_VERTRAGING_SEC):
            return
        while not self._stop.is_set():
            try:
                self.check_nu()
            except Exception as e:  # een fout hier mag Nova nooit raken
                print(f"[DATUM_TERUGBLIK] fout in check: {e}")
            if self._stop.wait(CHECK_INTERVAL_SEC):
                break

    def shutdown(self):
        self._stop.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)

    # --- analyse met cache ---
    def _laad_rijen(self, nu):
        mem = self.event_bus.modules.get("memory")
        if mem is None or getattr(mem, "conn", None) is None:
            return []
        ondergrens = nu.timestamp() - LOOKBACK_DAGEN * 86400
        try:
            mem._flush_buffer()
        except Exception:
            pass
        rijen = rijen_uit_conn(mem.conn, getattr(mem, "lock", None), ondergrens)
        if hasattr(mem, "save_path"):
            rijen += rijen_uit_gz(Path(mem.save_path).parent / "archive", ondergrens)
        return list({(ts, t): (ts, t) for ts, t in rijen}.values())

    def analyse_van_vandaag(self, nu=None, opnieuw=False):
        nu = nu or self.klok()
        vandaag = nu.date().isoformat()
        nu_ts = nu.timestamp()
        if not opnieuw and self._cache:
            dag, berekend, analyse = self._cache
            vers_genoeg = analyse["kandidaten"] or (nu_ts - berekend) < HERBEREKEN_NA_SEC
            if dag == vandaag and vers_genoeg:
                return analyse
        analyse = vind_terugblik(self._laad_rijen(nu), nu.date())
        self._cache = (vandaag, nu_ts, analyse)
        self.staat["laatste_analyse"] = {
            "datum": vandaag,
            "actieve_dagen": analyse["actieve_dagen"],
            "reden": analyse["reden"],
            "beste": ({"afstand_maanden": analyse["kandidaten"][0]["afstand_maanden"],
                       "woorden": analyse["kandidaten"][0]["woorden"],
                       "score": round(analyse["kandidaten"][0]["score"], 2)}
                      if analyse["kandidaten"] else None),
            "afgewezen": [f"{n} mnd: {r}" for n, r in analyse["afgewezen"]],
        }
        self._bewaar()
        return analyse

    # --- poorten ---
    def _mag_spreken(self):
        cm = self.event_bus.modules.get("context_manager")
        if cm is None:
            return False
        try:
            return bool(cm.can_interrupt())
        except Exception:
            return False

    def _woord_in_cooldown(self, stam, vandaag):
        laatst = self.staat["gemeld"].get(stam)
        if not laatst:
            return False
        try:
            verschil = (date.fromisoformat(vandaag) - date.fromisoformat(laatst)).days
        except ValueError:
            return False
        return verschil < HERHALING_DAGEN

    # --- de kern ---
    def check_nu(self, forceer=False):
        """
        Geeft (heeft_gesproken, reden). forceer=True slaat de spamregels en
        Layer 5 over (voor handmatig testen), maar spreekt nooit in modus 'uit'.
        """
        if self.modus == "uit":
            return False, "modus uit"
        if not forceer and self.via_emergence():
            # De emergence_engine kiest en zegt het (zie vind_insight). Zelf ook
            # spreken zou dubbel zijn en de gedeelde spam-rem van Layer 7 omzeilen.
            return False, "loopt via emergence_engine"
        nu = self.klok()
        vandaag = nu.date().isoformat()

        if not forceer:
            if self.staat["laatst_gemeld_datum"] == vandaag:
                return False, "vandaag al gemeld"
            if not (SPREEK_VANAF_UUR <= nu.hour < SPREEK_TOT_UUR):
                return False, "buiten de spreekuren"

        analyse = self.analyse_van_vandaag(nu)
        if not analyse["kandidaten"]:
            return False, analyse["reden"] or "geen sterke overeenkomst"

        kandidaat = None
        for k in analyse["kandidaten"]:
            if forceer or not any(self._woord_in_cooldown(s, vandaag) for s in k["stammen"]):
                kandidaat = k
                break
        if kandidaat is None:
            return False, "dezelfde woorden zijn recent al gemeld"

        if not forceer and self.modus == "aan" and not self._mag_spreken():
            return False, "Layer 5 zegt nee"

        tekst = formuleer(kandidaat, kies=self.kies)

        if self.modus == "droog" and not forceer:
            if self._droog_gelogd != vandaag:
                self._droog_gelogd = vandaag
                print(f"[DATUM_TERUGBLIK] (droog) zou zeggen: {tekst}")
            return False, "droge run"

        self.event_bus.publish("layer4_response", {"text": tekst})
        self._registreer_melding(kandidaat["stammen"], nu)
        return True, "gemeld"

    def _registreer_melding(self, stammen, nu):
        """Onthoudt dat er vandaag gemeld is en zet de woorden in cooldown."""
        vandaag = nu.date().isoformat()
        self.staat["laatst_gemeld_datum"] = vandaag
        for s in stammen:
            self.staat["gemeld"][s] = vandaag
        verval = (nu.date() - timedelta(days=90)).isoformat()
        self.staat["gemeld"] = {k: v for k, v in self.staat["gemeld"].items() if v >= verval}
        self._bewaar()

    # --- koppeling met Layer 7 (emergence_engine) ---
    def via_emergence(self):
        """
        True als de emergence_engine deze module als bron heeft (layers["datum_terugblik"]
        is deze instantie). Dan geeft de module haar inzicht door via vind_insight() en
        laat Layer 7 beslissen wanneer het hardop gezegd wordt. Zonder die koppeling
        spreekt de module zelf, zoals voorheen.
        """
        em = self.event_bus.modules.get("emergence_engine") if hasattr(self.event_bus, "modules") else None
        lagen = getattr(em, "layers", None)
        return isinstance(lagen, dict) and lagen.get("datum_terugblik") is self

    def vind_insight(self, nu=None):
        """
        Voor emergence_engine.analyze_datum_terugblik(): geeft het beste terugblik-inzicht
        van nu als dict, of None. Spreekt zelf NIET en wijzigt de staat niet; de
        spamregels van deze module (1 per dag, spreekuren, cooldown per woord) gelden
        hier ook. Layer 5, de cooldowns per type en de feedback regelt emergence_engine.
        """
        if self.modus == "uit":
            return None
        nu = nu or self.klok()
        vandaag = nu.date().isoformat()
        if self.staat["laatst_gemeld_datum"] == vandaag:
            return None
        if not (SPREEK_VANAF_UUR <= nu.hour < SPREEK_TOT_UUR):
            return None
        analyse = self.analyse_van_vandaag(nu)
        for k in analyse["kandidaten"]:
            if any(self._woord_in_cooldown(st, vandaag) for st in k["stammen"]):
                continue
            tekst = formuleer(k, kies=self.kies)
            if self.modus == "droog":
                if self._droog_gelogd != vandaag:
                    self._droog_gelogd = vandaag
                    print(f"[DATUM_TERUGBLIK] (droog) zou zeggen: {tekst}")
                return None
            return {
                "type": "datum_terugblik",
                "confidence": k["score"],
                "afstand_maanden": k["afstand_maanden"],
                "doel": k["doel"].isoformat(),
                "woorden": list(k["woorden"]),
                "stammen": list(k["stammen"]),
                "tekst": tekst,
            }
        return None

    def markeer_gemeld(self, insight):
        """emergence_engine roept dit aan nadat het inzicht ECHT hardop gezegd is."""
        self._registreer_melding(insight.get("stammen", []), self.klok())

    # --- inspectie ---
    def status_tekst(self):
        nu = self.klok()
        via = "emergence_engine (Layer 7)" if self.via_emergence() else "eigen thread"
        return f"Modus: {self.modus} (spreekt via: {via})\n" + formatteer_status(self.analyse_van_vandaag(nu, opnieuw=True), nu.date())

    def _print_status(self):
        try:
            print("[DATUM_TERUGBLIK] zelftest:\n" + self.status_tekst())
        except Exception as e:
            print(f"[DATUM_TERUGBLIK] zelftest mislukt: {e}")


def init_module(event_bus, sem=None):
    mod = DatumTerugblik(event_bus)
    event_bus.publish("module_loaded", {"name": "datum_terugblik"})
    print(f"[DATUM_TERUGBLIK] module geladen (modus: {mod.modus})")
    return mod