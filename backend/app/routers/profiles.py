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

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Profile
from ..schemas import ProfileCreate, ProfileRead

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/", response_model=list[ProfileRead])
def list_profiles(db: Session = Depends(get_db)):
    return db.query(Profile).all()


@router.post("/", response_model=ProfileRead)
def create_profile(body: ProfileCreate, db: Session = Depends(get_db)):
    profile = Profile(name=body.name, avatar_color=body.avatar_color)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.put("/{profile_id}", response_model=ProfileRead)
def update_profile(profile_id: int, body: ProfileCreate, db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise HTTPException(404, "Profile not found")
    profile.name = body.name
    profile.avatar_color = body.avatar_color
    db.commit()
    db.refresh(profile)
    return profile


@router.delete("/{profile_id}")
def delete_profile(profile_id: int, db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise HTTPException(404, "Profile not found")
    db.delete(profile)
    db.commit()
    return {"ok": True}
