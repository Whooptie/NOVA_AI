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

        # Bug #8-fix, VIERDE ONDERDEEL (31 juli 2026): als de links-API-
        # fallback meerdere, evenwaardige kandidaten oplevert (bv.
        # "mercurius" -> planeet/element/mythologie/voetbalclub, zonder
        # dat er een duidelijke "hoofdbetekenis" is zoals bij fysica/
        # chemie), stelt Nova een genummerde keuzevraag i.p.v. blind de
        # eerste (willekeurige) match te pakken. Deze state onthoudt dat
        # er zo'n vraag open staat, tot het volgende bericht van Kevin.
        # Zelfde patroon als semantic.py's pending_relation/
        # RelationFlowEngine -- eigen, lichte state i.p.v. het generieke
        # pending_question-systeem, want dat laatste is bewust enkel
        # bedoeld voor ja/nee-achtige reacties (zie
        # pending_question_roadmap.md), niet voor een open meerkeuze.
        self._pending_wiki_choice = None

        # Luister naar wikipedia intents
        event_bus.subscribe("intent_wiki", self.on_wiki)
        event_bus.subscribe("intent_wiki_andere_betekenis", self.on_wiki_andere_betekenis)

        print("[WikiTeacher] Wikipedia AutoTeacher geladen")

    # ---------------------------------------------------------
    # 1. Ophalen van Wikipedia samenvatting
    # ---------------------------------------------------------
    def _fetch_summary(self, word: str) -> dict | None:
        """
        Haalt de Wikipedia samenvatting op voor een woord.
        Geeft None terug als het woord niet gevonden wordt.

        Bug #8-fix, DERDE ONDERDEEL (31 juli 2026): woord.capitalize()
        zet niet enkel de eerste letter om naar een hoofdletter, maar
        ALLE andere letters ook naar kleine letters. Bij een simpel
        eenwoords-begrip ("fysica" -> "Fysica") is dat toevallig
        onschadelijk, maar bij een titel die al correcte hoofdletters
        bevat middenin — zoals "CVV Mercurius" (een titel die via
        _extract_first_disambiguation_target()'s links-API-fallback kan
        binnenkomen) — vernielt .capitalize() de titel tot "Cvv
        mercurius", wat niet bestaat op Wikipedia. Gevonden via live
        testen: "wiki debug mercurius" leverde correct "CVV Mercurius"
        als alternatief, maar de daaropvolgende _fetch_summary()-aanroep
        faalde stil doordat de titel intern kapotgemaakt werd.

        Nieuwe aanpak: enkel de EERSTE letter met een hoofdletter, de
        rest van het woord blijft ongewijzigd — zo blijven titels als
        "CVV Mercurius" of "Bank (financiële instelling)" intact, en
        krijgt een kaal, kleine-letter-woord zoals "fysica" nog steeds
        gewoon zijn hoofdletter.
        """
        if word and word[0].islower():
            word = word[0].upper() + word[1:]

        encoded = urllib.parse.quote(word)
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
    def _teach_word(self, word: str, definition: str, relations: list, examples: list = None, voeg_toe: bool = False) -> str:
        examples = examples or []
        """
        Slaat het woord op via de SemanticConceptsModule.
        Geeft een status-bericht terug.

        voeg_toe (vervolgpunt uit bug #27, 31 juli 2026): als True,
        wordt een bestaande sense NOOIT overschreven en NOOIT geweigerd
        — er wordt altijd een NIEUWE, aanvullende sense aangemaakt,
        zelfs als er al een wikipedia- of user-sense bestaat. Gebruikt
        door on_wiki_andere_betekenis(), waar Kevin EXPLICIET om een
        bijkomende betekenis vraagt (bv. na "zijn er nog andere
        betekenissen" → "Mercurius (planeet)" kiezen terwijl er al een
        sense "Mercurius = Caduceus" bestaat). Het gewone pad (on_wiki(),
        voeg_toe=False) blijft ONGEWIJZIGD: overschrijft een bestaande
        wikipedia-sense, weigert bij een bestaande user-sense.
        """
        if not self.semantic:
            return "Semantic module niet beschikbaar."

        word = word.lower().strip()

        if not voeg_toe:
            # Bestaand gedrag, ongewijzigd: controleer of Nova het woord
            # al kent met een echte definitie
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

        # Definitie opslaan.
        #
        # Bij voeg_toe=True wordt BEWUST NIET teach_engine.teach() maar
        # rechtstreeks sense_engine.add_sense() gebruikt: teach()'s
        # eigen "unknown upgraden"-stap (zie semantic.py, TeachEngine.
        # teach() regel 809-813) zou anders een eventuele oude,
        # onafgemaakte unknown-sense stilzwijgend opvullen in plaats van
        # een écht NIEUWE, aanvullende sense aan te maken — precies wat
        # deze vlag net moet garanderen.
        try:
            if voeg_toe:
                nieuwe_sense = self.semantic.sense_engine.add_sense(
                    word=word,
                    definition=definition,
                    source="wikipedia",
                    confidence=WIKI_CONFIDENCE,
                    pos=None,
                )
                sense_id_voor_relaties = nieuwe_sense.get("sense_id")
                if examples:
                    nieuwe_sense["examples"] = examples
                    self.semantic.store.save()
            else:
                self.semantic.teach_engine.teach(
                    word=word,
                    definition=definition
                )
                sense_id_voor_relaties = None
                concept = self.semantic.store.get_concept(word)
                if concept and concept.get("senses"):
                    for sense in concept["senses"]:
                        if sense.get("definition") == definition:
                            sense["source"] = "wikipedia"
                            sense["confidence"] = WIKI_CONFIDENCE
                            if examples:
                                sense["examples"] = examples
                            sense_id_voor_relaties = sense.get("sense_id")
                    self.semantic.store.save()
        except Exception as e:
            return f"Fout bij opslaan van definitie: {e}"

        # Relaties opslaan
        #
        # Bugfix, meegenomen bij deze wijziging: de oude code pakte
        # altijd concept["senses"][0] (de EERSTE sense) om relaties aan
        # te hangen — bij meerdere senses (zoals nu met voeg_toe=True
        # mogelijk wordt) zou dat relaties van sense #2 ten onrechte op
        # sense #1 plakken. Nu wordt de sense opgezocht op basis van
        # sense_id_voor_relaties (de sense die we net daadwerkelijk
        # aangemaakt/bijgewerkt hebben), met een fallback naar de eerste
        # sense voor het geval sense_id_voor_relaties onbekend bleef.
        relaties_geleerd = []
        for rel in relations:
            try:
                concept = self.semantic.store.get_concept(word)
                if concept and concept.get("senses"):
                    sense = None
                    if sense_id_voor_relaties:
                        sense = next(
                            (s for s in concept["senses"] if s.get("sense_id") == sense_id_voor_relaties),
                            None
                        )
                    if sense is None:
                        sense = concept["senses"][0]

                    bestaande = [r["target"] for r in sense.get("relations", [])]
                    if rel["target"] not in bestaande:
                        sense.setdefault("relations", []).append(rel)
                        self.semantic.store.save()
                        relaties_geleerd.append(f"{rel['type']}: {rel['target']}")
            except Exception:
                pass

        # Samenvatting
        if voeg_toe:
            bericht = f"Nieuwe betekenis geleerd voor '{word}': {definition}"
        else:
            bericht = f"Wikipedia: '{word}' → {definition}"
        if relaties_geleerd:
            bericht += f" (relaties: {', '.join(relaties_geleerd)})"

        return bericht

    # ---------------------------------------------------------
    # 5. Hoofd-handler
    # ---------------------------------------------------------
    def _extract_first_disambiguation_target(self, extract: str, original_word: str) -> str | None:
        """
        Haalt het eerste zinvolle woord/begrip op uit een doorverwijspagina.
        Als de extract leeg is na de dubbele punt, probeer dan
        _fetch_disambiguation_links_via_api() (echte MediaWiki-links-API)
        als vangnet, en pas daarna de standaard suffixen.

        Bug #8-fix, TWEEDE ITERATIE (31 juli 2026): via 'wiki debug fysica'
        bleek dat Wikipedia's extract-veld de alternatieven met NEWLINES
        (\\n) scheidt, niet met komma's zoals de eerste fix aannam:
        'Fysica kan verwijzen naar:natuurkunde\\neen fysica, een leerboek
        over de fysica\\nFysica, ...'. Een komma BINNEN een regel ("een
        fysica, een leerboek over de fysica") hoort dus BIJ dat ene
        alternatief, en is geen scheiding tussen alternatieven — de
        vorige versie splitste per ongeluk op elke komma en kwam daardoor
        op 'fysica' uit i.p.v. 'natuurkunde'.

        Bijkomende ontdekking: bij sommige doorverwijspagina's (bv.
        "Mercurius kan verwijzen naar:", "Bank kan verwijzen naar:") geeft
        Wikipedia's REST-summary-API HELEMAAL GEEN lijst mee in extract —
        die tekst staat blijkbaar enkel in de HTML-pagina, niet in het
        platte-tekst-samenvattingsveld. Voor dat geval kan geen enkele
        tekst-parsing ooit iets opleveren (de data is er simpelweg niet),
        dus is een aparte, ECHTE API-aanroep toegevoegd
        (_fetch_disambiguation_links_via_api(), gebruikt MediaWiki's
        action=query&prop=links) die de daadwerkelijke doorverwijs-
        alternatieven ophaalt wanneer extract leeg blijkt.
        """
        # Alles na de dubbele punt
        if ":" in extract:
            rest = extract.split(":", 1)[1].strip()
        else:
            rest = extract.strip()

        if rest:
            # Alternatieven zijn met \n gescheiden (bevestigd via
            # 'wiki debug fysica'). Een komma BINNEN een regel is geen
            # scheiding tussen alternatieven, dus NIET op komma splitsen.
            regels = [r.strip() for r in rest.split("\n") if r.strip()]
            stopwoorden = {"een", "de", "het"}

            for regel in regels[:5]:
                # Bij een komma in de regel ("een fysica, een leerboek
                # over de fysica"): enkel het EERSTE deel vóór de komma
                # is het eigenlijke, korte alternatief — de rest is een
                # toelichting op datzelfde alternatief.
                eerste_deel = regel.split(",")[0].strip()

                woorden = [w.strip("().,;:'") for w in eerste_deel.split()]
                woorden = [w for w in woorden if w and w.lower() not in stopwoorden]

                if not woorden:
                    continue

                # Meer dan 2 woorden = omschrijving, geen los begrip
                if len(woorden) > 2:
                    continue

                if woorden[0][0].isupper():
                    kandidaat = woorden[0]
                else:
                    kandidaat = woorden[-1]

                if len(kandidaat) > 1:
                    return kandidaat

        # Extract leverde niets op (leeg, of enkel omschrijvingen). Let
        # op: de links-API-aanroep gebeurt HIER BEWUST NIET meer (was
        # een overblijfsel van een eerdere fix-versie) — die aanroep is
        # verplaatst naar on_wiki() zelf, want daar wordt ook gecheckt
        # of de links-API 1 of MEERDERE kandidaten teruggeeft. Stond hij
        # hier nog, dan zou 'alternatief' altijd al gevuld zijn zodra er
        # een link gevonden werd, en zou on_wiki()'s keuzevraag-logica
        # (bij >1 kandidaat) nooit bereikt worden — precies de bug die
        # bij het testen met "mercurius" opdook: geen enkele vraag
        # verscheen, want dit blok greep al in vóór on_wiki() de kans
        # kreeg zelf de links-API met meerdere kandidaten te proberen.

        # Enkel de generieke suffixen nog als laatste redmiddel op dit
        # niveau — puur voor het geval een simpel woord een vaste,
        # voorspelbare disambiguatie-suffix heeft (bv. "appel" ->
        # "appel_(vrucht)"), dit is een andere situatie dan de bredere
        # links-API-fallback in on_wiki().
        suffixen = ["_(vrucht)", "_(begrip)", "_(plant)", "_(stad)", "_(naam)", "_(muziek)"]
        for suffix in suffixen:
            candidate = original_word.capitalize() + suffix
            test = self._fetch_summary(candidate)
            if test and test.get("type") == "standard":
                return candidate

        return None

    def _fetch_disambiguation_links_via_api(self, word: str) -> str | None:
        """
        Vangnet voor doorverwijspagina's waar het extract-veld van de
        REST-summary-API leeg is (bv. "Mercurius kan verwijzen naar:",
        zonder lijst erachter — bevestigd via 'wiki debug mercurius').

        Geeft enkel de EERSTE bruikbare link terug — gebruikt wanneer
        er toch maar één plausibele optie is. Voor het geval er meerdere,
        evenwaardige kandidaten zijn, zie _fetch_disambiguation_links_meerdere().
        """
        kandidaten = self._fetch_disambiguation_links_meerdere(word, max_kandidaten=1)
        return kandidaten[0] if kandidaten else None

    def _fetch_disambiguation_links_meerdere(self, word: str, max_kandidaten: int = 4) -> list:
        """
        Roept MediaWiki's ECHTE action-API aan (action=query&prop=links,
        niet de REST-summary-API) om de daadwerkelijke lijst met pagina's
        op te vragen waar een doorverwijspagina naar linkt. Dit is de
        betrouwbare, structurele bron voor deze data wanneer het
        extract-veld leeg is — pure symbolische API-aanroep + parsing,
        geen ML/generatie.

        Geeft tot max_kandidaten bruikbare link-titels terug.

        Vervolgpunt uit bug #27 opgepakt (31 juli 2026): de oude versie
        kapte af zodra de eerste max_kandidaten links gevonden waren,
        in de volgorde waarin Wikipedia ze toevallig vermeldt — bij
        "mercurius" bleken de eerste 4 links (CVV Mercurius, Caduceus,
        twee tijdschriften) allemaal weinig relevant, terwijl
        "Mercurius (planeet)"/"(element)"/"(mythologie)" WEL bestaan
        maar verderop in de lijst stonden en zo nooit als keuze-optie
        te zien waren.

        Nieuwe aanpak: EERST alle bruikbare links verzamelen (geen
        vroege afkap meer tijdens het verzamelen — de API zelf levert
        al max. pllimit=20 links, dat blijft de enige harde grens),
        DAARNA sorteren zodat titels met een haakjes-suffix
        ("Mercurius (planeet)") vooraan komen te staan en titels zonder
        haakjes ("CVV Mercurius") achteraan, en PAS DAN tot
        max_kandidaten afkappen. Binnen elke van de twee groepen blijft
        Wikipedia's eigen volgorde behouden (geen willekeurige
        her-sortering).

        Dit is een simpele, structurele heuristiek (haakjes aanwezig
        ja/nee) — GEEN inhoudelijk begrip van welke betekenis het
        "belangrijkst" is. Een titel zonder haakjes kan best de
        bedoelde betekenis zijn; die staat dan gewoon verderop in de
        keuzelijst in plaats van vooraan.
        """
        params = {
            "action": "query",
            "format": "json",
            "titles": word.capitalize(),
            "prop": "links",
            "pllimit": "20",
            "plnamespace": "0",  # enkel echte artikelen, geen Wikipedia:/Categorie:/...
        }
        url = "https://nl.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Nova-AI/1.0 (educational project)"}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception:
            return []

        pages = data.get("query", {}).get("pages", {})
        meta_namespaces = ("Wikipedia", "Categorie", "Help", "Overleg", "Sjabloon", "Portaal")
        alle_kandidaten = []

        for page in pages.values():
            for link in page.get("links", []):
                titel = link.get("title", "").strip()
                if not titel:
                    continue
                # Meta-pagina's overslaan
                if ":" in titel and titel.split(":", 1)[0] in meta_namespaces:
                    continue
                # Niet de doorverwijspagina zelf teruggeven
                if titel.lower() == word.lower():
                    continue
                if titel not in alle_kandidaten:
                    alle_kandidaten.append(titel)
                # Geen vroege 'return' meer hier — eerst ALLES verzamelen,
                # zodat de sortering hieronder ook titels verderop in de
                # lijst kan meenemen.

        # Sorteren: titels MET haakjes-suffix ("Mercurius (planeet)")
        # eerst, titels ZONDER haakjes ("CVV Mercurius") daarna.
        met_haakjes = [k for k in alle_kandidaten if "(" in k and ")" in k]
        zonder_haakjes = [k for k in alle_kandidaten if not ("(" in k and ")" in k)]
        gesorteerd = met_haakjes + zonder_haakjes

        return gesorteerd[:max_kandidaten]

    def _haal_bestaande_definities_op(self, word: str) -> list:
        """
        Verzamelt alle bestaande definitieteksten van een woord (over
        al zijn senses heen in concepts.json), om te kunnen checken
        welke Wikipedia-kandidaten Nova eigenlijk al kent.

        Bugfix bij live-testen (31 juli 2026): eerste versie gebruikte
        self.semantic.concepts rechtstreeks, wat een AttributeError gaf
        -- SemanticConceptsModule heeft zelf geen .concepts-attribuut,
        dat zit enkel op de onderliggende ConceptStore-klasse. De
        JUISTE, al bestaande API (zelfde patroon als _teach_word()
        hierboven al gebruikt op regel 258) is export_concept(), een
        facade-methode op SemanticConceptsModule die intern doorverwijst
        naar self.store.export_concept().
        """
        if not self.semantic:
            return []
        entry = self.semantic.export_concept(word.lower())
        if not entry:
            return []
        senses = entry.get("senses", [])
        return [s.get("definition", "") for s in senses if s.get("definition")]

    def _combineer_kandidaten(self, tekst_kandidaten: list, links_kandidaten: list, max_totaal: int = 20) -> list:
        """
        Combineert REST-tekst-kandidaten (kort/betekenisvol, bv.
        "natuurkunde") met links-API-kandidaten (volledige
        artikeltitels, bv. "Mercurius (planeet)") tot één
        gededupliceerde lijst.

        Dedup-regel: een titel MET haakjes-suffix wordt op zijn VOLLEDIGE
        tekst gededupliceerd (elke haakjes-variant is een apart begrip
        — "Mercurius (planeet)" ≠ "Mercurius (element)"). Een titel
        ZONDER haakjes wordt op het kale, kleine-letter-woord
        gededupliceerd (dekt hoofdletter-varianten van hetzelfde losse
        begrip, "fysicus" == "Fysicus").
        """
        resultaat = []
        gezien = set()
        for titel in tekst_kandidaten + links_kandidaten:
            sleutel = titel.strip().lower()
            if sleutel not in gezien:
                resultaat.append(titel)
                gezien.add(sleutel)
        return resultaat[:max_totaal]

    def _filter_reeds_gekende_kandidaten(self, kandidaten: list, bestaande_definities: list, original_word: str) -> list:
        """
        Sluit kandidaten uit waarvan de kernbetekenis al voorkomt in
        een bestaande definitie van hetzelfde woord — voorkomt dat
        Nova een betekenis aanbiedt die ze al kent.

        Speciaal geval: als de kandidaat-titel toevallig hetzelfde
        (kale) woord is als original_word zelf (bv. "Fysica (boek van
        Aristoteles)" of "Mercurius (planeet)" bij het opzoeken van
        "fysica"/"mercurius"), is enkel op de kale titel vergelijken
        zinloos — original_word komt vrijwel altijd letterlijk in zijn
        eigen bestaande definitie voor ("Natuurkunde of fysica is...",
        "Mercurius is de planeet..."), dat zegt op zich niets over of
        de SPECIFIEKE haakjes-variant al gekend is.

        Bugfix bij live-testen (31 juli 2026): de eerste versie
        vergeleek in dat geval de VOLLEDIGE titel MET haakjes
        ("mercurius (planeet)") tegen de definitietekst — die exacte
        combinatie staat vrijwel nooit letterlijk zo (met haakjes) in
        een lopende zin, waardoor "Mercurius (planeet)" bij het woord
        "mercurius" ten onrechte NIET gefilterd werd, ook al was de
        bestaande definitie letterlijk "Mercurius is de planeet...".
        Nieuwe aanpak: enkel de HAAKJES-INHOUD zelf ("planeet") wordt
        als los woord vergeleken, niet de titel als geheel.
        """
        gefilterd = []
        for kandidaat in kandidaten:
            kale_titel = kandidaat.split("(")[0].strip().lower()

            if kale_titel == original_word.lower():
                if "(" in kandidaat and ")" in kandidaat:
                    haakjes_inhoud = kandidaat.split("(", 1)[1].rsplit(")", 1)[0].strip().lower()
                    vergelijk_tekst = haakjes_inhoud if haakjes_inhoud else kandidaat.lower()
                else:
                    vergelijk_tekst = kandidaat.lower()
            else:
                vergelijk_tekst = kale_titel

            al_gekend = any(
                vergelijk_tekst in definitie.lower()
                for definitie in bestaande_definities
            )
            if not al_gekend:
                gefilterd.append(kandidaat)
        return gefilterd

    def on_wiki_andere_betekenis(self, data, event_type=None):
        """
        Afhandeling van "zijn er nog andere betekenissen" (vervolgpunt
        uit bug #27, 31 juli 2026). In tegenstelling tot on_wiki()
        (die stopt zodra er ÉÉN goede kandidaat is) verzamelt deze
        methode BEIDE bronnen (REST-tekst-extractie + links-API),
        combineert en sorteert ze, sluit kandidaten uit die al gedekt
        zijn door een bestaande sense, en toont het resultaat als een
        genummerde keuzevraag — ook als er maar 1 nieuwe optie over is,
        want hier vraagt Kevin EXPLICIET om alternatieven, dus is een
        vraag altijd op zijn plek (in tegenstelling tot on_wiki()'s
        automatische pad).
        """
        word = (data.get("word") or "").strip().lower()
        if not word:
            self.event_bus.publish("chat_response", {
                "text": "Welk woord bedoel je?"
            })
            return

        summary = self._fetch_summary(word)
        if not summary:
            summary = self._fetch_summary(word.capitalize())

        tekst_kandidaten = []
        if summary and summary.get("type") == "disambiguation":
            extract = summary.get("extract", "")
            # Hergebruikt dezelfde parsing-stap als
            # _extract_first_disambiguation_target(), maar verzamelt
            # ALLE bruikbare regels i.p.v. na de eerste te stoppen.
            if ":" in extract:
                rest = extract.split(":", 1)[1].strip()
            else:
                rest = extract.strip()
            if rest:
                regels = [r.strip() for r in rest.split("\n") if r.strip()]
                stopwoorden = {"een", "de", "het"}
                gezien_lower = set()
                for regel in regels:
                    eerste_deel = regel.split(",")[0].strip()
                    woorden = [w.strip("().,;:'") for w in eerste_deel.split()]
                    woorden = [w for w in woorden if w and w.lower() not in stopwoorden]
                    if not woorden or len(woorden) > 2:
                        continue
                    kandidaat = woorden[0] if woorden[0][0].isupper() else woorden[-1]
                    if kandidaat.lower() == word.lower():
                        continue
                    if kandidaat.lower() in gezien_lower:
                        continue
                    if len(kandidaat) > 1:
                        tekst_kandidaten.append(kandidaat)
                        gezien_lower.add(kandidaat.lower())

        links_kandidaten = self._fetch_disambiguation_links_meerdere(word, max_kandidaten=10)

        gecombineerd = self._combineer_kandidaten(tekst_kandidaten, links_kandidaten)

        bestaande_definities = self._haal_bestaande_definities_op(word)
        gefilterd = self._filter_reeds_gekende_kandidaten(gecombineerd, bestaande_definities, word)

        # Haakjes-varianten vooraan, zelfde heuristiek als
        # _fetch_disambiguation_links_meerdere() al gebruikt.
        met_haakjes = [k for k in gefilterd if "(" in k and ")" in k]
        zonder_haakjes = [k for k in gefilterd if not ("(" in k and ")" in k)]
        kandidaten = (met_haakjes + zonder_haakjes)[:6]

        if not kandidaten:
            self.event_bus.publish("chat_response", {
                "text": f"Ik ken voor '{word}' geen andere betekenissen dan wat ik al weet."
            })
            return

        if len(kandidaten) == 1:
            # Ook bij 1 resultaat toch een korte bevestigingsvraag,
            # want dit pad is EXPLICIET aangevraagd door Kevin — geen
            # automatische keuze zoals in on_wiki().
            self._pending_wiki_choice = {"woord": word, "kandidaten": kandidaten, "voeg_toe": True}
            self.event_bus.publish("chat_response", {
                "text": f"Ik vond nog 1 andere betekenis voor '{word}': {kandidaten[0]}. "
                        f"Typ '1' als je die wil leren, of iets anders om te annuleren."
            })
            return

        self._pending_wiki_choice = {"woord": word, "kandidaten": kandidaten, "voeg_toe": True}
        vraag = f"Nog andere betekenissen van '{word}':\n"
        for i, k in enumerate(kandidaten, start=1):
            vraag += f"  {i}. {k}\n"
        vraag += "Typ het nummer als je die wil leren, of iets anders om te annuleren."
        self.event_bus.publish("chat_response", {"text": vraag})

    def verwerk_wiki_keuze(self, tekst: str) -> bool:
        """
        Checkt of er een openstaande meerkeuzevraag is (gezet door
        on_wiki() hieronder) en of 'tekst' daar een geldig genummerd
        antwoord op is. Geeft True terug als dit bericht als keuze-
        antwoord verwerkt is (de aanroeper moet dan stoppen met verdere
        routing), False als er niets open stond of het geen geldig
        nummer was (dan gaat de tekst gewoon door de normale flow).

        Moet door intent_router.py's route() VÓÓR de bestaande
        text.isdigit()-sense-choice gecontroleerd worden, anders vangt
        semantic.py's eigen sense-choice-systeem het nummer al af.
        """
        if not self._pending_wiki_choice:
            return False

        tekst = tekst.strip()
        kandidaten = self._pending_wiki_choice["kandidaten"]
        oorspronkelijk_woord = self._pending_wiki_choice["woord"]

        if not tekst.isdigit():
            # Geen geldig nummer -> vraag laten vervallen, normaal doorgaan
            self._pending_wiki_choice = None
            return False

        idx = int(tekst) - 1
        if not (0 <= idx < len(kandidaten)):
            # Nummer buiten bereik -> vraag laten vervallen
            self._pending_wiki_choice = None
            self.event_bus.publish("chat_response", {
                "text": f"Dat nummer kende ik niet, ik laat de vraag varen. "
                        f"Probeer opnieuw met 'wiki {oorspronkelijk_woord}'."
            })
            return True

        gekozen = kandidaten[idx]
        voeg_toe = self._pending_wiki_choice.get("voeg_toe", False)
        self._pending_wiki_choice = None
        self._verwerk_gekozen_pagina(oorspronkelijk_woord, gekozen, voeg_toe=voeg_toe)
        return True

    def _verwerk_gekozen_pagina(self, oorspronkelijk_woord: str, gekozen_titel: str, voeg_toe: bool = False):
        """
        Haalt de samenvatting op van de door Kevin gekozen disambiguatie-
        optie en rondt de volledige teach-flow af (definitie/relaties/
        voorbeelden opslaan). Losgetrokken uit on_wiki() zodat zowel het
        automatische 1-kandidaat-pad als het na-een-keuzevraag-pad
        dezelfde afrondingslogica hergebruiken.

        voeg_toe wordt doorgegeven aan _teach_word(): True wanneer dit
        een EXPLICIETE "andere betekenis"-keuze is (via
        on_wiki_andere_betekenis()) — dan wordt altijd een nieuwe,
        aanvullende sense aangemaakt i.p.v. een bestaande te
        overschrijven of te weigeren.
        """
        summary = self._fetch_summary(gekozen_titel)
        if not summary or summary.get("type") == "disambiguation":
            self.event_bus.publish("chat_response", {
                "text": f"Ik kon geen bruikbare definitie vinden voor "
                        f"'{gekozen_titel}' op Wikipedia. "
                        f"Leer het me met: teach {oorspronkelijk_woord} <betekenis>"
            })
            return

        definition = self._extract_definition(summary)
        if not definition:
            self.event_bus.publish("chat_response", {
                "text": f"Ik kon geen bruikbare definitie vinden voor "
                        f"'{gekozen_titel}' op Wikipedia. "
                        f"Leer het me met: teach {oorspronkelijk_woord} <betekenis>"
            })
            return

        relations = self._extract_relations(oorspronkelijk_woord, definition)
        examples = self._extract_examples(oorspronkelijk_woord, summary, definition)
        resultaat = self._teach_word(oorspronkelijk_woord, definition, relations, examples, voeg_toe=voeg_toe)

        self.event_bus.publish("chat_response", {
            "text": resultaat
        })

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

            # Eerst de bestaande, geteste tekst-extractie proberen (werkt
            # al correct voor fysica/chemie/bank — blijft ONGEWIJZIGD,
            # geeft altijd maar 1 resultaat terug, want de tekst zelf
            # geeft meestal al een duidelijke "hoofdbetekenis" als eerste
            # regel).
            alternatief = self._extract_first_disambiguation_target(extract, word)

            if alternatief:
                summary2 = self._fetch_summary(alternatief)
                if summary2 and summary2.get("type") != "disambiguation":
                    summary = summary2
                else:
                    summary = None
            else:
                # Tekst-extractie leverde niets op (leeg extract-veld,
                # zoals bij "mercurius"/"bank" — bevestigd via
                # 'wiki debug'). Nieuw vangnet (31 juli 2026): de
                # links-API kan meerdere, EVENWAARDIGE kandidaten
                # opleveren zonder duidelijke volgorde (in tegenstelling
                # tot de tekst-extractie hierboven). Bij >1 kandidaat
                # stellen we daarom een keuzevraag i.p.v. blind de eerste
                # (mogelijk irrelevante) link te pakken.
                kandidaten = self._fetch_disambiguation_links_meerdere(word)

                if len(kandidaten) == 0:
                    summary = None
                elif len(kandidaten) == 1:
                    # Geen ambiguïteit in de praktijk -> gewoon doorgaan,
                    # net als het bestaande 1-alternatief-pad hierboven.
                    summary2 = self._fetch_summary(kandidaten[0])
                    summary = summary2 if summary2 and summary2.get("type") != "disambiguation" else None
                else:
                    # Meerdere evenwaardige kandidaten -> keuzevraag stellen.
                    # GEEN definities/beschrijvingen erbij (zou de vraag
                    # te lang maken voor Nova's typewriter-effect) — enkel
                    # de titels, kort en scanbaar.
                    self._pending_wiki_choice = {"woord": word, "kandidaten": kandidaten}
                    vraag = f"'{word}' kan meerdere dingen betekenen. Welke bedoel je?\n"
                    for i, k in enumerate(kandidaten, start=1):
                        vraag += f"  {i}. {k}\n"
                    vraag += "Typ het nummer van je keuze."
                    self.event_bus.publish("chat_response", {"text": vraag})
                    return

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