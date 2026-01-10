# 🏎️ F1 Car Builder with AI Race Engineer

> Interactive F1 car building experience with AI-powered assistant Dax, featuring OAuth 2.0 authentication, GDPR compliance, and cloud-based LLM integration

---

## 🚀 Project Overview

An immersive F1 car configuration system where players interact with **Dax**, an AI race engineer powered by Groq's LLM API. Players build custom Formula 1 cars by selecting chassis, engines, tires, and aerodynamic components while receiving real-time AI guidance and technical advice.

### Key Features

- 🔐 **OAuth 2.0 Authentication** - Login with Google or GitHub, or use email/password
- 🤖 **AI Race Engineer (Dax)** - Powered by Groq API (Llama 3.1 8B Instant)
- 🏎️ **Real-Time Car Building** - Select 5 F1 components with live preview
- 💾 **Auto-Save Progress** - Parts selection saved to database instantly
- 🧠 **Memory System** - AI remembers your conversation and build status
- 🎭 **Sentiment Analysis** - NPC responds to player emotions
- 📊 **PostgreSQL Database** - Cloud-hosted on Neon.tech
- 🔒 **GDPR Compliant** - Full privacy policy and data protection
- 🎨 **Cinematic UI** - F1 briefing-style interface with video backgrounds

---

## 🏗️ System Architecture

```
Player Login (OAuth/Email) → Cover Page → Chat Interface
                                              ↓
Part Selection → Auto-Save DB ← AI Assistant (Groq API)
                                              ↓
Build Complete → Submit Feedback → Portfolio Redirect
```

### Tech Stack

| Component              | Technology                                    |
| ---------------------- | --------------------------------------------- |
| **Backend API**        | FastAPI (Python)                              |
| **Database**           | PostgreSQL (Neon.tech)                        |
| **AI Model**           | Groq API - Llama 3.1 8B (150 tokens/response) |
| **Authentication**     | OAuth 2.0 (Google, GitHub) + JWT              |
| **Sentiment Analysis** | RoBERTa Transformer                           |
| **Frontend**           | HTML/CSS + Vanilla JavaScript                 |
| **Deployment**         | Render.com (ready)                            |

---

## 📋 Prerequisites

- Python 3.8+
- Git
- PostgreSQL database (Neon.tech recommended)
- Groq API key (free tier: 30 requests/min)
- Google OAuth credentials (optional)
- GitHub OAuth app (optional)

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

### 4. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env file with your credentials
```

**Required Environment Variables:**

```bash
# Database
DATABASE_URL=postgresql://username:password@host:port/database

# AI/LLM Configuration
USE_EXTERNAL_LLM=true
LLM_PROVIDER=groq
LLM_API_KEY=your_groq_api_key_here
LLM_MODEL=llama-3.1-8b-instant

# Authentication
JWT_SECRET_KEY=your_secret_key_here
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret

# Application
ENVIRONMENT=development
ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
```

### 5. Get API Keys

**Groq API (Free):**

1. Go to https://console.groq.com
2. Create account and get API key
3. Free tier: 30 requests/min

**Google OAuth (Optional):**

1. Go to https://console.cloud.google.com
2. Create OAuth 2.0 Client ID
3. Add redirect URI: `http://127.0.0.1:8000/auth/callback/google`

**GitHub OAuth (Optional):**

1. Go to https://github.com/settings/developers
2. Create new OAuth App
3. Add callback URL: `http://127.0.0.1:8000/auth/callback/github`

### 6. Run Application

```bash
uvicorn main:app --reload
```

### 7. Access Interface

Open your browser: `http://localhost:8000`

---

cp .env.example .env

# Edit .env file with your database credentials

# Contact project owner for production credentials

````

### 6. Run Application
```bash
uvicorn main:app --reload
````

### 7. Access Interface

Open your browser and navigate to: `http://localhost:8000`

---

## 🔌 API Endpoints

| Endpoint                | Method | Description                            |
| ----------------------- | ------ | -------------------------------------- |
| `/`                     | GET    | Login page                             |
| `/login`                | GET    | Login page (alias)                     |
| `/cover`                | GET    | Cinematic F1 briefing page             |
| `/chat`                 | GET    | AI-powered car builder (Dax)           |
| `/chat_static`          | GET    | Static dialogue car builder (TurboTom) |
| `/chat_api`             | POST   | Submit dialogue to AI (JSON)           |
| `/save_car_build`       | POST   | Auto-save car build progress           |
| `/create_player_form`   | POST   | Email/password registration            |
| `/verify_player`        | POST   | Email/password login                   |
| `/auth/login/google`    | GET    | Google OAuth login                     |
| `/auth/login/github`    | GET    | GitHub OAuth login                     |
| `/auth/callback/google` | GET    | Google OAuth callback                  |
| `/auth/callback/github` | GET    | GitHub OAuth callback                  |
| `/terms`                | GET    | Privacy policy & GDPR terms            |
| `/evaluation`           | GET    | Feedback submission page               |
| `/health`               | GET    | System health check                    |

---

## 🎮 Usage Flow

1. **Login** - Sign in with Google, GitHub, or email/password
2. **Cover Page** - Watch cinematic F1 briefing intro
3. **Start Building** - Randomized between AI chat or static flow
4. **Select Parts** - Choose chassis, engine, tires, front wing, rear wing
5. **AI Guidance** - Dax provides real-time advice and tracks progress
6. **Auto-Save** - Build saved to database on every part selection
7. **Complete Build** - Submit feedback and return to portfolio

### Available F1 Components

**Chassis:**

- Standard Monocoque
- Ground Effect Optimized

**Engine:**

- 2004 V10 (high power, fuel-hungry)
- 2006 V8 (balanced performance)

**Tires:**

- C5 Slick (dry conditions)
- Full Wet (rain conditions)

**Front Wing:**

- High Lift (better cornering, more drag)
- Simple Outwash (streamlined)

**Rear Wing:**

- High Downforce (stability)
- Low Drag (top speed)

---

## 🔧 Configuration

### LLM Settings (config.py)

```python
MODEL_MAX_TOKENS = 150        # Max response length
MODEL_TEMPERATURE = 0.4       # Response creativity (0.0-1.0)
CONTEXT_WINDOW = 10          # Recent messages for context
```

### Authentication (auth.py)

```python
ACCESS_TOKEN_EXPIRE = 15      # Minutes
REFRESH_TOKEN_EXPIRE = 7      # Days
JWT_ALGORITHM = "HS256"
```

### Database (models.py)

- **Players** - User accounts (email, password hash, OAuth data)
- **CarBuild** - F1 car configurations
- **NPCMemory** - Conversation history with sentiment
- **Consent** - GDPR consent records

---

## 🚀 Deployment on Render

### 1. Push to GitHub

```bash
git add .
git commit -m "Deploy F1 car builder"
git push origin main
```

### 2. Create Render Web Service

- Go to https://render.com
- New → Web Service
- Connect GitHub repo: `NJVinay/npc_memory`
- Runtime: **Python 3**
- Build: `pip install -r requirements.txt`
- Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### 3. Set Environment Variables

Add these in Render dashboard:

```
DATABASE_URL=<neon-postgresql-url>
LLM_API_KEY=<groq-api-key>
GOOGLE_CLIENT_ID=<google-client-id>
GOOGLE_CLIENT_SECRET=<google-secret>
GITHUB_CLIENT_ID=<github-client-id>
GITHUB_CLIENT_SECRET=<github-secret>
JWT_SECRET_KEY=<random-secret-key>
USE_EXTERNAL_LLM=true
LLM_PROVIDER=groq
LLM_MODEL=llama-3.1-8b-instant
ENVIRONMENT=production
```

### 4. Update OAuth Redirect URIs

After deployment (e.g., `https://your-app.onrender.com`):

**Google OAuth Console:**

- Add: `https://your-app.onrender.com/auth/callback/google`

**GitHub OAuth Settings:**

- Add: `https://your-app.onrender.com/auth/callback/github`

---

## 🧪 Testing

### API Health Check

```bash
curl http://localhost:8000/health
```

### Database Connection

```bash
python -c "from database import get_db; next(get_db()); print('✅ Database connected')"
```

### Sentiment Analysis

```bash
python -c "from sentiment import analyze_sentiment; print(analyze_sentiment('I love this!'))"
```

### Groq API

```bash
python -c "from llm_adapter import generate_with_groq; print(generate_with_groq('Hello'))"
```

---

## 🔧 Troubleshooting

### Common Issues

**OAuth Redirect Error**

```bash
# Add redirect URIs in OAuth settings:
# Google: https://console.cloud.google.com/apis/credentials
# GitHub: https://github.com/settings/developers
# Add: http://127.0.0.1:8000/auth/callback/google
# Add: http://127.0.0.1:8000/auth/callback/github
```

**Database Connection Error**

```bash
# Verify .env DATABASE_URL
# Test connection:
python -c "from database import engine; print(engine.connect())"
```

**Groq API Rate Limit**

```bash
# Free tier: 30 requests/minute
# Upgrade to paid tier for higher limits
# Or switch to OpenAI/HuggingFace in llm_adapter.py
```

**Cookie Security Warning**

```bash
# Development: secure=False (localhost)
# Production: Set ENVIRONMENT=production (auto-enables HTTPS cookies)
```

**Chat Box Overflow**

```bash
# Already fixed in templates/chat.html
# Chat box is 320px wide, 500px tall with auto-scrolling
# Text wraps with break-words for long messages
```

---

## 📊 Performance Notes

- **API Response Time**: ~2-5 seconds (Groq free tier)
- **Database Queries**: <100ms (Neon.tech)
- **Page Load**: ~1-2 seconds
- **Memory Usage**: ~200-300MB (no local model)
- **Storage**: Minimal (~50MB codebase)

**Groq Free Tier Limits:**

- 30 requests/minute
- Llama 3.1 8B Instant model
- 150 tokens max per response
- Production-ready reliability

---

## 🔮 Features

### Completed ✅

- OAuth 2.0 authentication (Google + GitHub)
- Email/password authentication with bcrypt
- JWT token management (15min access, 7 day refresh)
- Groq API integration (cloud-based LLM)
- Auto-save car builds on part selection
- Real-time chat with AI assistant
- Sentiment analysis for player messages
- GDPR-compliant privacy policy
- Cinematic F1 briefing cover page
- Portfolio redirect button
- Database migrations removed
- Production-ready deployment config
- Secure HTTPS cookies for production

### Future Enhancements 🚧

- Multiple AI engineers (different personalities)
- Voice input/output for Dax
- 3D car preview (Three.js)
- Race simulation with built car
- Leaderboards and sharing
- Mobile app version
- Multi-language support

---

## 📚 Project Context

Originally developed as a Bachelor's thesis on **"Memory-Driven NPC Behavior"** at Blekinge Institute of Technology, this project has been upgraded to a **job-ready portfolio piece** showcasing:

- Full-stack web development (FastAPI + PostgreSQL)
- Modern authentication patterns (OAuth 2.0, JWT)
- AI/LLM integration (Groq API)
- GDPR compliance and data protection
- Production deployment (Render.com)
- Clean architecture and code organization

### Academic Research

- Modular emotion-aware NPC systems
- Static vs. dynamic dialogue comparison
- Cloud LLM vs. local model tradeoffs
- User experience evaluation frameworks

---

## 📄 License

This project is developed for academic research and portfolio purposes.

---

## 📞 Contact & Support

**Developer:**

- Jyotir Vinay Naram
- Portfolio: https://jyotirvinay-portfolio.netlify.app
- Email: jv5102003@gmail.com

**Institution:**

- Blekinge Institute of Technology
- Computer Science Program
- Karlskrona, Sweden

**Project Links:**

- 🔗 GitHub: https://github.com/NJVinay/npc_memory
- 🚀 Live Demo: [Deploy on Render]
- 📧 Contact: jyna24@student.bth.se

---

## 🙏 Acknowledgments

- **Groq** - Free LLM API access
- **Neon.tech** - Serverless PostgreSQL hosting
- **Render.com** - Free web service deployment
- **Google/GitHub** - OAuth 2.0 infrastructure
- **Hugging Face** - RoBERTa sentiment model

---

**Built with ❤️ for the F1 racing community and AI enthusiasts**
