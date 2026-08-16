# Task (draft — promote to ACTIVE_TASK.md after the test-isolation patch is committed)

# Task: Purge the orphaned `fake-output.png` event chunks from the live store

## Context

The test suite spent roughly seven weeks writing fixture chunks into
`data/prod/chromadb`. That leak is now fixed and guarded
(`PLAN-2026-08-16-chroma-test-isolation.md`, changelog
`2026-08-16-chroma-test-isolation.md`): a full suite run leaves the production
store byte-identical, verified twice against an isolated tree. **The store no
longer grows — but nothing was removed.** This task removes what accumulated.

`PLAN-2026-08-15-artifact-backfill.md` deliberately skipped these chunks rather
than re-rendering them (`reason: no_artifact_row`): they cannot be re-derived,
because there is no source row to re-derive from. Deleting is the correct
treatment where re-rendering was not — they are test output that was never
anyone's experience, so removing them protects the raw stream rather than
eroding it.

**Sequencing is load-bearing and already satisfied:** the leak fix must be
committed first, or the store refills on the next `pytest` run.

## Measured target set (2026-08-16, read-only)

| measure | value |
|---|---|
| Chroma documents total | 305 |
| `artifact_*_event` chunks | 71 |
| **orphaned (no `artifacts` row)** | **50** |
| of those, pre-slim old shape | 34 |
| distinct titles among orphans | **1** — `fake-output.png` |
| orphans present in FTS | **0** — this is a Chroma-only delete |
| created_at range | 2026-06-25 → 2026-08-15 |

Every orphan is the `FakeBackend` fixture from `tests/test_image_generation.py`.
Expected end state: 305 → 255 documents, 71 → 21 event chunks, FTS unchanged at
255 rows.

## Mode

PLAN MODE. Investigate, then produce `PLAN-<date>-orphan-chunk-purge.md` in the
same format as the previous two plans (NORTH_STAR check, exact diff scope, open
questions, out-of-scope list). Paste the plan back before writing code.

## Investigate and answer in the plan (do not assume)

1. **Selector safety.** Define the delete selector and prove it cannot match a
   real record. "No `artifacts` row" is the necessary condition; is
   `title == "fake-output.png"` a useful *additional* guard, or does requiring it
   risk leaving genuine orphans behind? State which is primary. Re-measure at
   run time rather than trusting the numbers above — the store is live.
2. **Are there orphaned artifact *content* chunks too?** Today's count says the
   50 orphans are all `chunk_kind=event` and `artifact_document` chunks total
   162. Confirm whether any `artifact_*_chunk_N` records are also orphaned, and
   whether they belong in this purge or need separate treatment.
3. **Deletion mechanism.** `tir/memory/chroma.py` already has
   `delete_chunks_by_prefix` and `delete_chunk_records_by_index`; neither fits an
   id-list delete. Decide between a new narrow helper and calling
   `collection.delete(ids=[...])` from a maintenance module. Cite the actual
   implementations — and note that `_get_collection` now rebinds on a changed
   path, so a maintenance command can target a store explicitly.
4. **FTS symmetry.** Measured today: zero orphans have FTS rows, so this is
   Chroma-only. Re-verify at run time and state what happens if that changes —
   an orphan *with* an FTS row must not be half-deleted.
5. **Does anything reference these chunk ids?** Check `tool_trace`, message
   content, and the artifact card hydration path before deleting. If a real
   conversation references a fabricated artifact id, deleting the chunk does not
   remove that reference — state the consequence rather than discovering it later.

## Requirements

- **Dry run is the default**, `--apply` opts into writing — same shape as
  `artifact-backfill`.
- **Back up first** (`python -m tir.admin backup`). Not git-recoverable.
- **Report every id deleted**, with title and created_at — no silent bulk delete.
- **Before/after counts** for both stores; FTS must be unchanged.
- Existing tests keep passing (baseline: **947**), and the new test file must not
  trip the `tests/conftest.py` isolation guard.
- Re-running must be safe and cheap (second run deletes nothing).
- If deletion is not fully atomic across the id list, a partial failure must be
  reported accurately (which ids succeeded, which failed, and why) — never
  presented as a complete success when it wasn't.


## Out of scope

- The relevance-floor / retrieval-ranking work.
- Re-running or extending the artifact backfill.
- `routes.py`'s import-time `CHAT_DEBUG_TRACE_PATH` snapshot (noted as a
  follow-up in the isolation changelog).
- `OLLAMA_HOST` / `EMBED_MODEL`, and `index_artifact_file`'s exception handling.
- Deleting anything that is not an orphaned artifact chunk — in particular, the
  fabricated artifact blocks sitting in real `assistant` messages
  (conversations `0b6acc0e`, `6428649f`) are raw lived experience and are **not**
  part of this task. They need their own decision.
