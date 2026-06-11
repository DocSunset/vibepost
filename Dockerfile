# vibepost - social media scheduling and posting tool
# Copyright (C) 2026  Travis West
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Production single-container image: the FastAPI backend serves the built
# frontend. Used by fly.toml. For local development use docker-compose.yml
# or run the dev servers directly.

# ── frontend build ────────────────────────────────────────────────────────────
FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# ── backend ───────────────────────────────────────────────────────────────────
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app/ ./app/
COPY --from=frontend /build/dist /app/static

ENV DB_PATH=/data/vibepost.db \
    UPLOADS_DIR=/data/uploads \
    FRONTEND_DIST=/app/static \
    VIBEPOST_ENV=production

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
