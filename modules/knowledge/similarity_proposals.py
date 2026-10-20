# modules/knowledge/similarity_proposals.py
#
# Semantic Fase 12, stap 2 -- gelijkenis-voorstellen: tonen, koppelen, negeren.
#
# Twee manieren om een lijst te krijgen:
#
#   A. Per woord:
#      "zoek gelijkenissen voor fiets"  -> woorden die qua betekenis dicht bij
#                                          'fiets' liggen, als genummerde lijst.
#   B. Wachtrij over ALLE concepten:
#      "gelijkenissen overlopen"        -> de sterkste nog onbeoordeelde paren van
#                                          je hele kennisbank, hoogste score eerst,
#                                          acht per keer.
#      "volgende gelijkenissen"         -> de volgende acht.
#
# Keuzes (voor beide manieren hetzelfde):
#   "koppel 2"            -> voorstel 2 wordt opgeslagen als 'verwant aan'
#                            (related_to) EN bevestigd.
#   "koppel 1 3 4"        -> meerdere tegelijk (ook "koppel 1, 3 en 4").
#   "koppel 2 als onderdeel" -> met een type (soort = is_a, onderdeel = part_of,
#                            bevat = has_part, synoniem = synonym, verwant).
#                            De richting is: eerste woord -> tweede woord, zoals
#                            de lijst het toont ("meubel en zitmeubel": soort =
#                            'meubel is een soort zitmeubel').
#   "koppel 7 als soort omgekeerd" -> draait de richting om ('zitmeubel is een
#                            soort meubel'). Nova toont na elke keuze de zin die
#                            ze opslaat, zodat je de richting direct kan zien.
#   "negeer 2" / "negeer 2 5" -> afgewezen (tombstone), komt nooit meer terug.
#   "negeer rest"         -> alles in de huidige lijst dat je nog niet behandelde.
#   "maak ongedaan"       -> draait je LAATSTE koppel- of negeer-commando terug (alles
#                            wat dat commando opsloeg, in een keer). De relatie wordt
#                            weer verwijderd, het paar mag opnieuw voorgesteld worden en
#                            staat het nummer nog in de lijst, dan is het weer vrij.
#
# Belangrijk:
#   * Er wordt NIETS opgeslagen zolang jij niet "koppel ..." of "negeer ..." typt.
#   * Het model geeft alleen een score, GEEN relatietype. Jij kiest het type.
#   * De wachtrij (B) toont geen paren die al een gedeelde ouder hebben (beide
#     is_a getal, beide part_of huid, ...): die band staat al in de kennisbank.
#     Hetzelfde geldt voor paren waarvan het ene woord al een voorouder van het
#     andere is via een keten van is_a, of van part_of/has_part (bv. gletsjer ->
#     grote massa ijs -> ijs). Ketens via een SYNONIEM tellen bewust niet mee:
#     Nova's redenering volgt geen synoniemen, dus die directe band is echt nieuw.
#     Ook komt elk woord er hooguit een keer in voor (met zijn beste partner),
#     zodat een groep als de getallen de lijst niet volloopt.
#   * Bij de wachtrij (B) kent Nova de richting van een paar niet. Daarom geldt
#     de volgorde van de lijst ("a en b": a -> b) en draai je met 'omgekeerd'
#     om. Bij "zoek gelijkenissen voor X" is X altijd het eerste woord.
#   * Bewust geen "koppel rest": ML-suggesties neem je zelf over, nooit in bulk.
#   * Woorden waar al een relatie mee bestaat (in welke richting ook), of die je
#     eerder afwees, worden overgeslagen.
#
# Eerlijk over ML versus symbolisch: de scores komen van een voorgetraind
# taalmodel (extern, onderdeel van Nova als specialist). Alles in DIT bestand is
# symbolisch: filteren, nummeren, opslaan, afwijzen.
#
# Waarom andere commando's dan "neem N over" / "bevestig N"? Die zijn al van
# Fase 11.2 en Fase 10.2.
#
# Luistert op:
#   intent_similarity_search   {"word"}
#   intent_similarity_review   {"actie": "start"|"volgende"}
#   intent_similarity_keuze    {"actie": "koppel"|"negeer", "nummers": [int],
#                               "rest": bool,
#                               "type": "verwant"|"soort"|"onderdeel"|"bevat"|
#                                       "synoniem"|None,
#                               "omgekeerd": bool}
#                              (oudere vorm met "nummer": int werkt ook)
#   intent_similarity_ongedaan {}
#
# Opslag: bron "embedding", confidence 0.6, daarna confirm_relation() (jij hebt
# het immers gezien). oorspronkelijke_bron blijft "embedding" in concepts.json.

import time

BRON = "embedding"
EMBEDDING_CONFIDENCE = 0.6
# Cosine-schaal, NIET vergelijkbaar met PMI (0..1). Gemeten op jouw concepten
# (MiniLM): goede buren liggen grofweg tussen 0.5 en 0.8. Pas aan als er te veel
# of te weinig voorstellen komen.
MIN_SCORE = 0.45
# Voor de wachtrij over alle concepten kiezen we strenger: anders worden het er
# duizenden. Zet lager als je meer wilt zien.
OVERLOOP_MIN_SCORE = 0.55
MAX_VOORSTELLEN = 8
KANDIDATEN_OPHALEN = 60  # ruim ophalen; veel valt weg door het filter
LIJST_GELDIG_SECONDEN = 600

# Nederlands trefwoord -> relatietype. Opslag altijd: woord <type> doel.
TYPE_NAAR_RELATIE = {
    None: "related_to",
    "verwant": "related_to",
    "soort": "is_a",
    "onderdeel": "part_of",
    "bevat": "has_part",
    "synoniem": "synonym",
}


class SimilarityProposals:
    def __init__(self, event_bus, sem=None, specialist=None):
        self.event_bus = event_bus
        self.sem = sem
        self._specialist = specialist   # mag van buitenaf komen (tests)
        self._lijst = []                # huidige voorstellen; None = al behandeld
        self._lijst_tijd = 0.0
        self._lijst_woord = None
        self._wachtrij = []             # nog te tonen paren (modus "wachtrij")
        self._overgeslagen_ouder = 0    # paren die al een gedeelde ouder hebben
        self._overgeslagen_keten = 0    # paren die al via een is_a/part_of-keten bekend zijn
        self._laatste = []              # wat het laatste koppel-/negeer-commando opsloeg
        event_bus.subscribe("intent_similarity_search", self.on_search)
        event_bus.subscribe("intent_similarity_review", self.on_review)
        event_bus.subscribe("intent_similarity_keuze", self.on_keuze)
        event_bus.subscribe("intent_similarity_ongedaan", self.on_ongedaan)
        event_bus.publish("module_loaded", {"name": "similarity_proposals"})

    # ---------- hulpjes ----------
    def _toon(self, tekst):
        # chat_response (geen layer4_response): een lijst mag niet door de
        # toon-pipeline, die zet anders een '!' achter de laatste regel.
        self.event_bus.publish("chat_response",
                               {"source": "similarity_proposals", "text": tekst})

    def _get_specialist(self):
        if self._specialist is not None:
            return self._specialist
        modules = getattr(self.event_bus, "modules", {}) or {}
        return modules.get("embedding_specialist")

    def _beschikbare_specialist(self):
        """Geeft de specialist, of None na een uitleg aan Kevin."""
        if self.sem is None:
            self._toon("De kennisbank is niet beschikbaar, dus ik kan niets voorstellen.")
            return None
        spec = self._get_specialist()
        if spec is None or not spec.is_beschikbaar():
            reden = getattr(spec, "reden_uit", None) or "module niet geladen"
            self._toon(f"De embedding-module staat uit ({reden}), "
                       f"dus ik kan geen gelijkenissen zoeken.")
            return None
        return spec

    @staticmethod
    def _relaties_naar(concept, doel):
        """Alle relatie-objecten in 'concept' die naar 'doel' wijzen."""
        gevonden = []
        for sense in (concept or {}).get("senses", []):
            for rel in sense.get("relations", []):
                if rel.get("target") == doel:
                    gevonden.append(rel)
        return gevonden

    def _paar_status(self, a, b):
        """Bestaat er al een relatie tussen a en b, in welke richting en van welk
        type ook?  None = nee, 'bekend' = ja (niet afgewezen), 'afgewezen' =
        alleen afgewezen relaties (tombstone)."""
        rels = (self._relaties_naar(self.sem.store.get_concept(a), b)
                + self._relaties_naar(self.sem.store.get_concept(b), a))
        if not rels:
            return None
        if any(r.get("status") != "rejected" for r in rels):
            return "bekend"
        return "afgewezen"

    def _ouders(self, woord):
        """Doelen van de actieve is_a- en part_of-relaties van een woord."""
        uit = set()
        concept = self.sem.store.get_concept(woord)
        for sense in (concept or {}).get("senses", []):
            if sense.get("status") == "rejected":
                continue
            for rel in sense.get("relations", []):
                if rel.get("type") in ("is_a", "part_of") \
                        and rel.get("status") != "rejected" and rel.get("target"):
                    uit.add(rel["target"])
        return uit

    def _gedeelde_ouder(self, a, b):
        return bool(self._ouders(a) & self._ouders(b))

    def _bouw_ketens(self):
        """Twee grafen voor de wachtrij: woord -> directe ouders via is_a, en via
        part_of (een has_part van een ander woord telt als omgekeerde part_of).
        Afgewezen relaties en afgewezen senses tellen niet mee. Synoniemen en
        related_to doen bewust NIET mee."""
        is_a, part_of = {}, {}
        concepten = getattr(self.sem.store, "concepts", None) or {}
        for woord, concept in concepten.items():
            for sense in concept.get("senses", []):
                if sense.get("status") == "rejected":
                    continue
                for rel in sense.get("relations", []):
                    doel = rel.get("target")
                    if not doel or rel.get("status") == "rejected":
                        continue
                    soort = rel.get("type")
                    if soort == "is_a":
                        is_a.setdefault(woord, set()).add(doel)
                    elif soort == "part_of":
                        part_of.setdefault(woord, set()).add(doel)
                    elif soort == "has_part":
                        part_of.setdefault(doel, set()).add(woord)
        return is_a, part_of

    @staticmethod
    def _bereikbaar(graaf, start, doel):
        gezien, rij = {start}, [start]
        while rij:
            w = rij.pop()
            for ouder in graaf.get(w, ()):
                if ouder == doel:
                    return True
                if ouder not in gezien:
                    gezien.add(ouder)
                    rij.append(ouder)
        return False

    def _via_keten(self, ketens, a, b):
        """Is een van de twee woorden al een (verre) voorouder van het andere,
        via een zuivere keten van is_a OF van part_of (nooit door elkaar)?"""
        return any(self._bereikbaar(graaf, a, b) or self._bereikbaar(graaf, b, a)
                   for graaf in ketens)

    def _vind_sense_id(self, woord, rel_type, doel):
        concept = self.sem.store.get_concept(woord)
        if not concept:
            return None
        for sense in concept.get("senses", []):
            for rel in sense.get("relations", []):
                if rel.get("type") == rel_type and rel.get("target") == doel:
                    return sense.get("sense_id")
        return None

    @staticmethod
    def _zin(rel_type, w, d):
        w, d = w.replace("_", " "), d.replace("_", " ")
        return {
            "related_to": f"'{w}' is verwant aan '{d}'",
            "is_a": f"'{w}' is een soort '{d}'",
            "part_of": f"'{w}' is onderdeel van '{d}'",
            "has_part": f"'{w}' bevat '{d}'",
            "synonym": f"'{w}' is een synoniem van '{d}'",
        }.get(rel_type, f"'{w}' {rel_type} '{d}'")

    def _nieuwe_lijst(self, items, woord=None):
        self._lijst = list(items)
        self._lijst_tijd = time.time()
        self._lijst_woord = woord

    # ---------- A. "zoek gelijkenissen voor X" ----------
    def on_search(self, data, event_type=None):
        woord = (data.get("word") or "").strip().strip(".,!?;:").lower()
        if not woord:
            self._toon("Van welk woord wil je gelijkende woorden zoeken? "
                       "Bv. 'zoek gelijkenissen voor fiets'.")
            return
        spec = self._beschikbare_specialist()
        if spec is None:
            return

        if not self.sem.store.has_concept(woord):
            self._toon(f"Ik ken '{woord}' nog niet, dus ik kan er niets mee vergelijken.")
            return

        if not getattr(spec, "_cache", None):
            self._toon("Ik reken de betekenis-vectoren uit (de eerste keer duurt dit "
                       "even, daarna gaat het snel).")

        kandidaten = spec.find_similar(woord, top_k=KANDIDATEN_OPHALEN,
                                       min_score=MIN_SCORE)
        if not kandidaten:
            self._lijst = []
            self._toon(f"Ik vind geen woorden die qua betekenis dicht genoeg bij "
                       f"'{woord}' liggen, of '{woord}' heeft geen bruikbare definitie.")
            return

        voorstellen = []
        al_bekend = afgewezen = 0
        for k in kandidaten:
            doel = k["woord"]
            status = self._paar_status(woord, doel)
            if status == "afgewezen":
                afgewezen += 1
                continue
            if status == "bekend":
                al_bekend += 1
                continue
            voorstellen.append({"word": woord, "target": doel, "modus": "woord",
                                "score": k["score"], "model": k.get("model", "")})

        extra = []
        if al_bekend:
            extra.append(f"{al_bekend} hebben al een relatie met '{woord}'")
        if afgewezen:
            extra.append(f"{afgewezen} had je eerder afgewezen")
        toelichting = f" ({', '.join(extra)})" if extra else ""

        if not voorstellen:
            self._lijst = []
            self._toon(f"Er is niets nieuws om voor te stellen bij '{woord}'{toelichting}.")
            return

        getoond = voorstellen[:MAX_VOORSTELLEN]
        self._nieuwe_lijst(getoond, woord)

        regels = [f"{n}. {v['target']}  (score {v['score']:.2f})"
                  for n, v in enumerate(getoond, 1)]
        kop = (f"Ik heb gezocht naar woorden die qua betekenis dicht bij '{woord}' "
               f"liggen (nog niets opgeslagen){toelichting}:")
        voet = ("De score zegt dat ze bij elkaar passen, niet HOE. Jij kiest:\n"
                "  'koppel 1'  (verwant)   of   'koppel 1 als soort|onderdeel|bevat|synoniem'\n"
                "  'koppel 1 3 4' voor meerdere tegelijk  |  'omgekeerd' erachter draait de richting om\n"
                "  'negeer 2'  om af te wijzen   |   'negeer rest'  voor al het overige.")
        self._toon(kop + "\n" + "\n".join(regels) + "\n" + voet)

    # ---------- B. "gelijkenissen overlopen" / "volgende gelijkenissen" ----------
    def on_review(self, data, event_type=None):
        actie = data.get("actie")
        if actie not in ("start", "volgende"):
            return
        spec = self._beschikbare_specialist()
        if spec is None:
            return

        if actie == "start":
            if not getattr(spec, "_cache", None):
                self._toon("Ik reken de betekenis-vectoren uit (de eerste keer duurt dit "
                           "even, daarna gaat het snel).")
            paren = spec.find_all_pairs(min_score=OVERLOOP_MIN_SCORE)  # hoog -> laag
            self._wachtrij, gebruikt = [], set()
            self._overgeslagen_ouder = 0
            self._overgeslagen_keten = 0
            ketens = self._bouw_ketens()
            for p in paren:
                a, b = p["woord_a"], p["woord_b"]
                if self._paar_status(a, b) is not None:
                    continue
                if self._gedeelde_ouder(a, b):
                    self._overgeslagen_ouder += 1
                    continue
                if self._via_keten(ketens, a, b):
                    self._overgeslagen_keten += 1
                    continue
                if a in gebruikt or b in gebruikt:
                    continue   # elk woord hooguit een keer, met zijn beste partner
                gebruikt.update((a, b))
                self._wachtrij.append(
                    {"word": a, "target": b, "modus": "wachtrij",
                     "score": p["score"], "model": p.get("model", "")})
        elif not self._wachtrij and not self._lijst:
            self._toon("Er staat geen wachtrij klaar. Typ eerst 'gelijkenissen overlopen'.")
            return

        # Pak de volgende paren die nog steeds nieuw zijn (intussen kan een paar
        # via een ander pad een relatie hebben gekregen).
        batch = []
        while self._wachtrij and len(batch) < MAX_VOORSTELLEN:
            p = self._wachtrij.pop(0)
            if self._paar_status(p["word"], p["target"]) is None:
                batch.append(p)

        if not batch:
            self._lijst = []
            if actie == "start":
                self._toon(f"Er zijn geen nieuwe paren met een score vanaf "
                           f"{OVERLOOP_MIN_SCORE:.2f} om te beoordelen.")
            else:
                self._toon("De wachtrij is leeg. Je bent er doorheen.")
            return

        self._nieuwe_lijst(batch, None)
        nog = len(self._wachtrij)
        regels = [f"{n}. {v['word']} en {v['target']}  (score {v['score']:.2f})"
                  for n, v in enumerate(batch, 1)]
        if actie == "start":
            overslag = ""
            if self._overgeslagen_ouder:
                overslag = (f" Ik sla {self._overgeslagen_ouder} paren over die al dezelfde "
                            f"ouder delen (bv. allebei een getal): die band weet ik al.")
            if self._overgeslagen_keten:
                overslag += (f" Ik sla {self._overgeslagen_keten} paren over waarvan het ene "
                             f"woord al een voorouder van het andere is (bv. gletsjer, grote "
                             f"massa ijs, ijs): ook die band weet ik al.")
            kop = (f"Ik heb al je concepten met elkaar vergeleken en zocht de sterkste "
                   f"paren die nog geen relatie hebben (score vanaf {OVERLOOP_MIN_SCORE:.2f}, "
                   f"elk woord hooguit een keer).{overslag} Nog niets opgeslagen. "
                   f"Er staan er {len(batch) + nog} in de wachtrij:")
        else:
            kop = f"De volgende paren (nog {nog} daarna in de wachtrij, nog niets opgeslagen):"
        voet = ("Jij kiest:\n"
                "  'koppel 1'  (verwant)  |  'koppel 1 als synoniem'  |  'koppel 1 3 4'\n"
                "  'koppel 1 als soort|onderdeel|bevat': het eerste woord is een soort van / "
                "onderdeel van / bevat het tweede. Ik ken de richting niet zelf: zet "
                "'omgekeerd' erachter om te draaien (bv. 'koppel 7 als soort omgekeerd').\n"
                "  'negeer 2'  |  'negeer rest'\n"
                "  'volgende gelijkenissen'  voor de volgende paren (wat je liet staan "
                "komt een volgende keer terug).")
        self._toon(kop + "\n" + "\n".join(regels) + "\n" + voet)

    # ---------- "koppel N [N ...] [als type]" / "negeer N [N ...] | rest" ----------
    def _lijst_actueel(self):
        if not self._lijst or time.time() - self._lijst_tijd > LIJST_GELDIG_SECONDEN:
            self._lijst = []
            return False
        return True

    def _koppel(self, v, rel_type):
        """Slaat op en bevestigt. Geeft: opgeslagen|bekend|afgewezen|onbevestigd."""
        w, d = v["word"], v["target"]
        status = self._paar_status(w, d)
        if status == "afgewezen":
            return "afgewezen"
        if status == "bekend":
            return "bekend"
        toegevoegd = self.sem.add_relation(w, rel_type, d, source=BRON,
                                           confidence=EMBEDDING_CONFIDENCE)
        if not toegevoegd:
            return "bekend"
        sid = self._vind_sense_id(w, rel_type, d)
        if sid is None or not self.sem.confirm_relation(w, sid, rel_type, d):
            return "onbevestigd"
        return "opgeslagen"

    def _negeer(self, v):
        """Tombstone: related_to afgewezen. _paar_status() slaat dit paar daarna over."""
        w, d = v["word"], v["target"]
        if self._paar_status(w, d) == "bekend":
            return False   # staat er intussen al; niet stilzwijgend afwijzen
        self.sem.add_relation(w, "related_to", d, source=BRON,
                              confidence=EMBEDDING_CONFIDENCE)
        sid = self._vind_sense_id(w, "related_to", d)
        if sid is None:
            return False
        return bool(self.sem.reject_relation(
            w, sid, "related_to", d, reason="gelijkenis-voorstel (embedding) afgewezen"))

    def on_keuze(self, data, event_type=None):
        actie = data.get("actie")
        if actie not in ("koppel", "negeer"):
            return
        nummers = data.get("nummers")
        if nummers is None and isinstance(data.get("nummer"), int):
            nummers = [data["nummer"]]
        nummers = [n for n in (nummers or []) if isinstance(n, int)]
        rest = bool(data.get("rest"))
        if not nummers and not rest:
            return
        if rest and actie != "negeer":
            return   # "koppel rest" bestaat bewust niet
        type_nl = data.get("type")
        if type_nl not in TYPE_NAAR_RELATIE:
            return
        omgekeerd = bool(data.get("omgekeerd"))
        if self.sem is None or not self._lijst_actueel():
            self._toon("Ik heb geen actuele voorstellen. Vraag eerst bv. "
                       "'zoek gelijkenissen voor fiets' of 'gelijkenissen overlopen'.")
            return

        # Welke posities in de lijst?
        meldingen = []
        if rest:
            posities = [i for i, v in enumerate(self._lijst) if v is not None]
            if not posities:
                self._toon("Alles in deze lijst is al behandeld.")
                return
        else:
            posities, gezien = [], set()
            for n in nummers:
                if n in gezien:
                    continue
                gezien.add(n)
                if n < 1 or n > len(self._lijst):
                    meldingen.append(f"Nummer {n} staat niet in de lijst (1 t/m {len(self._lijst)}).")
                elif self._lijst[n - 1] is None:
                    meldingen.append(f"Nummer {n} heb je al behandeld.")
                else:
                    posities.append(n - 1)

        rel_type = TYPE_NAAR_RELATIE[type_nl]
        gedaan = []   # wat dit commando opsloeg, voor "maak ongedaan"
        for i in posities:
            v = self._lijst[i]
            if actie == "koppel":
                if omgekeerd:
                    v = {**v, "word": v["target"], "target": v["word"]}
                zin = self._zin(rel_type, v["word"], v["target"])
                res = self._koppel(v, rel_type)
                if res == "opgeslagen":
                    meldingen.append(f"Opgeslagen en bevestigd: {zin}.")
                elif res == "bekend":
                    meldingen.append(f"Er bestaat al een relatie tussen die twee, dus niets opgeslagen: {zin}.")
                elif res == "afgewezen":
                    meldingen.append(f"Dat had je eerder afgewezen, dus niet opgeslagen: {zin}.")
                else:
                    meldingen.append(f"Opgeslagen maar nog niet bevestigd (dat lukte niet): {zin}.")
                if res in ("opgeslagen", "onbevestigd"):
                    gedaan.append(self._onthoud("koppel", v, rel_type, i))
                self._lijst[i] = None
            else:
                if self._negeer(v):
                    meldingen.append(f"Afgewezen: '{v['word']}' en '{v['target']}'. "
                                     f"Ik stel dit paar niet meer voor.")
                    gedaan.append(self._onthoud("negeer", v, "related_to", i))
                    self._lijst[i] = None
                else:
                    meldingen.append(f"Nummer {i + 1} niet afgewezen (er staat intussen al een relatie, "
                                     f"of het lukte niet).")

        if gedaan:
            self._laatste = gedaan   # alleen als er echt iets is opgeslagen
            meldingen.append("Fout gekozen? Typ 'maak ongedaan'.")
        if self._wachtrij and all(v is None for v in self._lijst):
            meldingen.append("Lijst klaar. Typ 'volgende gelijkenissen' voor de volgende paren.")
        if meldingen:
            self._toon("\n".join(meldingen))


    # ---------- "maak ongedaan" ----------
    def _onthoud(self, soort, v, rel_type, index):
        """Bewaart wat er is opgeslagen, zodat 'maak ongedaan' het kan terugdraaien.
        Aanroepen VOORDAT self._lijst[index] op None gaat."""
        return {"soort": soort, "word": v["word"], "target": v["target"],
                "rel_type": rel_type,
                "sense_id": self._vind_sense_id(v["word"], rel_type, v["target"]),
                "lijst": self._lijst, "index": index,
                "item": self._lijst[index]}

    def _draai_terug(self, a):
        """Verwijdert de relatie van een eerdere koppel/negeer. Geeft:
        ok | weg | gewijzigd | mislukt.  Raakt NOOIT iets aan dat niet door dit
        voorstel is gemaakt (bron 'embedding') of intussen door jou is aangepast."""
        w, d, t, sid = a["word"], a["target"], a["rel_type"], a["sense_id"]
        if sid is None:
            return "mislukt"
        rel = None
        for sense in (self.sem.store.get_concept(w) or {}).get("senses", []):
            if sense.get("sense_id") != sid:
                continue
            for r in sense.get("relations", []):
                if r.get("type") == t and r.get("target") == d:
                    rel = r
        if rel is None:
            return "weg"
        if BRON not in (rel.get("source"), rel.get("oorspronkelijke_bron")):
            return "gewijzigd"
        if rel.get("status") != "rejected":
            if a["soort"] == "negeer":
                return "gewijzigd"   # een afwijzing die intussen weer actief is: niet aanraken
            # Eerst afwijzen, dan pas fysiek verwijderen (de guard van hard_delete_relation).
            if not self.sem.reject_relation(w, sid, t, d, reason="ongedaan gemaakt"):
                return "mislukt"
        return "ok" if self.sem.hard_delete_relation(w, sid, t, d) else "mislukt"

    def on_ongedaan(self, data=None, event_type=None):
        if self.sem is None:
            self._toon("De kennisbank is niet beschikbaar.")
            return
        if not self._laatste:
            self._toon("Er is niets om ongedaan te maken. Ik kan alleen je laatste "
                       "'koppel'- of 'negeer'-commando terugdraaien, en maar een keer.")
            return
        acties, self._laatste = self._laatste, []
        meldingen, teruggezet = [], []
        for a in reversed(acties):
            w, d = a["word"], a["target"]
            res = self._draai_terug(a)
            if res == "ok":
                if a["soort"] == "koppel":
                    meldingen.append(f"Ongedaan gemaakt, verwijderd: {self._zin(a['rel_type'], w, d)}.")
                else:
                    meldingen.append(f"Ongedaan gemaakt: '{w}' en '{d}' zijn niet meer afgewezen "
                                     f"en kunnen opnieuw voorgesteld worden.")
                i = a["index"]
                if self._lijst is a["lijst"] and 0 <= i < len(self._lijst) \
                        and self._lijst[i] is None:
                    self._lijst[i] = a["item"]
                    self._lijst_tijd = time.time()
                    teruggezet.append(i + 1)
            elif res == "weg":
                meldingen.append(f"'{w}' en '{d}': die relatie bestaat al niet meer, "
                                 f"dus er is niets te doen.")
            elif res == "gewijzigd":
                meldingen.append(f"'{w}' en '{d}': die relatie is intussen aangepast, "
                                 f"dus ik laat hem staan.")
            else:
                meldingen.append(f"'{w}' en '{d}': ongedaan maken lukte niet.")
        if teruggezet:
            nrs = ", ".join(str(n) for n in sorted(teruggezet))
            meldingen.append(f"Nummer {nrs} staat weer in de lijst.")
        self._toon("\n".join(meldingen))


def init_module(event_bus, sem=None):
    return SimilarityProposals(event_bus, sem)