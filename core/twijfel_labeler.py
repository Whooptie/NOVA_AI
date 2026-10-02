# core/twijfel_labeler.py
"""
Fase B (2 oktober 2026): hulpfuncties om twijfelgevallen van de
signaal-classifier (microlearning.py) en de sentiment-classifier
(sentiment_classifier.py) te labelen.

Achtergrond (Fase A, zie nova_changelog.md): twijfelgevallen zijn enkel
nog trainingsdata als ze een label hebben van een bron BUITEN het model
zelf:
  - "label_kevin": door Kevin gegeven via het debug-commando
    'label signaal <label>' / 'label sentiment <label>'. Wint altijd.
    De waarde "skip" betekent: overgeslagen, nooit trainingsdata.
  - "label_auto": automatisch gezet door microlearning.py bij een
    ondubbelzinnig, strikt trefwoord (enkel voor signaal).

Puur symbolisch: bestanden lezen, tellen, een veld zetten. Geen ML.

Bewust in core/ (niet modules/): dit zijn pure hulpfuncties zonder
init_module(), en core/ wordt niet doorzocht door module_loader.py's
dynamische scan -- zo kan die dit bestand nooit per ongeluk als module
proberen te starten.
"""

import json
import os
from collections import Counter


# Per soort: waar de bestanden staan (relatief t.o.v. de project-root),
# welk veld het label bevat in de trainingsdata, welk veld de gok van
# het model bevat in het twijfelbestand, en welke module de
# hertraining-check uitvoert.
BRONNEN = {
    "signaal": {
        "uncertain": os.path.join("identity", "personality", "uncertain_signals.jsonl"),
        "training": os.path.join("identity", "personality", "training_data.json"),
        "label_veld": "signaal",
        "gok_veld": "signaal",
        "module": "microlearning",
    },
    "sentiment": {
        "uncertain": os.path.join("modules", "preferences", "sentiment_uncertain.jsonl"),
        "training": os.path.join("modules", "preferences", "sentiment_training_data.json"),
        "label_veld": "categorie",
        "gok_veld": "categorie",
        "module": "sentiment_classifier",
    },
}

SKIP = "skip"


def _root():
    """
    Project-root (de map met main.py). Aparte functie zodat tests dit
    kunnen vervangen door tmp_path.
    """
    from modules.paths import get_project_root
    return get_project_root(__file__)


def pad(soort, sleutel):
    """Volledig pad, bv. pad("signaal", "uncertain")."""
    return os.path.join(str(_root()), BRONNEN[soort][sleutel])


def _normaliseer(tekst):
    """Zelfde vergelijking als de trainers: spaties rond weg, kleine letters."""
    return (tekst or "").strip().lower()


def _effectief_label(item):
    """Kevins label wint; anders een eventueel automatisch label."""
    return item.get("label_kevin") or item.get("label_auto")


def _lees(pad_bestand):
    """
    Leest een twijfelbestand als lijst van (ruwe_regel, item). item is
    None voor een kapotte regel -- die blijft wel bewaard, zodat
    zet_label() bij het herschrijven nooit stilzwijgend data weggooit.
    """
    if not os.path.exists(pad_bestand):
        return []

    regels = []
    with open(pad_bestand, "r", encoding="utf-8") as f:
        for ruw in f:
            ruw = ruw.rstrip("\n")
            if not ruw.strip():
                continue
            try:
                item = json.loads(ruw)
                if not isinstance(item, dict):
                    item = None
            except json.JSONDecodeError:
                item = None
            regels.append((ruw, item))
    return regels


def toegestane_labels(training_pad, label_veld):
    """
    De geldige labels = alle labels die in de handgeschreven
    trainingsdata voorkomen. Zo vangt het commando typfouten op
    ("neutrall") zonder een aparte, los te onderhouden lijst.
    """
    try:
        with open(training_pad, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return set()
    return {v[label_veld] for v in data.get("voorbeelden", []) if label_veld in v}


def volgende_ongelabelde(pad_bestand, gok_veld):
    """
    Geeft de volgende UNIEKE twijfelzin zonder label terug, de vaakst
    gelogde eerst (grootste effect per label). Een zin die ergens in
    het bestand al een label heeft, telt in zijn geheel als gelabeld --
    ook als hij nadien opnieuw zonder label gelogd werd. Zo komt een
    eenmaal gelabelde zin nooit terug in de wachtrij.

    Geeft None terug als er niets meer te labelen valt, anders:
    {"tekst", "aantal", "model_gok", "nog_te_gaan"}
    """
    tellingen = Counter()
    eerste_tekst = {}
    eerste_positie = {}
    gokken = {}
    gelabeld = set()

    for positie, (_, item) in enumerate(_lees(pad_bestand)):
        if item is None:
            continue
        tekst = (item.get("text") or "").strip()
        if not tekst:
            continue
        norm = tekst.lower()

        if _effectief_label(item):
            gelabeld.add(norm)
            continue

        tellingen[norm] += 1
        eerste_tekst.setdefault(norm, tekst)
        eerste_positie.setdefault(norm, positie)
        gokken.setdefault(norm, Counter())[item.get(gok_veld)] += 1

    kandidaten = [n for n in tellingen if n not in gelabeld]
    if not kandidaten:
        return None

    kandidaten.sort(key=lambda n: (-tellingen[n], eerste_positie[n]))
    keuze = kandidaten[0]

    return {
        "tekst": eerste_tekst[keuze],
        "aantal": tellingen[keuze],
        "model_gok": gokken[keuze].most_common(1)[0][0],
        "nog_te_gaan": len(kandidaten),
    }


def zet_label(pad_bestand, tekst, label):
    """
    Zet "label_kevin" op ALLE regels met dezelfde tekst (hoofdletters en
    spaties rond genegeerd). Schrijft atomisch weg: eerst naar een
    tijdelijk bestand, dan omwisselen met os.replace() -- zelfde aanpak
    als ConceptStore.save() in semantic.py. Bij een fout blijft het
    originele bestand intact.

    Eerlijke beperking: voegt microlearning.py/sentiment_classifier.py
    precies tussen het inlezen en het omwisselen een nieuwe regel toe
    (milliseconden), dan gaat die ene nieuwe logregel verloren.

    Geeft het aantal bijgewerkte regels terug (0 = niets gevonden,
    niets geschreven).
    """
    norm = _normaliseer(tekst)
    if not norm:
        return 0

    regels = _lees(pad_bestand)
    nieuwe_regels = []
    gewijzigd = 0

    for ruw, item in regels:
        if item is not None and _normaliseer(item.get("text")) == norm:
            item["label_kevin"] = label
            nieuwe_regels.append(json.dumps(item, ensure_ascii=False))
            gewijzigd += 1
        else:
            nieuwe_regels.append(ruw)

    if gewijzigd == 0:
        return 0

    tijdelijk = f"{pad_bestand}.tmp{os.getpid()}"
    try:
        with open(tijdelijk, "w", encoding="utf-8") as f:
            f.write("\n".join(nieuwe_regels) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tijdelijk, pad_bestand)
    except Exception:
        if os.path.exists(tijdelijk):
            os.remove(tijdelijk)
        raise

    return gewijzigd


def status(pad_bestand):
    """
    Telt per UNIEKE zin hoe hij gelabeld is. Als een zin op meerdere
    regels staat met verschillende labels, telt het "sterkste":
    Kevin (of skip) boven automatisch boven ongelabeld.
    """
    rang = {None: 0, "auto": 1, "kevin": 2, "skip": 2}
    per_tekst = {}
    aantal_regels = 0

    for _, item in _lees(pad_bestand):
        if item is None:
            continue
        norm = _normaliseer(item.get("text"))
        if not norm:
            continue
        aantal_regels += 1

        if item.get("label_kevin") == SKIP:
            soort = "skip"
        elif item.get("label_kevin"):
            soort = "kevin"
        elif item.get("label_auto"):
            soort = "auto"
        else:
            soort = None

        if norm not in per_tekst or rang[soort] > rang[per_tekst[norm]]:
            per_tekst[norm] = soort

    waarden = list(per_tekst.values())
    return {
        "regels": aantal_regels,
        "unieke_zinnen": len(per_tekst),
        "ongelabeld": waarden.count(None),
        "kevin": waarden.count("kevin"),
        "auto": waarden.count("auto"),
        "skip": waarden.count("skip"),
    }