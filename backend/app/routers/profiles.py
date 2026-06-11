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

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import UPLOADS_DIR
from ..database import get_db
from ..models import Profile, User
from ..ownership import owned_profile
from ..scheduler import cancel_post
from ..schemas import ProfileCreate, ProfileRead
from ..security import get_current_user

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/", response_model=list[ProfileRead])
def list_profiles(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Profile).filter(Profile.user_id == user.id).all()


@router.post("/", response_model=ProfileRead)
def create_profile(
    body: ProfileCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = Profile(user_id=user.id, name=body.name, avatar_color=body.avatar_color)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.put("/{profile_id}", response_model=ProfileRead)
def update_profile(
    profile_id: int,
    body: ProfileCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = owned_profile(db, user, profile_id)
    profile.name = body.name
    profile.avatar_color = body.avatar_color
    db.commit()
    db.refresh(profile)
    return profile


@router.delete("/{profile_id}")
def delete_profile(
    profile_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = owned_profile(db, user, profile_id)
    for post in profile.posts:
        cancel_post(post.id)
        for filename in json.loads(post.media_paths or "[]"):
            path = (UPLOADS_DIR / filename).resolve()
            if path.is_relative_to(UPLOADS_DIR.resolve()) and path.is_file():
                path.unlink(missing_ok=True)
    db.delete(profile)
    db.commit()
    return {"ok": True}
