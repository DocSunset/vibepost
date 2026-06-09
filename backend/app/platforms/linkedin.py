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

API = "https://api.linkedin.com/v2"


def linkedin_oauth_url(client_id: str, redirect_uri: str, state: str) -> str:
    params = urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "r_liteprofile w_member_social r_emailaddress",
        "state": state,
    })
    return f"https://www.linkedin.com/oauth/v2/authorization?{params}"


def exchange_code_for_token(code: str, client_id: str, client_secret: str, redirect_uri: str) -> dict:
    with httpx.Client() as c:
        r = c.post("https://www.linkedin.com/oauth/v2/accessToken", data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        }, headers={"Content-Type": "application/x-www-form-urlencoded"})
        r.raise_for_status()
        return r.json()


def get_profile(access_token: str) -> dict:
    with httpx.Client() as c:
        r = c.get(f"{API}/me", params={"fields": "id,localizedFirstName,localizedLastName"},
                  headers={"Authorization": f"Bearer {access_token}"})
        r.raise_for_status()
        return r.json()


def post_to_linkedin(credentials: dict, text: str, media_paths: list[str]) -> str:
    access_token = credentials["access_token"]
    person_urn = f"urn:li:person:{credentials['person_id']}"


    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    with httpx.Client() as c:
        if media_paths:
            asset_urns = []
            for filename in media_paths:
                # Register upload
                register_body = {
                    "registerUploadRequest": {
                        "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                        "owner": person_urn,
                        "serviceRelationships": [{
                            "relationshipType": "OWNER",
                            "identifier": "urn:li:userGeneratedContent",
                        }],
                    }
                }
                r = c.post(f"{API}/assets?action=registerUpload", json=register_body, headers=headers)
                r.raise_for_status()
                reg = r.json()
                upload_url = reg["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
                asset_urn = reg["value"]["asset"]

                full_path = UPLOADS_DIR / filename
                with open(full_path, "rb") as f:
                    put_r = c.put(upload_url, content=f.read(), headers={"Authorization": f"Bearer {access_token}"})
                put_r.raise_for_status()

                asset_urns.append(asset_urn)

            media_list = [{"status": "READY", "media": urn} for urn in asset_urns]
            post_body = {
                "author": person_urn,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": text},
                        "shareMediaCategory": "IMAGE",
                        "media": media_list,
                    }
                },
                "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
            }
        else:
            post_body = {
                "author": person_urn,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": text},
                        "shareMediaCategory": "NONE",
                    }
                },
                "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
            }

        r = c.post(f"{API}/ugcPosts", json=post_body, headers=headers)
        r.raise_for_status()
        return r.headers.get("x-restli-id", r.json().get("id", ""))
