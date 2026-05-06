# Document Lineage v1

## Summary

Added simple manual artifact lineage using the existing `revision_of` artifact field, with validated upload support and read-only Registry visibility.

## Files Changed

- `tir/memory/db.py`
- `tir/artifacts/__init__.py`
- `tir/artifacts/service.py`
- `tir/api/routes.py`
- `frontend/src/App.jsx`
- `frontend/src/components/RegistryPanel.jsx`
- `frontend/src/styles.css`
- `tests/test_artifacts.py`
- `tests/test_artifact_upload_api.py`
- `tests/test_api_registry_visibility.py`
- `changelog/2026-05-06-document-lineage-v1.md`

## Behavior Changed

- Added an index for `artifacts.revision_of` to support direct revision lookup.
- Artifact service results now include `revised_by_count`.
- Added `list_artifact_revisions(...)` and `count_artifact_revisions(...)`.
- Uploads may include `revision_of` when creating a new artifact revision.
- Upload validation rejects missing, empty, or conflicting revision targets.
- Registry upload UI includes an optional “Revision of artifact ID” field.
- Registry artifact details show both `revision_of` and direct `revised_by_count`.
- Older artifact status is not automatically mutated when a revision is uploaded.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_artifacts.py -v`
- `.pyanam/bin/python -m pytest tests/test_artifact_upload_api.py -v`
- `.pyanam/bin/python -m pytest tests/test_api_registry_visibility.py -v`
- `npm --prefix frontend run lint`
- `npm --prefix frontend run build`
- `git diff --check`

## Known Limitations

- `revision_of` is the only lineage relationship in v1.
- No supersedes field or automatic status mutation exists.
- No graph UI or revision selector exists.
- The upload UI uses a plain artifact-id text field.
- Lineage is manual and not inferred from file names or content.

## Follow-Up Work

- Add a revision selector or artifact picker if operator ergonomics require it.
- Design richer lineage relationships such as supersedes, derived_from, related_to, and summarized_by.
- Add a dedicated artifact detail view if Registry cards become too dense.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not call the entity Anam or Tír.
- Does not assign personality.
- Preserves older versions as historical source context rather than overwriting them.
- Keeps lineage traceable and inspectable.
- Does not add mutation actions, automatic authority promotion, automatic relationship inference, DB schema shape changes, autonomy, review workflow, research cycle behavior, or file content display.
