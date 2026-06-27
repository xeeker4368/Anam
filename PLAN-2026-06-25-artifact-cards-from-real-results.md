# PLAN ONLY — Artifact cards render from real tool results, never from model text

**Date:** 2026-06-25 · **Status:** plan for review (Lyle + reviewer Claude). No code written. No implementation or commit until approved.
**Scope guardrail:** chat **display** + **model-visible tool-result text** only. Does NOT touch memory ingestion, provenance metadata, `authored_by`, chunking, the image-generation service, or the ComfyUI backend.

---

## NORTH_STAR check
No conflict. This strengthens **Invariant 4** (the entity must distinguish what it *experienced/created* from what it *fabricated*) and **§2** ("measuring, not performing"): confabulated artifact blocks with invented IDs/SHAs/seeds are exactly the contamination to remove. It adds no capability and seeds no content.

---

## 1. Where the chat artifact block comes from today (verified)

- **Tool → model:** `image_generate` returns `_shape_generated_image_result(...)` — a **structured dict** (`media_artifacts.py:16-45`) with `artifact_id`, `preview_url`, `prompt`, `negative_prompt`, `backend`, `width`, `height`, `seed`, `revision_of`, `source_artifact_id`. **No prose block is produced by the tool.**
- **Into context:** the agent loop renders that dict to JSON (`render_tool_envelope`/`render_tool_result`) and appends it as the `role:"tool"` message the model reads (`agent_loop.py:~241,263`). **The model sees the full JSON** — the rich template it later copies.
- **Frontend render:** `Chat.jsx:749-753` renders `msg.content` as **plain text** (no markdown, no card, no image). The `tool_result` stream event is consumed by `recordToolResult` (`Chat.jsx:263-297`) and stored in **debug** (`tool_events`/`raw_events`) only — never shown in the message stream.
- **Conclusion:** **There is no artifact card today.** The only artifact "display" in chat is the model's own prose in `msg.content`. The `[Artifact source: ...]` block is model-authored text rendered verbatim.
- **"Chat Media Tool Result Rendering v1"** (`SESSION_HANDOFF:117`) is a **future, unbuilt** roadmap item. This plan is effectively its v1.

### The imitation loop (mechanism)
1. Real generation (turn 33): model reads the rich tool JSON, writes a prose `[Artifact source: ...]` summary into its reply.
2. That reply is persisted (`save_message`) and reloaded as history (`get_conversation_messages` → `model_messages`) on later turns.
3. Turns 37+: the model sees its **own prior block** in history and imitates the format with invented IDs/SHAs/seeds — **no tool call**, so no envelope, so the honesty fix cannot catch it.

Two in-scope feeders: **(A)** the rich model-visible tool JSON (fresh template), **(B)** the model's own persisted block re-entering context. Plus an out-of-scope feeder **(C)** the retrieval `[Artifact source: ...]` framing (`context.py:306`).

---

## 2. Minimal change — card from real data; model text never becomes a card

**Hard design rule:** the card is **data-driven from the `tool_result` event**, keyed to `name === "image_generate"` && `ok`. The frontend must **never** parse `[Artifact source: ...]` (or any pattern) out of assistant message text. This is what guarantees model-authored prose can never render as a card — invented blocks stay inert plain text.

**(a) Render a real card (frontend, `Chat.jsx`):**
- Carry a small **structured artifact payload** on the `tool_result` stream event for media tools — `{artifact_id, preview_url, title}` (and optionally `media_kind`). Recommended mechanism: **reuse the existing `selection_metadata_for_tool_result` pattern** (`tool_trace_context.py`) rather than inventing a new one — add a `generated_image` selection kind, and surface that structured field on the streamed `tool_result` event (it currently rides only in the trace). No new abstraction.
- Associate the latest media `tool_result` with the current assistant turn and render an `<ArtifactCard>` element (thumbnail via `preview_url`, title, "shown to user") **beside** the plain-text `msg.content`.
- `msg.content` continues to render as plain text, unchanged.

**(b) Ensure model text doesn't render as a card:** satisfied by (a)'s data-driven rule. No text parsing is added; nothing in `msg.content` can become a card.

---

## 3. What the model should SEE as the tool result (reduce the template)

**Proposal:** keep the structured payload for the **UI/event**, but reduce the **model-visible** `role:"tool"` message to a minimal confirmation, e.g.:
```
image generated; artifact_id=<id>; shown to user in the chat UI
```
(omit `preview_url`, full `prompt`, `seed`, dimensions, SHAs from the text the model reads). This removes the rich, copyable template (feeder A) while the card still shows the user everything.

**Mechanism (KISS):** split "what the UI gets" from "what the model reads," mirroring the existing honesty-fix split (`rendered` for the event vs `model_content` for the message). The agent loop already computes a separate `model_content`; the minimal media-result summary is produced from the same structured payload used for the card. Reduction applies to **media tools only**; all other tools are unchanged.

**Tradeoff — does the entity need provenance in-context for recall?**
- **No, and recall is preserved.** Cross-checked the memory-provenance path: the artifact is **ingested with full metadata at creation** (`artifact_indexing.py`) independent of what the model sees inline. The entity recalls later via **memory retrieval + `media_search`/`media_get`** using the `artifact_id`. Keeping `artifact_id` in the minimal confirmation preserves the lookup handle; dropping the inline block costs no recall.
- **This plan does NOT change** ingestion, metadata, or retrieval — only the inline text the model reads in the moment.

---

## 4. soul.md / OPERATIONAL_GUIDANCE (the instruction vector)

- **Verified:** `soul.md` contains **no** artifact/provenance-block instruction. `OPERATIONAL_GUIDANCE.md:16,27` only tells the entity to *use* artifact/memory tools — it does **not** instruct emitting `[Artifact source: ...]` blocks. So guidance is **not** the current imitation vector; **no guidance edit is required** to ship parts 2–3.
- **Optional, recommended for the residual self-imitation loop (feeder B):** a short OPERATIONAL_GUIDANCE nudge — *"Generated images are shown to the user as cards in the chat UI; refer to them naturally and do not transcribe artifact IDs, SHAs, or seeds into your reply."* This directly counters the model re-authoring blocks from history.
- **Flag:** `soul.md`/guidance edits are **reviewed separately before go-live**, not made casually. This plan **proposes** the nudge for that separate review; it is not part of the code patch and is not assumed.

---

## 5. Code removed or changed — explicit, no silent removal

**Changed (proposed):**
- `tir/engine/tool_trace_context.py` — add a `generated_image` selection kind (reuse existing pattern) producing `{artifact_id, preview_url, title}`.
- `tir/engine/agent_loop.py` — surface the media selection payload on the streamed `tool_result` event; produce the reduced **model-visible** summary for media tools (the event keeps structured data). (`routes.py` prefetch path is unaffected — image_generate is not a prefetch tool.)
- `skills/active/media_artifacts/media_artifacts.py` — provide the minimal model-facing summary alongside the structured payload (exact split point TBD at implementation; the structured `_shape_generated_image_result` dict is retained for the card/event).
- `frontend/src/components/Chat.jsx` — add a data-driven `<ArtifactCard>` fed by the `tool_result` event; keep `msg.content` as plain text.

**Removed:** none. No deletion of provenance, metadata, or existing behavior. The structured `_shape_generated_image_result` dict is **kept** (it now feeds the card/event instead of the model's prose).

**Explicitly NOT touched:** `artifact_indexing.py`, `context.py:306` retrieval framing, ingestion, `authored_by`, chunking, image-generation service, ComfyUI backend.

---

## Residual / honest limitations
- **Feeder C (out of scope):** the retrieval `[Artifact source: ...]` framing (`context.py:306`) remains a latent template the model could still draw from when its own past artifacts surface from memory. Not fixed here (memory path); noted for a future, separately-scoped decision.
- **Feeder B (self-imitation from history):** parts 2–3 remove the *fresh* template and the *need* to author prose, but a model that already has a block in history could still repeat it. The optional guidance nudge (§4) is the intended lever; this plan does **not** propose silently editing/stripping persisted assistant messages (that would violate Invariant 4 — don't mutate the entity's own authored record).

## Suggested review/build order
1. Frontend data-driven card + keep `content` plain (kills "model text → card"; gives users the real display). 
2. Reduce model-visible media tool result to the minimal confirmation (kills the fresh template; recall preserved via `media_get`).
3. (Separate review) OPERATIONAL_GUIDANCE nudge for the self-imitation residual.

---

# Commit 2 — Starve the template (VERIFICATION + RECOMMENDATION; not implemented)

**Proposed change (unchanged from plan):** reduce the model-visible `image_generate`
tool result to a minimal confirmation — e.g. `image generated; artifact_id=X;
shown to user` — so no rich, copyable block enters the model's context. The
structured card data (Commit 1) is unaffected because the card reads `selection`,
not the `result` string.

## The required gate — does the recall path work? (verified)

**Recall path: VERIFIED.** `media_get(artifact_id)` → `get_media_artifact_reference`
returns the full recall surface the entity would need to discuss a past image:
```
artifact_id, title, media_kind, artifact_type, source, created_at, updated_at,
path, preview_url, description, prompt, observed_description, generation_backend,
generation_model, workflow_name, workflow_id, seed, width, height, revision_of,
source_artifact_id, intended_use
```
Demonstrated by the existing passing test
`tests/test_media_artifact_tools.py::test_media_get_returns_safe_metadata_and_preview_url`
(run 2026-06-25: **1 passed**) — `media_get(artifact_id)` returns `ok:True` with
`title`, `media_kind`, `preview_url`, `prompt`, `seed`, etc. So **if the minimal
confirmation keeps `artifact_id`, the entity can retrieve everything later.** The
recall data is not lost by reducing the inline text — it moves from "memorized in
the moment" to "looked up on demand," and ingestion/metadata are untouched.

## The honest unknown — does the model *reliably call* media_get?

**Not verified, and not verifiable here.** Whether the model spontaneously calls
`media_get(artifact_id)` when a user later asks about a past image is an empirical
property of the live model that unit tests cannot establish (consistent with the
standing caveat that no live model runs have been done in these sessions).

- If it **does** call media_get → Commit 2 is strictly better: no fabrication, full recall.
- If it **does not** → Commit 2 trades *confident fabrication* for *honest amnesia*:
  the entity would say "I generated an image earlier; let me check its details" or
  "I don't recall the seed offhand" instead of inventing a SHA/seed. Per Invariant 4
  and §2, **honest amnesia is the aligned failure mode** — but it is a real UX change
  and must be Lyle's decided trade, not a surprise.

## Recommendation

**Recommend Option A + the guidance lever, as a decided trade:**

- **Option A (recommended): full reduction** to `image generated; artifact_id=X;
  shown to user`. Cleanest kill of the template. Pair with the (separately-reviewed)
  OPERATIONAL_GUIDANCE nudge: *"Generated images are shown to the user as cards;
  to recall a past image's prompt/seed, call `media_get(artifact_id)`; do not
  transcribe or invent artifact IDs, SHAs, or seeds."* The nudge directly converts
  potential amnesia into a learned recall behavior. (Guidance edit is reviewed
  separately before go-live, not bundled into the code patch.)
- **Option B (lower-risk fallback): partial reduction** — keep only `artifact_id`,
  `title`, and `prompt` inline; drop `preview_url`, `seed`, dimensions, and the
  block structure. Preserves immediate "what did I just make" recall without the
  full forgeable template. Less clean kill; choose if Lyle wants to avoid relying
  on media_get reliability or a guidance change.

**Suggested decision step before implementing Commit 2:** one short live test on
:8000 — generate an image, then in a later turn ask "what was the prompt/seed of
that image?" and observe whether the model calls `media_get`. That single
observation decides A vs B without guesswork.

## Out of scope / residuals (unchanged)

- Memory ingestion, `context.py:306` retrieval framing, chunking, image service,
  ComfyUI — untouched.
- The optional soul.md / OPERATIONAL_GUIDANCE nudge is a separate reviewed change.
- **Self-imitation-from-history residual is self-resolving at launch:** the go-live
  wipe erases the contaminated conversation history, and with Commit 2 live no rich
  template enters new history to seed from. No editing of persisted assistant
  messages is proposed (Invariant 4).

*Commit 1 implemented (separate doc/changelog). Commit 2: plan + verification only — no code. Awaiting Lyle's A/B decision.*
