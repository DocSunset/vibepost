# Incident Runbook

What to do when you suspect a compromise. Read this calmly *before* an
incident so the steps are familiar; during one, work top to bottom. Most of
the value of a runbook is not having to think under pressure.

## 0. Triage — what kind of incident?

| Signal | Likely scope | Start at |
|---|---|---|
| Leaked database file / volume snapshot / old backup | Ciphertext only (encrypted at rest) — low, verify and rotate anyway | §2 |
| `CREDENTIALS_KEY` or Fly secrets exposed (leaked env, shoulder-surfed dashboard) | All stored credentials potentially readable **if** the holder also gets the DB | §2, then §3 |
| Code execution on the server / malicious deploy | Everything: keys + data + live traffic | §1, then everything |
| A user's account hijacked (their mailbox or device) | That user's channels and posts | §4 |
| Fly / GitHub / Resend / registrar account compromise | Everything, via redeploys or DNS | §1, then everything |

## 1. Contain

```sh
fly machine list
fly machine stop <machine-id>        # takes the app offline; data is safe
```

Scheduled posts stop publishing while stopped — acceptable; tell users later.
Then, if accounts above the server are in question: rotate the Fly account
password + 2FA, revoke Fly tokens (`fly tokens list` / `fly tokens revoke`),
rotate GitHub credentials, check repo for unexpected commits or Actions runs.

Preserve evidence before changing anything you might want to inspect:

```sh
fly volumes snapshots create <volume-id>
fly ssh sftp get /data/vibepost.db ./evidence-$(date +%F).db   # encrypt + store safely
fly logs > ./evidence-logs-$(date +%F).txt
```

## 2. Rotate the application keys

**SECRET_KEY** (session signing) — cheap, do it on any suspicion:

```sh
fly secrets set SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
```

Every user is signed out; no data is lost.

**CREDENTIALS_KEY** (encryption at rest) — rotate without losing data:

```sh
# 1. Keep the old key available for decryption, set a new primary:
fly secrets set CREDENTIALS_KEY_OLD="<current key>" CREDENTIALS_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
# 2. Re-encrypt every row with the new key:
fly ssh console -C "python -m app.manage reencrypt"
# 3. Drop the old key:
fly secrets unset CREDENTIALS_KEY_OLD
```

Update the password-manager copy of both keys.

## 3. Revoke platform credentials

If stored platform credentials may have been *readable in plaintext*
(live-server compromise, or key + database both exposed), assume every
connected channel is burned:

- **Meta / Instagram / Facebook / Threads**: each beta user owns their dev
  app. Tell them to: Meta dashboard → their app → reset the App Secret, and
  remove vibepost's authorization at facebook.com/settings → Business
  Integrations. Page tokens derived from the old secret die with it.
- **Bluesky**: users revoke the app password at bsky.app → Settings → App
  Passwords. This kills the stored credential instantly.
- **LinkedIn**: users revoke access at linkedin.com/mypreferences →
  Permitted services, and rotate their app's client secret.
- In vibepost, disconnecting a channel deletes the stored credential;
  reconnecting mints fresh ones.

**Resend**: rotate the API key in the Resend dashboard, `fly secrets set
RESEND_API_KEY=...`. If the attacker could send mail as you, warn users that
sign-in emails during the incident window may be forged.

## 4. Single-account hijack

1. `fly ssh console -C "python -m app.manage users"` — confirm the account.
2. Kill every session immediately:
   ```sh
   fly ssh console -C "python -m app.manage revoke-sessions them@example.com"
   ```
3. Once the user controls their mailbox again, they sign in fresh, remove
   unrecognized passkeys in Settings, and disconnect/reconnect channels.
4. If the account is actively posting abuse, also revoke its channels'
   platform credentials (§3) — that stops the bleeding on the platforms.

## 5. Notify

Be honest and fast. For anything that touched user data: email affected
users (what happened, what was exposed, what you did, what they should do —
usually "revoke and reconnect your channels"). The privacy policy commits
to this; GDPR expects breach notification without undue delay (72h to a
supervisory authority where applicable). Keep a written timeline as you go —
it is much easier than reconstructing one later.

## 6. Post-incident

- Snapshot the lessons into this file while they're fresh.
- Re-run `./scripts/supply-chain-audit.sh` and `fly deploy` from a clean
  checkout.
- Verify backups still restore: pull a snapshot, decrypt a row locally with
  the (new) key.
- Check `python -m app.manage users` and the invite list for anything you
  didn't create.
