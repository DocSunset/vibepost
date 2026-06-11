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
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from ..config import MAX_UPLOAD_BYTES, UPLOADS_DIR
from ..database import get_db
from ..models import Channel, Post, PostChannel, Profile, User
from ..ownership import owned_post, owned_profile
from ..scheduler import cancel_post, publish_post, schedule_post
from ..schemas import PostCreate, PostRead, PostUpdate
from ..security import get_current_user

router = APIRouter(prefix="/posts", tags=["posts"])

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov"}


def _to_naive_utc(dt: datetime | None) -> datetime | None:
    """Datetimes are stored as naive UTC; aware inputs are converted, naive
    inputs are assumed to already be UTC."""
    if dt is not None and dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _as_utc(dt: datetime | None) -> datetime | None:
    """Attach the UTC marker for serialization so clients can localise."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@router.post("/upload")
async def upload_media(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File type {ext} not allowed")
    filename = f"{uuid.uuid4()}{ext}"
    dest = UPLOADS_DIR / filename
    written = 0
    with open(dest, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            written += len(chunk)
            if written > MAX_UPLOAD_BYTES:
                f.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, "File too large")
            f.write(chunk)
    return {"filename": filename}


@router.get("/media/{filename}")
def serve_media(filename: str, user: User = Depends(get_current_user)):
    path = (UPLOADS_DIR / filename).resolve()
    if not path.is_relative_to(UPLOADS_DIR.resolve()) or not path.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(path)


@router.get("/", response_model=list[PostRead])
def list_posts(
    profile_id: int | None = None,
    status: str | None = None,
    start: str | None = None,
    end: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = (
        db.query(Post)
        .join(Profile, Post.profile_id == Profile.id)
        .filter(Profile.user_id == user.id)
        .options(joinedload(Post.post_channels).joinedload(PostChannel.channel))
    )
    if profile_id is not None:
        q = q.filter(Post.profile_id == profile_id)
    if status:
        q = q.filter(Post.status == status)
    if start:
        q = q.filter(Post.scheduled_at >= _to_naive_utc(datetime.fromisoformat(start)))
    if end:
        q = q.filter(Post.scheduled_at <= _to_naive_utc(datetime.fromisoformat(end)))

    return [_serialize(p) for p in q.order_by(Post.created_at.desc()).all()]


@router.get("/{post_id}", response_model=PostRead)
def get_post(post_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned_post(db, user, post_id)
    return _serialize(_load(post_id, db))


@router.post("/", response_model=PostRead)
def create_post(body: PostCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned_profile(db, user, body.profile_id)

    post = Post(
        profile_id=body.profile_id,
        text=body.text,
        media_paths=json.dumps(body.media_paths),
        scheduled_at=_to_naive_utc(body.scheduled_at),
        status="scheduled" if body.scheduled_at else "draft",
    )
    db.add(post)
    db.flush()

    _attach_channels(db, user, post.id, body.channel_ids)

    db.commit()
    db.refresh(post)

    if body.scheduled_at:
        schedule_post(post.id, body.scheduled_at)

    return _serialize(_load(post.id, db))


@router.put("/{post_id}", response_model=PostRead)
def update_post(post_id: int, body: PostUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    post = owned_post(db, user, post_id)

    if body.text is not None:
        post.text = body.text
    if body.media_paths is not None:
        post.media_paths = json.dumps(body.media_paths)
    if body.scheduled_at is not None:
        post.scheduled_at = _to_naive_utc(body.scheduled_at)
        post.status = "scheduled"
        schedule_post(post.id, post.scheduled_at)
    if body.status is not None:
        post.status = body.status
        if body.status == "draft":
            cancel_post(post.id)

    if body.channel_ids is not None:
        db.query(PostChannel).filter(PostChannel.post_id == post_id).delete()
        _attach_channels(db, user, post_id, body.channel_ids)

    db.commit()
    return _serialize(_load(post_id, db))


@router.post("/{post_id}/publish", response_model=PostRead)
def publish_now(post_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    post = owned_post(db, user, post_id)
    if post.status == "published":
        raise HTTPException(400, "Already published")

    cancel_post(post_id)
    publish_post(post_id)

    return _serialize(_load(post_id, db))


@router.delete("/{post_id}")
def delete_post(post_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    post = owned_post(db, user, post_id)
    cancel_post(post_id)
    for filename in json.loads(post.media_paths or "[]"):
        path = (UPLOADS_DIR / filename).resolve()
        if path.is_relative_to(UPLOADS_DIR.resolve()) and path.is_file():
            path.unlink(missing_ok=True)
    db.delete(post)
    db.commit()
    return {"ok": True}


def _attach_channels(db: Session, user: User, post_id: int, channel_ids: list[int]):
    """Attach only channels that belong to the requesting user."""
    for cid in channel_ids:
        channel = (
            db.query(Channel)
            .join(Profile, Channel.profile_id == Profile.id)
            .filter(Channel.id == cid, Profile.user_id == user.id)
            .first()
        )
        if not channel:
            raise HTTPException(404, f"Channel {cid} not found")
        db.add(PostChannel(post_id=post_id, channel_id=cid))


def _load(post_id: int, db: Session) -> Post:
    return db.query(Post).options(
        joinedload(Post.post_channels).joinedload(PostChannel.channel)
    ).filter(Post.id == post_id).first()


def _serialize(post: Post) -> dict:
    return {
        "id": post.id,
        "profile_id": post.profile_id,
        "text": post.text or "",
        "media_paths": json.loads(post.media_paths or "[]"),
        "scheduled_at": _as_utc(post.scheduled_at),
        "published_at": _as_utc(post.published_at),
        "status": post.status,
        "created_at": _as_utc(post.created_at),
        "post_channels": [
            {
                "id": pc.id,
                "channel_id": pc.channel_id,
                "status": pc.status,
                "error_message": pc.error_message,
                "platform_post_id": pc.platform_post_id,
                "published_at": _as_utc(pc.published_at),
                "channel": {
                    "id": pc.channel.id,
                    "profile_id": pc.channel.profile_id,
                    "platform": pc.channel.platform,
                    "display_name": pc.channel.display_name,
                    "platform_user_id": pc.channel.platform_user_id,
                    "is_connected": pc.channel.is_connected,
                },
            }
            for pc in post.post_channels
        ],
    }
