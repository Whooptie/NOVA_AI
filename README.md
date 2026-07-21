<div align="center">

# 🌟 Nova AI

**Een volledig symbolische, lokale AI companion — gebouwd zonder LLM, zonder cloud.**

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)
![Privacy](https://img.shields.io/badge/Privacy-100%25%20Lokaal-2ea44f?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-In%20Ontwikkeling-orange?style=for-the-badge)
![License](https://img.shields.io/badge/License-All%20Rights%20Reserved-red?style=for-the-badge)

</div>

---

## 🤖 Wat is Nova?

Nova is een **persoonlijke AI companion** die volledig lokaal draait op mijn eigen machine. Ze gebruikt geen LLM (zoals ChatGPT), geen cloud en geen internet — alles gebeurt lokaal, door mijn eigen regels.

Nova is gebouwd op **symbolische AI**: ze leert via expliciete concepten, relaties en gedragspatronen — niet via een statistisch taalmodel. Ze draait **24/7 als achtergrondproces** en kan zelf proactief reageren op patronen in mijn gedrag.

> *"Geen black box. Geen cloud. Geen verrassingen."*

---

## 💬 Nova in actie

```text
[Kevin]  wat is een gitaar?
[Nova]   Een gitaar is een snaarinstrument, Kevin. 
         Wordt vaak van hout gemaakt. 🎸

[Kevin]  weer in Brugge
[Nova]   In Brugge is het 18°C en bewolkt. 
         Regenkans: 40% — neem een paraplu mee! ☔

[Kevin]  schaak bord
[Nova]   
         8  ♜ ♞ ♝ ♛ ♚ ♝ ♞ ♜
         7  ♟ ♟ ♟ ♟ ♟ ♟ ♟ ♟
         6  . . . . . . . .
         5  . . . . . . . .
         4  . . . . . . . .
         3  . . . . . . . .
         2  ♙ ♙ ♙ ♙ ♙ ♙ ♙ ♙
         1  ♖ ♘ ♗ ♕ ♔ ♗ ♘ ♖
            a b c d e f g h
         
         Zet 1. Wit aan zet
```

---

## ✨ Wat kan Nova al?

| Functie | Status |
|---|---|
| 💬 Gesprekken voeren in natuurlijke taal | ✅ |
| ♟️ Schaken tegen Stockfish (met statistieken & kleurenbord) | ✅ |
| 🌤️ Weersvoorspellingen opvragen (meerdere dagen) | ✅ |
| 📚 Wikipedia raadplegen & automatisch leren | ✅ |
| 🧠 Semantische concepten begrijpen (133+ concepten, 147 senses) | ✅ |
| 🔗 Woordassociaties leren via gebruik (PMI scoring) | ✅ |
| 📊 Gedragspatronen herkennen op tijdstip & frequentie | ✅ |
| 💡 Sjabloongebaseerde antwoorden met toonvariatie | ✅ |
| 😊 Eigen persoonlijkheid, emoties & expressie | ✅ |
| 🔄 Zichzelf herstarten zonder dataverlies (`/reboot`) | ✅ |
| 🕐 Tijdsbewustzijn (klok, datum, tijdzone) | ✅ |
| ➗ Wiskundige berekeningen | ✅ |

---

## 🔍 Wat maakt Nova anders?

| Kenmerk | ChatGPT / LLM | Nova (Symbolisch) |
|---|---|---|
| **Kennisbron** | Miljarden parameters (black box) | Expliciete concepten (`concepts.json`) |
| **Leren** | Fine-tunen (duur, duur) | `teach`-commando (direct) |
| **Redeneren** | Statistische gok | Chaining (`is_a_chained`) |
| **Privacy** | Data naar cloud | 100% lokaal |
| **Uitlegbaarheid** | "We weten niet waarom" | Elk antwoord is traceerbaar |
| **Werkt offline?** | Nee | Ja |

---

## 🏗️ Architectuur

Nova is gebouwd rond een centrale **EventBus** — een publish/subscribe systeem waarbij alle modules met elkaar communiceren zonder directe afhankelijkheden.

```
Gebruiker → IntentRouter → EventBus → Modules
                                    ↕
                              Memory Brain
                         (7-laags leerarchitectuur)
```

### 🧠 Het geheugen — 7 lagen

| Laag | Naam | Status |
|---|---|---|
| Layer 0 | SQLite opslag (WAL, write buffering, crash recovery) | ✅ Klaar |
| Layer 1 | Woordassociaties leerder (PMI scoring) | ✅ Klaar |
| Layer 2 | Gedragspatronen (tijdstip, frequentie, anomaly detection) | ✅ Klaar |
| Layer 3 | Semantische redenering (concepten, relaties, inferentie) | ✅ Klaar |
| Layer 4 | Antwoordgenerator (sjablonen, toonvariatie, routing) | ✅ Klaar |
| Layer 5 | Contextbeheer (interruption logic) | 🔜 Gepland |
| Layer 6 | Persoonlijkheid & emotie-engine | ✅ Klaar |
| Layer 7 | Emergent gedrag (zelfbewustzijn) | 🔮 Ver toekomst |


## 💻 Hoe het werkt — een voorbeeld

Nova leert via expliciete concepten. Geen statistiek, geen giswerk.

```python
# Kevin leert Nova een nieuw concept
> teach: een gitaar is een snaarinstrument

# Nova slaat dit op in concepts.json
{
  "gitaar": {
    "senses": [{
      "definition": "een snaarinstrument",
      "relations": {"is_a": ["snaarinstrument"]}
    }]
  }
}

# Later stelt Kevin een vraag
> is een gitaar een instrument?

# Nova redeneert:
# gitaar → is_a → snaarinstrument → is_a → instrument
# Antwoord: "Ja, een gitaar is een instrument."
```

---

### 📦 Kernmodules

```
Nova_AI/
├── core/
│   ├── event_bus.py          # Centrale communicatie-backbone
│   ├── intent_router.py      # Begrijpt wat de gebruiker bedoelt
│   ├── memory.py             # 7-laags leergeheugen (SQLite, WAL)
│   ├── semantic.py           # Concepten, relaties, redeneren
│   ├── response_engine.py    # Sjabloongebaseerde antwoorden
│   └── reboot_manager.py     # Veilig herstarten
├── modules/
│   ├── chat/                 # Gespreksafhandeling + toonvariatie
│   ├── chess/                # Schaakmotor (Stockfish)
│   ├── weather/              # Weermodule (meerdaagse voorspelling)
│   ├── knowledge/            # Wikipedia AutoTeacher
│   └── learning/             # Woordassociaties & gedragspatronen
├── identity/
│   ├── personality/          # Persoonlijkheidsmotor
│   ├── emotion/              # Emotie-engine
│   └── expression/           # Toon & stijl
└── main.py
```

---


## 🔒 Privacy & Principes

- **100% lokaal** — geen data verlaat mijn machine
- **Geen LLM** — geen OpenAI, geen Gemini, geen cloud-AI
- **Nooit handelen zonder toestemming** — Nova suggereert altijd eerst
- **Volledig transparant** — alles wordt gelogd en is inzichtelijk
- **Open architectuur** — elk concept is leesbaar in `concepts.json`
- **ML alleen als sensor** — externe modellen mogen helpen waarnemen, Nova beslist zelf

---

## ⚠️ Over de databestanden in deze repository

Deze repo bevat **niet enkel code**, maar ook Nova's echte, groeiende geheugen: bestanden zoals `concepts.json`, `word_associations.json`, `patterns_layer2.json` en alles onder `identity/personality/`. Dit zijn **geen voorbeeld- of testdata** — het is Nova's opgebouwde kennis en persoonlijkheid uit echte gesprekken met mij.

Deze repository dient in de eerste plaats als **persoonlijke backup**, en is publiek gemaakt zodat anderen kunnen meekijken in de bouw van het project — niet als kant-en-klaar installeerbaar pakket voor eigen gebruik.

---

## 🚀 Op de roadmap

- 🟡 Persoonlijkheidspipeline uitbreiden naar alle intents
- 🟢 Layer 5: Contextbeheer (wanneer mag Nova onderbreken?)
- 🟢 Gebruikersvoorkeuren-module (wat Nova over mij onthoudt)
- 🟢 Activity Awareness (activiteiten herkennen & proactief reageren)
- 🟢 Activity-Aware Interaction (interruption learning)
- 🟢 Intent classifier (klein lokaal ML-model als specialist)
- 🔮 Avatar / desktop companion (bewegende animatie, lipsync)
- 🔮 Meer bordspellen (dammen, Go)
- 🔮 Smart home integratie (lichten, sensoren)
- 🔮 Robotica-integratie (ver toekomst)

---

## 🛠️ Technische vereisten

- Python 3.10+
- Windows (getest op Windows 11)
- Stockfish engine (voor schaak — zelf te downloaden op stockfishchess.org)
- OpenWeatherMap API key (gratis aan te maken op openweathermap.org)

```bash
pip install -r requirements.txt
python main.py
```

> Let op: dit project is niet bedoeld om zomaar te klonen en te laten draaien — het is nauw verweven met mijn eigen paden, instellingen en persoonlijke databestanden.

---

## 👤 Over dit project

Nova wordt gebouwd door **Kevin** — een zelfgeleerde developer uit Brugge, België.
Geen voorkennis. Geen achtergrond in programmeren. Gewoon nieuwsgierigheid en doorzettingsvermogen.

Dit project begon als een experiment en groeit uit tot een volwaardig lokaal AI-systeem met een geplande roadmap van 498+ modules.

> *"De meeste AI-projecten geven je een black box. Nova is mijn poging om te begrijpen hoe intelligentie echt werkt — stap voor stap, concept voor concept."*

---

<div align="center">

**⭐ Deze code is publiek zichtbaar, maar niet vrij te gebruiken — zie LICENSE.txt**

*Gebouwd met Python · Aangedreven door nieuwsgierigheid · Zonder LLM*

</div>
