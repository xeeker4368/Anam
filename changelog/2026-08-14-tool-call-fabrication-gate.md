# 2026-08-14 — Tool-call fabrication gate (media/artifact v1)

## Summary

The model sometimes produces a tool-result-shaped response (a fake artifact
provenance block: `Artifact ID`, `Stored path`, `SHA256`, …) without ever calling
the tool — confirmed live on 2026-08-13 (rainbow, solar eclipse; `tool_call_count:
0`). This adds a detect-and-respond gate that catches fabricated *success* on the
finished turn and **fails honestly** instead of persisting/streaming the
fabrication. It is the success-side mirror of June's tool-*failure* honesty fix
(`frame_failed_tool_message`): both catch a mismatch between what really happened
and what the model claims. Implements `PLAN-2026-08-13-tool-call-fabrication-gate.md`
(all decisions approved; honest-message wording revised by the reviewer). No commit.

## Forced tool-choice: investigated, does NOT work (why the gate is the mechanism)

Tested against `gemma4:26b` via Ollama 0.31.1: `tool_choice: "required"` (native
`/api/chat` and OpenAI-compat `/v1/chat/completions`) and specific-function forcing
were all **silently ignored** — 0/8 forced attempts called a tool on a non-tool
prompt, while baseline tool-calling works. Forcing is unavailable, so a
detect-after gate is the primary mechanism (recorded in the plan; re-test on a
model/Ollama upgrade).

## What changed

- **New `tir/engine/fabrication_gate.py`** (pure, testable):
  - `FABRICATION_DETECTORS` — a per-tool-category registry; **media/artifact only**
    in v1 (the proven case). Adding a future category (web_search, moltbook) is a
    data addition, not new control flow — done evidence-first when a fabrication in
    that category is actually observed.
  - `detect_fabricated_tool_result(text, tool_call_count) -> category | None` —
    returns the matched category only when `tool_call_count == 0` AND the text
    carries that category's high-precision markers; returns `None` immediately when
    a tool ran or the text is empty.
  - `honest_fabrication_message(category) -> str` — the user-facing correction.
  - Markers (grounded in the real incident text) key on fabricated
    provenance/identity — `[Artifact source:`, an `Artifact ID:` UUID, `Stored
    path:`, the `generated/YYYY/MM/DD/` path, `SHA256:`, inline `artifact_id=`, and
    the slim-era `Artifact: … (id: …)` shape. These essentially never appear in
    honest prose.
- **`tir/api/routes.py`** — in the `terminated_reason == "complete"` branch, after
  `assistant_content`/`tool_call_count` are known and before persist/flush (the
  Option-2 drain means nothing has streamed yet): on a detection it logs a WARNING,
  replaces `assistant_content` with the honest message, **rewrites the buffered
  token events** (drops the fabricated tokens, appends one honest token), and
  persists the honest correction — **never the fabrication**. Surfaced as
  `fabrication_gate_triggered` in both the streamed `debug_update` timings bag
  (beside `tool_call_count`) and the on-disk `chat_debug.jsonl` trace record.

## Response: fail-honest, do not retry (as approved)

On detection the user sees exactly (reviewer-approved wording):

> "I wasn't able to generate that image — nothing was actually created. Want me to try again?"

Retry was rejected for v1: the model just free-chose not to call the tool, and the
forced-tool-choice test proves even hard forcing is ignored — so a retry relies on
the same lever that already failed, at the cost of a full extra generation. Failing
honestly is cheap, deterministic, and — critically — **does not persist the
fabrication**, which stops the self-poisoning loop (the fabricated block would
otherwise be imitation-bait for the next turn). This reinforces the in-flight
backfill/relevance-floor work rather than duplicating it.

## Behavior changed

- A completed turn with a media/artifact fabrication shape and **zero tool calls**
  now streams and persists the honest correction instead of the fabricated block;
  the fabrication is discarded (not saved to memory).
- Real generations (`tool_call_count > 0`) and image *concept descriptions* (no
  fabricated identity block) are unaffected — verified against real incident data.
- No change to the agent loop, tool framework, `ollama.py`, retrieval, or frontend.

## Tests / checks run

- `tests/test_fabrication_gate.py` (new, 8 tests): real eclipse-block fabrication +
  slim-era shape → detected; the real "Threshold" concept-description → **not**
  detected; artifact-shaped text with `tool_call_count > 0` → not detected; ordinary
  prose / empty → not detected; each marker triggers individually; honest message
  matches the approved wording.
- `tests/test_api_agent_stream.py` (new routes test): a fabricated complete turn
  streams the honest message (no `SHA256`/`Artifact ID` reaches the client),
  persists the honest message (not the block), and flags
  `fabrication_gate_triggered == "media_artifact"` in the debug event.
- Full suite → **922 passed**. `docs/PROMPT_INVENTORY.md` regenerated (line shifts).

## Known limitations (stated, not silently accepted)

- **v1 keys on `tool_call_count == 0`.** A turn that made a *different* real tool
  call (e.g. a URL prefetch) but fabricated a media result would have `count > 0`
  and slip through (false negative). The v2 tightening is to check whether the
  *specifically claimed* tool ran (the trace carries tool names) rather than the
  aggregate count — out of scope for v1.
- **Media/artifact category only.** Other categories are added evidence-first.

## Project Anam alignment check

- Catches fabricated success (the entity claiming an action it never took) and
  keeps it out of memory — serves Invariant 4 (distinguish what the entity did from
  what it fabricated) and the soul.md integrity floor.
- No name/persona/soul.md change; no schema/migration; no new dependency. Targeted
  gate, not a tool-framework rewrite. Scoped to the two planned files (+ tests).
