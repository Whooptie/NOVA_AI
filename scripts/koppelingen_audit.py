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

import argparse
import ast
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


def analyseer_bron(tekst):
    """Leest 1 bestand en geeft een dict met wat het doet. Bij een syntaxfout: {'fout': ...}."""
    info = {
        "fout": None, "verwijzingen": set(), "publiceert": set(), "luistert": set(),
        "emit_topics": set(), "emit_prefixen": set(), "labels": set(), "label_prefixen": set(),
        "heeft_thread": False, "heeft_check": False, "heeft_shutdown": False, "noemt_layer5": False,
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
            if node.name == "shutdown":
                info["heeft_shutdown"] = True
            for arg in node.args.args + node.args.kwonlyargs:
                if any(t in arg.arg.lower() for t in LAAG5_TEKENS):
                    info["noemt_layer5"] = True
            if any(t in node.name.lower() for t in ("layer5", "mag_spreken")):
                info["noemt_layer5"] = True
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
        resultaat[pad.relative_to(root).as_posix()] = info
    return resultaat


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


def bevindingen(infos):
    uit = {}

    # a) Spreekt uit zichzelf maar vraagt Layer 5 nooit of het mag.
    uit["proactief_zonder_layer5"] = sorted(
        pad for pad, i in infos.items()
        if (i["publiceert"] & SPREEK_EVENTS) and (i["heeft_check"] or i["heeft_thread"])
        and not i["noemt_layer5"] and i["stam"] != "main")

    # b) Eigen thread of timer, maar geen shutdown(): wordt bij /reboot niet netjes gestopt.
    uit["thread_zonder_shutdown"] = sorted(
        pad for pad, i in infos.items() if i["heeft_thread"] and not i["heeft_shutdown"])

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
    uit["luisteraars_zonder_zender"] = sorted(
        l for l in gericht if not any(_past(l, e) for e in zenders))

    # e) Modules zonder enige verwijzing naar een laag (hulpbestanden vallen hier ook onder).
    uit["zonder_laag"] = sorted(
        pad for pad, i in infos.items()
        if pad.startswith("modules/") and not any(lagen_van(i)[:2]) and lagen_van(i)[2] is None)
    return uit


# ---------------------------------------------------------------
# 5. Rapport
# ---------------------------------------------------------------
def maak_rapport(infos, alles=False):
    regels = []
    uit = bevindingen(infos)
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
    lijst("1. Proactief praten zonder Layer 5-check", uit["proactief_zonder_layer5"],
          "publiceert chat_response/layer4_response vanuit een check_*/thread, maar vraagt nergens "
          "can_interrupt()/mag_spreken. Kan tegen een lege terminal praten.")
    lijst("2. Thread/timer zonder shutdown()", uit["thread_zonder_shutdown"],
          "wordt bij /reboot en container-stop niet netjes gestopt.")
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
    lijst("6. Modules zonder verwijzing naar een laag", uit["zonder_laag"],
          "hulpmodules (holidays, math, ...) mogen dit zijn; kijk vooral naar modules die wel iets "
          "'slims' doen.")
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
    rapport = maak_rapport(infos, alles=args.alles)
    print(rapport)
    if args.md:
        Path(args.md).write_text("```\n" + rapport + "\n```\n", encoding="utf-8")
        print(f"\nRapport weggeschreven naar {args.md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())