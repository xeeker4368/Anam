# Artifact Provenance Detail Visibility

## Summary

Improved the Registry panel artifact cards with expandable detail disclosures that show file metadata, source/provenance metadata, indexing status, authority, and relative storage information.

## Files Changed

- `frontend/src/components/RegistryPanel.jsx`
- `frontend/src/styles.css`
- `changelog/2026-05-06-artifact-provenance-detail-visibility.md`

## Behavior Changed

- Artifact cards now show authority and indexing status badges when metadata is present.
- Artifact cards now include a native expandable Details disclosure.
- Expanded details show file metadata such as filename, safe filename, MIME type, size, short SHA-256 hash, and relative path.
- Expanded details show source/provenance metadata such as authority, source, created_by, source_type, conversation id, message id, source tool name, and revision_of when present.
- Expanded details show indexing status, artifact type, status, created_at, and updated_at.

## Tests/Checks Run

- `npm --prefix frontend run lint`
- `npm --prefix frontend run build`
- `git diff --check`

## Known Limitations

- No backend payload changes were made.
- No file contents are shown.
- No artifact edit, delete, lineage management, review queue, or file content viewer exists.
- Detail rows depend on metadata already present in the artifact registry API response.

## Follow-Up Work

- Add richer lineage/revision visualizations after artifact relationship semantics are designed.
- Add artifact filtering/search if registry volume grows.
- Consider targeted detail views later if cards become too dense.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not call the entity Anam or Tír.
- Does not assign personality.
- Improves traceability of artifact source experience.
- Keeps uploaded/generated artifacts visible as source material and provenance, not operational guidance, identity, personality, or core belief.
- Does not add mutation actions, DB schema changes, autonomy, review workflow, research cycle behavior, or file content display.
