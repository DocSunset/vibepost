# Plugin System / Programmable Workspace

## The Idea

vibepost is not just a social media scheduler. It is a programmable social media
workspace. The scheduler is the default configuration. Users — assisted by an
AI — can reshape it into whatever they actually want, while the app is running,
without a deploy, without code review, without filing a feature request.

A user opens a chat interface inside the app and says "I want a column that shows
all my scheduled posts for the next 48 hours grouped by platform." The AI writes
a component, it appears. They say "make the text smaller and add a countdown
timer." It updates. This is a new interaction paradigm for productivity tools.
Nobody has shipped it as a first-class feature inside a running SaaS.

---

## Architecture: Sandboxed Component Plugin System

The LLM does not have access to the app. It writes components that run inside a
sandbox, and those components communicate with the app only through a typed API.

### The sandbox

LLM-generated components run in a WebAssembly or iframe-based sandbox with a
strict Content Security Policy. The generated code cannot:
- Access the parent app's state, tokens, or DOM
- Make arbitrary network requests
- Read or write localStorage or OPFS outside its own namespace
- Import modules outside an approved list

Figma plugins work exactly this way. The model is proven.

### The typed plugin API

The sandbox exposes a fixed, versioned API surface that components can call:

```typescript
// Read
api.posts.list(filters)        // scheduled, published, draft
api.channels.list()            // connected accounts
api.profiles.list()

// Write
api.posts.create(draft)
api.posts.update(id, patch)
api.posts.cancel(id)

// UI
api.ui.toast(message)
api.ui.openComposer(prefill)

// Storage (sandboxed per plugin)
api.storage.get(key)
api.storage.set(key, value)
```

The LLM knows this API. Its task is to write a React component (or Svelte, or
vanilla JS — the sandbox can support multiple) that uses it. The component has
no knowledge of how the API is implemented, what database is behind it, or what
credentials the user holds. It cannot exfiltrate anything because there is
nothing to exfiltrate.

### Layout slots

The app has defined layout slots — regions where plugins can be mounted:
sidebar, main panel, header bar, compose drawer, calendar overlay, etc. The
LLM places the generated component into a slot. Multiple plugins can occupy the
same slot (tabbed or split). The default vibepost UI is itself just a set of
first-party plugins occupying the default slots — nothing architecturally
special about them.

### Persistence

A plugin is stored as:
- The generated source code (auditable, diffable)
- Metadata: name, description, slot, created_at, last_modified
- A preferences blob for user-configurable values

Stored per user in Postgres. When the app loads, it fetches the user's plugin
manifest, loads each plugin into the sandbox, and mounts them into their slots.

---

## The AI Interface

A persistent chat panel (collapsible) where the user talks to the AI. The AI:
- Has access to the plugin API schema
- Has access to the user's current plugin manifest (what components exist)
- Can create new components, modify existing ones, or remove them
- Can explain what a component does, suggest improvements, debug errors
- Cannot read the user's post content or credentials — only the schema

The AI is vibepost's primary interface for power users. The settings screen,
the preferences panel, the feature request backlog — all of these collapse into
a conversation.

---

## What This Changes About The Product

vibepost as a scheduler: one product, one set of opinions, one roadmap.

vibepost as a programmable workspace: a platform. The scheduler is the seed.
Users grow it into what they actually need. A journalist builds a breaking-news
queue. A brand manager builds an approval workflow. A solo creator builds a
content calendar that matches their personal system. None of these require a
feature request. None of them require a developer.

The competitive moat is not features. It is the capacity to become whatever
the user needs it to be.

---

## Open Questions

- What runtime for the sandbox? Iframe + postMessage is simpler and more mature;
  WASM (e.g. Extism) is more powerful and more portable.
- How do plugins get updated when the core API changes? Versioning strategy
  needed — plugins declare which API version they target.
- Should plugins be shareable between users? A marketplace of community plugins
  is a natural extension but adds moderation complexity.
- What model powers the AI interface? Claude via the Anthropic API is the obvious
  choice; the plugin API schema is a natural tool definition.
- Should the AI be able to modify the plugin API itself (i.e. request new backend
  capabilities)? Almost certainly not in v1 — that's a different kind of system.
