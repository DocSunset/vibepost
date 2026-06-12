# Privacy Strategy

## Orientation

vibepost is a tool, not a data business. Users give us access to their content
and their social media accounts to accomplish a specific task. We collect only
what is necessary to do that job, hold it only as long as required, and treat
everything we touch as belonging to the user rather than to us.

This document records every category of personal data we handle, why we have it,
how long we keep it, and what we do to ensure both legal compliance and genuine
respect for user privacy.

> **Implementation status (closed beta, June 2026).** The inventory below
> describes the target architecture. The shipped beta differs in several
> ways, all reflected in the served privacy policy (`/privacy`):
> auth is passwordless — passkeys first, emailed sign-in links via Resend
> as fallback, no passwords exist — handled by us rather than Supabase, so
> emails and passkey public keys live in our own SQLite tables; Resend is
> an additional processor (email address + sign-in mail only); all data is
> on a Fly.io volume (SQLite + local uploads) instead of Supabase/R2; and
> posts are retained until the user deletes them rather than auto-deleted
> on publish. Emails, platform credentials, settings, and post text are
> encrypted at rest (AES-256-GCM, key held only as a Fly secret — see
> `security.md` status note). The deletion cascade, JSON export, and
> disconnect-deletes-credential behaviours ARE implemented and tested.

---

## What We Hold and Why

### Email address

**Why:** account recovery if the user loses all passkey-synced devices;
transactional notifications (post failures, token expiry, channel disconnected);
contact channel for security issues or service changes.

**What we don't use it for:** login credentials, marketing, analytics, or sale
to third parties.

**How long:** for the lifetime of the account. Deleted immediately and
permanently on account deletion.

**Where it lives:** Supabase Auth — not in our application tables. It is held by
our data processor (Supabase), never copied into our own schema.

---

### Passkey public key

**Why:** primary authentication. The user's private key never leaves their device;
we hold only the corresponding public key, which is cryptographically useless
without the private key.

**What it reveals:** nothing about the user as a person. It is a random
cryptographic value.

**How long:** for the lifetime of the account. Deleted on account deletion.

**Where it lives:** Supabase Auth.

---

### Platform credentials (OAuth tokens, Bluesky app passwords)

**Why:** to post on the user's behalf at the scheduled time.

**How long:** for as long as the channel is connected. Deleted immediately when
the user disconnects a channel or deletes their account.

**Where it lives:** Supabase Vault — encrypted at rest with a server-managed key.
Only a UUID reference is stored in our schema; a database dump reveals nothing
useful. See `architecture.md` — Secrets and Vault.

**Scope limitation:** we request only the permissions needed to create posts.
We do not request read access to followers, messages, analytics, or ad accounts.

---

### Scheduled post content (text and media)

**Why:** to execute the scheduled post at the right time.

**How long:**
- Text: stored in Postgres until the post is published or cancelled, then deleted.
  We do not retain post history after publication.
- Media: stored in a private R2 bucket until the post is published or cancelled,
  then deleted. It is never publicly accessible until a short-TTL presigned URL
  is generated at T-5 minutes before posting, and that URL expires within the hour.

**Where it lives:** Postgres (text) and Cloudflare R2 (media). Both isolated to
the user's account via RLS.

---

### Server logs

**Why:** operational necessity — diagnosing errors, detecting abuse.

**What they contain:** IP addresses, request paths, timestamps, HTTP status codes.
No post content is logged.

**How long:** 7-day rolling retention, then automatically purged. We do not
archive logs or ship them to a third-party analytics service.

**Where they live:** Fly.io infrastructure logs. We configure the shortest
available retention window.

---

## What We Deliberately Do Not Collect

- Name or display name (not required; the user's social handles identify them
  on each platform)
- Phone number
- Date of birth
- Location
- Device identifiers or fingerprints
- Browsing behaviour or analytics (no tracking pixels, no third-party analytics)
- Payment card data (Stripe holds this; we store only a Stripe customer ID and
  subscription status)
- Post history after publication

---

## Third-Party Processors

We share data with the following processors, each under a signed Data Processing
Agreement:

| Processor | What they handle | DPA |
|---|---|---|
| **Supabase** | Email, passkey, platform credentials (Vault), post text | Accept in Supabase dashboard |
| **Cloudflare** | Media files (R2), frontend traffic (Pages) | Accept in Cloudflare dashboard |
| **Fly.io** | Server logs, backend compute | Accept in Fly.io dashboard |
| **Stripe** | Billing, payment card data | Accept in Stripe dashboard |

We share post content with the social platforms the user explicitly chooses to
post to. That sharing is the entire purpose of the service.

We share nothing with data brokers, advertisers, or analytics companies.

---

## User Rights and How We Fulfil Them

### Right to access
A user can ask what we hold on them. The answer is: email address, passkey,
connected channel credentials, and any scheduled posts not yet published. We
provide this on request. Server logs containing their IP are accessible for up
to 7 days; after that they are gone.

### Right to erasure (right to be forgotten)
Account deletion triggers a cascade:
1. All Postgres rows with the user's `user_id` are deleted (profiles, channels,
   posts, post_channels, settings)
2. All R2 media objects in the user's namespace are purged
3. All Vault secrets for the user's channels are deleted
4. The Supabase Auth record (email, passkey) is deleted
5. The Stripe customer record is deleted via the Stripe API
6. Server logs containing the user's IP will age out within 7 days

This is a hard delete. We retain no archive, no anonymised record, nothing.
The deletion flow must be tested and verified before public launch.

### Right to portability
On request (or via a self-serve export), we provide the user's scheduled post
text and channel list in a standard format (JSON). Media can be downloaded from
R2 via presigned URL before deletion.

### Right to withdraw consent / disconnect
The user can disconnect any social channel at any time. Disconnecting a channel
immediately deletes the stored credential from Vault and cancels any posts
scheduled to that channel.

---

## Legal Basis (GDPR)

**Performance of a contract:** we process the user's data to provide the
scheduling service they signed up for. This is the lawful basis for holding
email, passkey, platform credentials, and post content.

**Legitimate interests:** server logs for security and abuse detection, retained
for 7 days. This is proportionate given the short retention window and the
operational necessity.

We do not rely on consent as a lawful basis for core processing, which means
we are not required to present cookie banners or consent flows for the service
itself. If we ever add optional analytics, consent would be required for that
specific processing.

---

## Data Residency

Supabase region should be chosen at project creation. Choose EU (Frankfurt or
Ireland) if the user base is expected to be primarily European, or US East if
primarily North American. This cannot be changed after the fact without a full
data migration. Cloudflare R2 and Pages are global by nature; Fly.io region
should match Supabase for latency.

---

## Obligations Checklist (Before Public Launch)

- [ ] Privacy policy published at a stable URL (linked from sign-up and footer)
- [ ] DPAs accepted with Supabase, Cloudflare, Fly.io, Stripe
- [ ] Account deletion flow implemented and tested end-to-end
- [ ] Post-deletion R2 cleanup verified (no orphaned objects)
- [ ] Vault secret deletion verified on channel disconnect and account delete
- [ ] Fly.io log retention configured to 7 days
- [ ] Supabase region confirmed before any user data is written
- [ ] Self-serve data export available or documented request process in place
- [ ] Transactional email (failure notifications, recovery) working before email
      is collected from users — do not collect email if you cannot use it for
      its stated purpose
