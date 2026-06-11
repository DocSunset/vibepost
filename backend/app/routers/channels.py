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

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Channel, Profile, User
from ..ownership import owned_channel
from ..schemas import ChannelRead
from ..security import get_current_user

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("/", response_model=list[ChannelRead])
def list_channels(
    profile_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = (
        db.query(Channel)
        .join(Profile, Channel.profile_id == Profile.id)
        .filter(Profile.user_id == user.id)
    )
    if profile_id is not None:
        q = q.filter(Channel.profile_id == profile_id)
    return q.all()


@router.delete("/{channel_id}")
def delete_channel(
    channel_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Disconnect a channel: the stored credential is deleted with the row."""
    channel = owned_channel(db, user, channel_id)
    db.delete(channel)
    db.commit()
    return {"ok": True}
