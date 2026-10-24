# modules/knowledge/graph_commands.py

"""
graph_commands.py -- Semantic Fase 13.3: chatcommando's voor de kennisgraaf.

Luistert naar drie events die intent_router.py stuurt:
  intent_graph_show   {"word": "fiets", "diepte": 1}     "toon graaf van fiets"
  intent_graph_path   {"word_a": ..., "word_b": ...}     "hoe zijn fiets en auto verbonden"
  intent_graph_stats  {}                                 "graaf statistieken"
  intent_graph_all    {}                                 "toon de hele kennisgraaf"

Wat het doet:
  - alle antwoorden: heeft Nova een verbonden laptop, dan wordt de pagina ook meteen op de laptop geopend
    (commando "open_html" via client_bridge, zie _open_op_laptop)
  - show : maakt een interactieve 3D-pagina (graph_render_3d) in data/graphs/<woord>_3d.html
  - path : zoekt het kortste pad (graph_data.vind_pad), vertelt het in gewone zinnen en maakt
           een pagina waarin dat pad rood is (data/graphs/pad_<a>_<b>.html)
  - stats: antwoordt met de meting (graph_data.statistieken_tekst)

100% symbolisch: opzoeken, tellen en tekenen. Geen ML, geen generatie.

Het bestand komt altijd op de plek waar Nova draait (data/graphs/) en Nova zegt waar. Is de laptop
verbonden, dan wordt het bestand gecomprimeerd (gzip + base64) naar de laptop gestuurd en daar in
de standaardbrowser geopend. Is de laptop niet verbonden, dan blijft het bij het bestand op de server.
"""

import base64
import gzip
import os

from modules.knowledge import graph_data
from modules.knowledge.graph_render import LABELS_NL, STANDAARD_MAP

MAX_NAAR_LAPTOP_BYTES = 12 * 1024 * 1024   # grotere pagina's sturen we niet (de laptop weigert > 20 MB)
OPEN_HTML_TIMEOUT = 20                     # seconden wachten tot de laptop de pagina geopend heeft
MAX_DIEPTE_CHAT = 3          # hoger geeft in het begin al een kluwen; klikken breidt verder uit


def _dbg(tekst):
    print(f"[GRAAF] {tekst}")


class GraafCommands:
    def __init__(self, event_bus, semantic=None, map_pad=STANDAARD_MAP):
        self.event_bus = event_bus
        self.semantic = semantic
        self.map_pad = map_pad
        event_bus.subscribe("intent_graph_show", self.on_show)
        event_bus.subscribe("intent_graph_path", self.on_path)
        event_bus.subscribe("intent_graph_stats", self.on_stats)
        event_bus.subscribe("intent_graph_all", self.on_all)

    # ------------------------------------------------------------------
    # hulpjes
    # ------------------------------------------------------------------
    def _concepten(self):
        """De concepts-dictionary van semantic, of None als die er (nog) niet is."""
        store = getattr(self.semantic, "store", None)
        return getattr(store, "concepts", None)

    def _antwoord(self, tekst):
        self.event_bus.publish("layer4_response", {"text": tekst})

    def _geen_kennis(self):
        self._antwoord("Ik kan de kennisgraaf nu niet openen: mijn kennis is nog niet geladen.")

    @staticmethod
    def _stap_tekst(stap):
        """'wiel is deel van fiets', in de richting waarin de relatie echt is opgeslagen."""
        van, naar = stap["van"], stap["naar"]
        if stap["omgekeerd"]:
            van, naar = naar, van
        return f"{van} {LABELS_NL.get(stap['type'], stap['type'])} {naar}"

    def _open_op_laptop(self, pad):
        """
        Stuurt de pagina naar de laptop en laat hem daar openen. Geeft een korte zin terug om aan
        het antwoord te hangen ("" als er niets te melden valt, bv. geen client_bridge geladen).
        Gooit nooit een fout: het antwoord over het bestand zelf blijft altijd geldig.
        """
        bridge = getattr(self.event_bus, "modules", {}).get("client_bridge")
        if bridge is None:
            return ""
        try:
            if not bridge.is_laptop_verbonden():
                return " Je laptop is niet verbonden, dus ik kon hem daar niet openen."
            if os.path.getsize(pad) > MAX_NAAR_LAPTOP_BYTES:
                return " De pagina is te groot om naar je laptop te sturen."
            with open(pad, "rb") as f:
                inhoud = base64.b64encode(gzip.compress(f.read(), compresslevel=6)).decode("ascii")
            resultaat = bridge.stuur_commando_naar_laptop(
                "open_html", {"bestandsnaam": os.path.basename(pad), "inhoud": inhoud},
                timeout_seconden=OPEN_HTML_TIMEOUT)
        except Exception as fout:
            _dbg(f"fout bij sturen naar laptop: {fout}")
            return f" Naar je laptop sturen lukte niet: {fout}"
        if resultaat.get("ok"):
            return " Hij is ook geopend op je laptop."
        return f" Openen op je laptop lukte niet: {resultaat.get('reden') or 'onbekende fout'}."

    # ------------------------------------------------------------------
    # toon graaf van X
    # ------------------------------------------------------------------
    def on_show(self, data):
        concepten = self._concepten()
        if concepten is None:
            return self._geen_kennis()

        woord = str(data.get("word", "")).strip().lower()
        try:
            diepte = int(data.get("diepte") or 1)
        except (TypeError, ValueError):
            diepte = 1
        diepte = max(1, min(diepte, MAX_DIEPTE_CHAT))

        start = graph_data.bouw_graaf(concepten, woord, diepte=diepte)
        if start["fout"] == "onbekend":
            return self._antwoord(f"Ik ken '{woord}' nog niet, dus ik kan er geen graaf van maken.")
        if start["fout"] == "geen_relaties":
            return self._antwoord(f"'{woord}' heeft nog geen relaties met andere woorden, "
                                  f"dus er valt nog niets te tekenen.")

        try:
            from modules.knowledge import graph_render_3d
            pad = graph_render_3d.schrijf_html_3d(concepten, woord, map_pad=self.map_pad, diepte=diepte)
        except Exception as fout:
            _dbg(f"fout bij maken pagina: {fout}")
            return self._antwoord(f"De graaf maken lukte niet: {fout}")

        aantal = len(start["nodes"])
        extra = " Er zijn meer buren dan ik nu laat zien." if start["afgekapt"] else ""
        self._antwoord(
            f"Ik heb de graaf van {woord} gemaakt: {aantal} woorden om mee te beginnen.{extra} "
            f"Klik in de pagina op een woord om meer te tonen. Bestand: {pad}.{self._open_op_laptop(pad)}")

    # ------------------------------------------------------------------
    # toon de hele kennisgraaf
    # ------------------------------------------------------------------
    def on_all(self, data):
        concepten = self._concepten()
        if concepten is None:
            return self._geen_kennis()
        try:
            from modules.knowledge import graph_render_3d
            pad = graph_render_3d.schrijf_html_3d(concepten, None, map_pad=self.map_pad)
        except Exception as fout:
            _dbg(f"fout bij maken pagina: {fout}")
            return self._antwoord(f"De graaf maken lukte niet: {fout}")
        self._antwoord("Ik heb de hele kennisgraaf gemaakt, met kleuren per groep woorden. "
                       "Zoek een woord, klik erop of laat een pad tussen twee woorden zien. "
                       f"Bestand: {pad}.{self._open_op_laptop(pad)}")

    # ------------------------------------------------------------------
    # hoe zijn X en Y verbonden
    # ------------------------------------------------------------------
    def on_path(self, data):
        concepten = self._concepten()
        if concepten is None:
            return self._geen_kennis()

        a = str(data.get("word_a", "")).strip().lower()
        b = str(data.get("word_b", "")).strip().lower()

        onbekend = [w for w in (a, b) if graph_data._sleutel_opzoeken(concepten, w) is None]
        if onbekend:
            namen = " en ".join(f"'{w}'" for w in onbekend)
            return self._antwoord(f"Ik ken {namen} nog niet, dus ik kan geen verbinding zoeken.")
        if a == b:
            return self._antwoord(f"Dat is hetzelfde woord: {a}.")

        stappen = graph_data.vind_pad(concepten, a, b)
        if not stappen:
            return self._antwoord(f"Ik vind geen verbinding tussen {a} en {b} "
                                  f"(ik zoek tot {graph_data.MAX_PAD_DIEPTE} stappen ver).")

        uitleg = "; ".join(self._stap_tekst(s) for s in stappen)
        zin = f"{a} en {b} hangen zo samen ({len(stappen)} stappen): {uitleg}."

        try:
            from modules.knowledge import graph_render_3d
            bestand = graph_render_3d.schrijf_html_3d(
                concepten, a, bestandsnaam=f"pad_{a}_{b}", map_pad=self.map_pad, diepte=1, pad=stappen,
                per_betekenis=False)
            zin += f" Bestand met het pad in het rood: {bestand}.{self._open_op_laptop(bestand)}"
        except Exception as fout:           # het antwoord in woorden blijft gewoon geldig
            _dbg(f"fout bij maken pagina: {fout}")
        self._antwoord(zin)

    # ------------------------------------------------------------------
    # graaf statistieken
    # ------------------------------------------------------------------
    def on_stats(self, data):
        concepten = self._concepten()
        if concepten is None:
            return self._geen_kennis()
        self._antwoord(graph_data.statistieken_tekst(graph_data.statistieken(concepten)))


def init_module(event_bus, sem=None):
    return GraafCommands(event_bus, sem)