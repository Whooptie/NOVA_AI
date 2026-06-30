📘 Semantic v2 API (definitieve versie)
(Dit wordt een apart semantic_api.md in jouw repo)

🧱 1. Concept & Sense Management
create_concept
create_concept(word: str) -> dict

Maakt een nieuw concept aan met lege senses.

Wordt intern gebruikt door teach/auto‑learn.

add_sense
add_sense(word: str, definition: str, source="user", confidence=1.0) -> dict

Maakt een nieuwe sense aan.

Wordt gebruikt door teach, Wikipedia‑import, reasoning‑inference.

upgrade_unknown_sense
upgrade_unknown_sense(word: str, definition: str) -> dict

Als een woord "unknown" had → upgrade naar echte definitie.

Belangrijk voor auto‑learn → teach → reasoning.

get_senses
get_senses(word: str) -> list[dict]

Haalt alle senses op.

Wordt gebruikt door chat.py, UI, reasoning.

get_meaning
get_meaning(word: str) -> str | None

Geeft de “beste” definitie terug.

Later uitbreidbaar met confidence‑ranking.

🔗 2. Relation Engine
add_relation
add_relation(subject: str, relation_type: str, target: str, sense_id=None) -> bool

Voegt relation toe aan een specifieke sense.

Duplicate‑check.

Audit‑log.

get_relations
get_relations(word: str, relation_type=None) -> list[str]

Haalt alle relaties op.

Wordt gebruikt door intent_related_to, reasoning, UI.

is_a
is_a(source: str, target: str) -> bool

Checkt directe is_a.

Later uitbreidbaar naar chaining (reasoning).

🧠 3. Learning Engine
teach
teach(word: str, definition: str) -> dict

Primaire manier waarop Nova leert.

Bron = user.

Confidence = 1.0.

auto_learn
auto_learn(word: str) -> dict

Onbekend woord → "unknown" sense.

Bron = auto.

Confidence = 0.1.

learn_from_sentence
learn_from_sentence(sentence: str)

Detecteert relationele patronen.

Start sense‑choice of confirm‑flow.

Wordt aangeroepen door intent_router of chat_message.

🧩 4. Flow Engine (Sense‑choice & Confirm)
start_relation_flow
start_relation_flow(subject, relation_type, object)

Zet pending state.

Start sense‑choice of confirm.

handle_sense_choice
handle_sense_choice(user_input: str)

Gebruiker kiest sense.

Audit‑log.

Gaat naar confirm‑flow.

handle_confirm
handle_confirm(user_input: str)

“ja” → relation opslaan

“nee” → pending wissen

Audit‑log.

🗂️ 5. Storage Engine
save
save() -> None

Schrijft concepts.json weg.

load
load() -> dict

Laadt concepts.json.

export_concept
export_concept(word: str) -> dict

Voor UI/debugging.

🧪 6. Query Engine
has_concept
has_concept(word: str) -> bool

search
search(query: str) -> list[str]

Simpele zoekfunctie voor UI.

Later uitbreidbaar naar fuzzy matching.

⭐ Dit is de volledige Semantic v2 API
Met deze API kan Nova:

woorden leren

definities opslaan

senses beheren

relaties begrijpen

relationele zinnen verwerken

reasoning ondersteunen

Wikipedia‑data integreren

UI‑tools bouwen

chat.py en intent_router blijven gebruiken

Dit is de officiële interface waar alle andere modules op vertrouwen.