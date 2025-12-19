#!/bin/bash

# Profile Bot - Start Frontend Only
# This script starts the frontend Vite development server

set -e

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

cd frontend
echo "Starting Frontend (Vite) on http://localhost:5173"
npm run dev

