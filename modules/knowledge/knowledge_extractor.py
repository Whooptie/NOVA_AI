"""
knowledge_extractor.py -- Semantic Fase 11.1: feiten uit tekst halen

Wat doet dit bestand?
    Het leest een stuk Nederlandse tekst (bv. de inleiding van een
    Wikipedia-artikel) en zoekt daarin KANDIDAAT-FEITEN van twee soorten:

        is_a      "Een gitaar is een snaarinstrument."
        has_part  "Een fiets bestaat uit een frame, wielen en een stuur."

Belangrijk -- wat dit bestand NIET doet:
    * Het schrijft NIETS weg. Er komt niets in concepts.json terecht.
      Opslaan na jouw bevestiging is Fase 11.2.
    * Het begrijpt geen betekenis. spaCy ontleedt enkel de zinsbouw.

Eerlijk over ML versus symbolisch:
    * ML (extern, gespecialiseerd): spaCy's model `nl_core_news_sm`
      bepaalt woordsoorten en zinsbouw. Dat is een getraind model dat
      zich kan vergissen. NER (namen herkennen) zetten we bewust UIT,
      want dat bleek onbetrouwbaar.
    * Symbolisch: ALLE beslissingen over wat een feit is, zitten in dit
      bestand (vaste regels) en in data/extractie_regels.json (lijsten).

Veilig falen:
    * Ontbreekt spaCy, het model of het regelbestand, dan zet de module
      zichzelf stil uit en geeft extract_from_text() een lege lijst terug.
      Nova crasht dus nooit door deze module.

Gebruik:
    from modules.knowledge.knowledge_extractor import KnowledgeExtractor
    extractor = KnowledgeExtractor()
    if extractor.is_beschikbaar():
        voorstellen = extractor.extract_from_text(tekst, zoekwoord="fiets")
"""

import json
import re
from pathlib import Path


MODEL_NAAM = "nl_core_news_sm"
MAX_TEKENS = 5000  # we lezen enkel een inleiding, nooit een heel artikel


def _standaard_regels_pad():
    """Pad naar data/extractie_regels.json, vanaf de project-root."""
    # Drie mappen omhoog: modules/knowledge/<dit bestand> -> project-root
    return Path(__file__).resolve().parents[2] / "data" / "extractie_regels.json"


def verwijder_haakjes(tekst):
    """Haalt (...) weg uit de tekst, ook als er haakjes in haakjes staan."""
    vorige = None
    while vorige != tekst:
        vorige = tekst
        tekst = re.sub(r"\s*\([^()]*\)", "", tekst)
    return tekst


VOORVOEGSELS_STANDAARD = ("basis", "standaard")

# Woorden waarmee "X is een <woord> van Y" een is_a-relatie uitdrukt (Fase 11, 2B)
SOORT_WOORDEN = ("ondersoort", "soort", "variant", "vorm")
# "X is een <woord> van Y" / "X maakt deel uit van Y" -> X part_of Y (Fase 11, 2B)
DEEL_WOORDEN = ("onderdeel", "deel")
# "X is een <woord> om te ..." -> X used_for ... (Fase 11, used_for)
GEBRUIKSMIDDEL_WOORDEN = ("middel", "hulpmiddel", "gereedschap", "instrument",
                          "apparaat", "werktuig", "toestel")
# Een doel langer dan dit aantal woorden is een omschrijving, geen begrip
MAX_WOORDEN_GEBRUIKSDOEL = 4


class KnowledgeExtractor:
    """Zoekt is_a- en has_part-voorstellen in Nederlandse tekst."""

    def __init__(self, event_bus=None, regels_pad=None, nlp=None,
                 model_naam=MODEL_NAAM):
        self.event_bus = event_bus
        self.regels_pad = Path(regels_pad) if regels_pad else _standaard_regels_pad()
        self.model_naam = model_naam
        self.nlp = nlp  # mag van buitenaf meegegeven worden (tests)
        self.reden_uit = None  # waarom de module niet beschikbaar is

        self.voorbehoud = set()
        self.vage_woorden = set()
        self.doorverwijs_signalen = []
        # Voorvoegsels waarmee een samenstelling nog steeds "het woord zelf"
        # is ("basisfiets" = de gewone fiets). Optioneel in het regelbestand.
        self.samenstelling_voorvoegsels = set(VOORVOEGSELS_STANDAARD)

        self._laad_regels()
        if self.reden_uit is None and self.nlp is None:
            self._laad_model()

        if self.reden_uit:
            print(f"[KnowledgeExtractor] uitgeschakeld: {self.reden_uit}")
        else:
            print("[KnowledgeExtractor] module geladen (spaCy actief, NER uit)")

    # ------------------------------------------------------------------
    # Laden
    # ------------------------------------------------------------------

    def _laad_regels(self):
        """Leest data/extractie_regels.json. Faalt het, dan blijft de
        module uit: zonder voorbehoud-filter zouden we te veel fout
        voorstellen doorlaten."""
        try:
            with open(self.regels_pad, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.voorbehoud = {w.lower() for w in data["voorbehoud"]}
            self.vage_woorden = {w.lower() for w in data["vage_woorden"]}
            self.doorverwijs_signalen = [s.lower() for s in data["doorverwijs_signalen"]]
            if "samenstelling_voorvoegsels" in data:
                self.samenstelling_voorvoegsels = {
                    w.lower() for w in data["samenstelling_voorvoegsels"]}
        except FileNotFoundError:
            self.reden_uit = f"regelbestand ontbreekt ({self.regels_pad})"
        except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as e:
            self.reden_uit = f"regelbestand is ongeldig ({type(e).__name__}: {e})"

    def _laad_model(self):
        """Laadt spaCy en het Nederlandse model (NER uitgeschakeld)."""
        try:
            import spacy
        except ImportError:
            self.reden_uit = "spaCy is niet geinstalleerd"
            return
        try:
            self.nlp = spacy.load(self.model_naam, disable=["ner"])
        except OSError:
            self.reden_uit = f"model '{self.model_naam}' niet gevonden"

    def is_beschikbaar(self):
        return self.reden_uit is None and self.nlp is not None

    # ------------------------------------------------------------------
    # Hoofdfunctie
    # ------------------------------------------------------------------

    def extract_from_text(self, tekst, zoekwoord=None):
        """
        Geeft een lijst kandidaat-feiten terug. Elk feit is een dict:
            {"onderwerp", "relatie", "doel", "zin", "regel"}

        zoekwoord: het woord waar de tekst over gaat (bv. "fiets"). Het
            onderwerp van een feit moet dit woord bevatten. Zonder
            zoekwoord is die controle uit (handig voor losse zinnen).
        """
        if not self.is_beschikbaar() or not tekst or not tekst.strip():
            return []

        tekst = tekst[:MAX_TEKENS]

        # Doorverwijspagina's ("X kan verwijzen naar:") zijn geen definitie
        laag = tekst.lower()
        if any(s in laag for s in self.doorverwijs_signalen):
            return []

        zoek = zoekwoord.lower().strip() if zoekwoord else None
        doc = self.nlp(verwijder_haakjes(tekst))

        resultaten = []
        gezien = set()
        for nr, sent in enumerate(doc.sents):
            if self._heeft_voorbehoud(sent):
                continue
            # Alleen de allereerste zin mag 'de/het' i.p.v. 'een' gebruiken
            de_toegestaan = (nr == 0)
            feiten = (
                self._zoek_is_a(sent, zoek, de_toegestaan)
                + self._zoek_ondersoort(sent, zoek, de_toegestaan)
                + self._zoek_has_part(sent, zoek)
                + self._zoek_part_of(sent, zoek)
                + self._zoek_causes(sent, zoek)
                + self._zoek_used_for(sent, zoek, de_toegestaan)
            )
            for onderwerp, relatie, doel, regel in feiten:
                onderwerp = self._normaliseer_onderwerp(onderwerp, zoek)
                if doel == onderwerp:
                    continue   # "fiets is_a fiets" na het samenvoegen
                sleutel = (onderwerp, relatie, doel)
                if sleutel in gezien:
                    continue
                gezien.add(sleutel)
                resultaten.append({
                    "onderwerp": onderwerp,
                    "relatie": relatie,
                    "doel": doel,
                    "zin": sent.text.strip(),
                    "regel": regel,
                })
        return resultaten

    # ------------------------------------------------------------------
    # Hulpfuncties
    # ------------------------------------------------------------------

    def _heeft_voorbehoud(self, sent):
        """Voorbehoud/ontkenning telt alleen in de hoofdzin, niet in een
        'die/dat'-bijzin ('...dat doorgaans met spierkracht wordt...')."""
        for t in sent:
            if t.text.lower() not in self.voorbehoud:
                continue
            in_bijzin = t.dep_ == "acl:relcl" or any(
                a.dep_ == "acl:relcl" for a in t.ancestors
            )
            if not in_bijzin:
                return True
        return False

    @staticmethod
    def _is_tegenwoordig(tok):
        return "Pres" in tok.morph.get("Tense")

    @staticmethod
    def _onderwerp_frase(subj):
        """Onderwerp plus woorden die eraan vast zitten ('machine learning')."""
        links = [
            c for c in subj.children
            if c.i < subj.i and (
                c.dep_ in ("compound", "flat")
                or (c.dep_ == "nmod" and c.pos_ in ("NOUN", "PROPN"))
            )
        ]
        links.sort(key=lambda c: c.i)
        return " ".join([c.text for c in links] + [subj.text]).lower()

    def _normaliseer_onderwerp(self, onderwerp, zoek):
        """'basisfiets' -> 'fiets' als we over 'fiets' lezen (Fase 11, optie B).

        Bewust STRENG: alleen een enkel woord dat precies uit een bekend
        voorvoegsel (data/extractie_regels.json, 'samenstelling_voorvoegsels',
        standaard basis/standaard) plus het zoekwoord bestaat. Zo blijft
        'tandwiel' bij 'wiel' of 'racefiets' bij 'fiets' ongemoeid: dat zijn
        eigen, specifiekere dingen en geen andere naam voor het zoekwoord."""
        if not zoek or onderwerp == zoek or " " in onderwerp:
            return onderwerp
        if onderwerp.endswith(zoek):
            voorvoegsel = onderwerp[:-len(zoek)]
            if voorvoegsel in self.samenstelling_voorvoegsels:
                return zoek
        return onderwerp

    def _is_vaag(self, frase):
        return any(w in self.vage_woorden for w in frase.split())

    @staticmethod
    def _heeft_lidwoord(tok, toegestaan):
        """Staat er een toegestaan lidwoord voor het doel (of voor een
        'soort/type' ervoor, zoals in 'een soort vaartuig')?"""
        if any(c.dep_ == "det" and c.text.lower() in toegestaan
               for c in tok.children):
            return True
        for c in tok.children:
            if c.dep_ == "nmod" and c.lemma_ in ("soort", "type"):
                if any(g.dep_ == "det" and g.text.lower() in toegestaan
                       for g in c.children):
                    return True
        return False

    @staticmethod
    def _voorzetsel_ertussen(sent, van_tok, naar_tok):
        """Staat er een voorzetsel tussen twee woorden? Dan is het tweede
        woord waarschijnlijk deel van een 'van/met/in'-groep en geen echte
        nevenschikking ('verbinding van twee atomen en een zuurstofatoom')."""
        begin, einde = sorted((van_tok.i, naar_tok.i))
        return any(
            t.pos_ == "ADP" for t in sent.doc[begin + 1:einde]
        )

    # ------------------------------------------------------------------
    # Regels per relatietype
    # ------------------------------------------------------------------

    def _zoek_is_a(self, sent, zoek, de_toegestaan):
        """'X is een Y' -> (X, is_a, Y)."""
        out = []
        for tok in sent:
            if tok.dep_ != "ROOT" or tok.pos_ != "NOUN":
                continue
            # De kern mag niet aan een voorzetsel hangen ('is in opkomst')
            if any(c.dep_ == "case" for c in tok.children):
                continue
            # Koppelwerkwoord 'zijn' in de TEGENWOORDIGE tijd
            cops = [c for c in tok.children
                    if c.dep_ == "cop" and c.lemma_ == "zijn"
                    and self._is_tegenwoordig(c)]
            # Onderwerp moet een naamwoord zijn (geen 'het', 'hij', ...)
            subjs = [c for c in tok.children
                     if c.dep_ == "nsubj" and c.pos_ in ("NOUN", "PROPN")]
            if not cops or not subjs:
                continue

            frase = self._onderwerp_frase(subjs[0])
            if zoek and zoek not in frase:
                continue
            if self._is_vaag(frase):
                continue

            # 'de/het' alleen in de eerste zin EN als het onderwerp precies
            # het opgezochte woord is ("De hond is de ... van de wolf").
            if de_toegestaan and zoek and frase == zoek:
                toegestaan = {"een", "de", "het"}
            else:
                toegestaan = {"een"}

            doelen = [tok] + [
                c for c in tok.children
                if c.dep_ == "conj" and c.pos_ == "NOUN"
                and not self._voorzetsel_ertussen(sent, tok, c)
            ]
            for d in doelen:
                doel = d.text.lower()
                if not self._heeft_lidwoord(d, toegestaan):
                    continue
                if doel in self.vage_woorden:
                    continue
                if doel == frase or doel == subjs[0].text.lower():
                    continue
                out.append((frase, "is_a", doel, "is_a_koppelwerkwoord"))
        return out

    # ------------------------------------------------------------------
    # Fase 11, deel 2B: ondersoort van, part_of, causes
    # ------------------------------------------------------------------

    def _is_hoofdwerkwoord_nu(self, tok):
        """Staat dit werkwoord in de tegenwoordige tijd als hoofdwerkwoord?
        spaCy's kleine model labelt 'Regen veroorzaakt overstromingen' soms
        als voltooid deelwoord (VerbForm=Part, geen Tense). Zo'n werkwoord
        accepteren we alleen als het de kern van de zin is EN er geen
        hulpwerkwoord bij staat ('wordt/is/heeft veroorzaakt' = passief of
        voltooid, dus niet bedoeld)."""
        if self._is_tegenwoordig(tok):
            return True
        if tok.dep_ != "ROOT" or "Part" not in tok.morph.get("VerbForm"):
            return False
        return not any(c.dep_.startswith("aux") or c.dep_ == "cop"
                       for c in tok.children)

    @staticmethod
    def _heeft_van(tok):
        """Heeft dit woord een voorzetsel 'van' bij zich ('van de wolf')?"""
        return any(g.dep_ == "case" and g.text.lower() == "van"
                   for g in tok.children)

    def _koppel_en_onderwerp(self, tok):
        """Voor 'X is een Y ...': geeft het onderwerp (X) terug als de zin een
        tegenwoordig koppelwerkwoord 'zijn' en een naamwoord als onderwerp
        heeft, anders None."""
        cops = [c for c in tok.children
                if c.dep_ == "cop" and c.lemma_ == "zijn"
                and self._is_tegenwoordig(c)]
        subjs = [c for c in tok.children
                 if c.dep_ == "nsubj" and c.pos_ in ("NOUN", "PROPN")]
        if not cops or not subjs:
            return None
        return subjs[0]

    def _zoek_ondersoort(self, sent, zoek, de_toegestaan):
        """'X is een ondersoort/soort/variant van Y' -> (X, is_a, Y)."""
        out = []
        for tok in sent:
            if (tok.dep_ != "ROOT" or tok.pos_ != "NOUN"
                    or tok.lemma_ not in SOORT_WOORDEN):
                continue
            if any(c.dep_ == "case" for c in tok.children):
                continue
            subj = self._koppel_en_onderwerp(tok)
            if subj is None:
                continue
            frase = self._onderwerp_frase(subj)
            if zoek and zoek not in frase:
                continue
            if self._is_vaag(frase):
                continue
            if de_toegestaan and zoek and frase == zoek:
                toegestaan = {"een", "de", "het"}
            else:
                toegestaan = {"een"}
            if not self._heeft_lidwoord(tok, toegestaan):
                continue
            doelen = [c for c in tok.children
                      if c.dep_ in ("nmod", "obl") and c.pos_ in ("NOUN", "PROPN")
                      and self._heeft_van(c)]
            for d in list(doelen):
                doelen += [c for c in d.children
                           if c.dep_ == "conj" and c.pos_ in ("NOUN", "PROPN")
                           and not self._voorzetsel_ertussen(sent, d, c)]
            for d in doelen:
                doel = self._onderwerp_frase(d)
                if self._is_vaag(doel) or doel == frase:
                    continue
                out.append((frase, "is_a", doel, "is_a_ondersoort_van"))
        return out

    def _zoek_part_of(self, sent, zoek):
        """'X is een onderdeel/deel van Y' en 'X maakt deel uit van Y'
        -> (X, part_of, Y). X is het deel, Y het geheel (zoals Nova het bewaart).
        Het opgezochte woord moet in X of in Y staan."""
        out = []
        for tok in sent:
            if tok.dep_ != "ROOT":
                continue
            subj = None
            doelen = []
            if tok.pos_ == "NOUN" and tok.lemma_ in DEEL_WOORDEN:
                # "Het stuur is een onderdeel van de fiets."
                if any(c.dep_ == "case" for c in tok.children):
                    continue
                subj = self._koppel_en_onderwerp(tok)
                if subj is None or not self._heeft_lidwoord(tok, {"een"}):
                    continue
                doelen = [c for c in tok.children
                          if c.dep_ in ("nmod", "obl")
                          and c.pos_ in ("NOUN", "PROPN") and self._heeft_van(c)]
            elif (tok.pos_ == "VERB" and tok.lemma_ == "uitmaken"
                  and self._is_tegenwoordig(tok)):
                # "De trapas maakt deel uit van de aandrijving."
                if not any(c.dep_ == "obj" and c.text.lower() == "deel"
                           for c in tok.children):
                    continue
                subjs = [c for c in tok.children
                         if c.dep_ == "nsubj" and c.pos_ in ("NOUN", "PROPN")]
                if not subjs:
                    continue
                subj = subjs[0]
                doelen = [c for c in tok.children
                          if c.dep_ in ("obl", "nmod")
                          and c.pos_ in ("NOUN", "PROPN") and self._heeft_van(c)]
            if subj is None:
                continue
            frase = self._onderwerp_frase(subj)
            if self._is_vaag(frase):
                continue
            for d in doelen:
                geheel = self._onderwerp_frase(d)
                if self._is_vaag(geheel) or geheel == frase:
                    continue
                if zoek and zoek not in frase and zoek not in geheel:
                    continue
                out.append((frase, "part_of", geheel, "part_of_onderdeel_van"))
        return out

    def _zoek_causes(self, sent, zoek):
        """'X veroorzaakt Y' en 'X leidt tot Y' -> (X, causes, Y).
        Alleen tegenwoordige tijd, alleen naamwoorden aan beide kanten.
        Het opgezochte woord moet in X of in Y staan."""
        out = []
        for tok in sent:
            if tok.pos_ != "VERB" or not self._is_hoofdwerkwoord_nu(tok):
                continue
            if tok.lemma_ == "veroorzaken":
                # spaCy labelt het onderwerp soms als 'obj' ("Een vulkaan
                # veroorzaakt ..."), daarom kijken we naar de POSITIE:
                # links van het werkwoord = oorzaak, rechts = gevolg.
                oorzaken = [c for c in tok.children
                            if c.dep_ in ("nsubj", "obj") and c.i < tok.i
                            and c.pos_ in ("NOUN", "PROPN")]
                # Alleen het lijdend voorwerp: een bijzin als "schade AAN
                # gebouwen" mag 'gebouwen' niet tot zelfstandig gevolg maken.
                gevolgen = [c for c in tok.children
                            if c.dep_ == "obj" and c.i > tok.i
                            and c.pos_ in ("NOUN", "PROPN")]
                regel = "causes_veroorzaakt"
            elif tok.lemma_ == "leiden":
                oorzaken = [c for c in tok.children
                            if c.dep_ == "nsubj" and c.pos_ in ("NOUN", "PROPN")]
                gevolgen = [c for c in tok.children
                            if c.dep_ == "obl" and c.pos_ in ("NOUN", "PROPN")
                            and any(g.dep_ == "case" and g.text.lower() == "tot"
                                    for g in c.children)]
                regel = "causes_leidt_tot"
            else:
                continue
            if len(oorzaken) != 1 or not gevolgen:
                continue
            oorzaak = self._onderwerp_frase(oorzaken[0])
            if self._is_vaag(oorzaak):
                continue
            alle_gevolgen = list(gevolgen)
            for g in gevolgen:
                alle_gevolgen += [c for c in g.children
                                  if c.dep_ == "conj" and c.pos_ in ("NOUN", "PROPN")
                                  and not self._voorzetsel_ertussen(sent, g, c)]
            for g in alle_gevolgen:
                gevolg = self._onderwerp_frase(g)
                if self._is_vaag(gevolg) or gevolg == oorzaak:
                    continue
                if zoek and zoek not in oorzaak and zoek not in gevolg:
                    continue
                out.append((oorzaak, "causes", gevolg, regel))
        return out

    # ------------------------------------------------------------------
    # Fase 11, used_for: "X wordt gebruikt voor/om ..."
    # ------------------------------------------------------------------

    @staticmethod
    def _heeft_voorzetsel(tok, woord):
        """Heeft dit woord een voorzetsel/voegwoord (case/mark) met deze tekst?"""
        return any(c.dep_ in ("case", "mark") and c.text.lower() == woord
                   for c in tok.children)

    def _werkwoord_frase(self, verb):
        """'om spijkers te slaan' -> 'spijkers slaan'. Alleen het voorwerp
        en het werkwoord; bijwoorden en voorzetselgroepen vallen weg zodat
        een doel een kort begrip blijft."""
        delen = []
        voorwerpen = [c for c in verb.children
                      if c.dep_ == "obj" and c.pos_ in ("NOUN", "PROPN")]
        if voorwerpen:
            delen.append(voorwerpen[0].text.lower())
        scheid = [c for c in verb.children if c.dep_ == "compound:prt"]
        werkwoord = verb.text.lower()
        if scheid:   # "aan te sluiten" -> "aansluiten"
            werkwoord = scheid[0].text.lower() + werkwoord
        delen.append(werkwoord)
        return " ".join(delen)

    def _doel_frases_om(self, verb):
        """Doelen uit een om-te-bijzin, inclusief 'om te zagen en te boren'."""
        verbs = [verb] + [c for c in verb.children
                          if c.dep_ == "conj" and c.pos_ == "VERB"]
        return [self._werkwoord_frase(v) for v in verbs]

    def _doel_frases_voor(self, tok, sent):
        """Doelen uit 'voor X' (en 'voor X en Y'): een zelfstandig naamwoord,
        of 'het doorsnijden van hout'."""
        out = []
        kernen = [tok] + [c for c in tok.children
                          if c.dep_ == "conj" and c.pos_ in ("NOUN", "VERB")
                          and not self._voorzetsel_ertussen(sent, tok, c)]
        for k in kernen:
            if k.pos_ == "NOUN":
                out.append(self._onderwerp_frase(k))
            elif k.pos_ == "VERB":
                van = [c for c in k.children
                       if c.dep_ == "nmod" and c.pos_ in ("NOUN", "PROPN")
                       and self._heeft_van(c)]
                tekst = k.text.lower()
                if van:
                    tekst += " van " + van[0].text.lower()
                out.append(tekst)
        return out

    def _gebruiksdoelen(self, verb, sent):
        """Alle doelen die aan dit werkwoord hangen: om-bijzinnen en 'voor X'."""
        doelen = []
        for c in verb.children:
            if (c.dep_ in ("advcl", "xcomp", "acl") and c.pos_ == "VERB"
                    and self._heeft_voorzetsel(c, "om")):
                doelen += self._doel_frases_om(c)
            elif (c.dep_ == "obl" and c.pos_ in ("NOUN", "VERB")
                  and self._heeft_voorzetsel(c, "voor")):
                doelen += self._doel_frases_voor(c, sent)
        return doelen

    def _zoek_used_for(self, sent, zoek, de_toegestaan):
        """'X wordt gebruikt voor/om ...', 'X is een middel om te ...' en
        'X dient voor/om ...' -> (X, used_for, doel).

        Bewust niet: 'gebruikt als ...' (dat is een rol, geen doel) en
        'gebruikt bij/in ...' (dat is een plek of situatie)."""
        out = []
        for tok in sent:
            subj = None
            if (tok.dep_ == "ROOT" and tok.pos_ == "VERB"
                    and tok.lemma_ == "gebruiken"):
                # "Een hamer wordt gebruikt om ..."
                if any(c.dep_ == "aux:pass" and c.lemma_ == "worden"
                       and self._is_tegenwoordig(c) for c in tok.children):
                    subjs = [c for c in tok.children
                             if c.dep_ == "nsubj:pass" and c.pos_ in ("NOUN", "PROPN")]
                    subj = subjs[0] if subjs else None
                    doelen = self._gebruiksdoelen(tok, sent)
                    regel = "used_for_gebruikt"
            elif (tok.dep_ == "acl:relcl" and tok.pos_ == "VERB"
                  and tok.lemma_ == "gebruiken"
                  and tok.head.dep_ == "ROOT" and tok.head.pos_ == "NOUN"):
                # "Een hamer is een gereedschap dat gebruikt wordt om ..."
                kern = tok.head
                if (any(c.dep_ == "aux:pass" and c.lemma_ == "worden"
                        and self._is_tegenwoordig(c) for c in tok.children)
                        and any(c.dep_ == "cop" and self._is_tegenwoordig(c)
                                for c in kern.children)):
                    subjs = [c for c in kern.children
                             if c.dep_ == "nsubj" and c.pos_ in ("NOUN", "PROPN")]
                    subj = subjs[0] if subjs else None
                    doelen = self._gebruiksdoelen(tok, sent)
                    regel = "used_for_gebruikt"
            elif (tok.dep_ == "ROOT" and tok.pos_ == "NOUN"
                  and tok.lemma_ in GEBRUIKSMIDDEL_WOORDEN
                  and not any(c.dep_ == "case" for c in tok.children)):
                # "Een stuur is een middel om een voertuig te navigeren."
                if any(c.dep_ == "cop" and c.lemma_ == "zijn"
                       and self._is_tegenwoordig(c) for c in tok.children):
                    subjs = [c for c in tok.children
                             if c.dep_ == "nsubj" and c.pos_ in ("NOUN", "PROPN")]
                    subj = subjs[0] if subjs else None
                    doelen = self._gebruiksdoelen(tok, sent)
                    regel = "used_for_middel_om"
            elif (tok.dep_ == "ROOT" and tok.pos_ == "VERB"
                  and tok.lemma_ == "dienen" and self._is_hoofdwerkwoord_nu(tok)):
                # "Een lamp dient voor verlichting." / "... dient om te ..."
                subjs = [c for c in tok.children
                         if c.dep_ == "nsubj" and c.pos_ in ("NOUN", "PROPN")]
                subj = subjs[0] if subjs else None
                doelen = self._gebruiksdoelen(tok, sent)
                regel = "used_for_dient"
            if subj is None or not doelen:
                continue

            frase = self._onderwerp_frase(subj)
            if zoek and zoek not in frase:
                continue
            if self._is_vaag(frase):
                continue
            if de_toegestaan and zoek and frase == zoek:
                toegestaan = {"een", "de", "het"}
            else:
                toegestaan = {"een"}
            if not self._heeft_lidwoord(subj, toegestaan):
                continue

            for doel in doelen:
                if (not doel or doel == frase or self._is_vaag(doel)
                        or len(doel.split()) > MAX_WOORDEN_GEBRUIKSDOEL):
                    continue
                out.append((frase, "used_for", doel, regel))
        return out

    def _zoek_has_part(self, sent, zoek):
        """'X bestaat uit A, B en C' -> (X, has_part, A/B/C)."""
        out = []
        for tok in sent:
            if (tok.pos_ != "VERB" or tok.lemma_ != "bestaan"
                    or not self._is_tegenwoordig(tok)):
                continue
            subjs = [c for c in tok.children
                     if c.dep_ == "nsubj" and c.pos_ in ("NOUN", "PROPN")]
            if not subjs:
                continue
            frase = self._onderwerp_frase(subjs[0])
            if zoek and zoek not in frase:
                continue
            if self._is_vaag(frase):
                continue

            for obl in [c for c in tok.children if c.dep_ == "obl"]:
                if not any(g.dep_ == "case" and g.text.lower() == "uit"
                           for g in obl.children):
                    continue
                delen = [obl] + [
                    c for c in obl.children
                    if c.dep_ == "conj"
                    and not self._voorzetsel_ertussen(sent, obl, c)
                ]
                for d in delen:
                    deel = d.text.lower()
                    if deel in self.vage_woorden or deel == frase:
                        continue
                    out.append((frase, "has_part", deel, "has_part_bestaat_uit"))
        return out


def init_module(event_bus, sem=None):
    """Standaard module_loader-conventie: wordt automatisch gevonden."""
    extractor = KnowledgeExtractor(event_bus=event_bus)
    try:
        event_bus.register_module("knowledge_extractor", extractor)
    except Exception:
        pass  # de loader registreert de module zelf ook; dit is enkel een extra
    return extractor