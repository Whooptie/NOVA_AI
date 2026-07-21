<div align="center">

# 🌟 Nova AI

**A fully symbolic, local AI companion — built without an LLM, without the cloud.**

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)
![Privacy](https://img.shields.io/badge/Privacy-100%25%20Local-2ea44f?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-In%20Development-orange?style=for-the-badge)
![License](https://img.shields.io/badge/License-All%20Rights%20Reserved-red?style=for-the-badge)

</div>

---

## 🤖 What is Nova?

Nova is a **personal AI companion** that runs entirely locally on my own machine. She doesn't use an LLM (like ChatGPT), no cloud, no internet — everything happens locally, under my own rules.

Nova is built on **symbolic AI**: she learns through explicit concepts, relationships and behavioral patterns — not through a statistical language model. She runs **24/7 as a background process** and can proactively respond to patterns in my behavior.

> *"No black box. No cloud. No surprises."*

---

## 💬 Nova in action

```text
[Kevin]  what is a guitar?
[Nova]   A guitar is a stringed instrument, Kevin.
         Usually made of wood. 🎸

[Kevin]  weather in Bruges
[Nova]   In Bruges it's 18°C and cloudy.
         Chance of rain: 40% — bring an umbrella! ☔

[Kevin]  chess board
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

         Move 1. White to move
```

---

## ✨ What can Nova already do?

| Feature | Status |
|---|---|
| 💬 Natural language conversation | ✅ |
| ♟️ Playing chess against Stockfish (with stats & colored board) | ✅ |
| 🌤️ Weather forecasts (multiple days) | ✅ |
| 📚 Consulting Wikipedia & auto-learning | ✅ |
| 🧠 Understanding semantic concepts (133+ concepts, 147 senses) | ✅ |
| 🔗 Learning word associations through use (PMI scoring) | ✅ |
| 📊 Recognizing behavioral patterns by time & frequency | ✅ |
| 💡 Template-based responses with tone variation | ✅ |
| 😊 Own personality, emotions & expression | ✅ |
| 🔄 Restarting itself without data loss (`/reboot`) | ✅ |
| 🕐 Time awareness (clock, date, timezone) | ✅ |
| ➗ Mathematical calculations | ✅ |

---

## 🔍 What makes Nova different?

| Trait | ChatGPT / LLM | Nova (Symbolic) |
|---|---|---|
| **Knowledge source** | Billions of parameters (black box) | Explicit concepts (`concepts.json`) |
| **Learning** | Fine-tuning (slow, expensive) | `teach` command (instant) |
| **Reasoning** | Statistical guessing | Chaining (`is_a_chained`) |
| **Privacy** | Data sent to the cloud | 100% local |
| **Explainability** | "We don't know why" | Every answer is traceable |
| **Works offline?** | No | Yes |

---

## 🏗️ Architecture

Nova is built around a central **EventBus** — a publish/subscribe system where all modules communicate with each other without direct dependencies.

```
User → IntentRouter → EventBus → Modules
                                ↕
                          Memory Brain
                     (7-layer learning architecture)
```

### 🧠 The memory — 7 layers

| Layer | Name | Status |
|---|---|---|
| Layer 0 | SQLite storage (WAL, write buffering, crash recovery) | ✅ Done |
| Layer 1 | Word associations learner (PMI scoring) | ✅ Done |
| Layer 2 | Behavioral patterns (timing, frequency, anomaly detection) | ✅ Done |
| Layer 3 | Semantic reasoning (concepts, relations, inference) | ✅ Done |
| Layer 4 | Response generator (templates, tone variation, routing) | ✅ Done |
| Layer 5 | Context management (interruption logic) | 🔜 Planned |
| Layer 6 | Personality & emotion engine | ✅ Done |
| Layer 7 | Emergent behavior (self-awareness) | 🔮 Far future |

## 💻 How it works — an example

Nova learns through explicit concepts. No statistics, no guesswork.

```python
# Kevin teaches Nova a new concept
> teach: a guitar is a stringed instrument

# Nova stores this in concepts.json
{
  "guitar": {
    "senses": [{
      "definition": "a stringed instrument",
      "relations": {"is_a": ["stringed instrument"]}
    }]
  }
}

# Later, Kevin asks a question
> is a guitar an instrument?

# Nova reasons:
# guitar → is_a → stringed instrument → is_a → instrument
# Answer: "Yes, a guitar is an instrument."
```

---

### 📦 Core modules

```
Nova_AI/
├── core/
│   ├── event_bus.py          # Central communication backbone
│   ├── intent_router.py      # Understands what the user means
│   ├── memory.py             # 7-layer learning memory (SQLite, WAL)
│   ├── semantic.py           # Concepts, relations, reasoning
│   ├── response_engine.py    # Template-based responses
│   └── reboot_manager.py     # Safe restart
├── modules/
│   ├── chat/                 # Conversation handling + tone variation
│   ├── chess/                # Chess engine (Stockfish)
│   ├── weather/              # Weather module (multi-day forecast)
│   ├── knowledge/            # Wikipedia AutoTeacher
│   └── learning/             # Word associations & behavioral patterns
├── identity/
│   ├── personality/          # Personality engine
│   ├── emotion/              # Emotion engine
│   └── expression/           # Tone & style
└── main.py
```

---

## 🔒 Privacy & Principles

- **100% local** — no data leaves my machine
- **No LLM** — no OpenAI, no Gemini, no cloud AI
- **Never acts without consent** — Nova always suggests first
- **Fully transparent** — everything is logged and inspectable
- **Open architecture** — every concept is readable in `concepts.json`
- **ML only as a sensor** — external models may help perceive, Nova decides what to do

---

## ⚠️ About the data files in this repository

This repo contains **more than just code** — it also contains Nova's real, growing memory: files like `concepts.json`, `word_associations.json`, `patterns_layer2.json` and everything under `identity/personality/`. These are **not sample or test data** — this is Nova's accumulated knowledge and personality from real conversations with me.

This repository serves primarily as a **personal backup**, and has been made public so others can follow along with the project's development — not as a ready-to-use installable package for personal use.

---

## 🚀 On the roadmap

- 🟡 Expanding the personality pipeline to all intents
- 🟢 Layer 5: Context management (when may Nova interrupt?)
- 🟢 User preferences module (what Nova remembers about me)
- 🟢 Activity Awareness (recognizing activities & proactive responses)
- 🟢 Activity-Aware Interaction (interruption learning)
- 🟢 Intent classifier (small local ML model as a specialist)
- 🔮 Avatar / desktop companion (animated avatar, lipsync)
- 🔮 More board games (checkers, Go)
- 🔮 Smart home integration (lights, sensors)
- 🔮 Robotics integration (far future)

---

## 🛠️ Technical requirements

- Python 3.10+
- Windows (tested on Windows 11)
- Stockfish engine (for chess — download it yourself at stockfishchess.org)
- OpenWeatherMap API key (free to create at openweathermap.org)

```bash
pip install -r requirements.txt
python main.py
```

> Note: this project is not meant to be simply cloned and run — it's tightly coupled to my own paths, settings and personal data files.

---

## 👤 About this project

Nova is being built by **Kevin** — a self-taught developer from Bruges, Belgium.
No prior knowledge. No programming background. Just curiosity and persistence.

This project started as an experiment and is growing into a full local AI system with a planned roadmap of 498+ modules.

> *"Most AI projects give you a black box. Nova is my attempt to understand how intelligence really works — step by step, concept by concept."*

---

<div align="center">

**⭐ This code is publicly visible, but not free to use — see LICENSE.txt**

*Built with Python · Powered by curiosity · No LLM*

</div>