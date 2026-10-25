# modules/knowledge/hypothese.py
#
# Hypothetisch redeneren (Taal & Redeneerlimieten, idee 4).
#
# Kevin zegt bv. "stel dat een hond een meubel is" en vraagt daarna
# "is een hond een meubel?" -- Nova antwoordt dan "ja" (binnen de
# aanname), zonder ooit iets in concepts.json te schrijven.
#
# HOE HET WERKT (alles 100% symbolisch, geen ML):
#   1. De aannames staan ENKEL in het RAM-geheugen van dit object
#      (self.aannames). Er wordt nooit iets opgeslagen op schijf.
#   2. semantic.py's RelationEngine.get_relations() vraagt bij elke
#      lezing aan dit object: "heb jij extra relaties voor dit woord?"
#      (extra_relaties). Alle redeneerfuncties (is_a, ketens,
#      tegenstrijdigheden, ...) lezen via get_relations(), dus ze zien
#      de aannames vanzelf mee.
#   3. De aannames zijn ENKEL zichtbaar tijdens een gebruikersbericht
#      en enkel voor de thread die dat bericht afhandelt (threading.local).
#      De achtergrond-thread van contradiction_checker.py ziet ze dus
#      nooit en kan er dus ook nooit een "tegenstrijdigheid" mee vinden.
#   4. Aannames vervallen vanzelf na 10 minuten zonder activiteit,
#      en er mogen er maximaal 5 tegelijk zijn.
#
# Beperkingen v1 (bewust): enkel TOEVOEGEN van relaties (is_a, part_of,
# causes), het onderwerp moet een bekend concept zijn, en related_to /
# vergelijken / onzekerheid zien de aannames niet.

import threading
import time
from contextlib import contextmanager


RELATIE_NAMEN = {
    "is_a": "is een",
    "part_of": "is een onderdeel van",
    "causes": "veroorzaakt",
}


class HypotheseModule:

    def __init__(self, event_bus, semantic=None, verval_seconden=600,
                 max_aannames=5, klok=None):
        self.event_bus = event_bus
        self.semantic = semantic
        self.verval_seconden = verval_seconden
        self.max_aannames = max_aannames
        self.klok = klok or time.time

        # Lijst van dicts: {"subject", "relation", "target"}
        self.aannames = []
        self.laatste_activiteit = self.klok()

        # Per thread: hoe diep we in een gebruikersbericht zitten, of
        # er een aanname gebruikt is, en of de aannames tijdelijk uit staan.
        self._lokaal = threading.local()

        # Koppel ons aan de RelationEngine zodat get_relations() ons raadpleegt.
        if semantic is not None:
            semantic.relation_engine.overlay = self

        event_bus.subscribe("intent_hypothese_stel", self._on_stel)
        event_bus.subscribe("intent_hypothese_gevolg", self._on_gevolg)
        event_bus.subscribe("intent_hypothese_wis", self._on_wis)
        event_bus.subscribe("intent_hypothese_toon", self._on_toon)
        event_bus.publish("module_loaded", {"name": "hypothese"})

    # ---------------------------------------------------------
    # Beurt-beheer (aangeroepen door intent_router.route())
    # ---------------------------------------------------------
    def _diepte(self):
        return getattr(self._lokaal, "diepte", 0)

    def betreed_beurt(self):
        diepte = self._diepte()
        if diepte == 0:
            self._lokaal.gebruikt = False
            self._lokaal.stil = False
            self._lokaal.uit = False
            self._vervallen_opruimen()
        self._lokaal.diepte = diepte + 1

    def verlaat_beurt(self):
        diepte = max(0, self._diepte() - 1)
        self._lokaal.diepte = diepte
        if diepte != 0:
            return
        gebruikt = getattr(self._lokaal, "gebruikt", False)
        stil = getattr(self._lokaal, "stil", False)
        self._lokaal.gebruikt = False
        self._lokaal.stil = False
        if gebruikt and not stil and self.aannames:
            self._stuur(
                "(Let op: dit antwoord kan je tijdelijke aanname gebruikt hebben: "
                + self._aannames_tekst()
                + ". Zeg 'wis de aannames' om terug te gaan naar de feiten.)"
            )

    def markeer_gebruikt(self):
        self._lokaal.gebruikt = True

    @contextmanager
    def _beurt(self, stil=True):
        """Handlers draaien meestal binnen route(), maar tests niet."""
        self.betreed_beurt()
        try:
            yield
        finally:
            if stil:
                self._lokaal.stil = True
            self.verlaat_beurt()

    @contextmanager
    def zonder_aannames(self):
        vorige = getattr(self._lokaal, "uit", False)
        self._lokaal.uit = True
        try:
            yield
        finally:
            self._lokaal.uit = vorige

    def heeft_aannames(self):
        self._vervallen_opruimen()
        return bool(self.aannames)

    # ---------------------------------------------------------
    # De hook die semantic.py aanroept
    # ---------------------------------------------------------
    def extra_relaties(self, woord, relation_type=None):
        if self._diepte() == 0:
            return []                      # buiten een gebruikersbericht: onzichtbaar
        if getattr(self._lokaal, "uit", False):
            return []
        woord = woord.lower().strip()
        return [
            a["target"] for a in self.aannames
            if a["subject"] == woord
            and (relation_type is None or a["relation"] == relation_type)
        ]

    # ---------------------------------------------------------
    # Hulpfuncties
    # ---------------------------------------------------------
    def _stuur(self, tekst):
        self.event_bus.publish("chat_response", {
            "source": "hypothese",
            "text": tekst,
        })

    def _vervallen_opruimen(self):
        nu = self.klok()
        if self.aannames and nu - self.laatste_activiteit > self.verval_seconden:
            self.aannames = []

    def _aannames_tekst(self):
        return "; ".join(
            f"{a['subject']} {RELATIE_NAMEN.get(a['relation'], a['relation'])} {a['target']}"
            for a in self.aannames
        )

    def _voorouders(self, woord):
        """Alle is_a-voorouders (ketens, max 6 diep), met de huidige zichtbaarheid."""
        re_ = self.semantic.relation_engine
        gezien, rij = [], [(woord, 0)]
        while rij:
            huidig, diepte = rij.pop(0)
            if diepte >= 6:
                continue
            for ouder in re_.get_relations(huidig, relation_type="is_a"):
                if ouder not in gezien and ouder != woord:
                    gezien.append(ouder)
                    rij.append((ouder, diepte + 1))
        return gezien

    # ---------------------------------------------------------
    # Event-handlers
    # ---------------------------------------------------------
    def _on_stel(self, data, event_type=None):
        with self._beurt():
            subject = (data.get("subject") or "").lower().strip()
            relation = data.get("relation")
            target = (data.get("target") or "").lower().strip()

            if relation not in RELATIE_NAMEN or not subject or not target:
                self._stuur("Die aanname begrijp ik niet.")
                return
            if subject == target:
                self._stuur("Dat is een cirkel (iets is zichzelf), die aanname neem ik niet aan.")
                return
            if self.semantic is None or not self.semantic.store.has_concept(subject):
                self._stuur(
                    f"Ik ken '{subject}' nog niet, dus ik kan er (nog) geen aanname over doen. "
                    f"Leer het me eerst."
                )
                return

            self._vervallen_opruimen()
            nieuw = {"subject": subject, "relation": relation, "target": target}

            if nieuw in self.aannames:
                self._stuur("Die aanname had ik al.")
                return
            with self.zonder_aannames():
                echt = target in self.semantic.relation_engine.get_relations(
                    subject, relation_type=relation)
            if echt:
                self._stuur("Dat is volgens mij al zo, daar hoef je niets voor aan te nemen.")
                return
            if len(self.aannames) >= self.max_aannames:
                self._stuur(
                    f"Ik hou maximaal {self.max_aannames} aannames tegelijk vast. "
                    f"Zeg 'wis de aannames' om opnieuw te beginnen."
                )
                return

            self.aannames.append(nieuw)
            self.laatste_activiteit = self.klok()
            self._stuur(
                f"Oké, ik neem tijdelijk aan: {subject} {RELATIE_NAMEN[relation]} {target}. "
                f"Dit schrijf ik nergens op en het vervalt na 10 minuten of met "
                f"'wis de aannames'."
            )

    def _on_gevolg(self, data, event_type=None):
        with self._beurt():
            if not self.heeft_aannames():
                self._stuur("Ik heb nu geen aannames waar ik iets uit kan afleiden.")
                return
            self.laatste_activiteit = self.klok()
            regels = []
            for subject in dict.fromkeys(a["subject"] for a in self.aannames):
                met = self._voorouders(subject)
                with self.zonder_aannames():
                    zonder = self._voorouders(subject)
                    effecten_zonder = {e["woord"] for e in self.semantic.get_all_effects(subject)}
                nieuw = [w for w in met if w not in zonder]
                if nieuw:
                    regels.append(f"{subject} is dan ook: {', '.join(nieuw)}.")
                effecten = [e["woord"] for e in self.semantic.get_all_effects(subject)
                            if e["woord"] not in effecten_zonder]
                if effecten:
                    regels.append(f"{subject} veroorzaakt dan ook: {', '.join(effecten)}.")

                with self.zonder_aannames():
                    oude = {c["reason"] for c in self.semantic.find_contradictions(subject)}
                for c in self.semantic.find_contradictions(subject):
                    if c["reason"] not in oude:
                        regels.append(f"Let op, dat botst: {c['reason']}.")
            if not regels:
                regels.append("Daar volgt (met wat ik weet) niets nieuws uit.")
            self._stuur("Binnen je aanname(s) (" + self._aannames_tekst() + "): " + " ".join(regels))

    def _on_wis(self, data, event_type=None):
        with self._beurt():
            aantal = len(self.aannames)
            self.aannames = []
            if aantal:
                self._stuur("Oké, alle aannames zijn gewist. Terug naar de feiten.")
            else:
                self._stuur("Ik had geen aannames, dus er valt niets te wissen.")

    def _on_toon(self, data, event_type=None):
        with self._beurt():
            if not self.heeft_aannames():
                self._stuur("Ik neem op dit moment niets aan.")
                return
            self._stuur("Ik neem tijdelijk aan: " + self._aannames_tekst() + ".")


def init_module(event_bus, sem=None):
    return HypotheseModule(event_bus, semantic=sem)