# modules/diagnose/zelftest.py
#
# Zelftest (13 november 2026): Nova test zichzelf en vertelt wat ze vindt.
#
# WAT DOET DIT?
#   Nova start dezelfde controleprogramma's die jij met de hand typt, leest wat
#   eruit komt en vat het samen in gewone zinnen:
#     - pytest    : draaien al je tests (op een TIJDELIJKE KOPIE van het project)
#     - pyflakes  : zoekt slordigheden en ontbrekende namen in de code
#     - radon     : meet hoe ingewikkeld de functies zijn
#     - data      : zijn alle JSON-bestanden in data/ nog geldig, is de databank ok
#     - foutenlog : zijn er nieuwe fouten in logs/handler_fouten.log
#   Elk resultaat wordt bewaard in data/zelftest_historie.json, zodat Nova kan
#   zeggen wat er veranderd is sinds de vorige keer.
#
# PUUR SYMBOLISCH: programma's starten, hun tekst ontleden, getallen vergelijken
# en zinnen uit sjablonen bouwen. Geen ML. Nova ZIET dat iets mis is, maar weet
# niet WAAROM; het uitzoeken blijft aan jou.
#
# VEILIGHEIDSREGELS (bewust zo ontworpen):
#   1. Alleen LEZEN: Nova past nooit code of data aan op basis van een zelftest.
#   2. pytest draait in een APART PROCES op een KOPIE van het project, zonder
#      de echte databank, back-ups, logs, .env en zonder sleutels/tokens in de
#      omgeving. Zo kan geen enkele test je echte data of je gsm raken.
#   3. De kopie staat in een tijdelijke map en wordt na afloop altijd gewist.
#   4. Er draait nooit twee zelftests tegelijk.
#   5. Met een tijdslimiet: een vastgelopen test houdt Nova niet op.
#   6. Spontane meldingen (opstart/nacht) gaan ALLEEN naar je gsm als er echt
#      iets mis is (status "fout"). "Alles ok" komt enkel in de console.
#
# COMMANDO'S (via modules/debug/debug_commands.py):
#   zelftest          volledige zelftest (pytest, pyflakes, radon, data, foutenlog)
#   zelftest snel     enkel pyflakes, data en foutenlog (enkele seconden)
#   zelftest status   toont de laatste zelftest en de laatste vijf uitslagen
#   test jezelf       zelfde als "zelftest"
#
# AUTOMATISCH (aan/uit via .env):
#   ZELFTEST_OPSTART=aan|uit    korte controle ~3 minuten na het opstarten (standaard aan)
#   ZELFTEST_NACHT=03:30|uit    volledige controle 's nachts, 1x per dag (standaard UIT;
#                               zet hem pas aan nadat je "zelftest" op commando probeerde)
#   ZELFTEST_OPSTART_VERTRAGING seconden wachten na het opstarten (standaard 180)
#   ZELFTEST_PYTEST_TIMEOUT     tijdslimiet voor pytest in seconden (standaard 600)
#
# AUTO-DISCOVERY: staat in modules/diagnose/ en heeft init_module(event_bus, sem).
# module_loader.py vindt en laadt hem dus zelf; daar hoeft niets voor aangepast.
#
# TESTS: tests/test_zelftest.py (alles met een nep-runner, er wordt niets echt gestart).

import importlib.util
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, time as dagtijd, timedelta
from pathlib import Path

# ----------------------------------------------------------------------------
# Instellingen
# ----------------------------------------------------------------------------

ENV_GUARD = "NOVA_ZELFTEST_KIND"         # staat in de omgeving van het kind-proces: nooit recursief starten
PYTEST_TIMEOUT_STANDAARD = 600           # seconden
TOOL_TIMEOUT = 180                       # seconden voor pyflakes en radon
MAX_UITVOER = 4_000_000                  # we houden enkel het einde van lange uitvoer (radon geeft ~0,6 MB JSON)
HISTORIE_MAX = 60                        # bewaarde runs
OPSTART_VERTRAGING_STANDAARD = 180       # seconden na het opstarten
RUSTIG_NA_SECONDEN = 600                 # nachtrun wacht tot er 10 min geen bericht was
MAX_GETOOND = 5                          # aantal voorbeelden in een rapport
LOG_VENSTER_UREN = 24

CODE_MAPPEN = ("core", "modules", "identity", "tools", "scripts")
CODE_BESTANDEN = ("main.py",)
PYFLAKES_DOELEN = CODE_MAPPEN + ("tests",) + CODE_BESTANDEN
RADON_DOELEN = CODE_MAPPEN + CODE_BESTANDEN        # tests tellen niet mee voor complexiteit

# Woorden in een pyflakes-melding die op een ECHTE fout wijzen (niet op opruimwerk).
# Let op: "undefined name '" (met aanhalingsteken) en niet enkel "undefined name", want de
# waarschuwing over 'import *' zegt ook "unable to detect undefined names" en is geen fout.
ERNSTIG_WOORDEN = ("undefined name '", "syntax", "invalid", "indent", "unterminated", "eof")

# Omgevingsvariabelen die NIET aan de testkopie worden meegegeven.
GEVOELIGE_SLEUTELDELEN = ("NTFY", "API_KEY", "APIKEY", "TOKEN", "SECRET", "PASSWORD", "WACHTWOORD")

# Wat NIET mee naar de tijdelijke testkopie gaat.
ALTIJD_NEGEREN = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", "venv", ".venv",
                  "logs", ".env", "node_modules", "engines"}
DB_EINDEN = (".db", ".db-wal", ".db-shm", ".db-journal")
DATA_NEGEREN = {"backups", "models"}

_MODI = ("snel", "volledig")


# ----------------------------------------------------------------------------
# Kleine hulpfuncties
# ----------------------------------------------------------------------------

def _mv(n, enkelvoud, meervoud):
    """1 -> enkelvoud, anders meervoud. Geeft '3 tests' / '1 test'."""
    return f"{n} {enkelvoud if n == 1 else meervoud}"


def parse_tijd(tekst):
    """
    '03:30' -> time(3, 30); '3' -> time(3, 0); 'uit'/''/rommel -> None.
    Gebruikt voor ZELFTEST_NACHT.
    """
    if tekst is None:
        return None
    tekst = str(tekst).strip().lower()
    if tekst in ("", "uit", "nee", "0", "false", "off", "geen"):
        return None
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?", tekst)
    if not m:
        return None
    uur, minuut = int(m.group(1)), int(m.group(2) or 0)
    if uur > 23 or minuut > 59:
        return None
    return dagtijd(uur, minuut)


def veilige_omgeving(omgeving=None):
    """
    Kopie van de omgeving ZONDER sleutels, tokens, ntfy-gegevens enzovoort, plus
    de guard die voorkomt dat het kind-proces zelf weer een zelftest start.
    """
    bron = os.environ if omgeving is None else omgeving
    schoon = {}
    for naam, waarde in bron.items():
        if any(deel in naam.upper() for deel in GEVOELIGE_SLEUTELDELEN):
            continue
        schoon[naam] = waarde
    schoon[ENV_GUARD] = "pytest"
    schoon["PYTHONDONTWRITEBYTECODE"] = "1"
    return schoon


def standaard_runner(cmd, cwd, timeout, env=None, samenvoegen=True):
    """
    Start een programma, wacht (met tijdslimiet) en geeft (returncode, uitvoer, te_laat).
    Gooit NOOIT een fout naar buiten: een programma dat niet bestaat geeft code 127.
    samenvoegen=False gooit de foutuitvoer (stderr) weg; handig voor JSON op stdout.
    """
    try:
        p = subprocess.run(
            cmd, cwd=str(cwd), env=env, timeout=timeout,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT if samenvoegen else subprocess.DEVNULL,
        )
        uit = (p.stdout or b"").decode("utf-8", errors="replace")
        return p.returncode, uit[-MAX_UITVOER:], False
    except subprocess.TimeoutExpired as e:
        uit = (e.stdout or b"")
        if isinstance(uit, bytes):
            uit = uit.decode("utf-8", errors="replace")
        return -1, uit[-MAX_UITVOER:], True
    except (OSError, ValueError) as e:
        return 127, str(e), False


# ----------------------------------------------------------------------------
# De uitvoer van de programma's ontleden (allemaal losse, testbare functies)
# ----------------------------------------------------------------------------

_PYTEST_TELLER = re.compile(
    r"(\d+)\s+(passed|failed|errors?|skipped|xfailed|xpassed|deselected|warnings?)\b")
_PYTEST_DUUR = re.compile(r"\bin\s+(\d+(?:\.\d+)?)s\b")
_PYTEST_MISLUKT = re.compile(r"^(FAILED|ERROR)\s+(\S+)")


def parse_pytest(uitvoer, returncode, te_laat=False):
    """
    Haalt uit de pytest-uitvoer: geslaagd, gefaald, fouten, overgeslagen, duur en de
    namen van mislukte tests. De samenvattingsregel staat NIET altijd onderaan (Nova
    drukt na afloop nog 'Memory: netjes afgesloten' af), dus we zoeken er naar.
    """
    res = {"gelukt": False, "geslaagd": 0, "gefaald": 0, "fouten": 0, "overgeslagen": 0,
           "mislukt": [], "duur": None, "reden": None}
    uitvoer = uitvoer or ""

    samenvatting = None
    for regel in reversed(uitvoer.splitlines()):
        if _PYTEST_DUUR.search(regel) and _PYTEST_TELLER.search(regel):
            samenvatting = regel
            break
    if samenvatting:
        for aantal, soort in _PYTEST_TELLER.findall(samenvatting):
            n = int(aantal)
            if soort == "passed":
                res["geslaagd"] = n
            elif soort == "failed":
                res["gefaald"] = n
            elif soort.startswith("error"):
                res["fouten"] = n
            elif soort == "skipped":
                res["overgeslagen"] = n
        m = _PYTEST_DUUR.search(samenvatting)
        res["duur"] = float(m.group(1)) if m else None

    gezien = set()
    for regel in uitvoer.splitlines():
        m = _PYTEST_MISLUKT.match(regel)
        if m and m.group(2) not in gezien:
            gezien.add(m.group(2))
            res["mislukt"].append(m.group(2))
    res["mislukt"] = res["mislukt"][:20]

    if te_laat:
        res["reden"] = "tijdslimiet overschreden (de tests liepen te lang)"
    elif returncode == 127:
        res["reden"] = "pytest kon niet gestart worden"
    elif returncode == 5:
        res["reden"] = "pytest vond geen enkele test"
    elif samenvatting is None:
        res["reden"] = "geen samenvatting van pytest gevonden (is pytest gecrasht?)"
    else:
        res["gelukt"] = (returncode == 0)
    return res


_PYFLAKES_REGEL = re.compile(r"^(?P<pad>.+?):(?P<regel>\d+):(?:(?P<kol>\d+):?)?\s+(?P<tekst>.+)$")


def parse_pyflakes(uitvoer, returncode, te_laat=False):
    """
    Telt de pyflakes-meldingen en splitst ze in 'echte fouten' (ontbrekende namen,
    syntaxfouten) en 'opruimwerk' (ongebruikte imports enzovoort).
    """
    res = {"beschikbaar": True, "gelukt": True, "meldingen": 0, "ernstig_aantal": 0,
           "ernstig": [], "reden": None}
    if te_laat:
        res.update(gelukt=False, reden="tijdslimiet overschreden")
        return res
    if returncode == 127:
        res.update(gelukt=False, reden="pyflakes kon niet gestart worden")
        return res
    if returncode not in (0, 1):
        res.update(gelukt=False, reden=f"pyflakes stopte onverwacht (code {returncode})")
        return res

    for regel in (uitvoer or "").splitlines():
        m = _PYFLAKES_REGEL.match(regel.strip())
        if not m:
            continue            # bv. de regel met de code en het ^-teken bij een syntaxfout
        res["meldingen"] += 1
        tekst = m.group("tekst").lower()
        if any(w in tekst for w in ERNSTIG_WOORDEN):
            res["ernstig_aantal"] += 1
            if len(res["ernstig"]) < 20:
                res["ernstig"].append(f"{m.group('pad')}:{m.group('regel')}: {m.group('tekst')}")
    return res


def parse_radon(json_tekst, returncode, te_laat=False):
    """
    Ontleedt 'radon cc -j'. Telt alleen functies en methodes (klassen zouden dubbel
    tellen). 'zwaar' = rang D of erger (complexiteit 21 of hoger).
    """
    res = {"beschikbaar": True, "gelukt": False, "functies": 0, "gemiddelde": 0.0,
           "zwaar": 0, "zwaarste": [], "onleesbaar": [], "reden": None}
    if te_laat:
        res["reden"] = "tijdslimiet overschreden"
        return res
    if returncode == 127:
        res["reden"] = "radon kon niet gestart worden"
        return res
    try:
        data = json.loads(json_tekst or "{}")
    except (ValueError, TypeError):
        res["reden"] = "uitvoer van radon was geen geldige JSON"
        return res
    if not isinstance(data, dict):
        res["reden"] = "onverwachte uitvoer van radon"
        return res

    totaal, aantal, alle = 0, 0, []
    for bestand, blokken in data.items():
        if isinstance(blokken, dict):               # {"error": "..."} voor een onleesbaar bestand
            res["onleesbaar"].append(bestand)
            continue
        for b in blokken:
            if b.get("type") not in ("function", "method"):
                continue
            score = int(b.get("complexity", 0))
            aantal += 1
            totaal += score
            naam = f"{b['classname']}.{b['name']}" if b.get("classname") else b.get("name", "?")
            alle.append((score, bestand, naam))
            if b.get("rank") in ("D", "E", "F"):
                res["zwaar"] += 1

    alle.sort(reverse=True)
    res["zwaarste"] = [{"score": s, "bestand": f, "naam": n} for s, f, n in alle[:3]]
    res["functies"] = aantal
    res["gemiddelde"] = round(totaal / aantal, 1) if aantal else 0.0
    res["gelukt"] = True
    return res


def check_data(project_root):
    """
    Zijn alle data/*.json nog geldige JSON, en is de databank (interactions.db) in orde?
    De databank wordt ALLEEN-LEZEN geopend, dus Nova's eigen schrijven wordt niet gehinderd.
    """
    root = Path(project_root)
    res = {"json_gecontroleerd": 0, "json_stuk": [], "db": "niet aanwezig"}
    datamap = root / "data"
    if datamap.is_dir():
        for p in sorted(datamap.glob("*.json")):
            try:
                if p.stat().st_size > 100_000_000:
                    continue
                with open(p, encoding="utf-8") as f:
                    json.load(f)
                res["json_gecontroleerd"] += 1
            except Exception as e:
                res["json_stuk"].append(f"{p.name} ({type(e).__name__})")

    db = datamap / "interactions.db"
    if db.exists():
        verbinding = None
        try:
            verbinding = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
            rijen = verbinding.execute("PRAGMA quick_check").fetchall()
            res["db"] = "ok" if rijen == [("ok",)] else "stuk: " + "; ".join(str(r[0]) for r in rijen[:3])
        except sqlite3.OperationalError as e:           # bv. "database is locked": geen oordeel
            res["db"] = f"niet gecontroleerd ({e})"
        except sqlite3.DatabaseError as e:              # bv. "file is not a database"
            res["db"] = f"stuk: {e}"
        except Exception as e:
            res["db"] = f"niet gecontroleerd ({type(e).__name__})"
        finally:
            if verbinding is not None:
                verbinding.close()
    return res


def check_log(logbestand, nu):
    """
    Hoeveel fouten staan er in handler_fouten.log uit de laatste 24 uur?
    Hergebruikt de leesfunctie van modules/context/handler_fouten.py.
    """
    res = {"gelukt": True, "laatste_24u": 0, "laatste": None, "reden": None}
    try:
        from modules.context.handler_fouten import lees_logbestand, mooie_naam
        grens = nu - timedelta(hours=LOG_VENSTER_UREN)
        recent = []
        for f in lees_logbestand(logbestand):
            try:
                moment = datetime.strptime(f"{f['datum']} {f['tijd']}", "%Y-%m-%d %H:%M:%S")
            except (KeyError, ValueError):
                continue
            if moment >= grens:
                recent.append(f)
        res["laatste_24u"] = len(recent)
        if recent:
            laatste = recent[-1]
            res["laatste"] = f"{mooie_naam(laatste.get('handler'))}: {laatste.get('fout', '')}".strip()
    except Exception as e:
        res.update(gelukt=False, reden=f"foutenlog niet te lezen ({type(e).__name__})")
    return res


# ----------------------------------------------------------------------------
# Tijdelijke testkopie
# ----------------------------------------------------------------------------

def _negeer(dirpath, namen):
    """Voor shutil.copytree: wat NIET mee naar de kopie gaat."""
    in_data = os.path.basename(str(dirpath).rstrip("/\\")) == "data"
    over = set()
    for n in namen:
        if n in ALTIJD_NEGEREN or n.endswith(DB_EINDEN):
            over.add(n)
        elif in_data and (n in DATA_NEGEREN or n.startswith("interactions")):
            over.add(n)
    return over


def maak_testkopie(project_root, basismap=None):
    """
    Kopieert het project (zonder echte databank, back-ups, logs, .env en zware mappen)
    naar een tijdelijke map. Geeft (tijdelijke_map, pad_van_de_kopie).
    De engines-map (Stockfish) wordt niet gekopieerd maar gekoppeld, enkel om te lezen.
    """
    root = Path(project_root)
    tijdelijk = Path(tempfile.mkdtemp(prefix="nova_zelftest_", dir=basismap))
    kopie = tijdelijk / "nova"
    try:
        shutil.copytree(root, kopie, ignore=_negeer, symlinks=True)
        engines = root / "engines"
        if engines.is_dir():
            try:
                os.symlink(engines, kopie / "engines", target_is_directory=True)
            except OSError:
                pass            # geen symlinks mogelijk: de chess-tests slaan dit dan zelf over
    except Exception:
        ruim_op(tijdelijk)
        raise
    return tijdelijk, kopie


def ruim_op(tijdelijke_map):
    """Wist de tijdelijke map. Faalt stil."""
    if tijdelijke_map:
        shutil.rmtree(str(tijdelijke_map), ignore_errors=True)


# ----------------------------------------------------------------------------
# Beoordelen, vergelijken en zinnen bouwen
# ----------------------------------------------------------------------------

def _pytest_foutzin(pt):
    if pt.get("reden"):
        return f"pytest: {pt['reden']}"
    delen = []
    if pt.get("gefaald"):
        delen.append(_mv(pt["gefaald"], "test gefaald", "tests gefaald"))
    if pt.get("fouten"):
        delen.append(_mv(pt["fouten"], "fout bij het laden", "fouten bij het laden"))
    return "pytest: " + (" en ".join(delen) if delen else "niet geslaagd")


def _beoordeel_pytest(pt, vorig):
    """Elk _beoordeel_*-onderdeel geeft (fouten, opmerkingen, vergelijking) terug."""
    fouten, opmerkingen, vergelijking = [], [], []
    vp = vorig.get("pytest") or {}
    if not pt.get("gelukt"):
        fouten.append(_pytest_foutzin(pt))
    elif isinstance(vp.get("geslaagd"), int) and pt["geslaagd"] < vp["geslaagd"]:
        opmerkingen.append(
            f"{_mv(vp['geslaagd'] - pt['geslaagd'], 'test', 'tests')} minder geslaagd dan vorige keer "
            f"zonder dat er een faalt (tests verwijderd of overgeslagen?)")
    for sleutel, naam in (("geslaagd", "geslaagde tests"), ("gefaald", "gefaalde tests")):
        if isinstance(vp.get(sleutel), int) and pt.get(sleutel) != vp[sleutel]:
            vergelijking.append(f"{naam} {vp[sleutel]} \u2192 {pt.get(sleutel)}")
    return fouten, opmerkingen, vergelijking


def _beoordeel_pyflakes(pf, vorig):
    fouten, opmerkingen, vergelijking = [], [], []
    if not pf.get("beschikbaar", True):
        opmerkingen.append("pyflakes is niet geïnstalleerd (zet het in requirements.txt)")
        return fouten, opmerkingen, vergelijking
    if not pf.get("gelukt"):
        opmerkingen.append(f"pyflakes kon niet draaien: {pf.get('reden')}")
        return fouten, opmerkingen, vergelijking
    if pf.get("ernstig_aantal"):
        fouten.append(f"pyflakes: {_mv(pf['ernstig_aantal'], 'echte fout', 'echte fouten')} in de code")
    vp = vorig.get("pyflakes") or {}
    if isinstance(vp.get("meldingen"), int) and pf["meldingen"] != vp["meldingen"]:
        vergelijking.append(f"pyflakes-meldingen {vp['meldingen']} \u2192 {pf['meldingen']}")
        if pf["meldingen"] > vp["meldingen"]:
            opmerkingen.append(
                f"{_mv(pf['meldingen'] - vp['meldingen'], 'pyflakes-melding', 'pyflakes-meldingen')} meer dan vorige keer")
    return fouten, opmerkingen, vergelijking


def _beoordeel_radon(rd, vorig):
    fouten, opmerkingen, vergelijking = [], [], []
    if not rd.get("beschikbaar", True):
        opmerkingen.append("radon is niet geïnstalleerd (zet het in requirements.txt)")
        return fouten, opmerkingen, vergelijking
    if not rd.get("gelukt"):
        opmerkingen.append(f"radon kon niet draaien: {rd.get('reden')}")
        return fouten, opmerkingen, vergelijking
    vp = vorig.get("radon") or {}
    if isinstance(vp.get("zwaar"), int) and rd["zwaar"] != vp["zwaar"]:
        vergelijking.append(f"zware functies {vp['zwaar']} \u2192 {rd['zwaar']}")
        if rd["zwaar"] > vp["zwaar"]:
            opmerkingen.append(
                f"{_mv(rd['zwaar'] - vp['zwaar'], 'zware functie', 'zware functies')} meer dan vorige keer")
    return fouten, opmerkingen, vergelijking


def _beoordeel_data(da, vorig):
    fouten = []
    if da.get("json_stuk"):
        fouten.append("kapot JSON-bestand: " + ", ".join(da["json_stuk"][:3]))
    if str(da.get("db", "")).startswith("stuk"):
        fouten.append(f"databank: {da['db']}")
    return fouten, [], []


def _beoordeel_log(lg, vorig):
    opmerkingen = []
    if lg.get("gelukt") and lg.get("laatste_24u"):
        opmerkingen.append(
            f"{_mv(lg['laatste_24u'], 'nieuwe fout', 'nieuwe fouten')} in het foutenlog (laatste 24 uur)")
    return [], opmerkingen, []


_BEOORDELAARS = (("pytest", _beoordeel_pytest), ("pyflakes", _beoordeel_pyflakes),
                 ("radon", _beoordeel_radon), ("data", _beoordeel_data), ("log", _beoordeel_log))


def beoordeel(res, vorig=None):
    """
    Geeft {"status": "ok"|"let_op"|"fout", "punten": [...], "vergelijking": [...]}.
    'punten' zijn de redenen voor let_op/fout, 'vergelijking' de verschillen met 'vorig'
    (de vorige run van dezelfde soort). Elk onderdeel wordt door een eigen kleine functie
    beoordeeld; een onderdeel dat niet in 'res' zit (snelle run) wordt overgeslagen.
    """
    vorig = vorig or {}
    fouten, opmerkingen, vergelijking = [], [], []
    for sleutel, functie in _BEOORDELAARS:
        deel = res.get(sleutel)
        if deel is None:
            continue
        f, o, v = functie(deel, vorig)
        fouten += f
        opmerkingen += o
        vergelijking += v
    status = "fout" if fouten else ("let_op" if opmerkingen else "ok")
    return {"status": status, "punten": fouten + opmerkingen, "vergelijking": vergelijking}


def _fmt_tijd(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%d-%m %H:%M")
    except (TypeError, ValueError):
        return "eerder"


def _rapport_pytest(pt):
    if pt.get("reden"):
        return [f"\u2022 Tests: {pt['reden']}."]
    tekst = f"\u2022 Tests: {pt['geslaagd']} geslaagd, {pt['gefaald']} gefaald"
    if pt.get("fouten"):
        tekst += f", {pt['fouten']} fouten bij het laden"
    if pt.get("overgeslagen"):
        tekst += f", {pt['overgeslagen']} overgeslagen"
    regels = [tekst + "."]
    regels += [f"    - {naam}" for naam in pt.get("mislukt", [])[:MAX_GETOOND]]
    extra = len(pt.get("mislukt", [])) - MAX_GETOOND
    if extra > 0:
        regels.append(f"    - \u2026 en nog {extra}")
    return regels


def _rapport_pyflakes(pf):
    if not pf.get("beschikbaar", True):
        return ["\u2022 Pyflakes: niet gecontroleerd (niet geïnstalleerd)."]
    if not pf.get("gelukt"):
        return [f"\u2022 Pyflakes: kon niet draaien ({pf.get('reden')})."]
    regels = [f"\u2022 Pyflakes: {_mv(pf['meldingen'], 'melding', 'meldingen')}, "
              f"{_mv(pf['ernstig_aantal'], 'echte fout', 'echte fouten')}."]
    regels += [f"    - {r}" for r in pf.get("ernstig", [])[:3]]
    return regels


def _rapport_radon(rd):
    if not rd.get("beschikbaar", True):
        return ["\u2022 Complexiteit: niet gecontroleerd (radon niet geïnstalleerd)."]
    if not rd.get("gelukt"):
        return [f"\u2022 Complexiteit: kon niet gemeten worden ({rd.get('reden')})."]
    tekst = (f"\u2022 Complexiteit: {rd['functies']} functies, gemiddelde {rd['gemiddelde']}, "
             f"{_mv(rd['zwaar'], 'zware functie', 'zware functies')} (rang D of erger)")
    if rd.get("zwaarste"):
        z = rd["zwaarste"][0]
        tekst += f". Zwaarste: {z['naam']} ({z['score']})"
    return [tekst + "."]


def _rapport_data(da):
    tekst = f"\u2022 Data: {_mv(da['json_gecontroleerd'], 'JSON-bestand', 'JSON-bestanden')} gecontroleerd"
    if da.get("json_stuk"):
        tekst += f", KAPOT: {', '.join(da['json_stuk'][:3])}"
    return [tekst + f"; databank: {da.get('db')}."]


def _rapport_log(lg):
    if not lg.get("gelukt"):
        return [f"\u2022 Foutenlog: {lg.get('reden')}."]
    if lg.get("laatste_24u"):
        return [f"\u2022 Foutenlog: {_mv(lg['laatste_24u'], 'fout', 'fouten')} in de laatste 24 uur, "
                f"de laatste: {lg.get('laatste')}. Zeg 'laatste fouten' voor details."]
    return ["\u2022 Foutenlog: geen fouten in de laatste 24 uur."]


_RAPPORTEERDERS = (("pytest", _rapport_pytest), ("pyflakes", _rapport_pyflakes),
                   ("radon", _rapport_radon), ("data", _rapport_data), ("log", _rapport_log))


def maak_rapport(res, vorig=None):
    """Het volledige rapport voor de console. Pure functie: zelfde input, zelfde tekst."""
    kop = {"ok": "alles in orde", "let_op": "er is iets om op te letten",
           "fout": "er is iets mis"}.get(res.get("status"), "klaar")
    duur = res.get("duur")
    duurtekst = f" in {duur:.0f} s" if isinstance(duur, (int, float)) else ""
    regels = [f"Zelftest ({res.get('modus', '?')}) klaar{duurtekst}: {kop}."]
    for sleutel, functie in _RAPPORTEERDERS:
        if res.get(sleutel) is not None:
            regels += functie(res[sleutel])
    if res.get("status") != "ok" and res.get("punten"):
        regels.append("Let op: " + "; ".join(res["punten"]) + ".")
    if res.get("vergelijking"):
        regels.append(f"Sinds de vorige keer ({_fmt_tijd((vorig or {}).get('tijd'))}): "
                      + ", ".join(res["vergelijking"]) + ".")
    return "\n".join(regels)


def maak_meldingtekst(res):
    """Korte tekst voor de gsm (alleen bij status 'fout')."""
    punten = res.get("punten") or ["er is iets mis"]
    tekst = f"Zelftest ({res.get('modus', '?')}): " + "; ".join(punten[:2]) + "."
    if len(punten) > 2:
        tekst += f" (en nog {len(punten) - 2})"
    return tekst + " Zeg 'zelftest status' voor details."


# ----------------------------------------------------------------------------
# De module zelf
# ----------------------------------------------------------------------------

class Zelftest:
    def __init__(self, event_bus, project_root=None, historie_pad=None, logbestand=None,
                 runner=None, kopieer=None, tool_beschikbaar=None, klok=None,
                 opstart=None, nacht=None, opstart_vertraging=None, pytest_timeout=None,
                 achtergrond=None, drukaf=None):
        # Alles na event_bus bestaat vooral voor de tests (nep-runner, nep-klok,
        # tijdelijke paden). In Nova zelf wordt niets meegegeven: dan komt alles uit
        # .env en uit de plaats van dit bestand.
        self.event_bus = event_bus
        if project_root is None:
            from modules.paths import get_project_root
            project_root = get_project_root(__file__)
        self.root = Path(project_root)
        self._historie_pad = Path(historie_pad) if historie_pad else self.root / "data" / "zelftest_historie.json"
        self._logbestand = logbestand
        self._runner = runner or standaard_runner
        self._kopieer = kopieer or maak_testkopie
        self._tool_beschikbaar = tool_beschikbaar or (lambda naam: importlib.util.find_spec(naam) is not None)
        self._klok = klok or time.time
        self._print = drukaf or print

        # module_loader laadt deze module vóór ntfy_meldingen (alfabetisch), dus .env is op dit
        # punt misschien nog niet ingelezen. Zelf inlezen dus (bestaande waarden blijven staan).
        # Niet tijdens een pytest-run: dan mag een echt .env de andere tests niet beïnvloeden.
        if not os.getenv("PYTEST_CURRENT_TEST"):
            self._laad_dotenv()

        self._opstart_aan = self._lees_opstart(opstart)
        self._nacht = self._lees_nacht(nacht)
        self._opstart_vertraging = self._lees_getal(
            opstart_vertraging, "ZELFTEST_OPSTART_VERTRAGING", OPSTART_VERTRAGING_STANDAARD, 0, 3600)
        self._pytest_timeout = self._lees_getal(
            pytest_timeout, "ZELFTEST_PYTEST_TIMEOUT", PYTEST_TIMEOUT_STANDAARD, 30, 7200)

        self._bezig = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._laatste_bericht = 0.0           # tijdstip van het laatste bericht van Kevin
        self._historie = self._laad_historie()

        if event_bus is not None:
            event_bus.subscribe("raw_user_message", self._on_bericht)

        if achtergrond is None:
            achtergrond = not os.getenv("PYTEST_CURRENT_TEST") and not os.getenv(ENV_GUARD)
        if achtergrond and (self._opstart_aan or self._nacht is not None):
            self._thread = threading.Thread(target=self._achtergrondlus, daemon=True, name="zelftest")
            self._thread.start()
            plan = []
            if self._opstart_aan:
                plan.append(f"opstartcontrole na {self._opstart_vertraging} s")
            if self._nacht is not None:
                plan.append(f"nachtcontrole om {self._nacht.strftime('%H:%M')}")
            self._print("[ZELFTEST] Gepland: " + " en ".join(plan) + ".")

    # -- instellingen --------------------------------------------------------

    def _laad_dotenv(self):
        try:
            from dotenv import load_dotenv
            load_dotenv(self.root / ".env")
        except Exception:
            pass                                   # zonder python-dotenv gelden de gewone omgevingsvariabelen

    @staticmethod
    def _lees_opstart(waarde):
        if waarde is not None:
            return bool(waarde)
        return os.getenv("ZELFTEST_OPSTART", "aan").strip().lower() not in ("uit", "nee", "0", "false", "off")

    @staticmethod
    def _lees_nacht(waarde):
        if waarde is not None:
            return waarde if isinstance(waarde, dagtijd) else parse_tijd(waarde)
        return parse_tijd(os.getenv("ZELFTEST_NACHT", "uit"))

    @staticmethod
    def _lees_getal(waarde, naam, standaard, minimum, maximum):
        ruw = waarde if waarde is not None else os.getenv(naam, "")
        try:
            getal = int(ruw)
        except (TypeError, ValueError):
            return standaard
        return min(max(getal, minimum), maximum)

    # -- historie ------------------------------------------------------------

    def _laad_historie(self):
        leeg = {"versie": 1, "runs": [], "laatste_nacht_datum": None}
        try:
            with open(self._historie_pad, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("runs"), list):
                data.setdefault("laatste_nacht_datum", None)
                return data
        except (OSError, ValueError):
            pass
        return leeg

    def _bewaar_historie(self):
        """Atomisch schrijven: eerst een tijdelijk bestand, dan vervangen."""
        try:
            self._historie["runs"] = self._historie["runs"][-HISTORIE_MAX:]
            self._historie_pad.parent.mkdir(parents=True, exist_ok=True)
            tijdelijk = self._historie_pad.with_name(self._historie_pad.name + ".tmp")
            with open(tijdelijk, "w", encoding="utf-8") as f:
                json.dump(self._historie, f, ensure_ascii=False, indent=1)
            os.replace(tijdelijk, self._historie_pad)
        except OSError as e:
            self._print(f"[ZELFTEST] Historie niet bewaard: {e}")

    def _vorige_run(self, modus):
        for run in reversed(self._historie["runs"]):
            if run.get("modus") == modus:
                return run
        return None

    # -- de stappen ----------------------------------------------------------

    def _stap_pyflakes(self):
        if not self._tool_beschikbaar("pyflakes"):
            return {"beschikbaar": False, "gelukt": False, "reden": "niet geïnstalleerd"}
        doelen = [d for d in PYFLAKES_DOELEN if (self.root / d).exists()]
        rc, uit, te_laat = self._runner([sys.executable, "-m", "pyflakes", *doelen],
                                        self.root, TOOL_TIMEOUT)
        return parse_pyflakes(uit, rc, te_laat)

    def _stap_radon(self):
        if not self._tool_beschikbaar("radon"):
            return {"beschikbaar": False, "gelukt": False, "reden": "niet geïnstalleerd"}
        doelen = [d for d in RADON_DOELEN if (self.root / d).exists()]
        rc, uit, te_laat = self._runner([sys.executable, "-m", "radon", "cc", "-j", *doelen],
                                        self.root, TOOL_TIMEOUT, None, False)
        return parse_radon(uit, rc, te_laat)

    def _stap_data(self):
        return check_data(self.root)

    def _stap_log(self):
        pad = self._logbestand
        if pad is None:
            import core.event_bus as eb
            pad = eb._LOGBESTAND
        return check_log(pad, datetime.fromtimestamp(self._klok()))

    def _stap_pytest(self):
        if not self._tool_beschikbaar("pytest"):
            return {"gelukt": False, "geslaagd": 0, "gefaald": 0, "fouten": 0, "overgeslagen": 0,
                    "mislukt": [], "duur": None, "reden": "pytest is niet geïnstalleerd"}
        if not (self.root / "tests").is_dir():
            return {"gelukt": False, "geslaagd": 0, "gefaald": 0, "fouten": 0, "overgeslagen": 0,
                    "mislukt": [], "duur": None, "reden": "er is geen tests-map"}
        tijdelijk = None
        try:
            tijdelijk, kopie = self._kopieer(self.root)
            cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                   "--continue-on-collection-errors", "-rfE"]
            if os.name == "posix" and shutil.which("nice"):
                cmd = ["nice", "-n", "10"] + cmd          # laag in prioriteit: Nova en Kevin gaan voor
            rc, uit, te_laat = self._runner(cmd, kopie, self._pytest_timeout, veilige_omgeving())
            return parse_pytest(uit, rc, te_laat)
        except Exception as e:
            return {"gelukt": False, "geslaagd": 0, "gefaald": 0, "fouten": 0, "overgeslagen": 0,
                    "mislukt": [], "duur": None,
                    "reden": f"kon pytest niet voorbereiden ({type(e).__name__}: {e})"}
        finally:
            ruim_op(tijdelijk)

    # -- een zelftest uitvoeren ---------------------------------------------

    def voer_uit(self, modus="volledig", bron="commando"):
        """
        Draait de zelftest en geeft het resultaat (een dict) terug, of None als er al een
        zelftest loopt. Wordt in de historie bewaard. Gooit nooit een fout naar buiten.
        """
        if modus not in _MODI:
            modus = "volledig"
        if not self._bezig.acquire(blocking=False):
            return None
        try:
            begin = time.monotonic()
            res = {"tijd": datetime.fromtimestamp(self._klok()).isoformat(timespec="seconds"),
                   "modus": modus, "bron": bron}
            res["pyflakes"] = self._veilig(self._stap_pyflakes, "pyflakes")
            if modus == "volledig":
                res["radon"] = self._veilig(self._stap_radon, "radon")
            res["data"] = self._veilig(self._stap_data, "data",
                                       {"json_gecontroleerd": 0, "json_stuk": [], "db": "niet gecontroleerd"})
            res["log"] = self._veilig(self._stap_log, "log")
            if modus == "volledig":
                res["pytest"] = self._veilig(self._stap_pytest, "pytest")
            res["duur"] = round(time.monotonic() - begin, 1)

            vorig = self._vorige_run(modus)
            res.update(beoordeel(res, vorig))
            res["vorige_tijd"] = (vorig or {}).get("tijd")
            self._historie["runs"].append(res)
            self._bewaar_historie()
            return res
        finally:
            self._bezig.release()

    @staticmethod
    def _veilig(functie, naam, vangnet=None):
        """Een stap die crasht mag de rest van de zelftest nooit tegenhouden."""
        try:
            return functie()
        except Exception as e:
            res = dict(vangnet) if vangnet else {}
            res.update(gelukt=False, reden=f"{naam} crashte ({type(e).__name__}: {e})")
            return res

    # -- tekst voor Kevin ------------------------------------------------------

    def rapport(self, res):
        return maak_rapport(res, {"tijd": res.get("vorige_tijd")})

    def status_tekst(self):
        runs = self._historie["runs"]
        if not runs:
            return ("Ik heb mezelf nog niet getest. Typ 'zelftest' voor een volledige controle "
                    "of 'zelftest snel' voor een korte.")
        laatste = runs[-1]
        tekst = self.rapport(laatste)
        tekst += "\n(Dit is de laatste zelftest, van " + _fmt_tijd(laatste.get("tijd")) + ".)"
        tekst += "\nLaatste uitslagen: " + ", ".join(
            f"{_fmt_tijd(r.get('tijd'))} {r.get('modus')} {r.get('status')}" for r in runs[-5:])
        return tekst

    # -- op commando ---------------------------------------------------------

    def start_op_commando(self, modus, uitvoer=None):
        """
        Start een zelftest in een eigen thread (zodat het gesprek niet blokkeert) en geeft
        het rapport door aan uitvoer(tekst). Geeft False als er al een zelftest loopt.
        """
        uitvoer = uitvoer or self._print
        if self._bezig.locked():
            uitvoer("Er loopt al een zelftest. Even geduld.")
            return False
        duur = "enkele seconden" if modus == "snel" else "een halve minuut tot enkele minuten"
        uitvoer(f"Ik test mezelf ({modus}). Dat duurt {duur}; ik laat het weten als ik klaar ben.")

        def werk():
            try:
                res = self.voer_uit(modus, bron="commando")
                uitvoer("Er loopt al een zelftest. Even geduld." if res is None else self.rapport(res))
            except Exception as e:                      # vangnet: een thread mag niet stil sterven
                uitvoer(f"De zelftest is mislukt: {type(e).__name__}: {e}")

        threading.Thread(target=werk, daemon=True, name="zelftest-commando").start()
        return True

    # -- automatisch -----------------------------------------------------------

    def _on_bericht(self, data, event_type=None):
        self._laatste_bericht = self._klok()

    def _run_automatisch(self, modus, bron):
        """Opstart- of nachtrun: alleen een bericht (en dus een gsm-melding) bij 'fout'."""
        try:
            res = self.voer_uit(modus, bron=bron)
            if res is None:
                return None
            if res["status"] == "fout" and self.event_bus is not None:
                self.event_bus.publish("layer4_response", {"text": maak_meldingtekst(res)})
            else:
                self._print(f"[ZELFTEST] {bron}: {modus} klaar in {res['duur']:.0f} s, status {res['status']}.")
            return res
        except Exception as e:
            self._print(f"[ZELFTEST] Fout bij de {bron}-run (genegeerd): {e}")
            return None

    def controleer_nacht(self, nu=None):
        """
        Draait de nachtrun als het tijd is: na ZELFTEST_NACHT, nog niet vandaag gedaan en
        Kevin is al een tijdje stil. Geeft het resultaat terug of None.
        """
        if self._nacht is None:
            return None
        nu = nu or datetime.fromtimestamp(self._klok())
        if nu.time() < self._nacht:
            return None
        vandaag = nu.date().isoformat()
        if self._historie.get("laatste_nacht_datum") == vandaag:
            return None
        if self._klok() - self._laatste_bericht < RUSTIG_NA_SECONDEN:
            return None                                  # Kevin is bezig: later opnieuw proberen
        # Eerst noteren, dan pas draaien: zo start een crash of herstart niet nog eens.
        self._historie["laatste_nacht_datum"] = vandaag
        self._bewaar_historie()
        return self._run_automatisch("volledig", "nacht")

    def _achtergrondlus(self):
        if self._opstart_aan:
            if self._stop.wait(self._opstart_vertraging):
                return
            self._run_automatisch("snel", "opstart")
        while not self._stop.wait(60):
            try:
                self.controleer_nacht()
            except Exception as e:
                self._print(f"[ZELFTEST] Fout in de planning (genegeerd): {e}")

    def shutdown(self):
        """Stopt de planning-thread (wordt door de standaard afsluitronde aangeroepen)."""
        self._stop.set()


def init_module(event_bus, sem=None):
    """Standaard module_loader-conventie: init_module(event_bus, sem). 'sem' is niet nodig."""
    instance = Zelftest(event_bus)
    event_bus.publish("module_loaded", {"name": "zelftest"})
    return instance