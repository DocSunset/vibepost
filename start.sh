#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

# Backend
echo "==> Starting API server on http://localhost:8000"
cd "$ROOT/backend"
if [ -d .venv ]; then
  PYTHON=".venv/bin/python"
else
  PYTHON="python3"
fi
$PYTHON -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Frontend
echo "==> Starting frontend on http://localhost:5173"
cd "$ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "vibepost is running!"
echo "  App:  http://localhost:5173"
echo "  API:  http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM

wait
