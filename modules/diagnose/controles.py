# modules/diagnose/controles.py
#
# Extra controles voor de zelftest (14 november 2026): de "volledige diagnose".
#
# WAT ZIT HIERIN?
#   Alleen losse, kleine, testbare functies. Het BESTAAN van een controle (een
#   programma starten, een map lezen) en het BEOORDELEN van de uitkomst zitten
#   hier; het aansturen (welke controle draait wanneer) zit in zelftest.py.
#
#   Controles die hier wonen (sleutel in het zelftest-resultaat):
#     backup        is er een recente, leesbare back-up van de databank
#     schijf        hoeveel schijfruimte is er nog, hoe groot zijn data en logs
#     modules       zijn alle modules op schijf ook echt geladen
#     consistentie  kloppen identity.json (schema) en concepts.json (structuur)
#     docs          komt het modules-overzicht overeen met wat er op schijf staat
#     benchmark     taalbegrip (taalbenchmark) en rooktest (vaste vragen, niveau 3)
#     dekking       welk deel van de code raken de tests (coverage)
#     dode_code     code die nergens gebruikt wordt (vulture)
#     beveiliging   onveilige patronen in de code (bandit)
#     pakketten     bekende kwetsbaarheden in geinstalleerde pakketten (pip-audit)
#
#   Elke controle heeft: een functie die meet (check_* of parse_*), een
#   beoordeel_*-functie die (fouten, opmerkingen, vergelijking) teruggeeft en een
#   rapport_*-functie die regels voor de console bouwt.
#
# PUUR SYMBOLISCH: bestanden lezen, programma-uitvoer ontleden, getallen
# vergelijken, zinnen uit sjablonen bouwen. Geen ML. Alleen LEZEN: niets hier
# past code of data aan.
#
# Dit bestand heeft bewust GEEN init_module(): het is een hulpbestand, geen module.
# module_loader.py importeert het wel, maar slaat het over omdat init_module ontbreekt.
#
# TESTS: tests/test_zelftest_controles.py

import ast
import json
import os
import re
import shutil
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path

# ----------------------------------------------------------------------------
# Instellingen
# ----------------------------------------------------------------------------

BACKUP_LETOP_UREN = 8            # Nova maakt elke 6 uur een back-up (core/memory.py)
BACKUP_FOUT_UREN = 72            # pas na 3 dagen is het echt een probleem (en een gsm-melding)
SCHIJF_FOUT = (1.0, 2.0)         # minder dan 1 GB OF minder dan 2 procent vrij
SCHIJF_LETOP = (5.0, 10.0)       # minder dan 5 GB OF minder dan 10 procent vrij
LOGS_LETOP_MB = 200
MAX_VOORBEELDEN = 5

# Modules die module_loader.py bewust NIET in de gewone laadlus laadt (ze krijgen
# een eigen plek in de loader, zijn speciaal of staan in de groep "debug").
BEWUST_NIET_AUTOMATISCH = {
    "topic_suggestions", "emergence_engine", "client_bridge", "activity_detector",
    "focus_detector", "presence_detector", "variant_feedback_logger",
}
BEWUST_NIET_GROEPEN = {"debug"}

DOC_PAD = ("docs", "Andere", "nova_modules_overview.md")

# Parameters die elke signaalhandler of context-manager verplicht heeft, ook als je ze
# niet gebruikt: vulture meldt ze als "unused variable", maar het is geen dode code.
VULTURE_NEGEER_NAMEN = {"frame", "signum", "exc_type", "exc_val", "exc_tb"}

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


# ----------------------------------------------------------------------------
# Kleine hulpfuncties
# ----------------------------------------------------------------------------

def _mv(n, enkelvoud, meervoud):
    """1 -> enkelvoud, anders meervoud. Geeft '3 tests' / '1 test'."""
    return f"{n} {enkelvoud if n == 1 else meervoud}"


def _g(getal):
    """Getal zonder overbodig '.0' (78.0 -> '78', 78.4 -> '78.4')."""
    return format(getal, "g") if isinstance(getal, (int, float)) else str(getal)


def _verschil(naam, oud, nieuw, min_verschil=0):
    """'naam oud -> nieuw' als de getallen genoeg verschillen, anders None."""
    if not isinstance(oud, (int, float)) or not isinstance(nieuw, (int, float)):
        return None
    if nieuw == oud or abs(nieuw - oud) < min_verschil:
        return None
    return f"{naam} {_g(oud)} → {_g(nieuw)}"


def _json_uit(tekst):
    """Haalt een JSON-object uit programma-uitvoer (negeert tekst voor de eerste '{')."""
    tekst = tekst or ""
    begin = tekst.find("{")
    if begin < 0:
        raise ValueError("geen JSON gevonden")
    return json.loads(tekst[begin:])


def _tool_probleem(naam, tool, d, neutraal_bij_mislukken=False):
    """Een opmerking als een extern programma ontbreekt of niet draaide; anders None."""
    if not d.get("beschikbaar", True):
        return f"{tool} is niet geïnstalleerd (zet het in requirements.txt)"
    if not d.get("gelukt"):
        return None if neutraal_bij_mislukken else f"{naam} kon niet draaien: {d.get('reden')}"
    return None


def _tool_regel(naam, d):
    """De rapportregel voor een controle die niet kon draaien, of None als hij wel lukte."""
    if not d.get("beschikbaar", True):
        return f"• {naam}: niet gecontroleerd ({d.get('reden') or 'niet geïnstalleerd'})."
    if not d.get("gelukt"):
        return f"• {naam}: kon niet draaien ({d.get('reden')})."
    return None


def _tijdsduur(uren):
    if uren < 1:
        return "minder dan een uur"
    if uren < 48:
        return f"{uren:g} uur"
    return f"{uren / 24:.0f} dagen"


# ----------------------------------------------------------------------------
# BACKUP
# ----------------------------------------------------------------------------

def _controleer_backup_db(pad):
    """
    Opent een back-up ALLEEN-LEZEN en doet 'PRAGMA quick_check'. Geeft (db_ok, rijen):
    db_ok is True/False, of None als we het niet konden beoordelen.
    """
    verbinding = None
    try:
        uri = Path(pad).resolve().as_uri() + "?mode=ro&immutable=1"
        verbinding = sqlite3.connect(uri, uri=True, timeout=5)
        rijen = verbinding.execute("PRAGMA quick_check").fetchall()
        if rijen != [("ok",)]:
            return False, None
        try:
            return True, verbinding.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
        except sqlite3.DatabaseError:
            return True, None                      # geen 'interactions'-tabel: wel een geldige databank
    except sqlite3.OperationalError:
        return None, None
    except sqlite3.DatabaseError:
        return False, None
    finally:
        if verbinding is not None:
            verbinding.close()


def check_backup(root, nu):
    """
    Staat er een recente back-up in data/backups/ en is die leesbaar? Een back-up die
    nooit getest wordt, is geen zekerheid. Alleen lezen.
    """
    res = {"nodig": False, "gevonden": 0, "nieuwste": None, "leeftijd_uur": None,
           "db_ok": None, "rijen": None, "reden": None}
    root = Path(root)
    res["nodig"] = (root / "data" / "interactions.db").exists()
    backups = root / "data" / "backups"
    bestanden = []
    if backups.is_dir():
        try:
            bestanden = sorted(backups.glob("interactions_*.db"),
                               key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError as e:
            res["reden"] = f"back-upmap niet te lezen ({type(e).__name__})"
    res["gevonden"] = len(bestanden)
    if not bestanden:
        return res
    nieuwste = bestanden[0]
    uren = (nu - datetime.fromtimestamp(nieuwste.stat().st_mtime)).total_seconds() / 3600
    res["nieuwste"] = nieuwste.name
    res["leeftijd_uur"] = round(max(uren, 0.0), 1)
    res["db_ok"], res["rijen"] = _controleer_backup_db(nieuwste)
    return res


def beoordeel_backup(b, vorig):
    fouten, opmerkingen = [], []
    if not b.get("nodig") and not b.get("gevonden"):
        return fouten, opmerkingen, []
    if not b.get("gevonden"):
        opmerkingen.append("er is nog geen enkele back-up van de databank "
                           "(de back-uptimer start pas 6 uur na het opstarten van Nova)")
        return fouten, opmerkingen, []
    uren = b.get("leeftijd_uur") or 0
    if b.get("db_ok") is False:
        fouten.append(f"de nieuwste back-up ({b.get('nieuwste')}) is kapot")
    if uren > BACKUP_FOUT_UREN:
        fouten.append(f"de nieuwste back-up is {_tijdsduur(uren)} oud (verwacht: elke 6 uur)")
    elif uren > BACKUP_LETOP_UREN:
        opmerkingen.append(f"de nieuwste back-up is {_tijdsduur(uren)} oud (verwacht: elke 6 uur)")
    return fouten, opmerkingen, []


def rapport_backup(b):
    if not b.get("nodig") and not b.get("gevonden"):
        return ["• Back-up: er is geen databank, dus ook geen back-up nodig."]
    if not b.get("gevonden"):
        return ["• Back-up: GEEN enkele back-up gevonden."]
    inhoud = {True: "gecontroleerd en leesbaar", False: "KAPOT", None: "niet gecontroleerd"}[b.get("db_ok")]
    if b.get("db_ok") and b.get("rijen") is not None:
        inhoud += f" ({_mv(b['rijen'], 'rij', 'rijen')})"
    return [f"• Back-up: {b['gevonden']} bewaard, de nieuwste is {_tijdsduur(b.get('leeftijd_uur') or 0)} "
            f"oud ({b.get('nieuwste')}); {inhoud}."]


# ----------------------------------------------------------------------------
# SCHIJF EN LOGS
# ----------------------------------------------------------------------------

def _map_mb(pad, sla_over=()):
    """Totale grootte van een map in MB (volgt geen symlinks, slaat genoemde submappen over)."""
    totaal = 0
    for dirpad, dirnamen, bestanden in os.walk(str(pad), followlinks=False):
        dirnamen[:] = [d for d in dirnamen if d not in sla_over]
        for naam in bestanden:
            try:
                totaal += os.lstat(os.path.join(dirpad, naam)).st_size
            except OSError:
                continue
    return round(totaal / 1_000_000, 1)


def check_schijf(root):
    """Vrije schijfruimte en de grootte van data/, back-ups en logs."""
    res = {"gelukt": False, "vrij_gb": None, "vrij_procent": None,
           "data_mb": None, "backups_mb": None, "logs_mb": None, "reden": None}
    root = Path(root)
    try:
        gebruik = shutil.disk_usage(str(root))
        res["vrij_gb"] = round(gebruik.free / 1e9, 1)
        res["vrij_procent"] = round(100 * gebruik.free / gebruik.total, 1) if gebruik.total else None
        res["data_mb"] = _map_mb(root / "data", sla_over=("backups",))
        res["backups_mb"] = _map_mb(root / "data" / "backups")
        res["logs_mb"] = _map_mb(root / "logs")
        res["gelukt"] = True
    except OSError as e:
        res["reden"] = f"schijf niet te meten ({type(e).__name__})"
    return res


def _schijf_niveau(vrij_gb, vrij_procent):
    for niveau, (gb, procent) in (("fout", SCHIJF_FOUT), ("let_op", SCHIJF_LETOP)):
        if vrij_gb < gb or (vrij_procent is not None and vrij_procent < procent):
            return niveau
    return None


def beoordeel_schijf(s, vorig):
    fouten, opmerkingen, vergelijking = [], [], []
    if not s.get("gelukt"):
        return fouten, opmerkingen, vergelijking
    niveau = _schijf_niveau(s["vrij_gb"], s["vrij_procent"])
    zin = f"nog maar {_g(s['vrij_gb'])} GB vrij op de schijf ({_g(s['vrij_procent'])}%)"
    if niveau == "fout":
        fouten.append(zin)
    elif niveau == "let_op":
        opmerkingen.append(zin)
    if (s.get("logs_mb") or 0) >= LOGS_LETOP_MB:
        opmerkingen.append(f"de logs nemen {s['logs_mb']:.0f} MB in")
    vs = vorig.get("schijf") or {}
    for tekst in (_verschil("vrije ruimte (GB)", vs.get("vrij_gb"), s["vrij_gb"], 1.0),
                  _verschil("data (MB)", vs.get("data_mb"), s["data_mb"], 10.0),
                  _verschil("back-ups (MB)", vs.get("backups_mb"), s["backups_mb"], 10.0)):
        if tekst:
            vergelijking.append(tekst)
    return fouten, opmerkingen, vergelijking


def rapport_schijf(s):
    if not s.get("gelukt"):
        return [f"• Schijf: kon niet gemeten worden ({s.get('reden')})."]
    return [f"• Schijf: {_g(s['vrij_gb'])} GB vrij ({_g(s['vrij_procent'])}%); data {_g(s['data_mb'])} MB, "
            f"back-ups {_g(s['backups_mb'])} MB, logs {_g(s['logs_mb'])} MB."]


# ----------------------------------------------------------------------------
# MODULES
# ----------------------------------------------------------------------------

def _heeft_init_module(pad):
    try:
        boom = ast.parse(Path(pad).read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return False
    return any(isinstance(n, ast.FunctionDef) and n.name == "init_module" for n in boom.body)


def modules_op_schijf(root):
    """Alle modules/<groep>/<naam>.py met een init_module(): {naam: 'groep/naam.py'}."""
    gevonden = {}
    basis = Path(root) / "modules"
    if not basis.is_dir():
        return gevonden
    for groep in sorted(p for p in basis.iterdir() if p.is_dir() and (p / "__init__.py").exists()):
        for bestand in sorted(groep.glob("*.py")):
            if bestand.stem != "__init__" and _heeft_init_module(bestand):
                gevonden[bestand.stem] = f"{groep.name}/{bestand.name}"
    return gevonden


def verwachte_modules(root):
    """De modules die module_loader.py in zijn gewone laadlus zelf laadt."""
    return {naam: pad for naam, pad in modules_op_schijf(root).items()
            if naam not in BEWUST_NIET_AUTOMATISCH and pad.split("/")[0] not in BEWUST_NIET_GROEPEN}


def check_modules(bus, root):
    """Zijn alle modules op schijf ook geladen? 'bus.modules' is wat de loader registreerde."""
    res = {"gelukt": False, "verwacht": 0, "geladen": 0, "ontbreekt": [], "reden": None}
    geladen = getattr(bus, "modules", None)
    if not isinstance(geladen, dict) or not geladen:
        res["reden"] = "geen zicht op de geladen modules"
        return res
    verwacht = verwachte_modules(root)
    res.update(gelukt=True, verwacht=len(verwacht), geladen=len(geladen),
               ontbreekt=sorted(pad for naam, pad in verwacht.items() if naam not in geladen))
    return res


def beoordeel_modules(m, vorig):
    opmerkingen, vergelijking = [], []
    if not m.get("gelukt"):
        return [], opmerkingen, vergelijking
    if m.get("ontbreekt"):
        n = len(m["ontbreekt"])
        opmerkingen.append(f"{_mv(n, 'module staat', 'modules staan')} op schijf maar {'is' if n == 1 else 'zijn'} "
                           f"niet geladen: {', '.join(m['ontbreekt'][:MAX_VOORBEELDEN])}")
    tekst = _verschil("geladen modules", (vorig.get("modules") or {}).get("geladen"), m["geladen"])
    if tekst:
        vergelijking.append(tekst)
    return [], opmerkingen, vergelijking


def rapport_modules(m):
    if not m.get("gelukt"):
        return [f"• Modules: niet gecontroleerd ({m.get('reden')})."]
    tekst = f"• Modules: {m['geladen']} geladen, alle {m['verwacht']} verwachte modules van schijf aanwezig"
    if m.get("ontbreekt"):
        tekst = (f"• Modules: {m['geladen']} geladen, maar {len(m['ontbreekt'])} van de {m['verwacht']} "
                 f"verwachte ontbreken: {', '.join(m['ontbreekt'][:MAX_VOORBEELDEN])}")
    return [tekst + "."]


# ----------------------------------------------------------------------------
# CONSISTENTIE (identity.json en concepts.json)
# ----------------------------------------------------------------------------

def _check_identity(root):
    blauwdruk = Path(root) / "identity" / "blueprint"
    identiteit, schema = blauwdruk / "identity.json", blauwdruk / "schema.json"
    if not (identiteit.is_file() and schema.is_file()):
        return "niet aanwezig"
    try:
        from jsonschema import validate, ValidationError
    except ImportError:
        return "niet gecontroleerd (jsonschema ontbreekt)"
    try:
        with open(identiteit, encoding="utf-8") as f1, open(schema, encoding="utf-8") as f2:
            validate(instance=json.load(f1), schema=json.load(f2))
    except ValidationError as e:
        plek = "/".join(str(x) for x in e.path)
        return f"ongeldig: {e.message}" + (f" (bij {plek})" if plek else "")
    except (OSError, ValueError) as e:
        return f"niet te lezen ({type(e).__name__})"
    return "ok"


def _analyseer_concepten(data):
    """Telt structuurfouten, dubbele sense_id's en relaties naar onbekende concepten."""
    kapot, sense_ids, relaties, onbekend = [], Counter(), 0, 0
    sleutels = {str(k).lower() for k in data}
    for woord, concept in data.items():
        senses = concept.get("senses") if isinstance(concept, dict) else None
        if not isinstance(senses, list):
            kapot.append(str(woord))
            continue
        for sense in senses:
            if not isinstance(sense, dict):
                kapot.append(str(woord))
                continue
            if sense.get("sense_id"):
                sense_ids[sense["sense_id"]] += 1
            for rel in sense.get("relations") or []:
                relaties += 1
                doel = rel.get("target") if isinstance(rel, dict) else None
                if str(doel).lower() not in sleutels:
                    onbekend += 1
    dubbel = sorted(sid for sid, aantal in sense_ids.items() if aantal > 1)
    return kapot, dubbel, relaties, onbekend


def check_consistentie(root):
    """Klopt identity.json met zijn schema, en heeft elk concept in concepts.json een geldige vorm?"""
    res = {"identity": _check_identity(root), "concepten": None, "kapot_aantal": 0, "kapot": [],
           "dubbel_aantal": 0, "dubbel": [], "relaties": 0, "onbekend_doel": 0, "reden": None}
    pad = Path(root) / "data" / "concepts.json"
    if not pad.is_file():
        return res
    try:
        with open(pad, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        res["reden"] = f"concepts.json niet te lezen ({type(e).__name__})"
        return res
    if not isinstance(data, dict):
        res["reden"] = "concepts.json is geen woordenboek"
        return res
    kapot, dubbel, relaties, onbekend = _analyseer_concepten(data)
    res.update(concepten=len(data), kapot_aantal=len(kapot), kapot=kapot[:MAX_VOORBEELDEN],
               dubbel_aantal=len(dubbel), dubbel=dubbel[:MAX_VOORBEELDEN],
               relaties=relaties, onbekend_doel=onbekend)
    return res


def beoordeel_consistentie(c, vorig):
    fouten, opmerkingen, vergelijking = [], [], []
    if str(c.get("identity", "")).startswith("ongeldig"):
        fouten.append(f"identity.json klopt niet met zijn schema ({c['identity'].split(': ', 1)[-1]})")
    if c.get("kapot_aantal"):
        opmerkingen.append(f"{_mv(c['kapot_aantal'], 'concept heeft', 'concepten hebben')} een kapotte opbouw: "
                           f"{', '.join(c['kapot'])}")
    if c.get("dubbel_aantal"):
        opmerkingen.append(f"{_mv(c['dubbel_aantal'], 'sense_id komt', 'sense_ids komen')} dubbel voor: "
                           f"{', '.join(c['dubbel'])}")
    vc = vorig.get("consistentie") or {}
    for tekst in (_verschil("concepten", vc.get("concepten"), c.get("concepten")),
                  _verschil("relaties naar onbekende woorden", vc.get("onbekend_doel"), c.get("onbekend_doel"))):
        if tekst:
            vergelijking.append(tekst)
    return fouten, opmerkingen, vergelijking


def rapport_consistentie(c):
    regels = [f"• Identiteit: {c.get('identity')}."]
    if c.get("reden"):
        regels.append(f"• Concepten: {c['reden']}.")
    elif c.get("concepten") is not None:
        tekst = (f"• Concepten: {c['concepten']} concepten en {c['relaties']} relaties; "
                 f"{c['kapot_aantal']} kapot, {c['dubbel_aantal']} dubbele sense_id's, "
                 f"{c['onbekend_doel']} relaties naar een woord dat (nog) geen eigen concept is")
        regels.append(tekst + ".")
    return regels


# ----------------------------------------------------------------------------
# DOCUMENTATIE-SYNC (docs/Andere/nova_modules_overview.md)
# ----------------------------------------------------------------------------

def lees_modules_overzicht(pad):
    """Rijen uit de tabel: [{'file', 'pad', 'status'}]. Kopregel en scheidingslijn vallen weg."""
    rijen = []
    try:
        regels = Path(pad).read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError):
        return rijen
    for regel in regels:
        if not regel.startswith("|"):
            continue
        cellen = [c.strip() for c in regel.strip().strip("|").split("|")]
        if len(cellen) < 7 or cellen[0] in ("#", "") or set(cellen[0]) <= set("-: "):
            continue
        rijen.append({"file": cellen[3], "pad": cellen[4], "status": cellen[-1]})
    return rijen


def check_docs(root):
    """Komt het modules-overzicht overeen met de schijf? Alleen lezen."""
    res = {"aanwezig": False, "gebouwd": 0, "ontbreekt_op_schijf": [], "onbekende_status": [],
           "niet_beschreven_aantal": 0, "niet_beschreven": []}
    root = Path(root)
    doc = root.joinpath(*DOC_PAD)
    if not doc.is_file():
        return res
    res["aanwezig"] = True
    rijen = lees_modules_overzicht(doc)
    for rij in rijen:
        status = rij["status"].lower()
        if status == "gebouwd":
            res["gebouwd"] += 1
            if not (root / rij["pad"].strip().strip("/") / rij["file"]).is_file():
                res["ontbreekt_op_schijf"].append(f"{rij['pad'].strip()}{rij['file']}")
        elif status != "nog niet gebouwd":
            res["onbekende_status"].append(f"{rij['file']} ({rij['status']})")
    beschreven = {rij["file"] for rij in rijen}
    zonder = sorted(pad for naam, pad in modules_op_schijf(root).items() if f"{naam}.py" not in beschreven)
    res.update(niet_beschreven_aantal=len(zonder), niet_beschreven=zonder[:MAX_VOORBEELDEN])
    res["ontbreekt_op_schijf"] = res["ontbreekt_op_schijf"][:MAX_VOORBEELDEN]
    res["onbekende_status"] = res["onbekende_status"][:MAX_VOORBEELDEN]
    return res


def beoordeel_docs(d, vorig):
    opmerkingen, vergelijking = [], []
    if not d.get("aanwezig"):
        return [], opmerkingen, vergelijking
    if d.get("ontbreekt_op_schijf"):
        opmerkingen.append("het modules-overzicht zegt 'Gebouwd' maar het bestand staat niet op schijf: "
                           + ", ".join(d["ontbreekt_op_schijf"]))
    if d.get("onbekende_status"):
        opmerkingen.append("een rij in het modules-overzicht heeft een onbekende status: "
                           + ", ".join(d["onbekende_status"]))
    oud = (vorig.get("docs") or {}).get("niet_beschreven_aantal")
    nieuw = d.get("niet_beschreven_aantal", 0)
    if isinstance(oud, int) and nieuw > oud:
        opmerkingen.append(f"{_mv(nieuw - oud, 'nieuwe module staat', 'nieuwe modules staan')} nog niet "
                           f"in het modules-overzicht")
    tekst = _verschil("modules zonder beschrijving", oud, nieuw)
    return [], opmerkingen, [tekst] if tekst else vergelijking


def rapport_docs(d):
    if not d.get("aanwezig"):
        return ["• Documentatie: het modules-overzicht is niet gevonden."]
    tekst = (f"• Documentatie: {_mv(d['gebouwd'], 'rij', 'rijen')} met 'Gebouwd' in het modules-overzicht, "
             f"{len(d['ontbreekt_op_schijf'])} zonder bestand op schijf; "
             f"{_mv(d['niet_beschreven_aantal'], 'module staat', 'modules staan')} er nog niet in")
    if d.get("onbekende_status"):
        tekst += f"; onbekende status bij {', '.join(d['onbekende_status'])}"
    return [tekst + "."]


# ----------------------------------------------------------------------------
# BENCHMARK (taalbegrip en rooktest)
# ----------------------------------------------------------------------------

_BM_TOTAAL = re.compile(r"^TOTAAL\s+(\d+)%\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$")
_BM_ROUTER = re.compile(r"Router begreep (\d+)/(\d+) zinnen")


def _bm_leeg():
    return {"beschikbaar": True, "gelukt": False, "goed": 0, "fout": 0, "crash": 0, "niet_meetbaar": 0,
            "onterecht": 0, "router_begrepen": None, "router_totaal": None, "duur": None, "reden": None}


def parse_benchmark(uitvoer, returncode, te_laat=False):
    """
    Ontleedt de uitvoer van tools/run_benchmark.py: de TOTAAL-regel, het aantal onterechte
    antwoorden (stellig antwoord op iets wat ze niet kan weten) en, bij de taalbenchmark,
    hoeveel zinnen de router begreep.
    """
    res = _bm_leeg()
    if te_laat:
        res["reden"] = "tijdslimiet overschreden"
        return res
    if returncode == 127:
        res["reden"] = "de benchmark kon niet gestart worden"
        return res
    in_onterecht = False
    for regel in _ANSI.sub("", uitvoer or "").splitlines():
        regel = regel.rstrip()
        m = _BM_TOTAAL.match(regel)
        if m:
            res["goed"], res["fout"], res["crash"], res["niet_meetbaar"] = (int(x) for x in m.groups()[1:])
            res["gelukt"] = True
        m = _BM_ROUTER.search(regel)
        if m:
            res["router_begrepen"], res["router_totaal"] = int(m.group(1)), int(m.group(2))
        if regel.startswith("---"):
            in_onterecht = regel.startswith("--- ONTERECHTE ANTWOORDEN")
        elif in_onterecht and regel.lstrip().startswith("["):
            res["onterecht"] += 1
    if not res["gelukt"]:
        res["reden"] = "geen resultaat gevonden in de uitvoer (is de benchmark gecrasht?)"
    return res


def _bm_procent(deel):
    totaal = (deel.get("goed") or 0) + (deel.get("fout") or 0) + (deel.get("crash") or 0)
    return 100.0 * deel["goed"] / totaal if totaal and deel.get("goed") is not None else None


def _bm_router_procent(deel):
    if deel.get("router_totaal"):
        return 100.0 * deel["router_begrepen"] / deel["router_totaal"]
    return None


def _bm_vergelijk(sleutel, naam, deel, oud):
    """(opmerkingen, vergelijking) door dit deel met de vorige run te vergelijken."""
    opmerkingen, vergelijking = [], []
    metingen = [("score", _bm_procent(deel), _bm_procent(oud) if oud.get("gelukt") else None,
                 2.0 if sleutel == "taal" else 3.0)]
    if sleutel == "taal":
        metingen.append(("taalbegrip", _bm_router_procent(deel),
                         _bm_router_procent(oud) if oud.get("gelukt") else None, 1.0))
    for label, nieuw, vroeger, drempel in metingen:
        if nieuw is None or vroeger is None:
            continue
        if vroeger - nieuw >= drempel:
            opmerkingen.append(f"{naam}: {label} daalde van {vroeger:.0f}% naar {nieuw:.0f}%")
        if abs(nieuw - vroeger) >= 0.5:
            vergelijking.append(f"{naam} {label} {vroeger:.0f}% → {nieuw:.0f}%")
    if (sleutel == "rook" and oud.get("duur") and deel.get("duur")
            and deel["duur"] > 3 * oud["duur"] and deel["duur"] - oud["duur"] >= 10):
        opmerkingen.append(f"{naam} duurde {deel['duur']:.0f} s tegenover {oud['duur']:.0f} s vorige keer")
    return opmerkingen, vergelijking


def _beoordeel_bm_deel(sleutel, naam, deel, oud):
    fouten, opmerkingen, vergelijking = [], [], []
    if not deel.get("beschikbaar", True):
        return fouten, opmerkingen, vergelijking
    if not deel.get("gelukt"):
        opmerkingen.append(f"{naam} kon niet draaien: {deel.get('reden')}")
        return fouten, opmerkingen, vergelijking
    if deel.get("onterecht"):
        fouten.append(f"{naam}: {_mv(deel['onterecht'], 'onterecht antwoord', 'onterechte antwoorden')} "
                      f"(ze antwoordde stellig terwijl ze het niet kon weten)")
    if deel.get("crash"):
        fouten.append(f"{naam}: {_mv(deel['crash'], 'vraag liet', 'vragen lieten')} een module crashen")
    if sleutel == "rook" and deel.get("fout"):
        totaal = deel["goed"] + deel["fout"] + deel["crash"]
        opmerkingen.append(f"{naam}: {deel['fout']} van de {totaal} vaste vragen wordt niet goed beantwoord")
    o, v = _bm_vergelijk(sleutel, naam, deel, oud)
    return fouten, opmerkingen + o, vergelijking + v


def beoordeel_benchmark(b, vorig):
    fouten, opmerkingen, vergelijking = [], [], []
    vb = vorig.get("benchmark") or {}
    for sleutel, naam in (("taal", "taalbenchmark"), ("rook", "rooktest")):
        if b.get(sleutel) is None:
            continue
        f, o, v = _beoordeel_bm_deel(sleutel, naam, b[sleutel], vb.get(sleutel) or {})
        fouten += f
        opmerkingen += o
        vergelijking += v
    return fouten, opmerkingen, vergelijking


def _rapport_bm_taal(t):
    regel = _tool_regel("Taalbegrip", t)
    if regel:
        return [regel]
    totaal = t["goed"] + t["fout"] + t["crash"]
    tekst = "• Taalbegrip: "
    if t.get("router_totaal"):
        tekst += (f"de router begreep {t['router_begrepen']} van de {t['router_totaal']} zinnen "
                  f"({_bm_router_procent(t):.0f}%); ")
    tekst += f"{t['goed']} van de {totaal} antwoorden goed ({_bm_procent(t):.0f}%); "
    tekst += _mv(t["onterecht"], "onterecht antwoord", "onterechte antwoorden")
    return [tekst + "."]


def _rapport_bm_rook(r):
    regel = _tool_regel("Rooktest", r)
    if regel:
        return [regel]
    totaal = r["goed"] + r["fout"] + r["crash"]
    tekst = (f"• Rooktest: {r['goed']} van de {totaal} vaste vragen goed ({_bm_procent(r):.0f}%), "
             f"{_mv(r['crash'], 'crash', 'crashes')}")
    if r.get("duur") is not None:
        tekst += f", {r['duur']:.0f} s"
    return [tekst + "."]


def rapport_benchmark(b):
    regels = []
    if b.get("taal") is not None:
        regels += _rapport_bm_taal(b["taal"])
    if b.get("rook") is not None:
        regels += _rapport_bm_rook(b["rook"])
    return regels


# ----------------------------------------------------------------------------
# DEKKING (coverage)
# ----------------------------------------------------------------------------

def parse_coverage(json_tekst, returncode, te_laat=False):
    """Ontleedt 'coverage json': totaalpercentage en de minst geteste bestanden."""
    res = {"beschikbaar": True, "gelukt": False, "procent": None, "bestanden": 0,
           "ongetest": 0, "minst": [], "reden": None}
    if te_laat:
        res["reden"] = "tijdslimiet overschreden"
        return res
    if returncode == 127:
        res["reden"] = "coverage kon niet gestart worden"
        return res
    try:
        data = _json_uit(json_tekst)
        res["procent"] = round(float(data["totals"]["percent_covered"]), 1)
        bestanden = data["files"]
    except (ValueError, KeyError, TypeError):
        res["reden"] = "geen bruikbare dekkingsgegevens (zijn de tests gecrasht?)"
        return res
    lijst = []
    for pad, info in bestanden.items():
        samenvatting = info.get("summary") or {}
        n = samenvatting.get("num_statements", 0)
        if not n:
            continue
        procent = float(samenvatting.get("percent_covered", 0.0))
        res["bestanden"] += 1
        res["ongetest"] += 1 if procent == 0 else 0
        if n >= 30:
            lijst.append((procent, pad))
    lijst.sort()
    res["minst"] = [{"bestand": pad, "procent": round(p)} for p, pad in lijst[:3]]
    res["gelukt"] = True
    return res


def beoordeel_dekking(d, vorig):
    opmerkingen, vergelijking = [], []
    probleem = _tool_probleem("dekking meten", "coverage", d)
    if probleem:
        return [], [probleem], vergelijking
    if not d.get("gelukt"):
        return [], opmerkingen, vergelijking
    oud = (vorig.get("dekking") or {}).get("procent")
    if isinstance(oud, (int, float)) and oud - d["procent"] >= 1.0:
        opmerkingen.append(f"de dekking daalde van {_g(oud)}% naar {_g(d['procent'])}%")
    tekst = _verschil("dekking (%)", oud, d["procent"], 0.5)
    return [], opmerkingen, [tekst] if tekst else vergelijking


def rapport_dekking(d):
    regel = _tool_regel("Dekking", d)
    if regel:
        return [regel]
    tekst = (f"• Dekking: {_g(d['procent'])}% van de code wordt door tests geraakt "
             f"({_mv(d['bestanden'], 'bestand', 'bestanden')}, {d['ongetest']} helemaal niet)")
    if d.get("minst"):
        tekst += ". Minst getest: " + ", ".join(f"{m['bestand']} ({m['procent']}%)" for m in d["minst"])
    return [tekst + "."]


# ----------------------------------------------------------------------------
# DODE CODE (vulture)
# ----------------------------------------------------------------------------

_VULTURE_REGEL = re.compile(r"^(?P<pad>.+?):(?P<regel>\d+): (?P<tekst>.+?) \((?P<zeker>\d+)% confidence\)\s*$")


def parse_vulture(uitvoer, returncode, te_laat=False):
    """Telt meldingen van vulture (code die nergens gebruikt wordt)."""
    res = {"beschikbaar": True, "gelukt": True, "aantal": 0, "onbereikbaar": 0,
           "voorbeelden": [], "reden": None}
    if te_laat:
        res.update(gelukt=False, reden="tijdslimiet overschreden")
        return res
    if returncode == 127:
        res.update(gelukt=False, reden="vulture kon niet gestart worden")
        return res
    if returncode not in (0, 3):                         # 3 = dode code gevonden
        res.update(gelukt=False, reden=f"vulture stopte onverwacht (code {returncode})")
        return res
    for regel in (uitvoer or "").splitlines():
        m = _VULTURE_REGEL.match(regel.strip())
        if not m:
            continue
        tekst = m.group("tekst")
        naam = re.search(r"'([^']+)'", tekst)
        if "unused variable" in tekst and naam and naam.group(1) in VULTURE_NEGEER_NAMEN:
            continue
        res["aantal"] += 1
        if "unreachable" in tekst:
            res["onbereikbaar"] += 1
        if len(res["voorbeelden"]) < MAX_VOORBEELDEN:
            res["voorbeelden"].append(f"{m.group('pad')}:{m.group('regel')}: {tekst}")
    return res


def beoordeel_dode_code(d, vorig):
    opmerkingen, vergelijking = [], []
    probleem = _tool_probleem("de controle op dode code", "vulture", d)
    if probleem:
        return [], [probleem], vergelijking
    if not d.get("gelukt"):
        return [], opmerkingen, vergelijking
    oud = (vorig.get("dode_code") or {}).get("aantal")
    if isinstance(oud, int) and d["aantal"] > oud:
        opmerkingen.append(f"{_mv(d['aantal'] - oud, 'melding', 'meldingen')} meer over dode code dan vorige keer")
    tekst = _verschil("meldingen over dode code", oud, d["aantal"])
    return [], opmerkingen, [tekst] if tekst else vergelijking


def rapport_dode_code(d):
    regel = _tool_regel("Dode code", d)
    if regel:
        return [regel]
    tekst = f"• Dode code: {_mv(d['aantal'], 'melding', 'meldingen')}"
    if d.get("onbereikbaar"):
        tekst += f", waarvan {d['onbereikbaar']} onbereikbare code"
    regels = [tekst + "."]
    return regels + [f"    - {v}" for v in d.get("voorbeelden", [])[:3]]


# ----------------------------------------------------------------------------
# BEVEILIGING (bandit)
# ----------------------------------------------------------------------------

def parse_bandit(json_tekst, returncode, te_laat=False):
    """Telt de bevindingen van bandit per ernst (hoog/middel/laag)."""
    res = {"beschikbaar": True, "gelukt": False, "hoog": 0, "middel": 0, "laag": 0,
           "hoge": [], "reden": None}
    if te_laat:
        res["reden"] = "tijdslimiet overschreden"
        return res
    if returncode == 127:
        res["reden"] = "bandit kon niet gestart worden"
        return res
    try:
        resultaten = _json_uit(json_tekst)["results"]
    except (ValueError, KeyError, TypeError):
        res["reden"] = "uitvoer van bandit was geen geldige JSON"
        return res
    sleutel = {"HIGH": "hoog", "MEDIUM": "middel", "LOW": "laag"}
    for r in resultaten:
        soort = sleutel.get(str(r.get("issue_severity", "")).upper())
        if soort:
            res[soort] += 1
        if soort == "hoog" and len(res["hoge"]) < MAX_VOORBEELDEN:
            res["hoge"].append(f"{r.get('filename')}:{r.get('line_number')} {r.get('test_id')}: "
                               f"{str(r.get('issue_text', ''))[:70]}")
    res["gelukt"] = True
    return res


def beoordeel_beveiliging(b, vorig):
    opmerkingen, vergelijking = [], []
    probleem = _tool_probleem("de beveiligingscontrole", "bandit", b)
    if probleem:
        return [], [probleem], vergelijking
    if not b.get("gelukt"):
        return [], opmerkingen, vergelijking
    vb = vorig.get("beveiliging") or {}
    for soort, naam in (("hoog", "hoge"), ("middel", "middelhoge")):
        oud = vb.get(soort)
        if isinstance(oud, int) and b[soort] > oud:
            meer = b[soort] - oud
            woord = "bevinding" if meer == 1 else "bevindingen"
            opmerkingen.append(f"{meer} nieuwe {naam} beveiligings{woord}")
        tekst = _verschil(f"{naam} bevindingen", oud, b[soort])
        if tekst:
            vergelijking.append(tekst)
    return [], opmerkingen, vergelijking


def rapport_beveiliging(b):
    regel = _tool_regel("Beveiliging", b)
    if regel:
        return [regel]
    regels = [f"• Beveiliging: {b['hoog']} hoog, {b['middel']} middel, {b['laag']} laag (bandit)."]
    return regels + [f"    - {v}" for v in b.get("hoge", [])[:3]]


# ----------------------------------------------------------------------------
# PAKKETTEN (pip-audit) -- staat standaard UIT: heeft internet nodig
# ----------------------------------------------------------------------------

def parse_pipaudit(json_tekst, returncode, te_laat=False):
    """Ontleedt 'pip-audit -f json': welke geinstalleerde pakketten hebben bekende kwetsbaarheden."""
    res = {"beschikbaar": True, "gelukt": False, "pakketten": 0, "kwetsbaar": [],
           "kwetsbaar_aantal": 0, "kwetsbaarheden": 0, "reden": None}
    if te_laat:
        res["reden"] = "tijdslimiet overschreden"
        return res
    if returncode == 127:
        res["reden"] = "pip-audit kon niet gestart worden"
        return res
    try:
        afhankelijkheden = _json_uit(json_tekst)["dependencies"]
    except (ValueError, KeyError, TypeError):
        res["reden"] = "geen resultaat van pip-audit (geen internet?)"
        return res
    kwetsbaar = []
    for dep in afhankelijkheden:
        res["pakketten"] += 1
        vulns = dep.get("vulns") or []
        if vulns:
            kwetsbaar.append({"naam": dep.get("name"), "versie": dep.get("version"), "aantal": len(vulns)})
            res["kwetsbaarheden"] += len(vulns)
    kwetsbaar.sort(key=lambda k: (-k["aantal"], str(k["naam"])))
    res.update(gelukt=True, kwetsbaar_aantal=len(kwetsbaar), kwetsbaar=kwetsbaar[:10])
    return res


def beoordeel_pakketten(p, vorig):
    opmerkingen, vergelijking = [], []
    probleem = _tool_probleem("de pakkettencontrole", "pip-audit", p, neutraal_bij_mislukken=True)
    if probleem:
        return [], [probleem], vergelijking
    if not p.get("gelukt"):
        return [], opmerkingen, vergelijking
    oud = (vorig.get("pakketten") or {}).get("kwetsbaar_aantal")
    if isinstance(oud, int) and p["kwetsbaar_aantal"] > oud:
        opmerkingen.append(f"{_mv(p['kwetsbaar_aantal'] - oud, 'pakket', 'pakketten')} met een bekende "
                           f"kwetsbaarheid erbij")
    tekst = _verschil("kwetsbare pakketten", oud, p["kwetsbaar_aantal"])
    return [], opmerkingen, [tekst] if tekst else vergelijking


def rapport_pakketten(p):
    regel = _tool_regel("Pakketten", p)
    if regel:
        return [regel]
    tekst = (f"• Pakketten: {_mv(p['kwetsbaar_aantal'], 'pakket', 'pakketten')} van de {p['pakketten']} "
             f"met een bekende kwetsbaarheid ({p['kwetsbaarheden']} in totaal)")
    if p.get("kwetsbaar"):
        tekst += ": " + ", ".join(f"{k['naam']} {k['versie']}" for k in p["kwetsbaar"][:MAX_VOORBEELDEN])
    return [tekst + "."]


# ----------------------------------------------------------------------------
# Tabellen voor zelftest.py
# ----------------------------------------------------------------------------

BEOORDELAARS = {
    "backup": beoordeel_backup, "schijf": beoordeel_schijf, "modules": beoordeel_modules,
    "consistentie": beoordeel_consistentie, "docs": beoordeel_docs, "benchmark": beoordeel_benchmark,
    "dekking": beoordeel_dekking, "dode_code": beoordeel_dode_code,
    "beveiliging": beoordeel_beveiliging, "pakketten": beoordeel_pakketten,
}

RAPPORTEERDERS = {
    "backup": rapport_backup, "schijf": rapport_schijf, "modules": rapport_modules,
    "consistentie": rapport_consistentie, "docs": rapport_docs, "benchmark": rapport_benchmark,
    "dekking": rapport_dekking, "dode_code": rapport_dode_code,
    "beveiliging": rapport_beveiliging, "pakketten": rapport_pakketten,
}