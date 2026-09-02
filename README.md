# DarGlobal & Wasalt Property Chatbot

RAG chatbot over publicly scraped DarGlobal + Wasalt property data. FastAPI backend, React frontend, SQLite for chat/doc metadata, Qdrant for vectors, OpenRouter for the LLM.

See `IMPLEMENTATION_PLAN.md` for the full design.

## Local setup (no Docker required)

### Backend

```bash
cd backend
py -3.12 -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
./.venv/Scripts/python.exe -m playwright install chromium
cp .env.example .env   # fill in OPENROUTER_API_KEY, QDRANT_URL, QDRANT_API_KEY
```

Run the scraper + ingestion once to populate Qdrant + SQLite:

```bash
./.venv/Scripts/python.exe -m app.scraper.ingest
```

(Set `LIMIT_PER_SITE=5` env var for a quick smoke-test crawl before running the full one.)

Start the API:

```bash
./.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_BASE_URL=http://localhost:8000
npm run dev
```

Open http://localhost:5173.

## Deployment (no local Docker needed)

1. Push to GitHub.
2. Create a free Qdrant Cloud cluster at cloud.qdrant.io — copy URL + API key.
3. Get an OpenRouter API key and pick a `:free` model.
4. Deploy `backend/` (Dockerfile-based) to Railway or Render, set the env vars from `.env.example`.
5. Run `python -m app.scraper.ingest` once against the deployed backend (one-off job/shell) to populate Qdrant.
6. Deploy `frontend/` to Vercel or the same platform, set `VITE_API_BASE_URL` to the backend's public URL.
7. Confirm `CORS_ORIGINS` on the backend includes the frontend's deployed URL.
