# Backup and Restore Foundation

## Summary

Added explicit admin backup and restore tooling for Project Anam runtime state.

## Files Changed

- `tir/config.py`
- `tir/ops/__init__.py`
- `tir/ops/backup.py`
- `tir/admin.py`
- `tests/test_backup_restore.py`
- `changelog/2026-05-05-backup-restore-foundation.md`

## Behavior Changed

- Added `BACKUP_DIR`.
- Added `create_backup(...)` for timestamped runtime backups.
- Added `restore_backup(...)` with manifest validation, dry-run support, force requirement, and automatic pre-restore safety backup.
- Added admin commands:
  - `backup`
  - `restore <backup_path> --dry-run`
  - `restore <backup_path> --force`
- Backups include configured SQLite DBs, Chroma directory when present, and workspace directory when present.
- Backups skip `.env`, secrets, logs, caches, and unrelated repo files.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_backup_restore.py -v`
- `.pyanam/bin/python -m pytest tests/test_admin.py tests/test_memory_audit.py -v`
- `.pyanam/bin/python -m pytest tests/test_db.py tests/test_chunking.py -v`
- `git diff --check`

## Known Limitations

- Restore should be run with the app stopped.
- Chroma directory backup is filesystem-copy based and can be inconsistent if Chroma is actively writing.
- Backups are local uncompressed directories in v1.
- Per-file hashes for copied directories are not recorded in v1.

## Follow-Up Work

- Add compression/export options if backup size becomes an issue.
- Add scheduled backup policy only after manual backup/restore has runtime history.
- Consider richer restore verification after restore completes.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not call the entity Anam or Tír.
- Does not assign personality.
- Preserves raw experience as primary.
- Protects working/archive memory state, vector retrieval state, and workspace artifacts.
- Does not change DB schema, memory architecture, UI, API routes, or autonomy behavior.
