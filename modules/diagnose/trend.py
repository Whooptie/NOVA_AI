# modules/diagnose/trend.py
#
# Trend van de zelftest (14 november 2026): hoe groeit Nova week na week?
#
# WAT DOET DIT?
#   De zelftest bewaart elke run in data/zelftest_historie.json, maar dat bestand houdt
#   maar 60 runs vast (en elke handmatige run telt mee). Voor een trend over weken en
#   maanden is dat te weinig. Daarom bewaart dit bestand EEN METING PER DAG, met alleen de
#   belangrijkste getallen, in data/zelftest_trend.json (maximaal 400 dagen):
#     taalbegrip   hoeveel procent van de zinnen de router begrijpt
#     antwoorden   hoeveel procent van de taalvragen goed beantwoord wordt
#     rooktest     hoeveel procent van de vaste vragen goed beantwoord wordt
#     dekking      hoeveel procent van de code door tests geraakt wordt
#     tests        aantal geslaagde tests
#     zware_functies, concepten, data_mb
#   Meerdere runs op een dag: de nieuwste waarde per getal wint, een 'snel' run vult
#   dus enkel aan wat hij zelf meet.
#
# PUUR SYMBOLISCH: getallen bewaren, vergelijken en in een tabelletje zetten.
# Alleen LEZEN van de zelftest-resultaten; schrijft alleen zijn eigen trendbestand.
#
# Dit bestand heeft bewust GEEN init_module(): het is een hulpbestand, geen module.
#
# TESTS: tests/test_zelftest_trend.py

import json
import os
from datetime import date, datetime
from pathlib import Path

MAX_DAGEN = 400
WEEK = 7
_BLOKJES = "▁▂▃▄▅▆▇█"

# (sleutel, kolomnaam, eenheid): de kolommen in de tabel
KOLOMMEN = (
    ("taalbegrip", "taalbegrip", "%"),
    ("antwoorden", "antwoorden", "%"),
    ("rooktest", "rooktest", "%"),
    ("dekking", "dekking", "%"),
    ("tests", "tests", ""),
    ("concepten", "concepten", ""),
)
SPARKLINES = (("taalbegrip", "Taalbegrip"), ("antwoorden", "Antwoorden"), ("concepten", "Concepten"))


def _procent(goed, totaal):
    return round(100.0 * goed / totaal, 1) if totaal else None


def _bm_punten(benchmark):
    """Taalbegrip, antwoorden en rooktest uit het benchmark-deel van een zelftest-resultaat."""
    punt = {}
    taal = benchmark.get("taal") or {}
    if taal.get("gelukt"):
        begrip = _procent(taal.get("router_begrepen") or 0, taal.get("router_totaal"))
        antwoorden = _procent(taal["goed"], taal["goed"] + taal["fout"] + taal["crash"])
        punt.update({k: v for k, v in (("taalbegrip", begrip), ("antwoorden", antwoorden)) if v is not None})
    rook = benchmark.get("rook") or {}
    if rook.get("gelukt"):
        score = _procent(rook["goed"], rook["goed"] + rook["fout"] + rook["crash"])
        if score is not None:
            punt["rooktest"] = score
    return punt


def meetpunt(res):
    """De getallen uit een zelftest-resultaat die in de trend horen. Alleen wat gemeten is."""
    punt = _bm_punten(res.get("benchmark") or {})
    tests = res.get("pytest") or {}
    if tests.get("gelukt"):
        punt["tests"] = tests["geslaagd"]
    dekking = res.get("dekking") or {}
    if dekking.get("gelukt"):
        punt["dekking"] = dekking["procent"]
    radon = res.get("radon") or {}
    if radon.get("gelukt"):
        punt["zware_functies"] = radon["zwaar"]
    concepten = (res.get("consistentie") or {}).get("concepten")
    if concepten is not None:
        punt["concepten"] = concepten
    schijf = res.get("schijf") or {}
    if schijf.get("gelukt") and schijf.get("data_mb") is not None:
        punt["data_mb"] = schijf["data_mb"]
    return punt


def leeg():
    return {"versie": 1, "dagen": {}}


def voeg_toe(trend_data, tijd_iso, punt):
    """Zet 'punt' bij de dag van 'tijd_iso' (nieuwe waarden overschrijven oude). Houdt MAX_DAGEN dagen."""
    if not punt:
        return trend_data
    try:
        dag = datetime.fromisoformat(tijd_iso).date().isoformat()
    except (TypeError, ValueError):
        return trend_data
    trend_data.setdefault("dagen", {}).setdefault(dag, {}).update(punt)
    dagen = trend_data["dagen"]
    for oud in sorted(dagen)[:-MAX_DAGEN]:
        del dagen[oud]
    return trend_data


def opbouw_uit_historie(runs):
    """Bouwt een trend uit bestaande zelftest-runs (bij de eerste keer, zodat je niet van nul begint)."""
    trend_data = leeg()
    for run in runs:
        voeg_toe(trend_data, run.get("tijd"), meetpunt(run))
    return trend_data


def laad(pad):
    """Leest het trendbestand. Geeft None als het niet bestaat of kapot is."""
    try:
        with open(pad, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("dagen"), dict):
            return data
    except (OSError, ValueError):
        pass
    return None


def bewaar(pad, trend_data):
    """Atomisch schrijven: eerst een tijdelijk bestand, dan vervangen. Geeft False bij een fout."""
    try:
        pad = Path(pad)
        pad.parent.mkdir(parents=True, exist_ok=True)
        tijdelijk = pad.with_name(pad.name + ".tmp")
        with open(tijdelijk, "w", encoding="utf-8") as f:
            json.dump(trend_data, f, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tijdelijk, pad)
        return True
    except OSError:
        return False


# ----------------------------------------------------------------------------
# Tekst voor Kevin
# ----------------------------------------------------------------------------

def _fmt(waarde, eenheid=""):
    if waarde is None:
        return "-"
    return f"{waarde:g}{eenheid}"


def sparkline(waarden):
    """[1, 3, 2] -> een rijtje blokjes. Waarden die ontbreken (None) vallen weg."""
    echt = [w for w in waarden if w is not None]
    if len(echt) < 2:
        return ""
    laagste, hoogste = min(echt), max(echt)
    if hoogste == laagste:
        return _BLOKJES[3] * len(echt)
    stap = (hoogste - laagste) / (len(_BLOKJES) - 1)
    return "".join(_BLOKJES[round((w - laagste) / stap)] for w in echt)


def _dd_mm(dag):
    return datetime.fromisoformat(dag).strftime("%d-%m")


def _tabel(dagen, datums):
    kop = "  datum " + "".join(f"{naam:>12}" for _, naam, _ in KOLOMMEN)
    regels = [kop]
    for dag in datums:
        waarden = "".join(f"{_fmt(dagen[dag].get(sleutel), eenheid):>12}" for sleutel, _, eenheid in KOLOMMEN)
        regels.append(f"  {_dd_mm(dag)} {waarden}")
    return regels


def _vergelijkpunt(datums):
    """De dag die het dichtst bij een week voor de laatste meting ligt (of de oudste als er niet genoeg is)."""
    laatste = date.fromisoformat(datums[-1])
    kandidaten = [d for d in datums[:-1] if (laatste - date.fromisoformat(d)).days >= WEEK]
    return kandidaten[-1] if kandidaten else datums[0]


def _verandering(dagen, datums):
    oud_dag, nieuw_dag = _vergelijkpunt(datums), datums[-1]
    delen = []
    for sleutel, naam, eenheid in KOLOMMEN:
        oud, nieuw = dagen[oud_dag].get(sleutel), dagen[nieuw_dag].get(sleutel)
        if oud is None or nieuw is None or oud == nieuw:
            continue
        verschil = nieuw - oud
        punt = " punt" if eenheid == "%" and abs(verschil) == 1 else (" punten" if eenheid == "%" else "")
        delen.append(f"{naam} {_fmt(oud, eenheid)} → {_fmt(nieuw, eenheid)} ({verschil:+g}{punt})")
    if not delen:
        return [f"Sinds {_dd_mm(oud_dag)}: geen verandering in deze cijfers."]
    return [f"Sinds {_dd_mm(oud_dag)}: " + ", ".join(delen) + "."]


def trend_tekst(trend_data, max_dagen=8):
    """De trend als tekst: een tabel van de laatste meetdagen, sparklines en wat er veranderde."""
    dagen = (trend_data or {}).get("dagen") or {}
    datums = sorted(d for d, punt in dagen.items() if punt)
    if not datums:
        return "Nog geen trend. Typ 'zelftest' of 'zelftest alles'; vanaf dan bewaar ik elke dag een meting."
    getoond = datums[-max_dagen:]
    regels = [f"Trend van mijn taalbegrip en gezondheid ({len(datums)} meetdagen, laatste {len(getoond)}):"]
    regels += _tabel(dagen, getoond)
    for sleutel, naam in SPARKLINES:
        lijn = sparkline([dagen[d].get(sleutel) for d in datums[-30:]])
        if lijn:
            regels.append(f"  {naam:<11}{lijn}  (nu {_fmt(dagen[datums[-1]].get(sleutel))})")
    if len(datums) < 2:
        regels.append("Nog maar één meetdag; vanaf morgen zie ik hier de groei.")
    else:
        regels += _verandering(dagen, datums)
    return "\n".join(regels)