# scripts/koppelingen_audit.py
#
# Controleert met STATISCHE analyse (de broncode wordt gelezen, niets wordt uitgevoerd
# of gewijzigd) hoe goed Nova's modules aan de lagen en aan elkaar gekoppeld zijn.
#
# Gebruik (vanuit de projectmap, bv. /app in de container):
#   python scripts/koppelingen_audit.py              (overzicht + bevindingen)
#   python scripts/koppelingen_audit.py --alles      (ook de lange lijsten volledig)
#   python scripts/koppelingen_audit.py --md rapport.md   (schrijf het ook als Markdown weg)
#   python scripts/koppelingen_audit.py --root /ander/pad
#
# In Docker op battleserver:
#   docker exec nova-ai python scripts/koppelingen_audit.py
#
# EERLIJK OVER DE BETROUWBAARHEID: dit is een heuristiek op tekst en syntaxis. Het ziet
# alleen verwijzingen die er als letterlijke tekst staan (bv. .get("context_manager") of
# publish("layer4_response", ...)). Namen die pas tijdens het draaien samengesteld worden
# ziet het niet. Een bevinding is dus een AANWIJZING om na te kijken, geen bewezen bug, en
# "geen bevinding" is geen garantie. Puur symbolisch, geen ML.
#
# Wijzigingen 2 november 2026 (punt 57e):
#  - bestanden in identity/ tellen als Layer 6 (eigen laag)
#  - bevinding 1 kijkt per functie (check_*/loop) of ZIJ zelf een Layer 5-poort heeft
#  - _on_shutdown telt als shutdown; main.py telt niet mee bij bevinding 2
#  - intent_*-luisteraars zonder zender worden apart gehouden (router publiceert dynamisch)
#  - nieuwe bevinding 7: bestanden die geen enkele test importeert

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAPPEN = ("core", "modules", "identity")
LOSSE_BESTANDEN = ("main.py",)
NEGEER_MAPNAMEN = {"__pycache__", "tests", ".git", "node_modules"}

# Welke naam (zoals in .get("...") / loaded_modules[...]) hoort bij welke laag?
LAAG_VAN_NAAM = {
    "memory": 0,
    "word_associations": 1, "word_associations_learner": 1,
    "pattern_matcher": 2, "patterns": 2,
    "semantic": 3,
    "response_engine": 4, "response_pipeline": 4,
    "context_manager": 5, "activity_detector": 5, "focus_detector": 5, "presence_detector": 5,
    "personality": 6, "emotion": 6, "microlearning": 6,
    "emergence_engine": 7,
}
LAAG_TITEL = {0: "Mem", 1: "Ass", 2: "Pat", 3: "Sem", 4: "Rsp", 5: "Ctx", 6: "Prs", 7: "Emg"}

SPREEK_EVENTS = {"chat_response", "layer4_response"}
LAAG5_TEKENS = ("can_interrupt", "mag_spreken", "layer5", "context_manager")
# Waaraan herkennen we dat een FUNCTIE zelf een Layer 5-poort heeft?
POORT_TEKENS = ("layer5", "mag_spreken", "mag_nu_spreken", "can_interrupt")
# Events die de router dynamisch publiceert (de naam wordt pas tijdens het draaien gebouwd).
DYNAMISCHE_VOORVOEGSELS = ("intent_",)


# ---------------------------------------------------------------
# 1. Een bestand analyseren
# ---------------------------------------------------------------
def _eerste_tekst(call):
    """Eerste argument als (soort, tekst): ('vast', 'x') voor 'x', ('prefix', 'x') voor f'x{..}'."""
    if not call.args:
        return None
    a = call.args[0]
    if isinstance(a, ast.Constant) and isinstance(a.value, str):
        return "vast", a.value
    if isinstance(a, ast.JoinedStr) and a.values:
        eerste = a.values[0]
        if isinstance(eerste, ast.Constant) and isinstance(eerste.value, str) and eerste.value:
            return "prefix", eerste.value
    return None


def _controleer_spreken_in_check(functie, info):
    """
    Is dit een check_*/loop-functie die zelf spreekt (publish van chat_response/layer4_response)?
    Zo ja: heeft die functie zelf een Layer 5-poort (can_interrupt, mag_spreken, ...)?
    De poort kan ook in de AANROEPER zitten (bv. main.py); dat ziet het script niet.
    """
    naam = functie.name.lstrip("_")
    if not (naam.startswith("check") or "loop" in naam or "achtergrond" in naam):
        return
    spreekt = False
    poort = False
    for sub in ast.walk(functie):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr == "publish":
            e = _eerste_tekst(sub)
            if e and e[0] == "vast" and e[1] in SPREEK_EVENTS:
                spreekt = True
        elif isinstance(sub, ast.Attribute) and any(t in sub.attr.lower() for t in POORT_TEKENS):
            poort = True
        elif isinstance(sub, ast.Name) and any(t in sub.id.lower() for t in POORT_TEKENS):
            poort = True
    if spreekt:
        info["spreekt_in_check"] = True
        if not poort:
            info["check_zonder_poort"].append(functie.name)


def analyseer_bron(tekst):
    """Leest 1 bestand en geeft een dict met wat het doet. Bij een syntaxfout: {'fout': ...}."""
    info = {
        "fout": None, "verwijzingen": set(), "publiceert": set(), "luistert": set(),
        "emit_topics": set(), "emit_prefixen": set(), "labels": set(), "label_prefixen": set(),
        "heeft_thread": False, "heeft_check": False, "heeft_shutdown": False, "noemt_layer5": False,
        "spreekt_in_check": False, "check_zonder_poort": [],
    }
    try:
        boom = ast.parse(tekst)
    except (SyntaxError, ValueError) as e:
        info["fout"] = str(e)
        return info

    for node in ast.walk(boom):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            naam = node.func.attr
            eerste = _eerste_tekst(node)
            if naam in ("get", "get_module", "register_module") and eerste and eerste[0] == "vast":
                info["verwijzingen"].add(eerste[1])
            elif naam == "publish" and eerste:
                info["publiceert"].add(eerste[1] + ("*" if eerste[0] == "prefix" else ""))
            elif naam == "subscribe" and eerste:
                info["luistert"].add(eerste[1] + ("*" if eerste[0] == "prefix" else ""))
            elif naam == "_emit_topic" and eerste:
                (info["emit_topics"] if eerste[0] == "vast" else info["emit_prefixen"]).add(eerste[1])
            elif naam in ("Thread", "Timer"):
                info["heeft_thread"] = True
            elif naam == "can_interrupt":
                info["noemt_layer5"] = True
            elif (naam == "startswith" and isinstance(node.func.value, ast.Name)
                  and node.func.value.id == "topic_naam" and eerste and eerste[0] == "vast"):
                info["label_prefixen"].add(eerste[1])
        elif isinstance(node, ast.Tuple):
            # Intent-tabellen: ("topic_naam", self.detect_iets) -> de lus in route()
            # publiceert dit als topic, ook al staat er geen losse _emit_topic("naam").
            if (len(node.elts) == 2
                    and isinstance(node.elts[0], ast.Constant) and isinstance(node.elts[0].value, str)
                    and isinstance(node.elts[1], ast.Attribute)
                    and node.elts[1].attr.startswith("detect_")):
                info["emit_topics"].add(node.elts[0].value)
        elif isinstance(node, ast.Subscript):
            basis = node.value
            basisnaam = basis.attr if isinstance(basis, ast.Attribute) else getattr(basis, "id", "")
            sl = node.slice
            if basisnaam in ("modules", "loaded_modules", "layers") and isinstance(sl, ast.Constant) \
                    and isinstance(sl.value, str):
                info["verwijzingen"].add(sl.value)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("check"):
                info["heeft_check"] = True
            if node.name in ("shutdown", "_on_shutdown"):
                info["heeft_shutdown"] = True
            for arg in node.args.args + node.args.kwonlyargs:
                if any(t in arg.arg.lower() for t in LAAG5_TEKENS):
                    info["noemt_layer5"] = True
            if any(t in node.name.lower() for t in ("layer5", "mag_spreken")):
                info["noemt_layer5"] = True
            _controleer_spreken_in_check(node, info)
        elif isinstance(node, ast.Name):
            if any(t in node.id.lower() for t in ("layer5", "mag_spreken")):
                info["noemt_layer5"] = True
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            doelen = node.targets if isinstance(node, ast.Assign) else [node.target]
            for doel in doelen:
                doelnaam = doel.attr if isinstance(doel, ast.Attribute) else getattr(doel, "id", "")
                if doelnaam == "_topic_naam_labels" and isinstance(node.value, ast.Dict):
                    for sleutel in node.value.keys:
                        if isinstance(sleutel, ast.Constant) and isinstance(sleutel.value, str):
                            info["labels"].add(sleutel.value)

    if "context_manager" in info["verwijzingen"]:
        info["noemt_layer5"] = True
    return info


# ---------------------------------------------------------------
# 2. Alle bestanden verzamelen
# ---------------------------------------------------------------
def verzamel(root):
    """{relatief pad: info} voor alle .py-bestanden in core/, modules/, identity/ en main.py."""
    root = Path(root)
    bestanden = []
    for mapnaam in MAPPEN:
        basis = root / mapnaam
        if basis.is_dir():
            bestanden += [p for p in basis.rglob("*.py")
                          if not (set(p.relative_to(root).parts) & NEGEER_MAPNAMEN)
                          and p.name != "__init__.py"]
    bestanden += [root / n for n in LOSSE_BESTANDEN if (root / n).is_file()]

    resultaat = {}
    for pad in sorted(bestanden):
        try:
            tekst = pad.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as e:
            info = analyseer_bron("")
            info["fout"] = str(e)
        else:
            info = analyseer_bron(tekst)
        info["stam"] = pad.stem
        info["pad"] = pad.relative_to(root).as_posix()
        resultaat[info["pad"]] = info
    return resultaat


def lees_tests(root):
    """
    Alle import-regels uit tests/ die naar het project verwijzen (core/modules/identity/main),
    als 1 tekst. Handmatige scripts (manual_*, map manual/) tellen niet mee.
    Geeft None als er geen tests/-map is.
    """
    basis = Path(root) / "tests"
    if not basis.is_dir():
        return None
    regels = []
    for pad in basis.rglob("*.py"):
        delen = pad.relative_to(basis).parts
        if "__pycache__" in delen or "manual" in delen or pad.name.startswith("manual_"):
            continue
        try:
            tekst = pad.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue
        for r in tekst.splitlines():
            r = r.strip()
            if re.match(r"(from|import)\s+(core|modules|identity|main)\b", r):
                regels.append(r)
    return "\n".join(regels)


# ---------------------------------------------------------------
# 3. Lagen per module
# ---------------------------------------------------------------
def lagen_van(info):
    """(directe lagen, indirecte lagen, eigen laag) van 1 bestand."""
    direct = {LAAG_VAN_NAAM[v] for v in info["verwijzingen"] if v in LAAG_VAN_NAAM}
    indirect = set()
    if any(e == "layer4_response" for e in info["publiceert"]):
        indirect.add(4)
    if (info["emit_topics"] or info["emit_prefixen"]
            or any(e.startswith(("topic_detected:", "activity_started:")) for e in info["publiceert"])):
        indirect.add(2)
    eigen = LAAG_VAN_NAAM.get(info["stam"])
    if eigen is None and info.get("pad", "").startswith("identity/"):
        eigen = 6  # de hele map identity/ is Layer 6
    indirect -= direct
    return direct, indirect, eigen


# ---------------------------------------------------------------
# 4. Bevindingen
# ---------------------------------------------------------------
def _past(a, b):
    """Komen twee eventnamen overeen? Een eindigende '*' betekent: begint met dit voorvoegsel."""
    if a.endswith("*") and b.endswith("*"):
        return a[:-1].startswith(b[:-1]) or b[:-1].startswith(a[:-1])
    if a.endswith("*"):
        return b.startswith(a[:-1])
    if b.endswith("*"):
        return a.startswith(b[:-1])
    return a == b


def bevindingen(infos, tests_tekst=None):
    uit = {}

    # a) Een check_*/loop-functie spreekt, maar die functie zelf vraagt Layer 5 nooit of het mag.
    #    (De poort kan in de aanroeper zitten, bv. main.py: dan is het vals alarm.)
    uit["proactief_zonder_layer5"] = sorted(
        f"{pad} ({', '.join(dict.fromkeys(i['check_zonder_poort']))})"
        for pad, i in infos.items() if i["check_zonder_poort"] and i["stam"] != "main")

    # b) Eigen thread of timer, maar geen shutdown(): wordt bij /reboot niet netjes gestopt.
    uit["thread_zonder_shutdown"] = sorted(
        pad for pad, i in infos.items()
        if i["heeft_thread"] and not i["heeft_shutdown"] and i["stam"] != "main")

    # c) _emit_topic-namen waar Layer 7 geen label voor heeft ("vast recept" uit nova_state.md).
    emergence = [i for i in infos.values() if i["stam"] == "emergence_engine"]
    if emergence:
        labels = set().union(*(i["labels"] for i in emergence))
        prefixen = set().union(*(i["label_prefixen"] for i in emergence))
        emits = set().union(*(i["emit_topics"] for i in infos.values()))
        uit["topics_zonder_label"] = sorted(
            n for n in emits if n not in labels and not any(n.startswith(p) for p in prefixen))
        uit["topics_totaal"] = len(emits)
    else:
        uit["topics_zonder_label"] = None
        uit["topics_totaal"] = 0

    # d) Events zonder gerichte luisteraar / luisteraars zonder zender (alleen letterlijke namen).
    gericht = {}
    for pad, i in infos.items():
        for e in i["luistert"]:
            if e != "*":
                gericht.setdefault(e, set()).add(pad)
    zenders = {}
    for pad, i in infos.items():
        for e in i["publiceert"]:
            zenders.setdefault(e, set()).add(pad)
    uit["events_zonder_luisteraar"] = sorted(
        e for e in zenders if not any(_past(e, l) for l in gericht))
    zonder_zender = sorted(l for l in gericht if not any(_past(l, e) for e in zenders))
    uit["luisteraars_dynamisch"] = [l for l in zonder_zender if l.startswith(DYNAMISCHE_VOORVOEGSELS)]
    uit["luisteraars_zonder_zender"] = [l for l in zonder_zender
                                        if not l.startswith(DYNAMISCHE_VOORVOEGSELS)]

    # e) Modules zonder enige verwijzing naar een laag (hulpbestanden vallen hier ook onder).
    uit["zonder_laag"] = sorted(
        pad for pad, i in infos.items()
        if pad.startswith("modules/") and not any(lagen_van(i)[:2]) and lagen_van(i)[2] is None)

    # f) Bestanden die in geen enkele test geimporteerd worden.
    if tests_tekst is None:
        uit["zonder_test"] = None
    else:
        uit["zonder_test"] = sorted(
            pad for pad, i in infos.items()
            if not re.search(rf"\b{re.escape(i['stam'])}\b", tests_tekst))
    return uit


# ---------------------------------------------------------------
# 5. Rapport
# ---------------------------------------------------------------
def maak_rapport(infos, alles=False, tests_tekst=None):
    regels = []
    uit = bevindingen(infos, tests_tekst)
    regels.append(f"Koppelingen-audit: {len(infos)} bestanden gelezen "
                  f"({sum(1 for i in infos.values() if i['fout'])} met leesfout).")
    regels.append("")
    regels.append("LAGEN PER MODULE   ● = verwijst er rechtstreeks naar, ○ = via events, E = eigen laag")
    regels.append("   " + " ".join(f"{LAAG_TITEL[n]}" for n in range(8)) + "   bestand")
    for pad, i in infos.items():
        if i["fout"]:
            continue
        direct, indirect, eigen = lagen_van(i)
        if not (direct or indirect or eigen is not None):
            continue
        cellen = []
        for n in range(8):
            cellen.append(" E " if eigen == n else " ● " if n in direct else " ○ " if n in indirect else " · ")
        regels.append("  " + "".join(cellen) + "  " + pad)

    def lijst(titel, items, uitleg, max_n=15):
        regels.append("")
        regels.append(f"{titel}: {len(items)}")
        regels.append(f"  ({uitleg})")
        for x in (items if alles else items[:max_n]):
            regels.append(f"  - {x}")
        if not alles and len(items) > max_n:
            regels.append(f"  ... en nog {len(items) - max_n} (zie --alles)")

    regels.append("")
    regels.append("BEVINDINGEN (aanwijzingen om na te kijken, geen bewezen bugs)")
    lijst("1. Proactief praten zonder Layer 5-check in de functie zelf", uit["proactief_zonder_layer5"],
          "een check_*/loop-functie publiceert chat_response/layer4_response, maar die functie vraagt "
          "zelf nergens can_interrupt()/mag_spreken. Zit de poort in de aanroeper (bv. main.py), dan is "
          "het vals alarm. Spreken vanuit andere functienamen ziet het script niet.")
    lijst("2. Thread/timer zonder shutdown()", uit["thread_zonder_shutdown"],
          "wordt bij /reboot en container-stop niet netjes gestopt (_on_shutdown/atexit telt mee, "
          "main.py niet).")
    if uit["topics_zonder_label"] is None:
        regels.append("")
        regels.append("3. Topics zonder Layer 7-label: emergence_engine.py niet gevonden, overgeslagen.")
    else:
        lijst("3. Topics zonder Layer 7-label", uit["topics_zonder_label"],
              f"van {uit['topics_totaal']} _emit_topic-namen. Geen bug (de kale naam wordt dan getoond), "
              "maar een Engelse naam in een Nederlandse zin klinkt raar. Zie 'vast recept' in nova_state.md.")
    lijst("4. Events zonder gerichte luisteraar", uit["events_zonder_luisteraar"],
          "alleen letterlijke namen; wildcard-luisteraars (zoals memory) tellen niet mee. "
          "Vaak onschuldig: het event wordt enkel gelogd/geteld.")
    lijst("5. Luisteraars zonder zender", uit["luisteraars_zonder_zender"],
          "dit event wordt nergens letterlijk gepubliceerd. Kan dood zijn, of dynamisch gepubliceerd.")
    if uit["luisteraars_dynamisch"]:
        regels.append(f"  (+ {len(uit['luisteraars_dynamisch'])} 'intent_*'-luisteraars apart gehouden: "
                      "de router publiceert die dynamisch)")
        if alles:
            for x in uit["luisteraars_dynamisch"]:
                regels.append(f"    - {x}")
    lijst("6. Modules zonder verwijzing naar een laag", uit["zonder_laag"],
          "hulpmodules (holidays, math, ...) mogen dit zijn; kijk vooral naar modules die wel iets "
          "'slims' doen.")
    if uit["zonder_test"] is not None:
        uitleg_test = ("geen enkele test in tests/ importeert dit bestand (op bestandsnaam; "
                       "handmatige scripts tellen niet). Een test die het enkel via een ander "
                       "bestand aanraakt, ziet het script niet.")
        zt = uit["zonder_test"]
        lijst("7a. identity/ zonder test", [p for p in zt if p.startswith("identity/")],
              uitleg_test, max_n=40)
        lijst("7b. Overige bestanden zonder test", [p for p in zt if not p.startswith("identity/")],
              uitleg_test)
    regels.append("")
    regels.append("Let op: statische heuristiek. Controleer een bevinding altijd in de code zelf.")
    return "\n".join(regels)


def main():
    ouder = argparse.ArgumentParser(description="Audit van de koppelingen tussen Nova's modules en lagen.")
    ouder.add_argument("--root", default=str(ROOT), help="projectmap (standaard: de map boven scripts/)")
    ouder.add_argument("--alles", action="store_true", help="toon de lijsten volledig")
    ouder.add_argument("--md", help="schrijf het rapport ook weg naar dit Markdown-bestand")
    args = ouder.parse_args()

    infos = verzamel(args.root)
    if not infos:
        print(f"Geen bestanden gevonden onder {args.root}")
        return 1
    rapport = maak_rapport(infos, alles=args.alles, tests_tekst=lees_tests(args.root))
    print(rapport)
    if args.md:
        Path(args.md).write_text("```\n" + rapport + "\n```\n", encoding="utf-8")
        print(f"\nRapport weggeschreven naar {args.md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())