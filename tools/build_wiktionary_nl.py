import json
import os
import urllib.request
import subprocess

DUMP_URL = "https://dumps.wikimedia.org/nlwiktionary/latest/nlwiktionary-latest-pages-articles.xml.bz2"
DUMP_FILE = r"C:\Nova_AI\data\lexicons\wiktionary_dump.xml.bz2"
RAW_JSON = r"C:\Nova_AI\data\lexicons\wiktionary_raw.json"
OUTPUT_JSON = r"C:\Nova_AI\data\lexicons\wiktionary_nl.json"

def download_dump():
    os.makedirs(os.path.dirname(DUMP_FILE), exist_ok=True)
    print("Dump downloaden...")
    urllib.request.urlretrieve(DUMP_URL, DUMP_FILE)
    print("Download klaar.")

def run_wiktextract():
    print("wiktextract uitvoeren (dit duurt even)...")
    cmd = [
        "wiktextract",
        "--json-output", RAW_JSON,
        DUMP_FILE
    ]
    subprocess.run(cmd, check=True)
    print("wiktextract klaar.")

def filter_dutch():
    print("NL entries filteren...")
    result = {}

    with open(RAW_JSON, "r", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)

            if entry.get("lang") != "Dutch":
                continue

            word = entry.get("word", "").lower().strip()
            if not word:
                continue

            senses = entry.get("senses", [])
            if not senses:
                continue

            gloss = None
            examples = []
            synonyms = []

            for sense in senses:
                if not gloss and sense.get("glosses"):
                    gloss = sense["glosses"][0]

                if sense.get("examples"):
                    examples.extend(sense["examples"])

                if sense.get("synonyms"):
                    synonyms.extend(sense["synonyms"])

            if not gloss:
                continue

            result[word] = {
                "definition": gloss,
                "synonyms": synonyms,
                "examples": examples,
                "pos": entry.get("pos")
            }

    print(f"Totaal NL lemma's: {len(result)}")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("Klaar! Bestand opgeslagen:", OUTPUT_JSON)

def main():
    if not os.path.exists(DUMP_FILE):
        download_dump()

    run_wiktextract()
    filter_dutch()

if __name__ == "__main__":
    main()
