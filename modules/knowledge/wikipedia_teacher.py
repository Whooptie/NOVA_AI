# modules/knowledge/wikipedia_teacher.py
#
# Fase 6 — Wikipedia AutoTeacher
#
# Wat dit doet:
#   - Zoekt een woord op via de Nederlandse Wikipedia API
#   - Haalt de eerste zin op als definitie
#   - Extraheert is_a relaties uit de eerste zin
#   - Slaat alles op in Nova's woordenbrein (concepts.json)
#   - Confidence van Wikipedia = 0.8 (lager dan user = 1.0, hoger dan auto = 0.1)
#
# Commando's in chat:
#   "wiki appel"
#   "leer wikipedia appel"
#   "zoek op appel"

import re
import json
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime

# Wikipedia API instellingen
WIKI_API = "https://nl.wikipedia.org/api/rest_v1/page/summary/"
WIKI_CONFIDENCE = 0.8  # Wikipedia is betrouwbaar maar niet perfect


class WikipediaTeacher:
    def __init__(self, event_bus, semantic_module=None):
        self.event_bus = event_bus
        self.semantic = semantic_module

        # Luister naar wikipedia intents
        event_bus.subscribe("intent_wiki", self.on_wiki)

        print("[WikiTeacher] Wikipedia AutoTeacher geladen")

    # ---------------------------------------------------------
    # 1. Ophalen van Wikipedia samenvatting
    # ---------------------------------------------------------
    def _fetch_summary(self, word: str) -> dict | None:
        """
        Haalt de Wikipedia samenvatting op voor een woord.
        Geeft None terug als het woord niet gevonden wordt.
        """
        encoded = urllib.parse.quote(word.capitalize())
        url = WIKI_API + encoded

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Nova-AI/1.0 (educational project)"}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None  # Woord niet gevonden
            return None
        except Exception:
            return None

    # ---------------------------------------------------------
    # 2. Definitie extraheren uit Wikipedia tekst
    # ---------------------------------------------------------
    def _extract_definition(self, summary_data: dict) -> str | None:
        """
        Haalt de eerste zin op uit de Wikipedia samenvatting.
        """
        extract = summary_data.get("extract", "")
        if not extract:
            return None

        # Eerste zin ophalen (alles tot de eerste punt + spatie of einde)
        sentences = re.split(r'(?<=[.!?])\s+', extract.strip())
        if sentences:
            first = sentences[0].strip()
            # Doorverwijspagina detecteren
            if "kan verwijzen naar" in first or "kan ook verwijzen" in first:
                return None
            # Maximaal 200 tekens — langere definities zijn niet bruikbaar
            if len(first) > 200:
                first = first[:197] + "..."
            return first

        return None

    # ---------------------------------------------------------
    # 3. is_a relaties extraheren uit de definitie
    # ---------------------------------------------------------
    def _extract_relations(self, word: str, definition: str) -> list:
        """
        Probeert is_a relaties te vinden in de definitie.
        Symbolisch: puur op patroonherkenning.

        Voorbeelden:
          "Een appel is een vrucht" → is_a: vrucht
          "Een hond is een zoogdier" → is_a: zoogdier
        """
        relations = []
        t = definition.lower()
        w = word.lower()

        # Specifieke patronen — van specifiek naar algemeen
        patterns = [
            # "X is een Y met/uit/van/die/dat/voor..." → Y
            (rf"{w} is een (\w+)(?:\s+(?:met|uit|van|die|dat|voor)\b)", 1),
            (rf"een {w} is een (\w+)(?:\s+(?:met|uit|van|die|dat|voor)\b)", 1),
            # "de X is de/een Y van/met/uit..." → Y
            (rf"de {w} is (?:de |een )(\w+)(?:\s+(?:van|met|uit|die|dat)\b)", 1),
            # "X is een soort/type/variant/ondersoort van Y"
            (rf"{w} is een (?:soort|type|variant|ondersoort) van (?:de |het )?(\w+)", 1),
            # "X behoort tot de Y"
            (rf"{w} behoort tot (?:de |het )(\w+)", 1),
            # "de X is de Y" — zonder extra woorden
            (rf"de {w} is de (\w+)", 1),
            # "X is een Y" — simpelste patroon als laatste
            (rf"{w} is een (\w+)", 1),
        ]

        bijvoeglijk = {"groot", "klein", "lang", "breed", "hoog", "laag", "oud",
                       "nieuw", "goed", "slecht", "bekend", "veel", "weinig"}

        for pattern, group in patterns:
            m = re.search(pattern, t)
            if m:
                try:
                    target = m.group(group).strip().rstrip(".,;")
                except IndexError:
                    continue
                stopwords = {"de", "het", "een", "ook", "wel", "niet", "van", "en", "of"}
                if target and target not in stopwords and target not in bijvoeglijk and len(target) > 2:
                    relations.append({
                        "type": "is_a",
                        "target": target,
                        "confidence": WIKI_CONFIDENCE,
                        "source": "wikipedia",
                        "created_at": datetime.utcnow().isoformat()
                    })
                    break

        return relations

    # ---------------------------------------------------------
    # 4. Alles opslaan in Nova's woordenbrein
    # ---------------------------------------------------------
    def _teach_word(self, word: str, definition: str, relations: list) -> str:
        """
        Slaat het woord op via de SemanticConceptsModule.
        Geeft een status-bericht terug.
        """
        if not self.semantic:
            return "Semantic module niet beschikbaar."

        word = word.lower().strip()

        # Controleer of Nova het woord al kent met een echte definitie
        existing = self.semantic.export_concept(word)
        if existing:
            for sense in existing.get("senses", []):
                if sense.get("definition", "unknown") != "unknown" and \
                   sense.get("source") == "user":
                    return f"Ik ken '{word}' al van jou — Wikipedia overschrijft dat niet."

        # Definitie opslaan via teach_engine
        try:
            self.semantic.teach_engine.teach(
                word=word,
                definition=definition
            )
            # Source corrigeren naar wikipedia
            concept = self.semantic.store.get_concept(word)
            if concept and concept.get("senses"):
                for sense in concept["senses"]:
                    if sense.get("definition") == definition:
                        sense["source"] = "wikipedia"
                        sense["confidence"] = WIKI_CONFIDENCE
                self.semantic.store.save()
        except Exception as e:
            return f"Fout bij opslaan van definitie: {e}"

        # Relaties opslaan
        relaties_geleerd = []
        for rel in relations:
            try:
                concept = self.semantic.store.get_concept(word)
                if concept and concept.get("senses"):
                    sense = concept["senses"][0]
                    sense_id = sense["sense_id"]

                    # Deduplicatie check
                    bestaande = [r["target"] for r in sense.get("relations", [])]
                    if rel["target"] not in bestaande:
                        sense.setdefault("relations", []).append(rel)
                        self.semantic.store.save()
                        relaties_geleerd.append(f"{rel['type']}: {rel['target']}")
            except Exception:
                pass

        # Samenvatting
        bericht = f"Wikipedia: '{word}' → {definition}"
        if relaties_geleerd:
            bericht += f" (relaties: {', '.join(relaties_geleerd)})"

        return bericht

    # ---------------------------------------------------------
    # 5. Hoofd-handler
    # ---------------------------------------------------------
    def _extract_first_disambiguation_target(self, extract: str, original_word: str) -> str | None:
        """
        Haalt het eerste zinvolle woord op uit een doorverwijspagina.
        Als de extract leeg is na de dubbele punt, probeer dan standaard suffixen.
        """
        # Alles na de dubbele punt
        if ":" in extract:
            rest = extract.split(":", 1)[1].strip()
        else:
            rest = extract.strip()

        # Eerste woord met hoofdletter proberen
        m = re.match(r"([A-Z][a-zäëïöüA-Z\-]+(?:\s[a-z]+)?)", rest)
        if m:
            return m.group(1).strip()

        # Niets gevonden → generieke suffixen proberen
        suffixen = ["_(vrucht)", "_(begrip)", "_(plant)", "_(stad)", "_(naam)", "_(muziek)"]
        for suffix in suffixen:
            candidate = original_word.capitalize() + suffix
            test = self._fetch_summary(candidate)
            if test and test.get("type") == "standard":
                return candidate

        return None

    def on_wiki(self, data, event_type=None):
        word = (data.get("word") or "").strip().lower()
        auto = data.get("auto", False)

        if not word:
            self.event_bus.publish("chat_response", {
                "text": "Welk woord wil je opzoeken op Wikipedia?"
            })
            return

        # Feedback: Nova is aan het zoeken
        self.event_bus.publish("chat_response", {
            "text": f"Even zoeken op Wikipedia voor '{word}'..."
        })

        # 1. Wikipedia ophalen
        summary = self._fetch_summary(word)
        if not summary:
            summary = self._fetch_summary(word.capitalize())

        if not summary:
            self.event_bus.publish("chat_response", {
                "text": f"Ik kon '{word}' niet vinden op Wikipedia."
                if not auto else
                f"Ik ken '{word}' nog niet. Leer het me met: teach {word} <betekenis>"
            })
            return

        # 2. Doorverwijspagina afhandelen
        if summary.get("type") == "disambiguation":
            extract = summary.get("extract", "")
            alternatief = self._extract_first_disambiguation_target(extract, word)
            if alternatief:
                summary2 = self._fetch_summary(alternatief)
                if summary2 and summary2.get("type") != "disambiguation":
                    summary = summary2
                else:
                    summary = None
            else:
                summary = None

        if not summary:
            self.event_bus.publish("chat_response", {
                "text": f"Ik kon geen bruikbare definitie vinden voor '{word}' op Wikipedia. "
                        f"Leer het me met: teach {word} <betekenis>"
            })
            return

        # 3. Definitie extraheren
        definition = self._extract_definition(summary)

        if not definition:
            self.event_bus.publish("chat_response", {
                "text": f"Ik kon geen bruikbare definitie vinden voor '{word}' op Wikipedia. "
                        f"Leer het me met: teach {word} <betekenis>"
            })
            return

        # 4. Relaties extraheren
        relations = self._extract_relations(word, definition)

        # 5. Opslaan
        resultaat = self._teach_word(word, definition, relations)

        # 6. Antwoord tonen
        self.event_bus.publish("chat_response", {
            "text": resultaat
        })


def init_module(event_bus, semantic_module=None):
    teacher = WikipediaTeacher(event_bus, semantic_module)
    event_bus.publish("module_loaded", {"name": "wikipedia_teacher"})
    return teacher