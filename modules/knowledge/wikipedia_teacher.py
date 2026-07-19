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
        Haalt de eerste volledige zin (of eerste twee zinnen) op uit de
        Wikipedia samenvatting. Kapt nooit midden in een woord af.
        """
        extract = summary_data.get("extract", "")
        if not extract:
            return None

        MAX_LENGTH = 400  # opgetrokken van 200 naar 400

        # Zinnen opsplitsen
        sentences = re.split(r'(?<=[.!?])\s+', extract.strip())
        if not sentences:
            return None

        first = sentences[0].strip()

        # Doorverwijspagina detecteren
        if "kan verwijzen naar" in first or "kan ook verwijzen" in first:
            return None

        # Probeer de tweede zin erbij te nemen als er nog ruimte is
        definitie = first
        if len(sentences) > 1:
            kandidaat = first + " " + sentences[1].strip()
            if len(kandidaat) <= MAX_LENGTH:
                definitie = kandidaat

        # Als de definitie nog steeds te lang is, kap dan af op de laatste
        # volledige zin die binnen de limiet past — nooit midden in een woord
        if len(definitie) > MAX_LENGTH:
            afgekapt = definitie[:MAX_LENGTH]
            laatste_punt = afgekapt.rfind(". ")
            if laatste_punt > 0:
                definitie = afgekapt[:laatste_punt + 1]
            else:
                # Geen volledige zin gevonden binnen de limiet →
                # kap af op het laatste hele woord, geen "..." meer nodig
                laatste_spatie = afgekapt.rfind(" ")
                if laatste_spatie > 0:
                    definitie = afgekapt[:laatste_spatie] + "."
                else:
                    definitie = afgekapt

        return definitie.strip()

    # ---------------------------------------------------------
    # 2B. Voorbeeldzinnen extraheren uit Wikipedia tekst
    # ---------------------------------------------------------
    def _extract_examples(self, word: str, summary_data: dict, definitie: str) -> list:
        """
        Haalt extra zinnen uit de Wikipedia-extract die het woord bevatten
        en niet al gebruikt zijn in de definitie. Puur symbolisch:
        geen generatie, enkel bestaande Wikipedia-tekst hergebruiken.
        """
        extract = summary_data.get("extract", "")
        if not extract:
            return []

        w = word.lower()
        zinnen = re.split(r'(?<=[.!?])\s+', extract.strip())

        voorbeelden = []
        for zin in zinnen:
            zin = zin.strip()
            if not zin:
                continue
            # Sla zinnen over die al in de definitie zitten
            if zin in definitie:
                continue
            # Alleen zinnen die het woord zelf bevatten zijn nuttig als voorbeeld
            if w not in zin.lower():
                continue
            # Te lange zinnen zijn onhandig als voorbeeld
            if len(zin) > 250:
                continue
            voorbeelden.append(zin)
            if len(voorbeelden) >= 2:  # max 2 voorbeeldzinnen
                break

        return voorbeelden

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
    def _teach_word(self, word: str, definition: str, relations: list, examples: list = None) -> str:
        examples = examples or []
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

            # Bestaande Wikipedia-sense overschrijven i.p.v. dupliceren
            for sense in existing.get("senses", []):
                if sense.get("source") == "wikipedia":
                    concept = self.semantic.store.get_concept(word)
                    for s in concept["senses"]:
                        if s.get("sense_id") == sense.get("sense_id"):
                            s["definition"] = definition
                            s["confidence"] = WIKI_CONFIDENCE
                            s["relations"] = relations if relations else s.get("relations", [])
                            s["examples"] = examples if examples else s.get("examples", [])
                            concept["metadata"]["updated_at"] = datetime.utcnow().isoformat()
                    self.semantic.store.save()
                    return f"Wikipedia-definitie van '{word}' bijgewerkt → {definition}"

        # Definitie opslaan via teach_engine
        try:
            self.semantic.teach_engine.teach(
                word=word,
                definition=definition
            )
            # Source corrigeren naar wikipedia + voorbeeldzinnen toevoegen
            concept = self.semantic.store.get_concept(word)
            if concept and concept.get("senses"):
                for sense in concept["senses"]:
                    if sense.get("definition") == definition:
                        sense["source"] = "wikipedia"
                        sense["confidence"] = WIKI_CONFIDENCE
                        if examples:
                            sense["examples"] = examples
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
        # Bugfix #6 (18 juli 2026): defensief vangnet. chat.py stript
        # nu zelf al leestekens vóór dit event gepubliceerd wordt (zie
        # on_definition()), maar deze strip staat hier ALSNOG bij —
        # mocht een andere module ooit rechtstreeks een "intent_wiki"-
        # event sturen zonder via chat.py te lopen, dan blijft dit
        # bestand toch veilig, zonder van chat.py's interne volgorde
        # afhankelijk te zijn.
        word = (data.get("word") or "").strip().lower().strip(".,!?;:")
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

        # 4B. Voorbeeldzinnen extraheren
        examples = self._extract_examples(word, summary, definition)

        # 5. Opslaan
        resultaat = self._teach_word(word, definition, relations, examples)

        # 6. Antwoord tonen
        self.event_bus.publish("chat_response", {
            "text": resultaat
        })


def init_module(event_bus, semantic_module=None):
    teacher = WikipediaTeacher(event_bus, semantic_module)
    event_bus.publish("module_loaded", {"name": "wikipedia_teacher"})
    return teacher