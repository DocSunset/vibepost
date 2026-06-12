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

# Transactional email (sign-in links). Without an API key, emails are logged
# to the console instead — fine for development, useless in production.
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "vibepost <login@localhost>")
if IS_PROD and RESEND_API_KEY and "localhost" in EMAIL_FROM:
    sys.exit("FATAL: set EMAIL_FROM to a sender on your verified domain, e.g. 'vibepost <login@your-domain>'")

# How long an emailed sign-in link stays valid.
LOGIN_LINK_TTL_SECONDS = int(os.environ.get("LOGIN_LINK_TTL_SECONDS", str(15 * 60)))

# WebAuthn relying party: passkeys are bound to this domain. Defaults to the
# frontend's hostname, which is correct unless you serve from multiple hosts.
from urllib.parse import urlparse as _urlparse  # noqa: E402
WEBAUTHN_RP_ID = os.environ.get("WEBAUTHN_RP_ID", _urlparse(FRONTEND_URL).hostname or "localhost")
WEBAUTHN_RP_NAME = "vibepost"
# Origins allowed to complete WebAuthn ceremonies.
WEBAUTHN_ORIGINS = [o for o in {FRONTEND_URL.rstrip("/"), OAUTH_CALLBACK_BASE.rstrip("/")} if o]

MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(100 * 1024 * 1024)))
