# PLAN — Tool-call fabrication gate (generic) + forced tool-choice investigation. PLAN ONLY.

**Date:** 2026-08-13 · **Mode:** plan only. **No code, no commit.** For review before implementation.

## NORTH_STAR check
Catches fabricated *success* — the entity claiming it performed a tool action it never took — and stops that fabrication from being persisted into memory (where it becomes imitation-bait for the next turn). Serves Invariant 4 (distinguish what the entity *did* from what it *fabricated*) and the soul.md integrity floor. This is the success-side mirror of June's tool-*failure* honesty fix. Aligned.

---

## OPEN 1 — Does forced tool-choice work with gemma4:26b via this stack? **NO. Tested, not assumed.**

Environment: **Ollama 0.31.1**, `CHAT_MODEL = gemma4:26b`.

| test | endpoint | prompt | result |
|---|---|---|---|
| baseline (does tool-calling work at all?) | native `/api/chat` + tools | "What time is it? Use the tool." | **tool called** ✓ (`get_time`) |
| `tool_choice: "required"` | native `/api/chat` | "Just say hello." | **no tool call** (said "Hello") |
| `tool_choice: "required"` | OpenAI-compat `/v1/chat/completions` | "Just say hello." | **no tool call** |
| `tool_choice: {function: get_time}` (specific) | `/v1/chat/completions` | "Just say hello." | **no tool call** |
| consistency: `required`, non-tool prompt, ×4 each endpoint | both | "Just say hello." | **0/4 and 0/4 called a tool** |

**Conclusion:** `tool_choice` is silently ignored by gemma4:26b through Ollama 0.31.1 — on both endpoints, both `"required"` and specific-function forms, consistently (0/8). Tool-calling itself works, but the model still free-chooses whether to call. Forcing is not available. (Matches the project's prior finding that REQ tool-calling is unreliable — now confirmed for the *forcing* control specifically.)

## OPEN 2 — Is forced tool-choice usable here? **Moot (it doesn't work), and would be costly even if it did.**

Even if forcing worked, the app doesn't know in advance a turn should be a generation turn — the model decides. Forcing would require a **pre-classification step** (detect generation intent before the model's turn) with its own false-positive/negative cost, plus it only helps tools with a clean pre-classifiable intent. Given OPEN 1, this is not pursued. Recorded so it isn't revisited without new evidence (e.g. a model/Ollama upgrade that honors `tool_choice` — re-test then).

## OPEN 3 — Detect-and-respond gate (the primary mechanism). Recommendation below.

---

## The gate — design

### Ground truth available (no new plumbing)
- **`tool_call_count`** (routes.py:762,776,876) — the real count of tool dispatches this turn (prefetch + agent-loop). The two confirmed incidents had `tool_call_count: 0` and `tool_trace_present=False`.
- **`assistant_content`** — the model's text, known in the `terminated_reason == "complete"` branch (routes.py:916-918) **before** `save_message` (947) and **before** the buffered events are flushed. Because of the Option-2 drain (whole response buffered, nothing sent to the client yet), the gate can cleanly rewrite the outcome with no partial-stream problem. This is the ideal insertion point.

### Detection approach: **per-tool-category, generically extensible** (not one-pass fully generic)
A fully generic "tool-result-shaped prose" detector is impractical in one pass — each tool's result shape differs and false positives on legitimate prose are costly (they'd replace real answers with "I couldn't do that"). Instead: a small **registry of category detectors**, each a set of **high-precision markers** checked **only when `tool_call_count == 0`**. Ship **media/artifact first** (the proven, high-precision case); adding a future category (web_search, moltbook) is a data addition, not new control flow. This matches the DECIDED guidance ("per-tool-category first version acceptable; state which and why").

**Why media/artifact markers are high-precision** (grounded in the real incidents from `working.db`): the fabrications are verbatim artifact-provenance blocks that never occur in honest prose —
```
[Artifact source: anam_generated_00013_.png, ...]
Artifact ID: 9b8c7d6e-5f4a-3b2c-1d0e-9f8a7b6c5d4e
Stored path: generated/2026/08/12/9b8c7d6e-.../anam_generated_00013_.png
SHA256: a1b2c3d4... (truncated)
Size: 325412 bytes
```
Proposed markers (any one, case-insensitive, when `tool_call_count == 0`):
- `[Artifact source:` literal
- `Artifact ID:` followed by a UUID-ish token
- `Stored path:` and/or the path regex `generated/\d{4}/\d{2}/\d{2}/`
- `SHA256:` line
- `artifact_id=` inline
- the slim-era shape `Artifact: … (id: …)` (post-_event_text-slim imitations may morph toward this)

**Precision guards (must-haves, verified against real data):**
- **True negative — concept description:** the 2026-08-12 "Threshold" message (model describing an image *idea* in prose: "I want to visualize… I am imagining a stone doorway…") has **no** identity-block markers → correctly **not** flagged. The gate keys on fabricated *provenance/identity*, not on "talking about an image."
- **True negative — real generation:** a genuine `image_generate` turn has `tool_call_count > 0` → gate never fires, even though (post-Commit-2) the model may legitimately mention `artifact_id`.
- The markers (`SHA256:`, `Stored path: generated/…`, UUID after `Artifact ID:`) do not appear in normal conversation; combined with `tool_call_count == 0` this is essentially zero-false-positive for v1.

### Response on detection: **fail honestly (recommended) — do NOT retry by default**

| option | mechanism | pros | cons |
|---|---|---|---|
| (a) retry with explicit "you must call the tool now" | re-invoke `run_agent_loop` with an appended nudge | might succeed | **unreliable** — the model just free-chose not to call, and OPEN 1 proved even hard `tool_choice` forcing is ignored; a prompt nudge is the same lever that already failed. Costs a full extra generation (seconds–tens of s); needs a retry cap; a re-fabricated retry needs its own handling. |
| **(b) fail honestly (RECOMMENDED)** | replace fabricated content with an honest message; **do not persist the fabrication** | cheap, deterministic, honest; **and** prevents the fabricated block from entering memory — which is itself the imitation-bait for the next turn (double benefit, directly serves Invariant 4 and reinforces the in-flight backfill/relevance-floor work) | the user must re-ask to actually get the image |

**Recommend (b).** It is the "cheap insurance" the task frames this as, it is honest by construction, and not-persisting the fabrication is arguably more valuable than the correction itself (it stops the self-poisoning loop). Retry can be a **future, opt-in, bounded** escalation, but should not be v1 given the tested unreliability of getting the model to call on demand.

Honest message (wording for sign-off), e.g.:
> "I wasn't able to actually generate that image — no image was created, and the details above were not real. Want me to try again?"

The gate also **flips persistence to the honest message** (persist the correction, not the fabrication) and **rewrites the buffered token events** to the honest content before flush (clean because nothing has streamed yet).

### Where it fires vs. the tool-honesty precedent
This reuses the June precedent conceptually: `frame_failed_tool_message` catches a *hidden failure* (tool returned `ok:false`, model would narrate success) at the loop's tool-result step. This gate catches *fabricated success* (no tool ran, model narrates one) at turn completion — a layer the frame-failure fix cannot reach because there is no tool result to inspect. Same integrity principle, different point in the flow.

---

## Diff scope

- **New `tir/engine/fabrication_gate.py`** (small, pure, testable):
  - `FABRICATION_DETECTORS` — registry: `{category: [markers/regexes]}`, media/artifact populated.
  - `detect_fabricated_tool_result(text: str, tool_call_count: int) -> str | None` — returns the matched category (e.g. `"media_artifact"`) or `None`. Returns `None` immediately when `tool_call_count > 0` or text empty.
  - `honest_fabrication_message(category: str) -> str` — the user-facing correction.
- **`tir/api/routes.py`** — in the `terminated_reason == "complete"` branch (after `assistant_content`/`tool_call_count` are known, before `save_message` and before the flush): if `detect_fabricated_tool_result(...)`, set `assistant_content = honest_fabrication_message(...)`, keep `should_persist_assistant = True` (persist the honest correction, not the fabrication), drop the buffered `token` events for this turn and append one honest `token` event, and log a WARNING (mirrors `summarize_tool_failure` logging so incidents are visible in `tir.log`). Add `fabrication_gate_triggered` (+ category) to the debug trace record for observability. This is the only fiddly bit — the local `buffered_events` rewrite — and it is contained to this branch.
- **Tests — `tests/test_fabrication_gate.py`** (unit) + a routes test:
  - real incident blocks (rainbow/eclipse text) with `tool_call_count=0` → detected as `media_artifact`;
  - the "Threshold" concept-description text with `tool_call_count=0` → **not** detected (no identity markers);
  - fabrication-shaped text with `tool_call_count=1` → **not** detected (a tool ran);
  - ordinary prose → not detected;
  - routes-level: a complete turn with fabricated content + zero tool calls persists the **honest** message (not the block) and flushes honest tokens; a normal turn is unchanged.

No change to the agent loop, the tool framework, ollama.py, retrieval, or the frontend.

---

## How this generalizes (and where it stops, explicitly)

- **v1 covers media/artifact only** — the proven case, with high-precision markers grounded in real incident data. The registry structure makes adding a category (e.g. web_search: model claims "I searched the web and found…" with `tool_call_count == 0`; moltbook: "I posted…") a data addition. Those categories are **not** built in v1 (their markers aren't yet evidenced and risk false positives on legitimate discussion of the web/posts) — added when a fabrication in that category is actually observed, same evidence-first discipline used here.
- **Known v1 limitation (stated, not silently accepted):** the gate keys on `tool_call_count == 0`. A turn that made a *different* real tool call (e.g. a URL prefetch) but fabricated a *media* result would have `count > 0` and slip through (false negative). Rare, but the precise future refinement is to check whether the *specifically claimed* tool ran (the trace carries tool names) rather than the aggregate count — noted as the v2 tightening, out of scope for v1.
- The gate is **detection insurance**, independent of the in-flight backfill/relevance-floor work (which reduce *frequency*). It fires regardless of cause, per the DECIDED scope.

## Open items for reviewer
1. Confirm **fail-honest (b)** over retry for v1 (recommended, given the tested forced-choice failure).
2. Confirm **per-tool-category (media/artifact first)** over attempting one-pass fully-generic detection (recommended).
3. Approve the honest-message wording (or supply final text).
4. Confirm the `tool_call_count == 0` v1 keying (vs. the "did the specific claimed tool run?" v2 refinement) is acceptable for the first version.

*Plan only. No code, no commit.*
