📘 Semantic v2 — Architectuurdocument
Architectuur, interne engines en datastromen voor Nova’s nieuwe semantische kern

🧠 1. Overzicht
Semantic v2 is de centrale kennis‑ en begripslaag van Nova.
Ze beheert:

concepten

senses

definities

relationele kennis

voorbeelden

brontracking

confidence‑scores

audit‑logging

En vormt de basis voor:

teach‑flows

auto‑learn

relationele zinnen

reasoning (Fase 7)

toekomstige Wikipedia‑module

De module is opgebouwd uit gescheiden engines, elk verantwoordelijk voor één domein.
De hoofdmodule (SemanticConceptsModule) is enkel een coördinator.

🧱 2. Architectuurdiagram
Code
SemanticConceptsModule
│
├── ConceptStore
│     ├── load/save
│     ├── ensure_concept
│     ├── audit_log (concept)
│     └── metadata beheer
│
├── SenseEngine
│     ├── add_sense
│     ├── upgrade_unknown_sense
│     ├── get_senses
│     ├── get_best_definition
│     └── audit_log (sense)
│
├── RelationEngine
│     ├── add_relation
│     ├── get_relations
│     ├── is_a
│     └── duplicate-check
│
├── TeachEngine
│     ├── teach
│     ├── auto_learn
│     └── bron + confidence beheer
│
├── RelationParser
│     ├── detect_relation
│     └── parse_relation
│
└── RelationFlowEngine
      ├── start_relation_flow
      ├── handle_sense_choice
      └── handle_confirm
🧩 3. Componenten in detail
3.1 ConceptStore
Rol: opslaglaag voor concepts.json.

Verantwoordelijkheden
Laden en opslaan van alle concepten

ensure_concept(word)

Metadata beheren (created_at, updated_at, sources)

Concept‑niveau audit‑logging

File‑IO isoleren van de rest van semantic

Waarom?
Dit maakt semantic:

testbaar

uitbreidbaar

veilig tegen corruptie

modulair

3.2 SenseEngine
Rol: beheer van senses binnen één concept.

Verantwoordelijkheden
Nieuwe senses aanmaken

Unknown senses upgraden

Beste definitie kiezen

Sense‑audit bijhouden

POS, examples, confidence beheren

Waarom?
Senses zijn de kern van semantisch begrip.
Elke relation, definitie en reasoning‑stap werkt op sense‑niveau.

3.3 RelationEngine
Rol: relationele kennis opslaan en opvragen.

Verantwoordelijkheden
Relaties toevoegen aan een sense

Duplicate‑check

get_relations(word)

is_a(source, target)

Voorbereid op reasoning‑chaining

Waarom?
Relationele kennis is de basis voor:

categorisatie

inference

reasoning

contextbegrip

3.4 TeachEngine
Rol: alle leerprocessen bundelen.

Verantwoordelijkheden
teach(word, definition)

auto_learn(word)

Bronbeheer (user, auto, wikipedia)

Confidence‑beheer

Audit‑logging voor leeracties

Waarom?
Teach is de primaire manier waarop Nova kennis opbouwt.
Auto‑learn maakt Nova adaptief.

3.5 RelationParser
Rol: relationele zinnen analyseren.

Verantwoordelijkheden
Patronen detecteren

Subject/object extraheren

Lidwoorden strippen

Klaar voor uitbreidingen

Waarom?
Dit is de brug tussen natuurlijke taal en relationele kennis.

3.6 RelationFlowEngine
Rol: interactieve flow voor relationele zinnen.

Verantwoordelijkheden
Pending relation state beheren

Sense‑choice flow

Confirm‑flow

EventBus‑interactie (chat_response)

Waarom?
Nova moet ambiguïteit oplossen via dialoog, niet gokken.

🧠 4. Datamodel
4.1 Concept‑object
json
{
  "woord": {
    "senses": [...],
    "metadata": {
      "created_at": "...",
      "updated_at": "...",
      "sources": ["user"]
    },
    "audit_log": []
  }
}
4.2 Sense‑object
json
{
  "sense_id": "woord#1",
  "definition": "een dier dat blaft",
  "pos": "noun",
  "examples": ["De hond blaft."],
  "relations": [
    {"type": "is_a", "target": "dier"},
    {"type": "related_to", "target": "kat"}
  ],
  "source": "user",
  "confidence": 1.0,
  "audit_log": []
}
🔄 5. Datastromen
5.1 Teach‑flow
Code
teach() → SenseEngine.add_sense → ConceptStore.save → event: concept_learned
5.2 Auto‑learn
Code
auto_learn() → unknown sense → later upgrade via teach()
5.3 Relationele zin
Code
Parser.detect → Parser.parse → FlowEngine.start → (sense-choice?) → confirm → RelationEngine.add_relation
5.4 Query
Code
get_meaning → SenseEngine.get_best_definition
get_relations → RelationEngine.get_relations
is_a → RelationEngine.is_a
🧪 6. Teststrategie
Unit tests per engine

Integration tests: chat.py → semantic

Stress tests: 10k concepten, 50k relaties

Fuzz tests: parser robustness

🧭 7. Toekomstige uitbreidingen
Wikipedia‑module

Reasoning‑chaining

Contradiction detection

Confidence‑propagation

Contextuele senses

Vector‑achtige similarity (zonder ML)

🏁 8. Conclusie
Semantic v2 is:

modulair

schaalbaar

uitbreidbaar

volledig Nederlands

dictionary‑vrij

klaar voor reasoning

klaar voor Wikipedia

klaar voor Nova v1.0