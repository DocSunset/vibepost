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

"""Transactional email.

Uses Resend's HTTP API when RESEND_API_KEY is set; otherwise logs the message
to the server console, which is how sign-in links are retrieved during local
development. Only operational mail is ever sent (sign-in links, security
notices) — never marketing; see roadmap/privacy.md.
"""

import logging

import httpx

from .config import EMAIL_FROM, RESEND_API_KEY

logger = logging.getLogger("vibepost.email")


def send_email(to: str, subject: str, text: str) -> bool:
    """Send a plain-text email. Returns True if handed off successfully.

    Never raises: callers like the magic-link endpoint must not leak
    delivery failures to the client (email enumeration), so failures are
    logged and swallowed here.
    """
    if not RESEND_API_KEY:
        logger.warning(
            "RESEND_API_KEY not set; email to %s not sent.\nSubject: %s\n%s",
            to, subject, text,
        )
        # In development the operator reads the link from the log; treat as
        # delivered so flows can be exercised end to end.
        return True
    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={"from": EMAIL_FROM, "to": [to], "subject": subject, "text": text},
            timeout=10.0,
        )
        if resp.status_code >= 400:
            logger.error("Resend rejected email to %s: %s %s", to, resp.status_code, resp.text)
            return False
        return True
    except httpx.HTTPError as exc:
        logger.error("Failed to send email to %s: %s", to, exc)
        return False
