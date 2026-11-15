# modules/diagnose/controles_robuust.py
#
# Extra controles voor de zelftest (14 november 2026): "is Nova robuust?"
#
# WAT ZIT HIERIN?
#   Alleen losse, kleine, testbare functies. Het MEten (check_* / parse_*), het BEOORDELEN
#   (beoordeel_*) en het RAPPORTEREN (rapport_*) zitten hier; het aansturen (welke controle
#   wanneer draait) zit in zelftest.py.
#
#   Controles die hier wonen (sleutel in het zelftest-resultaat):
#     gebruik    geheugen, threads, open bestanden, uptime en opstarttijd van Nova ZELF
#                (leest /proc/self: de zelftest draait in Nova's eigen proces)
#     herstel    de nieuwste back-up echt TERUGZETTEN in een tijdelijke map en doorlichten:
#                volledige integriteitscontrole, alle tabellen lezen, schema vergelijken met de
#                echte databank
#     meldingen  komen het externe levenssignaal en de wekelijkse testmelding nog aan?
#                (leest data/hartslag_status.json, geschreven door modules/diagnose/watchdog.py)
#     rommel     rare, lege, enorme en willekeurige invoer op Nova gooien (tools/run_rommeltest.py)
#
# PUUR SYMBOLISCH: bestanden lezen, getallen vergelijken, zinnen uit sjablonen. Geen ML.
# Alleen LEZEN: niets hier past code of echte data aan (het terugzetten gebeurt op een KOPIE).
#
# Dit bestand heeft bewust GEEN init_module(): het is een hulpbestand, geen module.
#
# TESTS: tests/test_zelftest_robuust.py

import json
import os
import re
import shutil
import sqlite3
import tempfile
import time
from datetime import datetime
from pathlib import Path

from modules.diagnose.controles import _ANSI, _g, _mv, _tijdsduur, _tool_regel, _verschil

# ----------------------------------------------------------------------------
# Instellingen
# ----------------------------------------------------------------------------

RSS_LETOP_MB = 4000                    # zoveel geheugen is voor Nova ongewoon veel
RSS_GROEI_FACTOR, RSS_GROEI_MB = 1.5, 300      # let op bij 1,5x EN minstens 300 MB meer dan vorige run
THREADS_LETOP = 300
THREADS_GROEI = 50                     # let op bij 50 threads meer EN dubbel zoveel
FDS_LETOP = 800                        # open bestanden/verbindingen (de grens staat meestal op 1024)
HARTSLAG_MIN_WACHT_MINUTEN = 30        # zo lang mag een levenssignaal minimaal uitblijven voor een melding
HARTSLAG_FACTOR = 3                    # ... of dit aantal keer het ping-interval, als dat langer is
MELDINGSTEST_LETOP_DAGEN = 10          # een wekelijkse test die al 10 dagen niet lukte
MELDINGEN_FOUT_OP_RIJ = 3              # zo vaak achter elkaar mislukt = echt een probleem
MAX_VOORBEELDEN = 5

STATUSBESTAND = ("data", "hartslag_status.json")


def _lees_json(pad):
    try:
        with open(pad, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _iso_naar_tijd(tekst):
    try:
        return datetime.fromisoformat(tekst)
    except (TypeError, ValueError):
        return None


# ----------------------------------------------------------------------------
# GEBRUIK (geheugen, threads, bestanden, uptime, opstarttijd)
# ----------------------------------------------------------------------------

def _proc_getal(tekst, sleutel):
    """Haalt het getal achter 'Sleutel:' uit /proc/<pid>/status (bv. 'VmRSS:   123456 kB')."""
    m = re.search(rf"^{sleutel}:\s+(\d+)", tekst, re.MULTILINE)
    return int(m.group(1)) if m else None


def _proces_start(proc_map, proc_root, klok_ticks):
    """Tijdstip (epoch-seconden) waarop dit proces startte, of None."""
    try:
        stat = (Path(proc_map) / "stat").read_text(encoding="utf-8", errors="replace")
        na_naam = stat[stat.rindex(")") + 2:].split()       # velden vanaf nr. 3 (na de naam tussen haakjes)
        start_ticks = int(na_naam[19])                       # veld 22 = starttijd in klokticks sinds opstarten
        boot = None
        for regel in (Path(proc_root) / "stat").read_text(encoding="utf-8").splitlines():
            if regel.startswith("btime "):
                boot = int(regel.split()[1])
        if boot is None:
            return None
        return boot + start_ticks / klok_ticks
    except (OSError, ValueError, IndexError):
        return None


def meet_opstart_s(klaar, proc_root="/proc"):
    """
    Echte opstarttijd: seconden tussen het starten van het proces en het moment ('klaar',
    epoch-seconden) waarop Nova alle modules geladen had. None als dat niet te meten is
    (nog niet klaar, geen /proc, of een onmogelijke uitkomst).
    """
    if klaar is None:
        return None
    try:
        ticks = os.sysconf("SC_CLK_TCK")
    except (AttributeError, ValueError, OSError):
        ticks = 100
    start = _proces_start(Path(proc_root) / "self", proc_root, ticks)
    if start is None or klaar < start:
        return None
    return round(klaar - start, 1)


def check_gebruik(nu=None, opstart_s=None, proc_root="/proc"):
    """
    Meet Nova's eigen proces. 'nu' is een tijdstip (epoch-seconden). Op een systeem zonder /proc
    (Windows, macOS) geven we gewoon 'niet beschikbaar' terug: dat is geen fout.
    """
    res = {"beschikbaar": True, "gelukt": False, "rss_mb": None, "threads": None, "fds": None,
           "uptime_uur": None, "opstart_s": opstart_s, "reden": None}
    proc_map = Path(proc_root) / "self"
    try:
        status = (proc_map / "status").read_text(encoding="utf-8", errors="replace")
    except OSError:
        res["beschikbaar"], res["reden"] = False, "alleen te meten op Linux (/proc ontbreekt)"
        return res
    rss_kb = _proc_getal(status, "VmRSS")
    res["rss_mb"] = round(rss_kb / 1024, 1) if rss_kb is not None else None
    res["threads"] = _proc_getal(status, "Threads")
    try:
        res["fds"] = len(os.listdir(proc_map / "fd"))
    except OSError:
        pass
    try:
        ticks = os.sysconf("SC_CLK_TCK")
    except (AttributeError, ValueError, OSError):
        ticks = 100
    start = _proces_start(proc_map, proc_root, ticks)
    nu = time.time() if nu is None else nu
    if start is not None:
        res["uptime_uur"] = round(max(nu - start, 0) / 3600, 2)
    res["gelukt"] = res["rss_mb"] is not None
    if not res["gelukt"]:
        res["reden"] = "geheugengebruik niet te lezen"
    return res


def _gebruik_te_veel(g):
    """Opmerkingen over absoluut te hoge waarden (los van de vorige run)."""
    uit = []
    if g.get("rss_mb") is not None and g["rss_mb"] >= RSS_LETOP_MB:
        uit.append(f"ik gebruik {_g(g['rss_mb'])} MB geheugen (dat is ongewoon veel)")
    if g.get("threads") is not None and g["threads"] >= THREADS_LETOP:
        uit.append(f"er draaien {g['threads']} threads (dat is ongewoon veel)")
    if g.get("fds") is not None and g["fds"] >= FDS_LETOP:
        uit.append(f"er staan {g['fds']} bestanden/verbindingen open (de grens ligt meestal op 1024)")
    return uit


def _gebruik_groei(g, oud):
    """(opmerkingen, vergelijking) over groei sinds de vorige run van HETZELFDE proces."""
    opmerkingen, vergelijking = [], []
    for veld, naam, min_verschil, eenheid in (("rss_mb", "geheugen", 50, " MB"), ("threads", "threads", 5, ""),
                                              ("fds", "open bestanden", 20, "")):
        nieuw, vroeger = g.get(veld), oud.get(veld)
        if nieuw is None or not vroeger:
            continue
        v = _verschil(naam, vroeger, nieuw, min_verschil)
        if v:
            vergelijking.append(v + eenheid)
    rss, vroeger_rss = g.get("rss_mb"), oud.get("rss_mb")
    if rss and vroeger_rss and rss >= RSS_GROEI_FACTOR * vroeger_rss and rss - vroeger_rss >= RSS_GROEI_MB:
        opmerkingen.append(f"mijn geheugengebruik groeit snel ({_g(vroeger_rss)} → {_g(rss)} MB "
                           "sinds de vorige zelftest; een geheugenlek?)")
    threads, vroeger_threads = g.get("threads"), oud.get("threads")
    if threads and vroeger_threads and threads - vroeger_threads >= THREADS_GROEI and threads >= 2 * vroeger_threads:
        opmerkingen.append(f"het aantal threads groeit ({vroeger_threads} → {threads})")
    return opmerkingen, vergelijking


def beoordeel_gebruik(g, vorig):
    if not g.get("gelukt"):
        return [], [], []
    oud = (vorig.get("gebruik") or {}) if vorig else {}
    opmerkingen, vergelijking = _gebruik_te_veel(g), []
    zelfde_proces = bool(oud.get("gelukt")) and (g.get("uptime_uur") or 0) >= (oud.get("uptime_uur") or 0)
    if zelfde_proces:
        extra, vergelijking = _gebruik_groei(g, oud)
        opmerkingen += extra
    return [], opmerkingen, vergelijking


def rapport_gebruik(g):
    if not g.get("beschikbaar", True):
        return [f"• Gebruik: niet gemeten ({g.get('reden')})."]
    if not g.get("gelukt"):
        return [f"• Gebruik: kon niet meten ({g.get('reden')})."]
    delen = [f"{_g(g['rss_mb'])} MB geheugen"]
    if g.get("threads") is not None:
        delen.append(f"{_mv(g['threads'], 'thread', 'threads')}")
    if g.get("fds") is not None:
        delen.append(f"{_mv(g['fds'], 'open bestand', 'open bestanden')}")
    if g.get("uptime_uur") is not None:
        delen.append(f"draait al {_tijdsduur(g['uptime_uur'])}")
    if g.get("opstart_s") is not None:
        delen.append(f"opstarten duurde {g['opstart_s']:.1f} s")
    return ["• Gebruik: " + ", ".join(delen) + "."]


# ----------------------------------------------------------------------------
# HERSTEL (de back-up echt terugzetten en doorlichten)
# ----------------------------------------------------------------------------

def _tabellen(verbinding):
    rijen = verbinding.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
    return [r[0] for r in rijen]


def _kolommen(verbinding, tabel):
    # De tabelnaam komt uit de databank zelf (sqlite_master) en staat tussen aanhalingstekens.
    return [r[1] for r in verbinding.execute(f'PRAGMA table_info("{tabel}")').fetchall()]  # nosec B608


def _schema_vergelijk(backup_con, live_pad):
    """Vergelijkt tabellen en kolommen met de echte databank. Geeft (gelijk|None, [verschillen])."""
    live = None
    try:
        live = sqlite3.connect(Path(live_pad).resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
        live_tabellen, backup_tabellen = _tabellen(live), _tabellen(backup_con)
        verschillen = [f"tabel '{t}' ontbreekt in de back-up" for t in live_tabellen if t not in backup_tabellen]
        for t in live_tabellen:
            if t in backup_tabellen:
                ontbreekt = [k for k in _kolommen(live, t) if k not in _kolommen(backup_con, t)]
                if ontbreekt:
                    verschillen.append(f"tabel '{t}': kolom {', '.join(ontbreekt)} ontbreekt in de back-up")
        return (not verschillen), verschillen
    except sqlite3.Error:
        return None, []
    finally:
        if live is not None:
            live.close()


def check_herstel(root, tmp_basis=None):
    """
    Zet de nieuwste back-up terug (kopieert hem naar een tijdelijke map), opent hem als een
    gewone databank en stelt hem vragen. Ruimt altijd op. De echte databank wordt alleen gelezen.
    """
    res = {"nodig": False, "gevonden": 0, "nieuwste": None, "gelukt": False, "integriteit": None,
           "tabellen": None, "rijen": None, "schema_gelijk": None, "verschillen": [], "duur": None,
           "reden": None}
    root = Path(root)
    live = root / "data" / "interactions.db"
    res["nodig"] = live.exists()
    backups = root / "data" / "backups"
    try:
        bestanden = sorted(backups.glob("interactions_*.db"), key=lambda p: p.stat().st_mtime,
                           reverse=True) if backups.is_dir() else []
    except OSError as e:
        res["reden"] = f"back-upmap niet te lezen ({type(e).__name__})"
        return res
    res["gevonden"] = len(bestanden)
    if not bestanden:
        return res
    nieuwste = bestanden[0]
    res["nieuwste"] = nieuwste.name
    begin = time.monotonic()
    map_ = None
    verbinding = None
    try:
        grootte = nieuwste.stat().st_size
        basis = str(tmp_basis) if tmp_basis else tempfile.gettempdir()
        if shutil.disk_usage(basis).free < 2 * grootte + 50_000_000:
            res["reden"] = "te weinig schijfruimte om de back-up terug te zetten"
            return res
        map_ = tempfile.mkdtemp(prefix="nova_herstel_", dir=basis)
        doel = Path(map_) / "herstel.db"
        shutil.copyfile(nieuwste, doel)                         # DIT is het terugzetten
        verbinding = sqlite3.connect(str(doel), timeout=10)
        integriteit = verbinding.execute("PRAGMA integrity_check").fetchall()
        res["integriteit"] = integriteit == [("ok",)]
        if not res["integriteit"]:
            res["reden"] = "de integriteitscontrole van de teruggezette back-up faalde"
            return res
        tabellen = _tabellen(verbinding)
        rijen = 0
        for t in tabellen:
            rijen += verbinding.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]  # nosec B608
            try:
                verbinding.execute(f'SELECT * FROM "{t}" ORDER BY rowid DESC LIMIT 3').fetchall()  # nosec B608
            except sqlite3.OperationalError:                      # tabel zonder rowid: gewoon lezen
                verbinding.execute(f'SELECT * FROM "{t}" LIMIT 3').fetchall()  # nosec B608
        res["tabellen"], res["rijen"] = len(tabellen), rijen
        if live.exists():
            res["schema_gelijk"], res["verschillen"] = _schema_vergelijk(verbinding, live)
        res["gelukt"] = True
    except (sqlite3.DatabaseError, OSError) as e:
        res["reden"] = f"terugzetten mislukte ({type(e).__name__}: {e})"
        if isinstance(e, sqlite3.DatabaseError):
            res["integriteit"] = False
    finally:
        if verbinding is not None:
            verbinding.close()
        if map_:
            shutil.rmtree(map_, ignore_errors=True)
        res["duur"] = round(time.monotonic() - begin, 1)
    return res


def beoordeel_herstel(h, vorig):
    fouten, opmerkingen = [], []
    if not h.get("gevonden"):
        return fouten, opmerkingen, []
    if not h.get("gelukt"):
        if h.get("integriteit") is False:
            fouten.append(f"de nieuwste back-up ({h.get('nieuwste')}) laat zich niet terugzetten: {h.get('reden')}")
        else:
            opmerkingen.append(f"de terugzettest kon niet draaien: {h.get('reden')}")
        return fouten, opmerkingen, []
    for verschil in (h.get("verschillen") or [])[:MAX_VOORBEELDEN]:
        opmerkingen.append(f"de back-up wijkt af van de echte databank: {verschil}")
    return fouten, opmerkingen, []


def rapport_herstel(h):
    if not h.get("gevonden"):
        return ["• Terugzettest: geen back-up om terug te zetten."]
    if not h.get("gelukt"):
        return [f"• Terugzettest: MISLUKT voor {h.get('nieuwste')} ({h.get('reden')})."]
    schema = {True: "schema gelijk aan de echte databank", False: "schema WIJKT AF van de echte databank",
              None: "schema niet vergeleken"}[h.get("schema_gelijk")]
    return [f"• Terugzettest: {h['nieuwste']} is teruggezet en doorgelicht: integriteit ok, "
            f"{_mv(h['tabellen'], 'tabel', 'tabellen')}, {_mv(h['rijen'], 'rij', 'rijen')}, {schema} "
            f"({h['duur']:.1f} s)."]


# ----------------------------------------------------------------------------
# MELDINGEN (levenssignaal en wekelijkse testmelding)
# ----------------------------------------------------------------------------

def check_meldingen(root, nu):
    """Leest het statusbestand van modules/diagnose/watchdog.py. 'nu' is een datetime."""
    res = {"gelezen": False, "hartslag": None, "meldingstest": None, "bijgewerkt": None, "nu": nu.isoformat()}
    data = _lees_json(Path(root).joinpath(*STATUSBESTAND))
    if not isinstance(data, dict):
        return res
    res["gelezen"] = True
    res["hartslag"] = data.get("hartslag") if isinstance(data.get("hartslag"), dict) else None
    res["meldingstest"] = data.get("meldingstest") if isinstance(data.get("meldingstest"), dict) else None
    res["bijgewerkt"] = data.get("bijgewerkt")
    return res


def _beoordeel_hartslag(h, nu):
    fouten, opmerkingen = [], []
    if not h or not h.get("aan"):
        return fouten, opmerkingen
    interval = h.get("interval_min") or 10
    wacht_min = max(HARTSLAG_MIN_WACHT_MINUTEN, HARTSLAG_FACTOR * interval)
    if (h.get("fouten_op_rij") or 0) >= MELDINGEN_FOUT_OP_RIJ:
        opmerkingen.append(f"mijn levenssignaal naar buiten komt niet aan ({h['fouten_op_rij']} pogingen op rij "
                           "mislukt); als ik wegval, krijg je dus misschien geen alarm")
        return fouten, opmerkingen
    laatste = _iso_naar_tijd(h.get("laatste_ok"))
    if laatste is None:
        if (h.get("fouten_op_rij") or 0) > 0:
            opmerkingen.append("mijn levenssignaal naar buiten is nog nooit gelukt")
        return fouten, opmerkingen
    minuten = (nu - laatste).total_seconds() / 60
    if minuten > wacht_min:
        opmerkingen.append(f"mijn laatste levenssignaal naar buiten is {minuten / 60:.1f} uur geleden "
                           f"(ik stuur er elke {interval} minuten een)")
    return fouten, opmerkingen


def _beoordeel_meldingstest(m, nu):
    fouten, opmerkingen = [], []
    if not m or not m.get("aan"):
        return fouten, opmerkingen
    op_rij = m.get("fouten_op_rij") or 0
    if op_rij >= MELDINGEN_FOUT_OP_RIJ:
        fouten.append(f"de testmelding naar je gsm mislukt al {op_rij} keer op rij ({m.get('reden') or 'reden onbekend'}); "
                      "een echt alarm zou je dus ook niet bereiken")
    elif op_rij >= 1:
        opmerkingen.append(f"de laatste testmelding naar je gsm mislukte ({m.get('reden') or 'reden onbekend'}); "
                           "ik probeer het zo opnieuw")
    laatste = _iso_naar_tijd(m.get("laatste_ok"))
    if laatste is not None and (nu - laatste).days >= MELDINGSTEST_LETOP_DAGEN and op_rij == 0:
        opmerkingen.append(f"de laatste gelukte testmelding is {(nu - laatste).days} dagen oud (verwacht: wekelijks)")
    return fouten, opmerkingen


def beoordeel_meldingen(m, vorig):
    nu = _iso_naar_tijd(m.get("nu")) or datetime.now()
    f1, o1 = _beoordeel_hartslag(m.get("hartslag"), nu)
    f2, o2 = _beoordeel_meldingstest(m.get("meldingstest"), nu)
    return f1 + f2, o1 + o2, []


def _leeftijd_tekst(iso, nu):
    tijd = _iso_naar_tijd(iso)
    if tijd is None:
        return "nog nooit"
    minuten = (nu - tijd).total_seconds() / 60
    if minuten < 90:
        return f"{max(minuten, 0):.0f} minuten geleden"
    if minuten < 48 * 60:
        return f"{minuten / 60:.0f} uur geleden"
    return f"{minuten / 1440:.0f} dagen geleden"


def rapport_meldingen(m):
    if not m.get("gelezen"):
        return ["• Meldingen: de watchdog-module heeft nog geen statusbestand gemaakt (is hij geladen?)."]
    nu = _iso_naar_tijd(m.get("nu")) or datetime.now()
    h, t = m.get("hartslag"), m.get("meldingstest")
    regels = []
    if h and h.get("aan"):
        regels.append(f"levenssignaal naar buiten elke {h.get('interval_min')} minuten, "
                      f"laatste gelukt: {_leeftijd_tekst(h.get('laatste_ok'), nu)}")
    else:
        regels.append("levenssignaal naar buiten staat UIT (zet NOVA_HARTSLAG_URL in .env om te horen als ik helemaal wegval)")
    if t and t.get("aan"):
        regels.append(f"testmelding naar je gsm ({t.get('schema')}), laatste gelukt: "
                      f"{_leeftijd_tekst(t.get('laatste_ok'), nu)}")
    else:
        regels.append("wekelijkse testmelding staat UIT (zet NOVA_MELDINGSTEST in .env)")
    return ["• Meldingen: " + "; ".join(regels) + "."]


# ----------------------------------------------------------------------------
# ROMMEL (rare invoer)
# ----------------------------------------------------------------------------

_ROMMEL_REGEL = re.compile(
    r"ROMMELTEST: (\d+) invoeren, (\d+) crashes, (\d+) te traag, mediaan (\d+) ms, langste (\d+) ms")


def _rommel_leeg():
    return {"beschikbaar": True, "gelukt": False, "aantal": 0, "crashes": 0, "traag": 0,
            "mediaan_ms": None, "langste_ms": None, "voorbeelden": [], "duur": None, "reden": None}


def parse_rommel(uitvoer, returncode, te_laat=False):
    """Ontleedt de uitvoer van tools/run_rommeltest.py (de laatste 'ROMMELTEST:'-regel + voorbeelden)."""
    res = _rommel_leeg()
    if te_laat:
        res["reden"] = "tijdslimiet overschreden (blijft een invoer hangen?)"
        return res
    if returncode == 127:
        res["reden"] = "de rommel-invoertest kon niet gestart worden"
        return res
    sectie = None
    for regel in _ANSI.sub("", uitvoer or "").splitlines():
        regel = regel.rstrip()
        m = _ROMMEL_REGEL.search(regel)
        if m:
            res["aantal"], res["crashes"], res["traag"], res["mediaan_ms"], res["langste_ms"] = \
                (int(x) for x in m.groups())
            res["gelukt"] = True
        if regel.startswith("--- CRASHES"):
            sectie = "crash"
        elif regel.startswith("--- TE TRAAG"):
            sectie = "traag"
        elif regel.startswith("ROMMELTEST"):
            sectie = None
        elif sectie and regel.lstrip().startswith("[") and len(res["voorbeelden"]) < MAX_VOORBEELDEN:
            res["voorbeelden"].append((sectie, regel.strip()))
    if not res["gelukt"]:
        res["reden"] = ("de test stopte zonder uitslag (veiligheidscontrole of crash van de test zelf)"
                        if returncode == 2 else "geen resultaat gevonden in de uitvoer")
    return res


def _voorbeeld(res, soort):
    for s, tekst in res.get("voorbeelden") or []:
        if s == soort:
            return tekst
    return None


def beoordeel_rommel(r, vorig):
    fouten, opmerkingen, vergelijking = [], [], []
    if not r.get("gelukt"):
        opmerkingen.append(f"de rommel-invoertest kon niet draaien: {r.get('reden')}")
        return fouten, opmerkingen, vergelijking
    if r["traag"]:
        voorbeeld = _voorbeeld(r, "traag")
        fouten.append(f"{_mv(r['traag'], 'rare invoer hield', 'rare invoeren hielden')} me langer dan de tijdslimiet "
                      f"bezig (zo'n bericht kan me laten vastlopen){': ' + voorbeeld if voorbeeld else ''}")
    if r["crashes"]:
        voorbeeld = _voorbeeld(r, "crash")
        opmerkingen.append(f"{r['crashes']} van de {r['aantal']} rare invoeren veroorzaakten een fout"
                           f"{': ' + voorbeeld if voorbeeld else ''}")
    oud = (vorig.get("rommel") or {}) if vorig else {}
    if oud.get("gelukt"):
        v = _verschil("antwoordtijd", oud.get("mediaan_ms"), r.get("mediaan_ms"), 20)
        if v:
            vergelijking.append(v + " ms")
    return fouten, opmerkingen, vergelijking


def rapport_rommel(r):
    regel = _tool_regel("Rommel-invoertest", r)
    if regel:
        return [regel]
    tekst = (f"• Rommel-invoertest: {r['aantal']} rare invoeren (leeg, enorm, vreemde tekens, willekeurig): "
             f"{_mv(r['crashes'], 'crash', 'crashes')}, {_mv(r['traag'], 'te traag', 'te traag')}; "
             f"mediaan {r['mediaan_ms']} ms per antwoord, langste {r['langste_ms']} ms")
    if r.get("duur") is not None:
        tekst += f" ({r['duur']:.0f} s)"
    return [tekst + "."]


# ----------------------------------------------------------------------------
# Tabellen voor zelftest.py
# ----------------------------------------------------------------------------

BEOORDELAARS = {
    "gebruik": beoordeel_gebruik, "herstel": beoordeel_herstel,
    "meldingen": beoordeel_meldingen, "rommel": beoordeel_rommel,
}

RAPPORTEERDERS = {
    "gebruik": rapport_gebruik, "herstel": rapport_herstel,
    "meldingen": rapport_meldingen, "rommel": rapport_rommel,
}