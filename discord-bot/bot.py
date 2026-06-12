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

"""vibepost feedback bot.

Watches one #feedback channel. Each top-level message gets a thread and a
short, bounded conversation (ack -> at most two clarifying questions -> file
to GitHub). Security-flavoured reports are escalated privately instead of
filed. A nightly digest summarizes the day. Designed to run from a laptop:
pure outbound websocket, and on startup it catches up on anything posted
while it was offline.
"""

import datetime
import logging
import time
from functools import partial

import discord
from discord.ext import tasks

import agent
import config
import issues
from config import (
    ADMIN_USER_ID,
    DIGEST_CHANNEL_ID,
    DIGEST_HOUR_UTC,
    FEEDBACK_CHANNEL_ID,
    HOURLY_CALL_BUDGET,
)
from state import STATE

logger = logging.getLogger("feedback-bot")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

OK_TYPES = (discord.MessageType.default, discord.MessageType.reply)

_ready_once = False
_last_budget_alert = 0.0


def budget_ok() -> bool:
    return STATE.calls_in_last_hour() < HOURLY_CALL_BUDGET


async def alert_budget(channel) -> None:
    """Ping the admin (at most once an hour) when the call budget is hit."""
    global _last_budget_alert
    logger.warning("Hourly model-call budget (%d) exhausted.", HOURLY_CALL_BUDGET)
    if time.time() - _last_budget_alert < 3600:
        return
    _last_budget_alert = time.time()
    try:
        await channel.send(
            f"<@{ADMIN_USER_ID}> I've hit my hourly budget of {HOURLY_CALL_BUDGET} "
            f"model calls, so I'm pausing. Unanswered feedback will be picked up "
            f"on my next restart."
        )
    except discord.HTTPException:
        logger.exception("Could not post budget alert")


async def fetch_feedback_channel() -> discord.TextChannel:
    return client.get_channel(FEEDBACK_CHANNEL_ID) or await client.fetch_channel(
        FEEDBACK_CHANNEL_ID
    )


async def build_history(thread: discord.Thread) -> list[dict]:
    """Collect the thread (plus its starter message) into model messages."""
    entries: list[tuple[bool, str, str]] = []
    starter = thread.starter_message
    if starter is None:
        try:
            parent = await fetch_feedback_channel()
            starter = await parent.fetch_message(thread.id)
        except discord.NotFound:
            starter = None
    if starter is not None and starter.type in OK_TYPES:
        entries.append(
            (starter.author.id == client.user.id, starter.author.display_name, starter.content)
        )
    async for message in thread.history(limit=50, oldest_first=True):
        if message.type not in OK_TYPES:
            continue
        entries.append(
            (message.author.id == client.user.id, message.author.display_name, message.content)
        )
    return agent.merge_history(entries)


def make_on_file(thread: discord.Thread, permalink: str):
    async def on_file(inputs: dict) -> str:
        title = str(inputs.get("title", "Feedback"))[:120]
        classification = inputs.get("classification", "other")
        summary = str(inputs.get("summary", ""))
        details = str(inputs.get("details", ""))
        if not issues.configured():
            STATE.mark_filed(thread.id, "recorded")
            await thread.send(f"**Recorded:** {title}\n{summary}"[:2000])
            return "Recorded in the thread (GitHub filing is not configured)."
        try:
            existing = await issues.list_open_feedback_issues()
            duplicate = await agent.find_duplicate(title, summary, existing)
            if duplicate is not None:
                url = await issues.comment_on_issue(duplicate, summary, permalink)
                STATE.mark_filed(thread.id, url)
                await thread.send(f"📌 Added to an existing report: <{url}>")
                return f"Added as a comment on existing issue #{duplicate}: {url}"
            url = await issues.create_issue(title, classification, summary, details, permalink)
            STATE.mark_filed(thread.id, url)
            await thread.send(f"📌 Filed: <{url}>")
            return f"Filed new issue: {url}"
        except Exception:
            logger.exception("GitHub filing failed")
            STATE.mark_filed(thread.id, "recorded")
            await thread.send(f"**Recorded** (filing failed): {title}\n{summary}"[:2000])
            return "GitHub filing failed; the feedback was recorded in the thread instead."

    return on_file


def make_on_escalate(thread: discord.Thread, permalink: str):
    async def on_escalate(inputs: dict) -> str:
        STATE.mark_filed(thread.id, "escalated")
        reason = str(inputs.get("reason", ""))[:1500]
        try:
            admin = await client.fetch_user(ADMIN_USER_ID)
            await admin.send(f"🚨 Possible security report in {permalink}\n\n{reason}")
            return "The maintainer has been notified privately by DM."
        except discord.HTTPException:
            logger.exception("Could not DM admin; falling back to thread ping")
            await thread.send(
                f"<@{ADMIN_USER_ID}> — flagging this thread for your private attention."
            )
            return "Could not DM the maintainer, so they were pinged in the thread."

    return on_escalate


async def respond_in_thread(thread: discord.Thread) -> None:
    if not budget_ok():
        await alert_budget(thread)
        return
    permalink = thread.jump_url
    try:
        async with thread.typing():
            messages = await build_history(thread)
            if not messages:
                return
            text = await agent.run_turn(
                messages,
                on_file=make_on_file(thread, permalink),
                on_escalate=make_on_escalate(thread, permalink),
            )
        if text.strip():
            await thread.send(text.strip()[:2000])
    except Exception:
        logger.exception("Error responding in thread %s", thread.id)
        try:
            await thread.send("⚠️ I hit a snag processing this — it's logged, and a human will look.")
        except discord.HTTPException:
            pass


async def handle_new_feedback(message: discord.Message) -> None:
    if not budget_ok():
        try:
            await message.add_reaction("⏳")
        except discord.HTTPException:
            pass
        await alert_budget(message.channel)
        return  # deliberately not marked seen: catch-up retries it after restart
    STATE.mark_seen(message.id)
    name = " ".join(message.content.split())[:80] or "Feedback"
    thread = await message.create_thread(name=f"Feedback: {name}")
    await respond_in_thread(thread)


@client.event
async def on_message(message: discord.Message) -> None:
    # Never react to bots or webhooks: this is the loop-prevention rule.
    if message.author.bot or message.webhook_id is not None:
        return
    if message.type not in OK_TYPES:
        return
    channel = message.channel
    if isinstance(channel, discord.Thread) and channel.parent_id == FEEDBACK_CHANNEL_ID:
        if STATE.filed(channel.id):
            return  # this thread is done; stay quiet
        await respond_in_thread(channel)
    elif channel.id == FEEDBACK_CHANNEL_ID:
        await handle_new_feedback(message)


async def catch_up() -> None:
    """Process anything posted while the bot was offline (laptop slept)."""
    channel = await fetch_feedback_channel()
    if STATE.last_seen_id == 0:
        # First ever run: start from now rather than excavating history.
        if channel.last_message_id:
            STATE.mark_seen(channel.last_message_id)
    else:
        async for message in channel.history(
            after=discord.Object(id=STATE.last_seen_id), limit=100, oldest_first=True
        ):
            if message.author.bot or message.type not in OK_TYPES:
                STATE.mark_seen(message.id)
                continue
            if message.thread is not None:
                STATE.mark_seen(message.id)
                continue
            logger.info("Catching up on missed message %s", message.id)
            await handle_new_feedback(message)
    # Threads where a user spoke last and nothing has been filed yet.
    for thread in channel.threads:
        if STATE.filed(thread.id):
            continue
        last = None
        async for last in thread.history(limit=1):
            break
        if last is not None and not last.author.bot and last.type in OK_TYPES:
            logger.info("Catching up on thread %s", thread.id)
            await respond_in_thread(thread)


@tasks.loop(time=datetime.time(hour=DIGEST_HOUR_UTC, tzinfo=datetime.timezone.utc))
async def daily_digest() -> None:
    if not DIGEST_CHANNEL_ID:
        return
    try:
        channel = await fetch_feedback_channel()
        since = discord.utils.utcnow() - datetime.timedelta(hours=24)
        lines: list[str] = []
        async for message in channel.history(after=since, limit=200, oldest_first=True):
            if message.author.bot or message.type not in OK_TYPES:
                continue
            lines.append(f"{message.author.display_name}: {message.clean_content}")
        for thread in channel.threads:
            async for message in thread.history(after=since, limit=100, oldest_first=True):
                if message.type not in OK_TYPES:
                    continue
                author = "bot" if message.author.id == client.user.id else message.author.display_name
                lines.append(f"[{thread.name}] {author}: {message.clean_content}")
        if not lines:
            return
        if not budget_ok():
            logger.warning("Skipping digest: model-call budget exhausted")
            return
        summary = await agent.summarize_digest("\n".join(lines)[:8000])
        digest_channel = client.get_channel(DIGEST_CHANNEL_ID) or await client.fetch_channel(
            DIGEST_CHANNEL_ID
        )
        today = datetime.date.today().isoformat()
        await digest_channel.send(f"**Feedback digest — {today}**\n{summary}"[:2000])
    except Exception:
        logger.exception("Daily digest failed")


@client.event
async def on_ready() -> None:
    global _ready_once
    logger.info("Logged in as %s (id %s)", client.user, client.user.id)
    if _ready_once:
        return  # reconnects re-fire on_ready; only initialize once
    _ready_once = True
    await catch_up()
    daily_digest.start()
    logger.info("Ready. Watching channel %s.", FEEDBACK_CHANNEL_ID)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config.validate()
    client.run(config.DISCORD_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
