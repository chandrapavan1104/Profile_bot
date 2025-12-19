# Profile Bot - Quick Start Commands

This file contains commands for executing the frontend and backend servers.

## Quick Start (Both Servers)

Run both servers together:
```bash
./start.sh
```

## Individual Server Commands

### Backend Only

Using the script:
```bash
./start-backend.sh
```

Or manually:
```bash
source profile_bot_env/bin/activate
cd backend
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Backend URLs:**
- API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

### Frontend Only

Using the script:
```bash
./start-frontend.sh
```

Or manually:
```bash
cd frontend
npm run dev
```

**Frontend URL:**
- Application: http://localhost:5173

## Manual Commands (One-liners)

### Backend
```bash
cd backend && source ../profile_bot_env/bin/activate && python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd frontend && npm run dev
```

## Background Execution

To run both servers in the background:

### Backend (Background)
```bash
cd backend && source ../profile_bot_env/bin/activate && nohup python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 &
```

### Frontend (Background)
```bash
cd frontend && nohup npm run dev > /tmp/frontend.log 2>&1 &
```

## Stop Servers

To stop servers running in the background:
```bash
# Find and kill backend
lsof -ti:8000 | xargs kill -9

# Find and kill frontend
lsof -ti:5173 | xargs kill -9
```

Or stop all:
```bash
lsof -ti:8000,5173 | xargs kill -9
```

## Prerequisites

1. **Backend:**
   - Python 3.11+
   - Virtual environment activated (`profile_bot_env`)
   - Dependencies installed: `pip install -r backend/requirements.txt`
   - Environment variables set (e.g., `OPENAI_API_KEY`)

2. **Frontend:**
   - Node.js installed
   - Dependencies installed: `cd frontend && npm install`

