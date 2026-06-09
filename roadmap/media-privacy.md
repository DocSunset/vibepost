# Media Privacy: No Public Exposure Until Posting

## Requirement

A user should be able to cancel a scheduled post right up to the wire without
their media ever having been publicly accessible. Media should not be exposed to
the public internet until the moment it is needed to complete the post.

---

## The Problem With Naive Public URLs

The obvious approach — store media in R2 with a public URL and hand that URL to
Instagram/Threads when scheduling — exposes the content from the moment of
upload, potentially days before the post goes live. If the user cancels, the
content has already been public indefinitely at a stable URL.

---

## Solution: Private Bucket + Short-TTL Presigned URLs

Store all media in a **private R2 bucket** for its entire lifetime. Nothing is
publicly accessible by default.

At post time (a few minutes before the scheduled moment), the backend:

1. Generates a **presigned GET URL** for the R2 object with a short TTL
   (30–60 minutes is sufficient — long enough for Instagram's processing pipeline,
   short enough that a cancelled post's URL is useless within the hour)
2. Passes that presigned URL to the Instagram / Threads API as the image/video URL
3. Instagram fetches the media directly from R2 using the presigned URL
4. The URL expires automatically; no cleanup needed

R2 supports presigned URLs via its S3-compatible API. Instagram and Threads
accept any HTTPS URL that returns the media on a GET request — presigned URLs
with query string parameters work fine.

---

## Per-Platform Breakdown

| Platform | Needs public URL? | Approach |
|---|---|---|
| Instagram | Yes (API requirement) | Presigned R2 URL, generated ~2–5 min before post time |
| Threads (image) | Yes | Same as Instagram |
| Threads (text) | No | No media involved |
| Facebook | Yes (URL param) | Presigned R2 URL passed as `?url=` parameter; Facebook fetches directly from R2 |
| Bluesky | No | Backend fetches from private R2, uploads blob directly |
| LinkedIn | No | Backend fetches from private R2, uploads via presigned PUT flow |

For Facebook, Bluesky, and LinkedIn the media bytes flow through the backend
(private R2 → backend → platform API) and are never exposed to a public URL at
all.

---

## Cancellation Window

- **Instagram / Threads with images:** the posting sequence (create container,
  wait for platform processing, publish) takes roughly 1–3 minutes. The
  practical cancel deadline is ~3–5 minutes before scheduled time — after that,
  the sequence is in flight.
- **All other platforms:** cancellation can be accepted right up to the moment
  the backend fires the API call, since there is no pre-processing step.

The scheduler should enforce a soft lock at T-5 minutes for Instagram/Threads
posts with media, and T-0 for all others.

---

## Media Lifecycle

```
Draft        →  OPFS only (never leaves the browser)
Scheduled    →  Private R2 bucket (inaccessible to public)
Posting (T-5min) →  Presigned URL generated (short TTL, not guessable)
Published    →  Post is live on the platform; R2 copy can be retained or deleted
Cancelled    →  R2 object deleted; presigned URL (if any was generated) expires
```

Optionally: delete the R2 object after a successful post to avoid paying storage
for content that is already live on the platform and no longer needed.

---

## Implementation Notes

- R2 presigned URLs are generated with `generate_presigned_url('get_object', ...)`
  via the boto3-compatible R2 API. TTL is set in seconds at generation time.
- The scheduler job for Instagram/Threads should be enqueued at T-5 minutes, not
  T-0, to allow headroom for platform processing.
- A separate cleanup job (or post-publish hook) should delete the R2 object and
  mark the post as fully complete.
- If a user cancels after the presigned URL has been generated but before
  Instagram has fetched it: Instagram will not have the image yet (the container
  creation call hasn't been made), so no exposure has occurred. The URL expires
  harmlessly.
