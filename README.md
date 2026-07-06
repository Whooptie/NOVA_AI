
<div align="center">

---

## 🤖 Wat is Nova?

Nova is een **persoonlijke AI companion** die volledig lokaal draait op je eigen machine. Ze gebruikt geen LLM (zoals ChatGPT), geen cloud en geen internet — alles gebeurt op jouw computer, door jouw regels.

Nova is gebouwd op **symbolische AI**: ze leert via expliciete concepten, relaties en gedragspatronen — niet via statistisch taalmodel. Ze draait **24/7 als achtergrondproces** en kan zelf proactief reageren op patronen in jouw gedrag.

> *"Geen black box. Geen cloud. Geen verrassingen."*

---

## ✨ Wat kan Nova al?


| Functie                                               | Status |
| ------------------------------------------------------- | -------- |
| 💬 Gesprekken voeren in natuurlijke taal              | ✅     |
| ♟️ Schaken tegen Stockfish (met statistieken)       | ✅     |
| 🌤️ Weersvoorspellingen opvragen                     | ✅     |
| 📚 Wikipedia raadplegen & automatisch leren           | ✅     |
| 🧠 Semantische concepten begrijpen (118+ concepten)   | ✅     |
| 🔗 Woordassociaties leren via gebruik                 | ✅     |
| 📊 Gedragspatronen herkennen (tijdstip, frequentie)   | ✅     |
| 😊 Eigen persoonlijkheid, emoties & expressie         | ✅     |
| 🔄 Zichzelf herstarten zonder dataverlies (`/reboot`) | ✅     |
| 🕐 Tijdsbewustzijn (klok, datum, tijdzone)            | ✅     |
| ➗ Wiskundige berekeningen                            | ✅     |

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


| Laag    | Naam                                    | Status          |
| --------- | ----------------------------------------- | ----------------- |
| Layer 0 | SQLite opslag (WAL, write buffering)    | ✅ Klaar        |
| Layer 1 | Woordassociaties leerder (PMI scoring)  | ✅ Klaar        |
| Layer 2 | Gedragspatronen (tijdstip & frequentie) | ✅ Klaar        |
| Layer 3 | Semantische redenering                  | 🔜 Gepland      |
| Layer 4 | Antwoordgenerator                       | 🔜 Gepland      |
| Layer 5 | Contextbeheer                           | 🔜 Gepland      |
| Layer 6 | *(gereserveerd)*                        | —              |
| Layer 7 | Emergent gedrag (zelfbewustzijn)        | 🔮 Ver toekomst |

### 📦 Kernmodules

```
Nova_AI/
├── core/
│   ├── event_bus.py          # Centrale communicatie-backbone
│   ├── intent_router.py      # Begrijpt wat de gebruiker bedoelt
│   ├── memory.py             # 7-laags leergeheugen
│   ├── semantic.py           # Concepten, relaties, redeneren
│   └── reboot_manager.py     # Veilig herstarten
├── modules/
│   ├── chat/                 # Gespreksafhandeling
│   ├── chess/                # Schaakmotor (Stockfish)
│   ├── weather/              # Weermodule
│   ├── knowledge/            # Wikipedia AutoTeacher
│   └── learning/             # Woordassociaties & patronen
├── identity/
│   ├── personality/          # Persoonlijkheidsmotor
│   ├── emotion/              # Emotie-engine
│   └── expression/           # Toon & stijl
└── main.py
```

---

## 🔒 Privacy & Principes

- **100% lokaal** — geen data verlaat jouw machine
- **Geen LLM** — geen OpenAI, geen Gemini, geen cloud-AI
- **Nooit handelen zonder toestemming** — Nova suggereert altijd eerst
- **Volledig transparant** — alles wordt gelogd en is inzichtelijk
- **Open architectuur** — elk concept is leesbaar in `concepts.json`

---

## 🚀 Op de roadmap

- 🟡 Persoonlijkheidspipeline uitbreiden naar alle intents
- 🟢 Onderwerpherkenning voor Layer 2 (`topic_detected` events)
- 🟢 Gebruikersvoorkeuren-module (wat Nova over jou onthoudt)
- 🟢 Layer 4 antwoordgenerator (sjabloongebaseerde responses)
- 🟢 Intent classifier (klein lokaal ML-model als specialist)
- 🔮 Avatar / desktop companion (bewegende animatie)
- 🔮 Meer bordspellen (dammen, Go)
- 🔮 Robotica-integratie (ver toekomst)

---

## 🛠️ Technische vereisten

- Python 3.10+
- Windows (getest op Windows 11)
- Stockfish engine (voor schaak)
- OpenWeatherMap API key (voor weer)

```bash
pip install -r requirements.txt
python main.py
```

---

## 👤 Over dit project

Nova wordt gebouwd door **Kevin** — een zelfgeleerde developer.
Geen voorkennis. Geen achtergrond in programmeren. Gewoon nieuwsgierigheid en doorzettingsvermogen.

Dit project begon als een experiment en groeit uit tot een volwaardig lokaal AI-systeem met een geplande roadmap van 498+ modules.

> *"De meeste AI-projecten geven je een black box. Nova is mijn poging om te begrijpen hoe intelligentie echt werkt — stap voor stap, concept voor concept."*

---

<div align="center">
