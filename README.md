For full functionality, ask the project owner for the `.env` file or test credentials.


# 🧠 NPC Memory Dialogue System

> Dynamic Real-Time NPC Conversations with Memory, Sentiment Awareness, and LLM Integration

---

## 🚀 Project Description

This project implements a **memory-driven dynamic NPC dialogue system** that allows players to interact with non-player characters (NPCs) in a **realistic, sentiment-aware, and evolving** manner.

The system:
- Analyzes **player sentiment** using **RoBERTa**.
- Generates **NPC replies** using **Mistral 7B** LLM (through **Ollama**).
- **Remembers** past conversations (stored in **PostgreSQL** on **Neon.tech** cloud database).
- Displays an immersive **chat UI** with real-time updates and smooth user experience.

---

## 🛠️ Tech Stack

| Layer | Technology |
|:---|:---|
| Backend API | **FastAPI** (Python) |
| Database | **PostgreSQL** (hosted on **Neon.tech**) |
| Language Model | **Mistral 7B** / **DeepSeek** via **Ollama** |
| Sentiment Analysis | **RoBERTa** (Cardiff NLP) |
| Frontend | **HTML/CSS** + **Vanilla JavaScript** |
| Deployment | GitHub + Render/Neon (for future) |

---

## 📜 Features

- ✅ **Real-Time** Player-to-NPC Chat (No Page Reload)
- ✅ **Sentiment-Aware** Dialogue Generation
- ✅ **NPC Memory** of Past Conversations
- ✅ **Dynamic Chat UI** with "NPC is thinking..." Animation
- ✅ **Multiple Players** Supported
- ✅ **FastAPI Endpoints** for Chat, Memory Fetch, Player Creation
- ✅ **Clean API structure** for future 2D/3D game integration

---

## 🏗️ Project Architecture

```
Player Inputs Dialogue
    ↓
Frontend (AJAX Fetch)
    ↓
Backend FastAPI
    ↓
Analyze Sentiment (RoBERTa)
    ↓
Generate NPC Reply (Mistral 7B via Ollama)
    ↓
Save Interaction in Neon Database
    ↓
Return NPC Reply → Update Chat UI Live
```

---

## 📚 Setup Instructions

1. **Clone this Repository:**

```bash
git clone https://github.com/NJVinay/npc_memory.git
cd npc_memory
```

2. **Setup Virtual Environment:**

```bash
python -m venv .venv
source .venv/bin/activate  # (Linux/Mac)
.venv\Scripts\activate      # (Windows)
```

3. **Install Dependencies:**

```bash
pip install -r requirements.txt
```

4. **Setup `.env` file:**

Create a `.env` based on `.env.example` and add your Neon DATABASE_URL.

5. **Start Ollama LLM Server:**

```bash
ollama run mistral:7b
```

6. **Run FastAPI Backend:**

```bash
uvicorn main:app --reload
```

7. **Access Frontend:**
- Open the website using localhost url which looks something like this: [http://localhost:8000/](http://localhost:8000/)  

---

## 🔥 API Endpoints Overview

| Endpoint | Method | Purpose |
|:---|:---|:---|
| `/chat` | GET | Load Chat UI (with Player & Chat History) |
| `/chat` | POST | Submit New Dialogue (classic form) |
| `/chat_api` | POST | Submit New Dialogue (real-time fetch) |
| `/get_interactions/{player_id}/{npc_id}` | GET | Fetch Full Chat Memory |

---

## 🎯 Future Enhancements

- 🎮 Integration into 2D/3D Game World (Pygame, Unity API Gateway)
- 🎤 Voice-over for NPC replies
- 💬 More advanced multi-turn conversation memory
- 🎨 Better UI Animations (Typing indicators, Emotions)
- 🌍 Deploy Fullstack Version (Render + Neon Database)

---

## 📢 Final Note

NPC Memory Project shows how **modern AI models + emotional context + database memory** can be combined to create **realistic and intelligent** video game NPCs.

---

# 🧠 Contact

For questions, issues, or demo requests:  
📧 Email: [jv5102003@gmail.com]  
🔗 GitHub: [https://github.com/NJVinay](https://github.com/NJVinay)

---

# 📚 End of README.md
