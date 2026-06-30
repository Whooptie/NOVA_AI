import json
import os
import argostranslate.package
import argostranslate.translate

SOURCE = r"C:\Nova_AI\data\lexicons\nl_wiktextract.json"
TARGET = r"C:\Nova_AI\data\lexicons\nl_wikt_index.json"

# zorg dat EN->NL geïnstalleerd is via de CLI
installed_languages = argostranslate.translate.get_installed_languages()
en = next((l for l in installed_languages if l.code == "en"), None)
nl = next((l for l in installed_languages if l.code == "nl"), None)
translator = en.get_translation(nl) if en and nl else None

def translate_gloss(text: str) -> str:
    if not translator:
        return text
    try:
        return translator.translate(text)
    except:
        return text

def build_index():
    index = {}

    with open(SOURCE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
            except:
                continue

            if not isinstance(obj, dict):
                continue

            if obj.get("lang") != "Dutch" and obj.get("lang_code") != "nl":
                continue

            word = obj.get("word", "").lower()
            if not word:
                continue

            senses = obj.get("senses", [])
            if not senses:
                continue

            s0 = senses[0]

            gloss = s0.get("gloss")
            if not gloss:
                glosses = s0.get("glosses")
                if glosses and isinstance(glosses, list):
                    gloss = glosses[0]

            if not gloss:
                continue

            nl_gloss = translate_gloss(gloss)

            examples = []
            for ex in s0.get("examples", []):
                txt = ex.get("text")
                if txt:
                    examples.append(txt)

            synonyms = []
            for syn in s0.get("synonyms", []):
                w = syn.get("word")
                if w:
                    synonyms.append(w)

            index[word] = {
                "definition": nl_gloss,
                "examples": examples,
                "synonyms": synonyms
            }

    with open(TARGET, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    print("Index built:", len(index), "entries")

if __name__ == "__main__":
    build_index()
