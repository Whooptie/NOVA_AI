# modules/knowledge/knowledge_proposals.py
#
# Semantic Fase 11.2 -- voorstellen uit Wikipedia: tonen, overnemen, afwijzen.
#
#   "extraheer fiets"            -> Nova haalt de Wikipedia-inleiding op, laat
#                                    de extractor (11.1) er feiten in zoeken en
#                                    toont ze als genummerde lijst.
#   "neem 2 over"                -> voorstel 2 wordt opgeslagen EN meteen
#                                    bevestigd (jij hebt het immers gezien).
#   "neem alles over"            -> alle nog openstaande voorstellen.
#   "laat 2 vallen"              -> voorstel 2 wordt afgewezen (tombstone) en
#                                    komt nooit meer als voorstel terug.
#
# Belangrijk (besluit 1A): er wordt NIETS opgeslagen zolang jij niet
# "neem ... over" of "laat ... vallen" typt.
#
# Waarom andere commando's dan "bevestig N" / "wijs af N"? Die zijn al van de
# onzekerheidslijst (Fase 10.2, uncertainty.py). Twee lijsten met dezelfde
# commando's zouden elkaar in de weg zitten.
#
# Eerlijk over ML versus symbolisch: de zinnen worden door spaCy ontleed
# (ML, extern, zie knowledge_extractor.py). Alles in DIT bestand is symbolisch:
# filteren, nummeren, opslaan, afwijzen.
#
# Luistert op:
#   intent_kennis_extract   {"word"}
#   intent_kennis_keuze     {"actie": "neem"|"laat_vallen", "nummer": int|None,
#                            "alles": bool}
#
# Opslag-regels:
#   is_a      onderwerp is_a doel                (zoals het er staat)
#   has_part  "fiets bestaat uit wiel" wordt opgeslagen als de bestaande
#             conventie van Nova: wiel part_of fiets (deel -> geheel).
#   part_of   "X is een onderdeel van Y" wordt X part_of Y (Fase 11, 2B).
#   causes    "X veroorzaakt Y" / "X leidt tot Y" wordt X causes Y (Fase 11, 2B).
#   Bron "wikipedia", confidence 0.8. Bij overnemen daarna confirm_relation()
#   (status confirmed, confidence 1.0, oorspronkelijke_bron blijft "wikipedia").
#   Bij vallen laten: add_relation() + reject_relation() = tombstone, zodat
#   add_relation() dezelfde relatie nooit meer opnieuw toevoegt en de volgende
#   "extraheer" hem eruit filtert.

import json
import time
import urllib.error
import urllib.parse
import urllib.request

WIKI_CONFIDENCE = 0.8
BRON = "wikipedia"
MAX_VOORSTELLEN = 10
LIJST_GELDIG_SECONDEN = 600  # nummers blijven 10 minuten geldig (zoals 10.2)
MAX_WOORD_LENGTE = 40
TIMEOUT_SECONDEN = 8


def haal_wikipedia_intro(woord, timeout=TIMEOUT_SECONDEN):
    """Haalt de inleiding van een Nederlandse Wikipedia-pagina op
    (1 request). Geeft '' bij elke fout."""
    try:
        params = urllib.parse.urlencode({
            "action": "query", "prop": "extracts", "exintro": 1,
            "explaintext": 1, "redirects": 1, "format": "json",
            "titles": woord,
        })
        url = "https://nl.wikipedia.org/w/api.php?" + params
        req = urllib.request.Request(
            url, headers={"User-Agent": "Nova-AI/1.0 (educational project)"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        pagina = next(iter(data["query"]["pages"].values()))
        return pagina.get("extract", "") or ""
    except Exception:
        return ""


class KnowledgeProposals:
    def __init__(self, event_bus, sem=None, extractor=None, fetch=None):
        self.event_bus = event_bus
        self.sem = sem
        self._extractor = extractor      # mag van buitenaf komen (tests)
        self._fetch = fetch or haal_wikipedia_intro
        self._lijst = []                 # voorstellen; None = al behandeld
        self._lijst_tijd = 0.0
        self._lijst_woord = None
        event_bus.subscribe("intent_kennis_extract", self.on_extract)
        event_bus.subscribe("intent_kennis_keuze", self.on_keuze)
        event_bus.publish("module_loaded", {"name": "knowledge_proposals"})

    # ---------- hulpjes ----------
    def _toon(self, tekst):
        # chat_response (geen layer4_response): een lijst mag niet door de
        # toon-pipeline, die zet anders een '!' achter de laatste regel.
        self.event_bus.publish("chat_response",
                               {"source": "knowledge_proposals", "text": tekst})

    def _get_extractor(self):
        if self._extractor is not None:
            return self._extractor
        ex = self.event_bus.modules.get("knowledge_extractor")
        if ex is None:
            try:
                from modules.knowledge.knowledge_extractor import KnowledgeExtractor
                ex = KnowledgeExtractor(event_bus=self.event_bus)
            except Exception:
                ex = None
        self._extractor = ex
        return ex

    def _enkelvoud(self, woord):
        """Meervoud -> enkelvoud via Nova's bestaande regels (TeachEngine).
        Faalt stil naar het woord zelf."""
        te = getattr(self.sem, "teach_engine", None)
        fn = getattr(te, "_normalize_plural_if_noun", None)
        if fn is None:
            return woord
        try:
            return fn(woord, "noun") or woord
        except Exception:
            return woord

    @staticmethod
    def _zin(rel_type, s, t):
        s, t = s.replace("_", " "), t.replace("_", " ")
        if rel_type == "part_of":
            return f"'{s}' is onderdeel van '{t}'"
        if rel_type == "causes":
            return f"'{s}' veroorzaakt '{t}'"
        return f"{s} is een {t}"

    def _relatie_status(self, woord, rel_type, doel):
        """None = onbekend, 'bekend' = staat er al, 'afgewezen' = tombstone."""
        concept = self.sem.store.get_concept(woord)
        if not concept:
            return None
        status = None
        for sense in concept.get("senses", []):
            for rel in sense.get("relations", []):
                if rel.get("type") == rel_type and rel.get("target") == doel:
                    if rel.get("status") == "rejected":
                        return "afgewezen"
                    status = "bekend"
        return status

    def _vind_sense_id(self, woord, rel_type, doel):
        concept = self.sem.store.get_concept(woord)
        if not concept:
            return None
        for sense in concept.get("senses", []):
            for rel in sense.get("relations", []):
                if rel.get("type") == rel_type and rel.get("target") == doel:
                    return sense.get("sense_id")
        return None

    # ---------- voorstellen maken ----------
    def _naar_voorstel(self, feit):
        """Zet een extractor-feit om naar wat er opgeslagen zou worden."""
        if feit["relatie"] == "is_a":
            woord, rel_type = feit["onderwerp"], "is_a"
            doel = self._enkelvoud(feit["doel"])
        elif feit["relatie"] == "has_part":
            # "geheel heeft deel" -> deel part_of geheel
            woord, rel_type = self._enkelvoud(feit["doel"]), "part_of"
            doel = feit["onderwerp"]
        elif feit["relatie"] == "part_of":
            # "X is een onderdeel van Y" -> X part_of Y (deel -> geheel)
            woord, rel_type = self._enkelvoud(feit["onderwerp"]), "part_of"
            doel = self._enkelvoud(feit["doel"])
        elif feit["relatie"] == "causes":
            # "X veroorzaakt Y" -> X causes Y (gevolg in enkelvoud)
            woord, rel_type = feit["onderwerp"], "causes"
            doel = self._enkelvoud(feit["doel"])
        else:
            return None
        woord, doel = woord.lower().strip(), doel.lower().strip()
        if not woord or not doel or woord == doel:
            return None
        return {"word": woord, "relation_type": rel_type, "target": doel,
                "zin": feit.get("zin", "")}

    # ---------- "extraheer X" ----------
    def on_extract(self, data, event_type=None):
        woord = (data.get("word") or "").strip().lower().strip(".,!?;:")
        if not woord or len(woord) > MAX_WOORD_LENGTE:
            self._toon("Van welk woord wil je de Wikipedia-kennis bekijken? "
                       "Bv. 'extraheer fiets'.")
            return
        if self.sem is None:
            self._toon("De kennisbank is niet beschikbaar, dus ik kan niets voorstellen.")
            return

        ex = self._get_extractor()
        if ex is None or not ex.is_beschikbaar():
            reden = getattr(ex, "reden_uit", None) or "module niet geladen"
            self._toon(f"De extractor staat uit ({reden}), dus ik kan geen voorstellen maken.")
            return

        tekst = self._fetch(woord)
        if not tekst:
            self._toon(f"Ik kon de Wikipedia-inleiding van '{woord}' niet ophalen.")
            return

        feiten = ex.extract_from_text(tekst, zoekwoord=woord)

        voorstellen, gezien = [], set()
        al_bekend = afgewezen = 0
        for feit in feiten:
            v = self._naar_voorstel(feit)
            if v is None:
                continue
            sleutel = (v["word"], v["relation_type"], v["target"])
            if sleutel in gezien:
                continue
            gezien.add(sleutel)
            status = self._relatie_status(v["word"], v["relation_type"], v["target"])
            if status == "afgewezen":
                afgewezen += 1
                continue
            if status == "bekend":
                al_bekend += 1
                continue
            voorstellen.append(v)

        extra = []
        if al_bekend:
            extra.append(f"{al_bekend} stond(en) er al")
        if afgewezen:
            extra.append(f"{afgewezen} had je eerder afgewezen")
        toelichting = f" ({', '.join(extra)})" if extra else ""

        if not voorstellen:
            self._lijst = []
            if feiten:
                self._toon(f"Uit de inleiding van '{woord}' haal ik niets nieuws{toelichting}.")
            else:
                self._toon(f"Ik vond geen betrouwbare feiten over '{woord}' in de "
                           f"Wikipedia-inleiding. Dat betekent niet dat er niets te leren is, "
                           f"alleen dat mijn regels er niets zekers uit halen.")
            return

        meer = len(voorstellen) - MAX_VOORSTELLEN
        getoond = voorstellen[:MAX_VOORSTELLEN]
        self._lijst = list(getoond)
        self._lijst_tijd = time.time()
        self._lijst_woord = woord

        regels = [f"{n}. {self._zin(v['relation_type'], v['word'], v['target'])}"
                  for n, v in enumerate(getoond, 1)]
        if meer > 0:
            regels.append(f"... en nog {meer} meer (vraag later opnieuw)")
        kop = (f"Uit Wikipedia over '{woord}' kan ik dit voorstellen "
               f"(nog niets opgeslagen){toelichting}:")
        if len(getoond) == 1:
            voet = ("Typ 'neem 1 over' om het op te slaan, "
                    "of 'laat 1 vallen' om het af te wijzen.")
        else:
            voet = ("Typ 'neem 1 over' om er één op te slaan, 'neem alles over', "
                    "of 'laat 1 vallen' om er één af te wijzen.")
        self._toon(kop + "\n" + "\n".join(regels) + "\n" + voet)

    # ---------- "neem N over" / "laat N vallen" ----------
    def _lijst_actueel(self):
        if not self._lijst or time.time() - self._lijst_tijd > LIJST_GELDIG_SECONDEN:
            self._lijst = []
            return False
        return True

    def _neem_over(self, v):
        """Slaat een voorstel op en bevestigt het. Geeft een resultaatwoord."""
        w, t, d = v["word"], v["relation_type"], v["target"]
        toegevoegd = self.sem.add_relation(w, t, d, source=BRON, confidence=WIKI_CONFIDENCE)
        if not toegevoegd:
            status = self._relatie_status(w, t, d)
            return "afgewezen" if status == "afgewezen" else "bekend"
        sid = self._vind_sense_id(w, t, d)
        if sid is None or not self.sem.confirm_relation(w, sid, t, d):
            return "onbevestigd"
        return "opgeslagen"

    def _laat_vallen(self, v):
        w, t, d = v["word"], v["relation_type"], v["target"]
        # Staat de relatie intussen al in de kennisbank (bv. via een andere
        # weg bevestigd), dan wijzen we hem hier NIET stilzwijgend af.
        if self._relatie_status(w, t, d) == "bekend":
            return False
        self.sem.add_relation(w, t, d, source=BRON, confidence=WIKI_CONFIDENCE)
        sid = self._vind_sense_id(w, t, d)
        if sid is None:
            return False
        return bool(self.sem.reject_relation(
            w, sid, t, d, reason="voorstel uit Wikipedia afgewezen"))

    def on_keuze(self, data, event_type=None):
        actie = data.get("actie")
        nummer = data.get("nummer")
        alles = bool(data.get("alles"))
        if actie not in ("neem", "laat_vallen"):
            return
        if not alles and not isinstance(nummer, int):
            return
        if self.sem is None or not self._lijst_actueel():
            self._toon("Ik heb geen actuele voorstellen. Vraag eerst bv. 'extraheer fiets'.")
            return

        if alles:
            if actie != "neem":
                self._toon("Alles laten vallen doe ik bewust niet in één keer. "
                           "Gebruik 'laat 2 vallen' per voorstel.")
                return
            indices = [i for i, v in enumerate(self._lijst) if v is not None]
            if not indices:
                self._toon("Alle voorstellen zijn al behandeld.")
                return
        else:
            if nummer < 1 or nummer > len(self._lijst):
                self._toon(f"Nummer {nummer} staat niet in de lijst (1 t/m {len(self._lijst)}).")
                return
            if self._lijst[nummer - 1] is None:
                self._toon(f"Nummer {nummer} heb je al behandeld.")
                return
            indices = [nummer - 1]

        meldingen = []
        for i in indices:
            v = self._lijst[i]
            zin = self._zin(v["relation_type"], v["word"], v["target"])
            if actie == "neem":
                res = self._neem_over(v)
                if res == "opgeslagen":
                    meldingen.append(f"Opgeslagen en bevestigd: {zin}.")
                    self._lijst[i] = None
                elif res == "bekend":
                    meldingen.append(f"Dat stond er al: {zin}.")
                    self._lijst[i] = None
                elif res == "afgewezen":
                    meldingen.append(f"Dat had je eerder afgewezen, dus niet opgeslagen: {zin}.")
                    self._lijst[i] = None
                else:
                    meldingen.append(f"Opgeslagen maar nog niet bevestigd (dat lukte niet): {zin}.")
                    self._lijst[i] = None
            else:
                if self._laat_vallen(v):
                    meldingen.append(f"Afgewezen: {zin}. Ik stel het niet meer voor.")
                    self._lijst[i] = None
                else:
                    meldingen.append(f"Niet afgewezen (staat er intussen al, of het lukte niet): {zin}.")
        self._toon("\n".join(meldingen))


def init_module(event_bus, sem=None):
    return KnowledgeProposals(event_bus, sem)