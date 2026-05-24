# Backup Restore Atomic Hardening v1

## Summary

Hardened active restore behavior so missing backup payloads and directory copy failures cannot leave runtime destinations missing, empty, or half-restored.

## Files Changed

- `tir/ops/backup.py`
- `tests/test_backup_restore.py`
- `changelog/2026-05-22-backup-restore-atomic-hardening-v1.md`

## Behavior Changed

- Active restore now validates all expected backup payload files/directories before creating the pre-restore safety backup or modifying destinations.
- File restore verifies the source file first, copies to a sibling temporary file, then atomically replaces the destination.
- Directory restore verifies the source directory first, copies to a sibling temporary directory, then swaps only after the copy succeeds.
- If directory copy fails, the original destination remains intact.
- Temporary restore paths are cleaned up on success and normal failure paths.
- Existing restore CLI shape, dry-run behavior, force requirement, backup format, and backup-restore-verify command behavior are preserved.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_backup_restore.py -v`
- `.pyanam/bin/python -m pytest tests/test_admin.py -v`
- `.pyanam/bin/python -m pytest`
- `git diff --check`

## Known Limitations

- Directory replacement cannot be a single filesystem-level atomic operation on all platforms, but this patch avoids deleting the live destination before the replacement copy has succeeded and attempts to restore the original if a later swap step fails.

## Follow-Up Work

- Consider adding operator-facing restore audit output in a separate patch if go-live reset implementation needs richer diagnostics.

## Project Anam Alignment Check

- Did not assign the entity a name.
- Did not call the entity Anam or Tír.
- Did not assign personality, values, avatar, or identity.
- Preserved raw experience and runtime continuity by making destructive restore safer.
- Did not change backup format, DB schema, Chroma schema, research behavior, Moltbook/web behavior, auth/user mode, prompts, guidance files, `soul.md`, model config, or UI.
