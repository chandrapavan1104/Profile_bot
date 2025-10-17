# GCP Deployment Guide

Deploy the Profile Bot backend to Google Cloud Run. The React UI is built separately and hosted from the public GCS bucket `gs://profile-bot-ui`. The commands below are pre-filled with your project details.

## 1. Prerequisites

- Google Cloud project (`profilebot-474605`) with Cloud Run, Cloud Build, Artifact Registry, and Cloud Storage APIs enabled.
- `gcloud` CLI authenticated against the project.
- Artifact Registry Docker repository (`profile-bot`) in region `us-west2`.
- Cloud Storage buckets:
  - `profile_bot_docs` for source documents (Markdown files already uploaded).
  - `profile-bot-chroma` for the persistent Chroma vector store (ingestion uploads here; backend downloads on startup).
- Static site bucket `profile-bot-ui` that serves the compiled React frontend at `https://storage.googleapis.com/profile-bot-ui`.
- Service account `profile-bot-sa@profilebot-474605.iam.gserviceaccount.com` with the following permissions, attached to both Cloud Run services and the ingestion job:
  - `roles/run.invoker`
  - `roles/storage.objectAdmin` (read/write to the bucket)
  - `roles/artifactregistry.reader`
- OpenAI API key stored in Secret Manager **or** available when you deploy (currently in `.env`; plan to store in Secret Manager).

> Required variables you will need:
> - `PROJECT_ID=profilebot-474605`
> - `REGION=us-west2`
> - Artifact Registry repo name `profile-bot`
> - Artifact Registry host `us-west2-docker.pkg.dev`
> - Backend image tag `profile-bot-api:latest`
> - Cloud Storage bucket name `profile-bot-chroma` (vector store)
> - Optional documents bucket `profile_bot_docs`

## 2. Build & Push Images

```bash
export PROJECT_ID=profilebot-474605
export REGION=us-west2
export REPO=profile-bot
export AR_HOST=us-west2-docker.pkg.dev
export BACKEND_IMAGE=${AR_HOST}/${PROJECT_ID}/${REPO}/profile-bot-api:latest

gcloud auth configure-docker ${AR_HOST}

# Backend (FastAPI)
docker build -f backend/Dockerfile -t ${BACKEND_IMAGE} .
docker push ${BACKEND_IMAGE}
```

## 3. Prepare the Vector Store Bucket

1. Bucket `profile-bot-chroma` holds the vector store artifacts (already created). Runtime code will download/upload objects instead of using GCS Fuse.
2. Ensure `profile-bot-sa@profilebot-474605.iam.gserviceaccount.com` has `storage.objectAdmin` on both buckets.

## 4. Populate the Vector Store (Cloud Run Job)

Create a Cloud Run Job that runs the ingestion script and writes the embeddings into the mounted bucket.

```bash
gcloud run jobs create profile-bot-ingest \
  --image ${BACKEND_IMAGE} \
  --region ${REGION} \
  --task-timeout 30m \
  --set-env-vars VECTOR_STORE_PATH=/tmp/data_store,DOCUMENTS_PATH=gs://profile_bot_docs,VECTOR_STORE_GCS_URI=gs://profile-bot-chroma \
  --set-secrets OPENAI_API_KEY=OPENAI_API_KEY:latest \
  --service-account profile-bot-sa@${PROJECT_ID}.iam.gserviceaccount.com \
  --command python \
  --args scripts/ingest.py
```

Run the job whenever your source documents change:

```bash
gcloud run jobs execute profile-bot-ingest --region ${REGION}
```

## 5. Deploy the Backend Service

```bash
gcloud run deploy profile-bot-api \
  --image ${BACKEND_IMAGE} \
  --region ${REGION} \
  --allow-unauthenticated \
  --port 8080 \
  --set-env-vars VECTOR_STORE_PATH=/tmp/data_store,VECTOR_STORE_GCS_URI=gs://profile-bot-chroma \
  --set-secrets OPENAI_API_KEY=OPENAI_API_KEY:latest \
  --set-env-vars ALLOWED_ORIGINS=https://storage.googleapis.com/profile-bot-ui \
  --service-account profile-bot-sa@${PROJECT_ID}.iam.gserviceaccount.com
```

Notes:
- Replace `ALLOWED_ORIGINS` with the final HTTPS URL of the frontend. You can list multiple origins separated by commas (for example, a custom domain in addition to the storage URL).
- If you are using Secret Manager, use `--set-secrets` instead of `--set-env-vars` for sensitive values.

## 6. Update the Static Frontend

```bash
cd frontend
npm install
npm run build
gsutil -m rsync -r dist gs://profile-bot-ui
```

## 7. Verify & Automate

- Hit the backend health by sending a POST to `/ask`. The service downloads the latest vector store from `gs://profile-bot-chroma` during startup.
- Visit `https://storage.googleapis.com/profile-bot-ui/index.html` (or a custom domain if configured) and submit a question.
- Add Cloud Build triggers or GitHub Actions to automate image builds and deployments.
- Schedule the ingestion job or trigger it via Cloud Scheduler when documents change.

## 8. Optional Enhancements

- Configure a custom domain for each Cloud Run service.
- Move secrets (e.g. `OPENAI_API_KEY`) to Secret Manager and mount them as env vars.
- Store documents in a dedicated bucket and mount it for both the ingestion job and the backend (`DOCUMENTS_PATH`).
- Set up HTTPS load balancing (Cloud Run service can sit behind Cloud Endpoints or Cloud Armor if needed).
