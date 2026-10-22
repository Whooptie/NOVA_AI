#modules/knowledge/graph_render.py

"""
graph_render.py -- Semantic Fase 13.2: van graaf-data naar een HTML-bestand.

Neemt het resultaat van graph_data.bouw_graaf() en maakt er met Pyvis een
interactieve HTML-pagina van (slepen, zoomen, aanwijzen voor uitleg).

100% symbolisch: dit is alleen tekenen. Geen ML, geen generatie.

Belangrijk:
  - Het HTML-bestand is volledig OFFLINE (alle JavaScript zit er in). Het werkt dus ook
    zonder internet en kan zonder problemen naar je laptop worden gestuurd.
  - Tekst uit concepts.json komt deels van Wikipedia. Daarom worden < > & en aanhalingstekens
    uit alle teksten gehaald voordat ze in de pagina komen (_veilig). Zo kan er nooit
    HTML of JavaScript uit een definitie in de pagina terechtkomen.
  - Het bestand wordt altijd in de vaste map geschreven (standaard data/graphs) en de
    bestandsnaam wordt gezuiverd: geen paden, geen vreemde tekens, altijd .html.
"""

import os
import re

try:
    from pyvis.network import Network
    PYVIS_BESCHIKBAAR = True
except ImportError:           # pyvis niet geinstalleerd: de rest van Nova blijft werken
    Network = None
    PYVIS_BESCHIKBAAR = False

STANDAARD_MAP = os.path.join("data", "graphs")

# kleur per relatietype; onbekende types krijgen grijs
KLEUREN = {
    "is_a": "#2b7bba",
    "part_of": "#2e9e5b",
    "has_part": "#2e9e5b",
    "causes": "#d9822b",
    "related_to": "#8a8a8a",
    "synonym": "#8e5bb5",
    "antonym": "#c2185b",
    "property_of": "#b8a100",
    "used_for": "#1aa6a6",
    "None": "#e02020",               # type ontbreekt in concepts.json: opvallend rood
}
KLEUR_ONBEKEND = "#aaaaaa"
KLEUR_PAD = "#e02020"
KLEUR_CENTRUM = "#f2c230"
KLEUR_NODE = "#9ec5e8"
KLEUR_NODE_ONTBREEKT = "#d9d9d9"

LABELS_NL = {
    "is_a": "is een",
    "part_of": "is deel van",
    "has_part": "heeft als deel",
    "causes": "veroorzaakt",
    "related_to": "hangt samen met",
    "synonym": "is synoniem met",
    "antonym": "is tegengestelde van",
    "property_of": "is eigenschap van",
    "used_for": "wordt gebruikt voor",
    "None": "(relatietype ontbreekt!)",
}

# hoe een relatie heet als je hem vanaf de ANDERE kant leest (voor het zijpaneel van de 3D-graaf)
INVERS_NL = {
    "is_a": "hiervan zijn soorten",
    "part_of": "heeft als deel",
    "has_part": "is deel van",
    "causes": "wordt veroorzaakt door",
    "property_of": "heeft als eigenschap",
    "used_for": "wordt hiervoor gebruikt",
}


def _veilig(tekst):
    """Haalt tekens weg waarmee HTML of JavaScript in de pagina zou kunnen sluipen."""
    if tekst is None:
        return ""
    tekst = str(tekst)
    for teken in ("<", ">", "&", '"', "'", "`", "\\"):
        tekst = tekst.replace(teken, " ")
    return " ".join(tekst.split())


def veilige_bestandsnaam(naam):
    """'Mijn Fiets!!' -> 'mijn_fiets.html'. Nooit een pad, altijd .html."""
    naam = os.path.basename(str(naam)).lower()
    if naam.endswith(".html"):
        naam = naam[:-5]
    naam = re.sub(r"[^a-z0-9_-]+", "_", naam).strip("_")
    return (naam or "graaf") + ".html"


def _node_tekst(node):
    regels = [_veilig(node["label"])]
    if node.get("definitie"):
        regels.append(_veilig(node["definitie"])[:300])
    if node.get("ontstaan") is not None:
        regels.append(f"Ontstaan: {_veilig(node['ontstaan'])}")
    regels.append(f"Relaties: {node['aantal_relaties']}")
    if not node.get("bestaat", True):
        regels.append("(nog geen eigen concept)")
    return "\n".join(regels)


def _edge_tekst(edge):
    uitleg = LABELS_NL.get(edge["type"], _veilig(edge["type"]))
    regels = [f"{_veilig(edge['van'])} {uitleg} {_veilig(edge['naar'])}"]
    regels.append(f"Status: {_veilig(edge['status'])}")
    if edge.get("bron"):
        regels.append(f"Bron: {_veilig(edge['bron'])}")
    try:
        regels.append(f"Zekerheid: {float(edge['confidence']):.2f}")
    except (TypeError, ValueError):
        pass
    return "\n".join(regels)


def _pad_sleutels(pad):
    """Set van (van, naar) paren, in beide richtingen, om pad-pijlen rood te kunnen kleuren."""
    sleutels = set()
    for stap in pad or []:
        sleutels.add((stap["van"], stap["naar"]))
        sleutels.add((stap["naar"], stap["van"]))
    return sleutels


def _legenda(types):
    delen = []
    for t in sorted(types):
        kleur = KLEUREN.get(t, KLEUR_ONBEKEND)
        delen.append(f'<span style="color:{kleur};font-weight:bold">&#9644;</span> '
                     f'{_veilig(LABELS_NL.get(t, t))}')
    delen.append("&#9472;&#9472; bevestigd &nbsp; - - - niet bevestigd")
    return ('<div style="font-family:sans-serif;font-size:13px;padding:6px 10px;'
            'background:#f4f4f4;border-bottom:1px solid #ddd">' + " &nbsp;&nbsp; ".join(delen) + "</div>")


def render_html(graaf, pad=None, titel=None):
    """
    Maakt de HTML-tekst van een graaf (uitvoer van graph_data.bouw_graaf).
    `pad` is optioneel: uitvoer van graph_data.vind_pad(); die verbindingen worden rood.
    Geeft een string terug, schrijft niets weg.
    """
    if not PYVIS_BESCHIKBAAR:
        raise RuntimeError("pyvis is niet geinstalleerd")
    if not graaf.get("nodes"):
        raise ValueError("lege graaf: niets om te tekenen")

    net = Network(height="calc(100vh - 80px)", width="100%", directed=True,
                  cdn_resources="in_line", bgcolor="#ffffff", font_color="#222222")
    net.barnes_hut(gravity=-6000, central_gravity=0.25, spring_length=140)

    centrum = graaf["centrum"]
    for node in graaf["nodes"]:
        if node["id"] == centrum:
            kleur = KLEUR_CENTRUM
        elif not node.get("bestaat", True):
            kleur = KLEUR_NODE_ONTBREEKT
        else:
            kleur = KLEUR_NODE
        net.add_node(_veilig(node["id"]), label=_veilig(node["label"]),
                     title=_node_tekst(node), color=kleur,
                     size=12 + min(node["aantal_relaties"], 20) * 1.5 + (8 if node["id"] == centrum else 0),
                     font={"size": 18, "face": "sans-serif", "strokeWidth": 4, "strokeColor": "#ffffff"})

    op_pad = _pad_sleutels(pad)
    getekend = set()
    for edge in graaf["edges"]:
        kleur = KLEUREN.get(edge["type"], KLEUR_ONBEKEND)
        breedte = 1.5
        if (edge["van"], edge["naar"]) in op_pad:
            kleur, breedte = KLEUR_PAD, 4
        net.add_edge(_veilig(edge["van"]), _veilig(edge["naar"]),
                     title=_edge_tekst(edge), color=kleur, width=breedte,
                     dashes=(edge["status"] != "confirmed"),
                     arrows="to" if edge.get("gericht", True) else "")
        getekend.add(edge["type"])

    html = net.generate_html(notebook=False)
    # Pyvis laat bootstrap (alleen opmaak) nog van internet halen; we hebben het niet nodig
    html = re.sub(r'<link[^>]*cdn\.jsdelivr\.net[^>]*>', "", html)
    html = re.sub(r'<script[^>]*cdn\.jsdelivr\.net[^>]*></script>', "", html)

    kop = _veilig(titel) if titel else f"Kennisgraaf rond {_veilig(centrum)}"
    extra = ""
    if graaf.get("afgekapt"):
        extra = " (afgekapt: er zijn meer buren dan getoond)"
    balk = f'<div style="font-family:sans-serif;padding:8px 10px;font-weight:bold">{kop}{extra}</div>' + _legenda(getekend)
    return html.replace("<body>", "<body>" + balk, 1)


def schrijf_html(graaf, bestandsnaam, map_pad=STANDAARD_MAP, pad=None, titel=None):
    """Schrijft de pagina in `map_pad` en geeft het volledige pad terug."""
    html = render_html(graaf, pad=pad, titel=titel)
    os.makedirs(map_pad, exist_ok=True)
    volledig = os.path.join(map_pad, veilige_bestandsnaam(bestandsnaam))
    tijdelijk = volledig + ".tmp"
    with open(tijdelijk, "w", encoding="utf-8") as f:
        f.write(html)
    os.replace(tijdelijk, volledig)       # atomisch: nooit een half bestand
    return volledig