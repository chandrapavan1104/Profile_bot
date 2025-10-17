# Profile Bot

Profile Bot is a Retrieval-Augmented Generation (RAG) assistant that answers questions about Chandra Pavan Reddy Chada's experience and projects. The backend is a FastAPI service deployed on Cloud Run, and the frontend is a static React build hosted on Cloud Storage.

## How it works

1. **Document ingestion**
   - The `backend/scripts/ingest.py` script loads markdown files from the `gs://profile_bot_docs` bucket (or a local `docs/` directory when developing).
   - Documents are chunked with `langchain_text_splitters` and embedded using OpenAI's `text-embedding-3-small` model.
   - The resulting Chroma vector store is persisted to `/tmp/data_store`, then uploaded to the `gs://profile-bot-chroma` bucket for use in production.

2. **Query answering**
   - On startup, the FastAPI app downloads the latest vector store from Cloud Storage into `/tmp/data_store`.
   - Queries posted to `/ask` are answered by a LangChain `RetrievalQA` chain that performs similarity search on the vector store and responds with GPT-4 (temperature 0.2) using the persona prompt in `backend/app/persona_prompt.py`.

3. **Frontend**
   - The React client (in `frontend/`) calls the `/ask` endpoint.
   - Production builds are uploaded to `gs://profile-bot-ui`, which is served directly via `https://storage.googleapis.com/profile-bot-ui`.

## Repository layout

- `backend/` – FastAPI application, ingestion script, and Dockerfile.
- `frontend/` – React application source and docs for building/syncing to Cloud Storage.
- `docs/` – Deployment guides, including detailed Cloud Run instructions (`docs/deployment_gcp.md`).

## Running locally

```bash
# Backend
pip install -r backend/requirements.txt
export OPENAI_API_KEY=your-key
uvicorn backend.app.main:app --reload

# Frontend (dev server)
cd frontend
npm install
npm run dev
```

Set `VECTOR_STORE_PATH` and `DOCUMENTS_PATH` if you want to test ingestion locally against local files instead of GCS.

## Regenerating the vector store

```bash
docker build -f backend/Dockerfile -t profile-bot-api-local .
docker run --rm \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -e DOCUMENTS_PATH=gs://profile_bot_docs \
  -e VECTOR_STORE_PATH=/tmp/data_store \
  -e VECTOR_STORE_GCS_URI=gs://profile-bot-chroma \
  profile-bot-api-local \
  python scripts/ingest.py
```

In Cloud Run, the same script runs via the `profile-bot-ingest` job defined in `docs/deployment_gcp.md`.

## Deploying to Google Cloud

1. **Build & push backend**
   ```bash
   export PROJECT_ID=profilebot-474605
   export REGION=us-west2
   export REPO=profile-bot
   export AR_HOST=us-west2-docker.pkg.dev
   export BACKEND_IMAGE=${AR_HOST}/${PROJECT_ID}/${REPO}/profile-bot-api:latest

   docker buildx build --platform linux/amd64 -f backend/Dockerfile -t ${BACKEND_IMAGE} .
   docker push ${BACKEND_IMAGE}
   ```

2. **Run ingestion job**
   ```bash
   gcloud run jobs execute profile-bot-ingest --region ${REGION}
   ```

3. **Deploy backend service**
   ```bash
   gcloud run deploy profile-bot-api \
     --image ${BACKEND_IMAGE} \
     --region ${REGION} \
     --allow-unauthenticated \
     --port 8080 \
     --timeout 600s \
     --set-env-vars VECTOR_STORE_PATH=/tmp/data_store,VECTOR_STORE_GCS_URI=gs://profile-bot-chroma,ALLOWED_ORIGINS=https://storage.googleapis.com,http://localhost:5173 \
     --set-secrets OPENAI_API_KEY=OPENAI_API_KEY:latest \
     --service-account profile-bot-sa@${PROJECT_ID}.iam.gserviceaccount.com
   ```

4. **Publish frontend**
   ```bash
   cd frontend
   npm run build
   gsutil -m rsync -r dist gs://profile-bot-ui
   ```

All deployment steps are captured with additional context in `docs/deployment_gcp.md`.
