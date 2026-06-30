import json
from collections import Counter

logfile = "logs/concepts.jsonl"

stats = Counter()
per_word = {}

with open(logfile, "r", encoding="utf-8") as f:
    for line in f:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        status = entry.get("status")
        word = entry.get("word")

        if status:
            stats[status] += 1
        if word:
            per_word.setdefault(word, Counter())[status] += 1

print("=== Totale audit ===")
for k, v in stats.items():
    print(f"{k}: {v}")

print("\n=== Per woord ===")
for w, c in per_word.items():
    print(f"{w}: {dict(c)}")
