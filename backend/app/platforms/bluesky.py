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

from atproto import Client
from ..config import UPLOADS_DIR


def post_to_bluesky(credentials: dict, text: str, media_paths: list[str]) -> str:
    client = Client()
    client.login(credentials["handle"], credentials["app_password"])

    if media_paths:
        images = []
        for path in media_paths[:4]:
            full_path = UPLOADS_DIR / path
            with open(full_path, "rb") as f:
                data = f.read()
            ext = path.rsplit(".", 1)[-1].lower()
            mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
            upload = client.upload_blob(data, mime_type=mime)
            images.append({"alt": "", "image": upload.blob})

        embed = {"$type": "app.bsky.embed.images", "images": images}
        response = client.send_post(text=text, embed=embed)
    else:
        response = client.send_post(text=text)

    return response.uri


def test_bluesky_credentials(handle: str, app_password: str) -> dict:
    client = Client()
    profile = client.login(handle, app_password)
    return {"handle": profile.handle, "did": profile.did, "display_name": profile.display_name}
