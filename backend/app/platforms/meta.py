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

import httpx
import json
from urllib.parse import urlencode
from ..config import UPLOADS_DIR

GRAPH = "https://graph.facebook.com/v19.0"
THREADS_GRAPH = "https://graph.threads.net/v1.0"


def facebook_oauth_url(client_id: str, redirect_uri: str, state: str) -> str:
    params = urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "pages_manage_posts,pages_read_engagement,instagram_basic,instagram_content_publish,threads_basic,threads_content_publish",
        "state": state,
        "response_type": "code",
    })
    return f"https://www.facebook.com/v19.0/dialog/oauth?{params}"


def threads_oauth_url(client_id: str, redirect_uri: str, state: str) -> str:
    params = urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "threads_basic,threads_content_publish",
        "state": state,
        "response_type": "code",
    })
    return f"https://threads.net/oauth/authorize?{params}"


def exchange_code_for_token(code: str, client_id: str, client_secret: str, redirect_uri: str) -> dict:
    with httpx.Client() as c:
        r = c.get(f"{GRAPH}/oauth/access_token", params={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        })
        r.raise_for_status()
        return r.json()


def get_long_lived_token(short_token: str, client_id: str, client_secret: str) -> dict:
    with httpx.Client() as c:
        r = c.get(f"{GRAPH}/oauth/access_token", params={
            "grant_type": "fb_exchange_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "fb_exchange_token": short_token,
        })
        r.raise_for_status()
        return r.json()


def get_pages(user_token: str) -> list[dict]:
    with httpx.Client() as c:
        r = c.get(f"{GRAPH}/me/accounts", params={
            "access_token": user_token,
            "fields": "id,name,access_token,instagram_business_account{id,name,username}",
        })
        r.raise_for_status()
        return r.json().get("data", [])


def get_threads_profile(access_token: str) -> dict:
    with httpx.Client() as c:
        r = c.get(f"{THREADS_GRAPH}/me", params={
            "access_token": access_token,
            "fields": "id,name,username",
        })
        r.raise_for_status()
        return r.json()


def exchange_threads_code(code: str, client_id: str, client_secret: str, redirect_uri: str) -> dict:
    with httpx.Client() as c:
        r = c.post("https://graph.threads.net/oauth/access_token", data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code": code,
        })
        r.raise_for_status()
        return r.json()


def post_to_facebook(credentials: dict, text: str, media_paths: list[str]) -> str:
    page_id = credentials["page_id"]
    page_token = credentials["page_token"]


    with httpx.Client() as c:
        if media_paths:
            photo_ids = []
            for filename in media_paths:
                full_path = UPLOADS_DIR / filename
                with open(full_path, "rb") as f:
                    r = c.post(f"{GRAPH}/{page_id}/photos", data={
                        "access_token": page_token,
                        "published": "false",
                    }, files={"source": (filename, f)})
                r.raise_for_status()
                photo_ids.append(r.json()["id"])

            r = c.post(f"{GRAPH}/{page_id}/feed", data={
                "message": text,
                "attached_media": json.dumps([{"media_fbid": pid} for pid in photo_ids]),
                "access_token": page_token,
            })
        else:
            r = c.post(f"{GRAPH}/{page_id}/feed", data={
                "message": text,
                "access_token": page_token,
            })

        r.raise_for_status()
        result = r.json()
        if "id" not in result:
            raise Exception(result.get("error", {}).get("message", "Unknown error"))
        return result["id"]


def post_to_instagram(credentials: dict, text: str, media_paths: list[str], public_base_url: str) -> str:
    ig_user_id = credentials["ig_user_id"]
    access_token = credentials["access_token"]

    with httpx.Client() as c:
        if not media_paths:
            raise Exception("Instagram requires at least one image or video")

        if len(media_paths) == 1:
            image_url = f"{public_base_url.rstrip('/')}/media/{media_paths[0]}"
            r = c.post(f"{GRAPH}/{ig_user_id}/media", data={
                "image_url": image_url,
                "caption": text,
                "access_token": access_token,
            })
            r.raise_for_status()
            container_id = r.json()["id"]
        else:
            children = []
            for filename in media_paths[:10]:
                image_url = f"{public_base_url.rstrip('/')}/media/{filename}"
                r = c.post(f"{GRAPH}/{ig_user_id}/media", data={
                    "image_url": image_url,
                    "is_carousel_item": "true",
                    "access_token": access_token,
                })
                r.raise_for_status()
                children.append(r.json()["id"])

            r = c.post(f"{GRAPH}/{ig_user_id}/media", data={
                "media_type": "CAROUSEL",
                "caption": text,
                "children": ",".join(children),
                "access_token": access_token,
            })
            r.raise_for_status()
            container_id = r.json()["id"]

        r = c.post(f"{GRAPH}/{ig_user_id}/media_publish", data={
            "creation_id": container_id,
            "access_token": access_token,
        })
        r.raise_for_status()
        return r.json()["id"]


def post_to_threads(credentials: dict, text: str, media_paths: list[str], public_base_url: str) -> str:
    threads_user_id = credentials["threads_user_id"]
    access_token = credentials["access_token"]

    with httpx.Client() as c:
        if media_paths:
            image_url = f"{public_base_url.rstrip('/')}/media/{media_paths[0]}"
            r = c.post(f"{THREADS_GRAPH}/{threads_user_id}/threads", data={
                "media_type": "IMAGE",
                "image_url": image_url,
                "text": text,
                "access_token": access_token,
            })
        else:
            r = c.post(f"{THREADS_GRAPH}/{threads_user_id}/threads", data={
                "media_type": "TEXT",
                "text": text,
                "access_token": access_token,
            })

        r.raise_for_status()
        container_id = r.json()["id"]

        r = c.post(f"{THREADS_GRAPH}/{threads_user_id}/threads_publish", data={
            "creation_id": container_id,
            "access_token": access_token,
        })
        r.raise_for_status()
        return r.json()["id"]
