# Full System Architecture

This document is the primary technical reference. It synthesises everything
discussed and cross-references the more focused notes in this directory.
Start here.

---

## Services and Roles

| Service | Role |
|---|---|
| **Cloudflare Pages** | Hosts the built React frontend. Unlimited bandwidth, free. |
| **Supabase** | Postgres database, user auth (JWTs), encrypted secrets vault. |
| **Cloudflare R2** | Object storage for post media. Zero egress cost. Private bucket. |
| **Fly.io** | Runs the FastAPI backend. Thin: handles OAuth exchanges, presigned URL generation, scheduling, and platform API dispatch. Never touches media bytes except for Bluesky and LinkedIn scheduled posts (see Media Handling). |
| **Stripe** | Billing and subscription management. Hosts the payment form — we never see card data. |

---

## Two Completely Separate OAuth Flows

This is the most important conceptual distinction in the system.

### 1. App Auth — signing into vibepost

Users authenticate to vibepost itself via **Supabase Auth**. Supabase issues a
signed JWT on login. That JWT is sent as a Bearer token on every API request.
The FastAPI backend verifies it using Supabase's JWT secret (an env var) and
extracts `user_id` from the token claims. No session table. No cookies. Stateless.

Supabase Auth supports:
- Email + password with verification and password reset out of the box
- Social login (Google, GitHub, etc.) — useful for reducing signup friction
- Magic links

The `user_id` from the verified JWT is the key that scopes every database query.
It is threaded into every route handler and used in all RLS policies.

```
Browser  →  POST /api/auth/login  →  Supabase Auth  →  JWT
Browser  →  GET /api/posts  (Authorization: Bearer <jwt>)
             ↓
           FastAPI verifies JWT, extracts user_id
           DB query: SELECT ... WHERE user_id = $user_id
```

### 2. Platform Auth — connecting social accounts

When a user connects Facebook, Instagram, Threads, or LinkedIn, they go through
that *platform's* OAuth flow. This has nothing to do with signing into vibepost.

The backend handles the OAuth token exchange (requires the platform's
`client_secret`, which never leaves the server). The resulting access token is
stored in Supabase Vault (see Secrets). The frontend never sees the token after
the callback.

Bluesky uses app passwords instead of OAuth. The handle + app password are
stored in Vault the same way.

---

## Multi-Tenancy and User Isolation

Every table that holds user data — `profiles`, `channels`, `posts`,
`post_channels`, `app_settings` — carries a `user_id` foreign key referencing
`auth.users` (Supabase's built-in user table).

### Row Level Security

Supabase's Row Level Security (RLS) enforces isolation at the database layer.
Even if application code has a bug that omits a `WHERE user_id = ?` clause, the
database refuses to return another user's rows. This is not optional — it is the
foundation of multi-tenant safety.

Policies take the form:

```sql
-- Profiles: users can only see and modify their own
CREATE POLICY "profiles_own" ON profiles
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- Posts: same pattern
CREATE POLICY "posts_own" ON posts
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- Channels: same
CREATE POLICY "channels_own" ON channels
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());
```

`auth.uid()` is a Supabase function that returns the `user_id` from the JWT of
the current request. It is set automatically by Supabase when you pass the JWT
to the Postgres connection via the Supabase client. The FastAPI backend uses the
Supabase service role for some operations (scheduling, posting) and must
manually enforce `user_id` filtering in those cases — RLS with service role is
bypassed, so application-level enforcement is required for background jobs.

---

## Secrets and Vault

There are two distinct categories of secrets in the system.

### Category 1: App-level credentials

These belong to the vibepost application, not individual users. They are the
same for all users:

- Meta App ID and App Secret (for Facebook/Instagram/Threads OAuth)
- LinkedIn Client ID and Client Secret
- Cloudflare R2 access key and secret
- Supabase service role key
- JWT secret (for verifying Supabase Auth tokens)

These live in **environment variables** on Fly.io (set via `flyctl secrets set`).
They are never in the database and never sent to the client.

### Category 2: Per-user platform credentials

These belong to individual users and differ per account:

- OAuth access tokens for Facebook Pages, Instagram, Threads, LinkedIn
- Bluesky handle + app password

These are stored in **Supabase Vault** — a Postgres extension (`pgsodium`) that
encrypts values at rest using a server-managed key. The application never stores
these in plaintext in any table.

**Storage pattern:**

```sql
-- When a user connects a platform:
SELECT vault.create_secret(
  $token,           -- the plaintext access token
  $name,            -- e.g. 'linkedin_token_user123_channel456'
  $description
) → vault_secret_id (UUID)

-- Store only the UUID in the channels table:
UPDATE channels SET vault_secret_id = $vault_secret_id
  WHERE id = $channel_id;
```

**Retrieval pattern (at post time):**

```sql
SELECT decrypted_secret FROM vault.decrypted_secrets
  WHERE id = $vault_secret_id;
```

The decrypted value is read inside the Postgres connection and passed to the
backend in memory. It is never written to any log or persisted in plaintext.

**Key point:** the `channels` table no longer holds a `credentials` JSON column.
It holds a `vault_secret_id` UUID. Even a full database dump exposes nothing
useful about user credentials.

### Token Refresh

OAuth access tokens expire. The scheduler must handle token refresh:
- Before firing a post, check token expiry (stored as a separate non-secret
  column on the channel: `token_expires_at`)
- If expired or within 24 hours of expiry, refresh the token via the platform
  API and write the new token back to Vault using the same `vault_secret_id`
- LinkedIn tokens last 60 days; Meta long-lived tokens last 60 days; Bluesky app
  passwords don't expire

---

## Media Handling

See also: `client-side-architecture.md`, `media-privacy.md`

### Draft Phase (no backend involvement)

Media lives in the browser's **Origin Private File System (OPFS)** while the
user is composing. Nothing is uploaded anywhere. The user can abandon the post
and no bytes ever leave their device.

### Upload Phase (browser → R2)

When the user clicks Schedule or Post Now, the frontend requests a **presigned
R2 PUT URL** from the backend. The backend generates it using the R2 S3-compatible
API and returns it along with the final public-path key. The browser then PUTs
the file directly to R2. The backend never sees the bytes.

```
Frontend  →  POST /api/media/presign  { filename, content_type, post_id }
Backend   →  returns { upload_url, r2_key }  (no data transfer)
Frontend  →  PUT $upload_url  (bytes go browser → R2 directly)
Frontend  →  POST /api/posts  { text, r2_key, channel_ids, scheduled_at }
```

The R2 object is created in a **private bucket**. It is not publicly accessible.

### Posting Phase: Per-Platform Flows

#### Instagram and Threads (image or video)

*Requires a publicly accessible URL at container-creation time.*

At T-5 minutes before scheduled time:
1. Backend generates a **presigned R2 GET URL** (TTL: 60 minutes)
2. Backend calls `POST /{ig_user_id}/media` with the presigned URL as `image_url`
   or `video_url`; Instagram/Threads fetch the media directly from R2
3. Backend polls until container status is `FINISHED`
4. Backend calls `/{ig_user_id}/media_publish`
5. R2 presigned URL expires naturally; R2 object remains private (or is deleted)

Media bytes never pass through the backend. R2 egress is free.

#### Facebook

*Accepts either a URL or a binary upload.*

At scheduled time:
1. Backend generates a presigned R2 GET URL (TTL: 30 minutes)
2. Backend calls `POST /{page_id}/photos?url=$presigned_url&published=false`
   for each image, collecting photo IDs
3. Backend calls `POST /{page_id}/feed` with `attached_media` referencing the
   photo IDs

Media bytes never pass through the backend. R2 egress is free.

#### Bluesky

*Requires binary blob upload; does not accept URLs.*

At scheduled time:
1. Backend fetches the file from private R2 (R2 → backend, R2 egress free)
2. Backend calls `com.atproto.repo.uploadBlob` with the raw bytes
3. Backend calls `app.bsky.feed.post` with the blob reference

Media bytes pass through the backend once. Fly.io egress: $0.02/GB.
Bluesky images are capped at ~1MB each, 4 per post: maximum ~4MB, negligible.

#### LinkedIn

*Requires binary upload via a registered upload URL.*

At scheduled time:
1. Backend calls `POST /v2/assets?action=registerUpload` → receives upload URL
2. Backend fetches file from private R2 (R2 egress free)
3. Backend PUTs raw bytes to the LinkedIn upload URL
4. Backend creates the UGC post referencing the asset URN

Media bytes pass through the backend once. Fly.io egress: $0.02/GB.
Manageable even for video.

#### Immediate Posts (browser open)

When the user posts immediately rather than scheduling, the browser can bypass
the backend entirely for some platforms:

| Platform | Immediate post: browser direct? |
|---|---|
| Bluesky | Yes — atproto client works in-browser, CORS supported |
| Facebook | Yes — Graph API supports CORS with a valid token |
| LinkedIn | Likely yes — upload PUT is to a signed URL (test CORS first) |
| Instagram | No — requires public URL; use presigned R2 flow same as scheduled |
| Threads | No (images) — same as Instagram |

For immediate browser-direct posts, the bytes go from OPFS directly to the
platform, bypassing both the backend and R2 entirely. The backend is notified
after the fact to record the post as published.

---

## Scheduler

The scheduler fires post jobs at the correct time. It must be reliable across
backend restarts and (eventually) multiple backend instances.

**Job store:** APScheduler with `SQLAlchemyJobStore` pointed at the Supabase
Postgres connection. Jobs are persisted in the database, not in memory. On
restart, the scheduler rehydrates from the job store and resumes pending jobs.

**Job timing:**
- Instagram / Threads with images or video: enqueue at T-5 minutes to allow
  container creation and platform processing time before the scheduled moment
- All other platforms: enqueue at T-0

**Job isolation:** Each `PostChannel` (a post × channel pair) gets its own
scheduler job. If one channel's post fails, others are unaffected. Per-channel
status is updated independently.

**Failure handling:**
- On platform API error: mark `PostChannel.status = 'failed'`, store
  `error_message`, notify user
- On transient error (network timeout, rate limit): retry up to 3 times with
  exponential backoff before marking failed
- On token expiry: attempt refresh once; if refresh fails, mark failed and
  prompt user to reconnect the channel

---

## Backend Responsibilities (Complete List)

The FastAPI backend is intentionally thin. Its full surface area:

1. **JWT verification** — middleware, runs on every request
2. **App-level OAuth exchange** — code → token for Meta, LinkedIn; handle +
   app password validation for Bluesky
3. **Vault read/write** — store and retrieve per-user platform credentials
4. **Presigned URL generation** — issue R2 PUT URLs (upload) and GET URLs
   (Instagram/Threads/Facebook posting); no data transfer
5. **Post metadata CRUD** — text, r2_key, channel_ids, scheduled_at
6. **Scheduler management** — add, update, cancel APScheduler jobs
7. **Platform API dispatch** (at post time):
   - Instagram/Threads: call container creation + publish with presigned URL
   - Facebook: call photos + feed with presigned URL
   - Bluesky: fetch from R2, upload blob, create post
   - LinkedIn: fetch from R2, register upload, PUT, create UGC post
8. **Post-publish webhook / callback** — record platform post IDs, update status
9. **Token refresh** — check and refresh expiring platform tokens before posting
10. **Media cleanup** — delete R2 objects after successful publish (optional,
    configurable per user)

The backend performs no image processing, transcoding, resizing, or streaming.
It never stores media on disk or in the database.

---

## Data Model Changes From Current Implementation

The current implementation uses SQLite with plaintext credentials in the
`channels` table. The target model:

```
auth.users (Supabase managed)
  └── profiles (user_id FK)
       └── channels (user_id FK)
            ├── platform
            ├── display_name
            ├── platform_user_id
            ├── vault_secret_id  ← replaces credentials JSON
            ├── token_expires_at
            └── is_connected

posts (user_id FK)
  ├── text
  ├── r2_key          ← replaces media_paths array
  ├── scheduled_at
  ├── status
  └── post_channels
       ├── channel_id
       ├── status
       ├── error_message
       ├── platform_post_id
       └── published_at

app_settings (user_id FK)  ← per-user settings, not app-level
  └── key / value
```

App-level credentials (Meta App ID, R2 keys, etc.) move entirely out of the
database into Fly.io environment variables.

---

## CLI Tools for Operations

Everything deployable and manageable from a terminal:

| Tool | Operations |
|---|---|
| `flyctl` | Deploy backend, set env vars (`flyctl secrets set`), scale machines, view logs |
| `supabase` | Run migrations, manage RLS policies, local dev stack, deploy Edge Functions |
| `wrangler` | Deploy Cloudflare Pages frontend, manage R2 buckets, set R2 CORS policy |
| `git push` | Triggers CI/CD for all three services if configured |

---

## Billing (Stripe)

We never handle card data. Stripe hosts the payment form on their own domain;
we are not in scope for PCI DSS card data requirements.

**Checkout flow:**

```
User clicks Upgrade
  → Frontend: POST /api/billing/checkout
  → Backend: creates Stripe Checkout Session via Stripe API → gets back a URL
  → Backend: returns URL to frontend
  → Frontend: redirects to checkout.stripe.com/...
  → User enters card details on Stripe's page (we never see these)
  → Stripe: redirects back to vibepost.com/welcome on success
```

**How we learn about payment events:**

Stripe sends a signed webhook (`POST /api/billing/webhook`) for every billing
event: subscription created, renewed, payment failed, cancelled, etc. The backend
verifies the webhook signature (using a Fly.io secret) and updates the user's
record accordingly. We react to events; we never poll Stripe.

**What we store in our DB:**

- `stripe_customer_id` — links our user to their Stripe record
- `subscription_status` — `active`, `trialing`, `past_due`, `canceled`
- Plan name / tier if we have multiple

Nothing else. No card numbers, expiry dates, or billing addresses.

**Paywall enforcement:**

Every gated API endpoint checks `subscription_status IN ('active', 'trialing')`.
When a payment lapses, Stripe fires a webhook, we flip the status, and the gates
close automatically without any manual intervention.

---

## GDPR

GDPR applies if any users are in the EU. For a public SaaS, assume yes.

**Personal data we hold:**

- Email address (Supabase Auth)
- Social media account names and platform user IDs (`channels` table)
- Post text and media (Postgres + R2)
- IP addresses and access logs (held by Fly.io / Cloudflare — we are responsible
  for them as a data controller even though we don't see them directly)

**Lawful basis:** performance of a contract. We hold data to provide the service
the user signed up for. This covers the core processing without needing explicit
consent for each operation.

**Required in practice:**

- **Privacy policy** — document what we collect, why, which third-party processors
  we use (Supabase, Stripe, Cloudflare, Fly.io, the social platforms), and
  retention periods. Non-negotiable.
- **Data Processing Agreements** — Supabase, Stripe, Cloudflare, and Fly.io all
  offer standard DPAs. Accept them (usually a checkbox in the account settings).
  They commit to handling our users' data under GDPR rules.
- **Right to erasure** — when a user deletes their account: cascade-delete all
  Postgres rows, purge R2 objects, delete all Vault secrets, initiate Stripe
  customer deletion. This must actually work in the code.
- **Data residency** — pick a Supabase region from the start. EU region simplifies
  compliance for EU users; migrating later is painful.

**What we probably don't need:**

- Cookie consent banner — only required for tracking/analytics cookies. If we
  don't run ad pixels or third-party analytics, we likely have no consent-requiring
  cookies.
- A Data Protection Officer — only mandatory for large-scale or sensitive
  processing.

---

## Open Questions (Unresolved)

- **Meta/LinkedIn credentials — resolved for beta, open for production:** during
  development and closed beta, each user creates their own Meta developer app and
  enters their own App ID and Secret in the vibepost settings screen. This avoids
  Meta app review entirely since each user is only ever accessing their own
  accounts. The existing settings UI already supports this flow. Switch to a single
  shared vibepost app (with proper Meta review) when opening to the public — review
  requires a working demo and can take several weeks, so start the submission
  process well before the public launch date.
- Should media be deleted from R2 after a successful post, or retained for the
  user's own archive? Configurable per user is the right answer but adds surface
  area.
- LinkedIn CORS behaviour for direct browser uploads needs a live test before
  committing to that path.
- Video for Instagram Reels uses a different, chunked resumable upload flow —
  needs a separate investigation before promising video support there.
- Social login (sign in with Google etc.) for vibepost app auth — lower priority
  but reduces friction significantly.
