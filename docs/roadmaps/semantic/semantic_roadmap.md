🚀 Semantic v2.0 — COMPLETE TO‑DO LIST (1‑bestand versie)
🧱 FASE 1 — Datastructuur & opslag (bijna klaar)
Status: 95% klaar  
Nog te doen:

Audit‑log uitbreiden

Metadata uitbreiden (brontracking, update‑tracking)

Sense‑ID generator verbeteren

Relation‑object standaardiseren

🧠 FASE 2 — Teach & Auto‑Learn (bijna klaar)
Status: 90% klaar  
Nog te doen:

TeachEngine herschrijven (clean, modulair, future‑proof)

Examples‑engine toevoegen

Sense‑upgrade uitbreiden (confidence, audit)

POS‑tagging uitbreiden (300 werkwoorden, betere adj‑detectie)

Plural‑logic finaliseren (incl. irregulars)

🔗 FASE 3 — Relation Engine (gedeeltelijk klaar)
Status: 70% klaar  
Nog te doen:

Relation‑types uitbreiden (property_of, used_for, causes, instance_of)

Relation‑parser uitbreiden (meer patronen)

Relation‑flow audit‑logging

Relation‑deduplicatie verbeteren

Relation‑normalisatie (lemmatisatie)

🔍 FASE 4 — Query Engine (basis klaar)
Status: 80% klaar  
Nog te doen:

Query: related_to uitbreiden

Query: synonyms/antonyms

Query: multi‑sense ranking

Query: fallback‑strategie verbeteren

🔌 FASE 5 — Integratie (bijna klaar)
Status: 85% klaar  
Nog te doen:

IntentRouter uitbreiden met nieuwe semantic intents

Chat.py semantic‑aware maken

Response pipeline semantic‑aware maken

📚 FASE 6 — Wikipedia‑module (optioneel, maar voorbereid)
Status: 0%  
Nog te doen:

Wikipedia‑importer ontwerpen

Wikipedia‑parser bouwen

Wikipedia‑relation‑extractie

Wikipedia‑confidence‑model

🧠 FASE 7 — Reasoning Layer (grote stap)
Status: 0%  
Nog te doen:

Chaining engine

Inference engine

Contradiction detection

Relation propagation

Sense‑ranking op basis van context

🧩 DE UITGEBREIDE TO‑DO LIJST (met concrete implementatie‑taken)
Hier is de volledige lijst van ALLES wat nog moet gebeuren om semantic.py:

volledig

stabiel

schaalbaar

reasoning‑ready

Wikipedia‑ready

context‑aware

te maken.

🧱 FASE 1 — Datastructuur (detail)
1.1 Audit‑log uitbreiden
timestamp

event_type (teach, auto_learn, relation_add, upgrade, example_add)

old_value / new_value

source

1.2 Metadata uitbreiden
last_used_at

usage_count

confidence_history

1.3 Sense‑ID generator verbeteren
geen gaten (bank#1, bank#2, bank#4 → fout)

consistentie bij verwijderen

1.4 Relation‑object standaardiseren
type

target

confidence

source

created_at

🧠 FASE 2 — Teach & Auto‑Learn (detail)
2.1 TeachEngine herschrijven
clean architecture

plural‑logic

example‑logic

sense‑upgrade

audit‑logging

2.2 Examples‑engine
detect example‑zinnen

opslaan per sense

example‑ranking

2.3 Sense‑upgrade uitbreiden
confidence verhogen

audit‑entry

bron aanpassen

2.4 POS‑tagging uitbreiden
300 werkwoorden

200 adjectieven

irregular verbs

irregular plurals

2.5 Plural‑logic finaliseren
kinderen → kind

mensen → mens

eieren → ei

huizen → huis

🔗 FASE 3 — Relation Engine (detail)
3.1 Relation‑types uitbreiden
property_of

instance_of

used_for

causes

3.2 Relation‑parser uitbreiden
“X bestaat uit Y” → part_of

“X wordt gebruikt voor Y” → used_for

“X veroorzaakt Y” → causes

“X is een eigenschap van Y” → property_of

3.3 Relation‑flow audit‑logging
sense_choice

confirm

relation_added

3.4 Relation‑deduplicatie verbeteren
per sense

per relation_type

per target

3.5 Relation‑normalisatie
lemmatisatie

lowercase

plural‑normalisatie

🔍 FASE 4 — Query Engine (detail)
4.1 related_to uitbreiden
synonyms

antonyms

part_of

is_a

4.2 synonyms/antonyms queries
ranking

fallback

4.3 multi‑sense ranking
confidence

usage_count

context (later)

4.4 fallback‑strategie
unknown → ask user

no senses → auto_learn

🔌 FASE 5 — Integratie (detail)
5.1 IntentRouter uitbreiden
intent_related_to

intent_synonym

intent_antonym

5.2 Chat.py semantic‑aware
context‑aware definities

relation‑aware antwoorden

5.3 Pipeline semantic‑aware
semantic → content

pipeline → stijl

📚 FASE 6 — Wikipedia (detail)
6.1 Wikipedia‑importer
API

caching

throttling

6.2 Wikipedia‑parser
definities

categorieën

eigenschappen

6.3 Relation‑extractie
hyperlinks → related_to

infobox → properties

6.4 Confidence‑model
wikipedia = 0.8

user = 1.0

auto = 0.1

🧠 FASE 7 — Reasoning Layer (detail)
7.1 Chaining engine
A is_a B

B is_a C
→ A is_a C

7.2 Inference engine
X causes Y

Y causes Z
→ X causes Z

7.3 Contradiction detection
X is_a dier

X is_a meubel
→ conflict

7.4 Relation propagation
synonyms delen relaties

7.5 Context‑based sense ranking
zinscontext

relation‑context