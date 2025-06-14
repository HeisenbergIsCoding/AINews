#!/usr/bin/env bash
#
# start_dev.sh
#
# Concurrently start backend (FastAPI / Uvicorn) and frontend (Vite) dev servers.
# Usage: chmod +x start_dev.sh && ./start_dev.sh
#
set -e

# Function to clean up background processes on exit (Ctrl+C or script termination)
cleanup() {
  echo ""
  echo "Stopping dev servers..."
  if [[ -n "$BACKEND_PID" ]] && ps -p $BACKEND_PID > /dev/null 2>&1; then
    kill $BACKEND_PID
  fi
  if [[ -n "$FRONTEND_PID" ]] && ps -p $FRONTEND_PID > /dev/null 2>&1; then
    kill $FRONTEND_PID
  fi
  wait
}

trap cleanup EXIT

# Start backend (run from project root so import paths and DB paths resolve correctly)
uvicorn backend.app.main:app --reload --port 8000 &
BACKEND_PID=$!
echo "Backend started (PID: $BACKEND_PID) - http://127.0.0.1:8000"

# Start frontend
(
  cd frontend
  # Install dependencies automatically if node_modules is missing (first-time setup)
  if [ ! -d node_modules ]; then
    echo "Installing frontend dependencies..."
    npm install
  fi
  npm run dev
) &
FRONTEND_PID=$!
echo "Frontend started (PID: $FRONTEND_PID) - http://127.0.0.1:5173 (default Vite port)"

echo ""
echo "Backend and Frontend dev servers are running. Press Ctrl+C to stop."

# Wait for background jobs
wait