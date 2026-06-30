## 1️⃣ **Nieuwe plural‑logic (professioneel niveau)**

We bouwen:

* irregular plurals
* lemma‑detectie
* plural‑normalisatie die rekening houdt met POS
* plural‑normalisatie die rekening houdt met bestaande concepten

**Taken:**

* Irregular_plurals_toevoegen
* Plural_normalisatie_verbeteren

## 2️⃣ **Example‑engine v2**

TeachEngine moet automatisch voorbeelden herkennen:

* “ik zit op een stoel” → example voor *stoel*
* “de hond blaft naar de kat” → examples voor *hond* en *kat*

**Taken:**

* Example_detectie_bouwen
* Example_ranking_toevoegen
* Example_audit_logging

## 3️⃣ **Sense‑upgrade v2 (confidence‑model)**

Nu is upgrade simpel.
TeachEngine v2 moet:

* confidence verhogen bij herhaling
* bron‑confidence combineren
* conflict‑detectie voorbereiden

**Taken:**

* Confidence_model_bouwen
* Sense_upgrade_v2_maken

## 4️⃣ **Brontracking v2**

We breiden uit:

* meerdere bronnen per sense
* bron‑audit
* bron‑confidence

**Taken:**

* Brontracking_v2_bouwen

## 5️⃣ **POS‑detectie v2**

We voegen toe:

* 300 werkwoorden
* 200 adjectieven
* irregular verbs
* irregular nouns
* POS‑audit

**Taken:**

* POS_engine_v2_bouwen

## 6️⃣ **TeachEngine clean architecture**

We splitsen TeachEngine op in logische stappen:

1. normalisatie
2. POS
3. sense‑upgrade
4. nieuwe sense
5. examples
6. usage tracking
7. audit

**Taken:**

* TeachEngine_v2_refactor
