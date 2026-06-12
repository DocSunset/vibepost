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

"""Tiny JSON-file persistence.

Tracks just enough to survive restarts on a laptop that sleeps:
- the last top-level feedback message processed (for catch-up on startup),
- which threads have already been filed (so the bot goes quiet in them),
- a sliding log of model-call timestamps (the hourly cost budget).

Single process, low traffic — a JSON file with atomic replace is plenty.
"""

import json
import os
import time
from pathlib import Path

from config import STATE_PATH


class State:
    def __init__(self, path: Path):
        self.path = path
        self.last_seen_id: int = 0
        self.filed_threads: dict[str, str] = {}  # thread id -> issue URL / "escalated" / "recorded"
        self.call_log: list[float] = []
        if path.exists():
            data = json.loads(path.read_text())
            self.last_seen_id = data.get("last_seen_id", 0)
            self.filed_threads = data.get("filed_threads", {})
            self.call_log = data.get("call_log", [])

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {
                    "last_seen_id": self.last_seen_id,
                    "filed_threads": self.filed_threads,
                    "call_log": self.call_log[-200:],
                },
                indent=2,
            )
        )
        os.replace(tmp, self.path)

    def mark_seen(self, message_id: int) -> None:
        if message_id > self.last_seen_id:
            self.last_seen_id = message_id
            self.save()

    def filed(self, thread_id: int) -> str | None:
        return self.filed_threads.get(str(thread_id))

    def mark_filed(self, thread_id: int, ref: str) -> None:
        self.filed_threads[str(thread_id)] = ref
        self.save()

    # -- model-call budget -------------------------------------------------

    def record_call(self) -> None:
        self.call_log.append(time.time())
        self.save()

    def calls_in_last_hour(self) -> int:
        cutoff = time.time() - 3600
        return sum(1 for t in self.call_log if t > cutoff)


STATE = State(STATE_PATH)
