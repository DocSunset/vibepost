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

"""Ownership checks: every resource is reached through the requesting user.

All lookups 404 rather than 403 for resources owned by someone else, so the
API does not reveal which IDs exist.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import Channel, Post, Profile, User, UserSetting


def owned_profile(db: Session, user: User, profile_id: int) -> Profile:
    profile = db.query(Profile).filter(
        Profile.id == profile_id, Profile.user_id == user.id
    ).first()
    if not profile:
        raise HTTPException(404, "Profile not found")
    return profile


def owned_channel(db: Session, user: User, channel_id: int) -> Channel:
    channel = (
        db.query(Channel)
        .join(Profile, Channel.profile_id == Profile.id)
        .filter(Channel.id == channel_id, Profile.user_id == user.id)
        .first()
    )
    if not channel:
        raise HTTPException(404, "Channel not found")
    return channel


def owned_post(db: Session, user: User, post_id: int) -> Post:
    post = (
        db.query(Post)
        .join(Profile, Post.profile_id == Profile.id)
        .filter(Post.id == post_id, Profile.user_id == user.id)
        .first()
    )
    if not post:
        raise HTTPException(404, "Post not found")
    return post


def get_user_setting(db: Session, user_id: int, key: str) -> str | None:
    row = db.query(UserSetting).filter(
        UserSetting.user_id == user_id, UserSetting.key == key
    ).first()
    return row.value if row else None


def set_user_setting(db: Session, user_id: int, key: str, value: str) -> None:
    row = db.query(UserSetting).filter(
        UserSetting.user_id == user_id, UserSetting.key == key
    ).first()
    if row:
        row.value = value
    else:
        db.add(UserSetting(user_id=user_id, key=key, value=value))
