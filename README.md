# Profile Bot (Monorepo)

Profile Bot is a portfolio website + RAG assistant in a single repository.

- Frontend: React/Vite app in `frontend/`, deployed to Firebase Hosting through GitHub Actions.
- Backend: FastAPI + LangChain app in `backend/`, deployed to Cloud Run.

## Monorepo layout

- `frontend/` – portfolio UI, chatbot UI, Firebase config (`firebase.json`, `.firebaserc`)
- `backend/` – FastAPI API, vector retrieval logic, ingestion script
- `.github/workflows/` – Firebase Hosting CI/CD workflows
- `ops/monitoring/` – scripts to bootstrap Cloud Run/OpenAI dashboards and alerts
- `docs/` – deployment notes and runbooks

## Current deployment model

1. Frontend deploy (automatic)
   - Trigger: push to `main`
   - Workflow: `.github/workflows/firebase-hosting-merge.yml`
   - Hosting: Firebase project `profilebot-474605`

2. Frontend preview deploy (automatic)
   - Trigger: pull request
   - Workflow: `.github/workflows/firebase-hosting-pull-request.yml`

3. Backend deploy (manual script)
   - Script: `deploy-cloudrun.sh`
   - Target: Cloud Run service `profile-bot-api-usc` in `us-central1`

## Required GitHub secret (in this repo)

Set this in `Profile_bot` GitHub repo settings:

- `FIREBASE_SERVICE_ACCOUNT_PROFILEBOT_474605`

Without this, Firebase Hosting workflows will fail.

## Required runtime secrets (GCP Secret Manager)

- `OPENAI_API_KEY`
- `LANGSMITH_API_KEY` (optional)

Cloud Run is configured to read these via `--set-secrets`.

## Local development

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

If needed, set frontend env in `frontend/.env`:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## Backend data ingestion

Ingestion script:

- `backend/scripts/ingest.py`

It chunks documents, creates embeddings, and writes a Chroma vector store (then uploads/syncs for production usage).

## Monitoring setup (Cloud Run + OpenAI)

Bootstrap scripts:

- `ops/monitoring/setup_cloudrun_monitoring.sh`
- `ops/monitoring/setup_uptime_monitoring.sh`
- `ops/monitoring/setup_openai_observability.sh`

These create dashboards, log-based metrics, uptime checks, and alert policies.

## Notes

- The old standalone frontend repo (`portfolio-website`) is intentionally left as-is.
- This repo is now the single source of truth for both frontend and backend.
