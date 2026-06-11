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
import logging
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from sqlalchemy.orm import Session
from .config import OAUTH_CALLBACK_BASE
from .database import SessionLocal
from .models import Post, PostChannel, Channel, Profile, UserSetting

log = logging.getLogger(__name__)

scheduler = BackgroundScheduler(
    jobstores={"default": MemoryJobStore()},
    job_defaults={"coalesce": True, "max_instances": 1},
)


def _get_user_setting(db: Session, user_id: int | None, key: str) -> str | None:
    if user_id is None:
        return None
    row = db.query(UserSetting).filter(
        UserSetting.user_id == user_id, UserSetting.key == key
    ).first()
    return row.value if row else None


def publish_post(post_id: int):
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post or post.status not in ("scheduled", "draft"):
            return

        post.status = "published"
        media_paths = json.loads(post.media_paths or "[]")
        any_failure = False

        owner = db.query(Profile).filter(Profile.id == post.profile_id).first()
        owner_user_id = owner.user_id if owner else None

        for pc in post.post_channels:
            if pc.status == "published":
                continue
            channel: Channel = pc.channel
            creds = json.loads(channel.credentials or "{}")

            try:
                platform_post_id = _dispatch(channel.platform, creds, post.text, media_paths, db, owner_user_id)
                pc.status = "published"
                pc.platform_post_id = platform_post_id
                pc.published_at = datetime.now(timezone.utc)
            except Exception as e:
                log.error("Failed posting to %s channel %d: %s", channel.platform, channel.id, e)
                pc.status = "failed"
                pc.error_message = str(e)
                any_failure = True

        if any_failure:
            all_failed = all(pc.status == "failed" for pc in post.post_channels)
            post.status = "failed" if all_failed else "partial"
        else:
            post.published_at = datetime.now(timezone.utc)

        db.commit()
    except Exception as e:
        log.error("Error in publish_post(%d): %s", post_id, e)
        db.rollback()
    finally:
        db.close()


def _dispatch(platform: str, creds: dict, text: str, media_paths: list[str], db: Session, user_id: int | None) -> str:
    public_base = _get_user_setting(db, user_id, "public_media_base_url") or OAUTH_CALLBACK_BASE

    if platform == "bluesky":
        from .platforms.bluesky import post_to_bluesky
        return post_to_bluesky(creds, text, media_paths)

    if platform == "facebook":
        from .platforms.meta import post_to_facebook
        return post_to_facebook(creds, text, media_paths)

    if platform == "instagram":
        from .platforms.meta import post_to_instagram
        return post_to_instagram(creds, text, media_paths, public_base)

    if platform == "threads":
        from .platforms.meta import post_to_threads
        return post_to_threads(creds, text, media_paths, public_base)

    if platform == "linkedin":
        from .platforms.linkedin import post_to_linkedin
        return post_to_linkedin(creds, text, media_paths)

    raise ValueError(f"Unknown platform: {platform}")


def restore_jobs():
    """Re-create scheduler jobs after a restart.

    Jobs live in memory, so a deploy or crash loses them; the posts table is
    the source of truth. Future posts are re-scheduled; overdue ones are
    published immediately (better late than silently never).
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        pending = db.query(Post).filter(
            Post.status == "scheduled", Post.scheduled_at.isnot(None)
        ).all()
        for post in pending:
            if post.scheduled_at > now:
                schedule_post(post.id, post.scheduled_at)
            else:
                log.warning("Post %d was due at %s; publishing now", post.id, post.scheduled_at)
                scheduler.add_job(publish_post, args=[post.id], id=f"post_{post.id}", replace_existing=True)
    finally:
        db.close()


def schedule_post(post_id: int, run_at: datetime):
    # Stored datetimes are naive UTC; APScheduler would interpret a naive
    # datetime in the server's local timezone, so mark it explicitly.
    if run_at.tzinfo is None:
        run_at = run_at.replace(tzinfo=timezone.utc)
    job_id = f"post_{post_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    scheduler.add_job(publish_post, "date", run_date=run_at, args=[post_id], id=job_id)


def cancel_post(post_id: int):
    job_id = f"post_{post_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
