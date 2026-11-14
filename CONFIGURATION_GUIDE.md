# BridgeMate Backend — Configuration & API Keys Guide

This document details every manual key, secret, and environment variable required by the backend, where to obtain each, and what changes are required before moving to production.

---

## 1. Quick Setup Checklist

All configurations are managed in `.env` (or environment variables in Docker Compose). A template is provided in `.env.example`.

| Variable | Required For | Default / Example Value | Where to Obtain / Action Needed |
| :--- | :--- | :--- | :--- |
| **`SECRET_KEY`** | JWT Security | `BRIDGEMATE_SUPER_SECRET_KEY_...` | **Must change in production!** Generate a random 32+ character hex string. |
| **`DATABASE_URL`** | Data & Vector Store | `sqlite+aiosqlite:///./bridgemate.db` | Keep SQLite for local testing. In Docker / Production, switch to `postgresql+asyncpg://postgres:postgres@localhost:5432/bridgemate`. |
| **`GEMINI_API_KEY`** | AI Provider (Tier 1) | Empty (falls back to Tier 2/3) | Obtain free key from [Google AI Studio](https://aistudio.google.com/). |
| **`GROQ_API_KEY`** | AI Provider (Tier 2) | Empty (falls back to Tier 3) | Obtain free API key from [Groq Console](https://console.groq.com/). |
| **`TELEGRAM_BOT_TOKEN`** | Telegram Bot Service | Empty | Create a bot on Telegram via [@BotFather](https://t.me/botfather). |
| **`TELEGRAM_WEBHOOK_SECRET`**| Telegram Security | `bridgemate_tg_webhook_secret` | Any random secret string for webhook header verification. |
| **`CORS_ORIGINS`** | Frontend Embeddable | `*` | Keep `*` or specify host domains (e.g., `https://savanna.example.com,https://moodle.org`). |

---

## 2. Step-by-Step Configuration Guide

### A. AI Providers (Fallback Chain)
The backend implements a 3-tier fallback chain: **Gemini → Groq → Verified Offline FAQ**.
- If neither key is provided, the backend operates in **Offline FAQ mode** (guaranteed 100% uptime with pre-approved answers).

#### 1. Google Gemini API (`GEMINI_API_KEY`)
1. Go to [Google AI Studio](https://aistudio.google.com/).
2. Click **Create API Key**.
3. Copy the key and set in `.env`:
   ```env
   GEMINI_API_KEY=AIzaSy...
   GEMINI_MODEL=gemini-1.5-flash
   EMBEDDING_MODEL=text-embedding-004
   ```

#### 2. Groq Cloud API (`GROQ_API_KEY`)
1. Go to [Groq Console](https://console.groq.com/).
2. Create an API key in **API Keys**.
3. Copy the key and set in `.env`:
   ```env
   GROQ_API_KEY=gsk_...
   GROQ_MODEL=llama-3.3-70b-versatile
   ```

---

### B. Telegram Bot Setup (`TELEGRAM_BOT_TOKEN`)
1. Open Telegram and search for [@BotFather](https://t.me/botfather).
2. Type `/newbot` and follow the prompts to name your bot (e.g. `BridgeMate_Assistant_Bot`).
3. BotFather will provide an HTTP API token (format: `123456789:ABCdefGHIjklMNOpqrSTUvwxYZ`).
4. Set in `.env`:
   ```env
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
   TELEGRAM_WEBHOOK_SECRET=your_custom_secret_key
   ```
5. Set webhook URL in production:
   ```bash
   curl -F "url=https://your-domain.com/api/v1/telegram/webhook" \
        -F "secret_token=your_custom_secret_key" \
        https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook
   ```

---

### C. Database (PostgreSQL with pgvector vs Local SQLite)
- **Local Development / Quick Testing**:
  The system defaults to:
  ```env
  DATABASE_URL=sqlite+aiosqlite:///./bridgemate.db
  ```
  No database server installation required.
- **Production / Docker**:
  ```env
  DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/bridgemate
  ```
  Run `docker-compose up -d` to launch PostgreSQL with `pgvector` pre-configured.

---

## 3. Seeded Platform Credentials (For Frontend Team)

When running `python scripts/seed_data.py`, the following demo credentials are created:

| Entity | Field | Value | Usage in Frontend Plugin |
| :--- | :--- | :--- | :--- |
| **Demo Platform** | Name | `Savanna` | Host institution |
| **Script Tag Key** | `public_key` | `pk_live_savanna_sample_12345` | `<script data-public-key="pk_live_savanna_sample_12345" ...>` |
| **Backend Integration** | `secret_key` | `sk_live_savanna_secret_67890` | Server-to-server auth to mint learner tokens |
| **Test Student** | Email / Phone | `learner@savanna.example.com` / `+251911223344` | Verified learner record for Telegram & Web |
| **Test Admin** | Email / Pass | `admin@bridgemate.internal` / `AdminPass123!` | Dashboard & Admin API |

---

## 4. How the Frontend Communicates with the Backend

1. **Plugin Initialization**:
   - Frontend calls: `GET /api/v1/plugin/config/{public_key}`
   - Returns platform theme (`primary`, `secondary`, `background`), branding logo, position, features, and welcome message.
2. **Context-Aware Chat**:
   - Frontend sends: `POST /api/v1/chat/messages` with message + `context` payload (`page_type`, `url`, `title`, `content`).
   - Backend automatically sanitizes sensitive fields, retrieves grounded course/job materials, invokes AI fallback chain, and returns grounded answer with institutional citations.
3. **Dynamic Customization**:
   - Calling `PATCH /api/v1/platforms/{platform_id}/plugin-config` updates colors and branding in real time without rebuilding the frontend widget bundle.
