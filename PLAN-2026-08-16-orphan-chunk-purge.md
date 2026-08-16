# PLAN — Purge orphaned `fake-output.png` artifact chunks. PLAN ONLY.

**Date:** 2026-08-16 · **Mode:** plan only. **No code, no commit.** All numbers below were
measured read-only against the live store today; Chroma delete semantics were probed on a
throwaway scratch store, never on production.

**Task source:** `ACTIVE_TASK.md` — remove what the seven-week `CHROMA_DIR` test leak left
behind, now that the leak itself is fixed and guarded.

**Sequencing precondition: satisfied.** `4ef1de1` (test isolation) and `52b31fd` (backfill)
are both committed. A full suite run now leaves the production store byte-identical, so the
store will not refill after the purge.

---

## NORTH_STAR check

This is the sharpest Invariant 4 question the project has faced so far, because it is the
first task that *deletes* from the store rather than adding to or re-rendering it. The
argument for it: these 50 records were never anyone's experience. They have no source row,
no conversation, no user, no lived origin — they are fixture output from
`tests/test_image_generation.py` that a path-resolution bug redirected into production.
"Provenance is sacred" is precisely why they should go: they are the records with *no*
provenance, sitting in the same collection as records that have it, and they are retrieved
into the entity's context as though they were memories.

That said, deletion is irreversible and cannot be re-derived. So: mandatory backup, dry run
by default, per-id reporting, a deliberately conservative selector that refuses to delete
anything it is not certain about (§1), and an explicit refusal to touch real messages (§5).
**Aligned — with the caution the irreversibility deserves.**

---

## 1. Q1 — Selector safety. **Two conditions, both required. Title is a guard, not a convenience.**

**Measured today (live, read-only):**

| measure | value |
|---|---|
| Chroma documents | 305 |
| FTS rows | 255 |
| `artifacts` rows | 30 |
| `artifact_document` chunks | 162 (71 event + 91 content) |
| **orphan event chunks (no `artifacts` row)** | **50** |
| distinct titles among orphans | **1** — `fake-output.png` |
| chunks titled `fake-output.png` that DO have a row | **0** |
| orphan ids matching `artifact_<uuid36>_event` | 50/50 |
| orphan metadata `artifact_id` consistent with the chunk id | 50/50 |

Both candidate selectors select exactly the same 50 chunks today. They are not
interchangeable in principle, though, and the difference matters:

**"No `artifacts` row" is the necessary condition, but it is not sufficient to prove test
origin.** A genuine orphan is possible: `ingest_artifact_file` writes the chunks at
`ingestion.py:239` and the `artifacts` row at `ingestion.py:262` — **chunks first**. A crash
or exception between those two lines leaves a *real* upload's chunks with no row. There is
no `DELETE FROM artifacts` anywhere in `tir/` (only `go_live_reset`, which empties Chroma in
the same operation, so it creates no asymmetry). So "no row" can arise from exactly two
causes: the test leak, or a half-completed real ingest.

**Recommended selector — delete requires ALL of:**
1. `chunk_id` starts with `artifact_` and ends with `_event`
2. `metadata["chunk_kind"] == "event"` and `metadata["source_type"] == "artifact_document"`
3. `metadata["artifact_id"]` has **no** row in `artifacts`
4. `metadata["title"] == "fake-output.png"`

Condition 4 does **not** risk leaving genuine orphans behind — leaving genuine orphans
behind is the *point*. Any chunk satisfying 1–3 but failing 4 is reported as
`needs_review` and **not deleted**, because that is precisely the half-completed-real-ingest
case, and it deserves a human look rather than a silent delete. Today that set is empty; if
the run finds one, the operator learns something instead of losing something.

Counts are re-measured at run time, not taken from this document — the store is live.

## 2. Q2 — Orphaned content chunks. **None. Measured, and consistent with the mechanism.**

Of 162 `artifact_document` chunks, 91 are `chunk_kind=content` and **0 of them are
orphaned**. All 50 orphans are `chunk_kind=event`.

That matches how the leak worked: the fixture ingests `fake-output.png`, and
`index_artifact_file` writes the event chunk first, then returns early at the
`is_supported_text_file` check (`artifact_indexing.py:246-248`) because a PNG is not a
supported text type — so content chunks were never written for these.

The implementation still **selects on metadata rather than assuming this**, and reports any
orphaned content chunk it finds as `needs_review` rather than deleting it. If the mechanism
ever produced one, it would be a different bug and should be looked at, not swept up.

## 3. Q3 — Deletion mechanism. **New narrow helper. And do not trust Chroma's return value.**

Neither existing helper fits:
- `delete_chunk_records_by_index` (`chroma.py:221-244`) deletes by a metadata `where` on
  `(conversation_id, chunk_index)` — wrong keys entirely for artifact chunks.
- `delete_chunks_by_prefix` (`chroma.py:246-270`) lists all ids and deletes every id sharing
  a prefix. Far too blunt: the only prefix these share with each other is `artifact_`, which
  is also the prefix of every **real** artifact chunk. Using it here would delete the store.

**Recommended: add `delete_chunks_by_ids(ids, chroma_path=None)` to `chroma.py`** — an exact
id-list delete, the operation the module is missing — and have the maintenance module drive
it per id.

**Measured Chroma semantics (probed on a scratch store, chromadb as vendored):**

```
col.delete(ids=['zzz'])   ->  returns {'deleted': 1}   # id does NOT exist
count after               ->  3 (unchanged)
col.delete(ids=['a'])     ->  returns {'deleted': 1}   # id DID exist
count after               ->  2
col.delete(ids=['a'])     ->  no error, count still 2  # re-delete is a no-op
col.delete(ids=['b','nope']) -> deletes 'b', ignores 'nope'
```

Two consequences the implementation must respect:

- **The return value is not a success signal.** `{'deleted': 1}` is reported for an id that
  does not exist and was not deleted. Success must be established by re-reading:
  `collection.get(ids=[chunk_id])` must come back empty. This is what makes the
  partial-failure requirement satisfiable at all.
- **Deleting a nonexistent id does not raise**, so the operation is naturally idempotent and
  a second run is safe and cheap (it finds nothing to select in the first place).

`_get_collection` now rebinds on a changed path (`4ef1de1`), so the command can target a
store explicitly and a test can point it at a tmp path without touching production.

## 4. Q4 — FTS symmetry. **Chroma-only today. Verified per id at run time, never half-deleted.**

Measured: **0 of the 50 orphan chunk_ids appear in `chunks_fts`**, and FTS holds 255 rows
which must be unchanged by this operation. That is consistent with the leak mechanism — the
leak was Chroma-only because `importlib.reload(db_mod)` correctly redirected SQLite while
Chroma's import-time default did not.

The implementation does not hard-code that assumption. Per id: check for an FTS row; if one
exists, delete both stores in the same step and report it. If Chroma succeeds and FTS then
fails, the id is reported with status **`partial`** naming exactly which store still holds
it — never counted as a success, never left undisclosed.

## 5. Q5 — References. **Nothing dangles. But note what this purge is *not* touching.**

Checked every one of the 50 orphan `artifact_id`s against the live DB:

| reference site | hits |
|---|---|
| `messages.content` | **0** |
| `messages.tool_trace` | **0** |
| `chunks_fts.text` | **0** |
| `open_loops.related_artifact_id` | **0** |
| orphan `chunk_id` present in `chunks_fts` | **0** |

These ids are per-test-run `uuid4`s that exist *only* as Chroma metadata. Deleting them
leaves no dangling reference anywhere, and the artifact-card hydration path
(`artifactsFromToolTrace`, `edca6cd`) reads `tool_trace`, which never mentions them.

**The important distinction, stated so it is not discovered later:** the *fabricated*
artifact ids from the confabulation incident — `9b8c7d6e`, `a1b2c3d4`, `e2f3a4b5`,
`b9a8c7d6`, `8f2a3c1d`, `3d9e2b1a`, `4c9d8e7f` — **are** referenced, in eight real
`assistant` messages across conversations `0b6acc0e` and `6428649f`. They are a completely
different set: model-invented ids with **no Chroma chunks at all**. This purge does not
touch them and cannot; deleting these 50 has no effect on them. They are raw lived
experience (the entity really did say those things) and need their own decision — out of
scope here, as the task specifies.

---

## EXACT DIFF SCOPE

One edited module, one new module, one CLI subcommand, one new test file. **No change to the
backfill, retrieval, `_event_text`, schema, or frontend. No deletion of any message.**

### Edited — `tir/memory/chroma.py`
- Add `delete_chunks_by_ids(ids: list[str], chroma_path: str | None = None) -> None` — exact
  id-list delete via `collection.delete(ids=...)`, resolving the path through the existing
  `_resolve_chroma_path`. No behaviour change to anything already there.

### New — `tir/memory/artifact_orphan_purge.py`

```
purge_orphan_artifact_chunks(*, dry_run: bool = True, limit: int | None = None) -> dict
```

1. Enumerate `artifact_document` chunks from Chroma; classify by the §1 selector.
2. `needs_review` (orphan but not `fake-output.png`, or an orphaned *content* chunk) →
   recorded with its title/kind, **never deleted**.
3. Dry run → report each deletable id with `artifact_id`, `title`, `created_at`,
   `chunk_kind`, and a text preview; write nothing.
4. Live → per id: delete the FTS row if one exists, delete from Chroma, then **verify by
   re-reading** (`collection.get(ids=[id])` empty, FTS row gone). Status per id is
   `deleted` / `partial` / `failed`, with the reason.
5. Returns `{"dry_run", "scanned", "orphans_found", "deletable", "needs_review", "deleted",
   "partial", "failed", "entries", "counts_before", "counts_after"}`.

Per-id `try/except`: one failure never aborts the rest, and the summary reports the exact
split. Uses the same lazy `_db()` / `_chroma()` accessors as `artifact_backfill.py`.

### Edited — `tir/admin.py`
- `artifact-orphan-purge` subcommand mirroring `artifact-backfill` (`admin.py:1586-1599`):
  **dry run is the default, `--apply` opts into writing**, plus `--limit N`. Handler,
  printer (per-id lines + before/after counts + a warning if FTS count moved), dispatch
  entry, and the module docstring command list.

### New — `tests/test_artifact_orphan_purge.py`
Replaces `tir.memory.chroma._get_collection` with a fake, per the pattern in
`test_artifact_backfill.py` — so it never constructs a real-path client and cannot trip the
`tests/conftest.py` isolation guard.

---

## Tests (plan)

- orphan `fake-output.png` event chunk → deleted; real artifact chunks untouched
- orphan chunk that is **not** `fake-output.png` → `needs_review`, **not** deleted
- orphaned **content** chunk → `needs_review`, not deleted
- chunk with an `artifacts` row → never selected, whatever its title
- conversation chunk / research chunk → never selected
- dry run deletes nothing (Chroma and FTS byte-identical afterwards)
- second run reports 0 deletable (idempotent)
- an orphan that *does* have an FTS row → both stores cleaned, counts consistent
- FTS delete failing after Chroma succeeded → reported `partial`, not success
- one failing id does not abort the others
- **`delete_chunks_by_ids` success is established by re-reading, not by the
  `{'deleted': n}` return value** — a fake collection that reports `deleted: 1` while
  keeping the record must produce `failed`, not `deleted`
- `--limit` bounds the number processed

## Runbook (mandatory order)

1. **Stop the server**, and no `pytest` during the window.
2. **Back up:** `python -m tir.admin backup` — note the manifest path. This is the only
   rollback; deleted vectors cannot be re-derived.
3. **Record counts:** expect Chroma **305**, FTS **255**.
4. **Dry run:** `python -m tir.admin artifact-orphan-purge` — expect **50 deletable, 0
   needs_review**. Read the id list.
5. **Apply:** `python -m tir.admin artifact-orphan-purge --apply`.
6. **Verify:** Chroma **305 → 255**, event chunks **71 → 21**, FTS **255 unchanged**; re-run
   the dry run → **0 deletable**; `python -m tir.admin memory-audit` clean.
7. **Retrieval spot-check:** `retrieve("rainbow")` and a generated-image prompt phrase still
   return their real artifact chunks — the purge removed noise, not memory.

## Open items for reviewer

1. **Confirm `title == "fake-output.png"` as a mandatory second condition** (recommended),
   with non-matching orphans reported as `needs_review` rather than deleted. The alternative
   — delete on "no row" alone — is simpler but would silently delete a half-completed real
   ingest if one ever existed.
2. **Confirm `needs_review` items are left in place.** They are empty today; this is about
   what happens if the run finds one.
3. **New `delete_chunks_by_ids` helper in `chroma.py`** (recommended) vs. calling
   `collection.delete` directly from the maintenance module. The helper keeps store access
   in the store module, consistent with the rest of `tir/memory/`.
4. **Per-id delete with re-read verification** (recommended) vs. one bulk
   `collection.delete(ids=[...50])`. Bulk is one call, but the measured return value is
   unreliable, so bulk cannot report *which* ids actually went — and the task requires
   accurate partial-failure reporting. 50 ids is cheap.
5. **Go-live wipe interaction:** if the wipe is imminent, this is moot — `go_live_reset`
   empties Chroma anyway. It is still worth doing now because the store is live and these
   chunks are being retrieved into context today.

## Out of scope

- The relevance-floor / retrieval-ranking work.
- Re-running or extending the artifact backfill.
- `routes.py`'s import-time `CHAT_DEBUG_TRACE_PATH` snapshot.
- `OLLAMA_HOST` / `EMBED_MODEL`, and `index_artifact_file`'s exception handling.
- **The fabricated artifact blocks in real `assistant` messages** (`0b6acc0e`, `6428649f`) —
  raw lived experience, referenced by eight real messages, no chunks involved. Separate
  decision, not this task.
- Any change to `_event_text`, retrieval, schema, or frontend.

*Plan only. No code, no commit.*
