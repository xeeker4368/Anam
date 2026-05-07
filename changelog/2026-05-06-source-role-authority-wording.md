# Source Role and Origin Cleanup

## Summary

Replaced misleading normal-upload framing around `authority=source_material` with explicit artifact `origin` and `source_role` metadata. New uploaded artifacts are now framed as uploaded source artifacts rather than authority, foundational truth, operational guidance, or core identity.

## Files Changed

- `tir/artifacts/source_roles.py`
- `tir/artifacts/__init__.py`
- `tir/artifacts/ingestion.py`
- `tir/memory/artifact_indexing.py`
- `tir/engine/context.py`
- `tir/api/routes.py`
- `frontend/src/App.jsx`
- `frontend/src/components/RegistryPanel.jsx`
- `tests/test_artifact_ingestion.py`
- `tests/test_artifact_upload_api.py`
- `changelog/2026-05-06-source-role-authority-wording.md`

## Behavior Changed

- New normal uploads default to `origin=user_upload` and `source_role=uploaded_source`.
- New generated files default to `origin=generated` and `source_role=generated_artifact`.
- New generated draft artifacts use `source_role=draft` when created with draft status.
- New artifact metadata no longer writes `authority`.
- New artifact chunks no longer write `authority` metadata.
- New artifact event/content chunk text says `Origin: User upload` and `Source role: Uploaded source`.
- Retrieved artifact context now renders as `role: Uploaded source, origin: User upload`.
- The upload UI no longer sends `authority=source_material`.
- The Registry panel shows “Source role” and “Origin” instead of normal-upload authority wording.

## Transition / Compatibility Behavior

- Deprecated `authority` input remains accepted for old callers during this transition patch.
- Old dev rows/chunks containing `metadata.authority` are mapped to source-role display labels where needed.
- No DB migration or reindex was performed.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_artifact_ingestion.py -v`
- `.pyanam/bin/python -m pytest tests/test_context.py -v`
- `.pyanam/bin/python -m pytest tests/test_artifact_upload_api.py -v`
- `npm --prefix frontend run lint`
- `npm --prefix frontend run build`
- `git diff --check`

## Known Limitations

- Old indexed chunks may still contain old `Authority: source_material` text until DB wipe/rebuild or a future artifact reindex patch.
- `authority` is still accepted as deprecated transition input.
- No recent artifact awareness or context-budget work was added.

## Follow-Up Work

- Remove deprecated `authority` input once all callers use `origin/source_role`.
- Rebuild or reindex old artifact chunks if pre-live DBs are not wiped.
- Consider surfacing normalized display labels from the API later to avoid frontend/backend mapping drift.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not call the entity Anam or Tír.
- Does not assign personality.
- Reduces overclaiming by making uploaded files source artifacts rather than operational truth.
- Preserves raw artifact experience and retrieval behavior.
- Does not change runtime guidance loading, memory architecture, DB schema, autonomy, recent artifact awareness, or `soul.md`.
