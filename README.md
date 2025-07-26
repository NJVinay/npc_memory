# 🧠 NPC Memory Dialogue System
> Dynamic Real-Time NPC Conversations with Memory, Sentiment Awareness, and LLM Integration

---

## 🚀 Project Overview

This project implements a **memory-driven, emotion-aware NPC dialogue system** that enables realistic, evolving conversations between players and non-player characters. The system combines modern AI techniques to create NPCs that remember past interactions, understand player emotions, and respond contextually.

### Key Features
- 🎭 **Sentiment-Aware Responses** - NPCs detect and respond to player emotions using RoBERTa
- 🧠 **Persistent Memory** - NPCs remember all past conversations across sessions
- 🤖 **Local AI Processing** - Powered by Mistral 7B GGUF model via llama.cpp
- ⚡ **Real-Time Chat Interface** - Smooth, responsive web-based interaction
- 📊 **PostgreSQL Database** - Cloud-hosted conversation storage on Neon.tech

---

## 🏗️ System Architecture

```
Player Input → Sentiment Analysis (RoBERTa) → Memory Retrieval (PostgreSQL)
                                    ↓
Frontend (HTML/JS) ← NPC Response ← LLM Generation (Mistral 7B GGUF)
```

### Tech Stack
| Component | Technology |
|-----------|------------|
| **Backend API** | FastAPI (Python) |
| **Database** | PostgreSQL (Neon.tech) |
| **Language Model** | Mistral 7B GGUF (llama-cpp-python) |
| **Sentiment Analysis** | RoBERTa Transformer |
| **Frontend** | HTML/CSS + Vanilla JavaScript |
| **Deployment** | Self-hosted / Cloud-ready |

---

## 📋 Prerequisites

- Python 3.8+
- Git
- ~4GB RAM (for model loading)
- ~2GB storage space (for GGUF model)
- Internet connection (for database and model download)

---

## ⚙️ Installation & Setup

### 1. Clone Repository
```bash
git clone https://github.com/NJVinay/npc_memory.git
cd npc_memory
```

### 2. Create Virtual Environment
```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Setup Language Model

**Download Mistral 7B GGUF Model**
```bash
# Create models directory
mkdir models

# Download the quantized model (Q2_K version ~2.6GB)
# Option A: Direct download (if available)
wget -O models/mistral-7b-instruct-v0.1.Q2_K.gguf \
  https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.1-GGUF/resolve/main/mistral-7b-instruct-v0.1.Q2_K.gguf

# Option B: Manual download
# Visit: https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.1-GGUF
# Download: mistral-7b-instruct-v0.1.Q2_K.gguf
# Place in: models/ directory
```

**Alternative Model Sizes:**
| Model | Size | Quality | RAM Required |
|-------|------|---------|--------------|
| Q2_K | ~2.6GB | Good | 4GB |
| Q4_0 | ~4.1GB | Better | 6GB |
| Q5_0 | ~4.8GB | Best | 8GB |

### 5. Configure Environment
```bash
# Copy environment template
cp .env.example .env

# Edit .env file with your database credentials
# Contact project owner for production credentials
```

### 6. Run Application
```bash
uvicorn main:app --reload
```

### 7. Access Interface
Open your browser and navigate to: `http://localhost:8000`

---

## 🔌 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main chat interface |
| `/chat` | GET | Legacy chat page |
| `/chat` | POST | Submit dialogue (form-based) |
| `/chat_api` | POST | Submit dialogue (JSON API) |
| `/get_interactions/{player_id}/{npc_id}` | GET | Retrieve conversation history |
| `/health` | GET | System health check |

---

## 🎮 Usage

1. **Create/Select Player** - Choose your player identity
2. **Select NPC** - Pick an NPC to converse with
3. **Start Chatting** - Type messages and receive intelligent responses
4. **Experience Memory** - NPCs remember your conversation history
5. **Notice Emotions** - NPCs respond differently based on your sentiment

---

## 🔧 Configuration

### Environment Variables
```bash
DATABASE_URL=postgresql://username:password@host:port/database
MODEL_PATH=models/mistral-7b-instruct-v0.1.Q2_K.gguf
MAX_TOKENS=512
TEMPERATURE=0.7
```

### Model Configuration
The system uses `llamacpp.py` for local GGUF model inference:
```python
# Model settings (configurable in llamacpp.py)
model_path = "models/mistral-7b-instruct-v0.1.Q2_K.gguf"
n_ctx = 2048        # Context window
max_tokens = 512    # Max response length
temperature = 0.7   # Creativity level
```

---

## 🧪 Testing

### Manual Testing
```bash
# Test sentiment analysis
python -c "from sentiment import analyze_sentiment; print(analyze_sentiment('I love this game!'))"

# Test database connection
python -c "from database import get_db; next(get_db())"

# Test GGUF model loading
python -c "from llamacpp import generate_response; print(generate_response('Hello'))"
```

### API Testing
```bash
# Health check
curl http://localhost:8000/health

# Chat API test
curl -X POST http://localhost:8000/chat_api \
  -H "Content-Type: application/json" \
  -d '{"player_id": 1, "npc_id": 1, "message": "Hello!"}'
```

---

## 🔧 Troubleshooting

### Common Issues

**Model Loading Failed**
```bash
# Check if model file exists
ls -la models/mistral-7b-instruct-v0.1.Q2_K.gguf

# Verify file integrity (should be ~2.6GB)
du -h models/mistral-7b-instruct-v0.1.Q2_K.gguf

# Re-download if corrupted
rm models/mistral-7b-instruct-v0.1.Q2_K.gguf
# Then re-download using steps above
```

**Insufficient Memory**
```bash
# Check available RAM
free -h  # Linux/macOS
wmic OS get TotalVisibleMemorySize /value  # Windows

# Use smaller model if needed (Q2_K instead of Q4_0)
```

**Slow Response Times**
- First request: ~10-15 seconds (model loading)
- Subsequent requests: ~3-5 seconds
- Consider upgrading to Q4_0 model for better quality
- Ensure sufficient RAM availability

**Database Connection Error**
- Verify `.env` file contains correct DATABASE_URL
- Check internet connection
- Contact project owner for credentials

**llama-cpp-python Installation Issues**
```bash
# Force reinstall with specific flags
pip uninstall llama-cpp-python
CMAKE_ARGS="-DLLAMA_BLAS=ON -DLLAMA_BLAS_VENDOR=OpenBLAS" pip install llama-cpp-python
```

---

## 💾 Model Management

### Switching Models
```python
# Edit llamacpp.py to change model
MODEL_PATH = "models/your-preferred-model.gguf"
```

### Supported GGUF Models
- Mistral 7B variants
- Llama 2 7B/13B
- CodeLlama models
- Any GGUF-compatible model

### Performance Optimization
```python
# In llamacpp.py, adjust these parameters:
n_gpu_layers = 0      # Increase if you have GPU
n_threads = 4         # Match your CPU cores
use_mmap = True       # Memory mapping for efficiency
use_mlock = True      # Lock model in RAM
```

---

## 🚀 Deployment

### Local Development
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Production Considerations
- Ensure sufficient RAM (4GB+ for Q2_K model)
- Consider SSD storage for faster model loading
- Monitor memory usage during concurrent requests
- Use process managers like PM2 or systemd

---

## 📊 Performance Notes

- **Model Loading**: ~10-15 seconds (one-time)
- **First Response**: ~5-8 seconds
- **Subsequent Responses**: ~5-25 seconds
- **Memory Usage**: ~3-4GB RAM (Q2_K model)
- **Storage**: ~2.6GB for model file

---

## 🔮 Future Enhancements

- 🎮 **Game Engine Integration** (Unity, Unreal, Pygame)
- ⚡ **GPU Acceleration** for faster inference
- 🎨 **Enhanced UI/UX** with animations
- 🌍 **Multi-language Support**
- 📱 **Mobile-responsive Interface**
- 🔊 **Audio Input/Output**
- 🎯 **Multiple Model Support**

---

## 📚 Research Context

This system is part of a Bachelor's thesis on **"Memory-Driven NPC Behavior: Context-Aware and Emotion-Based Game Conversations"** at Blekinge Institute of Technology. The research explores how lightweight AI components can enhance NPC believability and player engagement.

### Academic Contributions
- Modular architecture for emotion-aware NPCs
- Comparison between static vs. dynamic dialogue systems
- Local GGUF model integration for privacy and control
- Evaluation framework for NPC interaction quality

---

## 📄 License

This project is developed for academic research purposes. Please contact the authors for usage permissions.

---

## 📞 Contact & Support

**Author:**
- Jyotir Vinay Naram - [jyna24@student.bth.se](mailto:jyna24@student.bth.se)

**Institution:**
- Blekinge Institute of Technology
- Computer Science
- Karlskrona, Sweden

**Project Links:**
- 🔗 GitHub: [https://github.com/NJVinay/npc_memory](https://github.com/NJVinay/npc_memory)
- 📧 Contact: [jv5102003@gmail.com](mailto:jv5102003@gmail.com)

---

**Note:** For full functionality, request the `.env` file with database credentials from the project authors. The GGUF model file must be downloaded separately due to size constraints.
