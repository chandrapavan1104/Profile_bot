# Profile Bot Frontend

This is a lightweight React client that lets you interact with the Profile Bot FastAPI backend.

## Prerequisites

- Node.js 18+
- The FastAPI server running locally on `http://localhost:8000`

## Getting started

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server starts on http://localhost:5173 and proxies API calls to the backend at `/ask`, so make sure the FastAPI app is running before you test the UI.

## Build for production

```bash
npm run build
npm run preview
```

The build output lives in `frontend/dist/` and can be served by any static host.
