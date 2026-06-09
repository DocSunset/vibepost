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
from ..models import Channel
from ..schemas import ChannelRead

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("/", response_model=list[ChannelRead])
def list_channels(profile_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(Channel)
    if profile_id is not None:
        q = q.filter(Channel.profile_id == profile_id)
    return q.all()


@router.delete("/{channel_id}")
def delete_channel(channel_id: int, db: Session = Depends(get_db)):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(404, "Channel not found")
    db.delete(channel)
    db.commit()
    return {"ok": True}
