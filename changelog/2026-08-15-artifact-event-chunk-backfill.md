# 2026-08-15 — Backfill artifact event chunks to slimmed `_event_text`

## Summary

`PLAN-2026-08-12-imagegen-confabulation-fix.md` slimmed `_event_text` so newly
indexed artifact chunks stop carrying forgeable identity fields (SHA256, stored
path, byte size, filename, seed). That fix was forward-only: chunks written
before it still hold the full pre-slim block and are still retrieved into
context. This adds a maintenance command that re-derives each old-shape chunk's
text from its current `artifacts` row and re-upserts it under the **same
chunk_id** — text and vector change, nothing else.

Implements `PLAN-2026-08-15-artifact-backfill.md` with the four approved
resolutions: orphans are skipped+logged (never touched, never deleted); text is
re-derived from the current `artifacts` row; dry run is the default with
`--apply` to write; proceeding despite the planned go-live wipe. No commit —
Lyle runs the device runbook and commits.

## What changed

- **New `tir/memory/artifact_backfill.py`** —
  `backfill_artifact_event_chunks(*, dry_run=True, limit=None) -> dict`:
  - **Selection is chunk-identity-first, marker-second.** A chunk qualifies only
    if `chunk_id` starts with `artifact_` **and** ends with `_event`, **and**
    `metadata["chunk_kind"] == "event"`, **and**
    `metadata["source_type"] == "artifact_document"` — and only then is it
    classified old-shape by `text.startswith("Artifact source:")`. A
    marker-substring scan alone would have rewritten raw memory: 15 chunks in
    the live store contain `SHA256:`/`Stored path:` and are *not* event chunks
    (conversation chunks where the model pasted a provenance block into chat,
    plus one artifact *content* chunk whose uploaded file body contains the
    text).
  - Re-renders via the shipped `_event_text` and writes via the shipped
    `_store_artifact_chunk` — both imported, neither reimplemented, neither
    modified.
  - **Provenance is read from the store and written straight back**: the Chroma
    metadata dict verbatim, and the FTS `conversation_id` / `user_id` /
    `source_type` / `source_trust` / `created_at` from the existing FTS row.
    `created_at` is never re-derived from the clock — that is the mistake
    `PLAN-2026-07-04` §6 flagged, and doing it here would rewrite provenance.
  - Per-chunk `try/except`: a failure is recorded with its exception and the run
    continues. No silent partial success.
  - Uses lazy `_db()` / `_chroma()` module accessors (the `tir/artifacts/service.py`
    convention) rather than import-time bindings.
- **`tir/admin.py`** — new `artifact-backfill` subcommand (`--apply`, `--limit N`),
  its `cmd_` handler, a `_print_artifact_backfill` reporter that prints old vs.
  new text per chunk and warns if chunk counts move, plus the module docstring
  entry and dispatch wiring.
- **New `tests/test_artifact_backfill.py`** — 13 tests.

## Explicitly verified: the embedding is recomputed from the new text

Checked in the diff rather than assumed from the plan doc, per the task.
`_store_artifact_chunk` (`artifact_indexing.py:160-164`) calls `upsert_chunk`
with `chunk_id`/`text`/`metadata` only — no `embedding` argument — so
`upsert_chunk` (`chroma.py:178-179`) hits `if embedding is None: embedding =
embed_text(text, ...)` and embeds the text it was handed, which is the new text.
The backfill module never reads, stores, or passes an old embedding; there is no
code path by which the old vector survives.

`test_embedding_is_recomputed_from_new_text_not_carried_over` proves it rather
than restating it: the seeded chunk carries a sentinel vector, the fake embedder
returns a **text-length-dependent** vector, and the test asserts `embed_text` was
called exactly once with the new text, that the stored vector equals
`_embedding_for(new_text)`, and that it equals neither the sentinel nor
`_embedding_for(old_text)`.

## Behavior changed

- New admin command. **Nothing runs automatically**; nothing in the request path,
  retrieval, indexing, or the API changed. `_event_text`, `summarize_tool_result_for_model`,
  `_artifact_match`, the schema, and the frontend are all untouched.
- Running `--apply` rewrites stored chunk text and re-embeds those chunks. Chunk
  counts are unchanged by construction (upsert by existing id; a chunk present in
  Chroma but missing from FTS is skipped rather than inserted, since inserting
  would add an FTS row).

## Freshness semantics (approved resolution 2, documented as required)

Text is re-derived from the **current** `artifacts` row, so a `description` or
`metadata_json` edited since original indexing is reflected in the new chunk
text. This is intended — the row is the source of truth — and is a no-op for
every row in the store today (`description` is NULL on all 17 backfillable rows,
and no `metadata_json` has been edited). Stated so a later divergence is not a
surprise.

## Tests / checks run

- `tests/test_artifact_backfill.py` — **13 passed**. Cases: rewrite-in-place with
  metadata and all five FTS provenance columns asserted identical; prompt kept for
  generations; description kept for uploads; `observed_description` kept with its
  uncertainty framing; descriptor-less artifact renders to a single non-empty
  line; already-slim chunk is not a candidate (zero upserts, zero embed calls);
  artifact *content* and *conversation* chunks containing `SHA256:`/`Stored path:`
  are untouched; orphan skipped as `no_artifact_row` and not blanked; chunk with no
  FTS row skipped as `missing_fts_row` rather than partially written; dry run
  writes nothing (document, embedding, and FTS row all byte-identical); second run
  rewrites nothing; one exploding chunk does not abort the others; `--limit`.
- **Full backend suite → 938 passed.**
- **Live dry run against the prod store** (`python -m tir.admin artifact-backfill`,
  read-only): 69 event chunks scanned · 18 already slim · 51 old-shape candidates
  · **17 would rewrite** · 34 skipped `no_artifact_row` · 0 failed · Chroma
  301 → 301 · FTS 253 → 253. Old→new text printed per chunk and eyeballed.

### Correction to the plan's expected dry-run numbers

`PLAN-2026-08-15` §Runbook step 5 says to expect "17 eligible, 48 skipped, 18
unchanged". That double-counts the 14 already-slim orphans (they are both
row-less and already slim), and 17+48+18 = 83 > 69. The command reports disjoint
categories instead — every scanned event chunk is counted exactly once — so the
correct expectation is the line above: **18 already slim, 51 candidates → 17
rewritten + 34 skipped**. Compare against those numbers when running the runbook.

## Known limitations (stated, not silently accepted)

- **Covers 17 of the 51 old-shape chunks in the retrieval pool.** The other 34
  are orphaned test output (`fake-output.png`) with no `artifacts` row, skipped by
  the approved resolution. The symptom in `SESSION_HANDOFF_2026-08-14.md` §1 will
  therefore only partially improve. This is expected, not a defect.
- **The `CHROMA_DIR` test leak is still live and got worse during this work.**
  The full suite run above added **2 more** orphan `fake-output.png` event chunks
  to the production Chroma store (301 → 303 documents, 69 → 71 event chunks, at
  `2026-08-15T22:52`); FTS was unaffected, as the diagnosis predicts. So the
  orphan population grows on every test run. Follow-up task drafted separately.
- **The runbook's count check requires no pytest run during the maintenance
  window** — a concurrent run silently adds Chroma documents, as just measured.
- **`--apply` requires Ollama up** with `nomic-embed-text`; every rewritten chunk
  is re-embedded. A dead Ollama fails each chunk individually (recorded, nothing
  corrupted), but it wastes the window.

## Project Anam alignment check

1. **Name?** No. 2. **Called the entity Anam/Tír?** No. 3. **Personality?** No.
4. **Raw experience preserved?** Yes — conversation chunks are excluded by the
   identity-first selector, and every field dropped from chunk text survives in
   chunk metadata and/or the `artifacts` row (`media_get` unchanged).
5. **Derived artifacts traceable?** Yes — text is re-derived from the source row,
   and the run reports old→new per chunk. 6. **Tool calls recorded?** Unchanged.
7. **Created artifacts remembered?** Yes — no chunk added or removed.
8. **Context construction inspectable?** Improved; the model-visible chunk is now
   the same slim shape for old and new artifacts.
9. **More cumulative?** Neutral. 10. **Anam/entity distinction?** Preserved.
11. **Migration?** No schema change; this is a data re-render, reversible only via
    the backup — hence the mandatory backup step in the runbook.
12. **Tests?** Above. 13. **Core substrate changed unnecessarily?** No — one new
    module and one CLI subcommand; no runtime path touched.
14. **External dependencies/services?** None added (Ollama already required).
15. **Workspace vs. self-modification?** Unaffected.
16. **Legacy renaming avoided?** Yes — `tir/` untouched as a name.

Invariant 4 note: this **does** mutate the store, which is why dry run is the
default, the backup is mandatory, the run prints old vs. new per chunk, and
provenance columns are round-tripped rather than recomputed. A deliberate,
logged, reviewed mutation — not a silent one.

## Follow-up

- Device runbook (Lyle): stop server → backup → dry run → `--apply` → verify
  counts / re-run / retrieval spot-check → live `ANAM_DEBUG_PROMPT=1` check.
- **Next task, ahead of the relevance floor:** fix the `CHROMA_DIR` test leak
  (reload `tir.memory.chroma` in the affected fixtures, or stop binding
  `CHROMA_DIR` as a default argument), then decide on purging the orphan
  `fake-output.png` chunks.
