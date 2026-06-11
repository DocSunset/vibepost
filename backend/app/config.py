# vibepost - social media scheduling and posting tool
# Copyright (C) 2026  Travis West
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import secrets
import sys
from pathlib import Path

_repo = Path(__file__).resolve().parent.parent

DB_PATH = Path(os.environ.get("DB_PATH", str(_repo / "vibepost.db")))
UPLOADS_DIR = Path(os.environ.get("UPLOADS_DIR", str(_repo / "uploads")))

# "development" or "production". Production enforces a configured SECRET_KEY
# and marks session cookies Secure (HTTPS only).
ENV = os.environ.get("VIBEPOST_ENV", "development")
IS_PROD = ENV == "production"

SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    if IS_PROD:
        sys.exit(
            "FATAL: SECRET_KEY must be set in production. "
            "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(48))'"
        )
    # Ephemeral key for development — sessions reset on restart.
    SECRET_KEY = secrets.token_urlsafe(48)

# Public base URL of the backend, used to build OAuth redirect URIs.
OAUTH_CALLBACK_BASE = os.environ.get("OAUTH_CALLBACK_BASE", "http://localhost:8000")

# Where to send the browser after OAuth callbacks complete.
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")

# Comma-separated list of allowed CORS origins. When the frontend is served
# by this same server (production single-container deploy), no CORS is needed
# and this can stay empty.
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CORS_ORIGINS",
        "" if IS_PROD else "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if o.strip()
]

# If set (and the directory exists), the backend serves the built frontend
# from this path — single-container deployment.
FRONTEND_DIST = os.environ.get("FRONTEND_DIST", "")

SESSION_COOKIE_NAME = "vibepost_session"
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", str(7 * 24 * 3600)))

# Default lifetime of an invite token, in days.
INVITE_TTL_DAYS = int(os.environ.get("INVITE_TTL_DAYS", "14"))

MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(100 * 1024 * 1024)))
