# 🧠 Reasoning Engine — losse uitbreidingsideeën (niet in officiële roadmap)

> Aangemaakt: 12 juli 2026
> Status: PLANNING — losse ideeën, géén onderdeel van semantic_roadmap.md of semantic_extension_roadmap.md
> Context: ontstaan tijdens gesprek over `part_of_chained`/`get_all_subtypes` (zie nova_state.md, Fase 7 §7.5)

---

## Waarom dit document?

Tijdens het bouwen en testen van `part_of_chained` en `get_all_subtypes` (12 juli 2026) kwamen 6 losse uitbreidingsideeën naar boven. Bij controle bleek dat deze **niet (volledig) samenvallen** met de al geplande Fases 8-13 uit `semantic_extension_roadmap.md`. Om ze niet verloren te laten gaan, maar ook niet zomaar in de officiële roadmap te proppen zonder Kevin's expliciete keuze, staan ze hier apart genoteerd.

**Belangrijk:** dit is geen bouwvolgorde, geen toezegging — puur een ideeënlijst om later uit te kiezen.

---

## De 6 ideeën

### 1. `get_all_parts` — spiegelbeeld van get_all_subtypes
**Type:** pure symbolisch, kleine moeite
**Wat:** het omgekeerde van `get_all_subtypes`, maar dan voor `part_of` i.p.v. `is_a`. Gegeven een concept (bv. `fiets`), geef alle onderdelen terug die er direct of via een keten toe behoren (wiel, stuur, zadel, ketting, ...).
**Implementatie:** vrijwel identiek aan `get_all_subtypes()`, maar met `part_of_chained()` in plaats van `is_a_chained()`. Hergebruikt dus bijna alle bestaande code.
**Relatie tot officiële roadmap:** staat niet expliciet vermeld, maar is een logisch, natuurlijk vervolg op wat al gebouwd is (12 juli 2026).

### 2. `related_to_chained` — keten-redenering voor related_to
**Type:** pure symbolisch
**Wat:** momenteel hebben alleen `is_a`, `causes` en `part_of` een keten-versie (`*_chained`). `related_to` heeft dat nog niet.
**Kanttekening:** conceptueel wat vager dan de andere drie, want `related_to` is losser/symmetrischer van aard — een lange keten van "gerelateerde" concepten zou snel weinig betekenisvol worden (bv. na 4-5 stappen ben je overal en nergens gerelateerd aan).
**Relatie tot officiële roadmap:** raakt gedeeltelijk aan Fase 7.4 "Relation propagation" (semantic_roadmap.md) — "synoniemen delen relaties" — maar is niet identiek.

### 3. Contradictiedetectie uitbreiden naar part_of-loops
**Type:** pure symbolisch
**Wat:** `find_contradictions()` bestaat al en checkt incompatibele `is_a`-categorieën (bv. iets kan niet tegelijk `dier` en `meubel` zijn). Uitbreiding: ook onmogelijke `part_of`-cirkels detecteren (bv. "gitaar part_of snaar" én "snaar part_of gitaar" tegelijk — een logische onmogelijkheid).
**Relatie tot officiële roadmap:** raakt aan Fase 8 "Causal Reasoning" (semantic_extension_roadmap.md), maar die fase is breder opgezet (sterktes/gewichten aan relaties, meerdere stappen diepe causale ketens) dan enkel deze ene contradictie-check.

### 4. Multi-hop vragen combineren
**Type:** pure symbolisch, grotere combinatie-opzet
**Wat:** bijvoorbeeld "welke onderdelen van een fiets zijn rond?" zou `get_all_parts(fiets)` (idee #1) moeten combineren met een `property_of`-check per gevonden onderdeel. Vereist twee of meer bestaande queries na elkaar te schakelen, met een nieuwe combinatielaag erboven.
**Relatie tot officiële roadmap:** niet vermeld in bestaande roadmap-documenten.

### 5. "Waarom niet"-uitleg bij een negatief antwoord
**Type:** pure symbolisch, kleine uitbreiding met grote gebruikswaarde
**Wat:** momenteel geeft `explain_is_a()` bij een `False`-resultaat enkel *"Ik kan niet bewijzen dat X een Y is."* Uitbreiding: als er wél een `is_a`-relatie bestaat maar naar een ánder concept, dat expliciet benoemen. Voorbeeld: "is een octopus een zoogdier?" → nee, maar Nova zou dan kunnen zeggen: *"Nee, een octopus is geen zoogdier — een octopus is wel een weekdier."*
**Waarom interessant:** dit hergebruikt puur bestaande bouwstenen (`is_a_chained` + `get_relations`) en maakt Nova's antwoorden merkbaar rijker zonder nieuwe complexiteit.
**Relatie tot officiële roadmap:** niet vermeld — eigen idee, geen officieel geplande fase.

### 6. Vergelijkingen tussen twee concepten
**Type:** pure symbolisch, grotere combinatie-opzet
**Wat:** bijvoorbeeld "wat is het verschil tussen een hond en een kat?" zou kunnen kijken naar hun gedeelde en niet-gedeelde `is_a`-ouders/relaties (bv. beide `is_a → zoogdier`, maar verder verschillende specifieke ouders).
**Relatie tot officiële roadmap:** niet vermeld in bestaande roadmap-documenten.

---

## Kort overzicht: overlap met bestaande roadmap

| Idee | Zit in officiële roadmap? |
| --- | --- |
| 1. get_all_parts | ❌ Niet vermeld — logische, kleine uitbreiding |
| 2. related_to_chained | 🟡 Deels — lijkt op Fase 7.4 "Relation propagation" |
| 3. Contradictiedetectie (part_of-loops) | 🟡 Deels — raakt aan Fase 8 "Causal Reasoning", maar smaller |
| 4. Multi-hop vragen combineren | ❌ Niet vermeld |
| 5. "Waarom niet"-uitleg | ❌ Niet vermeld — eigen idee, hoge gebruikswaarde/lage moeite |
| 6. Vergelijkingen tussen concepten | ❌ Niet vermeld |

**Advies (12 juli 2026):** de officiële roadmap (`semantic_roadmap.md` Fase 7.4/7.5, `semantic_extension_roadmap.md` Fase 8-10) blijft leidend voor de bouwvolgorde. Dit document is een aanvullende ideeënbak — idee #5 en #1 zijn qua moeite/waarde-verhouding de meest voor de hand liggende kandidaten mocht Kevin tussendoor iets kleins willen bouwen.

---

## Context: reeds afgeronde Fase 7-uitbreidingen (referentie)

Ter herinnering, deze twee zijn al gebouwd en getest (12 juli 2026), zie nova_state.md:

- **`part_of_chained` / `explain_part_of`** — analoog aan `is_a_chained`/`explain_is_a`, getest met keten snaar→gitaar→orkest
- **`get_all_subtypes`** — omgekeerde is_a-lookup, getest met "welke soorten dier ken je?" (16 concepten correct teruggegeven)

Beide staan in `semantic.py`, sectie 7.1b en 7.5 van de `ReasoningEngine`-klasse.
