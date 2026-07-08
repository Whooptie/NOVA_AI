# ML Components Overview: mogelijke ML-modellen per laag

**Status:** Referentie-overzicht, geen van deze is ingepland in bouwvolgorde
**Doel:** Per bestaande/geplande laag bijhouden wélke bounded ML-toevoeging ooit zinvol zou zijn, zodat het idee niet verloren gaat zonder dat het meteen een verplichting wordt
**Datum:** 8 juli 2026

---

## PRINCIPE (herhaling van architectuurregel)

Elke ML-toevoeging hieronder is een **externe, begrensde specialist-tool** — nooit de kern van Nova, nooit vrije generatie, altijd een vast, herkenbaar input/output-contract (zoals Stockfish: bord in, zet uit). Geen van deze modellen "praat" of "begrijpt" — ze leveren een getal, label, of voorstel terug aan Nova's symbolische kern, die zelf beslist wat ermee te doen.

---

## OVERZICHT PER LAAG

| Laag | Mogelijk ML-model | Type model | Wat lost het op | Prioriteit/status |
|---|---|---|---|---|
| Layer 1 (word_associations_learner.py) | Word embeddings (Word2Vec/FastText, lokaal getraind) | Licht neuraal netwerk | PMI ziet enkel woorden die letterlijk samen voorkomen. Embeddings zouden ook woorden herkennen die *nooit* samen zijn getypt maar wel gelijkaardig gebruikt worden (bv. "backgammon" en "dammen" in vergelijkbare zinscontexten) | Middel — staat al gepland als Fase 12 in semantic_extension_roadmap.md (daar toegepast op concepten i.p.v. woorden — mogelijk zelfde aanpak herbruikbaar) |
| Layer 2 (pattern_matcher.py) | Isolation Forest | Klassieke ML (geen neuraal netwerk) | Huidige anomaly-detectie werkt met vaste drempelwaarden op één variabele tegelijk. Isolation Forest zou meerdere variabelen samen kunnen bekijken (uur + dag + duur + vorige activiteit) voor subtielere, samengestelde anomalieën | Laag — huidige drempel-aanpak volstaat voorlopig |
| Layer 3 (semantic.py, Reasoning Layer) | Graph Neural Network (GNN) | Neuraal netwerk | Voorspelt ontbrekende relaties in concepts.json op basis van patronen in de bestaande kennisgraaf-structuur (bv. "kat" mist een houdt_van-relatie, maar andere dieren in de graaf hebben die wel) | Kevin's "achterhoofd"-optie — grootste en meest ingrijpende van dit overzicht, raakt kern van ConceptStore/RelationEngine, vereist apart trainingsproces buiten de daemon (PyTorch Geometric/DGL) |
| Layer 4 (response_engine.py, nog te bouwen) | Klein classificatiemodel voor sjabloonkeuze | Klassieke ML | Kiest de beste van meerdere mogelijke antwoord-sjablonen gegeven mood/context/onderwerp, i.p.v. een vaste if-else-boom | Laag — pas relevant zodra Layer 4 zelf bestaat |
| Intent-herkenning (los van de 7 lagen) | Intent classifier (TF-IDF + Logistic Regression) | Klassieke ML | Vangnet voor zinnen die intent_router.py niet herkent | Al volledig uitgewerkt — zie intent_classifier_roadmap.md |
| Activity/scherm/camera (activity_awareness) | Vision classifier / object detector | Neuraal netwerk | Herkent objecten/activiteiten in beeld als sensor-input voor activity-tracking | Concept — zie activity_awareness_roadmap.md, incl. privacy-overweging |

---

## EERLIJKHEID: WAT DIT OVERZICHT WEL EN NIET IS

- ✅ Een geheugensteun: per laag weten welke ML-optie ooit besproken is, zonder dat het een verplichting wordt
- ✅ Elk model hierboven is op zich, apart van de rest, te bouwen — geen onderlinge afhankelijkheid
- ❌ Geen bouwvolgorde of prioriteitenlijst — dat blijft aan Kevin om te bepalen wanneer relevant
- ❌ Geen van deze modellen verandert Nova's kernprincipe (geen LLM, ML altijd specialist nooit brein)
- ⚠️ Layer 3 (GNN) is verreweg de grootste ingreep — enige optie hier die de kern van een bestaande, afgewerkte module (semantic.py) zou raken in plaats van er enkel naast te staan

**Bijwerken:** dit document mag aangevuld worden telkens een nieuw ML-idee besproken wordt dat de moeite waard is om te onthouden voor later.
