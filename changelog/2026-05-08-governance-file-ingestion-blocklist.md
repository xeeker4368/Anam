# Governance File Ingestion Blocklist

## Summary
- Added a normal artifact-ingestion blocklist for Project Anam governance/runtime filenames.
- Blocked files are rejected before storage, indexing, chunking, or artifact registration.
- Added ingestion and upload API coverage for exact, case-insensitive basename matching.

## Files Changed
- `tir/artifacts/governance_blocklist.py`
- `tir/artifacts/ingestion.py`
- `tests/test_artifact_ingestion.py`
- `tests/test_artifact_upload_api.py`
- `changelog/2026-05-08-governance-file-ingestion-blocklist.md`

## Behavior Changed
- Normal artifact ingestion now rejects allowlisted governance/runtime filenames with:
  `This file is a governance/runtime file and cannot be ingested as normal artifact memory.`
- Matching is exact by basename and case-insensitive.
- Examples blocked: `soul.md`, `Soul.md`, `path/to/soul.md`, `ROADMAP.md`, `roadmap.md`.
- Near misses such as `soul_notes.md` remain allowed.
- Upload API returns HTTP 400 through the existing `ArtifactIngestionError` handling.

## Tests/Checks Run
- `.pyanam/bin/python -m pytest tests/test_artifact_ingestion.py -v`
- `.pyanam/bin/python -m pytest tests/test_artifact_upload_api.py -v`
- `.pyanam/bin/python -m pytest tests/test_backup_restore.py -v`
- `git diff --check`

## Known Limitations
- Existing already-ingested governance files are not removed or reindexed by this patch.
- Intentional governance-file inspection still needs a dedicated admin/self-inspection path later.

## Follow-Up Work
- Add a dedicated read-only governance inspection path if runtime self-inspection becomes an approved feature.
- Consider an admin audit command to detect older artifact rows that match the governance blocklist.

## Project Anam Alignment Check
- Does not assign the entity a name or personality.
- Does not modify `soul.md`, `BEHAVIORAL_GUIDANCE.md`, or runtime guidance contents.
- Reduces source-authority confusion by keeping governance/runtime files out of normal uploaded artifact memory.
- Does not change backup/restore, prompt loading, DB schema, or memory architecture.
