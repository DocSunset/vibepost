# Client-Side Architecture / Thin Backend

## Core Question

How much of the app can move to the browser, and what does that mean for
infrastructure costs?

---

## Media Storage: Origin Private File System

The browser's Origin Private File System (OPFS) is persistent, sandboxed per
origin, and quota is tied to available disk space (typically many GB on desktop).
It is fully supported in Chrome, Firefox, and Safari as of 2025.

Draft media (images and video) should never touch the backend at all. Store
everything in OPFS while composing. Only move media off-device at the moment a
post is actually published or scheduled — and even then, not through the backend
(see presigned uploads below).

Benefits:
- Zero backend storage cost for drafts, abandoned posts, and anything the user
  never publishes
- No upload latency during composition; preview is instant
- Works offline

---

## Direct Browser → Social API Calls

Some platforms can be called directly from the browser without routing through
the backend:

| Platform | Direct from browser | Notes |
|---|---|---|
| Bluesky | ✅ Yes | atproto API has CORS headers; blob upload works from browser |
| Facebook | ⚠️ Likely | Graph API generally supports CORS with a valid token |
| LinkedIn | ⚠️ Uncertain | Upload uses presigned PUT URLs; CORS behaviour is inconsistent — needs testing |
| Instagram | ❌ No | API requires a **publicly accessible URL** for all media; local files and blob URLs cannot satisfy this |
| Threads | ❌ No (images) | Same constraint as Instagram; text-only Threads posts may work |

For the platforms that support it, an immediate post can be fired entirely from
the browser: no backend round-trip, no bandwidth cost, no latency added by the
server.

---

## OAuth: Backend Still Required

The `client_secret` for Meta and LinkedIn cannot live in the browser — it would
be visible to anyone. The authorization code → access token exchange must happen
server-side.

After the exchange, the resulting access token *can* be handed back to the
browser and stored in OPFS or an encrypted IndexedDB entry. For a per-user app
this is acceptable: each user holds only their own tokens.

So the backend is involved in OAuth once at connect time, then steps out of the
posting flow entirely for platforms where direct browser calls work.

---

## Scheduled Posts: The Hard Blocker for Going Fully Client-Side

There is no reliable way to fire an arbitrary future task from a browser if the
tab or browser is closed. The relevant APIs:

- **Service Worker Background Sync** — retries failed requests when connectivity
  returns; not for scheduling future tasks
- **Periodic Background Sync** — minimum interval ~12 hours, heavily throttled
  by browsers, not suitable for precise scheduling
- **Push API** — a push message *can* wake a service worker, but requires a push
  server, which just moves the scheduling problem to that server

Scheduled posting requires a persistent server process. This is a firm constraint
and is not going away.

---

## The Right Split

Rather than "client-side or backend," the split should follow what each side is
actually good at:

### Browser handles:
- All composition and preview (already the case)
- Media storage during drafting (OPFS — new)
- Immediate posts to Bluesky and Facebook (direct API call — new)
- Media upload to object storage via presigned URL at publish/schedule time (new)

### Backend handles:
- OAuth token exchange (client_secret never leaves the server)
- Generating presigned upload URLs (S3/R2) — a sub-second call with no data transfer
- Storing post metadata and the resulting public media URL (not the bytes)
- Scheduling: firing posts at the requested time using the stored public URL
- Instagram and Threads image posts: calls the platform API with the public URL
  that was uploaded directly from the browser

### Object storage (R2/S3) handles:
- Permanent storage of published media
- Serving media to Instagram/Threads at post time via public URL
- CDN delivery if needed

---

## Presigned Upload Flow (Key Pattern)

This is how media gets from the browser to Instagram/Threads without passing
through the backend:

```
1. Browser selects a file from OPFS (or disk)
2. Browser requests a presigned PUT URL from the backend
   POST /api/media/presign  →  { upload_url, public_url, key }
   (backend generates this with S3/R2 SDK, returns it instantly, touches no bytes)
3. Browser PUTs the file directly to R2/S3 using upload_url
   (backend is not in this data path at all)
4. Browser sends the post payload to the backend with public_url
   POST /api/posts  →  { text, media_url: public_url, channel_ids, scheduled_at }
5. Backend stores the post record; at publish time, passes public_url to
   Instagram/Threads API
```

Backend bandwidth for a 50MB video upload: ~1KB (the presign request/response).
Without this pattern: 50MB in + 50MB out through the server.

---

## Infrastructure Cost Impact

| Concern | Without this pattern | With this pattern |
|---|---|---|
| Backend bandwidth | Full media size in + out | ~0 (only metadata) |
| Backend storage | Full media stored in DB/volume | ~0 (only URLs stored) |
| Object storage | N/A | R2: $0.015/GB/mo, **zero egress fees** |
| Scheduled post media | Must be re-fetched or cached | Public URL ready at schedule time |

Cloudflare R2 is specifically attractive here because it has no egress charges —
media served to Instagram/Threads from R2 costs nothing beyond storage. S3 would
charge per-GB for every post that includes an image or video.

---

## Revised Backend Surface Area

After this architecture, the backend is essentially:

1. OAuth token exchange (one call per platform connection)
2. Presigned URL generation (one call per upload, no data)
3. Post metadata storage (text, URLs, schedule time, channel refs)
4. Scheduler (APScheduler or equivalent, fires platform API calls at the right time)
5. Platform API calls for Instagram/Threads (passes the R2 public URL)

Everything else moves to the browser or to R2. The backend becomes stateless
with respect to media, which also makes horizontal scaling straightforward —
no shared filesystem needed.

---

## Open Questions

- For Bluesky and Facebook direct-from-browser posting: do we still store the
  media in R2 for record-keeping, or just OPFS? (Probably R2 for published posts,
  OPFS only for drafts.)
- Should the browser or the backend generate the R2 key / path structure?
  (Backend is safer — prevents path traversal and enforces per-user namespacing.)
- LinkedIn CORS behaviour needs a live test before committing to the direct-call
  path for that platform.
- Video for Instagram Reels uses a different upload flow (chunked, resumable);
  worth a separate investigation before promising video support there.
