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

"""Validation of media file references, and signed media URLs.

Media filenames are generated server-side as `<uuid4>.<ext>` at upload time.
Every place that later touches a media file by name — storing a reference on
a post, serving it, deleting it, or opening it to push bytes to a platform —
must go through these helpers so that a stored reference can never reach
outside the uploads directory.

Media is NOT public. /media/<name> serves a file only to its owner's
authenticated session, or to anyone holding a short-lived HMAC-signed URL —
minted exclusively at publish time for platforms (Instagram/Threads/Facebook)
that ingest media by fetching a URL. Until a post actually publishes, its
media has never been reachable from the public internet.
"""

import hashlib
import hmac
import re
import time
from pathlib import Path

from . import crypto
from .config import UPLOADS_DIR

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov"}

_MEDIA_NAME_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"\.(jpg|jpeg|png|gif|webp|mp4|mov)$"
)


def is_valid_media_name(filename: str) -> bool:
    """True only for names the upload endpoint could have generated."""
    return bool(_MEDIA_NAME_RE.match(filename))


def safe_media_path(filename: str) -> Path:
    """Resolve a media filename to a path strictly inside UPLOADS_DIR.

    Raises ValueError for anything that is not a server-generated media name.
    """
    if not is_valid_media_name(filename):
        raise ValueError(f"Invalid media reference: {filename!r}")
    path = (UPLOADS_DIR / filename).resolve()
    if not path.is_relative_to(UPLOADS_DIR.resolve()):
        raise ValueError(f"Invalid media reference: {filename!r}")
    return path


# Default lifetime of a signed media URL: long enough for Instagram's
# ingestion pipeline (which can take minutes), short enough that a cancelled
# post's URL is useless within the hour.
SIGNED_URL_TTL_SECONDS = 3600


def _media_mac(filename: str, exp: int) -> str:
    key = crypto.derive_key("media-url")
    return hmac.new(key, f"{filename}|{exp}".encode("utf-8"), hashlib.sha256).hexdigest()


def signed_media_url(base_url: str, filename: str, ttl_seconds: int = SIGNED_URL_TTL_SECONDS) -> str:
    """Mint a time-limited public URL for one media file.

    Only called at publish time, for platforms that ingest media by URL.
    """
    exp = int(time.time()) + ttl_seconds
    return f"{base_url.rstrip('/')}/media/{filename}?exp={exp}&sig={_media_mac(filename, exp)}"


def verify_media_signature(filename: str, exp: str | None, sig: str | None) -> bool:
    if not exp or not sig:
        return False
    try:
        exp_int = int(exp)
    except ValueError:
        return False
    if exp_int < time.time():
        return False
    return hmac.compare_digest(_media_mac(filename, exp_int), sig)
