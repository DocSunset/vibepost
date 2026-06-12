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

"""The LLM side of the feedback bot.

Design: interviewer + librarian, not a chatbot. Each call is stateless — the
only context is the one feedback thread — so cost scales with the length of a
single conversation (a few hundred tokens), never with the server's history.
"""

import logging
import re
from typing import Awaitable, Callable

from anthropic import AsyncAnthropic

from config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL, MAX_TOKENS
from state import STATE

logger = logging.getLogger("feedback-bot.agent")

client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """\
You are the feedback assistant in the Discord server for vibepost, a social
media cross-posting and scheduling tool currently in closed beta. Users
connect their Bluesky, Facebook, Instagram, Threads, and LinkedIn accounts
and schedule posts to several platforms at once.

Your only job is to collect feedback well. You are an interviewer and a
librarian, not a chatbot.

Rules:
- Be brief and warm. One short paragraph per message, no bullet lists.
- If the feedback is already actionable (a clear bug report or feature
  request), file it immediately with the file_feedback tool — don't ask
  questions for the sake of it.
- Otherwise, ask AT MOST two clarifying messages in total. Useful things to
  ask about: steps to reproduce, expected vs. actual behaviour, which
  platform or channel was involved. Then file with what you have.
- After filing, thank them briefly and stop. Do not keep the conversation
  going.
- For pure praise or thanks with nothing actionable, don't file anything —
  just thank them warmly.
- If a report smells like a security vulnerability (authentication bypass,
  seeing someone else's data, leaked credentials, injection), do NOT file it
  and do NOT discuss details further. Use the escalate_security tool
  immediately so the maintainer is notified privately.
- Never promise that anything will be fixed or built, and never estimate
  timelines. "I've passed it on" is the strongest commitment you can make.
- Never ask for passwords, tokens, or personal data. If someone pastes a
  credential, tell them to revoke it right away.
- You only handle vibepost feedback. Politely decline everything else
  (general chat, coding help, questions about other products).
"""

TOOLS = [
    {
        "name": "file_feedback",
        "description": (
            "Record one piece of user feedback permanently. Call this once per "
            "thread, when you have enough to act on (or when you've used up "
            "your clarifying questions)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Issue-tracker title, imperative and specific, max ~70 chars.",
                },
                "classification": {
                    "type": "string",
                    "enum": ["bug", "feature", "ux", "other"],
                },
                "summary": {
                    "type": "string",
                    "description": "2-3 sentence summary of the feedback.",
                },
                "details": {
                    "type": "string",
                    "description": (
                        "Everything actionable from the conversation: repro steps, "
                        "platform, expected vs. actual. Verbatim quotes welcome."
                    ),
                },
            },
            "required": ["title", "classification", "summary", "details"],
        },
    },
    {
        "name": "escalate_security",
        "description": (
            "Privately notify the maintainer of a potential security issue "
            "instead of filing it publicly. Use at the first hint of a "
            "vulnerability report."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "One-paragraph description of what was reported.",
                }
            },
            "required": ["reason"],
        },
    },
]

# Hard cap, enforced in code, not just in the prompt: once the bot has spoken
# this many times in a thread without filing, the next call MUST file.
MAX_ASSISTANT_TURNS_BEFORE_FILING = 2


def merge_history(entries: list[tuple[bool, str, str]]) -> list[dict]:
    """Turn thread messages into an alternating user/assistant message list.

    entries: (is_bot, author_display_name, content) in chronological order.
    User messages are prefixed with the author's name so the model can follow
    multi-person threads; consecutive same-role messages are merged because
    the Messages API requires alternation.
    """
    messages: list[dict] = []
    for is_bot, author, content in entries:
        content = content.strip()
        if not content:
            continue
        role = "assistant" if is_bot else "user"
        text = content if is_bot else f"{author}: {content}"
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"] += "\n\n" + text
        else:
            messages.append({"role": role, "content": text})
    # The API requires the conversation to start with a user message.
    if messages and messages[0]["role"] == "assistant":
        messages.insert(0, {"role": "user", "content": "(message unavailable)"})
    return messages


async def run_turn(
    messages: list[dict],
    on_file: Callable[[dict], Awaitable[str]],
    on_escalate: Callable[[dict], Awaitable[str]],
) -> str:
    """Run one bot turn for a thread. Returns the text to post.

    Tool calls are executed via the callbacks, whose string results are fed
    back so the model's closing message can reflect what actually happened.
    """
    assistant_turns = sum(1 for m in messages if m["role"] == "assistant")
    kwargs: dict = dict(
        model=ANTHROPIC_MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=messages,
    )
    if assistant_turns >= MAX_ASSISTANT_TURNS_BEFORE_FILING:
        kwargs["tool_choice"] = {"type": "tool", "name": "file_feedback"}

    STATE.record_call()
    response = await client.messages.create(**kwargs)

    tool_uses = [b for b in response.content if b.type == "tool_use"]
    texts = [b.text for b in response.content if b.type == "text"]
    if not tool_uses:
        return "\n".join(texts)

    tool_use = tool_uses[0]
    if tool_use.name == "file_feedback":
        result = await on_file(tool_use.input)
    else:
        result = await on_escalate(tool_use.input)

    followup = messages + [
        {"role": "assistant", "content": response.content},
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": tool_use.id, "content": result}
            ],
        },
    ]
    STATE.record_call()
    closing = await client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=followup,
    )
    closing_texts = [b.text for b in closing.content if b.type == "text"]
    return "\n".join(texts + closing_texts)


async def find_duplicate(
    title: str, summary: str, existing: list[tuple[int, str]]
) -> int | None:
    """One cheap call: is this feedback a duplicate of an open issue?"""
    if not existing:
        return None
    listing = "\n".join(f"#{number}: {issue_title}" for number, issue_title in existing)
    STATE.record_call()
    response = await client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=20,
        system=(
            "You deduplicate feedback against an issue tracker. Answer with "
            "ONLY the issue number (digits, no #) if the new feedback clearly "
            "reports the same thing as an existing issue, or the word 'no'. "
            "When unsure, answer 'no'."
        ),
        messages=[
            {
                "role": "user",
                "content": f"Existing open issues:\n{listing}\n\nNew feedback:\n{title}\n{summary}",
            }
        ],
    )
    answer = "".join(b.text for b in response.content if b.type == "text").strip()
    match = re.fullmatch(r"#?(\d+)", answer)
    if match and any(int(match.group(1)) == number for number, _ in existing):
        return int(match.group(1))
    return None


async def summarize_digest(transcript: str) -> str:
    """Summarize a day of feedback-channel activity into a short digest."""
    STATE.record_call()
    response = await client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=800,
        system=(
            "Summarize one day of activity from the feedback channel of "
            "vibepost (a social media scheduling tool in closed beta) for the "
            "maintainer. Group by theme, lead with anything urgent, mention "
            "who reported what, and keep it under ~200 words. Plain prose "
            "with at most a few short bullet points."
        ),
        messages=[{"role": "user", "content": transcript}],
    )
    return "".join(b.text for b in response.content if b.type == "text")
