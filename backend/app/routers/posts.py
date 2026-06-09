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
import shutil
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload
from ..database import get_db
from ..models import Post, PostChannel, Channel
from ..schemas import PostCreate, PostRead, PostUpdate
from ..scheduler import publish_post, schedule_post, cancel_post

router = APIRouter(prefix="/posts", tags=["posts"])

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov"}


@router.post("/upload")
async def upload_media(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File type {ext} not allowed")
    filename = f"{uuid.uuid4()}{ext}"
    dest = os.path.join(UPLOADS_DIR, filename)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"filename": filename}


@router.get("/media/{filename}")
def serve_media(filename: str):
    path = os.path.join(UPLOADS_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(404, "File not found")
    return FileResponse(path)


@router.get("/", response_model=list[PostRead])
def list_posts(
    profile_id: int | None = None,
    status: str | None = None,
    start: str | None = None,
    end: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(Post).options(
        joinedload(Post.post_channels).joinedload(PostChannel.channel)
    )
    if profile_id is not None:
        q = q.filter(Post.profile_id == profile_id)
    if status:
        q = q.filter(Post.status == status)
    if start:
        q = q.filter(Post.scheduled_at >= datetime.fromisoformat(start))
    if end:
        q = q.filter(Post.scheduled_at <= datetime.fromisoformat(end))

    posts = q.order_by(Post.created_at.desc()).all()
    result = []
    for p in posts:
        result.append(_serialize(p))
    return result


@router.get("/{post_id}", response_model=PostRead)
def get_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).options(
        joinedload(Post.post_channels).joinedload(PostChannel.channel)
    ).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post not found")
    return _serialize(post)


@router.post("/", response_model=PostRead)
def create_post(body: PostCreate, db: Session = Depends(get_db)):
    post = Post(
        profile_id=body.profile_id,
        text=body.text,
        media_paths=json.dumps(body.media_paths),
        scheduled_at=body.scheduled_at,
        status="scheduled" if body.scheduled_at else "draft",
    )
    db.add(post)
    db.flush()

    for cid in body.channel_ids:
        channel = db.query(Channel).filter(Channel.id == cid).first()
        if channel:
            db.add(PostChannel(post_id=post.id, channel_id=cid))

    db.commit()
    db.refresh(post)

    if body.scheduled_at:
        schedule_post(post.id, body.scheduled_at)

    return _serialize(_load(post.id, db))


@router.put("/{post_id}", response_model=PostRead)
def update_post(post_id: int, body: PostUpdate, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post not found")

    if body.text is not None:
        post.text = body.text
    if body.media_paths is not None:
        post.media_paths = json.dumps(body.media_paths)
    if body.scheduled_at is not None:
        post.scheduled_at = body.scheduled_at
        post.status = "scheduled"
        schedule_post(post.id, body.scheduled_at)
    if body.status is not None:
        post.status = body.status
        if body.status == "draft":
            cancel_post(post.id)

    if body.channel_ids is not None:
        db.query(PostChannel).filter(PostChannel.post_id == post_id).delete()
        for cid in body.channel_ids:
            db.add(PostChannel(post_id=post_id, channel_id=cid))

    db.commit()
    return _serialize(_load(post_id, db))


@router.post("/{post_id}/publish", response_model=PostRead)
def publish_now(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post not found")
    if post.status == "published":
        raise HTTPException(400, "Already published")

    cancel_post(post_id)
    publish_post(post_id)

    return _serialize(_load(post_id, db))


@router.delete("/{post_id}")
def delete_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post not found")
    cancel_post(post_id)
    db.delete(post)
    db.commit()
    return {"ok": True}


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
        "scheduled_at": post.scheduled_at,
        "published_at": post.published_at,
        "status": post.status,
        "created_at": post.created_at,
        "post_channels": [
            {
                "id": pc.id,
                "channel_id": pc.channel_id,
                "status": pc.status,
                "error_message": pc.error_message,
                "platform_post_id": pc.platform_post_id,
                "published_at": pc.published_at,
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
