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

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from .database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    # Empty string means no password: the account signs in via emailed link
    # or passkey only. (Sentinel rather than NULL so existing rows need no
    # schema migration; verify_password fails closed on "".)
    password_hash = Column(String, nullable=False, default="")
    is_admin = Column(Boolean, default=False, nullable=False)
    # Bumped on password change to invalidate all outstanding sessions
    session_epoch = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    profiles = relationship("Profile", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("UserSetting", back_populates="user", cascade="all, delete-orphan")
    passkeys = relationship("WebAuthnCredential", back_populates="user", cascade="all, delete-orphan")
    login_tokens = relationship("LoginToken", back_populates="user", cascade="all, delete-orphan")

    @property
    def has_password(self) -> bool:
        return bool(self.password_hash)


class LoginToken(Base):
    """Single-use emailed sign-in link. Only the SHA-256 hash is stored."""
    __tablename__ = "login_tokens"
    id = Column(Integer, primary_key=True, index=True)
    token_hash = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="login_tokens")


class WebAuthnCredential(Base):
    """A registered passkey. Stores only the public half; the private key
    never leaves the user's authenticator."""
    __tablename__ = "webauthn_credentials"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    credential_id = Column(String, unique=True, nullable=False, index=True)  # base64url
    public_key = Column(String, nullable=False)  # base64url
    sign_count = Column(Integer, default=0, nullable=False)
    transports = Column(String, default="")  # comma-separated hints
    label = Column(String, default="")  # user-facing name, e.g. "MacBook Touch ID"
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_used_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="passkeys")


class InviteToken(Base):
    __tablename__ = "invite_tokens"
    id = Column(Integer, primary_key=True, index=True)
    # Only a SHA-256 hash is stored; the token itself is shown once at creation.
    token_hash = Column(String, unique=True, nullable=False, index=True)
    note = Column(String, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=True)
    used_at = Column(DateTime, nullable=True)
    used_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    revoked = Column(Boolean, default=False, nullable=False)
    # Failed signup attempts with this token; auto-revoked after too many,
    # so a leaked invite cannot be used to probe for registered emails.
    failed_attempts = Column(Integer, default=0, nullable=False)


class UserSetting(Base):
    __tablename__ = "user_settings"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    key = Column(String, nullable=False)
    value = Column(Text)

    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_user_setting"),)

    user = relationship("User", back_populates="settings")


class Profile(Base):
    __tablename__ = "profiles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    name = Column(String, nullable=False)
    avatar_color = Column(String, default="#6366f1")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="profiles")

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


# Note: the legacy single-tenant `app_settings` table was replaced by
# `user_settings`; existing databases are migrated at startup (see database.py).
