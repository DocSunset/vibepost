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

"""Platform authentication: connecting social media accounts.

Not to be confused with app authentication (signing in to vibepost itself),
which lives in routers/account.py.
"""

import json
import secrets
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..config import FRONTEND_URL, OAUTH_CALLBACK_BASE
from ..database import get_db
from ..models import Channel, User
from ..ownership import get_user_setting, owned_profile, set_user_setting
from ..platforms import bluesky as bluesky_platform
from ..platforms import linkedin as linkedin_platform
from ..platforms import meta as meta_platform
from ..schemas import BlueskyConnectRequest
from ..security import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

# OAuth state tokens: single-use, short-lived, bound to the user who started
# the flow. In-memory is fine for a single-process deployment.
_oauth_states: dict[str, dict] = {}
_STATE_TTL_SECONDS = 600

SETTINGS_KEYS = [
    "meta_app_id",
    "meta_app_secret",
    "threads_app_id",
    "threads_app_secret",
    "linkedin_client_id",
    "linkedin_client_secret",
    "public_media_base_url",
]


def _new_state(user_id: int, profile_id: int, platform: str) -> str:
    now = time.monotonic()
    # Drop expired states so the dict can't grow without bound
    for key in [k for k, v in _oauth_states.items() if now - v["created"] > _STATE_TTL_SECONDS]:
        _oauth_states.pop(key, None)
    state = secrets.token_urlsafe(24)
    _oauth_states[state] = {
        "user_id": user_id,
        "profile_id": profile_id,
        "platform": platform,
        "created": now,
    }
    return state


def _pop_state(state: str, platform: str) -> dict | None:
    data = _oauth_states.pop(state, None)
    if not data or data["platform"] != platform:
        return None
    if time.monotonic() - data["created"] > _STATE_TTL_SECONDS:
        return None
    return data


def _redirect_uri(platform: str) -> str:
    # The auth router is mounted under /api
    return f"{OAUTH_CALLBACK_BASE.rstrip('/')}/api/auth/{platform}/callback"


@router.get("/settings")
def get_settings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    result = {}
    for k in SETTINGS_KEYS:
        v = get_user_setting(db, user.id, k)
        if k.endswith("_secret") and v:
            result[k] = "***"
        else:
            result[k] = v or ""
    # Let the UI display the exact redirect URIs the user must register
    result["oauth_redirect_uris"] = {
        p: _redirect_uri(p) for p in ("meta", "threads", "linkedin")
    }
    return result


@router.post("/settings")
def update_settings(body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    for key, value in body.items():
        if key not in SETTINGS_KEYS:
            continue
        if isinstance(value, str) and value and value != "***":
            set_user_setting(db, user.id, key, value)
    db.commit()
    return {"ok": True}


@router.post("/bluesky")
def connect_bluesky(
    body: BlueskyConnectRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owned_profile(db, user, body.profile_id)
    try:
        profile_info = bluesky_platform.test_bluesky_credentials(body.handle, body.app_password)
    except Exception:
        raise HTTPException(400, "Bluesky authentication failed — check your handle and app password")

    existing = db.query(Channel).filter(
        Channel.profile_id == body.profile_id,
        Channel.platform == "bluesky",
        Channel.platform_user_id == profile_info["did"],
    ).first()

    creds = json.dumps({"handle": body.handle, "app_password": body.app_password})
    display = profile_info.get("display_name") or f"@{profile_info['handle']}"
    if existing:
        existing.credentials = creds
        existing.display_name = display
        existing.is_connected = True
    else:
        db.add(Channel(
            profile_id=body.profile_id,
            platform="bluesky",
            display_name=display,
            platform_user_id=profile_info["did"],
            credentials=creds,
            is_connected=True,
        ))

    db.commit()
    return {"ok": True, "handle": profile_info["handle"]}


@router.get("/meta/url")
def meta_oauth_url(profile_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned_profile(db, user, profile_id)
    client_id = get_user_setting(db, user.id, "meta_app_id")
    if not client_id:
        raise HTTPException(400, "Meta App ID not configured")

    state = _new_state(user.id, profile_id, "meta")
    url = meta_platform.facebook_oauth_url(client_id, _redirect_uri("meta"), state)
    return {"url": url}


@router.get("/meta/callback")
def meta_callback(code: str = Query(...), state: str = Query(...), db: Session = Depends(get_db)):
    state_data = _pop_state(state, "meta")
    if not state_data:
        return RedirectResponse(f"{FRONTEND_URL}/?error=invalid_state")

    user_id = state_data["user_id"]
    profile_id = state_data["profile_id"]
    client_id = get_user_setting(db, user_id, "meta_app_id")
    client_secret = get_user_setting(db, user_id, "meta_app_secret")

    try:
        token_data = meta_platform.exchange_code_for_token(code, client_id, client_secret, _redirect_uri("meta"))
        short_token = token_data["access_token"]
        long_data = meta_platform.get_long_lived_token(short_token, client_id, client_secret)
        user_token = long_data["access_token"]

        pages = meta_platform.get_pages(user_token)
        for page in pages:
            page_id = page["id"]
            page_name = page["name"]
            page_token = page["access_token"]

            fb_creds = json.dumps({"page_id": page_id, "page_token": page_token})
            _upsert_channel(db, profile_id, "facebook", page_name, page_id, fb_creds)

            ig_account = page.get("instagram_business_account")
            if ig_account:
                ig_id = ig_account["id"]
                ig_name = ig_account.get("username") or ig_account.get("name") or page_name
                ig_creds = json.dumps({"ig_user_id": ig_id, "access_token": page_token})
                _upsert_channel(db, profile_id, "instagram", f"@{ig_name}", ig_id, ig_creds)

        db.commit()
    except Exception:
        return RedirectResponse(f"{FRONTEND_URL}/?error=meta_connection_failed")

    return RedirectResponse(f"{FRONTEND_URL}/?success=meta")


@router.get("/threads/url")
def threads_oauth_url(profile_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned_profile(db, user, profile_id)
    client_id = get_user_setting(db, user.id, "threads_app_id") or get_user_setting(db, user.id, "meta_app_id")
    if not client_id:
        raise HTTPException(400, "Threads App ID not configured")

    state = _new_state(user.id, profile_id, "threads")
    url = meta_platform.threads_oauth_url(client_id, _redirect_uri("threads"), state)
    return {"url": url}


@router.get("/threads/callback")
def threads_callback(code: str = Query(...), state: str = Query(...), db: Session = Depends(get_db)):
    state_data = _pop_state(state, "threads")
    if not state_data:
        return RedirectResponse(f"{FRONTEND_URL}/?error=invalid_state")

    user_id = state_data["user_id"]
    profile_id = state_data["profile_id"]
    client_id = get_user_setting(db, user_id, "threads_app_id") or get_user_setting(db, user_id, "meta_app_id")
    client_secret = get_user_setting(db, user_id, "threads_app_secret") or get_user_setting(db, user_id, "meta_app_secret")

    try:
        token_data = meta_platform.exchange_threads_code(code, client_id, client_secret, _redirect_uri("threads"))
        access_token = token_data["access_token"]

        profile_info = meta_platform.get_threads_profile(access_token)
        threads_id = profile_info["id"]
        display = profile_info.get("username") or profile_info.get("name") or threads_id

        creds = json.dumps({"threads_user_id": threads_id, "access_token": access_token})
        _upsert_channel(db, profile_id, "threads", f"@{display}", threads_id, creds)
        db.commit()
    except Exception:
        return RedirectResponse(f"{FRONTEND_URL}/?error=threads_connection_failed")

    return RedirectResponse(f"{FRONTEND_URL}/?success=threads")


@router.get("/linkedin/url")
def linkedin_oauth_url(profile_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned_profile(db, user, profile_id)
    client_id = get_user_setting(db, user.id, "linkedin_client_id")
    if not client_id:
        raise HTTPException(400, "LinkedIn Client ID not configured")

    state = _new_state(user.id, profile_id, "linkedin")
    url = linkedin_platform.linkedin_oauth_url(client_id, _redirect_uri("linkedin"), state)
    return {"url": url}


@router.get("/linkedin/callback")
def linkedin_callback(code: str = Query(...), state: str = Query(...), db: Session = Depends(get_db)):
    state_data = _pop_state(state, "linkedin")
    if not state_data:
        return RedirectResponse(f"{FRONTEND_URL}/?error=invalid_state")

    user_id = state_data["user_id"]
    profile_id = state_data["profile_id"]
    client_id = get_user_setting(db, user_id, "linkedin_client_id")
    client_secret = get_user_setting(db, user_id, "linkedin_client_secret")

    try:
        token_data = linkedin_platform.exchange_code_for_token(code, client_id, client_secret, _redirect_uri("linkedin"))
        access_token = token_data["access_token"]

        person = linkedin_platform.get_profile(access_token)
        person_id = person["id"]
        first = person.get("localizedFirstName", "")
        last = person.get("localizedLastName", "")
        display_name = f"{first} {last}".strip() or person_id

        creds = json.dumps({"access_token": access_token, "person_id": person_id})
        _upsert_channel(db, profile_id, "linkedin", display_name, person_id, creds)
        db.commit()
    except Exception:
        return RedirectResponse(f"{FRONTEND_URL}/?error=linkedin_connection_failed")

    return RedirectResponse(f"{FRONTEND_URL}/?success=linkedin")


def _upsert_channel(db: Session, profile_id: int, platform: str, display_name: str, platform_user_id: str, credentials: str):
    existing = db.query(Channel).filter(
        Channel.profile_id == profile_id,
        Channel.platform == platform,
        Channel.platform_user_id == platform_user_id,
    ).first()
    if existing:
        existing.credentials = credentials
        existing.display_name = display_name
        existing.is_connected = True
    else:
        db.add(Channel(
            profile_id=profile_id,
            platform=platform,
            display_name=display_name,
            platform_user_id=platform_user_id,
            credentials=credentials,
            is_connected=True,
        ))
