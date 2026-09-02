# AI Chatbot for DarGlobal & Wasalt — Implementation Plan

## 1. Requirement Recap

- Scrape publicly available data from **DarGlobal** and **Wasalt** (real estate sites).
- Build an **AI chatbot** using the scraped data (this is a RAG use case).
- Use a **free model via OpenRouter**.
- Containerize the app.
- **Deploy** it and hand over a **working URL** — source code alone is not acceptable.

## 2. Stack Decision

| Layer | Choice | Notes |
|---|---|---|
| Backend | **FastAPI** | Serves scraping trigger, ingestion, chat endpoint |
| Frontend | **React** (Vite) | Simple chat UI |
| Relational store | **SQLite** | Scraped raw docs, chat history, metadata |
| Vector store | **Qdrant** | Embeddings for RAG retrieval — use **Qdrant Cloud free tier** instead of local Docker, since you have no Docker locally |
| LLM | **OpenRouter** free model (e.g. `meta-llama/llama-3.1-8b-instruct:free` or similar `:free` tagged model) | Confirm current free model availability at request time — free model list on OpenRouter changes |
| Embeddings | Free/local option: `sentence-transformers` (e.g. `all-MiniLM-L6-v2`) run in-process — avoids needing a paid embedding API | Keeps embedding cost at $0 |
| Scraper | `httpx` + `BeautifulSoup4` (static pages) or `Playwright` if JS-rendered | Check `robots.txt` for both sites first |
| Containerization | Docker + docker-compose | You said "no Docker" for local dev — but the assignment explicitly requires **containerize the app**. Plan: write Dockerfiles now, and let the deployment platform (Railway/Render/Fly.io) build the image for you — you never need Docker installed locally |
| Deployment | **Railway** or **Render** (free/hobby tier, easiest with Dockerfile support) for backend+frontend; **Qdrant Cloud** (free 1GB cluster) for vectors | Gives you a public URL without managing infra |

### Why Qdrant Cloud instead of local Qdrant
You don't have Docker locally, and Qdrant's simplest self-host path is Docker. Qdrant Cloud has a permanent free tier (1 cluster, 1GB) — sign up, get a URL + API key, use it directly from FastAPI. No local install needed. The Docker requirement in the assignment is satisfied by containerizing the **FastAPI app** (and optionally React) for deployment — the deploy platform builds/runs that image, so you personally never run `docker build` on your machine.

## 3. Architecture

```
┌─────────────┐      HTTPS       ┌──────────────────┐
│   React SPA │ ───────────────▶ │   FastAPI backend │
│ (chat UI)   │ ◀─────────────── │  (Docker container)│
└─────────────┘   /api/chat      └────────┬──────────┘
                                           │
                    ┌──────────────────────┼───────────────────────┐
                    ▼                      ▼                       ▼
             ┌─────────────┐      ┌────────────────┐      ┌───────────────┐
             │   SQLite     │      │  Qdrant Cloud   │      │  OpenRouter   │
             │ (raw docs,   │      │ (embeddings /   │      │ (free LLM)    │
             │ chat log)    │      │  vector search) │      │               │
             └─────────────┘      └────────────────┘      └───────────────┘
                    ▲
                    │
             ┌─────────────┐
             │  Scraper job │  (offline/one-time or scheduled script)
             │ Dar Global + │
             │ Wasalt       │
             └─────────────┘
```

## 4. Repo Structure

```
ChatBoat/
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI app, CORS, routers
│   │   ├── config.py               # env vars (OpenRouter key, Qdrant URL/key)
│   │   ├── db.py                   # SQLite (SQLAlchemy) setup
│   │   ├── models.py               # SQLAlchemy models: Document, ChatMessage
│   │   ├── routers/
│   │   │   ├── chat.py             # POST /api/chat
│   │   │   └── health.py           # GET /health
│   │   ├── rag/
│   │   │   ├── embedder.py         # sentence-transformers wrapper
│   │   │   ├── vector_store.py     # Qdrant client wrapper (upsert/search)
│   │   │   ├── retriever.py        # top-k retrieval + prompt assembly
│   │   │   └── llm.py              # OpenRouter chat completion call
│   │   └── scraper/
│   │       ├── darglobal.py
│   │       ├── wasalt.py
│   │       └── ingest.py           # scrape -> chunk -> embed -> upsert to Qdrant + save raw to SQLite
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/ChatWindow.tsx
│   │   └── api/client.ts
│   ├── package.json
│   ├── Dockerfile
│   └── .env.example
├── docker-compose.yml              # local integration test only (backend+frontend; Qdrant stays cloud)
└── IMPLEMENTATION_PLAN.md
```

## 5. Data Pipeline (Scraping → RAG)

1. **Legal/ethical check**: fetch and read `https://www.darglobal.co.uk/robots.txt` and Wasalt's `robots.txt` before scraping; only hit allowed, publicly listed pages (property listings, project descriptions, FAQs, about/contact). No login-gated content.
2. **Scrape** with `httpx.get` + `BeautifulSoup` for static HTML; fall back to `playwright` only if content is rendered client-side (check via view-source first).
3. **Clean & chunk**: strip nav/footer boilerplate, split text into ~300–500 token chunks with slight overlap (e.g. `langchain`'s `RecursiveCharacterTextSplitter`, or a small hand-rolled splitter to avoid heavy deps).
4. **Store raw chunk + source URL + scraped_at** in SQLite (`documents` table) for traceability/debugging.
5. **Embed** each chunk locally with `sentence-transformers/all-MiniLM-L6-v2` (384-dim, fast, free, no API call).
6. **Upsert** vectors + payload (`text`, `source_url`, `site`) into a Qdrant collection (`property_docs`).
7. This ingestion step is a **one-off script** (`python -m app.scraper.ingest`) run at deploy/build time or manually — not on every request.

## 6. Chat / RAG Flow (per request)

1. React sends `POST /api/chat { message, session_id }`.
2. FastAPI embeds the user message (same MiniLM model).
3. Query Qdrant for top-k (e.g. 4) similar chunks.
4. Build a prompt: system instructions ("You are a property assistant for DarGlobal and Wasalt, answer only from the provided context, say you don't know if the answer isn't in context") + retrieved chunks + chat history (last N turns from SQLite) + user message.
5. Call **OpenRouter** chat completion endpoint (`https://openrouter.ai/api/v1/chat/completions`) with a `:free` model, using `OPENROUTER_API_KEY`.
6. Store user message + bot reply in SQLite (`chat_messages`), keyed by `session_id`.
7. Return the reply (and optionally the source URLs used) to React.

## 7. Key Environment Variables

```
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=meta-llama/llama-3.1-8b-instruct:free   # verify current free model name
QDRANT_URL=https://xxxx.cloud.qdrant.io
QDRANT_API_KEY=...
DATABASE_URL=sqlite:///./data/app.db
CORS_ORIGINS=https://your-frontend-url
```

## 8. Dockerization

- **backend/Dockerfile**: `python:3.11-slim` base, install `requirements.txt`, copy app, run `uvicorn app.main:app --host 0.0.0.0 --port 8000`. Mount/bundle a `data/` volume for the SQLite file (or accept ephemeral storage if the host wipes it, since SQLite here is just chat log + doc cache, not the source of truth for vectors).
- **frontend/Dockerfile**: multi-stage — `node:20` build stage (`npm run build`) → `nginx:alpine` to serve static files.
- **docker-compose.yml**: for your own local sanity-check only (backend + frontend containers; Qdrant/OpenRouter remain remote). You can validate this on any machine with Docker later (or skip local compose entirely and let Railway/Render build directly from the Dockerfiles — that's the more realistic path given you have no Docker locally).

## 9. Deployment Plan (no local Docker needed)

1. Push repo to GitHub.
2. **Qdrant Cloud**: create free cluster → get URL + API key.
3. **OpenRouter**: get API key, pick a `:free` model, sanity-test with a `curl` call.
4. **Backend**: deploy to **Railway** or **Render**
   - New service → "Deploy from GitHub" → point at `backend/Dockerfile`.
   - Set env vars from section 7.
   - Run ingestion once (Railway one-off job / Render shell) to populate Qdrant.
5. **Frontend**: deploy to **Vercel** (simplest for React/Vite, free tier, no Docker even needed there) or same Railway/Render service via its own Dockerfile.
   - Set `VITE_API_BASE_URL` to the deployed backend URL.
6. Confirm CORS on backend allows the deployed frontend origin.
7. Smoke-test the public URL end-to-end (ask a question about a DarGlobal/Wasalt property).
8. Hand over the **frontend URL** as the "working URL to access and test the chatbot directly."

## 10. Build Order (suggested milestones)

1. Scaffold backend (FastAPI skeleton, health check) + frontend (basic chat UI hitting a stub endpoint) — confirm wiring works end-to-end with a hardcoded reply.
2. Build scraper for DarGlobal, then Wasalt — save raw chunks to SQLite, print sample output, validate content quality.
3. Add embedding + Qdrant upsert (start with Qdrant Cloud free cluster from day one to avoid local Docker entirely).
4. Wire retrieval + OpenRouter call into `/api/chat`; test with real questions.
5. Add chat history persistence + session handling.
6. Polish React UI (loading states, error handling, message list).
7. Write Dockerfiles, verify they build cleanly (via platform build logs if no local Docker).
8. Deploy backend + frontend, run ingestion in production, smoke test.
9. Final pass: `robots.txt` compliance check, rate-limit the scraper (delay between requests), add basic input sanitization on chat endpoint.

## 11. Open Items to Confirm Before/During Build

- Exact current OpenRouter free model name (list changes — check `https://openrouter.ai/models?max_price=0` at build time).
- Whether DarGlobal/Wasalt pages are static HTML or JS-rendered (determines `httpx+BS4` vs `Playwright`).
- Which specific content areas are "publicly available" and in-scope (listings, projects, FAQs) vs excluded (any account-gated data).
- Free-tier limits on Railway/Render (may need to pick whichever currently has the more generous free web service tier — verify at deploy time as these change).
