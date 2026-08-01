# modules/knowledge/concept_overview.py
"""
Concept Overview — "wat weet je allemaal over X"

Geeft een kort, scanbaar overzicht van ALLES wat Nova al over een woord
weet (uit concepts.json, via SemanticConceptsModule.export_concept()):
alle senses, met per sense een telling van relaties/voorbeelden. Op
vraag (typ 'ja', of het nummer van een specifieke betekenis) volgt de
volledige uitsplitsing: relaties gegroepeerd per type, voorbeeldzinnen,
bron en zekerheid.

Puur symbolisch: leest enkel bestaande data uit concepts.json via de
al bestaande export_concept()-API, geen Wikipedia-aanroep, geen ML,
geen generatie. Bouwt voort op hetzelfde ontwerp als de "zijn er nog
andere betekenissen"-flow in wikipedia_teacher.py (bug #27-vervolg):
een kort antwoord met een pending-vraag voor wie meer detail wil, om
Nova's typewriter-effect niet te overladen met één lange boodschap.

Gebouwd: 1 augustus 2026.
"""


class ConceptOverview:
    def __init__(self, event_bus, semantic_module=None):
        self.event_bus = event_bus
        self.semantic = semantic_module

        # Zelfde patroon als wikipedia_teacher.py's _pending_wiki_choice:
        # onthoudt welk woord net getoond is, zodat een kort
        # vervolgantwoord ("ja", of een nummer) zonder het woord te
        # herhalen begrepen wordt. Bewust een EIGEN, lichte state i.p.v.
        # het generieke pending_question-systeem (dat is bedoeld voor
        # simpele ja/nee-reacties op EIGEN vragen elders in de codebase,
        # niet voor dit specifieke, iets rijkere "ja OF een nummer"-
        # antwoordpatroon).
        self._pending_overview = None

        event_bus.subscribe("intent_concept_overview", self.on_concept_overview)

        print("[ConceptOverview] module geladen")

    # ------------------------------------------------------------------
    # Kort overzicht opbouwen
    # ------------------------------------------------------------------

    def _bouw_kort_overzicht(self, word: str, concept_data: dict) -> str | None:
        """
        Bouwt een kort overzicht: per sense enkel de definitie plus een
        telling van relaties/voorbeelden (geen volledige uitsplitsing).
        """
        if not concept_data:
            return None

        senses = concept_data.get("senses", [])
        if not senses:
            return None

        regels = [f"Over '{word}' weet ik het volgende:"]
        for i, sense in enumerate(senses, start=1):
            definitie = sense.get("definition", "onbekend")
            n_relaties = len(sense.get("relations", []))
            n_examples = len(sense.get("examples", []))

            detail_delen = []
            if n_relaties:
                detail_delen.append(f"{n_relaties} relatie{'s' if n_relaties != 1 else ''}")
            if n_examples:
                detail_delen.append(f"{n_examples} voorbeeld{'zinnen' if n_examples != 1 else 'zin'}")
            detail = f" ({', '.join(detail_delen)})" if detail_delen else ""

            regels.append(f"  {i}. {definitie}{detail}")

        if len(senses) == 1:
            regels.append("Wil je de relaties en voorbeelden zien? Typ 'ja' om te bevestigen.")
        else:
            regels.append(
                "Wil je de relaties en voorbeelden per betekenis zien? "
                "Typ 'ja' voor alles, of het nummer van een specifieke betekenis."
            )

        return "\n".join(regels)

    # ------------------------------------------------------------------
    # Detailweergave opbouwen
    # ------------------------------------------------------------------

    def _bouw_detail_voor_sense(self, sense: dict, sense_nummer: int = None, totaal_senses: int = 1) -> str:
        """
        Volledige detailweergave voor 1 sense: definitie, bron/
        zekerheid, alle relaties gegroepeerd per relatietype (zodat
        bv. 13 has_part-relaties samen op 1 regel staan i.p.v. 13 losse
        regels), en alle voorbeeldzinnen.
        """
        regels = []
        prefix = f"Betekenis {sense_nummer}: " if (sense_nummer and totaal_senses > 1) else ""
        regels.append(f"{prefix}{sense.get('definition', 'onbekend')}")

        source = sense.get("source", "onbekend")
        confidence = sense.get("confidence")
        if confidence is not None:
            regels.append(f"  (bron: {source}, zekerheid: {confidence})")
        else:
            regels.append(f"  (bron: {source})")

        relaties = sense.get("relations", [])
        if relaties:
            per_type = {}
            for r in relaties:
                per_type.setdefault(r.get("type", "?"), []).append(r.get("target", "?"))

            regels.append("  Relaties:")
            for rel_type, targets in per_type.items():
                regels.append(f"    {rel_type}: {', '.join(targets)}")
        else:
            regels.append("  Geen relaties bekend.")

        examples = sense.get("examples", [])
        if examples:
            regels.append("  Voorbeelden:")
            for ex in examples:
                regels.append(f"    \"{ex}\"")

        return "\n".join(regels)

    def _bouw_volledig_detail(self, word: str, concept_data: dict, specifiek_nummer: int = None) -> str | None:
        """
        Bouwt de volledige detailweergave — ofwel voor 1 specifieke
        sense (specifiek_nummer gegeven), ofwel voor ALLE senses
        (specifiek_nummer=None, bv. na "ja").

        Geeft None terug bij een ongeldig sense-nummer.
        """
        senses = concept_data.get("senses", [])
        totaal = len(senses)

        if specifiek_nummer is not None:
            idx = specifiek_nummer - 1
            if not (0 <= idx < totaal):
                return None
            return self._bouw_detail_voor_sense(senses[idx], specifiek_nummer, totaal)

        delen = [f"Alles wat ik weet over '{word}':"]
        for i, sense in enumerate(senses, start=1):
            delen.append(self._bouw_detail_voor_sense(sense, i, totaal))
        return "\n\n".join(delen)

    # ------------------------------------------------------------------
    # Event-afhandeling
    # ------------------------------------------------------------------

    def on_concept_overview(self, data, event_type=None):
        """
        Afhandeling van "wat weet je allemaal over X". Toont eerst het
        korte overzicht en zet een pending-vraag klaar voor het
        vervolgantwoord.
        """
        word = (data.get("word") or "").strip().lower().strip(".,!?;:")

        if not word:
            self.event_bus.publish("chat_response", {
                "text": "Over welk woord wil je alles weten?"
            })
            return

        if not self.semantic:
            self.event_bus.publish("chat_response", {
                "text": "Semantic module niet beschikbaar."
            })
            return

        concept_data = self.semantic.export_concept(word)
        if not concept_data or not concept_data.get("senses"):
            self.event_bus.publish("chat_response", {
                "text": f"Ik ken '{word}' nog niet. Leer het me met: teach {word} <betekenis>"
            })
            return

        overzicht = self._bouw_kort_overzicht(word, concept_data)
        self._pending_overview = {"woord": word}
        self.event_bus.publish("chat_response", {"text": overzicht})

    def verwerk_overview_antwoord(self, tekst: str) -> bool:
        """
        Checkt of er een openstaande "wat weet je over X"-vraag is, en
        of 'tekst' daar een geldig vervolgantwoord op is ('ja', of een
        sense-nummer). Geeft True terug als dit bericht als zodanig
        verwerkt is (de aanroeper moet dan stoppen met verdere
        routing), False als er niets open stond.

        Moet door intent_router.py's route() gecontroleerd worden vóór
        de bestaande generieke sense-choice (text.isdigit()) en vóór
        wikipedia_teacher.py's verwerk_wiki_keuze() — zelfde
        voorrang-redenering als daar: als Nova net deze vraag stelde,
        mag het antwoord nooit door een andere, generieke intent
        opgevangen worden.
        """
        if not self._pending_overview:
            return False

        woord = self._pending_overview["woord"]
        tekst_lower = tekst.strip().lower()

        if tekst_lower in ("ja", "ja graag", "ja, graag", "yes"):
            concept_data = self.semantic.export_concept(woord)
            self._pending_overview = None
            if not concept_data:
                self.event_bus.publish("chat_response", {
                    "text": f"Ik kon '{woord}' niet meer terugvinden."
                })
                return True
            detail = self._bouw_volledig_detail(woord, concept_data)
            self.event_bus.publish("chat_response", {"text": detail})
            return True

        if tekst.strip().isdigit():
            concept_data = self.semantic.export_concept(woord)
            self._pending_overview = None
            if not concept_data:
                self.event_bus.publish("chat_response", {
                    "text": f"Ik kon '{woord}' niet meer terugvinden."
                })
                return True
            detail = self._bouw_volledig_detail(woord, concept_data, specifiek_nummer=int(tekst.strip()))
            if detail is None:
                self.event_bus.publish("chat_response", {
                    "text": f"Dat nummer kende ik niet voor '{woord}'."
                })
            else:
                self.event_bus.publish("chat_response", {"text": detail})
            return True

        # Geen geldig vervolgantwoord ('ja' of een nummer) -> vraag
        # laten vervallen, normaal doorgaan met de rest van de routing.
        self._pending_overview = None
        return False


def init_module(event_bus, semantic_module=None):
    overview = ConceptOverview(event_bus, semantic_module)
    event_bus.publish("module_loaded", {"name": "concept_overview"})
    return overview