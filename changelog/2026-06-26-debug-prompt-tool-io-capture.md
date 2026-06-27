# 2026-06-26 — Opt-in prompt + tool I/O debug capture (Part B)

## Summary

Until now the console showed only HTTP access logs and `chat_debug.jsonl`
deliberately omitted prompt text and tool args/results — so there was no way to
see what the model was actually given or what it tried to do (e.g. a pure
retrieval-replay/confabulation turn left no inspectable trace). This adds an
**opt-in, env-gated** capture of the assembled prompt and tool I/O, reusing the
existing debug-trace sink. **Off by default.** Observe-only — it does not change
prompt assembly or tool dispatch.

## What changed

- `tir/config.py` — new flag `DEBUG_PROMPT_ENABLED = _env_bool("ANAM_DEBUG_PROMPT", False)`
  (default off).
- `tir/api/routes.py` — when the flag is on, the per-turn debug record gains a
  `debug_prompt` block (written through the **existing** `write_chat_debug_trace`
  writer to the **existing** `CHAT_DEBUG_TRACE_PATH`, so secret-shaped strings are
  still redacted and there is one JSONL line per turn). `debug_prompt` contains:
  - `system_prompt` — the full assembled system prompt the model received
    (includes retrieved memory — this is where a replayed artifact block shows up);
  - `messages` — the conversation/messages list sent to the model (`role`,
    `tool_name`, `content`, `tool_calls`); tool **results** appear here as the
    `role:"tool"` message content (the inner envelope), untruncated;
  - `tool_calls` — convenience list of `{name, arguments}` the model emitted.

When the flag is off, the record is byte-for-byte the same as before (no
`debug_prompt` key).

## Tool-agnostic + zero-tool-call coverage

The capture is derived generically from `model_messages` and is not specific to
any tool. A turn with **no** tool calls is fully captured: `tool_calls` is `[]`
and `system_prompt` + `messages` still record exactly what produced the reply —
which is precisely the pure-confabulation case that was previously invisible.

## Behavior changed

- None to runtime behavior. The flag-on path only reads already-computed values
  (`system_prompt`, `model_messages`) at trace-write time and appends them to the
  debug record. Prompt assembly and tool dispatch are untouched.

## Tests / checks run

- `tests/test_api_agent_stream.py`:
  - `test_debug_prompt_flag_captures_prompt_and_tool_io` — flag on: `debug_prompt`
    present; `system_prompt` contains the retrieved-memory marker; messages include
    the user turn; zero-tool case → `tool_calls == []`.
  - `test_debug_prompt_flag_off_omits_capture` — default off: no `debug_prompt` key.
  - Existing `test_stream_chat_writes_structured_debug_trace_without_message_bodies`
    still passes (default record omits bodies and redacts secrets).
- Full suite: **892 passed**.
- `docs/PROMPT_INVENTORY.md` regenerated (line-number shift only; no new tracked
  strings).

## PII / safety considerations

- The captured `system_prompt` + `messages` contain the **full conversation and
  retrieved memory** (PII). Therefore: the flag is **off by default** and intended
  only for testing/diagnosis.
- The sink (`DATA_DIR/chat_debug.jsonl`) is **gitignored** (verified), so captures
  are not committed.
- The existing writer's secret redaction (`redact_debug_value`: Bearer tokens,
  api_secret/api_key/authorization/token) still runs over the whole record,
  including the new block. It redacts secret-shaped strings only — not general PII,
  which is why the flag stays off in normal operation.

## Known limitations

- General PII in the prompt is not redacted (only secret-shaped strings are); the
  off-by-default + gitignored controls are the safeguard.
- `messages` reflects the post-loop `model_messages` (history + any tool exchanges
  appended during the turn), which is the assembled prompt sequence the model saw.

## Follow-up work

- None required. Pairs with the Part A investigation
  (`CODE_REVIEW_2026-06-26-retrieval-replay-vector.md`): with this flag on, a
  retrieval-replay turn's `system_prompt` will show the injected artifact block
  directly.

## Project Anam alignment check

- Did not assign the entity a name; did not call it Anam or Tír.
- Did not add or assign personality.
- **Serves legibility/inspectability and Invariant 4** — makes what the entity was
  given and did inspectable, without altering it.
- Observe-only: no change to prompt assembly, tool dispatch, memory ingestion,
  chunking, retrieval, or the wipe path.
- No new external dependency or paid service; reuses the existing debug sink.
- Off by default; gitignored sink; secret redaction retained.
