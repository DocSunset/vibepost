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

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ProfileCreate(BaseModel):
    name: str
    avatar_color: str = "#6366f1"


class ProfileRead(BaseModel):
    id: int
    name: str
    avatar_color: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChannelRead(BaseModel):
    id: int
    profile_id: int
    platform: str
    display_name: str
    platform_user_id: Optional[str]
    is_connected: bool

    model_config = {"from_attributes": True}


class PostChannelRead(BaseModel):
    id: int
    channel_id: int
    status: str
    error_message: Optional[str]
    platform_post_id: Optional[str]
    published_at: Optional[datetime]
    channel: ChannelRead

    model_config = {"from_attributes": True}


class PostCreate(BaseModel):
    profile_id: int
    text: str = ""
    media_paths: list[str] = []
    channel_ids: list[int] = []
    scheduled_at: Optional[datetime] = None


class PostUpdate(BaseModel):
    text: Optional[str] = None
    media_paths: Optional[list[str]] = None
    channel_ids: Optional[list[int]] = None
    scheduled_at: Optional[datetime] = None
    status: Optional[str] = None


class PostRead(BaseModel):
    id: int
    profile_id: int
    text: str
    media_paths: list[str]
    scheduled_at: Optional[datetime]
    published_at: Optional[datetime]
    status: str
    created_at: datetime
    post_channels: list[PostChannelRead]

    model_config = {"from_attributes": True}


class BlueskyConnectRequest(BaseModel):
    profile_id: int
    handle: str
    app_password: str


class AppSettingUpdate(BaseModel):
    value: str
