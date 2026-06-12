# Post-Launch Backlog

Priorities and ideas captured during the pre-launch hardening work, in rough
priority order. (Decisions recorded here so they don't live only in chat.)

## 1. Vault / KMS migration — top priority after launch

Encryption at rest (June 2026) protects the database *file*: snapshots,
backups, and file-read bugs yield ciphertext. The remaining boundary is a
live-server compromise, where the attacker holds `CREDENTIALS_KEY` because
it's in the process environment. Closing that requires keys the app server
can use but not exfiltrate wholesale — Supabase Vault or an external KMS
with per-decryption audit logging, as designed in `security.md` and
`architecture.md`. **This is the top security priority once the beta is
live.** Fold media-file-at-rest encryption into the same work (media on the
volume is currently unencrypted; doing it properly wants chunked AEAD so a
100 MB video doesn't get buffered whole in RAM on a 512 MB machine).

## 2. Per-user storage accounting

It should be easy to see — and report to the user — how much data their
account holds: database rows (posts, settings, channels) and especially
media bytes on disk. Useful for transparency (pairs with the data-export
feature), for quota/billing later, and for noticing abuse. Probably:
a `manage usage` CLI command plus a small "your data" panel in account
settings. Cheap to compute: media files are tracked per user, post/channel
counts are one query each.

## 3. Post retention (decided: keep posts for now)

The privacy roadmap's target was delete-on-publish; the beta keeps published
posts until the user deletes them, and that's an accepted product decision —
post history is likely good UX. Revisit when the privacy policy is next
reviewed: if history becomes a feature, say so explicitly in the policy;
if not, implement delete-on-publish.
