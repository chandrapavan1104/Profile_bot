# Profile Bot Frontend

Frontend for the Profile Bot portfolio website (React + Vite).

This frontend is deployed through GitHub Actions from the monorepo root:

- `.github/workflows/firebase-hosting-merge.yml` (push to `main`)
- `.github/workflows/firebase-hosting-pull-request.yml` (PR preview)

Firebase config is kept in this directory:

- `frontend/firebase.json`
- `frontend/.firebaserc`

## Local development

Prerequisites:

- Node.js 18+
- Backend running on `http://127.0.0.1:8000` (or configure another URL)

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

## Environment variables

- `VITE_API_BASE_URL`
  - Backend base URL for API requests.
  - Example: `http://127.0.0.1:8000`

## Production build

```bash
cd frontend
npm run build
npm run preview
```

Publishing to Firebase Hosting is handled by GitHub Actions; no manual `gsutil rsync` is required.
