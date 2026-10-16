"""
spacy_verkenning3.py -- Semantic Fase 11, stap 0, ronde 3

Strengere regels voor is_a en has_part, alleen Wikipedia-inleidingen.
Schrijft niets weg en wijzigt NIETS aan Nova.

Draaien:
    docker exec nova-ai python scripts/spacy_verkenning3.py
"""

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

import spacy

MODEL_NAAM = "nl_core_news_sm"
PAUZE_SECONDEN = 2

# Ontkenning/voorbehoud: zin wordt overgeslagen
VOORBEHOUD = {
    "niet", "geen", "nooit", "soms", "meestal", "vaak", "bijna", "vrijwel",
    "kan", "kunnen", "mogelijk", "waarschijnlijk", "doorgaans", "hoofdzakelijk",
    "grotendeels", "voornamelijk", "meestal", "gewoonlijk", "veelal",
}

# Vage woorden die nooit als onderwerp of doel mogen dienen
VAGE_WOORDEN = {
    "voorbeeld", "voorbeelden", "uitzondering", "kenmerk", "nadeel", "voordeel",
    "resultaat", "herkomst", "aanduiding", "bijnaam", "sprake", "gedrag",
    "reden", "oorzaak", "gevolg", "onderdeel", "deel", "soort", "type",
    "vorm", "manier", "deze", "dit", "dat", "die",
}

EXTRA_ZINNEN = [
    # Moeten voorstellen geven
    "Een gitaar is een snaarinstrument en een muziekinstrument.",
    "Een zeilboot is een soort vaartuig.",
    "Een vulkaan is een berg waaruit lava komt.",
    "Machine learning is een vakgebied binnen de informatica.",
    "Een fiets bestaat uit een frame, twee wielen en een stuur.",
    # Moeten NIETS geven
    "De hond is de gedomesticeerde ondersoort van de wolf.",
    "De hond was het eerste dier dat door de mens werd gedomesticeerd.",
    "In het begin van de 21e eeuw is de elektrische fiets in opkomst.",
    "Een geleidehond is een voorbeeld van een assistentiehond.",
    "Een hond is een hond.",
    "Het is een dier dat blaft.",
    "Een kat is meestal een huisdier.",
    "Een hond is niet altijd een huisdier.",
    "Zijn maaltijd bestond uit brood en groenten.",
    "Honden zijn sociale dieren.",
]

WIKI_WOORDEN = [
    "hond", "fiets", "gitaar", "narwal", "vulkaan", "democratie", "piano",
    "auto", "huis", "boom", "computer", "appel", "kat", "vliegtuig",
    "tafel", "stoel", "zon", "water", "schaken", "telefoon",
]


def heeft_voorbehoud(sent):
    """Voorbehoud telt alleen in de hoofdzin, niet in een 'die/dat'-bijzin."""
    for t in sent:
        if t.text.lower() not in VOORBEHOUD:
            continue
        in_bijzin = t.dep_ == "acl:relcl" or any(
            a.dep_ == "acl:relcl" for a in t.ancestors
        )
        if not in_bijzin:
            return True
    return False


def verwijder_haakjes(tekst):
    """Haalt (...) weg, ook als er haakjes in haakjes staan."""
    vorige = None
    while vorige != tekst:
        vorige = tekst
        tekst = re.sub(r"\s*\([^()]*\)", "", tekst)
    return tekst


def is_tegenwoordig(tok):
    return "Pres" in tok.morph.get("Tense")


def onderwerp_frase(subj):
    """Onderwerp plus woorden eraan vast ('machine learning')."""
    links = [
        c for c in subj.children
        if c.i < subj.i and (
            c.dep_ in ("compound", "flat")
            or (c.dep_ == "nmod" and c.pos_ in ("NOUN", "PROPN"))
        )
    ]
    links.sort(key=lambda c: c.i)
    return " ".join([c.text for c in links] + [subj.text]).lower()


def is_vaag(frase):
    return any(w in VAGE_WOORDEN for w in frase.split())


def heeft_een(tok):
    """Staat er 'een' voor het doel (of voor 'soort/type' ervoor)?"""
    if any(c.dep_ == "det" and c.text.lower() == "een" for c in tok.children):
        return True
    for c in tok.children:
        if c.dep_ == "nmod" and c.lemma_ in ("soort", "type"):
            if any(g.dep_ == "det" and g.text.lower() == "een" for g in c.children):
                return True
    return False


def zoek_is_a(sent, zoek):
    out = []
    for tok in sent:
        if tok.dep_ != "ROOT" or tok.pos_ != "NOUN":
            continue
        # Regel 4: kern mag niet aan een voorzetsel hangen ("is in opkomst")
        if any(c.dep_ == "case" for c in tok.children):
            continue
        # Regel 3: koppelwerkwoord 'zijn' in de tegenwoordige tijd
        cops = [c for c in tok.children
                if c.dep_ == "cop" and c.lemma_ == "zijn" and is_tegenwoordig(c)]
        subjs = [c for c in tok.children
                 if c.dep_ == "nsubj" and c.pos_ in ("NOUN", "PROPN")]
        if not cops or not subjs:
            continue
        frase = onderwerp_frase(subjs[0])
        # Regel 1: onderwerp is (of bevat) het opgezochte woord
        if zoek and zoek not in frase:
            continue
        # Regel 5: vage woorden
        if is_vaag(frase):
            continue
        doelen = [tok] + [c for c in tok.children
                          if c.dep_ == "conj" and c.pos_ == "NOUN"]
        for d in doelen:
            doel = d.text.lower()
            # Regel 2: 'een' ervoor. Regel 5: niet vaag. Regel 6: niet gelijk.
            if not heeft_een(d) or doel in VAGE_WOORDEN:
                continue
            if doel == frase or doel == subjs[0].text.lower():
                continue
            out.append((frase, "is_a", doel))
    return out


def zoek_has_part(sent, zoek):
    out = []
    for tok in sent:
        if tok.pos_ != "VERB" or tok.lemma_ != "bestaan" or not is_tegenwoordig(tok):
            continue
        subjs = [c for c in tok.children
                 if c.dep_ == "nsubj" and c.pos_ in ("NOUN", "PROPN")]
        if not subjs:
            continue
        frase = onderwerp_frase(subjs[0])
        if zoek and zoek not in frase:
            continue
        if is_vaag(frase):
            continue
        for obl in [c for c in tok.children if c.dep_ == "obl"]:
            if not any(g.dep_ == "case" and g.text.lower() == "uit"
                       for g in obl.children):
                continue
            delen = [obl] + [c for c in obl.children if c.dep_ == "conj"]
            for d in delen:
                deel = d.text.lower()
                if deel in VAGE_WOORDEN or deel == frase:
                    continue
                out.append((frase, "has_part", deel))
    return out


def analyseer_zin(sent, zoek):
    if heeft_voorbehoud(sent):
        return [], "voorbehoud/ontkenning"
    return zoek_is_a(sent, zoek) + zoek_has_part(sent, zoek), None


def haal_wikipedia(woord):
    titel = woord[0].upper() + woord[1:]
    params = {
        "action": "query", "prop": "extracts", "explaintext": 1,
        "exintro": 1, "redirects": 1, "format": "json", "titles": titel,
    }
    url = "https://nl.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url, headers={"User-Agent": "NovaAI-verkenning/0.3 (hobbyproject, lokaal)"}
    )
    for poging in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.load(r)
            pagina = next(iter(data["query"]["pages"].values()))
            return pagina.get("extract", "")
        except urllib.error.HTTPError as e:
            if e.code == 429 and poging == 1:
                print(f"  (429 te veel aanvragen, wacht 15 seconden en probeer opnieuw)")
                time.sleep(15)
                continue
            raise


def main():
    nlp = spacy.load(MODEL_NAAM)

    print("=" * 70)
    print("DEEL A: TESTZINNEN (zonder opgezocht woord)")
    print("=" * 70)
    for zin in EXTRA_ZINNEN:
        doc = nlp(zin)
        for sent in doc.sents:
            feiten, skip = analyseer_zin(sent, None)
            if skip:
                print(f"OVERGESLAGEN ({skip}): {zin}")
            elif feiten:
                for f in feiten:
                    print(f"VOORSTEL {f}   <= {zin}")
            else:
                print(f"geen voorstel: {zin}")

    print("\n" + "=" * 70)
    print("DEEL B: WIKIPEDIA-INLEIDINGEN")
    print("=" * 70)
    totaal_voorstellen = 0
    woorden_zonder = []
    for woord in WIKI_WOORDEN:
        try:
            tekst = haal_wikipedia(woord)
        except Exception as e:
            print(f"\n[{woord}] ophalen mislukt: {e}")
            continue
        time.sleep(PAUZE_SECONDEN)
        if not tekst:
            print(f"\n[{woord}] geen tekst gevonden")
            continue

        print(f"\n### {woord} ({len(tekst)} tekens)")
        if len(tekst) < 200:
            print(f"  korte tekst: {tekst!r}")
        doc = nlp(verwijder_haakjes(tekst))
        zinnen = list(doc.sents)
        aantal = 0
        for nr, sent in enumerate(zinnen):
            feiten, skip = analyseer_zin(sent, woord)
            if skip and (zoek_is_a(sent, woord) or zoek_has_part(sent, woord)):
                print(f"  OVERGESLAGEN ({skip}): {sent.text.strip()[:100]}")
            for f in feiten:
                aantal += 1
                print(f"  VOORSTEL {f}   <= {sent.text.strip()[:80]}")
            if nr == 0 and not feiten:
                reden = skip or "geen regel paste"
                print(f"  [eerste zin gaf niets: {reden}] {sent.text.strip()[:160]}")
        totaal_voorstellen += aantal
        if aantal == 0:
            woorden_zonder.append(woord)

    print("\n" + "=" * 70)
    print(f"TOTAAL: {totaal_voorstellen} voorstellen over {len(WIKI_WOORDEN)} woorden")
    print(f"Woorden zonder enig voorstel: {', '.join(woorden_zonder) or '(geen)'}")


if __name__ == "__main__":
    main()