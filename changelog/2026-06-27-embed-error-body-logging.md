# 2026-06-27 — Log Ollama's error body on embed failure (observability only)

## Summary

`embed_text` called `resp.raise_for_status()`, which discards Ollama's response
body — so every embedding failure surfaced as a bare `400 Client Error` / `404
Client Error` with no reason. This adds an observability-only capture of the real
error body before re-raising, so the next real failures reveal *why* Ollama
rejected the request. No behavior change; the exception is re-raised unchanged.

This is the single permitted code change of the embed/memory-loss **diagnosis**
task (see `CODE_REVIEW_2026-06-27-embed-diagnosis.md`). No fix yet.

## Files changed

- `tir/memory/chroma.py` — in `embed_text`, wrap `resp.raise_for_status()` in
  `try/except requests.HTTPError` that logs `status`, `model`, input `text_len`,
  and `resp.text[:1000]` (the verbatim Ollama body) at ERROR, then `raise`.

## Behavior changed

- None functionally. On an embed HTTP error, one ERROR log line is now emitted
  before the same exception propagates. Success path untouched.

## Tests / checks run

- `pytest tests/test_chunking.py tests/test_memory_audit.py tests/test_retrieval.py` → 32 passed.
- Import smoke: `tir.memory.chroma` imports clean.

## Known limitations

- Reveals the body only for failures that occur *after* this is deployed; it
  cannot recover bodies for the historical failures already in `tir.log`.
- Body is truncated to 1000 chars (safety); enough for Ollama's error strings.

## Follow-up work

- Capture the verbatim 400/404 bodies off the next live failures (diagnosis
  step 3) — the fix decision waits on them.

## Project Anam alignment check

- Did not assign the entity a name; did not call it Anam or Tír.
- Observability only — preserves debug/instrumentation (does not remove it),
  serves the legible-substrate principle. No memory architecture, schema,
  chunking, or retrieval behavior changed. No migration.
- No new dependency or service. Reversible one-spot change.
