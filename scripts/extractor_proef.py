"""
extractor_proef.py -- live proef voor Fase 11.1

Haalt per woord de Wikipedia-inleiding op en toont wat de extractor
VOORSTELT. Er wordt niets opgeslagen.

Gebruik (in de container):
    docker exec nova-ai python scripts/extractor_proef.py
    docker exec nova-ai python scripts/extractor_proef.py fiets gitaar
"""
import sys
import time
import json
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.knowledge.knowledge_extractor import KnowledgeExtractor

STANDAARD_WOORDEN = ["fiets", "gitaar", "hond", "narwal", "vulkaan",
                     "computer", "vliegtuig", "auto", "kat", "water"]
PAUZE_SECONDEN = 2
USER_AGENT = "NovaAI/1.0 (lokale companion; extractor-proef)"


def haal_wikipedia(woord):
    """Een request per woord. Bij HTTP 429: 15 s wachten, 1x opnieuw."""
    params = urllib.parse.urlencode({
        "action": "query", "prop": "extracts", "exintro": 1,
        "explaintext": 1, "redirects": 1, "format": "json", "titles": woord,
    })
    url = f"https://nl.wikipedia.org/w/api.php?{params}"
    for poging in (1, 2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.load(r)
            pagina = next(iter(data["query"]["pages"].values()))
            return pagina.get("extract", "")
        except urllib.error.HTTPError as e:
            if e.code == 429 and poging == 1:
                print("  (te veel requests, 15 s wachten...)")
                time.sleep(15)
                continue
            print(f"  FOUT: HTTP {e.code}")
            return ""
        except Exception as e:
            print(f"  FOUT: {type(e).__name__}: {e}")
            return ""
    return ""


def main():
    woorden = sys.argv[1:] or STANDAARD_WOORDEN
    ex = KnowledgeExtractor()
    if not ex.is_beschikbaar():
        print(f"Extractor niet beschikbaar: {ex.reden_uit}")
        return
    totaal = 0
    zonder = []
    for woord in woorden:
        print(f"\n### {woord}")
        tekst = haal_wikipedia(woord)
        if tekst:
            voorstellen = ex.extract_from_text(tekst, zoekwoord=woord)
        else:
            voorstellen = []
        for v in voorstellen:
            print(f"  VOORSTEL ({v['onderwerp']}, {v['relatie']}, {v['doel']})"
                  f"   <= {v['zin'][:90]}")
        if not voorstellen:
            zonder.append(woord)
        totaal += len(voorstellen)
        time.sleep(PAUZE_SECONDEN)
    print(f"\nTOTAAL: {totaal} voorstellen over {len(woorden)} woorden")
    if zonder:
        print("Woorden zonder voorstel:", ", ".join(zonder))


if __name__ == "__main__":
    main()