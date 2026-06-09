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

import json
import secrets
import os
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Channel, AppSetting
from ..schemas import BlueskyConnectRequest
from ..platforms import bluesky as bluesky_platform
from ..platforms import meta as meta_platform
from ..platforms import linkedin as linkedin_platform

router = APIRouter(prefix="/auth", tags=["auth"])

_oauth_states: dict[str, dict] = {}

OAUTH_CALLBACK_BASE = os.getenv("OAUTH_CALLBACK_BASE", "http://localhost:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


def _get_setting(db: Session, key: str) -> str | None:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    return row.value if row else None


def _set_setting(db: Session, key: str, value: str):
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(AppSetting(key=key, value=value))
    db.commit()


@router.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    keys = ["meta_app_id", "meta_app_secret", "linkedin_client_id", "linkedin_client_secret", "public_media_base_url", "threads_app_id", "threads_app_secret"]
    result = {}
    for k in keys:
        v = _get_setting(db, k)
        if k.endswith("_secret") and v:
            result[k] = "***"
        else:
            result[k] = v or ""
    return result


@router.post("/settings")
def update_settings(body: dict, db: Session = Depends(get_db)):
    for key, value in body.items():
        if value and value != "***":
            _set_setting(db, key, value)
    return {"ok": True}


@router.post("/bluesky")
def connect_bluesky(body: BlueskyConnectRequest, db: Session = Depends(get_db)):
    try:
        profile_info = bluesky_platform.test_bluesky_credentials(body.handle, body.app_password)
    except Exception as e:
        raise HTTPException(400, f"Bluesky auth failed: {e}")

    existing = db.query(Channel).filter(
        Channel.profile_id == body.profile_id,
        Channel.platform == "bluesky",
        Channel.platform_user_id == profile_info["did"],
    ).first()

    if existing:
        existing.credentials = json.dumps({"handle": body.handle, "app_password": body.app_password})
        existing.display_name = profile_info.get("display_name") or f"@{profile_info['handle']}"
        existing.is_connected = True
    else:
        db.add(Channel(
            profile_id=body.profile_id,
            platform="bluesky",
            display_name=profile_info.get("display_name") or f"@{profile_info['handle']}",
            platform_user_id=profile_info["did"],
            credentials=json.dumps({"handle": body.handle, "app_password": body.app_password}),
            is_connected=True,
        ))

    db.commit()
    return {"ok": True, "handle": profile_info["handle"]}


@router.get("/meta/url")
def meta_oauth_url(profile_id: int, db: Session = Depends(get_db)):
    client_id = _get_setting(db, "meta_app_id")
    if not client_id:
        raise HTTPException(400, "Meta App ID not configured")

    state = secrets.token_urlsafe(16)
    _oauth_states[state] = {"profile_id": profile_id, "platform": "meta"}
    redirect_uri = f"{OAUTH_CALLBACK_BASE}/auth/meta/callback"
    url = meta_platform.facebook_oauth_url(client_id, redirect_uri, state)
    return {"url": url}


@router.get("/meta/callback")
def meta_callback(code: str = Query(...), state: str = Query(...), db: Session = Depends(get_db)):
    state_data = _oauth_states.pop(state, None)
    if not state_data:
        return RedirectResponse(f"{FRONTEND_URL}/settings?error=invalid_state")

    profile_id = state_data["profile_id"]
    client_id = _get_setting(db, "meta_app_id")
    client_secret = _get_setting(db, "meta_app_secret")

    try:
        redirect_uri = f"{OAUTH_CALLBACK_BASE}/auth/meta/callback"
        token_data = meta_platform.exchange_code_for_token(code, client_id, client_secret, redirect_uri)
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
    except Exception as e:
        return RedirectResponse(f"{FRONTEND_URL}/settings?error={str(e)[:100]}")

    return RedirectResponse(f"{FRONTEND_URL}/settings?success=meta")


@router.get("/threads/url")
def threads_oauth_url(profile_id: int, db: Session = Depends(get_db)):
    client_id = _get_setting(db, "threads_app_id") or _get_setting(db, "meta_app_id")
    if not client_id:
        raise HTTPException(400, "Threads App ID not configured")

    state = secrets.token_urlsafe(16)
    _oauth_states[state] = {"profile_id": profile_id, "platform": "threads"}
    redirect_uri = f"{OAUTH_CALLBACK_BASE}/auth/threads/callback"
    url = meta_platform.threads_oauth_url(client_id, redirect_uri, state)
    return {"url": url}


@router.get("/threads/callback")
def threads_callback(code: str = Query(...), state: str = Query(...), db: Session = Depends(get_db)):
    state_data = _oauth_states.pop(state, None)
    if not state_data:
        return RedirectResponse(f"{FRONTEND_URL}/settings?error=invalid_state")

    profile_id = state_data["profile_id"]
    client_id = _get_setting(db, "threads_app_id") or _get_setting(db, "meta_app_id")
    client_secret = _get_setting(db, "threads_app_secret") or _get_setting(db, "meta_app_secret")

    try:
        redirect_uri = f"{OAUTH_CALLBACK_BASE}/auth/threads/callback"
        token_data = meta_platform.exchange_threads_code(code, client_id, client_secret, redirect_uri)
        access_token = token_data["access_token"]

        profile_info = meta_platform.get_threads_profile(access_token)
        threads_id = profile_info["id"]
        display = profile_info.get("username") or profile_info.get("name") or threads_id

        creds = json.dumps({"threads_user_id": threads_id, "access_token": access_token})
        _upsert_channel(db, profile_id, "threads", f"@{display}", threads_id, creds)
        db.commit()
    except Exception as e:
        return RedirectResponse(f"{FRONTEND_URL}/settings?error={str(e)[:100]}")

    return RedirectResponse(f"{FRONTEND_URL}/settings?success=threads")


@router.get("/linkedin/url")
def linkedin_oauth_url(profile_id: int, db: Session = Depends(get_db)):
    client_id = _get_setting(db, "linkedin_client_id")
    if not client_id:
        raise HTTPException(400, "LinkedIn Client ID not configured")

    state = secrets.token_urlsafe(16)
    _oauth_states[state] = {"profile_id": profile_id, "platform": "linkedin"}
    redirect_uri = f"{OAUTH_CALLBACK_BASE}/auth/linkedin/callback"
    url = linkedin_platform.linkedin_oauth_url(client_id, redirect_uri, state)
    return {"url": url}


@router.get("/linkedin/callback")
def linkedin_callback(code: str = Query(...), state: str = Query(...), db: Session = Depends(get_db)):
    state_data = _oauth_states.pop(state, None)
    if not state_data:
        return RedirectResponse(f"{FRONTEND_URL}/settings?error=invalid_state")

    profile_id = state_data["profile_id"]
    client_id = _get_setting(db, "linkedin_client_id")
    client_secret = _get_setting(db, "linkedin_client_secret")

    try:
        redirect_uri = f"{OAUTH_CALLBACK_BASE}/auth/linkedin/callback"
        token_data = linkedin_platform.exchange_code_for_token(code, client_id, client_secret, redirect_uri)
        access_token = token_data["access_token"]

        person = linkedin_platform.get_profile(access_token)
        person_id = person["id"]
        first = person.get("localizedFirstName", "")
        last = person.get("localizedLastName", "")
        display_name = f"{first} {last}".strip() or person_id

        creds = json.dumps({"access_token": access_token, "person_id": person_id})
        _upsert_channel(db, profile_id, "linkedin", display_name, person_id, creds)
        db.commit()
    except Exception as e:
        return RedirectResponse(f"{FRONTEND_URL}/settings?error={str(e)[:100]}")

    return RedirectResponse(f"{FRONTEND_URL}/settings?success=linkedin")


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
