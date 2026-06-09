# Product and Business Model

## What vibepost is

A programmable social media workspace. The scheduler is the default
configuration. Users — with the help of an AI — reshape it into whatever they
actually need, while it's running, without a developer.

The competitive moat is not features. It is the capacity to become whatever
the user needs it to be.

---

## Tiers

The tiering falls out naturally from the architecture rather than being
artificially imposed. Each tier adds genuine capability, not just lifted
restrictions.

### Free — local-only

- PWA, runs entirely on the user's device
- Data lives in OPFS: posts, credentials, plugin manifests
- Posts directly to platforms from the browser
- AI assistant available with bring-your-own Anthropic API key
- No account required. No backend involvement. Nothing leaves the device
  except posts going to platforms and (optionally) AI requests going to Anthropic.
- Works offline for composition and scheduling; posting requires connectivity

**Privacy statement:** we collect nothing, because there's nothing to collect.

### Standard — backend sync

Adds:
- Multi-device synchronisation (mobile ↔ desktop ↔ web)
- Automated plugin and data backups
- Mediated AI channel: pooled costs, usage guardrails, personalisation over time
- Bring-your-own-key remains available for users who prefer it

### Pro — reliable execution

Adds:
- Server-side scheduling: posts go out even if the device is off or offline
- The backend is a fallback executor: device posts if awake, server posts if not
- Priority AI execution

---

## The AI Channel

### Mediated (Standard and Pro)

AI requests are routed through the vibepost backend. This enables:

- **Pooled costs** — usage is spread across all mediated users; no unexpected
  bills for individual users
- **Cost guardrails** — per-user limits prevent runaway spend
- **Safety guardrails** — requests that could generate harmful plugin code or
  exfiltrate data can be intercepted before reaching the model
- **Personalisation** — with consent, conversation history informs how the AI
  assists that specific user over time; the assistant learns how they work
- **Product improvement** — aggregate signal from conversations informs what
  the app should do better; specific users' conversations improve their own
  version of the app

**The honest framing:** users on the mediated tier know their conversations are
used this way. It is in the privacy policy. It is framed as a fair exchange —
pooled costs and a smarter assistant in exchange for signal. It is not a hidden
data harvest.

### Bring-your-own-key (all tiers)

Users supply their own Anthropic API key. Requests go browser-to-Anthropic
directly; vibepost never sees them. No conversation data is retained anywhere
on our infrastructure. This option is always available and never removed —
it signals that the mediated channel is a choice, not a lock-in.

---

## Tensions to stay honest about

- "We study your conversations to improve the app" and "privacy-first product"
  sit in friction. The resolution is consent, transparency, and the BYOK escape
  hatch — not pretending the tension doesn't exist.
- Server-side scheduling (Pro) requires storing credentials and post content
  on the backend, which reintroduces the privacy surface we designed the local
  architecture to avoid. Users who opt into Pro are explicitly trading some
  privacy for reliability. This should be stated plainly at upgrade time.
- Personalisation that improves a specific user's experience ("your assistant
  gets smarter about how you work") is a feature. Aggregate data collection
  for product improvement is a liability in perception even if benign in
  practice. Separate these in communication and in implementation.

---

## Plugin marketplace (future)

A natural extension of the plugin system: users share plugins with each other.
A community library of components — a Hacker News reader that feeds into the
composer, a weather widget that suggests posting times, a competitor monitoring
dashboard. Plugins are sandboxed so sharing is safe; the API surface is the
trust boundary.

Moderation is the hard part. Deferred until the plugin system is mature and
there is a user base generating plugins worth sharing.
