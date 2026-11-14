# BridgeMate Backend — Platform Integration & Context-Aware AI

Unified backend powering the **BridgeMate Embeddable Website Plugin** and **Telegram Bot**, built with **FastAPI**, **SQLAlchemy 2.0**, **PostgreSQL / pgvector**, and pluggable AI providers (**Gemini**, **Groq**, and **Verified Offline FAQ**).

---

## 🏛 System Architecture

```text
                  BRIDGEMATE
                       |
             FastAPI Backend
                       |
        +--------------+--------------+
        |              |              |
   Plugin API      Telegram API    Admin API
        |              |              |
   Website Widget  Telegram Bot   Dashboard
        |              |              |
        +--------------+--------------+
                       |
                Shared Services
                       |
        +--------------+--------------+
        |              |              |
     AI Engine     Knowledge Base   Platform
        |              |           Management
        |              |
   Gemini/Groq     PostgreSQL
   Offline FAQ      + pgvector
```

---

## 🚀 Key Features

1. **Embeddable Plugin Configuration (`GET /api/v1/plugin/config/{public_key}`)**:
   - Dynamic theming (primary, secondary, background, text, chat button color).
   - Platform branding (logo, platform name, custom welcome greeting).
   - Configurable features (voice, human support, simple mode, job assistance).
   - Live updates via `PATCH /api/v1/platforms/{id}/plugin-config` without rebuilding frontend bundles.

2. **Context-Aware Page Processing**:
   - Sanitizes and scrubs sensitive data (passwords, tokens, PII, scripts) from DOM payloads.
   - Detects page types: `course`, `lesson`, `assignment`, `job`, `application`, `general`.
   - Generates contextual quick actions tailored to the active webpage.

3. **Shared Knowledge Base & Grounded RAG**:
   - Ingests institutional materials (`PDF`, `DOCX`, `TXT`, `HTML`).
   - Splits content into structured chunks with page numbers and section titles.
   - 768-dimensional vector embeddings with `pgvector` similarity search.
   - Grounded citations returned with document title, page number, and snippet.

4. **3-Tier Pluggable AI Provider**:
   - Tier 1: **Google Gemini API** (`gemini-1.5-flash`)
   - Tier 2: **Groq API** (`llama-3.3-70b-versatile`)
   - Tier 3: **Verified Offline FAQ Provider** (guaranteed 100% uptime fallback)
   - Supports both **English** and **Amharic (አማርኛ)**.

5. **Telegram Integration**:
   - Phone verification matching verified LMS student records.
   - Multi-platform membership switching.
   - Shares the same knowledge base and AI engine.

6. **Career Gateway & Human Assistance**:
   - Job search, skill-based filtering, mock interview simulations.
   - Private interview accommodation requests with learner consent.
   - Support ticket lifecycle with optional conversation sharing and WebSocket updates.

---

## 📂 Project Structure

```text
Meri-back/
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── endpoints/
│   │   │   │   ├── plugin.py           # GET /plugin/config/{public_key}
│   │   │   │   ├── platforms.py        # Platform registration & dynamic styling
│   │   │   │   ├── auth.py             # Server-to-server token minting & telegram auth
│   │   │   │   ├── context.py          # Context analysis & security sanitization
│   │   │   │   ├── knowledge.py        # Courses, document upload & RAG search
│   │   │   │   ├── chat.py             # Context-aware chat & WebSockets
│   │   │   │   ├── jobs.py             # Career gateway & accommodations
│   │   │   │   ├── support.py          # Human support tickets & messaging
│   │   │   │   ├── telegram.py         # Telegram webhook & updates
│   │   │   │   └── analytics.py        # Platform & teacher insights
│   │   │   └── router.py               # Aggregated v1 router
│   ├── core/
│   │   ├── config.py                   # Pydantic v2 application settings
│   │   ├── database.py                 # Async SQLAlchemy engine & SafeVector
│   │   ├── security.py                 # JWT, hashing & key generators
│   │   └── dependencies.py             # Auth & platform resolvers
│   ├── models/                         # SQLAlchemy 2.0 ORM entities
│   ├── schemas/                        # Pydantic v2 validation models
│   ├── services/
│   │   ├── ai/                         # Gemini, Groq, Offline FAQ & Orchestrator
│   │   ├── context_engine.py           # DOM scrub & entity detector
│   │   ├── course_assistant.py         # RAG + grounded citations
│   │   ├── job_assistant.py            # Skill comparison & qualification
│   │   ├── interview_prep.py           # Mock interview generator
│   │   ├── document_parser.py          # PDF / DOCX / HTML parser
│   │   ├── telegram_service.py         # Bot flows & phone verification
│   │   └── websocket_manager.py        # Real-time WebSocket manager
│   └── main.py                         # FastAPI application entrypoint
├── alembic/                            # Database migrations
├── scripts/
│   └── seed_data.py                    # Seeder for demo platform, courses, jobs & FAQs
├── tests/
│   └── test_api.py                     # Automated test suite (9 test cases)
├── Dockerfile
├── docker-compose.yml
├── alembic.ini
├── requirements.txt
├── CONFIGURATION_GUIDE.md              # Detailed guide for all keys and variables
└── .env.example
```

---

## ⚡ Quick Start

### 1. Installation
```bash
# Clone and enter workspace
cd Meri-back

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
*(Refer to `CONFIGURATION_GUIDE.md` for API keys. Offline mode functions out of the box without keys!)*

### 3. Seed Database
```bash
python scripts/seed_data.py
```
This populates:
- **Demo Platform**: `Savanna` (`pk_live_savanna_sample_12345`)
- **Integration Secret**: `sk_live_savanna_secret_67890`
- **Course**: `CS101` with chunked learning materials and vector embeddings
- **Jobs**: `Junior Python Developer` and `Frontend React Specialist`
- **Verified Student**: `learner@savanna.example.com` / `+251911223344`

### 4. Run Development Server
```bash
uvicorn app.main:app --reload --port 8000
```
- Interactive Swagger UI: `http://localhost:8000/docs`
- ReDoc UI: `http://localhost:8000/redoc`

### 5. Run Automated Tests
```bash
python -m pytest tests/test_api.py -v
```

---

## 🐳 Docker Deployment

To launch the full stack with PostgreSQL (pgvector), Redis, and FastAPI:
```bash
docker-compose up --build -d
```
FastAPI will start on port `8000` and automatically run database migrations and seeding.
