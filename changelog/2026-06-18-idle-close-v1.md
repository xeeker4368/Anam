# Idle-Close v1 (in-process lazy sweep; manual Close removed)

## Summary

Conversations idle past a configurable window (default 15 min) are now closed
automatically — `ended_at` set + final chunking — by an in-process, bounded sweep
that piggybacks on chat traffic. This replaces the manual "Close" control (button
+ endpoint, removed) and restores the final-chunking trigger that close fired. No
new timer/daemon: the sweep runs at chat-stream start, throttled.

## Design (as approved)

- **Shared close primitive** `chunking.close_conversation(conversation_id, user_id)`:
  already-closed/missing guard → `end_conversation` (sets `ended_at`) →
  `chunk_conversation_final`. Single place close happens; the janitor calls it.
- **Idle query** `db.get_idle_open_conversations(cutoff_iso, exclude_id, limit)`:
  open convs whose `COALESCE(MAX(messages.timestamp), started_at) < cutoff`,
  oldest-first, capped. ISO-8601 UTC strings → lexical compare is chronological.
  No `last_message_at` column / no migration.
- **Janitor** in `routes.py`: `_active_generations` set, `_sweep_idle_conversations`
  (throttled `_SWEEP_THROTTLE_SECONDS=120`, bounded `_MAX_CLOSES_PER_SWEEP=3`),
  triggered **at chat-stream start only** with `exclude_id = resolved conversation`.
- **Two in-flight guards (both):**
  - **(a) Config floor:** `IDLE_CLOSE_MINUTES = max(2, configured)` — 2 min sits
    above worst-case turn (~62 s gen + ~60 s persist-on-disconnect tail), so an
    in-flight turn's last (user) message is never "idle."
  - **(b) Active-generation set:** the stream adds `conversation_id` after
    resolution and discards it in the drain's `finally`; the janitor skips any id
    in the set.
- **Config:** tracked `[conversations] idle_close_minutes = 15` in `defaults.toml`,
  read in `config.py` with `ANAM_IDLE_CLOSE_MINUTES` override and the floor.

## Interaction with persist-on-disconnect (Option 2) — verified

The marker discard lives in the **drain's `finally`**, not around the flush. In
Option 2 the drain is a no-yield stretch, so it always completes — including when
the client has already disconnected — *before* the flush where `GeneratorExit`
fires. So the marker is cleared on every path (normal completion, exception, and
disconnect), with no leak. After the drain, the conversation's newest message is
recent, so guard (a) keeps the janitor off it for the brief save/flush tail.

## Behavior Changed

- Chat-stream start now: marks the conversation in-flight, runs the throttled
  idle-close sweep (excluding itself), then proceeds; the drain `finally` clears
  the marker.
- `chunk_conversation_final` runs for idle conversations via `close_conversation`
  (the previously manual trigger is now automatic).

## Removed (surgical)

- `App.jsx`: `handleCloseConversation` and both Close buttons (the sidebar
  `sidebar-actions` wrapper — whose only child was the button — and the mobile
  header "Close"). Nothing else on that surface touched (conversation list, chat
  shell, keyboard untouched).
- `routes.py`: `POST /api/conversations/{id}/close` endpoint + its docstring line;
  the now-unused `end_conversation`/`chunk_conversation_final` imports in routes.
- `styles.css` `.btn-close` rule is now unused but left in place (touching CSS was
  out of scope).

## Files Changed

- `tir/config.py`, `config/defaults.toml` (config + floor)
- `tir/memory/chunking.py` (`close_conversation` + `end_conversation` import)
- `tir/memory/db.py` (`get_idle_open_conversations`)
- `tir/api/routes.py` (janitor + marker/finally + sweep trigger + endpoint removal + imports + docstring)
- `frontend/src/App.jsx` (Close control removal)
- `docs/PROMPT_INVENTORY.md` (regenerated — line-number drift only)
- `tests/test_idle_close.py` (new)

## Tests/Checks Run

- `pytest` — **872 passed** (+11 new in `test_idle_close.py`: idle query
  before/after cutoff, exclude_id, ended excluded, no-message started_at fallback,
  limit; `close_conversation` ends-then-chunks / already-ended no-op / missing
  no-op / ended-even-if-chunking-fails; sweep skips active+exclude & is bounded;
  sweep throttled; config floor `1 → 2`). No existing test referenced `/close`.
- `docs/PROMPT_INVENTORY.md` regenerated: only two line-number refs shifted
  (`routes.py:822→900`, `841→919`) from the added janitor code; drift test passes.
- Frontend `lint` + `build` clean (bundle shrank — Close control removed).

## Known Limitations / Chosen Costs

- **Traffic-gated:** idle convs close when the next chat-stream arrives, not on a
  precise wall clock — fine for a two-user system (final chunking just happens at
  next interaction). Clock-precise closure would need the cron-CLI path (not v1).
- **Stream-start latency:** the sweep is synchronous before generation; each close
  runs final chunking (embeddings), so a sweep that closes idle convs adds latency
  (cap 3 → typically ~0–1 closes; worst case a few seconds). Throttled to once/120 s.
- **Existing backlog:** `working.db` holds ~34 open threads from the pre-idle-close
  era; these drain a few per sweep over subsequent active use (or are cleared by a
  go-live reset).
- Device verification pending.

## Project Anam Alignment Check

- Did not assign the entity a name, personality, or visual identity.
- Did not alter prompts, model config, memory architecture, scheduler scope,
  research, or image generation. (`PROMPT_INVENTORY.md` change is a regenerated
  line-number index.)
- No schema change; no migration (derives idle from existing messages).
- No new dependencies/services; no package rename.
- Strengthens cumulative memory: idle conversations now reliably trigger final
  chunking instead of depending on a manual click.

## Branch

`feat/idle-close`, branched off `main` at `ef23b34` (persist-on-disconnect) atop
`8173cef` (resume-on-load) — both predecessors present.
