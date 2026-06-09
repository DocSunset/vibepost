#!/usr/bin/env bash
set -e

echo "==> Installing vibepost dependencies"

# Backend
cd backend
if [ ! -f .env ]; then
  cp .env.example .env
  echo "  Created backend/.env — fill in your API credentials there"
fi

if command -v uv &>/dev/null; then
  echo "  Using uv for Python deps"
  uv venv .venv --quiet
  uv pip install -r requirements.txt --quiet
else
  echo "  Using pip for Python deps"
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt --quiet
fi

cd ../frontend
echo "==> Installing frontend deps"
npm install --silent

echo ""
echo "Done! Run ./start.sh to launch vibepost."
