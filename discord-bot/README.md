# vibepost feedback bot

An LLM-backed Discord bot with one job: collect beta feedback well, then get
out of the way. It watches a single `#feedback` channel; each top-level
message gets a thread where the bot acknowledges, asks at most two clarifying
questions, and files the result as a labelled GitHub issue (deduplicated
against open ones). Reports that smell like security vulnerabilities are
never filed publicly — the maintainer is DM'd instead. Optionally it posts a
nightly digest of the day's feedback.

It is designed to run from a development machine: it only makes outbound
connections (Discord gateway websocket, Anthropic API, GitHub API), needs no
public IP, and catches up on missed messages when it starts. If the laptop
sleeps, feedback just waits in the channel.

## Cost

Model calls use Claude Haiku with small, per-thread contexts. A hard hourly
call budget (`HOURLY_CALL_BUDGET`, default 30) bounds worst-case spend: when
exhausted, the bot reacts with ⏳, pings the admin once, and goes quiet.
Expected cost for a closed beta is a few dollars per month.

## Setup

1. **Create the Discord application** at
   <https://discord.com/developers/applications>:
   - *Bot* tab: create the bot, copy the token, and enable the
     **Message Content Intent** (under "Privileged Gateway Intents" — the bot
     cannot read feedback without it).
   - *OAuth2 → URL Generator*: scope `bot`; permissions **View Channels,
     Send Messages, Create Public Threads, Send Messages in Threads,
     Read Message History, Add Reactions**. Open the generated URL to invite
     the bot to your server.
2. **Collect IDs**: in Discord, enable Settings → Advanced → Developer Mode,
   then right-click the feedback channel / digest channel / your own name and
   "Copy ID".
3. **Anthropic API key**: create a dedicated key at
   <https://console.anthropic.com> and give it a low monthly spend limit.
4. **GitHub token** (optional but recommended): a fine-grained PAT with
   Issues read/write on the repo. Without it the bot still works, it just
   summarizes into the thread instead of filing issues.
5. **Configure and run**:

   ```sh
   cd discord-bot
   cp .env.example .env   # fill it in
   uv venv .venv && VIRTUAL_ENV=$PWD/.venv uv pip install -r requirements.txt
   .venv/bin/python bot.py
   ```

Pin a notice in the feedback channel so people know an AI reads it, e.g.:

> 🤖 An AI assistant reads this channel to help triage feedback. It files
> actionable reports at github.com/DocSunset/vibepost/issues. Don't post
> passwords or tokens here (or anywhere).

## Behaviour notes

- The bot only ever acts in the feedback channel and its threads, ignores
  all bots and webhooks, and stops responding in a thread once feedback is
  filed.
- Conversations are stateless per thread: each reply re-reads only that
  thread, so context (and cost) stays small forever.
- The hard cap on clarifying questions is enforced in code, not just in the
  prompt: on the bot's third turn it is forced to file with what it has.
- State lives in `state.json` (last message processed, filed threads, call
  budget). Delete it to reset; the bot will then start from "now".
- Messages sent to the channel are processed via the Anthropic API
  (standard API traffic, not used for training) and may end up quoted in
  public GitHub issues — that's the pinned notice above.

## Later

Promoting it off the laptop is copying the directory and `.env` to any
machine that can run Python — a tiny Fly machine, a Pi, anything. Nothing in
the bot knows where it runs.
