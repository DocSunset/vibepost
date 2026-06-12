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

"""Configuration for the feedback bot, read from the environment / .env.

The bot is designed to run anywhere with outbound internet — a dev laptop is
fine. See README.md for how to obtain each value.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# Required
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
FEEDBACK_CHANNEL_ID = int(os.environ.get("FEEDBACK_CHANNEL_ID", "0"))
ADMIN_USER_ID = int(os.environ.get("ADMIN_USER_ID", "0"))

# Optional
DIGEST_CHANNEL_ID = int(os.environ.get("DIGEST_CHANNEL_ID", "0"))
GITHUB_REPO = os.environ.get("GITHUB_REPO", "DocSunset/vibepost")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# Cost guardrails. The budget bounds worst-case spend: even a spam raid can
# trigger at most HOURLY_CALL_BUDGET model calls per hour.
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "600"))
HOURLY_CALL_BUDGET = int(os.environ.get("HOURLY_CALL_BUDGET", "30"))
DIGEST_HOUR_UTC = int(os.environ.get("DIGEST_HOUR_UTC", "13"))

STATE_PATH = Path(os.environ.get("STATE_PATH", str(Path(__file__).parent / "state.json")))


def validate() -> None:
    missing = [
        name
        for name, value in [
            ("DISCORD_TOKEN", DISCORD_TOKEN),
            ("ANTHROPIC_API_KEY", ANTHROPIC_API_KEY),
            ("FEEDBACK_CHANNEL_ID", FEEDBACK_CHANNEL_ID),
            ("ADMIN_USER_ID", ADMIN_USER_ID),
        ]
        if not value
    ]
    if missing:
        sys.exit(f"Missing required configuration: {', '.join(missing)} (see .env.example)")
