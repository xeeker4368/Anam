# 2026-08-16 — Purge orphaned `fake-output.png` artifact chunks

## Summary

Adds `python -m tir.admin artifact-orphan-purge` — a dry-run-by-default maintenance
command that deletes the artifact chunks the `CHROMA_DIR` test-isolation leak wrote into
`data/prod/chromadb` over roughly seven weeks. 50 such chunks are present: titled
`fake-output.png`, with no row in `artifacts`, no conversation, no user, and no lived
origin, sitting in the retrieval pool alongside real memory.

Implements `PLAN-2026-08-16-orphan-chunk-purge.md` as approved, including the mandatory
two-condition selector and per-id re-read verification. **The purge has not been run against
production** — that is Lyle's runbook step. It has been proven end-to-end against a full
copy of the real store (see below). No commit.

## What changed

- **`tir/memory/chroma.py`** — new `delete_chunks_by_ids(ids, chroma_path=None) -> dict[str, bool]`.
  Deletes one id at a time and **verifies each removal by re-reading**
  (`collection.get(ids=[id])` must come back empty), returning `{chunk_id: removed?}`.
  Exceptions propagate; the caller owns the error policy. Neither existing helper fitted:
  `delete_chunk_records_by_index` keys on `(conversation_id, chunk_index)`, and
  `delete_chunks_by_prefix` would need the prefix `artifact_`, which is also the prefix of
  every *real* artifact chunk — using it here would have deleted the store.
- **New `tir/memory/artifact_orphan_purge.py`** — `purge_orphan_artifact_chunks(*, dry_run=True, limit=None)`.
- **`tir/admin.py`** — `artifact-orphan-purge` subcommand (`--apply`, `--limit N`), handler,
  a printer that reports every id with title/created_at/chunk_kind/reason plus before/after
  counts, dispatch and docstring entries.
- **New `tests/test_artifact_orphan_purge.py`** — 16 tests.

No change to the artifact backfill, retrieval, `_event_text`, schema, or the frontend. No
message, `tool_trace`, or `open_loops` row is read or written.

## Why the selector needs two conditions, not one

"No `artifacts` row" is necessary but **not sufficient** to prove test origin.
`ingest_artifact_file` writes the chunks (`ingestion.py:239`) **before** the artifacts row
(`ingestion.py:262`), so a crash between those two lines would leave a *real* upload's
chunks orphaned in exactly the same way. There is no `DELETE FROM artifacts` anywhere in
`tir/` (only `go_live_reset`, which empties Chroma in the same operation and so creates no
asymmetry), which leaves precisely two causes for an orphan: the test leak, or a
half-completed real ingest.

So deletion requires **all** of: `artifact_`-prefixed chunk id ending `_event`,
`chunk_kind == "event"`, `source_type == "artifact_document"`, no `artifacts` row, **and**
`title == "fake-output.png"`. Anything orphaned that fails the title guard — or any orphaned
*content* chunk — is reported as `needs_review` and left untouched. Leaving those behind is
the point, not a gap: that is the half-completed-real-ingest case, and it deserves a human
look rather than a silent delete.

## Why success is verified by re-reading

Measured against the vendored chromadb on a throwaway store:

```
col.delete(ids=['zzz'])  ->  {'deleted': 1}   # id does NOT exist
count after              ->  unchanged
```

`collection.delete()` reports `{"deleted": n}` regardless of whether anything was removed,
so its return value cannot distinguish "removed it" from "nothing was there" from "the write
did not land". Every delete is therefore confirmed by reading the id back and finding
nothing. This is what makes accurate partial-failure reporting possible at all, and it is
why the implementation deletes per id rather than issuing one bulk 50-id call — a bulk call
cannot report *which* ids actually went.

## Partial-failure reporting

FTS is handled first, then Chroma, and each id ends up in exactly one bucket:

- `deleted` — gone from both stores, verified by re-read
- `partial` — FTS row removed but the Chroma record survived or the delete raised; the
  reason names which store still holds it
- `failed` — nothing was removed, with the exception text
- `needs_review` — orphaned but outside the title guard; untouched
- `would_delete` — dry run only

One failing id never aborts the rest. There are tests for the lying-delete case, the
FTS-succeeded-then-Chroma-failed case, and the one-bad-id-among-many case.

## Tests / checks run

- **`tests/test_artifact_orphan_purge.py` — 16 passed.** Covers: orphan deleted; chunk with
  an artifacts row never selected (even when titled `fake-output.png`); orphan with an
  unexpected title → `needs_review`, untouched; orphaned content chunk → `needs_review`;
  conversation and research chunks never scanned; dry run deletes nothing; second run finds
  nothing; `--limit`; orphan with an FTS row cleaned from both stores; FTS untouched when the
  orphan has no FTS row; a delete that did not land reported `failed` not `deleted`;
  FTS-removed-then-Chroma-failed reported `partial`; one failing id does not abort the
  others; and three tests for `delete_chunks_by_ids` itself (re-read verification, one id per
  call, missing id treated as removed).
- **Full backend suite → 963 passed** (947 baseline + 16). Production store unchanged by the
  run: chroma 305 → 305, FTS 255 → 255.
- **Live dry run against production** (read-only): 162 artifact chunks scanned · 112 with an
  artifacts row · **50 orphaned · 0 needs_review · 50 deletable** · counts unchanged. Every
  id printed and eyeballed.
- **`--apply` proven against a full copy of the real production store** (isolated tree, prod
  never touched):

  | | before | after |
  |---|---|---|
  | Chroma documents | 305 | **255** |
  | `artifact_*_event` chunks | 71 | **21** |
  | FTS rows | 255 | **255 (unchanged)** |
  | orphans remaining | 50 | **0** |
  | chunks titled `fake-output.png` | 50 | **0** |
  | real `artifact_document` chunks | 112 | **112 (intact)** |

  Result line: 50 deleted, 0 partial, 0 failed, 0 needs_review. A second `--apply` on the
  purged copy found 0 orphans and changed nothing — idempotent. Retrieval on the purged copy
  still returns the correct real artifacts (`rainbow` → `ab527bd5`, the rainbow image;
  `a breathtaking total solar eclipse` → `2b3099cb`, the eclipse image), and the
  conversation/research/journal chunk census was untouched.

## Runbook (for the operator)

1. Stop the server; no `pytest` during the window.
2. `python -m tir.admin backup` — the only rollback. Deleted vectors cannot be re-derived.
3. `python -m tir.admin artifact-orphan-purge` — expect 50 deletable, 0 needs_review.
4. `python -m tir.admin artifact-orphan-purge --apply`.
5. Verify Chroma 305 → 255, event chunks 71 → 21, FTS unchanged at 255.
6. Re-run the dry run → 0 deletable (idempotency check).
7. Retrieval spot-check: `retrieve("rainbow")` still returns its real artifact chunk.

## Known limitations

- **Irreversible.** Recovery is the backup, nothing else — hence the mandatory backup step
  and the dry-run default.
- **The FTS delete uses raw SQL in the purge module** rather than a `tir/memory/db.py`
  helper. `delete_fts_chunk_index` keys on `(conversation_id, chunk_index)` and does not fit;
  adding a new db helper would have widened the diff beyond the approved scope. The raw query
  follows the `artifact_backfill._fts_provenance` precedent.
- **`needs_review` is empty today**, so that branch is proven by unit tests rather than by
  live data.
- **The fabricated artifact ids in real assistant messages are untouched**, as instructed —
  `9b8c7d6e`, `a1b2c3d4` and five others, referenced by eight real `assistant` messages in
  conversations `0b6acc0e` and `6428649f`. They have no Chroma chunks, so this purge neither
  reaches nor affects them. Still an open decision.

## Project Anam alignment check

1. **Name?** No. 2. **Called the entity Anam/Tír?** No. 3. **Personality?** No.
4. **Raw experience preserved?** Yes, and this is the crux: the deleted records are the ones
   with *no* provenance — no source row, no conversation, no user, no lived origin. Real
   memory (conversation, research, journal, and all 112 real artifact chunks) is verified
   intact on the purged copy. Nothing in `messages` is read or written.
5. **Derived artifacts traceable?** Unchanged. 6. **Tool calls recorded?** Unchanged.
7. **Created artifacts remembered?** Yes — every real artifact keeps its chunks.
8. **Context construction inspectable?** Improved: the retrieval pool no longer contains 50
   fictional artifacts. 9. **More cumulative?** Neutral. 10. **Anam/entity distinction?** Preserved.
11. **Migration?** No schema change; a data deletion, recoverable only from the backup.
12. **Tests?** Above. 13. **Core substrate changed unnecessarily?** One additive helper in
    `chroma.py`; no existing behaviour altered. 14. **External dependencies/services?** None.
15. **Workspace vs. self-modification?** Unaffected. 16. **Legacy renaming avoided?** Yes.

Invariant 4 note: this is the project's first deletion from the store, so the bar was
"prove it isn't memory" rather than "prove it's safe to remove". The two-condition selector,
the `needs_review` escape hatch, the re-read verification, the dry-run default, the mandatory
backup, and the full-copy rehearsal all exist to keep that bar honest.

## Follow-up

- Operator runbook above, then commit.
- Still open and undecided: the fabricated artifact blocks inside real assistant messages.
- Still open: the relevance-floor work, and `routes.py`'s import-time
  `CHAT_DEBUG_TRACE_PATH` snapshot.
