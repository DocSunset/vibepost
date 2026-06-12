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

"""GitHub issue filing for collected feedback.

Feedback becomes labelled issues in the public repo, so triage happens where
the work happens. Optional: without GITHUB_TOKEN the bot still summarizes
into the thread, it just can't file.
"""

import logging

import httpx

from config import GITHUB_REPO, GITHUB_TOKEN

logger = logging.getLogger("feedback-bot.issues")

API = "https://api.github.com"
FEEDBACK_LABEL = "discord-feedback"


def configured() -> bool:
    return bool(GITHUB_TOKEN)


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def list_open_feedback_issues() -> list[tuple[int, str]]:
    async with httpx.AsyncClient(timeout=15.0) as http:
        resp = await http.get(
            f"{API}/repos/{GITHUB_REPO}/issues",
            headers=_headers(),
            params={"labels": FEEDBACK_LABEL, "state": "open", "per_page": 100},
        )
    resp.raise_for_status()
    return [
        (item["number"], item["title"])
        for item in resp.json()
        if "pull_request" not in item
    ]


async def _ensure_label(http: httpx.AsyncClient, name: str) -> None:
    # 422 = already exists; anything else is non-fatal (issue still files,
    # GitHub silently drops unknown labels).
    resp = await http.post(
        f"{API}/repos/{GITHUB_REPO}/labels",
        headers=_headers(),
        json={"name": name, "color": "5319e7"},
    )
    if resp.status_code not in (201, 422):
        logger.warning("Could not ensure label %s: %s %s", name, resp.status_code, resp.text)


async def create_issue(
    title: str, classification: str, summary: str, details: str, permalink: str
) -> str:
    """File a new issue; returns its URL."""
    body = (
        f"**Classification:** {classification}\n\n"
        f"**Summary:** {summary}\n\n"
        f"**Details:**\n{details}\n\n"
        f"**Discord thread:** {permalink}\n\n"
        f"---\n*Filed by the vibepost feedback bot.*"
    )
    async with httpx.AsyncClient(timeout=15.0) as http:
        await _ensure_label(http, FEEDBACK_LABEL)
        await _ensure_label(http, classification)
        resp = await http.post(
            f"{API}/repos/{GITHUB_REPO}/issues",
            headers=_headers(),
            json={"title": title, "body": body, "labels": [FEEDBACK_LABEL, classification]},
        )
    resp.raise_for_status()
    return resp.json()["html_url"]


async def comment_on_issue(number: int, summary: str, permalink: str) -> str:
    """Add another report to an existing issue; returns the issue URL."""
    body = (
        f"Another report from Discord:\n\n{summary}\n\n"
        f"**Discord thread:** {permalink}\n\n"
        f"---\n*Filed by the vibepost feedback bot.*"
    )
    async with httpx.AsyncClient(timeout=15.0) as http:
        resp = await http.post(
            f"{API}/repos/{GITHUB_REPO}/issues/{number}/comments",
            headers=_headers(),
            json={"body": body},
        )
    resp.raise_for_status()
    return resp.json()["html_url"]
