# Profile Bot

Profile Bot is an AI-powered portfolio website with a built-in assistant that answers questions about experience, projects, and skills using Retrieval-Augmented Generation (RAG).

It combines a React frontend and a FastAPI backend. The backend retrieves relevant context from a vector store and uses OpenAI models to generate grounded responses.

## What this project does

- Serves a portfolio website with an integrated AI assistant
- Supports streaming responses (`/ask/stream`) for better UX
- Uses a vector database (Chroma) for context-aware answers
- Includes ingestion tools to rebuild/update the knowledge base
- Includes production monitoring scripts for Cloud Run and OpenAI dependency health

## High-level architecture

1. User sends a question from the website.
2. Frontend calls backend endpoint (`/ask` or `/ask/stream`).
3. Backend retrieves relevant chunks from Chroma vector store.
4. Backend composes prompt with persona + retrieved context.
5. OpenAI model generates the answer.
6. Backend returns response (or stream) to frontend.
7. Structured logs feed monitoring dashboards and alerts.

## Tech stack

- Frontend: React, Vite
- Backend: FastAPI, Uvicorn
- AI/RAG: LangChain, OpenAI, Chroma
- Storage/Cloud: Google Cloud Run, Google Cloud Storage, Firebase Hosting
- Observability: Cloud Logging, Cloud Monitoring, uptime checks, alert policies
- CI/CD: GitHub Actions (Firebase Hosting deploy workflows)

## Project structure

- `frontend/` - portfolio UI and chatbot interface
- `backend/` - FastAPI API, retrieval logic, ingestion scripts
- `ops/monitoring/` - monitoring dashboard/alert setup scripts
- `docs/` - deployment and operational notes

## API endpoints

- `GET /health` - health check
- `POST /ask` - standard response
- `POST /ask/stream` - server-sent event streaming response

## Required keys and configuration

### Backend required

- `OPENAI_API_KEY` (required)

### Backend optional but recommended

- `LANGSMITH_API_KEY` (for tracing/observability)
- `VECTOR_STORE_GCS_URI` (if vector store is pulled from GCS)
- `ALLOWED_ORIGINS` (CORS allow-list)
- `CHAT_MODEL`, `EMBEDDING_MODEL`, `RETRIEVER_K`, `OPENAI_MAX_RETRIES` (runtime tuning)

### Frontend

- `VITE_API_BASE_URL` (backend base URL)

See `.env.example` and `frontend/.env.example` for templates.

## Local development

### 1) Start backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 2) Start frontend

```bash
cd frontend
npm install
npm run dev
```

Open the app from the URL printed by Vite (typically `http://127.0.0.1:5173`).

## Knowledge base ingestion

Use `backend/scripts/ingest.py` to rebuild the vector store when source content changes.

Typical flow:

1. Collect source docs (portfolio content, markdown/text, optional GitHub metadata).
2. Run ingestion script to chunk + embed content.
3. Persist/upload vector store.
4. Restart/redeploy backend to use updated store.

## Deployment overview

- Frontend is built and deployed to Firebase Hosting via GitHub Actions.
- Backend is containerized and deployed to Cloud Run.
- Runtime secrets should be stored in Secret Manager (not in source code).

## Monitoring and operations

Scripts in `ops/monitoring/` can create:

- Cloud Run service dashboards
- Uptime checks and alerts
- OpenAI dependency health metrics and alerts

## Security notes

- Never commit real API keys or tokens.
- Keep secrets in GitHub Secrets and/or Google Secret Manager.
- Rotate keys immediately if exposed.
