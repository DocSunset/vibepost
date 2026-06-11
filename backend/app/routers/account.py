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
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from ..config import INVITE_TTL_DAYS, UPLOADS_DIR
from ..database import get_db
from ..models import InviteToken, Post, Profile, User
from ..schemas import (
    ChangePasswordRequest,
    InviteCreateRequest,
    LoginRequest,
    SignupRequest,
    UserRead,
)
from ..scheduler import cancel_post
from ..security import (
    MIN_PASSWORD_LENGTH,
    clear_session_cookie,
    create_session_token,
    get_current_admin,
    get_current_user,
    hash_password,
    hash_token,
    login_limiter,
    set_session_cookie,
    signup_limiter,
    verify_password,
)

router = APIRouter(prefix="/account", tags=["account"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_credentials(email: str, password: str) -> str:
    email = email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Invalid email address")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(400, f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    return email


MAX_INVITE_FAILURES = 5


def _lookup_invite(db: Session, token: str, now: datetime) -> InviteToken:
    invite = (
        db.query(InviteToken)
        .filter(InviteToken.token_hash == hash_token(token.strip()))
        .first()
    )
    if not invite or invite.revoked or invite.used_at is not None:
        raise HTTPException(403, "Invalid or already-used invite code")
    if invite.expires_at is not None and invite.expires_at < now.replace(tzinfo=None):
        raise HTTPException(403, "This invite code has expired")
    return invite


@router.post("/signup", response_model=UserRead)
def signup(body: SignupRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    signup_limiter.check(request)
    email = _validate_credentials(body.email, body.password)

    now = datetime.now(timezone.utc)
    invite = _lookup_invite(db, body.invite_code, now)

    if db.query(User).filter(User.email == email).first():
        # Burn the invite a little on every failure so a leaked code cannot
        # be replayed indefinitely to probe which emails are registered, and
        # keep the message vague for the same reason.
        invite.failed_attempts = (invite.failed_attempts or 0) + 1
        if invite.failed_attempts >= MAX_INVITE_FAILURES:
            invite.revoked = True
        db.commit()
        raise HTTPException(
            400,
            "Could not create an account with this email — if you already have one, sign in instead",
        )

    # The first account ever created becomes the admin.
    is_first = db.query(User).count() == 0
    user = User(email=email, password_hash=hash_password(body.password), is_admin=is_first)
    db.add(user)
    db.flush()

    invite.used_at = now
    invite.used_by_user_id = user.id
    db.commit()

    if is_first:
        # Guard against two concurrent first signups both claiming admin
        first_admin = db.query(User).filter(User.is_admin).order_by(User.id).first()
        if first_admin and first_admin.id != user.id:
            user.is_admin = False
            db.commit()
    db.refresh(user)

    set_session_cookie(response, create_session_token(user))
    return user


@router.post("/login", response_model=UserRead)
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    login_limiter.check(request)
    email = body.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    # Verify against a dummy hash when the user doesn't exist so response
    # timing doesn't reveal which emails are registered.
    if not user:
        verify_password(body.password, _DUMMY_HASH)
        raise HTTPException(401, "Incorrect email or password")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")

    set_session_cookie(response, create_session_token(user))
    return user


_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


@router.post("/logout")
def logout(response: Response):
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    login_limiter.check(request)
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(401, "Current password is incorrect")
    if len(body.new_password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(400, f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    user.password_hash = hash_password(body.new_password)
    # Revoke every outstanding session (stolen cookies included), then issue
    # a fresh one so the user changing their password stays signed in.
    user.session_epoch = (user.session_epoch or 0) + 1
    db.commit()
    set_session_cookie(response, create_session_token(user))
    return {"ok": True}


@router.get("/export")
def export_data(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Data portability: everything we hold for this account, as JSON.

    Platform credentials are deliberately excluded — exporting live tokens
    would be a security hazard, and they can be re-issued by the platforms.
    """
    profiles = db.query(Profile).filter(Profile.user_id == user.id).all()
    out = {
        "email": user.email,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "settings": {s.key: ("***" if s.key.endswith("_secret") else s.value) for s in user.settings},
        "profiles": [],
    }
    for p in profiles:
        out["profiles"].append({
            "name": p.name,
            "avatar_color": p.avatar_color,
            "channels": [
                {
                    "platform": c.platform,
                    "display_name": c.display_name,
                    "platform_user_id": c.platform_user_id,
                }
                for c in p.channels
            ],
            "posts": [
                {
                    "text": post.text,
                    "media_paths": json.loads(post.media_paths or "[]"),
                    "scheduled_at": post.scheduled_at.isoformat() if post.scheduled_at else None,
                    "published_at": post.published_at.isoformat() if post.published_at else None,
                    "status": post.status,
                }
                for post in p.posts
            ],
        })
    return out


@router.delete("")
def delete_account(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Hard-delete the account and everything attached to it.

    Cascade: scheduled jobs are cancelled, media files removed from disk,
    then all database rows (profiles, channels, posts, post_channels,
    settings, and the user itself) are deleted. Nothing is archived.
    """
    profiles = db.query(Profile).filter(Profile.user_id == user.id).all()
    for p in profiles:
        for post in p.posts:
            cancel_post(post.id)
            for filename in json.loads(post.media_paths or "[]"):
                path = (UPLOADS_DIR / filename).resolve()
                if path.is_relative_to(UPLOADS_DIR.resolve()) and path.is_file():
                    path.unlink(missing_ok=True)

    # Free the invite for audit purposes? No — keep it consumed but drop the
    # user link, since the user row is about to disappear.
    db.query(InviteToken).filter(InviteToken.used_by_user_id == user.id).update(
        {InviteToken.used_by_user_id: None}
    )
    db.delete(user)  # cascades to profiles -> channels/posts -> post_channels, and settings
    db.commit()

    clear_session_cookie(response)
    return {"ok": True}


# ── Admin: invite management ─────────────────────────────────────────────────

@router.post("/invites")
def create_invite(
    body: InviteCreateRequest,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    token = secrets.token_urlsafe(24)
    days = body.expires_in_days if body.expires_in_days is not None else INVITE_TTL_DAYS
    invite = InviteToken(
        token_hash=hash_token(token),
        note=body.note or "",
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=days),
    )
    db.add(invite)
    db.commit()
    # The plaintext token is returned exactly once and never stored.
    return {"token": token, "expires_in_days": days, "note": invite.note}


@router.get("/invites")
def list_invites(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    invites = db.query(InviteToken).order_by(InviteToken.created_at.desc()).all()
    return [
        {
            "id": i.id,
            "note": i.note,
            "created_at": i.created_at,
            "expires_at": i.expires_at,
            "used_at": i.used_at,
            "revoked": i.revoked,
        }
        for i in invites
    ]


@router.post("/invites/{invite_id}/revoke")
def revoke_invite(invite_id: int, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    invite = db.query(InviteToken).filter(InviteToken.id == invite_id).first()
    if not invite:
        raise HTTPException(404, "Invite not found")
    invite.revoked = True
    db.commit()
    return {"ok": True}
