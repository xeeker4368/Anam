# PLAN — Backfill existing artifact event chunks to slimmed `_event_text`. PLAN ONLY.

**Date:** 2026-08-15 · **Mode:** plan only. **No code, no commit.** Investigation done against the live
store (read-only); implementation only after review.

**Task source:** `ACTIVE_TASK.md` — close the forward-only gap left by
`PLAN-2026-08-12-imagegen-confabulation-fix.md` (`_event_text` slim, commit `2f7e3a6`).

---

## NORTH_STAR check

Re-rendering already-stored chunk **text** through already-shipped logic, from the artifact's own
source row, changing nothing about what the artifact *was*. No new content is authored (Invariant 2),
the raw stream is not deleted (Invariant 4 — every field dropped from the chunk text survives in chunk
metadata and/or the `artifacts` row), and the substrate gains no new mechanism beyond one maintenance
command (Invariant 3). **Aligned.**

One honest caveat: Invariant 4 says *never silently* mutate the store. This task *does* mutate stored
text and re-embeds the vector. That is why dry-run is the default, the backup is mandatory, and the
run reports per-chunk old→new. It is a deliberate, logged, reviewed mutation — not a silent one.

---

## 0. Headline finding — read this before the open questions

**The backfill as scoped fixes 17 of the 51 old-shape chunks that are actually in the retrieval pool.
The other 34 are test-suite pollution written into the *production* Chroma store, and they are still
being written today.**

Live read-only audit, 2026-08-15 (`data/prod/working.db`, `data/prod/chromadb`, server idle):

| store | total chunks | `artifact_*_event` chunks | old shape | new (slim) shape |
|---|---|---|---|---|
| Chroma (`tir_memory`) | 301 | **69** | **51** | 18 |
| FTS (`chunks_fts`) | 253 | **21** | **17** | 4 |

Cross-referencing every Chroma event chunk against the `artifacts` table:

| | count | old shape | has `artifacts` row? |
|---|---|---|---|
| **backfillable** | 21 | **17** | yes |
| **orphaned** | 48 | **34** | **no** |

All 48 orphans have `title = "fake-output.png"`, `media_kind = generated_image`, and prompts like
`"conversational path with no dimensions"` — they are the `FakeBackend` fixture from
`tests/test_image_generation.py:21`. Their `created_at` range is
`2026-06-25T00:56` → **`2026-08-15T00:43`** (today). FTS contains **zero** orphans.

**Root cause of the leak (verified, not inferred):** `tests/test_image_generation.py:44` monkeypatches
`tir.config.CHROMA_DIR`, but `tir/memory/chroma.py:155-161` binds it as a *default argument value*
(`chroma_path: str = CHROMA_DIR`) at import time. The fixture reloads `db_mod` (so SQLite redirects to
`tmp_path` correctly) but only calls `chroma_mod.reset_client()` — it never reloads `chroma_mod`, so
`upsert_chunk` keeps writing to the real `data/prod/chromadb`. Only 2 of the 19 test files that patch
`CHROMA_DIR` (`test_chunking.py:19`, `test_go_live_reset.py:29`) reload the chroma module.

**Consequences for this task:**
1. Scope as written (re-derive from source rows) cannot touch the 34 orphan old-shape chunks — they
   have no source row. Per the "skip + log, never silently blank" requirement they must be skipped.
   So the symptom in `SESSION_HANDOFF_2026-08-14.md` §1 ("old poisoned chunks forced into context on
   essentially every image request") will only be **partially** relieved — 17 of 51.
2. The "same document count before/after" verification is only meaningful if **no pytest run happens
   during the maintenance window**. A concurrent test run silently adds Chroma documents.
3. This needs a reviewer decision — **§Open item 1**.

---

## 1. Q1 — Data completeness. **All 17 backfillable rows are complete. 7 render to a single line.**

`_event_text` (`tir/memory/artifact_indexing.py:74-127`) needs exactly four inputs: `title`,
`artifact_id`, `description`, `media_metadata`. Re-derivation source per input:

| input | source | note |
|---|---|---|
| `title` | `artifacts.title` (NOT NULL) | present on 17/17 |
| `artifact_id` | `artifacts.artifact_id` (PK) | present on 17/17 |
| `description` | `artifacts.description` | **NULL on 17/17** (see below) |
| `media_metadata` | `media_indexing_metadata(json.loads(artifacts.metadata_json))` | `metadata_json` non-NULL on 17/17 |

`media_indexing_metadata` (`tir/artifacts/media.py:235-247`) is the same filter applied at original
index time (`tir/artifacts/ingestion.py:255`), so re-applying it to the stored `metadata_json`
reproduces the original `media_metadata` dict exactly. No schema field used by `_event_text` was added
after any of these rows were created — `prompt`, `negative_prompt`, `media_kind`,
`observed_description`, `uncertainty_label` are all part of `MEDIA_PROVENANCE_FIELDS`
(`media.py:28-50`), which predates every row here.

**Rendered outcome for the 17:**

| group | n | new text |
|---|---|---|
| generated images with `prompt` | 10 | `Artifact: {title} (id: {id})` + `Prompt: {prompt}` |
| text uploads, no prompt/description | 6 | **`Artifact: {title} (id: {id})` only** |
| one screenshot (`537bd3b7`, image/png), no prompt/description/observed_description | 1 | **title+id only** |

**No row is missing a field it once had** — the 7 single-line results are not data loss, they are what
the current indexer would produce for those same inputs today. `description` is NULL on all 17 because
none was supplied at upload; `observed_description` is absent from all 51 old chunks' metadata (no
vision captions exist yet). The 6 text uploads keep their real content in their
`artifact_{id}_chunk_{n}` content chunks, untouched. The screenshot loses no *semantic* content
because it never had any — its old 458-char block was pure forgeable identity — and it stays matchable
by title/filename/id through `_artifact_match`'s metadata path (§4).

**Skip-and-log set (no source row, cannot be re-derived):** the 48 orphans. Reported by chunk_id with
reason `no_artifact_row`, never blanked.

**Not in the population at all:** 9 `artifacts` rows (1 journal, 8 research_note) have no `_event`
chunk — they were created via `create_artifact_file`, not `ingest_artifact_file`, and never went
through `index_artifact_file`. Correctly untouched; the backfill iterates chunks that exist, not rows.

**Freshness note (deliberate):** re-deriving from the row means the new text reflects the *current*
`description`/`metadata_json`, not the values at index time. Today those are identical for all 17
(nothing has been edited), so this run is a pure shape change. Stated so it isn't a surprise later.

---

## 2. Q2 — Idempotency of the overwrite. **Both stores overwrite in place. Verified in code.**

- **Chroma — `tir/memory/chroma.py:155-191`.** `upsert_chunk` calls
  `collection.upsert(ids=[chunk_id], documents=[text], embeddings=[embedding], metadatas=[metadata])`.
  Chroma's `upsert` replaces document, embedding, and metadata for an existing id in place — one
  record per id, no duplicate, no orphaned old vector (the HNSW entry for that id is replaced, not
  appended). **The embedding is recomputed** (`upsert_chunk` embeds when `embedding is None`,
  `chroma.py:178-179`) — this is required and intended, since a stale vector for new text would be
  worse than doing nothing. `_validate_embedding_dimension` (`chroma.py:181`) fails the write if the
  embedding model ever returns a non-768 vector, so a wrong-model run aborts rather than corrupts.
- **FTS — `tir/memory/db.py:882-903`.** `upsert_chunk_fts` explicitly does
  `DELETE FROM main.chunks_fts WHERE chunk_id = ?` then `INSERT`, in one transaction, with the comment
  "FTS5 doesn't support UPSERT". Exactly one row per chunk_id survives. The FTS5 rowid advances (the
  shadow tables `chunks_fts_data`/`chunks_fts_idx` grow slightly); nothing reads rowid, and BM25
  ranking is unaffected.
- **Re-running is safe and cheap:** after a run the text starts with `Artifact: `, so the selector
  (§3) no longer matches it and it is not re-embedded. A partially-migrated store converges.

**Metadata and provenance must be passed back unchanged — this is a design requirement, not an
option.** `upsert_chunk` needs a full `metadata` dict and `upsert_chunk_fts` needs
`conversation_id / user_id / source_type / source_trust / created_at`. The implementation must read
those from the **existing** records (Chroma `collection.get`, and the existing `chunks_fts` row) and
write them straight back. Re-deriving `created_at` from `datetime.now()` — the mistake called out in
`PLAN-2026-07-04` §4/§6 — would rewrite provenance and violate Invariant 4. The plan's contract is
literally *text and vector change, nothing else*.

---

## 3. Q3 — Detection. **Two-part selector: chunk identity first, then shape marker.**

A marker-substring scan alone is **unsafe** — measured, not assumed. 15 chunks in the live Chroma
store contain `SHA256:` or `Stored path:` and are **not** artifact event chunks:

- `4a749c18-…_chunk_1`, `0b6acc0e-…_chunk_3_0`, `0b6acc0e-…_chunk_3_1`, `0b6acc0e-…_chunk_4`, … —
  **conversation chunks** (raw lived experience; the model pasted a provenance block into chat).
- `artifact_d180156d-…_chunk_0` — an artifact **content** chunk (the uploaded file's own text
  contains the marker).

Touching any of those would rewrite raw memory. So:

**Selector (all must hold):**
1. `chunk_id.startswith("artifact_")` **and** `chunk_id.endswith("_event")`
2. `metadata["chunk_kind"] == "event"` and `metadata["source_type"] == "artifact_document"`
3. `text.startswith("Artifact source:")` — the old shape's unconditional first line
   (`_event_text` pre-slim: `f"Artifact source: {title}"`, always emitted)

**Measured discrimination:** old shape → `Artifact source:` on 51/51; new shape → `Artifact: ` on
18/18; zero chunks in either store fall outside those two prefixes. Condition 3 alone would also catch
artifact *content* chunks (whose header is also `Artifact source: {title}`, `artifact_indexing.py:139`)
— which is exactly why conditions 1–2 come first.

**Enumeration source:** Chroma is authoritative for the population (69 event chunks vs FTS's 21) —
`collection.get(include=["documents","metadatas"])` filtered client-side, or
`where={"chunk_kind": "event"}`. FTS is then updated for whichever of those ids has an FTS row; ids
with no FTS row (the 48 orphans, if ever brought in scope) are reported, not inserted.

---

## 4. Q4 — Scope confirmation. **Only `artifact_*_event` uses this text shape. Nothing else is touched.**

- `_event_text` has exactly one caller: `index_artifact_file` (`artifact_indexing.py:231`), writing
  chunk id `artifact_{artifact_id}_event` with `chunk_kind="event"`.
- Live `chunk_kind` census (Chroma, 301 docs): `event` 69 · `content` 91 · `research_content` 9 ·
  `journal_content` 1 · absent 131 (conversation chunks). Only `event` uses this shape.
- Artifact **content** chunks use `_content_text_header` (`artifact_indexing.py:130-146`) — a different
  shape, excluded by the selector.
- **Consumer safety:** `_artifact_match` (`tir/memory/retrieval.py:122-157`) reads `artifact_id`,
  `filename`, and `title` metadata-first, falling back to `_artifact_header_value(text, …)` only when
  metadata is absent. Measured on the 51 old chunks: `artifact_id` 51/51, `title` 51/51, `filename`
  51/51 present in metadata. So the text-parse fallback is never reached for these chunks and slimming
  cannot regress artifact matching. (Same conclusion the 08-12 plan reached for forward writes,
  re-verified here against the actual stored records.)
- No other reader parses event-block body fields.

---

## EXACT DIFF SCOPE

Three new files, one edited file. **No change to `_event_text`, `_store_artifact_chunk`,
`index_artifact_file`, `summarize_tool_result_for_model`, retrieval, schema, or frontend.**

### New — `tir/memory/artifact_backfill.py`

```
backfill_artifact_event_chunks(*, dry_run: bool = True, limit: int | None = None) -> dict
```

1. Enumerate candidate chunks from Chroma via the §3 selector.
2. For each, load `artifacts` row by `artifact_id`. Missing → record
   `{chunk_id, status: "skipped", reason: "no_artifact_row"}`, continue.
3. Rebuild `new_text = _event_text(title=row["title"], artifact_id=…, description=row["description"],
   media_metadata=media_indexing_metadata(json.loads(row["metadata_json"] or "{}")))` — imported, not
   reimplemented.
4. `new_text == old_text` → `status: "unchanged"`, no write.
5. `dry_run` → record `{chunk_id, old_text, new_text, old_len, new_len}`, write nothing.
6. Live → read the existing FTS row for its `conversation_id/user_id/source_type/source_trust/
   created_at`; call `_store_artifact_chunk` with the **existing** Chroma metadata dict and those
   **existing** FTS provenance values, new text only. Per-chunk `try/except`; a failure is recorded
   (`status: "failed"`, exception text) and the loop continues — one bad chunk never aborts the run.
7. Return `{"scanned", "eligible", "rewritten", "unchanged", "skipped", "failed", "entries": [...],
   "counts_before": {...}, "counts_after": {...}}`, with counts from `get_collection_count()` and
   `SELECT COUNT(*) FROM chunks_fts`.

### Edited — `tir/admin.py`

One subparser next to `memory-repair` (`admin.py:1513`) plus its handler:

```
python -m tir.admin artifact-backfill            # dry run (default), prints old→new per chunk
python -m tir.admin artifact-backfill --apply    # live write
python -m tir.admin artifact-backfill --limit N
```

*Deviation flagged:* `memory-repair` uses an opt-in `--dry-run` flag. Here dry-run is the **default**
and `--apply` is the opt-in, per the ACTIVE_TASK requirement ("dry-run mode is the default and is
required"). Called out so the inconsistency is a decision, not an accident.

### New — `tests/test_artifact_backfill.py`

- old-shape chunk with a full artifacts row → rewritten to slim text; **metadata dict and FTS
  `created_at`/`user_id`/`source_type`/`source_trust` byte-identical before and after**
- generated image → `Prompt:` retained; upload with a description → `Description:` retained
- descriptor-less upload → single-line output, no crash, non-empty text (embed precondition holds)
- already-slim chunk → `unchanged`, zero writes, zero embed calls
- artifact **content** chunk and a **conversation** chunk both containing `SHA256:` → untouched
- event chunk with no artifacts row → `skipped`/`no_artifact_row`, not blanked
- dry-run writes nothing (assert Chroma + FTS byte-identical after)
- idempotency: run twice → second run reports 0 rewritten
- one failing chunk does not abort the others
- **the new test file must reload `tir.memory.chroma`, not just `reset_client()`** (§0), so it does not
  add to the leak it is documenting

### Not created

No migration (no schema change). No changelog until the patch is approved and implemented.

---

## Operational runbook (mandatory order)

1. **Stop the server**, and ensure **no pytest run** is in flight or starts during the window (§0 —
   tests write to prod Chroma; a concurrent run breaks the count invariant).
2. **Confirm Ollama is up** with `nomic-embed-text` — every rewritten chunk is re-embedded. A dead
   Ollama fails every chunk (recorded, nothing corrupted) — but check first.
3. **Back up:** `python -m tir.admin backup` → note the manifest path. Covers `working.db` + Chroma.
   Not git-recoverable; this is the only rollback.
4. **Record counts:** Chroma `get_collection_count()`, `SELECT COUNT(*) FROM chunks_fts`
   (expect **301** and **253** today).
5. **Dry run:** `python -m tir.admin artifact-backfill` — review every old→new pair. Expect
   **17 eligible, 48 skipped (`no_artifact_row`), 18 unchanged**.
6. **Apply:** `python -m tir.admin artifact-backfill --apply`.
7. **Verify:** counts unchanged (301 / 253); re-run the dry run → **0 eligible**; spot-check one
   rewritten chunk's metadata and FTS `created_at` against the pre-run capture; `retrieve()` on a
   distinctive prompt phrase from one of the 10 generated images still returns that chunk.
8. **Live check:** fresh conversation, `ANAM_DEBUG_PROMPT=1`, ask a question that retrieves a
   backfilled artifact → confirm the assembled prompt shows the slim block (no SHA/path).
   **Expect the symptom to persist in part** until the 34 orphans are dealt with (§Open item 1).

---

## Open items for reviewer

1. **The 34 orphan old-shape chunks (the majority of the problem) — how are they handled?**
   - **(A) Skip + log only** — literal ACTIVE_TASK scope. Safe, but leaves 34/51 poisoned chunks live
     and the observed symptom largely unchanged.
   - **(B) Also re-render orphans from their own Chroma metadata** (which carries `title`,
     `artifact_id`, `prompt`, `media_kind` — complete for all 48). Covers all 51 in one pass, and for
     the 17 with rows it produces byte-identical output to (A) today (verified: `description` is NULL
     on all 17). Cost: the "re-derive from source data" contract weakens to "re-derive from the chunk's
     own metadata", and it preserves 48 junk test records as tidier junk.
   - **(C) — recommended.** Do (A) here, and open an immediate separate task to (i) fix the
     `CHROMA_DIR` test leak (reload `tir.memory.chroma` in the affected fixtures, or stop binding
     `CHROMA_DIR` as a default argument) and (ii) **delete** all 48 `fake-output.png` orphan chunks.
     They are not memory — they are test output that was never anyone's experience, so deleting them
     is correct where re-rendering them is not. Deletion is out of this task's stated scope, so it
     needs its own approval; sequencing (i) before (ii) stops the store refilling.
2. **Confirm the freshness semantics** (§1): re-deriving from the current `artifacts` row means a
   later-edited `description`/`metadata_json` would be reflected in the chunk text. No-op today. Accept?
3. **Confirm the `--apply` / default-dry-run inversion** vs. `memory-repair`'s `--dry-run` convention.
4. **Go-live reset interaction:** if a full wipe is still planned at launch, this data disappears
   anyway. The backfill is still worth doing — the poisoning is active *now* — but if the wipe is
   imminent, that changes the priority relative to the test-leak fix (which survives the wipe).

---

## Out of scope (restated)

- No change to retrieval ranking, `_artifact_match`, or the relevance-floor problem.
- No schema or migration changes.
- No change to `_event_text`, `summarize_tool_result_for_model`, or anything from the 08-12 fix.
- No frontend changes.
- No deletion of any chunk (unless Open item 1(C) is separately approved).
- The `CHROMA_DIR` test leak is **reported here, not fixed here**.

*Plan only. No code, no commit.*
