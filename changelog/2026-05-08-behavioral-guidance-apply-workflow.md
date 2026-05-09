# Behavioral Guidance Apply-to-File Workflow v1

## Summary

Added a CLI-only workflow for applying an approved addition proposal to `BEHAVIORAL_GUIDANCE.md`.

## Files Changed

- `tir/behavioral_guidance/apply.py`
- `tir/admin.py`
- `tests/test_behavioral_guidance_apply.py`
- `tests/test_admin.py`

## Behavior Changed

- Added `tir.admin behavioral-guidance-proposal-apply PROPOSAL_ID`.
- Dry-run is the default and prints the exact append block.
- `--write` appends the approved guidance block and marks the proposal `applied`.
- Application records existing `applied_by_user_id`, `applied_at`, and `apply_note` fields.
- Only approved addition proposals can be applied in v1.
- Duplicate proposal IDs already present in the file are rejected.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_behavioral_guidance_apply.py -v`
- `.pyanam/bin/python -m pytest tests/test_behavioral_guidance.py -v`
- `.pyanam/bin/python -m pytest tests/test_context.py -v`
- `.pyanam/bin/python -m pytest tests/test_admin.py -v`
- `git diff --check`

## Known Limitations

- Addition-only v1; removal and revision apply mechanics are intentionally deferred.
- No UI apply button.
- `BEHAVIORAL_GUIDANCE.md` is still not loaded into runtime context.
- File write and database status update are not one atomic transaction.

## Follow-Up Work

- Design explicit removal/revision application mechanics.
- Add UI apply controls only after the CLI workflow is proven safe.
- Add repair/reporting for file/status drift if needed.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not assign a fixed personality.
- Keeps behavioral guidance AI-proposed and admin-applied.
- Does not modify `soul.md` or `OPERATIONAL_GUIDANCE.md`.
- Does not change runtime prompt loading.
