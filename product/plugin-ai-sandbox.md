# AI Agent in the Plugin Sandbox

## The Idea

Rather than the AI living outside the sandbox and writing code that runs inside
it, the AI lives inside the sandbox too. The sandboxed iframe is the agent's
environment — JavaScript is its bash, the DOM is its filesystem, the postMessage
API is its syscall interface. It doesn't generate a component and hand it over.
It lives in the environment, runs code, sees the results, and iterates. A genuine
REPL loop.

This maps directly onto how Claude computer use works — the agent has tools to
observe its environment and tools to act on it. Here the "computer" is a
sandboxed web environment with a controlled postMessage API instead of a full
desktop. The agent loop is identical; only the environment changes.

---

## Why This Is More Elegant Than the Alternative

**Better development loop.** The agent can write a component, render it, inspect
the result, notice something is wrong, fix it — all within one conversation turn.
It doesn't have to imagine what the rendered output will look like. It can observe
it directly via DOM inspection.

**Cleaner security model.** The boundary is simply: what does the postMessage API
expose? That is the complete and auditable list of what the AI can touch. Whether
the agent is writing code or calling tools directly, it is exactly as powerful as
the API and no more. No exceptions, no special cases.

**Model-agnostic.** The agent loop is the same regardless of whether it's Claude,
a local model, or something else — because the interface is just tool calls into
the postMessage API. Swapping models doesn't change the architecture.

---

## The Agent's Observation Tools

The agent doesn't need a screenshot to observe its environment — it's already
inside the iframe.

**DOM inspection** is the primary tool. `document.querySelector`,
`getBoundingClientRect`, `getComputedStyle` — the agent can read the exact
position, dimensions, and computed appearance of every element it rendered. This
is strictly more information than a screenshot.

**Canvas capture** via `html2canvas` is available for visual reasoning when the
agent needs to think about appearance rather than structure. `html2canvas` walks
the DOM, reads computed styles, and repaints to a canvas element. The result can
be encoded as base64 and passed to a vision model. Not pixel-perfect, but good
enough for layout reasoning. This runs entirely inside the sandbox — no parent
involvement, no special permissions.

**Why the parent can't take a better screenshot:**

The native `drawImage(iframeElement)` path would produce a compositor-accurate
render with none of `html2canvas`'s approximation errors. But it is blocked by
the browser's canvas taint rules: a canvas becomes tainted (unreadable) when you
draw cross-origin content onto it, and the browser determines origin from the
iframe's content URL, not from the sandbox attribute.

Crucially, the sandbox attribute's opaque origin (which provides the actual
security isolation) and the URL origin (which the canvas API checks) are
independent axes. An `<iframe sandbox>` without `allow-same-origin` runs in an
opaque origin regardless of its URL — but the canvas API still sees the URL
origin when deciding whether to taint. Granting `allow-same-origin` to fix this
would collapse the security boundary in ways that aren't acceptable: the iframe
could then access the parent's storage and DOM.

So `html2canvas` from inside the sandbox is the practical ceiling for visual
observation. DOM inspection covers everything else.

---

## Agent and Plugin Sandbox Relationship

The agent's iframe and the user's installed plugin iframes are distinct:

- **Agent sandbox** — the agent's working memory and scratchpad. It writes code,
  runs it, inspects results, iterates. Ephemeral.
- **Plugin sandboxes** — installed components that persist across sessions,
  mounted into layout slots, running continuously.

When the agent is satisfied with something it has built, it packages the code and
installs it as a plugin into a separate sandbox. The agent plays in its own yard;
finished work goes next door. The agent can inspect installed plugins (via the
postMessage API, not direct DOM access across sandbox boundaries) but cannot
modify their runtime state directly — it can only issue an update through the
plugin installation mechanism.

---

## The postMessage API as Syscall Interface

The postMessage API is the complete interface between the sandbox and the rest of
the system. For the agent this means:

**Read tools:**
- List posts (scheduled, published, draft)
- List channels and profiles
- Get plugin manifest (what's installed, what slots are occupied)
- Get current UI state (which slot is focused, what the user is looking at)

**Write tools:**
- Create / update / cancel posts
- Install / update / remove a plugin
- Mount a component into a layout slot
- Send a notification to the user

**Observation tools:**
- Request a DOM snapshot of a specific installed plugin's iframe
  (the parent can serialise the DOM tree and send it in; it cannot send pixel data
  for the reasons above, but the tree is enough for structural reasoning)

The agent cannot reach outside this list. It cannot read credentials, cannot make
arbitrary network requests, cannot access other users' data. The postMessage API
is the trust boundary and it is enforced by the browser.

---

## Open Questions

- What is the agent's persistent memory across sessions? Conversation history
  in OPFS is straightforward; a structured "what I know about this user's
  preferences" store is more interesting and harder.
- Should the agent be able to request new postMessage API capabilities — i.e.,
  ask vibepost to expose something it currently doesn't? In v1, no. Eventually,
  this is how the plugin API itself evolves: user demand expressed through agent
  requests surfaces what the API needs to expose next.
- Can two users share an agent session? (Pair programming for plugin authoring.)
  Interesting multi-player angle, probably out of scope for a long time.
- Local model vs API model for the agent: a local model running in the browser
  via WebAssembly would make the free tier genuinely serverless for AI too —
  no API key, no backend, no cost. This is not hypothetical:

  - **wllama** — a well-maintained WASM build of llama.cpp with a JavaScript API,
    runs inference in a Web Worker so it doesn't block the UI
  - **transformers.js** — Hugging Face's library for ONNX-format models in the
    browser, broader model support, actively maintained, WebGPU support
  - **llama.cpp's own WASM target** — exists in the main repo, less polished
    as a library

  The practical constraint is model size. 7B Q4 is ~4GB — too large for most
  browser contexts. But 1B–3B models at aggressive quantisation are 500MB–1GB,
  and models in that range have improved dramatically: Phi-4 Mini, Gemma 3 1B,
  Llama 3.2 1B are all plausible for constrained tasks like "write a React
  component given an API schema." WebGPU (now broadly available) makes inference
  interactive on most laptops and phones for models this size.

  Not something to build around today. Absolutely something to keep the
  architecture open to — the trajectory is clear and fast.
