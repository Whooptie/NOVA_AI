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
                + self._zoek_has_part(sent, zoek)
            )
            for onderwerp, relatie, doel, regel in feiten:
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