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

import hashlib
import time
import threading
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from .config import IS_PROD, SECRET_KEY, SESSION_COOKIE_NAME, SESSION_TTL_SECONDS
from .database import get_db
from .models import User

JWT_ALGORITHM = "HS256"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "epoch": user.session_epoch or 0,
        "iat": now,
        "exp": now + timedelta(seconds=SESSION_TTL_SECONDS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=IS_PROD,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = int(payload["sub"])
        epoch = int(payload.get("epoch", 0))
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(401, "Invalid or expired session")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(401, "Account no longer exists")
    if epoch != (user.session_epoch or 0):
        raise HTTPException(401, "Session has been revoked")
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, "Admin access required")
    return user


class RateLimiter:
    """Small in-memory sliding-window rate limiter, keyed by client IP.

    Suitable for a single-process deployment; replace with a shared store if
    the backend ever runs more than one instance.
    """

    def __init__(self, max_attempts: int, window_seconds: int):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def check(self, request: Request) -> None:
        self.check_key(_client_ip(request))

    def check_key(self, key: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            attempts = [t for t in self._attempts.get(key, []) if t > cutoff]
            if len(attempts) >= self.max_attempts:
                raise HTTPException(429, "Too many attempts; try again later")
            attempts.append(now)
            self._attempts[key] = attempts
            # Opportunistic cleanup so the map doesn't grow without bound
            if len(self._attempts) > 10000:
                self._attempts = {
                    k: [t for t in v if t > cutoff]
                    for k, v in self._attempts.items()
                    if any(t > cutoff for t in v)
                }


def _client_ip(request: Request) -> str:
    # Fly-Client-IP is set by Fly's edge proxy and cannot be forged by the
    # client. Never trust X-Forwarded-For for rate limiting: clients control
    # its left-most entries, which would grant a fresh bucket per request.
    fly_ip = request.headers.get("fly-client-ip")
    if fly_ip:
        return fly_ip.strip()
    return request.client.host if request.client else "unknown"


login_limiter = RateLimiter(max_attempts=10, window_seconds=300)
signup_limiter = RateLimiter(max_attempts=5, window_seconds=300)
