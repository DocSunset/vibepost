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

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from .database import Base


class Profile(Base):
    __tablename__ = "profiles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    avatar_color = Column(String, default="#6366f1")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    channels = relationship("Channel", back_populates="profile", cascade="all, delete-orphan")
    posts = relationship("Post", back_populates="profile", cascade="all, delete-orphan")


class Channel(Base):
    __tablename__ = "channels"
    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"), nullable=False)
    platform = Column(String, nullable=False)  # instagram | facebook | bluesky | threads | linkedin
    display_name = Column(String, nullable=False)
    platform_user_id = Column(String)
    credentials = Column(Text)  # JSON
    is_connected = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    profile = relationship("Profile", back_populates="channels")
    post_channels = relationship("PostChannel", back_populates="channel", cascade="all, delete-orphan")


class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"), nullable=False)
    text = Column(Text, default="")
    media_paths = Column(Text, default="[]")  # JSON array of filenames in uploads/
    scheduled_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)
    status = Column(String, default="draft")  # draft | scheduled | published | failed | partial
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    profile = relationship("Profile", back_populates="posts")
    post_channels = relationship("PostChannel", back_populates="post", cascade="all, delete-orphan")


class PostChannel(Base):
    __tablename__ = "post_channels"
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    status = Column(String, default="pending")  # pending | published | failed
    error_message = Column(Text, nullable=True)
    platform_post_id = Column(String, nullable=True)
    published_at = Column(DateTime, nullable=True)

    post = relationship("Post", back_populates="post_channels")
    channel = relationship("Channel", back_populates="post_channels")


class AppSetting(Base):
    __tablename__ = "app_settings"
    key = Column(String, primary_key=True)
    value = Column(Text)
