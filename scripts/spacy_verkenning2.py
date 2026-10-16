"""
spacy_verkenning2.py -- Semantic Fase 11, stap 0, ronde 2

Doel: onze eerste, MINIMALE regels (is_a en has_part) uitproberen op
extra zinnen en op echte Nederlandse Wikipedia-tekst. Schrijft niets
weg en wijzigt NIETS aan Nova.

Draaien:
    docker exec nova-ai python scripts/spacy_verkenning2.py
    docker exec nova-ai python scripts/spacy_verkenning2.py --volledig
(--volledig = hele artikel i.p.v. enkel de inleiding)
"""

import json
import sys
import urllib.parse
import urllib.request

import spacy

MODEL_NAAM = "nl_core_news_sm"
VOLLEDIG = "--volledig" in sys.argv

EXTRA_ZINNEN = [
    "Honden zijn zoogdieren.",
    "Een gitaar is een snaarinstrument en een muziekinstrument.",
    "Een zeilboot is een soort vaartuig.",
    "Een vulkaan is een berg waaruit lava komt.",
    "Machine learning is een vakgebied binnen de informatica.",
    "Een wiel maakt deel uit van een auto.",
    "Een auto heeft vier wielen.",
    "Regen leidt tot modder.",
    "Een mes wordt gebruikt om te snijden.",
    "Een kat is meestal een huisdier.",
]

WIKI_WOORDEN = ["hond", "fiets", "gitaar", "narwal", "vulkaan", "democratie"]

# Woorden die een zin onbetrouwbaar maken (ontkenning/voorbehoud)
VOORBEHOUD = {
    "niet", "geen", "nooit", "soms", "meestal", "vaak", "bijna",
    "vrijwel", "kan", "kunnen", "mogelijk", "waarschijnlijk",
}


def heeft_voorbehoud(sent):
    return any(t.text.lower() in VOORBEHOUD for t in sent)


def zoek_is_a(sent):
    gevonden = []
    for tok in sent:
        if tok.dep_ != "ROOT" or tok.pos_ not in ("NOUN", "PROPN"):
            continue
        cops = [c for c in tok.children if c.dep_ == "cop" and c.lemma_ == "zijn"]
        subjs = [c for c in tok.children if c.dep_ == "nsubj"]
        if not cops or not subjs:
            continue
        if subjs[0].pos_ not in ("NOUN", "PROPN"):
            continue  # voornaamwoord (het, hij, ...) overslaan
        doelen = [tok] + [c for c in tok.children
                          if c.dep_ == "conj" and c.pos_ == "NOUN"]
        for d in doelen:
            gevonden.append((subjs[0].text.lower(), "is_a", d.text.lower()))
    return gevonden


def zoek_has_part(sent):
    gevonden = []
    for tok in sent:
        if tok.pos_ != "VERB" or tok.lemma_ != "bestaan":
            continue
        subjs = [c for c in tok.children if c.dep_ == "nsubj"]
        if not subjs:
            continue
        for obl in [c for c in tok.children if c.dep_ == "obl"]:
            if not any(g.dep_ == "case" and g.text.lower() == "uit"
                       for g in obl.children):
                continue
            delen = [obl] + [c for c in obl.children if c.dep_ == "conj"]
            for d in delen:
                gevonden.append((subjs[0].text.lower(), "has_part", d.text.lower()))
    return gevonden


def analyseer_zin(sent):
    """Geeft (lijst feiten, reden-om-over-te-slaan of None)."""
    if heeft_voorbehoud(sent):
        return [], "voorbehoud/ontkenning"
    feiten = zoek_is_a(sent) + zoek_has_part(sent)
    return feiten, None


def haal_wikipedia(woord):
    titel = woord[0].upper() + woord[1:]
    params = {
        "action": "query", "prop": "extracts", "explaintext": 1,
        "redirects": 1, "format": "json", "titles": titel,
    }
    if not VOLLEDIG:
        params["exintro"] = 1
    url = "https://nl.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "NovaAI-verkenning/0.1"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.load(r)
    pagina = next(iter(data["query"]["pages"].values()))
    return pagina.get("extract", "")


def main():
    nlp = spacy.load(MODEL_NAAM)

    print("=" * 70)
    print("DEEL A: EXTRA ZINNEN")
    print("=" * 70)
    for zin in EXTRA_ZINNEN:
        doc = nlp(zin)
        print(f"\n{zin}")
        print("  " + "  ".join(f"{t.text}:{t.pos_}:{t.dep_}>{t.head.text}" for t in doc))
        for sent in doc.sents:
            feiten, skip = analyseer_zin(sent)
            if skip:
                print(f"  -> OVERGESLAGEN ({skip})")
            elif feiten:
                for f in feiten:
                    print(f"  -> VOORSTEL: {f}")
            else:
                print("  -> geen patroon")

    print("\n" + "=" * 70)
    print("DEEL B: ECHTE WIKIPEDIA-TEKST" + (" (volledig)" if VOLLEDIG else " (inleiding)"))
    print("=" * 70)
    totaal = {"zinnen": 0, "voorstellen": 0, "overgeslagen": 0}
    for woord in WIKI_WOORDEN:
        try:
            tekst = haal_wikipedia(woord)
        except Exception as e:
            print(f"\n[{woord}] ophalen mislukt: {e}")
            continue
        if not tekst:
            print(f"\n[{woord}] geen tekst gevonden")
            continue
        print(f"\n### {woord} ({len(tekst)} tekens)")
        doc = nlp(tekst)
        for sent in doc.sents:
            totaal["zinnen"] += 1
            feiten, skip = analyseer_zin(sent)
            if skip:
                if zoek_is_a(sent) or zoek_has_part(sent):
                    totaal["overgeslagen"] += 1
                    print(f"  OVERGESLAGEN ({skip}): {sent.text.strip()[:110]}")
            elif feiten:
                for f in feiten:
                    totaal["voorstellen"] += 1
                    print(f"  VOORSTEL {f}   <= {sent.text.strip()[:90]}")

    print("\n" + "=" * 70)
    print(f"TOTAAL: {totaal['zinnen']} zinnen, {totaal['voorstellen']} voorstellen, "
          f"{totaal['overgeslagen']} overgeslagen door voorbehoud")


if __name__ == "__main__":
    main()