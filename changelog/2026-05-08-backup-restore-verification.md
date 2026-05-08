# Backup / Restore Verification and Governance File Backup Hardening

## Summary
- Added governance file backup/restore support for an explicit allowlist of project guidance/state files.
- Added restore verification coverage for governance files, review queue items, behavioral guidance proposals, clean temp runtime restore, and workspace restore.
- Updated admin backup output to show governance file backup status.

## Files Changed
- `tir/ops/backup.py`
- `tir/admin.py`
- `tests/test_backup_restore.py`
- `changelog/2026-05-08-backup-restore-verification.md`

## Behavior Changed
- Backups now include a `governance_files` manifest section.
- Present allowlisted governance files are copied to `governance/` with byte size and SHA-256 hash metadata.
- Missing allowlisted governance files are recorded as `exists:false` and are not fatal.
- Restore dry-runs now report governance files.
- Forced restores restore governance files only when they are present in the backup manifest.
- Pre-restore safety backups continue to run before overwriting runtime state or governance files.

## Tests/Checks Run
- `.pyanam/bin/python -m pytest tests/test_backup_restore.py -v`
- `.pyanam/bin/python -m pytest tests/test_memory_audit.py -v`
- `.pyanam/bin/python -m pytest tests/test_behavioral_guidance.py tests/test_review_queue.py -v`
- `git diff --check`

## Known Limitations
- Chroma directory backup remains filesystem-copy based and should be treated as best-effort while the app is running.
- Restore should still be run with the app stopped.
- Governance file restoration is all-or-nothing per present manifest entry; there is no selective restore UI or CLI flag yet.

## Follow-Up Work
- Run a manual backup/restore smoke test against a disposable runtime clone before schema migration work.
- For that smoke test, bootstrap users with `.pyanam/bin/python -m tir.admin list-users` and `.pyanam/bin/python -m tir.admin add-user Lyle`; do not use a `user-create` command.
- Consider a dedicated restore preview format for governance files if operator output needs to become more compact.

## Project Anam Alignment Check
- Does not assign the entity a name or personality.
- Does not change `soul.md`, `OPERATIONAL_GUIDANCE.md`, or `BEHAVIORAL_GUIDANCE.md` contents.
- Preserves raw runtime state and governance artifacts as traceable backup material.
- Does not change memory architecture, schema, or prompt loading.
