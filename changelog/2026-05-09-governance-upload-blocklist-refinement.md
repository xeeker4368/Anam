# Governance Upload Blocklist Refinement

## Summary

Refined normal artifact upload blocking so only true runtime guidance/seed files are hard-blocked, while project reference/control documents can be uploaded as source material.

## Files Changed

- `tir/artifacts/governance_blocklist.py`
- `tir/artifacts/source_roles.py`
- `tir/engine/context.py`
- `tests/test_artifact_ingestion.py`
- `tests/test_artifact_upload_api.py`
- `tests/test_context.py`
- `changelog/2026-05-09-governance-upload-blocklist-refinement.md`

## Behavior Changed

- Hard-blocked filenames are now limited to `soul.md`, `OPERATIONAL_GUIDANCE.md`, and `BEHAVIORAL_GUIDANCE.md`.
- Matching remains basename-only and case-insensitive.
- Project reference/control docs such as `ROADMAP.md`, `PROJECT_STATE.md`, and `DECISIONS.md` are allowed through normal upload/ingestion.
- Added explicit `project_reference` source role support.
- Retrieved artifacts with `source_role=project_reference` are labeled as project reference source material, not runtime guidance.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_artifact_ingestion.py -v`
- `.pyanam/bin/python -m pytest tests/test_artifact_upload_api.py -v`
- `.pyanam/bin/python -m pytest tests/test_context.py -v`
- `git diff --check`

## Known Limitations

- Project reference docs are not auto-detected by filename in v1. Uploaders must explicitly set `source_role=project_reference` to get the specialized context label.

## Follow-Up Work

- Consider dedicated UI affordances for uploading project reference docs with the correct source role.
- Observe whether project-reference uploads need additional provenance fields later.

## Project Anam Alignment Check

- Does not change runtime loading of `soul.md`, `OPERATIONAL_GUIDANCE.md`, or `BEHAVIORAL_GUIDANCE.md`.
- Does not assign the entity a name or personality.
- Preserves source boundaries by distinguishing project reference material from runtime guidance.
