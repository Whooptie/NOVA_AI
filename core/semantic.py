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
        with open(self.concepts_file, "w", encoding="utf-8") as f:
            json.dump(self.concepts, f, indent=2, ensure_ascii=False)

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
                old_conf = s.get("confidence", 0)
                if confidence > old_conf:
                    s["confidence"] = confidence
                    self._audit_sense(concept, s, "confidence_update", source,
                                      old_value=old_conf, new_value=confidence)
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

    def upgrade_unknown_sense(self, word: str, definition: str) -> dict | None:
        word = word.lower().strip()
        concept = self.store.get_concept(word)
        if not concept:
            return None

        for s in concept["senses"]:
            if s.get("definition") == "unknown":
                old_def = s["definition"]
                s["definition"] = definition
                s["source"] = "user"
                s["confidence"] = 1.0
                concept["metadata"]["updated_at"] = datetime.utcnow().isoformat()
                self._audit_sense(concept, s, "sense_upgrade", "user",
                                  old_value=old_def, new_value=definition)
                self.store.touch_concept(word, s.get("confidence"))
                self.store.save()
                return s
        return None

    def get_senses(self, word: str) -> list[dict]:
        concept = self.store.get_concept(word)
        if not concept:
            return []
        return concept.get("senses", [])

    def get_best_definition(self, word: str) -> str | None:
        senses = self.get_senses(word)
        real_senses = [s for s in senses if s.get("definition") != "unknown"]
        if not real_senses:
            return None
        best = max(real_senses, key=lambda s: s.get("confidence", 0))
        return best.get("definition")

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
            "komen", "blijven", "eten", "drinken", "schrijven", "lezen"
        }
        if w in infinitives:
            return "verb"

        if w.endswith("lijk") or w.endswith("ig") or w.endswith("isch"):
            return "adj"

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
            "created_at": datetime.utcnow().isoformat()
        }
        sense["relations"].append(rel_obj)

        concept["metadata"]["updated_at"] = datetime.utcnow().isoformat()
        self._audit_relation(concept, sense, rel_obj, event_type="relation_add")
        self.store.touch_concept(subject, sense.get("confidence"))
        self.store.save()
        return True

    def get_relations(self, word: str, relation_type: Optional[str] = None) -> List[str]:
        word = word.lower().strip()
        concept = self.store.get_concept(word)
        if not concept:
            return []

        results = []
        for sense in concept["senses"]:
            for rel in sense["relations"]:
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
            for rel in sense["relations"]:
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

    def teach(self, word: str, definition: str) -> dict:
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
                    event_type="example_add", source="user",
                    old_value=None, new_value=definition
                )
                self.store.touch_concept(word, concept["senses"][0].get("confidence"))
                self.store.save()
                return concept["senses"][0]

        # 3. unknown upgraden
        upgraded = self.sense_engine.upgrade_unknown_sense(word, definition)
        if upgraded:
            self._auto_extract_is_a(word, definition, upgraded)  # NIEUW
            return upgraded

        # 4. definitieve POS (na normalisatie)
        pos = self.sense_engine.detect_pos(word)

        sense = self.sense_engine.add_sense(
            word=word,
            definition=definition,
            source="user",
            confidence=1.0,
            pos=pos
        )
        self._auto_extract_is_a(word, definition, sense)  # NIEUW
        return sense

    def _auto_extract_is_a(self, word: str, definition: str, sense: dict) -> None:
        """
        Extraheert automatisch een is_a relatie uit een definitie.
        "een vrucht met een harde pit" → is_a: vrucht
        "een dier dat blaft"           → is_a: dier
        "een soort voertuig"           → is_a: voertuig
        """
        import re
        t = definition.lower().strip()
        stopwords = {"de", "het", "een", "ook", "wel", "niet", "van", "en", "of"}
        bijvoeglijk = {"groot", "klein", "lang", "breed", "hoog", "laag", "oud",
                       "nieuw", "goed", "slecht", "bekend", "veel", "weinig"}

        target = None

        # "een X met/die/dat/van/voor/uit..."
        m = re.match(r"een\s+(\w+)\s+(?:met|die|dat|van|voor|uit|waar|om)\b", t)
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
                "created_at": datetime.utcnow().isoformat()
            })
            self.store.save()

    def auto_learn(self, word: str) -> dict:
        word = word.lower().strip()

        pos_guess = self.sense_engine.detect_pos(word)
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
        self.flow_engine = RelationFlowEngine(
            self.store, self.sense_engine, self.relation_engine, event_bus
        )

        event_bus.subscribe("teach_concept", self._on_teach_event)
        event_bus.subscribe("teach_pos", self._on_teach_pos)
        event_bus.subscribe("teach_example", self._on_teach_example)
        event_bus.publish("module_loaded", {"name": "semantic"})

    # Publieke API
    def teach(self, word, definition):
        return self.teach_engine.teach(word, definition)

    def auto_learn(self, word):
        return self.teach_engine.auto_learn(word)

    def get_senses(self, word):
        return self.sense_engine.get_senses(word)

    def get_meaning(self, word):
        # 1. normaliseer meervoud → enkelvoud
        pos_guess = self.sense_engine.detect_pos(word)
        word = self.teach_engine._normalize_plural_if_noun(word, pos_guess)

        # 2. zoek definitie
        return self.sense_engine.get_best_definition(word)


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

    def explain_causes(self, source, target):
        return self.reasoning_engine.explain_causes(source, target)

    def find_contradictions(self, word):
        return self.reasoning_engine.find_contradictions(word)

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

        self.flow_engine.start_relation_flow(
            parsed["subject"],
            detected["relation_type"],
            parsed["object"]
        )
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