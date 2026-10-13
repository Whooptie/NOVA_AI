# modules/knowledge/uncertainty.py
#
# Semantic Fase 10 -- Uncertainty Tracking.
#   10.1: "hoe zeker ben je dat een hond een dier is?" + bevestigingsvraag.
#   10.2: "wat weet je niet zeker (over hond)?" -> genummerde lijst,
#         "bevestig 3" / "wijs af 3", en
#         "waarom ben je er niet zeker van dat een hond een wolf is?".
#   10.3: zekerheid van een KETEN ("een puppy is een dier, via hond"):
#         een keten is zo zeker als zijn zwakste schakel. Staat de relatie
#         er niet direct, dan zoekt Nova de zekerste keten, noemt de
#         zwakste schakel en biedt aan precies die schakel te bevestigen.
#
# Puur symbolisch: Nova leest de status, bron en confidence die al bij de
# relatie in concepts.json staan en zegt eerlijk hoe zeker ze is. Die
# confidence is een vertrouwenslabel (komt uit regels of van jou), geen
# gemeten kans. Er is geen "aantal bewijzen" -- dat bewaart Nova niet, dus
# verzin ik het ook niet.
#
# Luistert op:
#   intent_uncertainty_query   {"relation_type", "source", "target"}
#   intent_uncertainty_why     {"relation_type", "source", "target"}
#   intent_uncertainty_list    {"word"}            (word mag None zijn)
#   intent_uncertainty_keuze   {"actie": "bevestig"|"wijs_af", "nummer"}
#   pending_question:answered  {"vraag_type", "signaal"}

import time

DREMPEL_ZEKER = 0.9
DREMPEL_WAARSCHIJNLIJK = 0.5
VRAAG_TYPE = "bevestig_relatie"
VERVAL_SECONDEN = 90
MAX_LIJST = 10
LIJST_GELDIG_SECONDEN = 600  # nummers uit een lijst blijven 10 minuten geldig
MAX_KETEN_DIEPTE = 5         # standaard maximaal aantal schakels (zelfde als ReasoningEngine)
MAX_KETEN_KNOPEN = 5000      # veiligheidsgrens voor het zoeken

ZIN = {
    "is_a": "{s} is een {t}",
    "part_of": "'{s}' is onderdeel van '{t}'",
    "causes": "{s} veroorzaakt {t}",
}

# Zelfde zinnen als bijzin ("... dat een hond een dier is")
ZIN_BIJZIN = {
    "is_a": "een {s} een {t} is",
    "part_of": "'{s}' onderdeel is van '{t}'",
    "causes": "'{s}' tot '{t}' leidt",
}

BRON_NAAM = {
    "wikipedia": "Wikipedia",
    "auto_extract": "een automatische afleiding uit een definitie",
    "auto": "een automatische gok",
    "auto_learn": "een automatische gok",
    "user": "jou",
}


class Uncertainty:
    def __init__(self, event_bus, sem):
        self.event_bus = event_bus
        self.sem = sem
        self._pending = None  # {"source", "sense_id", "relation_type", "target"}
        self._lijst = []      # items uit de laatst getoonde lijst (None = behandeld)
        self._lijst_tijd = 0.0
        event_bus.subscribe("intent_uncertainty_query", self.on_query)
        event_bus.subscribe("intent_uncertainty_why", self.on_why)
        event_bus.subscribe("intent_uncertainty_list", self.on_lijst)
        event_bus.subscribe("intent_uncertainty_keuze", self.on_keuze)
        event_bus.subscribe("pending_question:answered", self.on_antwoord)
        event_bus.publish("module_loaded", {"name": "uncertainty"})

    # ---------- hulpjes ----------
    def _zeg(self, tekst):
        self.event_bus.publish("layer4_response", {"text": tekst})

    def _toon_lijst(self, tekst):
        self.event_bus.publish("chat_response", {"source": "uncertainty", "text": tekst})

    def _zin(self, rel_type, s, t, bijzin=False):
        tabel = ZIN_BIJZIN if bijzin else ZIN
        return tabel.get(rel_type, "{s} -- " + rel_type + " -- {t}").format(
            s=s.replace("_", " "), t=t.replace("_", " "))

    def _enkelvoud(self, woord):
        """Meervoud -> enkelvoud via de bestaande regels van TeachEngine
        (onregelmatige lijst + -en/-s, alleen als het enkelvoud al als
        concept bestaat). Faalt stil naar het woord zelf."""
        te = getattr(self.sem, "teach_engine", None)
        fn = getattr(te, "_normalize_plural_if_noun", None)
        if fn is None:
            return woord
        try:
            return fn(woord, "noun") or woord
        except Exception:
            return woord

    def _zoek_relatie(self, source, rel_type, target, ook_afgewezen=False):
        """Beste directe match: (sense_id, relatie) of None."""
        concept = self.sem.store.get_concept(source)
        if not concept:
            return None
        beste = None
        for sense in concept.get("senses", []):
            if sense.get("status") == "rejected" and not ook_afgewezen:
                continue
            for rel in sense.get("relations", []):
                if rel.get("type") != rel_type or rel.get("target") != target:
                    continue
                if rel.get("status") == "rejected" and not ook_afgewezen:
                    continue
                if beste is None or rel.get("confidence", 0) > beste[1].get("confidence", 0):
                    beste = (sense.get("sense_id"), rel)
        return beste

    def _vind(self, rel_type, source, target):
        """Zoek precies zoals getypt, dan in enkelvoud.
        Geeft (source, target, gevonden) terug (woorden evt. in enkelvoud)."""
        gevonden = self._zoek_relatie(source, rel_type, target)
        if not gevonden:
            s2, t2 = self._enkelvoud(source), self._enkelvoud(target)
            if (s2, t2) != (source, target):
                source, target = s2, t2
                gevonden = self._zoek_relatie(source, rel_type, target)
        return source, target, gevonden

    @staticmethod
    def _zekerheidswoord(rel):
        conf = rel.get("confidence", 0) or 0
        if rel.get("status") == "confirmed" and conf >= DREMPEL_ZEKER:
            return "zeker"
        # niet bevestigd is nooit "zeker"
        if conf >= DREMPEL_WAARSCHIJNLIJK:
            return "waarschijnlijk"
        return "twijfelachtig"

    @staticmethod
    def _bronnaam(rel):
        return BRON_NAAM.get(rel.get("source"), rel.get("source") or "onbekend")

    def _keten(self, rel_type, source, target):
        """Oude, eenvoudige ketenvraag via de ReasoningEngine (alleen het pad)."""
        re_ = getattr(self.sem, "reasoning_engine", None)
        if re_ is None:
            return None
        naam = {"is_a": "is_a_chained", "part_of": "part_of_chained",
                "causes": "causes_chained"}.get(rel_type)
        fn = getattr(re_, naam, None) if naam else None
        if fn is None:
            return None
        try:
            ok, pad = fn(source, target)
        except Exception:
            return None
        return pad if ok else None

    # ---------- 10.3: zekerheid van een keten ----------
    def _uitgaand(self, woord, rel_type):
        """{doel: (sense_id, relatie)} -- beste niet-afgewezen relatie per doel."""
        concept = self.sem.store.concepts.get(woord)
        uit = {}
        if not concept:
            return uit
        for sense in concept.get("senses", []):
            if sense.get("status") == "rejected":
                continue
            for rel in sense.get("relations", []):
                if rel.get("type") != rel_type or rel.get("status") == "rejected":
                    continue
                doel = rel.get("target")
                huidig = uit.get(doel)
                if huidig is None or (rel.get("confidence", 0) or 0) > (huidig[1].get("confidence", 0) or 0):
                    uit[doel] = (sense.get("sense_id"), rel)
        return uit

    def _beste_keten(self, rel_type, source, target):
        """Zoekt de ZEKERSTE keten source -> ... -> target: de keten waarvan
        de zwakste schakel het hoogst scoort (bij gelijke score de kortste).
        Geeft een lijst schakels [(woord, sense_id, doel, relatie), ...] of None."""
        re_ = getattr(self.sem, "reasoning_engine", None)
        diepte = getattr(re_, "MAX_DEPTH", MAX_KETEN_DIEPTE)
        if not isinstance(diepte, int) or diepte < 1:
            diepte = MAX_KETEN_DIEPTE
        beste = {"sleutel": None, "hops": None}
        teller = [0]

        def dfs(woord, bezocht, hops):
            if teller[0] > MAX_KETEN_KNOPEN:
                return
            teller[0] += 1
            uit = self._uitgaand(woord, rel_type)
            for doel in sorted(uit):
                if doel in bezocht:
                    continue
                sid, rel = uit[doel]
                nieuw = hops + [(woord, sid, doel, rel)]
                if doel == target:
                    score = min((h[3].get("confidence", 0) or 0) for h in nieuw)
                    sleutel = (score, -len(nieuw))
                    if beste["sleutel"] is None or sleutel > beste["sleutel"]:
                        beste["sleutel"], beste["hops"] = sleutel, nieuw
                elif len(nieuw) < diepte:
                    dfs(doel, bezocht | {doel}, nieuw)

        dfs(source, {source}, [])
        return beste["hops"]

    def _analyseer_keten(self, rel_type, source, target):
        """Zekerheid van de zekerste keten, of None als er geen keten is."""
        hops = self._beste_keten(rel_type, source, target)
        if not hops:
            return None
        score = min((h[3].get("confidence", 0) or 0) for h in hops)
        onbevestigd = [h for h in hops if h[3].get("status") != "confirmed"]
        pseudo = {"status": "unverified" if onbevestigd else "confirmed", "confidence": score}
        zwakste = None
        if onbevestigd:
            zwakste = min(onbevestigd, key=lambda h: ((h[3].get("confidence", 0) or 0), h[0], h[2]))
        return {
            "hops": hops,
            "namen": [hops[0][0].replace("_", " ")] + [h[2].replace("_", " ") for h in hops],
            "score": score,
            "woord": self._zekerheidswoord(pseudo),
            "zwakste": zwakste,
        }

    def _keten_tekst(self, rel_type, source, target, analyse, vraag=True):
        """Antwoordtekst bij een keten. Zet (als vraag=True en kan) de
        bevestigingsvraag voor de zwakste onbevestigde schakel klaar."""
        bij = self._zin(rel_type, source, target, bijzin=True)
        tekst = (
            f"Ik ben er {analyse['woord']} van dat {bij} (zekerheid {analyse['score']:.2f}). "
            f"Dat staat er niet direct, maar volgt uit de keten {' -> '.join(analyse['namen'])}. "
            f"Een keten is zo zeker als zijn zwakste schakel."
        )
        z = analyse["zwakste"]
        if z is None:
            return tekst + " Alle schakels heb jij zelf bevestigd."

        w, sid, doel, rel = z
        tekst += (
            f" De zwakste onbevestigde schakel is {self._zin(rel_type, w, doel)} "
            f"({rel.get('confidence', 0) or 0:.2f}, {self._bronnaam(rel)})."
        )
        if vraag:
            vraagtekst = self._stel_bevestigvraag(w, sid, rel_type, doel)
            if vraagtekst:
                self._pending["keten"] = (rel_type, source, target)
                tekst += vraagtekst.replace("Wil je dit bevestigen?", "Wil je die schakel bevestigen?")
        return tekst

    def _niet_gevonden(self, rel_type, source, target, zin):
        # Eerst: heeft Kevin dit zelf afgewezen? Dan gaat dat voor elke keten.
        if self._zoek_relatie(source, rel_type, target, ook_afgewezen=True):
            return f"Dat heb jij afgewezen: {zin}. Ik beschouw het dus als onwaar."
        analyse = self._analyseer_keten(rel_type, source, target)
        if analyse:
            return self._keten_tekst(rel_type, source, target, analyse)
        pad = self._keten(rel_type, source, target)
        if pad:
            return (f"Dat staat er niet direct, maar {zin} volgt uit een keten: "
                    f"{' -> '.join(pad)}. Hoe zeker die keten is, kan ik niet bepalen.")
        return f"Dat weet ik niet: ik heb niets opgeslagen over: {zin}."

    def _stel_bevestigvraag(self, source, sense_id, rel_type, target):
        """Zet de ja/nee-vraag klaar. Geeft de vraagtekst terug, of ''
        als er al een andere vraag openstaat (of de module ontbreekt)."""
        pq = self.event_bus.modules.get("pending_question")
        if pq is None or pq.is_open():
            return ""
        self._pending = {"source": source, "sense_id": sense_id,
                         "relation_type": rel_type, "target": target}
        pq.set(VRAAG_TYPE, verval_seconden=VERVAL_SECONDEN)
        return " Wil je dit bevestigen? Typ 'ja' om te bevestigen of 'nee' om het zo te laten."

    # ---------- 10.1: hoe zeker? ----------
    def on_query(self, data, event_type=None):
        rel_type = data.get("relation_type")
        source = (data.get("source") or "").strip()
        target = (data.get("target") or "").strip()
        if not rel_type or not source or not target:
            return

        source, target, gevonden = self._vind(rel_type, source, target)
        zin = self._zin(rel_type, source, target)

        if gevonden:
            sense_id, rel = gevonden
            woord = self._zekerheidswoord(rel)
            conf = rel.get("confidence", 0) or 0
            bij = self._zin(rel_type, source, target, bijzin=True)
            tekst = f"Ik ben er {woord} van dat {bij} (zekerheid {conf:.2f})."
            if rel.get("status") == "confirmed":
                tekst += " Jij hebt dit zelf bevestigd."
                self._zeg(tekst)
                return

            tekst += f" Het komt van {self._bronnaam(rel)} en jij hebt het nog niet bevestigd."
            tekst += self._stel_bevestigvraag(source, sense_id, rel_type, target)
            self._zeg(tekst)
            return

        self._zeg(self._niet_gevonden(rel_type, source, target, zin))

    # ---------- 10.2: waarom? ----------
    def on_why(self, data, event_type=None):
        rel_type = data.get("relation_type")
        source = (data.get("source") or "").strip()
        target = (data.get("target") or "").strip()
        if not rel_type or not source or not target:
            return

        source, target, gevonden = self._vind(rel_type, source, target)
        zin = self._zin(rel_type, source, target)

        if not gevonden:
            self._zeg(self._niet_gevonden(rel_type, source, target, zin))
            return

        sense_id, rel = gevonden
        conf = rel.get("confidence", 0) or 0
        bij = self._zin(rel_type, source, target, bijzin=True)

        if rel.get("status") == "confirmed":
            oud = rel.get("oorspronkelijke_bron")
            tekst = f"Ik ben er zeker van dat {bij}, omdat jij dit zelf hebt bevestigd (zekerheid {conf:.2f})."
            if oud and oud != "user":
                tekst += f" Oorspronkelijk kwam het van {BRON_NAAM.get(oud, oud)}."
            self._zeg(tekst)
            return

        tekst = (
            f"Ik ben er niet helemaal zeker van dat {bij}. Het komt van {self._bronnaam(rel)} "
            f"(vertrouwen {conf:.2f}), en jij hebt het nooit zelf bevestigd of laten controleren. "
            f"Dat getal is een label van mijn regels, geen gemeten kans."
        )
        tekst += self._stel_bevestigvraag(source, sense_id, rel_type, target)
        self._zeg(tekst)

    # ---------- 10.2: lijst ----------
    def _verzamel_onzeker(self, woord=None):
        """Alle onbevestigde, niet-afgewezen relaties van de bekende types."""
        items = []
        concepten = self.sem.store.concepts
        woorden = [woord] if woord else list(concepten.keys())
        for w in woorden:
            concept = concepten.get(w)
            if not concept:
                continue
            for sense in concept.get("senses", []):
                if sense.get("status") == "rejected":
                    continue
                for rel in sense.get("relations", []):
                    if rel.get("type") not in ZIN:
                        continue
                    if rel.get("status") in ("confirmed", "rejected"):
                        continue
                    items.append({
                        "word": w,
                        "sense_id": sense.get("sense_id"),
                        "relation_type": rel.get("type"),
                        "target": rel.get("target"),
                        "confidence": rel.get("confidence", 0) or 0,
                        "source": rel.get("source"),
                    })
        items.sort(key=lambda i: (i["confidence"], i["word"], i["target"]))
        return items

    def on_lijst(self, data, event_type=None):
        woord = (data.get("word") or "").strip() or None
        if woord and woord not in self.sem.store.concepts:
            woord = self._enkelvoud(woord)

        if woord and woord not in self.sem.store.concepts:
            self._zeg(f"Over '{woord}' weet ik nog niets, dus ook niets onzekers.")
            return

        items = self._verzamel_onzeker(woord)
        over = f" over {woord}" if woord else ""
        if not items:
            self._lijst = []
            self._zeg(
                f"Ik heb geen onbevestigde relaties{over} (is-een, onderdeel-van, oorzaak). "
                f"Alles wat ik daarover weet, heb jij bevestigd of afgewezen."
            )
            return

        getoond = items[:MAX_LIJST]
        self._lijst = list(getoond)
        self._lijst_tijd = time.time()

        regels = []
        for n, i in enumerate(getoond, 1):
            zin = self._zin(i["relation_type"], i["word"], i["target"])
            regels.append(f"{n}. {zin} ({i['confidence']:.2f}, {self._bronnaam(i)})")
        if len(items) > len(getoond):
            regels.append(f"... en nog {len(items) - len(getoond)} meer")

        kop = f"Dit weet ik niet zeker{over} ({len(items)} onbevestigd, onzekerste eerst):"
        voet = "Typ 'bevestig 3' om er één te bevestigen of 'wijs af 3' om hem af te wijzen."
        self._toon_lijst(kop + "\n" + "\n".join(regels) + "\n" + voet)

    # ---------- 10.2: keuze uit de lijst ----------
    def on_keuze(self, data, event_type=None):
        actie = data.get("actie")
        nummer = data.get("nummer")
        if actie not in ("bevestig", "wijs_af") or not isinstance(nummer, int):
            return

        if not self._lijst or time.time() - self._lijst_tijd > LIJST_GELDIG_SECONDEN:
            self._lijst = []
            self._zeg("Ik heb geen actuele lijst. Vraag eerst: 'wat weet je niet zeker?'")
            return
        if nummer < 1 or nummer > len(self._lijst):
            self._zeg(f"Nummer {nummer} staat niet in de lijst (1 t/m {len(self._lijst)}).")
            return
        item = self._lijst[nummer - 1]
        if item is None:
            self._zeg(f"Nummer {nummer} heb je al behandeld.")
            return

        zin = self._zin(item["relation_type"], item["word"], item["target"])
        if actie == "bevestig":
            r = self.sem.confirm_relation(item["word"], item["sense_id"],
                                          item["relation_type"], item["target"])
            if r:
                self._zeg(f"Bevestigd: {zin}. Nu staat het op zeker.")
            else:
                self._zeg(f"Dat lukte niet: ik kon {zin} niet meer vinden.")
        else:
            r = self.sem.reject_relation(item["word"], item["sense_id"],
                                         item["relation_type"], item["target"],
                                         reason="afgewezen via onzekerheidslijst")
            if r:
                self._zeg(f"Afgewezen: {zin}. Ik negeer het voortaan bij het redeneren.")
            else:
                self._zeg(f"Dat lukte niet: ik kon {zin} niet meer vinden.")
        if r:
            self._lijst[nummer - 1] = None  # nummers verschuiven niet

    def _keten_na_bevestiging(self, keten):
        """Korte update over de keten waaruit de bevestigde schakel kwam."""
        if not keten:
            return ""
        rel_type, source, target = keten
        analyse = self._analyseer_keten(rel_type, source, target)
        if not analyse:
            return ""
        bij = self._zin(rel_type, source, target, bijzin=True)
        tekst = f" Ik ben er nu {analyse['woord']} van dat {bij} (zekerheid {analyse['score']:.2f})."
        z = analyse["zwakste"]
        if z is None:
            return tekst + " Alle schakels van de keten zijn nu bevestigd."
        return (tekst + f" Zwakste onbevestigde schakel nu: {self._zin(rel_type, z[0], z[2])}. "
                f"Stel de vraag opnieuw om die te bevestigen.")

    # ---------- antwoord op de bevestigingsvraag ----------
    def on_antwoord(self, data, event_type=None):
        if data.get("vraag_type") != VRAAG_TYPE:
            return
        p, self._pending = self._pending, None
        if not p:
            return
        zin = self._zin(p["relation_type"], p["source"], p["target"])
        signaal = data.get("signaal")

        if signaal == "bevestiging":
            r = self.sem.confirm_relation(p["source"], p["sense_id"],
                                          p["relation_type"], p["target"])
            if r:
                tekst = f"Bevestigd: {zin}. Nu staat het op zeker."
                tekst += self._keten_na_bevestiging(p.get("keten"))
                self._zeg(tekst)
            else:
                self._zeg(f"Dat lukte niet: ik kon {zin} niet meer vinden.")
        elif signaal == "ontkenning":
            self._zeg(
                f"Goed, {zin} blijft staan als niet bevestigd. Wil je het echt weghalen, "
                f"gebruik dan: weerleg: {p['source']} {p['relation_type']} {p['target']}"
            )


def init_module(event_bus, sem):
    return Uncertainty(event_bus, sem)