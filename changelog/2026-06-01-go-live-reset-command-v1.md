# Go-Live Reset Command v1

Date: 2026-06-01

## Summary

Implements the deliberate, destructive go-live reset described in
`docs/GO_LIVE_RESET_RUNBOOK.md`: a gated admin command that wipes contaminated
pre-live runtime memory/experience and starts the substrate fresh, while
preserving identity, user-mapping/config, schema, governance, config, code, and
backups. Chroma and the FTS index are emptied to EMPTY (they refill naturally
post-launch); they are NOT rebuilt from the archive, which is wiped too.

Logic lives in a new module `tir/ops/go_live_reset.py` (mirroring
`tir/ops/backup.py`), with a thin `go-live-reset` CLI wrapper in
`tir/admin.py`. A reusable "empty" seam was added to `tir/memory/chroma.py` for
a future empty + repopulate recoverability tool; that tool is not built here.

## Files changed

- `tir/ops/go_live_reset.py` (new) — reset logic, three entry points
  (`plan_go_live_reset`, `execute_go_live_reset`, `verify_clean`),
  `GoLiveResetError`, the table-classification constants, the classification
  guard, and the gated destructive sequence.
- `tir/memory/chroma.py` — added `COLLECTION_NAME` / `COLLECTION_METADATA`
  constants (shared by the live accessor and the new helper) and
  `empty_collection()`, which deletes + recreates the `tir_memory` collection
  empty and resets the cached client. The hot-path `_get_collection` now
  references the shared constants (identical values; no behavior change).
- `tir/admin.py` — imported the reset entry points, added `cmd_go_live_reset`,
  the `go-live-reset` subparser (`--dry-run` | `--verify-clean`,
  `--confirm-go-live-reset`, `--typed-confirm`), and registered the command.
- `tests/test_go_live_reset.py` (new) — 7 tests covering dry-run, destructive
  wipe/preserve, verify-clean pass/fail, phrase mismatch, backup-verify-failure
  abort, confirm-flag requirement, and the unclassified-table guard.

## Behavior changed

New `go-live-reset` admin command with three modes:

- `--dry-run`: reports per-table row counts, Chroma count, per-dir workspace
  file counts, and the preserve snapshot. No backup, no mutation.
- default (destructive): runs the gated sequence below.
- `--verify-clean`: asserts wiped tables empty, `chunks_fts` empty, Chroma
  empty, workspace dirs empty, users present, `schema_versions` non-empty;
  reports pass/fail (exit 1 on fail).

Destructive safety-gate sequence (abort on any failure; no wipe before gate 4):

1. arm switch — `--confirm-go-live-reset` required (no backup created
   otherwise);
2. fresh backup via `create_backup` (the rollback artifact);
3. `verify_backup_restore` into an isolated target — abort unless it passes;
4. typed confirmation must equal exactly `WIPE PRE-LIVE RUNTIME STATE`;
5. wipe inside a transaction under `PRAGMA defer_foreign_keys`; empty
   Chroma/FTS; clear workspace runtime dirs;
6. write an audit file recording timestamp, backup path (flagged as the
   rollback artifact), verify target/result, per-target wiped counts, Chroma
   count, workspace counts, and the preserved-user/schema snapshot to
   `backups/go-live-reset-audit/`.

Wipe/preserve classification (every table in both DBs classified; an
unclassified table aborts the reset via the classification guard):

- WIPE working.db: `conversations`, `messages`, `summaries`, `documents`,
  `artifacts`, `open_loops`, `review_items`, `tasks`, `feedback_records`,
  `diagnostic_issues`, `overnight_runs`, `behavioral_guidance_proposals`,
  `chunks_fts` (FTS via `DELETE FROM chunks_fts`; FTS5 shadow tables cleared
  through it, never touched directly).
- WIPE archive.db: `messages`.
- WIPE Chroma: `tir_memory` emptied (delete + recreate empty).
- WIPE workspace contents (dir kept): `research/`, `research/source-traces/`,
  `journals/`, `uploads/`, `generated/`.
- PRESERVE working.db: `users`, `channel_identifiers`, `schema_versions`.
- PRESERVE archive.db: `users` (archive has no `schema_versions` table).
- On preserved rows, only activity is cleared: `users.last_seen_at` → NULL.
  Confirmed there are no other activity/timestamp columns on `users` or
  `channel_identifiers` (`created_at` is identity provenance; `verified` /
  `auth_material` are config/credential state).

`behavioral_guidance_proposals` are wiped (pre-live activity-derived proposals);
the applied governance file `BEHAVIORAL_GUIDANCE.md` on disk is preserved.

## Tests/checks run

- New tests: `pytest tests/test_go_live_reset.py -q` → 7 passed (includes a
  self-referential `artifacts.revision_of` row to exercise
  `defer_foreign_keys`, and a non-wiped `workspace/writing/` file to prove
  preservation).
- Full suite: `python -m pytest -q` → 845 passed (838 prior + 7 new), 133
  pre-existing deprecation warnings (chromadb / FastAPI `on_event`), unrelated.
- `git diff --check` → clean.
- CLI smoke test: `python -m tir.admin go-live-reset --help` wires correctly.

## Known limitations

- The gate-1 backup is created automatically by the command (rather than the
  runbook's operator-supplied `--backup-path`/`--backup-verified`); this is
  strictly safer (backup cannot be skipped). No backup pruning/rotation exists
  in the codebase, so the rollback backup is durable.
- `verify_clean` requires at least one user present (`users` preserved); on a
  truly userless install it would report a failure for the empty users table.
- The destructive command should be run with the app stopped (operator
  procedure in the runbook); the command does not itself stop the backend.

## Follow-up work

- Build the empty + repopulate recoverability tool that reuses
  `chroma.empty_collection` (seam left, tool not built).
- Out of scope here: rebuild-Chroma/FTS-from-archive, embedding-model
  migration / re-embed, automating the reset, and adding users.
- The runbook's "Deferred / does not implement go-live-reset" section is now
  partly superseded; a doc-only follow-up could mark it implemented (left
  untouched here to keep this patch to the approved scope).

## Project Anam alignment check

1. Assign the entity a name? No.
2. Call the entity Anam or Tír? No.
3. Assign personality instead of observing behavior? No.
4. Preserve raw experience? This deliberately wipes pre-live raw experience as
   the defining go-live act (operator-gated, backed up + verified first); it
   does not alter how raw experience is captured going forward.
5. Are derived artifacts traceable? Yes — the audit file records backup path,
   verify result, and per-target counts.
6. Are tool calls recorded? Unaffected (the wipe clears pre-live traces by
   design).
7. Are created artifacts remembered? Pre-live artifacts are intentionally
   wiped; post-launch capture is unchanged.
8. Is context construction inspectable? Yes — dry-run + audit make the wipe
   fully inspectable before and after.
9. Does this make autonomy more cumulative? Neutral — it sets the clean launch
   baseline from which cumulative continuity begins.
10. Preserve the Anam/entity distinction? Yes.
11. Require a migration? No schema change. New runtime audit artifacts under
    `backups/go-live-reset-audit/`; no DB schema/migration changes.
12. Tests run? Full suite (845 passed) + new module tests + `git diff --check`.
13. Change core substrate behavior unnecessarily? No — additive command;
    chroma hot path unchanged (constants only).
14. Add external dependencies/services? No.
15. Preserve workspace vs self-modification distinction? Yes — only runtime
    output dirs are cleared; no self-modification surface touched.
16. Avoid casual legacy package renaming? Yes — no `tir/` → `anam/` rename.
