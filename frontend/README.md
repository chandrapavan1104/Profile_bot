# Profile Bot Frontend

This is a lightweight React client that lets you interact with the Profile Bot FastAPI backend. The production bundle is uploaded to the public bucket `gs://profile-bot-ui` and served at https://storage.googleapis.com/profile-bot-ui.

## Prerequisites

- Node.js 18+
- The FastAPI server running locally on `http://localhost:8000`

## Getting started

```bash
cd frontend
npm install
cp .env.example .env # optional: adjust API targets as needed
npm run dev
```

Environment variables:

- `VITE_API_PROXY_TARGET` (dev only) – backend URL used by the Vite dev proxy. Default: `http://localhost:8000`
- `VITE_API_BASE_URL` (build time) – absolute backend URL baked into the production bundle. Leave empty to use relative `/ask`.

The Vite dev server starts on http://localhost:5173 and proxies API calls to the backend at `/ask`, so make sure the FastAPI app is running before you test the UI.

## Build for production

```bash
npm run build
gsutil -m rsync -r dist gs://profile-bot-ui
```

You can optionally run `npm run preview` to view the static build locally before syncing it to Cloud Storage.
