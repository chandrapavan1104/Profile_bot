#!/bin/bash

# Profile Bot - Start Backend Only
# This script starts the backend FastAPI server

set -e

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if virtual environment exists
if [ ! -d "profile_bot_env" ]; then
    echo "Error: Virtual environment 'profile_bot_env' not found."
    exit 1
fi

# Activate virtual environment and start backend
source profile_bot_env/bin/activate
cd backend
echo "Starting Backend (FastAPI) on http://localhost:8000"
echo "API Docs available at http://localhost:8000/docs"
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

