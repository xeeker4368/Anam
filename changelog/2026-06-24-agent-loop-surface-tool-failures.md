# 2026-06-24 — Agent loop surfaces tool failures honestly (no more false success)

## Summary

A failed `image_generate` call was narrated by the entity as a success, with an
invented artifact block. Root cause: the agent loop only read the **outer**
dispatch envelope `ok` (which means "the tool ran without raising"), never the
**inner** `value["ok"]` that tools use to report honest failures. So a tool that
returned `{"ok": false, ...}` was recorded as success, summarized as
"succeeded," and handed to the model as raw JSON with no failure signal — which
the model then read as success.

This patch makes the agent loop (and the URL prefetch path) respect the inner
result and, on failure, give the model an explicit plain-language signal instead
of a buried `ok: false`. It is tool-agnostic: any inner failure from any tool now
surfaces as a failure everywhere.

## Root cause

- `registry.dispatch` returns `{"ok": True, "value": <inner>}` where outer `ok`
  only means "ran without raising" (documented at `registry.py:489-490`).
- `agent_loop.py` read only the outer `ok` (`:235,239,253,270`) and never
  unwrapped `value["ok"]`. A tool's honest inner failure (`_failure_trace` →
  `{"ok": false, "generation_error": true, "artifact_created": false, ...}`) was
  therefore treated as success.
- The model-visible tool message was the raw inner JSON with no natural-language
  failure framing, so the model narrated success.
- The correct inner-aware logic already existed as `_render_tool_envelope`
  (`routes.py:142`) but was wired only to the prefetch path. (See investigation
  doc `CODE_REVIEW_2026-06-24-tool-failure-reported-as-success.md`.)

## Fix (two coordinated parts + consolidation)

**Part 1 — control flow respects inner `ok`.** Consolidated the inner-aware
logic into one shared helper rather than duplicating it:
- `tir/tools/rendering.py` — added `render_tool_envelope(envelope) -> (effective_ok, rendered)`,
  where `effective_ok` is False if the tool crashed (outer `ok` False) **or**
  returned an inner failure (`value["ok"] is False`).
- `tir/api/routes.py` — removed the local `_render_tool_envelope`; the prefetch
  path now imports and uses the shared `render_tool_envelope` (behavior identical).
- `tir/engine/agent_loop.py` — the dispatch block now computes `effective_ok` and
  uses it for the streamed event `ok`, the trace record `ok`, and (transitively)
  the iteration-limit summarizer's "succeeded/failed" label (which reads the trace
  `ok` — no change needed to that function).

**Part 2 — model-visible failure framing.** Added
`frame_failed_tool_message(tool_name, rendered, envelope)` to
`tir/tools/rendering.py`. When `effective_ok` is False, the tool message the model
reads is prefixed with an explicit, tool-agnostic statement:
`TOOL FAILED — \`<tool>\` did not succeed and produced no usable result. Error: …
Do not claim it succeeded or invent its output …` followed by the raw payload.
Applied in **both** the agent loop (`agent_loop.py`) and the prefetch path
(`routes.py`) so the two consumers frame failures consistently.

## Tool-schema / scope notes

- `registry.dispatch`'s envelope shape was **not** changed (outer-`ok` = "ran" is
  used elsewhere; fixing at the consumer keeps the blast radius small).
- The tools themselves were **not** touched — `image_generate` was already
  returning honest inner failures. The bug was purely in consumption.
- The fix is **tool-agnostic**: it keys off `value["ok"] is False` for any tool.

## Files changed

- `tir/tools/rendering.py` — added `render_tool_envelope` and
  `frame_failed_tool_message`.
- `tir/api/routes.py` — removed local `_render_tool_envelope`; import + use shared
  helper; frame failed prefetch tool message for the model.
- `tir/engine/agent_loop.py` — use `effective_ok` for event/trace; frame failed
  tool message for the model; updated rendering imports.
- `tests/test_agent_loop.py` — added `inner_fail_tool` fixture and three tests.
- `tests/test_url_prefetch.py` — updated the failed-prefetch test to assert the
  new framing (raw payload still present after it).
- `docs/PROMPT_INVENTORY.md` — regenerated (line-number shift only; the inline
  framing string is not a tracked named entry).

## Behavior changed

- A tool that runs but returns inner `ok: false` is now reported as failure in:
  the streamed `tool_result` event, the persisted tool trace, and the
  iteration-limit summary.
- The model now reads an explicit `TOOL FAILED …` message (with the error and the
  raw payload) instead of bare JSON, so it cannot narrate a failed tool as success.
- Success path (inner `ok: true`, non-dict results, plain strings) is unchanged
  and unframed.
- The self-contradictory archive shape (`ok: true` with `rendered.ok: false`) no
  longer occurs — the trace `ok` now matches the inner result.

## Tests / checks run

- `pytest tests/test_agent_loop.py tests/test_url_prefetch.py tests/test_api_agent_stream.py tests/test_moltbook_selection_continuity.py` → 67 passed.
- Full suite `pytest -q` → **879 passed**.
- New tests: inner failure surfaced (event + trace + framed model message);
  inner failure labeled "failed" at the iteration limit; successful result not framed.

## Known limitations

- Framing is a fixed plain-language string; it does not vary by tool beyond
  including the tool name and the inner `error`/`error_type`.
- The streamed event `result` and the persisted trace `rendered` remain the raw
  rendered payload (unframed); the `ok` flag carries the failure signal there. The
  framing is applied to the model-visible message content, where it is needed.

## Follow-up work

- **Out of scope (separate issue):** the underlying cause of these specific
  failures is ComfyUI concurrency — it was mid-render on a ~26s job when calls 2
  and 3 arrived (`backend_unavailable`, HTTP 400). Honestly surfacing failures
  (this patch) is distinct from preventing them; a queue/retry-on-busy-backend
  policy should be designed separately.

## Project Anam alignment check

- Did not assign the entity a name; did not call it Anam or Tír.
- Did not add or assign personality.
- **Directly serves Invariant 4 (provenance / "what it experienced vs created"):**
  the entity's lived record now reflects real tool failures instead of fabricated
  successes; and §2 ("measuring, not performing") — it removes a source of
  manufactured success.
- No new capability added; no enable gate widened; no always-on mechanism.
- No memory architecture, schema, or database change; no migration required.
- No new external dependency or paid service.
- Additive, consumer-side fix; `registry.dispatch` and the tools were not changed.
- Tool traces are now internally consistent (`ok` matches the inner result).

## Addendum (2026-06-25) — WARNING log for tool failures

Confirmed in real production data (conversation `0b6acc0e`, turns 23 and 25):
`image_generate` returned inner `{"ok": false, ... backend_unavailable / status
400 ...}` while the persisted message `tool_trace` recorded outer `"ok": true` —
the exact outer-vs-inner `ok` bug this fix targets, now seen live, not just in
tests.

Follow-up addition (separate commit from the original fix): tool failures are now
logged at WARNING level so they are visible in `tir.log` instead of silent.

- `tir/tools/rendering.py` — added `summarize_tool_failure(tool_name, envelope)`,
  a one-line, tool-agnostic summary (tool name + `error_type`/`error`, falling
  back to the dispatch error when the tool crashed).
- `tir/engine/agent_loop.py` — at the `effective_ok is False` branch, one
  `logger.warning(summarize_tool_failure(...))` before the model message is framed.
- `tir/api/routes.py` — same one-line WARNING at the URL-prefetch failure branch.

No behavior change beyond logging; the streamed event, trace `ok`, model framing,
and control flow are unchanged. Full suite re-run: still green.
