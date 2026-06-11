# Security Considerations

Things we are responsible for protecting, and how.

> **Implementation status (closed beta, June 2026).** This document describes
> the *target* architecture (Supabase Auth + Vault, R2, RLS). The shipped
> closed beta differs, and an honest threat model has to say so:
>
> - **Platform credentials are plaintext JSON in SQLite** on the Fly volume,
>   not in Vault. A database dump *does* yield live tokens. Mitigations in the
>   beta: per-user API isolation, non-root container, strict validation of
>   every file path that reaches `open()`, no credential ever serialized to
>   the client, logs, or exports. Vault (or app-level encryption) is required
>   before widening access beyond trusted beta users.
> - **App auth is email + bcrypt password handled by us**, not Supabase
>   passkeys yet. Sessions are JWTs in httpOnly `SameSite=Lax` cookies with a
>   per-user epoch so password changes revoke all outstanding sessions.
> - **Isolation is application-level ownership checks** (every query joins
>   through the requesting user), not database RLS.
> - **Media is public-but-unguessable** (`/media/<uuid>`), not private R2 with
>   presigned URLs — see `media-privacy.md` for the target and the beta note.
>
> See `docs/launch-guide.md` for the accepted-limitations list shown to the
> operator.

---

## Platform Credentials (User Secrets)

OAuth access tokens, refresh tokens, and Bluesky app passwords give vibepost the
ability to post on a user's behalf. If leaked, an attacker can impersonate the
user on every connected platform.

**Protection:**
- Stored in Supabase Vault (pgsodium, encrypted at rest with a server-managed key)
- Only a UUID reference is stored in the `channels` table — a full DB dump is useless
- Tokens are decrypted in memory at post time only; never logged, never returned to the client
- Scope-limit every token request: request only the permissions needed to post, not
  admin or ad-management scopes
- Store `token_expires_at` in plaintext (not sensitive) and refresh proactively; a
  stale token in Vault is still worthless to an attacker but causes user-visible failures

**Bluesky-specific:** an app password is nearly as powerful as the main password.
When the user disconnects Bluesky, revoke the app password via atproto and delete
the Vault entry.

See also: `architecture.md` — Secrets and Vault section.

---

## Scheduled Post Content

A scheduled post may contain embargoed announcements, personal news the user
hasn't shared yet, or commercially sensitive information. Exposing it early
is a real harm even if the content eventually becomes public.

**Protection:**
- Post text stored in Postgres, isolated by RLS — other users cannot read it
- Media stored in a private R2 bucket — no public URL exists until T-5 minutes
  before posting, and even then only a short-TTL presigned URL is generated
- Drafts never leave the browser (OPFS) — they are invisible to the backend until
  the user explicitly schedules or posts
- Cancel right up to the wire: T-5min for Instagram/Threads with media, T-0 for
  all others; after cancellation, the R2 object is deleted and any presigned URL
  that was generated expires within its TTL

---

## Personal Information (PII)

At sign-up and sign-in we collect at minimum an email address and (optionally) a
display name or avatar. This is the floor of PII we hold.

**Protection:**
- Supabase Auth owns the credential store; we never handle or store passwords
  ourselves — hashing, salting, and breach detection are Supabase's responsibility
- Email is held by Supabase Auth, not in our application tables — reduce the
  number of places PII lives
- Collect the minimum necessary: do not ask for phone number, date of birth, or
  other fields unless a specific feature requires them
- GDPR / right to erasure: when a user deletes their account, delete all their
  rows from every table (Postgres cascade on `auth.users` deletion), purge their
  R2 objects, and revoke + delete all Vault secrets — do not retain post history
  or analytics that could re-identify them
- Audit log access to sensitive operations (token reads, schedule changes) so
  that if a breach occurs the blast radius can be scoped

---

## Payment Information

**Short answer: we never touch it.**

Use **Stripe Checkout** or **Stripe Billing Portal** for any payments. The card
form is hosted by Stripe on their domain; the card number, CVV, and expiry never
reach our servers. We receive only:
- A Stripe customer ID (not sensitive)
- Webhook events: `customer.subscription.created`, `invoice.paid`, etc.
- A subscription status flag in our DB: `active`, `trialing`, `past_due`, etc.

This means we are not in scope for PCI DSS card data requirements. We still need
to protect the Stripe webhook signing secret (env var on Fly.io) to prevent
fraudulent webhook injection.

If we ever need to store a billing address (e.g., for VAT compliance), store it
in Stripe's customer object, not in our DB, so Stripe's compliance posture covers it.

---

## App-Level Credentials

The Meta App Secret, LinkedIn Client Secret, R2 access key, Supabase service role
key, and Stripe webhook secret are all vibepost's own credentials. If any of these
leak, an attacker can impersonate the app itself.

**Protection:**
- Live only as Fly.io secrets (`flyctl secrets set`) — never in source code,
  never in the database, never in logs
- Never returned to the client in any API response
- Rotate immediately if a leak is suspected; each can be rotated independently
- The Supabase service role key in particular has RLS bypass — treat it as a
  master key; it should only ever be used by the backend scheduler for jobs that
  run outside a user request context

---

## Transport Security

**Protection:**
- All traffic is HTTPS. Fly.io, Supabase, and Cloudflare all terminate TLS
  automatically with managed certificates.
- The R2 presigned URLs are HTTPS. Never generate presigned URLs over HTTP.
- Set `Strict-Transport-Security` on the API and frontend.
- CORS: the FastAPI backend should only allow the production Cloudflare Pages
  origin (and localhost for development) — not `*`.

---

## Authentication and Session Security

**Protection:**
- Supabase Auth JWTs have a configurable expiry; keep it short (1 hour) and use
  refresh tokens for silent re-auth — do not issue week-long access tokens
- The JWT secret is an app-level credential (see above); if it leaks, all active
  sessions are compromised and every user must re-authenticate
- Store the access token in memory (React state) rather than `localStorage` where
  possible; `localStorage` is accessible to any XSS payload. If you need
  persistence across page reloads, use `sessionStorage` or a short-lived cookie
  with `HttpOnly` and `SameSite=Strict`.
- The OAuth state parameter (used in platform OAuth flows to prevent CSRF) is
  already implemented in the current codebase; keep it

---

## Injection and Input Handling

**Protection:**
- All DB queries use SQLAlchemy parameterised queries — never string-interpolated SQL
- Post text is stored verbatim and displayed verbatim in the UI; ensure the frontend
  sanitises output before rendering if it ever renders HTML (Bluesky rich text, etc.)
- Filenames from user uploads are not trusted: generate a random UUID-based R2 key
  on the backend; never use the original filename as the storage key

---

## Dependency and Supply Chain

**Protection:**
- Pin exact dependency versions in `requirements.txt` and `package.json` lockfiles
- Run `pip-audit` / `npm audit` in CI to catch known CVEs
- Minimise dependencies: every package added is potential attack surface
- The Docker base images (`python:3.12-slim`, `node:20-alpine`, `nginx:1.27-alpine`)
  should be rebuilt periodically to pick up OS-level patches

---

## What We Are Not Responsible For

Things that are somebody else's problem by design:

- Password storage and hashing — Supabase Auth
- Card data — Stripe
- Encryption key management for Vault — Supabase (pgsodium)
- DDoS mitigation — Cloudflare (frontend), Fly.io (backend has some protection)
- TLS certificate issuance and renewal — all three providers handle this automatically

---

## Open Questions

- Do we want audit logs for sensitive events (token reads, post cancellations,
  account deletion)? Postgres `audit` extension or a separate log table. Adds
  compliance value; adds storage cost.
- Retention policy for post content after publish: delete from our DB, or keep
  for the user's own history? Keeping it adds GDPR surface area.
- If we ever offer team/agency plans (multiple users on one billing account),
  the RLS model needs revisiting — team members may need read access to shared
  profiles without full account access.
