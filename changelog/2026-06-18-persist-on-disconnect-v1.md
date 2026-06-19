# Persist-on-Disconnect v1 (Option 2: drain → save → replay)

## Summary

Fixes the persistence gap where a mid-stream client disconnect lost the
assistant reply entirely. Previously `generate()` streamed tokens to the client
as it went and only called `save_message("assistant", …)` *after* the stream
loop; a client disconnect raised `GeneratorExit` at a `yield` and unwound the
generator before the save, so the reply was never written and a refresh
(resume-on-load) had nothing to show.

Now `generate()` **drains** the agent loop and **buffers** its client events
without yielding, **persists** the assistant reply, and only **then flushes** the
buffered events to the client. The save sits in a no-yield stretch, so a client
disconnect can no longer interrupt it.

This is the persistence half; resume-on-load (already on main) is the recovery
half — together, a reply generated during a dropped connection is saved and shown
on the next open.

## Why this works (and needs no GeneratorExit handling)

A synchronous generator only observes a client disconnect when it `yield`s
(Starlette pulls the next item). The agent loop already finishes generation before
any token is replayed (`agent_loop.py` buffers the model output, then replays it
as token events), so draining it here costs nothing extra in the common case. By
moving the `save_message` ahead of every reply-bearing `yield`, the drain +
decision + save all run in one uninterrupted stretch: a disconnect during that
stretch is simply not detected until the later flush, by which point the reply is
durable. A disconnect during the flush only stops delivery — the row is saved.

## Files Changed

- `tir/api/routes.py` (`generate()` only)
- `docs/PROMPT_INVENTORY.md` (regenerated — line-number drift only)

## Behavior Changed

- Agent-loop events (`token`/`tool_call`/`tool_result`) and the agent-loop
  exception error are now appended to a `buffered_events` list instead of being
  yielded inline.
- The assistant-save decision block (`complete` / `iteration_limit` / empty /
  error) likewise appends its client events to `buffered_events` instead of
  yielding.
- `save_message("assistant", …)` + `checkpoint_conversation` now run after the
  decision block and **before** any flush — in the no-yield stretch.
- A flush loop then yields all `buffered_events`, followed by `debug_update` and
  `done` (unchanged content/order). The early `debug` event and URL-prefetch
  events still yield before the loop (they are not the reply and precede
  generation).

## Gating Unchanged (moved when, not whether)

`should_persist_assistant` and `assistant_content` logic is byte-for-byte the
same (`loop_result is None` → no persist; `complete`/`iteration_limit` → persist
iff content non-empty; error → no persist). Only the moment of the save moved
(before flush instead of after streaming).

## Idempotency / Exactly-Once

The assistant `save_message` is **relocated, not duplicated** — there is exactly
one assistant save call site in `generate()` (verified), and the flush phase
contains no save. Exactly-once by construction.

## UX Note (tool-turn silence — assessed, no change needed)

From 183 recorded turns (`data/prod/chat_debug.jsonl`): even no-tool turns take
~15 s median (p90 ~33 s, max ~62 s) on the local model, and that silence is
pre-existing (generation is already buffered before the first token). The chat
already covers it: the optimistic assistant bubble renders a blinking cursor
(`Chat.jsx`) from send until `done`, and tool events only ever fed the debug
panel, never the chat. So buffering changes nothing in the user-facing chat; the
only thing deferred is live tool events in the **debug panel** (a developer
surface). No new "working" indicator is warranted.

Cost accepted: if a client disconnects during the drain, the server still
finishes that one turn before saving (up to ~60 s of post-disconnect work on this
model). Bounded to one in-flight request, no queue — fine for a two-user home
system, and it is what guarantees a complete reply.

## Scope

`tir/api/routes.py` `generate()` only. `agent_loop.py` untouched (consumed the
same, drained fully instead of interleaved). No frontend change (token burst +
`done` contract identical; the cursor indicator already exists). The
`docs/PROMPT_INVENTORY.md` change is a regenerated line-number index, not a prompt
edit.

## Tests/Checks Run

- `pytest` — **861 passed** (existing 31 stream tests pass unchanged: TestClient
  collects the full response, so buffered-then-flushed events arrive in the same
  order/content).
- `docs/PROMPT_INVENTORY.md` regenerated (`python -m scripts.extract_prompt_inventory`):
  only two line-number refs shifted (`routes.py:813→822`, `832→841`) from the
  added lines; its drift-guard test passes.
- Frontend `lint` + `build` clean (unchanged bundle — no frontend edit).

## Known Limitations

- Device verification pending: background mid-response on iOS, return → the reply
  is present after a clean reload (it was saved server-side despite the drop).
- Multi-iteration tool turns: a disconnect mid-turn still completes remaining
  iterations server-side before saving (bounded; intended).

## Branch / Base

Implemented on `feat/persist-on-disconnect`, branched off `main`. Note: `main`
now includes resume-on-load (merged since the resume-on-load handoff), so this
builds on main-with-resume-on-load — the two halves are complementary.

## Project Anam Alignment Check

- Did not assign the entity a name, personality, or visual identity.
- Did not alter prompts, model config, memory architecture, scheduler, research,
  or image generation. (`docs/PROMPT_INVENTORY.md` change is a regenerated
  line-number index.)
- No schema change; no migration. No new dependencies/services. `tir/` untouched
  structurally.
- Strengthens raw-experience integrity: an assistant reply that was generated is
  now reliably written to the archive even when the client drops, rather than
  silently lost.
