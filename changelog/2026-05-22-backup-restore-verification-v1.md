# Backup / Restore Verification v1

## Summary

Added isolated backup restore verification for Project Anam runtime state. The new admin command restores a selected backup into a separate target directory and verifies databases, Chroma/workspace presence, governance files, and manifest hashes without mutating active runtime paths.

## Files Changed

- `tir/ops/backup.py`
- `tir/admin.py`
- `tests/test_backup_restore.py`
- `ROADMAP.md`
- `ACTIVE_TASK.md`
- `changelog/2026-05-22-backup-restore-verification-v1.md`

## Behavior Changed

- Added `backup-restore-verify`.
- Supports `--backup-path <backup_path>` or `--latest`.
- Requires `--target-dir <target_dir>`.
- Rejects non-empty target directories unless `--overwrite-target` is provided.
- Restores into an isolated verification layout only:
  - `target_dir/data/prod/working.db`
  - `target_dir/data/prod/archive.db`
  - `target_dir/data/prod/chromadb`
  - `target_dir/workspace`
  - `target_dir/governance`
- Opens restored databases read-only and reports key table counts plus working schema versions.
- Verifies existing manifest SHA-256 entries for database and governance files.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_backup_restore.py -v`
- `.pyanam/bin/python -m pytest tests/test_admin.py -v`
- `.pyanam/bin/python -m pytest`
- `git diff --check`

## Known Limitations

- Directory-level recursive SHA-256 manifests are not implemented in v1.
- Chroma verification checks filesystem presence/readability only; it does not open a Chroma client.
- Verification does not start the live server, call Ollama, call Moltbook, or call web tools.

## Follow-Up Work

- Consider a future backup manifest v2 with recursive directory file hashes.
- Add an operator pre-go-live runbook that pairs backup verification with go-live wipe/reset steps.
- Consider a scheduled backup verification reminder once bounded scheduler work exists.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign personality, values, avatar, or identity.
- Preserved raw continuity state as primary.
- Kept backup verification separate from active runtime mutation.
- Did not change DB schema, Chroma schema, retrieval, research behavior, prompts, guidance files, `soul.md`, model config, UI, Moltbook/web behavior, or auth/user mode.
