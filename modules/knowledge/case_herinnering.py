# modules/knowledge/case_herinnering.py
#
# Case-based reasoning (Taal & Redeneerlimieten, idee 3).
#
# Nova zoekt zelf een VERGELIJKBARE EERDERE VRAAG van Kevin in Layer 0
# (memory.py) en gebruikt die als referentiepunt: "Je vroeg dit eerder al,
# gisteren. Toen antwoordde ik hetzelfde." Twee manieren:
#
#   1. AUTOMATISCH, na een kennisvraag (is-een, onderdelen, oorzaken,
#      definities, ...): als Kevin iets vergelijkbaars al eerder vroeg,
#      komt NA het gewone antwoord een korte regel tussen haakjes.
#      Beperkt, zodat het niet irritant wordt: de oude vraag moet
#      minstens 1 uur geleden zijn, en per vraag-onderwerp hoogstens
#      1 keer per dag.
#   2. OP VRAAG: "heb ik dit al eens gevraagd" (over je vorige vraag) en
#      "wanneer vroeg ik dat laatst".
#   Aan/uit: "stop met terugblikken" / "blik weer terug" (blijft bewaard).
#
# HOE "VERGELIJKBAAR" WERKT (100% symbolisch, geen ML, geen embeddings):
#   - Van elke vraag houden we de INHOUDSWOORDEN over: vraagwoorden en
#     stopwoorden eruit, rest ingekort tot een stam (simplemma + een
#     kleine eigen regel voor meervouden, "honden" en "hond" worden gelijk).
#     "niet" en "geen" blijven staan: "is een hond een dier" en "is een
#     hond GEEN dier" zijn NIET dezelfde vraag.
#   - Twee vragen zijn vergelijkbaar als hun woordverzamelingen minstens
#     2 woorden delen EN minstens 60% overlap hebben (Jaccard). Een vraag
#     van 1 inhoudswoord moet exact gelijk zijn.
#   - Er wordt gezocht in de recente database, de archief-tabel en ook in
#     de gzip-archieven (> 1 jaar) in data/archive/.
#   - Wat Nova TOEN antwoordde, is het eerstvolgende 'chat_response'-event
#     (binnen 60 seconden) na de oude vraag. Vergelijking met het huidige
#     antwoord zegt of Nova's antwoord gelijk bleef of veranderde.

import glob
import gzip
import json
import os
import re
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

try:  # lemmatizer is een extra; zonder werkt de stam-regel hieronder nog steeds
    import simplemma
except Exception:  # pragma: no cover
    simplemma = None

try:
    from core.nl_stopwoorden import STOPWOORDEN as _GEDEELDE_STOPWOORDEN
except Exception:  # pragma: no cover
    _GEDEELDE_STOPWOORDEN = set()


# Vraag- en functiewoorden die nooit het ONDERWERP van een vraag zijn.
# BEWUST niet in deze lijst: "niet", "geen", "nooit", "niets" (ontkenning
# verandert de betekenis van een vraag).
_EXTRA_FUNCTIEWOORDEN = frozenset({
    "wat", "wie", "waar", "wanneer", "waarom", "hoe", "welke", "welk", "waarmee",
    "is", "zijn", "was", "waren", "ben", "bent", "wordt", "worden", "werd",
    "een", "de", "het", "dat", "dit", "die", "deze", "dan", "toch", "wel",
    "ik", "je", "jij", "u", "we", "wij", "jullie", "mij", "me", "jou", "hem", "haar",
    "heb", "hebt", "heeft", "hebben", "had", "hadden", "kan", "kun", "kunnen",
    "kunt", "zou", "zouden", "zal", "zullen", "mag", "mogen", "moet", "moeten",
    "ook", "nog", "nu", "al", "eens", "even", "toen", "eerder", "weer",
    "nova", "alsjeblieft", "graag", "misschien", "echt", "eigenlijk",
    "en", "of", "maar", "van", "voor", "met", "op", "in", "aan", "bij", "naar",
    "tot", "door", "om", "over", "te", "er", "hier", "daar", "uit", "als",
    "zo", "zeg", "vertel", "gevraagd", "vraag", "vroeg", "vragen",
})

# Ontkenningen worden NOOIT weggefilterd, ook niet als de gedeelde
# stopwoordenlijst (core/nl_stopwoorden.py) ze bevat: "is een hond een dier"
# en "is een hond geen dier" zijn tegengestelde vragen.
_NEGATIES = frozenset({"niet", "geen", "nooit", "niets", "niks"})

# Beginwoorden waaraan we een VRAAG herkennen als er geen vraagteken staat
# (Kevin typt die vaak niet). Een stelling als "een hond is een dier" is
# geen vraag, en Nova zegt dan niet "je vroeg".
_VRAAG_BEGIN = frozenset({
    "is", "zijn", "was", "waren", "wat", "wie", "waar", "wanneer", "waarom", "hoe",
    "welke", "welk", "heb", "hebben", "heeft", "kan", "kun", "kunnen", "kunt",
    "wordt", "worden", "mag", "moet", "zou", "zal", "vertel", "geef", "noem",
    "leg", "toon", "laat", "zeg", "ken", "weet", "bestaat", "hoeveel",
})


def is_vraag(tekst):
    t = (tekst or "").strip().lower()
    if not t:
        return False
    if t.endswith("?"):
        return True
    eerste = re.findall(r"[a-zà-ÿ]+", t)
    return bool(eerste) and eerste[0] in _VRAAG_BEGIN


_ZEER_KORT_ANTWOORD_VENSTER = 60  # seconden na de oude vraag waarin Nova's antwoord valt

_MAANDEN = ["januari", "februari", "maart", "april", "mei", "juni", "juli",
            "augustus", "september", "oktober", "november", "december"]

# Events waarmee Nova een KENNISVRAAG beantwoordt: komt zo'n event tijdens
# een bericht voorbij, dan komt dat bericht in aanmerking voor een terugblik.
KENNIS_INTENTS = (
    "intent_relation_check", "intent_part_of_check", "intent_causes_check",
    "intent_causes", "intent_effects", "intent_definition", "intent_subtypes_query",
    "intent_parts_query", "intent_parts_with_property", "intent_related_to",
    "intent_related_to_check", "intent_compare_concepts", "intent_bridge_query",
    "intent_synonym", "intent_antonym", "intent_used_for", "intent_properties",
    "intent_concept_overview", "intent_temporal_query", "intent_temporal_tijdlijn",
    "intent_temporal_omgekeerd", "intent_uncertainty_query", "intent_uncertainty_why",
)


# ---------------------------------------------------------------
# Hulpfuncties (zonder state, daardoor makkelijk apart te testen)
# ---------------------------------------------------------------
def _stam(woord):
    """Brengt een woord terug tot een vergelijkbare sleutel."""
    w = woord.lower()
    if simplemma is not None:
        try:
            w = simplemma.lemmatize(w, lang="nl").lower()
        except Exception:
            pass
    # Eigen regel voor meervouden die simplemma mist ("katten" -> "kat").
    if len(w) > 4 and w.endswith("en"):
        w = w[:-2]
        if len(w) > 2 and w[-1] == w[-2] and w[-1] not in "aeiou":
            w = w[:-1]
    elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    return w


def inhoudssleutels(tekst):
    """Geeft de verzameling stam-sleutels van de inhoudswoorden van een vraag."""
    sleutels = set()
    for token in re.findall(r"[a-zà-ÿ0-9]+", (tekst or "").lower()):
        if token not in _NEGATIES and (
                token in _EXTRA_FUNCTIEWOORDEN or token in _GEDEELDE_STOPWOORDEN):
            continue
        sleutels.add(_stam(token))
    return frozenset(sleutels)


def _tokens(tekst):
    return [t for t in re.findall(r"[a-zà-ÿ0-9]+", (tekst or "").lower())
            if t in _NEGATIES
            or (t not in _EXTRA_FUNCTIEWOORDEN and t not in _GEDEELDE_STOPWOORDEN)]


_NEGATIE_SLEUTELS = frozenset(_stam(w) for w in _NEGATIES)


def is_vergelijkbaar(a, b, min_overlap=2, min_jaccard=0.6):
    """a en b zijn frozensets van sleutels (zie inhoudssleutels)."""
    if not a or not b:
        return False
    # "is een hond een dier" en "is een hond GEEN dier" zijn tegengestelde
    # vragen: de ontkenningen moeten aan beide kanten gelijk zijn.
    if (a & _NEGATIE_SLEUTELS) != (b & _NEGATIE_SLEUTELS):
        return False
    if len(a) == 1 or len(b) == 1:
        return a == b
    overlap = len(a & b)
    if overlap < min_overlap:
        return False
    return overlap / len(a | b) >= min_jaccard


def _normaliseer_antwoord(tekst):
    return re.sub(r"[^a-z0-9à-ÿ]+", " ", (tekst or "").lower()).strip()


class CaseHerinneringModule:

    def __init__(self, event_bus, pad=None, klok=None, min_afstand_auto=3600,
                 min_overlap=2, min_jaccard=0.6, max_antwoord_tekens=200,
                 max_candidaten=20000):
        self.event_bus = event_bus
        self.klok = klok or time.time
        self.min_afstand_auto = min_afstand_auto
        self.min_overlap = min_overlap
        self.min_jaccard = min_jaccard
        self.max_antwoord_tekens = max_antwoord_tekens
        self.max_candidaten = max_candidaten

        if pad is None:
            pad = Path(__file__).resolve().parent.parent.parent / "data" / "case_herinnering.json"
        self.pad = Path(pad)

        # Persistente staat: aan/uit + wanneer welk onderwerp laatst getoond is.
        self.staat = {"aan": True, "getoond": {}}
        self._laad()

        # Geschiedenis van gewone berichten (geen terugblik-commando's).
        self._berichten = []           # lijst van (timestamp, tekst), nieuwste laatst
        self._laatste_antwoord = None  # laatste echte antwoord van Nova (voor "heb ik dit al gevraagd")

        # Per beurt (thread-local, zelfde idee als hypothese.py).
        self._lokaal = threading.local()
        self._gz_cache = None          # (handtekening, rijen)

        event_bus.subscribe("raw_user_message", self._on_raw)
        event_bus.subscribe("chat_response", self._on_antwoord)
        for naam in KENNIS_INTENTS:
            event_bus.subscribe(naam, self._on_kennis)
        event_bus.subscribe("intent_case_herinnering_vorige", self._on_vorige)
        event_bus.subscribe("intent_case_herinnering_laatst", self._on_laatst)
        event_bus.subscribe("intent_case_herinnering_aan", self._on_aan)
        event_bus.subscribe("intent_case_herinnering_uit", self._on_uit)
        event_bus.publish("module_loaded", {"name": "case_herinnering"})

    # ---------------------------------------------------------
    # Opslag van de instelling
    # ---------------------------------------------------------
    def _laad(self):
        try:
            with open(self.pad, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self.staat["aan"] = bool(data.get("aan", True))
                getoond = data.get("getoond", {})
                if isinstance(getoond, dict):
                    self.staat["getoond"] = {str(k): str(v) for k, v in getoond.items()}
        except (OSError, ValueError):
            pass  # geen of kapot bestand: standaardwaarden

    def _bewaar(self):
        try:
            self.pad.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.pad.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.staat, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.pad)
        except OSError:
            pass  # bewaren mislukt: geen crash, de instelling geldt dan tot de herstart

    # ---------------------------------------------------------
    # Beurt-beheer (aangeroepen door intent_router.route())
    # ---------------------------------------------------------
    def _diepte(self):
        return getattr(self._lokaal, "diepte", 0)

    def betreed_beurt(self):
        diepte = self._diepte()
        if diepte == 0:
            self._lokaal.kennis = False
            self._lokaal.expliciet = False
            self._lokaal.huidig = None
            self._lokaal.antwoord = None
        self._lokaal.diepte = diepte + 1

    def verlaat_beurt(self):
        diepte = max(0, self._diepte() - 1)
        self._lokaal.diepte = diepte
        if diepte != 0:
            return
        kennis = getattr(self._lokaal, "kennis", False)
        expliciet = getattr(self._lokaal, "expliciet", False)
        huidig = getattr(self._lokaal, "huidig", None)
        antwoord = getattr(self._lokaal, "antwoord", None)
        self._lokaal.kennis = False
        self._lokaal.expliciet = False
        self._lokaal.huidig = None
        self._lokaal.antwoord = None
        if antwoord:
            self._laatste_antwoord = antwoord
        if kennis and huidig and not expliciet and self.staat["aan"]:
            try:
                self._terugblik_auto(huidig, antwoord)
            except Exception as e:  # een terugblik mag een gewoon antwoord nooit breken
                print(f"[CASE_HERINNERING] fout bij terugblik: {e}")

    @contextmanager
    def _beurt(self):
        self.betreed_beurt()
        try:
            yield
        finally:
            self.verlaat_beurt()

    # ---------------------------------------------------------
    # Event-handlers die meekijken
    # ---------------------------------------------------------
    def _on_raw(self, data, event_type=None):
        tekst = (data or {}).get("text", "")
        if not tekst:
            return
        nu = self.klok()
        self._berichten.append((nu, tekst))
        del self._berichten[:-5]
        if self._diepte() > 0:
            self._lokaal.huidig = (nu, tekst)

    def _on_kennis(self, data, event_type=None):
        if self._diepte() > 0:
            self._lokaal.kennis = True

    def _on_antwoord(self, data, event_type=None):
        data = data or {}
        tekst = data.get("text", "")
        if data.get("source") in ("hypothese", "case_herinnering"):
            return
        if not tekst or tekst.startswith("("):
            return
        # Enkel binnen een gebruikersbericht: spontane meldingen van andere
        # modules (weer, waarschuwingen) zijn geen antwoord op een vraag.
        if self._diepte() > 0 and getattr(self._lokaal, "antwoord", None) is None:
            self._lokaal.antwoord = tekst

    # ---------------------------------------------------------
    # Toegang tot Layer 0 (memory.py)
    # ---------------------------------------------------------
    def _memory(self):
        return self.event_bus.modules.get("memory")

    def _db_rijen(self, sql_where, params, limiet):
        """Voert dezelfde SELECT uit op 'interactions' en 'interactions_old'."""
        mem = self._memory()
        if mem is None or getattr(mem, "conn", None) is None:
            return []
        try:
            mem._flush_buffer()
        except Exception:
            pass
        rijen = []
        with mem.lock:
            for tabel in ("interactions", "interactions_old"):
                try:
                    cur = mem.conn.execute(
                        f"SELECT timestamp, data FROM {tabel} WHERE {sql_where} "
                        f"ORDER BY timestamp DESC LIMIT ?", list(params) + [limiet])
                    rijen.extend((r[0], r[1]) for r in cur.fetchall())
                except Exception as e:
                    print(f"[CASE_HERINNERING] memory-fout: {e}")
        return rijen

    def _gz_rijen(self):
        """Alle events uit de gzip-archieven (> 1 jaar), gecachet tot er iets verandert."""
        mem = self._memory()
        if mem is None or not hasattr(mem, "save_path"):
            return []
        map_ = Path(mem.save_path).parent / "archive"
        bestanden = sorted(glob.glob(str(map_ / "*.jsonl.gz")))
        try:
            handtekening = tuple((b, os.path.getmtime(b)) for b in bestanden)
        except OSError:
            return []
        if self._gz_cache and self._gz_cache[0] == handtekening:
            return self._gz_cache[1]
        rijen = []
        for b in bestanden:
            try:
                with gzip.open(b, "rt", encoding="utf-8") as f:
                    for regel in f:
                        try:
                            r = json.loads(regel)
                        except ValueError:
                            continue
                        if r.get("event_type") in ("raw_user_message", "chat_response"):
                            rijen.append((r.get("timestamp", 0), r["event_type"], r.get("data", "")))
            except (OSError, EOFError):
                continue
        rijen.sort(key=lambda r: r[0])
        self._gz_cache = (handtekening, rijen)
        return rijen

    @staticmethod
    def _tekst_uit(data):
        try:
            d = json.loads(data) if isinstance(data, str) else data
            return d.get("text", "") if isinstance(d, dict) else ""
        except ValueError:
            return ""

    def _kandidaten(self, sleutels, tokens):
        """Eerdere berichten van Kevin die minstens een van de woorden bevatten."""
        patronen = sorted({s for s in list(sleutels) + list(tokens) if len(s) >= 3})
        if not patronen:
            return []
        where = "event_type = 'raw_user_message' AND (" + " OR ".join(["data LIKE ?"] * len(patronen)) + ")"
        params = [f"%{p}%" for p in patronen]
        kandidaten = [(ts, self._tekst_uit(d)) for ts, d in
                      self._db_rijen(where, params, self.max_candidaten)]
        for ts, soort, data in self._gz_rijen():
            if soort == "raw_user_message":
                tekst = self._tekst_uit(data)
                laag = tekst.lower()
                if any(p in laag for p in patronen):
                    kandidaten.append((ts, tekst))
        return [(ts, t) for ts, t in kandidaten if t]

    def _antwoord_na(self, ts):
        """Het eerste echte chat_response-antwoord van Nova kort na tijdstip ts."""
        gevonden = []
        mem = self._memory()
        if mem is not None and getattr(mem, "conn", None) is not None:
            rijen = self._db_rijen(
                "event_type = 'chat_response' AND timestamp > ? AND timestamp <= ?",
                [ts, ts + _ZEER_KORT_ANTWOORD_VENSTER], 20)
            gevonden.extend(rijen)
        for t, soort, data in self._gz_rijen():
            if soort == "chat_response" and ts < t <= ts + _ZEER_KORT_ANTWOORD_VENSTER:
                gevonden.append((t, data))
        for t, data in sorted(gevonden, key=lambda r: r[0]):
            try:
                d = json.loads(data) if isinstance(data, str) else data
            except ValueError:
                continue
            tekst = d.get("text", "") if isinstance(d, dict) else ""
            if not tekst or tekst.startswith("("):
                continue
            if d.get("source") in ("hypothese", "case_herinnering"):
                continue
            return tekst
        return None

    # ---------------------------------------------------------
    # De kern: zoek vergelijkbare eerdere vragen
    # ---------------------------------------------------------
    def zoek_vergelijkbaar(self, tekst, tot_tijdstip):
        """
        Geeft een lijst (tijdstip, tekst) van eerdere, vergelijkbare vragen,
        nieuwste eerst. Alles met tijdstip >= tot_tijdstip telt niet mee.
        """
        sleutels = inhoudssleutels(tekst)
        if not sleutels:
            return []
        resultaat = {}
        for ts, oud in self._kandidaten(sleutels, _tokens(tekst)):
            if ts >= tot_tijdstip:
                continue
            if is_vergelijkbaar(sleutels, inhoudssleutels(oud),
                                self.min_overlap, self.min_jaccard):
                resultaat[(round(ts, 3), oud)] = (ts, oud)
        return sorted(resultaat.values(), key=lambda r: r[0], reverse=True)

    # ---------------------------------------------------------
    # Formuleren
    # ---------------------------------------------------------
    def _wanneer(self, ts):
        nu = datetime.fromtimestamp(self.klok())
        dt = datetime.fromtimestamp(ts)
        dagen = (nu.date() - dt.date()).days
        uur = dt.strftime("%H:%M")
        if dagen <= 0:
            return f"vandaag om {uur}"
        if dagen == 1:
            return f"gisteren om {uur}"
        if dagen < 7:
            return f"{dagen} dagen geleden ({dt.day} {_MAANDEN[dt.month - 1]})"
        datum = f"{dt.day} {_MAANDEN[dt.month - 1]}"
        if dt.year != nu.year:
            datum += f" {dt.year}"
        return datum

    def _inkorten(self, tekst):
        tekst = " ".join(tekst.split())
        if len(tekst) <= self.max_antwoord_tekens:
            return tekst
        return tekst[: self.max_antwoord_tekens - 1].rstrip() + "…"

    def _antwoordzin(self, oud_antwoord, nieuw_antwoord):
        if not oud_antwoord:
            return ""
        if nieuw_antwoord and _normaliseer_antwoord(oud_antwoord) == _normaliseer_antwoord(nieuw_antwoord):
            return " Ik antwoordde toen hetzelfde."
        return f" Toen antwoordde ik: \"{self._inkorten(oud_antwoord)}\""

    def _stuur(self, tekst):
        self.event_bus.publish("chat_response", {"source": "case_herinnering", "text": tekst})

    # ---------------------------------------------------------
    # Automatisch
    # ---------------------------------------------------------
    def _terugblik_auto(self, huidig, antwoord):
        hyp = self.event_bus.modules.get("hypothese")
        if hyp is not None and hyp.heeft_aannames():
            return  # antwoorden onder een aanname zijn geen echte vergelijking
        ts_nu, tekst = huidig
        sleutels = inhoudssleutels(tekst)
        if not sleutels:
            return
        vandaag = datetime.fromtimestamp(self.klok()).strftime("%Y-%m-%d")
        onderwerp = "|".join(sorted(sleutels))
        if self.staat["getoond"].get(onderwerp) == vandaag:
            return
        matches = self.zoek_vergelijkbaar(tekst, min(ts_nu, self.klok() - self.min_afstand_auto))
        if not matches:
            return
        laatste_ts, laatste_tekst = matches[0]
        aantal = len(matches)
        basis = "Je vroeg dit eerder al" if is_vraag(laatste_tekst) \
            else "Je zei eerder al iets vergelijkbaars"
        zin = basis + (f", {aantal} keer" if aantal > 1 else "")
        zin += f". Laatst {self._wanneer(laatste_ts)}" if aantal > 1 else f", {self._wanneer(laatste_ts)}"
        if _normaliseer_antwoord(laatste_tekst) != _normaliseer_antwoord(tekst):
            zin += f", als \"{self._inkorten(laatste_tekst)}\""
        zin += "."
        zin += self._antwoordzin(self._antwoord_na(laatste_ts), antwoord)
        self._stuur("(" + zin + ")")

        self.staat["getoond"][onderwerp] = vandaag
        grens = datetime.fromtimestamp(self.klok() - 30 * 86400).strftime("%Y-%m-%d")
        self.staat["getoond"] = {k: v for k, v in self.staat["getoond"].items() if v >= grens}
        self._bewaar()

    # ---------------------------------------------------------
    # Op vraag
    # ---------------------------------------------------------
    def _vorige_vraag(self):
        """Haalt het commando zelf uit de geschiedenis en geeft de vraag daarvoor."""
        if self._berichten:
            self._berichten.pop()   # het terugblik-commando zelf telt niet als vraag
        return self._berichten[-1] if self._berichten else None

    def _on_vorige(self, data, event_type=None):
        self._beantwoord_op_vraag(korte_vorm=False)

    def _on_laatst(self, data, event_type=None):
        self._beantwoord_op_vraag(korte_vorm=True)

    def _beantwoord_op_vraag(self, korte_vorm):
        with self._beurt():
            self._lokaal.expliciet = True
            vorige = self._vorige_vraag()
            if vorige is None:
                self._stuur("Ik heb geen eerdere vraag van jou om dit mee te vergelijken.")
                return
            ts, tekst = vorige
            if not inhoudssleutels(tekst):
                self._stuur("Je vorige bericht had geen onderwerp waar ik iets mee kan vergelijken.")
                return
            matches = self.zoek_vergelijkbaar(tekst, ts - 2.0)
            if not matches:
                self._stuur("Nee, voor zover ik het kan terugvinden is dit de eerste keer dat je dit vraagt.")
                return
            laatste_ts, laatste_tekst = matches[0]
            if korte_vorm:
                self._stuur(f"Dat vroeg je laatst {self._wanneer(laatste_ts)}.")
                return
            aantal = len(matches)
            if is_vraag(laatste_tekst):
                zin = f"Ja, je vroeg dit al {aantal} keer eerder. Laatst {self._wanneer(laatste_ts)}"
            else:
                zin = f"Ja, iets vergelijkbaars kwam al {aantal} keer eerder voorbij. Laatst {self._wanneer(laatste_ts)}"
            if _normaliseer_antwoord(laatste_tekst) != _normaliseer_antwoord(tekst):
                zin += f", als \"{self._inkorten(laatste_tekst)}\""
            zin += "."
            zin += self._antwoordzin(self._antwoord_na(laatste_ts), self._laatste_antwoord)
            self._stuur(zin)

    def _on_aan(self, data, event_type=None):
        with self._beurt():
            self._lokaal.expliciet = True
            if self._berichten:
                self._berichten.pop()
            self.staat["aan"] = True
            self._bewaar()
            self._stuur("Oké, ik blik weer terug als je iets vraagt dat je eerder al vroeg.")

    def _on_uit(self, data, event_type=None):
        with self._beurt():
            self._lokaal.expliciet = True
            if self._berichten:
                self._berichten.pop()
            self.staat["aan"] = False
            self._bewaar()
            self._stuur("Oké, ik blik niet meer vanzelf terug. Vragen als 'heb ik dit al eens gevraagd' "
                        "beantwoord ik nog wel. Zeg 'blik weer terug' om het weer aan te zetten.")


def init_module(event_bus, sem=None):
    return CaseHerinneringModule(event_bus)