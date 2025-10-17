# Profile Bot

Profile Bot is a Retrieval-Augmented Generation (RAG) assistant that demonstrates how to combine FastAPI, LangChain, and a static React UI to answer questions about a curated knowledge base. The project shows the full workflow—from document ingestion and vector storage to deployment on Google Cloud.

## Architecture overview

1. **Data ingestion**  
   `backend/scripts/ingest.py` loads source documents (markdown or text), slices them into overlapping chunks, and creates embeddings with OpenAI’s `text-embedding-3-small` model. The resulting Chroma vector store is written to a local directory and then synced to object storage so it can be reused by the deployed API.

2. **Question answering**  
   The FastAPI backend (`backend/app/main.py`) downloads the latest vector store on startup, wraps it in a LangChain `RetrievalQA` chain, and exposes a single `/ask` endpoint. Each request sends the question to GPT-4 along with the retrieved context, producing grounded answers.

3. **Frontend**  
   The React client under `frontend/` posts user questions to the API and renders responses. The production build is uploaded to a static hosting bucket or CDN, so the UI can be served independently of the backend.

## Repository layout

- `backend/` – FastAPI application, ingestion pipeline, and deployment Dockerfile.  
- `frontend/` – React single-page app; includes instructions for building and syncing to static hosting.  
- `docs/` – Deployment notes and runbooks, including Cloud Run guidance in `docs/deployment_gcp.md`.

## Local development

```bash
# Backend API
pip install -r backend/requirements.txt
export OPENAI_API_KEY=your_openai_key
uvicorn backend.app.main:app --reload

# Frontend (development server)
cd frontend
npm install
npm run dev
```

Set `DOCUMENTS_PATH` to a local folder if you want to ingest documents from disk; otherwise point it to a bucket-style URI that your environment can access.

## Rebuilding the vector store

```bash
docker build -f backend/Dockerfile -t profile-bot-api-local .
docker run --rm \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -e DOCUMENTS_PATH=gs://your-docs-bucket \
  -e VECTOR_STORE_PATH=/tmp/data_store \
  -e VECTOR_STORE_GCS_URI=gs://your-vector-store-bucket \
  profile-bot-api-local \
  python scripts/ingest.py
```

The same script is executed by a scheduled Cloud Run job in production, ensuring the vector store stays up to date whenever documents change.

## Deploying your own version

1. **Containerize the backend**
   ```bash
   export PROJECT_ID=<your-project>
   export REGION=<your-region>
   export REPO=<artifact-registry-repo>
   export AR_HOST=<region>-docker.pkg.dev
   export BACKEND_IMAGE=${AR_HOST}/${PROJECT_ID}/${REPO}/profile-bot-api:latest

   docker buildx build --platform linux/amd64 -f backend/Dockerfile -t ${BACKEND_IMAGE} .
   docker push ${BACKEND_IMAGE}
   ```

2. **Create an ingestion job** (see `docs/deployment_gcp.md` for the full command set). The job should mount/read your documents, write the Chroma files to `/tmp/data_store`, and upload them to a persistent bucket.

3. **Deploy the API to Cloud Run**
   ```bash
   gcloud run deploy profile-bot-api \
     --image ${BACKEND_IMAGE} \
     --region ${REGION} \
     --allow-unauthenticated \
     --port 8080 \
     --timeout 600s \
     --set-env-vars VECTOR_STORE_PATH=/tmp/data_store,VECTOR_STORE_GCS_URI=gs://your-vector-store-bucket,ALLOWED_ORIGINS=https://your-frontend-host \
     --set-secrets OPENAI_API_KEY=OPENAI_API_KEY:latest \
     --service-account <service-account-email>
   ```

4. **Host the frontend**
   ```bash
   cd frontend
   npm run build
   gsutil -m rsync -r dist gs://your-frontend-bucket
   ```
   or deploy with your preferred static host/CDN.

By following these steps you can adapt the stack to your own dataset: gather documents, run the ingestion job, deploy the API, and publish the UI—resulting in a fully managed RAG application on the cloud provider of your choice.
