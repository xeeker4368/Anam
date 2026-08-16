# 2026-08-16 — Stop the test suite writing into the production store

## Summary

Every `pytest` run was writing into `data/prod` — 2 chunks into `data/prod/chromadb`
and 7 lines into `data/prod/chat_debug.jsonl` — and had been for roughly seven weeks
(50 orphaned `fake-output.png` event chunks had accumulated). Both surfaces are now
closed at the source, with a guard that fails the run loudly if either is reintroduced.

Implements `PLAN-2026-08-16-chroma-test-isolation.md` as approved: fix (a′), the
`_get_collection` path rebind, the same fix shape for `chat_debug_trace.py`, a new
`tests/conftest.py` guard added *after* the fix, and a regression test proving the
guard catches a reintroduced leak. No existing test file was modified. `OLLAMA_HOST` /
`EMBED_MODEL` and `index_artifact_file`'s exception handling were left alone as
instructed. No commit — Lyle reviews and device-tests.

## What changed

- **`tir/memory/chroma.py`** — imports the `tir.config` *module* and resolves the store
  path at call time through a new `_resolve_chroma_path()`, instead of binding
  `CHROMA_DIR` as an import-time default argument. All seven `chroma_path` parameters
  (`_get_collection`, `upsert_chunk`, `delete_chunk_records_by_index`,
  `delete_chunks_by_prefix`, `query_similar`, `get_collection_count`,
  `empty_collection`) become `str | None = None`. `empty_collection`'s direct
  `PersistentClient` construction resolves through the same helper.
  - **Cache rebind:** `_get_collection` now tracks `_collection_path` and rebinds when a
    different path is requested. Previously the cache was unconditional, so once any
    collection was open the `chroma_path` argument was silently discarded and a caller
    asking for store B could be handed store A. `reset_client()` clears the new state too.
  - **`CHROMA_DIR` is kept as a module attribute** — a documented compatibility alias, not
    used for resolution. `tests/test_chroma.py` reads `chroma.CHROMA_DIR` as a default
    sentinel in three places, and no test file was allowed to change.
- **`tir/ops/chat_debug_trace.py`** — same shape: imports the config module, adds
  `chat_debug_trace_path()` resolving `config.DATA_DIR` at call time, and
  `write_chat_debug_trace` falls back to it. `CHAT_DEBUG_TRACE_PATH` kept as a documented
  alias (`tir/api/routes.py` imports it).
- **`tests/conftest.py`** (new) — the guard. First project-level conftest.
- **`tests/test_store_isolation.py`** (new) — 9 regression tests.

## Verification (full-suite against an isolated store, per the plan's methodology)

A single-file run of `test_image_generation.py` neither reproduces nor verifies this —
the leak only appears in a full-suite run, because the default path is bound when
`tir.memory.chroma` is first imported and pytest imports every test module before running
anything. All verification below is full-suite against a scratch copy of the tree with an
empty `data/prod`, where any file appearing under `data/prod` is by definition a leak.

| run | result | leaked into `data/prod` |
|---|---|---|
| before the fix (previous session) | 938 passed | **2 chroma docs + 7 trace lines** |
| after source fix, before guard | 938 passed | 0 chroma docs, 7 trace lines |
| after source fix + guard | **947 passed** | **nothing** |
| repeat run (stability, not order-luck) | **947 passed** | **nothing** |
| **fix deliberately reverted in the scratch copy** | **2 failed**, violation reported | **nothing — the guard blocked the write** |

- **Real repo, full suite: 947 passed** (938 baseline + 9 new).
- **Production store unchanged by a full suite run for the first time:** chroma 305 → 305,
  FTS 255 → 255, `chat_debug.jsonl` 515 → 515 lines. Previously every run moved the first
  and third.
- **Production behaviour unaffected**, checked outside pytest with no patches: chroma and
  chat-debug both resolve to the real paths, `routes.CHAT_DEBUG_TRACE_PATH` unchanged, the
  live collection reports its 305 chunks, and `query_similar` still returns hits. A server
  round-trip is left to the device test.

## The guard, and one deviation worth flagging

`tests/conftest.py` does two different things on purpose:

- **Chroma — guard only, no redirect,** exactly as the plan specified. With call-time
  resolution, the 19 existing fixtures that patch `tir.config.CHROMA_DIR` now genuinely
  redirect, so nothing needs helping.
- **Chat debug trace — redirect *and* guard.** This is the deviation. `tir/api/routes.py`
  snapshots `CHAT_DEBUG_TRACE_PATH` into its own namespace at import and passes it
  explicitly, so call-time resolution in `chat_debug_trace.py` cannot reach that call. Of
  the 7 leaking tests, 5 (`test_url_prefetch.py`, `test_moltbook_selection_continuity.py`)
  apply **no** path isolation at all — no source-side fix can stop them, and fixing them
  properly means editing those files, which this task forbade. So the conftest redirects
  the trace path per-test, with the guard still watching underneath. Tests with their own
  trace-path fixture (`test_api_agent_stream.py`) patch the same attribute afterwards and
  still win.

  The honest residual: `routes.py` still snapshots the path at import. Fixing that
  properly is a small `routes.py` change plus edits to `test_api_agent_stream.py` — both
  outside the approved diff scope. Recommended follow-up, noted below.

**`StoreIsolationViolation` inherits from `BaseException`**, not `Exception`. `retrieve`,
`index_artifact_file` and the routes trace call all wrap store access in
`except Exception`; a guard those swallow is no guard at all. Violations are also recorded
and re-reported at `pytest_sessionfinish`, so a swallowed one still fails the run visibly.
There is a test for the swallow case specifically.

## Tests / checks run

`tests/test_store_isolation.py` — 9 tests:
- patching `tir.config.CHROMA_DIR` alone (no `importlib.reload`) redirects `upsert_chunk`
- an explicit `chroma_path` still wins over config
- `_get_collection` rebinds when the path changes (two paths → two clients)
- the `chroma.CHROMA_DIR` compatibility alias is still exposed
- patching `tir.config.DATA_DIR` alone redirects `write_chat_debug_trace`
- the guard blocks opening the production Chroma store
- the guard blocks writing the production trace, **and the real file's size is asserted
  unchanged** — the test fails rather than damaging production if the guard regresses
- a violation survives a broad `except Exception`
- the guard allows isolated paths through

Plus the end-to-end proof in the table above: reverting the fix in the scratch copy makes
the suite fail with `PRODUCTION STORE ISOLATION VIOLATIONS: 1` and still writes nothing.

## Known limitations

- **`routes.py` still snapshots `CHAT_DEBUG_TRACE_PATH` at import.** Mitigated by the
  conftest redirect, not fixed. Follow-up above.
- **The 5 unisolated tests are still unisolated.** They pass because the conftest redirects
  them, not because they got better. Worth a cleanup pass someday.
- **`OLLAMA_HOST` / `EMBED_MODEL` have the identical defect** in `embed_text` — untouched,
  as instructed. No measured leak.
- **`index_artifact_file` still swallows all exceptions** — untouched, as instructed. It is
  why this went unnoticed; the guard now makes that swallow harmless for tests.
- **The orphan chunks are still there:** 71 event chunks, 50 orphaned, 34 old-shape. The
  store no longer grows, but nothing was removed. That purge is the separately-approved
  next task.

## Project Anam alignment check

1. **Name?** No. 2. **Called the entity Anam/Tír?** No. 3. **Personality?** No.
4. **Raw experience preserved?** Yes — nothing was read, rewritten, or deleted; this stops
   *additions* of records that were never anyone's experience.
5. **Derived artifacts traceable?** Unchanged. 6. **Tool calls recorded?** Unchanged.
7. **Created artifacts remembered?** Unchanged. 8. **Context construction inspectable?**
   Unchanged — and the trace file used for diagnosis is no longer contaminated with
   `conv-1` test records. 9. **More cumulative?** Neutral.
10. **Anam/entity distinction?** Preserved. 11. **Migration?** None — no schema or data change.
12. **Tests?** Above. 13. **Core substrate changed unnecessarily?** `chroma.py` is core, but
    the change is path *resolution timing* only, verified to be a production no-op.
14. **External dependencies/services?** None added.
15. **Workspace vs. self-modification?** Unaffected. 16. **Legacy renaming avoided?** Yes.

Invariant 4 note: this is the cleanest possible service to "never silently mutate the
store" — the mutations it stops were fictional records injected by test fixtures, with no
provenance and no lived origin, arriving silently on every run.

## Follow-up

- Device test (Lyle): server up, one real chat turn, confirm a chunk lands in
  `data/prod/chromadb` and a line in `chat_debug.jsonl` exactly as before.
- **Next task, already approved in principle:** purge the 50 orphaned `fake-output.png`
  event chunks from the live store. Strictly after this fix — purging first would refill on
  the next `pytest` run. Draft to follow once this is committed.
- Optional cleanup: make `routes.py` resolve the trace path at call time and drop the
  conftest redirect (needs a small `test_api_agent_stream.py` change).
