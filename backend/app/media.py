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

"""Validation of media file references.

Media filenames are generated server-side as `<uuid4>.<ext>` at upload time.
Every place that later touches a media file by name — storing a reference on
a post, serving it, deleting it, or opening it to push bytes to a platform —
must go through these helpers so that a stored reference can never reach
outside the uploads directory.
"""

import re
from pathlib import Path

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
