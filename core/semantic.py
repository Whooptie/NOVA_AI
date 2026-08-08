# core/semantic.py

import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Any

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
LOGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
CONCEPTS_FILE = os.path.join(BASE, "concepts.json")
CONCEPTS_LOG = os.path.join(LOGS, "concepts.jsonl")


# ---------------------------------------------------------
# 1. ConceptStore – opslaglaag
# ---------------------------------------------------------
class ConceptStore:
    def __init__(self, concepts_file: str = CONCEPTS_FILE, log_file: str = CONCEPTS_LOG):
        self.concepts_file = concepts_file
        self.log_file = log_file
        os.makedirs(os.path.dirname(self.concepts_file), exist_ok=True)
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        self.concepts: Dict[str, Dict[str, Any]] = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.concepts_file):
            with open(self.concepts_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save(self) -> None:
        """
        Atomische write (6 augustus 2026, ConceptStore.save()
        atomisch maken): schrijft eerst naar een tijdelijk bestand in
        DEZELFDE map (belangrijk -- os.replace() is enkel atomisch
        binnen hetzelfde bestandssysteem), en wisselt dat pas om naar
        het echte concepts.json met os.replace(). Die laatste stap is
        een enkele OS-niveau operatie: er bestaat geen tussentoestand
        waarin het bestand half geschreven is. Een crash/stroomuitval
        tijdens het schrijven naar het tijdelijke bestand laat het
        oude, intacte concepts.json gewoon ongemoeid staan -- voorheen
        (open(..., "w") direct op concepts.json zelf) leegde een
        onderbroken schrijfactie het HELE bestand, niet enkel de
        laatste wijziging.

        PID in de tijdelijke bestandsnaam zodat twee gelijktijdige
        save()-aanroepen (zou in Nova's huidige single-thread-
        schrijfpatroon niet mogen voorkomen, maar kost niets als
        extra veiligheid) elkaars tijdelijke bestand niet overschrijven.
        """
        tmp_pad = f"{self.concepts_file}.tmp{os.getpid()}"
        try:
            with open(tmp_pad, "w", encoding="utf-8") as f:
                json.dump(self.concepts, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_pad, self.concepts_file)
        except Exception:
            # Opruimen als het tijdelijke bestand wel aangemaakt werd
            # maar de write/replace zelf faalde (bv. schijf vol) --
            # anders blijft er een verweesd .tmp<pid>-bestand liggen.
            if os.path.exists(tmp_pad):
                try:
                    os.remove(tmp_pad)
                except OSError:
                    pass
            raise

    def _write_log(self, event_type: str, word: str, source: str, extra: dict = None) -> None:
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "word": word,
            "source": source
        }
        if extra:
            entry.update(extra)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _append_audit(self, concept: Dict[str, Any], entry: Dict[str, Any], word: str = "") -> None:
        entry.setdefault("timestamp", datetime.utcnow().isoformat())
        concept.setdefault("audit_log", []).append(entry)
        # Ook naar het externe logbestand schrijven
        self._write_log(
            event_type=entry.get("event_type", "unknown"),
            word=word,
            source=entry.get("source", "system"),
            extra={k: v for k, v in entry.items() if k not in ("event_type", "source", "timestamp")}
        )

    def ensure_concept(self, word: str) -> Dict[str, Any]:
        word = word.lower().strip()
        if word not in self.concepts:
            now = datetime.utcnow().isoformat()
            self.concepts[word] = {
                "senses": [],
                "metadata": {
                    "created_at": now,
                    "updated_at": now,
                    "sources": [],
                    "last_used_at": None,
                    "usage_count": 0,
                    "confidence_history": []
                },
                "audit_log": []
            }
            self._append_audit(self.concepts[word], {
                "event_type": "concept_created",
                "source": "system",
                "new_value": {"word": word}
            }, word=word)
        return self.concepts[word]

    def get_concept(self, word: str) -> Optional[Dict[str, Any]]:
        return self.concepts.get(word.lower().strip())

    def has_concept(self, word: str) -> bool:
        return word.lower().strip() in self.concepts

    def search(self, query: str) -> list:
        query = query.lower().strip()
        return [w for w in self.concepts if query in w]

    def export_concept(self, word: str) -> dict | None:
        return self.concepts.get(word.lower().strip())

    def touch_concept(self, word: str, confidence: Optional[float] = None) -> None:
        concept = self.get_concept(word)
        if not concept:
            return
        now = datetime.utcnow().isoformat()
        meta = concept["metadata"]
        meta["updated_at"] = now
        meta["last_used_at"] = now
        meta["usage_count"] = meta.get("usage_count", 0) + 1
        if confidence is not None:
            meta["confidence_history"].append({
                "timestamp": now,
                "confidence": confidence
            })


# ---------------------------------------------------------
# 2. SenseEngine – senses per woord
# ---------------------------------------------------------
class SenseEngine:
    def __init__(self, store: ConceptStore):
        self.store = store

    def _next_sense_id(self, word: str, concept: Dict[str, Any]) -> str:
        existing = concept.get("senses", [])
        max_idx = 0
        for s in existing:
            sid = s.get("sense_id", "")
            if sid.startswith(word + "#"):
                try:
                    idx = int(sid.split("#", 1)[1])
                    max_idx = max(max_idx, idx)
                except ValueError:
                    continue
        return f"{word}#{max_idx + 1}"

    def _audit_sense(self, concept: Dict[str, Any], sense: Dict[str, Any],
                     event_type: str, source: str, old_value: Any = None, new_value: Any = None,
                     extra: Optional[Dict[str, Any]] = None) -> None:
        entry = {
            "event_type": event_type,
            "source": source,
            "sense_id": sense.get("sense_id"),
            "old_value": old_value,
            "new_value": new_value
        }
        if extra:
            entry.update(extra)
        entry["timestamp"] = datetime.utcnow().isoformat()
        concept.setdefault("audit_log", []).append(entry)

    def add_sense(self, word: str, definition: str,
                  source: str = "user", confidence: float = 1.0,
                  pos: Optional[str] = None) -> dict:

        word = word.lower().strip()
        concept = self.store.ensure_concept(word)
        senses = concept["senses"]

        # Deduplicatie
        for s in senses:
            if s.get("definition") == definition:
                # Bug #32-fix (8 augustus 2026): een sense met
                # status == "rejected" mag NOOIT stilzwijgend terug
                # "confirmed"/"unverified" worden zodra dezelfde
                # definitie-tekst opnieuw wordt aangeboden. Vroeger liep
                # dit hieronder gewoon door alsof er niets aan de hand
                # was — een eerder afgewezen feit kwam dan ongemerkt
                # terug. In plaats daarvan geven we hier een duidelijk
                # herkenbaar "blocked"-signaal terug en raken we de
                # sense zelf NIET aan. De aanroeper (TeachEngine.teach()
                # / wikipedia_teacher.py) beslist wat daarmee gebeurt:
                # bij source == "user" moet Kevin expliciet gevraagd
                # worden of hij het écht opnieuw wil bevestigen; bij elke
                # andere bron (auto/auto_extract/wikipedia) moet het
                # gewoon gemeld worden, nooit automatisch verwerkt.
                if s.get("status") == "rejected":
                    return {
                        "blocked": "rejected",
                        "sense": s,
                        "attempted_source": source,
                        "attempted_confidence": confidence,
                    }

                old_conf = s.get("confidence", 0)
                if confidence > old_conf:
                    s["confidence"] = confidence
                    self._audit_sense(concept, s, "confidence_update", source,
                                      old_value=old_conf, new_value=confidence)
                # Trust state (punt 3, 6 augustus 2026): een bevestiging
                # door Kevin ("user") mag een eerdere unverified-status
                # altijd overschrijven naar confirmed. Andersom nooit --
                # een latere auto/wikipedia-match mag een reeds door
                # Kevin bevestigde sense niet terugzetten naar unverified.
                if source == "user":
                    s["status"] = "confirmed"
                elif "status" not in s:
                    s["status"] = "unverified"
                if source not in concept["metadata"]["sources"]:
                    concept["metadata"]["sources"].append(source)
                self.store.touch_concept(word, s.get("confidence"))
                self.store.save()
                return s

        # Unknown upgraden
        for s in senses:
            if s.get("definition") == "unknown":
                old_def = s.get("definition")
                s["definition"] = definition
                s["source"] = source
                s["confidence"] = confidence
                s["pos"] = pos
                # Trust state (punt 3, 6 augustus 2026): status volgt de
                # bron van deze upgrade -- zie deduplicatie-tak hierboven.
                s["status"] = "confirmed" if source == "user" else "unverified"
                concept["metadata"]["updated_at"] = datetime.utcnow().isoformat()
                self._audit_sense(concept, s, "sense_upgrade", source,
                                  old_value=old_def, new_value=definition)
                self.store.touch_concept(word, s.get("confidence"))
                self.store.save()
                return s

        # Nieuwe sense
        sense_id = self._next_sense_id(word, concept)
        new_sense = {
            "sense_id": sense_id,
            "definition": definition,
            "pos": pos,
            "examples": [],
            "relations": [],
            "source": source,
            "confidence": confidence,
            # Trust state (punt 3, 6 augustus 2026): status volgt de bron
            # -- "user" (teach()) is meteen bevestigd, alle andere bronnen
            # (auto, auto_extract, wikipedia) starten als unverified totdat
            # Kevin ze zelf bevestigt of afwijst (zie punt 1/2, later).
            "status": "confirmed" if source == "user" else "unverified",
            "audit_log": []
        }
        senses.append(new_sense)
        concept["metadata"]["updated_at"] = datetime.utcnow().isoformat()
        if source not in concept["metadata"]["sources"]:
            concept["metadata"]["sources"].append(source)
        self._audit_sense(concept, new_sense, "sense_created", source,
                          old_value=None, new_value=definition)
        self.store.touch_concept(word, confidence)
        self.store.save()
        return new_sense

    def upgrade_unknown_sense(self, word: str, definition: str,
                               source: str = "user", confidence: float = 1.0) -> dict | None:
        word = word.lower().strip()
        concept = self.store.get_concept(word)
        if not concept:
            return None

        for s in concept["senses"]:
            if s.get("definition") == "unknown":
                old_def = s["definition"]
                s["definition"] = definition
                s["source"] = source
                s["confidence"] = confidence
                # Trust state (punt 3, 6 augustus 2026), uitgebreid voor
                # Bug #32-fix (8 augustus 2026): status volgt nu de
                # daadwerkelijk meegegeven source i.p.v. altijd "user"
                # aan te nemen. Dit maakt het mogelijk dat
                # wikipedia_teacher.py deze methode met source="wikipedia"
                # aanroept en meteen de juiste status ("unverified")
                # krijgt, zonder dat een aparte, foutgevoelige
                # achteraf-correctie nog nodig is.
                s["status"] = "confirmed" if source == "user" else "unverified"
                concept["metadata"]["updated_at"] = datetime.utcnow().isoformat()
                self._audit_sense(concept, s, "sense_upgrade", source,
                                  old_value=old_def, new_value=definition)
                self.store.touch_concept(word, s.get("confidence"))
                self.store.save()
                return s
        return None

    # ---------------------------------------------------------
    # Verwijderpad (punt 1, 6 augustus 2026) — reject = tombstone,
    # hard_delete = fysiek verwijderen. Zie find_contradictions()/
    # reasoning-laag verderop, die "rejected" overal negeert.
    # ---------------------------------------------------------
    def reject_sense(self, word: str, sense_id: str, reason: str = "") -> dict | None:
        """
        Markeert een sense als afgewezen (tombstone). De sense blijft
        in concepts.json staan -- enkel status verandert naar
        "rejected" en de reden/tijdstip komen in de audit_log. De
        reasoning-laag (get_best_definition, get_relations via
        RelationEngine, is_a_chained, find_contradictions, ...)
        negeert voortaan alles met status "rejected".

        Geeft de sense terug bij succes, None als het woord of de
        sense_id niet bestaat.
        """
        word = word.lower().strip()
        concept = self.store.get_concept(word)
        if not concept:
            return None

        for s in concept.get("senses", []):
            if s.get("sense_id") == sense_id:
                old_status = s.get("status")
                s["status"] = "rejected"
                concept["metadata"]["updated_at"] = datetime.utcnow().isoformat()
                self._audit_sense(concept, s, "sense_rejected", "user",
                                  old_value=old_status, new_value="rejected",
                                  extra={"reason": reason} if reason else None)
                self.store.save()
                return s
        return None

    def hard_delete_sense(self, word: str, sense_id: str) -> bool:
        """
        Verwijdert een sense fysiek uit concepts.json. Enkel toegestaan
        als de sense al status "rejected" heeft (guard) -- zo blijft
        er altijd eerst een tombstone/audit-spoor voordat iets echt
        verdwijnt. Bedoeld voor pure ruis (bv. een interjectie die
        nooit een concept had moeten worden), niet voor het gewone
        afwijzen van een foute bewering (dat is reject_sense()).

        Geeft True terug bij succesvol verwijderen, False als het
        woord/de sense niet bestaat of niet eerst afgewezen was.
        """
        word = word.lower().strip()
        concept = self.store.get_concept(word)
        if not concept:
            return False

        senses = concept.get("senses", [])
        for i, s in enumerate(senses):
            if s.get("sense_id") == sense_id:
                if s.get("status") != "rejected":
                    return False  # guard: eerst reject_sense(), dan pas dit
                verwijderde_sense = senses.pop(i)
                concept["metadata"]["updated_at"] = datetime.utcnow().isoformat()
                # Audit-entry op CONCEPT-niveau (niet sense-niveau, want
                # de sense zelf bestaat zo meteen niet meer om naar te
                # verwijzen) -- bewaart wat er precies verdween.
                self.store._append_audit(concept, {
                    "event_type": "sense_hard_deleted",
                    "source": "user",
                    "sense_id": sense_id,
                    "old_value": verwijderde_sense.get("definition"),
                    "new_value": None,
                }, word=word)
                self.store.save()
                return True
        return False

    def reject_concept(self, word: str, reason: str = "") -> int:
        """
        Zet ALLE senses van een concept op status "rejected" in één
        keer -- bv. als een heel woord verzonnen/ruis bleek te zijn
        (zoals 'oei', een interjectie die nooit een concept had moeten
        worden), i.p.v. senses een voor een te moeten weerleggen.

        Relaties eronder hoeven niet apart aangepast te worden: zodra
        de sense zelf status "rejected" heeft, negeert get_relations()
        (RelationEngine) toch al ALLES eronder, ongeacht de eigen
        status van de relatie zelf.

        Geeft het aantal senses terug dat effectief aangepast is (0
        als het woord niet bestaat, of als alle senses al rejected
        waren).
        """
        word = word.lower().strip()
        concept = self.store.get_concept(word)
        if not concept:
            return 0

        aangepast = 0
        for s in concept.get("senses", []):
            if s.get("status") != "rejected":
                old_status = s.get("status")
                s["status"] = "rejected"
                self._audit_sense(concept, s, "sense_rejected", "user",
                                  old_value=old_status, new_value="rejected",
                                  extra={"reason": reason} if reason else None)
                aangepast += 1

        if aangepast:
            concept["metadata"]["updated_at"] = datetime.utcnow().isoformat()
            self.store.save()
        return aangepast

    def hard_delete_concept(self, word: str) -> bool:
        """
        Verwijdert een heel concept-record fysiek uit concepts.json.
        Guard: mag alleen als ALLE senses van dit concept al status
        "rejected" hebben (dus eerst reject_concept(), of losse
        reject_sense()-aanroepen voor elke sense).

        Geeft True terug bij succesvol verwijderen, False als het
        woord niet bestaat of nog niet-afgewezen senses heeft.
        """
        word = word.lower().strip()
        concept = self.store.get_concept(word)
        if not concept:
            return False

        senses = concept.get("senses", [])
        if any(s.get("status") != "rejected" for s in senses):
            return False  # guard: eerst reject_concept(), dan pas dit

        del self.store.concepts[word]
        # Geen audit-entry meer binnen het concept zelf mogelijk (het
        # bestaat niet meer) -- wel naar het externe logbestand, zodat
        # er alsnog een spoor blijft van WAT er verdween en WANNEER.
        self.store._write_log(
            event_type="concept_hard_deleted",
            word=word,
            source="user",
            extra={"aantal_senses_verwijderd": len(senses)}
        )
        self.store.save()
        return True

    def get_senses(self, word: str) -> list[dict]:
        concept = self.store.get_concept(word)
        if not concept:
            return []
        return concept.get("senses", [])

    def get_best_definition(self, word: str, context_words: list[str] | None = None) -> str | None:
        senses = self.get_senses(word)
        # Verwijderpad (punt 1/2, 6 augustus 2026): een afgewezen sense
        # mag nooit meer als "het beste antwoord" naar buiten komen --
        # get_senses() zelf blijft hem tonen (transparantie, bv. voor
        # concept_overview.py), maar deze reasoning-query niet.
        real_senses = [
            s for s in senses
            if s.get("definition") != "unknown" and s.get("status") != "rejected"
        ]
        if not real_senses:
            return None

        # Bug #10-fix: als er context_words zijn meegegeven, proberen we
        # eerst via signaalwoorden de juiste sense te herkennen (bv.
        # "wat is python, is dat een gevaarlijk dier?" -> python#2).
        # Geen context, of geen duidelijke match -> val terug op het
        # oude gedrag (hoogste confidence), exact zoals voorheen.
        if context_words:
            sense_id = self.detect_sense(word, context_words)
            if sense_id:
                for s in real_senses:
                    if s.get("sense_id") == sense_id:
                        return s.get("definition")

        best = max(real_senses, key=lambda s: s.get("confidence", 0))
        return best.get("definition")

    def detect_sense(self, word: str, context_words: list[str]) -> str | None:
        """
        Bepaalt welke sense van een meerduidig woord bedoeld is, op basis
        van de andere woorden in de zin (context_words).

        Werkt puur symbolisch via 'signaalwoorden' die per sense in
        concepts.json staan (bv. python#2 heeft signaalwoorden als
        "slang", "dier", "prooi"). Geen ML/LLM.

        Geeft terug:
        - None als het woord geen concept is, geen senses heeft, of maar
          1 sense heeft (dan is er toch niets te kiezen)
        - None bij een gelijke stand (geen duidelijke winnaar) of als
          geen enkele sense signaalwoorden heeft ingevuld
        - anders: de sense_id (bv. "python#2") van de sense met de meeste
          treffers in de context_words
        """
        senses = self.get_senses(word)
        # Verwijderpad (punt 1/2, 6 augustus 2026): een afgewezen sense
        # mag niet als disambiguatie-kandidaat voorgesteld worden.
        real_senses = [
            s for s in senses
            if s.get("definition") != "unknown" and s.get("status") != "rejected"
        ]

        if len(real_senses) <= 1:
            return None  # Niets om te disambigueren

        context_set = set(context_words)

        scores = []
        for s in real_senses:
            signaalwoorden = s.get("signaalwoorden", [])
            if not signaalwoorden:
                continue
            aantal_treffers = len(context_set & set(signaalwoorden))
            if aantal_treffers > 0:
                scores.append((s["sense_id"], aantal_treffers))

        if not scores:
            return None  # Geen enkele match

        scores.sort(key=lambda x: x[1], reverse=True)

        # Bij een gelijke stand tussen de top-2 is er geen duidelijke
        # winnaar — dan laten we het bewust aan None, zodat de aanroeper
        # (Layer 1 / get_meaning) op de bestaande fallback terugvalt.
        if len(scores) > 1 and scores[0][1] == scores[1][1]:
            return None

        return scores[0][0]

    def detect_pos(self, word: str) -> str:
        w = word.lower().strip()

        concept = self.store.get_concept(w)
        if concept:
            senses = concept.get("senses", [])
            real = [s for s in senses if s.get("definition") != "unknown"]
            if real and real[0].get("pos"):
                return real[0]["pos"]

        if w.endswith("en") and len(w) > 3:
            stem = w[:-2]
            if self.store.has_concept(stem):
                return "noun"

        infinitives = {
            "lopen", "werken", "spelen", "maken", "doen", "zien", "gaan",
            "komen", "blijven", "eten", "drinken", "schrijven", "lezen",
            "vinden", "spreken", "kijken", "denken", "geven", "nemen",
            "vragen", "zeggen", "weten", "kennen", "willen", "kunnen",
            "moeten", "helpen", "spelen", "praten",
        }
        if w in infinitives:
            return "verb"

        # Bugfix (27 juli 2026): vervoegde werkwoordsvormen (bv. "drink",
        # "speel", "vind" -- ik-vorm van "drinken"/"spelen"/"vinden")
        # werden hier voorheen niet herkend, want deze lijst checkte
        # enkel de kale INFINITIEF. Een niet-herkende vervoegde vorm
        # viel daardoor door naar de "noun"-default hieronder, en
        # auto_learn() sloeg het dan ten onrechte op als zelfstandig
        # naamwoord. Nu wordt ELKE veelvoorkomende vervoegingsuitgang
        # ("t", "en", "de", "den", "d") van het woord afgehaald en
        # gecombineerd met de twee gangbare infinitief-uitgangen
        # ("en"/"n") gecheckt tegen dezelfde infinitieven-set hierboven
        # -- geen nieuwe woordenlijst, enkel een bredere match op de
        # lijst die al bestond. Blijft bewust simpel/symbolisch: geen
        # volledige vervoegingsgrammatica, enkel de meest voorkomende
        # patronen (ik/jij/hij-vorm, verleden tijd).
        #
        # BUGFIX-VERVOLG (27 juli 2026): eerste versie van deze fix
        # miste nog "speel" (en soortgelijke: "loop", "maak", ...) --
        # de Nederlandse spellingsregel dat een lange klinker in de
        # ik-vorm ENKEL verdubbeld wordt als er geen uitgang volgt
        # (speel -> spelen, niet "speelen") werd nog niet gedekt. Nu
        # wordt bij een stam die eindigt op medeklinker + dubbele
        # klinker ("ee"/"oo"/"uu") ook de ENKELVOUDIGE klinkervorm
        # geprobeerd ("speel" -> "spel", dan "spel"+"en" = "spelen").
        vervoeging_afkappingen = ("den", "de", "en", "t", "d", "")
        kandidaat_stammen = {w}
        for afkapping in vervoeging_afkappingen:
            if afkapping and w.endswith(afkapping):
                kandidaat_stammen.add(w[: -len(afkapping)])

        for stam in kandidaat_stammen:
            for infinitief_uitgang in ("en", "n"):
                if stam + infinitief_uitgang in infinitives:
                    return "verb"

            # Klinkerverdubbelingsregel: medeklinker + dubbele klinker
            # (ee/oo/uu) aan het einde van de stam -> probeer ook de
            # enkelvoudige klinkervorm (speel -> spel, loop -> lop).
            if (
                len(stam) >= 3
                and stam[-1] not in "aeiou"
                and stam[-2] == stam[-3]
                and stam[-2] in "aeou"
            ):
                korte_stam = stam[:-2] + stam[-1]
                for infinitief_uitgang in ("en", "n"):
                    if korte_stam + infinitief_uitgang in infinitives:
                        return "verb"

        if w.endswith("lijk") or w.endswith("ig") or w.endswith("isch"):
            return "adj"

        # Bugfix (27 juli 2026): veelvoorkomende bijwoorden/voorzetsels/
        # functiewoorden die GEEN zelfstandig naamwoord zijn, maar door
        # de "noun"-default hieronder toch als concept werden aan-
        # gemaakt (bv. "graag", "heel", "snel", "aan"). Zelfde soort
        # vaste, symbolische stopwoordenlijst als RelationParser.
        # STOPWOORDEN (semantic.py) en response_pipeline.py's eigen
        # stopwoorden-set -- hier specifiek gericht op woordsoort i.p.v.
        # relatie-ruis. Geeft bewust geen "noun"/"verb" terug voor deze
        # woorden; "function" signaleert aan de aanroeper (auto_learn())
        # dat dit woord niet als zelfstandig naamwoord-concept hoort.
        FUNCTIEWOORDEN = {
            "graag", "heel", "snel", "aan", "even", "helemaal", "hoor",
            "warm", "welke", "waarop", "waarin", "waaruit", "waardoor",
            "waarvoor", "toch", "wel", "niet", "ook", "nog", "al",
            "misschien", "gewoon", "zeker", "eigenlijk", "samen",
        }
        if w in FUNCTIEWOORDEN:
            return "function"

        return "noun"


# ---------------------------------------------------------
# 3. RelationEngine – relaties tussen concepten
# ---------------------------------------------------------
class RelationEngine:
    def __init__(self, store: ConceptStore, sense_engine: SenseEngine):
        self.store = store
        self.sense_engine = sense_engine

    def _audit_relation(self, concept: Dict[str, Any], sense: Dict[str, Any],
                        rel: Dict[str, Any], event_type: str = "relation_add") -> None:
        entry = {
            "event_type": event_type,
            "source": rel.get("source", "user"),
            "sense_id": sense.get("sense_id"),
            "relation": {
                "type": rel.get("type"),
                "target": rel.get("target"),
                "confidence": rel.get("confidence"),
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        concept.setdefault("audit_log", []).append(entry)

    def add_relation(self, subject: str, relation_type: str,
                     target: str, sense_id: Optional[str] = None) -> bool:

        subject = subject.lower().strip()
        target = target.lower().strip()

        concept = self.store.ensure_concept(subject)
        senses = concept["senses"]

        # Sense kiezen
        if sense_id:
            sense = next((s for s in senses if s["sense_id"] == sense_id), None)
            if not sense:
                return False
        else:
            real_senses = [s for s in senses if s.get("definition") != "unknown"]
            if real_senses:
                sense = max(real_senses, key=lambda s: s.get("confidence", 0))
            else:
                sense = senses[0] if senses else self.sense_engine.add_sense(
                    subject, "unknown", source="auto", confidence=0.1
                )

        # Duplicate check
        for rel in sense["relations"]:
            if rel["type"] == relation_type and rel["target"] == target:
                self.store.save()
                return False

        rel_obj = {
            "type": relation_type,
            "target": target,
            "confidence": 1.0,
            "source": "user",
            # Trust state (punt 3, 6 augustus 2026): add_relation() wordt
            # altijd met source="user" opgeslagen (zie hierboven -- geen
            # source-parameter, dus elke aanroeper komt via de confirm-
            # flow van een mens). Status is hier dus altijd confirmed.
            # Mocht add_relation() ooit een source-parameter krijgen
            # (bv. voor auto_extract_is_a), dan moet deze regel mee
            # veranderen naar dezelfde "user" → confirmed / anders →
            # unverified-regel als bij add_sense().
            "status": "confirmed",
            "created_at": datetime.utcnow().isoformat()
        }
        sense["relations"].append(rel_obj)

        concept["metadata"]["updated_at"] = datetime.utcnow().isoformat()
        self._audit_relation(concept, sense, rel_obj, event_type="relation_add")
        self.store.touch_concept(subject, sense.get("confidence"))
        self.store.save()
        return True

    # ---------------------------------------------------------
    # Verwijderpad (punt 1, 6 augustus 2026) — zelfde opzet als
    # SenseEngine.reject_sense()/hard_delete_sense() hierboven.
    # Een relatie heeft geen eigen id -- geïdentificeerd via de
    # combinatie sense_id + relation_type + target, dezelfde
    # combinatie die add_relation()'s duplicate-check al gebruikt.
    # ---------------------------------------------------------
    def reject_relation(self, word: str, sense_id: str, relation_type: str,
                        target: str, reason: str = "") -> dict | None:
        """
        Markeert een relatie als afgewezen (tombstone). Blijft in
        concepts.json staan -- enkel status verandert naar "rejected".
        De reasoning-laag (get_relations, is_a_chained, ...) negeert
        voortaan alles met status "rejected".

        Geeft het relatie-object terug bij succes, None als het woord,
        de sense of de relatie niet gevonden wordt.
        """
        word = word.lower().strip()
        target = target.lower().strip()
        concept = self.store.get_concept(word)
        if not concept:
            return None

        sense = next((s for s in concept.get("senses", []) if s.get("sense_id") == sense_id), None)
        if not sense:
            return None

        for rel in sense.get("relations", []):
            if rel.get("type") == relation_type and rel.get("target") == target:
                old_status = rel.get("status")
                rel["status"] = "rejected"
                concept["metadata"]["updated_at"] = datetime.utcnow().isoformat()
                entry = {
                    "event_type": "relation_rejected",
                    "source": "user",
                    "sense_id": sense_id,
                    "relation": {"type": relation_type, "target": target},
                    "old_value": old_status,
                    "new_value": "rejected",
                }
                if reason:
                    entry["reason"] = reason
                entry["timestamp"] = datetime.utcnow().isoformat()
                concept.setdefault("audit_log", []).append(entry)
                self.store.save()
                return rel
        return None

    def hard_delete_relation(self, word: str, sense_id: str, relation_type: str,
                             target: str) -> bool:
        """
        Verwijdert een relatie fysiek. Enkel toegestaan als de relatie
        al status "rejected" heeft (guard, zelfde principe als
        hard_delete_sense()).

        Geeft True terug bij succesvol verwijderen, False anders.
        """
        word = word.lower().strip()
        target = target.lower().strip()
        concept = self.store.get_concept(word)
        if not concept:
            return False

        sense = next((s for s in concept.get("senses", []) if s.get("sense_id") == sense_id), None)
        if not sense:
            return False

        relations = sense.get("relations", [])
        for i, rel in enumerate(relations):
            if rel.get("type") == relation_type and rel.get("target") == target:
                if rel.get("status") != "rejected":
                    return False  # guard: eerst reject_relation(), dan pas dit
                verwijderde_relatie = relations.pop(i)
                concept["metadata"]["updated_at"] = datetime.utcnow().isoformat()
                self.store._append_audit(concept, {
                    "event_type": "relation_hard_deleted",
                    "source": "user",
                    "sense_id": sense_id,
                    "relation": {
                        "type": verwijderde_relatie.get("type"),
                        "target": verwijderde_relatie.get("target"),
                    },
                    "old_value": verwijderde_relatie.get("target"),
                    "new_value": None,
                }, word=word)
                self.store.save()
                return True
        return False

    def get_relations(self, word: str, relation_type: Optional[str] = None) -> List[str]:
        word = word.lower().strip()
        concept = self.store.get_concept(word)
        if not concept:
            return []

        results = []
        for sense in concept["senses"]:
            # Verwijderpad (punt 1/2, 6 augustus 2026): een afgewezen
            # sense telt sowieso niet mee -- alle relaties eronder zijn
            # dan irrelevant, wat er ook met hun eigen status is.
            if sense.get("status") == "rejected":
                continue
            for rel in sense["relations"]:
                # Een individueel afgewezen relatie (de sense zelf kan
                # prima confirmed/unverified blijven) telt ook niet mee.
                # unverified blijft WEL meetellen -- enkel rejected
                # wordt genegeerd, zie punt 3 se stand van zaken.
                if rel.get("status") == "rejected":
                    continue
                if relation_type is None or rel["type"] == relation_type:
                    results.append(rel["target"])

        return list(dict.fromkeys(results))

    def is_a(self, source: str, target: str) -> bool:
        source = source.lower().strip()
        target = target.lower().strip()
        relations = self.get_relations(source, relation_type="is_a")
        return target in relations

    def get_synonyms(self, word: str) -> List[str]:
        return self.get_relations(word, relation_type="synonym")

    def get_antonyms(self, word: str) -> List[str]:
        return self.get_relations(word, relation_type="antonym")

    def get_used_for(self, word: str) -> List[str]:
        return self.get_relations(word, relation_type="used_for")

    def get_causes(self, word: str) -> List[str]:
        return self.get_relations(word, relation_type="causes")

    def get_instances(self, word: str) -> List[str]:
        return self.get_relations(word, relation_type="instance_of")

    def get_properties(self, word: str) -> List[str]:
        return self.get_relations(word, relation_type="property_of")

    def get_all_relations(self, word: str) -> Dict[str, List[str]]:
        word = word.lower().strip()
        concept = self.store.get_concept(word)
        if not concept:
            return {}

        result: Dict[str, List[str]] = {}
        for sense in concept["senses"]:
            # Verwijderpad (punt 1/2, 6 augustus 2026): zelfde filter
            # als get_relations() hierboven.
            if sense.get("status") == "rejected":
                continue
            for rel in sense["relations"]:
                if rel.get("status") == "rejected":
                    continue
                rel_type = rel["type"]
                target = rel["target"]
                if rel_type not in result:
                    result[rel_type] = []
                if target not in result[rel_type]:
                    result[rel_type].append(target)
        return result

# ---------------------------------------------------------
# 4. ReasoningEngine – chaining, inference, contradictions
# ---------------------------------------------------------
class ReasoningEngine:
    """
    Fase 7 — Reasoning Layer
    Voert indirecte redenering uit over de kennisgraaf.
    """

    def __init__(self, store: ConceptStore, relation_engine: RelationEngine):
        self.store = store
        self.relation_engine = relation_engine
        self.MAX_DEPTH = 6  # maximale stappen bij chaining

    # ---------------------------------------------------------
    # 7.1 Chaining — is A via tussenstappen een B?
    # ---------------------------------------------------------
    def is_a_chained(self, source: str, target: str, _visited: set = None) -> tuple[bool, list]:
        """
        Zoekt of source → target bestaat via is_a ketens.
        Geeft terug: (gevonden: bool, pad: list)
        Voorbeeld: hond → dier → levend_wezen → True, ["hond", "dier", "levend_wezen"]
        """
        if _visited is None:
            _visited = set()

        source = source.lower().strip()
        target = target.lower().strip()

        if source == target:
            return True, [source]

        if source in _visited or len(_visited) >= self.MAX_DEPTH:
            return False, []

        _visited.add(source)

        direct = self.relation_engine.get_relations(source, relation_type="is_a")
        for parent in direct:
            if parent == target:
                return True, [source, target]
            found, pad = self.is_a_chained(parent, target, _visited)
            if found:
                return True, [source] + pad

        return False, []

    # ---------------------------------------------------------
    # 7.1b Chaining — is A onderdeel van B, via tussenstappen?
    # ---------------------------------------------------------
    def part_of_chained(self, source: str, target: str, _visited: set = None) -> tuple[bool, list]:
        """
        Zoekt of source → target bestaat via part_of ketens.
        Geeft terug: (gevonden: bool, pad: list)
        Voorbeeld: snaar → part_of → gitaar → part_of → orkest
                   part_of_chained("snaar", "orkest") -> True, ["snaar", "gitaar", "orkest"]
        Analoog aan is_a_chained, maar volgt uitsluitend part_of-relaties.
        """
        if _visited is None:
            _visited = set()

        source = source.lower().strip()
        target = target.lower().strip()

        if source == target:
            return True, [source]

        if source in _visited or len(_visited) >= self.MAX_DEPTH:
            return False, []

        _visited.add(source)

        direct = self.relation_engine.get_relations(source, relation_type="part_of")
        for parent in direct:
            if parent == target:
                return True, [source, target]
            found, pad = self.part_of_chained(parent, target, _visited)
            if found:
                return True, [source] + pad

        return False, []
    
    # ---------------------------------------------------------
    # 7.2 Inference — oorzaak-ketens doordenken
    # ---------------------------------------------------------
    def causes_chained(self, source: str, target: str, _visited: set = None) -> tuple[bool, list]:
        """
        Zoekt of source via causes-ketens target bereikt.
        Voorbeeld: regen → modder → uitglijden
        """
        if _visited is None:
            _visited = set()

        source = source.lower().strip()
        target = target.lower().strip()

        if source == target:
            return True, [source]

        if source in _visited or len(_visited) >= self.MAX_DEPTH:
            return False, []

        _visited.add(source)

        direct = self.relation_engine.get_relations(source, relation_type="causes")
        for effect in direct:
            if effect == target:
                return True, [source, target]
            found, pad = self.causes_chained(effect, target, _visited)
            if found:
                return True, [source] + pad

        return False, []

    # ---------------------------------------------------------
    # 7.3 Contradiction detection
    # ---------------------------------------------------------
    def find_contradictions(self, word: str) -> list[dict]:
        """
        Zoekt conflicterende is_a relaties voor een woord.
        Voorbeeld: als 'hond' zowel 'dier' als 'meubel' is → mogelijk conflict.
        Geeft lijst van conflicten terug.
        """
        contradictions = []

        # Bekende incompatibele categorieën
        INCOMPATIBLE_GROUPS = [
            {"dier", "plant", "meubel", "voertuig", "gebouw", "apparaat", "voedsel"},
            {"levend", "niet-levend"},
            {"vloeibaar", "vast", "gas"},
        ]

        parents = self.relation_engine.get_relations(word, relation_type="is_a")

        for group in INCOMPATIBLE_GROUPS:
            gevonden = [p for p in parents if p in group]
            if len(gevonden) >= 2:
                contradictions.append({
                    "word": word,
                    "conflict": gevonden,
                    "reason": f"'{word}' kan niet tegelijk {' en '.join(gevonden)} zijn"
                })

        return contradictions

    # ---------------------------------------------------------
    # 7.4 Hulpfuncties voor uitleg
    # ---------------------------------------------------------
    def explain_is_a(self, source: str, target: str) -> str:
        """
        Geeft een leesbare uitleg van het redeneerpad.
        Voorbeeld: "hond is een dier, want: hond → dier → levend wezen"
        """
        found, pad = self.is_a_chained(source, target)
        if not found:
            return f"Ik kan niet bewijzen dat '{source}' een '{target}' is."

        if len(pad) == 2:
            return f"Ja, een {source} is een {target}."

        stappen = " → ".join(pad)
        return f"Ja, een {source} is een {target}, want: {stappen}."

    def explain_causes(self, source: str, target: str) -> str:
        """
        Geeft een leesbare uitleg van een oorzaak-keten.
        """
        found, pad = self.causes_chained(source, target)
        if not found:
            return f"Ik kan niet bewijzen dat '{source}' leidt tot '{target}'."

        if len(pad) == 2:
            return f"Ja, {source} veroorzaakt {target}."

        stappen = " → ".join(pad)
        return f"Ja, {source} leidt uiteindelijk tot {target}, via: {stappen}."

    def explain_part_of(self, source: str, target: str) -> str:
        """
        Geeft een leesbare uitleg van het part_of-redeneerpad.
        Voorbeeld: "een snaar is onderdeel van een orkest, want:
        snaar → gitaar → orkest"
        Analoog aan explain_is_a, maar voor part_of-ketens.
        """
        found, pad = self.part_of_chained(source, target)
        if not found:
            return f"Ik kan niet bewijzen dat '{source}' onderdeel is van '{target}'."

        if len(pad) == 2:
            return f"Ja, een {source} is onderdeel van {target}."

        stappen = " → ".join(pad)
        return f"Ja, een {source} is onderdeel van {target}, want: {stappen}."

    # ---------------------------------------------------------
    # 7.5 Omgekeerde is_a-lookup — alle subtypes van een categorie
    # ---------------------------------------------------------
    def get_all_subtypes(self, target: str) -> list:
        """
        Geeft alle concepten terug die (direct of via een is_a-keten)
        naar 'target' verwijzen. Dit is NIET hetzelfde als de is_a-
        relatie omdraaien (dat zou inhoudelijk fout zijn) — het is een
        aparte, omgekeerde doorloop van de bestaande relatie-graaf.
        Voorbeeld: get_all_subtypes("dier") -> ["hond", "kat", "wolf",
        "grizzlybeer", "bruine beer", "beer", "zoogdier", ...]
        Nieuw (12 juli 2026), analoog qua opzet aan is_a_chained maar
        dan "achterstevoren": we doorlopen ALLE concepten en houden
        enkel diegene over waarvoor is_a_chained(concept, target) waar
        is.
        """
        target = target.lower().strip()
        subtypes = []

        for word in self.store.concepts.keys():
            if word == target:
                continue
            found, _ = self.is_a_chained(word, target)
            if found:
                subtypes.append(word)

        return subtypes

# ---------------------------------------------------------
# 5. TeachEngine
# ---------------------------------------------------------
class TeachEngine:
    IRREGULAR_PLURALS = {
        "kinderen": "kind",
        "mensen": "mens",
        "eieren": "ei",
        "huizen": "huis",
        "bladeren": "blad",
        "koeien": "koe",
        "varkens": "varken",
        "lui": "luiaard",
    }
    
    def __init__(self, store: ConceptStore, sense_engine: SenseEngine):
        self.store = store
        self.sense_engine = sense_engine
        

    def _normalize_plural_if_noun(self, word: str, pos: str) -> str:
        w = word.lower().strip()
        if pos == "verb":
            return w

        # 0) Irregular plurals
        if w in self.IRREGULAR_PLURALS:
            return self.IRREGULAR_PLURALS[w]

        # 1) bestaande logica: -en
        if w.endswith("en") and len(w) > 3:
            stem = w[:-2]
            if self.store.has_concept(stem):
                return stem

        # 2) nieuwe simpele logica: -s
        if w.endswith("s") and len(w) > 3:
            stem = w[:-1]
            if self.store.has_concept(stem):
                return stem

        return w

    def teach(self, word: str, definition: str, source: str = "user") -> dict:
        word = word.lower().strip()
        definition = definition.strip()

        # 1. voorlopige POS bepalen op basis van originele vorm
        pos_guess = self.sense_engine.detect_pos(word)

        # 2. meervoud-normalisatie alleen als het geen verb is
        word = self._normalize_plural_if_noun(word, pos_guess)

        # 2B. Meervoud-definitie blokkeren
        if definition.startswith("meerdere ") or definition.startswith("veel "):
            concept = self.store.ensure_concept(word)
            if concept["senses"]:
                concept["senses"][0]["examples"].append(definition)
                concept["metadata"]["updated_at"] = datetime.utcnow().isoformat()
                self.sense_engine._audit_sense(
                    concept, concept["senses"][0],
                    event_type="example_add", source=source,
                    old_value=None, new_value=definition
                )
                self.store.touch_concept(word, concept["senses"][0].get("confidence"))
                self.store.save()
                return concept["senses"][0]

        # 3. unknown upgraden
        upgraded = self.sense_engine.upgrade_unknown_sense(
            word, definition, source=source,
            confidence=1.0 if source == "user" else 0.7
        )
        if upgraded:
            # Trust state (punt 3, 6 augustus 2026): de sense zelf wordt
            # hierboven al confirmed (Kevin typte deze definitie). De
            # is_a-relatie die hieronder uit diezelfde tekst wordt
            # GERADEN blijft bewust apart unverified -- Kevin bevestigde
            # de definitie, niet noodzakelijk de afgeleide categorie.
            self._auto_extract_is_a(word, definition, upgraded)  # NIEUW
            return upgraded

        # 4. definitieve POS (na normalisatie)
        pos = self.sense_engine.detect_pos(word)

        sense = self.sense_engine.add_sense(
            word=word,
            definition=definition,
            source=source,
            confidence=1.0 if source == "user" else 0.7,
            pos=pos
        )

        # Bug #32-fix (8 augustus 2026): add_sense() geeft nu een
        # "blocked"-signaal terug i.p.v. een sense, als de definitie
        # matcht met een eerder AFGEWEZEN (rejected) sense. Dat mag hier
        # NOOIT stilzwijgend als een normale, geslaagde sense behandeld
        # worden -- dus geven we het signaal gewoon door aan de
        # aanroeper (SemanticConceptsModule/wikipedia_teacher.py), die
        # wél toegang heeft tot de chat om Kevin hierover te informeren
        # of te vragen. _auto_extract_is_a() wordt hier bewust NIET op
        # aangeroepen, want er is niets nieuws om relaties uit te halen.
        if isinstance(sense, dict) and sense.get("blocked") == "rejected":
            return sense

        # Trust state: zie opmerking hierboven -- zelfde redenering.
        self._auto_extract_is_a(word, definition, sense)  # NIEUW
        return sense

    def _auto_extract_is_a(self, word: str, definition: str, sense: dict) -> None:
        """
        Extraheert automatisch een is_a relatie uit een definitie.
        "een vrucht met een harde pit" → is_a: vrucht
        "een dier dat blaft"           → is_a: dier
        "een soort voertuig"           → is_a: voertuig

        Bugfix #7 (18 juli 2026): uitgebreid met twee nieuwe patronen.
        De oorspronkelijke drie patronen hierboven verwachten allemaal
        dat de definitie LETTERLIJK BEGINT met "een ..." — maar bijna
        elke Wikipedia-definitie in concepts.json volgt in de praktijk
        het patroon "[Het woord zelf] is een X die/dat/...", waarbij
        het woord zelf eerst genoemd wordt. Bijvoorbeeld:
          "Een fiets is een voertuig dat..."    → is_a: voertuig
          "Een planeet is een hemellichaam..."  → is_a: hemellichaam
          "De Octopoda zijn een orde binnen..." → is_a: orde
        Geen van de eerste drie patronen ving dit op, waardoor bijna
        alle Wikipedia-afkomstige definities nooit een automatische
        is_a-relatie kregen. Patroon 4/5/6 hieronder lossen dit op.

        Daarnaast zijn "waarmee/waarin/waaruit/waardoor/waarop/
        waarvoor" toegevoegd naast het bestaande losse "waar", omdat
        definities zoals "een apparaat waarmee gegevens..." anders
        gemist werden (het samengestelde voorzetsel-woord matchte niet
        met enkel "waar" gevolgd door een woordgrens).

        BEWUST NIET meegenomen (te onbetrouwbaar voor pure regex,
        apart werkpuntje voor later): definities met een bijvoeglijk
        naamwoord vlak na "een" en vóór het echte target-zelfstandig-
        naamwoord, zoals "een grote, niet-giftige slang" (target zou
        "slang" moeten zijn, niet "grote"). Dat vraagt een POS-check
        per woord (via detect_pos()) i.p.v. een simpele regex-match,
        en verhoogt het risico op foute matches — bewust uitgesteld.
        """
        import re
        t = definition.lower().strip()
        stopwords = {"de", "het", "een", "ook", "wel", "niet", "van", "en", "of"}
        bijvoeglijk = {"groot", "klein", "lang", "breed", "hoog", "laag", "oud",
                       "nieuw", "goed", "slecht", "bekend", "veel", "weinig"}

        # Voorzetsel-achtige woorden waarop een relatieve bijzin kan
        # volgen — inclusief de samengestelde "waar+voorzetsel"-vormen
        # (waarmee, waarin, waaruit, waardoor, waarop, waarvoor), die
        # voorheen ontbraken naast het losse "waar".
        volgwoorden = (
            r"met|die|dat|van|voor|uit|waar|om"
            r"|waarmee|waarin|waaruit|waardoor|waarop|waarvoor"
        )

        target = None

        # "een X met/die/dat/van/voor/uit/waar(mee/in/...)/om..."
        m = re.match(rf"een\s+(\w+)\s+(?:{volgwoorden})\b", t)
        if m:
            target = m.group(1)

        # "een soort/type X"
        if not target:
            m = re.match(r"een\s+(?:soort|type|vorm)\s+(?:van\s+)?(\w+)", t)
            if m:
                target = m.group(1)

        # "een X" alleen (zonder extra woorden)
        if not target:
            m = re.match(r"een\s+(\w+)$", t)
            if m:
                target = m.group(1)

        # NIEUW — Patroon 4: "[...] is een X met/die/dat/waarmee/..."
        # Het woord zelf staat voorop de zin ("Een fiets IS EEN
        # voertuig dat..."), dus we zoeken niet vanaf het begin van de
        # zin (re.match) maar ergens IN de zin (re.search).
        if not target:
            m = re.search(rf"\bis\s+een\s+(\w+)\s+(?:{volgwoorden})\b", t)
            if m:
                target = m.group(1)

        # NIEUW — Patroon 5: "[...] zijn een X met/die/dat/..." (voor
        # meervoud-onderwerpen, bv. "De Octopoda ZIJN EEN orde binnen...")
        if not target:
            m = re.search(rf"\bzijn\s+een\s+(\w+)\s+(?:{volgwoorden})\b", t)
            if m:
                target = m.group(1)

        # NIEUW — Patroon 6: "[...] is een X" zonder vervolg (kortere
        # definities zonder relatieve bijzin erna)
        if not target:
            m = re.search(r"\bis\s+een\s+(\w+)$", t)
            if m:
                target = m.group(1)

        if not target:
            return
        if target in stopwords or target in bijvoeglijk or len(target) <= 2:
            return
        if target == word:
            return

        # Relatie toevoegen als die nog niet bestaat
        bestaande = [r["target"] for r in sense.get("relations", [])]
        if target not in bestaande:
            sense.setdefault("relations", []).append({
                "type": "is_a",
                "target": target,
                "confidence": 0.9,
                "source": "auto_extract",
                # Trust state (punt 3, 6 augustus 2026): automatisch uit
                # een definitie geëxtraheerd, nooit door Kevin bevestigd
                # -> unverified totdat hij het bevestigt of afwijst.
                "status": "unverified",
                "created_at": datetime.utcnow().isoformat()
            })
            self.store.save()

    def auto_learn(self, word: str) -> dict:
        word = word.lower().strip()

        pos_guess = self.sense_engine.detect_pos(word)

        # Bugfix (27 juli 2026): functiewoorden (bijwoorden/voorzetsels,
        # zie detect_pos()'s nieuwe FUNCTIEWOORDEN-check) mogen nooit
        # als concept aangemaakt worden -- dit was exact de bron van de
        # 11 resterende ruis-concepten (drink, graag, speel, vind, ...)
        # in concepts.json. Geeft een "leeg" resultaat terug i.p.v. een
        # nieuw concept, zodat de aanroeper weet dat hier bewust niets
        # geleerd is.
        if pos_guess == "function":
            return {"definition": "unknown", "pos": "function", "geweigerd": True}

        word = self._normalize_plural_if_noun(word, pos_guess)

        concept = self.store.ensure_concept(word)

        for s in concept["senses"]:
            if s.get("definition") == "unknown":
                return s

        pos = self.sense_engine.detect_pos(word)
        return self.sense_engine.add_sense(
            word=word,
            definition="unknown",
            source="auto",
            confidence=0.1,
            pos=pos
        )


# ---------------------------------------------------------
# 6. RelationParser
# ---------------------------------------------------------
class RelationParser:
    # Woorden die NOOIT als nieuw subject/object mogen dienen voor een
    # automatisch aangemaakt "unknown"-concept. Dit zijn vraagwoorden,
    # tussenwerpsels en functiewoorden die toevallig binnen een patroon
    # als " is een ", " lijkt op ", " zijn " kunnen vallen in gewone
    # chatzinnen die GEEN echte kennisrelatie beschrijven (bv. "dat lijkt
    # op wat ik bedoelde"). Bestaande concepten worden hier NOOIT door
    # geblokkeerd -- enkel het aanmaken van NIEUWE unknown-ruis wordt
    # tegengehouden (zie is_ruiswoord()).
    STOPWOORDEN = {
        "lijkt", "synoniem", "oke", "oké", "wat", "nova", "emergence",
        "wie", "hoe", "heet", "dank", "helpt", "echt", "snap", "bedoelt",
        "even", "helemaal", "focussen", "stuk", "snel", "elegant", "hoor",
        "warm", "welke", "ken", "waarop", "waarin", "waaruit", "waardoor",
        "waarvoor", "dat", "die", "dit", "deze", "het", "een", "de",
    }

    def __init__(self):
        self.relation_mapping = {
            " is een soort van ": "is_a",
            " is een soort ": "is_a",
            " is een ": "is_a",
            " zijn ": "is_a",
            " is het tegenovergestelde van ": "antonym",
            " is het synoniem van ": "synonym",
            " is synoniem van ": "synonym",
            " hoort bij ": "part_of",
            " is onderdeel van ": "part_of",
            " is deel van ": "part_of",
            " bestaat uit ": "part_of",
            " lijkt op ": "related_to",
            " wordt gebruikt voor ": "used_for",
            " gebruik je voor ": "used_for",
            " veroorzaakt ": "causes",
            " zorgt voor ": "causes",
            " is een eigenschap van ": "property_of",
            " is een kenmerk van ": "property_of",
            " is een voorbeeld van ": "instance_of",
            " is een instantie van ": "instance_of",
        }

    def detect_relation(self, sentence: str) -> Optional[Dict[str, str]]:
        text = " " + sentence.strip().lower() + " "
        for pattern, rel_type in self.relation_mapping.items():
            if pattern in text:
                return {
                    "pattern": pattern,
                    "relation_type": rel_type
                }
        return None

    def is_ruiswoord(self, woord: str) -> bool:
        """
        True als 'woord' een vraagwoord/tussenwerpsel/functiewoord is
        dat NIET als nieuw unknown-concept mag worden aangemaakt.
        Wordt enkel geraadpleegd als het woord nog GEEN bestaand concept
        is -- bestaande concepten (ook al staan ze toevallig in deze
        lijst) worden hier nooit door geraakt.
        """
        return woord.strip().lower() in self.STOPWOORDEN

    def parse_relation(self, sentence: str, pattern: str) -> Optional[Dict[str, str]]:
        text = sentence.strip()

        # Gebruik lowercase voor detectie
        lower = " " + text.lower() + " "
        idx = lower.find(pattern)
        if idx == -1:
            return None

        # Slice op basis van lower, maar map terug naar originele text
        # Bereken begin/eind op basis van lower
        start_left = idx
        end_left = idx + len(pattern)

        # Haal de substrings uit lower
        left_lower = lower[:start_left].strip()
        right_lower = lower[end_left:].strip()

        # Vind deze substrings terug in originele text
        # (veiligste manier zonder indexverschuiving)
        left = text[:len(left_lower)].strip()
        right_len = len(right_lower)
        right = text[-right_len:].strip() if right_len > 0 else ""

        # BUGFIX (11 juli 2026): 'right' kapte voorheen niet af bij de
        # eerstvolgende zinsgrens, waardoor bij meerdere zinnen in één
        # keer geplakt (bv. een alinea tekst) de HELE rest van de tekst
        # als object werd meegenomen i.p.v. enkel de huidige zin.
        # We knippen 'right' daarom af bij het eerste zinseinde-teken.
        for eind_teken in [". ", "! ", "? ", "\n"]:
            pos = right.find(eind_teken)
            if pos != -1:
                right = right[:pos]
        # Ook een punt/uitroepteken/vraagteken helemaal aan het einde
        # van 'right' zelf (laatste zin van de tekst) moet nog worden
        # afgekapt, want de loop hierboven vindt enkel tekens MET een
        # spatie erna.
        right = right.rstrip(".!?").strip()

        # BUGFIX 2 (11 juli 2026): zelfs binnen ÉÉN zin kan 'right' nog
        # een bijzin bevatten (bv. "berg waaruit gesmolten gesteente
        # ... komen"), waardoor het object voor een is_a-relatie veel
        # te lang en beschrijvend wordt i.p.v. een kort begrip zoals
        # "berg". We knippen 'right' daarom ook af bij de eerste
        # bijzin-marker die met een spatie ervoor voorkomt.
        bijzin_markers = [
            " waaruit ", " waarbij ", " waarvan ", " waarmee ", " waarop ",
            " waar ", " die ", " dat ", " wat ", " wie ",
        ]
        right_lower_check = " " + right.lower() + " "
        cut_pos = None
        for marker in bijzin_markers:
            pos = right_lower_check.find(marker)
            if pos != -1:
                # pos is index in de met-spaties-omhulde lowercase versie,
                # dus -1 om te corrigeren naar de echte 'right'-index
                real_pos = pos - 1
                if cut_pos is None or real_pos < cut_pos:
                    cut_pos = real_pos
        if cut_pos is not None and cut_pos > 0:
            right = right[:cut_pos].strip()

        # Lidwoorden strippen
        left = self._strip_articles(left)
        right = self._strip_articles(right)

        if not left or not right:
            return None

        return {
            "subject": left,
            "object": right
        }

    def _strip_articles(self, phrase: str) -> str:
        phrase = phrase.strip()
        lower = phrase.lower()

        articles = ["een ", "de ", "het "]
        for art in articles:
            if lower.startswith(art):
                # strip op basis van lower, maar slice op originele phrase
                return phrase[len(art):].strip()

        return phrase


# ---------------------------------------------------------
# 7. RelationFlowEngine
# ---------------------------------------------------------
class RelationFlowEngine:
    def __init__(self, store, sense_engine, relation_engine, event_bus):
        self.store = store
        self.sense_engine = sense_engine
        self.relation_engine = relation_engine
        self.event_bus = event_bus
        self.pending_relation = None

    def start_relation_flow(self, subject, relation_type, obj):
        subject = subject.strip()
        obj = obj.strip()

        self.pending_relation = {
            "subject": subject,
            "object": obj,
            "relation_type": relation_type,
            "subject_sense_id": None,
            "object_sense_id": None,
            "state": None
        }

        # 1. Subject-senses ophalen
        subject_senses = self.sense_engine.get_senses(subject)
        subject_real = [s for s in subject_senses if s.get("definition") != "unknown"]

        # 1A. Sense-choice voor subject
        if len(subject_real) > 1:
            self.pending_relation["state"] = "sense_choice_subject"
            self._ask_sense_choice(subject, subject_real, target="subject")
            return
        elif len(subject_real) == 1:
            self.pending_relation["subject_sense_id"] = subject_real[0]["sense_id"]
        elif subject_senses:
            self.pending_relation["subject_sense_id"] = subject_senses[0]["sense_id"]
        else:
            s = self.sense_engine.add_sense(subject, "unknown", source="auto", confidence=0.1)
            self.pending_relation["subject_sense_id"] = s["sense_id"]

        # 2. Object-senses ophalen
        object_senses = self.sense_engine.get_senses(obj)
        object_real = [s for s in object_senses if s.get("definition") != "unknown"]

        # 2A. Sense-choice voor object
        if len(object_real) > 1:
            self.pending_relation["state"] = "sense_choice_object"
            self._ask_sense_choice(obj, object_real, target="object")
            return
        elif len(object_real) == 1:
            self.pending_relation["object_sense_id"] = object_real[0]["sense_id"]
        elif object_senses:
            self.pending_relation["object_sense_id"] = object_senses[0]["sense_id"]
        else:
            s = self.sense_engine.add_sense(obj, "unknown", source="auto", confidence=0.1)
            self.pending_relation["object_sense_id"] = s["sense_id"]

        # 3. Beide senses bekend → confirm
        self.pending_relation["state"] = "confirm"
        self._ask_confirm()

    def handle_sense_choice(self, user_input: str):
        if not self.pending_relation:
            return

        state = self.pending_relation.get("state")
        if state not in ("sense_choice_subject", "sense_choice_object"):
            return

        user_input = user_input.strip().lower()

        try:
            idx = int(user_input) - 1
        except ValueError:
            self._send_chat("Ik begrijp je keuze niet. Kies een nummer.")
            return

        target = "subject" if state == "sense_choice_subject" else "object"
        word = self.pending_relation[target]

        senses = self.sense_engine.get_senses(word)
        real_senses = [s for s in senses if s.get("definition") != "unknown"]

        if idx < 0 or idx >= len(real_senses):
            self._send_chat("Dat nummer staat niet in de lijst. Kies opnieuw.")
            return

        chosen = real_senses[idx]
        self.pending_relation[f"{target}_sense_id"] = chosen["sense_id"]

        # Als subject gekozen is → object nog checken
        if state == "sense_choice_subject":
            obj = self.pending_relation["object"]
            object_senses = self.sense_engine.get_senses(obj)
            object_real = [s for s in object_senses if s.get("definition") != "unknown"]

            if len(object_real) > 1:
                self.pending_relation["state"] = "sense_choice_object"
                self._ask_sense_choice(obj, object_real, target="object")
                return
            elif len(object_real) == 1:
                self.pending_relation["object_sense_id"] = object_real[0]["sense_id"]
            elif object_senses:
                self.pending_relation["object_sense_id"] = object_senses[0]["sense_id"]
            else:
                s = self.sense_engine.add_sense(obj, "unknown", source="auto", confidence=0.1)
                self.pending_relation["object_sense_id"] = s["sense_id"]

        # Beide senses bekend → confirm
        self.pending_relation["state"] = "confirm"
        self._ask_confirm()

    def handle_confirm(self, user_input: str):
        if not self.pending_relation:
            return

        answer = user_input.strip().lower()
        subject = self.pending_relation["subject"]
        obj = self.pending_relation["object"]
        rel_type = self.pending_relation["relation_type"]

        if answer in ("ja", "yes", "y"):
            self.relation_engine.add_relation(
                subject,
                rel_type,
                obj,
                sense_id=self.pending_relation["subject_sense_id"]
            )
            self._send_chat(f"Oké, ik onthoud nu dat '{subject}' {rel_type} '{obj}' is.")
            self.pending_relation = None
            return

        if answer in ("nee", "no", "n"):
            self._send_chat("Oké, ik sla deze relatie niet op.")
            self.pending_relation = None
            return

        self._send_chat("Kun je dat beantwoorden met 'ja' of 'nee'?")

    def _ask_confirm(self):
        subject = self.pending_relation["subject"]
        obj = self.pending_relation["object"]
        rel_type = self.pending_relation["relation_type"]

        rel_text = {
            "is_a": "is een soort van",
            "part_of": "is onderdeel van",
            "synonym": "is synoniem van",
            "antonym": "is het tegenovergestelde van",
            "related_to": "lijkt op"
        }.get(rel_type, rel_type)

        self._send_chat(f"Mag ik onthouden dat '{subject}' {rel_text} '{obj}'?")

    def _ask_sense_choice(self, word, senses, target):
        lines = [f"Ik ken meerdere betekenissen voor '{word}'. Welke bedoel je?"]
        for i, s in enumerate(senses, start=1):
            definition = s.get("definition") or "onbekend"
            lines.append(f"{i}. {definition}")
        lines.append("Antwoord met het nummer van de juiste betekenis.")
        self._send_chat("\n".join(lines))

    def _send_chat(self, text: str):
        self.event_bus.publish("chat_response", {
            "source": "semantic",
            "text": text
        })


# ---------------------------------------------------------
# 8. SemanticConceptsModule
# ---------------------------------------------------------
class SemanticConceptsModule:

    def __init__(self, event_bus, memory_module=None):
        self.event_bus = event_bus
        self.memory = memory_module

        self.store = ConceptStore()
        self.sense_engine = SenseEngine(self.store)
        self.relation_engine = RelationEngine(self.store, self.sense_engine)
        self.reasoning_engine = ReasoningEngine(self.store, self.relation_engine)  # NIEUW
        self.teach_engine = TeachEngine(self.store, self.sense_engine)
        self.parser = RelationParser()
        # Bug #32-fix (8 augustus 2026): losse pending-state voor de
        # "wil je deze eerder afgewezen sense echt heractiveren?"-vraag.
        # Analoog aan flow_engine.pending_relation hieronder, maar een
        # eigen, kleinere state -- dit gaat over sense-reactivatie, niet
        # over een nieuwe relatie tussen twee woorden.
        self.pending_reactivation = None
        self.flow_engine = RelationFlowEngine(
            self.store, self.sense_engine, self.relation_engine, event_bus
        )

        event_bus.subscribe("teach_concept", self._on_teach_event)
        event_bus.subscribe("teach_pos", self._on_teach_pos)
        event_bus.subscribe("teach_example", self._on_teach_example)
        event_bus.publish("module_loaded", {"name": "semantic"})

    # Publieke API
    def _send_chat(self, text: str):
        self.event_bus.publish("chat_response", {
            "source": "semantic",
            "text": text
        })

    def teach(self, word, definition, source="user"):
        result = self.teach_engine.teach(word, definition, source=source)

        # Bug #32-fix (8 augustus 2026): TeachEngine.teach() geeft een
        # "blocked"-signaal terug i.p.v. een sense als de definitie
        # matcht met een eerder afgewezen (rejected) sense. Hier, op
        # module-niveau, hebben we wél toegang tot event_bus om Kevin
        # hierover te informeren -- dat kon TeachEngine zelf niet.
        if isinstance(result, dict) and result.get("blocked") == "rejected":
            sense = result["sense"]
            if source == "user":
                # Kevin zelf biedt de tekst opnieuw aan -> expliciet
                # vragen i.p.v. stilzwijgend heractiveren.
                self.pending_reactivation = {
                    "word": word.lower().strip(),
                    "sense_id": sense.get("sense_id"),
                    "definition": definition,
                    "source": source,
                    "confidence": result.get("attempted_confidence", 1.0),
                }
                self._send_chat(
                    f"Ik had '{word}' → \"{sense.get('definition')}\" eerder al "
                    f"afgewezen. Wil je dit echt opnieuw bevestigen? (ja/nee)"
                )
            else:
                # Een niet-user-bron (wikipedia/auto/auto_extract) mag
                # dit nooit zelf beslissen -- enkel melden, niets
                # aanpassen aan de bestaande rejected sense.
                self._send_chat(
                    f"Een nieuwe bron ({source}) leverde voor '{word}' dezelfde "
                    f"betekenis op die je eerder al had afgewezen — genegeerd, "
                    f"laat het weten als je dit toch wil heroverwegen."
                )
            return result

        return result

    def handle_reactivation_confirm(self, user_input: str):
        """
        Bug #32-fix (8 augustus 2026): tegenhanger van RelationFlowEngine.
        handle_confirm() hierboven, maar dan voor de "wil je deze eerder
        afgewezen sense echt heractiveren?"-vraag. Zelfde ja/nee-patroon,
        zelfde manier van aanroepen vanuit intent_router.py (via
        pending_reactivation als "is er iets aan het wachten?"-check,
        analoog aan hoe flow_engine.pending_relation al gebruikt wordt).
        """
        if not self.pending_reactivation:
            return

        answer = user_input.strip().lower()
        pending = self.pending_reactivation

        if answer in ("ja", "yes", "y"):
            concept = self.store.get_concept(pending["word"])
            if not concept:
                self._send_chat("Dat woord kon ik niet meer terugvinden.")
                self.pending_reactivation = None
                return

            for s in concept["senses"]:
                if s.get("sense_id") == pending["sense_id"]:
                    old_status = s.get("status")
                    s["status"] = "confirmed"
                    s["confidence"] = pending["confidence"]
                    concept["metadata"]["updated_at"] = datetime.utcnow().isoformat()
                    self.sense_engine._audit_sense(
                        concept, s, "sense_reactivated", pending["source"],
                        old_value=old_status, new_value="confirmed",
                        extra={"reden": "Kevin bevestigde expliciet opnieuw"}
                    )
                    self.store.touch_concept(pending["word"], s.get("confidence"))
                    self.store.save()
                    self._send_chat(
                        f"Oké, ik onthoud '{pending['word']}' → "
                        f"\"{s.get('definition')}\" weer opnieuw."
                    )
                    break
            self.pending_reactivation = None
            return

        if answer in ("nee", "no", "n"):
            self._send_chat("Oké, ik laat het zoals het was — afgewezen blijft afgewezen.")
            self.pending_reactivation = None
            return

        self._send_chat("Kun je dat beantwoorden met 'ja' of 'nee'?")

    def auto_learn(self, word):
        return self.teach_engine.auto_learn(word)

    def get_senses(self, word):
        return self.sense_engine.get_senses(word)

    def get_meaning(self, word, context_words=None):
        # 1. normaliseer meervoud → enkelvoud
        pos_guess = self.sense_engine.detect_pos(word)
        word = self.teach_engine._normalize_plural_if_noun(word, pos_guess)

        # 2. Bug #10-fix, stap 7: als context_words zelf geen duidelijke
        # sense oplevert (bv. te korte zin, "wat is python?" zonder
        # verdere aanwijzingen), kijken we of Kevin hiervoor ooit een
        # voorkeur heeft ingesteld via kevin_profile.py. Vindt
        # get_best_definition() zelf al iets via context_words, dan
        # komt deze voorkeur er nooit meer aan te pas (zie
        # get_best_definition() zelf: context_words heeft voorrang).
        #
        # We bepalen dit HIER (i.p.v. binnenin get_best_definition())
        # omdat enkel SemanticConceptsModule toegang heeft tot
        # event_bus.modules, en dus tot kevin_profile.
        voorkeur_sense_id = None
        if not context_words or not self.sense_engine.detect_sense(word, context_words):
            kevin_profile = self.event_bus.modules.get("kevin_profile") if self.event_bus else None
            if kevin_profile is not None:
                try:
                    voorkeur_sense_id = kevin_profile.get_sense_voorkeur(word)
                except Exception:
                    voorkeur_sense_id = None

        if voorkeur_sense_id:
            senses = self.sense_engine.get_senses(word)
            for s in senses:
                if s.get("sense_id") == voorkeur_sense_id and s.get("definition") != "unknown":
                    return s.get("definition")
            # Voorkeur verwijst naar een sense die niet (meer) bestaat
            # -> gewoon laten doorvallen naar de normale route hieronder.

        # 3. zoek definitie (met optionele sense-disambiguatie, Bug #10)
        return self.sense_engine.get_best_definition(word, context_words)

    def detect_sense(self, word, context_words):
        return self.sense_engine.detect_sense(word, context_words)


    def add_relation(self, subject, relation_type, target):
        return self.relation_engine.add_relation(subject, relation_type, target)

    def get_relations(self, word, relation_type=None):
        return self.relation_engine.get_relations(word, relation_type)

    def is_a(self, source, target):
        # Eerst directe check, dan chaining
        if self.relation_engine.is_a(source, target):
            return True
        found, _ = self.reasoning_engine.is_a_chained(source, target)
        return found

    def explain_is_a(self, source, target):
        return self.reasoning_engine.explain_is_a(source, target)

    def part_of(self, source, target):
        # Analoog aan is_a hierboven: eerst directe check, dan chaining.
        # Nieuw (11 juli 2026), samen met explain_part_of.
        if target in self.relation_engine.get_relations(source, relation_type="part_of"):
            return True
        found, _ = self.reasoning_engine.part_of_chained(source, target)
        return found

    def explain_part_of(self, source, target):
        return self.reasoning_engine.explain_part_of(source, target)
    
    def get_all_subtypes(self, target):
        return self.reasoning_engine.get_all_subtypes(target)
    
    def explain_causes(self, source, target):
        return self.reasoning_engine.explain_causes(source, target)

    def find_contradictions(self, word):
        return self.reasoning_engine.find_contradictions(word)

    # ---------------------------------------------------------
    # Verwijderpad (punt 1, 6 augustus 2026)
    # ---------------------------------------------------------
    def reject_sense(self, word, sense_id, reason=""):
        return self.sense_engine.reject_sense(word, sense_id, reason)

    def hard_delete_sense(self, word, sense_id):
        return self.sense_engine.hard_delete_sense(word, sense_id)

    def reject_concept(self, word, reason=""):
        return self.sense_engine.reject_concept(word, reason)

    def hard_delete_concept(self, word):
        return self.sense_engine.hard_delete_concept(word)

    def reject_relation(self, word, sense_id, relation_type, target, reason=""):
        return self.relation_engine.reject_relation(word, sense_id, relation_type, target, reason)

    def hard_delete_relation(self, word, sense_id, relation_type, target):
        return self.relation_engine.hard_delete_relation(word, sense_id, relation_type, target)

    def search(self, query: str) -> list:
        return self.store.search(query)

    def export_concept(self, word: str) -> dict | None:
        return self.store.export_concept(word)

    def get_synonyms(self, word):
        return self.relation_engine.get_synonyms(word)

    def get_antonyms(self, word):
        return self.relation_engine.get_antonyms(word)

    def get_used_for(self, word):
        return self.relation_engine.get_used_for(word)

    def get_causes(self, word):
        return self.relation_engine.get_causes(word)

    def get_instances(self, word):
        return self.relation_engine.get_instances(word)

    def get_properties(self, word):
        return self.relation_engine.get_properties(word)

    def get_all_relations(self, word):
        return self.relation_engine.get_all_relations(word)
        
    # Relation detectie
    def _detect_relation(self, text: str) -> bool:
        detected = self.parser.detect_relation(text)
        if not detected:
            return False

        parsed = self.parser.parse_relation(text, detected["pattern"])
        if not parsed:
            return False

        subject = parsed["subject"]
        obj = parsed["object"]

        # BUGFIX (25 juli 2026): voorkom dat losse vraagwoorden/
        # tussenwerpsels/functiewoorden ("lijkt", "oké", "wat", "hoe", ...)
        # als nieuw unknown/auto/0.1-concept in concepts.json belanden.
        # Dit gebeurde omdat elke niet-herkende chatzin door de relatie-
        # parser liep en toevallige patroonmatches (bv. " lijkt op ",
        # " zijn ", " is een ") in gewone zinnen als echte kennisrelatie
        # werden behandeld. De stopwoordencheck geldt ENKEL voor woorden
        # die nog geen bestaand concept zijn -- een bestaand concept
        # (ook al staat het toevallig in de stopwoordenlijst) wordt hier
        # nooit door geblokkeerd.
        # BUGFIX-VERVOLG (25 juli 2026): "bestaat al" moet betekenen dat
        # het woord een ECHTE, betekenisvolle sense heeft -- niet enkel
        # dat er al IETS in senses staat. Een woord met uitsluitend
        # unknown/auto/0.1-ruis (zoals 'echt' en 'warm' vóór deze fix)
        # telde voorheen ten onrechte als "bestaand", waardoor de
        # stopwoordencheck werd overgeslagen en de relatie alsnog werd
        # aangemaakt. Nu wordt enkel een sense met een echte definitie
        # (definition != "unknown") als geldig bestaand beschouwd.
        subject_bestaat_al = any(
            s.get("definition") != "unknown"
            for s in self.sense_engine.get_senses(subject)
        )
        object_bestaat_al = any(
            s.get("definition") != "unknown"
            for s in self.sense_engine.get_senses(obj)
        )

        if not subject_bestaat_al and self.parser.is_ruiswoord(subject):
            return False
        if not object_bestaat_al and self.parser.is_ruiswoord(obj):
            return False

        self.flow_engine.start_relation_flow(subject, detected["relation_type"], obj)
        return True

    # Confirm-flow
    def handle_confirm(self, user_input: str):
        self.flow_engine.handle_confirm(user_input)
    
    def handle_sense_choice(self, user_input: str):
        self.flow_engine.handle_sense_choice(user_input)

    # Teach event
    def _on_teach_event(self, data, event_type=None):
        word = (data.get("word") or "").strip()
        meaning = (data.get("meaning") or "").strip()
        if not word or not meaning:
            return
        self.teach(word, meaning)

    def _on_teach_pos(self, data, event_type=None):
        word = (data.get("word") or "").strip()
        pos = (data.get("pos") or "").strip()
        if not word or not pos:
            return

        concept = self.store.ensure_concept(word)
        senses = concept["senses"]

        if senses:
            senses[0]["pos"] = pos
        else:
            self.sense_engine.add_sense(word, "unknown", pos=pos, source="user", confidence=0.1)

        concept["metadata"]["updated_at"] = datetime.utcnow().isoformat()
        self.store.save()

    def _on_teach_example(self, data, event_type=None):
        word = (data.get("word") or "").strip().lower()
        sentence = (data.get("sentence") or "").strip()

        if not word or not sentence:
            self.event_bus.publish("chat_response", {
                "text": "Gebruik: example <woord> <voorbeeldzin>"
            })
            return

        concept = self.store.ensure_concept(word)
        senses = concept["senses"]

        if not senses:
            # Woord bestaat nog niet — maak een unknown sense aan
            self.sense_engine.add_sense(word, "unknown", pos=None, source="user", confidence=0.1)
            concept = self.store.get_concept(word)
            senses = concept["senses"]

        sense = senses[0]
        sense.setdefault("examples", [])

        if sentence in sense["examples"]:
            self.event_bus.publish("chat_response", {
                "text": f"Die voorbeeldzin ken ik al bij '{word}'."
            })
            return

        sense["examples"].append(sentence)
        concept["metadata"]["updated_at"] = datetime.utcnow().isoformat()
        self.store.save()

        self.event_bus.publish("chat_response", {
            "text": f"Voorbeeldzin toegevoegd bij '{word}': \"{sentence}\""
        })


def init_module(event_bus, memory_module=None):
    return SemanticConceptsModule(event_bus, memory_module)