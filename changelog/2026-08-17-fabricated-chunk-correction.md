# 2026-08-17 — Correct retrievable chunks carrying pre-gate fabricated artifact blocks

## Summary

11 assistant messages across conversations `0b6acc0e` and `6428649f`, all pre-dating the
fabrication gate (`9b84583`, 2026-08-14), state fabricated artifact-ID provenance blocks
as fact. They are live in retrieval and have been served into real prompts. This adds a
one-off script that re-renders the derived chunks with those fabrications removed, while
**never writing to `messages`** — source row is truth, derived text gets re-rendered, the
same principle as the 2026-08-15 artifact backfill.

Implements `PLAN-2026-08-17-fabrication-chunk-correction-FINAL.md`. **The correction has
not been applied to production** — dry run only. No commit.

## What changed

- **New `scripts/correct_fabricated_chunks.py`** — dry-run by default, `--apply` to write.
  Keyed strictly to 11 hardcoded full message IDs; never re-scans chunk text for gate
  markers (see below for why that distinction is load-bearing).
- **`tir/memory/chunking.py`** — one optional `created_at: str | None = None` parameter on
  `_store_chunk` and `_store_chunk_group`, passed through to both Chroma metadata and the
  FTS row. `None` (every existing caller) stamps `datetime.now()` exactly as before. This
  is the only change to that file.
- **New `tests/test_fabricated_chunk_correction.py`** — 13 tests.

## Why correction is message-ID-scoped, not a text scan

Three chunks contain a **real** artifact block beside the fabricated one — all in
`6428649f`: `_chunk_3_0` (real `0a2a95f5`), `_chunk_4` (real `104fb896`), `_chunk_9`
(real `0a2a95f5`). And `_chunk_3_0` additionally holds three deliberate `deadbeef` /
`anam_generated_99999_.png` test-scaffolding messages (two of them **user** messages)
that match the gate's markers but are explicitly out of scope.

A blanket `[Artifact source:` scan-and-strip at chunk-text level would have destroyed real
provenance in three chunks and deleted intentional test data in one. The script therefore
keys off the 11 known IDs and nothing else.

## Delivery shape

`scripts/` is the established location for standalone tools (shebang + docstring, as in
`export_db_schema.py`, `extract_prompt_inventory.py`, `probe.py`). **All three existing
scripts are read-only**, so a mutating script is new here; the filename and the first line
of the docstring both say so explicitly rather than relying on the reader to notice.

## `created_at` preservation

`_store_chunk` previously stamped `datetime.now()` unconditionally, with no way to pass a
value — verified by execution, not by reading. Since `created_at` is rendered to the model
as `[Conversation — {ts}]`, restamping would present a June/August exchange as freshly
created: a smaller, subtler dishonesty introduced by a task whose whole purpose is
removing dishonesty from memory. The new parameter lets the script pass each group's
existing timestamp through.

**One detail the plan did not anticipate:** the three collapsing groups have *two*
sub-units stamped microseconds apart (e.g. `…10.125620` and `…10.242163`). Merging them
into one chunk forces a choice. The script takes the **earliest** — the moment that group's
write began — and reports it per group in the dry run.

## Correction of the plan's idempotency criterion

The plan's minimum bar asked for "running the correction twice is idempotent — second run
finds nothing left to correct." **That is not achievable, and should not be.** Because
`messages` rows are never modified, a re-run re-reads the same fabricated source and
corrects it again; it will always report 11 messages corrected and 8 groups written.

The property that actually holds is **convergence**, which is stronger where it matters and
was verified end-to-end against an isolated copy of the real store: applying twice left the
store **byte-identical** (Chroma documents, FTS rows, and `created_at` all unchanged
between run 1 and run 2). A test asserts the pure-function half of this; the changelog
records the end-to-end half.

## Verification

**Mechanism**, executed against an isolated copy of the real store before implementation:
`_store_chunk_group` accepts a modified in-memory message list; `messages` rows confirmed
untouched by direct re-read after write; Chroma text == FTS text; metadata, `source_trust`,
`user_id`, `chunk_index` all carried forward; sub-unit collapse produced **zero orphaned
sub-unit IDs** in either store.

**Dry run against production** (read-only, counts unchanged at 255/255): 8 turn-groups
targeted, **11 messages corrected**, 3 sub-unit collapses detected and reported, all
`created_at` values preserved. Programmatic safety check over the dry-run output:

| group | fabricated IDs in new text | real blocks kept | deadbeef scaffolding |
|---|---|---|---|
| `0b6acc0e` grp 3 | 0 | 1/1 | — |
| `0b6acc0e` grp 4, 5, 6 | 0 | n/a | — |
| `6428649f` grp 3 | 0 | **2/2** | **3 → 3 intact** |
| `6428649f` grp 4 | 0 | **1/1** | — |
| `6428649f` grp 8 | 0 | n/a | — |
| `6428649f` grp 9 | 0 | **1/1** | — |

Truncation sizes (prose preserved, block removed): `40d84295` 2954→1765, `4f94ecec`
1386→205, `032481af` 1418→237, `41b0ef35` 1290→249, `9b4c2c90` 1237→451, `d8fe5308`
2382→1198, `373654e4` 1964→686.

**Convergence**, isolated copy: run 1 wrote 8 groups (255 → **252** documents, matching the
predicted 11 records → 8), run 2 produced byte-identical state.

**Tests: 13 passed. Full suite: 992 passed** (979 + 13). Production store untouched
throughout (255 Chroma / 255 FTS).

## Safety behaviour worth noting

`_corrected_content` **refuses rather than guesses** in three cases: a `truncate` message
with no block, a `truncate` message that would be emptied (i.e. misclassified and should
be `replace`), and a `replace` message the gate would not have caught. Each raises with a
specific message. Given this blanks content in the entity's memory, failing loudly on a
classification mismatch is preferable to silently producing an empty or wrongly-substituted
chunk. Three tests cover these paths.

## Known limitations

- **Not yet applied to production.** Backup → dry run → `--apply` → verify remains to be
  run; the runbook is in the plan.
- **Three fabrication-free chunks lose their standalone IDs** — `0b6acc0e…_chunk_3_0`
  (which holds a real artifact block), `6428649f…_chunk_3_1`, `6428649f…_chunk_8_0`. Their
  content is preserved inside the merged chunk; only the ID disappears. Nothing reads
  chunk IDs outside write/delete targeting and debug display, so this is cosmetic — but it
  is a real consequence of group-level regeneration, and the dry run lists all three.
- **`0b6acc0e…_chunk_6` contains the most sensitive personal content in the store** beside
  two fabrications. The correction does not touch that content, but any human reviewing the
  dry-run diff will see it. Reviewing on-device rather than pasting the output elsewhere is
  the sensible handling.
- **The script is deliberately not reusable.** Hardcoded to a closed population of 11. If
  contamination is ever found elsewhere, this is a template, not a tool.
- **`chunking.py` is core substrate.** The change is one optional parameter with a
  default-preserving path and a regression test for existing callers, but it is a core file
  and warrants that framing.

## Project Anam alignment check

1. **Name?** No. 2. **Called the entity Anam/Tír?** No. 3. **Personality?** No.
4. **Raw experience preserved?** Yes, and this is the crux: `messages` — the actual
   historical record, including the entity's fabrications — is never written to under any
   code path. Only the derived retrieval text changes. The entity's history still contains
   what it said; its *memory* stops asserting those artifacts exist.
5. **Derived artifacts traceable?** Yes — derived text is re-rendered from the immutable
   source, and the dry run prints old → new per record. 6. **Tool calls recorded?** Unchanged.
7. **Created artifacts remembered?** Yes — every real artifact block is preserved
   byte-identical, verified per chunk. 8. **Context construction inspectable?** Improved:
   retrieval stops surfacing eleven false provenance blocks as fact.
9. **More cumulative?** Yes — future recall is no longer contaminated by invented artifacts.
10. **Anam/entity distinction?** Preserved. 11. **Migration?** No schema change; a derived-data
    re-render, recoverable from backup. 12. **Tests?** Above. 13. **Core substrate changed
    unnecessarily?** One optional parameter in `chunking.py`, justified above and
    default-preserving. 14. **External dependencies?** None. 15. **Workspace vs.
    self-modification?** Unaffected. 16. **Legacy renaming avoided?** Yes.

Invariant 4 note: this is a deliberate, reviewed mutation of derived text with the raw
stream held immutable — the distinction the invariant exists to protect. The entity keeps
the record of having fabricated; it loses only the false claim presented to it as memory.

## Follow-up

- Runbook (Lyle): stop server → backup → dry run → eyeball the three real+fake chunks and
  the deadbeef scaffolding → `--apply` → verify → live retrieval spot-check.
- Still open and tracked separately: widening the fabrication gate's marker set (the 08-16
  session measured 1-of-5 detection on real traffic), and `memory_search`'s empty-result
  wording.
