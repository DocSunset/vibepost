# VibePost Infrastructure Pricing Research
**Researched:** June 9, 2026  
**Scope:** Multi-tenant SaaS social media scheduler — FastAPI backend + React frontend, containerized with Docker. Needs: managed Postgres, user auth, encrypted secrets, media file storage (images + video), auto-scaling compute.

---

## Table of Contents

1. [Supabase](#1-supabase) — DB + Auth + Storage + Vault
2. [Fly.io](#2-flyio) — Backend Compute
3. [Cloudflare Pages + R2](#3-cloudflare-pages--r2) — Frontend + Storage Alternative
4. [Railway](#4-railway) — All-in-One Alternative
5. [Render](#5-render) — All-in-One Alternative
6. [AWS](#6-aws) — RDS + S3 + App Runner/Fargate + Cognito
7. [Neon](#7-neon) — Serverless Postgres Alternative
8. [Summary Comparison Tables](#8-summary-comparison-tables)
9. [Recommendation](#9-recommendation)

---

## 1. Supabase

**Pricing page:** https://supabase.com/pricing  
**Storage docs:** https://supabase.com/docs/guides/storage/uploads/file-limits  
**Bandwidth docs:** https://supabase.com/docs/guides/storage/serving/bandwidth

Supabase bundles Postgres, Auth, File Storage, Realtime, Edge Functions, and Vault (encrypted secrets) into a single platform. It's the most feature-complete option for a Firebase-style backend.

### Plans

| Feature | Free | Pro ($25/mo) | Team ($599/mo) |
|---|---|---|---|
| Database storage | 500 MB | 8 GB | 8 GB |
| Database RAM/CPU | Shared CPU, 500 MB RAM | Micro (1 vCPU, 1 GB RAM shared) via $10 compute credit | Same as Pro base |
| Auth MAUs | 50,000 | 100,000 | 100,000 |
| File storage | 1 GB | 100 GB | 100 GB |
| Egress (uncached) | 5 GB | 250 GB | 250 GB |
| Egress (cached) | 5 GB | 250 GB | 250 GB |
| Backups | None | 7-day | 14-day PITR |
| Inactivity pause | After 1 week | None | None |
| Projects | 2 | Unlimited | Unlimited |
| Vault (secrets) | Included | Included | Included |
| Compliance | None | None | SOC2, ISO 27001 |

### Pay-as-You-Go Overage Rates (Pro/Team)

| Resource | Rate |
|---|---|
| Database storage | $0.125/GB/month |
| File storage | $0.0213/GB/month |
| Egress (uncached) | $0.09/GB |
| Egress (cached/CDN) | $0.03/GB |
| Auth MAUs beyond 100K | $0.00325/MAU/month |
| Image transformations | $5 per 1,000 origin images (first 100 free) |
| Realtime messages (beyond 5M/mo) | $2.50 per 1M messages |

### Compute Costs

The Pro plan's $10 compute credit covers one Micro instance (shared CPU, 1 GB RAM). If you need dedicated compute, you pay separately:

| Compute Size | Monthly Cost (after $10 credit) |
|---|---|
| Micro (shared) | $0 (covered by credit) |
| Small (2 GB RAM, 2 dedicated vCPU) | ~$20/month |
| Medium (4 GB RAM) | ~$40/month |
| Large (8 GB RAM) | ~$76/month |
| XL (16 GB RAM) | ~$152/month |

A practical production setup with Small compute runs approximately **$45–55/month** base before storage overages.

### Storage and Media — Key Details

- **Free tier max file size:** 50 MB — a hard blocker for video uploads
- **Pro/Team max file size:** 500 GB per file — supports large video uploads
- **Standard uploads:** Reliable up to ~5 GB; TUS resumable uploads recommended for video
- **Storage pricing:** $0.0213/GB/month — very cheap; 1 TB of stored video would be ~$21/month
- **Egress is the real cost:** Streaming or downloading video hits $0.09/GB uncached. A user who watches their 100 MB scheduled post preview 10 times = $0.09 of egress. At scale, this compounds fast.
- **CDN caching mitigates egress:** If you serve media via Supabase's CDN, cached hits cost only $0.03/GB — 3x cheaper. Configure your buckets to be public and leverage caching aggressively.
- **250 GB egress included on Pro:** Enough headroom for a small app, but a media-heavy app with even 100 active users uploading and previewing video will burn through this.

### Vault

Supabase Vault is a first-party Postgres extension using pgsodium for authenticated encryption. It's **included in all tiers at no extra cost** — not a separate product line. Secrets are stored encrypted in the database with transparent decryption via Postgres functions. For a social media scheduler that needs to store OAuth tokens and API keys for social platforms, this is a significant feature advantage.

### Cliff Edges

- **Inactivity pause on Free:** Projects pause after 1 week of inactivity, which breaks scheduled jobs. Free tier is not usable for a scheduler in production.
- **Compute credit gotcha:** The $10 compute credit on Pro sounds generous but only covers a Micro shared instance. Any production workload warrants a Small ($20) or Medium ($40) dedicated compute, raising the effective base cost.
- **Spend caps:** Pro plans have a configurable spend cap (default on). You must manually disable it to allow unlimited pay-as-you-grow. This means surprise billing stops, but also means your app can stop working if it exceeds the cap unexpectedly.
- **Team plan jump:** From Pro (~$45-55/month) to Team ($599/month) is a massive cliff for compliance features. No mid-tier option exists.

---

## 2. Fly.io

**Pricing page:** https://fly.io/pricing  
**Detailed pricing docs:** https://fly.io/docs/about/pricing/

Fly.io is a compute-only platform — you deploy Docker containers as "Machines" (microVMs). No database or auth services included. It pairs naturally with Supabase for the DB/auth layer.

### Compute Pricing

All pricing is pay-per-second for running machines. No free tier for new accounts (free trial: 2 VM hours or 7 days, whichever is shorter).

**Shared CPU machines** (shared vCPU, suitable for most web workloads):

| Machine | RAM | Hourly | Monthly (730 hrs) |
|---|---|---|---|
| shared-cpu-1x | 256 MB | $0.0028/hr | ~$2.02 |
| shared-cpu-1x | 512 MB | ~$0.0042/hr | ~$3.07 |
| shared-cpu-2x | 1 GB | $0.0092/hr | ~$6.64 |
| shared-cpu-4x | 4 GB | $0.0329/hr | ~$23.66 |

**Performance CPU machines** (dedicated vCPU, for consistent throughput):

| Machine | RAM | Hourly | Monthly |
|---|---|---|---|
| performance-1x | 2 GB | $0.0447/hr | ~$32.19 |
| performance-2x | 8 GB | $0.1183/hr | ~$85.17 |
| performance-4x | 16 GB | $0.2366/hr | ~$170.33 |

Additional RAM: ~$5/GB/month.  
**Machine reservation discount:** 40% off when you commit to a block of compute time.

**Stopped machines (scaled-to-zero):**  
$0.15/GB of rootfs per 30 days — negligible for most apps.

### Persistent Storage Volumes

- **Volume storage:** $0.15/GB/month of provisioned capacity
- **Volume snapshots:** $0.08/GB/month (first 10 GB free each month)
- Note: Fly volumes are not object storage — they're block devices attached to machines. For media file storage, use an external object store (Supabase Storage, Cloudflare R2, or S3).

### Network / Egress

- **North America & Europe:** $0.02/GB outbound
- **Asia Pacific, Oceania, South America:** $0.04/GB
- **Africa & India:** $0.12/GB
- **Dedicated IPv4:** $2/month (required if you need a static IP)
- **Static egress IP:** ~$3.60/month (needed if social platform APIs whitelist by IP)

### Auto-Scaling

Fly.io supports scaling to zero and back — machines stop when idle and start on incoming traffic. Cold start time is 1–3 seconds for pre-built images. For a scheduler that runs background jobs, you'd likely want at least one machine always running, but secondary workers can be ephemeral.

### Realistic Cost Scenarios

| Scenario | Monthly Estimate |
|---|---|
| 1x shared-cpu-2x (1 GB) always-on | ~$6.64 |
| 1x performance-1x (2 GB) always-on | ~$32.19 |
| 2x shared-cpu-2x for HA | ~$13.28 |
| 2x performance-1x for HA | ~$64.38 |
| 100 GB North America egress | ~$2.00 |

### Cliff Edges

- No free tier — even minimal usage requires a credit card and payment from day one.
- Egress costs are low (2 cents/GB) but add up if the FastAPI backend streams video from object storage to social APIs. A backend that downloads a 100 MB video from Supabase Storage and uploads it to Twitter/Instagram generates ~$0.002 per video in Fly egress — not alarming, but budget for it.
- Volumes are provisioned capacity, not used capacity — you pay for what you allocate, not what you write. Avoid over-provisioning.

---

## 3. Cloudflare Pages + R2

**Pages limits:** https://developers.cloudflare.com/pages/platform/limits/  
**R2 pricing:** https://developers.cloudflare.com/r2/pricing/  
**Plans:** https://www.cloudflare.com/plans/developer-platform/

### Cloudflare Pages (Frontend Hosting)

Pages is purpose-built for static sites and JAMstack frontends. The React build of VibePost would deploy here.

| Feature | Free | Pro ($5/mo) | Business ($50/mo) |
|---|---|---|---|
| Bandwidth | **Unlimited** | **Unlimited** | **Unlimited** |
| Builds/month | 500 | 5,000 | 20,000 |
| Concurrent builds | 1 | 5 | 20 |
| Max file size per asset | 25 MB | 25 MB | 25 MB |
| Max files per site | 20,000 | 100,000 | 100,000 |
| Workers (Pages Functions) requests/day | 100,000 | — | — |

**Verdict for VibePost frontend:** Free tier is sufficient for any scale. Bandwidth is truly unlimited. The only limit that matters is the 500 builds/month on free — roughly 16 deploys/day, which is plenty. Pages is the clear winner for React frontend hosting.

### Cloudflare R2 (Object Storage)

R2 is Cloudflare's S3-compatible object storage with one defining feature: **zero egress fees**.

| Metric | Free Tier | Paid |
|---|---|---|
| Storage | 10 GB-month | $0.015/GB-month (Standard) |
| Storage (Infrequent Access) | — | $0.010/GB-month |
| Class A ops (writes, PUTs) | 1M requests/month | $4.50/million requests |
| Class B ops (reads, GETs) | 10M requests/month | $0.36/million requests |
| Egress | **Free (unlimited)** | **Free (unlimited)** |
| IA data retrieval | — | $0.01/GB |

**Critical point for VibePost:** If the FastAPI backend needs to stream video to social platform APIs, using R2 as the storage backend means that egress is free — regardless of volume. This is a **fundamental advantage** over S3 (which charges $0.09/GB egress) and Supabase Storage (which charges $0.09/GB uncached egress after the 250 GB included).

**R2 vs S3 storage cost comparison (100 GB/month):**
- R2: $1.50 storage + $0 egress = **$1.50/month**
- S3: $2.30 storage + $9.00 egress (100 GB) = **$11.30/month**
- Supabase Storage (Pro, 100 GB overages): $2.13 storage + egress from included pool

**Infrequent Access tier:** Better for content that isn't accessed frequently (archived posts, old media). 30-day minimum storage duration — if you delete before 30 days, you're billed for the full 30.

**R2 as Supabase Storage alternative:** R2 exposes an S3-compatible API. You can use R2 directly from the FastAPI backend, bypassing Supabase Storage entirely. Use R2 for media files; keep Supabase for DB/auth/vault.

---

## 4. Railway

**Pricing page:** https://railway.com/pricing  
**Docs:** https://docs.railway.com/pricing/plans

Railway is a container platform that also offers managed Postgres (via templates) and Redis. It bills per second on actual resource consumption, making it predictably cheap at low usage and linearly scalable.

### Plans

| Plan | Monthly Base | Included Usage |
|---|---|---|
| Free trial | $5 one-time credit | No card required |
| Hobby | $5/month | $5 of resource usage |
| Pro | $20/month per seat | $20 of resource usage |
| Enterprise | Custom | Custom |

The included usage means: if your app uses $4 of compute in a month, you pay $5 (the plan minimum). If you use $25, you pay $5 plan fee + $5 overage = $25 total.

### Resource Rates

| Resource | Rate |
|---|---|
| CPU | $20/vCPU/month ($0.000463/vCPU/minute) |
| Memory (RAM) | $10/GB/month ($0.000231/GB/minute) |
| Volume storage | $0.15/GB/month |
| Network egress | $0.05/GB |
| Object storage | Per GB-month (egress free — Railway Object Storage) |

### Realistic Workload Costs

**Minimal backend (0.5 vCPU, 512 MB RAM, always-on):**
- CPU: 0.5 × $20 = $10/month
- RAM: 0.5 × $10 = $5/month
- Total compute: ~$15/month
- Plus Hobby plan fee: $5/month → **$20/month total**

**Mid-tier backend (1 vCPU, 1 GB RAM, always-on):**
- CPU: $20 + RAM: $10 = $30/month compute
- Plus Pro seat: $20 → effectively $50/month but $20 is covered by inclusion
- Actual additional cost: **~$30/month**

**Managed Postgres on Railway (via template, running as container):**
Railway doesn't offer a fully managed Postgres service with automated backups and PITR — it runs Postgres inside a container with a volume. Storage: $0.15/GB/month. You handle your own backups. This is a meaningful operational burden vs. Supabase or RDS.

### Network Egress

$0.05/GB — 2.5x higher than Fly.io's $0.02/GB for North America, but still very manageable. 100 GB of video throughput via the backend = $5/month.

### Cliff Edges

- **No managed Postgres:** Railway Postgres is self-managed in a container. No automated backups, no point-in-time recovery, no connection pooling out of the box. This is a significant gap for production.
- **No auth service, no file storage, no secrets vault:** Railway is compute-only plus DIY Postgres. You'd need to add Supabase or Auth0 for auth, and separate object storage for media.
- **Pro seat is per-person:** Teams pay $20/seat/month per developer, plus compute costs. A 3-person team paying $60/month in seat fees before any usage is a real cost.

---

## 5. Render

**Pricing page:** https://render.com/pricing  
**Bandwidth docs:** https://render.com/docs/outbound-bandwidth  
**Postgres docs:** https://render.com/docs/postgresql-refresh

Render offers managed web services, managed Postgres, Redis, and background workers. It's a more polished PaaS than Railway with better database management, but a steeper pricing structure.

### Web Services (Compute)

| Tier | Monthly | RAM | CPU |
|---|---|---|---|
| Free | $0 | 512 MB | 0.1 vCPU (shared) |
| Starter | $7 | 512 MB | 0.5 vCPU |
| Standard | $25 | 2 GB | 1 vCPU |
| Pro | $85 | 4 GB | 2 vCPU |
| Pro Plus | $175 | 8 GB | 4 vCPU |

- **Free tier:** Spins down after 15 minutes of inactivity with a 30–60 second cold start. Completely unusable for a scheduler (background jobs would fail on idle).
- **Auto-scaling:** Available on paid tiers. You pay per additional instance.

### PostgreSQL Database

| Tier | Monthly | RAM | CPU | Included Storage |
|---|---|---|---|---|
| Free | $0 | 256 MB | Shared | 1 GB (30-day expiry!) |
| Basic-256MB | ~$7 | 256 MB | Shared | 1 GB |
| Basic-1GB | ~$20 | 1 GB | Shared | 10 GB |
| Pro-1GB | ~$45 | 1 GB | 1 dedicated | 10 GB |
| Pro-4GB | ~$97 | 4 GB | 2 dedicated | 50 GB |

- **Storage overage:** $0.30/GB/month — significantly higher than Supabase ($0.125/GB) or S3/R2
- **Free Postgres:** Hard-deleted after 30 days with zero grace period. Do not use for anything real.
- **PITR:** Requires upgrading workspace to Pro plan ($19+/user/month), not just the DB tier

### Workspace Plans (in addition to service costs)

| Plan | Monthly/user | Included Bandwidth |
|---|---|---|
| Hobby | Free | 5 GB |
| Pro | $19/user | 25 GB |
| Scale | Custom | 1 TB |

### Bandwidth / Egress

- Overage: **$0.15/GB** beyond included amount
- Hobby (free workspace) includes only 5 GB — a single video download blows through this
- Pro workspace includes 25 GB — still very limited for media-heavy apps

### Cliff Edges

- **Storage overage at $0.30/GB** is 2.4x more expensive than Supabase's $0.125/GB and 14x more than Supabase Storage's $0.0213/GB. Render is not a file storage service.
- **Bandwidth is dangerously limited:** 5 GB free, 25 GB Pro. For a social media scheduler serving video previews, this is a cliff edge. A single user previewing a 50 MB video 10 times = 500 MB egress.
- **No dedicated object storage:** Render has no equivalent to S3, R2, or Supabase Storage. You'd need an external service.
- **No auth service, no secrets vault:** Same gap as Railway.
- **Workspace fee stacks with compute:** A team of 3 with Standard web service + Basic Postgres = ($19×3) + $25 + $20 = **$102/month before any overages**.

---

## 6. AWS

**RDS pricing:** https://aws.amazon.com/rds/postgresql/pricing/  
**S3 pricing:** https://aws.amazon.com/s3/pricing/  
**Fargate pricing:** https://aws.amazon.com/fargate/pricing/  
**App Runner pricing:** https://aws.amazon.com/apprunner/pricing/  
**Cognito pricing:** https://aws.amazon.com/cognito/pricing/

AWS is the most mature and flexible option, but requires the most operational overhead and has the highest egress costs of any option surveyed.

### RDS PostgreSQL

**Instance pricing (us-east-1, Single-AZ, on-demand):**

| Instance | vCPU | RAM | Hourly | Monthly |
|---|---|---|---|---|
| db.t4g.micro | 2 | 1 GB | $0.016/hr | ~$11.52 |
| db.t4g.small | 2 | 2 GB | ~$0.032/hr | ~$23.04 |
| db.t4g.medium | 2 | 4 GB | ~$0.065/hr | ~$46.80 |

- **gp3 storage:** $0.115/GB/month (includes 3,000 IOPS and 125 MB/s free baseline)
- **Backup storage:** Free up to 100% of database size; $0.095/GB/month beyond
- **Multi-AZ:** ~2x the instance cost (adds a synchronous standby)
- **Free tier (new accounts only):** 750 hours/month of db.t4g.micro for 12 months + 20 GB gp2 storage. Note: AWS changed the free tier in July 2025 — new accounts after that date get $200 credits instead.

**CPU credits for T4g (burstable):** If you exceed baseline CPU for sustained periods, you pay $0.075/vCPU-hour for credits in Unlimited mode. At low to moderate load, T4g instances are cheap. A scheduler doing burst processing could rack up CPU credit charges.

### S3 (Object Storage for Media)

**Storage (Standard, us-east-1):**
- First 50 TB/month: $0.023/GB-month
- Next 450 TB: $0.022/GB-month

**Requests:**
- PUT/POST: $0.005/1,000 requests
- GET: $0.0004/1,000 requests

**Egress (Data Transfer Out to Internet):**
- First 10 TB/month: **$0.09/GB**
- Next 40 TB: $0.085/GB

**Free tier:** No longer a permanent free tier for S3. New accounts get $200 in credits, valid 6 months.

**S3 Transfer Acceleration:** Additional cost on top of egress for faster uploads — not necessary for most use cases.

**The egress problem:** At $0.09/GB, streaming 1 TB of video through an App Runner backend to social APIs costs **$92/month in S3 egress alone**. This is the primary reason to consider Cloudflare R2 as the media store.

### Compute Options

#### AWS App Runner (Simplest — containers to production, no infra management)

| Resource | Rate (us-east-1) |
|---|---|
| Active (processing requests) vCPU | $0.064/vCPU-hour |
| Active memory | $0.007/GB-hour |
| Provisioned (idle) memory | $0.007/GB-hour |

**Example — 1 vCPU, 2 GB RAM, always-on:**
- Active compute (assuming 25% CPU utilization average): $0.064/hr × 720 hrs = $46.08/month CPU + $0.007 × 2 GB × 720 hrs = $10.08/month RAM
- **Total: ~$56/month** (comparable to performance-1x on Fly.io)

App Runner supports autoscaling and scale-to-zero (minimum 1 provisioned instance by default). Good for variable traffic, poor for background scheduler jobs unless you keep a minimum instance.

#### AWS Fargate (More control — ECS task-based)

| Resource | Rate (us-east-1, Linux/x86) |
|---|---|
| vCPU | $0.0405/vCPU-hour |
| Memory | $0.00444/GB-hour |

**Example — 0.5 vCPU, 1 GB RAM, always-on:**
- $0.0405 × 0.5 × 720 = $14.58 CPU + $0.00444 × 1 × 720 = $3.20 RAM = **~$17.78/month**

Fargate requires more operational knowledge (ECS clusters, task definitions, load balancers) but is cheaper than App Runner and more granular. Requires ALB (~$18/month base) or API Gateway for routing.

### Amazon Cognito (Auth)

| Feature | Free | Cost Beyond |
|---|---|---|
| MAUs (Lite tier) | 10,000 | $0.0055/MAU up to 100K, then $0.0046 |
| MAUs (Essentials tier) | 10,000 | $0.015/MAU flat |
| SAML/OIDC federation | 50 MAUs | $0.015/MAU |

**Cognito vs Supabase Auth at 50K MAUs:**
- Cognito (Lite): 10K free, then 40K × $0.0055 = **$220/month**
- Supabase Pro: 100K free → **$0/month** for 50K MAUs

Cognito's free tier is far stingier than Supabase's. For a social media app with rapid user growth, Cognito auth costs can become significant quickly.

### AWS Full-Stack Cost Example (50K users, moderate media)

| Component | Monthly |
|---|---|
| RDS db.t4g.small (Single-AZ) | $23 |
| gp3 storage 50 GB | $5.75 |
| S3 storage 500 GB | $11.50 |
| S3 egress 200 GB | $18.00 |
| App Runner (1 vCPU, 2 GB) | $56 |
| Cognito 50K MAUs | $220 |
| **Total** | **~$334/month** |

The Cognito auth cost dominates at scale. AWS is not competitive for auth-heavy SaaS at mid-range MAU counts.

---

## 7. Neon

**Pricing page:** https://neon.com/pricing  
**Plans docs:** https://neon.com/docs/introduction/plans

Neon is a serverless, auto-scaling Postgres-as-a-service with branching. It's Postgres only — no auth, no storage, no secrets. Use it to replace the Supabase DB layer if you want cheaper serverless Postgres, while keeping other services elsewhere.

### Plans

| Feature | Free | Launch | Scale |
|---|---|---|---|
| Compute | 100 CU-hours/month | $0.106/CU-hour | $0.222/CU-hour |
| Storage | 0.5 GB/project | $0.35/GB-month | $0.35/GB-month |
| Branches | 10/project | 10/project (+$1.50/extra) | 25/project (+$1.50/extra) |
| Scale-to-zero timeout | 5 minutes | 5 minutes | Configurable (1 min to always-on) |
| Max compute | 2 CU (8 GB RAM) | 16 CU (64 GB RAM) | 56 CU (224 GB RAM) |
| Egress | 5 GB | Beyond 500 GB: $0.10/GB | Beyond 500 GB: $0.10/GB |
| Auth MAUs | 60,000 (Neon Auth) | Up to 1M (free) | Up to 1M (free) |
| Private networking | No | No | $0.01/GB (AWS PrivateLink) |
| Compliance | None | None | SOC2, ISO, GDPR, HIPAA |
| PITR | 7 days | 7 days | 30 days |

**1 CU = 0.25 vCPU + ~1 GB RAM.** A typical web app backend database runs on 0.25–1 CU most of the time.

### Cost Calculation Examples

**Launch tier, 1 CU always-on (smallest realistic production DB):**
- 730 hours/month × $0.106/CU-hour = **$77.38/month**

**Launch tier, 0.25 CU with scale-to-zero (active ~8 hours/day):**
- 240 hours × $0.106/CU-hour = **$25.44/month**

**Free tier headroom:**
- 100 CU-hours ÷ 0.25 CU = 400 hours of compute at minimum size. Enough for 24/7 at the smallest setting — but a scheduler running jobs constantly would exhaust this.

**Storage:** $0.35/GB/month is significantly higher than Supabase's $0.125/GB or RDS's $0.115/GB. A 50 GB database on Neon costs $17.50/month in storage vs $6.25 on Supabase.

### Neon Auth

Neon recently launched Neon Auth (powered by Stack Auth). It's included free up to:
- Free plan: 60,000 MAUs
- Paid plans: up to 1 million MAUs at no extra charge

This is a strong feature for paid plan users — effectively matching Supabase Auth's 100K MAU inclusion, then going much further (1M vs $0.00325/MAU overage at Supabase).

### Serverless Behavior — Production Concerns

Scale-to-zero means the database pauses when idle. Cold starts take 1–5 seconds. For a scheduler that needs to fire jobs on a cron schedule, the first connection after idle will experience this cold start. On the Scale plan, you can disable scale-to-zero entirely (always-on), but you pay full hours.

### Neon vs Supabase DB Only

| Metric | Neon Launch | Supabase Pro |
|---|---|---|
| Storage/GB | $0.35 | $0.125 |
| Compute | Pay-per-use (CU-hours) | Fixed Micro, or add-on |
| Auth | Free up to 1M MAU | Included up to 100K MAU |
| Connection pooling | Built-in (pgBouncer) | Via Supabase Pooler |
| Branch databases | Yes (dev/staging) | No |
| Vault/Secrets | No | Yes (pgsodium) |
| File storage | No | Yes (100 GB on Pro) |

**When to pick Neon over Supabase DB:**  
You want branch-based development workflows and are okay assembling auth (Neon Auth or Auth0/Clerk), secrets management, and file storage separately.

**When to stick with Supabase:**  
You want a single integrated platform with Vault, Storage, and Auth under one roof. Supabase's storage cost ($0.125/GB DB, $0.0213/GB file) is substantially cheaper than Neon's $0.35/GB.

---

## 8. Summary Comparison Tables

### Storage Cost Comparison (per GB/month)

| Service | File/Object Storage | Database Storage | Egress | Notes |
|---|---|---|---|---|
| Cloudflare R2 | $0.015 | — | **$0.00 (free)** | Best egress story |
| Supabase Storage | $0.0213 | $0.125 (DB) | $0.09 uncached / $0.03 cached | 250 GB egress included on Pro |
| AWS S3 | $0.023 | — | $0.09 | High egress is the pain point |
| Railway | $0.15 (volume) | via volume | $0.05 | No dedicated object storage |
| Render | — | $0.30 (DB storage) | $0.15 | No object storage; very expensive DB storage |
| Neon | — | $0.35 | $0.10 (beyond 500 GB) | Expensive DB storage |

### Auth Cost at Scale (MAUs)

| Service | Free MAUs | 10K MAUs | 50K MAUs | 100K MAUs | 500K MAUs |
|---|---|---|---|---|---|
| Supabase Auth | 50,000 | $0 | $0 | $0 | ~$1,300 |
| Neon Auth | 60,000 (free) / 1M (paid) | $0 | $0 | $0 | $0 |
| AWS Cognito | 10,000 | $0 | ~$220 | ~$495 | ~$2,254 |
| Auth0 (not surveyed) | 25,000 | $0 | ~$240 | ~$720 | contact |

### Compute Cost Comparison (1 vCPU / 2 GB RAM equivalent, always-on)

| Platform | Monthly | Notes |
|---|---|---|
| Fly.io shared-cpu-2x (2×) | ~$13–26 | Shared vCPU, not dedicated |
| Fly.io performance-1x | ~$32 | Dedicated 1 vCPU |
| Railway (1 vCPU / 2 GB) | ~$30 | Billed per second |
| Render Standard | $25 | 1 vCPU / 2 GB |
| AWS App Runner (1 vCPU / 2 GB) | ~$56 | Includes autoscaling |
| AWS Fargate (0.5 vCPU / 1 GB) | ~$18 | Add ALB ~$18/mo |

### Platform Feature Coverage

| Platform | Postgres | Auth | File Storage | Secrets/Vault | Compute | Frontend |
|---|---|---|---|---|---|---|
| Supabase | Yes | Yes | Yes | Yes (Vault) | Limited | No |
| Fly.io | No | No | No | No | Yes | No |
| Cloudflare | No | No | R2 | Workers Secrets | Workers | Pages |
| Railway | DIY container | No | Object Storage | No | Yes | No |
| Render | Managed | No | No | No | Yes | Static sites |
| AWS | RDS | Cognito | S3 | Secrets Manager | Fargate/App Runner | CloudFront |
| Neon | Yes (only) | Neon Auth | No | No | No | No |

---

## 9. Recommendation

### Context

VibePost is a **media-heavy scheduler** — users upload images and videos, which the backend then needs to retrieve and push to social platform APIs. This shapes the analysis significantly:

1. **Stored media volume grows indefinitely** unless purged after posting
2. **Backend must read each file and upload it outbound** to social APIs — this is double-egress: once from storage to backend, once from backend to the internet
3. **Video files can be 500 MB–2 GB each** — file size limits and per-file costs matter
4. **Scheduled jobs must run reliably 24/7** — services with inactivity pauses or scale-to-zero cold starts are unreliable for this use case

### Primary Recommendation: Supabase + Fly.io + Cloudflare R2 + Cloudflare Pages

This is the originally proposed stack with one important modification: **replace Supabase Storage with Cloudflare R2 for media files**.

**Why this combination:**

**Cloudflare R2 for media storage** is the single most impactful infrastructure decision for a media-heavy app. The $0.00 egress cost means your backend can read video files from R2 and upload them to social APIs without any storage egress charge. Compare:
- Supabase Storage: $0.09/GB egress (uncached) — 1 TB of video uploads over a month = $92 in egress from storage
- Cloudflare R2: $0.00 egress — same 1 TB = $0

The R2 S3-compatible API means you can use `boto3` or `httpx` directly from the FastAPI backend. There's no lock-in.

**Supabase for DB + Auth + Vault** gives you:
- Postgres (managed, with connection pooling, PITR on Pro)
- Auth with 100K free MAUs — generous for early growth
- Vault for encrypted OAuth tokens — the social media API credentials stored per user need encryption at rest; Supabase Vault handles this without an extra service
- $25/month base (Pro) with enough headroom for early-stage

**Fly.io for compute** gives you:
- Pay-per-second pricing with no idle waste
- Easy Docker deployment (VibePost is already containerized)
- Low North America egress ($0.02/GB) for backend → social API traffic
- Auto-scaling machines for handling burst posting windows

**Cloudflare Pages for frontend** — unlimited bandwidth, free tier sufficient, best performance for a static React build.

### Cost Projections (Proposed Stack)

**Early stage (< 1,000 users, < 100 GB media):**

| Component | Monthly |
|---|---|
| Supabase Pro (with Micro compute) | $25 |
| Cloudflare R2 (100 GB storage) | $1.50 |
| Fly.io shared-cpu-2x (1 GB, always-on) | ~$6.64 |
| Fly.io egress (50 GB backend outbound) | ~$1.00 |
| Cloudflare Pages (frontend) | $0 |
| **Total** | **~$34/month** |

**Growth stage (5,000 users, 1 TB media, 500 GB/mo throughput):**

| Component | Monthly |
|---|---|
| Supabase Pro + Small compute add-on | $45 |
| Cloudflare R2 (1 TB storage) | $15.00 |
| Fly.io performance-1x × 2 (HA) | ~$64 |
| Fly.io egress (200 GB backend outbound) | ~$4.00 |
| Cloudflare Pages (frontend) | $0 |
| **Total** | **~$128/month** |

**Scale stage (50K users, 10 TB media, 5 TB/mo throughput):**

| Component | Monthly |
|---|---|
| Supabase Pro + Large compute | $111 |
| Cloudflare R2 (10 TB storage) | $150 |
| Fly.io performance-2x × 3 | ~$255 |
| Fly.io egress (1 TB backend outbound) | ~$20 |
| Cloudflare Pages | $0 |
| **Total** | **~$536/month** |

If you had used S3 instead of R2 at scale stage: S3 storage $230 + $450 egress = $680 just for storage, vs R2's $150 total. **R2 saves ~$530/month at 10 TB media + 5 TB egress.**

### Alternative: Supabase + Railway

If you want to consolidate on fewer vendors, Railway can replace Fly.io. The egress rate is $0.05/GB vs Fly.io's $0.02/GB — negligible at small scale. Railway's per-second billing and Docker deployment are both excellent. The gap: Railway has no native autoscaling group or machine-level isolation, and its managed Postgres is a DIY container (keep Supabase for the DB). This works but isn't meaningfully cheaper or simpler than Fly.io.

### Alternative: Full Supabase (Storage included)

If you want zero additional vendors and can live with storage egress costs, keep Supabase Storage and budget for the $0.09/GB egress. The 250 GB included egress on Pro covers a small user base. This is the lowest operational complexity option — one dashboard, one bill, one API. At small scale (under 1 TB/month of media egress), the cost difference between Supabase Storage and R2 is under $80/month. Add R2 when the egress bill starts to hurt.

### Avoid for This Use Case

- **AWS full stack:** Cognito's auth pricing ($220+/month at 50K MAUs) makes it uncompetitive vs Supabase's free 100K MAUs. S3 egress at $0.09/GB is expensive at media scale. The operational overhead of RDS + ECS/Fargate + ALB + S3 is substantial for a small team.
- **Render for compute:** Extremely limited bandwidth (5 GB free, 25 GB Pro) before $0.15/GB overages. A scheduler uploading media cannot function here without large bandwidth costs.
- **Neon as the only DB:** Neon's storage at $0.35/GB is 2.8x more expensive than Supabase's $0.125/GB. Neon Auth is generous, but the lack of Vault means you'd need a separate secrets service (AWS Secrets Manager: $0.40/secret/month + $0.05/10K API calls).

### Decision Summary

| Decision | Recommendation | Rationale |
|---|---|---|
| Database | **Supabase Postgres** | Managed, cheap, PITR, connection pooler included |
| Auth | **Supabase Auth** | 100K free MAUs, social OAuth built-in |
| Secrets | **Supabase Vault** | Included, encrypted, no extra service needed |
| Media storage | **Cloudflare R2** | Zero egress cost — critical for video-heavy scheduler |
| Backend compute | **Fly.io** | Low cost, Docker-native, low egress fees |
| Frontend | **Cloudflare Pages** | Unlimited bandwidth, free, CDN-native |
| DB alternative | **Neon (Scale)** | If you need branch databases for dev/staging workflows |

---

## Pricing URLs Consulted

- Supabase pricing: https://supabase.com/pricing
- Supabase Storage limits: https://supabase.com/docs/guides/storage/uploads/file-limits
- Supabase bandwidth: https://supabase.com/docs/guides/storage/serving/bandwidth
- Supabase Storage pricing: https://supabase.com/docs/guides/storage/pricing
- Fly.io pricing overview: https://fly.io/pricing
- Fly.io pricing docs: https://fly.io/docs/about/pricing/
- Cloudflare Pages limits: https://developers.cloudflare.com/pages/platform/limits/
- Cloudflare R2 pricing: https://developers.cloudflare.com/r2/pricing/
- Cloudflare developer plans: https://www.cloudflare.com/plans/developer-platform/
- Railway pricing: https://railway.com/pricing
- Railway pricing docs: https://docs.railway.com/pricing/plans
- Render pricing: https://render.com/pricing
- Render Postgres docs: https://render.com/docs/postgresql-refresh
- Render bandwidth docs: https://render.com/docs/outbound-bandwidth
- AWS RDS PostgreSQL pricing: https://aws.amazon.com/rds/postgresql/pricing/
- AWS S3 pricing: https://aws.amazon.com/s3/pricing/
- AWS Fargate pricing: https://aws.amazon.com/fargate/pricing/
- AWS App Runner pricing: https://aws.amazon.com/apprunner/pricing/
- AWS Cognito pricing: https://aws.amazon.com/cognito/pricing/
- Neon pricing: https://neon.com/pricing
- Neon plans docs: https://neon.com/docs/introduction/plans
