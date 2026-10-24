#moddules/knowledge/graph_render_3d.py

"""
graph_render_3d.py -- Semantic Fase 13.2b: interactieve 3D-kennisgraaf als HTML-bestand.

Maakt 1 HTML-bestand waarin je:
  - kunt ronddraaien (slepen), zoomen (scrollen) en schuiven (rechtermuisknop)
  - op een woord kunt KLIKKEN: dan verschijnen de buren van dat woord in de graaf, en rechts
    zie je de definitie en alle relaties van dat woord (ook klikbaar)
  - een woord kunt opzoeken, een pad tussen twee woorden kunt laten tekenen,
    en relatietypes aan/uit kunt zetten

Hoe het werkt: de HELE kennisgraaf zit als data in de pagina. Het uitbreiden gebeurt in de
browser (JavaScript), dus Nova hoeft niets te doen na het maken van het bestand en het
bestand werkt ook offline op je laptop. Het is een momentopname: nieuwe kennis die Nova
later leert zie je pas als je het bestand opnieuw laat maken.

100% symbolisch: dit is alleen tekenen en tellen. Geen ML, geen generatie.

De tekenbibliotheek (3d-force-graph, MIT-licentie, 1 bestand) staat in
modules/knowledge/vendor/3d-force-graph.min.js en wordt in de pagina gekopieerd.

Veiligheid:
  - Alle data staat als JSON in de pagina met < > & geescaped (\\u003c enz.), dus een definitie
    kan nooit de pagina uit breken.
  - In de browser wordt tekst alleen met textContent of met esc() getoond, nooit als ruwe HTML.
"""

import html as html_lib
import json
import os
import re

from modules.knowledge import graph_data
from modules.knowledge.graph_render import (
    INVERS_NL, KLEUREN, LABELS_NL, STANDAARD_MAP, veilige_bestandsnaam,
)

LIB_PAD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor", "3d-force-graph.min.js")

MAX_DEFINITIE = 400
MAX_START_NODES = 60
AANTAL_HUBS = 8

# kleuren van de groepen (helder, want de achtergrond is donker); meer groepen dan kleuren komt niet voor
GROEP_KLEUREN = [
    "#5aa9ff", "#4cd38a", "#ffb347", "#ff6b9a", "#c08bff", "#4fe0e0", "#f2d95c", "#ff7a59",
    "#9be564", "#e07bff", "#6ee7b7", "#f59ec7", "#7fb3ff", "#ffd27f", "#b0e0e6", "#d4a5ff",
]

# helderdere kleuren, want de achtergrond is donker
KLEUREN_3D = {
    "is_a": "#5aa9ff",
    "part_of": "#4cd38a",
    "causes": "#ffa94d",
    "related_to": "#a0a7b4",
    "synonym": "#c08bff",
    "antonym": "#ff6b9a",
    "property_of": "#f2d95c",
    "used_for": "#4fe0e0",
    "None": "#ff3b3b",
    "betekenis": "#c9d1e6",
}


def _lees_bibliotheek():
    try:
        with open(LIB_PAD, encoding="utf-8") as f:
            tekst = f.read()
    except OSError:
        raise RuntimeError(
            "3d-force-graph.min.js ontbreekt. Zet het bestand in modules/knowledge/vendor/ "
            f"(verwacht pad: {LIB_PAD})")
    tekst = re.sub(r"//# sourceMappingURL=\S+", "", tekst)
    if "</script" in tekst.lower():
        raise RuntimeError("bibliotheek bevat </script en kan niet veilig worden ingebed")
    return tekst


def _json_veilig(data):
    """JSON die veilig tussen <script>-tags kan staan."""
    tekst = json.dumps(data, ensure_ascii=True, separators=(",", ":"))
    return tekst.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _bouw_data(concepten, centrum, diepte, max_start, toon_afgewezen, pad, per_betekenis=True):
    """
    centrum=None betekent: de HELE kennis als startbeeld (overzicht).
    per_betekenis=True: woorden met meerdere betekenissen krijgen een tak per betekenis (13.5).
    """
    woorden = graph_data.volledige_graaf(concepten, toon_afgewezen=toon_afgewezen)   # 1 bolletje per woord
    alles = (graph_data.volledige_graaf(concepten, toon_afgewezen=toon_afgewezen, per_betekenis=True)
             if per_betekenis else woorden)

    if centrum is None:
        start_ids = [n["id"] for n in woorden["nodes"] if n["aantal_relaties"] > 0]
        start_centrum, afgekapt = None, False
    else:
        start = graph_data.bouw_graaf(concepten, centrum, diepte=diepte, max_nodes=max_start,
                                      toon_afgewezen=toon_afgewezen)
        if start["fout"] == "onbekend":
            raise ValueError(f"onbekend concept: {centrum}")
        start_ids = [n["id"] for n in start["nodes"]]
        start_centrum, afgekapt = start["centrum"], bool(start["afgekapt"])

    # de groepen worden altijd op woordniveau bepaald (takken erven de groep van hun stam)
    toewijzing, groepen = graph_data.gemeenschappen(woorden["nodes"], woorden["edges"])

    # takken van woorden die in het startbeeld staan, staan er ook bij
    if per_betekenis:
        in_start = set(start_ids)
        start_ids = start_ids + [n["id"] for n in alles["nodes"] if n.get("stam") in in_start]

    nodes = []
    for n in alles["nodes"]:
        definitie = (n["definitie"] or "")[:MAX_DEFINITIE]
        knoop = {"id": n["id"], "label": n["label"], "def": definitie,
                 "ontstaan": n["ontstaan"], "n": n["aantal_relaties"], "bestaat": n["bestaat"],
                 "c": toewijzing.get(n.get("stam", n["id"]), -1)}
        if n.get("stam"):
            knoop["stam"] = n["stam"]
            knoop["betekenis"] = n["betekenis"]
        nodes.append(knoop)
    for i, groep in enumerate(groepen):
        groep["kleur"] = GROEP_KLEUREN[i % len(GROEP_KLEUREN)]

    hubs = [n["id"] for n in sorted(
        (n for n in nodes if n["bestaat"] and "stam" not in n), key=lambda n: (-n["n"], n["id"]))[:AANTAL_HUBS]]

    pad_ids = []
    for stap in pad or []:
        for w in (stap["van"], stap["naar"]):
            if w not in pad_ids:
                pad_ids.append(w)

    return {
        "nodes": nodes,
        "edges": alles["edges"],
        "start": start_ids,
        "centrum": start_centrum,
        "afgekapt": afgekapt,
        "pad": pad_ids,
        "groepen": groepen,
        "hubs": hubs,
        "kleuren": KLEUREN_3D,
        "labels": LABELS_NL,
        "invers": INVERS_NL,
    }


def render_html_3d(concepten, centrum=None, diepte=1, max_start=MAX_START_NODES,
                   toon_afgewezen=False, pad=None, titel=None, per_betekenis=True):
    """
    Geeft de HTML-tekst van de interactieve 3D-graaf.
      concepten : de concepts-dictionary (ConceptStore.concepts of json.load(concepts.json))
      centrum   : woord waar de graaf mee begint; None = de hele kennis als overzicht
      diepte    : hoeveel stappen rond het centrum al getoond worden bij het openen (standaard 1)
      pad       : optioneel, uitvoer van graph_data.vind_pad(); wordt rood en blijft zichtbaar
      per_betekenis : woorden met meerdere betekenissen krijgen een tak per betekenis (standaard aan).
                  Een pagina met `pad` (woordniveau) hoort op False te staan.
    """
    data = _bouw_data(concepten, centrum, diepte, max_start, toon_afgewezen, pad, per_betekenis)
    kop = titel or (f"Kennisgraaf van Nova: {data['centrum']}" if data["centrum"] else "Kennisgraaf van Nova")
    return (_TEMPLATE
            .replace("__TITEL__", html_lib.escape(kop))
            .replace("__DATA__", _json_veilig(data))
            .replace("__LIB__", _lees_bibliotheek()))


def schrijf_html_3d(concepten, centrum=None, bestandsnaam=None, map_pad=STANDAARD_MAP, **opties):
    """Schrijft de pagina in `map_pad` (atomisch) en geeft het volledige pad terug."""
    html = render_html_3d(concepten, centrum, **opties)
    os.makedirs(map_pad, exist_ok=True)
    naam = veilige_bestandsnaam(bestandsnaam or (f"{centrum}_3d" if centrum else "alles_3d"))
    volledig = os.path.join(map_pad, naam)
    tijdelijk = volledig + ".tmp"
    with open(tijdelijk, "w", encoding="utf-8") as f:
        f.write(html)
    os.replace(tijdelijk, volledig)
    return volledig


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITEL__</title>
<style>
  :root { --bg:#070a14; --paneel:rgba(10,14,28,.9); --rand:#222c4a; --tekst:#e6e9f0; --zacht:#8e99b8; --accent:#5aa9ff; }
  html, body { margin:0; height:100%; background:var(--bg); color:var(--tekst);
               font-family: system-ui, -apple-system, "Segoe UI", sans-serif; overflow:hidden; font-size:13px; }
  #graaf { position:absolute; inset:0; }
  #labels { position:absolute; inset:0; pointer-events:none; overflow:hidden; z-index:2; }
  .lbl { position:absolute; left:0; top:0; font-size:12px; color:#dfe6f7; white-space:nowrap;
         text-shadow:0 0 4px #070a14, 0 0 4px #070a14, 0 0 4px #070a14; margin:9px 0 0 9px; }
  .lbl.hub { font-size:14px; font-weight:600; color:#fff; }
  .lbl.sel { font-size:15px; font-weight:700; color:#fff; }
  #links { position:absolute; top:0; left:0; bottom:0; width:292px; z-index:5; box-sizing:border-box; padding:14px;
           background:var(--paneel); border-right:1px solid var(--rand); overflow-y:auto; }
  #links.dicht { transform:translateX(-292px); }
  #knopdicht { position:absolute; left:292px; top:10px; z-index:6; background:var(--paneel); border:1px solid var(--rand);
               color:var(--zacht); border-radius:0 6px 6px 0; padding:4px 7px; cursor:pointer; }
  #links.dicht + #knopdicht { left:0; }
  h1 { margin:0 0 2px; font-size:16px; letter-spacing:.04em; }
  .sub { color:var(--zacht); font-size:12px; margin-bottom:10px; }
  .kop { margin:14px 0 6px; font-size:10.5px; letter-spacing:.14em; color:var(--zacht); text-transform:uppercase; }
  input[type=text] { background:#0f1530; color:var(--tekst); border:1px solid #2c3963; border-radius:6px;
                     padding:6px 8px; width:100%; box-sizing:border-box; }
  .rij { display:flex; gap:6px; align-items:center; margin:5px 0; }
  .rij input[type=text] { width:auto; flex:1; min-width:0; }
  button { background:#223a73; color:#fff; border:0; border-radius:6px; padding:5px 10px; cursor:pointer; }
  button:hover { background:#34509a; }
  button.zacht { background:#141b36; border:1px solid var(--rand); color:var(--tekst); }
  #inspector { background:#0c1228; border:1px solid var(--rand); border-radius:8px; padding:9px 10px; min-height:44px; }
  #inspector h2 { margin:0 0 4px; font-size:16px; }
  #inspector .def { color:#c3cbe0; margin-bottom:6px; }
  #inspector .hint { color:var(--zacht); }
  #inspector .groep { margin-top:8px; font-weight:600; }
  #inspector .rel { display:block; width:100%; text-align:left; background:none; border:0; color:#8fc2ff; padding:1px 0; font-size:13px; }
  #inspector .rel:hover { text-decoration:underline; background:none; }
  #inspector .zwak { opacity:.6; font-style:italic; }
  .hub-rij { display:flex; justify-content:space-between; width:100%; background:none; border:0; padding:4px 2px;
             color:var(--tekst); text-align:left; border-bottom:1px solid #131a33; border-radius:0; }
  .hub-rij:hover { background:#121a36; }
  .hub-rij span.n { color:var(--zacht); }
  .stip { display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:7px; }
  .regel { display:flex; align-items:center; gap:8px; margin:4px 0; }
  .regel label { flex:0 0 78px; color:var(--zacht); }
  .regel input[type=range] { flex:1; }
  label.type { display:block; cursor:pointer; user-select:none; margin:3px 0; }
  #melding { color:#ffd166; min-height:1.2em; margin-top:8px; }
  #uitleg { color:var(--zacht); font-size:11.5px; margin-top:12px; line-height:1.5; }
  #rechts { position:absolute; top:12px; right:12px; z-index:5; width:200px; background:var(--paneel);
            border:1px solid var(--rand); border-radius:8px; padding:9px 11px; max-height:70vh; overflow-y:auto; }
  #rechts .kop { margin-top:0; }
  .groeprij { display:flex; align-items:center; gap:7px; margin:4px 0; cursor:pointer; user-select:none; }
  .groeprij .gn { margin-left:auto; color:var(--zacht); }
  #boven { position:absolute; top:12px; left:50%; transform:translateX(-50%); z-index:5; display:flex; gap:8px; }
  .scene-tooltip { color:#fff !important; }
  @media (max-width: 800px) { #rechts { display:none; } }
</style>
</head>
<body>
<div id="graaf"></div>
<div id="labels"></div>

<div id="links">
  <h1>__TITEL__</h1>
  <div class="sub" id="telling"></div>
  <div class="rij"><input type="text" id="zoek" list="woorden" placeholder="Zoek een woord..."><button id="zoekknop">Toon</button></div>

  <div class="kop">Inspector</div>
  <div id="inspector"><div class="hint">Klik op een woord: alleen dat woord en zijn verbindingen lichten op en je leest hier de uitleg. Klik op een leeg stuk om los te laten.</div></div>
  <div id="melding"></div>

  <div class="kop" style="display:none">Meest verbonden</div>
  <div id="hubs" style="display:none"></div>

  <div class="kop">Pad tussen twee woorden</div>
  <div class="rij"><input type="text" id="padA" list="woorden" placeholder="van"><input type="text" id="padB" list="woorden" placeholder="naar"></div>
  <button id="padknop" class="zacht">Toon pad</button>

  <div class="kop">Krachten</div>
  <div class="regel"><label>Afstoting</label><input type="range" id="krachtAfstoot" min="10" max="300" value="60"></div>
  <div class="regel"><label>Lijnlengte</label><input type="range" id="krachtLengte" min="10" max="200" value="45"></div>

  <div class="kop">Relatietypes</div>
  <div id="typen"></div>

  <div class="kop">Weergave</div>
  <label class="type"><input type="checkbox" id="draai"> langzaam draaien</label>
  <label class="type"><input type="checkbox" id="alleLabels"> alle namen tonen</label>
  <div class="rij"><button id="reset" class="zacht">Terug naar begin</button></div>

  <div id="uitleg">Slepen: draaien &middot; scrollen: zoomen &middot; rechtermuisknop: schuiven &middot; lichtere lijn: niet bevestigd &middot; pijl: richting van de relatie &middot; kleuren: groepen woorden die veel met elkaar verbonden zijn.</div>
</div>
<div id="knopdicht" title="paneel in- of uitklappen">&#9664;</div>

<div id="boven"><button id="fit" class="zacht">Alles in beeld</button></div>

<div id="rechts" style="display:none"><div class="kop">Groepen</div><div id="groepen"></div></div>
<datalist id="woorden"></datalist>

<script type="application/json" id="data">__DATA__</script>
<script>__LIB__</script>
<script>
(function () {
"use strict";
var DATA = JSON.parse(document.getElementById("data").textContent);
var MAX_PER_KLIK = 30;
var ALLE_LABELS_TOT = 70;               // tot zoveel woorden in beeld: alle namen tonen
var GRIJS = "#7d8596", ONTBREEKT = "#4a5163", ACHTERGROND = "#070a14";

function esc(t) {
  return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) {
    return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];
  });
}
function rgb(hex) { return [parseInt(hex.substr(1,2),16), parseInt(hex.substr(3,2),16), parseInt(hex.substr(5,2),16)]; }
function naarHex(a) { return "#" + a.map(function (x) { return ("0" + Math.round(x).toString(16)).slice(-2); }).join(""); }
function meng(hex, naar, deel) {        // deel 0 = hex, 1 = naar
  var a = rgb(hex), b = rgb(naar);
  return naarHex([a[0] + (b[0]-a[0])*deel, a[1] + (b[1]-a[1])*deel, a[2] + (b[2]-a[2])*deel]);
}
function kleurType(t) { return DATA.kleuren[t] || "#8a8f9c"; }
function typeNaam(t) { return DATA.labels[t] || t; }
function el(id) { return document.getElementById(id); }
function melding(t) { el("melding").textContent = t || ""; }

var byId = {}, byLabel = {}, adj = {};
DATA.nodes.forEach(function (n) { byId[n.id] = n; byLabel[n.label.toLowerCase()] = n.id; adj[n.id] = []; });
DATA.edges.forEach(function (e) { adj[e.van].push(e); adj[e.naar].push(e); });
function andere(e, id) { return e.van === id ? e.naar : e.van; }
var tak = {};                                   // stam -> ids van zijn takken (woorden met meerdere betekenissen)
DATA.nodes.forEach(function (n) { if (n.stam) (tak[n.stam] = tak[n.stam] || []).push(n.id); });
function leden(id) { return [id].concat(tak[id] || []); }

var vis = {};                           // id -> node-object van de graaf
var gekozen = null, focus = null;       // focus = {id: true} voor het gekozen woord en zijn buren
var verborgenTypes = {}, verborgenGroepen = {};
var padSleutels = {};
var rotatie = false, alleLabels = false;
var hubSet = {}; DATA.hubs.forEach(function (id) { hubSet[id] = true; });

function groepKleur(n) {
  if (!n.d.bestaat) return ONTBREEKT;
  var g = DATA.groepen[n.d.c];
  return g ? g.kleur : GRIJS;
}
function nodeKleur(n) {
  var k = groepKleur(n);
  if (n.d.stam) k = meng(k, "#ffffff", 0.4);      // takken per betekenis: lichter dan hun stam
  if (n.id === gekozen) return "#ffffff";
  if (focus && !focus[n.id]) return meng(k, ACHTERGROND, 0.82);
  return k;
}
function linkKleur(l) {
  var sleutel = l.e.van + "|" + l.e.naar;
  if (padSleutels[sleutel]) return "#ff3b3b";
  var c = kleurType(l.e.type);
  if (l.e.status !== "confirmed") c = meng(c, "#ffffff", 0.45);
  if (focus && !(focus[l.e.van] && focus[l.e.naar] && (l.e.van === gekozen || l.e.naar === gekozen))) return meng(c, ACHTERGROND, 0.88);
  return meng(c, ACHTERGROND, focus ? 0 : 0.35);
}

var Graph = ForceGraph3D()(el("graaf"))
  .backgroundColor(ACHTERGROND)
  .nodeRelSize(3)
  .nodeResolution(14)
  .nodeOpacity(0.95)
  .nodeVal(function (n) { return 1 + Math.min(n.d.n, 40) * 0.45; })
  .nodeColor(nodeKleur)
  .nodeLabel(function (n) {
    var g = DATA.groepen[n.d.c];
    var t = "<b>" + esc(n.d.label) + "</b>" + (g ? " <span style='opacity:.7'>(" + esc(g.naam) + ")</span>" : "");
    if (n.d.def) t += "<br>" + esc(n.d.def.slice(0, 160));
    return t + "<br>relaties: " + n.d.n;
  })
  .linkColor(linkKleur)
  .linkWidth(function (l) { return padSleutels[l.e.van + "|" + l.e.naar] ? 3 : (l.e.status === "confirmed" ? 0.7 : 0.35); })
  .linkOpacity(0.8)
  .linkDirectionalArrowLength(function (l) { return l.e.gericht ? 3.5 : 0; })
  .linkDirectionalArrowRelPos(1)
  .linkLabel(function (l) {
    var t = esc(l.e.van) + " " + esc(typeNaam(l.e.type)) + " " + esc(l.e.naar) + "<br>status: " + esc(l.e.status);
    if (l.e.bron) t += "<br>bron: " + esc(l.e.bron);
    return t;
  })
  .onNodeClick(function (n) { kies(n.id, true); })
  .onBackgroundClick(function () { loslaten(); })
  .onNodeDragEnd(function (n) { n.fx = n.x; n.fy = n.y; n.fz = n.z; });

function kleurenVernieuwen() {          // nieuwe functie-referenties dwingen een herkleuring af
  Graph.nodeColor(function (n) { return nodeKleur(n); });
  Graph.linkColor(function (l) { return linkKleur(l); });
  maakLabels();
}

function zichtbaar(id) { var n = byId[id]; return !(n && verborgenGroepen[n.c]); }

function maakNode(id, nabij) {
  if (vis[id]) return vis[id];
  var o = { id: id, d: byId[id] };
  if (nabij && nabij.x !== undefined) {
    o.x = nabij.x + (Math.random() - 0.5) * 30; o.y = nabij.y + (Math.random() - 0.5) * 30; o.z = nabij.z + (Math.random() - 0.5) * 30;
  }
  vis[id] = o;
  return o;
}

function huidigeLinks() {
  var out = [];
  DATA.edges.forEach(function (e) {
    var opPad = padSleutels[e.van + "|" + e.naar];
    if (verborgenTypes[e.type] && !opPad) return;
    if (vis[e.van] && vis[e.naar] && zichtbaar(e.van) && zichtbaar(e.naar)) out.push({ source: e.van, target: e.naar, e: e });
  });
  return out;
}

function ververs() {
  var nodes = Object.keys(vis).filter(zichtbaar).map(function (k) { return vis[k]; });
  Graph.graphData({ nodes: nodes, links: huidigeLinks() });
  var nTakken = Object.keys(tak).reduce(function (som, k) { return som + tak[k].length; }, 0);
  el("telling").textContent = nodes.length + " van " + DATA.nodes.length + " zichtbaar (" + (DATA.nodes.length - nTakken) + " woorden"
    + (nTakken ? " + " + nTakken + " betekenis-takken" : "") + ") · " + DATA.edges.length + " verbindingen";
  maakLabels();
}

function uitbreiden(id) {
  var bron = vis[id], kandidaten = [];
  adj[id].forEach(function (e) {
    if (verborgenTypes[e.type]) return;
    var o = andere(e, id);
    if (!vis[o] && zichtbaar(o) && kandidaten.indexOf(o) < 0) kandidaten.push(o);
  });
  kandidaten.sort(function (a, b) { return byId[b].n - byId[a].n; });
  var nieuw = kandidaten.slice(0, MAX_PER_KLIK);
  nieuw.forEach(function (o) { maakNode(o, bron); });
  if (kandidaten.length > nieuw.length) melding(byId[id].label + ": nog " + (kandidaten.length - nieuw.length) + " buren verborgen. Klik nogmaals voor meer.");
  else if (nieuw.length === 0) melding(byId[id].label + ": alle buren zijn al zichtbaar.");
  else melding("");
}

function berekenFocus(id) {
  focus = {}; focus[id] = true;
  adj[id].forEach(function (e) { var o = andere(e, id); if (vis[o]) focus[o] = true; });
}

function kies(id, uitbreid) {
  if (!byId[id]) return;
  var eerst = !vis[id];
  maakNode(id, null);
  gekozen = id;
  if (uitbreid) uitbreiden(id);
  ververs();
  berekenFocus(id);
  kleurenVernieuwen();
  toonInspector(id);
  var o = vis[id];
  setTimeout(function () {
    if (o.x === undefined) return;
    var r = Math.hypot(o.x, o.y, o.z) || 1, f = 1 + 110 / r;
    Graph.cameraPosition({ x: o.x * f, y: o.y * f, z: o.z * f }, o, 900);
  }, eerst ? 400 : 0);
}

function loslaten() {
  if (gekozen === null) return;
  gekozen = null; focus = null;
  kleurenVernieuwen();
  toonInspector(null);
}

function toonInspector(id) {
  var p = el("inspector"); p.textContent = "";
  if (id === null) {
    var h0 = document.createElement("div"); h0.className = "hint";
    h0.textContent = "Klik op een woord: alleen dat woord en zijn verbindingen lichten op en je leest hier de uitleg. Klik op een leeg stuk om los te laten.";
    p.appendChild(h0); return;
  }
  var n = byId[id];
  var h = document.createElement("h2"); h.textContent = n.label; p.appendChild(h);
  var g = DATA.groepen[n.c];
  if (n.stam) { var bt = document.createElement("div"); bt.className = "hint"; bt.textContent = "betekenis " + n.betekenis + " van " + n.stam; p.appendChild(bt); }
  if (g) { var gg = document.createElement("div"); gg.className = "hint"; gg.textContent = "groep: " + g.naam; p.appendChild(gg); }
  var d = document.createElement("div"); d.className = "def";
  d.textContent = n.def || (n.bestaat ? "(geen definitie)" : "(nog geen eigen concept in Nova)");
  p.appendChild(d);
  if (n.ontstaan !== null && n.ontstaan !== undefined) { var o = document.createElement("div"); o.textContent = "Ontstaan: " + n.ontstaan; p.appendChild(o); }
  var groepen = {};
  adj[id].forEach(function (e) {
    var uit = e.van === id, naam, ander = andere(e, id);
    if (e.type === "betekenis") naam = uit ? typeNaam("betekenis") : DATA.invers["betekenis"];
    else if (e.gericht === false || uit) naam = typeNaam(e.type);
    else naam = DATA.invers[e.type] || (typeNaam(e.type) + " (omgekeerd)");
    (groepen[naam] = groepen[naam] || []).push({ id: ander, zwak: e.status !== "confirmed" });
  });
  Object.keys(groepen).forEach(function (naam) {
    var k = document.createElement("div"); k.className = "groep"; k.textContent = naam; p.appendChild(k);
    groepen[naam].sort(function (a, b) { return byId[a.id].label.localeCompare(byId[b.id].label); });
    groepen[naam].forEach(function (r) {
      var b = document.createElement("button"); b.className = "rel" + (r.zwak ? " zwak" : "");
      b.textContent = byId[r.id].label + (r.zwak ? " (niet bevestigd)" : "") + (vis[r.id] ? "" : "  +");
      b.onclick = function () { kies(r.id, false); };
      p.appendChild(b);
    });
  });
}

// ---------- labels als HTML bovenop de 3D-scene ----------
var labelEls = {};
function welkeLabels() {
  var ids = Object.keys(vis).filter(zichtbaar);
  if (alleLabels || ids.length <= ALLE_LABELS_TOT) return ids;
  return ids.filter(function (id) { return hubSet[id] || id === gekozen || (focus && focus[id]) || byId[id].n >= 14; });
}
function maakLabels() {
  var cont = el("labels"), gewenst = {};
  welkeLabels().forEach(function (id) { gewenst[id] = true; });
  Object.keys(labelEls).forEach(function (id) { if (!gewenst[id]) { cont.removeChild(labelEls[id]); delete labelEls[id]; } });
  Object.keys(gewenst).forEach(function (id) {
    if (labelEls[id]) return;
    var s = document.createElement("div"); s.className = "lbl"; s.textContent = byId[id].label;
    cont.appendChild(s); labelEls[id] = s;
  });
}
function tekenLabels() {
  var cam = Graph.camera(), q = cam.quaternion, cp = cam.position;
  var fx = -(2 * (q.x * q.z + q.w * q.y)), fy = -(2 * (q.y * q.z - q.w * q.x)), fz = -(1 - 2 * (q.x * q.x + q.y * q.y));
  Object.keys(labelEls).forEach(function (id) {
    var o = vis[id], s = labelEls[id];
    if (!o || o.x === undefined) { s.style.display = "none"; return; }
    var voor = (o.x - cp.x) * fx + (o.y - cp.y) * fy + (o.z - cp.z) * fz;
    if (voor <= 0) { s.style.display = "none"; return; }
    var c = Graph.graph2ScreenCoords(o.x, o.y, o.z);
    s.style.display = "block";
    s.style.transform = "translate(" + Math.round(c.x) + "px," + Math.round(c.y) + "px)";
    s.className = "lbl" + (id === gekozen ? " sel" : (hubSet[id] ? " hub" : ""));
    s.style.opacity = (focus && !focus[id]) ? "0.35" : "1";
  });
  if (rotatie) {
    var a = 0.004, x = cp.x, z = cp.z;
    Graph.cameraPosition({ x: x * Math.cos(a) - z * Math.sin(a), y: cp.y, z: x * Math.sin(a) + z * Math.cos(a) });
  }
  requestAnimationFrame(tekenLabels);
}

// ---------- pad zoeken (in de browser, over alle relaties) ----------
// De stam-tak-verbindingen tellen NIET mee als stap: zo wordt trap (pedaal) nooit via het woord "trap"
// verbonden met trap (in huis). Wie een stam intypt als begin of einde, mag wel met al zijn takken beginnen/eindigen.
function zoekPad(a, b) {
  if (a === b) return [a];
  var doelen = {}; leden(b).forEach(function (x) { doelen[x] = true; });
  var vorige = {}, rij = [];
  leden(a).forEach(function (x) { vorige[x] = null; rij.push([x, 0]); });
  while (rij.length) {
    var h = rij.shift(), id = h[0], diep = h[1];
    if (doelen[id] && diep > 0) { var p = [id], y = id; while (vorige[y] !== null) { y = vorige[y]; p.unshift(y); } return p; }
    if (diep >= 6) continue;
    var buren = adj[id].filter(function (e) { return e.type !== "betekenis"; }).map(function (e) { return andere(e, id); }).sort();
    for (var i = 0; i < buren.length; i++) {
      var o = buren[i];
      if (o in vorige) continue;
      vorige[o] = id;
      if (doelen[o]) { var pad = [o], x = o; while (vorige[x] !== null) { x = vorige[x]; pad.unshift(x); } return pad; }
      rij.push([o, diep + 1]);
    }
  }
  return null;
}
function toonPad(ids) {
  padSleutels = {};
  for (var i = 0; i < ids.length - 1; i++) { padSleutels[ids[i] + "|" + ids[i + 1]] = true; padSleutels[ids[i + 1] + "|" + ids[i]] = true; }
  ids.forEach(function (id, i) { maakNode(id, i > 0 ? vis[ids[i - 1]] : null); });
  ververs();
}

// ---------- knoppen en regelaars ----------
function zoekWoord(t) { return byLabel[String(t).trim().toLowerCase()]; }

el("zoekknop").onclick = function () {
  var id = zoekWoord(el("zoek").value);
  if (!id) { melding("Dat woord ken ik niet in de graaf."); return; }
  melding(""); kies(id, true);
};
el("zoek").onkeydown = function (e) { if (e.key === "Enter") el("zoekknop").onclick(); };

el("padknop").onclick = function () {
  var a = zoekWoord(el("padA").value), b = zoekWoord(el("padB").value);
  if (!a || !b) { melding("Een van de twee woorden ken ik niet in de graaf."); return; }
  var pad = zoekPad(a, b);
  if (!pad) { melding("Geen verbinding tussen " + byId[a].label + " en " + byId[b].label + " (binnen 6 stappen)."); return; }
  toonPad(pad);
  melding("Pad (" + (pad.length - 1) + " stappen): " + pad.map(function (id) { return byId[id].label; }).join(" → "));
  Graph.zoomToFit(800, 80);
};

el("fit").onclick = function () { Graph.zoomToFit(700, 60); };
el("draai").onchange = function () { rotatie = this.checked; };
el("alleLabels").onchange = function () { alleLabels = this.checked; maakLabels(); };
el("knopdicht").onclick = function () { el("links").classList.toggle("dicht"); };

function krachten() {
  // de graaf bouwt zijn simulatie pas op na het eerste beeld; tot dan is er niets om af te stellen
  try {
    var afstoot = -Number(el("krachtAfstoot").value), lengte = Number(el("krachtLengte").value);
    var c = Graph.d3Force("charge"), l = Graph.d3Force("link");
    if (c) c.strength(afstoot);
    if (l) l.distance(lengte);
    Graph.d3ReheatSimulation();
  } catch (fout) { /* te vroeg: de regelaars werken zodra de graaf staat */ }
}
el("krachtAfstoot").oninput = krachten;
el("krachtLengte").oninput = krachten;

el("reset").onclick = function () {
  Object.keys(vis).forEach(function (k) { delete vis[k]; });
  padSleutels = {}; gekozen = null; focus = null; melding("");
  toonInspector(null);
  begin();
};

// lijsten: meest verbonden, groepen, relatietypes, zoeklijst
(function () {
  var hubs = el("hubs");
  DATA.hubs.forEach(function (id) {
    var b = document.createElement("button"); b.className = "hub-rij";
    var a = document.createElement("span"); a.textContent = byId[id].label;
    var n = document.createElement("span"); n.className = "n"; n.textContent = byId[id].n;
    b.appendChild(a); b.appendChild(n); b.onclick = function () { kies(id, true); };
    hubs.appendChild(b);
  });

  var gc = el("groepen");
  DATA.groepen.forEach(function (g, i) {
    var r = document.createElement("label"); r.className = "groeprij";
    var c = document.createElement("input"); c.type = "checkbox"; c.checked = true;
    c.onchange = function () { verborgenGroepen[i] = !c.checked; ververs(); };
    var s = document.createElement("span"); s.className = "stip"; s.style.background = g.kleur;
    var t = document.createElement("span"); t.textContent = g.naam;
    var n = document.createElement("span"); n.className = "gn"; n.textContent = g.grootte;
    r.appendChild(c); r.appendChild(s); r.appendChild(t); r.appendChild(n); gc.appendChild(r);
  });
  if (!DATA.groepen.length) el("rechts").style.display = "none";

  var typen = {};
  DATA.edges.forEach(function (e) { typen[e.type] = (typen[e.type] || 0) + 1; });
  var tc = el("typen");
  Object.keys(typen).sort().forEach(function (t) {
    var l = document.createElement("label"); l.className = "type";
    var c = document.createElement("input"); c.type = "checkbox"; c.checked = true;
    c.onchange = function () { verborgenTypes[t] = !c.checked; ververs(); };
    var s = document.createElement("span"); s.textContent = " ■ "; s.style.color = kleurType(t);
    l.appendChild(c); l.appendChild(s); l.appendChild(document.createTextNode(typeNaam(t) + " (" + typen[t] + ")"));
    tc.appendChild(l);
  });

  var dl = el("woorden");
  DATA.nodes.forEach(function (n) { var o = document.createElement("option"); o.value = n.label; dl.appendChild(o); });
})();

function begin() {
  DATA.start.forEach(function (id) { maakNode(id, null); });
  if (DATA.pad.length > 1) { toonPad(DATA.pad); } else { ververs(); }
  if (DATA.centrum) {
    gekozen = DATA.centrum; berekenFocus(gekozen); toonInspector(gekozen);
    if (DATA.afgekapt) melding("Er zijn meer buren dan in het begin getoond. Klik op een woord om uit te breiden.");
  } else {
    gekozen = null; focus = null;
  }
  kleurenVernieuwen();
  setTimeout(krachten, 500);
  setTimeout(function () { Graph.zoomToFit(700, 70); }, DATA.start.length > 200 ? 3500 : 1800);
}

window.addEventListener("resize", function () { Graph.width(window.innerWidth).height(window.innerHeight); });
Graph.width(window.innerWidth).height(window.innerHeight);
begin();
tekenLabels();
})();
</script>
</body>
</html>
"""